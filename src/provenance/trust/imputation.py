"""Bridge the trained imputation models (§7.2, ``models.hstgat``) into the trust load.

Lives in ``trust`` rather than ``io`` because it has to import the graph and neural
stack (:mod:`provenance.graph`, :mod:`provenance.models.hstgat`) to run live
inference, and the layering test (``tests/architecture/test_layering.py``) forbids
``io`` from importing either — ``trust`` is the layer allowed to depend on both
(§ pipeline order: ``... -> audit -> trust -> graph -> models -> explain``). The
loader (io) only ever imports this module, never ``graph``/``models`` directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pandas as pd

from provenance.schema import canonical as C

if TYPE_CHECKING:  # pragma: no cover
    from provenance.io.loaders import StationLocation


def stations_by_parameter(frame: pd.DataFrame) -> dict[str, set[str]]:
    """Which stations carry each parameter, from the data actually loaded."""
    out: dict[str, set[str]] = {}
    for parameter, station in zip(
        frame[C.PARAMETER].astype(str), frame[C.STATION_ID].astype(str), strict=True
    ):
        out.setdefault(parameter, set()).add(station)
    return out


@dataclass(frozen=True, slots=True)
class ImputationLookup:
    """Per-load cache of the trained imputation models' station/hour uncertainty.

    Built once per ``load_frame`` call, not per station or per instant: each
    parameter's graph batch is built at most once (lazily, on first use) and reused
    across every station and every scoring instant that needs it — one batch build
    per parameter over a whole load, not one per (station, instant) pair. Absent any
    trained artefact for a parameter, that parameter simply never enters ``models``,
    and every station falls back to the raw placeholder for it (graceful degradation,
    standing rule 6).
    """

    frame: pd.DataFrame
    points: list[Any]
    wind: Any
    cfg: dict[str, Any]
    models: dict[str, Any]
    _batches: dict[str, Any] = field(default_factory=dict)
    _sigma: dict[tuple[str, pd.Timestamp], dict[str, float]] = field(default_factory=dict)

    @classmethod
    def build(
        cls, frame: pd.DataFrame, station_meta: dict[str, StationLocation]
    ) -> ImputationLookup:
        from provenance.config.loading import load_graph_config
        from provenance.graph.build import station_points_from_metadata
        from provenance.graph.wind import WindField
        from provenance.models.hstgat.data import imputable_parameters
        from provenance.models.hstgat.imputation_serving import available_imputation_models

        points = station_points_from_metadata(dict(station_meta))
        if not points:
            # No coordinates for this drop (e.g. the synthetic corpus without a
            # Location column) - the graph cannot be built, so every station stays
            # on the placeholder. Cheap: no model is even loaded.
            return cls(frame, [], None, {}, {})
        from provenance.schema.observe import observe

        cfg = load_graph_config()
        wind = WindField.from_frame(frame)
        parameters = imputable_parameters(frame)
        checksum = observe(frame).checksum
        models = available_imputation_models(parameters, data_checksum=checksum)
        return cls(frame, points, wind, cfg, models)

    def _batch_for(self, parameter: str) -> Any:
        from provenance.models.hstgat.imputation_serving import build_imputation_batch

        batch = self._batches.get(parameter)
        if batch is None:
            loaded = self.models[parameter]
            batch = build_imputation_batch(loaded, self.frame, self.points, self.wind, self.cfg)
            self._batches[parameter] = batch
        return batch

    def modelled_uncertainty(
        self, station_id: str, station_parameters: list[str], at: pd.Timestamp
    ) -> float | None:
        """Mean modelled uncertainty across this station's modelled parameters, or None."""
        from provenance.models.hstgat.imputation_serving import sigma_at

        values: list[float] = []
        for parameter in station_parameters:
            loaded = self.models.get(parameter)
            if loaded is None:
                continue
            key = (parameter, at)
            per_station = self._sigma.get(key)
            if per_station is None:
                per_station = sigma_at(loaded, self._batch_for(parameter), at)
                self._sigma[key] = per_station
            value = per_station.get(station_id)
            if value is not None:
                values.append(value)
        if not values:
            return None
        return sum(values) / len(values)

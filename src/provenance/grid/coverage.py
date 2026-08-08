"""The coverage model - the part the brief warns is easiest to get wrong.

Four quantities are kept strictly separate, because conflating them is what
inflates the defect rate:

* **expected** cells - every (station, parameter, tick) the network intends to
  produce, including sensors a station structurally lacks.
* **observed** cells - readings actually present.
* **absent** cells - covered ticks with no reading (missingness = R01).
* **structurally excluded** cells - ticks for a (station, parameter) the station
  never carried. Reported separately, and in neither side of the defect rate.

By construction ``expected == observed + absent + structurally_excluded``.

Cadence is inferred per series from the data (air and groundwater tick hourly,
noise ticks daily), never assumed, so reindexing a daily series against an hourly
grid cannot invent thousands of phantom absences.

Structural absence is inferred, not hardcoded: a station is judged to lack a
sensor when a parameter carried by a majority of the network is entirely absent
from that station. That rule recovers the two documented cases (KER15 has no wind,
KER02 has no groundwater file) without naming a single station in code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from provenance.config.loading import load_schema_assumptions
from provenance.schema import canonical as C

_HOUR = pd.Timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class SeriesGrid:
    """The complete expected timeline for one covered (station, parameter)."""

    station_id: str
    parameter: str
    cadence: pd.Timedelta
    start: pd.Timestamp
    end: pd.Timestamp
    n_expected: int
    n_observed: int
    absent_timestamps: tuple[pd.Timestamp, ...]

    @property
    def n_absent(self) -> int:
        return len(self.absent_timestamps)


@dataclass(frozen=True, slots=True)
class StructuralAbsence:
    """A (station, parameter) the station never carried. A coverage fact, not a defect."""

    station_id: str
    parameter: str
    domain: str
    reason_code: str  # R18 (single parameter) or R19 (a whole source/domain)
    n_excluded_cells: int


@dataclass(frozen=True, slots=True)
class CoverageModel:
    stations: tuple[str, ...]
    parameters: tuple[str, ...]
    series_grids: dict[tuple[str, str], SeriesGrid]
    structural_absences: tuple[StructuralAbsence, ...]
    param_domains: dict[str, str]
    global_start: pd.Timestamp
    global_end: pd.Timestamp
    coverage_matrix: pd.DataFrame = field(default_factory=pd.DataFrame)

    # -- the four quantities -------------------------------------------------
    def n_observed_cells(self) -> int:
        return sum(g.n_observed for g in self.series_grids.values())

    def n_absent_cells(self) -> int:
        return sum(g.n_absent for g in self.series_grids.values())

    def n_covered_cells(self) -> int:
        """Denominator of the defect rate: observed + absent."""
        return sum(g.n_expected for g in self.series_grids.values())

    def n_structurally_excluded_cells(self) -> int:
        return sum(s.n_excluded_cells for s in self.structural_absences)

    def n_expected_cells(self) -> int:
        return self.n_covered_cells() + self.n_structurally_excluded_cells()

    def covered_pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple(self.series_grids.keys())

    def absent_frame(self) -> pd.DataFrame:
        """Every absent tick as rows (station_id, parameter, timestamp_utc)."""
        rows = [
            {C.STATION_ID: g.station_id, C.PARAMETER: g.parameter, C.TIMESTAMP: ts}
            for g in self.series_grids.values()
            for ts in g.absent_timestamps
        ]
        return pd.DataFrame(rows, columns=[C.STATION_ID, C.PARAMETER, C.TIMESTAMP])


# Plain-language domain words, used as a fallback when the vendor token (which is
# Hungarian for the real export) is not present - e.g. the synthetic fixtures name
# their files "<station>_air.csv" / "<station>_water.csv".
_DOMAIN_WORDS: tuple[str, ...] = ("groundwater", "water", "air", "noise", "soil")


def _domain_of_source(source_file: str, file_domains: dict[str, str]) -> str:
    for token, domain in file_domains.items():
        if token in source_file:
            return domain
    lowered = source_file.lower()
    for word in _DOMAIN_WORDS:
        if word in lowered:
            return word
    return "unknown"


def _infer_cadence(timestamps: pd.Series) -> pd.Timedelta:
    """Modal gap between consecutive readings; default to hourly if undecidable."""
    ordered = pd.Series(pd.to_datetime(timestamps).sort_values().unique())
    if len(ordered) < 2:
        return _HOUR
    deltas = ordered.diff().dropna()
    positive = deltas[deltas > pd.Timedelta(0)]
    if positive.empty:
        return _HOUR
    return pd.Timedelta(positive.mode().iloc[0])


def build_coverage(frame: pd.DataFrame, *, majority: float = 0.5) -> CoverageModel:
    """Build the coverage model for a canonical long frame."""
    assumptions = load_schema_assumptions()
    file_domains: dict[str, str] = assumptions["green_sentinel"]["file_domains"]

    stations = tuple(sorted(frame[C.STATION_ID].unique()))
    parameters = tuple(sorted(frame[C.PARAMETER].unique()))
    global_start = pd.Timestamp(frame[C.TIMESTAMP].min())
    global_end = pd.Timestamp(frame[C.TIMESTAMP].max())

    # Parameter -> domain, read from the source files the parameter appears in.
    param_domains: dict[str, str] = {}
    for parameter, g in frame.groupby(C.PARAMETER):
        src = str(g[C.SOURCE_FILE].iloc[0])
        param_domains[str(parameter)] = _domain_of_source(src, file_domains)

    # Which stations carry each parameter, and each parameter's network cadence.
    carriers: dict[str, set[str]] = {}
    network_cadence: dict[str, pd.Timedelta] = {}
    for parameter, g in frame.groupby(C.PARAMETER):
        carriers[str(parameter)] = set(g[C.STATION_ID].unique())
        network_cadence[str(parameter)] = _infer_cadence(g[C.TIMESTAMP])

    n_stations = len(stations)
    threshold = math.ceil(majority * n_stations)
    network_standard = {p for p, sts in carriers.items() if len(sts) >= threshold}

    # Covered series grids, one per (station, parameter) with >= 1 reading.
    series_grids: dict[tuple[str, str], SeriesGrid] = {}
    for key, g in frame.groupby([C.STATION_ID, C.PARAMETER]):
        station, parameter = str(key[0]), str(key[1])
        cadence = _infer_cadence(g[C.TIMESTAMP])
        start = pd.Timestamp(g[C.TIMESTAMP].min())
        end = pd.Timestamp(g[C.TIMESTAMP].max())
        full = pd.date_range(start=start, end=end, freq=cadence)
        observed_ts = pd.DatetimeIndex(pd.to_datetime(g[C.TIMESTAMP]).unique())
        absent = full.difference(observed_ts)
        series_grids[(str(station), str(parameter))] = SeriesGrid(
            station_id=str(station),
            parameter=str(parameter),
            cadence=cadence,
            start=start,
            end=end,
            n_expected=len(full),
            n_observed=len(observed_ts),
            absent_timestamps=tuple(absent),
        )

    structural = _structural_absences(
        stations=stations,
        network_standard=network_standard,
        carriers=carriers,
        param_domains=param_domains,
        network_cadence=network_cadence,
        global_start=global_start,
        global_end=global_end,
    )

    coverage_matrix = frame.pivot_table(
        index=C.STATION_ID, columns=C.PARAMETER, values=C.VALUE, aggfunc="count", fill_value=0
    )

    return CoverageModel(
        stations=stations,
        parameters=parameters,
        series_grids=series_grids,
        structural_absences=structural,
        param_domains=param_domains,
        global_start=global_start,
        global_end=global_end,
        coverage_matrix=coverage_matrix,
    )


def _structural_absences(
    *,
    stations: tuple[str, ...],
    network_standard: set[str],
    carriers: dict[str, set[str]],
    param_domains: dict[str, str],
    network_cadence: dict[str, pd.Timedelta],
    global_start: pd.Timestamp,
    global_end: pd.Timestamp,
) -> tuple[StructuralAbsence, ...]:
    """A station that lacks a network-standard sensor entirely.

    When a station is missing *every* standard parameter of a domain, that is one
    source-level absence (R19, e.g. a whole groundwater file); missing some but
    not all standard parameters of a domain is per-parameter (R18, e.g. no wind).
    """
    # Standard parameters grouped by domain.
    domain_standard: dict[str, set[str]] = {}
    for p in network_standard:
        domain_standard.setdefault(param_domains.get(p, "unknown"), set()).add(p)

    out: list[StructuralAbsence] = []
    for station in stations:
        for domain, std_params in domain_standard.items():
            missing = {p for p in std_params if station not in carriers[p]}
            if not missing:
                continue
            source_level = missing == std_params and len(std_params) > 1
            for p in sorted(missing):
                cells = _cells_between(global_start, global_end, network_cadence[p])
                out.append(
                    StructuralAbsence(
                        station_id=station,
                        parameter=p,
                        domain=domain,
                        reason_code="R19" if source_level else "R18",
                        n_excluded_cells=cells,
                    )
                )
    return tuple(sorted(out, key=lambda s: (s.station_id, s.parameter)))


def _cells_between(start: pd.Timestamp, end: pd.Timestamp, cadence: pd.Timedelta) -> int:
    if cadence <= pd.Timedelta(0):
        return 0
    return int((end - start) / cadence) + 1


def write_coverage_debug(model: CoverageModel, path: Path) -> Path:  # pragma: no cover
    """Optional: dump the coverage matrix for eyeballing. Not used by the audit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    model.coverage_matrix.to_csv(path)
    return path

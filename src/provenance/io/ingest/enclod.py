"""The Enclod traffic-counter file-drop adapter.

Enclod archive CSVs hold cumulative 15-minute counters (see
``schema_assumptions.yaml``: ``enclod_traffic``). The counter columns are marked
``unconfirmed`` there, so this adapter *discovers* the files but refuses to invent
a schema for them: ``read()`` fails loudly until the columns are confirmed and the
reset-aware differencing from ``io/counter_repair.py`` is wired in. Discovery is
still useful — it proves the drop is present without committing to a parse.

``counter_locations`` is the one exception, mirroring ``gtfs.stops_with_route_counts``:
each counter's ``lat``/``lng`` are observed, static, per-physical-device columns
(ADR 0005), independent of the cumulative vehicle-count parse that ``read()`` still
refuses. Placing a counter on the map commits to nothing about differencing it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from provenance.config.loading import load_schema_assumptions
from provenance.io.ingest.base import SourceNotReady
from provenance.schema.canonical import SchemaDriftError


class EnclodAdapter:
    source = "enclod_traffic"
    kind = "readings"

    def discover(self, root: Path) -> list[Path]:
        root = Path(root)
        return sorted(root.glob("**/Enclod*/**/*.csv")) + sorted(root.glob("**/enclod*.csv"))

    def read(self, root: Path) -> pd.DataFrame:
        cfg = load_schema_assumptions()["enclod_traffic"]
        if cfg.get("status") != "confirmed" or not cfg.get("counter_column"):
            raise SchemaDriftError(
                "Enclod counter columns are unconfirmed in schema_assumptions.yaml "
                "(enclod_traffic.status). Confirm timestamp/counter columns from a real "
                "archive CSV before enabling this adapter; the reset-aware differencing "
                "in io/counter_repair.py then maps the cumulative counters to canonical."
            )
        raise NotImplementedError(  # pragma: no cover - reached only once columns are confirmed
            "Enclod parsing lands once the columns above are confirmed."
        )


def counter_locations(root: Path) -> pd.DataFrame:
    """Real per-counter coordinates: ``counter_id, name, lat, lon``.

    Reads only the ``uuid``/``nick``/``lat``/``lng`` columns recorded as *observed*
    in ``schema_assumptions.yaml`` — never the cumulative measure columns, so this
    commits to nothing the reset-aware repair step in ``io/counter_repair.py``
    hasn't confirmed yet. A counter's coordinate is a fixed property of the
    physical device: reading it from every archive file and keeping the first
    occurrence per id is a real, observed value, not an inference.

    Raises :class:`SourceNotReady` when no Enclod archive CSVs are found under
    ``root`` — this is reference data with no live-vs-absent distinction, so the
    caller (the reference API) reports "not loaded" rather than a coordinate list.
    """
    root = Path(root)
    files = EnclodAdapter().discover(root)
    if not files:
        raise SourceNotReady(f"No Enclod archive CSVs found under {root}.")

    cfg = load_schema_assumptions()["enclod_traffic"]
    id_col = cfg["counter_id_column"]
    name_col = cfg["counter_name_column"]
    lat_col = cfg["latitude_column"]
    lon_col = cfg["longitude_column"]

    frames = [
        pd.read_csv(f, usecols=[id_col, name_col, lat_col, lon_col], dtype=str) for f in files
    ]
    combined = pd.concat(frames, ignore_index=True)
    combined[lat_col] = pd.to_numeric(combined[lat_col], errors="coerce")
    combined[lon_col] = pd.to_numeric(combined[lon_col], errors="coerce")
    combined = combined.dropna(subset=[lat_col, lon_col])
    combined = combined.drop_duplicates(subset=[id_col], keep="first")
    combined = combined.rename(
        columns={id_col: "counter_id", name_col: "name", lat_col: "lat", lon_col: "lon"}
    )
    cols = ["counter_id", "name", "lat", "lon"]
    return combined[cols].sort_values("counter_id").reset_index(drop=True)

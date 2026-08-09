"""The GTFS static file-drop adapter (reference source).

GTFS static is transit reference data — stops, routes, ridership context — not a
time series of readings. It feeds the PopulationExposure factor of the Risk score
(§7.8), which was stubbed at 1.0 until phase 7. ``read()`` still refuses to return a
readings frame it has no business producing; the phase-7 addition is
``stops_with_route_counts``, which parses the bundle into the stop table the
exposure layer aggregates (:mod:`provenance.grid.exposure`).

A bundle is either an unpacked directory of ``.txt`` files or a ``*gtfs*.zip``; both
are read the same way. Only the columns the exposure proxy needs are parsed — stop
coordinates and, where ``trips.txt``/``stop_times.txt`` are present, the number of
distinct routes serving each stop. Missing optional files degrade to one route per
stop rather than failing (standing rule 6): a coordinate is enough to place a stop.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from provenance.io.ingest.base import SourceNotReady


class GtfsAdapter:
    source = "gtfs"
    kind = "reference"

    def discover(self, root: Path) -> list[Path]:
        root = Path(root)
        return (
            sorted(root.glob("**/stops.txt"))
            + sorted(root.glob("**/routes.txt"))
            + sorted(root.glob("**/*gtfs*.zip"))
        )

    def read(self, root: Path) -> pd.DataFrame:
        raise SourceNotReady(
            "GTFS static is reference data feeding PopulationExposure (Risk, §7.8). "
            "It produces no readings frame; use stops_with_route_counts() for the "
            "transit-corridor layer."
        )


def find_gtfs_bundle(root: Path) -> Path | None:
    """Locate a GTFS bundle under ``root``: an unpacked ``stops.txt`` dir or a zip."""
    root = Path(root)
    stops = sorted(root.glob("**/stops.txt"))
    if stops:
        return stops[0].parent
    zips = sorted(root.glob("**/*gtfs*.zip"))
    return zips[0] if zips else None


def _read_member(bundle: Path, name: str) -> pd.DataFrame | None:
    """Read one GTFS table from a directory or a zip, or None when it is absent."""
    if bundle.is_dir():
        path = bundle / name
        if not path.exists():
            return None
        return pd.read_csv(path, dtype=str)
    with zipfile.ZipFile(bundle) as zf:
        if name not in zf.namelist():
            return None
        with zf.open(name) as fh:
            return pd.read_csv(io.BytesIO(fh.read()), dtype=str)


def stops_with_route_counts(bundle: Path) -> pd.DataFrame:
    """Parse a GTFS bundle into ``stop_id, stop_lat, stop_lon, n_routes``.

    ``n_routes`` is the count of distinct routes serving each stop, joined through
    ``stop_times`` → ``trips`` → ``route_id`` when those files exist; otherwise every
    stop is credited with a single route. Rows without a numeric coordinate are
    dropped rather than defaulted, so a malformed stop never lands in a corridor.
    """
    bundle = Path(bundle)
    stops = _read_member(bundle, "stops.txt")
    if stops is None or stops.empty:
        raise SourceNotReady(f"No stops.txt in GTFS bundle {bundle}.")
    stops = stops.copy()
    stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
    stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
    stops = stops.dropna(subset=["stop_lat", "stop_lon"])

    n_routes = _route_counts_per_stop(bundle)
    stops["n_routes"] = (
        stops["stop_id"].map(n_routes).fillna(1.0).astype(float) if n_routes else 1.0
    )
    cols = ["stop_id", "stop_lat", "stop_lon", "n_routes"]
    return stops[cols].sort_values("stop_id").reset_index(drop=True)


def _route_counts_per_stop(bundle: Path) -> dict[str, int]:
    """Distinct routes serving each stop, or an empty map when the join is unavailable."""
    trips = _read_member(bundle, "trips.txt")
    stop_times = _read_member(bundle, "stop_times.txt")
    if trips is None or stop_times is None:
        return {}
    merged = stop_times.merge(trips[["trip_id", "route_id"]], on="trip_id", how="left")
    grouped = merged.dropna(subset=["route_id"]).groupby("stop_id")["route_id"].nunique()
    return {str(k): int(v) for k, v in grouped.items()}

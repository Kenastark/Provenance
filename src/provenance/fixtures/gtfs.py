"""A deterministic synthetic GTFS bundle for the transit-corridor exposure layer.

The real Debrecen GTFS feed is unconfirmed (schema_assumptions.yaml) and no bundle
ships in the repo, so — exactly as the synthetic readings corpus stands in for the
real export — this writes a **seeded, synthetic** GTFS bundle around a set of station
coordinates so the PopulationExposure layer (:mod:`provenance.grid.exposure`) has a
real file to aggregate in tests and in the offline demo.

It is synthetic and says so: the stop coordinates are generated, the route counts are
assigned from a deterministic per-station weight, and nothing here is passed off as
the municipality's feed. The one thing it is faithful about is *shape* — real
``stops.txt`` / ``routes.txt`` / ``trips.txt`` / ``stop_times.txt`` columns — so the
same parser reads this and a real bundle unchanged. Service intensity is deliberately
spread across stations (a busy core, quiet edges) so exposure varies and the Risk
ranking has something to rank on.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

# Roughly one metre in decimal degrees at Debrecen's latitude, for placing stops
# inside a walkable corridor of a station. A modelling constant for the fixture, not
# a data-derived value.
_DEG_PER_M_LAT = 1.0 / 111_320.0
_DEG_PER_M_LON = 1.0 / 74_000.0


def _weight_for(station_id: str, *, levels: int = 6) -> int:
    """A stable 1..levels service weight for a station, from a hash of its id.

    Deterministic and platform-independent (hashlib, not the salted built-in
    ``hash``), so two runs place the same number of stops around each station
    (standing rule 8).
    """
    digest = hashlib.sha256(station_id.encode("utf-8")).hexdigest()
    return 1 + int(digest, 16) % levels


def generate_gtfs(
    points: dict[str, tuple[float, float]], *, radius_m: float = 350.0
) -> dict[str, pd.DataFrame]:
    """Build the four GTFS tables around ``points`` (station_id → (lat, lon)).

    Each station gets ``weight`` stops within ``radius_m``, and each of its stops is
    served by ``weight`` routes, so a heavier station carries a higher route-weighted
    service intensity. Every figure is rounded so the written files are byte-stable.
    """
    stops_rows: list[dict[str, object]] = []
    routes_rows: list[dict[str, object]] = []
    trips_rows: list[dict[str, object]] = []
    stop_times_rows: list[dict[str, object]] = []

    for sid, (lat, lon) in sorted(points.items()):
        weight = _weight_for(sid)
        for r in range(weight):
            route_id = f"R-{sid}-{r}"
            routes_rows.append(
                {"route_id": route_id, "route_short_name": f"{sid[-2:]}{r}", "route_type": "3"}
            )
            trip_id = f"T-{sid}-{r}"
            trips_rows.append({"route_id": route_id, "service_id": "WD", "trip_id": trip_id})
        for i in range(weight):
            stop_id = f"S-{sid}-{i}"
            # Fan the stops out on a small deterministic ring inside the corridor.
            ring = (i + 1) / (weight + 1)
            dlat = round(radius_m * ring * _DEG_PER_M_LAT * (1 if i % 2 == 0 else -1), 6)
            dlon = round(radius_m * ring * _DEG_PER_M_LON * (1 if i % 3 == 0 else -1), 6)
            stops_rows.append(
                {
                    "stop_id": stop_id,
                    "stop_name": f"{sid} stop {i}",
                    "stop_lat": round(lat + dlat, 6),
                    "stop_lon": round(lon + dlon, 6),
                }
            )
            # Every route at this station calls at every one of its stops — enough to
            # make n_routes-per-stop equal the station weight through the real join.
            for r in range(weight):
                stop_times_rows.append(
                    {
                        "trip_id": f"T-{sid}-{r}",
                        "stop_id": stop_id,
                        "stop_sequence": str(i),
                    }
                )

    return {
        "stops": pd.DataFrame(stops_rows),
        "routes": pd.DataFrame(routes_rows),
        "trips": pd.DataFrame(trips_rows),
        "stop_times": pd.DataFrame(stop_times_rows),
    }


def write_gtfs_bundle(out_dir: Path, points: dict[str, tuple[float, float]]) -> Path:
    """Write a synthetic GTFS bundle (the four ``.txt`` files) under ``out_dir/gtfs``."""
    tables = generate_gtfs(points)
    bundle = Path(out_dir) / "gtfs"
    bundle.mkdir(parents=True, exist_ok=True)
    tables["stops"].to_csv(bundle / "stops.txt", index=False)
    tables["routes"].to_csv(bundle / "routes.txt", index=False)
    tables["trips"].to_csv(bundle / "trips.txt", index=False)
    tables["stop_times"].to_csv(bundle / "stop_times.txt", index=False)
    return bundle

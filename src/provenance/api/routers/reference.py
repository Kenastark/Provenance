"""Reference-layer endpoints: real coordinates for non-station map features.

Bus stops and traffic counters are not part of the station trust surface — they
carry no readings, no trust score, no reason codes. They are static context the map
can place *if and only if* real coordinates exist for them (never
``synthetic-provisional`` graph placeholders, see ``graph/topology.py``). Each
endpoint reports ``available=False`` rather than an empty list when its source drop
is absent, so the frontend can tell "nothing here" from "not loaded" (standing
rule 3) and disable the layer toggle honestly instead of rendering nothing
silently.

Both handlers do their own file I/O (no database row for either source), so they
are plain ``def``s: FastAPI runs a sync endpoint in a worker thread rather than
blocking the event loop.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from provenance.api.auth import Role
from provenance.api.deps import get_data_raw, require
from provenance.api.schemas import (
    BusStopOut,
    ReferenceCountersOut,
    ReferenceStopsOut,
    TrafficCounterOut,
)
from provenance.io.ingest.base import SourceNotReady
from provenance.io.ingest.enclod import counter_locations
from provenance.io.ingest.gtfs import find_gtfs_bundle, stops_with_route_counts

router = APIRouter(prefix="/v1/reference", tags=["reference"])


@router.get("/bus-stops", response_model=ReferenceStopsOut)
def bus_stops(
    data_raw: Path = Depends(get_data_raw),
    _: Role = Depends(require(Role.PUBLIC_READ)),
) -> ReferenceStopsOut:
    bundle = find_gtfs_bundle(data_raw)
    if bundle is None:
        return ReferenceStopsOut(available=False, stops=[])
    stops = stops_with_route_counts(bundle)
    return ReferenceStopsOut(
        available=True,
        stops=[
            BusStopOut(
                stop_id=str(row["stop_id"]),
                lat=float(row["stop_lat"]),
                lon=float(row["stop_lon"]),
                n_routes=float(row["n_routes"]),
            )
            for row in stops.to_dict("records")
        ],
    )


@router.get("/traffic-counters", response_model=ReferenceCountersOut)
def traffic_counters(
    data_raw: Path = Depends(get_data_raw),
    _: Role = Depends(require(Role.PUBLIC_READ)),
) -> ReferenceCountersOut:
    try:
        counters = counter_locations(data_raw)
    except SourceNotReady:
        return ReferenceCountersOut(available=False, counters=[])
    return ReferenceCountersOut(
        available=True,
        counters=[
            TrafficCounterOut(
                counter_id=str(row["counter_id"]),
                name=str(row["name"]),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
            )
            for row in counters.to_dict("records")
        ],
    )

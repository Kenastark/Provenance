"""Graph endpoint: the HST-GAT's attention, for the map overlay.

``GET /v1/graph/attention`` answers "which neighbours did the learned model lean on,
right now" (§8) — a read-out of the HST-GAT's attention weights, never an accuracy
claim (standing rule 4). It is reachable only when a trained artefact exists and its
target parameter is present in the currently loaded data; otherwise the response
degrades honestly with ``available=False`` and a reason a human (and the map's layer
toggle) can read (standing rule 6) — never a silent empty overlay, and never an error
for what is the normal pre-training state.

The forward pass is CPU-bound, so it runs off the event loop in a worker thread, like
the explain endpoint's SHAP computation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.schemas import AttentionOverlayOut
from provenance.io.db import repository as repo

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pandas as pd

    from provenance.io.db import models as m

router = APIRouter(prefix="/v1/graph", tags=["graph"])

_NOT_TRAINED_REASON = (
    "The HST-GAT has not been trained. Run `prov models train-hstgat` to enable the "
    "learned attention overlay."
)
_TARGET_ABSENT_REASON = (
    "The trained HST-GAT's target parameter is not present in the currently loaded "
    "data, so no attention overlay can be computed."
)


@router.get("/attention", response_model=AttentionOverlayOut)
async def get_attention_overlay(
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.PUBLIC_READ)),
) -> AttentionOverlayOut:
    from provenance.models.hstgat import store

    # A cheap file-existence check first (models_status.py's pattern), so the common
    # pre-training demo state never pays for a network-wide frame read.
    if store.latest_stem() is None:
        return AttentionOverlayOut(available=False, reason=_NOT_TRAINED_REASON)

    frame = await repo.network_frame(session)
    stations = await repo.list_stations(session, limit=100_000, after=None)
    result = await run_in_threadpool(_compute_overlay, frame, stations)
    if result is None:
        return AttentionOverlayOut(available=False, reason=_TARGET_ABSENT_REASON)
    return AttentionOverlayOut(available=True, **result)


def _compute_overlay(frame: pd.DataFrame, stations: Sequence[m.Station]) -> dict[str, Any] | None:
    """Load the HST-GAT and build the overlay from the DB's current frame. Off-loop."""
    from provenance.config.loading import load_graph_config
    from provenance.graph.topology import StationPoint
    from provenance.graph.wind import WindField
    from provenance.models.hstgat import store
    from provenance.models.hstgat.attention import attention_overlay
    from provenance.schema import canonical as C

    # Warmed at startup (api/app.py lifespan); this is a cache hit on the request path.
    loaded = store.load_latest_cached()
    if loaded is None:
        return None
    present = set(frame[C.PARAMETER].astype(str).unique()) if not frame.empty else set()
    if loaded.target_parameter not in present:
        return None
    points = [
        StationPoint(station_id=s.station_id, lat=s.lat, lon=s.lon)
        for s in stations
        if s.lat is not None and s.lon is not None
    ]
    wind = WindField.from_frame(frame)
    cfg = load_graph_config()
    try:
        overlay = attention_overlay(loaded, frame, points, wind, cfg)
    except ValueError:
        # No mapped station carries the target parameter (e.g. no station with
        # coordinates measures it) — a coverage mismatch, not a code bug.
        return None
    return {
        "reason": None,
        "at": overlay["at"],
        "target_parameter": overlay["target_parameter"],
        "relations": overlay["relations"],
    }

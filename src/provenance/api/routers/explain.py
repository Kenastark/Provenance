"""Explain endpoint: per-defect SHAP attributions, or an honest degraded reason.

``GET /v1/explain/{defect_id}`` returns why a flagged reading is what it is. When the
model artefacts are present it explains the weather-predicted value with SHAP and
reports the residual and fault class; when they are absent it returns the statistics-
layer reason, flagged degraded (standing rule 6). Either way the response carries a
sentence a human can read — it is never a bare set of weights.

The CPU-bound work (loading the models, running the classifier, computing SHAP) is
pushed to a worker thread so it never blocks the event loop.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.errors import ProblemException
from provenance.api.schemas import ExplainOut
from provenance.config.settings import get_settings
from provenance.explain.service import DefectRef, explain_defect
from provenance.io.db import repository as repo

router = APIRouter(prefix="/v1/explain", tags=["explain"])

# Defect ids are positive and stored as signed 64-bit integers; bounding the path
# param keeps an out-of-range id a 422 (client error) rather than a database overflow
# surfacing as a 500 (the schemathesis "never a server error" gate).
_MAX_DEFECT_ID = 9_223_372_036_854_775_807


@router.get("/{defect_id}", response_model=ExplainOut)
async def get_explain(
    defect_id: int = Path(ge=1, le=_MAX_DEFECT_ID),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.RESEARCHER)),
) -> ExplainOut:
    defect = await repo.get_defect(session, defect_id)
    if defect is None:
        raise ProblemException(404, f"No defect with id {defect_id}.")

    ref = DefectRef(
        defect_id=defect.id,
        station_id=defect.station_id,
        parameter=defect.parameter,
        timestamp_utc=pd.Timestamp(defect.timestamp_utc),
        reason_code=defect.reason_code,
        evidence=dict(defect.evidence or {}),
    )
    frame = await repo.station_frame(session, defect.station_id)

    result = await run_in_threadpool(_explain, frame, ref)
    return ExplainOut.model_validate(result)


def _explain(frame: pd.DataFrame, ref: DefectRef) -> dict[str, object]:
    """Load the model bundle (if any) and explain the defect. Runs off the event loop."""
    from provenance.models import registry

    directory = get_settings().artefacts_dir
    available = registry.bundle_available(directory)
    # Warmed at startup (api/app.py lifespan); this is a cache hit on the request path.
    bundle = registry.load_bundle_cached(directory) if available else None
    return explain_defect(frame, ref, bundle).to_dict()

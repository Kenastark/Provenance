"""Operational endpoints: liveness, readiness, and version provenance.

These are unauthenticated on purpose — orchestration probes them without a key.
``/version`` reports the git sha, the config hash, the trust-weights hash, and the
model versions, so a running instance can be tied to the exact code and config that
produced its answers.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache

from fastapi import APIRouter, Request
from sqlalchemy import text

from provenance import __version__
from provenance.api.schemas import HealthOut, ReadyOut, VersionOut
from provenance.config.loading import config_hash
from provenance.trust.weights import trust_config_hash

router = APIRouter(tags=["meta"])


@lru_cache(maxsize=1)
def _git_sha() -> str:
    from provenance.config.settings import REPO_ROOT

    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError):  # pragma: no cover
        return "unknown"


@router.get("/healthz", response_model=HealthOut)
async def healthz() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/readyz", response_model=ReadyOut)
async def readyz(request: Request) -> ReadyOut:
    sessionmaker = request.app.state.sessionmaker
    try:
        async with sessionmaker() as session:
            await session.execute(text("SELECT 1"))
        db = "ok"
    except Exception:  # pragma: no cover - only on a real outage
        db = "unavailable"
    return ReadyOut(status="ok" if db == "ok" else "degraded", database=db)


@router.get("/version", response_model=VersionOut)
async def version() -> VersionOut:
    # No ML model artefacts exist yet (phase 2 is statistics-only), so model
    # versions carry the trust score's own version and nothing more.
    return VersionOut(
        version=__version__,
        git_sha=_git_sha(),
        config_hash=config_hash(),
        trust_config_hash=trust_config_hash(),
        model_versions={"trust_score": "v1"},
    )

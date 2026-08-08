"""The regulator-facing audit-trail export (§2).

For one audit run it emits, deterministically, which readings were judged defective
and why (the defects) and which cells were excluded as structural absences and why
(the coverage facts). The CSV is byte-for-byte reproducible for a fixed run id —
sorted rows, sorted evidence keys — so a regulator can diff two exports and a test
can assert stability. The defect row count reconciles exactly against the defects
table for that run.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.errors import ProblemException
from provenance.grid.defect_rate import DEFINITION
from provenance.io.db import repository as repo

router = APIRouter(prefix="/v1/export", tags=["export"])

_CSV_COLUMNS = [
    "record_type",
    "station_id",
    "parameter",
    "timestamp_utc",
    "reason_code",
    "severity",
    "counts_toward_rate",
    "excluded_cells",
    "evidence",
]


async def _resolve_run_id(session: AsyncSession, run_id: str | None) -> str:
    if run_id is None:
        latest = await repo.latest_audit_run(session)
        if latest is None:
            raise ProblemException(404, "No audit run exists yet. Load a data drop first.")
        return latest.id
    if await repo.get_audit_run(session, run_id) is None:
        raise ProblemException(404, f"No audit run with id {run_id!r}.")
    return run_id


@router.get("/audit-trail")
async def audit_trail(
    run_id: str | None = Query(default=None, description="Audit run; defaults to the latest."),
    fmt: str = Query(default="json", pattern="^(json|csv)$", alias="format"),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.RESEARCHER)),
) -> Response:
    run_id = await _resolve_run_id(session, run_id)
    defects = await repo.defects_for_audit_run(session, run_id)
    coverage_facts = await repo.coverage_facts_for_audit_run(session, run_id)

    if fmt == "csv":
        return _csv_response(run_id, defects, coverage_facts)
    return _json_response(run_id, defects, coverage_facts)


def _csv_response(run_id: str, defects: Any, coverage_facts: Any) -> Response:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for d in defects:
        writer.writerow(
            {
                "record_type": "defect",
                "station_id": d.station_id,
                "parameter": d.parameter,
                "timestamp_utc": d.timestamp_utc.isoformat(),
                "reason_code": d.reason_code,
                "severity": d.severity,
                "counts_toward_rate": d.counts_toward_rate,
                "excluded_cells": "",
                "evidence": json.dumps(d.evidence or {}, sort_keys=True, ensure_ascii=False),
            }
        )
    for c in coverage_facts:
        writer.writerow(
            {
                "record_type": "structural_exclusion",
                "station_id": c.station_id,
                "parameter": c.parameter,
                "timestamp_utc": "",
                "reason_code": c.reason_code,
                "severity": "info",
                "counts_toward_rate": False,
                "excluded_cells": c.excluded_cells,
                "evidence": json.dumps({"domain": c.domain}, sort_keys=True, ensure_ascii=False),
            }
        )
    body = buf.getvalue().replace("\r\n", "\n")
    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="audit-trail-{run_id}.csv"',
            "X-Audit-Run-Id": run_id,
            "X-Defect-Row-Count": str(len(defects)),
        },
    )


def _json_response(run_id: str, defects: Any, coverage_facts: Any) -> JSONResponse:
    payload = {
        "audit_run_id": run_id,
        "definition": DEFINITION,
        "defects": [
            {
                "station_id": d.station_id,
                "parameter": d.parameter,
                "timestamp_utc": d.timestamp_utc.isoformat(),
                "reason_code": d.reason_code,
                "severity": d.severity,
                "counts_toward_rate": d.counts_toward_rate,
                "evidence": d.evidence or {},
            }
            for d in defects
        ],
        "structural_exclusions": [
            {
                "station_id": c.station_id,
                "parameter": c.parameter,
                "domain": c.domain,
                "reason_code": c.reason_code,
                "excluded_cells": c.excluded_cells,
            }
            for c in coverage_facts
        ],
        "reconciliation": {
            "n_defect_rows": len(defects),
            "n_structural_exclusions": len(coverage_facts),
        },
    }
    return JSONResponse(content=payload, headers={"X-Defect-Row-Count": str(len(defects))})

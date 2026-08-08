"""The detector contract.

Every detector is a pure function over the canonical frame plus an
:class:`AuditContext`, returning a *DefectFrame*: one row per flagged cell, each
carrying the reason code, where and when it fired, a severity, and an evidence
dict holding the exact numbers that justified the flag. That evidence dict is
what the dashboard's "why was this flagged?" panel renders, so a detector that
cannot say *why* has not done its job (standing rule 9).

Keeping detectors to this one signature is what lets the orchestrator run them
uniformly and lets the architecture test prove none of them reaches into the API
or model layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from provenance.config import reason_codes
from provenance.grid.coverage import CoverageModel
from provenance.schema import canonical as C

REASON_CODE = "reason_code"
SEVERITY = "severity"
EVIDENCE = "evidence"

DEFECT_COLUMNS: tuple[str, ...] = (
    REASON_CODE,
    C.STATION_ID,
    C.PARAMETER,
    C.TIMESTAMP,
    SEVERITY,
    EVIDENCE,
)


def empty_defect_frame() -> pd.DataFrame:
    """A correctly-typed DefectFrame with no rows."""
    df = pd.DataFrame({c: pd.Series(dtype="object") for c in DEFECT_COLUMNS})
    df[C.TIMESTAMP] = pd.Series(dtype="datetime64[ns]")
    return df


def defect_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a DefectFrame from a list of row dicts, keeping column order stable."""
    if not rows:
        return empty_defect_frame()
    df = pd.DataFrame(rows)
    for col in DEFECT_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[list(DEFECT_COLUMNS)]
    df[C.TIMESTAMP] = pd.to_datetime(df[C.TIMESTAMP])
    return df.reset_index(drop=True)


@dataclass(frozen=True, slots=True)
class AuditContext:
    """Everything a detector needs beyond the frame itself.

    Detectors read thresholds and coverage from here rather than importing config
    directly, so a test can hand a detector a bespoke context without touching the
    global YAML.
    """

    thresholds: dict[str, Any]
    coverage: CoverageModel

    def severity_for(self, code: str) -> str:
        return str(reason_codes.get(code).severity)


@runtime_checkable
class Detector(Protocol):
    """A single reason code's worth of logic."""

    code: str

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame: ...


def make_row(
    code: str, station: str, parameter: str, ts: object, ctx: AuditContext, **evidence: Any
) -> dict[str, Any]:
    """Helper: one DefectFrame row with the code's severity filled in."""
    return {
        REASON_CODE: code,
        C.STATION_ID: station,
        C.PARAMETER: parameter,
        C.TIMESTAMP: ts,
        SEVERITY: ctx.severity_for(code),
        EVIDENCE: evidence,
    }

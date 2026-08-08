"""Pydantic response models — the API's public contract.

The trust models are the load-bearing ones: :class:`TrustScoreOut` makes it
structurally impossible to return a bare score. ``components`` and ``reason_codes``
are required, non-empty-by-construction fields, so a serialiser cannot emit a
trust number without them (standing rule 9). ``tests/architecture`` proves no
response model in this module carries a trust value without those two fields.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StationOut(BaseModel):
    station_id: str
    name: str | None = None
    lat: float | None = None
    lon: float | None = None
    zone_type: str | None = None
    coverage: dict[str, int] = Field(default_factory=dict)


class ReadingOut(BaseModel):
    station_id: str
    parameter: str
    timestamp_utc: str
    value: float | None
    unit: str
    instrument_id: str | None = None
    source_file: str
    row_hash: str
    reason_codes: list[str] | None = None
    """Present only when ``quality_flagged=true``: the audit codes on this cell."""


class DefectOut(BaseModel):
    id: int
    audit_run_id: str
    reason_code: str
    station_id: str
    parameter: str
    timestamp_utc: str
    severity: str
    counts_toward_rate: bool
    evidence: dict[str, Any]


class ComponentOut(BaseModel):
    name: str
    value: float
    weight: float
    contribution: float
    is_placeholder: bool
    detail: str


class RiskOut(BaseModel):
    value: float
    trust: float
    severity_vs_threshold: float
    population_exposure: float
    population_exposure_stubbed: bool


class TrustScoreOut(BaseModel):
    """A trust score, inseparable from its explanation.

    ``components`` and ``reason_codes`` are required and validated non-empty: a
    ``TrustScoreOut`` cannot be constructed as a bare number.
    """

    station_id: str
    timestamp_utc: str
    trust: float
    components: list[ComponentOut] = Field(min_length=1)
    reason_codes: list[str] = Field(min_length=1)
    risk: RiskOut
    degraded: bool = False
    notes: list[str] = Field(default_factory=list)


class EventOut(BaseModel):
    id: int
    audit_run_id: str
    rank: int
    category: str
    reason_code: str
    station_id: str
    parameter: str
    timestamp_utc: str
    headline: str
    severity: str
    evidence: dict[str, Any]
    verdict: str | None = None  # null until Phase 4 adjudicates


class AuditRunOut(BaseModel):
    id: str
    code_version: str
    config_hash: str
    data_checksum: str
    generated_at: str
    n_rows: int
    n_defective_cells: int
    n_covered_cells: int
    defect_rate: float
    conventional_completeness_pct: float
    ingest_batch_id: str | None = None


class QualityStationOut(BaseModel):
    station_id: str
    zone_type: str | None
    health: float | None
    trust: float | None
    flag_count: int
    n_parameters: int
    last_reading_at: str | None
    # Even the at-a-glance tile is never a bare number: it carries the same
    # explanation the trust endpoint does (standing rule 9).
    components: list[ComponentOut] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)


class QualitySummaryOut(BaseModel):
    audit_run_id: str
    stations: list[QualityStationOut]


class VersionOut(BaseModel):
    version: str
    git_sha: str
    config_hash: str
    trust_config_hash: str
    model_versions: dict[str, str]


class HealthOut(BaseModel):
    status: str


class ReadyOut(BaseModel):
    status: str
    database: str

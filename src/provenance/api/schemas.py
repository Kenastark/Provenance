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
    evidence: dict[str, Any] = Field(default_factory=dict)
    """The figures behind this term, keyed by the placeholder names the reason-code
    sentences use. ``detail`` is the same information as prose; this is the form a
    renderer can substitute, so a client never has to show an unfilled sentence."""


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
    evidence: dict[str, Any] = Field(default_factory=dict)
    """Every component's figures, merged: the substitution map for ``reason_codes``.

    A consumer renders a code's registry sentence against this. Without it the only
    way to show a reason was to print the template, placeholders and all."""


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
    evidence: dict[str, Any] = Field(default_factory=dict)
    """As :class:`TrustScoreOut.evidence`: the map a reason-code sentence renders
    against, so the at-a-glance table can say a sentence too."""


class QualitySummaryOut(BaseModel):
    audit_run_id: str
    stations: list[QualityStationOut]


class AttributionOut(BaseModel):
    feature: str
    value: float
    feature_value: float
    provenance: str


class ExplainOut(BaseModel):
    """A per-defect explanation. Never a bare score: it always carries a sentence.

    ``method`` records how the explanation was produced — ``model`` (SHAP over a tree
    model), ``rule`` (a deterministic detector decided it), or ``degraded`` (no model
    artefact was available, so the statistics-layer reason is returned instead). When
    ``degraded`` is true the ``attributions`` list is empty by construction and the
    response says so, per standing rule 6.
    """

    defect_id: int
    station_id: str
    parameter: str
    timestamp_utc: str
    reason_code: str
    method: str
    fault_class: str | None = None
    predicted_class: str | None = None
    sentence: str
    degraded: bool = False
    model_versions: dict[str, str] = Field(default_factory=dict)
    base_value: float | None = None
    prediction: float | None = None
    residual: float | None = None
    reconstructs: bool | None = None
    attributions: list[AttributionOut] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DeweatherPointOut(BaseModel):
    timestamp_utc: str
    actual: float
    predicted: float
    residual: float


class DeweatherSeriesOut(BaseModel):
    """A station's deweathered series for one pollutant: raw vs weather-predicted vs residual.

    The before/after view (§7.6): ``actual`` is what the sensor reported, ``predicted`` is
    what weather and time alone explain, and ``residual`` is what is left — the part
    anomaly detection should see. ``degraded`` is true when no residuals have been stored
    (no model trained), in which case ``series`` is empty and the client says so.
    """

    station_id: str
    parameter: str
    model_version: str | None = None
    degraded: bool = False
    series: list[DeweatherPointOut] = Field(default_factory=list)


class BusStopOut(BaseModel):
    stop_id: str
    lat: float
    lon: float
    n_routes: float


class ReferenceStopsOut(BaseModel):
    """``available=False`` means no GTFS bundle was found — a coverage fact, not an
    empty layer (standing rule 3): the map must tell the two apart."""

    available: bool
    stops: list[BusStopOut]


class TrafficCounterOut(BaseModel):
    counter_id: str
    name: str
    lat: float
    lon: float


class ReferenceCountersOut(BaseModel):
    """``available=False`` means no Enclod archive CSVs were found under the data
    root — distinct from the counters existing but carrying no coordinate."""

    available: bool
    counters: list[TrafficCounterOut]


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

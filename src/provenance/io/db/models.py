"""The ORM: the tables Provenance persists.

The two hypertables (``readings`` and ``trust_scores``) are plain tables here and
become TimescaleDB hypertables in the migration; the ORM does not depend on any
Timescale-specific feature so the same models build on SQLite for tests.

Naming and provenance follow one rule: every row that was produced by a run
carries the id of that run. Readings carry the ``ingest_batch_id`` that loaded
them; defects, coverage facts, events and trust scores carry the
``audit_run_id`` that produced them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from provenance.io.db.base import Base


class IngestBatch(Base):
    """One file-drop load. Its checksum makes re-loading the same bytes a no-op."""

    __tablename__ = "ingest_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    checksum: Mapped[str] = mapped_column(String, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Station(Base):
    """A monitoring station. ``geom`` (PostGIS point) is added by the migration."""

    __tablename__ = "stations"

    station_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    zone_type: Mapped[str | None] = mapped_column(String, nullable=True)
    coverage: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    """Coverage matrix: parameter -> reading count, from the audit's coverage model."""
    ingest_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("ingest_batches.id"), nullable=True
    )


class Parameter(Base):
    """A measured quantity, its canonical unit, and the domain it belongs to."""

    __tablename__ = "parameters"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)


class Reading(Base):
    """One observed reading. Hypertable in Postgres, chunked by day on ``timestamp_utc``.

    The primary key is ``(timestamp_utc, row_hash)``: ``row_hash`` uniquely
    identifies a reading's content, and the partition column must take part in the
    key for the Timescale hypertable. Two readings that share a timestamp but
    differ in value (the duplicate-timestamp defect) hash differently and both
    persist; two byte-identical loads collide on the same key and de-duplicate,
    which is what makes loading idempotent.
    """

    __tablename__ = "readings"

    timestamp_utc: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    row_hash: Mapped[str] = mapped_column(String, primary_key=True)
    station_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    parameter: Mapped[str] = mapped_column(String, nullable=False, index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    instrument_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_file: Mapped[str] = mapped_column(String, nullable=False)
    ingest_batch_id: Mapped[str] = mapped_column(
        ForeignKey("ingest_batches.id"), nullable=False, index=True
    )


class AuditRun(Base):
    """One audit. The defect rate is stored with the arithmetic that produced it."""

    __tablename__ = "audit_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    code_version: Mapped[str] = mapped_column(String, nullable=False)
    config_hash: Mapped[str] = mapped_column(String, nullable=False)
    data_checksum: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    n_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    n_defective_cells: Mapped[int] = mapped_column(Integer, nullable=False)
    n_covered_cells: Mapped[int] = mapped_column(Integer, nullable=False)
    defect_rate: Mapped[float] = mapped_column(Float, nullable=False)
    conventional_completeness_pct: Mapped[float] = mapped_column(Float, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    """The full AuditResult.to_dict(), so a run reconstructs without a re-audit."""
    ingest_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("ingest_batches.id"), nullable=True
    )

    defects: Mapped[list[Defect]] = relationship(back_populates="audit_run")
    coverage_facts: Mapped[list[CoverageFact]] = relationship(back_populates="audit_run")
    events: Mapped[list[Event]] = relationship(back_populates="audit_run")


class Defect(Base):
    """One flagged cell. ``counts_toward_rate`` mirrors the reason-code registry."""

    __tablename__ = "defects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.id"), nullable=False, index=True
    )
    reason_code: Mapped[str] = mapped_column(String, nullable=False, index=True)
    station_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    parameter: Mapped[str] = mapped_column(String, nullable=False, index=True)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False, index=True)
    counts_toward_rate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    audit_run: Mapped[AuditRun] = relationship(back_populates="defects")


class CoverageFact(Base):
    """A structural absence: a sensor a station never carried. Never a defect."""

    __tablename__ = "coverage_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.id"), nullable=False, index=True
    )
    station_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    parameter: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    reason_code: Mapped[str] = mapped_column(String, nullable=False)
    excluded_cells: Mapped[int] = mapped_column(Integer, nullable=False)

    audit_run: Mapped[AuditRun] = relationship(back_populates="coverage_facts")


class Event(Base):
    """A candidate notable event. ``verdict`` stays null until Phase 4 adjudicates."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.id"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    reason_code: Mapped[str] = mapped_column(String, nullable=False)
    station_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    parameter: Mapped[str] = mapped_column(String, nullable=False)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    headline: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)

    audit_run: Mapped[AuditRun] = relationship(back_populates="events")


class Residual(Base):
    """A deweathered residual: actual minus weather-predicted, per reading.

    The residual, not the raw value, is what anomaly detection sees downstream (§7.6),
    so it is stored alongside the ``model_version`` that produced it — a residual is
    meaningless without knowing which deweather model left it behind. Hypertable in
    Postgres, chunked by day; the partition column ``timestamp_utc`` is part of the
    primary key so Timescale accepts it.
    """

    __tablename__ = "residuals"

    timestamp_utc: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    station_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    parameter: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    model_version: Mapped[str] = mapped_column(String, primary_key=True)
    actual: Mapped[float] = mapped_column(Float, nullable=False)
    predicted: Mapped[float] = mapped_column(Float, nullable=False)
    residual: Mapped[float] = mapped_column(Float, nullable=False)
    audit_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("audit_runs.id"), nullable=True, index=True
    )


class TrustScore(Base):
    """A trust score at a point in time. Hypertable in Postgres, chunked by day.

    A score never persists without its component breakdown and reason codes: the
    ``components`` and ``reason_codes`` columns are not nullable, which is the
    storage-layer half of the guarantee the API's serialiser enforces on output.
    """

    __tablename__ = "trust_scores"
    __table_args__ = (UniqueConstraint("timestamp_utc", "station_id", name="uq_trust_station_ts"),)

    timestamp_utc: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    station_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    trust: Mapped[float] = mapped_column(Float, nullable=False)
    risk_value: Mapped[float] = mapped_column(Float, nullable=False)
    components: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    reason_codes: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    risk: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    notes: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    degraded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    population_exposure_stubbed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    audit_run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.id"), nullable=False, index=True
    )

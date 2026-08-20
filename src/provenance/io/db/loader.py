"""Idempotent load: a data drop → readings, an audit run, and trust scores, persisted.

The whole load is keyed on the data's content checksum. Re-loading the same bytes
resolves to the same ``ingest_batch`` id, and a batch that already exists is a
no-op — loading is idempotent by construction, which the test asserts by loading
the same fixture twice and checking row counts do not move.

Every persisted row carries its provenance: readings carry the ``ingest_batch_id``
that loaded them; defects, coverage facts, events and trust scores carry the
``audit_run_id`` that produced them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.audit.orchestrator import run_audit
from provenance.audit.result import AuditResult
from provenance.config import reason_codes
from provenance.detectors import registry
from provenance.detectors.base import AuditContext
from provenance.grid.coverage import CoverageModel, build_coverage
from provenance.grid.exposure import ExposureLayer
from provenance.io.db import models as m
from provenance.io.loaders import StationLocation
from provenance.schema import canonical as C
from provenance.schema.observe import observe
from provenance.trust.engine import compute_trust


@dataclass(frozen=True, slots=True)
class LoadReport:
    """What one load did (or didn't do, when the batch already existed)."""

    ingest_batch_id: str
    audit_run_id: str
    already_loaded: bool
    readings_inserted: int
    defects_inserted: int
    trust_scores_inserted: int


async def load_frame(
    session: AsyncSession,
    frame: pd.DataFrame,
    *,
    source: str,
    path: str,
    station_meta: dict[str, StationLocation] | None = None,
    exposure: ExposureLayer | None = None,
) -> LoadReport:
    """Persist a canonical frame plus its audit and trust scores, idempotently.

    ``station_meta`` (from the loader) supplies each station's site name and
    coordinates; when absent (e.g. the synthetic corpus, which carries no Location)
    those columns stay null rather than being invented.
    """
    obs = observe(frame)
    checksum = obs.checksum
    batch_id = f"ib_{checksum}"

    existing = await session.get(m.IngestBatch, batch_id)
    if existing is not None:
        run_id = _run_id(frame)
        return LoadReport(
            ingest_batch_id=batch_id,
            audit_run_id=run_id,
            already_loaded=True,
            readings_inserted=0,
            defects_inserted=0,
            trust_scores_inserted=0,
        )

    session.add(
        m.IngestBatch(
            id=batch_id,
            source=source,
            path=path,
            checksum=checksum,
            row_count=len(frame),
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )

    coverage = build_coverage(frame)
    result = run_audit(frame)
    run_id = _run_id(frame)

    readings_inserted = await _insert_readings(session, frame, batch_id)
    await _insert_stations(session, coverage, batch_id, station_meta or {})
    await _insert_parameters(session, coverage)
    _insert_audit_run(session, result, run_id, batch_id)
    defects_inserted = _insert_defects(session, result, run_id)
    _insert_coverage_facts(session, result, run_id)
    _insert_events(session, result, run_id)
    trust_inserted = _insert_trust_scores(session, frame, coverage, run_id, exposure=exposure)

    await session.commit()
    return LoadReport(
        ingest_batch_id=batch_id,
        audit_run_id=run_id,
        already_loaded=False,
        readings_inserted=readings_inserted,
        defects_inserted=defects_inserted,
        trust_scores_inserted=trust_inserted,
    )


async def load_path(
    session: AsyncSession, data_dir: Path, *, source: str = "green_sentinel"
) -> LoadReport:
    """Load whatever canonical readings live under ``data_dir`` (fixtures or export)."""
    from provenance.io import loaders

    frame = loaders.load_data(data_dir)
    station_meta = loaders.load_station_metadata(data_dir)
    exposure = exposure_for_drop(data_dir, station_meta)
    return await load_frame(
        session,
        frame,
        source=source,
        path=str(data_dir),
        station_meta=station_meta,
        exposure=exposure,
    )


def exposure_for_drop(
    data_dir: Path, station_meta: dict[str, StationLocation]
) -> ExposureLayer | None:
    """Build the PopulationExposure layer for a data drop, or None when it cannot be.

    Needs both a GTFS bundle under ``data_dir`` and station coordinates; without either
    the trust scores fall back to the neutral, stubbed exposure factor rather than
    inventing one (standing rule 6). Kept here (io) so the trust layer stays a pure
    function of a per-station factor and never learns how GTFS is discovered.
    """
    from provenance.grid.exposure import build_exposure_layer
    from provenance.io.ingest.gtfs import find_gtfs_bundle, stops_with_route_counts

    bundle = find_gtfs_bundle(data_dir)
    points = {sid: (loc.lat, loc.lon) for sid, loc in station_meta.items()}
    if bundle is None or not points:
        return None
    stops = stops_with_route_counts(bundle)
    return build_exposure_layer(stops, points)


def _run_id(frame: pd.DataFrame) -> str:
    from provenance.config.loading import config_hash

    return f"ar_{observe(frame).checksum}_{config_hash()}"


async def _insert_readings(session: AsyncSession, frame: pd.DataFrame, batch_id: str) -> int:
    existing = set((await session.scalars(select(m.Reading.row_hash))).all())
    to_insert = []
    for row in frame.to_dict(orient="records"):
        rh = str(row[C.ROW_HASH])
        if rh in existing:
            continue
        existing.add(rh)
        val = row[C.VALUE]
        instrument = row.get(C.INSTRUMENT_ID)
        to_insert.append(
            {
                "timestamp_utc": pd.Timestamp(row[C.TIMESTAMP]).to_pydatetime(),
                "row_hash": rh,
                "station_id": str(row[C.STATION_ID]),
                "parameter": str(row[C.PARAMETER]),
                "value": None if pd.isna(val) else float(val),
                "unit": str(row[C.UNIT]),
                "instrument_id": None
                if instrument is None or pd.isna(instrument)
                else str(instrument),
                "source_file": str(row[C.SOURCE_FILE]),
                "ingest_batch_id": batch_id,
            }
        )
    if to_insert:
        await session.execute(insert(m.Reading), to_insert)
    return len(to_insert)


async def _insert_stations(
    session: AsyncSession,
    coverage: CoverageModel,
    batch_id: str,
    station_meta: dict[str, StationLocation],
) -> None:
    from provenance.config.loading import load_station_zones

    zones = load_station_zones()
    matrix = coverage.coverage_matrix
    # station_id is the global primary key, shared across every batch that has ever
    # been loaded into this database. Two different drops (e.g. the synthetic demo
    # corpus and a real Green Sentinel export, or two dated real exports) can name
    # the same station, so a plain insert must not repeat one already on record.
    existing = set((await session.scalars(select(m.Station.station_id))).all())
    for station in coverage.stations:
        if station in existing:
            continue
        cov = (
            {str(k): int(v) for k, v in matrix.loc[station].to_dict().items() if int(v) > 0}
            if station in matrix.index
            else {}
        )
        meta = station_meta.get(station)
        session.add(
            m.Station(
                station_id=station,
                name=None if meta is None else meta.name,
                lat=None if meta is None else meta.lat,
                lon=None if meta is None else meta.lon,
                # zone_type has no source column in the export; it comes from the
                # curated, provisional station_zones.yaml. Stations not in that map
                # (e.g. the synthetic fixtures) stay null — never invented.
                zone_type=zones.get(station),
                coverage=cov,
                ingest_batch_id=batch_id,
            )
        )


async def _insert_parameters(session: AsyncSession, coverage: CoverageModel) -> None:
    # name is the global primary key. The synthetic fixture generator and the real
    # Green Sentinel export share a lot of parameter vocabulary (CO2, PM10, ...), so
    # loading a second, differently-checksummed batch must skip names already on
    # record rather than re-inserting them.
    existing = set((await session.scalars(select(m.Parameter.name))).all())
    for parameter in coverage.parameters:
        if parameter in existing:
            continue
        session.add(
            m.Parameter(
                name=parameter,
                unit=None,
                domain=coverage.param_domains.get(parameter),
            )
        )


def _insert_audit_run(
    session: AsyncSession, result: AuditResult, run_id: str, batch_id: str
) -> None:
    session.add(
        m.AuditRun(
            id=run_id,
            code_version=result.meta.code_version,
            config_hash=result.meta.config_hash,
            data_checksum=result.meta.data_checksum,
            generated_at=datetime.fromisoformat(result.meta.generated_at).replace(tzinfo=None),
            n_rows=result.meta.n_rows,
            n_defective_cells=result.defect_rate.n_defective_cells,
            n_covered_cells=result.defect_rate.n_covered_cells,
            defect_rate=result.defect_rate.rate,
            conventional_completeness_pct=result.coverage.conventional_completeness_pct,
            summary=result.to_dict(include_generated_at=False),
            ingest_batch_id=batch_id,
        )
    )


def _insert_defects(session: AsyncSession, result: AuditResult, run_id: str) -> int:
    counting = {rc.code for rc in reason_codes.defect_codes()}
    n = 0
    for rec in result.defects:
        code = str(rec["reason_code"])
        session.add(
            m.Defect(
                audit_run_id=run_id,
                reason_code=code,
                station_id=str(rec[C.STATION_ID]),
                parameter=str(rec[C.PARAMETER]),
                timestamp_utc=pd.Timestamp(rec[C.TIMESTAMP]).to_pydatetime(),
                severity=str(rec["severity"]),
                counts_toward_rate=code in counting,
                evidence=dict(rec["evidence"]),
            )
        )
        n += 1
    return n


def _insert_coverage_facts(session: AsyncSession, result: AuditResult, run_id: str) -> None:
    for s in result.structural_absences:
        session.add(
            m.CoverageFact(
                audit_run_id=run_id,
                station_id=s.station_id,
                parameter=s.parameter,
                domain=s.domain,
                reason_code=s.reason_code,
                excluded_cells=s.excluded_cells,
            )
        )


def _insert_events(session: AsyncSession, result: AuditResult, run_id: str) -> None:
    for e in result.notable_events:
        session.add(
            m.Event(
                audit_run_id=run_id,
                rank=e.rank,
                category=e.category,
                reason_code=e.reason_code,
                station_id=e.station_id,
                parameter=e.parameter,
                timestamp_utc=datetime.fromisoformat(e.timestamp_utc).replace(tzinfo=None),
                headline=e.headline,
                severity=e.severity,
                evidence=dict(e.evidence),
                verdict=None,  # null until Phase 4 adjudicates
            )
        )


def _insert_trust_scores(
    session: AsyncSession,
    frame: pd.DataFrame,
    coverage: CoverageModel,
    run_id: str,
    *,
    exposure: ExposureLayer | None = None,
) -> int:
    from provenance.config.loading import load_thresholds
    from provenance.trust.engine import scoring_instants
    from provenance.trust.weights import load_trust_weights

    thresholds = load_thresholds()
    weights_cfg = load_trust_weights()
    scfg = weights_cfg.get("scoring", {})
    ctx = AuditContext(thresholds=thresholds, coverage=coverage)
    defects = registry.run_detectors(frame, ctx)
    instants = scoring_instants(
        frame,
        cadence_hours=int(scfg.get("cadence_hours", 24)),
        max_points=int(scfg.get("max_points", 120)),
    )
    n = 0
    for station in coverage.stations:
        factor = (
            exposure.factor_for(station)
            if exposure is not None and exposure.is_measured(station)
            else None
        )
        for at in instants:
            score = compute_trust(
                frame,
                defects,
                station,
                at,
                coverage=coverage,
                thresholds=thresholds,
                weights_cfg=weights_cfg,
                exposure=factor,
            )
            session.add(
                m.TrustScore(
                    timestamp_utc=at.to_pydatetime(),
                    station_id=station,
                    trust=score.value,
                    risk_value=score.risk.value,
                    components=[c.to_dict() for c in score.components],
                    reason_codes=score.reason_codes,
                    risk=score.risk.to_dict(),
                    notes=score.notes,
                    degraded=score.degraded,
                    population_exposure_stubbed=score.risk.population_exposure_stubbed,
                    audit_run_id=run_id,
                )
            )
            n += 1
    return n


async def count_readings(session: AsyncSession) -> int:
    return int((await session.scalar(select(func.count()).select_from(m.Reading))) or 0)

"""The audit orchestrator: canonical frame in, :class:`AuditResult` out.

This is the seam the whole product hangs from. It builds the coverage model, runs
every detector, counts defective *cells* (not flags) for the one defect-rate
definition, and ranks the notable events so the headline anomalies - the 4100 µg/m3
PM10 spike, the longest outages, the longest frozen runs - surface without any
station being named in the code.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from provenance import __version__
from provenance.audit.result import (
    AuditResult,
    CoverageSummary,
    NetworkWideFinding,
    NotableEvent,
    RunMeta,
    StructuralAbsenceRow,
)
from provenance.config import reason_codes
from provenance.config.loading import config_hash, load_thresholds
from provenance.detectors import registry
from provenance.detectors.base import EVIDENCE, REASON_CODE, AuditContext
from provenance.grid import coverage as coverage_mod
from provenance.grid.defect_rate import DefectRate
from provenance.schema import canonical as C
from provenance.schema.observe import observe

_CELL_KEYS = [C.STATION_ID, C.PARAMETER, C.TIMESTAMP]


def run_audit(frame: pd.DataFrame, *, now: datetime | None = None) -> AuditResult:
    """Run the full statistics-only audit over a canonical long frame."""
    thresholds = load_thresholds()
    model = coverage_mod.build_coverage(frame)
    ctx = AuditContext(thresholds=thresholds, coverage=model)
    defects = registry.run_detectors(frame, ctx)

    counting_codes = {rc.code for rc in reason_codes.defect_codes()}
    counting = defects[defects[REASON_CODE].isin(counting_codes)]
    defective_cells = counting[_CELL_KEYS].drop_duplicates()
    defect_rate = DefectRate(
        n_defective_cells=len(defective_cells),
        n_covered_cells=int(model.n_covered_cells()),
    )

    coverage_summary = _coverage_summary(frame, model)
    meta = RunMeta(
        code_version=__version__,
        config_hash=config_hash(),
        data_checksum=observe(frame).checksum,
        generated_at=(now or datetime.now(UTC)).isoformat(),
        n_rows=len(frame),
    )

    return AuditResult(
        meta=meta,
        coverage=coverage_summary,
        defect_rate=defect_rate,
        defects_by_code=_counts(defects, REASON_CODE),
        defects_by_station=_counts(counting, C.STATION_ID),
        defects_by_parameter=_counts(counting, C.PARAMETER),
        defects_by_day=_by_day(counting),
        structural_absences=[
            StructuralAbsenceRow(
                station_id=s.station_id,
                parameter=s.parameter,
                domain=s.domain,
                reason_code=s.reason_code,
                excluded_cells=s.n_excluded_cells,
            )
            for s in model.structural_absences
        ],
        notable_events=_notable_events(defects),
        network_wide_findings=_network_wide_findings(counting, frame, model, thresholds),
        thresholds=thresholds,
        defects=_defects_records(defects),
    )


def _coverage_summary(frame: pd.DataFrame, model: coverage_mod.CoverageModel) -> CoverageSummary:
    n_rows = len(frame)
    n_nonnull = int(frame[C.VALUE].notna().sum())
    conventional = round(100.0 * n_nonnull / n_rows, 4) if n_rows else 0.0
    covered = model.n_covered_cells()
    grid = round(100.0 * model.n_observed_cells() / covered, 4) if covered else 0.0
    return CoverageSummary(
        n_stations=len(model.stations),
        n_parameters=len(model.parameters),
        n_covered_pairs=len(model.series_grids),
        n_observed_cells=model.n_observed_cells(),
        n_absent_cells=model.n_absent_cells(),
        n_covered_cells=covered,
        n_structurally_excluded_cells=model.n_structurally_excluded_cells(),
        n_expected_cells=model.n_expected_cells(),
        conventional_completeness_pct=conventional,
        grid_completeness_pct=grid,
        window_start=pd.Timestamp(model.global_start).isoformat(),
        window_end=pd.Timestamp(model.global_end).isoformat(),
    )


def _counts(defects: pd.DataFrame, column: str) -> dict[str, int]:
    if defects.empty:
        return {}
    counts = defects[column].astype(str).value_counts()
    return {str(k): int(v) for k, v in sorted(counts.items())}


def _by_day(defects: pd.DataFrame) -> dict[str, int]:
    if defects.empty:
        return {}
    days = pd.to_datetime(defects[C.TIMESTAMP]).dt.date.astype(str)
    counts = days.value_counts()
    return {str(k): int(v) for k, v in sorted(counts.items())}


def _network_wide_findings(
    counting: pd.DataFrame,
    frame: pd.DataFrame,
    model: coverage_mod.CoverageModel,
    thresholds: dict[str, Any],
) -> list[NetworkWideFinding]:
    """A (reason_code, parameter) fires on every station that carries the parameter,
    for essentially every *reading* that parameter has - a single systemic fact
    about a whole channel (e.g. a mislabelled unit), not a station-specific fault.

    Generic over both dimensions - never a hardcoded code or parameter (standing
    rule 1/2): "every carrying station" comes from the coverage model's own
    ``series_grids`` keys, and the fraction gate is a configured reporting
    threshold (``thresholds.yaml``'s ``network_wide_finding.min_fraction``), not a
    magic number in code.

    Restricted to codes whose flagged cells are all *present* readings (checked by
    set membership against the frame's own non-null cells, never a hardcoded code
    list) - an absence-pattern code like R01 has no present reading to compare
    against at all, so "what fraction of readings are flagged" is not a question
    that applies to it; that is a completeness story, already reported separately
    by the coverage summary, not this one.
    """
    if counting.empty:
        return []
    min_fraction = float(thresholds.get("network_wide_finding", {}).get("min_fraction", 0.95))

    carriers: dict[str, set[str]] = {}
    for station, parameter in model.series_grids:
        carriers.setdefault(parameter, set()).add(station)

    present = frame[frame[C.VALUE].notna()]
    present_cells = set(
        zip(
            present[C.STATION_ID].astype(str),
            present[C.PARAMETER].astype(str),
            present[C.TIMESTAMP],
            strict=True,
        )
    )
    present_counts = present.groupby(C.PARAMETER).size()

    # A cell can be flagged by the same code more than once if a detector or the
    # registry ever double-fires - drop_duplicates keeps "flagged" a cell count,
    # matching the defect rate's own established cell-dedup (see `defective_cells`
    # above).
    deduped = counting.drop_duplicates(subset=[*_CELL_KEYS, REASON_CODE])

    findings: list[NetworkWideFinding] = []
    for key, rows in deduped.groupby([REASON_CODE, C.PARAMETER]):
        code, parameter = str(key[0]), str(key[1])
        carrying_stations = carriers.get(parameter, set())
        if not carrying_stations:
            continue
        affected_stations = set(rows[C.STATION_ID].astype(str).unique())
        if affected_stations != carrying_stations:
            continue  # not every carrying station is affected - a local fault, not systemic
        flagged_keys = set(
            zip(
                rows[C.STATION_ID].astype(str),
                rows[C.PARAMETER].astype(str),
                rows[C.TIMESTAMP],
                strict=True,
            )
        )
        if not flagged_keys.issubset(present_cells):
            continue  # an absence-pattern code - a completeness story, not this one
        total_readings = int(present_counts.get(parameter, 0))
        if total_readings == 0:
            continue
        flagged_readings = len(rows)
        fraction = flagged_readings / total_readings
        if fraction < min_fraction:
            continue
        findings.append(
            NetworkWideFinding(
                reason_code=code,
                parameter=parameter,
                station_count=len(carrying_stations),
                flagged_readings=flagged_readings,
                total_readings=total_readings,
                fraction=round(fraction, 6),
            )
        )
    findings.sort(key=lambda f: (-f.fraction, f.reason_code, f.parameter))
    return findings


def _headline(code: str, parameter: str, evidence: dict[str, Any]) -> str:
    return reason_codes.get(code).render(parameter=parameter, **evidence)


def _notable_events(defects: pd.DataFrame) -> list[NotableEvent]:
    """Rank the most report-worthy defects across categories."""
    if defects.empty:
        return []
    candidates: list[tuple[float, str, pd.Series]] = []

    def _add(
        code: str, sort_key: Callable[[dict[str, Any]], float], category: str, limit: int
    ) -> None:
        rows = defects[defects[REASON_CODE] == code]
        if rows.empty:
            return
        scored = sorted(
            (r for _, r in rows.iterrows()), key=lambda r: sort_key(r[EVIDENCE]), reverse=True
        )
        for r in scored[:limit]:
            candidates.append((sort_key(r[EVIDENCE]), category, r))

    # Priority order: physical impossibilities first, then outages/freezes/shifts.
    _add("R07", lambda e: float(e.get("value", 0)), "physical_exceedance", 5)
    _add("R09", lambda e: float(e.get("excess", 0)), "cross_parameter", 5)
    _add("R02", lambda e: float(e.get("missing_ticks", 0)), "communication_outage", 5)
    _add("R12", lambda e: float(e.get("n_readings", 0)), "frozen_sensor", 5)
    _add("R14", lambda e: float(e.get("magnitude", 0)), "step_change", 5)
    _add("R21", lambda e: float(e.get("silent_hours", 0)), "dead_sensor", 3)

    priority = {
        "physical_exceedance": 0,
        "cross_parameter": 1,
        "communication_outage": 2,
        "frozen_sensor": 3,
        "step_change": 4,
        "dead_sensor": 5,
    }
    candidates.sort(key=lambda c: (priority[c[1]], -c[0]))

    events: list[NotableEvent] = []
    seen: set[tuple[Any, ...]] = set()
    for _, category, r in candidates:
        key = (r[REASON_CODE], r[C.STATION_ID], r[C.PARAMETER], str(r[C.TIMESTAMP]))
        if key in seen:
            continue
        seen.add(key)
        events.append(
            NotableEvent(
                rank=len(events) + 1,
                category=category,
                reason_code=str(r[REASON_CODE]),
                station_id=str(r[C.STATION_ID]),
                parameter=str(r[C.PARAMETER]),
                timestamp_utc=pd.Timestamp(r[C.TIMESTAMP]).isoformat(),
                headline=_headline(str(r[REASON_CODE]), str(r[C.PARAMETER]), dict(r[EVIDENCE])),
                severity=str(r["severity"]),
                evidence=dict(r[EVIDENCE]),
            )
        )
    return events


def _defects_records(defects: pd.DataFrame) -> list[dict[str, Any]]:
    if defects.empty:
        return []
    out = defects.copy()
    out[C.TIMESTAMP] = pd.to_datetime(out[C.TIMESTAMP]).map(lambda t: pd.Timestamp(t).isoformat())
    records: list[dict[str, Any]] = [
        {str(k): v for k, v in row.items()} for row in out.to_dict(orient="records")
    ]
    return records

"""The :class:`AuditResult` - everything one audit run produced, in one object.

It is designed to serialise to JSON deterministically: sorted keys, stable float
formatting, and a single ``generated_at`` field that callers exclude when
comparing two runs for byte-identity (standing rule 8). Nothing here renders
anything; the report layer turns this into HTML/Markdown.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from provenance.grid.defect_rate import DefectRate


@dataclass(frozen=True, slots=True)
class RunMeta:
    code_version: str
    config_hash: str
    data_checksum: str
    generated_at: str  # UTC ISO-8601; excluded from determinism comparisons
    n_rows: int


@dataclass(frozen=True, slots=True)
class CoverageSummary:
    n_stations: int
    n_parameters: int
    n_covered_pairs: int
    n_observed_cells: int
    n_absent_cells: int
    n_covered_cells: int
    n_structurally_excluded_cells: int
    n_expected_cells: int
    conventional_completeness_pct: float
    grid_completeness_pct: float
    window_start: str
    window_end: str


@dataclass(frozen=True, slots=True)
class StructuralAbsenceRow:
    station_id: str
    parameter: str
    domain: str
    reason_code: str
    excluded_cells: int


@dataclass(frozen=True, slots=True)
class NotableEvent:
    rank: int
    category: str
    reason_code: str
    station_id: str
    parameter: str
    timestamp_utc: str
    headline: str
    severity: str
    evidence: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AuditResult:
    meta: RunMeta
    coverage: CoverageSummary
    defect_rate: DefectRate
    defects_by_code: dict[str, int]
    defects_by_station: dict[str, int]
    defects_by_parameter: dict[str, int]
    defects_by_day: dict[str, int]
    structural_absences: list[StructuralAbsenceRow]
    notable_events: list[NotableEvent]
    thresholds: dict[str, Any] = field(default_factory=dict)
    defects: list[dict[str, Any]] = field(default_factory=list)
    """The full DefectFrame as records, for report drill-down."""

    def to_dict(self, *, include_generated_at: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "meta": asdict(self.meta),
            "coverage": asdict(self.coverage),
            "defect_rate": {
                "n_defective_cells": self.defect_rate.n_defective_cells,
                "n_covered_cells": self.defect_rate.n_covered_cells,
                "rate": round(self.defect_rate.rate, 6),
                "percent": self.defect_rate.percent,
                "definition": self.defect_rate.definition,
            },
            "defects_by_code": self.defects_by_code,
            "defects_by_station": self.defects_by_station,
            "defects_by_parameter": self.defects_by_parameter,
            "defects_by_day": self.defects_by_day,
            "structural_absences": [asdict(s) for s in self.structural_absences],
            "notable_events": [asdict(e) for e in self.notable_events],
            "thresholds": self.thresholds,
        }
        if not include_generated_at:
            d["meta"] = {k: v for k, v in d["meta"].items() if k != "generated_at"}
        return d

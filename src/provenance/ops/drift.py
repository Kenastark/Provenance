"""Model-plane monitoring: the model-drift monitor (§11).

This is a different question from service health (that lives in the infra plane at
``/metrics``). Here we watch whether the *models and the data* are moving under the
system's feet:

* the deweathering R² over time,
* the fault-classifier confusion matrix over time,
* the conformal interval's empirical coverage over time (does it still hold nominal?),
* the defect-rate drift by station (is a station degrading?).

Keeping this apart from infra monitoring — a separate module here, a separate admin
endpoint, a separate Grafana dashboard — is itself the maturity signal the phase-7
prompt calls out: an SRE watches ``/metrics``; a data scientist watches model drift,
and conflating the two hides both.

The functions here are pure: they turn ordered observations into a drift series with a
baseline, a latest value, and a direction. What history is *available* is the caller's
concern — the defect-rate drift is always computable from the audit runs, while the
model-metric series exist only once models have been trained (their artefacts are
gitignored), and the report says so rather than inventing a trend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DriftPoint:
    at: str
    value: float


@dataclass(frozen=True, slots=True)
class DriftSeries:
    """An ordered metric with its movement summarised — never a bare latest number."""

    name: str
    unit: str
    points: list[DriftPoint]
    baseline: float | None
    latest: float | None
    delta: float | None
    direction: str  # "up" | "down" | "flat" | "unknown"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "points": [{"at": p.at, "value": round(p.value, 6)} for p in self.points],
            "baseline": self.baseline,
            "latest": self.latest,
            "delta": None if self.delta is None else round(self.delta, 6),
            "direction": self.direction,
            "note": self.note,
        }


def _direction(delta: float | None, *, eps: float = 1e-9) -> str:
    if delta is None:
        return "unknown"
    if delta > eps:
        return "up"
    if delta < -eps:
        return "down"
    return "flat"


def drift_series(name: str, unit: str, points: list[DriftPoint], *, note: str = "") -> DriftSeries:
    """Summarise ordered points into a drift series (baseline, latest, delta, direction)."""
    if not points:
        return DriftSeries(name, unit, [], None, None, None, "unknown", note or "no history yet")
    baseline = points[0].value
    latest = points[-1].value
    delta = latest - baseline
    return DriftSeries(name, unit, list(points), baseline, latest, delta, _direction(delta), note)


@dataclass(frozen=True, slots=True)
class RunStationCounts:
    """Per-run, per-station counting-defect and covered-cell counts."""

    run_id: str
    generated_at: str
    counting_defects: dict[str, int]
    covered_cells: dict[str, int]


def defect_rate_drift_by_station(runs: list[RunStationCounts]) -> dict[str, DriftSeries]:
    """A per-station defect-rate (%) series across audit runs, oldest first.

    The rate is counting-defects ÷ covered cells for that station, in percent — the
    same numerator/denominator discipline as the network defect rate (structural
    absences never enter it, standing rule 3). With a single audit run the series is a
    single point and the direction is ``flat``; that is honest, not a bug.
    """
    ordered = sorted(runs, key=lambda r: (r.generated_at, r.run_id))
    stations = sorted({s for r in ordered for s in r.covered_cells})
    out: dict[str, DriftSeries] = {}
    for station in stations:
        points: list[DriftPoint] = []
        for r in ordered:
            covered = r.covered_cells.get(station, 0)
            defects = r.counting_defects.get(station, 0)
            rate = (100.0 * defects / covered) if covered else 0.0
            points.append(DriftPoint(at=r.generated_at, value=rate))
        out[station] = drift_series(
            f"defect_rate::{station}", "percent", points, note="counting defects ÷ covered cells"
        )
    return out


def conformal_coverage_drift(points: list[tuple[str, float]], *, nominal: float) -> DriftSeries:
    """Empirical conformal coverage over time, annotated with the nominal target.

    Drift *toward* nominal is good and *away* is the warning; the note carries the
    nominal so a reader judges the latest value against the promise, not against zero.
    """
    dpts = [DriftPoint(at=at, value=v) for at, v in points]
    series = drift_series("conformal_coverage", "fraction", dpts, note=f"nominal target {nominal}")
    return series


def r2_drift(points: list[tuple[str, float]]) -> DriftSeries:
    """Deweathering R² over time."""
    dpts = [DriftPoint(at=at, value=v) for at, v in points]
    return drift_series("deweather_r2", "r2", dpts)

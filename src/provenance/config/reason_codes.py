"""The reason-code registry.

This is the single source of truth for what Provenance can say about a reading,
and it is deliberately the first real module in the repository, because two of
the project's standing rules live here:

1. A reading is never flagged with a bare code. Every code carries an operator
   sentence written in plain language, because "72% trust" means nothing to a
   city official deciding whether to issue a public warning.
2. Structural absence is not a defect. A station that never carried a wind sensor
   is a fact about the network's coverage, not a failed reading. Codes with
   ``counts_toward_defect_rate = False`` are excluded from both the numerator and
   the denominator of the headline defect rate. Getting this wrong inflates the
   single most scrutinised number in the pitch.

Codes R07 (physical maximum) and R12 (zero variance) are fixed by the blueprint's
dashboard mockups and must not be renumbered.

Stdlib only, on purpose: this module is importable before anything is installed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class Category(StrEnum):
    """Why a check exists, which determines who is expected to act on it."""

    STRUCTURAL = "structural"
    """The shape of the data is wrong: rows absent, duplicated, out of order."""

    PHYSICAL = "physical"
    """The value contradicts physics, chemistry, or the instrument's own limits."""

    STATISTICAL = "statistical"
    """The value is inconsistent with its own history or with its neighbours."""

    COVERAGE = "coverage"
    """A fact about what the network measures. Never a defect."""


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ReasonCode:
    """One thing the system can say about a reading, and how it says it."""

    code: str
    name: str
    sentence: str
    """Plain-language template shown to an operator. May contain {placeholders}
    filled from the detector's evidence dict."""
    category: Category
    severity: Severity
    counts_toward_defect_rate: bool
    implemented_in_phase: int
    notes: str = ""

    def render(self, **evidence: object) -> str:
        """Return the operator sentence with evidence substituted.

        Missing placeholders are left visible rather than raising, so a partially
        populated evidence dict degrades to something still readable on screen.
        """
        try:
            return self.sentence.format(**evidence)
        except (KeyError, IndexError):
            return self.sentence


def _c(
    code: str,
    name: str,
    sentence: str,
    category: Category,
    severity: Severity,
    *,
    counts: bool = True,
    phase: int = 1,
    notes: str = "",
) -> ReasonCode:
    return ReasonCode(
        code=code,
        name=name,
        sentence=sentence,
        category=category,
        severity=severity,
        counts_toward_defect_rate=counts,
        implemented_in_phase=phase,
        notes=notes,
    )


_REGISTRY: tuple[ReasonCode, ...] = (
    # ---------------------------------------------------------------- structural
    _c(
        "R01",
        "ROW_ABSENT",
        "No reading was recorded for this hour.",
        Category.STRUCTURAL,
        Severity.LOW,
        notes="Missingness in this corpus appears as absent rows, not nulls. "
        "Detection requires reindexing against a complete hourly grid.",
    ),
    _c(
        "R02",
        "COMM_GAP",
        "No readings for {duration} - the station stopped transmitting.",
        Category.STRUCTURAL,
        Severity.HIGH,
        notes="A run of R01 long enough to mean communication failure rather than a single lost hour.",
    ),
    _c(
        "R03",
        "DUPLICATE_TIMESTAMP",
        "Two different readings claim the same timestamp.",
        Category.STRUCTURAL,
        Severity.MEDIUM,
    ),
    _c(
        "R04",
        "TIMESTAMP_OUT_OF_ORDER",
        "This reading is timestamped earlier than the one before it.",
        Category.STRUCTURAL,
        Severity.MEDIUM,
    ),
    _c(
        "R05",
        "COUNTER_RESET",
        "The cumulative counter reset from {previous} to {current}.",
        Category.STRUCTURAL,
        Severity.LOW,
        notes="Traffic counters are cumulative and reset frequently (~80-96 times per column). "
        "This is the 'counter repair' step: differencing must be reset-aware.",
    ),
    _c(
        "R06",
        "COUNTER_NONMONOTONIC",
        "The cumulative counter went backwards without a reset.",
        Category.STRUCTURAL,
        Severity.MEDIUM,
    ),
    # ------------------------------------------------------------------ physical
    _c(
        "R07",
        "EXCEEDS_PHYSICAL_MAX",
        "Value of {value} {unit} exceeds the physical maximum for {parameter}.",
        Category.PHYSICAL,
        Severity.CRITICAL,
        notes="Anchor code. Referenced by the dashboard mockups; do not renumber.",
    ),
    _c(
        "R08",
        "BELOW_PHYSICAL_MIN",
        "Value of {value} {unit} is below the physical minimum for {parameter}.",
        Category.PHYSICAL,
        Severity.HIGH,
    ),
    _c(
        "R09",
        "CROSS_PARAM_INVERSION",
        "PM2.5 ({pm25}) exceeds PM10 ({pm10}), which is physically impossible.",
        Category.PHYSICAL,
        Severity.CRITICAL,
        notes="PM2.5 is a subset of PM10 by definition. Confirmed present in the corpus.",
    ),
    _c(
        "R10",
        "UNIT_INCONSISTENT",
        "Declared unit ({declared}) does not match the observed value range, which "
        "is consistent with {inferred}.",
        Category.PHYSICAL,
        Severity.HIGH,
        notes="Confirmed case: CO2 labelled ug/m3 where the range confirms ppm.",
    ),
    _c(
        "R11",
        "DETECTION_LIMIT_FLOOR",
        "Value is pinned at the instrument's detection limit ({limit} {unit}) and is "
        "left-censored, not a measurement.",
        Category.PHYSICAL,
        Severity.MEDIUM,
        notes="Confirmed case: NO floored at its detection limit. Must be modelled as censored.",
    ),
    # --------------------------------------------------------------- statistical
    _c(
        "R12",
        "ZERO_VARIANCE",
        "Reading has not changed for {duration} - likely a frozen sensor.",
        Category.STATISTICAL,
        Severity.HIGH,
        notes="Anchor code. 20+ series in the corpus carry a single unique value across ~700 hours.",
    ),
    _c(
        "R13",
        "LOW_VARIANCE_DEGRADED",
        "Variation over {window} is far below this sensor's normal range.",
        Category.STATISTICAL,
        Severity.MEDIUM,
    ),
    _c(
        "R14",
        "STEP_CHANGE",
        "The series shifted by {magnitude} {unit} and did not return.",
        Category.STATISTICAL,
        Severity.MEDIUM,
        notes="EWMA/CUSUM control chart.",
    ),
    _c(
        "R15",
        "CALIBRATION_EPOCH_DISCONTINUITY",
        "Readings before and after the {date} calibration are not comparable.",
        Category.STATISTICAL,
        Severity.MEDIUM,
    ),
    _c(
        "R16",
        "DRIFT_VS_CONSENSUS",
        "This sensor has drifted {magnitude} {unit} from its neighbours over {window}.",
        Category.STATISTICAL,
        Severity.MEDIUM,
        phase=5,
    ),
    _c(
        "R17",
        "SPATIAL_INCONSISTENCY",
        "This reading contradicts {n} physically connected neighbours.",
        Category.STATISTICAL,
        Severity.HIGH,
        phase=4,
        notes="Requires the wind-conditioned graph. Registered now, implemented in phase 4.",
    ),
    _c(
        "R20",
        "METEO_ARTEFACT_SUSPECTED",
        "The rise is explained by weather conditions, not by an emission source.",
        Category.STATISTICAL,
        Severity.INFO,
        counts=False,
        phase=5,
        notes="An explanation, not a fault. Misclassifying a real inversion event as a fault "
        "is the most damaging error this system can make.",
    ),
    _c(
        "R21",
        "SENSOR_DEAD",
        "This sensor has reported nothing usable since {since}.",
        Category.STATISTICAL,
        Severity.CRITICAL,
        notes="Two traffic counters in the Enclod bundle are silently dead.",
    ),
    # ------------------------------------------------- coverage: NOT defects
    _c(
        "R18",
        "PARAMETER_ABSENT_STRUCTURAL",
        "This station does not carry a {parameter} sensor.",
        Category.COVERAGE,
        Severity.INFO,
        counts=False,
        notes="Confirmed: KER15 carries no wind sensors. Excluded from the defect rate "
        "and reported separately.",
    ),
    _c(
        "R19",
        "SOURCE_ABSENT",
        "No {source} data exists for this station.",
        Category.COVERAGE,
        Severity.INFO,
        counts=False,
        notes="Confirmed: KER02 has no groundwater file.",
    ),
)

REASON_CODES: Mapping[str, ReasonCode] = MappingProxyType({rc.code: rc for rc in _REGISTRY})
"""Immutable registry, keyed by code."""


def get(code: str) -> ReasonCode:
    """Look up a reason code, raising a useful error if it does not exist."""
    try:
        return REASON_CODES[code]
    except KeyError:
        known = ", ".join(sorted(REASON_CODES))
        raise KeyError(f"Unknown reason code {code!r}. Known codes: {known}") from None


def defect_codes() -> tuple[ReasonCode, ...]:
    """Codes that count toward the headline defect rate."""
    return tuple(rc for rc in _REGISTRY if rc.counts_toward_defect_rate)


def coverage_codes() -> tuple[ReasonCode, ...]:
    """Codes that describe what the network measures. Never defects."""
    return tuple(rc for rc in _REGISTRY if not rc.counts_toward_defect_rate)


def codes_for_phase(phase: int) -> tuple[ReasonCode, ...]:
    """Codes expected to be implemented by the end of a given build phase."""
    return tuple(rc for rc in _REGISTRY if rc.implemented_in_phase <= phase)

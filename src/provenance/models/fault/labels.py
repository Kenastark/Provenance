"""The fault taxonomy and the rule→class precedence that the ML must never break.

Seven classes (§7.3). Four are decided **deterministically** by the Phase-1
detectors and short-circuit the model; the ML only ever chooses among the three
subtle classes. Splitting them here — rather than inside the classifier — is what
lets a test assert the precedence directly: a physically-impossible reading resolves
to :data:`FaultClass.PHYSICALLY_IMPOSSIBLE` no matter what the ML would have said.
"""

from __future__ import annotations

from enum import StrEnum


class FaultClass(StrEnum):
    """The seven fault classes the hybrid classifier can assign to a reading."""

    NONE = "none"
    COMMUNICATION_FAILURE = "communication_failure"
    FROZEN = "frozen"
    PHYSICALLY_IMPOSSIBLE = "physically_impossible"
    UNIT_INCONSISTENCY = "unit_inconsistency"
    CALIBRATION_DRIFT = "calibration_drift"
    METEOROLOGICAL_ARTEFACT = "meteorological_artefact"


# Deterministic reason codes → the fault class they force. The ML never overrides any
# of these; the mapping is the rule layer's whole authority.
_RULE_CLASS_MAP: dict[str, FaultClass] = {
    "R07": FaultClass.PHYSICALLY_IMPOSSIBLE,  # exceeds physical maximum
    "R08": FaultClass.PHYSICALLY_IMPOSSIBLE,  # below physical minimum
    "R09": FaultClass.PHYSICALLY_IMPOSSIBLE,  # cross-parameter inversion (PM2.5 > PM10)
    "R02": FaultClass.COMMUNICATION_FAILURE,  # communication gap
    "R12": FaultClass.FROZEN,  # zero variance (frozen sensor)
    "R10": FaultClass.UNIT_INCONSISTENCY,  # declared unit inconsistent with the range
}

# The codes that assert a physical impossibility. Highest precedence of all — the
# standing rule "never let the ML override a deterministic physical-impossibility
# flag" is enforced by giving these priority over every other signal.
PHYSICAL_IMPOSSIBILITY_CODES: frozenset[str] = frozenset({"R07", "R08", "R09"})

# The classes a rule can assign (deterministic; never learned).
DETERMINISTIC_RULE_CLASSES: frozenset[FaultClass] = frozenset(_RULE_CLASS_MAP.values())

# The classes the LightGBM model chooses among — everything the rules cannot see.
SUBTLE_CLASSES: tuple[FaultClass, ...] = (
    FaultClass.NONE,
    FaultClass.CALIBRATION_DRIFT,
    FaultClass.METEOROLOGICAL_ARTEFACT,
)

# Precedence when several deterministic codes fire on one cell: physical impossibility
# outranks everything, then a frozen sensor, then a comms gap, then a unit mismatch.
_PRECEDENCE: tuple[FaultClass, ...] = (
    FaultClass.PHYSICALLY_IMPOSSIBLE,
    FaultClass.FROZEN,
    FaultClass.COMMUNICATION_FAILURE,
    FaultClass.UNIT_INCONSISTENCY,
)


def rule_class_for(codes: set[str]) -> FaultClass | None:
    """The deterministic class for a cell flagged by ``codes``, or ``None`` if none apply.

    When more than one deterministic code fires, the highest-precedence class wins, so
    a reading that is both frozen and physically impossible is reported as physically
    impossible — never downgraded by a coincident softer flag or by the ML.
    """
    candidates = {_RULE_CLASS_MAP[c] for c in codes if c in _RULE_CLASS_MAP}
    for cls in _PRECEDENCE:
        if cls in candidates:
            return cls
    return None

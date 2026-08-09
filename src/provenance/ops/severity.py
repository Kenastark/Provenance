"""One shared severity scale for the operational layer.

The maintenance queue and the Alert Centre both need to turn a severity label into a
number. Keeping the mapping in one place stops the queue and the alerts from drifting
apart — a "critical" must weigh the same wherever it is ranked. These are ordinal
modelling weights, not data-derived constants (standing rule 1): they encode the
fixed ordering critical > high > medium > low > info.
"""

from __future__ import annotations

# Severity weight, used to prioritise maintenance tickets (how urgent the fix is).
SEVERITY_WEIGHT: dict[str, float] = {
    "critical": 1.0,
    "high": 0.7,
    "medium": 0.4,
    "low": 0.2,
    "info": 0.05,
}

# Hazard, used to rank alerts by public-health consequence *if the reading is real*.
# On the same ordinal scale but normalised to [0, 1] so it composes as a factor.
HAZARD: dict[str, float] = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.25,
    "info": 0.1,
}


def severity_weight(severity: str) -> float:
    return SEVERITY_WEIGHT.get(severity, 0.2)


def hazard(severity: str) -> float:
    return HAZARD.get(severity, 0.25)

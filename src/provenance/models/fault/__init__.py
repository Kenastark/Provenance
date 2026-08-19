"""The fault classifier (§7.3): deterministic rules first, LightGBM for the rest.

Hybrid by design, and the order is load-bearing. The deterministic detectors from
Phase 1 run **first** and short-circuit: a physically-impossible reading, a frozen
sensor, a communication gap, a unit mismatch — these are decided by rule, and the ML
model never gets a vote (standing rule: "Never let the ML fault classifier override a
deterministic physical-impossibility flag"). LightGBM handles only the subtle residual
cases the rules cannot see — calibration drift and the meteorological artefact.

That last class is the one to watch. Calling a real inversion event a fault is the
most damaging mistake this system can make (§7.3), so the model card reports
meteorological_artefact precision separately and floors it, and no headline accuracy
figure is ever quoted for the classifier as a whole (standing rule 4).
"""

from __future__ import annotations

from provenance.models.fault.classify import (
    FaultClassifier,
    classify_faults,
    train_fault_classifier,
)
from provenance.models.fault.labels import (
    DETERMINISTIC_RULE_CLASSES,
    PHYSICAL_IMPOSSIBILITY_CODES,
    SUBTLE_CLASSES,
    FaultClass,
    rule_class_for,
)

__all__ = [
    "DETERMINISTIC_RULE_CLASSES",
    "PHYSICAL_IMPOSSIBILITY_CODES",
    "SUBTLE_CLASSES",
    "FaultClass",
    "FaultClassifier",
    "classify_faults",
    "rule_class_for",
    "train_fault_classifier",
]

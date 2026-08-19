"""Explainability (§8): a tree model's output, turned into a reason a human reads.

Two halves:

* :mod:`provenance.explain.shap_explain` computes SHAP attributions over the tree
  models with a stable feature-name mapping, so the same feature always carries the
  same label from the model to the API to the screen.
* :mod:`provenance.explain.render` turns those attributions into the operator
  sentence format — "driven primarily by a sustained 6-day trend deviation, not
  short-term noise" — because a list of feature weights is not an explanation a city
  official can act on.

``explain`` is the last layer in the pipeline; it may import everything upstream
(models included) and is imported only by the presentation layers.
"""

from __future__ import annotations

from provenance.explain.render import feature_phrase, operator_sentence
from provenance.explain.service import (
    DefectRef,
    ExplanationResult,
    explain_defect,
)
from provenance.explain.shap_explain import (
    Attribution,
    ShapExplanation,
    explain_deweather,
    explain_fault,
)

__all__ = [
    "Attribution",
    "DefectRef",
    "ExplanationResult",
    "ShapExplanation",
    "explain_defect",
    "explain_deweather",
    "explain_fault",
    "feature_phrase",
    "operator_sentence",
]

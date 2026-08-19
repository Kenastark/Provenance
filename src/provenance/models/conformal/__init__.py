"""Split conformal prediction: a calibrated interval around any model output (§7.7).

Hand-rolled rather than MAPIE, deliberately — the whole method fits on a slide and a
judge can check it by eye: score the calibration set, take the right order statistic,
and every future prediction gets ``ŷ ± q`` (or ``ŷ ± q·σ`` when the model reports its
own uncertainty) with a finite-sample coverage guarantee. The one rule that must not
bend is that the calibration set is a held-out **time** block, never a random sample
(standing rule 7).
"""

from provenance.models.conformal.split import (
    SplitConformal,
    calibrate,
    conformal_quantile,
    empirical_coverage,
)

__all__ = [
    "SplitConformal",
    "calibrate",
    "conformal_quantile",
    "empirical_coverage",
]

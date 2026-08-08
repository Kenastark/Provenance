"""The HungaroMet weather file-drop adapter (covariate source).

Weather is not a monitored quantity Provenance scores; it is a covariate the
phase-4/5 graph and deweathering layers condition on. The adapter is registered
now so the ingest surface is complete, but the feed's columns are unconfirmed
(``schema_assumptions.yaml``: ``weather``), so ``read()`` fails loudly rather than
guessing wind/pressure column names.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from provenance.io.ingest.base import SourceNotReady


class HungaroMetAdapter:
    source = "hungaromet"
    kind = "covariate"

    def discover(self, root: Path) -> list[Path]:
        root = Path(root)
        return sorted(root.glob("**/hungaromet*.csv")) + sorted(root.glob("**/weather*.csv"))

    def read(self, root: Path) -> pd.DataFrame:
        raise SourceNotReady(
            "HungaroMet weather is a covariate source consumed by the phase-4 "
            "wind-conditioned graph. Its columns are unconfirmed; wire them into "
            "schema_assumptions.yaml (weather) before enabling this adapter."
        )

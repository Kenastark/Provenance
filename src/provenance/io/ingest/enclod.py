"""The Enclod traffic-counter file-drop adapter.

Enclod archive CSVs hold cumulative 15-minute counters (see
``schema_assumptions.yaml``: ``enclod_traffic``). The counter columns are marked
``unconfirmed`` there, so this adapter *discovers* the files but refuses to invent
a schema for them: ``read()`` fails loudly until the columns are confirmed and the
reset-aware differencing from ``io/counter_repair.py`` is wired in. Discovery is
still useful — it proves the drop is present without committing to a parse.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from provenance.config.loading import load_schema_assumptions
from provenance.schema.canonical import SchemaDriftError


class EnclodAdapter:
    source = "enclod_traffic"
    kind = "readings"

    def discover(self, root: Path) -> list[Path]:
        root = Path(root)
        return sorted(root.glob("**/Enclod*/**/*.csv")) + sorted(root.glob("**/enclod*.csv"))

    def read(self, root: Path) -> pd.DataFrame:
        cfg = load_schema_assumptions()["enclod_traffic"]
        if cfg.get("status") != "confirmed" or not cfg.get("counter_column"):
            raise SchemaDriftError(
                "Enclod counter columns are unconfirmed in schema_assumptions.yaml "
                "(enclod_traffic.status). Confirm timestamp/counter columns from a real "
                "archive CSV before enabling this adapter; the reset-aware differencing "
                "in io/counter_repair.py then maps the cumulative counters to canonical."
            )
        raise NotImplementedError(  # pragma: no cover - reached only once columns are confirmed
            "Enclod parsing lands once the columns above are confirmed."
        )

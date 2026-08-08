"""The Green Sentinel file-drop adapter — the one fully-wired source in phase 2.

It delegates to the phase-1 loaders, which already read the real Hungarian-schema
export (and the materialised fixture corpus) into the canonical frame and fail
loudly on drift. Wrapping them in the adapter interface is what lets the loader and
the CLI treat every source uniformly.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from provenance.io import loaders


class GreenSentinelAdapter:
    source = "green_sentinel"
    kind = "readings"

    def discover(self, root: Path) -> list[Path]:
        root = Path(root)
        found: list[Path] = []
        parquet = root / "corpus.parquet"
        if parquet.exists():
            found.append(parquet)
        gs_root = loaders.find_green_sentinel_root(root)
        if gs_root is not None:
            found.extend(sorted(gs_root.glob("DEB-KER*/*.xlsx")))
        return found

    def read(self, root: Path) -> pd.DataFrame:
        return loaders.load_data(Path(root))

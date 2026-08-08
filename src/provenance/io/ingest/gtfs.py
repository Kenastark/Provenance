"""The GTFS static file-drop adapter (reference source).

GTFS static is transit reference data — stops, routes, ridership context — not a
time series of readings. It feeds the PopulationExposure factor of the Risk score,
which is stubbed at 1.0 until this lands (phase 7). The adapter discovers a GTFS
bundle (a zip or the unpacked ``stops.txt``/``routes.txt``) so the drop is
recognised, but ``read()`` reports the source is not yet parsed rather than
returning a readings frame it has no business producing.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from provenance.io.ingest.base import SourceNotReady


class GtfsAdapter:
    source = "gtfs"
    kind = "reference"

    def discover(self, root: Path) -> list[Path]:
        root = Path(root)
        return (
            sorted(root.glob("**/stops.txt"))
            + sorted(root.glob("**/routes.txt"))
            + sorted(root.glob("**/*gtfs*.zip"))
        )

    def read(self, root: Path) -> pd.DataFrame:
        raise SourceNotReady(
            "GTFS static is reference data feeding PopulationExposure (Risk, §7.8), "
            "which is stubbed at 1.0 until phase 7. It produces no readings frame."
        )

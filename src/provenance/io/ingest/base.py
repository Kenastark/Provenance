"""The ingestion abstraction.

Every source of data — the Green Sentinel Excel export today, a Kafka topic
tomorrow — enters the system through one :class:`IngestAdapter`. An adapter's job
is narrow and total: turn its source into the canonical long frame (for readings)
or declare itself a reference/covariate source that the pipeline consumes later.
Nothing downstream of ``read()`` knows or cares which adapter produced the frame,
which is the whole point: adding a streaming adapter is a new class here and *zero*
changes in detectors, audit, or trust. See ``docs/decisions/0003-ingestion-abstraction.md``.

Standing rule 2 lives here too: an adapter for a source whose schema is not yet
confirmed fails loudly (:class:`SchemaDriftError`) rather than inventing column
names. Discovery is always safe to call; only ``read()`` commits to a schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd


class SourceNotReady(Exception):
    """The source is recognised and confirmed to exist, but not yet parseable.

    Distinct from :class:`~provenance.schema.canonical.SchemaDriftError`: the file
    format is simply not implemented for this phase (e.g. GTFS static, wired up in
    phase 7), not a drift from a confirmed assumption.
    """


@runtime_checkable
class IngestAdapter(Protocol):
    """One data source, mapped to the canonical frame."""

    source: str
    """Stable source key, recorded on every ingest batch (e.g. ``green_sentinel``)."""

    kind: str
    """``readings`` (canonical time series), ``covariate`` (weather), or
    ``reference`` (static context such as GTFS)."""

    def discover(self, root: Path) -> list[Path]:
        """Return the input files this adapter recognises under ``root`` (may be empty)."""
        ...

    def read(self, root: Path) -> pd.DataFrame:
        """Read the source under ``root`` into a canonical long frame.

        Raises :class:`SchemaDriftError` on a confirmed-schema mismatch and
        :class:`SourceNotReady` when the format is recognised but not yet parsed.
        """
        ...

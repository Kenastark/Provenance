"""The canonical long frame.

Everything downstream of the loaders speaks one shape: one row per observed
reading, with the columns below. Keeping the whole pipeline on a single validated
frame is what lets a detector be a pure function ``(frame, ctx) -> DefectFrame``
without knowing which file or vendor the reading came from.

``row_hash`` is deterministic: the same reading always hashes to the same value,
across runs and machines, so two audits over the same input produce byte-
identical output (standing rule 8).
"""

from __future__ import annotations

import hashlib
from typing import Final

import pandas as pd
from pandera.pandas import Column, DataFrameSchema


class SchemaDriftError(Exception):
    """The real files do not match ``schema_assumptions.yaml``.

    Raised loudly rather than coerced, per standing rule 2. Carries the specific
    mismatch so the fix is a one-line edit to the assumptions file, not a hunt.
    """


# The canonical column order. Reports and the row hash both depend on it.
STATION_ID: Final = "station_id"
PARAMETER: Final = "parameter"
TIMESTAMP: Final = "timestamp_utc"
VALUE: Final = "value"
UNIT: Final = "unit"
INSTRUMENT_ID: Final = "instrument_id"
SOURCE_FILE: Final = "source_file"
ROW_HASH: Final = "row_hash"

LONG_COLUMNS: Final[tuple[str, ...]] = (
    STATION_ID,
    PARAMETER,
    TIMESTAMP,
    VALUE,
    UNIT,
    INSTRUMENT_ID,
    SOURCE_FILE,
    ROW_HASH,
)

# The columns that identify a reading for hashing. instrument_id and row_hash are
# excluded: the first is often absent, the second is the hash itself.
_HASH_COLUMNS: Final[tuple[str, ...]] = (STATION_ID, PARAMETER, TIMESTAMP, VALUE, UNIT, SOURCE_FILE)


CANONICAL_SCHEMA: Final = DataFrameSchema(
    {
        STATION_ID: Column(str, nullable=False),
        PARAMETER: Column(str, nullable=False),
        TIMESTAMP: Column("datetime64[ns]", nullable=False),
        VALUE: Column(float, nullable=True),
        UNIT: Column(str, nullable=False),
        INSTRUMENT_ID: Column(str, nullable=True, required=True),
        SOURCE_FILE: Column(str, nullable=False),
        ROW_HASH: Column(str, nullable=False, unique=False),
    },
    strict=True,
    ordered=True,
    coerce=True,
)


def _hash_one(
    station: str, parameter: str, ts: pd.Timestamp, value: object, unit: str, src: str
) -> str:
    # ISO-8601 timestamp and repr(value) are both stable across runs; joining with
    # a control character no field can contain avoids accidental collisions.
    parts = (
        str(station),
        str(parameter),
        pd.Timestamp(ts).isoformat(),
        "NaN" if pd.isna(value) else repr(float(value)),  # type: ignore[call-overload,arg-type]
        str(unit),
        str(src),
    )
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()


def add_row_hash(frame: pd.DataFrame) -> pd.DataFrame:
    """Return ``frame`` with a deterministic ``row_hash`` column."""
    out = frame.copy()
    out[ROW_HASH] = [
        _hash_one(
            row[STATION_ID],
            row[PARAMETER],
            row[TIMESTAMP],
            row[VALUE],
            row[UNIT],
            row[SOURCE_FILE],
        )
        for _, row in out.iterrows()
    ]
    return out


def validate(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and coerce a frame to the canonical schema, failing loudly.

    Sorted by (station, parameter, timestamp) so any two runs over the same
    readings yield the same row order - a precondition for deterministic output.
    """
    # Put canonical columns in canonical order when they are all present, so a
    # caller that assembled them in a different order still validates. An extra or
    # missing column changes the set, so the strict schema still rejects it.
    if set(frame.columns) == set(LONG_COLUMNS) and list(frame.columns) != list(LONG_COLUMNS):
        frame = frame[list(LONG_COLUMNS)]
    validated: pd.DataFrame = CANONICAL_SCHEMA.validate(frame)
    validated = validated.sort_values(
        [STATION_ID, PARAMETER, TIMESTAMP], kind="stable"
    ).reset_index(drop=True)
    return validated

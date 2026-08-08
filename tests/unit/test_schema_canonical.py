"""Canonical frame: validation, ordering, and deterministic row hashing."""

from __future__ import annotations

import pytest
from tests.support import series_rows

from provenance.schema import canonical as C
from provenance.schema.canonical import SchemaDriftError


def test_row_hash_is_deterministic(make_frame) -> None:
    frame = make_frame(series_rows("S1", "PM10", [10.0, 11.0, 12.0]))
    again = C.add_row_hash(frame.drop(columns=[C.ROW_HASH]))
    assert list(again[C.ROW_HASH]) == list(frame[C.ROW_HASH])


def test_row_hash_changes_with_value(make_frame) -> None:
    a = make_frame(series_rows("S1", "PM10", [10.0]))
    b = make_frame(series_rows("S1", "PM10", [11.0]))
    assert a[C.ROW_HASH].iloc[0] != b[C.ROW_HASH].iloc[0]


def test_validate_sorts_stably(make_frame) -> None:
    rows = series_rows("S2", "PM10", [1.0, 2.0]) + series_rows("S1", "PM10", [3.0, 4.0])
    frame = make_frame(rows)
    assert list(frame[C.STATION_ID]) == ["S1", "S1", "S2", "S2"]


def test_validate_rejects_unknown_column(make_frame) -> None:
    frame = make_frame(series_rows("S1", "PM10", [10.0]))
    frame["surprise"] = 1
    with pytest.raises(Exception):  # noqa: B017 - pandera raises its own error type
        C.validate(frame)


def test_schema_drift_error_is_raisable() -> None:
    with pytest.raises(SchemaDriftError):
        raise SchemaDriftError("boom")

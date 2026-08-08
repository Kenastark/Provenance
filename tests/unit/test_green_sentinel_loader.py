"""The Green Sentinel workbook loader, exercised on synthetic xlsx files.

These build tiny workbooks in the real export's shape (Hungarian column names,
one sheet named "export", station id in the file name) so the loader path is
covered without ever touching the real dataset (standing rule 7).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from provenance.io import loaders
from provenance.schema import canonical as C
from provenance.schema.canonical import SchemaDriftError

_COLS = ["timestamp", "Location", "Mérőeszköz", "érték", "mértékegység"]


def _workbook(path: Path, parameter: str, unit: str, values: list[float]) -> None:
    times = [f"2026-05-21-{h:02d}-00" for h in range(len(values))]
    df = pd.DataFrame(
        {
            "timestamp": times,
            "Location": ["Test site (47.5, 21.6)"] * len(values),
            "Mérőeszköz": [parameter] * len(values),
            "érték": values,
            "mértékegység": [unit] * len(values),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, sheet_name="export", index=False)


def test_loads_synthetic_green_sentinel_drop(tmp_path: Path) -> None:
    root = tmp_path / "green_sentinel"
    _workbook(root / "DEB-KER01" / "DEB-KER01_Levego.xlsx", "PM10", "µg/m3", [10.0, 12.0, 14.0])
    _workbook(root / "DEB-KER02" / "DEB-KER02_Levego.xlsx", "CO2", "ppm", [450.0, 460.0])
    frame = loaders.load_green_sentinel(tmp_path)
    assert set(frame[C.STATION_ID]) == {"DEB-KER01", "DEB-KER02"}
    assert list(frame.columns) == list(C.LONG_COLUMNS)
    assert frame[C.TIMESTAMP].dtype == "datetime64[ns]"


def test_unknown_parameter_raises_schema_drift(tmp_path: Path) -> None:
    root = tmp_path / "green_sentinel"
    _workbook(root / "DEB-KER01" / "DEB-KER01_Levego.xlsx", "Unobtanium", "µg/m3", [1.0, 2.0])
    with pytest.raises(SchemaDriftError, match="Unknown parameters"):
        loaders.load_green_sentinel(tmp_path)


def test_missing_columns_raise_schema_drift(tmp_path: Path) -> None:
    path = tmp_path / "green_sentinel" / "DEB-KER01" / "DEB-KER01_Levego.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"wrong": [1], "columns": [2]}).to_excel(path, sheet_name="export", index=False)
    with pytest.raises(SchemaDriftError):
        loaders.load_green_sentinel(tmp_path)


def test_empty_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        loaders.load_green_sentinel(tmp_path)


def test_load_data_dispatches_to_green_sentinel(tmp_path: Path) -> None:
    root = tmp_path / "green_sentinel"
    _workbook(root / "DEB-KER01" / "DEB-KER01_Levego.xlsx", "O3", "µg/m3", [30.0, 31.0])
    frame = loaders.load_data(tmp_path)
    assert not frame.empty

"""Loaders that turn vendor files into the canonical long frame.

Standing rules honoured here:

* Field names and units are read from the files, never invented. The Green
  Sentinel columns are Hungarian; the mapping to canonical names lives in
  ``schema_assumptions.yaml`` and any drift raises :class:`SchemaDriftError`.
* Timestamps are normalised to UTC. The export is timezone-naive; we treat it as
  UTC and record that decision in the manifest rather than guessing an offset.
* Nothing is silently coerced. A CO2 value labelled µg/m3 stays labelled that way
  so the unit detector can flag it - the loader does not correct units.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from provenance.config.loading import load_schema_assumptions
from provenance.schema import canonical as C
from provenance.schema.canonical import SchemaDriftError

# Station id is the DEB-KERnn prefix of every workbook file name.
_STATION_RE = re.compile(r"(DEB-KER\d+)", re.IGNORECASE)
_TIMESTAMP_FORMAT = "%Y-%m-%d-%H-%M"

# The Green Sentinel Location column, verified from the real export, is
# "<site name> (<lat>, <lon>)" in decimal degrees, e.g.
# "ÉNYGÖ, BMW körút (47.577175, 21.502204)". The coordinate pair is anchored at the
# end so a site name containing commas still parses; anything else fails loudly
# (standing rule 2: read the format, never invent it).
_LOCATION_RE = re.compile(
    r"^(?P<name>.*?)\s*\(\s*(?P<lat>-?\d+(?:\.\d+)?)\s*,\s*(?P<lon>-?\d+(?:\.\d+)?)\s*\)\s*$"
)


@dataclass(frozen=True, slots=True)
class StationLocation:
    """A station's human-readable site name and decimal-degree coordinates."""

    station_id: str
    name: str
    lat: float
    lon: float


def parse_location(value: str) -> tuple[str, float, float]:
    """Parse a Green Sentinel ``Location`` string into (name, lat, lon).

    Raises :class:`SchemaDriftError` if the ``<name> (lat, lon)`` shape is absent,
    rather than guessing coordinates.
    """
    m = _LOCATION_RE.match(str(value).strip())
    if not m:
        raise SchemaDriftError(
            f"Green Sentinel Location {value!r} is not of the confirmed form "
            "'<site name> (<lat>, <lon>)'. Update schema_assumptions.yaml if the "
            "export's Location format really changed."
        )
    return m.group("name").strip(), float(m.group("lat")), float(m.group("lon"))


def _station_from_name(name: str) -> str:
    m = _STATION_RE.search(name)
    if not m:
        raise SchemaDriftError(
            f"Could not read a DEB-KERnn station id from file name {name!r}. "
            "Green Sentinel workbooks are expected to be named <station>_<domain>.xlsx."
        )
    return m.group(1).upper()


def _read_workbook(path: Path, assumptions: dict[str, Any]) -> pd.DataFrame:
    gs = assumptions["green_sentinel"]
    sheet = gs["sheet_name"]
    expected = {
        gs["timestamp_column"],
        gs["location_column"],
        gs["parameter_column"],
        gs["value_column"],
        gs["unit_column"],
    }
    raw = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    got = set(raw.columns)
    if not expected.issubset(got):
        raise SchemaDriftError(
            f"{path.name}: expected columns {sorted(expected)} but found {sorted(got)}. "
            "Update schema_assumptions.yaml if the export format really changed."
        )

    station = _station_from_name(path.name)
    ts = pd.to_datetime(raw[gs["timestamp_column"]], format=_TIMESTAMP_FORMAT, utc=False)
    frame = pd.DataFrame(
        {
            C.STATION_ID: station,
            C.PARAMETER: raw[gs["parameter_column"]].astype(str),
            C.TIMESTAMP: ts.dt.tz_localize(None),
            C.VALUE: pd.to_numeric(raw[gs["value_column"]], errors="coerce"),
            C.UNIT: raw[gs["unit_column"]].astype(str),
            C.INSTRUMENT_ID: pd.Series([pd.NA] * len(raw), dtype="string"),
            C.SOURCE_FILE: path.name,
        }
    )
    return frame


def find_green_sentinel_root(data_dir: Path) -> Path | None:
    """Return the directory holding the per-station workbook folders, if present.

    The export ships inside a dated ``monitoring_*`` folder; accept either that
    folder or a directory that directly contains ``DEB-KER*`` subfolders.
    """
    data_dir = Path(data_dir)
    if any(data_dir.glob("DEB-KER*")):
        return data_dir
    matches = sorted(data_dir.glob("**/DEB-KER*"))
    if matches:
        return matches[0].parent
    return None


def load_green_sentinel(data_dir: Path) -> pd.DataFrame:
    """Load every Green Sentinel workbook under ``data_dir`` into a canonical frame."""
    assumptions = load_schema_assumptions()
    root = find_green_sentinel_root(data_dir)
    if root is None:
        raise FileNotFoundError(
            f"No Green Sentinel station folders (DEB-KER*) found under {data_dir}."
        )
    workbooks = sorted(root.glob("DEB-KER*/*.xlsx"))
    if not workbooks:
        raise FileNotFoundError(f"No station workbooks found under {root}.")

    frames = [_read_workbook(p, assumptions) for p in workbooks]
    combined = pd.concat(frames, ignore_index=True)
    known = set(assumptions["green_sentinel"]["known_parameters"])
    seen = set(combined[C.PARAMETER].unique())
    unknown = seen - known
    if unknown:
        raise SchemaDriftError(
            f"Unknown parameters {sorted(unknown)} in the export. "
            "Add them to schema_assumptions.yaml (known_parameters) once confirmed."
        )
    combined = C.add_row_hash(combined)
    return C.validate(combined)


def load_canonical(path: Path) -> pd.DataFrame:
    """Load a previously materialised canonical frame (parquet), e.g. a fixture."""
    frame = pd.read_parquet(path)
    if C.ROW_HASH not in frame.columns:
        frame = C.add_row_hash(frame)
    return C.validate(frame)


def load_data(data_dir: Path) -> pd.DataFrame:
    """Load whatever canonical readings live under ``data_dir``.

    Dispatches: a materialised ``corpus.parquet`` (fixtures) wins; otherwise the
    Green Sentinel workbooks are loaded. This is the single entry point the audit
    CLI uses, so a fixture drop and the real export run through the same code.
    """
    data_dir = Path(data_dir)
    parquet = data_dir / "corpus.parquet"
    if parquet.exists():
        return load_canonical(parquet)
    return load_green_sentinel(data_dir)


def load_station_metadata(data_dir: Path) -> dict[str, StationLocation]:
    """Read one site name + coordinate pair per station from the Green Sentinel drop.

    Cheap: only the ``Location`` column's first row of each workbook is read. Returns
    an empty map for the fixture corpus (the canonical parquet carries no Location),
    so the loader populates coordinates for the real export and leaves them null for
    synthetic data — never inventing a coordinate.
    """
    data_dir = Path(data_dir)
    if (data_dir / "corpus.parquet").exists():
        return {}
    root = find_green_sentinel_root(data_dir)
    if root is None:
        return {}
    assumptions = load_schema_assumptions()
    location_col = assumptions["green_sentinel"]["location_column"]
    sheet = assumptions["green_sentinel"]["sheet_name"]
    out: dict[str, StationLocation] = {}
    for path in sorted(root.glob("DEB-KER*/*.xlsx")):
        station = _station_from_name(path.name)
        if station in out:
            continue
        raw = pd.read_excel(
            path, sheet_name=sheet, engine="openpyxl", usecols=[location_col], nrows=1
        )
        if raw.empty or location_col not in raw.columns:
            continue
        name, lat, lon = parse_location(str(raw[location_col].iloc[0]))
        out[station] = StationLocation(station_id=station, name=name, lat=lat, lon=lon)
    return out

"""Seeded synthetic corpus with a ground-truth defect ledger.

Everything in the test suite runs against this, never the real export (standing
rule 7). The generator builds a small, clean, fully deterministic network, then
injects each reason code a known number of times and records, in the ledger, the
exact number of flags the audit is expected to emit for that code. The golden
recovery test asserts the audit reproduces the ledger exactly - if a detector
over- or under-counts, that test fails with the diff.

Design note: injections are placed on separate series and calibrated so they do
not cross-trigger one another. The baseline is a deterministic sum of sinusoids
(not random noise), which gives every series real variance while keeping the
CUSUM step detector quiet, so a clean series produces zero flags.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from provenance.schema import canonical as C

# Injection tables map (station, parameter) -> value array / unit / present-mask.
_ByKey = dict[tuple[str, str], np.ndarray]
_Units = dict[tuple[str, str], str]
_Present = dict[tuple[str, str], np.ndarray]

_HOUR = pd.Timedelta(hours=1)

# Values are quantised to 4 decimals before hashing. np.sin differs in its last
# ULP across CPU architectures, and that tiny difference would otherwise leak into
# the row hash and make the corpus checksum non-portable (arm64 dev vs x86 CI).
# Rounding well above that noise floor makes the synthetic corpus bit-identical
# everywhere - and real sensors report far coarser precision than this anyway.
_QUANTISE_DECIMALS = 4


def _quantise(value: float) -> float:
    return round(float(value), _QUANTISE_DECIMALS)


@dataclass(frozen=True, slots=True)
class ParamSpec:
    name: str
    unit: str
    mean: float
    amp: float
    domain: str


# Six parameters across two domains - enough to exercise every phase-1 detector,
# including the cross-parameter (PM2.5/PM10) and structural (missing source) cases.
_PARAMS: tuple[ParamSpec, ...] = (
    ParamSpec("PM10", "µg/m3", 30.0, 12.0, "air"),
    ParamSpec("PM2.5", "µg/m3", 0.0, 0.0, "air"),  # derived from PM10
    ParamSpec("CO2", "ppm", 450.0, 30.0, "air"),
    ParamSpec("NO", "µg/m3", 12.0, 4.0, "air"),
    ParamSpec("WaterTemp", "celsius", 13.0, 0.5, "water"),
    ParamSpec("WaterLevel", "m", 5.0, 0.3, "water"),
)
_STATIONS = ("STA-01", "STA-02", "STA-03", "STA-04")

# The four injected stations. Every reason code is placed on one of these, so the
# ledger is unchanged no matter how many extra clean stations a caller asks for.
_INJECTED_STATIONS = 4

# Synthetic coordinates for synthetic stations.
#
# The dashboard's map needs somewhere to put a marker, and the fixture corpus is a
# canonical parquet with no Location column - so coordinates are generated here
# rather than read. These are FIXTURE coordinates for FIXTURE stations (STA-nn) and
# make no claim about the real network: the real DEB-KERnn coordinates are parsed
# from the export's Location column at load time and never come from this file.
#
# The lattice is anchored on the one confirmed real coordinate in the repository
# (DEB-KER01 at 47.577175, 21.502204, recorded in schema_assumptions.yaml) so a
# fixture network lands over Debrecen at a plausible scale, which is what makes the
# map legible in a demo. Deterministic: station n always gets the same point.
_FIXTURE_ANCHOR_LAT = 47.577175
_FIXTURE_ANCHOR_LON = 21.502204
_FIXTURE_SPACING_DEG = 0.018


def station_ids(n_stations: int = len(_STATIONS)) -> tuple[str, ...]:
    """``STA-01`` … ``STA-nn``. The first four carry every injected defect."""
    if n_stations < _INJECTED_STATIONS:
        raise ValueError(
            f"The injection layout needs at least {_INJECTED_STATIONS} stations; got {n_stations}."
        )
    return tuple(f"STA-{i:02d}" for i in range(1, n_stations + 1))


def station_locations(n_stations: int = len(_STATIONS)) -> dict[str, dict[str, Any]]:
    """Deterministic synthetic site names and coordinates, laid out on a lattice."""
    out: dict[str, dict[str, Any]] = {}
    for index, station in enumerate(station_ids(n_stations)):
        row, column = divmod(index, 5)
        out[station] = {
            "name": f"Synthetic site {station}",
            # Latitude decreases down the lattice; both are rounded so the sidecar is
            # byte-stable across platforms (standing rule 8).
            "lat": round(_FIXTURE_ANCHOR_LAT - row * _FIXTURE_SPACING_DEG, 6),
            "lon": round(_FIXTURE_ANCHOR_LON + column * _FIXTURE_SPACING_DEG, 6),
        }
    return out


@dataclass
class Ledger:
    """Ground truth: expected audit flag count per reason code, plus notes."""

    expected_counts: dict[str, int] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)
    n_stations: int = 0
    n_parameters: int = 0
    n_days: int = 0
    seed: int = 0

    def bump(self, code: str, n: int, note: str = "") -> None:
        self.expected_counts[code] = self.expected_counts.get(code, 0) + n
        if note:
            self.notes[code] = note

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "n_stations": self.n_stations,
            "n_parameters": self.n_parameters,
            "n_days": self.n_days,
            "expected_counts": {k: self.expected_counts[k] for k in sorted(self.expected_counts)},
            "notes": self.notes,
        }


def _baseline(spec: ParamSpec, station_ix: int, t: np.ndarray) -> np.ndarray:
    """Deterministic diurnal signal; same amplitude across stations.

    A pure daily sinusoid is mean-reverting every 24h, so its CUSUM stays well
    below the decision interval - a clean series produces no R14. (A slow weekly
    drift term, by contrast, IS a sustained trend and would legitimately trip the
    step detector, so it is deliberately omitted.)
    """
    phase = station_ix * 0.7
    # Period 12h keeps each contiguous positive excursion short, so the CUSUM of a
    # clean series peaks near 2.7 - comfortably under the h=5 decision interval.
    cycle = spec.amp * np.sin(2 * np.pi * t / 12 + phase)
    return np.asarray(spec.mean + cycle, dtype=float)


def generate(
    *,
    seed: int = 20260907,
    n_days: int = 14,
    inject: bool = True,
    n_stations: int = len(_STATIONS),
    with_weather: bool = False,
    with_plume: bool = False,
) -> tuple[pd.DataFrame, Ledger]:
    """Build the synthetic corpus and its ledger.

    ``inject=False`` returns a perfectly clean corpus (used to prove the baseline
    trips no detector and to test R09's zero-flag property).

    ``n_stations`` appends additional *clean* stations beyond the four the injection
    layout targets. The ledger's expected counts are therefore unchanged by it - the
    golden recovery test keeps the default four - while `make demo` can ask for a
    network the size of the real one so the dashboard's map has something to show.

    ``with_weather`` and ``with_plume`` are OPT-IN (default ``False``) and layer
    meteorology and a wind-corroborated plume / isolated fault on top, via
    :mod:`provenance.fixtures.demo_scenario` - see that module for what they add.
    Both default off so the default corpus this function returns is byte-identical
    to what it has always been (CLAUDE.md rule 8; the golden recovery ledger pins
    this). ``with_plume`` requires ``with_weather`` - a plume without wind is not a
    plume.
    """
    if inject and n_days < 14:
        raise ValueError(
            "The injection layout places defects at fixed hour offsets up to ~300, "
            "so an injected corpus needs n_days >= 14. Use inject=False for smaller sizes."
        )
    if with_plume and not with_weather:
        raise ValueError("with_plume requires with_weather (a plume needs a wind field to ride).")
    stations = station_ids(n_stations)
    hours = n_days * 24
    t = np.arange(hours)
    start = pd.Timestamp("2026-05-01T00:00:00")
    times = pd.DatetimeIndex([start + i * _HOUR for i in range(hours)])
    ledger = Ledger(n_stations=len(stations), n_parameters=len(_PARAMS), n_days=n_days, seed=seed)

    by_key: dict[tuple[str, str], np.ndarray] = {}
    units: dict[tuple[str, str], str] = {}
    present: dict[tuple[str, str], np.ndarray] = {}  # boolean mask of present hours

    pm10_index = {s: _baseline(_PARAMS[0], i, t) for i, s in enumerate(stations)}
    for i, station in enumerate(stations):
        for spec in _PARAMS:
            if spec.name == "PM2.5":
                values = 0.45 * pm10_index[station]  # subset of PM10 by construction
            else:
                values = _baseline(spec, i, t).copy()
            by_key[(station, spec.name)] = values
            units[(station, spec.name)] = spec.unit
            present[(station, spec.name)] = np.ones(hours, dtype=bool)

    if with_weather:
        from provenance.fixtures.demo_scenario import add_wind

        add_wind(by_key, units, present, ledger, hours=hours, t=t, stations=stations)

    if inject:
        _inject(by_key, units, present, ledger, hours)

    if with_plume:
        from provenance.fixtures.demo_scenario import add_plume

        add_plume(by_key, ledger, hours=hours, stations=stations)

    frame = _materialise(by_key, units, present, times)
    return frame, ledger


def _inject(by_key: _ByKey, units: _Units, present: _Present, ledger: Ledger, hours: int) -> None:
    # Every injection lands on one of the first four stations, so extra clean
    # stations never shift the ledger.
    sta_a, sta_b, sta_c, sta_d = _STATIONS[:_INJECTED_STATIONS]

    # R01 ROW_ABSENT: 5 scattered interior hours removed from CO2 at station A.
    for h in (30, 60, 90, 120, 150):
        present[(sta_a, "CO2")][h] = False
    ledger.bump("R01", 5, "5 interior hours removed from CO2@STA-01")

    # R02 COMM_GAP: one 12-hour outage on NO at station D (also 12 more absent -> R01).
    # A full 12h cycle is removed so the surrounding sinusoid stays phase-continuous
    # and the outage does not masquerade as a step change.
    for h in range(204, 216):
        present[(sta_d, "NO")][h] = False
    ledger.bump("R02", 1, "one 12h outage on NO@STA-04")
    ledger.bump("R01", 12, "the 12h outage hours also count as absent")

    # R03 DUPLICATE_TIMESTAMP: 2 duplicated hours on WaterTemp at station A.
    ledger.bump("R03", 2, "2 duplicate (station,parameter,hour) rows on WaterTemp@STA-01")
    present[("__dup__", "WaterTemp")] = np.array([24, 48])  # hours to duplicate
    by_key[("__dup__", "WaterTemp")] = np.array([13.9, 12.1])  # differing values at those hours
    units[("__dup__", "WaterTemp")] = "celsius"

    # R07 EXCEEDS_PHYSICAL_MAX: 3 impossible PM10 values at station C.
    for h in (12, 36, 300):
        by_key[(sta_c, "PM10")][h] = 3000.0
    ledger.bump("R07", 3, "3 PM10 values at 3000 µg/m3 (> 2000 max) at STA-03")

    # R08 BELOW_PHYSICAL_MIN: 2 impossible WaterTemp values at station C.
    for h in (100, 220):
        by_key[(sta_c, "WaterTemp")][h] = -10.0
    ledger.bump("R08", 2, "2 WaterTemp values at -10 C (< -5 min) at STA-03")

    # R09 CROSS_PARAM_INVERSION: 4 hours where PM2.5 exceeds PM10 at station A.
    for h in (10, 70, 130, 190):
        by_key[(sta_a, "PM2.5")][h] = by_key[(sta_a, "PM10")][h] + 5.0
    ledger.bump("R09", 4, "4 hours of PM2.5 > PM10 at STA-01")

    # R10 UNIT_INCONSISTENT: CO2 at station B mislabelled µg/m3 (values are ppm).
    units[(sta_b, "CO2")] = "µg/m3"
    ledger.bump("R10", hours, "whole CO2 series at STA-02 mislabelled µg/m3")

    # R11 DETECTION_LIMIT_FLOOR: an 8-hour run pinned at the NO floor at station A.
    for h in range(50, 58):
        by_key[(sta_a, "NO")][h] = 0.7
    ledger.bump("R11", 8, "8h run at the 0.7 µg/m3 NO floor at STA-01")

    # R12 ZERO_VARIANCE: WaterLevel at station A frozen at one value.
    by_key[(sta_a, "WaterLevel")][:] = 5.0
    ledger.bump("R12", hours, "WaterLevel@STA-01 frozen for the whole record")

    # R13 LOW_VARIANCE_DEGRADED: PM10 at station D abnormally flat vs peers.
    # Period-12 (like the baseline) so this degraded series stays CUSUM-quiet.
    by_key[(sta_d, "PM10")] = 30.0 + 0.05 * np.sin(2 * np.pi * np.arange(hours) / 12)
    ledger.bump("R13", hours, "PM10@STA-04 near-flat relative to peer stations")

    # R14 STEP_CHANGE: a sustained upward shift in NO at station B, halfway through.
    half = hours // 2
    by_key[(sta_b, "NO")][half:] += 15.0
    ledger.bump("R14", 1, "one sustained +15 µg/m3 step in NO@STA-02")

    # R18 PARAMETER_ABSENT_STRUCTURAL: station C carries no NO sensor.
    present[(sta_c, "NO")][:] = False
    del by_key[(sta_c, "NO")]
    ledger.bump("R18", 1, "NO absent entirely from STA-03 (a network-standard sensor)")

    # R19 SOURCE_ABSENT: station D has no groundwater source at all.
    for pname in ("WaterTemp", "WaterLevel"):
        present[(sta_d, pname)][:] = False
        del by_key[(sta_d, pname)]
    ledger.bump("R19", 2, "both groundwater parameters absent from STA-04 (whole source)")


def _materialise(
    by_key: _ByKey, units: _Units, present: _Present, times: pd.DatetimeIndex
) -> pd.DataFrame:
    rows_station: list[str] = []
    rows_param: list[str] = []
    rows_ts: list[pd.Timestamp] = []
    rows_val: list[float] = []
    rows_unit: list[str] = []
    rows_src: list[str] = []

    for (station, parameter), values in by_key.items():
        if station == "__dup__":
            # Duplicate rows: value array carries values, present array carries hours.
            hours_ix = present[(station, parameter)]
            real_station = "STA-01"
            for hix, val in zip(hours_ix.tolist(), values.tolist(), strict=True):
                rows_station.append(real_station)
                rows_param.append(parameter)
                rows_ts.append(times[int(hix)])
                rows_val.append(_quantise(val))
                rows_unit.append(units[(station, parameter)])
                rows_src.append(f"{real_station}_water.csv")
            continue
        domain = _domain_for(parameter)
        src = f"{station}_{domain}.csv"
        mask = present[(station, parameter)]
        unit = units[(station, parameter)]
        for hix in np.nonzero(mask)[0]:
            rows_station.append(station)
            rows_param.append(parameter)
            rows_ts.append(times[int(hix)])
            rows_val.append(_quantise(values[hix]))
            rows_unit.append(unit)
            rows_src.append(src)

    frame = pd.DataFrame(
        {
            C.STATION_ID: rows_station,
            C.PARAMETER: rows_param,
            C.TIMESTAMP: rows_ts,
            C.VALUE: rows_val,
            C.UNIT: rows_unit,
            C.INSTRUMENT_ID: pd.Series([pd.NA] * len(rows_station), dtype="string"),
            C.SOURCE_FILE: rows_src,
        }
    )
    frame = C.add_row_hash(frame)
    return C.validate(frame)


def _domain_for(parameter: str) -> str:
    for spec in _PARAMS:
        if spec.name == parameter:
            return spec.domain
    return "air"


def write_corpus(
    out_dir: Path,
    *,
    seed: int = 20260907,
    n_days: int = 14,
    n_stations: int = len(_STATIONS),
    with_weather: bool = False,
    with_plume: bool = False,
) -> dict[str, Path]:
    """Materialise the corpus, ledger and station sidecar to ``out_dir``.

    ``stations.json`` is the fixture equivalent of the Green Sentinel ``Location``
    column: the canonical parquet has no place for a site name or a coordinate, and
    the loader will not invent one. Writing it here means the dashboard's map works
    against fixtures without any code path guessing where a station is.

    ``with_weather``/``with_plume`` are opt-in and passed straight to
    :func:`generate` - see there and :mod:`provenance.fixtures.demo_scenario`.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame, ledger = generate(
        seed=seed,
        n_days=n_days,
        n_stations=n_stations,
        with_weather=with_weather,
        with_plume=with_plume,
    )
    paths = {
        "corpus": out_dir / "corpus.parquet",
        "ledger": out_dir / "ledger.json",
        "stations": out_dir / "stations.json",
    }
    frame.to_parquet(paths["corpus"], index=False)
    paths["ledger"].write_text(
        json.dumps(ledger.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["stations"].write_text(
        json.dumps(station_locations(n_stations), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return paths

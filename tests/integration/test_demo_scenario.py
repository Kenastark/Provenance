"""`--with-weather --with-plume`: opt-in, additive, and correct on its own physics.

Three things standing rule 8 and the golden ledger require of this feature:

1. The default corpus (no flags) is untouched - proven directly here, on top of
   the golden recovery test's existing coverage of `generate()`'s default path.
2. The opt-in corpus is itself deterministic.
3. The planted plume and fault are not just present but actually adjudicate the
   way the feature exists to demonstrate: GENUINE_EVENT for the corroborated
   plume, LIKELY_FAULT for the isolated spike - using the real adjudicator, the
   real wind-edge weights, not an assumption about what "should" happen.
"""

from __future__ import annotations

import pandas as pd
import pytest

from provenance.config.loading import load_graph_config
from provenance.fixtures.demo_scenario import (
    _FAULT_HOUR_FROM_END,
    _FAULT_STATION_INDEX,
    _NO_WIND_STATION_INDEX,
    _PLUME_HOUR_FROM_END,
    _PLUME_STATION_INDEX,
    _TARGET_PARAM,
    WIND_DIRECTION_PARAM,
    WIND_SPEED_PARAM,
)
from provenance.fixtures.generator import generate, station_ids, station_locations
from provenance.graph.adjudicate import Verdict, validate_event
from provenance.graph.replay import build_candidate
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindField
from provenance.schema import canonical as C

_N_STATIONS = 18
_N_DAYS = 14
_START = pd.Timestamp("2026-05-01T00:00:00")


def test_default_output_is_unaffected_by_the_opt_in_flags() -> None:
    plain, plain_ledger = generate(n_stations=_N_STATIONS)
    off, off_ledger = generate(n_stations=_N_STATIONS, with_weather=False, with_plume=False)
    assert plain.equals(off)
    assert plain_ledger.to_dict() == off_ledger.to_dict()


def test_with_plume_without_with_weather_is_rejected() -> None:
    with pytest.raises(ValueError, match="with_weather"):
        generate(n_stations=_N_STATIONS, with_plume=True)


def test_opt_in_corpus_is_deterministic() -> None:
    f1, l1 = generate(n_stations=_N_STATIONS, with_weather=True, with_plume=True)
    f2, l2 = generate(n_stations=_N_STATIONS, with_weather=True, with_plume=True)
    assert f1.equals(f2)
    assert l1.to_dict() == l2.to_dict()


def test_exactly_one_station_carries_no_wind_sensor() -> None:
    frame, _ = generate(n_stations=_N_STATIONS, with_weather=True)
    wind_stations = set(
        frame.loc[frame[C.PARAMETER].isin([WIND_SPEED_PARAM, WIND_DIRECTION_PARAM]), C.STATION_ID]
    )
    stations = station_ids(_N_STATIONS)
    missing = set(stations) - wind_stations
    assert missing == {stations[_NO_WIND_STATION_INDEX]}


def test_pm25_never_exceeds_pm10_once_weather_is_coupled() -> None:
    # R09 (cross_parameter) must stay at its ledger-pinned count of 4 (STA-01's
    # deliberately injected inversion hours) - the wind coupling must not create
    # any *extra* ones by pushing PM10 below PM2.5 elsewhere.
    from provenance.audit.orchestrator import run_audit

    frame, ledger = generate(n_stations=_N_STATIONS, with_weather=True)
    result = run_audit(frame)
    assert result.defects_by_code.get("R09", 0) == ledger.to_dict()["expected_counts"]["R09"]


def test_plume_reads_genuine_and_fault_reads_likely_fault() -> None:
    frame, _ = generate(n_stations=_N_STATIONS, n_days=_N_DAYS, with_weather=True, with_plume=True)
    stations = station_ids(_N_STATIONS)
    locations = station_locations(_N_STATIONS)
    points = [StationPoint(s, loc["lat"], loc["lon"]) for s, loc in locations.items()]
    wind = WindField.from_frame(frame)
    cfg = load_graph_config()

    plume_station = stations[_PLUME_STATION_INDEX]
    fault_station = stations[_FAULT_STATION_INDEX]
    hours = _N_DAYS * 24
    plume_ts = _START + pd.Timedelta(hours=hours - _PLUME_HOUR_FROM_END)
    fault_ts = _START + pd.Timedelta(hours=hours - _FAULT_HOUR_FROM_END)

    plume_candidate = build_candidate(
        frame, plume_station, _TARGET_PARAM, plume_ts, window_hours=48
    )
    fault_candidate = build_candidate(
        frame, fault_station, _TARGET_PARAM, fault_ts, window_hours=48
    )
    assert plume_candidate is not None
    assert fault_candidate is not None

    plume_adj = validate_event(plume_candidate, points, wind, frame, cfg)
    fault_adj = validate_event(fault_candidate, points, wind, frame, cfg)

    assert plume_adj.verdict is Verdict.GENUINE_EVENT
    assert plume_adj.evidence.match_score >= cfg["adjudicator"]["genuine_match_threshold"]
    assert fault_adj.verdict is Verdict.LIKELY_FAULT
    assert fault_adj.evidence.match_score == 0.0

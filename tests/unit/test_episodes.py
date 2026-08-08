"""Fault episodes: collapsing per-cell flags into distinct faults."""

from __future__ import annotations

import pandas as pd
from tests.support import series_rows

from provenance.config.loading import load_thresholds
from provenance.detectors import registry
from provenance.detectors.base import REASON_CODE, AuditContext
from provenance.detectors.episodes import defect_episodes, empty_episode_frame
from provenance.grid.coverage import build_coverage
from provenance.schema import canonical as C


def _frame(specs: list[tuple[str, str, list[float]]]) -> pd.DataFrame:
    rows: list[dict] = []
    for station, parameter, values in specs:
        rows += series_rows(station, parameter, values)
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
    return C.validate(C.add_row_hash(frame))


def _episodes(frame: pd.DataFrame) -> pd.DataFrame:
    coverage = build_coverage(frame)
    ctx = AuditContext(thresholds=load_thresholds(), coverage=coverage)
    return defect_episodes(registry.run_detectors(frame, ctx), coverage)


def test_a_continuous_freeze_is_one_episode_not_one_per_cell() -> None:
    frame = _frame([("S1", "PM10", [42.0] * 48)])
    frozen = _episodes(frame)
    frozen = frozen[frozen[REASON_CODE] == "R12"]
    assert len(frozen) == 1, frozen
    assert int(frozen.iloc[0]["n_cells"]) == 48


def test_separated_faults_are_separate_episodes() -> None:
    values = [30.0 + (i % 7) for i in range(48)]
    values[10] = 5000.0  # two impossible readings, far apart
    values[40] = 5000.0
    frame = _frame([("S1", "PM10", values)])
    spikes = _episodes(frame)
    spikes = spikes[spikes[REASON_CODE] == "R07"]
    assert len(spikes) == 2
    assert set(spikes["n_cells"]) == {1}


def test_adjacent_faults_merge_into_one_episode() -> None:
    values = [30.0 + (i % 7) for i in range(48)]
    values[10] = values[11] = values[12] = 5000.0  # three consecutive hours
    frame = _frame([("S1", "PM10", values)])
    spikes = _episodes(frame)
    spikes = spikes[spikes[REASON_CODE] == "R07"]
    assert len(spikes) == 1
    assert int(spikes.iloc[0]["n_cells"]) == 3


def test_episodes_never_merge_across_code_parameter_or_station() -> None:
    frame = _frame([("S1", "PM10", [42.0] * 48), ("S1", "NO2", [7.0] * 48)])
    episodes = _episodes(frame)
    frozen = episodes[episodes[REASON_CODE] == "R12"]
    assert set(frozen[C.PARAMETER]) == {"PM10", "NO2"}
    assert len(frozen) == 2  # one per series, never pooled


def test_empty_defects_give_an_empty_frame() -> None:
    frame = _frame([("S1", "PM10", [30.0 + (i % 7) for i in range(48)])])
    coverage = build_coverage(frame)
    assert defect_episodes(empty_episode_frame(), coverage).empty


def test_episode_count_never_exceeds_flag_count() -> None:
    frame = _frame(
        [("S1", "PM10", [42.0] * 48), ("S2", "PM10", [30.0 + (i % 5) for i in range(48)])]
    )
    coverage = build_coverage(frame)
    ctx = AuditContext(thresholds=load_thresholds(), coverage=coverage)
    defects = registry.run_detectors(frame, ctx)
    episodes = defect_episodes(defects, coverage)
    assert len(episodes) <= len(defects)
    assert int(episodes["n_cells"].sum()) <= len(defects)

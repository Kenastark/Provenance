"""The maintenance queue's state machine and priority (§9.5, phase 7)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from provenance.ops import maintenance as mnt

pytestmark = pytest.mark.unit


@dataclass
class _Fault:
    station_id: str
    parameter: str
    reason_code: str
    severity: str


def test_lifecycle_allows_only_forward_moves() -> None:
    assert mnt.can_transition(mnt.OPEN, mnt.ACKNOWLEDGED)
    assert mnt.can_transition(mnt.ACKNOWLEDGED, mnt.DISPATCHED)
    assert mnt.can_transition(mnt.DISPATCHED, mnt.RESOLVED)
    assert mnt.can_transition(mnt.ACKNOWLEDGED, mnt.RESOLVED)  # cleared without a dispatch
    # No skipping and no going back.
    assert not mnt.can_transition(mnt.OPEN, mnt.DISPATCHED)
    assert not mnt.can_transition(mnt.DISPATCHED, mnt.ACKNOWLEDGED)
    assert not mnt.can_transition(mnt.RESOLVED, mnt.OPEN)


def test_check_transition_raises_on_an_illegal_move() -> None:
    with pytest.raises(mnt.InvalidTransitionError):
        mnt.check_transition(mnt.OPEN, mnt.RESOLVED)
    with pytest.raises(mnt.InvalidTransitionError):
        mnt.check_transition(mnt.OPEN, "nonsense")


def test_priority_is_severity_times_importance() -> None:
    # critical (1.0) at a busy corridor (1.6) beats critical at a quiet one (0.6).
    assert mnt.priority("critical", 1.6) > mnt.priority("critical", 0.6)
    # A low-severity fault at a busy site can still fall below a critical at a quiet one.
    assert mnt.priority("low", 1.6) < mnt.priority("critical", 0.6)


def test_build_specs_groups_and_ranks_by_priority() -> None:
    faults = [
        _Fault("STA-01", "PM10", "R12", "high"),
        _Fault("STA-01", "PM10", "R12", "high"),  # same ticket, second flag
        _Fault("STA-02", "PM10", "R07", "critical"),
    ]
    importance = {"STA-01": 1.6, "STA-02": 0.6}
    specs = mnt.build_specs(faults, importance)

    assert len(specs) == 2  # two distinct (station, parameter, code) groups
    frozen = next(s for s in specs if s.reason_code == "R12")
    assert frozen.n_flags == 2
    assert frozen.importance == 1.6
    # Priority order: R12 high×1.6 = 1.12 vs R07 critical×0.6 = 0.6.
    assert specs[0].reason_code == "R12"


def test_build_specs_is_deterministic() -> None:
    faults = [
        _Fault("STA-02", "NO", "R11", "medium"),
        _Fault("STA-01", "PM10", "R12", "high"),
    ]
    a = mnt.build_specs(faults, {})
    b = mnt.build_specs(list(reversed(faults)), {})
    assert [s.reason_code for s in a] == [s.reason_code for s in b]

"""The demo runs fully offline (§ phase-7.6 test gate). Demo-critical.

Conference wifi will fail; the demo must not. This blocks all network egress —
``socket.socket.connect``, ``create_connection``, and DNS — and then runs the entire
demo scenario suite and the CLI rehearsal. If anything reached for the network (a tile
server, an external API), these tests would raise ``OfflineViolationError`` instead of
completing.
"""

from __future__ import annotations

import socket

import pytest
from typer.testing import CliRunner

from provenance.cli.main import app
from provenance.ops import demo

pytestmark = pytest.mark.demo_critical


class OfflineViolationError(Exception):
    """Raised if the code under test attempts any network egress."""


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*args, **kwargs):
        raise OfflineViolationError("network egress attempted during the offline demo")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)


def test_scenarios_build_with_network_blocked(no_network: None, demo_drop: dict) -> None:
    scenarios = demo.build_all(demo_drop["frame"], demo_drop["meta"])
    assert set(scenarios) == set(demo.available_scenarios())
    for sc in scenarios.values():
        assert sc.steps


def test_cli_rehearse_runs_offline(no_network: None, demo_drop: dict, tmp_path) -> None:
    result = CliRunner().invoke(
        app,
        ["demo", "rehearse", "--data", str(demo_drop["path"]), "--out", str(tmp_path / "demo")],
    )
    assert result.exit_code == 0, result.output
    written = list((tmp_path / "demo").glob("*.json"))
    # One file per scenario plus the index.
    assert len(written) == len(demo.available_scenarios()) + 1

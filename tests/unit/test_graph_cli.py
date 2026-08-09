"""The `prov graph` command line: adjudicate and snapshot over a data drop."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from provenance.cli.main import app
from provenance.graph import scenarios as S

runner = CliRunner()


def _write_drop(directory: Path) -> None:
    """Materialise a scenario as a loadable drop (corpus.parquet + stations.json)."""
    scenario = S.corroborated_plume()
    directory.mkdir(parents=True, exist_ok=True)
    scenario.frame.to_parquet(directory / "corpus.parquet", index=False)
    stations = {
        p.station_id: {"name": p.station_id, "lat": p.lat, "lon": p.lon} for p in scenario.points
    }
    (directory / "stations.json").write_text(json.dumps(stations), encoding="utf-8")


def test_graph_adjudicate_writes_bundles_and_prints_verdicts(tmp_path: Path) -> None:
    drop = tmp_path / "drop"
    out = tmp_path / "adj"
    _write_drop(drop)

    result = runner.invoke(app, ["graph", "adjudicate", "--data", str(drop), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "Adjudicated events" in result.output  # the table rendered
    # The verdict itself is asserted from the written bundle, which the narrow table
    # cell in captured output would otherwise truncate.
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert index[0]["verdict"] == "GENUINE_EVENT"
    assert index[0]["station_id"] == "SCEN-SRC"


def test_graph_snapshot_prints_shape(tmp_path: Path) -> None:
    drop = tmp_path / "drop"
    _write_drop(drop)
    result = runner.invoke(app, ["graph", "snapshot", "--data", str(drop)])
    assert result.exit_code == 0, result.output
    assert "EnvStation" in result.output


def test_graph_help_lists_commands() -> None:
    result = runner.invoke(app, ["graph", "--help"])
    assert result.exit_code == 0
    assert "adjudicate" in result.output
    assert "snapshot" in result.output

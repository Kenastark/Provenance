"""io loaders: canonical round-trip and the data-drop dispatcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from provenance.io import loaders
from provenance.schema import canonical as C


def test_load_canonical_round_trips(tmp_path: Path, synthetic_corpus) -> None:
    frame, _ = synthetic_corpus
    path = tmp_path / "corpus.parquet"
    frame.to_parquet(path, index=False)
    loaded = loaders.load_canonical(path)
    assert len(loaded) == len(frame)
    assert list(loaded.columns) == list(C.LONG_COLUMNS)


def test_load_data_prefers_corpus_parquet(tmp_path: Path) -> None:
    from provenance.fixtures.generator import write_corpus

    write_corpus(tmp_path)
    frame = loaders.load_data(tmp_path)
    assert not frame.empty
    assert "STA-01" in set(frame[C.STATION_ID])


def test_load_data_raises_on_empty_dir(tmp_path: Path) -> None:
    with pytest.raises((FileNotFoundError, ValueError)):
        loaders.load_data(tmp_path)

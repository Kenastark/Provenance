"""The model caches: load once, and never remember an absence.

Two properties are pinned here. A second call must not read the artefact from disk again —
that is the whole point of warming the caches at API startup rather than paying the load on
someone's first request. And a ``None`` must never be cached: a missing artefact is a normal
state (standing rule 6), so an API process that started before ``prov models train`` ran has
to pick the model up on a later call instead of reporting "no model" for its whole lifetime.

The loaders are monkeypatched rather than fed real artefacts: what is under test is the
cache's behaviour, and the load path itself is covered by ``test_model_registry.py`` and
``test_hstgat_train.py``. Identity (``is``) is the assertion throughout — an equal object
would mean a second deserialisation, which is exactly what these caches exist to avoid.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from provenance.models import registry
from provenance.models.hstgat import store
from provenance.models.hstgat.store import LoadedModel
from provenance.models.registry import ModelBundle

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _cold_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts cold and leaves no cached state behind for the next one."""
    monkeypatch.setattr(registry, "_BUNDLE_CACHE", {})
    monkeypatch.setattr(store, "_LATEST_CACHE", {})


def _a_bundle() -> ModelBundle:
    """A stand-in for a loaded bundle; these tests only ever inspect its identity."""
    return cast(ModelBundle, object())


def _a_model() -> LoadedModel:
    return cast(LoadedModel, object())


def test_bundle_is_read_from_disk_only_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = _a_bundle()
    calls = 0

    def load_once(artefacts_dir: Path | None = None) -> ModelBundle | None:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise AssertionError("load_bundle went back to disk on a cache hit")
        return bundle

    monkeypatch.setattr(registry, "load_bundle", load_once)

    first = registry.load_bundle_cached(tmp_path)
    second = registry.load_bundle_cached(tmp_path)

    assert first is bundle
    assert second is first  # the same object, not an equal one
    assert calls == 1


def test_hstgat_is_read_from_disk_only_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = _a_model()
    calls = 0

    def load_once(
        name: str = "hst-gat", *, artefacts_dir: Path | None = None
    ) -> LoadedModel | None:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise AssertionError("load_latest went back to disk on a cache hit")
        return model

    monkeypatch.setattr(store, "load_latest", load_once)

    first = store.load_latest_cached(artefacts_dir=tmp_path)
    second = store.load_latest_cached(artefacts_dir=tmp_path)

    assert first is model
    assert second is first
    assert calls == 1


def test_absent_bundle_is_never_cached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A model trained after the process started must still be picked up: caching the None
    # would pin "no model" for the life of the API (standing rule 6).
    bundle = _a_bundle()
    results: list[ModelBundle | None] = [None, bundle]

    def load_then_appear(artefacts_dir: Path | None = None) -> ModelBundle | None:
        return results.pop(0)

    monkeypatch.setattr(registry, "load_bundle", load_then_appear)

    assert registry.load_bundle_cached(tmp_path) is None
    assert registry.load_bundle_cached(tmp_path) is bundle


def test_absent_hstgat_is_never_cached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = _a_model()
    results: list[LoadedModel | None] = [None, model]

    def load_then_appear(
        name: str = "hst-gat", *, artefacts_dir: Path | None = None
    ) -> LoadedModel | None:
        return results.pop(0)

    monkeypatch.setattr(store, "load_latest", load_then_appear)

    assert store.load_latest_cached(artefacts_dir=tmp_path) is None
    assert store.load_latest_cached(artefacts_dir=tmp_path) is model


def test_cache_is_keyed_by_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Two artefact directories are two different stores; a hit on one must not serve the
    # other. The tests pass an explicit artefacts_dir, so this is the key that matters.
    first_dir, second_dir = tmp_path / "one", tmp_path / "two"
    by_dir = {first_dir: _a_bundle(), second_dir: _a_bundle()}

    def load_for_dir(artefacts_dir: Path | None = None) -> ModelBundle | None:
        assert artefacts_dir is not None
        return by_dir[artefacts_dir]

    monkeypatch.setattr(registry, "load_bundle", load_for_dir)

    assert registry.load_bundle_cached(first_dir) is by_dir[first_dir]
    assert registry.load_bundle_cached(second_dir) is by_dir[second_dir]
    assert registry.load_bundle_cached(first_dir) is by_dir[first_dir]

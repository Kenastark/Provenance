from __future__ import annotations

from provenance.config.settings import Settings, get_settings


def test_defaults_are_usable_without_an_env_file() -> None:
    s = Settings(_env_file=None)
    assert s.env
    assert s.random_seed


def test_settings_are_cached() -> None:
    assert get_settings() is get_settings()

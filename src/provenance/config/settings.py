"""Runtime settings. Everything configurable lives here or in a YAML next to it."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Environment-driven configuration.

    Values come from the process environment, then `.env`, then these defaults.
    Secrets never have a default.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = Field(default="local", alias="PROVENANCE_ENV")
    log_level: str = Field(default="INFO", alias="PROVENANCE_LOG_LEVEL")

    database_url: str = Field(
        default="postgresql+psycopg://provenance:provenance@localhost:5432/provenance",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    data_raw: Path = Field(default=REPO_ROOT / "data" / "raw", alias="PROVENANCE_DATA_RAW")
    reports_dir: Path = Field(default=REPO_ROOT / "reports", alias="PROVENANCE_REPORTS_DIR")

    api_keys_json: str = Field(default="", alias="PROVENANCE_API_KEYS")
    """Optional JSON ``{api_key: role}`` map. Empty means use the local-dev keys in
    ``api/auth.py``. Full OIDC is deferred to phase 7 (ADR 0004)."""

    random_seed: int = 20260907
    """Global seed. Every run of every pipeline is reproducible from this."""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Call this rather than instantiating Settings."""
    return Settings()

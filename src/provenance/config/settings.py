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

    data_raw: Path = Field(default=REPO_ROOT / "data" / "raw", alias="PROVENANCE_DATA_RAW")
    reports_dir: Path = Field(default=REPO_ROOT / "reports", alias="PROVENANCE_REPORTS_DIR")

    artefacts_dir: Path = Field(
        default=REPO_ROOT / "src" / "provenance" / "models" / "artefacts",
        alias="PROVENANCE_ARTEFACTS_DIR",
    )
    """Where trained model artefacts and their card sidecars live. Gitignored (see
    ``.gitignore``): models are reproducible from ``prov models train`` and never
    committed. Missing artefacts are not an error — the system degrades gracefully to
    the statistics layer and says so (standing rule 6)."""

    model_docs_dir: Path = Field(
        default=REPO_ROOT / "docs" / "model-cards",
        alias="PROVENANCE_MODEL_DOCS_DIR",
    )
    """Where the human-readable model cards are written at training time. The
    auto-generated ML cards (``deweather-*``/``fault-*``) are gitignored — they are
    reproducible from ``prov models train`` and their filenames carry the data
    checksum, so committing them would only churn. The hand-written cards (the
    propagation adjudicator) stay tracked."""

    api_keys_json: str = Field(default="", alias="PROVENANCE_API_KEYS")
    """Optional JSON ``{api_key: role}`` map. Empty means use the local-dev keys in
    ``api/auth.py``. Full OIDC is deferred to phase 7 (ADR 0004)."""

    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:4173",
        alias="PROVENANCE_CORS_ORIGINS",
    )
    """Comma-separated origins allowed to call the API from a browser.

    The dashboard is a browser client on a different origin to the API, so without
    this every request fails preflight and the screens render empty. The default
    covers the two local ports the frontend uses (Vite dev and Vite preview) and
    nothing else — this is an allow-list, never ``*``, because the API accepts an
    API key header and a wildcard origin would let any page on the internet spend
    an operator's credentials."""

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    random_seed: int = 20260907
    """Global seed. Every run of every pipeline is reproducible from this."""

    learned_propagation: bool = Field(default=False, alias="PROVENANCE_LEARNED_PROPAGATION")
    """Phase-6 feature flag. When true, the propagation adjudicator swaps its analytic
    expectation for the HST-GAT forecast (§6.4). Off by default: the analytic prior is
    the shipped, demoable path, and the learned one is opt-in. If the flag is on but the
    model artefact is absent or fails to load, the adjudicator falls back to the analytic
    prior automatically and records which path produced the verdict (standing rule 6)."""

    torch_device: str = Field(default="cpu", alias="PROVENANCE_TORCH_DEVICE")
    """Device for the neural stack. ``cpu`` is the deterministic default CI uses (ADR
    0009); ``mps`` is opt-in on Apple Silicon. An unavailable device falls back to CPU
    with a logged warning rather than crashing."""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Call this rather than instantiating Settings."""
    return Settings()

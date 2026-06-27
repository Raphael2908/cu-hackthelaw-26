from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized typed config. Every external key has a mock-safe blank default so the whole
    stack boots with no secrets. Production fails loudly if real mode has no Anthropic key."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Runtime ---
    ENV: Literal["development", "production"] = "development"
    PROVIDER_MODE: Literal["mock", "real"] = "mock"
    LOG_LEVEL: str = "info"

    # --- API / CORS ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost"

    # --- Store ---
    SQLITE_PATH: str = "data/cockpit.sqlite"

    # --- Dispatch --- Approving a plan runs each AI/hybrid task's worker→checker→ranker pipeline.
    # In real mode that is many slow model calls, so dispatch is enqueued to Celery and the approve
    # request returns immediately; the cockpit reflects progress as tasks finish. With this off,
    # the pipeline runs inline in-process (no broker needed) — the test/offline fallback.
    ASYNC_DISPATCH: bool = True

    # --- Celery / Redis --- broker + result backend for off-request dispatch (architecture.md §8).
    # Mock-safe defaults: the broker is only contacted on enqueue, so the stack still boots without
    # Redis. Compose overrides these to redis://redis:... inside its network.
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # --- LLM (Anthropic) --- blank = mock mode
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-4-8"

    # --- EU Cellar (live citation source, architecture.md §7.1/§9) --- opt-in. Default OFF so the
    # stack stays fully offline (fixtures only) and tests never touch the network. When enabled, the
    # citation-support signal fetches a source by CELEX from the EU Publications Office on a local
    # miss; the seeded fixtures remain the offline fallback.
    CELLAR_ENABLED: bool = False
    CELLAR_BASE_URL: str = "http://publications.europa.eu"
    CELLAR_LANGUAGE: str = "en"
    CELLAR_TIMEOUT: float = 10.0
    CELLAR_SPARQL_PATH: str = "/webapi/rdf/sparql"  # CDM knowledge graph, for title/type metadata
    CELLAR_USER_AGENT: str = "supervision-cockpit/1.0 (legal-AI-supervision; +contact)"

    # --- Risk signal tuning (architecture.md §7) ---
    SAMPLE_RATE: float = 0.2
    DISAGREEMENT_RUNS: int = 3
    W_CITATION: float = 0.5
    W_DEVIATION: float = 0.3
    W_DISAGREEMENT: float = 0.2

    # --- Delegation track record (architecture.md §6) --- Minimum completed AI/hybrid tasks on a
    # process-map section, all clean (no amend/reject), before the planner graduates that section to
    # AI by default. Delegation is decided by task nature, never severity; the track record only
    # graduates (clean) or pulls back (adverse) on top of the planner's nature-based suggestion.
    AI_TRACK_RECORD_MIN: int = 3

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _require_key_in_real_mode(self) -> Settings:
        if self.ENV == "production" and self.PROVIDER_MODE == "real" and not self.ANTHROPIC_API_KEY:
            raise ValueError("PROVIDER_MODE=real in production requires ANTHROPIC_API_KEY.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

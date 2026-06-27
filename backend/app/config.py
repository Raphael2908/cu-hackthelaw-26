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
    # In real mode that is many slow model calls, so dispatch runs in a background thread pool and
    # the approve request returns immediately; the cockpit reflects progress as tasks finish. Tests
    # disable this (conftest) to keep assertions synchronous and deterministic.
    ASYNC_DISPATCH: bool = True
    DISPATCH_WORKERS: int = 4

    # --- LLM (Anthropic) --- blank = mock mode
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-4-8"
    # Output budget per structured call. The default was 2048, which truncated the worker's JSON
    # mid-string on large real-world documents (e.g. Harvey Labs review tasks) — see todo.md.
    ANTHROPIC_MAX_TOKENS: int = 32768

    # --- Risk signal tuning (architecture.md §7) ---
    SAMPLE_RATE: float = 0.2
    DISAGREEMENT_RUNS: int = 3
    W_CITATION: float = 0.5
    W_DEVIATION: float = 0.3
    W_DISAGREEMENT: float = 0.2

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

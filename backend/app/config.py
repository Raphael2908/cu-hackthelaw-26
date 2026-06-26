from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized typed config. Every external key has a mock-safe blank default so the whole
    stack boots with no secrets (PROVIDER_MODE=mock). Production fails loudly if creds are blank.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Runtime ---
    ENV: Literal["development", "production"] = "development"
    ROLE: Literal["api", "worker", "beat"] = "api"
    PROVIDER_MODE: Literal["mock", "real"] = "mock"
    LOG_LEVEL: str = "info"

    # --- API / CORS ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost"

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Supabase (DB + Auth) ---
    SUPABASE_URL: str = ""  # blank → auth/repo raise 503; mock stack doesn't need it
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_SECRET_KEY: str = ""

    # --- AWS / S3 (uploaded documents + outputs) ---
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "eu-west-1"
    S3_BUCKET: str = ""  # blank → storage returns mock presigned URLs

    # --- LLM (Anthropic Claude) ---
    ANTHROPIC_API_KEY: str = ""  # blank → mock LLM returns canned agent output
    LLM_MODEL_PLANNER: str = "claude-opus-4-8"
    LLM_MODEL_AGENT: str = "claude-sonnet-4-6"
    LLM_MODEL_EVAL: str = "claude-opus-4-8"

    # --- Web research (Perplexity) ---
    PERPLEXITY_API_KEY: str = ""  # blank → mock research results
    PERPLEXITY_MODEL: str = "sonar-pro"

    # --- EU legal corpus (CELLAR) ---
    CELLAR_BASE_URL: str = "https://publications.europa.eu/webapi/rdf/sparql"

    # --- Reranker ---
    RERANK_MODE: Literal["deterministic", "cohere"] = "deterministic"
    COHERE_API_KEY: str = ""
    COHERE_RERANK_MODEL: str = "rerank-v3.5"

    # --- Pipeline defaults / guards ---
    DEFAULT_EVAL_DOC_COUNT: int = 5  # N: docs the evaluator scrutinises (lawyer-overridable)
    MAX_INFLIGHT_TASKS: int = 20
    RATE_LIMIT_PER_MIN: int = 60
    VENDOR_CONCURRENCY_LLM: int = 8
    VENDOR_CONCURRENCY_PERPLEXITY: int = 4
    TASK_MAX_RETRIES: int = 3
    AGENT_TIMEOUT_S: int = 240

    # --- Email (optional) ---
    RESEND_API_KEY: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _require_core_in_production(self) -> Settings:
        if self.ENV == "production":
            missing = [
                n
                for n in ("SUPABASE_URL", "SUPABASE_SECRET_KEY")
                if not getattr(self, n)
            ]
            if missing:
                raise ValueError(
                    "Missing required production settings: " + ", ".join(missing)
                )
            if self.PROVIDER_MODE == "real" and not self.ANTHROPIC_API_KEY:
                raise ValueError("PROVIDER_MODE=real in production requires ANTHROPIC_API_KEY")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

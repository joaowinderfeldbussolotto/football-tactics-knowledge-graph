"""Configuração central da PoC, lida de variáveis de ambiente / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM ---
    llm_provider: Literal["anthropic", "openai", "gemini", "openai_compatible"] = "anthropic"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-5"
    llm_small_model: str = "claude-haiku-4-5-20251001"
    llm_base_url: str | None = None
    llm_max_retries: int = 5

    # --- Embeddings ---
    embedder_provider: Literal["openai", "gemini"] = "openai"
    embedder_api_key: str = ""
    embedder_model: str = "text-embedding-3-small"

    # --- Concorrência ---
    semaphore_limit: int = Field(default=5, alias="SEMAPHORE_LIMIT")

    # --- Neo4j ---
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"

    # --- Redis ---
    redis_url: str = "redis://redis:6379/0"

    # --- Langfuse ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = False

    # --- StatsBomb ---
    statsbomb_match_ids: str = ""
    statsbomb_replay_speed: float = 60.0

    @property
    def match_ids(self) -> list[str]:
        return [m.strip() for m in self.statsbomb_match_ids.split(",") if m.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

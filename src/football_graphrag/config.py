"""Configuração central, lida do .env via pydantic-settings.

Regra do projeto (docs/05-decisoes.md): trocar de provedor de LLM é editar
LLM_PROVIDER no .env, nada mais. Nenhum outro módulo lê os.environ direto,
exceto o Graphiti, que lê SEMAPHORE_LIMIT nativamente.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM ---
    llm_provider: Literal["mistral", "anthropic", "gemini"] = "mistral"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_small_model: str = ""
    llm_max_retries: int = 5  # repassado ao construtor do SDK; não é camada nossa

    # --- Embeddings ---
    embedder_provider: str = ""
    embedder_api_key: str = ""
    embedder_model: str = ""

    # --- Concorrência ---
    # Lido nativamente pelo Graphiti (env SEMAPHORE_LIMIT); reaproveitado no
    # semáforo de aplicação que envolve cada agent.run() do PydanticAI.
    semaphore_limit: int = 5

    # Pacing proativo da indexação do Graphiti (segundos entre triplets).
    # Cada triplet faz ~3-4 chamadas de embedding; 2.0 mantém a indexação
    # dentro da cota free-tier do Gemini (100 embed-requests/min). Com chave
    # paga, use 0. O retry nativo (LLM_MAX_RETRIES) cobre o que passar disso.
    graphiti_pace_seconds: float = 2.0

    # --- Neo4j ---
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"

    # --- Langfuse (vazio desliga a instrumentação) ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # --- Dados ---
    statsbomb_match_ids: str = "3869685,3869519,3869354"
    data_dir: Path = Path("data")

    @property
    def match_ids(self) -> list[int]:
        return [int(m) for m in self.statsbomb_match_ids.split(",") if m.strip()]

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"


@lru_cache
def get_settings() -> Settings:
    return Settings()

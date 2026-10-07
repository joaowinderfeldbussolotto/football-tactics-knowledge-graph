"""Configuração central, lida do .env via pydantic-settings.

Regra do projeto: trocar de provedor de LLM é
editar LLM_PROVIDER no .env, nada mais. Nenhum outro módulo lê os.environ direto.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM ---
    # "openrouter" é um agregador compatível com OpenAI: dá acesso a modelos de
    # vários laboratórios por uma chave só. Não serve embeddings — EMBEDDER_PROVIDER
    # continua sendo configurado à parte.
    llm_provider: Literal["mistral", "anthropic", "gemini", "openrouter"] = "mistral"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_max_retries: int = 5  # repassado ao construtor do SDK; não é camada nossa
    # Teto de tokens de SAÍDA por chamada dos agentes.
    # Em modelo de raciocínio o raciocínio oculto conta contra este teto: se ele o
    # consome inteiro, a chamada termina com finish_reason "length" e SEM texto, e o
    # PydanticAI levanta "Model token limit (N) exceeded before any response was
    # generated". O default é o valor que o código sempre usou.
    llm_max_tokens: int = 16000
    # Esforço de raciocínio, enviado como extra_body["reasoning"]["effort"] — só
    # openrouter. Vazio = não envia nada (comportamento do modelo). Opt-in porque
    # esforço menor pode piorar o uso de ferramenta e a saída estruturada, e isso
    # não foi medido neste projeto.
    llm_reasoning_effort: Literal["", "none", "low", "medium", "high"] = ""

    # --- Embeddings ---
    embedder_provider: str = ""
    embedder_api_key: str = ""
    embedder_model: str = ""

    # --- Neo4j ---
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"

    # --- Langfuse (vazio desliga a instrumentação) ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # --- Dados ---
    # Benchmark: só a final (Argentina x França). Outras partidas continuam
    # suportadas pela pipeline, mas não entram nas perguntas.
    statsbomb_match_ids: str = "3869685"
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

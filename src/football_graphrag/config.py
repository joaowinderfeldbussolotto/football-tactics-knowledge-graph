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
    llm_provider: Literal["mistral", "anthropic", "gemini", "openrouter", "bedrock"] = "mistral"
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
    # Provedor FIXO no OpenRouter, enviado como extra_body["provider"] com
    # allow_fallbacks=false: o pedido falha em vez de cair em outro provedor (que
    # pode custar várias vezes mais ou servir outra quantização). Slug do provedor
    # como na página do modelo, ex. "baidu/fp8"; vários separados por vírgula
    # formam uma ordem de preferência. Vazio = o OpenRouter escolhe. Só openrouter.
    llm_provider_order: str = ""
    # Amazon Bedrock (API Converse). LLM_MODEL é o ID do modelo no Bedrock (ou do perfil de
    # inferência, ex. "us.<id>"). LLM_API_KEY é uma chave de API do Bedrock (bearer); vazio =
    # credenciais AWS padrão (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, perfil ou papel).
    # LLM_AWS_REGION vazio = AWS_REGION / AWS_DEFAULT_REGION do ambiente.
    llm_aws_region: str = ""
    # Marca o fim dos dados do prompt como ponto de cache (benchmark: braços com tabela de
    # eventos). Desligue em modelo cujo provedor não aceita cache de prompt: o ponto de cache
    # não muda o que o modelo lê, só a conta.
    llm_prompt_cache: bool = True

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

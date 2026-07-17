"""Troca de provedor de LLM. Módulo inteiro do "abstraction layer" do projeto.

Regra (seção 4 do plano): nada de interface própria. No PydanticAI o provedor
é uma string; no Graphiti é escolher a classe do cliente. Este módulo só faz
esse mapeamento a partir do .env. Retry é dos SDKs (max_retries nativo);
rate limiting é o SEMAPHORE_LIMIT lido pelo Graphiti + um asyncio.Semaphore
de aplicação em api/agents.py.
"""

from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.embedder import EmbedderClient, OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client import LLMClient, LLMConfig

from football_graphrag.config import Settings

MISTRAL_BASE_URL = "https://api.mistral.ai/v1"

# Prefixo de modelo do PydanticAI por provedor (docs do PydanticAI).
_PYDANTIC_AI_PREFIX = {"mistral": "mistral", "anthropic": "anthropic", "gemini": "google-gla"}


def pydantic_ai_model_name(settings: Settings) -> str:
    """String de modelo do PydanticAI, ex: 'anthropic:claude-haiku-4-5'."""
    return f"{_PYDANTIC_AI_PREFIX[settings.llm_provider]}:{settings.llm_model}"


def pydantic_ai_model(settings: Settings):
    """Modelo PydanticAI com a credencial do .env injetada explicitamente.

    A forma-string ('anthropic:<modelo>') deixaria o PydanticAI ler a env var
    do próprio provedor (ANTHROPIC_API_KEY etc.); aqui a chave vem de
    LLM_API_KEY, então construímos o Model com o Provider explícito.
    Validado ao vivo com Anthropic (ver ADR-5).
    """
    if settings.llm_provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        return AnthropicModel(settings.llm_model, provider=AnthropicProvider(api_key=settings.llm_api_key))
    if settings.llm_provider == "mistral":
        from pydantic_ai.models.mistral import MistralModel
        from pydantic_ai.providers.mistral import MistralProvider

        return MistralModel(settings.llm_model, provider=MistralProvider(api_key=settings.llm_api_key))
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    return GoogleModel(settings.llm_model, provider=GoogleProvider(api_key=settings.llm_api_key))


def graphiti_llm_client(settings: Settings) -> LLMClient:
    """Cliente de LLM do Graphiti para o provedor configurado (camada 3 apenas)."""
    config = LLMConfig(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        small_model=settings.llm_small_model or settings.llm_model,
    )
    if settings.llm_provider == "mistral":
        # Mistral expõe endpoint compatível com OpenAI; ver docs/05-decisoes.md
        # sobre structured_output_mode caso o json_schema falhe.
        from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

        config.base_url = MISTRAL_BASE_URL
        return OpenAIGenericClient(config=config)
    if settings.llm_provider == "anthropic":
        from graphiti_core.llm_client.anthropic_client import AnthropicClient

        return AnthropicClient(config=config)
    from graphiti_core.llm_client.gemini_client import GeminiClient

    return GeminiClient(config=config)


def graphiti_embedder(settings: Settings) -> EmbedderClient:
    """Embedder do Graphiti. Anthropic não tem API de embeddings, então o
    provedor de embeddings é configurado à parte (EMBEDDER_PROVIDER)."""
    if settings.embedder_provider == "gemini":
        from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig

        return GeminiEmbedder(
            config=GeminiEmbedderConfig(
                api_key=settings.embedder_api_key, embedding_model=settings.embedder_model
            )
        )
    # Default: qualquer endpoint compatível com OpenAI (inclui mistral-embed).
    base_url = MISTRAL_BASE_URL if settings.embedder_provider == "mistral" else None
    return OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=settings.embedder_api_key,
            embedding_model=settings.embedder_model,
            base_url=base_url,
        )
    )


def graphiti_cross_encoder(settings: Settings) -> CrossEncoderClient:
    """Reranker da busca híbrida. Atenção (validado ao vivo, ver ADR-5):
    passar None faz o Graphiti instanciar o OpenAIRerankerClient default,
    que exige OPENAI_API_KEY — não existe fallback "sem reranker". Então:
    - provedor gemini, ou embedder gemini: GeminiRerankerClient (usa a chave
      Gemini disponível; modelo default do próprio cliente);
    - mistral: OpenAIRerankerClient apontado para o endpoint compatível.
    """
    if settings.llm_provider == "gemini" or settings.embedder_provider == "gemini":
        from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient

        api_key = settings.llm_api_key if settings.llm_provider == "gemini" else settings.embedder_api_key
        return GeminiRerankerClient(config=LLMConfig(api_key=api_key))
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

    return OpenAIRerankerClient(
        config=LLMConfig(
            api_key=settings.llm_api_key,
            model=settings.llm_small_model or settings.llm_model,
            base_url=MISTRAL_BASE_URL if settings.llm_provider == "mistral" else None,
        )
    )

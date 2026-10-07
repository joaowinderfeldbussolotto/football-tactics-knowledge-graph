"""Troca de provedor de LLM. Módulo inteiro do "abstraction layer" do projeto.

Regra (seção 4 do plano): nada de interface própria, nada de tenacity, nada
de token bucket. Todo o tratamento de rate limit (429) é feito pelos knobs
NATIVOS de cada SDK, configurados aqui uma única vez a partir do .env:

- ``LLM_MAX_RETRIES`` é repassado ao construtor de cada SDK:
  - Anthropic/OpenAI-compat: ``max_retries`` (os SDKs respeitam o header
    Retry-After do servidor com backoff exponencial);
  - google-genai: ``HttpRetryOptions`` (backoff exponencial com jitter até
    ``max_delay`` — dimensionado para atravessar a janela de 1 min das cotas
    free-tier do Gemini, cujo retryDelay chega a ~50 s);
  - mistralai: ``RetryConfig(strategy="backoff")``.

"""

import logging

from football_graphrag.config import Settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Prefixo de modelo do PydanticAI por provedor (docs do PydanticAI).
_PYDANTIC_AI_PREFIX = {
    "mistral": "mistral",
    "anthropic": "anthropic",
    "gemini": "google-gla",
    "openrouter": "openrouter",
}


# ---------------------------------------------------------------------------
# Clientes SDK com retry nativo configurado (uma fábrica por SDK)
# ---------------------------------------------------------------------------

def _anthropic_sdk_client(settings: Settings):
    from anthropic import AsyncAnthropic

    return AsyncAnthropic(api_key=settings.llm_api_key, max_retries=settings.llm_max_retries)


def _openai_compat_sdk_client(api_key: str, base_url: str | None, settings: Settings):
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=settings.llm_max_retries)


def _genai_retry_options(settings: Settings):
    """Retry nativo do google-genai, dimensionado para cotas por minuto.

    Free-tier do Gemini devolve 429 com retryDelay de até ~50 s; o backoff
    exponencial (2,4,8,...) com ``max_delay=65`` e attempts suficientes cruza
    a virada do minuto sem nenhuma camada própria de retry.
    """
    from google.genai import types

    return types.HttpRetryOptions(
        attempts=settings.llm_max_retries + 2,  # inclui a tentativa original
        initial_delay=2.0,
        max_delay=65.0,
        exp_base=2.0,
        jitter=0.5,
        http_status_codes=[429, 500, 502, 503, 504],
    )


def _mistral_sdk_client(settings: Settings):
    from mistralai.client import Mistral
    from mistralai.client.utils.retries import BackoffStrategy, RetryConfig

    return Mistral(
        api_key=settings.llm_api_key,
        retry_config=RetryConfig(
            strategy="backoff",
            backoff=BackoffStrategy(
                initial_interval=2000,       # ms
                max_interval=65000,          # ms — cruza a janela de 1 min
                exponent=2.0,
                max_elapsed_time=180000,     # ms
            ),
            retry_connection_errors=True,
        ),
    )


# ---------------------------------------------------------------------------
# PydanticAI
# ---------------------------------------------------------------------------

def pydantic_ai_model_name(settings: Settings) -> str:
    """String de modelo do PydanticAI, ex: 'anthropic:claude-haiku-4-5'."""
    return f"{_PYDANTIC_AI_PREFIX[settings.llm_provider]}:{settings.llm_model}"


def pydantic_ai_model(settings: Settings):
    """Modelo PydanticAI com credencial do .env e retry nativo injetados.

    A forma-string ('anthropic:<modelo>') leria a env var do próprio provedor
    e usaria os defaults de retry do SDK; aqui o Model recebe o cliente SDK
    já configurado com LLM_MAX_RETRIES (validado ao vivo, ADR-5/ADR-7).
    """
    if settings.llm_provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        return AnthropicModel(
            settings.llm_model,
            provider=AnthropicProvider(anthropic_client=_anthropic_sdk_client(settings)),
        )
    if settings.llm_provider == "mistral":
        from pydantic_ai.models.mistral import MistralModel
        from pydantic_ai.providers.mistral import MistralProvider

        return MistralModel(
            settings.llm_model,
            provider=MistralProvider(mistral_client=_mistral_sdk_client(settings)),
        )
    if settings.llm_provider == "openrouter":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        openai_client = _openai_compat_sdk_client(settings.llm_api_key, OPENROUTER_BASE_URL, settings)
        return OpenAIChatModel(
            settings.llm_model,
            provider=OpenRouterProvider(
                openai_client=openai_client,
                app_title="football-tactics-knowledge-graph",
            ),
        )
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    return GoogleModel(
        settings.llm_model,
        provider=GoogleProvider(
            api_key=settings.llm_api_key, retry_options=_genai_retry_options(settings)
        ),
    )


def pydantic_ai_model_settings(settings: Settings) -> dict:
    """Settings de chamada dos agentes (``Agent(model_settings=...)``).

    Fica aqui porque o que muda de provedor para provedor é responsabilidade
    desta camada — e porque a ``extra_body`` que o
    OpenRouter entende não existe nos outros.

    ``max_tokens`` vem de ``LLM_MAX_TOKENS``. ``LLM_REASONING_EFFORT`` só é
    traduzido para o OpenRouter, via ``extra_body["reasoning"]``: o projeto usa
    ``OpenAIChatModel`` com ``OpenRouterProvider``, e é esse o caminho que esse
    modelo envia (a tradução ``openrouter_reasoning`` pertence à classe
    ``OpenRouterModel``, que não é a usada). Em outro provedor a opção é
    ignorada COM aviso — ignorar em silêncio faria parecer que o botão
    funciona.
    """
    configuradas: dict = {"max_tokens": settings.llm_max_tokens}
    esforco = settings.llm_reasoning_effort
    if esforco:
        if settings.llm_provider == "openrouter":
            configuradas["extra_body"] = {"reasoning": {"effort": esforco}}
        else:
            logger.warning(
                "LLM_REASONING_EFFORT=%s ignorado: só é traduzido para o provedor openrouter "
                "(provedor atual: %s)",
                esforco, settings.llm_provider,
            )
    return configuradas


# ---------------------------------------------------------------------------
# Embeddings (the benchmark's "vector" arm)
# ---------------------------------------------------------------------------

MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
EMBED_BATCH = 100  # Gemini's batch limit; fine for OpenAI-compatible endpoints too


async def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    """Embed texts in batches with the provider configured in EMBEDDER_*.

    One request per batch of 100, so the 2.6k event lines of a match cost
    ~26 requests (the Gemini free tier allows 100 requests per minute).
    Retries are the SDK's own (LLM_MAX_RETRIES), as everywhere else.
    """
    vectors: list[list[float]] = []
    batches = [texts[i : i + EMBED_BATCH] for i in range(0, len(texts), EMBED_BATCH)]
    if settings.embedder_provider == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=settings.embedder_api_key,
            http_options=types.HttpOptions(retry_options=_genai_retry_options(settings)),
        )
        for batch in batches:
            result = await client.aio.models.embed_content(model=settings.embedder_model, contents=batch)
            vectors.extend(e.values for e in result.embeddings)
        return vectors
    # Default: any OpenAI-compatible endpoint (includes mistral-embed).
    base_url = MISTRAL_BASE_URL if settings.embedder_provider == "mistral" else None
    client = _openai_compat_sdk_client(settings.embedder_api_key, base_url, settings)
    for batch in batches:
        result = await client.embeddings.create(model=settings.embedder_model, input=batch)
        vectors.extend(d.embedding for d in result.data)
    return vectors

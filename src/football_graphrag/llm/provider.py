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
- Concorrência continua sendo só o ``SEMAPHORE_LIMIT`` (lido pelo Graphiti e
  reaproveitado no semáforo de aplicação em api/agents.py).
- O único pacing proativo do projeto fica na indexação do Graphiti
  (``GRAPHITI_PACE_SECONDS``, ver graph/communities.py), porque lá o número
  de chamadas é previsível e evitar o 429 é mais barato que absorvê-lo.

Validações ao vivo registradas no ADR-5/ADR-7 de docs/05-decisoes.md.
"""

import asyncio
import json
import logging

from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.embedder import EmbedderClient, OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client import LLMClient, LLMConfig

from football_graphrag.config import Settings

logger = logging.getLogger(__name__)

MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Prefixo de modelo do PydanticAI por provedor (docs do PydanticAI).
_PYDANTIC_AI_PREFIX = {
    "mistral": "mistral",
    "anthropic": "anthropic",
    "gemini": "google-gla",
    "openrouter": "openrouter",
}

# Provedores servidos por um endpoint compatível com OpenAI (Mistral e
# OpenRouter caem no mesmo caminho no Graphiti: OpenAIGenericClient/
# OpenAIEmbedder/OpenAIRerankerClient, só muda a base URL).
_OPENAI_COMPAT_BASE_URL = {"mistral": MISTRAL_BASE_URL, "openrouter": OPENROUTER_BASE_URL}


def _openai_compat_base_url(provider: str) -> str | None:
    """Base URL do endpoint compatível com OpenAI, ou None (endpoint OpenAI real)."""
    return _OPENAI_COMPAT_BASE_URL.get(provider)


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


def _genai_sdk_client(api_key: str, settings: Settings):
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(retry_options=_genai_retry_options(settings)),
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
# PydanticAI (agentes das camadas 3 e avaliação)
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


# ---------------------------------------------------------------------------
# Graphiti (camada 3: indexação, comunidades, busca híbrida)
# ---------------------------------------------------------------------------

def _classe_cliente_resiliente():
    """Cliente do Graphiti que repete a chamada quando o provedor devolve lixo.

    Três assinaturas de "resposta ruim" de um provedor agregado, todas vistas
    ao indexar com OpenRouter + ``z-ai/glm-5.3-flash``:

    - ``TypeError: 'NoneType' object is not subscriptable`` — resposta sem
      ``choices`` (graphiti-core antigo fazia ``response.choices[0]`` sem
      checar);
    - ``EmptyResponseError`` — corpo vazio (graphiti-core 0.30 trata o caso e
      levanta isto);
    - ``json.JSONDecodeError`` — JSON cortado no meio (``Unterminated string
      starting at ... char 13``).

    O Graphiti já repete as duas últimas (4 tentativas, backoff de 5 a 120 s)
    e, esgotadas, reraise — foi o que derrubou o ``index_graphiti.py`` no meio
    da construção de comunidades. Esta camada fica DENTRO de cada tentativa
    dele: 3 chamadas rápidas por tentativa do Graphiti, ou seja, até 12 no
    total antes de desistir, sem multiplicar as esperas longas.

    Não se afirma aqui a causa da resposta vazia — pode ser orçamento de
    ``max_tokens`` consumido por raciocínio oculto, pode ser o
    ``finish_reason: "error"`` intermitente que este provedor já mostrou. O
    Graphiti usa ``temperature=1`` por padrão, então repetir NÃO é reexecutar
    a mesma amostra; é uma nova tirada, e é isso que se está apostando.

    A subclasse é montada dentro da função, e não no topo do módulo, porque
    ``graphiti_core`` é dependência pesada que o projeto só importa onde
    precisa.
    """
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

    try:
        from graphiti_core.llm_client.errors import EmptyResponseError
    except ImportError:  # graphiti-core antigo, sem a classe: nada a capturar

        class EmptyResponseError(Exception):  # type: ignore[no-redef]
            pass

    class ClienteResiliente(OpenAIGenericClient):
        TENTATIVAS = 3
        ESPERA_S = 3.0

        async def _generate_response(self, *args, **kwargs):
            ultimo: Exception | None = None
            for tentativa in range(1, self.TENTATIVAS + 1):
                try:
                    return await super()._generate_response(*args, **kwargs)
                except (EmptyResponseError, json.JSONDecodeError) as exc:
                    ultimo = exc
                except TypeError as exc:
                    # a assinatura exata do defeito: choices ausente/None
                    if "subscriptable" not in str(exc):
                        raise
                    ultimo = exc
                logger.warning(
                    "resposta ruim do provedor (tentativa %d/%d): %s: %s",
                    tentativa, self.TENTATIVAS, type(ultimo).__name__, ultimo,
                )
                if tentativa < self.TENTATIVAS:
                    await asyncio.sleep(self.ESPERA_S * tentativa)
            assert ultimo is not None
            raise ultimo

    return ClienteResiliente


def pydantic_ai_model_settings(settings: Settings) -> dict:
    """Settings de chamada dos agentes da camada 3 (``Agent(model_settings=...)``).

    Fica aqui, e não em ``api/agents.py``, porque o que muda de provedor para
    provedor é responsabilidade desta camada — e porque a ``extra_body`` que o
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


def graphiti_llm_client(settings: Settings) -> LLMClient:
    """Cliente de LLM do Graphiti com o cliente SDK (e seu retry) injetado."""
    config = LLMConfig(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        small_model=settings.llm_small_model or settings.llm_model,
    )
    base_url = _openai_compat_base_url(settings.llm_provider)
    if base_url is not None:
        # Endpoint compatível com OpenAI (Mistral, OpenRouter). Ver
        # docs/05-decisoes.md sobre structured_output_mode caso o json_schema
        # falhe num modelo específico — botão exposto em LLM_STRUCTURED_OUTPUT_MODE.
        config.base_url = base_url
        return _classe_cliente_resiliente()(
            config=config,
            client=_openai_compat_sdk_client(settings.llm_api_key, base_url, settings),
            structured_output_mode=settings.llm_structured_output_mode,
        )
    if settings.llm_provider == "anthropic":
        from graphiti_core.llm_client.anthropic_client import AnthropicClient

        return AnthropicClient(config=config, client=_anthropic_sdk_client(settings))
    from graphiti_core.llm_client.gemini_client import GeminiClient

    return GeminiClient(config=config, client=_genai_sdk_client(settings.llm_api_key, settings))


def graphiti_embedder(settings: Settings) -> EmbedderClient:
    """Embedder do Graphiti com retry nativo. Anthropic não tem API de
    embeddings, então o provedor de embeddings é configurado à parte
    (EMBEDDER_PROVIDER)."""
    if settings.embedder_provider == "gemini":
        from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig

        return GeminiEmbedder(
            config=GeminiEmbedderConfig(
                api_key=settings.embedder_api_key, embedding_model=settings.embedder_model
            ),
            client=_genai_sdk_client(settings.embedder_api_key, settings),
        )
    # Default: qualquer endpoint compatível com OpenAI (inclui mistral-embed).
    base_url = MISTRAL_BASE_URL if settings.embedder_provider == "mistral" else None
    return OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=settings.embedder_api_key,
            embedding_model=settings.embedder_model,
            base_url=base_url,
        ),
        client=_openai_compat_sdk_client(settings.embedder_api_key, base_url, settings),
    )


def graphiti_cross_encoder(settings: Settings) -> CrossEncoderClient:
    """Reranker da busca híbrida, também com retry nativo. Atenção (validado
    ao vivo, ADR-5): passar None faria o Graphiti instanciar o
    OpenAIRerankerClient default, que exige OPENAI_API_KEY — não existe
    fallback "sem reranker". Então:
    - provedor gemini, ou embedder gemini: GeminiRerankerClient (usa a chave
      Gemini disponível; modelo default do próprio cliente);
    - mistral/openrouter: OpenAIRerankerClient apontado para o endpoint compatível.
    """
    if settings.llm_provider == "gemini" or settings.embedder_provider == "gemini":
        from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient

        api_key = settings.llm_api_key if settings.llm_provider == "gemini" else settings.embedder_api_key
        return GeminiRerankerClient(
            config=LLMConfig(api_key=api_key), client=_genai_sdk_client(api_key, settings)
        )
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

    base_url = _openai_compat_base_url(settings.llm_provider)
    return OpenAIRerankerClient(
        config=LLMConfig(
            api_key=settings.llm_api_key,
            model=settings.llm_small_model or settings.llm_model,
            base_url=base_url,
        ),
        client=_openai_compat_sdk_client(settings.llm_api_key, base_url, settings),
    )

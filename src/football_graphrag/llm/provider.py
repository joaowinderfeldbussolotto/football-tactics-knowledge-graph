"""Ponte mínima entre config -> Graphiti e config -> PydanticAI.

Não é uma camada de abstração de provedor própria: cada função aqui só
escolhe a classe certa das libs (`graphiti_core`, `pydantic_ai`) e a
configura. Retry e concorrência são resolvidos nativamente por essas libs
(ver README, seção "Camada de LLM"); nada disso é reimplementado aqui.
"""

from __future__ import annotations

from collections.abc import Iterable

from anthropic import AsyncAnthropic
from google import genai
from graphiti_core import Graphiti
from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.anthropic_client import AnthropicClient
from graphiti_core.llm_client.client import LLMClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.gemini_client import GeminiClient
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from openai import AsyncOpenAI
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from football_graphrag.config import Settings


def build_graphiti_llm_client(settings: Settings) -> LLMClient:
    """Só escolhe a classe certa do graphiti_core e devolve configurada."""
    config = LLMConfig(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        small_model=settings.llm_small_model,
        base_url=settings.llm_base_url,
    )

    if settings.llm_provider == "anthropic":
        client = AsyncAnthropic(api_key=settings.llm_api_key, max_retries=settings.llm_max_retries)
        return AnthropicClient(config=config, client=client)

    if settings.llm_provider == "openai":
        client = AsyncOpenAI(api_key=settings.llm_api_key, max_retries=settings.llm_max_retries)
        return OpenAIClient(config=config, client=client)

    if settings.llm_provider == "gemini":
        # google-genai já traz retry embutido nas chamadas; sem parâmetro dedicado
        # de max_retries no construtor do Client, então repassamos só a config.
        return GeminiClient(config=config)

    if settings.llm_provider == "openai_compatible":
        if not settings.llm_base_url:
            raise ValueError("LLM_BASE_URL é obrigatório quando LLM_PROVIDER=openai_compatible")
        client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            max_retries=settings.llm_max_retries,
        )
        return OpenAIGenericClient(config=config, client=client)

    raise ValueError(f"LLM_PROVIDER desconhecido: {settings.llm_provider}")


class _DedupingEmbedder(EmbedderClient):
    """Garante que `create_batch` devolva exatamente um vetor por string de
    entrada, mesmo quando a lista tem strings repetidas.

    Achado rodando ingestão de verdade: `graphiti_core.utils.maintenance.
    node_operations._semantic_candidate_search` chama `embedder.create_batch(
    queries)` e depois faz `zip(extracted_nodes, query_vectors, strict=True)`,
    assumindo `len(query_vectors) == len(queries)`. Fases de posse mencionam o
    mesmo jogador mais de uma vez (ex: dribla, depois passa), então o LLM de
    extração frequentemente devolve o mesmo nome de entidade mais de uma vez
    antes da deduplicação do Graphiti — e pelo menos a API de embeddings da
    OpenAI pode devolver menos vetores do que strings enviadas quando a lista
    tem duplicatas exatas, quebrando essa suposição com
    `ValueError: zip() argument 2 is shorter than argument 1`.

    Em vez de confiar que toda API de embedding preserva 1:1 duplicatas,
    deduplicamos antes de chamar a API e reexpandimos depois — strings
    idênticas legitimamente devem ter o mesmo vetor mesmo.
    """

    def __init__(self, inner: EmbedderClient):
        self._inner = inner

    async def create(
        self, input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]]
    ) -> list[float]:
        return await self._inner.create(input_data)

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        if not input_data_list:
            return []
        unique_inputs = list(dict.fromkeys(input_data_list))
        unique_vectors = await self._inner.create_batch(unique_inputs)
        vector_by_input = dict(zip(unique_inputs, unique_vectors, strict=True))
        return [vector_by_input[s] for s in input_data_list]


def build_embedder(settings: Settings) -> EmbedderClient:
    if settings.embedder_provider == "openai":
        inner = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=settings.embedder_api_key,
                embedding_model=settings.embedder_model,
            )
        )
    elif settings.embedder_provider == "gemini":
        inner = GeminiEmbedder(
            config=GeminiEmbedderConfig(
                api_key=settings.embedder_api_key,
                embedding_model=settings.embedder_model,
            )
        )
    else:
        raise ValueError(f"EMBEDDER_PROVIDER desconhecido: {settings.embedder_provider}")

    return _DedupingEmbedder(inner)


class _PassthroughCrossEncoder(CrossEncoderClient):
    """Cross-encoder no-op: mantém a ordem de entrada, com scores decrescentes.

    O Graphiti sempre exige um `CrossEncoderClient` construído no `__init__`
    (por padrão, um `OpenAIRerankerClient()` sem argumentos — que quebra se
    `OPENAI_API_KEY` não estiver setada, mesmo rodando 100% em outro
    provedor). Essa PoC nunca depende de reranking via cross-encoder: a
    recuperação usada em `graph.client.get_match_facts` é `graphiti.search()`,
    que já usa RRF (bm25 + embeddings) sem chamar LLM — exatamente para
    cumprir o critério de retrieval <1s da seção 9. Este passthrough existe
    só para não acoplar a troca de `LLM_PROVIDER` à disponibilidade de um
    reranker de um provedor específico.
    """

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        n = max(len(passages), 1)
        return [(p, 1.0 - i / n) for i, p in enumerate(passages)]


def build_graphiti(settings: Settings) -> Graphiti:
    """Monta o Graphiti com o driver Neo4j + cliente de LLM + embedder.

    Os tipos de entidade/aresta customizados (graph/entities.py, graph/edges.py)
    não são "registrados" aqui: são passados por chamada em `add_episode()`,
    dentro de `graph/client.py::ingest_match`.
    """
    driver = Neo4jDriver(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    return Graphiti(
        graph_driver=driver,
        llm_client=build_graphiti_llm_client(settings),
        embedder=build_embedder(settings),
        cross_encoder=_PassthroughCrossEncoder(),
        max_coroutines=settings.semaphore_limit,
    )


def pydantic_ai_model_string(settings: Settings) -> str:
    """Ex: 'anthropic:claude-sonnet-5'. Útil para logs/observabilidade.

    Para instanciar o Agent com controle de `max_retries` no cliente HTTP
    subjacente (seção 5.3), use `build_pydantic_ai_model` em vez desta string.
    """
    provider_prefix = {"gemini": "google"}.get(settings.llm_provider, settings.llm_provider)
    return f"{provider_prefix}:{settings.llm_model}"


def build_pydantic_ai_model(settings: Settings) -> Model:
    """Monta o Model do PydanticAI, repassando LLM_MAX_RETRIES ao cliente HTTP
    nativo do provedor (Anthropic/OpenAI) em vez de deixar isso implícito.

    Trocar de provedor é só mudar `LLM_PROVIDER`/`LLM_MODEL` no `.env` e
    reiniciar o container `api` — nenhum outro código do projeto muda.
    """
    if settings.llm_provider == "anthropic":
        client = AsyncAnthropic(api_key=settings.llm_api_key, max_retries=settings.llm_max_retries)
        return AnthropicModel(settings.llm_model, provider=AnthropicProvider(anthropic_client=client))

    if settings.llm_provider == "openai":
        client = AsyncOpenAI(api_key=settings.llm_api_key, max_retries=settings.llm_max_retries)
        return OpenAIChatModel(settings.llm_model, provider=OpenAIProvider(openai_client=client))

    if settings.llm_provider == "gemini":
        client = genai.Client(api_key=settings.llm_api_key)
        return GoogleModel(settings.llm_model, provider=GoogleProvider(client=client))

    if settings.llm_provider == "openai_compatible":
        if not settings.llm_base_url:
            raise ValueError("LLM_BASE_URL é obrigatório quando LLM_PROVIDER=openai_compatible")
        client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            max_retries=settings.llm_max_retries,
        )
        return OpenAIChatModel(settings.llm_model, provider=OpenAIProvider(openai_client=client))

    raise ValueError(f"LLM_PROVIDER desconhecido: {settings.llm_provider}")

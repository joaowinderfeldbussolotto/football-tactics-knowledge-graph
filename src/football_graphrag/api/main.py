"""App FastAPI da PoC (seção 7 do plano).

O startup faz três coisas, nessa ordem: liga o tracing (Langfuse + OTel),
instrumenta todos os agentes PydanticAI de uma vez (`Agent.instrument_all()`,
sem decorator manual por rota), e constrói o cliente Graphiti + o semáforo
compartilhado que limita a concorrência de chamadas de LLM (seção 5.2 — o
mesmo `SEMAPHORE_LIMIT` que o Graphiti já usa internamente).

Não chamamos `build_indices_and_constraints()` explicitamente aqui: o
`Neo4jDriver` do graphiti-core já agenda essa criação sozinho, como uma task
em background, assim que é construído (dentro de `build_graphiti`). Chamar
de novo aqui só duplicava a corrida contra a mesma criação de índice — o que
o `docker compose up` real deste projeto expôs como um `EquivalentSchemaRuleAlreadyExists`
nos logs do `replay-worker` (o container `api` e o `replay-worker` constroem
cada um seu próprio driver, e cada um agenda a própria criação de índices).
O graphiti-core já trata essa corrida como benigna internamente
(`Neo4jDriver._execute_index_query` ignora esse erro específico); a única
coisa que dependia de nós era não adicionar uma terceira tentativa.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from pydantic_ai import Agent

from football_graphrag.api.routes_ask import router as ask_router
from football_graphrag.api.routes_ingest import router as ingest_router
from football_graphrag.api.routes_live import router as live_router
from football_graphrag.api.routes_report import router as report_router
from football_graphrag.api.schemas import HealthResponse
from football_graphrag.config import get_settings
from football_graphrag.graph.client import build_graphiti
from football_graphrag.observability.langfuse_setup import setup_langfuse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings

    setup_langfuse(settings)
    Agent.instrument_all()

    app.state.graphiti = build_graphiti(settings)

    app.state.llm_semaphore = asyncio.Semaphore(settings.semaphore_limit)
    app.state.replay_producer_tasks = {}

    yield

    await app.state.graphiti.close()


app = FastAPI(title="Football GraphRAG PoC", lifespan=lifespan)
app.include_router(ingest_router)
app.include_router(report_router)
app.include_router(live_router)
app.include_router(ask_router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = app.state.settings

    neo4j_ok = False
    try:
        await app.state.graphiti.driver.execute_query("RETURN 1")
        neo4j_ok = True
    except Exception:
        logger.warning("Health check: Neo4j indisponível.", exc_info=True)

    redis_ok = False
    client = redis.from_url(settings.redis_url)
    try:
        redis_ok = await client.ping()
    except Exception:
        logger.warning("Health check: Redis indisponível.", exc_info=True)
    finally:
        await client.aclose()

    status = "ok" if (neo4j_ok and redis_ok) else "degraded"
    return HealthResponse(status=status, neo4j=neo4j_ok, redis=redis_ok)

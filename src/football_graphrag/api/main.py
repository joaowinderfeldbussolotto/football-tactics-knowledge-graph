"""Aplicação FastAPI (camada 3)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from football_graphrag.api.routes import router
from football_graphrag.config import get_settings
from football_graphrag.graph import db
from football_graphrag.observability.langfuse_setup import setup_observability

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_observability(settings)
    app.state.driver = db.make_driver(settings)
    app.state.graphiti = None
    if settings.llm_api_key and settings.embedder_api_key:
        from football_graphrag.graph.communities import make_graphiti

        app.state.graphiti = make_graphiti(settings)
        logger.info("Graphiti habilitado (%s)", settings.llm_provider)
    else:
        logger.warning("sem credenciais de LLM/embedder: endpoints /report e /ask exigirão chaves; busca híbrida desligada")
    yield
    app.state.driver.close()


app = FastAPI(
    title="football-graphrag",
    description="Grafo tático de futebol com insights não triviais (PoC)",
    lifespan=lifespan,
)
app.include_router(router)

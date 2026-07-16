"""Inicialização do Langfuse (OTel nativo, seção 5 do plano).

O Langfuse Python SDK v3+ é nativamente OpenTelemetry: instanciar o cliente
registra um `TracerProvider` global, e `Agent.instrument_all()` (chamado no
startup da API, ver `api/main.py`) já basta para todo `agent.run(...)` do
PydanticAI virar spans exportados para o Langfuse — sem decorator manual em
cada rota.
"""

from __future__ import annotations

import logging

from football_graphrag.config import Settings

logger = logging.getLogger(__name__)


def setup_langfuse(settings: Settings) -> None:
    if not settings.langfuse_enabled:
        logger.info("Langfuse desabilitado (LANGFUSE_ENABLED=false); pulando tracing.")
        return

    from langfuse import Langfuse

    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    logger.info("Langfuse habilitado (host=%s).", settings.langfuse_host)

"""Observabilidade nativa: Langfuse (OTel) + instrumentação do PydanticAI.

Regra da seção 4 do plano: `Agent.instrument_all()` uma vez no startup e o
SDK v3+ do Langfuse (OTel nativo) faz o resto. Nenhum @observe() espalhado.
Sem chaves configuradas, vira no-op silencioso (dev sem Langfuse funciona).
"""

import logging

from football_graphrag.config import Settings

logger = logging.getLogger(__name__)


def setup_observability(settings: Settings) -> bool:
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.info("Langfuse não configurado; instrumentação desligada")
        return False
    import os

    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

    from langfuse import get_client
    from pydantic_ai import Agent

    get_client()  # inicializa o exporter OTel do Langfuse
    Agent.instrument_all()
    logger.info("Langfuse + PydanticAI instrumentados")
    return True

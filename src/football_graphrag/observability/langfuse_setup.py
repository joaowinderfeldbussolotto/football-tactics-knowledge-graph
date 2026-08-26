"""Observabilidade nativa: Langfuse (OTel) + instrumentação do PydanticAI.

Regra da seção 4 do plano: `Agent.instrument_all()` uma vez no startup e o
SDK v3+ do Langfuse (OTel nativo) faz o resto. Nenhum @observe() espalhado.
Sem chaves configuradas, vira no-op silencioso (dev sem Langfuse funciona).
"""

import logging
from contextlib import contextmanager

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


@contextmanager
def observacao(nome: str, *, ativo: bool, **metadata):
    """Agrupa o trabalho de um bloco num span nomeado do Langfuse.

    Sem isso, uma rodada de avaliação chega ao Langfuse como uma enxurrada de
    chamadas soltas: o agente, os dois juízes e o baseline de trinta perguntas
    viram ~250 traces sem nome, impossíveis de ler. Com o span por
    (pergunta, braço), cada trace tem o nome do que estava sendo medido e as
    gerações do PydanticAI penduradas embaixo.

    No-op silencioso quando ``ativo`` é falso — o mesmo contrato de
    ``setup_observability``: sem chaves, o código roda igual.
    """
    if not ativo:
        yield
        return
    from langfuse import get_client

    with get_client().start_as_current_observation(
        name=nome, as_type="span", metadata=metadata
    ):
        yield


def flush(ativo: bool) -> None:
    """Manda os spans que ficaram no buffer do exporter OTel.

    Necessário em script de vida curta: o exporter manda em lote e o processo
    termina antes do lote sair — sem isto, a rodada inteira não chega.
    """
    if not ativo:
        return
    from langfuse import get_client

    get_client().flush()

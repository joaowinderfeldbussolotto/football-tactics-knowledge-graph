"""Integração com o Graphiti (camada 3): indexação dos padrões e comunidades.

O Graphiti entra AQUI, não na camada 1 (ver ADR em docs/05-decisoes.md):
- ``index_match_patterns``: insere cada PadraoTatico como fato temporal via
  ``add_triplet`` (sem extração por LLM), com intervalo de validade nos
  padrões bitemporais (insight 7.7). Volume: dezenas de fatos por partida.
- ``build_pattern_communities``: usa o ``build_communities()`` nativo do
  Graphiti para resumos de comunidade (nada de map-reduce próprio).
- ``hybrid_search``: busca híbrida nativa (semântica + BM25 + travessia)
  para o Q&A, sem chamada de LLM na recuperação.

Requer credenciais de LLM/embedder no .env. O grupo de cada partida é
``match-{match_id}``, o que permite buscar por partida.
"""

import logging
from datetime import datetime, timedelta, timezone

from graphiti_core import Graphiti
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode
from neo4j import Driver

from football_graphrag.config import Settings
from football_graphrag.llm import provider

logger = logging.getLogger(__name__)

# Data de referência para converter minuto de jogo em datetime (o modelo
# bitemporal do Graphiti usa datetimes; o minuto vira offset do kickoff).
KICKOFF = datetime(2022, 12, 1, 15, 0, tzinfo=timezone.utc)


def make_graphiti(settings: Settings) -> Graphiti:
    return Graphiti(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
        llm_client=provider.graphiti_llm_client(settings),
        embedder=provider.graphiti_embedder(settings),
        cross_encoder=provider.graphiti_cross_encoder(settings),
    )


def _fetch_patterns(driver: Driver, match_id: int) -> list[dict]:
    with driver.session() as session:
        return session.run(
            "MATCH (p:PadraoTatico {match_id: $m}) RETURN p ORDER BY p.tipo",
            m=match_id,
        ).value()


async def index_match_patterns(
    graphiti: Graphiti, driver: Driver, match_id: int, pace_seconds: float | None = None
) -> int:
    """Indexa os PadraoTatico de uma partida como fatos temporais no Graphiti.

    Um triplet por padrão: (Time) -[EXIBE_PADRAO {fact: descricao}]-> (Padrao).
    Padrões bitemporais (mudanca_estado) carregam valid_at/invalid_at
    derivados dos minutos de validade — o fato antigo fica invalidado, não
    apagado, que é exatamente o modelo do Graphiti.

    Nota operacional (validado ao vivo, ADR-5/ADR-7): o grupo é limpo antes
    de reindexar — ``add_triplet`` gera uuids novos por execução e a resolução
    de duplicatas não é garantida entre execuções. ``pace_seconds`` (default:
    GRAPHITI_PACE_SECONDS do .env) espaça os triplets (~3-4 chamadas de
    embedding cada) para caber em cotas free-tier (Gemini: 100
    embed-requests/min); estouros residuais são absorvidos pelo retry nativo
    dos SDKs (LLM_MAX_RETRIES, ver llm/provider.py).
    """
    import asyncio

    from football_graphrag.config import get_settings

    if pace_seconds is None:
        pace_seconds = get_settings().graphiti_pace_seconds
    group_id = f"match-{match_id}"
    with driver.session() as session:
        session.run(
            "MATCH (n:Entity {group_id: $g}) DETACH DELETE n", g=group_id
        ).consume()
        session.run(
            "MATCH (n:Community {group_id: $g}) DETACH DELETE n", g=group_id
        ).consume()
    patterns = _fetch_patterns(driver, match_id)
    for p in patterns:
        team_node = EntityNode(name=p["time"], group_id=group_id, labels=["Entity"], summary=f"Seleção {p['time']}")
        pattern_name = f"{p['tipo']}:{p['uid'][:8]}"
        pattern_node = EntityNode(
            name=pattern_name,
            group_id=group_id,
            labels=["Entity"],
            summary=p["descricao_curta"],
        )
        valid_at = KICKOFF + timedelta(minutes=p["valid_at"]) if p.get("valid_at") is not None else None
        invalid_at = KICKOFF + timedelta(minutes=p["invalid_at"]) if p.get("invalid_at") is not None else None
        edge = EntityEdge(
            source_node_uuid=team_node.uuid,
            target_node_uuid=pattern_node.uuid,
            name="EXIBE_PADRAO",
            fact=p["descricao_curta"],
            group_id=group_id,
            created_at=datetime.now(timezone.utc),
            valid_at=valid_at,
            invalid_at=invalid_at,
        )
        await graphiti.add_triplet(team_node, edge, pattern_node)
        if pace_seconds:
            await asyncio.sleep(pace_seconds)
    logger.info("indexados %d padrões da partida %s no Graphiti", len(patterns), match_id)
    return len(patterns)


async def build_pattern_communities(graphiti: Graphiti, match_id: int):
    """Resumos de comunidade nativos do Graphiti sobre os fatos indexados."""
    return await graphiti.build_communities(group_ids=[f"match-{match_id}"])


async def hybrid_search(graphiti: Graphiti, match_id: int, query: str, limit: int = 10) -> list[str]:
    """Busca híbrida nativa (semântica + BM25 + grafo), sem LLM na recuperação.

    Retorna os fatos (strings) mais relevantes para a pergunta.
    """
    results = await graphiti.search(query, group_ids=[f"match-{match_id}"], num_results=limit)
    return [edge.fact for edge in results]

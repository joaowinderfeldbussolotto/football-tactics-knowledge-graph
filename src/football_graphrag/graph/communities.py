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


def _limpar_grupo(driver: Driver, group_id: str) -> None:
    """Apaga o índice do Graphiti de uma partida (Entity e Community)."""
    with driver.session() as session:
        session.run("MATCH (n:Entity {group_id: $g}) DETACH DELETE n", g=group_id).consume()
        session.run("MATCH (n:Community {group_id: $g}) DETACH DELETE n", g=group_id).consume()


def _nomes_ja_indexados(driver: Driver, group_id: str) -> set[str]:
    """Nomes dos nós Entity já gravados no grupo (padrões e times)."""
    with driver.session() as session:
        return set(
            session.run("MATCH (n:Entity {group_id: $g}) RETURN n.name AS nome", g=group_id).value()
        )


async def index_match_patterns(
    graphiti: Graphiti,
    driver: Driver,
    match_id: int,
    pace_seconds: float | None = None,
    limpar: bool = False,
) -> int:
    """Indexa os PadraoTatico de uma partida como fatos temporais no Graphiti.

    Um triplet por padrão: (Time) -[EXIBE_PADRAO {fact: descricao}]-> (Padrao).
    Padrões bitemporais (mudanca_estado) carregam valid_at/invalid_at
    derivados dos minutos de validade — o fato antigo fica invalidado, não
    apagado, que é exatamente o modelo do Graphiti.

    Retomável por padrão (``limpar=False``): padrões cujo nó já existe no grupo
    são pulados, então rodar de novo depois de uma queda só paga o que faltou.
    Antes, cada execução apagava o grupo inteiro — e uma queda no meio custava
    refazer (e repagar) tudo, inclusive o que tinha dado certo. O nome do nó
    do padrão (``tipo:uid[:8]``) é a chave de retomada; um triplet que falhou
    não deixa nó, então é tentado de novo.

    ``limpar=True`` restaura o comportamento antigo (apaga e reindexa tudo).
    Use quando os PadraoTatico mudaram — a análise foi refeita e os
    resumos já indexados estão velhos. Era o motivo de o grupo ser sempre
    limpo (ADR-5/ADR-7): ``add_triplet`` gera uuids novos por execução e a
    resolução de duplicatas não é garantida entre execuções, então reindexar
    por cima do que existe duplicaria fatos.

    ``pace_seconds`` (default: GRAPHITI_PACE_SECONDS do .env) espaça os
    triplets (~3-4 chamadas de embedding cada) para caber em cotas free-tier
    (Gemini: 100 embed-requests/min); estouros residuais são absorvidos pelo
    retry nativo dos SDKs (LLM_MAX_RETRIES, ver llm/provider.py).

    Retorna quantos padrões foram indexados NESTA execução (não conta os
    pulados).
    """
    import asyncio

    from football_graphrag.config import get_settings

    if pace_seconds is None:
        pace_seconds = get_settings().graphiti_pace_seconds
    group_id = f"match-{match_id}"
    if limpar:
        _limpar_grupo(driver, group_id)
        ja_indexados: set[str] = set()
    else:
        ja_indexados = _nomes_ja_indexados(driver, group_id)
    patterns = _fetch_patterns(driver, match_id)
    indexados = 0
    pulados = 0
    falhas: list[str] = []
    for p in patterns:
        pattern_name = f"{p['tipo']}:{p['uid'][:8]}"
        if pattern_name in ja_indexados:
            pulados += 1
            continue
        team_node = EntityNode(name=p["time"], group_id=group_id, labels=["Entity"], summary=f"Seleção {p['time']}")
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
        try:
            await graphiti.add_triplet(team_node, edge, pattern_node)
        except Exception:
            # Um triplet que falha não pode derrubar a indexação inteira: são
            # dezenas por partida, cada uma custa dinheiro, e perder as 20 já
            # feitas por causa da 21ª é caro. Falha real observada: o cliente
            # genérico do Graphiti faz response.choices[0] sem checar, e um
            # provedor que devolva choices vazio levanta TypeError ali dentro.
            logger.exception("padrão %s falhou ao indexar; seguindo", pattern_name)
            falhas.append(pattern_name)
            continue
        indexados += 1
        if pace_seconds:
            await asyncio.sleep(pace_seconds)
    if falhas:
        logger.warning("%d padrões não indexados na partida %s: %s", len(falhas), match_id, falhas)
    logger.info(
        "partida %s: %d indexados agora, %d já existiam (pulados), %d falharam, de %d padrões",
        match_id, indexados, pulados, len(falhas), len(patterns),
    )
    return indexados


async def build_pattern_communities(
    graphiti: Graphiti,
    match_id: int,
    driver: Driver | None = None,
    tentativas: int = 3,
    espera_s: float = 60.0,
):
    """Resumos de comunidade nativos do Graphiti sobre os fatos indexados.

    O ``build_communities`` do Graphiti é tudo-ou-nada: resume os clusters em
    paralelo e só grava no fim. Uma única chamada de LLM que falhe depois de
    esgotar o retry interno dele (4 tentativas) derruba o cluster inteiro e
    perde todas as chamadas já pagas daquela partida — foi o que interrompeu
    ``index_graphiti.py`` com ``EmptyResponseError``.

    Aqui a etapa inteira é repetida ``tentativas`` vezes, com espera crescente
    entre elas (a cota por minuto de embeddings e as falhas intermitentes do
    provedor passam com o tempo). Se ``driver`` for dado, as comunidades de uma
    tentativa anterior são apagadas antes de cada nova, para não duplicar.
    Esgotadas as tentativas, a ÚLTIMA exceção sobe — quem chama decide se a
    ausência de comunidades é fatal (para o Q&A não é: a busca híbrida
    funciona sobre os fatos, e as comunidades só acrescentam resumos).
    """
    import asyncio

    group_id = f"match-{match_id}"
    ultimo: Exception | None = None
    for tentativa in range(1, tentativas + 1):
        if driver is not None:
            with driver.session() as session:
                session.run(
                    "MATCH (n:Community {group_id: $g}) DETACH DELETE n", g=group_id
                ).consume()
        try:
            return await graphiti.build_communities(group_ids=[group_id])
        except Exception as exc:
            ultimo = exc
            logger.warning(
                "comunidades da partida %s falharam (tentativa %d/%d): %s: %s",
                match_id, tentativa, tentativas, type(exc).__name__, exc,
            )
            if tentativa < tentativas:
                await asyncio.sleep(espera_s * tentativa)
    assert ultimo is not None
    raise ultimo


async def hybrid_search(graphiti: Graphiti, match_id: int, query: str, limit: int = 10) -> list[str]:
    """Busca híbrida nativa (semântica + BM25 + grafo), sem LLM na recuperação.

    Retorna os fatos (strings) mais relevantes para a pergunta.
    """
    results = await graphiti.search(query, group_ids=[f"match-{match_id}"], num_results=limit)
    return [edge.fact for edge in results]

"""Projeções do GDS usadas pela camada 2.

Cada análise projeta um subgrafo específico em memória via a função de
agregação Cypher ``gds.graph.project`` e o descarta ao final. As projeções
estão documentadas uma a uma em docs/02-modelo-grafo.md (qual subgrafo,
qual peso, para qual insight).
"""

import logging
from contextlib import contextmanager

from neo4j import Driver

logger = logging.getLogger(__name__)


def drop_if_exists(driver: Driver, name: str) -> None:
    with driver.session() as session:
        session.run("CALL gds.graph.drop($name, false)", name=name).consume()


@contextmanager
def pass_network(driver: Driver, match_id: int, team: str, name: str = "passnet", undirected: bool = False):
    """Projeção: rede de passes agregada de um time numa partida.

    Nós: jogadores do time. Arestas: pares (a,b) com >=1 PASSOU_PARA,
    agregadas com peso ``n_passes`` (contagem), ``xt_total`` (soma de
    xt_gerado) e ``cost`` = 1/(1+xt_total) — custo usado por algoritmos de
    caminho (betweenness), em que conexões de maior ameaça = caminhos curtos.
    """
    drop_if_exists(driver, name)
    orientation = {"undirectedRelationshipTypes": ["*"]} if undirected else {}
    query = """
    MATCH (a:Jogador)-[p:PASSOU_PARA {match_id: $match_id}]->(b:Jogador)
    WHERE a.time = $team AND b.time = $team
    WITH a, b, count(*) AS n_passes, sum(p.xt_gerado) AS xt_total
    WITH gds.graph.project(
        $name, a, b,
        {relationshipProperties: {n_passes: n_passes, xt_total: xt_total, cost: 1.0 / (1.0 + xt_total)}},
        $orientation
    ) AS g
    RETURN g.graphName AS name, g.nodeCount AS nodes, g.relationshipCount AS rels
    """
    with driver.session() as session:
        info = session.run(query, match_id=match_id, team=team, name=name, orientation=orientation).single()
        logger.info("projeção %s: %s nós, %s arestas", name, info["nodes"], info["rels"])
    try:
        yield name
    finally:
        drop_if_exists(driver, name)


@contextmanager
def pressure_network(driver: Driver, match_id: int, pressing_team: str, name: str = "pressnet"):
    """Projeção: rede de pressão de um time (arestas PRESSIONOU individuais).

    Nós: pressionadores do time + alvos adversários. Peso: contagem por par.
    Usada pelo insight 7.8 (grau de entrada = quem é o alvo).
    """
    drop_if_exists(driver, name)
    query = """
    MATCH (a:Jogador)-[p:PRESSIONOU {match_id: $match_id}]->(b:Jogador)
    WHERE a.time = $team
    WITH a, b, count(*) AS n_pressoes
    WITH gds.graph.project($name, a, b, {relationshipProperties: {n_pressoes: n_pressoes}}) AS g
    RETURN g.graphName AS name
    """
    with driver.session() as session:
        session.run(query, match_id=match_id, team=pressing_team, name=name).consume()
    try:
        yield name
    finally:
        drop_if_exists(driver, name)

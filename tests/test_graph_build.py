"""Testes da camada 1: construção do grafo factual (requer Neo4j + parquet)."""

from tests.conftest import requires_data, requires_neo4j

from football_graphrag.config import get_settings
from football_graphrag.graph import db
from football_graphrag.graph.build import build_factual_graph, graph_stats
from football_graphrag.graph.entities import uid_for

MATCH_ID = 3869685


def test_uid_deterministic():
    assert uid_for("jogador", 123) == uid_for("jogador", 123)
    assert uid_for("jogador", 123) != uid_for("jogador", 124)
    assert uid_for("jogador", 123) != uid_for("time", 123)


@requires_neo4j
@requires_data
def test_build_is_idempotent():
    settings = get_settings()
    driver = db.make_driver(settings)
    try:
        build_factual_graph(MATCH_ID, settings.data_dir, driver)
        first = graph_stats(driver, MATCH_ID)
        build_factual_graph(MATCH_ID, settings.data_dir, driver)
        second = graph_stats(driver, MATCH_ID)
        assert first == second, "reconstruir a mesma partida não pode duplicar nós/arestas"
    finally:
        driver.close()


@requires_neo4j
@requires_data
def test_pass_edges_match_parquet():
    import pandas as pd

    settings = get_settings()
    parquet = pd.read_parquet(settings.processed_dir / f"{MATCH_ID}.parquet")
    from football_graphrag.graph.build import PASS_TYPES

    expected = int((parquet["receiver_player_id"].notna() & parquet["type_name"].isin(PASS_TYPES)).sum())
    driver = db.make_driver(settings)
    try:
        stats = graph_stats(driver, MATCH_ID)
        assert stats["edges"]["PASSOU_PARA"] == expected
    finally:
        driver.close()


@requires_neo4j
@requires_data
def test_goal_and_assist_edges():
    """A final teve 6 gols no jogo corrido (períodos 1-4) e 2 assistências."""
    settings = get_settings()
    driver = db.make_driver(settings)
    try:
        with driver.session() as session:
            gols = session.run(
                "MATCH ()-[f:FINALIZOU {match_id: $m}]->() WHERE f.gol RETURN count(f) AS n",
                m=MATCH_ID,
            ).single()["n"]
            assists = session.run(
                "MATCH ()-[a:DEU_ASSISTENCIA {match_id: $m}]->() RETURN count(a) AS n",
                m=MATCH_ID,
            ).single()["n"]
        assert gols == 6
        assert assists == 2
    finally:
        driver.close()


@requires_neo4j
@requires_data
def test_realizou_covers_all_actions():
    """REALIZOU é o log completo: uma aresta por ação SPADL com jogador."""
    import pandas as pd

    settings = get_settings()
    parquet = pd.read_parquet(settings.processed_dir / f"{MATCH_ID}.parquet")
    expected = int(parquet["player_id"].notna().sum())
    driver = db.make_driver(settings)
    try:
        with driver.session() as session:
            n = session.run(
                "MATCH ()-[x:REALIZOU {match_id: $m}]->() RETURN count(x) AS n", m=MATCH_ID
            ).single()["n"]
            amarelos = session.run(
                """MATCH ()-[x:REALIZOU {match_id: $m, tipo: 'foul', resultado: 'yellow_card'}]->()
                   RETURN count(x) AS n""",
                m=MATCH_ID,
            ).single()["n"]
        assert n == expected
        assert amarelos == 6  # cartões amarelos da final no jogo corrido
    finally:
        driver.close()


def test_readonly_guard_rejects_writes_and_calls():
    import pytest

    for bad in (
        "CREATE (n:Hack) RETURN n",
        "MATCH (n) DETACH DELETE n",
        "MATCH (n) SET n.x = 1 RETURN n",
        "CALL dbms.components()",
        "CALL { MATCH (n) RETURN n } RETURN 1",
    ):
        with pytest.raises(db.UnsafeCypherError):
            db.assert_readonly_cypher(bad)
    # leitura legítima passa
    db.assert_readonly_cypher("MATCH (j:Jogador)-[p:PASSOU_PARA {match_id: 1}]->(k) RETURN j.nome, count(p)")


@requires_neo4j
def test_run_readonly_blocks_write_at_server():
    """Defesa em profundidade: mesmo se a guarda sintática falhasse, a
    transação READ do servidor rejeita escrita."""
    import pytest

    settings = get_settings()
    driver = db.make_driver(settings)
    try:
        with pytest.raises(db.UnsafeCypherError):
            db.run_readonly(driver, "CREATE (n:Hack) RETURN n")
        rows = db.run_readonly(driver, "MATCH (t:Time) RETURN t.nome LIMIT 2")
        assert len(rows) <= 2
    finally:
        driver.close()

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

"""Driver Neo4j compartilhado e helpers de escrita em lote."""

import logging
from contextlib import contextmanager

from neo4j import Driver, GraphDatabase

from football_graphrag.config import Settings

logger = logging.getLogger(__name__)

CONSTRAINTS = [
    "CREATE CONSTRAINT jogador_uid IF NOT EXISTS FOR (n:Jogador) REQUIRE n.uid IS UNIQUE",
    "CREATE CONSTRAINT time_uid IF NOT EXISTS FOR (n:Time) REQUIRE n.uid IS UNIQUE",
    "CREATE CONSTRAINT zona_uid IF NOT EXISTS FOR (n:Zona) REQUIRE n.uid IS UNIQUE",
    "CREATE CONSTRAINT fase_uid IF NOT EXISTS FOR (n:FaseDePosse) REQUIRE n.uid IS UNIQUE",
    "CREATE CONSTRAINT partida_uid IF NOT EXISTS FOR (n:Partida) REQUIRE n.uid IS UNIQUE",
    "CREATE CONSTRAINT padrao_uid IF NOT EXISTS FOR (n:PadraoTatico) REQUIRE n.uid IS UNIQUE",
]


def make_driver(settings: Settings) -> Driver:
    return GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))


def ensure_constraints(driver: Driver) -> None:
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            session.run(stmt)


def run_batched(driver: Driver, query: str, rows: list[dict], batch_size: int = 1000) -> int:
    """Executa uma query UNWIND $rows em lotes. Retorna total de linhas enviadas."""
    total = 0
    with driver.session() as session:
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            session.run(query, rows=batch).consume()
            total += len(batch)
    return total


@contextmanager
def session_scope(driver: Driver):
    with driver.session() as session:
        yield session

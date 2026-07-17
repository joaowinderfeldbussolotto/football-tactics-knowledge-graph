"""Driver Neo4j compartilhado e helpers de escrita em lote / leitura segura."""

import logging
import re
from contextlib import contextmanager

import neo4j
from neo4j import Driver, GraphDatabase

from football_graphrag.config import Settings

logger = logging.getLogger(__name__)

# Guarda sintática do executor read-only (defesa em profundidade: a garantia
# real é a transação READ do Neo4j, que rejeita escrita no servidor).
_WRITE_PATTERN = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|FOREACH|LOAD\s+CSV)\b|CALL\s*[a-zA-Z{]",
    re.IGNORECASE,
)


class UnsafeCypherError(ValueError):
    """Consulta recusada pela guarda read-only."""


def assert_readonly_cypher(cypher: str) -> None:
    """Rejeita cláusulas de escrita e chamadas de procedure (CALL).

    ``CALL`` é bloqueado por inteiro — inclusive subqueries ``CALL {}`` — para
    impedir procedures administrativas/pesadas (dbms.*, apoc.*, gds.*); o
    agente não precisa delas: o schema do grafo vai no prompt.
    """
    match = _WRITE_PATTERN.search(cypher)
    if match:
        raise UnsafeCypherError(
            f"consulta recusada: '{match.group(0)}' não é permitido no modo leitura"
        )


def run_readonly(driver: Driver, cypher: str, max_rows: int = 50, timeout: float = 15.0) -> list[dict]:
    """Executa Cypher em transação READ (o servidor rejeita escrita), com
    guarda sintática, limite de linhas e timeout. É a única porta de entrada
    do Cypher gerado pelo LLM (ADR-8)."""
    assert_readonly_cypher(cypher)

    @neo4j.unit_of_work(timeout=timeout)
    def _read(tx):
        return [dict(record) for record in tx.run(cypher)][: max_rows + 1]

    with driver.session(default_access_mode=neo4j.READ_ACCESS) as session:
        rows = session.execute_read(_read)
    if len(rows) > max_rows:
        rows = rows[:max_rows]
        rows.append({"_aviso": f"resultado truncado em {max_rows} linhas; use LIMIT/agregação"})
    return rows

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

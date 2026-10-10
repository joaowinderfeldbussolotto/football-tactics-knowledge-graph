"""The sixth arm, ``text_to_cypher``: the model writes Cypher, one tool runs it on Neo4j.

The usual text-to-Cypher pattern: the model gets the graph schema (read from the
database, never written by hand) and a single tool that runs a read-only query and
returns the rows. There are no task tools: every count, network or sequence is the
model's own query.

Guards, in order:
1. ``check_query`` refuses what is not a read query: write clauses, procedure calls
   (``CALL db.x``, ``CALL gds.x``: no graph algorithms, see below) and the hidden labels.
   ``CALL { ... }`` subqueries are allowed.
2. The query runs in a READ session: Neo4j itself refuses any write that got through.
3. A timeout per query and a cap on the rows returned (the model is told about both and
   should aggregate, order and LIMIT instead of reading raw rows).

Two choices that make the arm comparable to the others:
- **No graph algorithms.** GDS procedures are refused. ``graph_tools`` reaches
  betweenness, articulation points and communities through its tools; here the model
  has plain Cypher. Whether it can still answer the network questions is part of what
  the arm measures. Projections also cost heap (``tools.py``), which a free query
  could exhaust.
- **No precomputed answers.** Layer 2 stores its findings as ``PadraoTatico`` nodes
  ("X is the structural bottleneck of team Y: betweenness 34"): reading them would be
  reading answers, not querying data. ``HIDDEN_LABELS`` leaves them out of the schema
  and the guard refuses queries that name them.

The graph holds three matches; the schema says which ``match_id`` the questions are
about (an id, not the match), and the model must filter on it.
"""

import re

import neo4j
from neo4j import Driver, Query
from neo4j.exceptions import ClientError, CypherSyntaxError, Neo4jError
from neo4j.graph import Node, Path, Relationship

from football_graphrag.benchmark.questions import MATCH_ID
from football_graphrag.benchmark.tools import ToolError

MAX_ROWS = 50
TIMEOUT_S = 15.0
MAX_ENUM = 25  # string properties with at most this many values are listed in full
HIDDEN_LABELS = ("PadraoTatico",)
HIDDEN_RELATIONSHIPS = ("OBSERVADO_EM",)  # (:PadraoTatico)-[:OBSERVADO_EM]->(:Partida)
# Internal keys and provenance, as in graph/schema.py (tipo_spadl would bring back the raw
# SPADL vocabulary the layer 0 labels replace).
HIDDEN_PROPERTIES = ("uid", "tipo_spadl", "pressure_idx")

_WRITE = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|FOREACH|LOAD\s+CSV|USE)\b", re.I)
_PROCEDURE = re.compile(r"\bCALL\s+(?![({])", re.I)  # CALL { ... } and CALL (x) { ... } are subqueries
_STRINGS = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|//[^\n]*|/\*.*?\*/", re.S)

# What each label and relationship is for: the only hand-written part of the schema.
# Properties, types, counts and value lists are read from the database.
NODES = {
    "Jogador": "a player (nome is the full name, e.g. 'Lionel Andrés Messi Cuccittini')",
    "Time": "a national team",
    "Partida": "a match",
    "EstatisticaJogador": "one per player per match: the player's match totals",
    "EstatisticaTime": "one per team per match: the team's match totals",
    "FaseDePosse": "a possession phase: consecutive actions of one team, until the other team has the ball",
    "Zona": "a cell of the 12x8 pitch grid (id_zona = column*8 + row; column 0-11 from the acting team's own goal)",
}
RELATIONSHIPS = {
    "REALIZOU": ("Jogador", "Partida", "one per on-ball action of the player (the action log)"),
    "PASSOU_PARA": ("Jogador", "Jogador", "one per completed pass between teammates, passer -> receiver"),
    "FINALIZOU": ("Jogador", "Partida", "one per shot"),
    "DEU_ASSISTENCIA": ("Jogador", "Jogador", "one per assisted goal, assister -> scorer"),
    "PRESSIONOU": ("Jogador", "Jogador", "one per pressure on an opponent"),
    "PARTICIPOU_DE": ("Jogador", "FaseDePosse", "the player touched the ball in the possession phase"),
    "ATUOU_EM": ("Jogador", "Zona", "how much the player acted in each zone"),
    "PROGREDIU_PARA": ("Zona", "Zona", "ball flow between zones, per team"),
    "MEMBRO_DE": ("Jogador", "Time", "squad"),
    "TEM_ESTATISTICA": ("Jogador|Time", "EstatisticaJogador|EstatisticaTime", "links a player or team to its totals"),
}
# Meanings that the names alone do not give ("Owner.property" wins over "property").
PROPERTIES = {
    "Zona.corredor": "corridor of the cell (esquerda/centro/direita), from the acting team's view",
    "Zona.faixa": "third of the pitch of the cell (defesa/meio/ataque), from the acting team's view",
    "PRESSIONOU.zona": "grid cell where the pressure happened (see Zona)",
    "FaseDePosse.minuto_inicio": "minutes since the start of the phase's period (the phase has no period: "
                                 "use the periodo of its actions)",
    "FaseDePosse.minuto_fim": "minutes since the start of the phase's period, at its last action",
    "FaseDePosse.team_id": "the team in possession (= Time.team_id)",
    "FaseDePosse.n_acoes": "number of actions in the phase",
    "no_gol": "the shot was on target",
    "periodo": "1 and 2 are the halves, 3 and 4 extra time (the shootout is not in the data)",
    "periodo_nome": "the period, spelled out",
    "minuto": "broadcast minute (1-120+), with stoppage time",
    "segundo": "seconds since kick-off, continuous across the periods (orders actions in time)",
    "action_id": "position of the action in the match (orders actions; a pass and its PASSOU_PARA share it)",
    "fase_posse_id": "the possession phase of the action (= FaseDePosse.fase_id)",
    "terco": "third of the pitch where the action started, from the acting team's view",
    "corredor": "corridor where the action started (esquerda/centro/direita), from the acting team's view",
    "zona": "grid cell where the action started (see Zona)",
    "zona_origem": "grid cell where the pass started",
    "zona_destino": "grid cell where the pass ended",
    "sucesso": "the action succeeded (for a pass: it reached a teammate)",
    "gol": "the action is a goal",
    "xt_gerado": "expected threat added by the action",
    "vaep": "VAEP value of the action",
    "progressivo": "the pass or carry moved the ball clearly towards the opponent's goal",
    "desfecho": "outcome of a shot",
    "numero_de_toques": "the player's touches in the possession phase",
}


class CypherRejected(ToolError):
    """A query the arm does not run (a write, a procedure call, a hidden label)."""


def check_query(query: str) -> None:
    code = _STRINGS.sub("''", query)  # keywords inside strings and comments do not count
    if not code.strip():
        raise CypherRejected("empty query")
    if m := _WRITE.search(code):
        raise CypherRejected(f"read-only: {m.group(1).upper()} is not allowed; write a MATCH ... RETURN query")
    if _PROCEDURE.search(code):
        raise CypherRejected("procedure calls (CALL db.*, CALL gds.*, apoc.*) are not available; "
                             "use plain Cypher (CALL { ... } subqueries are fine)")
    if re.search(r"\bapoc\.", code, re.I):
        raise CypherRejected("APOC is not available; use plain Cypher")
    for hidden in (*HIDDEN_LABELS, *HIDDEN_RELATIONSHIPS):
        if re.search(rf"\b{hidden}\b", code):
            raise CypherRejected(f"{hidden} is not part of this graph")


def _plain(value):
    """Neo4j values as JSON-friendly data: nodes and relationships as their properties."""
    if isinstance(value, Node):
        return {"_labels": sorted(value.labels),
                **{k: _plain(v) for k, v in value.items() if k not in HIDDEN_PROPERTIES}}
    if isinstance(value, Relationship):
        return {"_type": value.type, **{k: _plain(v) for k, v in value.items() if k not in HIDDEN_PROPERTIES}}
    if isinstance(value, Path):
        return [_plain(n) for n in value.nodes]
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def run_query(driver: Driver, query: str) -> dict:
    """Run one read-only query. A query error comes back as ``{"error": ...}`` so the model
    can fix it; a refused query raises ``CypherRejected`` (also turned into a message)."""
    check_query(query)
    try:
        with driver.session(default_access_mode=neo4j.READ_ACCESS) as session:
            result = session.run(Query(query, timeout=TIMEOUT_S))
            records = result.fetch(MAX_ROWS + 1)
            columns = list(result.keys())
            result.consume()
    except CypherSyntaxError as exc:
        return {"error": f"syntax error: {_message(exc)}"}
    except ClientError as exc:
        if "Timeout" in (exc.code or "") or "terminated" in _message(exc).lower():
            return {"error": f"the query took more than {TIMEOUT_S:g} s; aggregate or filter more"}
        return {"error": _message(exc)}
    except Neo4jError as exc:
        return {"error": _message(exc)}
    rows = [{k: _plain(r[k]) for k in columns} for r in records[:MAX_ROWS]]
    return {"columns": columns, "rows": rows, "rows_returned": len(rows), "truncated": len(records) > MAX_ROWS}


def _message(exc: Neo4jError) -> str:
    return " ".join((exc.message or str(exc)).split())[:600]


# --------------------------------------------------------------------------- schema

def _props(session, owner: str, pattern: str, var: str, filtered: bool) -> list[str]:
    """Properties of a label or relationship type, with type and values, from the data."""
    where = f"WHERE {var}.match_id = {MATCH_ID}" if filtered else ""
    keys = session.run(f"MATCH {pattern} {where} UNWIND keys({var}) AS k RETURN DISTINCT k ORDER BY k").value()
    out = []
    for k in (k for k in keys if k not in HIDDEN_PROPERTIES):
        row = session.run(
            f"MATCH {pattern} {where} WITH {var}.`{k}` AS v WHERE v IS NOT NULL "
            "RETURN count(DISTINCT v) AS n, collect(DISTINCT v)[..$cap] AS values, "
            "min(v) AS lo, max(v) AS hi", cap=MAX_ENUM + 1).single()
        sample = row["values"][0] if row["values"] else None
        kind = type(sample).__name__.replace("str", "string").replace("bool", "boolean")
        if isinstance(sample, list):
            kind = "list"
        if isinstance(sample, str) and row["n"] <= MAX_ENUM:
            detail = "values: " + ", ".join(sorted(row["values"]))
        elif isinstance(sample, bool) or isinstance(sample, list):
            detail = ""
        elif isinstance(sample, (int, float)):
            detail = f"{_plain(row['lo'])} to {_plain(row['hi'])}"
        else:
            detail = f"e.g. {sample!r}"
        meaning = PROPERTIES.get(f"{owner}.{k}", PROPERTIES.get(k, ""))
        out.append(f"{k} ({kind}{'; ' + detail if detail else ''}){': ' + meaning if meaning else ''}")
    return out


def describe(driver: Driver) -> str:
    """The schema text the model reads, for the match of the questions."""
    lines = [
        "Neo4j graph of football matches built from StatsBomb event data. It holds more than one "
        f"match: the questions are about the match with match_id = {MATCH_ID}. Relationships, "
        "statistics and possession phases carry match_id: filter on it in every query.",
        "Names, labels and values are in Portuguese, as below. Player names are full names: match "
        "them with CONTAINS (e.g. j.nome CONTAINS 'Messi').",
        "",
        "NODES (label: what it is; count in this match or overall; properties)",
    ]
    with driver.session(default_access_mode=neo4j.READ_ACCESS) as session:
        for label, purpose in NODES.items():
            has_match = session.run(f"MATCH (n:{label}) WHERE n.match_id IS NOT NULL RETURN count(n) > 0").single()[0]
            where = f"WHERE n.match_id = {MATCH_ID}" if has_match else ""
            count = session.run(f"MATCH (n:{label}) {where} RETURN count(n)").single()[0]
            lines.append(f"(:{label}) {purpose}. {count} {'in this match' if has_match else 'overall'}.")
            lines += [f"    {p}" for p in _props(session, label, f"(n:{label})", "n", has_match)]
        lines += ["", "RELATIONSHIPS (pattern: what it is; count in this match; properties)"]
        for rel, (src, dst, purpose) in RELATIONSHIPS.items():
            has_match = session.run(f"MATCH ()-[r:{rel}]->() WHERE r.match_id IS NOT NULL "
                                    "RETURN count(r) > 0").single()[0]
            where = f"WHERE r.match_id = {MATCH_ID}" if has_match else ""
            count = session.run(f"MATCH ()-[r:{rel}]->() {where} RETURN count(r)").single()[0]
            lines.append(f"(:{src})-[:{rel}]->(:{dst}) {purpose}. {count} {'in this match' if has_match else 'overall'}.")
            lines += [f"    {p}" for p in _props(session, rel, f"()-[r:{rel}]->()", "r", has_match)]
    lines += [
        "",
        f"The tool runs one read-only Cypher query and returns at most {MAX_ROWS} rows "
        f"(truncated: true when there were more); a query has {TIMEOUT_S:g} s. Aggregate, ORDER BY "
        "and LIMIT in the query instead of reading raw rows. Procedures (CALL db.*, gds.*, apoc.*) "
        "are not available: graph measures have to be written in plain Cypher.",
    ]
    return "\n".join(lines)


_SCHEMA: str | None = None


def cached_schema(driver: Driver) -> str:
    """``describe`` once per process (the graph does not change during a run)."""
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = describe(driver)
    return _SCHEMA

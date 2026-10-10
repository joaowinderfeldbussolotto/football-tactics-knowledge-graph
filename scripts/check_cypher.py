#!/usr/bin/env python
"""What plain Cypher can answer: hand-written queries for the active questions, run through
the text_to_cypher tool (same guard, read session, timeout and row cap), against the
ground truth. No LLM, no cost.

The counterpart of ``check_ground_truth.py`` for the sixth arm: there, one recipe of
graph_tools calls per question shows the tools are enough; here, one Cypher query per
question shows what the graph answers with no graph algorithm library. Even the "main
link" questions (betweenness) fit in one query: every shortest path between two
teammates, and the share of them each player sits on. Whether the model writes such
queries is what the arm measures.

Some queries take a shortcut that holds in this match and is said next to them (for
"a player without whom a teammate would be cut off", the teammate whose only partner is
that player).

Usage:
    python scripts/check_cypher.py              # active questions
    python scripts/check_cypher.py --question n04
"""

import argparse
import logging
import sys

from football_graphrag.benchmark import cypher, ground_truth
from football_graphrag.benchmark.questions import MATCH_ID, QUESTIONS, get_question
from football_graphrag.benchmark.tools import PASS_ACTIONS
from football_graphrag.config import get_settings
from football_graphrag.graph import db
from football_graphrag.observability import logging_setup

M = MATCH_ID
PASSES = "[" + ", ".join(f"'{a}'" for a in PASS_ACTIONS) + "]"
SHOTS = "['finalizacao', 'penalti', 'falta_direta']"
ARG, FRA = "'Argentina'", "'France'"
# The n-th goal of the match (1-based), as an action_id.
GOAL = f"""MATCH ()-[g:REALIZOU {{match_id: {M}}}]->() WHERE g.gol
WITH g ORDER BY g.action_id WITH collect(g.action_id) AS goals"""


def last_action(name: str) -> str:
    return f"""MATCH (s:Jogador)-[x:REALIZOU {{match_id: {M}}}]->() WHERE s.nome CONTAINS '{name}'
WITH max(x.action_id) AS last"""


def link(team: str, edge_where: str, node_where: str = "true") -> str:
    """Unweighted betweenness in plain Cypher: for each pair of teammates, the distinct
    shortest routes between them; each player in the middle of a route gets its share."""
    def on(var: str) -> str:
        return node_where.replace("n.", f"{var}.")
    return f"""MATCH (x:Jogador {{time: {team}}}), (y:Jogador {{time: {team}}})
WHERE x.nome < y.nome AND {on("x")} AND {on("y")}
  AND EXISTS {{ MATCH (x)-[r:PASSOU_PARA]-() WHERE {edge_where} }}
  AND EXISTS {{ MATCH (y)-[r:PASSOU_PARA]-() WHERE {edge_where} }}
MATCH path = allShortestPaths((x)-[:PASSOU_PARA*..8]-(y))
WHERE all(r IN relationships(path) WHERE {edge_where}) AND all(n IN nodes(path) WHERE {node_where})
WITH x, y, collect(DISTINCT [n IN nodes(path) | n.nome]) AS routes
UNWIND routes AS route
UNWIND route[1..-1] AS v
WITH x, y, v, size(routes) AS total, count(*) AS through
RETURN v AS player, sum(toFloat(through) / total) AS betweenness ORDER BY betweenness DESC LIMIT 1"""


def pair(team: str, where: str = "true", prefix: str = "") -> str:
    return f"""{prefix} MATCH (a:Jogador {{time: {team}}})-[p:PASSOU_PARA {{match_id: {M}}}]->(b:Jogador)
WHERE {where}
WITH CASE WHEN a.nome < b.nome THEN [a.nome, b.nome] ELSE [b.nome, a.nome] END AS pair, count(*) AS n
RETURN pair ORDER BY n DESC LIMIT 1"""


def receiver(team: str, where: str = "true", prefix: str = "") -> str:
    return f"""{prefix} MATCH (a:Jogador {{time: {team}}})-[p:PASSOU_PARA {{match_id: {M}}}]->(b:Jogador)
WHERE {where} RETURN b.nome, count(*) AS n ORDER BY n DESC LIMIT 1"""


def passer(team: str, where: str = "true", prefix: str = "") -> str:
    return f"""{prefix} MATCH (a:Jogador {{time: {team}}})-[p:PASSOU_PARA {{match_id: {M}}}]->(b:Jogador)
WHERE {where} RETURN a.nome, count(*) AS n ORDER BY n DESC LIMIT 1"""


def partners(team: str, where: str = "true") -> str:
    return f"""MATCH (a:Jogador {{time: {team}}})-[p:PASSOU_PARA {{match_id: {M}}}]-(b:Jogador)
WHERE {where} RETURN a.nome, count(DISTINCT b) AS n ORDER BY n DESC LIMIT 1"""


def only_partner(team: str, where: str = "true") -> str:
    """The player who is some teammate's only passing partner (that teammate is cut off without him)."""
    return f"""MATCH (x:Jogador {{time: {team}}})-[p:PASSOU_PARA {{match_id: {M}}}]-(y:Jogador)
WHERE {where} WITH x, collect(DISTINCT y.nome) AS ys WHERE size(ys) = 1 RETURN ys[0] AS player"""


def trio(team: str, where: str = "true") -> str:
    """A -> B -> C: B's pass is the next pass attempt after A's, in the same possession."""
    return f"""MATCH (a:Jogador {{time: {team}}})-[p1:PASSOU_PARA {{match_id: {M}}}]->(b:Jogador)
      -[p2:PASSOU_PARA {{match_id: {M}}}]->(c:Jogador)
WHERE {where} AND p2.fase_posse_id = p1.fase_posse_id AND p2.action_id > p1.action_id
  AND a <> c AND NOT EXISTS {{ MATCH ()-[x:REALIZOU {{match_id: {M}}}]->()
                              WHERE x.acao IN {PASSES} AND p1.action_id < x.action_id < p2.action_id }}
RETURN [a.nome, b.nome, c.nome] AS trio, count(*) AS n ORDER BY n DESC LIMIT 1"""


def plays(team: str, end: str, start: str = "true", period: str = "true") -> str:
    """Possession phases of a team (first and last action, thirds reached), for play questions."""
    return f"""MATCH (j:Jogador {{time: {team}}})-[r:REALIZOU {{match_id: {M}}}]->() WHERE {period}
WITH r.fase_posse_id AS f, r ORDER BY r.action_id
WITH f, collect(r) AS acts
WITH f, acts[0] AS first, acts[-1] AS last, [a IN acts | a.terco] AS thirds
WHERE {start} AND {end}"""


ENDS_IN_SHOT = f"last.acao IN {SHOTS}"
REACHES_ATTACK = "'ataque' IN thirds"


def players_in(plays_query: str, team: str, with_player: str | None = None) -> str:
    if with_player:
        return f"""{plays_query}
MATCH (w:Jogador)-[:PARTICIPOU_DE {{match_id: {M}}}]->(fp:FaseDePosse {{fase_id: f}})
      <-[:PARTICIPOU_DE {{match_id: {M}}}]-(j:Jogador {{time: {team}}})
WHERE w.nome CONTAINS '{with_player}' AND j <> w
RETURN j.nome, count(*) AS n ORDER BY n DESC LIMIT 1"""
    return f"""{plays_query}
MATCH (j:Jogador {{time: {team}}})-[:PARTICIPOU_DE {{match_id: {M}}}]->(:FaseDePosse {{fase_id: f}})
RETURN j.nome, count(*) AS n ORDER BY n DESC LIMIT 1"""


def pairs_in(plays_query: str, team: str) -> str:
    return f"""{plays_query}
MATCH (a:Jogador {{time: {team}}})-[:PARTICIPOU_DE {{match_id: {M}}}]->(:FaseDePosse {{fase_id: f}})
      <-[:PARTICIPOU_DE {{match_id: {M}}}]-(b:Jogador {{time: {team}}})
WHERE a.nome < b.nome RETURN [a.nome, b.nome] AS pair, count(*) AS n ORDER BY n DESC LIMIT 1"""


AFTER_DI_MARIA = (last_action("Di María"), "p.action_id > last")
AFTER_DEMBELE = (last_action("Dembélé"), "p.action_id > last")

# question id -> Cypher query (first column of the first row is the answer; "list": every row)
QUERIES = {
    "f01": f"""MATCH (j:Jogador)-[r:REALIZOU {{match_id: {M}}}]->() WHERE r.cartao_amarelo
               RETURN j.nome ORDER BY r.action_id LIMIT 1""",
    "f02": f"""MATCH ()-[pen:REALIZOU {{match_id: {M}, acao: 'penalti'}}]->() WITH min(pen.action_id) AS a
               MATCH (j:Jogador)-[f:REALIZOU {{match_id: {M}, acao: 'falta_cometida'}}]->() WHERE f.action_id < a
               RETURN j.nome ORDER BY f.action_id DESC LIMIT 1""",
    "f03": f"""{GOAL}
               MATCH (:Jogador {{time: {FRA}}})-[sv:REALIZOU {{match_id: {M}, acao: 'defesa_do_goleiro'}}]->()
               WHERE sv.action_id < goals[4] WITH max(sv.action_id) AS save
               MATCH (j:Jogador {{time: {ARG}}})-[s:FINALIZOU {{match_id: {M}}}]->() WHERE s.action_id < save
               RETURN j.nome ORDER BY s.action_id DESC LIMIT 1""",
    "f04": f"""{GOAL}
               MATCH (a:Jogador)-[d:DEU_ASSISTENCIA {{match_id: {M}}}]->() WHERE d.action_id <= goals[3]
               RETURN a.nome ORDER BY d.action_id DESC LIMIT 1""",
    "f05": f"""MATCH (j:Jogador {{time: {FRA}}})-[s:FINALIZOU {{match_id: {M}}}]->()
               RETURN j.nome ORDER BY s.action_id DESC LIMIT 1""",
    "a01": f"""MATCH (j:Jogador {{time: {ARG}}})-[r:REALIZOU {{match_id: {M}}}]->()
               WHERE r.acao IN {PASSES} AND r.sucesso AND r.terco = 'ataque'
               RETURN j.nome, count(*) AS n ORDER BY n DESC LIMIT 1""",
    # open-play passes: with every pass, Rabiot and Mbappé tie at 10 (only Rabiot leads in every reading)
    "a02": f"""MATCH (j:Jogador {{time: {FRA}}})-[r:REALIZOU {{match_id: {M}, acao: 'passe'}}]->()
               WHERE r.sucesso AND r.terco = 'ataque'
               RETURN j.nome, count(*) AS n ORDER BY n DESC LIMIT 1""",
    "a03": f"""{GOAL}
               MATCH (:Jogador {{time: {ARG}}})-[r:REALIZOU {{match_id: {M}}}]->()
               WHERE r.acao IN {SHOTS} AND r.action_id > goals[3] RETURN count(*) AS shots""",
    "a05": f"""{GOAL}
               MATCH (j:Jogador {{time: {ARG}}})-[r:REALIZOU {{match_id: {M}}}]->()
               WHERE r.acao IN {PASSES} AND r.sucesso AND goals[1] < r.action_id < goals[2]
               RETURN j.nome, count(*) AS n ORDER BY n DESC LIMIT 1""",
    "a06": f"""MATCH (j:Jogador {{time: {ARG}}})-[r:REALIZOU {{match_id: {M}, acao: 'desarme'}}]->()
               WHERE r.sucesso AND r.periodo IN [3, 4] RETURN j.nome, count(*) AS n ORDER BY n DESC LIMIT 1""",
    "a07": f"""MATCH (j:Jogador)-[r:REALIZOU {{match_id: {M}, acao: 'falta_cometida', periodo: 2}}]->()
               RETURN j.nome, count(*) AS n ORDER BY n DESC LIMIT 1""",
    "n03": (only_partner(ARG), "list"),  # shortcut: the cut-off teammate has a single partner
    "n04": pair(FRA),
    "n05": pair(ARG),
    "n06": partners(ARG),
    "n09": trio(FRA),
    "n11": passer(ARG, "b.nome CONTAINS 'Messi'"),
    "n12": passer(FRA, "b.nome CONTAINS 'Mbappé'"),
    "s01": link(FRA, f"r.match_id = {M} AND r.periodo IN [3, 4]"),
    "s03": pair(FRA, "p.action_id > goals[3]", GOAL),
    "s04": pair(ARG, "p.periodo = 2"),
    "s06": receiver(ARG, "a.nome CONTAINS 'Enzo' AND p.periodo = 2"),
    "s07": trio(ARG, "p1.periodo IN [3, 4]"),
    "s09": partners(ARG, "p.periodo IN [3, 4]"),
    "s10": f"""MATCH (a:Jogador {{time: {ARG}}})-[p:PASSOU_PARA {{match_id: {M}}}]->(b:Jogador),
              (z:Zona {{id_zona: p.zona_origem}})
        WHERE z.corredor = 'direita' AND z.faixa = 'ataque'
        WITH CASE WHEN a.nome < b.nome THEN [a.nome, b.nome] ELSE [b.nome, a.nome] END AS pair, count(*) AS n
        RETURN pair ORDER BY n DESC LIMIT 1""",
    "s11": f"""MATCH (a:Jogador {{time: {ARG}}})-[p:PASSOU_PARA {{match_id: {M}}}]->(b:Jogador),
                     (z:Zona {{id_zona: p.zona_origem}})
               WHERE z.corredor = 'esquerda' AND z.faixa = 'ataque'
               RETURN b.nome, count(*) AS n ORDER BY n DESC LIMIT 1""",
    "s12": receiver(FRA, "goals[1] < p.action_id < goals[2]", GOAL),
    "s13": receiver(FRA, "p.action_id > goals[3]", GOAL),
    "t06": (only_partner(FRA, "p.periodo IN [3, 4]"), "list"),  # same shortcut as n03
    "c01": link(ARG, f"r.match_id = {M}", "NOT n.nome CONTAINS 'Enzo'"),
    "c02": (f"""MATCH (o:Jogador) WHERE o.nome CONTAINS 'Otamendi'
                MATCH (x:Jogador {{time: {ARG}}})-[:PASSOU_PARA {{match_id: {M}}}]-(y:Jogador)
                WITH o, x, collect(DISTINCT y) AS ys WHERE ys = [o] RETURN x.nome""", "list"),
    "q01": f"""MATCH (a:Jogador {{time: {ARG}}})-[p:PASSOU_PARA {{match_id: {M}}}]->(b:Jogador)
                     -[s:FINALIZOU {{match_id: {M}}}]->()
               WHERE s.action_id > p.action_id AND NOT EXISTS {{
                 MATCH (x:Jogador)-[r:REALIZOU {{match_id: {M}}}]->()
                 WHERE p.action_id < r.action_id < s.action_id AND (x <> b OR NOT r.acao IN ['conducao', 'drible']) }}
               RETURN b.nome, count(*) AS n ORDER BY n DESC LIMIT 1""",
    "q03": f"""MATCH (a:Jogador {{time: {ARG}}})-[p1:PASSOU_PARA {{match_id: {M}}}]->(b:Jogador)
                     -[p2:PASSOU_PARA {{match_id: {M}}}]->(c:Jogador)-[s:FINALIZOU {{match_id: {M}}}]->()
               WHERE p1.action_id < p2.action_id < s.action_id AND p1.fase_posse_id = p2.fase_posse_id
                 AND NOT EXISTS {{ MATCH (x:Jogador)-[r:REALIZOU {{match_id: {M}}}]->()
                   WHERE (p2.action_id < r.action_id < s.action_id AND (x <> c OR NOT r.acao IN ['conducao', 'drible']))
                      OR (p1.action_id < r.action_id < p2.action_id AND r.acao IN {PASSES}) }}
               RETURN a.nome, count(*) AS n ORDER BY n DESC LIMIT 1""",
    "p01": pairs_in(plays(ARG, REACHES_ATTACK), ARG),
    "p02": players_in(plays(ARG, ENDS_IN_SHOT, "first.terco = 'defesa'"), ARG),
    "p03": players_in(plays(ARG, ENDS_IN_SHOT), ARG),
    "p04": players_in(plays(FRA, ENDS_IN_SHOT), FRA),
    "p05": players_in(plays(ARG, ENDS_IN_SHOT), ARG, "Messi"),
    "p06": players_in(plays(FRA, ENDS_IN_SHOT), FRA, "Mbappé"),
    "p07": pairs_in(plays(FRA, REACHES_ATTACK), FRA),
    "p08": players_in(plays(FRA, REACHES_ATTACK, "first.terco = 'defesa'", "r.periodo = 2"), FRA),
    "b02": passer(ARG, f"b.nome CONTAINS 'Messi' AND {AFTER_DI_MARIA[1]}", AFTER_DI_MARIA[0]),
    "b03": passer(FRA, f"b.nome CONTAINS 'Mbappé' AND {AFTER_DEMBELE[1]}", AFTER_DEMBELE[0]),
    "b05": receiver(FRA, f"a.nome CONTAINS 'Mbappé' AND {AFTER_DEMBELE[1]}", AFTER_DEMBELE[0]),
    "b06": pair(FRA, AFTER_DEMBELE[1], AFTER_DEMBELE[0]),
    "b07": receiver(ARG, f"a.nome CONTAINS 'Messi' AND {AFTER_DI_MARIA[1]}", AFTER_DI_MARIA[0]),
    "b09": receiver(ARG, AFTER_DI_MARIA[1], AFTER_DI_MARIA[0]),
}


def answer_of(q, result: dict, mode: str):
    if "error" in result:
        return ("error", result["error"])
    rows = result["rows"]
    if not rows:
        return None
    first = rows[0][result["columns"][0]]
    if mode == "list":
        return sorted({r[result["columns"][0]] for r in rows})[:1] if q.check == "player" else \
            sorted({r[result["columns"][0]] for r in rows})
    if q.check == "value":
        return first
    if q.check == "player_and_value":
        return ([first], rows[0][result["columns"][1]])
    if q.check == "set":
        return sorted(first)
    return [first]


def expected(gt: dict, q) -> list:
    if q.check == "value":
        return [gt["value"]]
    if q.check == "player_and_value":
        return [(gt["players"][:1], gt["value"])]
    if q.check == "set":
        return [sorted(a) for a in gt["accepted"]]
    return [a[:1] for a in gt["accepted"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--question")
    args = parser.parse_args()
    logging_setup.setup(level=logging.ERROR)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    gt = ground_truth.load()
    questions = [get_question(args.question)] if args.question else QUESTIONS
    driver = db.make_driver(get_settings())
    tally = {"OK": 0, "XX": 0, "--": 0}
    try:
        for q in questions:
            if q.type == "unanswerable":
                continue
            spec = QUERIES.get(q.id)
            if spec is None:
                tally["--"] += 1
                print(f"--  {q.id}  no query written")
                continue
            query, mode = spec if isinstance(spec, tuple) else (spec, "first")
            got = answer_of(q, cypher.run_query(driver, query), mode)
            ok = got in expected(gt[q.id], q)
            tally["OK" if ok else "XX"] += 1
            want = expected(gt[q.id], q)
            print(f"{'OK' if ok else 'XX'}  {q.id}  ground truth: {want[0] if len(want) == 1 else want}  |  cypher: {got}")
    finally:
        driver.close()
    answerable = sum(1 for q in questions if q.type != "unanswerable")
    print(f"\n{tally['OK']}/{answerable} answered by plain Cypher; {tally['XX']} disagree; "
          f"{tally['--']} without a query")
    return 0 if tally["XX"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

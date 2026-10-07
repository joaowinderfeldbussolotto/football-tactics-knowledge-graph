#!/usr/bin/env python
"""Cross-check: the ground truth (raw JSON / Parquet / networkx) versus the graph.

For each question, prints side by side the expected answer and what Neo4j
answers through a fixed Cypher query (layers 1, 1b and 2, plus GDS run live
for the second place in betweenness, which layer 2 does not store). It
validates the ground truth and the graph at the same time: they are computed
by independent paths, so agreement is evidence that both are right.

No LLM involved.

Usage:
    python scripts/check_ground_truth.py
    python scripts/check_ground_truth.py --question s03
"""

import argparse
import logging
import sys

from football_graphrag.benchmark import ground_truth
from football_graphrag.benchmark.questions import MATCH_ID, QUESTIONS, get_question
from football_graphrag.config import get_settings
from football_graphrag.graph import db, projections
from football_graphrag.observability import logging_setup

M = MATCH_ID


def _rows(driver, query: str, **params) -> list[dict]:
    with driver.session() as session:
        return session.run(query, m=M, **params).data()


def _stat(driver, name: str, field: str):
    rows = _rows(driver, f"MATCH (e:EstatisticaJogador {{match_id: $m, nome: $name}}) RETURN e.{field} AS v",
                 name=name)
    return rows[0]["v"] if rows else None


def _ranking(driver, field: str, n: int) -> list[dict]:
    return _rows(driver, f"""MATCH (e:EstatisticaJogador {{match_id: $m}})
                             RETURN e.nome AS nome, e.{field} AS v ORDER BY v DESC LIMIT {n}""")


def _pivot_pattern(driver, team: str) -> str:
    """Layer 2: the stored PadraoTatico."""
    rows = _rows(driver, """MATCH (p:PadraoTatico {match_id: $m, tipo: 'pivo_estrutural', time: $team})
                            RETURN p.jogadores_envolvidos[0] AS nome""", team=team)
    return rows[0]["nome"]


def _betweenness(driver, team: str) -> list[dict]:
    """GDS run live on the same projection layer 2 uses."""
    with projections.pass_network(driver, M, team, name=f"check_{team}") as g:
        return _rows(driver, """CALL gds.betweenness.stream($g, {relationshipWeightProperty: 'cost'})
                                YIELD nodeId, score
                                RETURN gds.util.asNode(nodeId).nome AS nome, score
                                ORDER BY score DESC, nome""", g=g)


_TRIOS = """
MATCH (a:Jogador)-[p1:PASSOU_PARA {match_id: $m}]->(b:Jogador)-[p2:PASSOU_PARA {match_id: $m}]->(c:Jogador)
WHERE p1.fase_posse_id = p2.fase_posse_id
  AND p2.action_id > p1.action_id AND p2.action_id - p1.action_id <= 3
  AND a <> b AND b <> c AND a <> c
  AND (p2.zona_destino / 8) / 4 > (p1.zona_origem / 8) / 4
  AND a.time = $team
RETURN a.nome AS a, b.nome AS b, c.nome AS c, count(*) AS n,
       sum(p1.xt_gerado + p2.xt_gerado) AS xt_total
ORDER BY n DESC, xt_total DESC
"""


def graph_answer(driver, qid: str) -> dict:
    """What the graph says, in the same shape as the ground truth."""
    def ans(players=(), value=None, detail=""):
        return {"players": list(players), "value": value, "detail": detail}

    if qid == "f01":
        r = _rows(driver, """MATCH (j:Jogador)-[r:REALIZOU {match_id: $m}]->() WHERE r.gol
                             RETURN j.nome AS nome ORDER BY r.periodo, r.segundo LIMIT 1""")
        return ans([r[0]["nome"]])
    if qid == "f02":
        r = _rows(driver, "MATCH (e:EstatisticaTime {match_id: $m}) RETURN sum(e.gols) AS v")
        return ans(value=r[0]["v"])
    if qid == "f03":
        r = _rows(driver, """MATCH (a:Jogador)-[s:DEU_ASSISTENCIA {match_id: $m}]->(b:Jogador {time: 'France'})
                             RETURN a.nome AS nome, s.minuto AS minuto ORDER BY s.periodo, s.minuto""")
        # France's 2nd goal (81') is its only assisted goal; the 1st (80') was a penalty.
        goals = _rows(driver, """MATCH (j:Jogador {time: 'France'})-[r:REALIZOU {match_id: $m}]->() WHERE r.gol
                                 RETURN r.minuto AS minuto ORDER BY r.periodo, r.segundo""")
        second = goals[1]["minuto"]
        return ans([x["nome"] for x in r if x["minuto"] == second], detail=f"2nd goal at {second}'")
    if qid == "f04":
        r = _rows(driver, """MATCH (j:Jogador)-[r:REALIZOU {match_id: $m}]->() WHERE r.cartao_amarelo
                             RETURN j.nome AS nome, r.minuto AS minuto ORDER BY r.periodo, r.segundo LIMIT 1""")
        return ans([r[0]["nome"]], detail=f"{r[0]['minuto']}'")
    if qid == "f05":
        r = _rows(driver, """MATCH (j:Jogador)-[r:REALIZOU {match_id: $m}]->()
                             WHERE r.cartao_amarelo AND r.acao <> 'falta_cometida'
                             RETURN j.nome AS nome, r.acao AS acao""")
        return ans([x["nome"] for x in r], detail=str([x["acao"] for x in r]))
    if qid == "f06":
        return ans(value=_stat(driver, "Lautaro Javier Martínez", "finalizacoes"))
    if qid == "a01":
        r = _ranking(driver, "desarmes_certos", 4)
        return ans([x["nome"] for x in r[:3]], detail=str([(x["nome"], x["v"]) for x in r]))
    if qid in ("a02", "a03", "a05"):
        field = {"a02": "passes_certos", "a03": "dribles_certos", "a05": "faltas_cometidas"}[qid]
        r = _ranking(driver, field, 2)
        return ans([r[0]["nome"]], r[0]["v"], detail=f"2nd: {r[1]['nome']} {r[1]['v']}")
    if qid == "a04":
        r = _rows(driver, "MATCH (e:EstatisticaTime {match_id: $m, nome: 'France'}) RETURN e.finalizacoes AS v")
        return ans(value=r[0]["v"])
    if qid == "a06":
        r = _rows(driver, """MATCH (j:Jogador {time: 'France'})-[r:REALIZOU {match_id: $m}]->()
                             WHERE r.cartao_amarelo RETURN j.nome AS nome""")
        return ans([x["nome"] for x in r])
    if qid in ("s01", "s02"):
        team = "Argentina" if qid == "s01" else "France"
        stored = _pivot_pattern(driver, team)
        live = _betweenness(driver, team)
        return ans([stored], detail=f"PadraoTatico; GDS live top: {live[0]['nome']} {live[0]['score']}")
    if qid == "s03":
        live = _betweenness(driver, "Argentina")
        return ans([live[1]["nome"]], detail=f"GDS live: {[(x['nome'], x['score']) for x in live[:3]]}")
    if qid == "s04":
        trio = graph_answer(driver, "s05")["players"]
        return ans([trio[1]], detail=" -> ".join(trio))
    if qid == "s05":
        stored = _rows(driver, """MATCH (p:PadraoTatico {match_id: $m, tipo: 'terceiro_homem', time: 'France'})
                                  RETURN p.jogadores_envolvidos AS js, p.valor_metrica AS n
                                  ORDER BY n DESC LIMIT 1""")
        return ans(stored[0]["js"], detail=f"PadraoTatico, {stored[0]['n']}x")
    if qid == "s06":
        r = [x for x in _rows(driver, _TRIOS, team="Argentina") if x["n"] >= 2]
        return ans(value=len(r), detail="Cypher path pattern (same as layer 2), n >= 2")
    if qid == "c01":
        p = _pivot_pattern(driver, "Argentina")
        return ans(value=_stat(driver, p, "passes_tentados") - _stat(driver, p, "passes_certos"), detail=p)
    if qid == "c02":
        p = _pivot_pattern(driver, "France")
        return ans(value=_stat(driver, p, "passes_certos"), detail=p)
    if qid == "c03":
        p = _betweenness(driver, "Argentina")[1]["nome"]
        return ans(value=_stat(driver, p, "desarmes_certos"), detail=p)
    if qid == "c04":
        trio = graph_answer(driver, "s05")["players"]
        passes = {p: _stat(driver, p, "passes_certos") for p in trio}
        return ans([max(passes, key=passes.get)], detail=str(passes))
    if qid == "c05":
        a = _pivot_pattern(driver, "Argentina")
        b = _betweenness(driver, "Argentina")[1]["nome"]
        r = _rows(driver, """MATCH (:Jogador {nome: $a})-[p:PASSOU_PARA {match_id: $m}]->(:Jogador {nome: $b})
                             RETURN count(p) AS v""", a=a, b=b)
        return ans(value=r[0]["v"], detail=f"{a} -> {b}")
    if qid == "c06":
        p = _pivot_pattern(driver, "France")
        return ans(value=_stat(driver, p, "faltas_cometidas"), detail=p)
    return ans(detail="no graph query: the data has no answer")


def agrees(question, expected: dict, got: dict) -> bool:
    if question.check == "no_data":
        return not got["players"] and got["value"] is None
    ok = True
    if question.check in ("player", "player_and_value"):
        ok &= bool(got["players"]) and got["players"][0] == expected["players"][0]
    if question.check == "set":
        ok &= set(got["players"]) == set(expected["players"])
    if question.check in ("value", "player_and_value"):
        ok &= got["value"] is not None and abs(float(got["value"]) - float(expected["value"])) <= question.tolerance
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--question", help="check a single question id (e.g. s03)")
    args = parser.parse_args()
    logging_setup.setup(level=logging.WARNING)

    questions = [get_question(args.question)] if args.question else QUESTIONS
    truth = ground_truth.compute()
    driver = db.make_driver(get_settings())
    failures = 0
    try:
        for q in questions:
            exp, got = truth[q.id], graph_answer(driver, q.id)
            ok = agrees(q, exp, got)
            failures += not ok
            fmt = lambda a: ", ".join(a["players"]) + (f" = {a['value']}" if a.get("value") is not None else "")
            print(f"[{'OK ' if ok else 'DIFF'}] {q.id} {q.type:<12} ({exp['source']})")
            print(f"       truth: {fmt(exp) or 'no_data'}   {exp['detail'][:100]}")
            print(f"       graph: {fmt(got) or '-'}   {got['detail'][:100]}")
    finally:
        driver.close()
    print(f"\n{len(questions) - failures}/{len(questions)} agree")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

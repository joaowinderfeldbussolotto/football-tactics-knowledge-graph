#!/usr/bin/env python
"""Cross-check: the ground truth (raw JSON / Parquet / networkx) versus the graph.

For each question, answers it again through the graph_tools tools (Neo4j),
with a fixed recipe of tool calls, and compares with the ground truth. The
two are computed by independent paths, so agreement validates both. The
recipe is also one combination of tools that solves the question: it shows
that the frozen tools are enough, without an LLM.

Usage:
    python scripts/check_ground_truth.py              # active questions
    python scripts/check_ground_truth.py --all        # every stable question
    python scripts/check_ground_truth.py --question s01
"""

import argparse
import logging
import sys

from football_graphrag.benchmark import ground_truth
from football_graphrag.benchmark.questions import ALL_QUESTIONS, QUESTIONS, get_question
from football_graphrag.benchmark.tools import PASS_ACTIONS, Toolbox
from football_graphrag.config import get_settings
from football_graphrag.graph import db
from football_graphrag.observability import logging_setup

SHOTS = ["finalizacao", "penalti", "falta_direta"]


def goal_second(tb: Toolbox, n: int) -> float:
    return tb.list_actions({"goal": True})["actions"][n - 1]["second"]


def first_second(tb: Toolbox, period: int) -> float:
    return tb.list_actions({"period": period}, limit=1)["actions"][0]["second"]


def top_pair(tb: Toolbox, team: str, filters=None) -> list[str]:
    """network_edges lists passer -> receiver; a pair sums both directions."""
    net = tb.pass_network(team, filters)
    pairs: dict[tuple, int] = {}
    for e in tb.network_edges(net["network_id"], top=100)["edges"]:
        key = tuple(sorted((e["passer"], e["receiver"])))
        pairs[key] = pairs.get(key, 0) + e["passes"]
    return list(max(pairs, key=pairs.get))


def top(rows: list[dict], field: str = "player") -> list[str]:
    return [rows[0][field]]


def top_trio(tb: Toolbox, team: str, filters=None) -> list[str]:
    """pass_paths may repeat a player (A -> B -> A); a trio has three different ones."""
    seqs = tb.pass_paths(team, 3, True, True, filters=filters, top=100)["sequences"]
    return next(s["players"] for s in seqs if len(set(s["players"])) == 3)


def top_receiver(tb: Toolbox, team: str, passer: str, filters=None) -> list[str]:
    net = tb.pass_network(team, filters)
    edges = [e for e in tb.network_edges(net["network_id"], player=passer, top=100)["edges"]
             if e["passer"] == tb.resolve_player(passer)]
    return [edges[0]["receiver"]]


# One recipe per question: the tool calls, in order, that answer it.
RECIPES = {
    "f01": lambda tb: [tb.list_actions({"yellow_card": True}, limit=1)["actions"][0]["player"]],
    "f02": lambda tb: [tb.list_actions({"action": "falta_cometida",
                                        "second_to": tb.list_actions({"action": "penalti"}, 1)["actions"][0]["second"]},
                                       100)["actions"][-1]["player"]],
    "f03": lambda tb: [next(a["player"] for a in reversed(tb.list_actions(
        {"action": SHOTS, "second_from": goal_second(tb, 5) - 60, "second_to": goal_second(tb, 5)}, 100)["actions"])
        if a["outcome"] == "defendida")],
    "f04": lambda tb: [[a for a in tb.list_actions({"assist": True})["actions"]
                        if a["second"] <= goal_second(tb, 4)][-1]["player"]],
    "a01": lambda tb: top(tb.query_actions({"team": "Argentina", "action": list(PASS_ACTIONS), "success": True,
                                            "third": "attacking"}, ["player"], top=1)),
    "a03": lambda tb: tb.query_actions({"team": "Argentina", "action": SHOTS,
                                        "second_from": goal_second(tb, 4)})[0]["count"],
    "a05": lambda tb: (lambda r: ([r["player"]], r["count"]))(tb.query_actions(
        {"team": "Argentina", "action": list(PASS_ACTIONS), "success": True,
         "second_from": goal_second(tb, 2), "second_to": goal_second(tb, 3)}, ["player"], top=1)[0]),
    "a06": lambda tb: top(tb.query_actions({"team": "Argentina", "action": "desarme", "success": True,
                                            "second_from": first_second(tb, 3)}, ["player"], top=1)),
    "n03": lambda tb: tb.network_metric(tb.pass_network("Argentina")["network_id"],
                                        "articulation_points")["articulation_points"],
    "n04": lambda tb: top_pair(tb, "France"),
    "n05": lambda tb: top_pair(tb, "Argentina"),
    "s01": lambda tb: top(tb.network_metric(tb.pass_network("France", {"second_from": first_second(tb, 3)})["network_id"],
                                            "betweenness", "none", "directed", top=1)["ranking"]),
    "s03": lambda tb: top_pair(tb, "France", {"second_from": goal_second(tb, 4)}),
    "s04": lambda tb: top_pair(tb, "Argentina", {"period": 2}),
    "f05": lambda tb: [tb.list_actions({"team": "France", "action": SHOTS}, 100)["actions"][-1]["player"]],
    "f06": lambda tb: [a["player"] for a in tb.list_actions({"yellow_card": True})["actions"]
                       if a["action"] != "falta_cometida"],
    "a07": lambda tb: top(tb.query_actions({"action": "falta_cometida", "period": 2}, ["player"], top=1)),
    "a08": lambda tb: top(tb.query_actions({"action": "drible", "success": True, "period": [3, 4]},
                                           ["player"], top=1)),
    "n06": lambda tb: top(tb.network_metric(tb.pass_network("Argentina")["network_id"], "degree", "none",
                                            "undirected", top=1)["ranking"]),
    "n08": lambda tb: top_receiver(tb, "Argentina", "Messi"),
    "n09": lambda tb: top_trio(tb, "France"),
    "n10": lambda tb: top_trio(tb, "Argentina"),
    "s05": lambda tb: tb.network_metric(tb.pass_network("Argentina", {"period": [3, 4]})["network_id"],
                                        "articulation_points")["articulation_points"],
    "s06": lambda tb: top_receiver(tb, "Argentina", "Enzo Fernández", {"period": 2}),
    "s07": lambda tb: top_trio(tb, "Argentina", {"period": [3, 4]}),
}


def expected(gt: dict, q) -> object:
    if q.check == "value":
        return gt["value"]
    if q.check == "player_and_value":
        return (gt["players"][:1], gt["value"])
    if q.check == "set":
        return sorted(gt["players"])
    return gt["players"][:1]


def normalized(q, got) -> object:
    if q.check == "set":
        return sorted(got)
    if q.check == "player":
        return got[:1]
    return got


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--question")
    parser.add_argument("--all", action="store_true", help="every stable question, not only the active ones")
    args = parser.parse_args()
    logging_setup.setup(level=logging.WARNING)

    gt = ground_truth.compute()
    questions = [get_question(args.question)] if args.question else (
        [q for q in ALL_QUESTIONS if gt[q.id]["stable"]] if args.all else QUESTIONS)
    driver = db.make_driver(get_settings())
    agree = 0
    try:
        for q in questions:
            truth = gt[q.id]
            if not truth["stable"]:
                print(f"--  {q.id}  unstable across readings (stage {q.stage}); not checked")
                continue
            if q.type == "unanswerable":
                # Nothing to compare: no tool returns tracking, speeds or distances.
                print(f"OK  {q.id}  no data expected; the tools expose only on-ball events")
                agree += 1
                continue
            tb = Toolbox(driver)
            try:
                got = normalized(q, RECIPES[q.id](tb))
            finally:
                tb.close()
            want = expected(truth, q)
            ok = got == want
            agree += ok
            print(f"{'OK ' if ok else 'XX '} {q.id}  ground truth: {want}  |  graph (tools): {got}")
    finally:
        driver.close()
    checked = sum(1 for q in questions if gt[q.id]["stable"])
    print(f"\n{agree}/{checked} agree")
    return 0 if agree == checked else 1


if __name__ == "__main__":
    sys.exit(main())

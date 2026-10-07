"""Ground truth for the benchmark questions, with a robustness test. Never reads Neo4j.

The answer key comes from a path independent of the systems being evaluated:
pandas over the RAW StatsBomb JSON (facts, simple counts) or the layer 0
Parquet (counts whose definition belongs to layer 0, passes with receiver),
and networkx for pass networks.

Robustness test: a question in football language can be read in more than
one way ("passes" with or without set pieces, a connection weighted by the
number of passes or by xT, "after the goal" with or without the goal
itself...). Each answer function returns the answer under EVERY reasonable
reading. A question is ``stable`` when all readings agree on what its check
looks at; an unstable question leaves the benchmark (``stage: removed`` in
the YAML). Ties count as unstable: "who did the most" has no single answer.

Readings used:
- pass set: every completed pass (set pieces, throw-ins, goal kicks
  included) or open-play passes only (layer 0 action ``passe``);
- network weight: none, number of passes, xT (betweenness turns weights into
  lengths, ``1/passes`` and ``1/(1+xT)``; other metrics use them as
  strengths, negative xT as zero);
- network direction: directed (passer -> receiver) or undirected (both
  directions of a pair summed);
- time cut at an event: the event itself included or not.

Usage: ``python -m football_graphrag.benchmark.ground_truth`` writes
``data/benchmark/ground_truth.json`` (every question, with all readings).
"""

import itertools
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

import networkx as nx
import pandas as pd

from football_graphrag.benchmark.questions import ALL_QUESTIONS, MATCH_ID, Question
from football_graphrag.config import get_settings

# The layer 0 actions that are pass attempts (graph/build.py::PASS_TYPES).
PASS_ACTIONS = (
    "passe", "cruzamento", "arremesso_lateral", "falta_cobrada_curta", "falta_cobrada_na_area",
    "escanteio_curto", "escanteio_na_area", "tiro_de_meta",
)
PASS_SETS = {"all passes": PASS_ACTIONS, "open-play passes": ("passe",)}
WEIGHTS = ("none", "passes", "xt")
DIRECTIONS = ("directed", "undirected")


# --------------------------------------------------------------------------- loading

@lru_cache
def raw_events(match_id: int = MATCH_ID) -> list[dict]:
    """Raw StatsBomb events, without the penalty shootout (period 5)."""
    path = get_settings().raw_dir / "statsbomb" / "events" / f"{match_id}.json"
    return [e for e in json.loads(path.read_text()) if e["period"] <= 4]


@lru_cache
def actions(match_id: int = MATCH_ID) -> pd.DataFrame:
    """Layer 0 actions in match order, with receiver name and team."""
    df = pd.read_parquet(get_settings().processed_dir / f"{match_id}.parquet")
    df = df.sort_values(["period_id", "time_seconds", "action_id"]).reset_index(drop=True)
    df["order"] = range(len(df))
    known = df.dropna(subset=["player_id"])
    names = known.groupby("player_id").player_name.first()
    teams = known.groupby("player_id").team_name.first()
    rec = df.receiver_player_id
    df["receiver"] = rec.map(lambda r: names.get(int(r)) if pd.notna(r) else None)
    df["receiver_team"] = rec.map(lambda r: teams.get(int(r)) if pd.notna(r) else None)
    return df


def goal_order(n: int) -> int:
    """Match order of the n-th goal (1-based)."""
    return int(actions()[actions().gol].order.iloc[n - 1])


def after(order: int, inclusive: bool):
    return lambda d: d.order >= order if inclusive else d.order > order


def between(start: int, end: int, inclusive: bool):
    return lambda d: (d.order >= start) & (d.order <= end) if inclusive else (d.order > start) & (d.order < end)


def periods(*ids: int):
    return lambda d: d.period_id.isin(ids)


def _type(e: dict) -> str:
    return e["type"]["name"]


def _player(e: dict) -> str | None:
    return e.get("player", {}).get("name")


# --------------------------------------------------------------------------- answers and readings

def answer(players=(), value=None) -> dict:
    return {"players": list(players), "value": value}


def tie(*candidates) -> dict:
    return {"tie": [list(c) if isinstance(c, tuple) else c for c in candidates]}


def leader(scores: dict, n: int = 1) -> dict:
    """The top player (or n players), or a tie at the boundary."""
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    if not ranked:
        return tie()
    if len(ranked) > n and ranked[n - 1][1] == ranked[n][1]:
        return tie(*[p for p, s in ranked if s == ranked[n - 1][1]])
    return answer([p for p, _ in ranked[:n]], ranked[n - 1][1] if n == 1 else None)


def readings_product(**axes):
    """Every combination of the reading axes, as (label, {axis: value})."""
    keys = list(axes)
    for values in itertools.product(*(axes[k] for k in keys)):
        yield " / ".join(str(v) for v in values), dict(zip(keys, values))


# --------------------------------------------------------------------------- pass networks (networkx)

def team_passes(team: str, pass_set=PASS_ACTIONS, mask=None) -> pd.DataFrame:
    """Completed passes between teammates (the edges of the pass network)."""
    df = actions()
    p = df[df.acao.isin(pass_set) & df.receiver.notna() & (df.team_name == team)
           & (df.receiver_team == team) & (df.receiver != df.player_name)]
    return p if mask is None else p[mask(p)]


def pass_network(team: str, direction: str, pass_set=PASS_ACTIONS, mask=None) -> nx.Graph:
    """Directed: one edge per passer -> receiver. Undirected: both directions of a
    pair summed. Edge attributes: passes, xt, and the betweenness lengths
    (``len_passes`` = 1/passes, ``len_xt`` = 1/(1+xt), the layer 2 cost)."""
    p = team_passes(team, pass_set, mask)
    agg = p.groupby(["player_name", "receiver"]).agg(passes=("order", "size"), xt=("xt_value", "sum"))
    g = nx.DiGraph() if direction == "directed" else nx.Graph()
    for (a, b), row in agg.iterrows():
        old = g.get_edge_data(a, b, {"passes": 0, "xt": 0.0}) if direction == "undirected" else {"passes": 0, "xt": 0.0}
        g.add_edge(a, b, passes=old["passes"] + int(row.passes), xt=old["xt"] + float(row.xt))
    for _, _, e in g.edges(data=True):
        e["len_passes"], e["len_xt"] = 1.0 / e["passes"], 1.0 / (1.0 + e["xt"])
    return g


def betweenness(g: nx.Graph, weight: str) -> dict:
    """GDS ``gds.betweenness.stream`` equivalent (raw scores, not normalized)."""
    w = {"none": None, "passes": "len_passes", "xt": "len_xt"}[weight]
    return nx.betweenness_centrality(g, weight=w, normalized=False)


def link_readings(team: str, cuts: dict | None = None) -> dict:
    """'Main link of the ball circulation': top betweenness in every reading."""
    out = {}
    for label, r in readings_product(passes=PASS_SETS, direction=DIRECTIONS, weight=WEIGHTS,
                                     **({"cut": list(cuts)} if cuts else {})):
        mask = cuts[r["cut"]] if cuts else None
        g = pass_network(team, r["direction"], PASS_SETS[r["passes"]], mask)
        out[label] = leader(betweenness(g, r["weight"]))
    return out


def pair_readings(team: str, cuts: dict | None = None) -> dict:
    """'Pair that exchanged the most passes': the heaviest connection, with both
    directions summed (undirected) or one direction only (directed)."""
    out = {}
    for label, r in readings_product(passes=PASS_SETS, direction=DIRECTIONS,
                                     **({"cut": list(cuts)} if cuts else {})):
        mask = cuts[r["cut"]] if cuts else None
        g = pass_network(team, r["direction"], PASS_SETS[r["passes"]], mask)
        edges = sorted(((d["passes"], tuple(sorted((a, b)))) for a, b, d in g.edges(data=True)), reverse=True)
        if len(edges) > 1 and edges[0][0] == edges[1][0]:
            out[label] = tie(*[pair for n, pair in edges if n == edges[0][0]])
        else:
            out[label] = answer(edges[0][1], edges[0][0])
    return out


def isolating_player_readings(team: str, cuts: dict | None = None) -> dict:
    """'Player without whom a teammate would exchange passes with nobody': the
    articulation points of the network. Direction does not matter (a player
    cut off in the undirected network is cut off in both directions)."""
    out = {}
    for label, r in readings_product(passes=PASS_SETS, **({"cut": list(cuts)} if cuts else {})):
        mask = cuts[r["cut"]] if cuts else None
        points = sorted(nx.articulation_points(pass_network(team, "undirected", PASS_SETS[r["passes"]], mask)))
        out[label] = answer(points) if len(points) == 1 else tie(*points)
    return out


# --------------------------------------------------------------------------- the questions

def f01() -> dict:
    cards = sorted(
        ((e["minute"], e["second"], _player(e)) for e in raw_events()
         for key in ("foul_committed", "bad_behaviour")
         if e.get(key, {}).get("card", {}).get("name") == "Yellow Card"))
    return {"raw JSON": answer([cards[0][2]])}


def f02() -> dict:
    fouls = [e for e in raw_events() if _type(e) == "Foul Committed" and e.get("foul_committed", {}).get("penalty")]
    return {"raw JSON (foul flagged as penalty)": answer([_player(fouls[0])])}


def f03() -> dict:
    goal = next(e for e in raw_events() if _type(e) == "Shot" and e["shot"]["outcome"]["name"] == "Goal"
                and e["period"] == 4 and _player(e).startswith("Lionel"))
    saved = [e for e in raw_events() if _type(e) == "Shot" and e["shot"]["outcome"]["name"] == "Saved"
             and e["index"] < goal["index"] and e["possession"] == goal["possession"]]
    return {"raw JSON (saved shot in the goal's possession)": answer([_player(saved[-1])])}


def f04() -> dict:
    goals = [e for e in raw_events() if _type(e) == "Shot" and e["shot"]["outcome"]["name"] == "Goal"]
    equalizer = goals[3]  # 2-2, regular time
    assist = [e for e in raw_events() if _type(e) == "Pass" and e["pass"].get("goal_assist")
              and e["index"] < equalizer["index"]][-1]
    df = actions()
    last_pass = df[(df.order < goal_order(4)) & (df.receiver == equalizer["player"]["name"])].iloc[-1]
    return {"raw JSON (goal_assist)": answer([_player(assist)]),
            "layer 0 (last pass to the scorer)": answer([last_pass.player_name])}


def _final_third_passers(team: str) -> dict:
    df = actions()
    out = {}
    for label, r in readings_product(passes=PASS_SETS, third=("third where the pass starts", "third where it ends")):
        p = df[df.acao.isin(PASS_SETS[r["passes"]]) & df.sucesso & (df.team_name == team)]
        p = p[p.terco == "ataque"] if r["third"].startswith("third where the pass starts") else p[p.zone_end // 8 >= 8]
        out[label] = leader(Counter(p.player_name))
    return out


def a01() -> dict:
    return _final_third_passers("Argentina")


def a02() -> dict:
    return _final_third_passers("France")


def _shots_after_equalizer(team: str) -> dict:
    df = actions()
    out = {}
    for inclusive in (True, False):
        cut = "with the 2-2 shot" if inclusive else "without the 2-2 shot"
        shots = df[after(goal_order(4), inclusive)(df) & (df.grupo_acao == "finalizacao") & (df.team_name == team)]
        out[f"layer 0 / {cut}"] = answer(value=len(shots))
    # the same count from the raw JSON
    goal_index = [e for e in raw_events() if _type(e) == "Shot" and e["shot"]["outcome"]["name"] == "Goal"][3]["index"]
    for inclusive in (True, False):
        cut = "with the 2-2 shot" if inclusive else "without the 2-2 shot"
        n = sum(1 for e in raw_events() if _type(e) == "Shot" and e["team"]["name"] == team
                and (e["index"] >= goal_index if inclusive else e["index"] > goal_index))
        out[f"raw JSON / {cut}"] = answer(value=n)
    return out


def a03() -> dict:
    return _shots_after_equalizer("Argentina")


def a04() -> dict:
    return _shots_after_equalizer("France")


def a05() -> dict:
    df = actions()
    out = {}
    for label, r in readings_product(passes=PASS_SETS, cut=("goals included", "goals excluded")):
        window = between(goal_order(2), goal_order(3), r["cut"] == "goals included")
        p = df[window(df) & df.acao.isin(PASS_SETS[r["passes"]]) & df.sucesso & (df.team_name == "Argentina")]
        out[label] = leader(Counter(p.player_name))
    return out


def a06() -> dict:
    df = actions()
    t = df[periods(3, 4)(df) & (df.acao == "desarme") & df.sucesso & (df.team_name == "Argentina")]
    return {"layer 0 (tackles won)": leader(Counter(t.player_name))}


def n01() -> dict:
    return link_readings("Argentina")


def n02() -> dict:
    return link_readings("France")


def n03() -> dict:
    return isolating_player_readings("Argentina")


def n04() -> dict:
    return pair_readings("France")


def n05() -> dict:
    return pair_readings("Argentina")


def s01() -> dict:
    return link_readings("France", {"extra time": periods(3, 4)})


def s02() -> dict:
    cuts = {"goals included": between(goal_order(2), goal_order(3), True),
            "goals excluded": between(goal_order(2), goal_order(3), False)}
    return link_readings("France", cuts)


def s03() -> dict:
    cuts = {"with the 2-2 goal": after(goal_order(4), True), "without the 2-2 goal": after(goal_order(4), False)}
    return pair_readings("France", cuts)


def s04() -> dict:
    return pair_readings("Argentina", {"2nd half": periods(2)})


ANSWERS = {name: fn for name, fn in globals().items() if callable(fn) and name[:1] in "fansu"
           and name[1:].isdigit()}

# A premise a question states, which must be stable too even though the
# check does not look at it: s04 says the 1st half pair is no longer the
# main one in the 2nd half.
CONTEXT = {"s04": lambda: pair_readings("Argentina", {"1st half": periods(1)})}


# --------------------------------------------------------------------------- stability

def key(q: Question, a: dict):
    """What the question's check looks at, so readings can be compared."""
    if "tie" in a:
        return ("tie",)
    if q.check == "player":
        return a["players"][:1]
    if q.check == "set":
        return tuple(sorted(a["players"]))
    if q.check == "value":
        return a["value"]
    return (a["players"][:1], a["value"])  # player_and_value


def evaluate(q: Question) -> dict:
    if q.type == "unanswerable":
        return {"players": [], "value": None, "no_data": True, "stable": True, "readings": {},
                "detail": q.note}
    readings = ANSWERS[q.id]()
    stable = _agree(q, readings)
    first = next(iter(readings.values()))
    out = {
        "players": first["players"] if stable else None,
        # a count that varies across readings is not part of a player check
        "value": first.get("value") if stable and q.check in ("value", "player_and_value") else None,
        "no_data": False,
        "stable": stable,
        "readings": readings,
    }
    if q.id in CONTEXT:
        context = CONTEXT[q.id]()
        out["context_readings"] = context
        out["stable"] = stable and _agree(q, context)
    return out


def _agree(q: Question, readings: dict) -> bool:
    keys = {str(key(q, a)) for a in readings.values()}
    return len(keys) == 1 and "('tie',)" not in keys


def compute() -> dict[str, dict]:
    missing = [q.id for q in ALL_QUESTIONS if q.type != "unanswerable" and q.id not in ANSWERS]
    if missing:
        raise ValueError(f"no answer function for {missing}")
    return {q.id: evaluate(q) for q in ALL_QUESTIONS}


def ground_truth_path() -> Path:
    return get_settings().data_dir / "benchmark" / "ground_truth.json"


def write() -> Path:
    path = ground_truth_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(compute(), ensure_ascii=False, indent=2) + "\n")
    return path


def load() -> dict[str, dict]:
    """Ground truth from disk; computed and written on first use."""
    path = ground_truth_path()
    if not path.exists():
        write()
    return json.loads(path.read_text())


if __name__ == "__main__":
    print(f"written {write()}")

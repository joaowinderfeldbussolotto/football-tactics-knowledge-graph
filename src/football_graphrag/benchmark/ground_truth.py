"""Ground truth for the 30 benchmark questions. Never reads Neo4j.

The answer key is computed by a path independent of the systems being
evaluated:

- facts and simple counts (goals, cards, assists, shots, fouls, completed
  passes, dribbles) come from the RAW StatsBomb JSON;
- counts whose definition belongs to layer 0 (a "successful tackle" is
  defined in ``ingestion/football_semantics.py``) come from the layer 0
  Parquet, applying the same definition;
- structural answers are computed with networkx on the layer 0 Parquet,
  replicating ``graph/projections.py::pass_network`` and the Cypher of
  ``graph/analysis.py::terceiro_homem`` exactly.

Sanity check against the official FIFA match report: 6 goals (broadcast
minutes 23, 36, 80, 81, 108, 118) and 7 yellow cards during play (the 8th,
Emiliano Martínez's, was shown in the penalty shootout and is out of scope).
StatsBomb's ``minute`` field is elapsed minutes, so it reads 22, 35, 79, 80,
107, 117; the layer 0 ``minuto`` column adds 1.

Usage: ``python -m football_graphrag.benchmark.ground_truth`` writes
``data/benchmark/ground_truth.json``.
"""

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

import networkx as nx
import pandas as pd

from football_graphrag.benchmark.questions import MATCH_ID, QUESTIONS
from football_graphrag.config import get_settings

# Same list as graph/build.py: the SPADL action types that become PASSOU_PARA.
PASS_TYPES = [
    "pass", "cross", "freekick_short", "corner_short", "throw_in",
    "goalkick", "freekick_crossed", "corner_crossed",
]
TEAMS = {"Argentina": "Argentina", "França": "France"}


# --------------------------------------------------------------------------- loading

@lru_cache
def raw_events(match_id: int = MATCH_ID) -> list[dict]:
    """Raw StatsBomb events, without the penalty shootout (period 5)."""
    path = get_settings().raw_dir / "statsbomb" / "events" / f"{match_id}.json"
    return [e for e in json.loads(path.read_text()) if e["period"] <= 4]


@lru_cache
def actions(match_id: int = MATCH_ID) -> pd.DataFrame:
    """Layer 0 SPADL actions."""
    return pd.read_parquet(get_settings().processed_dir / f"{match_id}.parquet")


def _type(e: dict) -> str:
    return e["type"]["name"]


def _player(e: dict) -> str | None:
    return e.get("player", {}).get("name")


def _is_completed_pass(e: dict) -> bool:
    # StatsBomb marks only failed passes with an outcome.
    return _type(e) == "Pass" and "outcome" not in e["pass"]


# --------------------------------------------------------------------------- raw JSON

def goals() -> list[dict]:
    return [
        {"minute": e["minute"], "player": _player(e), "team": e["team"]["name"]}
        for e in raw_events()
        if _type(e) == "Shot" and e["shot"]["outcome"]["name"] == "Goal"
    ]


def yellow_cards() -> list[dict]:
    """Yellow cards come from fouls and from "Bad Behaviour" (no foul)."""
    cards = []
    for e in raw_events():
        for key in ("foul_committed", "bad_behaviour"):
            card = e.get(key, {}).get("card", {}).get("name")
            if card == "Yellow Card":
                cards.append({"minute": e["minute"], "second": e["second"], "player": _player(e),
                              "team": e["team"]["name"], "foul": key == "foul_committed"})
    return sorted(cards, key=lambda c: (c["minute"], c["second"]))


def assist_for(goal: dict) -> str | None:
    """The pass marked ``goal_assist`` in the same team, closest before the goal."""
    candidates = [
        e for e in raw_events()
        if _type(e) == "Pass" and e["pass"].get("goal_assist")
        and e["team"]["name"] == goal["team"] and e["minute"] <= goal["minute"]
    ]
    return _player(max(candidates, key=lambda e: (e["minute"], e["second"]))) if candidates else None


def count_by_player(predicate) -> Counter:
    return Counter(_player(e) for e in raw_events() if predicate(e))


def completed_passes() -> Counter:
    return count_by_player(_is_completed_pass)


def failed_passes() -> Counter:
    return count_by_player(lambda e: _type(e) == "Pass" and "outcome" in e["pass"])


def completed_passes_between(passer: str, receiver: str) -> int:
    return sum(
        1 for e in raw_events()
        if _is_completed_pass(e) and _player(e) == passer
        and e["pass"].get("recipient", {}).get("name") == receiver
    )


# --------------------------------------------------------------------------- parquet

def successful_tackles() -> Counter:
    """Layer 0 definition: ``acao == 'desarme'`` and ``sucesso``."""
    df = actions()
    return Counter(df[(df.acao == "desarme") & df.sucesso].player_name)


def _player_teams() -> dict[int, str]:
    # The same rule as graph/build.py::_write_jogadores: the team of a
    # player's first action.
    df = actions().dropna(subset=["player_id"])
    return df.groupby("player_id").team_name.first().to_dict()


def _player_names() -> dict[int, str]:
    df = actions().dropna(subset=["player_id"])
    return df.groupby("player_id").player_name.first().to_dict()


def completed_pass_actions() -> pd.DataFrame:
    """The rows that become PASSOU_PARA edges: passes with a known receiver."""
    df = actions()
    p = df[df.receiver_player_id.notna() & df.type_name.isin(PASS_TYPES)].copy()
    p["receiver_id"] = p.receiver_player_id.astype(int)
    p["receiver_name"] = p.receiver_id.map(_player_names())
    p["receiver_team"] = p.receiver_id.map(_player_teams())
    p["passer_team"] = p.player_id.astype(int).map(_player_teams())
    return p


def pass_network(team: str) -> nx.DiGraph:
    """Replica of graph/projections.py::pass_network.

    Directed; nodes are the team's players; one edge per (a, b) pair with
    ``n_passes``, ``xt_total`` and ``cost = 1 / (1 + xt_total)``.
    """
    p = completed_pass_actions()
    p = p[(p.passer_team == team) & (p.receiver_team == team)]
    agg = p.groupby(["player_name", "receiver_name"]).agg(
        n_passes=("action_id", "size"), xt_total=("xt_value", "sum")
    )
    g = nx.DiGraph()
    for (a, b), row in agg.iterrows():
        g.add_edge(a, b, n_passes=int(row.n_passes), xt_total=float(row.xt_total),
                   cost=1.0 / (1.0 + float(row.xt_total)))
    return g


def betweenness_ranking(team: str) -> list[tuple[str, float]]:
    """GDS ``gds.betweenness.stream`` with ``relationshipWeightProperty: 'cost'``.

    GDS returns raw (non-normalized) scores, hence ``normalized=False``.
    """
    scores = nx.betweenness_centrality(pass_network(team), weight="cost", normalized=False)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def progressive_trios() -> pd.DataFrame:
    """Replica of the Cypher in graph/analysis.py::terceiro_homem.

    Two PASSOU_PARA edges a->b->c in the same possession phase, the second
    1 to 3 action_ids after the first, three distinct players, and the
    final zone in a more advanced third than the starting zone
    (``(zone // 8) // 4``: 12x8 grid, 4 columns per third).
    """
    p = completed_pass_actions().sort_values("action_id")
    first = p[["action_id", "possession_id", "player_name", "receiver_name", "passer_team",
               "zone_start", "xt_value"]]
    second = p[["action_id", "possession_id", "player_name", "receiver_name", "zone_end", "xt_value"]]
    m = first.merge(second, left_on=["possession_id", "receiver_name"],
                    right_on=["possession_id", "player_name"], suffixes=("_1", "_2"))
    gap = m.action_id_2 - m.action_id_1
    m = m[(gap > 0) & (gap <= 3)]
    m = m[(m.player_name_1 != m.receiver_name_2) & (m.player_name_1 != m.receiver_name_1)
          & (m.receiver_name_1 != m.receiver_name_2)]
    m = m[(m.zone_end.astype(int) // 8) // 4 > (m.zone_start.astype(int) // 8) // 4]
    m = m.rename(columns={"player_name_1": "a", "receiver_name_1": "b", "receiver_name_2": "c",
                          "passer_team": "team"})
    m["xt"] = m.xt_value_1 + m.xt_value_2
    out = m.groupby(["team", "a", "b", "c"]).agg(n=("xt", "size"), xt_total=("xt", "sum")).reset_index()
    return out.sort_values(["n", "xt_total"], ascending=[False, False]).reset_index(drop=True)


# --------------------------------------------------------------------------- answers

def _answer(source: str, players=(), value=None, no_data=False, detail="") -> dict:
    return {"source": source, "players": list(players), "value": value, "no_data": no_data,
            "detail": detail}


def _top(counter: Counter, n: int = 1) -> list[tuple[str, int]]:
    """Top n, refusing ties at the boundary: a tie would make the question ambiguous."""
    ranked = counter.most_common()
    if len(ranked) > n and ranked[n - 1][1] == ranked[n][1]:
        raise ValueError(f"tie at position {n}: {ranked[: n + 1]}")
    return ranked[:n]


def _pivot(team: str, position: int = 1) -> tuple[str, float]:
    ranking = betweenness_ranking(team)
    if ranking[position - 1][1] == ranking[position][1]:
        raise ValueError(f"betweenness tie at position {position} for {team}: {ranking[:position + 1]}")
    return ranking[position - 1]


def _top_trio(team: str) -> tuple[list[str], int]:
    t = progressive_trios()
    t = t[t.team == team]
    if t.iloc[0].n == t.iloc[1].n:
        raise ValueError(f"trio tie for {team}: {t.head(2).to_dict('records')}")
    row = t.iloc[0]
    return [row.a, row.b, row.c], int(row.n)


def compute() -> dict[str, dict]:
    g = goals()
    cards = yellow_cards()
    shots = count_by_player(lambda e: _type(e) == "Shot")
    fouls = count_by_player(lambda e: _type(e) == "Foul Committed")
    dribbles = count_by_player(lambda e: _type(e) == "Dribble" and e["dribble"]["outcome"]["name"] == "Complete")
    passes_ok = completed_passes()
    france_goals = [x for x in g if x["team"] == "France"]

    arg_pivot, arg_pivot_score = _pivot("Argentina")
    fra_pivot, fra_pivot_score = _pivot("France")
    arg_second, arg_second_score = _pivot("Argentina", 2)
    fra_second, fra_second_score = _pivot("France", 2)
    fra_trio, fra_trio_n = _top_trio("France")
    trios = progressive_trios()
    arg_repeated = trios[(trios.team == "Argentina") & (trios.n >= 2)]

    (top_passer, top_passes), = _top(passes_ok)
    (top_dribbler, top_dribbles), = _top(dribbles)
    (top_fouler, top_fouls), = _top(fouls)
    top_tacklers = _top(successful_tackles(), 3)
    (trio_best_passer, trio_best_passes), = _top(Counter({p: passes_ok[p] for p in fra_trio}))

    gt = {
        "f01": _answer("raw_json", [g[0]["player"]], detail=f"goal at StatsBomb minute {g[0]['minute']}"),
        "f02": _answer("raw_json", value=len(g), detail=str([(x["minute"], x["player"]) for x in g])),
        "f03": _answer("raw_json", [assist_for(france_goals[1])],
                       detail=f"France's 2nd goal, StatsBomb minute {france_goals[1]['minute']}"),
        "f04": _answer("raw_json", [cards[0]["player"]], detail=f"StatsBomb minute {cards[0]['minute']}"),
        "f05": _answer("raw_json", [c["player"] for c in cards if not c["foul"]],
                       detail="the only yellow card from a Bad Behaviour event"),
        "f06": _answer("raw_json", value=shots["Lautaro Javier Martínez"]),
        "a01": _answer("parquet", [p for p, _ in top_tacklers], detail=str(top_tacklers)),
        "a02": _answer("raw_json", [top_passer], top_passes),
        "a03": _answer("raw_json", [top_dribbler], top_dribbles),
        "a04": _answer("raw_json", value=sum(1 for e in raw_events() if _type(e) == "Shot"
                                             and e["team"]["name"] == "France")),
        "a05": _answer("raw_json", [top_fouler], top_fouls),
        "a06": _answer("raw_json", [c["player"] for c in cards if c["team"] == "France"]),
        "s01": _answer("parquet", [arg_pivot], detail=f"betweenness {arg_pivot_score}"),
        "s02": _answer("parquet", [fra_pivot], detail=f"betweenness {fra_pivot_score}"),
        "s03": _answer("parquet", [arg_second], detail=f"betweenness {arg_second_score}"),
        "s04": _answer("parquet", [fra_second], detail=f"betweenness {fra_second_score}"),
        "s05": _answer("parquet", fra_trio, detail=f"{' -> '.join(fra_trio)}, {fra_trio_n}x"),
        "s06": _answer("parquet", value=len(arg_repeated),
                       detail=str([" -> ".join((r.a, r.b, r.c)) for r in arg_repeated.itertuples()])),
        "c01": _answer("parquet+raw_json", value=failed_passes()[arg_pivot], detail=f"pivot: {arg_pivot}"),
        "c02": _answer("parquet+raw_json", value=passes_ok[fra_pivot], detail=f"pivot: {fra_pivot}"),
        "c03": _answer("parquet", value=successful_tackles()[arg_second], detail=f"2nd: {arg_second}"),
        "c04": _answer("parquet+raw_json", [trio_best_passer],
                       detail=str({p: passes_ok[p] for p in fra_trio})),
        "c05": _answer("parquet+raw_json", value=completed_passes_between(arg_pivot, arg_second),
                       detail=f"{arg_pivot} -> {arg_second}"),
        "c06": _answer("parquet+raw_json", value=fouls[fra_second], detail=f"2nd: {fra_second}"),
    }
    for q in QUESTIONS:
        if q.type == "unanswerable":
            gt[q.id] = _answer("none", no_data=True,
                               detail="StatsBomb event data has no tracking, physiological or venue data")
    assert set(gt) == {q.id for q in QUESTIONS}
    return {q.id: gt[q.id] for q in QUESTIONS}


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

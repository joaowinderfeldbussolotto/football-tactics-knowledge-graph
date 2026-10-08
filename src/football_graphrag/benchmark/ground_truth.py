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

from football_graphrag.benchmark.questions import ALL_QUESTIONS, MATCH_ID, ORDER, Question
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


def partners_readings(team: str, cuts: dict | None = None) -> dict:
    """'Exchanged passes with the most different teammates': distinct partners
    in either direction, as passer only, or as receiver only."""
    out = {}
    for label, r in readings_product(passes=PASS_SETS, partners=("either direction", "passed to", "received from"),
                                     **({"cut": list(cuts)} if cuts else {})):
        mask = cuts[r["cut"]] if cuts else None
        if r["partners"] == "either direction":
            g = pass_network(team, "undirected", PASS_SETS[r["passes"]], mask)
            degree = dict(g.degree())
        else:
            g = pass_network(team, "directed", PASS_SETS[r["passes"]], mask)
            degree = dict(g.out_degree() if r["partners"] == "passed to" else g.in_degree())
        out[label] = leader(degree)
    return out


def receiver_readings(passer: str, cuts: dict | None = None) -> dict:
    """'The teammate who received the most passes from X'."""
    out = {}
    df = actions()
    for label, r in readings_product(passes=PASS_SETS, **({"cut": list(cuts)} if cuts else {})):
        p = df[df.acao.isin(PASS_SETS[r["passes"]]) & (df.player_name == passer) & df.receiver.notna()
               & (df.receiver_team == df.team_name)]
        if cuts:
            p = p[cuts[r["cut"]](p)]
        out[label] = leader(Counter(p.receiver))
    return out


def chains(team: str, length: int, same_possession: bool, consecutive: bool, pass_set=PASS_ACTIONS,
           first=None) -> Counter:
    """Sequences of completed passes A -> B -> C ...: after receiving, the link
    is the receiver's next pass attempt; the chain stops if it is not
    completed. same_possession: whole chain in one possession; consecutive:
    no other pass attempt, by anyone, between two linked passes. ``first``
    selects the passes that may start a chain."""
    df = actions()
    attempts = df[df.acao.isin(pass_set)].reset_index(drop=True)
    ok = (attempts.receiver.notna() & (attempts.receiver_team == attempts.team_name)
          & (attempts.receiver != attempts.player_name))
    by_passer: dict[str, list[int]] = {}
    for i, name in enumerate(attempts.player_name):
        by_passer.setdefault(name, []).append(i)
    starts = attempts.index if first is None else attempts.index[first(attempts)]
    counts: Counter = Counter()
    for i in starts:
        if attempts.team_name[i] != team or not ok[i]:
            continue
        seq, cur = [attempts.player_name[i], attempts.receiver[i]], i
        for _ in range(length - 1):
            later = [k for k in by_passer.get(attempts.receiver[cur], []) if k > cur]
            if not later or not ok[later[0]]:
                break
            nxt = later[0]
            if same_possession and attempts.possession_id[nxt] != attempts.possession_id[cur]:
                break
            if consecutive and nxt != cur + 1:
                break
            seq.append(attempts.receiver[nxt])
            cur = nxt
        else:
            counts[tuple(seq)] += 1
    return counts


def trio_readings(team: str, first=None) -> dict:
    """'The sequence of three different players, one passing to the next, that
    repeated the most'."""
    out = {}
    for label, r in readings_product(passes=PASS_SETS, possession=("same possession", "any possession"),
                                     link=("consecutive passes", "other passes between allowed")):
        c = chains(team, 2, r["possession"] == "same possession", r["link"] == "consecutive passes",
                   PASS_SETS[r["passes"]], first)
        c = Counter({s: n for s, n in c.items() if len(set(s)) == 3})
        ranked = c.most_common()
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            out[label] = tie(*[s for s, n in ranked if n == ranked[0][1]])
        else:
            out[label] = answer(ranked[0][0], ranked[0][1])
    return out


# --------------------------------------------------------------------------- graph-heavy readings

SHOT_ACTIONS = ("finalizacao", "penalti", "falta_direta")


def triangle_readings(team: str, cuts: dict | None = None) -> dict:
    """'The trio that exchanged the most passes among themselves, all three passing to each
    other': triangles of the network ranked by the passes among the three. Readings: pass
    set; any direction on each pair vs all six directions present."""
    out = {}
    for label, r in readings_product(passes=PASS_SETS, links=("each pair in some direction", "all six directions"),
                                     **({"cut": list(cuts)} if cuts else {})):
        mask = cuts[r["cut"]] if cuts else None
        d = pass_network(team, "directed", PASS_SETS[r["passes"]], mask)
        u = pass_network(team, "undirected", PASS_SETS[r["passes"]], mask)
        trios = {}
        for t in (c for c in nx.enumerate_all_cliques(u) if len(c) == 3):
            pairs = [(a, b) for a in t for b in t if a != b]
            if r["links"] == "all six directions" and not all(d.has_edge(a, b) for a, b in pairs):
                continue
            trios[tuple(sorted(t))] = sum(d[a][b]["passes"] for a, b in pairs if d.has_edge(a, b))
        out[label] = top_group(trios)
    return out


def top_group(scores: dict) -> dict:
    """The highest-scoring group of players, or a tie."""
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    if not ranked:
        return tie()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return tie(*[g for g, n in ranked if n == ranked[0][1]])
    return answer(ranked[0][0], ranked[0][1])


def link_without_readings(team: str, without: str) -> dict:
    """'If X were not on the pitch, who would be the main link': betweenness on the
    network without X, in every reading."""
    out = {}
    for label, r in readings_product(passes=PASS_SETS, direction=DIRECTIONS, weight=WEIGHTS):
        g = pass_network(team, r["direction"], PASS_SETS[r["passes"]])
        g.remove_node(without)
        out[label] = leader(betweenness(g, r["weight"]))
    return out


def isolated_without_readings(team: str, without: str) -> dict:
    """'Without X, would a teammate exchange passes with nobody? Who?': players left with
    no connection once X is removed."""
    out = {}
    for label, r in readings_product(passes=PASS_SETS):
        g = pass_network(team, "undirected", PASS_SETS[r["passes"]])
        g.remove_node(without)
        alone = sorted(n for n in g.nodes if g.degree(n) == 0)
        out[label] = answer(alone) if len(alone) == 1 else tie(*alone)
    return out


def passes_before_shots(team: str, pass_set=PASS_ACTIONS, rule: str = "receiver shoots") -> list[list[str]]:
    """For each shot of the team, the passers of the completed passes before it in the same
    possession, latest first. rule 'receiver shoots': the last pass's receiver is the shooter
    and only carries or take-ons come between; 'any pass in the possession': the last passes
    of the possession before the shot, whoever received them."""
    df = actions()
    out = []
    for shot in df[(df.team_name == team) & df.acao.isin(SHOT_ACTIONS)].itertuples():
        before = df[(df.possession_id == shot.possession_id) & (df.order < shot.order)]
        completed = before[before.acao.isin(pass_set) & before.receiver.notna() & (before.receiver_team == team)]
        if completed.empty:
            continue
        if rule == "receiver shoots":
            last = completed.iloc[-1]
            between = before[before.order > last.order]
            if last.receiver != shot.player_name or not between.acao.isin(["conducao", "drible"]).all() \
                    or not (between.player_name == shot.player_name).all():
                continue
        out.append(list(completed.player_name[::-1]))
    return out


def before_shot_readings(team: str, position: int) -> dict:
    """'Who gave the last (position 1) or second-to-last (2) pass before a shot the most'."""
    out = {}
    for label, r in readings_product(passes=PASS_SETS, rule=("receiver shoots", "any pass in the possession")):
        chains = passes_before_shots(team, PASS_SETS[r["passes"]], r["rule"])
        out[label] = leader(Counter(c[position - 1] for c in chains if len(c) >= position))
    return out


def possession_table() -> pd.DataFrame:
    """One row per possession phase of layer 0: team, start, thirds, last action, players."""
    df = actions().dropna(subset=["possession_id"])
    g = df.groupby("possession_id")
    first = g.first()
    return pd.DataFrame({
        "team": first.team_name, "period": first.period_id, "start_order": first.order,
        "start_third": first.terco, "start_column": first.zone_start // 8,
        "thirds": g.terco.agg(set), "last_action": g.acao.last(),
        "has_shot": g.acao.agg(lambda a: bool(set(a) & set(SHOT_ACTIONS))),
        "players": g.player_name.agg(set),
    })


def play_readings(team: str, start: str | None, end: str, by: str, with_player: str | None = None) -> dict:
    """Possessions ('jogadas') of a team that start deep and/or end in a shot or reach the
    final third, ranked by player or by pair. Readings: 'ended in a shot' as the last action
    or any shot in the possession; 'own field of defence' as the defensive third or the own
    half."""
    ph = possession_table()
    ph = ph[ph.team == team]
    out = {}
    starts = {"defensive third": ph.start_third == "defesa", "own half": ph.start_column < 6} if start else {"": True}
    ends = ({"last action is a shot": ph.last_action.isin(SHOT_ACTIONS), "a shot in the possession": ph.has_shot}
            if end == "shot" else {"reaches the attacking third": ph.thirds.map(lambda t: "ataque" in t)})
    for (s_label, s_mask), (e_label, e_mask) in itertools.product(starts.items(), ends.items()):
        sel = ph[s_mask & e_mask] if start else ph[e_mask]
        if with_player:
            sel = sel[sel.players.map(lambda p: with_player in p)]
        counts = Counter()
        for players in sel.players:
            if by == "player":
                counts.update(players)
            elif by == "partner":
                counts.update(p for p in players if p != with_player)
            else:
                counts.update(itertools.combinations(sorted(players), 2))
        label = " / ".join(x for x in (s_label, e_label) if x)
        out[label] = top_group({k if isinstance(k, tuple) else (k,): v for k, v in counts.items()})
    return out


def substitution_cuts(player: str) -> dict:
    """'After X left': from the substitution event in the raw JSON, or after X's last action."""
    df = actions()
    last = int(df[df.player_name == player].order.max())
    sub = next(e for e in raw_events() if _type(e) == "Substitution" and _player(e) == player)
    sub_time = (sub["period"], sub["minute"] * 60 + sub["second"])
    start_min = {1: 0, 2: 45, 3: 90, 4: 105}
    later = df[(df.period_id > sub_time[0]) | ((df.period_id == sub_time[0])
               & (df.time_seconds >= sub_time[1] - start_min[sub_time[0]] * 60))]
    return {"after the substitution (raw JSON)": after(int(later.order.min()), True),
            "after the player's last action": after(last, False)}


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


def f05() -> dict:
    shots = [e for e in raw_events() if _type(e) == "Shot" and e["team"]["name"] == "France"]
    open_play = [e for e in shots if e["shot"]["type"]["name"] != "Penalty"]
    df = actions()
    l0 = df[(df.team_name == "France") & (df.grupo_acao == "finalizacao")]
    return {"raw JSON / every shot": answer([_player(shots[-1])]),
            "raw JSON / penalties excluded": answer([_player(open_play[-1])]),
            "layer 0": answer([l0.player_name.iloc[-1]])}


def f06() -> dict:
    cards = [e for e in raw_events() if e.get("bad_behaviour", {}).get("card", {}).get("name") == "Yellow Card"]
    return {"raw JSON (Bad Behaviour card)": answer([_player(e) for e in cards])}


def a07() -> dict:
    raw = Counter(_player(e) for e in raw_events() if _type(e) == "Foul Committed" and e["period"] == 2)
    df = actions()
    l0 = Counter(df[(df.period_id == 2) & (df.acao == "falta_cometida")].player_name)
    return {"raw JSON": leader(raw), "layer 0": leader(l0)}


def a08() -> dict:
    raw = Counter(_player(e) for e in raw_events() if _type(e) == "Dribble" and e["period"] >= 3
                  and e["dribble"]["outcome"]["name"] == "Complete")
    df = actions()
    l0 = Counter(df[periods(3, 4)(df) & (df.acao == "drible") & df.sucesso].player_name)
    return {"raw JSON": leader(raw), "layer 0": leader(l0)}


def a09() -> dict:
    raw = Counter(_player(e) for e in raw_events() if _type(e) == "Interception" and e["period"] == 1)
    df = actions()
    l0 = Counter(df[(df.period_id == 1) & (df.acao == "interceptacao")].player_name)
    return {"raw JSON (every interception)": leader(raw), "layer 0 (successful only)": leader(l0)}


def n06() -> dict:
    return partners_readings("Argentina")


def n07() -> dict:
    return partners_readings("France")


def n08() -> dict:
    return receiver_readings("Lionel Andrés Messi Cuccittini")


def n09() -> dict:
    return trio_readings("France")


def n10() -> dict:
    return trio_readings("Argentina")


def s05() -> dict:
    return isolating_player_readings("Argentina", {"extra time": periods(3, 4)})


def s06() -> dict:
    return receiver_readings("Enzo Fernandez", {"2nd half": periods(2)})


def s07() -> dict:
    return trio_readings("Argentina", periods(3, 4))


def s08() -> dict:
    return partners_readings("France", {"1st half": periods(1)})


def s09() -> dict:
    return partners_readings("Argentina", {"extra time": periods(3, 4)})


# --------------------------------------------------------------------------- graph-heavy questions

ARG, FRA = "Argentina", "France"
MESSI, ENZO, OTAMENDI = "Lionel Andrés Messi Cuccittini", "Enzo Fernandez", "Nicolás Hernán Otamendi"
DI_MARIA, MBAPPE, DEMBELE = "Ángel Fabián Di María Hernández", "Kylian Mbappé Lottin", "Ousmane Dembélé"


def passers_to_readings(receiver: str, cuts: dict | None = None) -> dict:
    """'The teammate who passed the most to X'."""
    out = {}
    df = actions()
    for label, r in readings_product(passes=PASS_SETS, **({"cut": list(cuts)} if cuts else {})):
        p = df[df.acao.isin(PASS_SETS[r["passes"]]) & (df.receiver == receiver) & (df.receiver_team == df.team_name)]
        if cuts:
            p = p[cuts[r["cut"]](p)]
        out[label] = leader(Counter(p.player_name))
    return out


def shooter_after_pass_readings(team: str) -> dict:
    """'Who most often shot right after receiving a pass': the shooter is the receiver of the
    last completed pass of the possession; with or without requiring that only his carries
    and take-ons come between."""
    df = actions()
    out = {}
    for label, r in readings_product(passes=PASS_SETS, between=("anything", "only his carries and take-ons")):
        counts = Counter()
        for shot in df[(df.team_name == team) & df.acao.isin(SHOT_ACTIONS)].itertuples():
            before = df[(df.possession_id == shot.possession_id) & (df.order < shot.order)]
            done = before[before.acao.isin(PASS_SETS[r["passes"]]) & before.receiver.notna()
                          & (before.receiver_team == team)]
            if done.empty or done.iloc[-1].receiver != shot.player_name:
                continue
            gap = before[before.order > done.iloc[-1].order]
            if r["between"] != "anything" and not (gap.acao.isin(["conducao", "drible"]).all()
                                                   and (gap.player_name == shot.player_name).all()):
                continue
            counts[shot.player_name] += 1
        out[label] = leader(counts)
    return out


def t01() -> dict: return triangle_readings(ARG, {"1st half": periods(1)})
def t02() -> dict: return triangle_readings(FRA)
def t03() -> dict: return triangle_readings(ARG, {"2nd half": periods(2)})
def t04() -> dict: return triangle_readings(FRA, {"1st half": periods(1)})
def t05() -> dict: return triangle_readings(ARG, {"extra time": periods(3, 4)})
def t06() -> dict: return isolating_player_readings(FRA, {"extra time": periods(3, 4)})
def t07() -> dict: return triangle_readings(FRA, {"extra time": periods(3, 4)})
def c01() -> dict: return link_without_readings(ARG, ENZO)
def c02() -> dict: return isolated_without_readings(ARG, OTAMENDI)
def c03() -> dict: return link_without_readings(ARG, MESSI)
def c04() -> dict: return link_without_readings(FRA, "Raphaël Varane")
def c05() -> dict: return link_without_readings(FRA, "Jules Koundé")
def q01() -> dict: return shooter_after_pass_readings(ARG)
def q02() -> dict: return before_shot_readings(ARG, 1)
def q03() -> dict: return before_shot_readings(ARG, 2)
def q04() -> dict: return shooter_after_pass_readings(FRA)
def p01() -> dict: return play_readings(ARG, None, "attacking", "pair")
def p02() -> dict: return play_readings(ARG, "deep", "shot", "player")
def p03() -> dict: return play_readings(ARG, None, "shot", "player")
def p04() -> dict: return play_readings(FRA, None, "shot", "player")
def p05() -> dict: return play_readings(ARG, None, "shot", "partner", MESSI)
def p06() -> dict: return play_readings(FRA, None, "shot", "partner", MBAPPE)
def p07() -> dict: return play_readings(FRA, None, "attacking", "pair")
def b01() -> dict: return triangle_readings(ARG, substitution_cuts(DI_MARIA))
def b02() -> dict: return passers_to_readings(MESSI, substitution_cuts(DI_MARIA))
def b03() -> dict: return passers_to_readings(MBAPPE, substitution_cuts(DEMBELE))
def b04() -> dict: return triangle_readings(FRA, substitution_cuts(DEMBELE))
def b05() -> dict: return receiver_readings(MBAPPE, substitution_cuts(DEMBELE))
def b06() -> dict: return pair_readings(FRA, substitution_cuts(DEMBELE))
def b07() -> dict: return receiver_readings(MESSI, substitution_cuts(DI_MARIA))


def _possessions_by(team: str, masks: dict, by: str = "player", value_of: str | None = None) -> dict:
    out = {}
    ph = possession_table()
    for label, mask in masks.items():
        sel = ph[(ph.team == team) & mask(ph)]
        if value_of:
            out[label] = answer(value=int(sum(value_of in p for p in sel.players)))
            continue
        counts = Counter()
        for players in sel.players:
            counts.update(players)
        out[label] = leader(counts)
    return out


def p08() -> dict:
    reach = lambda ph: ph.thirds.map(lambda t: "ataque" in t) & (ph.period == 2)
    return _possessions_by(FRA, {"defensive third": lambda ph: (ph.start_third == "defesa") & reach(ph),
                                 "own half": lambda ph: (ph.start_column < 6) & reach(ph)})


def p09() -> dict:
    et = lambda ph: ph.period.isin([3, 4])
    return _possessions_by(FRA, {"last action is a shot": lambda ph: ph.last_action.isin(SHOT_ACTIONS) & et(ph),
                                 "a shot in the possession": lambda ph: ph.has_shot & et(ph)}, value_of=MBAPPE)


def p10() -> dict:
    df = actions()
    goals = df[df.gol & (df.team_name == ARG)]
    open_play = set(goals[goals.acao != "penalti"].possession_id)
    return _possessions_by(ARG, {"every goal": lambda ph: ph.index.isin(set(goals.possession_id)),
                                 "penalty goals left out": lambda ph: ph.index.isin(open_play)})


def b08() -> dict:
    sub = next(e for e in raw_events() if _type(e) == "Substitution"
               and e["substitution"]["replacement"]["name"] == "Randal Kolo Muani")
    cuts = substitution_cuts(_player(sub))
    out = {}
    for label, r in readings_product(passes=PASS_SETS, cut=list(cuts),
                                     direction=("both directions", "to Mbappé", "from Mbappé")):
        p = team_passes(FRA, PASS_SETS[r["passes"]], cuts[r["cut"]])
        to, frm = Counter(p[p.receiver == MBAPPE].player_name), Counter(p[p.player_name == MBAPPE].receiver)
        out[label] = leader({"both directions": to + frm, "to Mbappé": to, "from Mbappé": frm}[r["direction"]])
    return out


def b09() -> dict:
    cuts = substitution_cuts(DI_MARIA)
    out = {}
    for label, r in readings_product(passes=PASS_SETS, cut=list(cuts)):
        p = team_passes(ARG, PASS_SETS[r["passes"]], cuts[r["cut"]])
        out[label] = leader(Counter(p.receiver))
    return out


ANSWERS = {name: fn for name, fn in globals().items() if callable(fn) and name[:1] in ORDER
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

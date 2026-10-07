"""The seven primitive tools against the layer 0 Parquet (an independent path).

Counts come from pandas and networks from networkx, never from Neo4j: if a
tool and its reference agree, both are right.
"""

import networkx as nx
import pandas as pd
import pytest

from football_graphrag.benchmark import tools
from tests.conftest import requires_data, requires_neo4j

pytestmark = [requires_neo4j, requires_data]


@pytest.fixture(scope="module")
def tb():
    from football_graphrag.config import get_settings
    from football_graphrag.graph import db

    driver = db.make_driver(get_settings())
    box = tools.Toolbox(driver)
    yield box
    box.close()
    driver.close()


@pytest.fixture(scope="module")
def df():
    from football_graphrag.config import get_settings

    actions = pd.read_parquet(get_settings().processed_dir / "3869685.parquet")
    # Continuous second: each period starts where the previous one's last action was.
    ends = actions.groupby("period_id").time_seconds.max()
    offset = ends.cumsum().shift(fill_value=0.0)
    actions["second"] = actions.time_seconds + actions.period_id.map(offset)
    known = actions.dropna(subset=["player_id"])
    names = known.groupby("player_id").player_name.first()
    teams = known.groupby("player_id").team_name.first()
    rec = actions.receiver_player_id
    actions["receiver"] = rec.map(lambda r: names.get(int(r)) if pd.notna(r) else None)
    actions["receiver_team"] = rec.map(lambda r: teams.get(int(r)) if pd.notna(r) else None)
    return actions.sort_values("action_id").reset_index(drop=True)


def completed_passes(df, team):
    p = df[df.acao.isin(tools.PASS_ACTIONS) & df.receiver.notna()]
    return p[(p.team_name == team) & (p.receiver_team == team) & (p.receiver != p.player_name)]


def as_dict(rows, key="player", value="count"):
    return {r[key]: r[value] for r in rows}


# --------------------------------------------------------------------------- actions

def test_list_players_matches_the_parquet(tb, df):
    players = tb.list_players("França")
    assert {p["player"] for p in players} == set(df[df.team_name == "France"].player_name.dropna())
    assert all(p["team"] == "France" and p["position"] for p in players)
    assert len(tb.list_players()) == df.player_name.nunique()


def test_query_actions_counts_and_groups(tb, df):
    tackles = df[(df.acao == "desarme") & df.sucesso].player_name.value_counts().to_dict()
    got = tb.query_actions({"action": "desarme", "success": True}, ["player"], top=100)
    assert as_dict(got) == tackles
    assert tb.query_actions() == [{"count": len(df)}]
    by_team_action = df.groupby(["team_name", "acao"]).size()
    got = tb.query_actions(None, ["team", "action"], top=100)
    assert {(r["team"], r["action"]): r["count"] for r in got} == by_team_action.to_dict()
    # results come largest first
    assert [r["count"] for r in got] == sorted((r["count"] for r in got), reverse=True)


def test_query_actions_receiver_and_xt_sum(tb, df):
    p = completed_passes(df, "Argentina")
    got = tb.query_actions({"team": "Argentina", "action": list(tools.PASS_ACTIONS)}, ["receiver"], top=100)
    received = {k: v for k, v in as_dict(got, "receiver").items() if k is not None}
    assert received == p.receiver.value_counts().to_dict()
    xt = tb.query_actions({"team": "France"}, [], metric="xt_sum")[0]["xt_sum"]
    assert xt == pytest.approx(df[df.team_name == "France"].xt_value.sum(), abs=1e-3)


@pytest.mark.parametrize("filters, mask", [
    ({"period": 3}, lambda d: d.period_id == 3),
    ({"third": "attacking", "team": "Argentina"}, lambda d: (d.terco == "ataque") & (d.team_name == "Argentina")),
    ({"corridor": "left", "success": False}, lambda d: (d.corredor == "esquerda") & ~d.sucesso),
    ({"goal": True}, lambda d: d.gol),
    ({"yellow_card": True}, lambda d: d.cartao_amarelo),
    ({"player": "Messi", "action": ["finalizacao", "penalti"]},
     lambda d: (d.player_name == "Lionel Andrés Messi Cuccittini") & d.acao.isin(["finalizacao", "penalti"])),
])
def test_filters(tb, df, filters, mask):
    assert tb.query_actions(filters)[0]["count"] == int(mask(df).sum())


def test_basic_facts(tb):
    assert tb.query_actions({"goal": True})[0]["count"] == 6
    assert tb.query_actions({"yellow_card": True})[0]["count"] == 7
    assists = tb.list_actions({"assist": True})["actions"]
    assert [(a["player"], a["receiver"]) for a in assists] == [
        ("Alexis Mac Allister", "Ángel Fabián Di María Hernández"),
        ("Marcus Thuram", "Kylian Mbappé Lottin"),
    ]


def test_time_filter_crosses_periods(tb, df):
    # A two-minute window around the start of extra time: the end of the 2nd
    # half and the start of the 1st half of extra time.
    start_et = df[df.period_id == 3].second.min()
    window = {"second_from": start_et - 60, "second_to": start_et + 60}
    expected = df[(df.second >= window["second_from"]) & (df.second <= window["second_to"])]
    assert set(expected.period_id) == {2, 3}
    got = tb.list_actions(window, limit=100)
    assert got["total"] == len(expected)
    seconds = [a["second"] for a in got["actions"]]
    assert seconds == sorted(seconds)
    assert {a["period"] for a in got["actions"]} == {2, 3}


def test_list_actions_is_in_match_order_with_limit(tb, df):
    got = tb.list_actions({"team": "France", "action": "falta_cometida"}, limit=3)
    assert got["total"] == int(((df.team_name == "France") & (df.acao == "falta_cometida")).sum())
    assert got["shown"] == 3
    first = df[(df.team_name == "France") & (df.acao == "falta_cometida")].sort_values(["period_id", "time_seconds"])
    assert [a["player"] for a in got["actions"]] == first.player_name.head(3).tolist()


def test_bad_arguments_raise_tool_errors(tb):
    with pytest.raises(tools.ToolError, match="ambiguous"):
        tb.query_actions({"player": "Martínez"})
    with pytest.raises(tools.ToolError, match="unknown team"):
        tb.list_players("Brasil")
    with pytest.raises(tools.ToolError, match="network_id"):
        tb.network_metric("net99", "degree")


# --------------------------------------------------------------------------- pass network

def reference_network(df, team, mask=None):
    p = completed_passes(df, team)
    if mask is not None:
        p = p[mask(p)]
    agg = p.groupby(["player_name", "receiver"]).agg(n=("action_id", "size"), xt=("xt_value", "sum")).reset_index()
    directed, undirected = nx.DiGraph(), nx.Graph()
    for r in agg.itertuples():
        directed.add_edge(r.player_name, r.receiver, n=r.n, xt=r.xt)
        old = undirected.get_edge_data(r.player_name, r.receiver, {"n": 0, "xt": 0.0})
        undirected.add_edge(r.player_name, r.receiver, n=old["n"] + r.n, xt=old["xt"] + r.xt)
    for g in (directed, undirected):
        for _, _, e in g.edges(data=True):
            e["cost_passes"], e["cost_xt"] = 1 / e["n"], 1 / (1 + e["xt"])
    return directed, undirected, len(p)


def test_pass_network_summary_and_edges(tb, df):
    net = tb.pass_network("Argentina")
    directed, _, n_passes = reference_network(df, "Argentina")
    assert net["passes"] == n_passes
    assert net["connections"] == directed.number_of_edges()
    assert net["players"] == directed.number_of_nodes()
    edges = tb.network_edges(net["network_id"], top=100)["edges"]
    assert len(edges) == 100
    for e in edges:
        assert directed[e["passer"]][e["receiver"]]["n"] == e["passes"]
    assert edges[0]["passes"] == max(d["n"] for _, _, d in directed.edges(data=True))
    messi = tb.network_edges(net["network_id"], player="Messi", top=100)["edges"]
    assert all("Lionel Andrés Messi Cuccittini" in (e["passer"], e["receiver"]) for e in messi)


@pytest.mark.parametrize("weight, nx_weight", [("none", None), ("passes", "cost_passes"), ("xt", "cost_xt")])
@pytest.mark.parametrize("direction", ["directed", "undirected"])
def test_betweenness_in_every_weight_and_direction(tb, df, weight, nx_weight, direction):
    net = tb.pass_network("France")
    directed, undirected, _ = reference_network(df, "France")
    graph = directed if direction == "directed" else undirected
    expected = nx.betweenness_centrality(graph, weight=nx_weight, normalized=False)
    got = tb.network_metric(net["network_id"], "betweenness", weight, direction, top=100)["ranking"]
    assert as_dict(got, value="score") == pytest.approx(expected, abs=1e-3)


@pytest.mark.parametrize("weight, nx_weight", [("none", None), ("passes", "n")])
def test_degree_and_pagerank(tb, df, weight, nx_weight):
    net = tb.pass_network("Argentina")
    directed, undirected, _ = reference_network(df, "Argentina")
    got = {r["player"]: r for r in tb.network_metric(net["network_id"], "degree", weight, "directed", 100)["ranking"]}
    out_deg = dict(directed.out_degree(weight=nx_weight))
    assert {p: r["outgoing"] for p, r in got.items()} == pytest.approx(out_deg)
    und = tb.network_metric(net["network_id"], "degree", weight, "undirected", 100)["ranking"]
    assert as_dict(und, value="score") == pytest.approx(dict(undirected.degree(weight=nx_weight)))
    pr = tb.network_metric(net["network_id"], "pagerank", weight, "directed", 3)["ranking"]
    ref = nx.pagerank(directed, weight=nx_weight)
    assert [r["player"] for r in pr] == sorted(ref, key=ref.get, reverse=True)[:3]


def test_bridges_articulation_points_and_communities(tb, df):
    net = tb.pass_network("Argentina")
    _, undirected, _ = reference_network(df, "Argentina")
    got = tb.network_metric(net["network_id"], "bridges")["bridges"]
    assert got == sorted(sorted(b) for b in nx.bridges(undirected))
    got = tb.network_metric(net["network_id"], "articulation_points")["articulation_points"]
    assert got == sorted(nx.articulation_points(undirected))
    groups = tb.network_metric(net["network_id"], "communities", "passes")["communities"]
    assert sorted(p for g in groups for p in g) == sorted(undirected.nodes)


def test_pass_network_with_filters(tb, df):
    net = tb.pass_network("France", {"period": 2, "third": "attacking"})
    _, _, n_passes = reference_network(df, "France", lambda p: (p.period_id == 2) & (p.terco == "ataque"))
    assert net["passes"] == n_passes


# --------------------------------------------------------------------------- pass chains

def reference_chains(df, team, length, same_possession, consecutive, first=None):
    """Brute force over the Parquet: the receiver's next pass attempt continues the chain."""
    attempts = df[df.acao.isin(tools.PASS_ACTIONS)].reset_index(drop=True)
    ok = (attempts.receiver.notna() & (attempts.receiver_team == attempts.team_name)
          & (attempts.receiver != attempts.player_name))
    counts = {}
    for i in attempts.index:
        p = attempts.loc[i]
        if p.team_name != team or not ok[i] or (first is not None and not first(p)):
            continue
        seq, cur = [p.player_name, p.receiver], i
        for _ in range(length - 1):
            later = attempts[(attempts.index > cur) & (attempts.player_name == attempts.loc[cur, "receiver"])]
            if later.empty:
                break
            nxt = later.index[0]
            if not ok[nxt]:
                break
            if same_possession and attempts.loc[nxt, "possession_id"] != attempts.loc[cur, "possession_id"]:
                break
            if consecutive and nxt != cur + 1:
                break
            seq.append(attempts.loc[nxt, "receiver"])
            cur = nxt
        else:
            counts[tuple(seq)] = counts.get(tuple(seq), 0) + 1
    return counts


@pytest.mark.parametrize("same_possession, consecutive", [(True, True), (True, False), (False, False)])
def test_pass_paths_match_brute_force(tb, df, same_possession, consecutive):
    expected = reference_chains(df, "France", 2, same_possession, consecutive)
    got = tb.pass_paths("France", 2, same_possession, consecutive, top=100)
    assert got["total_chains"] == sum(expected.values())
    assert got["distinct_sequences"] == len(expected)
    for s in got["sequences"]:
        assert expected[tuple(s["players"])] == s["count"]


def test_pass_paths_longer_chains_and_filters(tb, df):
    expected = reference_chains(df, "Argentina", 3, True, False, first=lambda p: p.period_id == 1)
    got = tb.pass_paths("Argentina", 3, True, False, {"period": 1}, top=100)
    assert got["total_chains"] == sum(expected.values())
    assert all(len(s["players"]) == 4 for s in got["sequences"])


def test_the_second_shown_works_as_a_filter_boundary(tb, df):
    # The second list_actions shows, fed back as a time filter, keeps the
    # action itself on both sides of the window (approved fix after the freeze).
    for period in (2, 3, 4):
        first = tb.list_actions({"period": period}, limit=1)["actions"][0]
        same = tb.list_actions({"second_from": first["second"], "second_to": first["second"]})["actions"]
        assert any(a["player"] == first["player"] and a["action"] == first["action"] for a in same)


def test_period_takes_a_list(tb, df):
    both = tb.query_actions({"period": [3, 4]})[0]["count"]
    assert both == int(df.period_id.isin([3, 4]).sum())
    net = tb.pass_network("France", {"period": [3, 4]})
    _, _, n_passes = reference_network(df, "France", lambda p: p.period_id.isin([3, 4]))
    assert net["passes"] == n_passes


def test_network_results_repeat_team_and_filters(tb):
    net = tb.pass_network("Argentina", {"period": 2, "team": "France"})
    assert net["team"] == "Argentina" and net["filters"] == {"period": 2}
    edges = tb.network_edges(net["network_id"], top=1)
    metric = tb.network_metric(net["network_id"], "degree")
    assert edges["filters"] == metric["filters"] == {"period": 2}
    assert edges["team"] == metric["team"] == "Argentina"


def test_list_actions_shows_the_score_before_each_action(tb, df):
    goals = tb.list_actions({"goal": True})["actions"]
    assert [g["score"] for g in goals] == [
        "Argentina 0-0 France", "Argentina 1-0 France", "Argentina 2-0 France",
        "Argentina 2-1 France", "Argentina 2-2 France", "Argentina 3-2 France",
    ]
    # every action of the match against the Parquet: goals strictly before it
    rows = tb.list_actions({"team": "France", "action": "falta_cometida"}, limit=100)["actions"]
    scored = df[df.gol].sort_values(["period_id", "time_seconds", "action_id"])
    for r in rows:
        before = scored[scored.second < r["second"] - 1e-6]
        arg, fra = (before.team_name == "Argentina").sum(), (before.team_name == "France").sum()
        assert r["score"] == f"Argentina {arg}-{fra} France"

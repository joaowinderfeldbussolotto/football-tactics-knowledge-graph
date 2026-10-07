"""Graph tools of the ``graph_tools`` arm.

Each tool runs a fixed, parameterized Cypher query: the LLM never writes
Cypher. Tools are generic (none is shaped after a question) and return
rankings and data, not finished answers.

They never read the ``PadraoTatico`` nodes of layer 2: that would hand the
arm the answer already computed. The structural tools compute on the fly,
using the same GDS projections as layer 2 (``graph/projections.py``).

Every function here takes the Neo4j driver and returns plain JSON-able data,
so it can be tested and called without an LLM.
"""

import itertools
import uuid

from neo4j import Driver

from football_graphrag.benchmark.questions import MATCH_ID
from football_graphrag.benchmark.scoring import canonical_name, normalize
from football_graphrag.graph import projections

MAX_ROWS = 100
MAX_TOP = 30

TEAMS = {"argentina": "Argentina", "france": "France", "franca": "France"}

PLAYER_STATS = (
    "toques", "passes_tentados", "passes_certos", "precisao_passe_pct", "passes_progressivos",
    "cruzamentos_tentados", "cruzamentos_certos", "conducoes", "dribles_tentados", "dribles_certos",
    "desarmes_tentados", "desarmes_certos", "interceptacoes", "cortes", "faltas_cometidas",
    "cartoes_amarelos", "finalizacoes", "finalizacoes_no_gol", "gols", "gols_de_penalti",
    "assistencias", "defesas_do_goleiro", "erros_de_dominio", "pressoes_feitas",
    "pressoes_sofridas", "xt_total", "vaep_total",
)

# What each stats field means. Shown to the graph_tools arm (stat_ranking
# description) AND to the stats_in_prompt arm (table header): both arms read
# the same numbers, so both get the same explanation of them.
STAT_GLOSSARY = {
    "toques": "on-ball actions of any type",
    "acoes": "on-ball actions of any type (team)",
    "passes_tentados": "passes attempted, including set pieces (throw-ins, goal kicks, free kicks, corners)",
    "passes_certos": "completed passes (same scope as passes_tentados)",
    "precisao_passe_pct": "passes_certos / passes_tentados, in %",
    "passes_progressivos": "completed passes that moved the ball substantially closer to the opponent's goal (Wyscout definition)",
    "cruzamentos_tentados": "crosses attempted",
    "cruzamentos_certos": "crosses completed",
    "conducoes": "carries (moving with the ball)",
    "dribles_tentados": "take-ons attempted (trying to beat an opponent)",
    "dribles_certos": "take-ons completed",
    "desarmes_tentados": "tackles attempted",
    "desarmes_certos": "tackles won",
    "interceptacoes": "interceptions",
    "cortes": "clearances",
    "faltas_cometidas": "fouls committed",
    "cartoes_amarelos": "yellow cards (from fouls or not)",
    "finalizacoes": "shots, penalties included",
    "finalizacoes_no_gol": "shots on target (saved or scored)",
    "gols": "goals (penalty shootout excluded)",
    "gols_de_penalti": "goals from penalties",
    "assistencias": "passes that set up a goal",
    "defesas_do_goleiro": "goalkeeper saves",
    "erros_de_dominio": "miscontrols",
    "pressoes_feitas": "pressures applied on an opponent with the ball",
    "pressoes_sofridas": "pressures received from opponents",
    "xt_total": "expected threat (xT) added by the player's actions",
    "vaep_total": "VAEP value of the player's actions",
    "acoes_no_terco_final": "actions in the attacking third (team)",
    "posse_pct": "ball possession by time, in % (team)",
    "ppda_1o_tempo": "opponent passes per defensive action, 1st half; lower = more pressing (team)",
    "ppda_2o_tempo": "same, 2nd half (team)",
    "field_tilt_pct": "share of the two teams' attacking-third actions, in % (team)",
}


def glossary(fields) -> str:
    return "\n".join(f"- {f}: {STAT_GLOSSARY[f]}" for f in fields if f in STAT_GLOSSARY)


# event_type -> filter on the REALIZOU action log (layer 1).
EVENT_FILTERS = {
    "goal": "r.gol",
    "yellow_card": "r.cartao_amarelo",
    "shot": "r.grupo_acao = 'finalizacao'",
    "foul": "r.acao = 'falta_cometida'",
    "tackle": "r.acao = 'desarme'",
    "interception": "r.acao = 'interceptacao'",
    "dribble": "r.acao = 'drible'",
    "clearance": "r.acao = 'corte'",
    "keeper_save": "r.acao = 'defesa_do_goleiro'",
}
EVENT_TYPES = (*EVENT_FILTERS, "assist")

_HIDDEN = {"uid", "match_id", "player_id", "team_id"}


class ToolError(ValueError):
    """Bad argument; the message goes back to the model so it can retry."""


def _rows(driver: Driver, query: str, **params) -> list[dict]:
    with driver.session() as session:
        return session.run(query, m=MATCH_ID, **params).data()


def resolve_team(team: str | None) -> str | None:
    if team is None or not str(team).strip():
        return None
    try:
        return TEAMS[normalize(team)]
    except KeyError:
        raise ToolError(f"unknown team {team!r}; use 'Argentina' or 'France'") from None


def resolve_player(driver: Driver, name: str) -> str:
    """Exact name in the graph, from a full name, nickname or unique surname."""
    names = [r["nome"] for r in _rows(driver, "MATCH (e:EstatisticaJogador {match_id: $m}) RETURN e.nome AS nome")]
    wanted = canonical_name(name)
    if wanted in names:
        return wanted
    matches = [n for n in names if normalize(name) in normalize(n)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ToolError(f"{name!r} is ambiguous: {matches}")
    raise ToolError(f"no player matches {name!r}; call list_players to see the names")


def _graph_name(kind: str) -> str:
    """Unique GDS projection name: the model may call the same tool in parallel."""
    return f"tool_{kind}_{uuid.uuid4().hex[:8]}"


def _clean(props: dict) -> dict:
    return {k: v for k, v in sorted(props.items()) if k not in _HIDDEN}


# --------------------------------------------------------------------------- stats (layer 1b)

def list_players(driver: Driver, team: str) -> list[dict]:
    team = resolve_team(team)
    return _rows(driver, """MATCH (e:EstatisticaJogador {match_id: $m, time: $team})
                            RETURN e.nome AS player, e.posicao AS position, e.toques AS touches
                            ORDER BY touches DESC""", team=team)


def player_stats(driver: Driver, name: str) -> dict:
    player = resolve_player(driver, name)
    rows = _rows(driver, "MATCH (e:EstatisticaJogador {match_id: $m, nome: $n}) RETURN properties(e) AS p", n=player)
    return _clean(rows[0]["p"])


def team_stats(driver: Driver, team: str) -> dict:
    team = resolve_team(team)
    rows = _rows(driver, "MATCH (e:EstatisticaTime {match_id: $m, nome: $t}) RETURN properties(e) AS p", t=team)
    return _clean(rows[0]["p"])


def stat_ranking(driver: Driver, stat: str, team: str | None = None, top: int = 5) -> list[dict]:
    if stat not in PLAYER_STATS:
        raise ToolError(f"unknown stat {stat!r}; valid: {', '.join(PLAYER_STATS)}")
    team = resolve_team(team)
    top = max(1, min(int(top), MAX_TOP))
    # The field name is interpolated only after the whitelist check above.
    return _rows(driver, f"""MATCH (e:EstatisticaJogador {{match_id: $m}})
                             WHERE $team IS NULL OR e.time = $team
                             RETURN e.nome AS player, e.time AS team, e.{stat} AS value
                             ORDER BY value DESC, player LIMIT $top""", team=team, top=top)


# --------------------------------------------------------------------------- events (layer 1)

def events(driver: Driver, event_type: str, team: str | None = None) -> list[dict]:
    team = resolve_team(team)
    if event_type == "assist":
        return _rows(driver, """MATCH (a:Jogador)-[s:DEU_ASSISTENCIA {match_id: $m}]->(b:Jogador)
                                WHERE $team IS NULL OR a.time = $team
                                RETURN s.minuto AS minute, s.periodo AS period, a.time AS team,
                                       a.nome AS assister, b.nome AS scorer
                                ORDER BY period, minute""", team=team)
    if event_type not in EVENT_FILTERS:
        raise ToolError(f"unknown event_type {event_type!r}; valid: {', '.join(EVENT_TYPES)}")
    return _rows(driver, f"""MATCH (j:Jogador)-[r:REALIZOU {{match_id: $m}}]->()
                             WHERE {EVENT_FILTERS[event_type]} AND ($team IS NULL OR j.time = $team)
                             RETURN r.minuto AS minute, r.periodo AS period, j.time AS team,
                                    j.nome AS player, r.acao AS action, r.sucesso AS success,
                                    r.desfecho AS outcome, r.gol AS goal, r.cartao_amarelo AS yellow_card
                             ORDER BY period, r.segundo LIMIT {MAX_ROWS}""", team=team)


# --------------------------------------------------------------------------- pass network (GDS, live)

def pass_network_centrality(driver: Driver, team: str, top: int = 5) -> list[dict]:
    """Betweenness on the team's pass network, weighted by cost = 1/(1+xT)."""
    team = resolve_team(team)
    top = max(1, min(int(top), MAX_TOP))
    with projections.pass_network(driver, MATCH_ID, team, name=_graph_name("bc")) as g:
        return _rows(driver, """CALL gds.betweenness.stream($g, {relationshipWeightProperty: 'cost'})
                                YIELD nodeId, score
                                RETURN gds.util.asNode(nodeId).nome AS player, score AS betweenness
                                ORDER BY betweenness DESC, player LIMIT $top""", g=g, top=top)


def three_player_sequences(driver: Driver, team: str, top: int = 5) -> list[dict]:
    """Most frequent progressive A->B->C completed-pass sequences.

    Same possession, second pass 1-3 actions after the first, three distinct
    players, ball ending in a more advanced third than it started.
    """
    team = resolve_team(team)
    top = max(1, min(int(top), MAX_TOP))
    return _rows(driver, """
        MATCH (a:Jogador)-[p1:PASSOU_PARA {match_id: $m}]->(b:Jogador)-[p2:PASSOU_PARA {match_id: $m}]->(c:Jogador)
        WHERE p1.fase_posse_id = p2.fase_posse_id
          AND p2.action_id > p1.action_id AND p2.action_id - p1.action_id <= 3
          AND a <> b AND b <> c AND a <> c
          AND (p2.zona_destino / 8) / 4 > (p1.zona_origem / 8) / 4
          AND a.time = $team
        RETURN a.nome AS a, b.nome AS b, c.nome AS c, count(*) AS occurrences,
               round(sum(p1.xt_gerado + p2.xt_gerado), 4) AS xt_total
        ORDER BY occurrences DESC, xt_total DESC LIMIT $top""", team=team, top=top)


def pass_network_bridges(driver: Driver, team: str) -> dict:
    """Bridges and Louvain communities of the undirected pass network."""
    team = resolve_team(team)
    with projections.pass_network(driver, MATCH_ID, team, name=_graph_name("br"), undirected=True) as g:
        bridges = _rows(driver, """CALL gds.bridges.stream($g) YIELD from, to
                                   RETURN gds.util.asNode(from).nome AS a, gds.util.asNode(to).nome AS b""", g=g)
        members = _rows(driver, """CALL gds.louvain.stream($g, {relationshipWeightProperty: 'n_passes'})
                                   YIELD nodeId, communityId
                                   RETURN communityId AS community, gds.util.asNode(nodeId).nome AS player
                                   ORDER BY community, player""", g=g)
    communities = [
        [m["player"] for m in group]
        for _, group in itertools.groupby(members, key=lambda m: m["community"])
    ]
    return {"bridges": bridges, "communities": communities}

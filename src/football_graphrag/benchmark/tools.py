"""Primitive graph tools of the ``graph_tools`` arm.

Seven operations with no tactical concept built in: filter and count
actions, list actions, build a pass network, compute a network metric, list
its connections and count chains of passes. The model has to combine them;
no tool is shaped after a question.

Each tool runs fixed, parameterized Cypher (and Neo4j GDS for network
metrics): the LLM never writes Cypher. The tools never read the
``PadraoTatico`` nodes of layer 2, which hold answers already computed.

``Toolbox`` holds the state of one run: the pass networks it built, kept as
edge lists. Each network metric projects its network into GDS, computes and
drops the projection. Every method returns plain
JSON-able data, so it can be tested and called without an LLM.
"""

import bisect
import uuid
from collections import Counter
from contextlib import contextmanager
from typing import Literal

from neo4j import Driver
from pydantic import BaseModel, Field

from football_graphrag.benchmark.questions import MATCH_ID
from football_graphrag.benchmark.scoring import canonical_name, normalize
from football_graphrag.ingestion.football_semantics import ACAO_POR_TIPO_SPADL

MAX_LIST = 100
MAX_TOP = 100

TEAMS = {"argentina": "Argentina", "france": "France", "franca": "France"}

# The closed action vocabulary of layer 0 (plus the dissent card it recovers
# from the raw JSON).
ACTIONS = (*ACAO_POR_TIPO_SPADL.values(), "cartao_por_reclamacao")
# The actions that are pass attempts (graph/build.py::PASS_TYPES, in Portuguese).
PASS_ACTIONS = (
    "passe", "cruzamento", "arremesso_lateral", "falta_cobrada_curta", "falta_cobrada_na_area",
    "escanteio_curto", "escanteio_na_area", "tiro_de_meta",
)
THIRDS = {"defensive": "defesa", "middle": "meio", "attacking": "ataque"}
CORRIDORS = {"left": "esquerda", "center": "centro", "right": "direita"}
# Game clock (REALIZOU.segundo) at the start of each period.
PERIOD_CLOCK_START = {1: 0, 2: 45 * 60, 3: 90 * 60, 4: 105 * 60}

Action = Literal[ACTIONS]
GroupBy = Literal["player", "receiver", "team", "action", "period", "third", "corridor"]
NetworkMetric = Literal["betweenness", "degree", "pagerank", "bridges", "articulation_points", "communities"]
Weight = Literal["none", "passes", "xt"]
Direction = Literal["directed", "undirected"]

TEAM_HELP = '"Argentina" or "France" (Portuguese names such as "França" also work).'

# --------------------------------------------------------------------------- stats glossary
# Not used by the tools any more: the stats_in_prompt arm prints it as the
# header of its tables (arms.py::stats_table).

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
    "interceptacoes": "successful interceptions",
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
    "field_tilt_pct": "this team's share of the passes both teams made in their attacking third, in % (team)",
}

_HIDDEN = {"uid", "match_id", "player_id", "team_id"}


def glossary(fields) -> str:
    return "\n".join(f"- {f}: {STAT_GLOSSARY[f]}" for f in fields if f in STAT_GLOSSARY)


# --------------------------------------------------------------------------- filters

class ActionFilters(BaseModel):
    """Which actions to include. Every field is optional; omitted fields do not filter."""

    team: str | None = Field(None, description=f"Team that performed the action: {TEAM_HELP}")
    player: str | None = Field(
        None, description='Player who performed the action: full name, nickname or a surname that is '
                          'unique in the match (e.g. "Messi"). An ambiguous name returns the candidates.')
    action: list[Action] | Action | None = Field(
        None, description=(
            "One or more action types (Portuguese labels). Passes and set pieces: passe, cruzamento "
            "(cross), arremesso_lateral (throw-in), tiro_de_meta (goal kick), escanteio_curto / "
            "escanteio_na_area (corner played short / into the box), falta_cobrada_curta / "
            "falta_cobrada_na_area (free kick played short / into the box). Shots: finalizacao, penalti, "
            "falta_direta (direct free kick). With the ball: conducao (carry), drible (take-on, trying to "
            "beat an opponent). Defending: desarme (tackle), interceptacao, corte (clearance). Others: "
            "falta_cometida (foul committed), erro_de_dominio (miscontrol), defesa_do_goleiro (save), "
            "goleiro_encaixa / goleiro_soca / goleiro_recolhe (keeper claim / punch / pick-up), "
            "cartao_por_reclamacao (booking for dissent, without a foul)."))
    success: bool | None = Field(None, description="true: successful actions only; false: failed actions only.")
    period: list[Literal[1, 2, 3, 4]] | Literal[1, 2, 3, 4] | None = Field(
        None, description="One or more periods. 1 and 2: the halves of regular time; 3 and 4: the halves "
                          "of extra time. The penalty shootout is not in the data.")
    second_from: float | None = Field(
        None, description="Start of a time window, inclusive: elapsed match time in seconds since the "
                          "kickoff, continuous across periods (breaks excluded). list_actions shows the "
                          "second of every action.")
    second_to: float | None = Field(None, description="End of the time window, inclusive, same scale as second_from.")
    third: Literal["defensive", "middle", "attacking"] | None = Field(
        None, description="Third of the pitch where the action started, seen from the acting team "
                          "(defensive: near its own goal).")
    corridor: Literal["left", "center", "right"] | None = Field(
        None, description="Corridor of the pitch where the action started, seen from the acting team "
                          "facing the opponent's goal.")
    goal: bool | None = Field(None, description="true: only actions that scored a goal.")
    yellow_card: bool | None = Field(None, description="true: only actions that led to a yellow card.")
    assist: bool | None = Field(
        None, description="true: only the passes that set up a goal (the last pass to the scorer in "
                          "the same possession).")


class ToolError(ValueError):
    """Bad argument; the message goes back to the model so it can retry."""


def resolve_team(team: str | None) -> str | None:
    if team is None or not str(team).strip():
        return None
    try:
        return TEAMS[normalize(team)]
    except KeyError:
        raise ToolError(f"unknown team {team!r}; use 'Argentina' or 'France'") from None


def _as_filters(filters) -> ActionFilters:
    if filters is None:
        return ActionFilters()
    if isinstance(filters, ActionFilters):
        return filters
    return ActionFilters.model_validate(filters)


def _top(top: int, limit: int = MAX_TOP) -> int:
    return max(1, min(int(top), limit))


# Every action of the match, with its player (j), receiver (rc, completed
# passes only) and the continuous second since kickoff.
_ACTIONS = """
MATCH (j:Jogador)-[x:REALIZOU {match_id: $m}]->()
OPTIONAL MATCH (j)-[:PASSOU_PARA {match_id: $m, action_id: x.action_id}]->(rc:Jogador)
WITH j, x, rc, x.segundo - $clock_start[toString(x.periodo)] + $clock_offset[toString(x.periodo)] AS second
"""

_GROUP_FIELDS = {
    "player": "j.nome", "receiver": "rc.nome", "team": "j.time", "action": "x.acao",
    "period": "x.periodo", "third": "x.terco", "corridor": "x.corredor",
}
_TO_ENGLISH = {**{v: k for k, v in THIRDS.items()}, **{v: k for k, v in CORRIDORS.items()}}


def _outcome(row: dict) -> str:
    parts = []
    if row.pop("gol"):
        parts.append("goal")
    if row.pop("cartao_amarelo"):
        parts.append("yellow_card")
    desfecho = row.pop("desfecho")
    if desfecho and desfecho != "gol":
        parts.append(desfecho)
    return "+".join(parts)


class Toolbox:
    """The seven tools, bound to a driver, for one run (one question)."""

    def __init__(self, driver: Driver, match_id: int = MATCH_ID):
        self.driver = driver
        self.match_id = match_id
        self.networks: dict[str, dict] = {}
        self._names: list[str] | None = None
        self._clock: dict | None = None
        self._assists: list[int] | None = None
        self._goals: list[tuple] | None = None

    # ------------------------------------------------------------------ plumbing

    def _rows(self, query: str, **params) -> list[dict]:
        with self.driver.session() as session:
            return session.run(query, m=self.match_id, **params).data()

    def _drop(self, name: str) -> None:
        self._rows("CALL gds.graph.drop($name, false) YIELD graphName RETURN graphName", name=name)

    def close(self) -> None:
        """Forget this run's networks (their GDS projections never outlive a call)."""
        self.networks.clear()

    def clock(self) -> dict:
        """Cypher parameters for the continuous second: each period starts
        where the previous one ended (its last action)."""
        if self._clock is None:
            rows = self._rows("""MATCH ()-[x:REALIZOU {match_id: $m}]->()
                                 RETURN x.periodo AS period, max(x.segundo) AS last ORDER BY period""")
            offset, start = {}, {}
            elapsed = 0.0
            for r in rows:
                start[str(r["period"])] = PERIOD_CLOCK_START[r["period"]]
                offset[str(r["period"])] = elapsed
                elapsed += r["last"] - PERIOD_CLOCK_START[r["period"]]
            self._clock = {"clock_start": start, "clock_offset": offset}
        return self._clock

    def assist_ids(self) -> list[int]:
        """action_id of each assist: the scorer's last received pass in the
        goal's possession (the rule of layer 1's DEU_ASSISTENCIA)."""
        if self._assists is None:
            rows = self._rows("""
                MATCH (a:Jogador)-[s:DEU_ASSISTENCIA {match_id: $m}]->(b:Jogador)
                MATCH (b)-[g:REALIZOU {match_id: $m, action_id: s.action_id}]->()
                MATCH (a)-[p:PASSOU_PARA {match_id: $m}]->(b)
                WHERE p.fase_posse_id = g.fase_posse_id AND p.action_id < s.action_id
                RETURN s.action_id AS goal, max(p.action_id) AS assist""")
            self._assists = [r["assist"] for r in rows]
        return self._assists

    def goals(self) -> list[tuple]:
        """(period, game clock, action_id, team) of every goal, in match order."""
        if self._goals is None:
            self._goals = [(r["period"], r["clock"], r["aid"], r["team"]) for r in self._rows("""
                MATCH (j:Jogador)-[x:REALIZOU {match_id: $m, gol: true}]->()
                RETURN x.periodo AS period, x.segundo AS clock, x.action_id AS aid, j.time AS team
                ORDER BY period, clock, aid""")]
        return self._goals

    def score_before(self, period: int, clock: float, action_id: int) -> str:
        """The score when an action starts, before it: "Argentina 2-1 France"."""
        scored = [g[3] for g in self.goals() if g[:3] < (period, clock, action_id)]
        return f"Argentina {scored.count('Argentina')}-{scored.count('France')} France"

    def player_names(self) -> list[str]:
        if self._names is None:
            self._names = [r["name"] for r in self._rows(
                "MATCH (j:Jogador)-[:REALIZOU {match_id: $m}]->() RETURN DISTINCT j.nome AS name")]
        return self._names

    def resolve_player(self, name: str) -> str:
        """Exact name in the graph, from a full name, nickname or unique surname."""
        names = self.player_names()
        wanted = canonical_name(name)
        if wanted in names:
            return wanted
        matches = [n for n in names if normalize(name) in normalize(n)]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise ToolError(f"{name!r} is ambiguous: {sorted(matches)}")
        raise ToolError(f"no player matches {name!r}; call list_players to see the names")

    def _where(self, filters) -> tuple[str, dict]:
        """Cypher conditions (on j, x, rc, second) and parameters for the filters."""
        f = _as_filters(filters)
        conds, params = [], dict(self.clock())
        if f.team:
            conds.append("j.time = $team")
            params["team"] = resolve_team(f.team)
        if f.player:
            conds.append("j.nome = $player")
            params["player"] = self.resolve_player(f.player)
        if f.action:
            conds.append("x.acao IN $actions")
            params["actions"] = [f.action] if isinstance(f.action, str) else list(f.action)
        if f.success is not None:
            conds.append("x.sucesso = $success")
            params["success"] = f.success
        if f.period is not None:
            conds.append("x.periodo IN $periods")
            params["periods"] = [f.period] if isinstance(f.period, int) else list(f.period)
        if f.second_from is not None:
            conds.append("round(second, 3) >= $second_from")
            params["second_from"] = f.second_from
        if f.second_to is not None:
            conds.append("round(second, 3) <= $second_to")
            params["second_to"] = f.second_to
        if f.third:
            conds.append("x.terco = $third")
            params["third"] = THIRDS[f.third]
        if f.corridor:
            conds.append("x.corredor = $corridor")
            params["corridor"] = CORRIDORS[f.corridor]
        if f.goal is not None:
            conds.append("x.gol = $goal")
            params["goal"] = f.goal
        if f.yellow_card is not None:
            conds.append("x.cartao_amarelo = $yellow_card")
            params["yellow_card"] = f.yellow_card
        if f.assist is not None:
            conds.append("(x.action_id IN $assist_ids) = $assist")
            params["assist_ids"] = self.assist_ids()
            params["assist"] = f.assist
        return " AND ".join(conds) or "true", params

    # ------------------------------------------------------------------ actions

    def list_players(self, team: str | None = None) -> list[dict]:
        return self._rows("""MATCH (j:Jogador)-[:REALIZOU {match_id: $m}]->()
                             WHERE $team IS NULL OR j.time = $team
                             RETURN DISTINCT j.nome AS player, j.time AS team, j.posicao_nominal AS position
                             ORDER BY team, player""", team=resolve_team(team))

    def query_actions(self, filters=None, group_by=None, metric: str = "count", top: int = 10) -> list[dict]:
        group_by = list(dict.fromkeys(group_by or []))
        unknown = [g for g in group_by if g not in _GROUP_FIELDS]
        if unknown:
            raise ToolError(f"unknown group_by {unknown}; valid: {', '.join(_GROUP_FIELDS)}")
        if metric not in ("count", "xt_sum"):
            raise ToolError("metric must be 'count' or 'xt_sum'")
        where, params = self._where(filters)
        keys = ", ".join(f"{_GROUP_FIELDS[g]} AS {g}" for g in group_by)
        value = "count(*)" if metric == "count" else "round(sum(x.xt_gerado), 4)"
        order = ", ".join(["value DESC", *group_by])
        rows = self._rows(f"""{_ACTIONS} WHERE {where}
                              RETURN {keys + ', ' if keys else ''}{value} AS value
                              ORDER BY {order} LIMIT $top""", top=_top(top), **params)
        for r in rows:
            for g in ("third", "corridor"):
                if g in r:
                    r[g] = _TO_ENGLISH.get(r[g], r[g])
            r[metric] = r.pop("value")
        return rows

    def list_actions(self, filters=None, limit: int = 20) -> dict:
        where, params = self._where(filters)
        rows = self._rows(f"""{_ACTIONS} WHERE {where}
                              RETURN x.periodo AS period, x.minuto AS minute, round(second, 3) AS second,
                                     j.time AS team, j.nome AS player, x.acao AS action,
                                     x.sucesso AS success, rc.nome AS receiver, x.terco AS third,
                                     x.corredor AS corridor, x.gol AS gol, x.cartao_amarelo AS cartao_amarelo,
                                     x.desfecho AS desfecho, x.segundo AS clock, x.action_id AS aid
                              ORDER BY period, x.segundo, x.action_id""", **params)
        shown = rows[: _top(limit, MAX_LIST)]
        for r in shown:
            r["score"] = self.score_before(r["period"], r.pop("clock"), r.pop("aid"))
            r["third"] = _TO_ENGLISH.get(r["third"], r["third"])
            r["corridor"] = _TO_ENGLISH.get(r["corridor"], r["corridor"])
            r["outcome"] = _outcome(r)
        return {"total": len(rows), "shown": len(shown), "actions": shown}

    # ------------------------------------------------------------------ pass network

    def _pass_edges(self, team: str, filters) -> list[dict]:
        """Completed passes between teammates matching the filters, per passer -> receiver."""
        f = _as_filters(filters).model_copy(update={"team": team, "success": None})
        where, params = self._where(f)
        return self._rows(f"""{_ACTIONS} WHERE {where} AND rc IS NOT NULL AND rc.time = j.time AND rc <> j
                              RETURN elementId(j) AS a_id, elementId(rc) AS b_id,
                                     j.nome AS passer, rc.nome AS receiver,
                                     count(*) AS passes, sum(x.xt_gerado) AS xt
                              ORDER BY passes DESC, xt DESC, passer, receiver""", **params)

    @contextmanager
    def _projection(self, edges: list[dict], undirected: bool):
        """A GDS projection of the edges, dropped on exit. Each projection takes
        ~100 MiB of heap however small the network, so none is kept."""
        name = f"bench_{uuid.uuid4().hex[:12]}"
        if undirected:
            pairs: dict[tuple, dict] = {}
            for e in edges:
                key = tuple(sorted((e["a_id"], e["b_id"])))
                p = pairs.setdefault(key, {"a_id": key[0], "b_id": key[1], "passes": 0, "xt": 0.0})
                p["passes"] += e["passes"]
                p["xt"] += e["xt"]
            edges = list(pairs.values())
        self._rows("""
            UNWIND $edges AS e
            MATCH (a:Jogador) WHERE elementId(a) = e.a_id
            MATCH (b:Jogador) WHERE elementId(b) = e.b_id
            WITH gds.graph.project($name, a, b, {relationshipProperties: {
                passes: toFloat(e.passes),
                xt: CASE WHEN e.xt > 0 THEN e.xt ELSE 0.0 END,
                cost_passes: 1.0 / e.passes,
                cost_xt: 1.0 / (1.0 + e.xt)
            }}, $config) AS g
            RETURN g.graphName AS name""",
                   edges=edges, name=name,
                   config={"undirectedRelationshipTypes": ["*"]} if undirected else {})
        try:
            yield name
        finally:
            self._drop(name)

    def pass_network(self, team: str, filters=None) -> dict:
        team = resolve_team(team)
        if team is None:
            raise ToolError("team is required: 'Argentina' or 'France'")
        edges = self._pass_edges(team, filters)
        if not edges:
            raise ToolError("no completed pass between teammates matches these filters")
        network_id = f"net{len(self.networks) + 1}"
        used = _as_filters(filters).model_dump(exclude_none=True, exclude={"team", "success"})
        self.networks[network_id] = {"team": team, "filters": used, "edges": edges}
        players = sorted({e["passer"] for e in edges} | {e["receiver"] for e in edges})
        return {"network_id": network_id, "team": team, "filters": used, "players": len(players),
                "player_names": players, "connections": len(edges), "passes": sum(e["passes"] for e in edges)}

    def _network(self, network_id: str) -> dict:
        try:
            return self.networks[network_id]
        except KeyError:
            raise ToolError(f"unknown network_id {network_id!r}; call pass_network first"
                            f"{' (existing: ' + ', '.join(self.networks) + ')' if self.networks else ''}") from None

    def network_metric(self, network_id: str, metric: str, weight: str = "none",
                       direction: str = "directed", top: int = 10) -> dict:
        net = self._network(network_id)
        if weight not in ("none", "passes", "xt"):
            raise ToolError("weight must be 'none', 'passes' or 'xt'")
        if direction not in ("directed", "undirected"):
            raise ToolError("direction must be 'directed' or 'undirected'")
        if metric not in ("betweenness", "degree", "pagerank", "bridges", "articulation_points", "communities"):
            raise ToolError(f"unknown metric {metric!r}; valid: betweenness, degree, pagerank, bridges, "
                            "articulation_points, communities")
        out = {"network_id": network_id, "team": net["team"], "filters": net["filters"], "metric": metric}
        undirected = direction == "undirected" or metric in ("bridges", "articulation_points", "communities")
        with self._projection(net["edges"], undirected) as graph:
            return self._metric(graph, out, metric, weight, direction, top)

    def _metric(self, graph: str, out: dict, metric: str, weight: str, direction: str, top: int) -> dict:
        if metric in ("bridges", "articulation_points"):
            out["note"] = "always unweighted and undirected"
            g = graph
            if metric == "bridges":
                rows = self._rows("""CALL gds.bridges.stream($g) YIELD from, to
                                     RETURN gds.util.asNode(from).nome AS a, gds.util.asNode(to).nome AS b""", g=g)
                out["bridges"] = sorted([sorted((r["a"], r["b"])) for r in rows])
            else:
                rows = self._rows("""CALL gds.articulationPoints.stream($g) YIELD nodeId
                                     RETURN gds.util.asNode(nodeId).nome AS player""", g=g)
                out["articulation_points"] = sorted(r["player"] for r in rows)
            return out

        out |= {"weight": weight, "direction": direction}
        strength = {"none": None, "passes": "passes", "xt": "xt"}[weight]
        if metric == "betweenness":
            cost = {"none": None, "passes": "cost_passes", "xt": "cost_xt"}[weight]
            config = {"relationshipWeightProperty": cost} if cost else {}
            rows = self._rows("""CALL gds.betweenness.stream($g, $config) YIELD nodeId, score
                                 RETURN gds.util.asNode(nodeId).nome AS player, round(score, 4) AS score
                                 ORDER BY score DESC, player LIMIT $top""", g=graph, config=config, top=_top(top))
        elif metric == "pagerank":
            config = {"relationshipWeightProperty": strength} if strength else {}
            rows = self._rows("""CALL gds.pageRank.stream($g, $config) YIELD nodeId, score
                                 RETURN gds.util.asNode(nodeId).nome AS player, round(score, 4) AS score
                                 ORDER BY score DESC, player LIMIT $top""", g=graph, config=config, top=_top(top))
        elif metric == "degree":
            config = {"relationshipWeightProperty": strength} if strength else {}
            if direction == "undirected":
                rows = self._rows("""CALL gds.degree.stream($g, $config) YIELD nodeId, score
                                     RETURN gds.util.asNode(nodeId).nome AS player, round(score, 4) AS score
                                     ORDER BY score DESC, player LIMIT $top""",
                                  g=graph, config=config, top=_top(top))
            else:
                scores: dict[str, dict] = {}
                for orientation, key in (("NATURAL", "outgoing"), ("REVERSE", "incoming")):
                    for r in self._rows("""CALL gds.degree.stream($g, $config) YIELD nodeId, score
                                           RETURN gds.util.asNode(nodeId).nome AS player, score""",
                                        g=graph, config={**config, "orientation": orientation}):
                        scores.setdefault(r["player"], {})[key] = round(r["score"], 4)
                rows = [{"player": p, "outgoing": s.get("outgoing", 0), "incoming": s.get("incoming", 0),
                         "score": round(s.get("outgoing", 0) + s.get("incoming", 0), 4)}
                        for p, s in scores.items()]
                rows = sorted(rows, key=lambda r: (-r["score"], r["player"]))[: _top(top)]
        elif metric == "communities":
            config = {"relationshipWeightProperty": strength} if strength else {}
            out |= {"direction": "undirected", "note": "always undirected; groups can vary between calls"}
            rows = self._rows("""CALL gds.louvain.stream($g, $config) YIELD nodeId, communityId
                                 RETURN communityId AS community, gds.util.asNode(nodeId).nome AS player""",
                              g=graph, config=config)
            groups: dict[int, list[str]] = {}
            for r in rows:
                groups.setdefault(r["community"], []).append(r["player"])
            out["communities"] = sorted((sorted(g) for g in groups.values()), key=lambda g: (-len(g), g))
            return out
        out["ranking"] = rows
        return out

    def network_edges(self, network_id: str, player: str | None = None, top: int = 20) -> dict:
        net = self._network(network_id)
        edges = net["edges"]
        if player:
            name = self.resolve_player(player)
            edges = [e for e in edges if name in (e["passer"], e["receiver"])]
        return {"network_id": network_id, "team": net["team"], "filters": net["filters"],
                "edges": [{"passer": e["passer"], "receiver": e["receiver"], "passes": e["passes"],
                           "xt": round(e["xt"], 4)} for e in edges[: _top(top)]]}

    # ------------------------------------------------------------------ pass chains

    def pass_paths(self, team: str, length: int = 2, same_possession: bool = True,
                   consecutive: bool = True, filters=None, top: int = 10) -> dict:
        team = resolve_team(team)
        if team is None:
            raise ToolError("team is required: 'Argentina' or 'France'")
        if not 2 <= int(length) <= 4:
            raise ToolError("length must be 2, 3 or 4 (passes in the chain)")
        length = int(length)
        f = _as_filters(filters).model_copy(update={"team": team})
        where, params = self._where(f)
        # Every pass attempt of both teams, in match order, flagged when it
        # matches the filters (filters select the first pass of a chain).
        passes = self._rows(f"""{_ACTIONS} WHERE x.acao IN $pass_actions
                                RETURN x.action_id AS id, j.nome AS passer, j.time AS team,
                                       CASE WHEN rc IS NOT NULL AND rc.time = j.time THEN rc.nome END AS receiver,
                                       x.fase_posse_id AS possession, ({where}) AS selected
                                ORDER BY x.action_id""", pass_actions=list(PASS_ACTIONS), **params)
        by_passer: dict[str, list[int]] = {}
        for i, p in enumerate(passes):
            by_passer.setdefault(p["passer"], []).append(i)

        def next_pass(i: int) -> int | None:
            """Index of the receiver's next pass attempt after pass i."""
            mine = by_passer.get(passes[i]["receiver"], [])
            k = bisect.bisect_right(mine, i)
            return mine[k] if k < len(mine) else None

        chains: Counter = Counter()
        for i, p in enumerate(passes):
            if not (p["selected"] and p["team"] == team and p["receiver"]):
                continue
            seq, cur = [p["passer"], p["receiver"]], i
            for _ in range(length - 1):
                nxt = next_pass(cur)
                if nxt is None or not passes[nxt]["receiver"]:
                    break
                if same_possession and passes[nxt]["possession"] != passes[cur]["possession"]:
                    break
                if consecutive and nxt != cur + 1:
                    break
                seq.append(passes[nxt]["receiver"])
                cur = nxt
            else:
                chains[tuple(seq)] += 1
        ranked = sorted(chains.items(), key=lambda kv: (-kv[1], kv[0]))[: _top(top)]
        return {"team": team, "filters": f.model_dump(exclude_none=True, exclude={"team"}),
                "length": length, "same_possession": same_possession, "consecutive": consecutive,
                "total_chains": sum(chains.values()), "distinct_sequences": len(chains),
                "sequences": [{"players": list(s), "count": n} for s, n in ranked]}

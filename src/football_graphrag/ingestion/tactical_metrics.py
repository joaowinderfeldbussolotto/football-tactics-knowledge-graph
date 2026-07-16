"""Métricas táticas calculadas em cima das ações SPADL já enriquecidas com xT/VAEP.

Todas as funções aqui são leitura + agregação sobre o DataFrame de ações;
nenhuma delas dispara I/O ou chamadas de LLM. Uma vez que o parquet em
`data/processed/{match_id}.parquet` é gerado, essas métricas nunca são
recalculadas — a camada de grafo (seção 6.4) só lê os valores já prontos.

Definições usadas (documentadas aqui porque são convenções, não padrões
únicos da literatura):

- **PPDA** (passes allowed per defensive action): para um time defensor,
  é o número de passes bem-sucedidos do adversário fora do terço de campo
  mais próximo do gol do defensor, dividido pelas ações defensivas
  (desarme, interceptação, falta) do defensor nessa mesma zona.
- **Field tilt**: percentual dos toques no terço de ataque que pertencem a
  um time, sobre o total de toques de ambos os times nesse terço.
- **Passe progressivo**: passe bem-sucedido que reduz em pelo menos 25% a
  distância até o centro do gol adversário.
"""

from __future__ import annotations

import math

import networkx as nx
import pandas as pd

FIELD_LENGTH = 105.0
FIELD_WIDTH = 68.0

_DEFENSIVE_ACTION_TYPES = {"tackle", "interception", "foul"}
_PASS_ACTION_TYPES = {"pass", "cross", "freekick_short", "freekick_crossed", "corner_short", "corner_crossed"}

_LEFT_CORRIDOR_Y = FIELD_WIDTH / 3
_RIGHT_CORRIDOR_Y = 2 * FIELD_WIDTH / 3


def _defensive_third_bound(ground: str) -> tuple[float, float]:
    """Retorna (x_min, x_max) do terço de campo mais próximo do próprio gol."""
    third = FIELD_LENGTH / 3
    return (0.0, third) if ground == "home" else (FIELD_LENGTH - third, FIELD_LENGTH)


def _attacking_third_bound(ground: str) -> tuple[float, float]:
    x_min, x_max = _defensive_third_bound("away" if ground == "home" else "home")
    return x_min, x_max


def compute_ppda(actions: pd.DataFrame, team_id: str, opponent_team_id: str, ground: str) -> float | None:
    """PPDA do `team_id` (o time cuja intensidade de pressão está sendo medida)."""
    def_x_min, def_x_max = _defensive_third_bound(ground)
    # Zona "fora do terço defensivo" = os outros dois terços do campo.
    pressing_zone = ~actions["start_x"].between(def_x_min, def_x_max)

    opponent_passes = actions[
        (actions["team_id"] == opponent_team_id)
        & actions["type_name"].isin(_PASS_ACTION_TYPES)
        & (actions["result_name"] == "success")
        & pressing_zone
    ]
    defensive_actions = actions[
        (actions["team_id"] == team_id) & actions["type_name"].isin(_DEFENSIVE_ACTION_TYPES) & pressing_zone
    ]

    if len(defensive_actions) == 0:
        return None
    return len(opponent_passes) / len(defensive_actions)


def compute_field_tilt(actions: pd.DataFrame, team_id: str, opponent_team_id: str, ground: str) -> float | None:
    """Percentual de toques no terço de ataque do `team_id` sobre o total (0-100)."""
    att_x_min, att_x_max = _attacking_third_bound(ground)
    opp_ground = "away" if ground == "home" else "home"
    opp_att_x_min, opp_att_x_max = _attacking_third_bound(opp_ground)

    team_touches = actions[(actions["team_id"] == team_id) & actions["start_x"].between(att_x_min, att_x_max)]
    opponent_touches = actions[
        (actions["team_id"] == opponent_team_id) & actions["start_x"].between(opp_att_x_min, opp_att_x_max)
    ]

    total = len(team_touches) + len(opponent_touches)
    if total == 0:
        return None
    return 100.0 * len(team_touches) / total


def _distance_to_goal(x: pd.Series, y: pd.Series, ground: str) -> pd.Series:
    goal_x = FIELD_LENGTH if ground == "home" else 0.0
    goal_y = FIELD_WIDTH / 2
    return ((goal_x - x) ** 2 + (goal_y - y) ** 2) ** 0.5


def _corridor(y: float) -> str:
    if y <= _LEFT_CORRIDOR_Y:
        return "esquerdo"
    if y >= _RIGHT_CORRIDOR_Y:
        return "direito"
    return "central"


def compute_progressive_passes(actions: pd.DataFrame, team_grounds: dict[str, str], threshold: float = 0.25) -> pd.DataFrame:
    """Marca passes progressivos e devolve um DataFrame indexado como `actions`
    com as colunas `progressive` (bool) e `corridor` (str)."""
    is_pass = actions["type_name"].isin(_PASS_ACTION_TYPES) & (actions["result_name"] == "success")

    result = pd.DataFrame(index=actions.index)
    result["progressive"] = False
    result["corridor"] = actions["start_y"].apply(_corridor)

    for team_id, ground in team_grounds.items():
        mask = is_pass & (actions["team_id"] == team_id)
        if not mask.any():
            continue
        start_dist = _distance_to_goal(actions.loc[mask, "start_x"], actions.loc[mask, "start_y"], ground)
        end_dist = _distance_to_goal(actions.loc[mask, "end_x"], actions.loc[mask, "end_y"], ground)
        reduction = (start_dist - end_dist) / start_dist.replace(0, pd.NA)
        result.loc[mask, "progressive"] = (reduction >= threshold).fillna(False)

    return result


def segment_possession_phases(actions: pd.DataFrame) -> pd.DataFrame:
    """Agrupa ações consecutivas do mesmo time em fases de posse.

    Retorna um DataFrame com uma linha por fase: `phase_id`, `team_id`,
    `start_time`, `end_time`, `n_actions`, `outcome` (tipo da última ação da
    fase, ex.: 'shot', 'bad_touch').
    """
    ordered = actions.sort_values(["period_id", "time_seconds"]).reset_index(drop=True)
    team_changed = ordered["team_id"] != ordered["team_id"].shift()
    period_changed = ordered["period_id"] != ordered["period_id"].shift()
    phase_id = (team_changed | period_changed).cumsum() - 1
    ordered = ordered.assign(phase_id=phase_id)

    phases = ordered.groupby("phase_id").agg(
        team_id=("team_id", "first"),
        period_id=("period_id", "first"),
        start_time=("time_seconds", "min"),
        end_time=("time_seconds", "max"),
        n_actions=("action_id", "count"),
        outcome=("type_name", "last"),
    )
    phases["duration_seconds"] = phases["end_time"] - phases["start_time"]
    return phases.reset_index()


def assign_possession_phase_id(actions: pd.DataFrame) -> pd.Series:
    """Igual a `segment_possession_phases`, mas devolve só a coluna `phase_id`
    alinhada ao índice original de `actions` (útil para fazer merge)."""
    ordered = actions.sort_values(["period_id", "time_seconds"])
    team_changed = ordered["team_id"] != ordered["team_id"].shift()
    period_changed = ordered["period_id"] != ordered["period_id"].shift()
    phase_id = (team_changed | period_changed).cumsum() - 1
    return phase_id.reindex(actions.index)


def _infer_pass_receiver(actions: pd.DataFrame) -> pd.Series:
    """Heurística: o receptor de um passe bem-sucedido é o jogador da próxima
    ação, se essa ação for do mesmo time (o SPADL não guarda o receptor
    diretamente)."""
    ordered = actions.sort_values(["period_id", "time_seconds"])
    next_player = ordered["player_id"].shift(-1)
    next_team = ordered["team_id"].shift(-1)
    same_team_next = next_team == ordered["team_id"]
    receiver = next_player.where(same_team_next)
    return receiver.reindex(actions.index)


def build_passing_network(actions: pd.DataFrame, team_id: str, players: dict[str, str]) -> nx.DiGraph:
    """Rede de passes de um time: nós = jogadores, arestas = nº de passes
    concluídos de A para B. `players` mapeia player_id -> nome (para rótulo)."""
    team_passes = actions[
        (actions["team_id"] == team_id)
        & actions["type_name"].isin(_PASS_ACTION_TYPES)
        & (actions["result_name"] == "success")
    ].copy()
    team_passes["receiver_id"] = _infer_pass_receiver(actions).loc[team_passes.index]

    graph = nx.DiGraph()
    for player_id, name in players.items():
        graph.add_node(player_id, name=name)

    for (passer, receiver), group in team_passes.dropna(subset=["receiver_id"]).groupby(["player_id", "receiver_id"]):
        if passer == receiver:
            continue
        graph.add_edge(passer, receiver, weight=len(group))

    return graph


def passing_network_centrality(graph: nx.DiGraph) -> pd.DataFrame:
    """Grau, centralidade de intermediação (betweenness) e clustering
    coefficient por jogador, a partir da rede de passes."""
    if graph.number_of_nodes() == 0:
        return pd.DataFrame(columns=["player_id", "name", "degree", "betweenness", "clustering"])

    undirected = graph.to_undirected()
    degree = dict(graph.degree(weight="weight"))
    betweenness = nx.betweenness_centrality(graph, weight="weight", normalized=True)
    clustering = nx.clustering(undirected, weight="weight")

    rows = [
        {
            "player_id": node,
            "name": data.get("name", node),
            "degree": degree.get(node, 0),
            "betweenness": betweenness.get(node, 0.0),
            "clustering": clustering.get(node, 0.0),
        }
        for node, data in graph.nodes(data=True)
    ]
    return pd.DataFrame(rows)


def team_match_summary(
    actions: pd.DataFrame,
    team_id: str,
    opponent_team_id: str,
    ground: str,
    period_id: int | None = None,
) -> dict:
    """Resumo tático de um time para uma partida (ou um período específico)."""
    scoped = actions if period_id is None else actions[actions["period_id"] == period_id]
    return {
        "team_id": team_id,
        "period_id": period_id,
        "ppda": compute_ppda(scoped, team_id, opponent_team_id, ground),
        "field_tilt_pct": compute_field_tilt(scoped, team_id, opponent_team_id, ground),
        "xt_total": scoped.loc[scoped["team_id"] == team_id, "xt_value"].sum() if "xt_value" in scoped else None,
        "vaep_total": scoped.loc[scoped["team_id"] == team_id, "vaep_value"].sum() if "vaep_value" in scoped else None,
    }

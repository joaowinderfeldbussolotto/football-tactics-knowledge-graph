"""Conversão de eventos kloppy -> SPADL, com xT e VAEP.

Fluxo: `EventDataset` (kloppy) -> ações SPADL (`socceraction.spadl.kloppy`)
-> enriquecimento com xT (grid pré-treinado de Karun Singh) e VAEP (modelo
treinado sob demanda com as próprias ações das partidas processadas).

VAEP precisa de exemplos suficientes de gols para aprender algo com
sentido: treinar em uma única partida seria uma amostra pequena demais
para ter poder preditivo real. Por isso `fit_vaep_model` recebe as ações de
*todas* as partidas baixadas nesta execução da PoC e treina um único
modelo, reaproveitado para avaliar (`rate`) cada partida individualmente.
Isso é uma limitação conhecida de uma PoC com poucas partidas, não do
método em si — em produção o modelo seria treinado numa base bem maior.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd
from kloppy.domain import EventDataset, Ground
from socceraction.spadl import add_names, play_left_to_right
from socceraction.spadl.kloppy import convert_to_actions
from socceraction.vaep.base import VAEP
from socceraction.xthreat import ExpectedThreat, load_model as load_xt_model

logger = logging.getLogger(__name__)

# Grid 12x8 de Expected Threat pré-treinado publicado por Karun Singh, usado
# amplamente como baseline no ecossistema socceraction/kloppy. Ver
# https://karun.in/blog/expected-threat.html
_KARUN_SINGH_XT_GRID_URL = "https://karun.in/blog/data/open_xt_12x8_v1.json"

_MOVE_ACTION_TYPES = {"pass", "cross", "dribble", "take_on", "freekick_short", "freekick_crossed",
                       "corner_short", "corner_crossed", "throw_in", "goalkick"}


@dataclass
class MatchTeamInfo:
    team_id: str
    name: str
    ground: str  # "home" | "away"


@dataclass
class MatchPlayerInfo:
    player_id: str
    name: str
    team_id: str
    starting: bool
    position: str | None


@dataclass
class MatchContext:
    match_id: str
    game_row: pd.Series
    teams: dict[str, MatchTeamInfo] = field(default_factory=dict)
    players: dict[str, MatchPlayerInfo] = field(default_factory=dict)


def build_match_context(dataset: EventDataset, match_id: str) -> MatchContext:
    """Extrai metadados de times/jogadores necessários para enriquecer as ações
    e, mais tarde, para escrever texto legível nos episodes do Graphiti."""
    teams: dict[str, MatchTeamInfo] = {}
    players: dict[str, MatchPlayerInfo] = {}
    home_team_id: str | None = None

    for team in dataset.metadata.teams:
        ground = "home" if team.ground == Ground.HOME else "away"
        teams[team.team_id] = MatchTeamInfo(team_id=team.team_id, name=team.name, ground=ground)
        if ground == "home":
            home_team_id = team.team_id

        for player in team.players:
            position = player.starting_position.name if player.starting_position else None
            players[player.player_id] = MatchPlayerInfo(
                player_id=player.player_id,
                name=player.name,
                team_id=team.team_id,
                starting=bool(player.starting),
                position=position,
            )

    game_row = pd.Series({"game_id": match_id, "home_team_id": home_team_id})
    return MatchContext(match_id=match_id, game_row=game_row, teams=teams, players=players)


def convert_to_spadl(dataset: EventDataset, match_id: str) -> pd.DataFrame:
    """Converte o EventDataset do kloppy para o formato de ações SPADL."""
    actions = convert_to_actions(dataset, game_id=match_id)
    return add_names(actions)


_xt_model_cache: ExpectedThreat | None = None


def get_xt_model() -> ExpectedThreat:
    """Carrega (e cacheia em processo) o modelo de xT pré-treinado."""
    global _xt_model_cache
    if _xt_model_cache is None:
        try:
            _xt_model_cache = load_xt_model(_KARUN_SINGH_XT_GRID_URL)
        except Exception:
            logger.warning(
                "Não foi possível baixar o grid de xT de %s; usando um modelo uniforme como fallback. "
                "Valores de xT ficarão pouco informativos nesse modo.",
                _KARUN_SINGH_XT_GRID_URL,
            )
            fallback = ExpectedThreat(l=12, w=8)
            fallback.xT = fallback.xT * 0 + 0.01
            _xt_model_cache = fallback
    return _xt_model_cache


def compute_xt(actions: pd.DataFrame, home_team_id: str) -> pd.Series:
    """xT gerado por ação: só ações de movimento de bola bem-sucedidas geram
    valor; as demais recebem 0.0 (convenção comum em cima do modelo de Karun
    Singh, que só é definido para ações que movem a bola entre duas zonas).

    O modelo de xT assume que toda ação avança "da esquerda para a direita"
    em direção ao gol adversário. Como as ações SPADL ficam na orientação
    fixa HOME_AWAY (o time visitante ataca da direita para a esquerda), é
    preciso espelhar as coordenadas do time visitante antes de avaliar —
    exatamente o que `play_left_to_right` faz.
    """
    model = get_xt_model()
    move_mask = actions["type_name"].isin(_MOVE_ACTION_TYPES) & (actions["result_name"] == "success")

    xt_values = pd.Series(0.0, index=actions.index, name="xt_value")
    if move_mask.any():
        ltr_actions = play_left_to_right(actions, home_team_id)
        # use_interpolation=False (padrão): interp2d do SciPy foi removido em
        # versões recentes, então usamos o lookup discreto na grid em vez de
        # interpolação contínua.
        rated = model.rate(ltr_actions[move_mask], use_interpolation=False)
        xt_values.loc[move_mask] = rated
    return xt_values


def fit_vaep_model(actions_by_match: dict[str, tuple[pd.Series, pd.DataFrame]]) -> VAEP:
    """Treina um único modelo VAEP nas ações combinadas de todas as partidas
    passadas. Ver docstring do módulo sobre a limitação de amostra pequena."""
    model = VAEP()

    features_parts, labels_parts = [], []
    for game_row, actions in actions_by_match.values():
        features_parts.append(model.compute_features(game_row, actions))
        labels_parts.append(model.compute_labels(game_row, actions))

    X = pd.concat(features_parts, ignore_index=True)
    y = pd.concat(labels_parts, ignore_index=True)
    model.fit(X, y)
    return model


def compute_vaep(model: VAEP, game_row: pd.Series, actions: pd.DataFrame) -> pd.DataFrame:
    """Retorna offensive_value/defensive_value/vaep_value por ação."""
    return model.rate(game_row, actions)


def enrich_actions(
    actions: pd.DataFrame,
    game_row: pd.Series,
    vaep_model: VAEP | None = None,
) -> pd.DataFrame:
    """Junta xT (sempre) e VAEP (se um modelo treinado for passado) às ações SPADL."""
    enriched = actions.copy()
    enriched["xt_value"] = compute_xt(actions, home_team_id=game_row["home_team_id"]).values

    if vaep_model is not None:
        vaep_values = compute_vaep(vaep_model, game_row, actions)
        enriched["offensive_value"] = vaep_values["offensive_value"].values
        enriched["defensive_value"] = vaep_values["defensive_value"].values
        enriched["vaep_value"] = vaep_values["vaep_value"].values
    else:
        enriched["offensive_value"] = float("nan")
        enriched["defensive_value"] = float("nan")
        enriched["vaep_value"] = float("nan")

    return enriched

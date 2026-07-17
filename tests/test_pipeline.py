"""Testes da camada 0 (métricas determinísticas, sem rede e sem Neo4j)."""

import numpy as np
import pandas as pd
import pytest

from football_graphrag.ingestion import tactical_metrics as tm


def make_actions(rows):
    defaults = {
        "type_name": "pass",
        "result_name": "success",
        "team_id": 1,
        "player_id": 10,
        "period_id": 1,
        "time_seconds": 0.0,
        "start_x": 10.0,
        "start_y": 34.0,
        "end_x": 20.0,
        "end_y": 34.0,
        "xt_value": 0.0,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


def test_zone_grid_bounds():
    zones = tm.zone_of(pd.Series([0.0, 104.9, 52.5]), pd.Series([0.0, 67.9, 34.0]))
    assert zones.tolist() == [0, 95, 6 * 8 + 4]


def test_zone_band_and_channel():
    assert tm.zone_band(0) == "defesa"
    assert tm.zone_band(95) == "ataque"
    assert tm.zone_channel(0) == "direita"   # y baixo = direita do ataque
    assert tm.zone_channel(7) == "esquerda"  # y alto = esquerda do ataque


def test_possession_phase_changes_on_team_change():
    actions = make_actions([
        {"team_id": 1}, {"team_id": 1}, {"team_id": 2}, {"team_id": 2}, {"team_id": 1},
    ])
    out = tm.add_possession_phases(actions)
    assert out["possession_id"].nunique() == 3


def test_possession_phase_breaks_after_shot():
    actions = make_actions([
        {"type_name": "pass"}, {"type_name": "shot"}, {"type_name": "pass"},
    ])
    out = tm.add_possession_phases(actions)
    # o passe DEPOIS da finalização abre nova fase, mesmo sem trocar o time
    assert out["possession_id"].iloc[2] != out["possession_id"].iloc[1]


def test_progressive_pass_wyscout_thresholds():
    actions = make_actions([
        # campo próprio -> campo próprio, ganho de 31m em direção ao gol: progressivo
        {"start_x": 5.0, "end_x": 36.0, "start_y": 34.0, "end_y": 34.0},
        # mesmo recorte com ganho de 20m: não progressivo (limiar 30m)
        {"start_x": 5.0, "end_x": 25.0, "start_y": 34.0, "end_y": 34.0},
        # campo adversário -> campo adversário, ganho de 12m: progressivo (limiar 10m)
        {"start_x": 70.0, "end_x": 82.0, "start_y": 34.0, "end_y": 34.0},
    ])
    out = tm.add_progressive_flag(actions)
    assert out["progressive"].tolist() == [True, False, True]


def test_ppda_returns_nan_without_defensive_actions():
    actions = make_actions([{"team_id": 2, "type_name": "pass", "start_x": 30.0}])
    assert np.isnan(tm.compute_ppda(actions, team_id=1))


def test_ppda_counts_opponent_passes_over_defensive_actions():
    actions = make_actions(
        [{"team_id": 2, "type_name": "pass", "start_x": 30.0}] * 12
        + [{"team_id": 1, "type_name": "tackle", "start_x": 60.0}] * 3
    )
    assert tm.compute_ppda(actions, team_id=1) == pytest.approx(4.0)


def test_field_tilt():
    actions = make_actions(
        [{"team_id": 1, "type_name": "pass", "start_x": 80.0}] * 3
        + [{"team_id": 2, "type_name": "pass", "start_x": 80.0}] * 1
    )
    assert tm.compute_field_tilt(actions, team_id=1) == pytest.approx(0.75)


def test_pass_receiver_requires_same_team_next_action():
    actions = make_actions([
        {"player_id": 10, "team_id": 1},
        {"player_id": 11, "team_id": 1},
        {"player_id": 12, "team_id": 1},
        {"player_id": 20, "team_id": 2},
    ])
    out = tm.add_pass_receivers(actions)
    assert out["receiver_player_id"].iloc[0] == 11
    assert out["receiver_player_id"].iloc[1] == 12
    assert pd.isna(out["receiver_player_id"].iloc[2])  # próxima ação é do adversário

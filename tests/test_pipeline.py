"""Testes da camada 0 (métricas determinísticas, sem rede e sem Neo4j)."""

import numpy as np
import pandas as pd
import pytest

from football_graphrag.ingestion import tactical_metrics as tm
from tests.conftest import requires_data


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


def test_dicionario_de_dados_cobre_todas_as_colunas():
    """SCHEMA_DOC tem que descrever exatamente as colunas do parquet.

    O dicionário de dados (scripts/gen_data_dictionary.py) nasce do
    SCHEMA_DOC. Uma coluna nova sem entrada lá sai do dicionário em silêncio
    — foi o que aconteceu com ``segundo`` quando ela foi criada.
    """
    import pandas as pd

    from football_graphrag.config import get_settings
    from football_graphrag.ingestion.pipeline import SCHEMA_DOC
    from tests.conftest import match_data_available

    if not match_data_available():
        pytest.skip("parquet da partida não gerado")

    documentadas = {nome for nome, _, _, _ in SCHEMA_DOC}
    reais = set(pd.read_parquet(get_settings().processed_dir / "3869685.parquet").columns)
    assert reais - documentadas == set(), f"colunas sem entrada no SCHEMA_DOC: {sorted(reais - documentadas)}"
    assert documentadas - reais == set(), f"SCHEMA_DOC descreve colunas inexistentes: {sorted(documentadas - reais)}"


def test_kloppy_orientation_is_flipped_to_left_to_right():
    """kloppy's HOME_AWAY: home attacks left to right in odd periods, sides switch every period."""
    from football_graphrag.ingestion.spadl_transform import _play_left_to_right

    acts = make_actions([
        {"team_id": "H", "period_id": 1, "start_x": 90.0, "end_x": 95.0, "start_y": 10.0, "end_y": 10.0},
        {"team_id": "H", "period_id": 2, "start_x": 15.0, "end_x": 10.0, "start_y": 10.0, "end_y": 10.0},
        {"team_id": "A", "period_id": 3, "start_x": 15.0, "end_x": 10.0, "start_y": 10.0, "end_y": 10.0},
        {"team_id": "A", "period_id": 4, "start_x": 90.0, "end_x": 95.0, "start_y": 10.0, "end_y": 10.0},
    ])
    out = _play_left_to_right(acts, "H")
    assert out.start_x.tolist() == [90.0, 90.0, 90.0, 90.0]
    assert out.end_x.tolist() == [95.0, 95.0, 95.0, 95.0]
    assert out.start_y.tolist() == [10.0, 58.0, 58.0, 10.0]


@requires_data
def test_final_actions_attack_left_to_right_like_the_raw_json():
    """Every action in the same place as in the raw StatsBomb JSON (which is
    always seen from the acting team), and every shot in the attacking third."""
    import json

    from football_graphrag.config import get_settings

    s = get_settings()
    df = pd.read_parquet(s.processed_dir / "3869685.parquet")
    raw = {e["id"]: e for e in json.loads((s.raw_dir / "statsbomb" / "events" / "3869685.json").read_text())}
    loc = df.original_event_id.map(lambda i: (raw.get(i) or {}).get("location"))
    has = loc.notna()
    raw_x = loc[has].map(lambda xy: xy[0] * 105 / 120)
    assert (df.start_x[has] - raw_x).abs().max() < 1.5
    shots = df[df.grupo_acao == "finalizacao"]
    assert (shots.terco == "ataque").all()

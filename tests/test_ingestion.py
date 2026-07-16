import json

import pandas as pd
import pytest

from football_graphrag.ingestion import tactical_metrics as tm
from football_graphrag.ingestion.pipeline import load_match_summary


def test_load_match_summary_reads_existing_sidecar(tmp_path):
    (tmp_path / "15946_summary.json").write_text(json.dumps({"match_id": "15946", "team_summaries": []}))

    summary = load_match_summary("15946", processed_dir=tmp_path)

    assert summary is not None
    assert summary["match_id"] == "15946"


def test_load_match_summary_returns_none_when_missing(tmp_path):
    assert load_match_summary("99999", processed_dir=tmp_path) is None


@pytest.fixture
def synthetic_actions() -> pd.DataFrame:
    # Time A é mandante (defende x em [0,35], ataca em direção a x=105).
    # Time B é visitante (defende x em [70,105], ataca em direção a x=0).
    # Desenhado para que o PPDA de ambos os times fique definido e igual a
    # 2.0 (2 passes do adversário fora do terço defensivo / 1 ação defensiva
    # nessa mesma zona), o que também exercita a segmentação em 3 fases
    # (A -> B -> A) e a rede de passes de cada time (A1->A2, B1->B2).
    rows = [
        dict(period_id=1, time_seconds=0.0, team_id="A", player_id="A1", start_x=10, start_y=34,
             end_x=30, end_y=34, type_name="pass", result_name="success", action_id=0),
        dict(period_id=1, time_seconds=3.0, team_id="A", player_id="A2", start_x=30, start_y=34,
             end_x=95, end_y=34, type_name="pass", result_name="success", action_id=1),
        dict(period_id=1, time_seconds=6.0, team_id="B", player_id="B1", start_x=50, start_y=34,
             end_x=50, end_y=34, type_name="tackle", result_name="success", action_id=2),
        dict(period_id=1, time_seconds=10.0, team_id="B", player_id="B1", start_x=95, start_y=34,
             end_x=60, end_y=34, type_name="pass", result_name="success", action_id=3),
        dict(period_id=1, time_seconds=13.0, team_id="B", player_id="B2", start_x=60, start_y=10,
             end_x=20, end_y=10, type_name="pass", result_name="success", action_id=4),
        dict(period_id=1, time_seconds=16.0, team_id="A", player_id="A1", start_x=40, start_y=10,
             end_x=40, end_y=10, type_name="tackle", result_name="success", action_id=5),
    ]
    df = pd.DataFrame(rows)
    df["xt_value"] = 0.0
    df["vaep_value"] = 0.0
    return df


def test_compute_ppda_excludes_own_defensive_third(synthetic_actions):
    # A ação defensiva de B (tackle em x=50) fica dentro do terço não-defensivo
    # de B (B defende [70,105]), então conta; os 2 passes de A fora do terço
    # defensivo de B (x<70) também contam -> PPDA_B = 2/1.
    assert tm.compute_ppda(synthetic_actions, "B", "A", ground="away") == pytest.approx(2.0)
    # Simetricamente para A: o tackle de A em x=40 e os 2 passes de B com
    # start_x>=35 (fora do terço defensivo de A) -> PPDA_A = 2/1.
    assert tm.compute_ppda(synthetic_actions, "A", "B", ground="home") == pytest.approx(2.0)


def test_compute_ppda_is_none_without_defensive_actions_in_zone(synthetic_actions):
    # Remove a única ação defensiva de A na zona relevante: PPDA_A vira indefinido.
    without_a_tackle = synthetic_actions.iloc[:-1]
    assert tm.compute_ppda(without_a_tackle, "A", "B", ground="home") is None


def test_compute_field_tilt_between_0_and_100():
    # Fixture dedicada: touches de A no próprio terço de ataque ([70,105])
    # e touches de B no próprio terço de ataque ([0,35]), para exercitar um
    # field tilt não-degenerado (nem 0 nem 100 nem None) em ambos os lados.
    rows = [
        dict(period_id=1, time_seconds=0.0, team_id="A", start_x=80, start_y=34,
             type_name="dribble", result_name="success"),
        dict(period_id=1, time_seconds=1.0, team_id="A", start_x=85, start_y=34,
             type_name="dribble", result_name="success"),
        dict(period_id=1, time_seconds=2.0, team_id="B", start_x=20, start_y=34,
             type_name="dribble", result_name="success"),
    ]
    df = pd.DataFrame(rows)

    tilt_a = tm.compute_field_tilt(df, "A", "B", ground="home")
    tilt_b = tm.compute_field_tilt(df, "B", "A", ground="away")
    assert tilt_a is not None and tilt_b is not None
    assert 0.0 <= tilt_a <= 100.0
    assert tilt_a + tilt_b == pytest.approx(100.0)
    assert tilt_a == pytest.approx(2 / 3 * 100)


def test_segment_possession_phases_splits_on_team_change(synthetic_actions):
    phases = tm.segment_possession_phases(synthetic_actions)
    assert list(phases["team_id"]) == ["A", "B", "A"]
    assert list(phases["n_actions"]) == [2, 3, 1]


def test_compute_progressive_passes_flags_forward_progress(synthetic_actions):
    result = tm.compute_progressive_passes(synthetic_actions, {"A": "home", "B": "away"})
    long_pass_idx = synthetic_actions.index[synthetic_actions["action_id"] == 1][0]
    assert result.loc[long_pass_idx, "progressive"]
    short_pass_idx = synthetic_actions.index[synthetic_actions["action_id"] == 0][0]
    assert not result.loc[short_pass_idx, "progressive"]


def test_build_passing_network_counts_completed_passes(synthetic_actions):
    players = {"A1": "Jogador A1", "A2": "Jogador A2"}
    graph = tm.build_passing_network(synthetic_actions, "A", players)
    assert graph.number_of_nodes() == 2
    assert graph.has_edge("A1", "A2")
    assert graph["A1"]["A2"]["weight"] == 1


def test_passing_network_centrality_returns_all_players(synthetic_actions):
    players = {"B1": "Jogador B1", "B2": "Jogador B2"}
    graph = tm.build_passing_network(synthetic_actions, "B", players)
    centrality = tm.passing_network_centrality(graph)
    assert set(centrality["player_id"]) == {"B1", "B2"}
    assert (centrality["degree"] >= 0).all()

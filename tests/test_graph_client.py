from datetime import datetime, timezone

import pandas as pd

from football_graphrag.graph.client import (
    _phase_reference_time,
    build_match_summary_episode_body,
    build_phase_episode_body,
    group_id_for_match,
)


def test_group_id_for_match_is_namespaced():
    assert group_id_for_match("15946") == "match-15946"
    assert group_id_for_match("15946") != group_id_for_match("15947")


def test_phase_reference_time_advances_with_time_and_period():
    kickoff = datetime(2024, 1, 1, tzinfo=timezone.utc)
    first_half = _phase_reference_time(period_id=1, start_time_seconds=120.0, kickoff=kickoff)
    second_half = _phase_reference_time(period_id=2, start_time_seconds=120.0, kickoff=kickoff)

    assert first_half > kickoff
    # O 2º tempo deve ficar depois do 1º mesmo com o mesmo time_seconds local.
    assert second_half > first_half


def test_build_phase_episode_body_mentions_key_facts():
    phase_actions = pd.DataFrame(
        [
            dict(
                period_id=1, time_seconds=125.0, team_id="217", team_name="Barcelona",
                player_id="5503", player_name="Messi", type_name="pass", result_name="success",
                corridor="direito", progressive=True, xt_value=0.045, vaep_value=0.012,
            ),
            dict(
                period_id=1, time_seconds=128.0, team_id="217", team_name="Barcelona",
                player_id="5246", player_name="Suárez", type_name="shot", result_name="fail",
                corridor="central", progressive=False, xt_value=0.0, vaep_value=-0.003,
            ),
        ]
    )

    body = build_phase_episode_body(phase_actions)

    assert "Barcelona" in body
    assert "Messi" in body
    assert "Suárez" in body
    assert "progressivo" in body
    assert "shot" in body
    assert "1º tempo" in body


def test_build_match_summary_episode_body_mentions_ppda_and_field_tilt():
    # Regressão: PPDA/field tilt são agregados por time/partida, nunca
    # aparecem em `build_phase_episode_body` (que só vê ações individuais).
    # Sem este episode extra, nenhuma pergunta sobre pressão teria como ser
    # respondida via /report ou /ask, porque o fato nunca entraria no grafo.
    summary = {
        "teams": {
            "217": {"name": "Barcelona", "ground": "home"},
            "206": {"name": "Deportivo Alavés", "ground": "away"},
        },
        "team_summaries": [
            {"team_id": "217", "ppda": 7.0, "field_tilt_pct": 72.89, "vaep_total": 2.5316},
            {"team_id": "206", "ppda": 16.78, "field_tilt_pct": 27.11, "vaep_total": 1.3174},
        ],
    }

    body = build_match_summary_episode_body(summary)

    assert "Barcelona" in body
    assert "Deportivo Alavés" in body
    assert "PPDA 7.00" in body
    assert "PPDA 16.78" in body
    assert "field tilt 72.9%" in body
    assert "field tilt 27.1%" in body


def test_build_match_summary_episode_body_skips_missing_metrics():
    summary = {
        "teams": {"1": {"name": "Time A", "ground": "home"}},
        "team_summaries": [{"team_id": "1", "ppda": None, "field_tilt_pct": None, "vaep_total": None}],
    }

    body = build_match_summary_episode_body(summary)

    assert "Time A" in body
    assert "PPDA" not in body
    assert "field tilt" not in body

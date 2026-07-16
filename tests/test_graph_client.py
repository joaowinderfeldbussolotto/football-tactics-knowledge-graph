from datetime import datetime, timezone

import pandas as pd

from football_graphrag.graph.client import (
    _phase_reference_time,
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

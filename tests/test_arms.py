"""The arms and graph tools without any paid call (PydanticAI TestModel, fake embeddings)."""

import hashlib

import numpy as np
import pytest
from pydantic_ai.models.test import TestModel

from football_graphrag.benchmark import arms, tools
from tests.conftest import requires_data, requires_neo4j


def fake_embeddings(texts, settings):
    """Deterministic bag-of-words vectors: similar text, similar vector."""
    async def _run():
        out = []
        for t in texts:
            v = np.zeros(256, dtype=np.float32)
            for word in t.lower().replace(",", " ").split():
                v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 256] += 1
            out.append(v.tolist())
        return out
    return _run()


@pytest.fixture
def fake_vector_store(monkeypatch, tmp_path):
    monkeypatch.setattr(arms, "embed_texts", fake_embeddings)
    monkeypatch.setattr(arms, "_cache_dir", lambda: tmp_path)


@requires_data
def test_event_table_has_one_line_per_action_with_cards_and_goals():
    header, lines = arms.event_lines()
    assert header.split(",") == [
        "period", "minute", "team", "player", "action", "success", "receiver",
        "zone_from", "zone_to", "possession", "outcome",
    ]
    assert len(lines) == 2585
    giroud = [ln for ln in lines if "Olivier Giroud" in ln and "yellow_card" in ln]
    assert len(giroud) == 1 and "cartao_por_reclamacao" in giroud[0]
    assert sum("goal" in ln.split(",")[-1].split("+") for ln in lines) == 6


@requires_data
async def test_vector_arm_sends_the_30_most_similar_events(fake_vector_store):
    with arms.plain_agent().override(model=TestModel()):
        result = await arms.run_arm("vector", "Quem recebeu cartão amarelo? Olivier Giroud yellow_card")
    assert result.answer is not None
    rows = result.prompt_preview.split("possession,outcome\n")[1].split("\n\nQuestion:")[0].split("\n")
    assert len(rows) == arms.VECTOR_TOP_K
    assert any("Olivier Giroud" in r and "yellow_card" in r for r in rows)


@requires_data
async def test_events_and_no_context_arms_differ_only_in_the_message():
    q = "Quantas finalizações a França fez?"
    no_context = await arms.build_prompt("no_context", q)
    events = await arms.build_prompt("events_in_prompt", q)
    assert no_context == q
    assert events.endswith(f"Question: {q}") and len(events) > 100_000


@requires_neo4j
async def test_stats_arm_reads_layer_1b_from_neo4j():
    prompt = await arms.build_prompt("stats_in_prompt", "?")
    assert "Enzo Fernandez,Argentina" in prompt
    assert "desarmes_certos" in prompt and "posse_pct" in prompt
    assert "PadraoTatico" not in prompt and "betweenness" not in prompt  # no layer 2


@requires_neo4j
async def test_graph_tools_arm_logs_calls_and_turns_bad_arguments_into_messages():
    # TestModel calls every tool once with dummy arguments ("a"): every
    # call must come back as an error message, not an exception.
    with arms.graph_agent().override(model=TestModel()):
        result = await arms.run_arm("graph_tools", "Quem foi o pivô da Argentina?")
    assert result.answer is not None
    assert {c["tool"] for c in result.tool_calls} == {
        "list_players", "player_stats", "team_stats", "stat_ranking", "events",
        "pass_network_centrality", "three_player_sequences", "pass_network_bridges",
    }


@requires_neo4j
def test_tool_call_limit_returns_a_message_after_8_calls():
    class Ctx:
        deps = arms.GraphDeps(driver=None, calls=[{}] * arms.MAX_TOOL_CALLS)
    assert "limit" in arms._call(Ctx(), "team_stats", tools.team_stats, team="Argentina")["error"]


@requires_neo4j
def test_tools_answer_from_the_graph():
    from football_graphrag.config import get_settings
    from football_graphrag.graph import db

    d = db.make_driver(get_settings())
    try:
        assert tools.player_stats(d, "Enzo Fernández")["desarmes_certos"] == 5
        assert tools.pass_network_centrality(d, "Argentina", 2)[1] == {"player": "Enzo Fernandez", "betweenness": 25.0}
        trio = tools.three_player_sequences(d, "França", 1)[0]
        assert (trio["a"], trio["b"], trio["c"], trio["occurrences"]) == (
            "Jules Koundé", "Raphaël Varane", "Dayotchanculle Upamecano", 3)
        assert len(tools.events(d, "yellow_card")) == 7
        with pytest.raises(tools.ToolError, match="ambiguous"):
            tools.player_stats(d, "Martínez")
    finally:
        d.close()


@requires_data
def test_event_table_is_in_match_order():
    # Giroud's card (95', recovered from the raw JSON) used to sit at the end.
    _, lines = arms.event_lines()
    period_minute = [tuple(int(x) for x in ln.split(",")[:2]) for ln in lines]
    assert period_minute == sorted(period_minute)
    assert "Olivier Giroud" not in lines[-1]


def test_cached_arms_split_data_and_question_around_a_cache_point():
    from pydantic_ai.messages import CachePoint

    prompt = "Match stats:\nnome,toques\nEnzo,195\n\nQuestion: Quem tocou mais?"
    data, cache_point, question = arms.user_content("stats_in_prompt", prompt)
    assert isinstance(cache_point, CachePoint)
    assert data == "Match stats:\nnome,toques\nEnzo,195"
    assert question == "Question: Quem tocou mais?"
    # arms whose content changes with the question are sent as a plain string
    assert arms.user_content("vector", prompt) == prompt
    assert arms.user_content("no_context", "Quem?") == "Quem?"

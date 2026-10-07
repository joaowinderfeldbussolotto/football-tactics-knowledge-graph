"""The questions must not hand the graph_tools arm a lexical shortcut."""

import re

import pytest

from football_graphrag.benchmark.questions import QUESTIONS

# Tool names, algorithm names and graph jargon: a question that uses them
# names the tool for the model instead of asking about football.
FORBIDDEN = [
    "betweenness", "centralidade", "centrality", "pagerank", "louvain", "gds", "cypher",
    "grafo", "graph", "xt", "vaep", "spadl", "ponderad", "pivô", "trio progressivo",
    "list_players", "player_stats", "team_stats", "stat_ranking", "events",
    "pass_network", "three_player", "sequences", "bridges",
]


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q.id)
def test_question_uses_football_language_not_tool_vocabulary(question):
    words = question.text.lower()
    found = [w for w in FORBIDDEN if re.search(rf"\b{re.escape(w)}", words)]
    assert not found, f"{question.id} uses tool vocabulary: {found}"

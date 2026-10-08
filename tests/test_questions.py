"""The questions file: football language, valid structure, stable answers."""

import re

import pytest

from football_graphrag.benchmark.questions import ALL_QUESTIONS, QUESTIONS

# Tool names, algorithm names and graph jargon: a question that uses them
# names the tool for the model instead of asking about football.
FORBIDDEN = [
    "betweenness", "centralidade", "centrality", "pagerank", "louvain", "gds", "cypher",
    "grafo", "graph", "xt", "vaep", "spadl", "ponderad", "pivô", "trio progressivo", "rede",
    "ponto de articulação", "articulation", "aresta", "nó", "grau", "degree", "intermediação",
    "list_players", "query_actions", "list_actions", "pass_network", "network", "pass_paths",
    "same_possession", "consecutive",
]


@pytest.mark.parametrize("question", ALL_QUESTIONS, ids=lambda q: q.id)
def test_question_uses_football_language_not_tool_vocabulary(question):
    words = question.text.lower()
    found = [w for w in FORBIDDEN if re.search(rf"\b{re.escape(w)}\b", words)]
    assert not found, f"{question.id} uses tool vocabulary: {found}"


def test_the_yaml_file_is_the_source_and_is_validated(tmp_path):
    from football_graphrag.benchmark.questions import QUESTIONS_FILE, load

    qs = load(QUESTIONS_FILE)
    assert qs.match_id == 3869685
    types = {q.type for q in qs.active}
    assert qs.per_type is None or len(qs.active) == len(types) * qs.per_type
    text = QUESTIONS_FILE.read_text()
    broken = tmp_path / "questions.yaml"
    broken.write_text(text.replace("check: set", "check: sett", 1))
    with pytest.raises(ValueError, match="unknown check 'sett'"):
        load(broken)
    # the main benchmark: 5 per type; one question less breaks it
    import re
    main = re.sub(r"(?m)^active_stages: .*\nper_type:.*$", "active_stages: [pilot, full]\nper_type: 5", text)
    assert len(load_text(tmp_path, main).active) == 25
    broken.write_text(main.replace("stage: pilot", "stage: candidate", 1))
    with pytest.raises(ValueError, match="active questions of type 'fact', expected"):
        load(broken)


def load_text(tmp_path, text):
    from football_graphrag.benchmark.questions import load

    path = tmp_path / "q.yaml"
    path.write_text(text)
    return load(path)


def test_active_questions_have_stable_ground_truth():
    from football_graphrag.benchmark import ground_truth

    gt = ground_truth.load()
    unstable = [q.id for q in QUESTIONS if not gt[q.id]["stable"]]
    assert not unstable, f"active questions whose answer changes with the reading: {unstable}"
    # a removed question is unstable, unless its note says why else it left
    removed_but_stable = [q.id for q in ALL_QUESTIONS if q.stage == "removed" and gt[q.id]["stable"]
                          and not q.note.startswith("Retirada")]
    assert not removed_but_stable, f"removed questions that are stable: {removed_but_stable}"

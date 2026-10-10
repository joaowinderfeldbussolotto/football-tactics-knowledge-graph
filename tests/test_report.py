"""The run page is a pure function of the results rows."""

from datetime import date

from football_graphrag.benchmark.report import RunInfo, add_to_index, index_row, next_number, render


def row(qid, typ, arm, correct, abstention=False, format_error=False):
    return {
        "question_id": qid, "type": typ, "arm": arm, "repeat": 1, "correct": correct,
        "abstention": abstention, "format_error": format_error,
        "answer": None if format_error else {"players": ["Messi"], "value": None, "no_data": abstention},
        "expected": {"players": ["Enzo Fernandez"], "accepted": [["Enzo Fernandez"]], "value": None, "no_data": False},
        "input_tokens": 100, "output_tokens": 10, "n_tool_calls": 1, "latency_s": 1.0, "model": "openrouter:x/m",
        "trace_url": f"https://t/{qid}/{arm}",
    }


ROWS = [
    row("f01", "fact", "graph_tools", True), row("f01", "fact", "events_in_prompt", True),
    row("n04", "network", "graph_tools", True), row("n04", "network", "events_in_prompt", False),
    row("p03", "play", "graph_tools", False, abstention=True), row("p03", "play", "events_in_prompt", False),
    row("u01", "unanswerable", "graph_tools", True), row("u01", "unanswerable", "events_in_prompt", True),
]


def test_render_has_groups_errors_reading_and_traces():
    md = render(ROWS, 12, "teste", RunInfo(command="python x", cost_usd=0.5, day=date(2026, 1, 2)),
                "../../r.jsonl", "../../s.md", "commit `abc`")
    assert md.startswith("# Execução 12: teste")
    assert "| Custo real | US$ 0.50" in md
    assert "| Busca e contagem | 1 | 1/1 (100%) | 1/1 (100%) |" in md
    assert "| **total sem o controle** | 3 | **1/3 (33%)** | **2/3 (67%)** |" in md
    assert "**Nenhum braço acertou** (1): p03." in md
    assert "**Só `graph_tools` acertou** (1): n04." in md
    assert "[🟡](https://t/p03/graph_tools)" in md
    assert "| [n04](https://t/n04/events_in_prompt) |" in md and "| Enzo Fernandez | Messi | alucinação |" in md


def test_numbering_and_index(tmp_path):
    (tmp_path / "2026-01-01_07_x.md").write_text("")
    (tmp_path / "README.md").write_text("| # |\n|---|\n| [07](2026-01-01_07_x.md) | a |\n\nfim\n")
    assert next_number(tmp_path) == 8
    add_to_index(index_row(8, "p.md", RunInfo(day=date(2026, 1, 2)), "t", ROWS), tmp_path)
    lines = (tmp_path / "README.md").read_text().splitlines()
    assert lines[3].startswith("| [08](p.md) | 2026-01-02 | t | m | 8 | 3/4 | – |")

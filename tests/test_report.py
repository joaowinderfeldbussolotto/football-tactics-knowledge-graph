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


def test_rewriting_a_page_keeps_number_and_adds_cost(tmp_path):
    import json

    from football_graphrag.benchmark.report import write_report

    results = tmp_path / "x_results.jsonl"
    results.write_text("".join(json.dumps(r) + "\n" for r in ROWS))
    (tmp_path / "README.md").write_text("| # |\n|---|\n| [03](2026-01-01_03_x.md) | old |\n")
    page = tmp_path / "2026-01-01_03_x.md"
    page.write_text("# Execução 03: título\n\n| Comando | `python a` |\n| Custo real | US$ 0.80 (x) |\n")
    write_report(results, tmp_path / "s.md", RunInfo(command="python b", cost_usd=0.1), runs_dir=tmp_path, page=page)
    text = page.read_text()
    assert text.startswith("# Execução 03: título") and "| Data | 2026-01-01 |" in text
    assert "US$ 0.90" in text and "`python a`, depois `python b`" in text
    assert "| [03](2026-01-01_03_x.md) | 2026-01-01 | título |" in (tmp_path / "README.md").read_text()


def test_rescore_uses_the_current_ground_truth():
    from football_graphrag.benchmark.runner import rescore

    rows = [{**row("p07", "play", "graph_tools", False),
             "answer": {"rationale": "", "players": ["Adrien Rabiot", "Aurélien Djani Tchouaméni", "Kylian Mbappé Lottin"],
                        "value": None, "no_data": False}}]
    truth = {"p07": {"players": ["Adrien Rabiot", "Aurélien Djani Tchouaméni"], "value": None, "no_data": False,
                     "accepted": [["Adrien Rabiot", "Aurélien Djani Tchouaméni"], ["Adrien Rabiot", "Kylian Mbappé Lottin"]]}}
    assert rescore(rows, truth) == 1 and rows[0]["correct"]


def test_merge_keeps_the_last_file_for_a_repeated_run(tmp_path):
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location(
        "merge_results", __file__.replace("tests/test_report.py", "scripts/merge_results.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    a.write_text("".join(json.dumps(r) + "\n" for r in [row("f01", "fact", "graph_tools", False),
                                                       row("n04", "network", "graph_tools", True)]))
    b.write_text(json.dumps(row("f01", "fact", "graph_tools", True)) + "\n" + json.dumps(row("f01", "fact", "vector", False)) + "\n")
    merged = module.merge([a, b])
    assert [(r["question_id"], r["arm"], r["correct"]) for r in merged] == [
        ("f01", "vector", False), ("f01", "graph_tools", True), ("n04", "graph_tools", True)]


def test_the_scripts_compile():
    import py_compile
    from pathlib import Path

    for script in sorted((Path(__file__).resolve().parents[1] / "scripts").glob("*.py")):
        py_compile.compile(str(script), doraise=True)

"""summary.md is a pure function of results.jsonl."""

from football_graphrag.benchmark.summary import summarize


def row(qid, arm, repeat, correct, players=("Enzo Fernandez",), abstention=False, format_error=False):
    return {
        "question_id": qid, "type": {"f": "fact", "u": "unanswerable"}[qid[0]], "arm": arm,
        "repeat": repeat, "correct": correct, "abstention": abstention, "format_error": format_error,
        "answer": None if format_error else {"players": list(players), "value": None, "no_data": abstention},
        "input_tokens": 100, "output_tokens": 10, "n_tool_calls": 0, "latency_s": 1.0, "model": "m:x",
    }


def test_summary_counts_accuracy_errors_and_consistency():
    rows = [
        row("f01", "graph_tools", 1, True), row("f01", "graph_tools", 2, True),
        row("u01", "graph_tools", 1, False), row("u01", "graph_tools", 2, False, players=("Messi",)),
        row("f01", "no_context", 1, False, abstention=True), row("f01", "no_context", 2, False, format_error=True),
    ]
    md = summarize(rows)
    assert "| fact | 0% | 100% |" in md  # arms in ARMS order: no_context before graph_tools
    assert "| **all** | **0%** | **50%** |" in md
    assert "| **all but unanswerable** | **0%** | **100%** |" in md
    assert "| no_context | 0% | 50% | 50% |" in md  # hallucination, abstention, format error
    assert "| graph_tools | 50% | 0% | 0% |" in md
    # f01 same answer twice; u01 two different answers ("Enzo" vs "Messi")
    assert "| graph_tools | 50% | 2 |" in md


def test_summary_file_names():
    from pathlib import Path

    from football_graphrag.benchmark.summary import summary_path_for

    assert summary_path_for(Path("d/results.jsonl")) == Path("d/summary.md")
    assert summary_path_for(Path("d/pilot_results.jsonl")) == Path("d/pilot_summary.md")
    assert summary_path_for(Path("d/sample_haiku.jsonl")) == Path("d/sample_haiku_summary.md")

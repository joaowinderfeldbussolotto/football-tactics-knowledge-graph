"""One benchmark run = one question x one arm x one repeat.

Shared by ``scripts/ask.py`` and ``scripts/run_benchmark.py`` so both go
through exactly the same code: ``run_arm`` -> ``score`` -> result row.
"""

from datetime import datetime, timezone

from football_graphrag.benchmark.arms import ArmResult, run_arm
from football_graphrag.benchmark.questions import BY_ID, Question
from football_graphrag.benchmark.scoring import Answer, Score, score
from football_graphrag.config import get_settings
from football_graphrag.observability.langfuse_setup import current_trace_url, span


async def run_one(question_text: str, arm: str, span_name: str, *, observed: bool, **metadata) -> ArmResult:
    with span(span_name, active=observed, arm=arm, **metadata):
        result = await run_arm(arm, question_text)
        result.trace_url = current_trace_url(observed)
    return result


def result_row(question: Question, arm: str, repeat: int, result: ArmResult, expected: dict) -> dict:
    s: Score = score(question, expected, result.answer)
    settings = get_settings()
    return {
        "question_id": question.id,
        "type": question.type,
        "arm": arm,
        "repeat": repeat,
        "answer": result.answer.model_dump() if result.answer else None,
        "expected": {k: expected.get(k) for k in ("players", "accepted", "value", "no_data")},
        "correct": s.correct,
        "abstention": s.abstention,
        "format_error": s.format_error,
        "error": result.error,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cache_read_tokens": result.cache_read_tokens,
        "cache_write_tokens": result.cache_write_tokens,
        "n_tool_calls": len(result.tool_calls),
        "tool_calls": result.tool_calls,
        "latency_s": result.latency_s,
        "trace_url": result.trace_url,
        "model": f"{settings.llm_provider}:{settings.llm_model}",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def rescore(rows: list[dict], truth: dict) -> int:
    """Score the stored answers again against the current ground truth and scoring rules
    (in place). Returns how many rows changed verdict."""
    changed = 0
    for row in rows:
        q = BY_ID.get(row["question_id"])
        if q is None or q.id not in truth:
            continue
        answer = Answer(**row["answer"]) if row["answer"] else None
        s = score(q, truth[q.id], answer)
        before = (row["correct"], row["abstention"], row["format_error"])
        row["expected"] = {k: truth[q.id].get(k) for k in ("players", "accepted", "value", "no_data")}
        row["correct"], row["abstention"], row["format_error"] = s.correct, s.abstention, s.format_error
        changed += before != (s.correct, s.abstention, s.format_error)
    return changed

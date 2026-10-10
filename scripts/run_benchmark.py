#!/usr/bin/env python
"""Run the benchmark: questions x arms x repeats, one results.jsonl line per run.

Usage:
    python scripts/run_benchmark.py                       # active questions x configured arms x 3 repeats
    python scripts/run_benchmark.py --repeats 1
    python scripts/run_benchmark.py --arms no_context,stats_in_prompt,graph_tools
    python scripts/run_benchmark.py --questions f01,s02
    python scripts/run_benchmark.py --sample              # 1 question per type, 1 repeat
    python scripts/run_benchmark.py --resume              # skip what is already in the file

Each line is written right after its call, so a crash loses at most one run;
``--resume`` continues from there. A provider error (after the SDK's own
retries) is reported and NOT written, so ``--resume`` retries it. A model
answer that never validates is written, as a format error.

At the end, writes summary.md (same as ``scripts/summarize.py``) and the page of the
run in docs/execucoes/ (same as ``scripts/report_run.py``), with the real cost when the
provider is OpenRouter. ``--no-report`` skips the page.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from football_graphrag.benchmark import ground_truth
from football_graphrag.benchmark.arms import ARMS, configured_arms, missing_config
from football_graphrag.benchmark.report import RunInfo, openrouter_usage, write_report
from football_graphrag.benchmark.questions import QUESTION_SET, QUESTION_TYPES, QUESTIONS, get_question
from football_graphrag.benchmark.runner import result_row, run_one
from football_graphrag.benchmark.summary import load_rows, write_summary
from football_graphrag.config import get_settings
from football_graphrag.observability import logging_setup
from football_graphrag.observability.langfuse_setup import flush, setup_observability

logger = logging.getLogger("run_benchmark")


def default_output() -> Path:
    """pilot_results.jsonl while only the pilot questions are active, else results.jsonl."""
    name = "pilot_results.jsonl" if QUESTION_SET.active_stages == ("pilot",) else "results.jsonl"
    return get_settings().data_dir / "benchmark" / name


async def main(args) -> int:
    settings = get_settings()
    arms = args.arms.split(",") if args.arms else configured_arms()
    for a in arms:
        if a not in ARMS:
            print(f"unknown arm {a!r}; valid: {', '.join(ARMS)}")
            return 2
    problems = missing_config(arms)
    if problems:
        print("cannot run:\n  " + "\n  ".join(problems))
        return 2

    if args.sample:
        questions = [next(q for q in QUESTIONS if q.type == t) for t in QUESTION_TYPES]
        repeats = 1
    else:
        questions = [get_question(q) for q in args.questions.split(",")] if args.questions else QUESTIONS
        repeats = args.repeats

    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {(r["question_id"], r["arm"], r["repeat"]) for r in load_rows(out)}
    if done and not args.resume and not args.fresh:
        print(f"{out} already has {len(done)} runs. Use --resume to continue or --fresh to start over.")
        return 2
    if args.fresh:
        out.write_text("")
        done = set()

    truth = ground_truth.load()
    observed = setup_observability(settings)
    plan = [(q, a, n) for n in range(1, repeats + 1) for q in questions for a in arms
            if (q.id, a, n) not in done]
    print(f"model {settings.llm_provider}:{settings.llm_model} | {len(plan)} runs to do "
          f"({len(done)} already in {out})")

    usage_before = openrouter_usage(settings.llm_api_key) if settings.llm_provider == "openrouter" else None
    failed = 0
    with out.open("a") as f:
        for i, (q, arm, n) in enumerate(plan, 1):
            try:
                result = await run_one(q.text, arm, f"{q.id}/{arm}/r{n}", observed=observed,
                                       question_id=q.id, type=q.type, repeat=n)
            except Exception as exc:  # provider/network error after the SDK retries
                failed += 1
                print(f"[{i}/{len(plan)}] {q.id} {arm} r{n}: PROVIDER ERROR {type(exc).__name__}: {exc}")
                continue
            row = result_row(q, arm, n, result, truth[q.id])
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            verdict = ("ok" if row["correct"] else "abstention" if row["abstention"]
                       else "format_error" if row["format_error"] else "wrong")
            print(f"[{i}/{len(plan)}] {q.id} {arm} r{n}: {verdict} "
                  f"({row['input_tokens']}/{row['output_tokens']} tok, {row['latency_s']}s)")

    flush(observed)
    summary = write_summary(out)
    print(f"\nresults: {out}\nsummary: {summary}")
    if plan and not args.no_report:
        usage_after = openrouter_usage(settings.llm_api_key) if usage_before is not None else None
        cost = usage_after - usage_before if usage_after is not None else None
        info = RunInfo(command="python " + " ".join(sys.argv), cost_usd=cost, failed=failed)
        print(f"report:  {write_report(out, summary, info, args.title)}")
    if failed:
        print(f"{failed} runs failed with provider errors and were not written; run again with --resume.")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--arms", help=f"comma-separated subset of: {','.join(ARMS)} "
                                       "(default: the arms in config/benchmark.yaml)")
    parser.add_argument("--questions", help="comma-separated question ids, e.g. f01,s02")
    parser.add_argument("--sample", action="store_true", help="first question of each type, 1 repeat")
    parser.add_argument("--resume", action="store_true", help="skip runs already in the output file")
    parser.add_argument("--fresh", action="store_true", help="empty the output file first")
    parser.add_argument("--output", type=Path, default=None, help="default: data/benchmark/results.jsonl")
    parser.add_argument("--title", help="title of the run page in docs/execucoes/ (default: questions and arms)")
    parser.add_argument("--no-report", action="store_true", help="do not write the run page in docs/execucoes/")
    args = parser.parse_args()
    args.output = args.output or default_output()
    logging_setup.setup(level=logging.WARNING)
    sys.exit(asyncio.run(main(args)))

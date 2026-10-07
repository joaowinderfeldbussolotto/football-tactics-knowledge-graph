#!/usr/bin/env python
"""Ask one question to one arm, or to all of them. Never writes results.jsonl.

Usage:
    python scripts/ask.py --question s01                      # benchmark question, all arms
    python scripts/ask.py --question s01 --arm graph_tools    # benchmark question, one arm
    python scripts/ask.py "Quem tocou mais na bola?"          # free question, all arms
    python scripts/ask.py "Quem tocou mais na bola?" --arm stats_in_prompt
    python scripts/ask.py --question s01 --show-prompt        # also print the prompt sent

For a benchmark question it also prints the ground truth and whether the
answer is right. A free question has no ground truth.
"""

import argparse
import asyncio
import json
import logging
import sys

from football_graphrag.benchmark import ground_truth
from football_graphrag.benchmark.arms import ARMS, SYSTEM_PROMPT, missing_config
from football_graphrag.benchmark.questions import get_question
from football_graphrag.benchmark.runner import run_one
from football_graphrag.benchmark.scoring import score
from football_graphrag.config import get_settings
from football_graphrag.observability import logging_setup
from football_graphrag.observability.langfuse_setup import flush, setup_observability


async def main(args) -> int:
    settings = get_settings()
    question = get_question(args.question) if args.question else None
    text = question.text if question else args.text
    expected = ground_truth.load()[question.id] if question else None
    problems = missing_config([args.arm] if args.arm else list(ARMS))
    if problems:
        print("cannot run:\n  " + "\n  ".join(problems))
        return 2
    observed = setup_observability(settings)

    print(f"model: {settings.llm_provider}:{settings.llm_model}")
    print(f"question{f' {question.id} ({question.type})' if question else ''}: {text}")
    if expected:
        print(f"ground truth: players={expected['players']} value={expected['value']} no_data={expected['no_data']}")
    if args.show_prompt:
        print(f"\n--- system prompt (all arms) ---\n{SYSTEM_PROMPT}")

    for arm in [args.arm] if args.arm else ARMS:
        r = await run_one(text, arm, f"ask/{question.id if question else 'adhoc'}/{arm}", observed=observed)
        print(f"\n=== {arm}  ({r.latency_s}s, tokens in/out {r.input_tokens}/{r.output_tokens})")
        if r.trace_url:
            print(f"  trace: {r.trace_url}")
        if args.show_prompt:
            print(f"--- user prompt ---\n{r.prompt_preview}\n---")
        for c in r.tool_calls:
            print(f"  tool: {c['tool']}({json.dumps(c['args'], ensure_ascii=False)})")
        if r.answer is None:
            print(f"  no valid answer: {r.error}")
        else:
            print(f"  {json.dumps(r.answer.model_dump(), ensure_ascii=False, indent=2)}")
        if question:
            s = score(question, expected, r.answer)
            verdict = "CORRECT" if s.correct else ("ABSTENTION" if s.abstention else
                                                 "FORMAT ERROR" if s.format_error else "WRONG")
            print(f"  -> {verdict}")
    flush(observed)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text", nargs="?", help="a free question (in Portuguese)")
    parser.add_argument("--question", help="a benchmark question id, e.g. s01")
    parser.add_argument("--arm", choices=ARMS, help="only this arm (default: all)")
    parser.add_argument("--show-prompt", action="store_true", help="print the prompt sent to the model")
    args = parser.parse_args()
    if bool(args.text) == bool(args.question):
        parser.error("give either a free question or --question <id>")
    logging_setup.setup(level=logging.WARNING)
    sys.exit(asyncio.run(main(args)))

#!/usr/bin/env python
"""Ask questions to one arm or to all of them. Never writes results.jsonl.

Usage:
    python scripts/ask.py                                     # interactive: type free questions, one per line
    python scripts/ask.py --arm graph_tools                   # interactive, one arm only (cheaper)
    python scripts/ask.py "Quem tocou mais na bola?"          # one free question, all arms
    python scripts/ask.py "Quem tocou mais na bola?" --arm stats_in_prompt
    python scripts/ask.py --question s01                      # benchmark question, all arms
    python scripts/ask.py --question s01 --arm graph_tools    # benchmark question, one arm
    python scripts/ask.py --question s01 --show-prompt        # also print the prompt sent

A free question has no ground truth: the answer is shown, not scored. A
benchmark question also shows the ground truth and whether the answer is right.
Every arm answers in the same format (rationale, players, value, no_data), so
the rationale is where the explanation is.
"""

import argparse
import asyncio
import logging
import sys

from football_graphrag.benchmark import ground_truth
from football_graphrag.benchmark.arms import ARMS, SYSTEM_PROMPT, ArmResult, configured_arms, missing_config
from football_graphrag.benchmark.questions import Question, get_question
from football_graphrag.benchmark.runner import run_one
from football_graphrag.benchmark.scoring import score
from football_graphrag.config import get_settings
from football_graphrag.observability import logging_setup
from football_graphrag.observability.langfuse_setup import flush, setup_observability

EXIT_WORDS = {"", "sair", "exit", "quit"}


def show(r: ArmResult, show_prompt: bool) -> None:
    print(f"\n=== {r.arm}  ({r.latency_s}s, tokens in/out {r.input_tokens}/{r.output_tokens})")
    if show_prompt:
        print(f"--- user prompt ---\n{r.prompt_preview}\n---")
    for c in r.tool_calls:
        args = ", ".join(f"{k}={v!r}" for k, v in c["args"].items())
        print(f"  tool: {c['tool']}({args})")
    if r.answer is None:
        print(f"  no valid answer: {r.error}")
    else:
        a = r.answer
        print(f"  answer:  {a.rationale}")
        print(f"  players: {', '.join(a.players) or '-'} | value: {a.value if a.value is not None else '-'}"
              f" | no_data: {'yes' if a.no_data else 'no'}")
    if r.trace_url:
        print(f"  trace:   {r.trace_url}")


async def ask(text: str, arms: list[str], *, question: Question | None, show_prompt: bool, observed: bool) -> None:
    expected = ground_truth.load()[question.id] if question else None
    if expected:
        print(f"ground truth: players={expected['players']} value={expected['value']} no_data={expected['no_data']}")
    for arm in arms:
        r = await run_one(text, arm, f"ask/{question.id if question else 'adhoc'}/{arm}", observed=observed)
        show(r, show_prompt)
        if question:
            s = score(question, expected, r.answer)
            verdict = "CORRECT" if s.correct else ("ABSTENTION" if s.abstention else
                                                 "FORMAT ERROR" if s.format_error else "WRONG")
            print(f"  -> {verdict}")


async def main(args) -> int:
    settings = get_settings()
    arms = [args.arm] if args.arm else configured_arms()
    problems = missing_config(arms)
    if problems:
        print("cannot run:\n  " + "\n  ".join(problems))
        return 2
    observed = setup_observability(settings)
    print(f"model: {settings.llm_provider}:{settings.llm_model} | arms: {', '.join(arms)}")
    if args.show_prompt:
        print(f"\n--- system prompt (all arms) ---\n{SYSTEM_PROMPT}")

    try:
        if args.question or args.text:
            question = get_question(args.question) if args.question else None
            text = question.text if question else args.text
            print(f"question{f' {question.id} ({question.type})' if question else ''}: {text}")
            await ask(text, arms, question=question, show_prompt=args.show_prompt, observed=observed)
            return 0

        print("Free questions about the 2022 World Cup final, one per line. Empty line or 'sair' to quit.")
        if len(arms) > 1:
            print("Tip: --arm graph_tools (or another arm) is cheaper and faster than all five.")
        while True:
            try:
                text = (await asyncio.to_thread(input, "\npergunta> ")).strip()
            except EOFError:
                break
            if text.lower() in EXIT_WORDS:
                break
            await ask(text, arms, question=None, show_prompt=args.show_prompt, observed=observed)
        return 0
    finally:
        flush(observed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text", nargs="?", help="a free question (in Portuguese); omit it for interactive mode")
    parser.add_argument("--question", help="a benchmark question id, e.g. s01")
    parser.add_argument("--arm", choices=ARMS, help="only this arm (default: the arms in config/benchmark.yaml)")
    parser.add_argument("--show-prompt", action="store_true", help="print the prompt sent to the model")
    args = parser.parse_args()
    if args.text and args.question:
        parser.error("give a free question or --question <id>, not both")
    logging_setup.setup(level=logging.WARNING)
    sys.exit(asyncio.run(main(args)))

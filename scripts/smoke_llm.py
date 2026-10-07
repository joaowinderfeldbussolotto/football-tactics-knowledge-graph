#!/usr/bin/env python
"""Smoke test for the LLM configured in .env.

The benchmark needs two capabilities from the model, and they are the first
to break on an unfamiliar model or provider:

1. tool calling (the ``graph_tools`` arm is an agent with tools);
2. structured output (every arm answers with a Pydantic model).

This script checks both with a single cheap call: an agent with one tool
whose result only the tool knows, asked to return a structured answer.
It does not touch Neo4j.

Usage:
    python scripts/smoke_llm.py
"""

import asyncio
import sys
import time

from pydantic import BaseModel
from pydantic_ai import Agent

from football_graphrag.config import get_settings
from football_graphrag.llm.provider import pydantic_ai_model, pydantic_ai_model_settings
from football_graphrag.observability import logging_setup

logging_setup.setup()

SECRET = 7341


class SmokeAnswer(BaseModel):
    value: float | None = None


async def main() -> int:
    settings = get_settings()
    if not settings.llm_api_key:
        print("LLM_API_KEY is missing in .env: nothing to test.")
        return 1
    print(f"provider={settings.llm_provider}  model={settings.llm_model}")

    agent = Agent(
        pydantic_ai_model(settings),
        output_type=SmokeAnswer,
        output_retries=2,
        model_settings={**pydantic_ai_model_settings(settings), "temperature": 0},
        system_prompt="Use the available tool to answer. Do not guess.",
    )
    calls: list[str] = []

    @agent.tool_plain
    def get_ticket_number() -> int:
        """Return the ticket number the user is asking about."""
        calls.append("get_ticket_number")
        return SECRET

    t0 = time.perf_counter()
    try:
        result = await agent.run("What is the ticket number? Put it in `value`.")
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return 1
    elapsed = time.perf_counter() - t0

    tool_ok = bool(calls)
    output_ok = result.output.value == SECRET
    usage = result.usage()
    print(f"tool calling:      {'ok' if tool_ok else 'FAILED (tool was not called)'}")
    print(f"structured output: {'ok' if output_ok else f'FAILED (value={result.output.value})'}")
    print(f"tokens in/out: {usage.input_tokens}/{usage.output_tokens}  latency: {elapsed:.1f}s")
    return 0 if tool_ok and output_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

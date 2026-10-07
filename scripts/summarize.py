#!/usr/bin/env python
"""Regenerate summary.md from results.jsonl, without calling any LLM.

Usage:
    python scripts/summarize.py
    python scripts/summarize.py --results data/benchmark/sample.jsonl
"""

import argparse
from pathlib import Path

from football_graphrag.benchmark.summary import write_summary
from football_graphrag.config import get_settings

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=None, help="default: data/benchmark/results.jsonl")
    args = parser.parse_args()
    results = args.results or get_settings().data_dir / "benchmark" / "results.jsonl"
    if not results.exists():
        raise SystemExit(f"{results} does not exist; run scripts/run_benchmark.py first")
    print(f"written {write_summary(results)}")

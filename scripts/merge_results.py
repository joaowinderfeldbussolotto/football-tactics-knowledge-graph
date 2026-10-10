#!/usr/bin/env python
"""Merge results files into one, without calling any LLM.

A run is identified by (question, arm, repeat). When the same run is in more than one
file, the line from the LAST file wins, so a file with reruns can be put after the file it
corrects. The merged file is then summarized and reported like any other
(``scripts/summarize.py``, ``scripts/report_run.py``).

Usage:
    python scripts/merge_results.py data/benchmark/all52_results.jsonl data/benchmark/cypher_results.jsonl \\
        --output data/benchmark/final_results.jsonl
"""

import argparse
import json
from pathlib import Path

from football_graphrag.benchmark.arms import ARMS
from football_graphrag.benchmark.questions import ORDER
from football_graphrag.benchmark.summary import load_rows


def merge(paths: list[Path]) -> list[dict]:
    runs: dict[tuple, dict] = {}
    for path in paths:
        for row in load_rows(path):
            runs[(row["question_id"], row["arm"], int(row["repeat"]))] = row
    return sorted(runs.values(), key=lambda r: (int(r["repeat"]), ORDER.index(r["question_id"][0]),
                                                r["question_id"], ARMS.index(r["arm"])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    missing = [str(p) for p in args.results if not p.exists()]
    if missing:
        raise SystemExit(f"not found: {', '.join(missing)}")
    rows = merge(args.results)
    args.output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{len(rows)} runs from {len(args.results)} files -> {args.output}")

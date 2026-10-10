#!/usr/bin/env python
"""Write the page of a run in docs/execucoes/ from an existing results file, without calling any LLM.

``scripts/run_benchmark.py`` already does this at the end of every run; use this script
to write the page again, or for a results file from before the automatic pages.

Usage:
    python scripts/report_run.py --results data/benchmark/results.jsonl
    python scripts/report_run.py --results data/benchmark/x_results.jsonl --title "..." --cost 0.62
"""

import argparse
from pathlib import Path

from football_graphrag.benchmark.report import RunInfo, write_report
from football_graphrag.benchmark.summary import write_summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--title")
    parser.add_argument("--cost", type=float, help="real cost in US$, if known")
    parser.add_argument("--command", default="", help="the command that produced the results")
    parser.add_argument("--page", type=Path, help="rewrite this existing page instead of writing a new one")
    args = parser.parse_args()
    if not args.results.exists():
        raise SystemExit(f"{args.results} does not exist")
    summary = write_summary(args.results)
    info = RunInfo(command=args.command, cost_usd=args.cost)
    page = write_report(args.results, summary, info, args.title, page=args.page)
    print(f"written {page}")

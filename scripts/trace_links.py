#!/usr/bin/env python
"""Langfuse trace links for a results file, as a markdown table (question x arm).

New runs already store ``trace_url`` in each results.jsonl line. For runs made
before that, ``--write`` finds each trace in Langfuse by its span name
(``{question}/{arm}/r{n}``) and start time, and adds ``trace_url`` to the file.

Usage:
    python scripts/trace_links.py --results data/benchmark/results.jsonl
    python scripts/trace_links.py --results data/benchmark/results.jsonl --write

Needs the LANGFUSE_* keys. The links open in the Langfuse UI, which requires a
login to the project.
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from football_graphrag.benchmark.arms import ARMS
from football_graphrag.config import get_settings

MAX_GAP = timedelta(minutes=2)  # trace start vs. (row end time - latency)


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_traces(start: datetime, end: datetime) -> tuple[str, list[dict]]:
    s = get_settings()
    auth = (s.langfuse_public_key, s.langfuse_secret_key)
    project = httpx.get(f"{s.langfuse_host}/api/public/projects", auth=auth, timeout=30).json()["data"][0]["id"]
    traces, page = [], 1
    while True:
        r = httpx.get(
            f"{s.langfuse_host}/api/public/traces",
            params={"fromTimestamp": start.isoformat(), "toTimestamp": end.isoformat(), "limit": 100, "page": page},
            auth=auth, timeout=60,
        ).json()
        traces += r["data"]
        if page >= r["meta"]["totalPages"]:
            break
        page += 1
    return f"{s.langfuse_host}/project/{project}/traces/", traces


def add_trace_urls(rows: list[dict]) -> int:
    """Fill ``trace_url`` where missing. Returns how many were found."""
    missing = [r for r in rows if not r.get("trace_url")]
    if not missing:
        return 0
    starts = [_ts(r["timestamp"]) - timedelta(seconds=r["latency_s"]) for r in missing]
    base, traces = fetch_traces(min(starts) - MAX_GAP, max(_ts(r["timestamp"]) for r in missing) + MAX_GAP)
    by_name: dict[str, list[dict]] = {}
    for t in traces:
        by_name.setdefault(t["name"], []).append(t)
    found = 0
    for row, start in zip(missing, starts):
        candidates = by_name.get(f"{row['question_id']}/{row['arm']}/r{row['repeat']}", [])
        best = min(candidates, key=lambda t: abs(_ts(t["timestamp"]) - start), default=None)
        if best and abs(_ts(best["timestamp"]) - start) <= MAX_GAP:
            row["trace_url"] = base + best["id"]
            found += 1
    return found


def markdown_table(rows: list[dict]) -> str:
    arms = [a for a in ARMS if any(r["arm"] == a for r in rows)]
    order = "fascu"
    qids = sorted({r["question_id"] for r in rows}, key=lambda q: (order.index(q[0]), q))
    cell = {}
    for r in rows:
        mark = ("✅" if r["correct"] else "🟡" if r["abstention"] else "⚠️" if r["format_error"] else "❌")
        cell.setdefault((r["question_id"], r["arm"]), []).append(
            f"[{mark}]({r['trace_url']})" if r.get("trace_url") else mark
        )
    lines = ["| pergunta | " + " | ".join(f"`{a}`" for a in arms) + " |", "|---" * (len(arms) + 1) + "|"]
    for q in qids:
        lines.append(f"| {q} | " + " | ".join(" ".join(cell.get((q, a), ["–"])) for a in arms) + " |")
    lines.append("")
    lines.append("✅ certo · ❌ alucinação · 🟡 abstenção · ⚠️ erro de formato. Cada símbolo abre o trace no Langfuse.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--write", action="store_true", help="add the trace_url found to the results file")
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.results.read_text().splitlines() if line.strip()]
    found = add_trace_urls(rows)
    if args.write and found:
        args.results.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    linked = sum(bool(r.get("trace_url")) for r in rows)
    print(markdown_table(rows))
    print(f"\n<!-- {linked}/{len(rows)} runs linked; {found} found now{' and written' if args.write and found else ''} -->")


if __name__ == "__main__":
    main()

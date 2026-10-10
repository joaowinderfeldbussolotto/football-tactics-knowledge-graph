#!/usr/bin/env python
"""Draw the paper's figures from the versioned results, as vector PDF.

F2  the abstraction ladder: accuracy of the six arms in the order of how much of the query
    logic is ready before the model starts, with the Wilson interval;
F3  accuracy by question group, for the arms that are not zero everywhere;
F4  the tuning trajectory of graph_tools on fixed sets of questions, against the first-contact
    text_to_cypher.

The look follows paper/template.json (column width, text size, font): grey bars with a single
accent colour, text as large as the paper's, no colour needed to read it. Confirm the template
there before using the PDFs in the paper: with ``"confirmed": false`` this script warns.

Usage:
    python scripts/figures.py
    python scripts/figures.py --results data/benchmark/repeats_final_results.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from football_graphrag.benchmark import paper_stats as ps

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
OUT = PAPER / "generated" / "figures"
BENCH = ROOT / "data" / "benchmark"
GREY, DARK, ACCENT = "#BDBDBD", "#7F7F7F", "#1F5C99"
HIGHLIGHT = "graph_tools"
NAMES = {"no_context": "no_context", "vector": "vector", "events_in_prompt": "events_in_prompt",
         "text_to_cypher": "text_to_cypher", "graph_tools": "graph_tools", "stats_in_prompt": "stats_in_prompt"}


def style(template: dict):
    import matplotlib
    import matplotlib.pyplot

    matplotlib.use("Agg")
    size = float(template.get("text_font_pt", 10))
    matplotlib.rcParams.update({
        "font.family": "STIXGeneral", "mathtext.fontset": "stix",
        "font.size": size, "axes.labelsize": size, "axes.titlesize": size, "xtick.labelsize": size,
        "ytick.labelsize": size, "legend.fontsize": size,
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "axes.grid": False,
        "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    })
    return matplotlib.pyplot


def save(fig, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    fig.savefig(path, format="pdf", metadata={"CreationDate": None, "ModDate": None, "Producer": None})
    return path


def ladder(plt, rows, types, template) -> Path:
    arms = [a for a in ps.LADDER if any(r["arm"] == a for r in rows)]
    acc = [ps.accuracy(ps.select(ps.by_question(rows, a), types, answerable=True)) for a in arms]
    fig, ax = plt.subplots(figsize=(template["column_width_in"], 0.32 * len(arms) + 0.5))
    y = list(range(len(arms)))[::-1]
    colors = [ACCENT if a == HIGHLIGHT else GREY for a in arms]
    ax.barh(y, [100 * a.share for a in acc], color=colors, height=0.62)
    ax.errorbar([100 * a.share for a in acc], y, xerr=[[max(0.0, 100 * (a.share - a.low)) for a in acc], [max(0.0, 100 * (a.high - a.share)) for a in acc]],
                fmt="none", ecolor="black", elinewidth=0.7, capsize=2)
    ax.set_yticks(y, [NAMES[a] for a in arms])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Acerto nas perguntas com resposta (%)")
    ax.xaxis.grid(True, linewidth=0.3, color="#DDDDDD")
    ax.set_axisbelow(True)
    return save(fig, "f2_ladder.pdf")


def by_group(plt, rows, types, template) -> Path:
    arms = [a for a in ("vector", "events_in_prompt", "text_to_cypher", "graph_tools") if any(r["arm"] == a for r in rows)]
    groups = [g for g in ps.GROUP_KEYS if g != ps.CONTROL]
    shades = ["#E3E3E3", "#BDBDBD", "#8C8C8C", ACCENT]
    fig, ax = plt.subplots(figsize=(template["column_width_in"], 0.28 * len(groups) * len(arms) / 2 + 0.7))
    height = 0.8 / len(arms)
    for i, a in enumerate(arms):
        per_q = ps.by_question(rows, a)
        vals = [100 * ps.accuracy(ps.select(per_q, types, groups=(g,))).share for g in groups]
        ys = [j - 0.4 + height * (i + 0.5) for j in range(len(groups))][::-1]
        ax.barh(ys, vals, height=height * 0.92, color=shades[i % len(shades)] if a != HIGHLIGHT else ACCENT, label=NAMES[a])
    ax.set_yticks(list(range(len(groups)))[::-1], [_wrap(g) for g in groups])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Acerto (%)")
    ax.xaxis.grid(True, linewidth=0.3, color="#DDDDDD")
    ax.set_axisbelow(True)
    handles, labels = ax.get_legend_handles_labels()  # top-to-bottom order of the bars in each group
    ax.legend(handles[::-1], labels[::-1], frameon=False, loc="lower center", bbox_to_anchor=(0.45, 1.0),
              ncol=2, handlelength=1.0, columnspacing=1.0)
    return save(fig, "f3_groups.pdf")


def _wrap(text: str, width: int = 22) -> str:
    words, lines, line = text.split(), [], ""
    for w in words:
        if len(line) + len(w) + 1 > width and line:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    return "\n".join(lines + [line])


def trajectory(plt, rows, template) -> Path | None:
    cfg = yaml.safe_load((PAPER / "data" / "trajectory.yaml").read_text(encoding="utf-8"))["series"]
    series = []
    for s in cfg:
        try:
            series.append((s, ps.trajectory(s, BENCH, rows)))
        except FileNotFoundError as exc:
            print(f"trajectory: {s['key']} skipped, file not found: {exc.filename}", file=sys.stderr)
    if not series:
        return None
    width = float(template.get("text_width_in", template["column_width_in"] * 2))
    fig, axes = plt.subplots(1, len(series), figsize=(width, 2.0), sharey=True)
    axes = [axes] if len(series) == 1 else list(axes)
    for ax, (s, points) in zip(axes, series):
        main = [p for p in points if not p.get("reference")]
        ref = next((p for p in points if p.get("reference")), None)
        x = list(range(len(main)))
        ax.fill_between(x, [100 * p["low"] for p in main], [100 * p["high"] for p in main], color="#E3E3E3", linewidth=0)
        ax.plot(x, [100 * p["share"] for p in main], color=ACCENT, marker="o", markersize=3.5, linewidth=1.2)
        if ref:
            ax.axhline(100 * ref["share"], color="black", linestyle="--", linewidth=0.8)
            ax.text(len(main) - 1, 100 * ref["share"] - 4, NAMES[ref["label"]], ha="right", va="top")
        ax.set_xticks(x, [p["label"] for p in main])
        ax.set_title(f"{s['name']} ($n={main[0]['n']}$)")
        ax.set_ylim(0, 100)
        ax.yaxis.grid(True, linewidth=0.3, color="#DDDDDD")
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Acerto do graph_tools (%)")
    fig.tight_layout()
    return save(fig, "f4_trajectory.pdf")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=BENCH / "final_results.jsonl")
    args = parser.parse_args()
    template = json.loads((PAPER / "template.json").read_text(encoding="utf-8"))
    if not template.get("confirmed"):
        print("warning: paper/template.json is not confirmed; widths and font are placeholders", file=sys.stderr)
    rows = ps.load(args.results)
    types = ps.question_types(rows)
    plt = style(template)
    made = [ladder(plt, rows, types, template), by_group(plt, rows, types, template), trajectory(plt, rows, template)]
    for path in filter(None, made):
        print(f"written {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

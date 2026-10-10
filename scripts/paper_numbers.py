#!/usr/bin/env python
"""Regenerate paper/generated/ (numbers.tex, tables/) from the versioned results files.

Every number the paper states is a LaTeX macro defined in ``numbers.tex``; the text never has
a typed digit (``paper/scripts/lint_paper.py`` fails if it does). Run this again after any
change to a results file, and the whole paper follows.

The default input is data/benchmark/final_results.jsonl (one repeat of 52 questions x 6 arms).
After the repeats round, point ``--results`` at the merged file (see paper/README.md).

Usage:
    python scripts/paper_numbers.py
    python scripts/paper_numbers.py --results data/benchmark/repeats_final_results.jsonl
    python scripts/paper_numbers.py --check      # fail if paper/generated/ is out of date
"""

import argparse
import difflib
import sys
from pathlib import Path

import yaml

from football_graphrag.benchmark import paper_stats as ps
from football_graphrag.benchmark.questions import GROUPS

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "benchmark"
PAPER = ROOT / "paper"
GENERATED = PAPER / "generated"
# Pairs of neighbouring steps of the ladder, in the order of the paper's table.
PAIRS = (("text_to_cypher", "events_in_prompt"), ("graph_tools", "text_to_cypher"), ("graph_tools", "events_in_prompt"))
# Display names of the arms in the paper: (full, short for table headers). The code identifiers do not change.
ARM_NAMES = {
    "no_context": ("Sem dados", "Sem dados"),
    "vector": ("Busca vetorial", "Vetorial"),
    "events_in_prompt": ("Eventos brutos", "Eventos"),
    "stats_in_prompt": ("Estatísticas resumidas", "Estatísticas"),
    "text_to_cypher": ("Consulta escrita pelo modelo", "Consulta"),
    "graph_tools": ("Ferramentas sobre o grafo", "Ferramentas"),
}
# Group labels in the order of the paper.
GROUP_ORDER = tuple(GROUPS)


# --------------------------------------------------------------------------- formatting (pt-BR)

def num(x: float, decimals: int = 0) -> str:
    """Brazilian format: thousands with a point, decimals with a comma."""
    if decimals == 0 and abs(x - round(x)) > 1e-9:
        decimals = 1
    text = f"{x:,.{decimals}f}"
    return text.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")


def pct(share: float) -> str:
    return f"{round(100 * share)}\\%"


def p_value(p: float) -> str:
    return "menor que 0,001" if p < 0.001 else num(p, 3)


def macro(name: str, value: str) -> str:
    return f"\\newcommand{{\\{name}}}{{{value}}}"


# --------------------------------------------------------------------------- numbers

def build(results: Path) -> tuple[dict[str, str], dict[str, str]]:
    """The macros (name -> value) and the table fragments (file name -> LaTeX)."""
    rows = ps.load(results)
    types = ps.question_types(rows)
    arms = [a for a in ps.LADDER if any(r["arm"] == a for r in rows)]
    n_repeats = max(int(r["repeat"]) for r in rows)
    answerable = {q for q, t in types.items() if t != "unanswerable"}
    m: dict[str, str] = {
        "nQuestions": str(len(types)), "nAnswerable": str(len(answerable)),
        "nControl": str(len(types) - len(answerable)), "nArms": str(len(arms)), "nRuns": str(len(rows)),
        "nRepeats": str(n_repeats),
        "modelName": "Claude Haiku 5.5",
    }
    for a, (full, short) in ARM_NAMES.items():  # the names the paper uses; the identifiers stay in the code
        m[f"arm{ps.ARM_KEYS[a]}"], m[f"armShort{ps.ARM_KEYS[a]}"] = full, short
    for g in GROUP_ORDER:
        m[f"nGroup{ps.GROUP_KEYS[g]}"] = str(len({q for q, t in types.items() if ps.GROUP_OF_TYPE[t] == g}))

    per_arm = {a: ps.by_question(rows, a) for a in arms}
    for a in arms:
        k = ps.ARM_KEYS[a]
        acc = ps.accuracy(ps.select(per_arm[a], types, answerable=True))
        every = ps.accuracy(per_arm[a])
        m[f"acc{k}"], m[f"k{k}"] = pct(acc.share), num(acc.correct, 1 if acc.correct != int(acc.correct) else 0)
        m[f"ciLow{k}"], m[f"ciHigh{k}"] = num(round(100 * acc.low)), num(round(100 * acc.high))
        m[f"accAll{k}"], m[f"kAll{k}"] = pct(every.share), num(every.correct, 1 if every.correct != int(every.correct) else 0)
        c = ps.cost_profile(rows, a)
        m[f"hall{k}"], m[f"abst{k}"], m[f"fmt{k}"] = pct(c["hallucination"]), pct(c["abstention"]), pct(c["format_error"])
        m[f"tokIn{k}"], m[f"tokOut{k}"] = num(round(c["tokens_in"])), num(round(c["tokens_out"]))
        m[f"calls{k}"], m[f"lat{k}"] = num(c["calls"], 1), num(c["latency"], 1)
        m[f"rep{k}"] = str(max(r.repeats for r in per_arm[a].values()))
        for g in GROUP_ORDER:
            sel = ps.select(per_arm[a], types, groups=(g,))
            if sel:
                gk = ps.GROUP_KEYS[g]
                ga = ps.accuracy(sel)
                m[f"acc{gk}{k}"] = pct(ga.share)
                m[f"k{gk}{k}"] = num(ga.correct, 1 if ga.correct != int(ga.correct) else 0)

    pair_rows = []
    for first, second in PAIRS:
        if first in per_arm and second in per_arm:
            x, y, p = ps.pair_counts(ps.select(per_arm[first], types, answerable=True),
                                     ps.select(per_arm[second], types, answerable=True))
            pair_rows.append((first, second, x, y, p))
    adjusted = ps.holm([r[4] for r in pair_rows])
    pair_rows = [r + (adj,) for r, adj in zip(pair_rows, adjusted)]
    for first, second, x, y, p, adj in pair_rows:
        key = f"mc{ps.ARM_KEYS[first]}{ps.ARM_KEYS[second]}"
        m[f"{key}First"], m[f"{key}Second"] = str(x), str(y)
        m[f"{key}P"], m[f"{key}PHolm"] = p_value(p), p_value(adj)

    # the graph_tools before the fixes of the last round (execution 12), kept as it was measured
    before = BENCH / "all52_before_fixes_results.jsonl"
    if before.exists():
        b = ps.by_question(ps.load(before), "graph_tools")
        m["preFixKGraphTools"], m["preFixNGraphTools"] = num(sum(r.share for r in b.values())), str(len(b))

    costs = yaml.safe_load((PAPER / "data" / "costs.yaml").read_text(encoding="utf-8"))["rounds"]
    for name, info in costs.items():
        if info.get("usd") is not None:
            m[f"cost{name.capitalize()}"] = num(info["usd"], 2)

    tables = {
        "groups.tex": groups_table(per_arm, types, arms),
        "mcnemar.tex": mcnemar_table(pair_rows, m),
        "cost.tex": cost_table(rows, arms),
        "ladder.tex": ladder_table(per_arm, types, arms),
    }
    return m, tables


# --------------------------------------------------------------------------- tables

LABEL = {arm: short for arm, (_, short) in ARM_NAMES.items()}  # short names: the columns are narrow


def _tabular(spec: str, header: list[str], body: list[list[str]]) -> str:
    lines = [f"\\begin{{tabular}}{{{spec}}}", "\\toprule", " & ".join(header) + r" \\", "\\midrule"]
    lines += [" & ".join(r) + r" \\" for r in body]
    lines += ["\\bottomrule", "\\end{tabular}", ""]
    return "\n".join(lines)


def ladder_table(per_arm, types, arms) -> str:
    body = []
    for a in arms:
        acc = ps.accuracy(ps.select(per_arm[a], types, answerable=True))
        body.append([LABEL[a], f"{num(acc.correct)}/{acc.n}", pct(acc.share), f"{round(100 * acc.low)} a {round(100 * acc.high)}"])
    return _tabular("lrrr", ["Braço", "Acertos", "Acerto", "IC 95\\%"], body)


def groups_table(per_arm, types, arms) -> str:
    body = []
    for g in GROUP_ORDER:
        cells = [g]
        n = None
        for a in arms:
            sel = ps.select(per_arm[a], types, groups=(g,))
            n = len(sel)
            cells.append(f"{num(ps.accuracy(sel).correct)}")
        body.append([cells[0], str(n)] + cells[1:])
    header = ["Grupo", "$n$"] + [LABEL[a] for a in arms]
    return _tabular("l" + "r" * (len(arms) + 1), header, body)


def mcnemar_table(pair_rows, m) -> str:
    body = [[f"{LABEL[a]} contra {LABEL[b]}", str(x), str(y), p_value(p), p_value(adj)] for a, b, x, y, p, adj in pair_rows]
    return _tabular("lrrrr", ["Par", "Só o primeiro", "Só o segundo", "$p$", "$p$ (Holm)"], body)


def cost_table(rows, arms) -> str:
    body = []
    for a in arms:
        c = ps.cost_profile(rows, a)
        body.append([LABEL[a], pct(c["hallucination"]), pct(c["abstention"]), num(round(c["tokens_in"])),
                     num(c["calls"], 1), f"{num(c['latency'], 1)}"])
    return _tabular("lrrrrr", ["Braço", "Alucinação", "Abstenção", "Tokens de entrada", "Chamadas", "Latência (s)"], body)


# --------------------------------------------------------------------------- output

HEADER = ("% Generated by scripts/paper_numbers.py from {src}. Do not edit by hand.\n"
          "% Every number in the paper text is one of these macros.\n")


def render(macros: dict[str, str], src: str) -> str:
    return HEADER.format(src=src) + "\n".join(macro(k, v) for k, v in sorted(macros.items())) + "\n"


def files(results: Path) -> dict[Path, str]:
    macros, tables = build(results)
    try:
        src = str(results.resolve().relative_to(ROOT))
    except ValueError:
        src = str(results)
    out = {GENERATED / "numbers.tex": render(macros, src)}
    out.update({GENERATED / "tables" / name: text for name, text in tables.items()})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=BENCH / "final_results.jsonl")
    parser.add_argument("--check", action="store_true", help="fail if paper/generated/ differs from a fresh build")
    args = parser.parse_args()
    built = files(args.results)
    if args.check:
        stale = [p for p, text in built.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        for p in stale:
            old = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
            diff = difflib.unified_diff(old, built[p].splitlines(), str(p.relative_to(ROOT)), "regenerated", lineterm="", n=0)
            print("\n".join(list(diff)[:12]))
        print(f"{len(stale)} of {len(built)} generated files are out of date" if stale else "paper/generated/ is up to date")
        return 1 if stale else 0
    for path, text in built.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"written {len(built)} files in {GENERATED.relative_to(ROOT)}/ from {args.results.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
import statistics
import difflib
import sys
from pathlib import Path

import yaml

from football_graphrag.benchmark import arms as arm_defs
from football_graphrag.benchmark import cypher
from football_graphrag.config import Settings
from football_graphrag.benchmark import paper_stats as ps
from football_graphrag.benchmark.questions import GROUPS, QUESTIONS

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "benchmark"
PAPER = ROOT / "paper"
GENERATED = PAPER / "generated"
# The three comparisons of the paper, in the order of its table.
PAIRS = (("text_to_cypher", "events_in_prompt"), ("graph_tools", "text_to_cypher"), ("graph_tools", "events_in_prompt"))
# The match data (paper/ALERTAS.md, checked on 10/10/2026 against the StatsBomb file and the Parquet table).
N_RAW_EVENTS, N_ACTIONS = 4407, 2585
# Nodes of the match graph (docs/02-dos-dados-ao-grafo.md, counted in Neo4j for the final).
N_PLAYERS, N_PHASES, N_ZONES = 34, 537, 96
ARM_NAMES = ps.ARM_NAMES
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
    }
    m.update({
        "nEvents": num(N_RAW_EVENTS), "nActions": num(N_ACTIONS),
        "nPlayers": str(N_PLAYERS), "nPhases": str(N_PHASES), "nZones": str(N_ZONES),
        "nMaxCalls": str(arm_defs.MAX_TOOL_CALLS), "nTopK": str(arm_defs.VECTOR_TOP_K), "nTools": str(len(arm_defs.TOOLS)),
        "nMaxRows": str(cypher.MAX_ROWS),
        "nMaxOutTokens": f"{Settings.model_fields['llm_max_tokens'].default // 1000} mil",
        "nCheckPlayer": str(sum(q.check == "player" for q in QUESTIONS)),
        "nCheckSet": str(sum(q.check == "set" for q in QUESTIONS)),
        "nCheckValue": str(sum(q.check in ("value", "player_and_value") for q in QUESTIONS)),
        "nCheckNoData": str(sum(q.check == "no_data" for q in QUESTIONS)), "tokTableApprox": "cerca de 100 mil tokens", "ciLevel": "95\\%",
    })
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

    models = load_models()
    m.update(model_macros(models))
    m.update(tier_ranges(models))

    tables = {
        "models.tex": models_table(models),
        "fig_models.tex": models_figure(models),
        "groups_models.tex": models_groups_table(models),
        "cost_models.tex": models_cost_table(models),
        "mcnemar_models.tex": models_mcnemar_table(models),
        "errors_models.tex": models_errors_table(models),
        "groups.tex": groups_table(per_arm, types, arms),
        "mcnemar.tex": mcnemar_table(pair_rows, m),
        "cost.tex": cost_table(rows, arms),
        "ladder.tex": ladder_table(per_arm, types, arms),
    }
    return m, tables


# --------------------------------------------------------------------------- models

def load_models() -> list[dict]:
    """The models of paper/data/models.yaml with their rows; the first is the main one."""
    spec = yaml.safe_load((PAPER / "data" / "models.yaml").read_text(encoding="utf-8"))["models"]
    out = []
    for entry in spec:
        rows = ps.load(ROOT / entry["results"])
        types = ps.question_types(rows)
        arms = [a for a in ps.LADDER if any(r["arm"] == a for r in rows)]
        out.append({**entry, "rows": rows, "types": types, "arms": arms,
                    "per_arm": {a: ps.by_question(rows, a) for a in arms}})
    return out


def model_pairs(model: dict) -> list[tuple]:
    """The comparisons of PAIRS for one model: (first, second, only first, only second, p, p Holm)."""
    per_arm, types = model["per_arm"], model["types"]
    found = [(a, b) + ps.pair_counts(ps.select(per_arm[a], types, answerable=True),
                                    ps.select(per_arm[b], types, answerable=True))
             for a, b in PAIRS if a in per_arm and b in per_arm]
    return [r + (adj,) for r, adj in zip(found, ps.holm([r[4] for r in found]))]


def model_macros(models: list[dict]) -> dict[str, str]:
    names = [md["name"] for md in models]
    m = {"nModels": str(len(models)), "nModelsLow": str(sum(md.get("tier") == "baixo" for md in models)),
         "nModelsHigh": str(sum(md.get("tier") == "alto" for md in models)),
         "modelList": names[0] if len(names) == 1 else ", ".join(names[:-1]) + " e " + names[-1]}
    for md in models:
        key, per_arm, types = md["key"], md["per_arm"], md["types"]
        m[f"model{key}"] = md["name"]
        if md.get("usd") is not None:
            m[f"cost{key}"] = num(md["usd"], 2)
        for a in md["arms"]:
            k = key + ps.ARM_KEYS[a]
            acc = ps.accuracy(ps.select(per_arm[a], types, answerable=True))
            every = ps.accuracy(per_arm[a])
            control = ps.accuracy(ps.select(per_arm[a], types, groups=(ps.CONTROL,)))
            m[f"acc{k}"], m[f"k{k}"] = pct(acc.share), num(acc.correct)
            m[f"ciLow{k}"], m[f"ciHigh{k}"] = num(round(100 * acc.low)), num(round(100 * acc.high))
            m[f"accAll{k}"], m[f"accControl{k}"] = pct(every.share), pct(control.share)
            c = ps.cost_profile(md["rows"], a)
            m[f"hall{k}"], m[f"abst{k}"], m[f"fmt{k}"] = pct(c["hallucination"]), pct(c["abstention"]), pct(c["format_error"])
            m[f"tokIn{k}"], m[f"calls{k}"], m[f"lat{k}"] = num(round(c["tokens_in"])), num(c["calls"], 1), num(c["latency"], 1)
        for a, b, x, y, p, adj in model_pairs(md):
            pk = f"mc{key}{ps.ARM_KEYS[a]}{ps.ARM_KEYS[b]}"
            m[f"{pk}First"], m[f"{pk}Second"], m[f"{pk}P"], m[f"{pk}PHolm"] = str(x), str(y), p_value(p), p_value(adj)
    return m


def models_table(models: list[dict]) -> str:
    """Accuracy (%) on the answerable questions, one column per model (the intervals are in the figure and the macros)."""
    body = []
    for a in ps.LADDER:
        cells = [LABEL[a]]
        for md in models:
            if a not in md["per_arm"]:
                cells.append("--")
                continue
            acc = ps.accuracy(ps.select(md["per_arm"][a], md["types"], answerable=True))
            cells.append(str(round(100 * acc.share)))
        body.append(cells)
    return _tabular("l" + "r" * len(models), ["Abordagem"] + [md["short"] for md in models], body)


def p_cell(p: float) -> str:
    """A p value in a narrow table cell."""
    return "$<$0,001" if p < 0.001 else num(p, 3)


def models_mcnemar_table(models: list[dict]) -> str:
    """The comparisons of PAIRS, one block of rows per model."""
    lines = ["\\begin{tabular}{lrrr}", "\\toprule", r"Par (A contra B) & Só A & Só B & $p$ (Holm) \\"]
    for md in models:
        lines += ["\\midrule", f"\\multicolumn{{4}}{{l}}{{\\textit{{{md['name']}}}}} \\\\"]
        for a, b, x, y, p, adj in model_pairs(md):
            lines.append(" & ".join([f"{LABEL[a]} contra {LABEL[b]}", str(x), str(y), p_cell(adj)]) + r" \\")
    lines += ["\\bottomrule", "\\end{tabular}", ""]
    return "\n".join(lines)


def models_errors_table(models: list[dict]) -> str:
    """Error profile and cost per execution of the three data approaches, one block of rows per model.

    Tokens are in thousands; the money cost is left out on purpose (prices change, tokens and latency do not)."""
    lines = ["\\begin{tabular}{lrrrrrr}", "\\toprule",
             r"Abordagem & Aluc. & Abst. & Form. & Entrada & Saída & Lat. \\"]
    for md in models:
        lines += ["\\midrule", f"\\multicolumn{{7}}{{l}}{{\\textit{{{md['name']}}}}} \\\\"]
        for a in DATA_ARMS:
            c = ps.cost_profile(md["rows"], a)
            lines.append(" & ".join([LABEL[a], pct(c["hallucination"]), pct(c["abstention"]), pct(c["format_error"]),
                                     num(c["tokens_in"] / 1000, 1), num(c["tokens_out"] / 1000, 1),
                                     num(c["latency"], 1)]) + r" \\")
    lines += ["\\bottomrule", "\\end{tabular}", ""]
    return "\n".join(lines)


def median_profile(rows: list[dict], arm: str) -> dict[str, float]:
    """Medians per execution: a few questions with many tool calls pull the agents' means far up (each call sends
    the whole conversation again), so the table and its ranges show the typical question."""
    rs = [r for r in rows if r["arm"] == arm]
    return {"tokens_in": statistics.median(r["input_tokens"] for r in rs),
            "tokens_out": statistics.median(r["output_tokens"] for r in rs),
            "latency": statistics.median(r["latency_s"] for r in rs)}


def models_cost_table(models: list[dict]) -> str:
    """Medians per execution of input and output tokens (thousands) and latency (s) of the three data approaches:
    one column per model, one block per measure. Input tokens include the ones read from the prompt cache."""
    lines = ["\\begin{tabular}{l" + "r" * len(models) + "}", "\\toprule",
             "Abordagem & " + " & ".join(md["short"] for md in models) + r" \\"]
    for title, key, fmt in (("Tokens de entrada (mil)", "tokens_in", lambda x: num(round(x / 1000))),
                            ("Tokens de saída (mil)", "tokens_out", lambda x: num(x / 1000, 1)),
                            ("Latência (s)", "latency", lambda x: num(round(x)))):
        lines += ["\\midrule", f"\\multicolumn{{{len(models) + 1}}}{{l}}{{\\textit{{{title}}}}} \\\\"]
        for a in DATA_ARMS:
            lines.append(" & ".join([LABEL[a]] + [fmt(median_profile(md["rows"], a)[key]) for md in models]) + r" \\")
    lines += ["\\bottomrule", "\\end{tabular}", ""]
    return "\n".join(lines)


def models_groups_table(models: list[dict]) -> str:
    """Correct answers per group of answerable questions: one column per model, each cell the three data
    approaches in the order of DATA_ARMS."""
    body = []
    for g in GROUP_ORDER:
        if g == ps.CONTROL:
            continue
        cells, n = [GROUP_SHORT[g]], None
        for md in models:
            counts = []
            for a in DATA_ARMS:
                sel = ps.select(md["per_arm"][a], md["types"], groups=(g,))
                n = len(sel)
                counts.append(num(ps.accuracy(sel).correct))
            cells.append("/".join(counts))
        body.append([cells[0], str(n)] + cells[1:])
    return _tabular("lr" + "c" * len(models), ["Grupo", "$n$"] + [md["short"] for md in models], body)


# The three approaches that read the match data, in the order of the figure and of the cells "a/b/c".
DATA_ARMS = ("events_in_prompt", "text_to_cypher", "graph_tools")


def models_figure(models: list[dict]) -> str:
    """Lines: accuracy of the three data approaches in each model, low price tier first, with the Wilson
    interval; the high price tier is shaded."""
    styles = {"events_in_prompt": "black!45, thick, mark=square*, mark options={fill=black!25}",
              "text_to_cypher": "black!80, thick, mark=triangle*, mark options={fill=black!60}",
              "graph_tools": "accent, very thick, mark=*"}
    coords = ",".join(md["short"] for md in models)
    high = [md["short"] for md in models if md.get("tier") == "alto"]
    lines = ["\\definecolor{accent}{HTML}{1F5C99}", "\\begin{tikzpicture}", "\\begin{axis}[",
             "  width=0.97\\columnwidth, height=5.2cm, ymin=0, ymax=100, clip=false,",
             f"  symbolic x coords={{{coords}}}, xtick=data, enlarge x limits={{abs=26pt}},",
             "  ylabel={Acerto (\\%)}, ytick={0,25,50,75,100}, axis x line*=bottom, axis y line*=left,",
             "  tick label style={font=\\small}, label style={font=\\small}, legend style={font=\\footnotesize, draw=none,",
             "  fill=none, at={(0.5,1.03)}, anchor=south, legend columns=-1,",
             "  /tikz/every even column/.append style={column sep=3pt}},",
             "  error bars/y dir=both, error bars/y explicit, error bars/error bar style={line width=0.4pt},",
             "]"]
    if high:
        lines.append(f"\\fill[black!6] ([xshift=-16pt]axis cs:{high[0]},0) rectangle ([xshift=16pt]axis cs:{high[-1]},100);")
        lines.append(f"\\node[font=\\footnotesize, black!60, anchor=south] at ([xshift=24pt]axis cs:{high[0]},2) {{modelos maiores}};")
    for a in DATA_ARMS:
        pts = []
        for md in models:
            acc = ps.accuracy(ps.select(md["per_arm"][a], md["types"], answerable=True))
            v, lo, hi = 100 * acc.share, 100 * acc.low, 100 * acc.high
            pts.append(f"({md['short']},{v:.1f}) += (0,{hi - v:.1f}) -= (0,{v - lo:.1f})")
        lines.append(f"\\addplot[{styles[a]}] coordinates {{{' '.join(pts)}}};")
    lines.append("\\legend{" + ",".join(ARM_NAMES[a][1] for a in DATA_ARMS) + "}")
    lines += ["\\end{axis}", "\\end{tikzpicture}", ""]
    return "\n".join(lines)


def tier_ranges(models: list[dict]) -> dict[str, str]:
    """Ranges across models ("83\\% a 89\\%"), overall and per price tier, for the text."""
    m = {}

    def rng(values: list[float], fmt) -> str:
        lo, hi = min(values), max(values)
        return fmt(lo) if fmt(lo) == fmt(hi) else f"{fmt(lo)} a {fmt(hi)}"

    others = [ps.accuracy(ps.select(md["per_arm"][a], md["types"], answerable=True)).share
              for md in models for a in ps.LADDER if a not in DATA_ARMS and a in md["per_arm"]]
    m["accMaxOthers"] = pct(max(others))  # the best of no_context, stats_in_prompt and vector in any model
    tiers = {"": models, "Low": [md for md in models if md.get("tier") == "baixo"],
             "High": [md for md in models if md.get("tier") == "alto"]}
    for a in ps.LADDER:
        k = ps.ARM_KEYS[a]
        for tk, ms in tiers.items():
            ms = [md for md in ms if a in md["per_arm"]]
            if not ms:
                continue
            accs = [ps.accuracy(ps.select(md["per_arm"][a], md["types"], answerable=True)).share for md in ms]
            costs = [median_profile(md["rows"], a) for md in ms]  # medians, as in the cost table
            m[f"accRange{tk}{k}"] = rng(accs, pct)
            m[f"outRange{tk}{k}"] = rng([c["tokens_out"] for c in costs], lambda x: num(round(x)))
            m[f"inRange{tk}{k}"] = rng([c["tokens_in"] / 1000 for c in costs], lambda x: num(round(x)))
            m[f"latRange{tk}{k}"] = rng([c["latency"] for c in costs], lambda x: num(round(x)))
            m[f"abstRange{tk}{k}"] = rng([ps.cost_profile(md["rows"], a)["abstention"] for md in ms], pct)
    return m


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
    return _tabular("lrrr", ["Abordagem", "Acertos", "Acerto", "IC 95\\%"], body)


# Short group names for the table by group (the caption spells them out); its approach columns are rotated.
GROUP_SHORT = {"Busca e contagem": "Busca", "Relações na rede de passes": "Relações", "Jogadas e sequências": "Jogadas",
               "Antes e depois de um momento do jogo": "Momento", ps.CONTROL: "Controle"}


def groups_table(per_arm, types, arms) -> str:
    body = []
    for g in GROUP_ORDER:
        cells = [GROUP_SHORT[g]]
        n = None
        for a in arms:
            sel = ps.select(per_arm[a], types, groups=(g,))
            n = len(sel)
            cells.append(f"{num(ps.accuracy(sel).correct)}")
        body.append([cells[0], str(n)] + cells[1:])
    header = ["Grupo", "$n$"] + [f"\\rotatebox{{90}}{{{LABEL[a]}}}" for a in arms]
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
    return _tabular("lrrrrr", ["Abordagem", "Alucinação", "Abstenção", "Tokens de entrada", "Chamadas", "Latência (s)"], body)


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

"""Numbers for the paper, as a pure function of the versioned results files.

Nothing here calls a model or Neo4j. ``scripts/paper_numbers.py`` turns these functions into
``paper/generated/numbers.tex`` and the tables; ``scripts/figures.py`` draws the figures.

Statistical choices (they are choices; the paper must say them):

- The unit is the QUESTION, not the run. With R repeats an arm's result on a question is the
  share of repeats it got right. With one repeat that share is 0 or 1.
- Accuracy of an arm = mean of those shares over the questions. With the same number of repeats
  for every question this equals the share of runs.
- Confidence interval: Wilson, with n = number of questions and the mean share as the
  proportion. With one repeat this is the usual Wilson interval. With repeats it treats the
  question as the sample unit, so the repeats do not make the interval narrower than the
  number of questions allows.
- Paired comparison of two arms: exact McNemar test (two-sided binomial on the discordant
  questions). A question counts as correct for an arm when it was right in more than half of
  that arm's repeats.
- Questions without an answer in the data (the control group) are reported apart: an arm that
  always says "no data" gets all of them right.
"""

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from football_graphrag.benchmark.arms import ARMS
from football_graphrag.benchmark.questions import GROUPS

CONTROL = "Controle: sem resposta"
# Arms in the order of the abstraction ladder: how much of the query logic is ready before the
# model starts (nothing, retrieved lines, the whole match, the model's own queries, ready tools,
# fixed aggregates).
LADDER = ("no_context", "vector", "events_in_prompt", "text_to_cypher", "graph_tools", "stats_in_prompt")
# Macro-safe names (LaTeX control sequences have letters only).
ARM_KEYS = {"no_context": "NoContext", "vector": "Vector", "events_in_prompt": "EventsInPrompt",
            "stats_in_prompt": "StatsInPrompt", "graph_tools": "GraphTools", "text_to_cypher": "TextToCypher"}
GROUP_KEYS = {"Busca e contagem": "Search", "Relações na rede de passes": "Relations",
              "Jogadas e sequências": "Plays", "Antes e depois de um momento do jogo": "Moments",
              CONTROL: "Control"}
assert set(LADDER) == set(ARMS) and set(GROUP_KEYS) == set(GROUPS)
GROUP_OF_TYPE = {t: g for g, types in GROUPS.items() for t in types}


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def verdict(row: dict) -> str:
    if row["correct"]:
        return "ok"
    return "format_error" if row["format_error"] else "abstention" if row["abstention"] else "hallucination"


# --------------------------------------------------------------------------- intervals and tests

def wilson(k: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion k/n (k may be fractional: see the module note)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    low = 0.0 if k <= 0 else max(0.0, (centre - half) / denom)  # exactly 0 and 1 at the extremes
    high = 1.0 if k >= n else min(1.0, (centre + half) / denom)
    return low, high


def mcnemar_exact(only_first: int, only_second: int) -> float:
    """Two-sided exact McNemar p: binomial(only_first + only_second, 1/2) on the discordant pairs."""
    n = only_first + only_second
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(only_first, only_second) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def holm(pvalues: list[float]) -> list[float]:
    """Holm-adjusted p-values (step-down), in the order given. Three pairwise tests are reported,
    so the adjusted value is the one to read against 0.05."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted, running = [0.0] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


# --------------------------------------------------------------------------- per question

@dataclass(frozen=True)
class Result:
    """One arm on one question: the share of repeats right, and how many repeats."""
    share: float
    repeats: int

    @property
    def majority(self) -> bool:
        return self.share > 0.5


def by_question(rows: list[dict], arm: str) -> dict[str, Result]:
    runs = defaultdict(list)
    for r in rows:
        if r["arm"] == arm:
            runs[r["question_id"]].append(bool(r["correct"]))
    return {q: Result(sum(v) / len(v), len(v)) for q, v in runs.items()}


def question_types(rows: list[dict]) -> dict[str, str]:
    return {r["question_id"]: r["type"] for r in rows}


def select(results: dict[str, Result], types: dict[str, str], groups: tuple[str, ...] | None = None,
           answerable: bool = False, questions: set[str] | None = None) -> dict[str, Result]:
    out = {}
    for q, res in results.items():
        if questions is not None and q not in questions:
            continue
        if answerable and types[q] == "unanswerable":
            continue
        if groups is not None and GROUP_OF_TYPE[types[q]] not in groups:
            continue
        out[q] = res
    return out


@dataclass(frozen=True)
class Accuracy:
    correct: float  # sum of shares; an integer with one repeat
    n: int  # questions
    low: float
    high: float

    @property
    def share(self) -> float:
        return self.correct / self.n if self.n else 0.0


def accuracy(results: dict[str, Result]) -> Accuracy:
    k, n = sum(r.share for r in results.values()), len(results)
    low, high = wilson(k, n)
    return Accuracy(k, n, low, high)


def pair_counts(a: dict[str, Result], b: dict[str, Result]) -> tuple[int, int, float]:
    """Questions only ``a`` got right, only ``b`` got right, exact McNemar p."""
    shared = a.keys() & b.keys()
    only_a = sum(a[q].majority and not b[q].majority for q in shared)
    only_b = sum(b[q].majority and not a[q].majority for q in shared)
    return only_a, only_b, mcnemar_exact(only_a, only_b)


# --------------------------------------------------------------------------- tables

def cost_profile(rows: list[dict], arm: str) -> dict[str, float]:
    rs = [r for r in rows if r["arm"] == arm]
    kinds = [verdict(r) for r in rs]
    n = len(rs)
    return {
        "hallucination": kinds.count("hallucination") / n, "abstention": kinds.count("abstention") / n,
        "format_error": kinds.count("format_error") / n,
        "tokens_in": sum(r["input_tokens"] for r in rs) / n, "tokens_out": sum(r["output_tokens"] for r in rs) / n,
        "calls": sum(r["n_tool_calls"] for r in rs) / n, "latency": sum(r["latency_s"] for r in rs) / n,
    }


def only_arm_right(rows: list[dict], arm: str, others: tuple[str, ...]) -> list[str]:
    mine = by_question(rows, arm)
    theirs = [by_question(rows, o) for o in others]
    return sorted(q for q, res in mine.items()
                  if res.majority and not any(o.get(q, Result(0, 0)).majority for o in theirs))


# --------------------------------------------------------------------------- trajectory

def trajectory(series: dict, base: Path, reference_rows: list[dict] | None = None) -> list[dict]:
    """Accuracy of an arm across versions on a FIXED set of questions per series.

    ``series``: {"name", "arm", "points": [{"label", "file", "repeat"?}]}. The questions are those
    present in every file of the series, so each point is comparable with the next. Results are
    the verdicts stored when each run was scored (the scoring rules changed after some of them).
    """
    arm = series.get("arm", "graph_tools")
    loaded = []
    for point in series["points"]:
        rows = load(base / point["file"])
        if "repeat" in point:
            rows = [r for r in rows if int(r["repeat"]) == int(point["repeat"])]
        loaded.append((point["label"], by_question(rows, arm), rows))
    common = set.intersection(*(set(res) for _, res, _ in loaded))
    types = question_types(loaded[-1][2])
    common = {q for q in common if types.get(q) != "unanswerable"}
    out = [{"label": label, "n": len(common), **_acc(res, common)} for label, res, _ in loaded]
    if series.get("reference_arm") and reference_rows is not None:
        ref = by_question(reference_rows, series["reference_arm"])
        out.append({"label": series["reference_arm"], "n": len(common), "reference": True, **_acc(ref, common)})
    return out


def _acc(results: dict[str, Result], questions: set[str]) -> dict:
    a = accuracy({q: results[q] for q in questions})
    return {"correct": a.correct, "low": a.low, "high": a.high, "share": a.share}

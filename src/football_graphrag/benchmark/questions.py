"""Load and validate the benchmark questions from ``config/questions.yaml``.

The YAML file is the only source of the questions (see the header of that
file for the fields and the rules). This module turns it into ``Question``
objects and refuses a file that breaks the rules: wrong number per type
among the active questions, unknown ``check`` or ``stage``, duplicate ids,
an id prefix that does not match the type.

``ALL_QUESTIONS`` has every question written, including candidates and the
ones removed by the robustness test; ``QUESTIONS`` has only the active ones
(the stages in ``active_stages``), which are the ones the benchmark runs.

The expected answers are not here: ``ground_truth.py`` computes them
without Neo4j.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

# config/questions.yaml at the repository root (src/football_graphrag/benchmark/ -> ../../../).
QUESTIONS_FILE = Path(__file__).resolve().parents[3] / "config" / "questions.yaml"

PREFIXES = {"fact": "f", "filtered_aggregation": "a", "network": "n", "network_slice": "s", "unanswerable": "u"}
QUESTION_TYPES = tuple(PREFIXES)
CHECKS = ("player", "value", "set", "player_and_value", "no_data")
STAGES = ("pilot", "full", "candidate", "removed")
RUN_STAGES = ("pilot", "full")


@dataclass(frozen=True)
class Question:
    id: str  # type prefix + number: f01, a01, n01, s01, u01
    type: str  # fact | filtered_aggregation | network | network_slice | unanswerable
    text: str  # in Portuguese, exactly as sent to the model
    check: str  # player | value | set | player_and_value | no_data
    stage: str = "pilot"  # pilot | full | candidate | removed
    tolerance: float = 0.0  # only for continuous values; counts are exact
    note: str = ""  # for humans; never sent to the model


@dataclass(frozen=True)
class QuestionSet:
    match_id: int
    active_stages: tuple[str, ...]
    per_type: int
    all: list[Question]

    @property
    def active(self) -> list[Question]:
        return [q for q in self.all if q.stage in self.active_stages]


def load(path: Path = QUESTIONS_FILE) -> QuestionSet:
    """Every question in the YAML file, validated."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = [
        Question(
            id=str(q["id"]),
            type=q["type"],
            text=" ".join(str(q["text"]).split()),
            check=q["check"],
            stage=q.get("stage", "pilot"),
            tolerance=float(q.get("tolerance", 0.0)),
            note=" ".join(str(q.get("note", "")).split()),
        )
        for q in data["questions"]
    ]
    qs = QuestionSet(int(data["match_id"]), tuple(data["active_stages"]), int(data["per_type"]), questions)
    validate(qs)
    return qs


def validate(qs: QuestionSet) -> None:
    errors = []
    ids = [q.id for q in qs.all]
    if len(set(ids)) != len(ids):
        errors.append(f"duplicate ids: {sorted({i for i in ids if ids.count(i) > 1})}")
    unknown = set(qs.active_stages) - set(RUN_STAGES)
    if unknown:
        errors.append(f"active_stages may only hold {RUN_STAGES}, not {sorted(unknown)}")
    for t in QUESTION_TYPES:
        n = sum(q.type == t for q in qs.active)
        if n != qs.per_type:
            errors.append(f"{n} active questions of type {t!r}, expected {qs.per_type}")
    for q in qs.all:
        if q.type not in QUESTION_TYPES:
            errors.append(f"{q.id}: unknown type {q.type!r}")
            continue
        if q.check not in CHECKS:
            errors.append(f"{q.id}: unknown check {q.check!r}")
        if q.stage not in STAGES:
            errors.append(f"{q.id}: unknown stage {q.stage!r}")
        if q.id[:1] != PREFIXES[q.type]:
            errors.append(f"{q.id}: id prefix should be {PREFIXES[q.type]!r} for type {q.type!r}")
        if (q.check == "no_data") != (q.type == "unanswerable"):
            errors.append(f"{q.id}: check no_data is for (and only for) unanswerable questions")
        if q.stage == "removed" and not q.note:
            errors.append(f"{q.id}: a removed question needs a note saying why")
        if not q.text:
            errors.append(f"{q.id}: empty text")
    if errors:
        raise ValueError(f"invalid {QUESTIONS_FILE.name}:\n  " + "\n  ".join(errors))


QUESTION_SET = load()
MATCH_ID = QUESTION_SET.match_id
ALL_QUESTIONS = QUESTION_SET.all
QUESTIONS = QUESTION_SET.active
BY_ID: dict[str, Question] = {q.id: q for q in ALL_QUESTIONS}


def get_question(question_id: str) -> Question:
    try:
        return BY_ID[question_id]
    except KeyError:
        raise KeyError(f"unknown question id {question_id!r}; valid: {', '.join(BY_ID)}") from None

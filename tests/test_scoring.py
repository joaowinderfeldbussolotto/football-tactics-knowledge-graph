"""Deterministic scoring: every check type, aliases, abstention, format errors."""

import pytest

from football_graphrag.benchmark.questions import Question
from football_graphrag.benchmark.scoring import Answer, build_aliases, canonical_name, normalize, score

LINEUP = [
    {"player_name": "Lionel Andrés Messi Cuccittini", "player_nickname": "Lionel Messi"},
    {"player_name": "Lautaro Javier Martínez", "player_nickname": "Lautaro Martínez"},
    {"player_name": "Damián Emiliano Martínez", "player_nickname": "Emiliano Martínez"},
    {"player_name": "Ángel Fabián Di María Hernández", "player_nickname": "Ángel Di María"},
    {"player_name": "Theo Bernard François Hernández", "player_nickname": "Theo Hernández"},
    {"player_name": "Enzo Fernandez", "player_nickname": None},
    {"player_name": "Randal Kolo Muani", "player_nickname": "Randal Kolo"},
]
ALIASES = build_aliases(LINEUP)


def q(check: str, tolerance: float = 0.0) -> Question:
    return Question("x01", "factual", "?", check, tolerance)


def expected(players=(), value=None) -> dict:
    return {"players": list(players), "value": value, "no_data": False}


def ans(players=(), value=None, no_data=False) -> Answer:
    return Answer(rationale="r", players=list(players), value=value, no_data=no_data)


# --------------------------------------------------------------------------- names

def test_normalize_drops_accents_case_and_notes():
    assert normalize("  Kylian MBAPPÉ (França) ") == "kylian mbappe"


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("Lionel Andrés Messi Cuccittini", "Lionel Andrés Messi Cuccittini"),  # player_name
        ("Lionel Messi", "Lionel Andrés Messi Cuccittini"),  # nickname
        ("messi", "Lionel Andrés Messi Cuccittini"),  # unique surname, any case
        ("Di Maria", "Ángel Fabián Di María Hernández"),  # multi-word surname, no accent
        ("Enzo Fernández", "Enzo Fernandez"),  # accent the data does not have
        ("Kolo Muani", "Randal Kolo Muani"),
        ("Emiliano Martínez", "Damián Emiliano Martínez"),
    ],
)
def test_aliases_resolve_to_the_canonical_name(alias, canonical):
    assert canonical_name(alias, ALIASES) == canonical


@pytest.mark.parametrize("ambiguous", ["Martínez", "Hernández"])
def test_ambiguous_surname_is_not_an_alias(ambiguous):
    # Martínez = Lautaro and Emiliano; Hernández = Theo and Di María.
    assert canonical_name(ambiguous, ALIASES) == normalize(ambiguous)
    assert score(q("player"), expected(["Lautaro Javier Martínez"]), ans([ambiguous]), ALIASES).correct is False


# --------------------------------------------------------------------------- checks

def test_player_checks_only_the_first_name():
    exp = expected(["Lionel Andrés Messi Cuccittini"])
    assert score(q("player"), exp, ans(["Messi", "Enzo Fernandez"]), ALIASES).correct
    assert not score(q("player"), exp, ans(["Enzo Fernandez", "Messi"]), ALIASES).correct
    assert not score(q("player"), exp, ans([]), ALIASES).correct


def test_value_exact_and_with_tolerance():
    assert score(q("value"), expected(value=6), ans(value=6.0), ALIASES).correct
    assert not score(q("value"), expected(value=6), ans(value=7), ALIASES).correct
    assert not score(q("value"), expected(value=6), ans(value=None), ALIASES).correct
    assert score(q("value", tolerance=0.5), expected(value=84.0), ans(value=84.4), ALIASES).correct
    assert not score(q("value", tolerance=0.5), expected(value=84.0), ans(value=84.6), ALIASES).correct


def test_set_ignores_order_but_not_members():
    exp = expected(["Enzo Fernandez", "Lionel Andrés Messi Cuccittini", "Randal Kolo Muani"])
    assert score(q("set"), exp, ans(["Kolo Muani", "Enzo Fernández", "Messi"]), ALIASES).correct
    assert not score(q("set"), exp, ans(["Kolo Muani", "Enzo Fernández"]), ALIASES).correct
    assert not score(q("set"), exp, ans(["Kolo Muani", "Enzo Fernández", "Messi", "Di María"]), ALIASES).correct


def test_player_and_value_needs_both():
    exp = expected(["Enzo Fernandez"], 79)
    assert score(q("player_and_value"), exp, ans(["Enzo Fernández"], 79), ALIASES).correct
    assert not score(q("player_and_value"), exp, ans(["Enzo Fernández"], 78), ALIASES).correct
    assert not score(q("player_and_value"), exp, ans(["Messi"], 79), ALIASES).correct


def test_no_data_question_is_right_only_when_no_data():
    exp = {"players": [], "value": None, "no_data": True}
    assert score(q("no_data"), exp, ans(no_data=True), ALIASES).correct
    wrong = score(q("no_data"), exp, ans(["Messi"]), ALIASES)
    assert not wrong.correct and not wrong.abstention  # a hallucination, not an abstention


# --------------------------------------------------------------------------- abstention / format

def test_abstention_on_an_answerable_question_is_an_error_recorded_apart():
    s = score(q("player"), expected(["Enzo Fernandez"]), ans(["Enzo Fernandez"], no_data=True), ALIASES)
    assert (s.correct, s.abstention, s.format_error) == (False, True, False)


def test_format_error_when_there_is_no_valid_answer():
    s = score(q("player"), expected(["Enzo Fernandez"]), None, ALIASES)
    assert (s.correct, s.abstention, s.format_error) == (False, False, True)


def test_answer_schema_puts_rationale_first():
    assert list(Answer.model_json_schema()["properties"])[0] == "rationale"


def test_the_ground_truth_scores_30_of_30_against_itself():
    """Ground truth and scoring speak the same format (needs the raw data)."""
    from football_graphrag.benchmark import ground_truth
    from football_graphrag.benchmark.questions import QUESTIONS
    from football_graphrag.config import get_settings

    if not (get_settings().raw_dir / "statsbomb" / "lineups").exists():
        pytest.skip("raw StatsBomb data not downloaded")
    truth = ground_truth.load()
    for question in QUESTIONS:
        e = truth[question.id]
        a = ans(e["players"], e["value"], e["no_data"])
        assert score(question, e, a).correct, question.id

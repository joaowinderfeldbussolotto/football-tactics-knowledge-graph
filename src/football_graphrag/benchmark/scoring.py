"""The answer format shared by every arm, and the deterministic scoring.

No LLM grades anything: an answer is right or wrong by code.

``Answer`` is the PydanticAI ``output_type`` of every arm. Field order is
deliberate: ``rationale`` comes first so the model writes its reasoning
before filling the answer fields. ``rationale`` is never scored; it is there
to investigate errors.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from pydantic import BaseModel, Field

from football_graphrag.benchmark.questions import MATCH_ID, Question
from football_graphrag.config import get_settings


class Answer(BaseModel):
    rationale: str = Field(
        description="Brief reasoning based only on the provided data. Written before the answer fields."
    )
    players: list[str] = Field(
        default_factory=list,
        description="Full player names as they appear in the data. Empty if the question is not about players. "
        "For rankings, list in order, best first.",
    )
    value: float | None = Field(
        default=None,
        description="A single number, no units. Null if the question does not ask for a number.",
    )
    no_data: bool = Field(
        default=False,
        description="True only if the provided data does not contain what is needed to answer.",
    )


# --------------------------------------------------------------------------- names

def normalize(name: str) -> str:
    """Lowercase, no accents, no parenthetical notes, single spaces."""
    name = re.sub(r"\(.*?\)", " ", name)
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    return " ".join(name.split())


def _surnames(full: str) -> list[str]:
    """Every trailing run of words after the first: "Ángel Di María" ->
    ["Di María", "María"]. Multi-word surnames (Di María, De Paul, Mac
    Allister, Kolo Muani) only work this way."""
    words = full.split()
    return [" ".join(words[i:]) for i in range(1, len(words))]


def build_aliases(lineup_players: list[dict]) -> dict[str, str]:
    """Map normalized alias -> canonical ``player_name``.

    Aliases: the StatsBomb ``player_name`` and ``player_nickname``, plus a
    surname alone ONLY when no other player of the match shares it
    ("Martínez" is both Lautaro and Emiliano, so it is not an alias).
    """
    aliases: dict[str, str] = {}
    surname_owners: dict[str, set[str]] = {}
    for p in lineup_players:
        canonical = p["player_name"]
        names = [canonical] + ([p["player_nickname"]] if p.get("player_nickname") else [])
        for n in names:
            aliases[normalize(n)] = canonical
            for s in _surnames(n):
                surname_owners.setdefault(normalize(s), set()).add(canonical)
    for surname, owners in surname_owners.items():
        if len(owners) == 1 and surname not in aliases:
            aliases[surname] = next(iter(owners))
    return aliases


@lru_cache
def match_aliases(match_id: int = MATCH_ID) -> dict[str, str]:
    path = get_settings().raw_dir / "statsbomb" / "lineups" / f"{match_id}.json"
    teams = json.loads(path.read_text())
    return build_aliases([p for team in teams for p in team["lineup"]])


def canonical_name(name: str, aliases: dict[str, str] | None = None) -> str:
    """Canonical player name, or the normalized input if it is not a known alias."""
    aliases = match_aliases() if aliases is None else aliases
    key = normalize(name)
    return aliases.get(key, key)


# --------------------------------------------------------------------------- scoring

@dataclass(frozen=True)
class Score:
    correct: bool
    abstention: bool  # answered no_data on a question that has an answer
    format_error: bool  # no valid Answer even after the output retries


def score(question: Question, expected: dict, answer: Answer | None,
          aliases: dict[str, str] | None = None) -> Score:
    """Score one answer against its ground truth entry (see ground_truth.py)."""
    if answer is None:
        return Score(correct=False, abstention=False, format_error=True)
    if question.check == "no_data":
        return Score(correct=answer.no_data, abstention=False, format_error=False)
    if answer.no_data:
        return Score(correct=False, abstention=True, format_error=False)

    def canon(names: list[str]) -> list[str]:
        return [canonical_name(n, aliases) for n in names]

    got_players, want_players = canon(answer.players), canon(expected["players"])
    player_ok = bool(got_players) and got_players[0] == want_players[0] if want_players else False
    set_ok = set(got_players) == set(want_players)
    value_ok = (
        answer.value is not None
        and expected["value"] is not None
        and abs(answer.value - expected["value"]) <= question.tolerance
    )
    correct = {
        "player": player_ok,
        "value": value_ok,
        "set": set_ok,
        "player_and_value": player_ok and value_ok,
    }[question.check]
    return Score(correct=correct, abstention=False, format_error=False)

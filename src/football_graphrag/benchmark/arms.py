"""The five arms of the benchmark.

Every arm uses the same model (from .env), the same base system prompt,
``temperature=0`` and the same ``output_type=Answer`` (PydanticAI's default
tool output mode). The only difference between arms is what the LLM gets:

- ``no_context``: the question only;
- ``vector``: the 30 event lines most similar to the question;
- ``events_in_prompt``: the compact table of every event of the match;
- ``stats_in_prompt``: per-player and per-team stats read from Neo4j (layer 1b);
- ``graph_tools``: eight primitive tools that query Neo4j (``benchmark/tools.py``).
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, get_type_hints

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, BeforeValidator
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.messages import CachePoint
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.usage import RunUsage, UsageLimits

from football_graphrag.benchmark import tools
from football_graphrag.benchmark.questions import MATCH_ID
from football_graphrag.benchmark.scoring import Answer
from football_graphrag.config import get_settings
from football_graphrag.graph import db
from football_graphrag.llm.provider import embed_texts, pydantic_ai_model, pydantic_ai_model_settings

# PydanticAI prints a promotional banner on the first run; it ends up in every log.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

ARMS = ("no_context", "vector", "events_in_prompt", "stats_in_prompt", "graph_tools")
# config/benchmark.yaml at the repository root: which arms run by default.
BENCHMARK_CONFIG = Path(__file__).resolve().parents[3] / "config" / "benchmark.yaml"


def configured_arms(path: Path = BENCHMARK_CONFIG) -> list[str]:
    """The arms listed in config/benchmark.yaml, in ARMS order; all arms if the file is missing."""
    if not path.exists():
        return list(ARMS)
    listed = yaml.safe_load(path.read_text(encoding="utf-8")).get("arms") or []
    unknown = [a for a in listed if a not in ARMS]
    if unknown or not listed:
        raise ValueError(f"{path.name}: arms must be a non-empty list of {', '.join(ARMS)}; got {listed}")
    return [a for a in ARMS if a in listed]

SYSTEM_PROMPT = """\
You answer questions about one football match, using the data provided in
this conversation. Questions are in Portuguese.

Answer only with the data provided in this conversation (in the message or
returned by your tools). Do not use outside knowledge, even if you think you
know the answer. If the provided data does not contain exactly what the
question asks for, set no_data to true: do not answer with a different or
approximate measure in its place.

Write player names exactly as they appear in the data."""

VECTOR_TOP_K = 30
MAX_TOOL_CALLS = 12
# A run makes one request per tool call round, plus the final answer and up
# to 2 output retries. Beyond this, the run is stopped (counted as no answer).
REQUEST_LIMIT = MAX_TOOL_CALLS + 4
OUTPUT_RETRIES = 2
# Retries after a tool argument fails validation (e.g. a value outside a closed list).
TOOL_RETRIES = 2


@dataclass
class ArmResult:
    arm: str
    answer: Answer | None  # None: no valid Answer even after the output retries
    input_tokens: int = 0  # includes cached tokens
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    latency_s: float = 0.0
    prompt_preview: str = ""
    error: str | None = None  # why there is no answer (format or usage limit)
    trace_url: str | None = None  # Langfuse trace, when instrumentation is on


# --------------------------------------------------------------------------- data views

EVENT_LEGEND = """\
One row per on-ball action (SPADL), in match order; penalty shootout excluded.
period: 1 and 2 regular time, 3 and 4 extra time. minute: broadcast minute (stoppage
time continues the count, so the 1st half goes past 45). team, player: who acted. action: action type
(Portuguese labels, e.g. passe, conducao, drible, desarme, interceptacao,
falta_cometida, finalizacao, penalti, cartao_por_reclamacao). success: 1/0.
receiver: who received a completed pass. zone_from/zone_to: cell of a 12x8 grid,
zone = column*8 + row, column 0-11 from the acting team's own goal to the
opponent's goal; third = zone // 32 (0 defensive, 1 middle, 2 attacking).
possession: id of the possession phase. outcome: goal with the score it made,
e.g. goal(3-2), yellow_card, and the shot result (defendida, bloqueada,
para_fora) when there is one. score: the score Argentina-France when the
action starts, before it (2-1: Argentina 2, France 1)."""


def _int(value) -> str:
    return "" if pd.isna(value) else str(int(value))


def _outcome(row) -> str:
    parts = []
    if row.gol:
        parts.append("goal")
    if row.cartao_amarelo:
        parts.append("yellow_card")
    if isinstance(row.desfecho, str) and row.desfecho != "gol":
        parts.append(row.desfecho)
    return "+".join(parts)


@lru_cache
def event_lines(match_id: int = MATCH_ID) -> tuple[str, list[str]]:
    """Header and one CSV line per action, built from the layer 0 Parquet."""
    # Match order is (period, time). action_id alone is not: layer 0 appends
    # actions it recovers from the raw JSON (e.g. Giroud's yellow card for
    # dissent, 95') at the end of the table.
    df = pd.read_parquet(get_settings().processed_dir / f"{match_id}.parquet").sort_values(
        ["period_id", "time_seconds", "action_id"]
    )
    names = df.dropna(subset=["player_id"]).groupby("player_id").player_name.first()
    receiver = df.receiver_player_id.map(lambda r: names.get(int(r), "") if pd.notna(r) else "")
    header = "period,minute,team,player,action,success,receiver,zone_from,zone_to,possession,outcome,score"
    lines, goals = [], {"Argentina": 0, "France": 0}
    for r, rec in zip(df.itertuples(), receiver):
        score = f"{goals['Argentina']}-{goals['France']}"  # before this action
        outcome = _outcome(r)
        if r.gol:
            goals[r.team_name] += 1
            outcome = outcome.replace("goal", f"goal({goals['Argentina']}-{goals['France']})", 1)
        lines.append(",".join([
            str(r.period_id), str(r.minuto), r.team_name, r.player_name, r.acao, str(int(r.sucesso)), rec,
            _int(r.zone_start), _int(r.zone_end), _int(r.possession_id), outcome, score,
        ]))
    return header, lines


def events_table(lines: list[str] | None = None) -> str:
    header, all_lines = event_lines()
    return f"{EVENT_LEGEND}\n\n{header}\n" + "\n".join(all_lines if lines is None else lines)


@lru_cache
def stats_table(match_id: int = MATCH_ID) -> str:
    """Layer 1b stats as text. Source: Neo4j (the same numbers graph_tools sees)."""
    driver = db.make_driver(get_settings())
    try:
        with driver.session() as session:
            teams = [r["p"] for r in session.run(
                "MATCH (e:EstatisticaTime {match_id: $m}) RETURN properties(e) AS p ORDER BY e.nome", m=match_id)]
            players = [r["p"] for r in session.run(
                """MATCH (e:EstatisticaJogador {match_id: $m}) RETURN properties(e) AS p
                   ORDER BY e.time, e.toques DESC""", m=match_id)]
    finally:
        driver.close()

    def table(rows: list[dict], first: list[str]) -> str:
        cols = first + sorted({k for r in rows for k in r} - set(first) - tools._HIDDEN)
        body = [",".join("" if r.get(c) is None else str(r[c]) for c in cols) for r in rows]
        return "\n".join([",".join(cols), *body])

    fields = sorted({k for r in teams + players for k in r} - tools._HIDDEN)
    return (
        f"What each column means:\n{tools.glossary(fields)}\n\n"
        "Team stats:\n"
        f"{table(teams, ['nome'])}\n\n"
        "Player stats (one row per player who acted):\n"
        f"{table(players, ['nome', 'time', 'posicao'])}"
    )


# --------------------------------------------------------------------------- vector index

def _cache_dir():
    path = get_settings().data_dir / "benchmark" / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


async def event_vectors() -> np.ndarray:
    """Embeddings of every event line, cached on disk (paid once)."""
    s = get_settings()
    _, lines = event_lines()
    path = _cache_dir() / f"events_{_key(s.embedder_provider, s.embedder_model, *lines)}.npy"
    if path.exists():
        return np.load(path)
    vectors = np.array(await embed_texts(lines, s), dtype=np.float32)
    np.save(path, vectors)
    return vectors


async def question_vector(text: str) -> np.ndarray:
    """Embedding of a question, cached on disk (the benchmark repeats them)."""
    s = get_settings()
    path = _cache_dir() / "questions.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    key = _key(s.embedder_provider, s.embedder_model, text)
    if key not in cache:
        [cache[key]] = await embed_texts([text], s)
        path.write_text(json.dumps(cache))
    return np.array(cache[key], dtype=np.float32)


async def similar_events(text: str, k: int = VECTOR_TOP_K) -> list[str]:
    """Top-k lines by cosine similarity, returned in match order."""
    vectors = await event_vectors()
    q = await question_vector(text)
    sims = vectors @ q / (np.linalg.norm(vectors, axis=1) * np.linalg.norm(q) + 1e-12)
    top = sorted(np.argsort(-sims)[:k])
    _, lines = event_lines()
    return [lines[i] for i in top]


# --------------------------------------------------------------------------- agents

def _model_settings() -> dict:
    return {**pydantic_ai_model_settings(get_settings()), "temperature": 0.0}


@lru_cache
def plain_agent() -> Agent[None, Answer]:
    """Agent of the four arms without tools: they differ only in the user message."""
    return Agent(
        pydantic_ai_model(get_settings()),
        output_type=Answer,
        retries={"output": OUTPUT_RETRIES},
        model_settings=_model_settings(),
        system_prompt=SYSTEM_PROMPT,
    )


@dataclass
class GraphDeps:
    toolbox: tools.Toolbox
    calls: list[dict] = field(default_factory=list)


def _jsonable(value):
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_none=True)
    return value


def _call(ctx: RunContext[GraphDeps], tool_name: str, fn, **kwargs):
    """Run one tool, log it, enforce the call limit, and turn bad arguments
    into a message the model can act on (instead of an exception)."""
    ctx.deps.calls.append({"tool": tool_name, "args": {k: _jsonable(v) for k, v in kwargs.items()}})
    if len(ctx.deps.calls) > MAX_TOOL_CALLS:
        return {"error": f"tool call limit ({MAX_TOOL_CALLS}) reached; answer now with the data you have"}
    try:
        return fn(**kwargs)
    except tools.ToolError as exc:
        return {"error": str(exc)}


def _unquote(value):
    """Drop stray quotes the model sometimes wraps around a string argument
    ('"player"' or '"player'), in any argument, nested ones included. No real value
    starts or ends with a quote, and the argument schema sent to the model is unchanged."""
    if isinstance(value, str):
        return value.strip().strip("\"'").strip()
    if isinstance(value, list):
        return [_unquote(v) for v in value]
    if isinstance(value, dict):
        return {k: _unquote(v) for k, v in value.items()}
    return value


def _describe(doc: str):
    """Set a tool's docstring from a computed string (PydanticAI reads the tool and
    argument descriptions from the docstring, and an f-string is not a docstring), and
    let every argument go through ``_unquote`` before validation."""
    def wrap(fn):
        fn.__doc__ = doc
        hints = get_type_hints(fn, include_extras=True)
        fn.__annotations__ = {name: hint if name in ("ctx", "return") else Annotated[hint, BeforeValidator(_unquote)]
                              for name, hint in hints.items()}
        return fn
    return wrap


# Each tool description has two parts: what the tool computes (mechanics) and
# what that usually means in football. Neither may carry a rule or a hint
# meant for a specific question.

@_describe(f"""Lists the players who took part in the match (everyone with at least one
on-ball action), with team and nominal position. Names come exactly as the other tools
expect them.

In football terms: the squad sheet of the final, starters and substitutes who played.

Args:
    team: Optional. {tools.TEAM_HELP} Omit it for both teams.
""")
def list_players(ctx: RunContext[GraphDeps], team: str | None = None) -> list[dict]:
    return _call(ctx, "list_players", ctx.deps.toolbox.list_players, team=team)


@_describe(f"""Counts the on-ball actions that match the filters, or sums the expected
threat (xT) they added, grouped by the fields chosen, largest first. Without group_by it
returns a single total. Both teams, every period; the penalty shootout is not in the data.

In football terms: how many times something happened and who or which team did it most
(passes, tackles, shots, fouls, ...), in the whole match or in any slice of it: a team, a
player, a period, a stretch of time, an area of the pitch. xT measures how much an action
moved the ball toward dangerous areas.

Args:
    filters: Which actions to count. Omit it for every action.
    group_by: Fields to group by, in order: player (who acted), receiver (who received a
        completed pass), team, action, period, third, corridor. Omit it for a single total.
    metric: count (number of actions) or xt_sum (sum of the xT added).
    top: How many rows to return, 1 to {tools.MAX_TOP}.
""")
def query_actions(ctx: RunContext[GraphDeps], filters: tools.ActionFilters | None = None,
                  group_by: list[tools.GroupBy] | None = None, metric: Literal["count", "xt_sum"] = "count",
                  top: int = 10) -> list[dict]:
    return _call(ctx, "query_actions", ctx.deps.toolbox.query_actions,
                 filters=filters, group_by=group_by, metric=metric, top=top)


@_describe(f"""Lists the individual actions that match the filters, in match order: period,
broadcast minute, second (elapsed time since kickoff, the scale of the time filters), team,
player, action, success, receiver, third, corridor, outcome (goal with the score after
it, yellow_card, shot result) and score (the score when the action starts, before it:
"Argentina 2-1 France").
Returns at most `limit` actions and the total that matched.

In football terms: the play-by-play of the match. It shows when and how something
happened, in what order, and locates a moment of the match in time.

Args:
    filters: Which actions to list. Omit it for every action.
    limit: How many actions to return, 1 to {tools.MAX_LIST}, from the start of the match.
""")
def list_actions(ctx: RunContext[GraphDeps], filters: tools.ActionFilters | None = None,
                 limit: int = 20) -> dict:
    return _call(ctx, "list_actions", ctx.deps.toolbox.list_actions, filters=filters, limit=limit)


@_describe(f"""Builds a team's pass network from the completed passes between teammates that
match the filters: each player is a node, and each passer -> receiver pair is a connection
carrying the number of passes and the xT they added. Returns a network_id, used by
network_metric and network_edges, the team, filters and removed players it was built with,
and a summary (players, connections, passes). Players can be left out: the network is then
built as if they were not there (no passes to or from them), and the summary lists the
players who, as a result, keep no connection with anyone. Networks last until the end of
the question.

In football terms: the map of who passes to whom, for the whole match or for a slice of
it (a period, a stretch of time, an area of the pitch). Leaving players out shows how the
team's circulation would be connected without them.

Args:
    team: {tools.TEAM_HELP}
    filters: Which passes to include. The team is the one above, and only completed passes
        count. Omit it for every completed pass of the team.
    without_players: Optional. Players to leave out of the network: full name, nickname or
        a surname that is unique in the match.
""")
def pass_network(ctx: RunContext[GraphDeps], team: str, filters: tools.ActionFilters | None = None,
                 without_players: list[str] | None = None) -> dict:
    return _call(ctx, "pass_network", ctx.deps.toolbox.pass_network, team=team, filters=filters,
                 without_players=without_players)


@_describe(f"""Computes a graph metric on a network built by pass_network (Neo4j GDS). The result
repeats the team and filters the network was built with.
- betweenness: for every pair of other players, counts how many shortest passing routes
  go through each player. Unweighted, every connection has length 1; weighted, a
  connection is shorter the more passes (length 1/passes) or the more xT (length
  1/(1+xT)) it carries.
- degree: number of teammates a player passes to and receives from; weighted, the number
  of passes or the xT on those connections. Directed gives outgoing and incoming apart.
- pagerank: a player scores high when receiving the ball from players who themselves
  score high; weighted by passes or xT.
- bridges: connections whose removal would split the network in two.
- articulation_points: players whose removal would split the network in two.
- communities: groups of players connected mostly among themselves (Louvain; groups can
  change between calls).
- triangles: every trio of players all connected to each other, with the passes among the
  three (both directions of the three pairs) and whether all six directions occur, most
  passes first.
Directed keeps passer -> receiver; undirected merges both directions of a pair. bridges,
articulation_points and triangles are always unweighted and undirected; communities,
undirected.
xT on a connection can be negative (passes backward); degree, pagerank and communities
count a negative total as zero.

In football terms: betweenness marks a player who connects teammates in ball
circulation, a link or hub of the build-up; degree, how involved a player was in the
passing and with how many partners; pagerank, the reference players the ball tends to
flow to; bridges and articulation points, fragile links whose absence would cut the team
in two; communities, the sub-groups of the team that combine most with each other;
triangles, the small groups that circulate the ball among themselves, the units a team
builds its passing around.

Args:
    network_id: The id returned by pass_network.
    metric: betweenness, degree, pagerank, bridges, articulation_points, communities or
        triangles.
    weight: none, passes or xt.
    direction: directed or undirected.
    top: How many players to return in a ranking, 1 to {tools.MAX_TOP}.
""")
def network_metric(ctx: RunContext[GraphDeps], network_id: str, metric: tools.NetworkMetric,
                   weight: tools.Weight = "none", direction: tools.Direction = "directed",
                   top: int = 10) -> dict:
    return _call(ctx, "network_metric", ctx.deps.toolbox.network_metric,
                 network_id=network_id, metric=metric, weight=weight, direction=direction, top=top)


@_describe(f"""Lists the connections of a network built by pass_network: passer, receiver,
number of completed passes and the xT they added, most passes first, with the team and
filters the network was built with. With a player, only the connections where that
player passes or receives.

In football terms: the passing partnerships of a team or of one player, and which of
them moved the ball toward danger.

Args:
    network_id: The id returned by pass_network.
    player: Optional. Full name, nickname or a surname that is unique in the match.
    top: How many connections to return, 1 to {tools.MAX_TOP}.
""")
def network_edges(ctx: RunContext[GraphDeps], network_id: str, player: str | None = None,
                  top: int = 20) -> dict:
    return _call(ctx, "network_edges", ctx.deps.toolbox.network_edges,
                 network_id=network_id, player=player, top=top)


@_describe(f"""Finds chains of completed passes in which each pass is made by the receiver
of the previous one (A -> B -> C ...) and counts the most frequent sequences of players.
After receiving, the link is the receiver's next pass attempt; the chain stops if that
pass is not completed. same_possession: all passes of a chain in the same possession of
the ball. consecutive: no other pass, by anyone, between two linked passes. Players may
repeat (A -> B -> A). The filters select the first pass of each chain. then_action keeps
only the chains after which the last receiver, keeping the ball (carries and take-ons
only), performs one of the given actions in the same possession.

In football terms: a team's recurring passing combinations, who tends to find whom and
through whom when the ball moves from player to player, and which combinations lead to a
given outcome, such as a shot.

Args:
    team: {tools.TEAM_HELP}
    players: Number of players in a sequence, 2 to 5 (2 is a single pass A -> B; 3 is
        A -> B -> C, two passes).
    same_possession: Require the whole chain within one possession.
    consecutive: Require no other pass between two linked passes.
    then_action: Optional. Action labels (as in the filters' action field); keep only the
        chains whose last receiver then performs one of them.
    filters: Which passes may start a chain. Omit it for every completed pass of the team.
    top: How many sequences to return, 1 to {tools.MAX_TOP}.
""")
def pass_paths(ctx: RunContext[GraphDeps], team: str, players: int = 3, same_possession: bool = True,
               consecutive: bool = True, then_action: list[tools.Action] | None = None,
               filters: tools.ActionFilters | None = None, top: int = 10) -> dict:
    return _call(ctx, "pass_paths", ctx.deps.toolbox.pass_paths, team=team, players=players,
                 same_possession=same_possession, consecutive=consecutive, then_action=then_action,
                 filters=filters, top=top)


@_describe(f"""Counts possessions (phases of consecutive actions of one team, ending when the other
team acts, the period ends, or after a foul, shot, save, clearance or miscontrol) that meet
the conditions, and who took part in them (players with at least one action in the
possession). group_by player ranks players by the possessions they took part in; pair ranks
pairs of teammates by the possessions they took part in together. Conditions on time refer
to the possession's first action.

In football terms: the team's moves as a whole, not single passes: who was involved in the
moves that started deep and ended in a shot, or reached the final third, and which players
were most often involved together.

Args:
    team: Optional. {tools.TEAM_HELP}
    period: Optional. One or more periods (1 to 4).
    second_from: Optional. Earliest start of the possession, in elapsed seconds (as in
        list_actions).
    second_to: Optional. Latest start of the possession, same scale.
    starts_in_third: Optional. defensive, middle or attacking: third of the first action.
    reaches_third: Optional. defensive, middle or attacking: some action of the possession
        is in that third.
    ends_with: Optional. Action labels; the last action of the possession is one of them.
    includes_players: Optional. Players who all took part in the possession.
    group_by: none (only the count), player or pair.
    top: How many rows to return, 1 to {tools.MAX_TOP}.
""")
def query_possessions(ctx: RunContext[GraphDeps], team: str | None = None,
                      period: list[Literal[1, 2, 3, 4]] | None = None, second_from: float | None = None,
                      second_to: float | None = None,
                      starts_in_third: Literal["defensive", "middle", "attacking"] | None = None,
                      reaches_third: Literal["defensive", "middle", "attacking"] | None = None,
                      ends_with: list[tools.Action] | None = None, includes_players: list[str] | None = None,
                      group_by: Literal["none", "player", "pair"] = "none", top: int = 10) -> dict:
    return _call(ctx, "query_possessions", ctx.deps.toolbox.query_possessions, team=team, period=period,
                 second_from=second_from, second_to=second_to, starts_in_third=starts_in_third,
                 reaches_third=reaches_third, ends_with=ends_with, includes_players=includes_players,
                 group_by=group_by, top=top)


TOOLS = {f.__name__: f for f in (list_players, query_actions, list_actions, query_possessions,
                                 pass_network, network_metric, network_edges, pass_paths)}
# An arm with tools is an agent plus a list of tools. A future arm without the
# network tools would be one line: "tools_no_graph": tuple(TOOLS)[:4].
TOOL_ARMS = {"graph_tools": tuple(TOOLS)}


@lru_cache
def tool_agent(arm: str = "graph_tools") -> Agent[GraphDeps, Answer]:
    return Agent(
        pydantic_ai_model(get_settings()),
        deps_type=GraphDeps,
        output_type=Answer,
        retries={"output": OUTPUT_RETRIES, "tools": TOOL_RETRIES},
        # One tool call per step: in parallel, the model asked for a network's
        # edges before the network existed, with an invented id.
        model_settings={**_model_settings(), "parallel_tool_calls": False},
        system_prompt=SYSTEM_PROMPT,
        tools=[Tool(TOOLS[name], takes_ctx=True) for name in TOOL_ARMS[arm]],
    )


@lru_cache
def _driver():
    return db.make_driver(get_settings())


# --------------------------------------------------------------------------- entry point

def missing_config(arms: list[str]) -> list[str]:
    """What .env lacks to run these arms (empty list: ready)."""
    s = get_settings()
    problems = []
    if not (s.llm_api_key and s.llm_model):
        problems.append("LLM_API_KEY and LLM_MODEL must be set in .env (every arm uses the LLM)")
    if "vector" in arms and not (s.embedder_api_key and s.embedder_model):
        problems.append("EMBEDDER_API_KEY and EMBEDDER_MODEL must be set in .env (the vector arm embeds events)")
    return problems


async def build_prompt(arm: str, question_text: str) -> str:
    """The user message of an arm (the system prompt is the same for all)."""
    if arm == "no_context" or arm in TOOL_ARMS:
        return question_text
    if arm == "events_in_prompt":
        return f"Match events:\n{events_table()}\n\nQuestion: {question_text}"
    if arm == "vector":
        lines = await similar_events(question_text)
        return (
            f"The {len(lines)} match events most similar to the question:\n{events_table(lines)}"
            f"\n\nQuestion: {question_text}"
        )
    if arm == "stats_in_prompt":
        return f"Match stats:\n{stats_table()}\n\nQuestion: {question_text}"
    raise ValueError(f"unknown arm {arm!r}; valid: {', '.join(ARMS)}")


# Arms whose data block is identical for every question: worth caching.
CACHED_ARMS = ("events_in_prompt", "stats_in_prompt")
QUESTION_MARKER = "\n\nQuestion: "


def user_content(arm: str, prompt: str) -> str | list:
    """The user message as sent. For the cached arms, the same text split in
    two parts, data and question, with a cache breakpoint after the data.

    Prompt caching changes the bill, not what the model reads: the parts
    are the same text. The question has to be a separate part because the
    cache matches a prefix up to the breakpoint, and the question changes.
    """
    if arm not in CACHED_ARMS:
        return prompt
    data, question = prompt.rsplit(QUESTION_MARKER, 1)
    return [data, CachePoint(), f"{QUESTION_MARKER.lstrip()}{question}"]


async def run_arm(arm: str, question_text: str) -> ArmResult:
    """Ask one question to one arm. Never raises for a bad model answer."""
    prompt = await build_prompt(arm, question_text)
    usage = RunUsage()
    deps = GraphDeps(toolbox=tools.Toolbox(_driver())) if arm in TOOL_ARMS else None
    agent = tool_agent(arm) if arm in TOOL_ARMS else plain_agent()
    t0 = time.perf_counter()
    answer, error = None, None
    try:
        result = await agent.run(user_content(arm, prompt), deps=deps, usage=usage,
                                 usage_limits=UsageLimits(request_limit=REQUEST_LIMIT))
        answer = result.output
    except UnexpectedModelBehavior as exc:  # output still invalid after the retries
        error = f"format: {exc}"
    except UsageLimitExceeded as exc:
        error = f"usage_limit: {exc}"
    finally:
        if deps:
            deps.toolbox.close()  # drop this run's GDS projections
    return ArmResult(
        arm=arm,
        answer=answer,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        tool_calls=deps.calls if deps else [],
        latency_s=round(time.perf_counter() - t0, 2),
        prompt_preview=prompt,
        error=error,
    )

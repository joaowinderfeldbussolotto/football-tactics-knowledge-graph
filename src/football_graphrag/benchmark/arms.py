"""The five arms of the benchmark.

Every arm uses the same model (from .env), the same base system prompt,
``temperature=0`` and the same ``output_type=Answer`` (PydanticAI's default
tool output mode). The only difference between arms is what the LLM gets:

- ``no_context``: the question only;
- ``vector``: the 30 event lines most similar to the question;
- ``events_in_prompt``: the compact table of every event of the match;
- ``stats_in_prompt``: per-player and per-team stats read from Neo4j (layer 1b);
- ``graph_tools``: tools that query Neo4j (``benchmark/tools.py``).
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd
from pydantic_ai import Agent, RunContext
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

SYSTEM_PROMPT = """\
You answer questions about one football match: the 2022 FIFA World Cup final,
Argentina vs France. Questions are in Portuguese.

Answer only with the data provided in this conversation (in the message or
returned by your tools). Do not use outside knowledge, even if you think you
know the answer. If the provided data does not contain what is needed to
answer, set no_data to true.

Write player names exactly as they appear in the data."""

VECTOR_TOP_K = 30
MAX_TOOL_CALLS = 8
# A run makes one request per tool call round, plus the final answer and up
# to 2 output retries. Beyond this, the run is stopped (counted as no answer).
REQUEST_LIMIT = MAX_TOOL_CALLS + 4
OUTPUT_RETRIES = 2


@dataclass
class ArmResult:
    arm: str
    answer: Answer | None  # None: no valid Answer even after the output retries
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    latency_s: float = 0.0
    prompt_preview: str = ""
    error: str | None = None  # why there is no answer (format or usage limit)


# --------------------------------------------------------------------------- data views

EVENT_LEGEND = """\
One row per on-ball action (SPADL), in match order; penalty shootout excluded.
minute: broadcast minute (1-120+). team, player: who acted. action: action type
(Portuguese labels, e.g. passe, conducao, drible, desarme, interceptacao,
falta_cometida, finalizacao, penalti, cartao_por_reclamacao). success: 1/0.
receiver: who received a completed pass. zone_from/zone_to: cell of a 12x8 grid,
zone = column*8 + row, column 0-11 from the acting team's own goal to the
opponent's goal; third = zone // 32 (0 defensive, 1 middle, 2 attacking).
possession: id of the possession phase. outcome: goal, yellow_card, and the
shot result (defendida, bloqueada, para_fora) when there is one."""


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
    df = pd.read_parquet(get_settings().processed_dir / f"{match_id}.parquet").sort_values("action_id")
    names = df.dropna(subset=["player_id"]).groupby("player_id").player_name.first()
    receiver = df.receiver_player_id.map(lambda r: names.get(int(r), "") if pd.notna(r) else "")
    header = "minute,team,player,action,success,receiver,zone_from,zone_to,possession,outcome"
    lines = [
        ",".join([
            str(r.minuto), r.team_name, r.player_name, r.acao, str(int(r.sucesso)), rec,
            _int(r.zone_start), _int(r.zone_end), _int(r.possession_id), _outcome(r),
        ])
        for r, rec in zip(df.itertuples(), receiver)
    ]
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

    return (
        "Team stats (posse_pct is possession by time; ppda = opponent passes per defensive action):\n"
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
    driver: object
    calls: list[dict] = field(default_factory=list)


def _call(ctx: RunContext[GraphDeps], tool_name: str, fn, **kwargs):
    """Run one tool, log it, enforce the 8-call limit, and turn bad arguments
    into a message the model can act on (instead of an exception)."""
    ctx.deps.calls.append({"tool": tool_name, "args": kwargs})
    if len(ctx.deps.calls) > MAX_TOOL_CALLS:
        return {"error": f"tool call limit ({MAX_TOOL_CALLS}) reached; answer now with the data you have"}
    try:
        return fn(ctx.deps.driver, **kwargs)
    except tools.ToolError as exc:
        return {"error": str(exc)}


@lru_cache
def graph_agent() -> Agent[GraphDeps, Answer]:
    agent = Agent(
        pydantic_ai_model(get_settings()),
        deps_type=GraphDeps,
        output_type=Answer,
        retries={"output": OUTPUT_RETRIES},
        model_settings=_model_settings(),
        system_prompt=SYSTEM_PROMPT,
    )

    @agent.tool
    def list_players(ctx: RunContext[GraphDeps], team: str) -> list[dict]:
        """Players of a team ('Argentina' or 'France') who acted in the match, with position and touches."""
        return _call(ctx, "list_players", tools.list_players, team=team)

    @agent.tool
    def player_stats(ctx: RunContext[GraphDeps], name: str) -> dict:
        """All aggregated stats of one player (name, nickname or unique surname)."""
        return _call(ctx, "player_stats", tools.player_stats, name=name)

    @agent.tool
    def team_stats(ctx: RunContext[GraphDeps], team: str) -> dict:
        """Aggregated stats of a team ('Argentina' or 'France')."""
        return _call(ctx, "team_stats", tools.team_stats, team=team)

    @agent.tool(description="Players ranked by one stat, highest first. Optional team filter. "
                f"Valid stats: {', '.join(tools.PLAYER_STATS)}.")
    def stat_ranking(ctx: RunContext[GraphDeps], stat: str, team: str | None = None, top: int = 5) -> list[dict]:
        return _call(ctx, "stat_ranking", tools.stat_ranking, stat=stat, team=team, top=top)

    @agent.tool(description="Events of one type in match order (minute, period, team, player, action, "
                f"outcome). Optional team filter. Valid event_type: {', '.join(tools.EVENT_TYPES)}.")
    def events(ctx: RunContext[GraphDeps], event_type: str, team: str | None = None) -> list[dict]:
        return _call(ctx, "events", tools.events, event_type=event_type, team=team)

    @agent.tool
    def pass_network_centrality(ctx: RunContext[GraphDeps], team: str, top: int = 5) -> list[dict]:
        """Betweenness centrality ranking on the team's network of completed passes
        (directed, weighted by cost = 1 / (1 + xT of the passes)). Computed live with GDS."""
        return _call(ctx, "pass_network_centrality", tools.pass_network_centrality, team=team, top=top)

    @agent.tool
    def three_player_sequences(ctx: RunContext[GraphDeps], team: str, top: int = 5) -> list[dict]:
        """Most frequent progressive completed-pass sequences A->B->C of a team: same
        possession, nearly consecutive, three distinct players, ending in a more
        advanced third of the pitch. Returns occurrences and summed xT."""
        return _call(ctx, "three_player_sequences", tools.three_player_sequences, team=team, top=top)

    @agent.tool
    def pass_network_bridges(ctx: RunContext[GraphDeps], team: str) -> dict:
        """Bridges (edges whose removal disconnects the network) and Louvain
        communities of the team's undirected pass network. Computed live with GDS."""
        return _call(ctx, "pass_network_bridges", tools.pass_network_bridges, team=team)

    return agent


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
    if arm in ("no_context", "graph_tools"):
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


async def run_arm(arm: str, question_text: str) -> ArmResult:
    """Ask one question to one arm. Never raises for a bad model answer."""
    prompt = await build_prompt(arm, question_text)
    usage = RunUsage()
    deps = GraphDeps(driver=_driver()) if arm == "graph_tools" else None
    agent = graph_agent() if arm == "graph_tools" else plain_agent()
    t0 = time.perf_counter()
    answer, error = None, None
    try:
        result = await agent.run(prompt, deps=deps, usage=usage,
                                 usage_limits=UsageLimits(request_limit=REQUEST_LIMIT))
        answer = result.output
    except UnexpectedModelBehavior as exc:  # output still invalid after the retries
        error = f"format: {exc}"
    except UsageLimitExceeded as exc:
        error = f"usage_limit: {exc}"
    return ArmResult(
        arm=arm,
        answer=answer,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        tool_calls=deps.calls if deps else [],
        latency_s=round(time.perf_counter() - t0, 2),
        prompt_preview=prompt,
        error=error,
    )

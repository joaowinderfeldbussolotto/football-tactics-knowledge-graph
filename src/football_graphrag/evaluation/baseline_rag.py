"""Baseline de comparação: RAG vetorial plano (seção 9 do plano).

Um resumo textual por partida com as métricas AGREGADAS (as que um sistema
tabular tem), embeddado e recuperado por similaridade; a resposta vem do
mesmo LLM. A tese do projeto prevê que este baseline:
- empate nas perguntas de métrica agregada (a informação está no resumo);
- falhe nas perguntas estruturais (7.1, 7.2, 7.4, 7.5...), porque a
  informação simplesmente NÃO EXISTE no resumo dele.

O resumo é gerado por template determinístico a partir do parquet/meta —
deliberadamente o mesmo tipo de conteúdo dos sistemas RAG descritivos
existentes (métricas por partida), sem nenhum resultado da camada 2.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
from pydantic_ai import Agent

from football_graphrag.config import get_settings
from football_graphrag.llm.provider import pydantic_ai_model

PROMPT_BASELINE = """\
Você é um analista de futebol. Responda a pergunta usando APENAS os trechos
de contexto fornecidos. Se a informação não estiver no contexto, diga que
não é possível responder com os dados disponíveis. Não invente. Responda em
português.
"""


def build_match_summary(match_id: int, data_dir: Path) -> list[str]:
    """Resumo textual por partida (chunks), só com métricas agregadas."""
    processed = data_dir / "processed"
    meta = json.loads((processed / f"{match_id}_meta.json").read_text())
    actions = pd.read_parquet(processed / f"{match_id}.parquet")
    teams = meta["teams"]
    chunks = []
    for team_id, team in teams.items():
        tdf = actions[actions["team_id"] == int(team_id)]
        passes = tdf[tdf["type_name"] == "pass"]
        m = meta["team_metrics"][str(team_id)] if str(team_id) in meta.get("team_metrics", {}) else meta["team_metrics"][int(team_id)]
        top_passers = passes.groupby("player_name").size().sort_values(ascending=False).head(5)
        chunks.append(
            f"Partida {match_id} — {team}: {len(passes)} passes "
            f"({passes['result_name'].eq('success').mean():.0%} completos), "
            f"{tdf['progressive'].sum()} ações progressivas, "
            f"PPDA 1º tempo {m['ppda_p1']:.1f}, PPDA 2º tempo {m['ppda_p2']:.1f}, "
            f"field tilt {m['field_tilt']:.0%}. "
            f"xT total {tdf['xt_value'].sum():.3f}, VAEP total {tdf['vaep_value'].sum():.3f}."
        )
        chunks.append(
            f"Partida {match_id} — {team}, jogadores com mais passes: "
            + "; ".join(f"{nome}: {n}" for nome, n in top_passers.items())
            + "."
        )
    return chunks


@dataclass
class BaselineIndex:
    chunks: list[str]
    vectors: list[list[float]]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeddings via o mesmo provedor de embeddings do Graphiti."""
    from football_graphrag.llm.provider import graphiti_embedder

    embedder = graphiti_embedder(get_settings())
    return [await embedder.create(input_data=[t]) for t in texts]


async def build_index(match_ids: list[int], data_dir: Path) -> BaselineIndex:
    chunks = [c for m in match_ids for c in build_match_summary(m, data_dir)]
    vectors = await embed_texts(chunks)
    return BaselineIndex(chunks=chunks, vectors=vectors)


def _cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    den = (sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5)
    return num / den if den else 0.0


@lru_cache
def baseline_agent() -> Agent:
    return Agent(pydantic_ai_model(get_settings()), output_type=str, system_prompt=PROMPT_BASELINE)


async def answer_with_baseline(index: BaselineIndex, question: str, top_k: int = 4) -> tuple[str, list[str]]:
    [qvec] = await embed_texts([question])
    ranked = sorted(zip(index.chunks, index.vectors), key=lambda cv: -_cosine(qvec, cv[1]))
    context = [c for c, _ in ranked[:top_k]]
    result = await baseline_agent().run(
        f"PERGUNTA: {question}\n\nCONTEXTO:\n" + "\n".join(f"- {c}" for c in context)
    )
    return result.output, context

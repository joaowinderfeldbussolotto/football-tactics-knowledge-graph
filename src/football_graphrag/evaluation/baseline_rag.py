"""Baseline de comparação: RAG vetorial plano (seção 9 do plano).

Um resumo textual por partida, embeddado e recuperado por similaridade; a
resposta vem do mesmo LLM. A tese do projeto prevê que este baseline:
- empate nas perguntas factuais e de métrica agregada (a informação está no
  resumo);
- falhe nas perguntas estruturais (7.1, 7.2, 7.4, 7.5...), porque a
  informação simplesmente NÃO EXISTE em resumo nenhum — ela é uma
  propriedade da topologia da rede de passes, não um número por jogador.

O resumo é gerado por template determinístico a partir do parquet/meta, sem
nenhum resultado da camada 2.

Paridade de fatos (importante para a validade da comparação)
------------------------------------------------------------
O baseline recebe os MESMOS FATOS que o grafo: gols, assistências, cartões e
a súmula completa de cada jogador — as mesmas contagens do nó
``EstatisticaJogador``, vindas de ``evaluation/match_facts.py``. Inclui
também leaderboards ("quem mais desarmou"), que é o que um sistema RAG
descritivo bem construído precomputaria.

Isso é deliberado e não é generosidade com o baseline: sem paridade de
fatos, vencer as perguntas factuais não significaria nada — seria um sistema
COM o dado contra um sistema SEM o dado. Com paridade, o que sobra de
diferença é a REPRESENTAÇÃO (grafo consultável versus texto embeddado), que
é exatamente a variável que a pesquisa quer isolar.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
from pydantic_ai import Agent

from football_graphrag.config import get_settings
from football_graphrag.evaluation import match_facts
from football_graphrag.llm.provider import pydantic_ai_model

# Rankings precomputados. Sem eles, "quem mais desarmou?" exigiria do baseline
# uma agregação que texto plano não faz — e a pergunta viraria um teste de
# agregação, não de representação.
LEADERBOARDS = [
    ("jogadores com mais passes certos", "passes_certos"),
    ("jogadores com mais desarmes certos", "desarmes_certos"),
    ("jogadores com mais dribles certos", "dribles_certos"),
    ("jogadores com mais finalizações", "finalizacoes"),
    ("jogadores com mais interceptações", "interceptacoes"),
    ("jogadores com mais passes progressivos", "passes_progressivos"),
    ("goleiros com mais defesas", "defesas_do_goleiro"),
    ("jogadores com mais faltas cometidas", "faltas_cometidas"),
]

PROMPT_BASELINE = """\
Você é um analista de futebol. Responda a pergunta usando APENAS os trechos
de contexto fornecidos. Se a informação não estiver no contexto, diga que
não é possível responder com os dados disponíveis. Não invente. Responda em
português.
"""


def build_match_summary(match_id: int, data_dir: Path) -> list[str]:
    """Resumo textual da partida em chunks, com paridade de fatos com o grafo.

    Chunks emitidos:
    - um agregado por time (posse, passes, PPDA, field tilt, xT/VAEP);
    - um leaderboard por time e por estatística ("quem mais desarmou");
    - a ficha do jogo: gols, assistências e cartões;
    - uma súmula individual por jogador com volume relevante.
    """
    processed = data_dir / "processed"
    meta = json.loads((processed / f"{match_id}_meta.json").read_text())
    actions = pd.read_parquet(processed / f"{match_id}.parquet")
    phases = pd.read_parquet(processed / f"{match_id}_phases.parquet")

    por_jogador = match_facts.resumo_por_jogador(actions)
    por_time = match_facts.resumo_por_time(actions, phases)
    chunks: list[str] = []

    # --- agregado por time ---
    for team_id, team in meta["teams"].items():
        m = meta["team_metrics"].get(str(team_id)) or meta["team_metrics"][int(team_id)]
        if team not in por_time.index:
            continue
        # .loc numa linha de dtypes mistos devolve tudo como object/float:
        # sem o int() sairia "3.0 gols" no texto embeddado.
        t = por_time.loc[team]
        n = lambda campo: int(t[campo])
        chunks.append(
            f"Partida {match_id} — {team}: {n('gols')} gols, {n('finalizacoes')} finalizações "
            f"({n('finalizacoes_no_gol')} no gol), {n('passes_certos')} passes certos de "
            f"{n('passes_tentados')} ({t.precisao_passe_pct}% de acerto), "
            f"posse {t.get('posse_pct', 'n/d')}%, {n('desarmes_certos')} desarmes certos, "
            f"{n('interceptacoes')} interceptações, {n('faltas_cometidas')} faltas, "
            f"{n('cartoes_amarelos')} cartões amarelos. "
            f"PPDA 1º tempo {m['ppda_p1']:.1f}, PPDA 2º tempo {m['ppda_p2']:.1f}, "
            f"field tilt {m['field_tilt']:.0%}. xT total {t.xt_total:.3f}."
        )

    # --- leaderboards: o que um RAG descritivo precomputaria ---
    for rotulo, coluna in LEADERBOARDS:
        top = por_jogador.nlargest(5, coluna)
        top = top[top[coluna] > 0]
        if top.empty:
            continue
        chunks.append(
            f"Partida {match_id} — {rotulo}: "
            + "; ".join(f"{r.nome} ({r.time}): {getattr(r, coluna)}" for r in top.itertuples())
            + "."
        )

    # --- ficha do jogo ---
    gols = match_facts.gols_da_partida(actions)
    if len(gols):
        chunks.append(
            f"Partida {match_id} — gols: "
            + "; ".join(
                f"{g.player_name} ({g.team_name}) aos {g.minuto} min do {g.periodo_nome}"
                + (" de pênalti" if g.acao == "penalti" else "")
                for g in gols.itertuples()
            )
            + "."
        )
    assist = match_facts.assistencias(actions)
    if assist:
        nomes = por_jogador["nome"]
        chunks.append(
            f"Partida {match_id} — assistências: "
            + "; ".join(f"{nomes.get(pid, pid)}: {n}" for pid, n in assist.items())
            + "."
        )
    cartoes = match_facts.cartoes_da_partida(actions)
    if len(cartoes):
        chunks.append(
            f"Partida {match_id} — cartões amarelos: "
            + "; ".join(f"{c.player_name} ({c.team_name}) aos {c.minuto} min" for c in cartoes.itertuples())
            + "."
        )

    # --- súmula individual dos jogadores com volume ---
    for r in por_jogador.nlargest(24, "toques").itertuples():
        chunks.append(
            f"Partida {match_id} — {r.nome} ({r.time}): {r.toques} ações, "
            f"{r.passes_certos}/{r.passes_tentados} passes certos ({r.precisao_passe_pct}%), "
            f"{r.passes_progressivos} progressivos, {r.gols} gols, {r.assistencias} assistências, "
            f"{r.finalizacoes} finalizações ({r.finalizacoes_no_gol} no gol), "
            f"{r.dribles_certos}/{r.dribles_tentados} dribles certos, "
            f"{r.desarmes_certos}/{r.desarmes_tentados} desarmes certos, "
            f"{r.interceptacoes} interceptações, {r.cortes} cortes, "
            f"{r.faltas_cometidas} faltas, {r.cartoes_amarelos} cartões, "
            f"{r.defesas_do_goleiro} defesas de goleiro, xT {r.xt_total:.3f}."
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

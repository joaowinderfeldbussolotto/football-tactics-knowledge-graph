#!/usr/bin/env python
"""Avaliação (seção 9): três braços sobre as MESMAS perguntas e o mesmo modelo.

Braços:

1. ``grafo_sem_sumula`` — padrões da camada 2 no contexto; os números
   factuais só chegam se o agente escrever Cypher (``consultar_grafo``).
   É o braço que MEDE a autonomia do ADR-8.
2. ``grafo_com_sumula`` — o anterior mais a súmula pré-agregada (camada 1b)
   já no contexto. É o comportamento da API.
3. ``baseline`` — RAG vetorial plano, com paridade de fatos (ver
   ``evaluation/match_facts.py``).

Por que dois braços de grafo: entregar a súmula pronta economiza uma ida e
volta de ferramenta e cala o text-to-Cypher no mesmo gesto. A diferença entre
1 e 2 é a medida desse custo-benefício, em vez de uma escolha de design não
justificada. Ver ADR-10 em ``docs/05-decisoes.md``.

Duas notas de recuperação, e elas NÃO são intercambiáveis:

- ``retrieval_previo`` pontua o contexto que a recuperação entregou ANTES de
  o agente rodar. **É esta que compara com o baseline**, porque o contexto do
  baseline também é só o que a recuperação dele entregou.
- ``retrieval_final`` pontua esse contexto MAIS o resultado das consultas que
  o agente fez durante a geração. Mede o sistema inteiro, não a recuperação —
  e não tem contrapartida no baseline, que não tem ferramenta.

Até a 3ª rodada existia uma nota só, e ela era a ``final`` comparada contra a
``previo`` do baseline. A assimetria favorecia o grafo.

Salva ``data/processed/eval_results.json`` (ou o ``--saida`` pedido).
Requer chaves de LLM/embedder no .env.
"""

import argparse
import asyncio
import json
import logging

from football_graphrag.api import agents, retrieval
from football_graphrag.config import get_settings
from football_graphrag.observability import logging_setup
from football_graphrag.evaluation import baseline_rag, faithfulness, judges
from football_graphrag.evaluation.golden_dataset import GOLDEN_QUESTIONS
from football_graphrag.graph import db

logging_setup.setup(formato="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

CATEGORIAS = ("estrutural", "factual", "agregada", "composta")
# nome do braço -> passa a súmula no contexto?
BRACOS_GRAFO = {"grafo_sem_sumula": False, "grafo_com_sumula": True}


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


async def avaliar_grafo(driver, q, *, incluir_sumula: bool) -> dict:
    """Um braço do grafo, para uma pergunta."""
    patterns, stats, extra_facts, timings = await retrieval.retrieve_context(
        driver, q.match_id, q.pergunta, incluir_sumula=incluir_sumula
    )
    resposta = await agents.answer_question(
        q.pergunta, patterns, stats, extra_facts, driver, q.match_id
    )
    fid = faithfulness.check_citations(driver, resposta.metricas_citadas)
    qfid = faithfulness.check_queries(driver, resposta.consultas_executadas)

    contexto_previo = _json(patterns)
    if stats:
        contexto_previo += "\n\nSÚMULA RECUPERADA:\n" + _json(stats)
    contexto_final = contexto_previo
    if resposta.consultas_executadas:
        contexto_final += "\n\nCONSULTAS EXECUTADAS NO GRAFO:\n" + "\n".join(
            f"- {c.cypher} => {c.resultado_resumido}" for c in resposta.consultas_executadas
        )

    j_previo = await judges.judge_retrieval(q.pergunta, q.resposta_referencia, contexto_previo)
    # Sem consulta nenhuma os dois contextos são o MESMO texto. Reaproveitar a
    # nota (em vez de chamar o juiz de novo) evita que ruído de amostragem de
    # um juiz estocástico vire uma diferença aparente entre as duas métricas.
    j_final = (
        j_previo
        if contexto_final == contexto_previo
        else await judges.judge_retrieval(q.pergunta, q.resposta_referencia, contexto_final)
    )
    insight = await judges.judge_insight(q.pergunta, q.resposta_referencia, resposta.resposta)

    return {
        "resposta": resposta.resposta,
        "faithfulness": fid.score,
        "query_reexec": qfid.score,
        "n_consultas": len(resposta.consultas_executadas),
        "retrieval_previo": j_previo.score,
        "retrieval_final": j_final.score,
        "tactical_insight": insight.score,
        "timings": timings,
    }


async def avaliar_baseline(index, q) -> dict:
    resposta, contexto = await baseline_rag.answer_with_baseline(index, q.pergunta)
    r = await judges.judge_retrieval(q.pergunta, q.resposta_referencia, "\n".join(contexto))
    i = await judges.judge_insight(q.pergunta, q.resposta_referencia, resposta)
    # O baseline não tem ferramenta: só existe contexto prévio. O nome do
    # campo diz isso, para ninguém comparar com o retrieval_final do grafo.
    return {"resposta": resposta, "retrieval_previo": r.score, "tactical_insight": i.score}


def selecionar(args) -> list:
    if args.ids:
        pedidos = [i.strip() for i in args.ids.split(",") if i.strip()]
        escolhidas = [q for q in GOLDEN_QUESTIONS if q.id in pedidos]
        faltando = set(pedidos) - {q.id for q in escolhidas}
        if faltando:
            raise SystemExit(f"ids inexistentes no golden dataset: {sorted(faltando)}")
        return escolhidas
    if args.amostra:
        # a primeira de cada categoria: confere o pipeline dos três braços
        # sem comprometer as 30 perguntas
        return [next(q for q in GOLDEN_QUESTIONS if q.categoria == c) for c in CATEGORIAS]
    return list(GOLDEN_QUESTIONS)


async def main(args) -> None:
    settings = get_settings()
    if not settings.llm_api_key:
        raise SystemExit("LLM_API_KEY ausente no .env: a avaliação usa o agente e os juízes")
    perguntas = selecionar(args)
    driver = db.make_driver(settings)
    # Só as partidas das perguntas escolhidas: indexar as três com um
    # subconjunto de 4 perguntas gastaria cota de embeddings à toa.
    match_ids = sorted({q.match_id for q in perguntas})
    logger.info("%d perguntas, partidas %s", len(perguntas), match_ids)
    try:
        baseline_index = await baseline_rag.build_index(match_ids, settings.data_dir)
    except Exception as exc:
        # ex.: cota diária de embeddings esgotada (free tier). O lado do grafo
        # não usa embeddings — avalia só ele e registra o baseline como ausente.
        logger.warning("baseline indisponível (%s); avaliando só o sistema de grafo", exc)
        baseline_index = None

    results = []
    for q in perguntas:
        linha = {"id": q.id, "categoria": q.categoria, "insight": q.insight, "pergunta": q.pergunta}
        for braco, incluir in BRACOS_GRAFO.items():
            logger.info("%s [%s]", q.id, braco)
            linha[braco] = await avaliar_grafo(driver, q, incluir_sumula=incluir)
        if baseline_index is not None:
            logger.info("%s [baseline]", q.id)
            linha["baseline"] = await avaliar_baseline(baseline_index, q)
        else:
            linha["baseline"] = None
        results.append(linha)

    summary = _summarize(results, settings)
    out = settings.processed_dir / args.saida
    out.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n-> {out}")
    driver.close()


def _summarize(results: list[dict], settings) -> dict:
    def avg(rows, braco, metrica):
        vals = [r[braco][metrica] for r in rows if r.get(braco) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    by_cat = {}
    for cat in CATEGORIAS:
        rows = [r for r in results if r["categoria"] == cat]
        if not rows:
            continue
        entrada = {"n": len(rows)}
        for braco in BRACOS_GRAFO:
            entrada[braco] = {
                "retrieval_previo": avg(rows, braco, "retrieval_previo"),
                "retrieval_final": avg(rows, braco, "retrieval_final"),
                "insight": avg(rows, braco, "tactical_insight"),
                "consultas_media": avg(rows, braco, "n_consultas"),
            }
        entrada["baseline"] = {
            "retrieval_previo": avg(rows, "baseline", "retrieval_previo"),
            "insight": avg(rows, "baseline", "tactical_insight"),
        }
        by_cat[cat] = entrada

    return {
        "modelo": agents.settings_fingerprint(settings),
        "n_perguntas": len(results),
        "faithfulness_media": {
            braco: round(sum(r[braco]["faithfulness"] for r in results) / len(results), 4)
            for braco in BRACOS_GRAFO
        },
        "por_categoria": by_cat,
    }


def _args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sel = p.add_mutually_exclusive_group()
    sel.add_argument("--amostra", action="store_true", help="uma pergunta de cada categoria")
    sel.add_argument("--ids", help="ids separados por vírgula (ex.: q01,q17)")
    p.add_argument("--saida", default="eval_results.json", help="nome do arquivo em data/processed")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_args()))

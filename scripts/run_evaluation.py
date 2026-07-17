#!/usr/bin/env python
"""Avaliação completa (seção 9): sistema de grafo vs baseline vetorial.

Para cada pergunta do golden dataset:
1. Sistema de grafo: recuperação estruturada+híbrida -> agente -> fidelidade
   determinística + juízes (retrieval_accuracy, tactical_insight).
2. Baseline vetorial plano: resumo agregado embeddado -> agente -> juízes.

Salva data/processed/eval_results.json com a tabela comparativa — o
resultado central do trabalho. Requer chaves de LLM/embedder no .env.
"""

import asyncio
import json
import logging

from football_graphrag.api import agents, retrieval
from football_graphrag.config import get_settings
from football_graphrag.evaluation import baseline_rag, faithfulness, judges
from football_graphrag.evaluation.golden_dataset import GOLDEN_QUESTIONS
from football_graphrag.graph import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    if not settings.llm_api_key:
        raise SystemExit("LLM_API_KEY ausente no .env: a avaliação usa o agente e os juízes")
    driver = db.make_driver(settings)
    match_ids = sorted({q.match_id for q in GOLDEN_QUESTIONS})
    baseline_index = await baseline_rag.build_index(match_ids, settings.data_dir)

    results = []
    for q in GOLDEN_QUESTIONS:
        logger.info("pergunta %s", q.id)
        # --- sistema de grafo ---
        patterns, extra_facts, timings = await retrieval.retrieve_context(driver, q.match_id, q.pergunta)
        graph_answer = await agents.answer_question(q.pergunta, patterns, extra_facts)
        fid = faithfulness.check_citations(driver, graph_answer.metricas_citadas)
        contexto_str = json.dumps(patterns, ensure_ascii=False, default=str)
        graph_retrieval = await judges.judge_retrieval(q.pergunta, q.resposta_referencia, contexto_str)
        graph_insight = await judges.judge_insight(q.pergunta, q.resposta_referencia, graph_answer.resposta)
        # --- baseline vetorial ---
        base_answer, base_context = await baseline_rag.answer_with_baseline(baseline_index, q.pergunta)
        base_retrieval = await judges.judge_retrieval(q.pergunta, q.resposta_referencia, "\n".join(base_context))
        base_insight = await judges.judge_insight(q.pergunta, q.resposta_referencia, base_answer)

        results.append(
            {
                "id": q.id,
                "categoria": q.categoria,
                "insight": q.insight,
                "pergunta": q.pergunta,
                "grafo": {
                    "resposta": graph_answer.resposta,
                    "faithfulness": fid.score,
                    "retrieval_accuracy": graph_retrieval.score,
                    "tactical_insight": graph_insight.score,
                    "timings": timings,
                },
                "baseline": {
                    "resposta": base_answer,
                    "retrieval_accuracy": base_retrieval.score,
                    "tactical_insight": base_insight.score,
                },
            }
        )

    out = settings.processed_dir / "eval_results.json"
    summary = _summarize(results)
    out.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    driver.close()


def _summarize(results: list[dict]) -> dict:
    def avg(rows, system, metric):
        vals = [r[system][metric] for r in rows]
        return round(sum(vals) / len(vals), 2) if vals else None

    by_cat = {}
    for cat in ("estrutural", "agregada"):
        rows = [r for r in results if r["categoria"] == cat]
        by_cat[cat] = {
            "n": len(rows),
            "grafo_retrieval": avg(rows, "grafo", "retrieval_accuracy"),
            "grafo_insight": avg(rows, "grafo", "tactical_insight"),
            "baseline_retrieval": avg(rows, "baseline", "retrieval_accuracy"),
            "baseline_insight": avg(rows, "baseline", "tactical_insight"),
        }
    return {
        "faithfulness_media": round(sum(r["grafo"]["faithfulness"] for r in results) / len(results), 4),
        "por_categoria": by_cat,
    }


if __name__ == "__main__":
    asyncio.run(main())

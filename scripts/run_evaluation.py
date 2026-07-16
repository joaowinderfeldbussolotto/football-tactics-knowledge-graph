#!/usr/bin/env python3
"""Roda o golden dataset (seção 8 do plano) contra a API já rodando e imprime
os scores de fidelidade + LLM-as-judge.

Pré-requisitos: a API (`docker compose up` ou `uvicorn ... --reload`) e a
partida já ingerida (`POST /ingest/{match_id}`) — este script consome
`GET /report/{match_id}` pela rede, não chama o pipeline diretamente.

Uso:
    python scripts/run_evaluation.py 15946
    python scripts/run_evaluation.py 15946 --api-base http://localhost:8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx  # noqa: E402

from football_graphrag.api.schemas import TacticalReport  # noqa: E402
from football_graphrag.config import get_settings  # noqa: E402
from football_graphrag.evaluation.faithfulness import check_faithfulness  # noqa: E402
from football_graphrag.evaluation.golden_dataset import build_golden_dataset  # noqa: E402
from football_graphrag.evaluation.judges import judge_retrieval_accuracy, judge_tactical_insight  # noqa: E402
from football_graphrag.graph.client import build_graphiti  # noqa: E402
from football_graphrag.ingestion.pipeline import DATA_PROCESSED_DIR  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _report_context(report: TacticalReport) -> str:
    citations = "\n".join(
        f"- {c.edge_type}.{c.attribute}={c.value} (node_id={c.node_id})" for c in report.cited_metrics
    )
    return f"{report.narrative}\n\nMétricas citadas:\n{citations}"


async def run_evaluation(match_id: str, api_base: str) -> dict:
    settings = get_settings()

    async with httpx.AsyncClient(base_url=api_base, timeout=120.0) as client:
        response = await client.get(f"/report/{match_id}")
        response.raise_for_status()
        report = TacticalReport.model_validate(response.json())

    graphiti = build_graphiti(settings)
    try:
        faithfulness = await check_faithfulness(graphiti, report)
    finally:
        await graphiti.close()

    context = _report_context(report)
    questions = build_golden_dataset(match_id)

    retrieval_scores = []
    for question in questions:
        score = await judge_retrieval_accuracy(settings, question.question, question.reference_answer, context)
        retrieval_scores.append({"question_id": question.id, "score": score.score, "rationale": score.rationale})
        logger.info("retrieval_accuracy[%s] = %.2f", question.id, score.score)

    insight_score = await judge_tactical_insight(settings, report.narrative)
    logger.info("tactical_insight = %.2f", insight_score.score)

    avg_retrieval = sum(r["score"] for r in retrieval_scores) / len(retrieval_scores) if retrieval_scores else 0.0

    return {
        "match_id": match_id,
        "n_golden_questions": len(questions),
        "faithfulness": {
            "score": faithfulness.score,
            "n_checked": faithfulness.n_checked,
            "n_faithful": faithfulness.n_faithful,
            "details": [
                {"attribute": c.citation.attribute, "faithful": c.faithful, "reason": c.reason}
                for c in faithfulness.checks
            ],
        },
        "retrieval_accuracy": {"average": avg_retrieval, "per_question": retrieval_scores},
        "tactical_insight": {"score": insight_score.score, "rationale": insight_score.rationale},
    }


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python scripts/run_evaluation.py <match_id> [--api-base http://localhost:8000]")

    match_id = sys.argv[1]
    api_base = "http://localhost:8000"
    if "--api-base" in sys.argv:
        api_base = sys.argv[sys.argv.index("--api-base") + 1]

    results = asyncio.run(run_evaluation(match_id, api_base))

    output_path = DATA_PROCESSED_DIR / "eval_results.json"
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    logger.info("Resultados salvos -> %s", output_path)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

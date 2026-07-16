"""GET /live/{match_id}/insights: consulta híbrida (sem LLM) + geração de um
alerta tático (seção 7/9, critério 3: retrieval deve responder em <1s)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from football_graphrag.api.schemas import LiveInsightsResponse
from football_graphrag.api.tactical_agent import build_tactical_agent, format_facts_context
from football_graphrag.graph.client import get_match_facts

router = APIRouter()

_LIVE_QUERY = "eventos táticos recentes: pressão, passes progressivos, xT, VAEP, fases de posse"


@router.get("/live/{match_id}/insights", response_model=LiveInsightsResponse)
async def get_live_insights(match_id: str, request: Request, since_minute: float | None = None) -> LiveInsightsResponse:
    graphiti = request.app.state.graphiti
    settings = request.app.state.settings

    retrieval_start = time.monotonic()
    facts = await get_match_facts(graphiti, match_id, _LIVE_QUERY, num_results=15)
    retrieval_ms = (time.monotonic() - retrieval_start) * 1000

    since_note = f" (considere só fatos relevantes a partir do minuto {since_minute:.1f})" if since_minute else ""
    user_prompt = (
        f"Gere um alerta tático curto para a partida {match_id}, com base no estado atual do grafo{since_note}.\n\n"
        f"Fatos disponíveis para citação em cited_metrics:\n{format_facts_context(facts)}"
    )

    agent = build_tactical_agent(settings)
    generation_start = time.monotonic()
    async with request.app.state.llm_semaphore:
        result = await agent.run(user_prompt)
    generation_ms = (time.monotonic() - generation_start) * 1000

    return LiveInsightsResponse(
        match_id=match_id,
        since_minute=since_minute,
        report=result.output,
        retrieval_ms=retrieval_ms,
        generation_ms=generation_ms,
        n_facts_retrieved=len(facts),
    )

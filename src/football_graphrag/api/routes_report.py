"""GET /report/{match_id}: relatório tático pós-jogo (modo batch, seção 7).

Dispara detecção de comunidades sobre o grafo completo da partida (só faz
sentido depois da ingestão completa) e pede ao agente para sintetizar um
`TacticalReport` grounded nos resumos de comunidade + fatos recuperados.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from football_graphrag.api.schemas import TacticalReport
from football_graphrag.api.tactical_agent import build_tactical_agent, format_facts_context
from football_graphrag.graph.client import get_match_facts
from football_graphrag.graph.communities import build_match_communities

router = APIRouter()

_REPORT_QUERY = "métricas táticas da partida: xT, VAEP, PPDA, pressão, passes progressivos, fases de posse"


@router.get("/report/{match_id}", response_model=TacticalReport)
async def get_report(match_id: str, request: Request) -> TacticalReport:
    graphiti = request.app.state.graphiti
    settings = request.app.state.settings

    communities = await build_match_communities(graphiti, match_id)
    facts = await get_match_facts(graphiti, match_id, _REPORT_QUERY, num_results=30)

    if not communities and not facts:
        raise HTTPException(
            404,
            f"Nada encontrado no grafo para a partida {match_id}. Rode POST /ingest/{match_id} primeiro.",
        )

    community_summaries = "\n".join(f"- {c.name}: {c.summary}" for c in communities) or "Nenhuma comunidade detectada."
    user_prompt = (
        f"Escreva um relatório tático pós-jogo da partida {match_id}.\n\n"
        f"Resumos de comunidades detectadas no grafo:\n{community_summaries}\n\n"
        f"Fatos individuais disponíveis para citação em cited_metrics:\n{format_facts_context(facts)}"
    )

    agent = build_tactical_agent(settings)
    async with request.app.state.llm_semaphore:
        result = await agent.run(user_prompt)

    return result.output

"""GET /ask/{match_id}?q=...: pergunta livre sobre uma partida já ingerida.

Reaproveita exatamente o mesmo retrieval de `/live/.../insights`
(`graph.client.get_match_facts`, busca híbrida sem LLM) e o mesmo padrão de
geração estruturada de `/report`, mas com a query vindo do usuário em vez de
uma string fixa, e um system prompt orientado a responder a pergunta
específica (`tactical_agent.build_qa_agent`) em vez de sempre escrever uma
síntese completa da partida.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request

from football_graphrag.api.schemas import AskResponse
from football_graphrag.api.tactical_agent import build_qa_agent, format_facts_context
from football_graphrag.graph.client import get_match_facts

router = APIRouter()


@router.get("/ask/{match_id}", response_model=AskResponse)
async def ask_question(match_id: str, request: Request, q: str) -> AskResponse:
    if not q or not q.strip():
        raise HTTPException(400, "Parâmetro 'q' é obrigatório e não pode ser vazio.")

    graphiti = request.app.state.graphiti
    settings = request.app.state.settings

    retrieval_start = time.monotonic()
    facts = await get_match_facts(graphiti, match_id, q, num_results=15)
    retrieval_ms = (time.monotonic() - retrieval_start) * 1000

    user_prompt = (
        f"Pergunta sobre a partida {match_id}: {q}\n\n"
        f"Fatos disponíveis para citação em cited_metrics:\n{format_facts_context(facts)}"
    )

    agent = build_qa_agent(settings)
    generation_start = time.monotonic()
    async with request.app.state.llm_semaphore:
        result = await agent.run(user_prompt)
    generation_ms = (time.monotonic() - generation_start) * 1000

    return AskResponse(
        match_id=match_id,
        question=q,
        report=result.output,
        retrieval_ms=retrieval_ms,
        generation_ms=generation_ms,
        n_facts_retrieved=len(facts),
    )

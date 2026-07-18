"""Endpoints da API (camada 3)."""

import logging
import time

from fastapi import APIRouter, HTTPException, Request

from football_graphrag.api import agents, retrieval, schemas
from football_graphrag.config import get_settings
from football_graphrag.graph import analysis
from football_graphrag.graph.build import build_factual_graph, graph_stats
from football_graphrag.ingestion.pipeline import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


def _driver(request: Request):
    return request.app.state.driver


def _graphiti(request: Request):
    return getattr(request.app.state, "graphiti", None)


def _require_llm() -> None:
    settings = get_settings()
    if not (settings.llm_api_key and settings.llm_model):
        raise HTTPException(
            status_code=503,
            detail="LLM_API_KEY/LLM_MODEL ausentes no .env: este endpoint usa o agente de verbalização (camada 3)",
        )


@router.get("/health")
async def health(request: Request):
    try:
        with _driver(request).session() as session:
            session.run("RETURN 1").consume()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Neo4j indisponível: {exc}") from exc
    return {"status": "ok", "llm": agents.settings_fingerprint(get_settings())}


@router.post("/ingest/{match_id}", response_model=schemas.IngestResponse)
async def ingest(match_id: int, request: Request):
    """Roda camada 0 (pipeline) e camada 1 (grafo factual). Sem LLM."""
    settings = get_settings()
    pipeline_meta = run_pipeline(match_id, settings.data_dir)
    graph_result = build_factual_graph(match_id, settings.data_dir, _driver(request))
    return schemas.IngestResponse(match_id=match_id, pipeline=pipeline_meta, graph=graph_result)


@router.post("/analyze/{match_id}", response_model=schemas.AnalyzeResponse)
async def analyze(match_id: int, request: Request):
    """Roda camada 2 (insights via GDS) e indexa no Graphiti se configurado."""
    settings = get_settings()
    results = analysis.run_all(_driver(request), match_id, settings.data_dir)
    graphiti = _graphiti(request)
    if graphiti is not None:
        from football_graphrag.graph.communities import build_pattern_communities, index_match_patterns

        await index_match_patterns(graphiti, _driver(request), match_id)
        await build_pattern_communities(graphiti, match_id)
    return schemas.AnalyzeResponse(match_id=match_id, padroes_por_tipo=results)


@router.get("/report/{match_id}", response_model=schemas.RelatorioTatico)
async def report(match_id: int, request: Request):
    """Relatório tático: padrões via Cypher direto (sabemos o que queremos) +
    ficha factual via consultar_grafo (ADR-8). O agente não calcula nada —
    todo fato vem de padrão ou de consulta auditável."""
    _require_llm()
    patterns = retrieval.fetch_all_patterns(_driver(request), match_id)
    if not patterns:
        raise HTTPException(status_code=404, detail=f"sem padrões para {match_id}; rode /analyze antes")
    t0 = time.perf_counter()
    result = await agents.generate_report(patterns, _driver(request), match_id)
    logger.info("relatório %s gerado em %.2fs (%d padrões)", match_id, time.perf_counter() - t0, len(patterns))
    return result


@router.post("/ask", response_model=schemas.RespostaTatica)
async def ask(body: schemas.AskRequest, request: Request):
    """Q&A: recuperação estruturada + híbrida (sem LLM), geração com citação."""
    _require_llm()
    patterns, extra_facts, timings = await retrieval.retrieve_context(
        _driver(request), body.match_id, body.pergunta, _graphiti(request)
    )
    t0 = time.perf_counter()
    result = await agents.answer_question(
        body.pergunta, patterns, extra_facts, _driver(request), body.match_id
    )
    timings["generation_seconds"] = round(time.perf_counter() - t0, 4)
    logger.info("ask %s: %s", body.match_id, timings)
    return result


@router.get("/graph/{match_id}/stats")
async def stats(match_id: int, request: Request):
    return graph_stats(_driver(request), match_id)

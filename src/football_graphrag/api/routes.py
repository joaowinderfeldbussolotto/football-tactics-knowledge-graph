"""Endpoints da API (camada 3)."""

import logging
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic_ai.exceptions import UnexpectedModelBehavior

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


def _erro_do_modelo(exc: UnexpectedModelBehavior) -> HTTPException:
    """502 com mensagem acionável no lugar de um 500 com traceback.

    ``UnexpectedModelBehavior`` é o modelo (ou o provedor) devolvendo algo que
    não dá para usar — não é bug da aplicação, e quem chamou a API precisa saber
    o que ajustar. O caso que motivou isto: ``finish_reason: length`` sem texto,
    típico de modelo de raciocínio cujo raciocínio consumiu o teto de tokens.
    """
    texto = str(exc)
    if "token limit" in texto:
        detalhe = (
            "O modelo esgotou o limite de tokens de saída antes de produzir resposta "
            "(em modelo de raciocínio, o raciocínio oculto conta contra o limite). "
            "Aumente LLM_MAX_TOKENS ou, no openrouter, defina LLM_REASONING_EFFORT=low, "
            f"reinicie a API e tente de novo. Detalhe: {texto}"
        )
    else:
        detalhe = f"O modelo devolveu uma resposta inutilizável: {texto}"
    return HTTPException(status_code=502, detail=detalhe)


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
    """Roda a camada 2 (insights via GDS). Determinística, sem LLM, sem custo.

    Esta rota NÃO toca no Graphiti. Já tocou: indexava os padrões e construía
    as comunidades aqui, e isso tinha três problemas que pesaram mais que a
    conveniência — apagava o índice da partida a cada chamada (``limpar=True``)
    repagando todas as chamadas de LLM, uma falha intermitente do provedor
    virava 500 mesmo com a análise já gravada, e quem chamava ``/analyze`` só
    para refazer a camada 2 gastava dinheiro sem saber.

    O índice do Graphiti, que alimenta a busca híbrida do ``/ask``, é
    construído por ``scripts/index_graphiti.py``: retomável, não destrutivo por
    padrão, e que mostra o estado antes de agir (ADR-13).
    """
    settings = get_settings()
    results = analysis.run_all(_driver(request), match_id, settings.data_dir)
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
    try:
        result = await agents.generate_report(patterns, _driver(request), match_id)
    except UnexpectedModelBehavior as exc:
        logger.exception("relatório %s: modelo devolveu resposta inutilizável", match_id)
        raise _erro_do_modelo(exc) from exc
    logger.info("relatório %s gerado em %.2fs (%d padrões)", match_id, time.perf_counter() - t0, len(patterns))
    return result


@router.post("/ask", response_model=schemas.RespostaTatica)
async def ask(body: schemas.AskRequest, request: Request):
    """Q&A: recuperação estruturada + híbrida (sem LLM), geração com citação."""
    _require_llm()
    patterns, stats, extra_facts, timings = await retrieval.retrieve_context(
        _driver(request), body.match_id, body.pergunta, _graphiti(request)
    )
    t0 = time.perf_counter()
    try:
        result = await agents.answer_question(
            body.pergunta, patterns, stats, extra_facts, _driver(request), body.match_id
        )
    except UnexpectedModelBehavior as exc:
        logger.exception("ask %s: modelo devolveu resposta inutilizável", body.match_id)
        raise _erro_do_modelo(exc) from exc
    timings["generation_seconds"] = round(time.perf_counter() - t0, 4)
    logger.info("ask %s: %s", body.match_id, timings)
    return result


@router.get("/graph/{match_id}/stats")
async def stats(match_id: int, request: Request):
    return graph_stats(_driver(request), match_id)

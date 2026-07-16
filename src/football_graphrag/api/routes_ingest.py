"""POST /ingest/{match_id} (modo batch) e POST /replay/{match_id}/start."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request

from football_graphrag.api.schemas import IngestResponse, ReplayStartResponse
from football_graphrag.graph.client import ingest_match_batch
from football_graphrag.ingestion.pipeline import DATA_PROCESSED_DIR
from football_graphrag.ingestion.replay import run_producer

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ingest/{match_id}", response_model=IngestResponse)
async def ingest_match(match_id: str, request: Request, mode: str = "batch") -> IngestResponse:
    if mode != "batch":
        raise HTTPException(400, f"mode='{mode}' não suportado; use mode=batch (replay usa /replay/{{match_id}}/start).")

    graphiti = request.app.state.graphiti
    try:
        summaries = await ingest_match_batch(graphiti, match_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    return IngestResponse(match_id=match_id, mode=mode, n_phases_ingested=len(summaries))


@router.post("/replay/{match_id}/start", response_model=ReplayStartResponse)
async def start_replay(match_id: str, request: Request) -> ReplayStartResponse:
    parquet_path = DATA_PROCESSED_DIR / f"{match_id}.parquet"
    if not parquet_path.exists():
        raise HTTPException(404, f"{parquet_path} não existe. Rode a ingestão offline primeiro.")

    settings = request.app.state.settings
    tasks = request.app.state.replay_producer_tasks
    if match_id in tasks and not tasks[match_id].done():
        return ReplayStartResponse(match_id=match_id, status="already_running")

    async def _run() -> None:
        try:
            await run_producer(match_id, settings.redis_url, speed=settings.statsbomb_replay_speed)
        except Exception:
            logger.exception("Produtor de replay falhou para a partida %s", match_id)

    tasks[match_id] = asyncio.create_task(_run())
    return ReplayStartResponse(match_id=match_id, status="started")

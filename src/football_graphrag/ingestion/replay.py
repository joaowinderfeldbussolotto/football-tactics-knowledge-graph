"""Replay "ao vivo" simulado via fila Redis (seção 6.5 do plano da PoC).

Dois papéis, pensados para rodar como processos/tasks independentes:

- `run_producer`: lê o parquet processado de uma partida e publica cada fase
  de posse na fila Redis `match:{match_id}:events`, respeitando o intervalo
  real entre timestamps dividido por `STATSBOMB_REPLAY_SPEED`. Rápido, nunca
  bloqueia no grafo.
- `run_consumer`: roda no container `replay-worker` (`python -m
  football_graphrag.ingestion.replay`). Faz BRPOP nas filas de todas as
  partidas em `STATSBOMB_MATCH_IDS`, ingere cada fase no grafo via
  `graph.client.ingest_possession_phase` (chamada de LLM, lento) e mede o
  lag de ingestão: minuto de jogo publicado - minuto de jogo já escrito.

Essa separação existe porque o consumidor (que dispara LLM) é uma ordem de
grandeza mais lento que o produtor (que só respeita o relógio do jogo); ver
a discussão completa na seção 6.5 do plano.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd
import redis.asyncio as redis

from football_graphrag.config import Settings, get_settings
from football_graphrag.graph.client import build_graphiti, ingest_possession_phase
from football_graphrag.ingestion.pipeline import DATA_PROCESSED_DIR

logger = logging.getLogger(__name__)

_END_OF_MATCH = "__end_of_match__"


def _queue_key(match_id: str) -> str:
    return f"match:{match_id}:events"


def _producer_minute_key(match_id: str) -> str:
    return f"match:{match_id}:producer_minute"


def _ingested_minute_key(match_id: str) -> str:
    return f"match:{match_id}:ingested_minute"


def _json_default(value: Any):
    if hasattr(value, "item"):  # numpy scalars
        return value.item()
    return str(value)


def _phase_minute(phase_actions: pd.DataFrame) -> float:
    first = phase_actions.iloc[0]
    return 45.0 * max(int(first["period_id"]) - 1, 0) + float(first["time_seconds"]) / 60.0


def _phase_to_payload(match_id: str, phase_id: int, phase_actions: pd.DataFrame) -> str:
    records = phase_actions.where(pd.notna(phase_actions), None).to_dict(orient="records")
    return json.dumps({"match_id": match_id, "phase_id": phase_id, "actions": records}, default=_json_default)


async def run_producer(
    match_id: str,
    redis_url: str,
    processed_dir: Path = DATA_PROCESSED_DIR,
    speed: float = 60.0,
) -> None:
    """Publica todas as fases de posse de uma partida na fila Redis,
    respeitando o relógio do jogo (dividido por `speed`)."""
    parquet_path = processed_dir / f"{match_id}.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"{parquet_path} não existe. Rode `scripts/run_ingestion.py {match_id}` primeiro."
        )

    actions = pd.read_parquet(parquet_path).sort_values(["period_id", "time_seconds"])
    phases = list(actions.groupby("phase_id", sort=True))

    client = redis.from_url(redis_url)
    try:
        prev_absolute_seconds: float | None = None
        for phase_id, phase_actions in phases:
            first = phase_actions.iloc[0]
            absolute_seconds = 2700.0 * max(int(first["period_id"]) - 1, 0) + float(first["time_seconds"])

            if prev_absolute_seconds is not None:
                wait = max(absolute_seconds - prev_absolute_seconds, 0.0) / speed
                if wait > 0:
                    await asyncio.sleep(wait)
            prev_absolute_seconds = absolute_seconds

            payload = _phase_to_payload(match_id, int(phase_id), phase_actions)
            await client.lpush(_queue_key(match_id), payload)
            await client.set(_producer_minute_key(match_id), _phase_minute(phase_actions))
            logger.info(
                "produtor[%s]: fase %s publicada (minuto %.1f, fila=%d)",
                match_id, phase_id, _phase_minute(phase_actions), await client.llen(_queue_key(match_id)),
            )

        await client.lpush(_queue_key(match_id), json.dumps({"match_id": match_id, "type": _END_OF_MATCH}))
        logger.info("produtor[%s]: fim da partida publicado", match_id)
    finally:
        await client.aclose()


async def _consume_one(graphiti, redis_client: redis.Redis, match_id: str, raw_payload: bytes, metrics: list[dict]) -> bool:
    """Processa um item da fila. Retorna False se for o sentinela de fim de partida."""
    payload = json.loads(raw_payload)
    if payload.get("type") == _END_OF_MATCH:
        logger.info("consumidor[%s]: fim da partida recebido", match_id)
        return False

    phase_actions = pd.DataFrame(payload["actions"])
    started_at = time.monotonic()
    await ingest_possession_phase(graphiti, match_id, payload["phase_id"], phase_actions)
    elapsed = time.monotonic() - started_at

    ingested_minute = _phase_minute(phase_actions)
    await redis_client.set(_ingested_minute_key(match_id), ingested_minute)

    producer_minute_raw = await redis_client.get(_producer_minute_key(match_id))
    producer_minute = float(producer_minute_raw) if producer_minute_raw is not None else ingested_minute
    queue_depth = await redis_client.llen(_queue_key(match_id))

    metrics.append(
        {
            "wall_clock": time.time(),
            "phase_id": payload["phase_id"],
            "producer_minute": producer_minute,
            "ingested_minute": ingested_minute,
            "lag_minutes": max(producer_minute - ingested_minute, 0.0),
            "queue_depth": queue_depth,
            "ingestion_seconds": elapsed,
        }
    )
    logger.info(
        "consumidor[%s]: fase %s ingerida em %.2fs (lag=%.1f min, fila=%d)",
        match_id, payload["phase_id"], elapsed, metrics[-1]["lag_minutes"], queue_depth,
    )
    return True


async def run_consumer(settings: Settings | None = None) -> None:
    """Loop principal do worker: BRPOP nas filas de todas as partidas
    configuradas em STATSBOMB_MATCH_IDS, ingerindo cada fase no grafo."""
    settings = settings or get_settings()
    match_ids = settings.match_ids
    if not match_ids:
        raise SystemExit("STATSBOMB_MATCH_IDS está vazio; nada para o replay-worker consumir.")

    graphiti = build_graphiti(settings)
    redis_client = redis.from_url(settings.redis_url)
    queue_keys = [_queue_key(m) for m in match_ids]
    metrics_by_match: dict[str, list[dict]] = {m: [] for m in match_ids}
    active_matches = set(match_ids)

    logger.info("replay-worker escutando: %s", queue_keys)
    try:
        while active_matches:
            result = await redis_client.brpop(
                [_queue_key(m) for m in active_matches], timeout=5
            )
            if result is None:
                continue

            queue_key, raw_payload = result
            match_id = queue_key.decode().split(":")[1] if isinstance(queue_key, bytes) else queue_key.split(":")[1]

            keep_going = await _consume_one(graphiti, redis_client, match_id, raw_payload, metrics_by_match[match_id])
            if not keep_going:
                active_matches.discard(match_id)
                metrics_path = DATA_PROCESSED_DIR / f"{match_id}_replay_metrics.json"
                metrics_path.write_text(json.dumps(metrics_by_match[match_id], indent=2))
                logger.info("Métricas de replay salvas -> %s", metrics_path)
    finally:
        await redis_client.aclose()
        await graphiti.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_consumer())


if __name__ == "__main__":
    main()

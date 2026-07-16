#!/usr/bin/env python3
"""Demo standalone do replay "ao vivo" (seção 6.5), sem precisar subir a API
nem o container `replay-worker` separado: roda produtor e consumidor no
mesmo processo, contra o Neo4j/Redis reais configurados no `.env`.

Pré-requisito: a partida já processada (`scripts/run_ingestion.py {match_id}`).

Uso:
    python scripts/run_replay_demo.py 15946
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from football_graphrag.config import get_settings  # noqa: E402
from football_graphrag.ingestion.replay import run_consumer, run_producer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main(match_id: str) -> None:
    settings = get_settings()
    # Restringe o consumidor a essa única partida, mesmo que STATSBOMB_MATCH_IDS
    # no .env liste outras.
    demo_settings = settings.model_copy(update={"statsbomb_match_ids": match_id})

    logger.info("Iniciando replay demo da partida %s (speed=%sx)...", match_id, settings.statsbomb_replay_speed)
    producer_task = asyncio.create_task(
        run_producer(match_id, settings.redis_url, speed=settings.statsbomb_replay_speed)
    )
    consumer_task = asyncio.create_task(run_consumer(demo_settings))

    await producer_task
    await consumer_task
    logger.info("Replay demo concluído. Veja data/processed/%s_replay_metrics.json para a série de lag.", match_id)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python scripts/run_replay_demo.py <match_id>")
    asyncio.run(main(sys.argv[1]))

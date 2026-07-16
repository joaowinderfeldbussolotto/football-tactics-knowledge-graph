#!/usr/bin/env python3
"""Roda o pipeline offline completo (download -> SPADL -> xT/VAEP -> métricas
táticas -> parquet processado) para uma ou mais partidas.

Uso:
    python scripts/run_ingestion.py                  # usa STATSBOMB_MATCH_IDS do .env
    python scripts/run_ingestion.py 3869151 3869685   # IDs explícitos

Este script só produz `data/processed/{match_id}.parquet`; carregar esses
dados no grafo é feito depois, via `graph.client.ingest_match` (chamado pela
API em `POST /ingest/{match_id}` ou por `scripts/run_replay_demo.py`).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from football_graphrag.config import get_settings  # noqa: E402
from football_graphrag.ingestion.pipeline import run_ingestion_pipeline  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    match_ids = sys.argv[1:] or get_settings().match_ids
    if not match_ids:
        raise SystemExit(
            "Nenhum match_id informado. Passe IDs como argumento ou preencha STATSBOMB_MATCH_IDS no .env."
        )

    paths = run_ingestion_pipeline(match_ids)
    logger.info("Concluído. Parquets gerados: %s", [str(p) for p in paths])


if __name__ == "__main__":
    main()

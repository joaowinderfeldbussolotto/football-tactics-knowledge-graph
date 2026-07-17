#!/usr/bin/env python
"""Roda a camada 0 (pipeline determinística) para as partidas do .env.

Uso: python scripts/run_pipeline.py [match_id ...]
Sem argumentos usa STATSBOMB_MATCH_IDS do .env.
"""

import logging
import sys

from football_graphrag.config import get_settings
from football_graphrag.ingestion.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

if __name__ == "__main__":
    settings = get_settings()
    match_ids = [int(a) for a in sys.argv[1:]] or settings.match_ids
    for match_id in match_ids:
        meta = run_pipeline(match_id, settings.data_dir)
        print(
            f"[{match_id}] {meta['n_kloppy_events']} eventos kloppy -> "
            f"{meta['n_spadl_actions']} ações SPADL ({meta['n_phases']} fases de posse) "
            f"em {meta['elapsed_seconds']}s"
        )

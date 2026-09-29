#!/usr/bin/env python
"""Baixa (com cache) os dados brutos do StatsBomb Open Data para o data/raw.

Uso: python scripts/download_statsbomb.py [match_id ...]
"""

import logging
import sys

from football_graphrag.config import get_settings
from football_graphrag.ingestion.statsbomb_loader import download_match

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

if __name__ == "__main__":
    settings = get_settings()
    match_ids = [int(a) for a in sys.argv[1:]] or settings.match_ids
    for match_id in match_ids:
        files = download_match(match_id, settings.raw_dir)
        print(f"[{match_id}] events={files.events} lineups={files.lineups} 360={files.three_sixty}")

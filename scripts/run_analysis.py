#!/usr/bin/env python
"""Roda a camada 2 (insights via GDS) para as partidas do .env."""

import logging
import sys

from football_graphrag.config import get_settings
from football_graphrag.graph import analysis, db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

if __name__ == "__main__":
    settings = get_settings()
    match_ids = [int(a) for a in sys.argv[1:]] or settings.match_ids
    driver = db.make_driver(settings)
    try:
        for match_id in match_ids:
            results = analysis.run_all(driver, match_id, settings.data_dir)
            total = sum(results.values())
            print(f"[{match_id}] {total} padrões táticos: {results}")
    finally:
        driver.close()

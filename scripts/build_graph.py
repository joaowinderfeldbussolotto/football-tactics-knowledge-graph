#!/usr/bin/env python
"""Roda a camada 1 (grafo factual determinístico) para as partidas do .env."""

import sys

from football_graphrag.config import get_settings
from football_graphrag.observability import logging_setup
from football_graphrag.graph import db
from football_graphrag.graph.build import build_factual_graph, graph_stats

logging_setup.setup()

if __name__ == "__main__":
    settings = get_settings()
    match_ids = [int(a) for a in sys.argv[1:]] or settings.match_ids
    driver = db.make_driver(settings)
    try:
        for match_id in match_ids:
            result = build_factual_graph(match_id, settings.data_dir, driver)
            print(f"[{match_id}] {result['total_writes']} escritas em {result['elapsed_seconds']}s")
            print(f"  stats: {graph_stats(driver, match_id)}")
    finally:
        driver.close()

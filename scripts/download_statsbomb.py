#!/usr/bin/env python3
"""Baixa e cacheia N partidas do StatsBomb Open Data em data/raw/.

Uso:
    python scripts/download_statsbomb.py                  # usa STATSBOMB_MATCH_IDS do .env
    python scripts/download_statsbomb.py 3869151 3869685   # IDs explícitos
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from football_graphrag.config import get_settings  # noqa: E402
from football_graphrag.ingestion.statsbomb_loader import download_match  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    match_ids = sys.argv[1:] or get_settings().match_ids
    if not match_ids:
        raise SystemExit(
            "Nenhum match_id informado. Passe IDs como argumento ou preencha STATSBOMB_MATCH_IDS no .env."
        )

    for match_id in match_ids:
        logger.info("Baixando partida %s...", match_id)
        paths = download_match(match_id)
        logger.info("Partida %s pronta em: %s", match_id, {k: str(v) for k, v in paths.items()})


if __name__ == "__main__":
    main()

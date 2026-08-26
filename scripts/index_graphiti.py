#!/usr/bin/env python
"""Indexa os PadraoTatico no Graphiti, para a busca híbrida da camada 3.

Por que este script existe
--------------------------
A indexação só acontecia dentro da rota ``POST /analyze/{match_id}`` da API.
Quem reproduz o projeto pelos scripts (``run_pipeline`` → ``build_graph`` →
``run_analysis``) nunca criava o índice — e a busca híbrida ficava dormente
sem avisar, porque ``retrieve_context`` recebe ``graphiti=None`` e segue só
com a recuperação estruturada.

Consequência para a pesquisa: todos os números medidos até a 4ª rodada são de
recuperação ESTRUTURADA PURA, não híbrida. Este script fecha essa lacuna.

Custo: ~3-4 chamadas de embedding por padrão, espaçadas por
GRAPHITI_PACE_SECONDS (default 2.0) para caber na cota free-tier do Gemini.
"""

import argparse
import asyncio
import logging

from football_graphrag.config import get_settings
from football_graphrag.graph import db
from football_graphrag.graph.communities import (
    build_pattern_communities,
    index_match_patterns,
    make_graphiti,
)
from football_graphrag.observability import logging_setup

logging_setup.setup(formato="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


async def main(partidas: list[int] | None) -> None:
    settings = get_settings()
    if not (settings.llm_api_key and settings.embedder_api_key):
        raise SystemExit("LLM_API_KEY e EMBEDDER_API_KEY são necessárias para indexar")
    driver = db.make_driver(settings)
    graphiti = make_graphiti(settings)
    try:
        await graphiti.build_indices_and_constraints()
        alvos = partidas or settings.match_ids
        logger.info("indexando %s", alvos)
        for match_id in alvos:
            n = await index_match_patterns(graphiti, driver, match_id)
            logger.info("partida %s: %d padrões indexados", match_id, n)
            await build_pattern_communities(graphiti, match_id)
            logger.info("partida %s: comunidades construídas", match_id)
    finally:
        driver.close()
        await graphiti.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--partidas", help="match_ids separados por vírgula (default: os do .env). "
                                      "Reindexar é seguro: o grupo é limpo antes.")
    args = p.parse_args()
    ids = [int(x) for x in args.partidas.split(",")] if args.partidas else None
    asyncio.run(main(ids))

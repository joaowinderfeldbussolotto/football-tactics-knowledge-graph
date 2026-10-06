#!/usr/bin/env python
"""Indexa os PadraoTatico no Graphiti, para a busca híbrida da camada 3.

Por que este script existe
--------------------------
A indexação acontecia dentro da rota ``POST /analyze/{match_id}`` da API — e
foi removida de lá (ADR-13): este script é o único caminho. Quem reproduzia o
projeto pelos scripts (``run_pipeline`` → ``build_graph`` →
``run_analysis``) nunca criava o índice — e a busca híbrida ficava dormente
sem avisar, porque ``retrieve_context`` recebe ``graphiti=None`` e segue só
com a recuperação estruturada.

Retomável e não destrutivo
--------------------------
Indexar custa dinheiro (cada padrão gasta chamadas de LLM e de embedding;
medido, ~US$ 0,06 por partida). Por isso o comportamento padrão é
**continuar de onde parou**: padrões já indexados são pulados, e a construção
de comunidades — a parte que mais falhou — só roda se a partida ainda não
tiver comunidades. Rodar de novo depois de uma queda paga só o que faltou.

- ``--do-zero``: apaga o índice das partidas pedidas e refaz TUDO (e repaga).
  Só faz sentido se os PadraoTatico mudaram.
- ``--so-comunidades``: pula os triplets e refaz apenas as comunidades. É o
  comando para quando o fim do script avisar que alguma ficou pendente.

Uma falha na construção de comunidades de uma partida não impede as demais:
o script segue, lista as pendentes no fim e sai com código 2. Para o Q&A a
ausência de comunidades não é fatal — a busca híbrida funciona sobre os
fatos; as comunidades só acrescentam resumos.

Custo: ~3-4 chamadas de embedding por padrão, espaçadas por
GRAPHITI_PACE_SECONDS (default 2.0) para caber na cota free-tier do Gemini.
"""

import argparse
import asyncio
import logging
import sys

from neo4j import Driver

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


def _contar(driver: Driver, match_id: int, label: str) -> int:
    with driver.session() as session:
        return session.run(
            f"MATCH (n:{label} {{group_id: $g}}) RETURN count(n) AS n", g=f"match-{match_id}"
        ).single()["n"]


def _estado(driver: Driver, alvos: list[int]) -> dict[int, tuple[int, int]]:
    """(nós Entity, comunidades) já gravados, por partida."""
    return {m: (_contar(driver, m, "Entity"), _contar(driver, m, "Community")) for m in alvos}


async def main(partidas: list[int] | None, do_zero: bool, so_comunidades: bool) -> int:
    settings = get_settings()
    if not (settings.llm_api_key and settings.embedder_api_key):
        raise SystemExit("LLM_API_KEY e EMBEDDER_API_KEY são necessárias para indexar")
    driver = db.make_driver(settings)
    graphiti = make_graphiti(settings)
    pendentes: list[int] = []
    try:
        await graphiti.build_indices_and_constraints()
        alvos = partidas or settings.match_ids

        antes = _estado(driver, alvos)
        for m, (nos, com) in antes.items():
            logger.info("estado atual da partida %s: %d nós Entity, %d comunidades", m, nos, com)
        if do_zero:
            logger.warning(
                "--do-zero: o índice atual destas partidas será APAGADO e refeito do zero "
                "(custa de novo)"
            )

        for match_id in alvos:
            if not so_comunidades:
                await index_match_patterns(graphiti, driver, match_id, limpar=do_zero)

            ja_tem_comunidades = _contar(driver, match_id, "Community") > 0
            if ja_tem_comunidades and not so_comunidades and not do_zero:
                logger.info("partida %s: comunidades já existem, pulando", match_id)
                continue
            try:
                await build_pattern_communities(graphiti, match_id, driver=driver)
                logger.info("partida %s: comunidades construídas", match_id)
            except Exception:
                # Não derruba as outras partidas: os triplets desta já estão
                # gravados e pagos, e as comunidades se refazem sozinhas.
                logger.exception("partida %s: comunidades NÃO construídas", match_id)
                pendentes.append(match_id)

        depois = _estado(driver, alvos)
        logger.info("---- resumo ----")
        for m in alvos:
            nos, com = depois[m]
            logger.info(
                "partida %s: %d nós Entity, %d comunidades%s",
                m, nos, com, "  <- PENDENTE" if m in pendentes else "",
            )
    finally:
        driver.close()
        await graphiti.close()

    if pendentes:
        logger.warning(
            "comunidades pendentes nas partidas %s. Os triplets estão salvos; para refazer só "
            "as comunidades (sem repagar nada mais): python scripts/index_graphiti.py "
            "--so-comunidades --partidas %s",
            pendentes, ",".join(map(str, pendentes)),
        )
        return 2
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--partidas", help="match_ids separados por vírgula (default: os do .env)")
    p.add_argument(
        "--do-zero", action="store_true",
        help="apaga o índice das partidas e refaz tudo (repaga). Padrão: retomar de onde parou",
    )
    p.add_argument(
        "--so-comunidades", action="store_true",
        help="pula os triplets e refaz só as comunidades",
    )
    args = p.parse_args()
    if args.do_zero and args.so_comunidades:
        p.error("--do-zero e --so-comunidades são mutuamente exclusivos")
    ids = [int(x) for x in args.partidas.split(",")] if args.partidas else None
    sys.exit(asyncio.run(main(ids, args.do_zero, args.so_comunidades)))

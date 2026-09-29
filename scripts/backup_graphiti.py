#!/usr/bin/env python
"""Backup do índice do Graphiti (a única parte cara de reconstruir).

Por que só o índice
-------------------
As camadas 0, 1, 1b e 2 se reconstroem de graça em minutos, a partir do
parquet que já está em ``data/processed/`` (``build_graph.py`` +
``run_analysis.py``). O índice do Graphiti, não: cada padrão indexado gasta
chamadas de LLM e de embedding — medido, ~US$ 0,06 por partida. É o que vale
a pena guardar.

O que entra no arquivo
----------------------
Nós ``Entity`` e ``Community`` dos grupos ``match-*``, as arestas
``RELATES_TO`` e ``HAS_MEMBER`` entre eles, e os vetores de embedding
(``name_embedding``, ``fact_embedding``). Mais um cabeçalho com data, provedor
e modelo de embedding, dimensão dos vetores e contagens.

Não usa ``apoc.export`` de propósito: ``apoc.export.file.enabled`` não está
ligado no ``docker-compose.yml``, e depender disso tornaria o backup
impossível de rodar num ambiente limpo do projeto.

Uso:
    python scripts/backup_graphiti.py --saida backup_graphiti.json.gz
"""

import argparse
import gzip
import json
import logging
from datetime import datetime, timezone

import neo4j.time

from football_graphrag.config import get_settings
from football_graphrag.graph import db
from football_graphrag.observability import logging_setup

logging_setup.setup(formato="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# Restaurar um datetime como string o transformaria em string no banco, e o
# Graphiti espera temporal. O backup marca essas chaves para a restauração
# reconvertê-las (ver restore_graphiti.py).
CHAVES_DATA = ("created_at", "expired_at", "invalid_at", "valid_at")

FILTRO = "n.group_id STARTS WITH 'match-'"


def _serializa(valor):
    if isinstance(valor, (neo4j.time.DateTime, neo4j.time.Date)):
        return valor.iso_format()
    return valor


def _props(d: dict) -> dict:
    return {k: _serializa(v) for k, v in d.items()}


def main(saida: str) -> None:
    settings = get_settings()
    driver = db.make_driver(settings)
    try:
        with driver.session() as session:
            nos = [
                {"labels": r["labels"], "props": _props(r["props"])}
                for r in session.run(
                    f"MATCH (n) WHERE {FILTRO} RETURN labels(n) AS labels, properties(n) AS props"
                )
            ]
            arestas = [
                {"de": r["de"], "para": r["para"], "tipo": r["tipo"], "props": _props(r["props"])}
                for r in session.run(
                    f"""MATCH (n)-[r]->(b) WHERE {FILTRO}
                        RETURN n.uuid AS de, b.uuid AS para, type(r) AS tipo,
                               properties(r) AS props"""
                )
            ]
    finally:
        driver.close()

    if not nos:
        raise SystemExit("nenhum nó do Graphiti encontrado: rode scripts/index_graphiti.py antes")

    dim = next(
        (len(n["props"]["name_embedding"]) for n in nos if n["props"].get("name_embedding")), None
    )
    grupos = sorted({n["props"]["group_id"] for n in nos})
    conteudo = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "embedder_provider": settings.embedder_provider,
        "embedder_model": settings.embedder_model,
        "dimensao_embedding": dim,
        "grupos": grupos,
        "chaves_data": list(CHAVES_DATA),
        "contagens": {"nos": len(nos), "arestas": len(arestas)},
        "nos": nos,
        "arestas": arestas,
    }
    with gzip.open(saida, "wt", encoding="utf-8") as fh:
        json.dump(conteudo, fh)
    logger.info(
        "backup: %d nós, %d arestas, grupos %s -> %s",
        len(nos), len(arestas), grupos, saida,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--saida", default="backup_graphiti.json.gz")
    main(p.parse_args().saida)

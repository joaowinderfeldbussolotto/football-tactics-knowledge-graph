#!/usr/bin/env python
"""Restaura o índice do Graphiti a partir de um backup, sem pagar reindexação.

Uso:
    python scripts/restore_graphiti.py backup_graphiti.json.gz

Recusa-se a restaurar se o modelo de embedding do arquivo não bater com o do
``.env``. Não é preciosismo: misturar vetores de modelos diferentes no mesmo
índice não levanta erro nenhum — só piora a busca, em silêncio. Num trabalho
que compara sistemas de recuperação, é o defeito mais caro possível. Use
``--forcar`` se souber o que está fazendo.

O que ele faz:
1. apaga os grupos ``match-*`` presentes no arquivo (restauração é idempotente);
2. recria os nós ``Entity``/``Community`` e as arestas ``RELATES_TO``/``HAS_MEMBER``;
3. reconverte para temporal as chaves de data marcadas no backup.
"""

import argparse
import gzip
import json
import logging

from football_graphrag.config import get_settings
from football_graphrag.graph import db
from football_graphrag.observability import logging_setup

logging_setup.setup(formato="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

LABELS = ("Entity", "Community")
TIPOS = ("RELATES_TO", "HAS_MEMBER")


def _set_datas(alvo: str, chaves: list[str], props: dict) -> str:
    """Gera as atribuições que devolvem o tipo temporal às chaves de data.

    ``SET n += $props`` sozinho gravaria a data como string. As chaves com
    data são poucas e conhecidas (vêm no cabeçalho do backup), então a cláusula
    é montada aqui em vez de exigir apoc.create.setProperty.
    """
    presentes = [k for k in chaves if props.get(k) is not None]
    return "".join(f", {alvo}.{k} = datetime(${alvo}_props.{k})" for k in presentes)


def main(arquivo: str, forcar: bool) -> None:
    settings = get_settings()
    with gzip.open(arquivo, "rt", encoding="utf-8") as fh:
        d = json.load(fh)

    if d.get("embedder_model") != settings.embedder_model and not forcar:
        raise SystemExit(
            f"backup foi gerado com embedder '{d.get('embedder_model')}' e o .env diz "
            f"'{settings.embedder_model}'. Vetores de modelos diferentes degradam a busca "
            "sem levantar erro. Use --forcar para ignorar."
        )

    chaves_data = d.get("chaves_data", [])
    driver = db.make_driver(settings)
    try:
        with driver.session() as session:
            for grupo in d["grupos"]:
                session.run("MATCH (n) WHERE n.group_id = $g DETACH DELETE n", g=grupo)
            logger.info("grupos limpos: %s", d["grupos"])

            for label in LABELS:
                itens = [n for n in d["nos"] if label in n["labels"]]
                for no in itens:
                    session.run(
                        f"MERGE (n:{label} {{uuid: $n_props.uuid}}) "
                        f"SET n += $n_props{_set_datas('n', chaves_data, no['props'])}",
                        n_props=no["props"],
                    )
                logger.info("%s: %d nós restaurados", label, len(itens))

            for tipo in TIPOS:
                itens = [a for a in d["arestas"] if a["tipo"] == tipo]
                for ar in itens:
                    session.run(
                        f"""MATCH (a {{uuid: $de}}), (b {{uuid: $para}})
                            MERGE (a)-[r:{tipo} {{uuid: $r_props.uuid}}]->(b)
                            SET r += $r_props{_set_datas('r', chaves_data, ar['props'])}""",
                        de=ar["de"], para=ar["para"], r_props=ar["props"],
                    )
                logger.info("%s: %d arestas restauradas", tipo, len(itens))

        with driver.session() as session:
            n = session.run(
                "MATCH (n) WHERE n.group_id STARTS WITH 'match-' RETURN count(n)"
            ).single()[0]
        esperado = d["contagens"]["nos"]
        logger.info("conferência: %d nós no banco, %d no backup", n, esperado)
        if n != esperado:
            raise SystemExit(f"restauração incompleta: {n} != {esperado}")
        logger.info("índice restaurado. A busca híbrida (--hibrida) já pode ser usada.")
    finally:
        driver.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("arquivo")
    p.add_argument("--forcar", action="store_true", help="ignora a checagem de modelo de embedding")
    args = p.parse_args()
    main(args.arquivo, args.forcar)

"""Configuração de log dos scripts, num lugar só.

O driver do Neo4j emite um aviso de "cartesian product" para toda escrita em
lote no formato ``MATCH (a {uid: ...}), (b {uid: ...})``. O aviso é falso
positivo aqui — os dois lados são busca por índice de uid, não varredura —
mas são dezenas de blocos de texto por execução, que enterram a saída útil.
Por isso o canal de notificações fica em WARNING.
"""

import logging

# Canais silenciados e até que nível. O do Neo4j vai para ERROR porque além
# do falso positivo de cartesian product ele repete, a cada projeção do GDS,
# um aviso de campo depreciado em ``gds.graph.drop`` — nada acionável do
# nosso lado e quatro blocos por partida.
RUIDOSOS = {
    "neo4j.notifications": logging.ERROR,
    "kloppy.infra.serializers.event.statsbomb.deserializer": logging.WARNING,
    "httpx": logging.WARNING,  # uma linha por request HTTP dos SDKs de LLM
}


def setup(level: int = logging.INFO, formato: str = "%(asctime)s %(name)s %(message)s") -> None:
    """Liga o log da aplicação e cala as bibliotecas ruidosas."""
    logging.basicConfig(level=level, format=formato)
    for nome, nivel in RUIDOSOS.items():
        logging.getLogger(nome).setLevel(nivel)

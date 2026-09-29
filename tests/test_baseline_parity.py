"""Paridade de fatos entre o baseline e o grafo.

A comparação central do trabalho (grafo versus RAG vetorial) só significa
alguma coisa se os dois lados tiverem os MESMOS FATOS e diferirem apenas na
REPRESENTAÇÃO. Estes testes são o que garante isso.

Sem eles a paridade seria uma promessa de docstring: as contagens do grafo
estão em Cypher (graph/statistics.py) e as do baseline em pandas
(evaluation/match_facts.py), e nada impediria as duas de se afastarem numa
mudança futura — reabrindo em silêncio a crítica de que o grafo venceu as
perguntas factuais por ter mais dado, não por ser grafo.
"""

from pathlib import Path

import pandas as pd

from football_graphrag.config import get_settings
from football_graphrag.evaluation import match_facts
from football_graphrag.evaluation.baseline_rag import build_match_summary
from football_graphrag.graph import db
from tests.conftest import requires_data, requires_neo4j

MATCH_ID = 3869685

# Campos que existem dos dois lados e têm que bater exatamente.
CAMPOS = [
    "toques", "passes_certos", "passes_tentados", "passes_progressivos",
    "cruzamentos_certos", "cruzamentos_tentados", "conducoes",
    "dribles_certos", "dribles_tentados", "desarmes_certos", "desarmes_tentados",
    "interceptacoes", "cortes", "faltas_cometidas", "cartoes_amarelos",
    "finalizacoes", "finalizacoes_no_gol", "gols", "gols_de_penalti",
    "defesas_do_goleiro", "erros_de_dominio", "assistencias",
]


def _parquet() -> pd.DataFrame:
    return pd.read_parquet(get_settings().processed_dir / f"{MATCH_ID}.parquet")


@requires_neo4j
@requires_data
def test_sumula_do_baseline_bate_com_a_do_grafo():
    """pandas (baseline) e Cypher (grafo) contam a mesma coisa, jogador a jogador."""
    pandas_side = match_facts.resumo_por_jogador(_parquet())

    driver = db.make_driver(get_settings())
    try:
        with driver.session() as session:
            grafo = {
                r["pid"]: r["props"]
                for r in session.run(
                    """MATCH (e:EstatisticaJogador {match_id: $m})
                       RETURN e.player_id AS pid, properties(e) AS props""",
                    m=MATCH_ID,
                ).data()
            }
    finally:
        driver.close()

    assert set(grafo) == set(pandas_side.index), "conjuntos de jogadores diferentes"

    divergencias = []
    for pid, props in grafo.items():
        esperado = pandas_side.loc[pid]
        for campo in CAMPOS:
            if int(props[campo]) != int(esperado[campo]):
                divergencias.append(
                    f"{props['nome']}.{campo}: grafo={props[campo]} baseline={esperado[campo]}"
                )
    assert not divergencias, "baseline e grafo divergem:\n" + "\n".join(divergencias)


@requires_data
def test_baseline_tem_os_fatos_que_as_perguntas_factuais_pedem():
    """O resumo do baseline cobre gols, cartões, desarmes, dribles e defesas.

    Antes desta mudança nenhum desses fatos existia no resumo, e o baseline
    perdia as factuais por ausência de dado — o que não é evidência sobre
    grafos.
    """
    texto = "\n".join(build_match_summary(MATCH_ID, Path(get_settings().data_dir))).lower()
    for termo in ("gols:", "cartões amarelos:", "desarmes certos", "dribles certos", "defesas"):
        assert termo in texto, f"o resumo do baseline não menciona '{termo}'"

    # os nomes e números das perguntas factuais têm que estar lá
    assert "mbappé" in texto and "messi" in texto
    assert "enzo fernandez" in texto
    assert "giroud" in texto, "o 7º amarelo (reclamação) tem que aparecer também no baseline"


@requires_data
def test_baseline_nao_vaza_resultado_da_camada_2():
    """O baseline não pode conter padrão tático — senão deixa de ser baseline.

    A vantagem que a tese mede é justamente o que só existe na topologia.
    Se betweenness ou comunidade aparecessem no resumo, a comparação
    perderia o sentido pelo outro lado.
    """
    texto = "\n".join(build_match_summary(MATCH_ID, Path(get_settings().data_dir))).lower()
    for proibido in ("betweenness", "louvain", "comunidade", "ponte", "gargalo", "pagerank"):
        assert proibido not in texto, f"resultado da camada 2 vazou para o baseline: '{proibido}'"

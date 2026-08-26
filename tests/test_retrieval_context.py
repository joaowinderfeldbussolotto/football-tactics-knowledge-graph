"""O contexto recuperado, nos dois braços da ablação.

No default (``incluir_sumula=True``, o comportamento da API) a súmula da
camada 1b entra no contexto e a pergunta factual é respondida sem consulta.
No braço de controle (``False``) ela não entra, e o agente só chega aos
números escrevendo Cypher — que é o mecanismo do ADR-8 sendo medido.

Os dois precisam continuar trazendo os padrões da camada 2: a súmula é sobre
o que é factual, e não pode roubar o lugar do que é estrutural.
"""

import asyncio

from football_graphrag.api import retrieval
from football_graphrag.config import get_settings
from football_graphrag.graph import db
from tests.conftest import requires_data, requires_neo4j

MATCH_ID = 3869685


def _contexto(pergunta: str, incluir_sumula: bool = True):
    driver = db.make_driver(get_settings())
    try:
        return asyncio.run(
            retrieval.retrieve_context(
                driver, MATCH_ID, pergunta, incluir_sumula=incluir_sumula
            )
        )
    finally:
        driver.close()


@requires_neo4j
@requires_data
def test_pergunta_com_jogador_traz_a_sumula_dele():
    _, stats, _, _ = _contexto("Quantos desarmes certos o Enzo Fernandez fez na final?")
    enzo = [s for s in stats if s.get("nome") == "Enzo Fernandez"]
    assert enzo, "a súmula do jogador citado não veio no contexto"
    assert enzo[0]["desarmes_certos"] == 5
    assert enzo[0]["desarmes_tentados"] == 9


@requires_neo4j
@requires_data
def test_pergunta_sem_entidade_traz_as_sumulas_dos_times():
    """Duas linhas cabem sempre e cobrem placar, posse e pressão."""
    _, stats, _, _ = _contexto("Como foi o jogo?")
    times = {s["nome"] for s in stats if "posse_pct" in s}
    assert times == {"Argentina", "France"}


@requires_neo4j
@requires_data
def test_sumula_nao_expoe_chaves_internas():
    _, stats, _, _ = _contexto("Como o Enzo Fernandez jogou?")
    for s in stats:
        for interna in ("uid", "player_id", "team_id"):
            assert interna not in s, f"chave interna vazou para o contexto: {interna}"


@requires_neo4j
@requires_data
def test_pergunta_estrutural_continua_trazendo_padroes():
    """A súmula não pode ter roubado o lugar dos padrões da camada 2."""
    pats, _, _, _ = _contexto("Qual jogador foi o gargalo estrutural da Argentina?")
    assert any(p["tipo"] == "pivo_estrutural" for p in pats)


@requires_neo4j
@requires_data
def test_braco_de_controle_nao_traz_sumula():
    """incluir_sumula=False: o agente tem que ir buscar o número no grafo."""
    pergunta = "Quantos desarmes certos o Enzo Fernandez fez na final?"
    _, stats, _, timings = _contexto(pergunta, incluir_sumula=False)
    assert stats == []
    assert "sumula" not in timings["estrategia"]


@requires_neo4j
@requires_data
def test_braco_de_controle_mantem_os_padroes():
    """Desligar a súmula não pode desligar a camada 2 junto: a ablação isola
    UMA variável, senão a diferença entre os braços não quer dizer nada."""
    pats, _, _, _ = _contexto(
        "Qual jogador foi o gargalo estrutural da Argentina?", incluir_sumula=False
    )
    assert any(p["tipo"] == "pivo_estrutural" for p in pats)

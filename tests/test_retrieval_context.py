"""O contexto recuperado precisa CONTER a resposta quando ela já existe.

Antes, a recuperação devolvia só PadraoTatico. Numa pergunta factual isso
significava um contexto sem a resposta: o agente tinha que gastar uma ida e
volta de ferramenta, e o juiz de recuperação da avaliação — que pontua o
CONTEXTO, não a resposta final — dava nota baixa mesmo quando a resposta
saía correta. Com a súmula no contexto, os dois problemas somem.
"""

import asyncio

from football_graphrag.api import retrieval
from football_graphrag.config import get_settings
from football_graphrag.graph import db
from tests.conftest import requires_data, requires_neo4j

MATCH_ID = 3869685


def _contexto(pergunta: str):
    driver = db.make_driver(get_settings())
    try:
        return asyncio.run(retrieval.retrieve_context(driver, MATCH_ID, pergunta))
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

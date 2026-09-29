"""Testes da súmula pré-agregada e do schema gerado (camada 1b).

A garantia mais importante testada aqui: o número pré-agregado e uma
contagem ad-hoc sobre as mesmas arestas NUNCA divergem. Duas respostas
certas e incompatíveis seriam pior que nenhuma.
"""

from football_graphrag.config import get_settings
from football_graphrag.graph import db, schema
from tests.conftest import requires_data, requires_neo4j

MATCH_ID = 3869685


def _driver():
    return db.make_driver(get_settings())


@requires_neo4j
@requires_data
def test_sumula_bate_com_contagem_ad_hoc():
    """EstatisticaJogador.desarmes_certos == contagem direta no log de ações."""
    driver = _driver()
    try:
        with driver.session() as session:
            sumula = {
                r["nome"]: r["n"]
                for r in session.run(
                    """MATCH (e:EstatisticaJogador {match_id: $m}) WHERE e.desarmes_certos > 0
                       RETURN e.nome AS nome, e.desarmes_certos AS n""",
                    m=MATCH_ID,
                ).data()
            }
            adhoc = {
                r["nome"]: r["n"]
                for r in session.run(
                    """MATCH (j:Jogador)-[r:REALIZOU {match_id: $m}]->(:Partida)
                       WHERE r.acao = 'desarme' AND r.sucesso
                       RETURN j.nome AS nome, count(r) AS n""",
                    m=MATCH_ID,
                ).data()
            }
        assert sumula == adhoc
    finally:
        driver.close()


@requires_neo4j
@requires_data
def test_desarmes_da_final_conferidos_a_mao():
    """A pergunta que o sistema errava: 'quem fez mais desarmes na final?'

    Resposta certa por desarmes CERTOS: Enzo 5, Camavinga 4, Tagliafico 4.
    Por TENTATIVAS o ranking é outro (Enzo 9, Tagliafico 7) — foi essa
    confusão que produziu a resposta errada antes de a distinção existir
    no dado.
    """
    driver = _driver()
    try:
        with driver.session() as session:
            linhas = session.run(
                """MATCH (e:EstatisticaJogador {match_id: $m})
                   RETURN e.nome AS nome, e.desarmes_certos AS certos,
                          e.desarmes_tentados AS tentados
                   ORDER BY certos DESC, tentados DESC LIMIT 3""",
                m=MATCH_ID,
            ).data()
        assert linhas[0]["nome"] == "Enzo Fernandez"
        assert linhas[0]["certos"] == 5
        assert linhas[0]["tentados"] == 9
        assert {l["certos"] for l in linhas[1:]} == {4}
    finally:
        driver.close()


@requires_neo4j
@requires_data
def test_estatistica_time_reproduz_a_sumula_oficial():
    """Posse e gols da final batem com o placar real (Argentina 3x3 França)."""
    driver = _driver()
    try:
        with driver.session() as session:
            times = {
                r["nome"]: r
                for r in session.run(
                    """MATCH (e:EstatisticaTime {match_id: $m})
                       RETURN e.nome AS nome, e.gols AS gols, e.posse_pct AS posse""",
                    m=MATCH_ID,
                ).data()
            }
        assert times["Argentina"]["gols"] == 3
        assert times["France"]["gols"] == 3
        # posse soma 100% e a Argentina teve mais (54% na súmula da FIFA)
        assert round(times["Argentina"]["posse"] + times["France"]["posse"]) == 100
        assert times["Argentina"]["posse"] > times["France"]["posse"]
    finally:
        driver.close()


@requires_neo4j
@requires_data
def test_schema_gerado_nao_vaza_jargao_spadl():
    """O schema exposto ao agente fala futebol, não SPADL.

    Esta é a trava contra a regressão que motivou a refatoração: se
    'take_on' ou 'tackle' reaparecerem no prompt, a ambiguidade voltou e o
    agente pode contar tentativa como acerto de novo.
    """
    driver = _driver()
    try:
        texto = schema.describe_graph(driver)
    finally:
        driver.close()

    for jargao in ("take_on", "tackle", "tipo_spadl", "result_name", "bad_touch", "keeper_save"):
        assert jargao not in texto, f"jargão SPADL vazou para o schema: {jargao}"

    # e traz o vocabulário de futebol, enumerado do banco
    for termo in ("desarme", "drible", "conducao", "EstatisticaJogador"):
        assert termo in texto


@requires_neo4j
@requires_data
def test_schema_nao_expoe_chaves_internas():
    driver = _driver()
    try:
        texto = schema.describe_graph(driver)
    finally:
        driver.close()
    for oculta in ("uid", "action_id", "pressure_idx"):
        assert f" {oculta}," not in texto and not texto.endswith(f" {oculta}")

"""Testes do vocabulário de futebol (passo 0.4h).

O que estes testes protegem é a decisão central da refatoração: a semântica
mora no DADO, não no prompt. Se algum deles quebrar, alguma ambiguidade
voltou para o grafo.
"""

import pandas as pd
import pytest

from football_graphrag.config import get_settings
from football_graphrag.ingestion import football_semantics as fs
from tests.conftest import requires_data

MATCH_ID = 3869685


def test_todo_tipo_spadl_tem_traducao():
    """Nenhum tipo SPADL pode ficar sem nome em português.

    Um tipo sem tradução viraria buraco silencioso no grafo — a ação
    existiria mas ninguém saberia perguntar por ela.
    """
    faltando = set(fs.GRUPO_POR_ACAO) - set(fs.ACAO_POR_TIPO_SPADL.values())
    assert not faltando, f"grupo definido para ação inexistente: {faltando}"
    sem_grupo = set(fs.ACAO_POR_TIPO_SPADL.values()) - set(fs.GRUPO_POR_ACAO)
    assert not sem_grupo, f"ação sem grupo: {sem_grupo}"


def test_as_duas_armadilhas_de_nomenclatura():
    """dribble é CONDUÇÃO e take_on é DRIBLE — trocar os dois erra por 20x."""
    assert fs.ACAO_POR_TIPO_SPADL["dribble"] == "conducao"
    assert fs.ACAO_POR_TIPO_SPADL["take_on"] == "drible"
    assert fs.ACAO_POR_TIPO_SPADL["tackle"] == "desarme"


def test_vocabulario_sem_acentos():
    """Valores sem acento: ninguém erra a consulta por causa de cedilha."""
    for acao in fs.ACAO_POR_TIPO_SPADL.values():
        assert acao.isascii(), f"'{acao}' tem caractere não-ASCII"
        assert acao == acao.lower()


def test_minuto_de_jogo_bate_com_a_sumula_da_fifa():
    """Os 6 gols da final da Copa 2022, nos minutos que o mundo viu.

    Entrada: (período, segundos no período) -> minuto de transmissão.
    """
    casos = [
        (1, 1344.11, 23),   # Messi, pênalti
        (1, 2122.65, 36),   # Di María
        (2, 2064.97, 80),   # Mbappé, pênalti
        (2, 2159.03, 81),   # Mbappé
        (4, 178.08, 108),   # Messi, 2ª prorrogação
        (4, 725.19, 118),   # Mbappé, pênalti
    ]
    periodos = pd.Series([c[0] for c in casos])
    segundos = pd.Series([c[1] for c in casos])
    esperado = [c[2] for c in casos]
    assert list(fs.minuto_de_jogo(periodos, segundos)) == esperado


def test_segundo_de_jogo_e_escala_continua():
    """Escala contínua entre períodos — é o que faz a janela temporal fechar.

    O minuto 34 do 2º tempo vem DEPOIS do minuto 50 do 1º, mesmo o número
    sendo menor. Só ``segundo`` preserva essa ordem.
    """
    fim_do_primeiro = fs.segundo_de_jogo(pd.Series([1]), pd.Series([50 * 60.0]))[0]
    meio_do_segundo = fs.segundo_de_jogo(pd.Series([2]), pd.Series([34 * 60.0]))[0]
    assert meio_do_segundo > fim_do_primeiro


@requires_data
def test_semantica_aplicada_ao_parquet_real():
    df = pd.read_parquet(get_settings().processed_dir / f"{MATCH_ID}.parquet")

    # sucesso é booleano explícito, não uma string a interpretar
    assert df["sucesso"].dtype == bool

    # desarme certo != desarme tentado: a distinção que o LLM errava
    tentados = int((df["acao"] == "desarme").sum())
    certos = int(((df["acao"] == "desarme") & df["sucesso"]).sum())
    assert certos < tentados, "se forem iguais, a distinção sumiu do dado"

    # condução e drible são coisas diferentes e em ordens de grandeza distintas
    assert (df["acao"] == "conducao").sum() > 10 * (df["acao"] == "drible").sum()

    # todo gol é uma finalização bem-sucedida, e são 6 na final
    assert int(df["gol"].sum()) == 6
    assert bool((df.loc[df["gol"], "grupo_acao"] == "finalizacao").all())


@requires_data
def test_cartao_por_reclamacao_recuperado_do_bruto():
    """O SPADL perde cartões que não vêm de falta; nós os recuperamos.

    Na final foram 7 amarelos em campo: 6 por falta + o do Giroud (95') por
    reclamação. Sem o resgate, o grafo responderia 6 — e estaria errado.
    """
    df = pd.read_parquet(get_settings().processed_dir / f"{MATCH_ID}.parquet")
    assert int(df["cartao_amarelo"].sum()) == 7
    reclamacao = df[df["acao"] == "cartao_por_reclamacao"]
    assert len(reclamacao) == 1
    assert "Giroud" in reclamacao.iloc[0]["player_name"]


@requires_data
def test_desfecho_de_finalizacao_existe():
    """SPADL só guarda gol/não-gol; recuperamos defendida/para_fora/bloqueada."""
    df = pd.read_parquet(get_settings().processed_dir / f"{MATCH_ID}.parquet")
    finalizacoes = df[df["grupo_acao"] == "finalizacao"]
    assert finalizacoes["desfecho"].notna().any()
    # toda finalização com desfecho 'gol' tem que ser um gol, e vice-versa
    assert bool(finalizacoes.loc[finalizacoes["desfecho"] == "gol", "gol"].all())
    assert bool((finalizacoes.loc[finalizacoes["gol"], "desfecho"] == "gol").all())


def test_traducao_rejeita_tipo_desconhecido():
    """Tipo SPADL novo tem que estourar, não passar batido."""
    df = pd.DataFrame(
        {
            "type_name": ["tipo_que_nao_existe"],
            "result_name": ["success"],
            "period_id": [1],
            "time_seconds": [10.0],
            "bodypart_name": ["foot"],
            "zone_start": [0],
        }
    )
    with pytest.raises(ValueError, match="sem tradução"):
        fs.add_football_semantics(df)

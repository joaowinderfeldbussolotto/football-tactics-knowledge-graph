"""Resiliência da indexação do Graphiti: o que não pode custar dinheiro de novo.

A indexação caiu três vezes em dias diferentes por causas diferentes (resposta
sem ``choices``, resposta vazia, JSON cortado), e cada queda jogava fora o que
já tinha sido pago. Estes testes fixam o contrato que impede isso — sem rede,
sem Neo4j e sem LLM, com fakes no lugar do Graphiti e do driver.

Um deles existe por um defeito específico: o ramo que repete a chamada quando
a resposta vem sem ``choices`` usava ``logger`` sem que o módulo o definisse,
e só teria estourado (NameError) no dia em que o ramo rodasse de verdade.
"""

import asyncio
import json

import pytest
from graphiti_core.llm_client import LLMConfig
from graphiti_core.llm_client.errors import EmptyResponseError
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from openai import AsyncOpenAI

from football_graphrag.graph import communities
from football_graphrag.llm import provider


# ---------------------------------------------------------------------------
# Cliente de LLM resiliente
# ---------------------------------------------------------------------------

@pytest.fixture
def sem_espera(monkeypatch):
    """Troca asyncio.sleep por um registrador: os testes não esperam de verdade."""
    esperas: list[float] = []

    async def fake_sleep(segundos):
        esperas.append(segundos)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return esperas


def _cliente():
    classe = provider._classe_cliente_resiliente()
    return classe(
        config=LLMConfig(api_key="x", model="m"),
        client=AsyncOpenAI(api_key="x", base_url="http://127.0.0.1:1"),
    )


def _base_que_falha(monkeypatch, erros: list[Exception], resposta=None):
    """Faz o método da classe-base levantar ``erros`` em sequência e depois
    devolver ``resposta``. Devolve a lista onde cada chamada é registrada."""
    chamadas: list[int] = []
    fila = list(erros)

    async def fake(self, *args, **kwargs):
        chamadas.append(1)
        if fila:
            raise fila.pop(0)
        return resposta if resposta is not None else {"ok": True}

    monkeypatch.setattr(OpenAIGenericClient, "_generate_response", fake)
    return chamadas


def test_repete_resposta_vazia_e_recupera(monkeypatch, sem_espera):
    chamadas = _base_que_falha(
        monkeypatch, [EmptyResponseError("LLM returned an empty response")] * 2
    )
    resultado = asyncio.run(_cliente()._generate_response([]))
    assert resultado == {"ok": True}
    assert len(chamadas) == 3
    assert sem_espera == [3.0, 6.0]  # backoff crescente entre tentativas


def test_repete_json_cortado_no_meio(monkeypatch, sem_espera):
    """O ``Unterminated string starting at ... char 13`` do log real."""
    cortado = json.JSONDecodeError("Unterminated string starting at", '{"summary": "x', 13)
    chamadas = _base_que_falha(monkeypatch, [cortado])
    assert asyncio.run(_cliente()._generate_response([])) == {"ok": True}
    assert len(chamadas) == 2


def test_repete_resposta_sem_choices(monkeypatch, sem_espera):
    """Este é o ramo que usava ``logger`` sem o módulo definir um: antes do
    conserto virava NameError na primeira vez que rodasse."""
    sem_choices = TypeError("'NoneType' object is not subscriptable")
    chamadas = _base_que_falha(monkeypatch, [sem_choices])
    assert asyncio.run(_cliente()._generate_response([])) == {"ok": True}
    assert len(chamadas) == 2


def test_nao_engole_erro_que_nao_e_do_provedor(monkeypatch, sem_espera):
    """Um TypeError qualquer (bug nosso) tem que subir na hora, sem retry."""
    chamadas = _base_que_falha(monkeypatch, [TypeError("argumento posicional inesperado")])
    with pytest.raises(TypeError, match="posicional"):
        asyncio.run(_cliente()._generate_response([]))
    assert len(chamadas) == 1
    assert sem_espera == []


def test_esgotadas_as_tentativas_sobe_o_ultimo_erro(monkeypatch, sem_espera):
    chamadas = _base_que_falha(monkeypatch, [EmptyResponseError("vazia")] * 10)
    with pytest.raises(EmptyResponseError):
        asyncio.run(_cliente()._generate_response([]))
    assert len(chamadas) == 3  # TENTATIVAS, sem multiplicar além do combinado


# ---------------------------------------------------------------------------
# Indexação retomável
# ---------------------------------------------------------------------------

class _Resultado:
    def __init__(self, valores=None):
        self._valores = valores or []

    def value(self):
        return self._valores

    def consume(self):
        return None


class _SessaoFalsa:
    def __init__(self, banco):
        self.banco = banco

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query, **params):
        if "DETACH DELETE" in query:
            self.banco.apagados.append(query)
            self.banco.nomes.clear()
            return _Resultado()
        if "RETURN n.name" in query:
            return _Resultado(sorted(self.banco.nomes))
        if "PadraoTatico" in query:
            return _Resultado(self.banco.padroes)
        raise AssertionError(f"consulta inesperada no fake: {query}")


class _BancoFalso:
    """Driver mínimo: padrões do grafo, nomes já indexados e DELETEs emitidos."""

    def __init__(self, padroes, ja_indexados=()):
        self.padroes = padroes
        self.nomes = set(ja_indexados)
        self.apagados: list[str] = []

    def session(self):
        return _SessaoFalsa(self)


class _GraphitiFalso:
    def __init__(self, falha_em=()):
        self.falha_em = set(falha_em)
        self.indexados: list[str] = []

    async def add_triplet(self, team, edge, pattern):
        if pattern.name in self.falha_em:
            raise RuntimeError("provedor falhou")
        self.indexados.append(pattern.name)


def _padroes(n=3):
    return [
        {
            "uid": f"{i:08d}-aaaa-bbbb-cccc-dddddddddddd",
            "tipo": "pivo_estrutural",
            "time": "Argentina",
            "descricao_curta": f"padrão {i}",
        }
        for i in range(n)
    ]


def _nome(p):
    return f"{p['tipo']}:{p['uid'][:8]}"


def test_retomada_paga_so_o_que_faltou():
    padroes = _padroes(3)
    banco = _BancoFalso(padroes, ja_indexados=[_nome(padroes[0]), _nome(padroes[1])])
    graphiti = _GraphitiFalso()

    n = asyncio.run(
        communities.index_match_patterns(graphiti, banco, 1, pace_seconds=0)
    )

    assert n == 1
    assert graphiti.indexados == [_nome(padroes[2])]
    assert banco.apagados == []  # o ponto central: retomar NÃO apaga o que foi pago


def test_limpar_apaga_e_refaz_tudo():
    padroes = _padroes(3)
    banco = _BancoFalso(padroes, ja_indexados=[_nome(p) for p in padroes])
    graphiti = _GraphitiFalso()

    n = asyncio.run(
        communities.index_match_patterns(graphiti, banco, 1, pace_seconds=0, limpar=True)
    )

    assert n == 3
    assert len(banco.apagados) == 2  # Entity e Community
    assert len(graphiti.indexados) == 3


def test_triplet_que_falha_nao_derruba_os_outros_e_fica_para_a_retomada():
    padroes = _padroes(3)
    banco = _BancoFalso(padroes)
    graphiti = _GraphitiFalso(falha_em=[_nome(padroes[1])])

    n = asyncio.run(
        communities.index_match_patterns(graphiti, banco, 1, pace_seconds=0)
    )

    assert n == 2
    assert _nome(padroes[1]) not in graphiti.indexados  # não conta como feito
    # na retomada ele volta a ser candidato: ainda não está entre os indexados
    banco.nomes.update(graphiti.indexados)
    graphiti2 = _GraphitiFalso()
    asyncio.run(communities.index_match_patterns(graphiti2, banco, 1, pace_seconds=0))
    assert graphiti2.indexados == [_nome(padroes[1])]


# ---------------------------------------------------------------------------
# Comunidades: tudo-ou-nada do Graphiti, repetido pela etapa inteira
# ---------------------------------------------------------------------------

class _GraphitiComunidades:
    def __init__(self, falhas):
        self.falhas = list(falhas)
        self.chamadas = 0

    async def build_communities(self, group_ids):
        self.chamadas += 1
        if self.falhas:
            raise self.falhas.pop(0)
        return ("nos", "arestas")


class _BancoComunidades:
    def __init__(self):
        self.apagados = 0

    def session(self):
        banco = self

        class S:
            def __enter__(s):
                return s

            def __exit__(s, *exc):
                return False

            def run(s, query, **params):
                banco.apagados += 1
                return _Resultado()

        return S()


def test_comunidades_repete_a_etapa_inteira_e_limpa_antes_de_cada_tentativa(sem_espera):
    graphiti = _GraphitiComunidades([EmptyResponseError("vazia")] * 2)
    banco = _BancoComunidades()

    resultado = asyncio.run(
        communities.build_pattern_communities(graphiti, 1, driver=banco, tentativas=3, espera_s=10)
    )

    assert resultado == ("nos", "arestas")
    assert graphiti.chamadas == 3
    assert banco.apagados == 3  # limpa antes de CADA tentativa: não duplica
    assert sem_espera == [10, 20]  # espera crescente


def test_comunidades_esgotadas_sobem_a_ultima_excecao(sem_espera):
    graphiti = _GraphitiComunidades([EmptyResponseError("vazia")] * 5)
    with pytest.raises(EmptyResponseError):
        asyncio.run(
            communities.build_pattern_communities(graphiti, 1, tentativas=2, espera_s=1)
        )
    assert graphiti.chamadas == 2


# ---------------------------------------------------------------------------
# scripts/index_graphiti.py — o cenário exato que custou dinheiro
# ---------------------------------------------------------------------------

def _carregar_script_de_indexacao():
    """O script não é um pacote: carrega pelo caminho, como o Python faria."""
    import importlib.util
    from pathlib import Path

    caminho = Path(__file__).resolve().parent.parent / "scripts" / "index_graphiti.py"
    spec = importlib.util.spec_from_file_location("index_graphiti_script", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _ContagemFalsa:
    """Driver que só responde ao COUNT do script: nós e comunidades por grupo."""

    def __init__(self, entidades=None, comunidades=None):
        self.entidades = entidades or {}
        self.comunidades = comunidades or {}

    def session(self):
        banco = self

        class S:
            def __enter__(s):
                return s

            def __exit__(s, *exc):
                return False

            def run(s, query, **params):
                grupo = params["g"]
                tabela = banco.comunidades if ":Community" in query else banco.entidades

                class R:
                    def single(r):
                        return {"n": tabela.get(grupo, 0)}

                return R()

        return S()

    def close(self):
        pass


class _GraphitiDoScript:
    async def build_indices_and_constraints(self):
        pass

    async def close(self):
        pass


@pytest.fixture
def script(monkeypatch):
    """O script com tudo que custa dinheiro ou precisa de rede trocado por fake."""
    modulo = _carregar_script_de_indexacao()
    chamadas = {"indice": [], "comunidades": []}

    class Settings:
        llm_api_key = "k"
        embedder_api_key = "k"
        match_ids = [1, 2, 3]

    async def indice_falso(graphiti, driver, match_id, limpar=False, **kw):
        chamadas["indice"].append((match_id, limpar))
        return 1

    monkeypatch.setattr(modulo, "get_settings", lambda: Settings())
    monkeypatch.setattr(modulo, "make_graphiti", lambda s: _GraphitiDoScript())
    monkeypatch.setattr(modulo, "index_match_patterns", indice_falso)
    modulo._chamadas = chamadas
    return modulo


def _comunidades_que_falham(modulo, monkeypatch, partidas_com_falha):
    async def falso(graphiti, match_id, driver=None, **kw):
        modulo._chamadas["comunidades"].append(match_id)
        if match_id in partidas_com_falha:
            raise EmptyResponseError("LLM returned an empty response")

    monkeypatch.setattr(modulo, "build_pattern_communities", falso)


def test_falha_de_comunidades_numa_partida_nao_aborta_as_outras(script, monkeypatch):
    """O crash real: EmptyResponseError em build_communities matava o processo e
    deixava as partidas seguintes sem indexar, com o dinheiro das anteriores
    já gasto. Agora a partida 2 fica pendente e a 3 é processada."""
    _comunidades_que_falham(script, monkeypatch, {2})
    monkeypatch.setattr(script.db, "make_driver", lambda s: _ContagemFalsa())

    codigo = asyncio.run(script.main(None, False, False))

    assert codigo == 2  # sinaliza pendência, sem esconder
    assert [m for m, _ in script._chamadas["indice"]] == [1, 2, 3]
    assert script._chamadas["comunidades"] == [1, 2, 3]  # a 3 rodou depois da falha da 2


def test_tudo_certo_sai_com_codigo_zero(script, monkeypatch):
    _comunidades_que_falham(script, monkeypatch, set())
    monkeypatch.setattr(script.db, "make_driver", lambda s: _ContagemFalsa())
    assert asyncio.run(script.main(None, False, False)) == 0


def test_retomada_pula_comunidades_que_ja_existem(script, monkeypatch):
    _comunidades_que_falham(script, monkeypatch, set())
    monkeypatch.setattr(
        script.db, "make_driver", lambda s: _ContagemFalsa(comunidades={"match-1": 4, "match-3": 2})
    )

    asyncio.run(script.main(None, False, False))

    assert script._chamadas["comunidades"] == [2]  # só a que faltava


def test_so_comunidades_nao_repaga_os_triplets(script, monkeypatch):
    _comunidades_que_falham(script, monkeypatch, set())
    monkeypatch.setattr(
        script.db, "make_driver", lambda s: _ContagemFalsa(comunidades={"match-1": 4})
    )

    asyncio.run(script.main([1, 2], False, True))

    assert script._chamadas["indice"] == []  # nenhum triplet foi tocado
    assert script._chamadas["comunidades"] == [1, 2]  # refaz mesmo as que existiam


def test_do_zero_pede_limpeza_explicitamente(script, monkeypatch):
    _comunidades_que_falham(script, monkeypatch, set())
    monkeypatch.setattr(script.db, "make_driver", lambda s: _ContagemFalsa())

    asyncio.run(script.main([1], True, False))

    assert script._chamadas["indice"] == [(1, True)]


# ---------------------------------------------------------------------------
# POST /analyze — só a camada 2; nunca toca o Graphiti
# ---------------------------------------------------------------------------

def _cliente_da_api(monkeypatch, graphiti):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from football_graphrag.api import routes

    monkeypatch.setattr(routes.analysis, "run_all", lambda *a, **k: {"pivo_estrutural": 2})
    app = FastAPI()
    app.include_router(routes.router)
    app.state.driver = object()
    app.state.graphiti = graphiti
    return TestClient(app)


def test_analyze_nao_toca_no_graphiti_mesmo_quando_ele_esta_habilitado(monkeypatch):
    """A rota já indexou aqui: apagava o índice da partida a cada chamada
    (limpar=True) e repagava tudo, e uma falha do provedor virava 500 com a
    análise já gravada. Foi decidido tirar o Graphiti da rota (ADR-13). Este
    teste impede a volta: qualquer chamada ao Graphiti durante /analyze falha."""
    from football_graphrag.graph import communities

    async def proibido(*a, **k):
        raise AssertionError("/analyze não pode tocar no Graphiti")

    monkeypatch.setattr(communities, "index_match_patterns", proibido)
    monkeypatch.setattr(communities, "build_pattern_communities", proibido)

    class GraphitiQueExplode:
        def __getattr__(self, nome):
            raise AssertionError(f"/analyze acessou graphiti.{nome}")

    resposta = _cliente_da_api(monkeypatch, GraphitiQueExplode()).post("/analyze/3869685")

    assert resposta.status_code == 200
    assert resposta.json() == {"match_id": 3869685, "padroes_por_tipo": {"pivo_estrutural": 2}}


def test_analyze_responde_igual_com_e_sem_graphiti(monkeypatch):
    com = _cliente_da_api(monkeypatch, object()).post("/analyze/1").json()
    sem = _cliente_da_api(monkeypatch, None).post("/analyze/1").json()
    assert com == sem

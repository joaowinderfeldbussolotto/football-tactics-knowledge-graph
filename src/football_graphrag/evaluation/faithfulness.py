"""Checagem de fidelidade DETERMINÍSTICA, sem LLM.

Para cada MetricaCitada na saída do agente, consulta o grafo e confirma que
aquele PadraoTatico existe com aquele valor. Score = proporção de citações
que batem. Meta: 100%. Qualquer valor abaixo é bug, não ruído.

Para o modo autônomo (ADR-8): cada ConsultaCypher registrada na resposta é
RE-EXECUTADA em transação read-only — a auditabilidade do text-to-Cypher é
"a consulta citada roda e retorna dados", verificável por qualquer revisor.

O QUE ESTA MÉTRICA NÃO MEDE
---------------------------
Fidelidade 1.0 **não** quer dizer que a resposta está correta. Ela diz duas
coisas mais estreitas:

- toda métrica citada aponta para um PadraoTatico que existe, com o mesmo
  valor, nome e algoritmo de origem;
- toda consulta registrada roda e devolve linhas.

Uma consulta pode rodar, devolver linhas, ter o número transcrito
corretamente para o texto — e ainda assim responder a pergunta errada. Foi
o que aconteceu em ``q23_desarmes_final`` na 3ª rodada de avaliação: o
agente contou tentativas de desarme em vez de desarmes certos, respondeu
"Enzo 9" (a resposta é 5), e a fidelidade deu 1.0. O número veio mesmo da
consulta; a consulta é que perguntava outra coisa.

Erro semântico de consulta é invisível para qualquer verificação que não
saiba a resposta certa de antemão. Por isso a defesa contra ele não está
aqui: está em não deixar a consulta ser ambígua (campo ``desarmes_certos``
separado de ``desarmes_tentados``, em graph/statistics.py) e em
``scripts/check_golden_queries.py``, que compara com resposta conferida
à mão.
"""

import math
from dataclasses import dataclass, field

from neo4j import Driver

from football_graphrag.api.schemas import ConsultaCypher, MetricaCitada
from football_graphrag.graph import db

TOLERANCE = 1e-4  # tolerância de arredondamento de float na serialização


@dataclass
class FaithfulnessResult:
    total: int
    matched: int
    mismatches: list[dict] = field(default_factory=list)

    @property
    def score(self) -> float:
        return 1.0 if self.total == 0 else self.matched / self.total


def check_queries(driver: Driver, consultas: list[ConsultaCypher]) -> FaithfulnessResult:
    """Re-executa cada consulta citada (read-only). Passa se a consulta roda
    e retorna ao menos uma linha — i.e., a resposta é auditável contra o grafo."""
    result = FaithfulnessResult(total=len(consultas), matched=0)
    for c in consultas:
        try:
            rows = db.run_readonly(driver, c.cypher)
        except Exception as exc:
            result.mismatches.append({"cypher": c.cypher, "erro": f"nao_reexecuta: {exc}"})
            continue
        if rows:
            result.matched += 1
        else:
            result.mismatches.append({"cypher": c.cypher, "erro": "reexecucao_vazia"})
    return result


def check_citations(driver: Driver, citations: list[MetricaCitada]) -> FaithfulnessResult:
    result = FaithfulnessResult(total=len(citations), matched=0)
    with driver.session() as session:
        for c in citations:
            record = session.run(
                """MATCH (p:PadraoTatico {uid: $uid})
                   RETURN p.valor_metrica AS valor, p.nome_metrica AS nome,
                          p.algoritmo_origem AS algoritmo""",
                uid=c.padrao_tatico_id,
            ).single()
            if record is None:
                result.mismatches.append({"uid": c.padrao_tatico_id, "erro": "padrao_inexistente", "citado": c.model_dump()})
                continue
            ok_valor = math.isclose(record["valor"], c.valor, abs_tol=TOLERANCE)
            ok_nome = record["nome"] == c.nome_metrica
            ok_algo = record["algoritmo"] == c.algoritmo_origem
            if ok_valor and ok_nome and ok_algo:
                result.matched += 1
            else:
                result.mismatches.append(
                    {
                        "uid": c.padrao_tatico_id,
                        "erro": "valores_divergentes",
                        "citado": c.model_dump(),
                        "no_grafo": dict(record),
                    }
                )
    return result

"""Checagem de fidelidade DETERMINÍSTICA, sem LLM.

Para cada MetricaCitada na saída do agente, consulta o grafo e confirma que
aquele PadraoTatico existe com aquele valor. Score = proporção de citações
que batem. Meta: 100%. Qualquer valor abaixo é bug, não ruído.
"""

import math
from dataclasses import dataclass, field

from neo4j import Driver

from football_graphrag.api.schemas import MetricaCitada

TOLERANCE = 1e-4  # tolerância de arredondamento de float na serialização


@dataclass
class FaithfulnessResult:
    total: int
    matched: int
    mismatches: list[dict] = field(default_factory=list)

    @property
    def score(self) -> float:
        return 1.0 if self.total == 0 else self.matched / self.total


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

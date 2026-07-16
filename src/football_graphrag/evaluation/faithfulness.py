"""Checagem determinística de fidelidade (seção 8 do plano, sem LLM).

Para cada `MetricCitation` de um `TacticalReport`, confirma que existe de
fato uma aresta `edge_type` tocando o nó `node_id` no grafo, com o atributo
`attribute` igual a `value`. É uma consulta + comparação, não uma chamada de
LLM — mais barato, determinístico e mais confiável do que pedir a outro LLM
para "julgar" se um número está certo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from graphiti_core import Graphiti
from graphiti_core.edges import EntityEdge

from football_graphrag.api.schemas import MetricCitation, TacticalReport


@dataclass
class CitationCheck:
    citation: MetricCitation
    faithful: bool
    reason: str


@dataclass
class FaithfulnessResult:
    checks: list[CitationCheck]

    @property
    def n_checked(self) -> int:
        return len(self.checks)

    @property
    def n_faithful(self) -> int:
        return sum(1 for c in self.checks if c.faithful)

    @property
    def score(self) -> float:
        return self.n_faithful / self.n_checked if self.n_checked else 0.0


def _values_match(actual: object, expected: float, rel_tol: float = 1e-3, abs_tol: float = 1e-4) -> bool:
    if not isinstance(actual, (int, float)):
        return False
    return math.isclose(float(actual), expected, rel_tol=rel_tol, abs_tol=abs_tol)


async def _check_citation(graphiti: Graphiti, citation: MetricCitation) -> CitationCheck:
    try:
        edges: list[EntityEdge] = await EntityEdge.get_by_node_uuid(graphiti.driver, citation.node_id)
    except Exception as exc:  # nó inexistente, uuid inválido, etc.
        return CitationCheck(citation, False, f"Falha ao consultar node_id={citation.node_id}: {exc}")

    matching_type = [e for e in edges if e.name == citation.edge_type]
    if not matching_type:
        return CitationCheck(
            citation, False, f"Nenhuma aresta '{citation.edge_type}' encontrada tocando node_id={citation.node_id}."
        )

    for edge in matching_type:
        actual = (edge.attributes or {}).get(citation.attribute)
        if _values_match(actual, citation.value):
            return CitationCheck(citation, True, f"OK: {citation.attribute}={actual} confere com o grafo.")

    return CitationCheck(
        citation,
        False,
        f"Aresta '{citation.edge_type}' existe, mas nenhuma tem {citation.attribute}={citation.value}.",
    )


async def check_faithfulness(graphiti: Graphiti, report: TacticalReport) -> FaithfulnessResult:
    checks = [await _check_citation(graphiti, citation) for citation in report.cited_metrics]
    return FaithfulnessResult(checks=checks)

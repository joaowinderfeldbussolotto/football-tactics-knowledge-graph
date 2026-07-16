"""Construção do agente PydanticAI usado por `/report` e `/live/.../insights`.

Ambos os endpoints seguem o mesmo padrão: buscar fatos no grafo (sem LLM,
seção 6.4/`graph.client.get_match_facts`) e pedir ao agente para redigir uma
`TacticalReport` citando só esses fatos — não é um agente com ferramentas,
é geração estruturada grounded em contexto já recuperado.
"""

from __future__ import annotations

from graphiti_core.edges import EntityEdge
from pydantic_ai import Agent

from football_graphrag.api.schemas import TacticalReport
from football_graphrag.config import Settings
from football_graphrag.llm.provider import build_pydantic_ai_model

_SYSTEM_PROMPT = (
    "Você é um analista tático de futebol. Escreva a narrativa em português, "
    "citando apenas os fatos fornecidos no contexto. Nunca invente um node_id, "
    "edge_type, attribute ou value que não esteja explicitamente listado nos fatos "
    "recebidos — copie esses campos exatamente como aparecem no contexto. "
    "Toda afirmação numérica na narrativa (xT, VAEP, PPDA, field tilt, intensidade "
    "de pressão etc.) deve ter uma entrada correspondente em cited_metrics. "
    "Se os fatos fornecidos não sustentarem uma métrica específica, não a cite."
)


def build_tactical_agent(settings: Settings) -> Agent[None, TacticalReport]:
    return Agent(
        model=build_pydantic_ai_model(settings),
        output_type=TacticalReport,
        system_prompt=_SYSTEM_PROMPT,
    )


def format_facts_context(facts: list[EntityEdge]) -> str:
    """Serializa os fatos recuperados do grafo num formato que o agente pode
    citar diretamente em `cited_metrics` (node_id = source_node_uuid)."""
    if not facts:
        return "Nenhum fato recuperado do grafo para esta consulta."

    lines = []
    for fact in facts:
        attrs = ", ".join(f"{k}={v}" for k, v in (fact.attributes or {}).items() if isinstance(v, (int, float)))
        lines.append(
            f"- fato: \"{fact.fact}\" | edge_type={fact.name} | node_id={fact.source_node_uuid} | atributos: {attrs or 'nenhum'}"
        )
    return "\n".join(lines)

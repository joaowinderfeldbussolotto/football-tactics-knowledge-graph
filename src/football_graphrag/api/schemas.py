"""Schemas Pydantic da API. `TacticalReport`/`MetricCitation` (seção 7 do
plano) são também o `output_type` do agente PydanticAI: o próprio modelo
lista, de forma estruturada, qual fato do grafo embasou cada afirmação do
texto, o que permite checar fidelidade sem outro LLM como juiz (seção 8)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MetricCitation(BaseModel):
    node_id: str = Field(description="UUID do nó de origem da aresta citada, tal como armazenado no Neo4j.")
    edge_type: str = Field(description="Nome do tipo de aresta citado, ex: 'Passa', 'Pressiona'.")
    attribute: str = Field(description="Atributo numérico citado dentro da aresta, ex: 'xt_gerado', 'intensidade'.")
    value: float = Field(description="Valor do atributo, copiado exatamente do fato fornecido como contexto.")


class TacticalReport(BaseModel):
    narrative: str = Field(description="Texto em português com a análise tática, citando os fatos relevantes.")
    cited_metrics: list[MetricCitation] = Field(
        default_factory=list,
        description="Toda métrica numérica mencionada na narrativa deve ter uma citação correspondente aqui.",
    )


class IngestResponse(BaseModel):
    match_id: str
    mode: str
    n_phases_ingested: int


class ReplayStartResponse(BaseModel):
    match_id: str
    status: str


class LiveInsightsResponse(BaseModel):
    match_id: str
    since_minute: float | None
    report: TacticalReport
    retrieval_ms: float
    generation_ms: float
    n_facts_retrieved: int


class HealthResponse(BaseModel):
    status: str
    neo4j: bool
    redis: bool

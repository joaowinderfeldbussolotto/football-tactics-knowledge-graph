"""Modelos de entrada/saída da API (camada 3).

``MetricaCitada`` é o contrato de citação obrigatória: cada número que o
LLM escreve aponta para um PadraoTatico existente no grafo, o que torna a
checagem de fidelidade (evaluation/faithfulness.py) determinística.
"""

from pydantic import BaseModel, Field


class MetricaCitada(BaseModel):
    padrao_tatico_id: str = Field(description="uid do nó PadraoTatico citado")
    nome_metrica: str
    valor: float
    algoritmo_origem: str


class SecaoRelatorio(BaseModel):
    titulo: str
    narrativa: str
    metricas_citadas: list[MetricaCitada]


class RelatorioTatico(BaseModel):
    resumo_executivo: str
    secoes: list[SecaoRelatorio]


class RespostaTatica(BaseModel):
    resposta: str
    metricas_citadas: list[MetricaCitada]
    confianca: str = Field(description="alta | media | baixa, segundo cobertura do contexto")


class AskRequest(BaseModel):
    match_id: int
    pergunta: str


class IngestResponse(BaseModel):
    match_id: int
    pipeline: dict
    graph: dict


class AnalyzeResponse(BaseModel):
    match_id: int
    padroes_por_tipo: dict[str, int]

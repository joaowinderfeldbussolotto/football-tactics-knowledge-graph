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
    narrativa: str = Field(description="análise em linguagem tática (tatiquês)")
    em_bom_portugues: str = Field(
        description="a mesma conclusão explicada em termos do dia a dia, sem jargão, "
        "como se fosse para alguém que assiste futebol mas não estuda tática"
    )
    metricas_citadas: list[MetricaCitada]


class RelatorioTatico(BaseModel):
    resumo_executivo: str
    secoes: list[SecaoRelatorio]


class ConsultaCypher(BaseModel):
    """Auditabilidade do modo autônomo: cada consulta que sustentou a resposta
    fica registrada e pode ser re-executada (evaluation/faithfulness.py)."""

    cypher: str
    resultado_resumido: str = Field(description="resumo de 1 linha do que a consulta retornou")


class RespostaTatica(BaseModel):
    resposta: str = Field(description="resposta em linguagem tática (tatiquês)")
    em_bom_portugues: str = Field(
        description="a mesma resposta explicada em termos do dia a dia, sem jargão"
    )
    metricas_citadas: list[MetricaCitada]
    consultas_executadas: list[ConsultaCypher] = Field(
        default_factory=list,
        description="consultas Cypher executadas via ferramenta que sustentam números da resposta",
    )
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

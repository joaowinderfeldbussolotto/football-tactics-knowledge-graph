"""Modelos de entrada/saída da API (camada 3).

``MetricaCitada`` é o contrato de citação obrigatória: cada número que o
LLM escreve aponta para um PadraoTatico existente no grafo, o que torna a
checagem de fidelidade (evaluation/faithfulness.py) determinística.
"""

import re

from pydantic import BaseModel, Field, field_validator

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _rejeita_eco_da_descricao(valor: str, descricao: str, campo: str) -> str:
    """Falha real, medida na 4ª rodada: o modelo às vezes copia o TEXTO da
    description do campo Pydantic como se fosse o valor — passa na validação
    de schema porque é uma string válida, e derruba a fidelidade em silêncio
    (padrao_tatico_id virou a string literal "uid" porque a description diz
    "uid do nó PadraoTatico citado"). O retry nativo do Agent (retries=2) só
    dispara quando a validação FALHA; um eco sintaticamente válido não a
    aciona. Este validador cria a falha que faltava, para o retry existente
    resolver sozinho em vez de precisar de um mecanismo novo.
    """
    normalizado = valor.strip().lower()
    if normalizado in {campo.lower(), descricao.strip().lower()} or normalizado in descricao.lower():
        raise ValueError(
            f"{campo!r} veio igual à descrição do campo ({valor!r}), não um valor real. "
            "Preencha com o dado de verdade, não repita o texto de ajuda."
        )
    return valor


class MetricaCitada(BaseModel):
    padrao_tatico_id: str = Field(description="uid do nó PadraoTatico citado")
    nome_metrica: str
    valor: float
    algoritmo_origem: str

    @field_validator("padrao_tatico_id")
    @classmethod
    def _uid_valido(cls, v: str) -> str:
        if not _UUID_RE.match(v.strip()):
            raise ValueError(
                f"padrao_tatico_id deve ser o uid (formato UUID) do PadraoTatico citado no "
                f"contexto, não {v!r}. Copie o campo uid exato do padrão, não um nome ou rótulo."
            )
        return v


class SecaoRelatorio(BaseModel):
    titulo: str
    narrativa: str = Field(description="análise em linguagem tática (tatiquês)")
    em_bom_portugues: str = Field(
        description="a mesma conclusão explicada em termos do dia a dia, sem jargão, "
        "como se fosse para alguém que assiste futebol mas não estuda tática"
    )
    metricas_citadas: list[MetricaCitada]


class ConsultaCypher(BaseModel):
    """Auditabilidade do modo autônomo: cada consulta que sustentou a resposta
    fica registrada e pode ser re-executada (evaluation/faithfulness.py)."""

    cypher: str
    resultado_resumido: str = Field(description="resumo de 1 linha do que a consulta retornou")


class RelatorioTatico(BaseModel):
    resumo_executivo: str
    secoes: list[SecaoRelatorio]
    consultas_executadas: list[ConsultaCypher] = Field(
        default_factory=list,
        description="consultas Cypher (read-only) que sustentam os fatos do jogo citados no relatório",
    )


class RespostaTatica(BaseModel):
    resposta: str = Field(description="resposta em linguagem tática (tatiquês)")
    em_bom_portugues: str = Field(
        description="a mesma resposta explicada em termos do dia a dia, sem jargão"
    )
    metricas_citadas: list[MetricaCitada]

    @field_validator("resposta")
    @classmethod
    def _resposta_nao_eh_a_descricao(cls, v: str) -> str:
        return _rejeita_eco_da_descricao(v, "resposta em linguagem tática (tatiquês)", "resposta")

    @field_validator("em_bom_portugues")
    @classmethod
    def _em_bom_portugues_nao_eh_a_descricao(cls, v: str) -> str:
        return _rejeita_eco_da_descricao(
            v, "a mesma resposta explicada em termos do dia a dia, sem jargão", "em_bom_portugues"
        )
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
    # None = Graphiti desligado (sem chaves de LLM/embedder). Presente = o que
    # aconteceu com a indexação opcional; uma falha ali não derruba a análise.
    graphiti: dict | None = None

"""Tipos de aresta customizados do Graphiti para o domínio tático de futebol.

Os atributos numéricos aqui vêm sempre das métricas já pré-calculadas pelo
pipeline de ingestão (`ingestion/spadl_transform.py`, `ingestion/tactical_metrics.py`)
e são apenas repassados ao LLM de extração como fatos do texto do episode;
nunca são recalculados na hora da consulta. Ver seção 6.3 do plano da PoC.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Passa(BaseModel):
    """Um passe de um jogador para outro (ou para um espaço)."""

    xt_gerado: float | None = Field(default=None, description="Valor de Expected Threat (xT) gerado pelo passe.")
    vaep_valor: float | None = Field(default=None, description="Valor VAEP da ação de passe.")
    progressivo: bool | None = Field(
        default=None, description="Se o passe avançou a bola significativamente em direção ao gol adversário."
    )
    sucesso: bool | None = Field(default=None, description="Se o passe chegou a um companheiro de time.")
    corredor: str | None = Field(default=None, description="Corredor do campo do passe: 'esquerdo', 'central' ou 'direito'.")


class Pressiona(BaseModel):
    """Um jogador ou time pressionando o portador da bola adversário."""

    intensidade: float | None = Field(default=None, description="Intensidade da pressão (ex: PPDA local).")
    zona: str | None = Field(default=None, description="Zona do campo onde a pressão ocorreu.")


class EmPosse(BaseModel):
    """Um jogador ou time em posse da bola por um intervalo de tempo."""

    duracao_segundos: float | None = Field(default=None, description="Duração da posse, em segundos.")


class ProgrideBolaVia(BaseModel):
    """Progressão de bola de uma fase de posse através de um corredor do campo."""

    corredor: str | None = Field(default=None, description="Corredor do campo usado na progressão.")
    distancia: float | None = Field(default=None, description="Distância progredida em direção ao gol, em metros.")


class MembroDoTime(BaseModel):
    """Vínculo de um jogador com um time durante a partida."""

    titular: bool | None = Field(default=None, description="Se o jogador começou a partida como titular.")


EDGE_TYPES: dict[str, type[BaseModel]] = {
    "Passa": Passa,
    "Pressiona": Pressiona,
    "EmPosse": EmPosse,
    "ProgrideBolaVia": ProgrideBolaVia,
    "MembroDoTime": MembroDoTime,
}

# Restringe quais tipos de aresta o LLM pode extrair entre cada par de tipos
# de entidade (fonte, destino). Reduz alucinação de arestas fora de domínio.
EDGE_TYPE_MAP: dict[tuple[str, str], list[str]] = {
    ("Jogador", "Jogador"): ["Passa", "Pressiona"],
    ("Jogador", "Time"): ["MembroDoTime"],
    ("Time", "Jogador"): ["Pressiona"],
    ("Time", "Time"): ["Pressiona"],
    ("Jogador", "FaseDePosse"): ["EmPosse"],
    ("Time", "FaseDePosse"): ["EmPosse", "ProgrideBolaVia"],
    ("FaseDePosse", "PadraoDeConstrucao"): ["ProgrideBolaVia"],
    ("Time", "SequenciaDePressao"): ["Pressiona"],
}

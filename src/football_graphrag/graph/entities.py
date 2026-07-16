"""Tipos de entidade customizados do Graphiti para o domínio tático de futebol.

Cada classe estende o nó genérico `Entity` do Graphiti com atributos
adicionais que o LLM de extração deve preencher a partir do texto do
episode. O `name` e o `summary` do nó já são cobertos pelo Graphiti; aqui
só declaramos os campos extras específicos do domínio. Ver seção 6.3 do
plano da PoC.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Jogador(BaseModel):
    """Um jogador em campo durante a partida."""

    posicao: str | None = Field(
        default=None, description="Posição principal do jogador em campo (ex: 'zagueiro', 'meia')."
    )
    time: str | None = Field(default=None, description="Nome do time pelo qual o jogador atuou na ação.")
    numero_camisa: int | None = Field(default=None, description="Número da camisa do jogador, se mencionado.")


class Time(BaseModel):
    """Um time (clube ou seleção) presente na partida."""

    lado: str | None = Field(
        default=None, description="Lado do time na partida, ex: 'mandante' ou 'visitante'."
    )


class FaseDePosse(BaseModel):
    """Uma sequência contínua de posse de bola por um dos times."""

    time_com_posse: str | None = Field(default=None, description="Nome do time que estava com a bola.")
    minuto_inicio: float | None = Field(default=None, description="Minuto de jogo em que a posse começou.")
    minuto_fim: float | None = Field(default=None, description="Minuto de jogo em que a posse terminou.")
    resultado: str | None = Field(
        default=None,
        description="Como a fase de posse terminou, ex: 'finalização', 'perda de bola', 'escanteio'.",
    )


class SequenciaDePressao(BaseModel):
    """Um episódio de pressão exercido por um time sobre o adversário."""

    time_pressionando: str | None = Field(default=None, description="Time que exerceu a pressão.")
    zona_campo: str | None = Field(
        default=None,
        description="Zona do campo onde a pressão ocorreu (ex: 'terço final', 'campo de defesa').",
    )
    intensidade: float | None = Field(
        default=None, description="Intensidade da pressão, tipicamente medida via PPDA na janela avaliada."
    )


class PadraoDeConstrucao(BaseModel):
    """Um padrão recorrente de construção de jogada identificado no jogo."""

    rotulo: str | None = Field(
        default=None, description="Rótulo descritivo do padrão, ex: 'saída pela direita com triangulação'."
    )
    corredor: str | None = Field(
        default=None, description="Corredor do campo predominantemente envolvido: 'esquerdo', 'central' ou 'direito'."
    )


ENTITY_TYPES: dict[str, type[BaseModel]] = {
    "Jogador": Jogador,
    "Time": Time,
    "FaseDePosse": FaseDePosse,
    "SequenciaDePressao": SequenciaDePressao,
    "PadraoDeConstrucao": PadraoDeConstrucao,
}

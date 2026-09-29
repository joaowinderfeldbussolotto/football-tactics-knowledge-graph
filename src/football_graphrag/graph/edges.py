"""Tipos Pydantic das arestas factuais (camada 1).

Regra da camada 1: toda propriedade numérica de aresta vem de uma coluna do
parquet, sem transformação. As agregações (ATUOU_EM, PROGREDIU_PARA,
PARTICIPOU_DE) são somas/contagens diretas de colunas — transformação
aritmética nova pertence ao passo 0.4, não aqui.
"""

from pydantic import BaseModel


class PassouPara(BaseModel):
    """Jogador -> Jogador. Um passe bem-sucedido com recebedor resolvido."""

    match_id: int
    action_id: int          # chave de idempotência da aresta
    minuto: float
    xt_gerado: float
    vaep: float
    progressivo: bool
    sucesso: bool
    zona_origem: int
    zona_destino: int
    fase_posse_id: str


class Pressionou(BaseModel):
    """Jogador -> Jogador. Evento de pressão do StatsBomb (fora do SPADL)."""

    match_id: int
    pressure_idx: int       # chave de idempotência
    minuto: float
    zona: int | None
    fase_posse_id: str | None = None


class AtuouEm(BaseModel):
    """Jogador -> Zona. Agregado por partida."""

    match_id: int
    contagem_acoes: int
    xt_acumulado: float


class ParticipouDe(BaseModel):
    """Jogador -> FaseDePosse."""

    match_id: int
    numero_de_toques: int


class MembroDe(BaseModel):
    """Jogador -> Time."""

    match_id: int
    posicao_nominal: str | None


class ProgrediuPara(BaseModel):
    """Zona -> Zona. Fluxo agregado de progressão por time na partida."""

    match_id: int
    team_id: int
    contagem: int
    xt_medio: float

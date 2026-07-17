"""Tipos Pydantic dos nós do grafo (camada 1 + nó derivado da camada 2).

Cada nó tem um ``uid`` determinístico (uuid5 sobre a chave natural), que é a
base da idempotência da escrita: rodar a construção duas vezes não duplica
nada. Ver docs/02-modelo-grafo.md para a legenda completa.
"""

import uuid

from pydantic import BaseModel

# Namespace fixo do projeto para uuid5 (determinístico por definição).
NAMESPACE = uuid.UUID("b70ac57e-7a5f-4f3e-9c2b-2f6d84cba0aa")


def uid_for(kind: str, *key_parts: object) -> str:
    """uuid5 determinístico: mesma entidade => mesmo uid, sempre."""
    return str(uuid.uuid5(NAMESPACE, kind + ":" + ":".join(str(p) for p in key_parts)))


class Jogador(BaseModel):
    uid: str
    player_id: int
    nome: str
    posicao_nominal: str | None = None
    time: str | None = None

    @classmethod
    def make(cls, player_id: int, nome: str, posicao_nominal: str | None, time: str | None) -> "Jogador":
        return cls(uid=uid_for("jogador", player_id), player_id=player_id, nome=nome, posicao_nominal=posicao_nominal, time=time)


class Time(BaseModel):
    uid: str
    team_id: int
    nome: str

    @classmethod
    def make(cls, team_id: int, nome: str) -> "Time":
        return cls(uid=uid_for("time", team_id), team_id=team_id, nome=nome)


class Zona(BaseModel):
    uid: str
    id_zona: int
    faixa: str      # defesa | meio | ataque
    corredor: str   # esquerda | centro | direita

    @classmethod
    def make(cls, id_zona: int, faixa: str, corredor: str) -> "Zona":
        return cls(uid=uid_for("zona", id_zona), id_zona=id_zona, faixa=faixa, corredor=corredor)


class FaseDePosse(BaseModel):
    uid: str
    fase_id: str            # "{match_id}:{possession_id}"
    match_id: int
    team_id: int
    minuto_inicio: float
    minuto_fim: float
    xt_total: float
    zona_inicio: int
    zona_fim: int
    n_acoes: int

    @classmethod
    def make(cls, match_id: int, possession_id: int, **props) -> "FaseDePosse":
        fase_id = f"{match_id}:{possession_id}"
        return cls(uid=uid_for("fase", fase_id), fase_id=fase_id, match_id=match_id, **props)


class Partida(BaseModel):
    uid: str
    match_id: int
    competicao: str
    data: str
    times: list[str]

    @classmethod
    def make(cls, match_id: int, competicao: str, data: str, times: list[str]) -> "Partida":
        return cls(uid=uid_for("partida", match_id), match_id=match_id, competicao=competicao, data=data, times=times)


class PadraoTatico(BaseModel):
    """Nó derivado da camada 2. ``algoritmo_origem`` é obrigatório: é a
    rastreabilidade acadêmica de qual procedure produziu o padrão."""

    uid: str
    tipo: str
    descricao_curta: str
    match_id: int
    time: str
    minuto_inicio: float | None = None
    minuto_fim: float | None = None
    valor_metrica: float
    nome_metrica: str
    algoritmo_origem: str
    jogadores_envolvidos: list[str] = []
    zonas_envolvidas: list[int] = []
    # Modelo bitemporal (insight 7.7): estado válido num intervalo do jogo.
    valid_at: float | None = None
    invalid_at: float | None = None

    @classmethod
    def make(cls, tipo: str, match_id: int, time: str, chave_extra: str = "", **props) -> "PadraoTatico":
        return cls(uid=uid_for("padrao", tipo, match_id, time, chave_extra), tipo=tipo, match_id=match_id, time=time, **props)

"""The 30 benchmark questions about the 2022 World Cup final (match 3869685).

Six per type:

- ``factual``: find one fact;
- ``aggregation``: count and rank many events;
- ``structural``: run a graph algorithm on the pass network;
- ``composite``: a structural result combined with an aggregation;
- ``unanswerable``: the data does not contain the answer.

Every question is closed ("quem", "quantos", "quais"). The expected answers
live in ``ground_truth.py``, computed without Neo4j.

Choices made while writing them (details in docs/benchmark.md):

- Only 2 factual questions have a widely known answer (f01, f02); the
  ``no_context`` arm measures how much the model answers from memory.
- No question depends on a definition where the raw StatsBomb JSON and the
  SPADL actions disagree: "passes attempted" (SPADL drops a few passes) and
  goalkeeper saves (SPADL counts one "Keeper Sweeper Clear" as a save) were
  left out on purpose.
- Structural questions use only ``pivo_estrutural`` (betweenness) and
  ``terceiro_homem`` (path pattern). ``ligacao_fragil`` was left out: the
  final has no bridges in either pass network, so the pattern falls back to
  Louvain communities, which change with the random seed. A ground truth
  that depends on a seed is not a ground truth.
- No question has a tie at the position being asked.
"""

from dataclasses import dataclass

MATCH_ID = 3869685

QUESTION_TYPES = ("factual", "aggregation", "structural", "composite", "unanswerable")
CHECKS = ("player", "value", "set", "player_and_value", "no_data")

# Definitions repeated in the structural and composite questions, so that
# every arm receives the same, self-contained question.
_PIVOT = (
    "o pivô da rede de passes {team} (o jogador com maior betweenness centrality "
    "na rede de passes certos do time, ponderada pelo xT)"
)
_SECOND = (
    "o jogador com a segunda maior betweenness centrality na rede de passes {team} "
    "(rede de passes certos do time, ponderada pelo xT)"
)
_TRIO_DEFINITION = (
    "sequência de passes certos A→B→C entre três jogadores diferentes, na mesma "
    "posse e quase consecutivos, que leva a bola a um terço mais avançado do campo"
)
_TRIO = f"trio progressivo ({_TRIO_DEFINITION})"


@dataclass(frozen=True)
class Question:
    id: str  # type prefix: f01, a01, s01, c01, u01
    type: str  # factual | aggregation | structural | composite | unanswerable
    text: str  # in Portuguese
    check: str  # player | value | set | player_and_value | no_data
    tolerance: float = 0.0  # only for continuous values; counts are exact


QUESTIONS: list[Question] = [
    # ------------------------------------------------------------ factual
    Question("f01", "factual", "Quem marcou o primeiro gol da final?", "player"),
    Question(
        "f02",
        "factual",
        "Quantos gols foram marcados na final, somando tempo normal e prorrogação "
        "(sem contar a disputa de pênaltis)?",
        "value",
    ),
    Question("f03", "factual", "Quem deu a assistência para o segundo gol da França na final?", "player"),
    Question("f04", "factual", "Quem foi o primeiro jogador a receber cartão amarelo na final?", "player"),
    Question(
        "f05",
        "factual",
        "Qual jogador recebeu cartão amarelo na final sem ter cometido falta?",
        "player",
    ),
    Question("f06", "factual", "Quantas finalizações Lautaro Martínez fez na final?", "value"),
    # ------------------------------------------------------------ aggregation
    Question(
        "a01",
        "aggregation",
        "Quem fez mais desarmes certos na final? Liste os 3 primeiros.",
        "set",
    ),
    Question(
        "a02",
        "aggregation",
        "Qual jogador deu mais passes certos na final, e quantos foram?",
        "player_and_value",
    ),
    Question(
        "a03",
        "aggregation",
        "Qual jogador completou mais dribles na final, e quantos foram?",
        "player_and_value",
    ),
    Question(
        "a04",
        "aggregation",
        "Quantas finalizações a França fez na final (tempo normal e prorrogação)?",
        "value",
    ),
    Question(
        "a05",
        "aggregation",
        "Qual jogador cometeu mais faltas na final, e quantas foram?",
        "player_and_value",
    ),
    Question("a06", "aggregation", "Quais jogadores da França receberam cartão amarelo na final?", "set"),
    # ------------------------------------------------------------ structural
    Question("s01", "structural", f"Na final, quem era {_PIVOT.format(team='da Argentina')}?", "player"),
    Question("s02", "structural", f"Na final, quem era {_PIVOT.format(team='da França')}?", "player"),
    Question("s03", "structural", f"Na final, quem era {_SECOND.format(team='da Argentina')}?", "player"),
    Question("s04", "structural", f"Na final, quem era {_SECOND.format(team='da França')}?", "player"),
    Question(
        "s05",
        "structural",
        f"Quais jogadores formam o {_TRIO} que a França mais repetiu na final?",
        "set",
    ),
    Question(
        "s06",
        "structural",
        "Quantos trios progressivos distintos a Argentina repetiu pelo menos duas vezes "
        f"na final? Trio progressivo: {_TRIO_DEFINITION}.",
        "value",
    ),
    # ------------------------------------------------------------ composite
    Question(
        "c01",
        "composite",
        f"Quantos passes errou {_PIVOT.format(team='da Argentina')} na final?",
        "value",
    ),
    Question(
        "c02",
        "composite",
        f"Quantos passes certos deu {_PIVOT.format(team='da França')} na final?",
        "value",
    ),
    Question(
        "c03",
        "composite",
        f"Quantos desarmes certos fez {_SECOND.format(team='da Argentina')} na final?",
        "value",
    ),
    Question(
        "c04",
        "composite",
        f"Entre os três jogadores do {_TRIO} que a França mais repetiu na final, "
        "qual deu mais passes certos na partida?",
        "player",
    ),
    Question(
        "c05",
        "composite",
        f"Quantos passes certos {_PIVOT.format(team='da Argentina')} deu para "
        f"{_SECOND.format(team='da Argentina')}, na final?",
        "value",
    ),
    Question(
        "c06",
        "composite",
        f"Quantas faltas cometeu {_SECOND.format(team='da França')} na final?",
        "value",
    ),
    # ------------------------------------------------------------ unanswerable
    Question("u01", "unanswerable", "Qual foi a velocidade máxima atingida por Mbappé na final?", "no_data"),
    Question("u02", "unanswerable", "Quantos quilômetros Enzo Fernández percorreu na final?", "no_data"),
    Question("u03", "unanswerable", "Quem foi eleito o melhor jogador da final?", "no_data"),
    Question(
        "u04", "unanswerable", "Qual era a temperatura no estádio durante a final?", "no_data"
    ),
    Question("u05", "unanswerable", "Quantos torcedores assistiram à final no estádio?", "no_data"),
    Question(
        "u06",
        "unanswerable",
        "Qual foi a frequência cardíaca máxima de Di María durante a final?",
        "no_data",
    ),
]

BY_ID: dict[str, Question] = {q.id: q for q in QUESTIONS}


def get_question(question_id: str) -> Question:
    try:
        return BY_ID[question_id]
    except KeyError:
        raise KeyError(f"unknown question id {question_id!r}; valid: {', '.join(BY_ID)}") from None


def _validate() -> None:
    assert len(QUESTIONS) == 30, len(QUESTIONS)
    assert len(BY_ID) == 30, "duplicate ids"
    for t in QUESTION_TYPES:
        assert sum(q.type == t for q in QUESTIONS) == 6, t
    for q in QUESTIONS:
        assert q.check in CHECKS, q
        assert q.id[0] == q.type[0], q
        assert (q.check == "no_data") == (q.type == "unanswerable"), q


_validate()

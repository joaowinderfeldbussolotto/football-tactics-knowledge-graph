"""Duas rubricas via LLM-as-judge (seção 8 do plano).

Reduzidas de três para duas porque fidelidade já é coberta, sem LLM, por
`faithfulness.py`:

- `retrieval_accuracy`: o contexto recuperado do grafo contém os fatos
  necessários para responder a pergunta do golden dataset.
- `tactical_insight`: a narrativa vai além de repetir o número — explica o
  padrão tático por trás dele.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from football_graphrag.config import Settings
from football_graphrag.llm.provider import build_pydantic_ai_model


class JudgeScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="0.0 = reprovado, 1.0 = totalmente satisfatório.")
    rationale: str = Field(description="Justificativa curta da nota, em português.")


_RETRIEVAL_ACCURACY_PROMPT = (
    "Você avalia se um contexto recuperado de um grafo de conhecimento tático de futebol "
    "contém os fatos necessários para responder a uma pergunta específica, comparando com uma "
    "resposta de referência. Dê score 1.0 se o contexto sustenta totalmente a resposta de "
    "referência, 0.5 se sustenta parcialmente, e 0.0 se não tem relação com a pergunta."
)

_TACTICAL_INSIGHT_PROMPT = (
    "Você avalia a profundidade tática de uma narrativa de análise de futebol. Dê score 1.0 se "
    "o texto explica padrões e causas (ex: por que a pressão funcionou, o que a métrica revela "
    "sobre o estilo de jogo), 0.5 se mistura números com alguma explicação rasa, e 0.0 se apenas "
    "repete números sem nenhuma interpretação tática."
)


def _build_judge(settings: Settings, system_prompt: str) -> Agent[None, JudgeScore]:
    return Agent(model=build_pydantic_ai_model(settings), output_type=JudgeScore, system_prompt=system_prompt)


async def judge_retrieval_accuracy(
    settings: Settings, question: str, reference_answer: str, retrieved_context: str
) -> JudgeScore:
    agent = _build_judge(settings, _RETRIEVAL_ACCURACY_PROMPT)
    prompt = (
        f"Pergunta: {question}\n"
        f"Resposta de referência: {reference_answer}\n\n"
        f"Contexto recuperado do grafo:\n{retrieved_context}"
    )
    result = await agent.run(prompt)
    return result.output


async def judge_tactical_insight(settings: Settings, narrative: str) -> JudgeScore:
    agent = _build_judge(settings, _TACTICAL_INSIGHT_PROMPT)
    result = await agent.run(f"Narrativa a avaliar:\n{narrative}")
    return result.output

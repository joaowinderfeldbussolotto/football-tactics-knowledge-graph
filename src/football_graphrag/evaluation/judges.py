"""LLM-as-judge: duas rubricas (seção 9 do plano).

- retrieval_accuracy: o contexto recuperado continha o necessário?
- tactical_insight: a narrativa explica o padrão ou só repete o número?

Os juízes usam o mesmo provedor configurado (PydanticAI), com saída
estruturada. São a parte NÃO determinística da avaliação; a fidelidade
numérica é a checagem determinística de faithfulness.py.
"""

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from football_graphrag.config import get_settings
from football_graphrag.llm.provider import pydantic_ai_model


class JudgeScore(BaseModel):
    score: int = Field(ge=1, le=5, description="1=péssimo, 5=excelente")
    justificativa: str


PROMPT_RETRIEVAL = """\
Você avalia RECUPERAÇÃO de contexto num sistema de Q&A tático de futebol.
Recebe: a pergunta, a resposta de referência e o contexto que foi recuperado.
Dê score 1-5 respondendo: o contexto recuperado continha a informação
necessária para produzir a resposta de referência? (5 = tudo presente;
3 = parcial; 1 = a informação necessária não está no contexto).
Avalie APENAS o contexto, não a resposta gerada.
"""

PROMPT_INSIGHT = """\
Você avalia QUALIDADE DE INSIGHT TÁTICO numa resposta sobre futebol.
Recebe: a pergunta, a resposta de referência e a resposta gerada.
Dê score 1-5 respondendo: a resposta gerada EXPLICA o padrão tático
(mecanismo, por que importa, o que revela sobre o time) ou só repete
números? (5 = explica o mecanismo corretamente e é consistente com a
referência; 3 = correta mas rasa, só repete o número; 1 = errada ou vazia).
"""


@lru_cache
def retrieval_judge() -> Agent:
    return Agent(pydantic_ai_model(get_settings()), output_type=JudgeScore, system_prompt=PROMPT_RETRIEVAL)


@lru_cache
def insight_judge() -> Agent:
    return Agent(pydantic_ai_model(get_settings()), output_type=JudgeScore, system_prompt=PROMPT_INSIGHT)


async def judge_retrieval(pergunta: str, referencia: str, contexto: str) -> JudgeScore:
    result = await retrieval_judge().run(
        f"PERGUNTA: {pergunta}\n\nRESPOSTA DE REFERÊNCIA: {referencia}\n\nCONTEXTO RECUPERADO:\n{contexto}"
    )
    return result.output


async def judge_insight(pergunta: str, referencia: str, resposta: str) -> JudgeScore:
    result = await insight_judge().run(
        f"PERGUNTA: {pergunta}\n\nRESPOSTA DE REFERÊNCIA: {referencia}\n\nRESPOSTA GERADA:\n{resposta}"
    )
    return result.output

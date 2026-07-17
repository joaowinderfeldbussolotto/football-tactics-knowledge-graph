"""Agentes PydanticAI (camada 3). O LLM NUNCA calcula: só lê e escreve.

Regras da seção 4 do plano aplicadas aqui:
- Troca de provedor: string do PydanticAI vinda de llm/provider.py.
- Rate limiting: um único asyncio.Semaphore de aplicação, inicializado com
  SEMAPHORE_LIMIT (o mesmo valor que o Graphiti lê do ambiente), adquirido
  antes de cada agent.run(). Isso é o rate limiting inteiro do projeto.
- Retry: nenhum aqui; os SDKs por baixo já retentam (LLM_MAX_RETRIES).
"""

import asyncio
import json
from functools import lru_cache

from pydantic_ai import Agent

from football_graphrag.api.schemas import RelatorioTatico, RespostaTatica
from football_graphrag.config import Settings, get_settings
from football_graphrag.llm.provider import pydantic_ai_model

PROMPT_RELATORIO = """\
Você é um analista tático de futebol. Recebe uma lista de PADRÕES TÁTICOS já
calculados por algoritmos de grafo determinísticos (betweenness, comunidades,
caminhos multi-hop, janelas temporais) sobre o grafo da partida, e opcionalmente
resumos de comunidades de padrões.

Sua tarefa é VERBALIZAR esses achados numa narrativa tática estruturada.

Regras invioláveis:
1. Você NÃO calcula nada. Todo número da narrativa vem de um padrão recebido.
2. Toda métrica mencionada entra em metricas_citadas com o padrao_tatico_id
   (campo uid), nome_metrica, valor e algoritmo_origem EXATOS do padrão citado.
3. NÃO mencione placar, gols nem quem venceu: o relatório é sobre COMO o jogo
   foi jogado, não sobre o resultado.
4. Não invente padrões, jogadores nem valores que não estejam no contexto.
5. Escreva em DOIS registros por seção:
   - narrativa: linguagem tática (tatiquês) — betweenness, PPDA, bloco, corredor,
     linha de passe — explicando POR QUE cada padrão importa e o que um
     treinador faria com essa informação.
   - em_bom_portugues: a MESMA conclusão em termos do dia a dia, sem nenhum
     jargão, como você explicaria para alguém que assiste futebol no bar:
     o que aconteceu em campo e por que isso decidiu alguma coisa
     (ex.: "quase toda jogada da Argentina passava pelo Otamendi; se a França
     tivesse colado um atacante nele, o time ficava sem saída de bola").
Organize as seções por tema (estrutura de construção, pressão, mudanças ao
longo do jogo), não uma seção por padrão.
"""

PROMPT_QA = """\
Você é um analista tático de futebol respondendo uma pergunta específica sobre
uma partida. Recebe contexto recuperado do grafo da partida: padrões táticos
calculados por algoritmos determinísticos e, às vezes, fatos factuais do grafo.

Regras invioláveis:
1. Você NÃO calcula nada; responde apenas com o que está no contexto.
2. Toda métrica citada entra em metricas_citadas com o padrao_tatico_id (uid),
   nome_metrica, valor e algoritmo_origem EXATOS.
3. Se o contexto não contém a resposta, diga isso explicitamente e marque
   confianca=baixa. NÃO complete com conhecimento externo sobre a partida.
4. Não mencione placar nem resultado, a menos que a pergunta seja sobre isso
   e o dado esteja no contexto.
Responda em português, direto ao ponto, em DOIS registros:
- resposta: linguagem tática (tatiquês), com as métricas.
- em_bom_portugues: a MESMA resposta em termos do dia a dia, sem jargão,
  como você explicaria para alguém que assiste futebol no bar — o que isso
  significava em campo, na prática.
"""


@lru_cache
def _semaphore() -> asyncio.Semaphore:
    """Semáforo único de aplicação (mesmo limite que o Graphiti usa)."""
    return asyncio.Semaphore(get_settings().semaphore_limit)


# Knobs nativos do PydanticAI (não são camada nossa): retries = novas
# tentativas quando a saída estruturada falha na validação; max_tokens alto
# porque o relatório completo não cabe no default de 4096 do SDK.
_MODEL_SETTINGS = {"max_tokens": 16000}


@lru_cache
def report_agent() -> Agent:
    return Agent(
        pydantic_ai_model(get_settings()),
        output_type=RelatorioTatico,
        system_prompt=PROMPT_RELATORIO,
        retries=2,
        model_settings=_MODEL_SETTINGS,
    )


@lru_cache
def qa_agent() -> Agent:
    return Agent(
        pydantic_ai_model(get_settings()),
        output_type=RespostaTatica,
        system_prompt=PROMPT_QA,
        retries=2,
        model_settings=_MODEL_SETTINGS,
    )


def _format_patterns(patterns: list[dict]) -> str:
    return json.dumps(patterns, ensure_ascii=False, indent=2, default=str)


async def generate_report(patterns: list[dict], community_summaries: list[str] | None = None) -> RelatorioTatico:
    """Gera o relatório tático a partir de padrões JÁ calculados (camada 2)."""
    context = "PADRÕES TÁTICOS CALCULADOS:\n" + _format_patterns(patterns)
    if community_summaries:
        context += "\n\nRESUMOS DE COMUNIDADES:\n" + "\n".join(community_summaries)
    async with _semaphore():
        result = await report_agent().run(context)
    return result.output


async def answer_question(question: str, context_patterns: list[dict], extra_facts: list[str]) -> RespostaTatica:
    """Responde uma pergunta usando contexto recuperado do grafo."""
    context = (
        f"PERGUNTA: {question}\n\n"
        "PADRÕES TÁTICOS RELEVANTES:\n" + _format_patterns(context_patterns)
    )
    if extra_facts:
        context += "\n\nFATOS ADICIONAIS RECUPERADOS:\n" + "\n".join(f"- {f}" for f in extra_facts)
    async with _semaphore():
        result = await qa_agent().run(context)
    return result.output


def settings_fingerprint(settings: Settings) -> str:
    """Identificação do provedor ativo (para logs e docs/05-decisoes.md)."""
    return f"{settings.llm_provider}:{settings.llm_model}"

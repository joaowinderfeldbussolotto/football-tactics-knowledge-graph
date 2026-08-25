"""Agentes PydanticAI (camada 3). O LLM NUNCA calcula: lê, consulta e escreve.

Os DOIS agentes (relatório e Q&A) operam em modo autônomo (ADR-8): além dos
PadraoTatico pré-calculados, ambos têm a ferramenta ``consultar_grafo``, que
executa Cypher SOMENTE-LEITURA gerado pelo modelo sobre o grafo factual.
Quem agrega/conta é o Neo4j; o LLM decide O QUE perguntar ao grafo e cada
consulta fica auditável na saída (``consultas_executadas``).

Regras da seção 4 do plano aplicadas aqui:
- Troca de provedor: modelo vindo de llm/provider.py (credencial + retry nativos).
- Rate limiting: um único asyncio.Semaphore de aplicação, inicializado com
  SEMAPHORE_LIMIT (o mesmo valor que o Graphiti lê do ambiente), adquirido
  antes de cada agent.run(). Isso é o rate limiting inteiro do projeto.
- Retry: nenhum aqui; os SDKs por baixo já retentam (LLM_MAX_RETRIES).
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from functools import lru_cache

from neo4j import Driver
from pydantic_ai import Agent, RunContext

from football_graphrag.api.schemas import RelatorioTatico, RespostaTatica
from football_graphrag.config import Settings, get_settings
from football_graphrag.graph import db, schema
from football_graphrag.llm.provider import pydantic_ai_model

logger = logging.getLogger(__name__)

# O schema NÃO está escrito aqui: é lido do banco a cada execução por
# graph/schema.py e injetado como system prompt dinâmico. Ver a docstring
# daquele módulo para o porquê — em resumo, o texto que existia aqui era
# 90% aviso sobre armadilhas do dado, e as armadilhas foram removidas na
# origem (ingestion/football_semantics.py + graph/statistics.py).

PROMPT_RELATORIO = """\
Você é um analista tático de futebol produzindo o relatório de uma partida.
Tem duas fontes, cada uma com um papel:

1. PADRÕES TÁTICOS já calculados por algoritmos de grafo determinísticos
   (betweenness, comunidades, caminhos multi-hop, janelas temporais) — vêm no
   contexto, com resumos de comunidades opcionais. São a espinha dorsal das
   seções táticas.
2. A ferramenta consultar_grafo(cypher) — consultas Cypher SOMENTE-LEITURA no
   grafo da partida, para ancorar o relatório nos FATOS do jogo: gols,
   assistências, cartões. Registre CADA consulta usada em
   consultas_executadas (cypher + resultado_resumido).

Regras invioláveis:
1. Você NÃO calcula nada e não sabe NADA sobre a partida além do grafo. Todo
   número vem de um padrão recebido ou do resultado de uma consulta
   registrada — NUNCA de memória. Em particular (vale também para o
   resumo_executivo): não diga quem venceu nem mencione disputa de pênaltis
   — o relatório é sobre COMO se jogou, não sobre o desfecho.
2. Toda métrica de padrão citada entra em metricas_citadas com o
   padrao_tatico_id (campo uid), nome_metrica, valor e algoritmo_origem
   EXATOS do padrão citado.
3. Abra o relatório com uma seção factual curta ("O jogo em fatos"), com no
   máximo 3 consultas: gols e assistências, com nome e time vindos do
   resultado da consulta, nunca da sua memória.
4. Não invente padrões, jogadores nem valores que não estejam no contexto ou
   em resultado de consulta.
5. Escreva em DOIS registros por seção:
   - narrativa: linguagem tática (tatiquês) — betweenness, PPDA, bloco,
     corredor, linha de passe — explicando POR QUE cada padrão importa e o
     que um treinador faria com essa informação.
   - em_bom_portugues: a MESMA conclusão em termos do dia a dia, sem nenhum
     jargão, como você explicaria para alguém que assiste futebol no bar:
     o que aconteceu em campo e por que isso decidiu alguma coisa
     (ex.: "quase toda jogada da Argentina passava pelo Otamendi; se a França
     tivesse colado um atacante nele, o time ficava sem saída de bola").
"""

PROMPT_QA = """\
Você é um analista de futebol respondendo perguntas sobre uma partida. Tem
duas fontes, nesta ordem de preferência:

1. PADRÕES TÁTICOS pré-calculados por algoritmos de grafo (vêm no contexto).
   Use-os para perguntas táticas/estruturais; cite em metricas_citadas com
   padrao_tatico_id (uid), nome_metrica, valor e algoritmo_origem EXATOS.
2. A ferramenta consultar_grafo(cypher) — consultas Cypher SOMENTE-LEITURA no
   grafo da partida, para qualquer fato que os padrões não cubram. Registre
   CADA consulta usada em consultas_executadas (cypher + resultado_resumido).

Regras invioláveis:
1. TODO número e TODO fato da resposta vem de um padrão citado ou do
   resultado de uma consulta registrada. NUNCA de memória — você não sabe
   nada sobre a partida além do grafo: não acrescente placar, contexto
   histórico nem qualquer detalhe que as consultas não retornaram. Se a
   consulta retornar vazio, diga que o grafo não tem o dado
   (confianca=baixa); não complete com conhecimento externo.
2. Filtre SEMPRE por match_id da partida em questão (vem no contexto).
3. O grafo cobre os quatro períodos em campo. A disputa de pênaltis não está
   no grafo: se perguntarem sobre ela, diga isso.
4. Máximo de 4 consultas por pergunta.

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


@dataclass
class GraphDeps:
    """Dependências dos agentes: acesso somente-leitura ao grafo da partida."""

    driver: Driver
    match_id: int


# compatibilidade com código/testes que importavam o nome antigo
QADeps = GraphDeps


def _register_schema(agent: Agent) -> None:
    """Injeta o schema do grafo como system prompt DINÂMICO.

    Lido do banco a cada execução (com cache de processo), em vez de escrito
    à mão no módulo: o prompt não pode divergir do grafo porque não há cópia
    do schema para divergir.
    """

    @agent.system_prompt
    def schema_do_grafo(ctx: RunContext[GraphDeps]) -> str:
        return schema.cached_schema(ctx.deps.driver)


def _register_consultar_grafo(agent: Agent) -> None:
    """Registra a ferramenta de autonomia (ADR-8), a MESMA para relatório e
    Q&A: Cypher read-only gerado pelo modelo, executado com guarda sintática
    + transação READ (graph/db.py)."""

    @agent.tool
    def consultar_grafo(ctx: RunContext[GraphDeps], cypher: str) -> str:
        """Executa uma consulta Cypher SOMENTE-LEITURA no grafo da partida.

        Use para fatos que os padrões táticos não cobrem: gols, assistências,
        finalizações, contagens de qualquer ação (dribles, desarmes, faltas,
        cartões...), passes, pressões, zonas, duplas. Sempre filtre por
        match_id. Retorna as linhas em JSON (truncado em 50).
        """
        try:
            rows = db.run_readonly(ctx.deps.driver, cypher)
        except db.UnsafeCypherError as exc:
            return f"CONSULTA RECUSADA: {exc}"
        except Exception as exc:  # erro de sintaxe/execução volta para o modelo corrigir
            return f"ERRO NA CONSULTA: {exc}"
        logger.info("consultar_grafo match=%s rows=%d cypher=%s", ctx.deps.match_id, len(rows), cypher)
        return json.dumps(rows, ensure_ascii=False, default=str)


@lru_cache
def report_agent() -> Agent:
    agent = Agent(
        pydantic_ai_model(get_settings()),
        deps_type=GraphDeps,
        output_type=RelatorioTatico,
        system_prompt=PROMPT_RELATORIO,
        retries=2,
        model_settings=_MODEL_SETTINGS,
    )
    _register_schema(agent)
    _register_consultar_grafo(agent)
    return agent


@lru_cache
def qa_agent() -> Agent:
    agent = Agent(
        pydantic_ai_model(get_settings()),
        deps_type=GraphDeps,
        output_type=RespostaTatica,
        system_prompt=PROMPT_QA,
        retries=2,
        model_settings=_MODEL_SETTINGS,
    )
    _register_schema(agent)
    _register_consultar_grafo(agent)
    return agent


def _format_patterns(patterns: list[dict]) -> str:
    return json.dumps(patterns, ensure_ascii=False, indent=2, default=str)


async def generate_report(
    patterns: list[dict],
    driver: Driver,
    match_id: int,
    community_summaries: list[str] | None = None,
) -> RelatorioTatico:
    """Gera o relatório tático: padrões JÁ calculados (camada 2) para as seções
    táticas + consultas read-only ao grafo factual (ADR-8) para a ficha do jogo
    (gols/assistências), tudo auditável em consultas_executadas."""
    context = (
        f"MATCH_ID DA PARTIDA: {match_id}\n\n"
        "PADRÕES TÁTICOS CALCULADOS:\n" + _format_patterns(patterns)
    )
    if community_summaries:
        context += "\n\nRESUMOS DE COMUNIDADES:\n" + "\n".join(community_summaries)
    async with _semaphore():
        result = await report_agent().run(context, deps=GraphDeps(driver=driver, match_id=match_id))
    return result.output


async def answer_question(
    question: str,
    context_patterns: list[dict],
    extra_facts: list[str],
    driver: Driver,
    match_id: int,
) -> RespostaTatica:
    """Responde uma pergunta usando padrões recuperados + consultas read-only
    ao grafo factual (ferramenta consultar_grafo, ADR-8)."""
    context = (
        f"PERGUNTA: {question}\n"
        f"MATCH_ID DA PARTIDA: {match_id}\n\n"
        "PADRÕES TÁTICOS RELEVANTES:\n" + _format_patterns(context_patterns)
    )
    if extra_facts:
        context += "\n\nFATOS ADICIONAIS RECUPERADOS:\n" + "\n".join(f"- {f}" for f in extra_facts)
    async with _semaphore():
        result = await qa_agent().run(context, deps=GraphDeps(driver=driver, match_id=match_id))
    return result.output


def settings_fingerprint(settings: Settings) -> str:
    """Identificação do provedor ativo (para logs e docs/05-decisoes.md)."""
    return f"{settings.llm_provider}:{settings.llm_model}"

"""Agentes PydanticAI (camada 3). O LLM NUNCA calcula: lê, consulta e escreve.

- Relatório: verbalização pura dos PadraoTatico (sem ferramenta).
- Q&A: padrões pré-calculados + modo autônomo (ADR-8) — a ferramenta
  ``consultar_grafo`` executa Cypher SOMENTE-LEITURA gerado pelo modelo;
  quem agrega/conta é o Neo4j, e cada consulta fica auditável na resposta.

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
from football_graphrag.graph import db
from football_graphrag.llm.provider import pydantic_ai_model

logger = logging.getLogger(__name__)

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

GRAPH_SCHEMA = """\
SCHEMA DO GRAFO (Neo4j) — use nos MATCH exatamente estes labels/propriedades:

Nós:
- (j:Jogador {nome, player_id, time, posicao_nominal})  // time = nome da seleção, ex. 'Argentina'
- (t:Time {nome, team_id})
- (m:Partida {match_id, competicao, times})
- (z:Zona {id_zona 0-95, faixa: 'defesa'|'meio'|'ataque', corredor: 'esquerda'|'centro'|'direita'})
- (f:FaseDePosse {fase_id, match_id, team_id, minuto_inicio, minuto_fim, xt_total, n_acoes})
- (p:PadraoTatico {uid, tipo, descricao_curta, time, valor_metrica, nome_metrica, algoritmo_origem, match_id})

Arestas (TODAS carregam match_id — filtre SEMPRE por ele):
- (Jogador)-[:PASSOU_PARA {match_id, action_id, minuto, periodo, xt_gerado, vaep, progressivo, zona_origem, zona_destino, fase_posse_id}]->(Jogador)
- (Jogador)-[:FINALIZOU {match_id, minuto, periodo, tipo: 'shot'|'shot_penalty'|'shot_freekick', resultado, gol: boolean, zona}]->(Partida)
- (Jogador)-[:DEU_ASSISTENCIA {match_id, minuto, periodo}]->(Jogador)  // destino = autor do gol; UMA aresta POR GOL assistido — conte as arestas direto, NUNCA faça join com FINALIZOU (multiplica linhas)
- (Jogador)-[:PRESSIONOU {match_id, minuto, periodo, zona}]->(Jogador)
- (Jogador)-[:ATUOU_EM {match_id, contagem_acoes, xt_acumulado}]->(Zona)
- (Jogador)-[:PARTICIPOU_DE {match_id, numero_de_toques}]->(FaseDePosse)
- (Jogador)-[:MEMBRO_DE {match_id}]->(Time)
- (Zona)-[:PROGREDIU_PARA {match_id, team_id, contagem, xt_medio}]->(Zona)
- (PadraoTatico)-[:OBSERVADO_EM]->(Partida)

Convenções: minuto reinicia por periodo (1=1ºT, 2=2ºT, 3/4=prorrogação);
'gols' = FINALIZOU com gol=true; nomes de jogador são completos (use CONTAINS
para apelidos, ex. j.nome CONTAINS 'Messi'). PASSOU_PARA existe só para
passes completos com recebedor identificado.
"""

PROMPT_QA = f"""\
Você é um analista de futebol respondendo perguntas sobre uma partida. Tem
duas fontes, nesta ordem de preferência:

1. PADRÕES TÁTICOS pré-calculados por algoritmos de grafo (vêm no contexto).
   Use-os para perguntas táticas/estruturais; cite em metricas_citadas com
   padrao_tatico_id (uid), nome_metrica, valor e algoritmo_origem EXATOS.
2. A ferramenta consultar_grafo(cypher) — consultas Cypher SOMENTE-LEITURA no
   grafo factual da partida. Use-a para perguntas factuais que os padrões não
   cobrem: gols, assistências, finalizações, contagens de passes, pressões,
   zonas, duplas, fases de posse. Registre CADA consulta usada em
   consultas_executadas (cypher + resultado_resumido).

{GRAPH_SCHEMA}

Regras invioláveis:
1. TODO número e TODO fato da resposta vem de um padrão citado ou do
   resultado de uma consulta registrada. NUNCA de memória — você não sabe
   nada sobre a partida além do grafo: não acrescente placar agregado,
   disputa de pênaltis, contexto histórico nem qualquer detalhe que as
   consultas não retornaram. Se a consulta retornar vazio, diga que o grafo
   não tem o dado (confianca=baixa); não complete com conhecimento externo.
2. Filtre SEMPRE por match_id da partida em questão (vem no contexto).
3. Máximo de 4 consultas por pergunta; prefira agregações (count, sum) com
   LIMIT a listar linhas.
4. Cuidado com joins que multiplicam linhas (um MATCH extra pode duplicar a
   contagem): conte arestas diretamente e use COUNT(DISTINCT ...) quando
   juntar dois padrões de aresta. Antes de responder, cheque se o número
   faz sentido com o resultado bruto da consulta.
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


@dataclass
class QADeps:
    """Dependências do agente de Q&A: acesso somente-leitura ao grafo."""

    driver: Driver
    match_id: int


@lru_cache
def qa_agent() -> Agent:
    agent = Agent(
        pydantic_ai_model(get_settings()),
        deps_type=QADeps,
        output_type=RespostaTatica,
        system_prompt=PROMPT_QA,
        retries=2,
        model_settings=_MODEL_SETTINGS,
    )

    @agent.tool
    def consultar_grafo(ctx: RunContext[QADeps], cypher: str) -> str:
        """Executa uma consulta Cypher SOMENTE-LEITURA no grafo da partida.

        Use para fatos que os padrões táticos não cobrem: gols, assistências,
        finalizações, contagens de passes/pressões, zonas, duplas. Sempre
        filtre por match_id. Retorna as linhas em JSON (truncado em 50).
        """
        try:
            rows = db.run_readonly(ctx.deps.driver, cypher)
        except db.UnsafeCypherError as exc:
            return f"CONSULTA RECUSADA: {exc}"
        except Exception as exc:  # erro de sintaxe/execução volta para o modelo corrigir
            return f"ERRO NA CONSULTA: {exc}"
        logger.info("consultar_grafo match=%s rows=%d cypher=%s", ctx.deps.match_id, len(rows), cypher)
        return json.dumps(rows, ensure_ascii=False, default=str)

    return agent


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
        result = await qa_agent().run(context, deps=QADeps(driver=driver, match_id=match_id))
    return result.output


def settings_fingerprint(settings: Settings) -> str:
    """Identificação do provedor ativo (para logs e docs/05-decisoes.md)."""
    return f"{settings.llm_provider}:{settings.llm_model}"

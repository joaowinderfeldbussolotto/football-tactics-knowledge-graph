"""Recuperação para o Q&A (camada 3). Sem LLM nesta etapa.

Aprendizado incorporado do trabalho de Heredia (2025): quando a pergunta
nomeia uma entidade (jogador, time), filtro estruturado bate busca semântica
(100% vs 70% de acurácia de recuperação). Então a ordem é:

1. SEMPRE: resolver entidades nomeadas por identificador (Cypher CONTAINS
   sobre nomes de Jogador/Time) e recuperar, para elas, DUAS coisas:
   a. os PadraoTatico que as envolvem (camada 2);
   b. a súmula pré-agregada — EstatisticaJogador/EstatisticaTime (camada 1b).
2. COMPLEMENTO: busca híbrida do Graphiti (semântica + BM25 + travessia)
   para perguntas conceituais — apenas se houver credenciais configuradas.
3. FALLBACK: se nada foi recuperado, todos os padrões da partida (são
   dezenas, cabem no contexto) e as súmulas dos dois times.

Por que a súmula entra na recuperação
-------------------------------------
Antes, o contexto recuperado era só PadraoTatico. Numa pergunta factual
("quem fez mais desarmes?") isso devolvia padrões que não têm nada a ver, e
o agente precisava escrever Cypher para tudo. Duas consequências ruins:

- gasto de uma ida e volta de ferramenta para um dado que já está calculado;
- o juiz de recuperação da avaliação pontua o CONTEXTO, e um contexto sem a
  resposta tirava nota baixa mesmo quando a resposta final saía correta.

Com a súmula no contexto, a pergunta factual costuma ser respondida sem
nenhuma consulta, e a nota de recuperação passa a medir o que deveria.
"""

import logging
import re
import time
import unicodedata

from neo4j import Driver

logger = logging.getLogger(__name__)

STOPWORDS = {
    "de", "da", "do", "das", "dos", "o", "a", "os", "as", "um", "uma", "que", "qual",
    "quais", "quem", "como", "onde", "quando", "por", "para", "com", "sem", "e", "ou",
    "foi", "era", "time", "jogador", "partida", "jogo", "contra", "entre", "mais",
    "menos", "pressão", "pressao", "passe", "passes", "gol", "gols",
}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def extract_candidate_names(question: str) -> list[str]:
    """Tokens capitalizáveis da pergunta que podem ser nomes próprios."""
    tokens = re.findall(r"[A-Za-zÀ-ÿ]{3,}", question)
    return [t for t in tokens if _normalize(t) not in STOPWORDS]


def fetch_all_patterns(driver: Driver, match_id: int) -> list[dict]:
    with driver.session() as session:
        return [dict(p) for p in session.run(
            "MATCH (p:PadraoTatico {match_id: $m}) RETURN p ORDER BY p.tipo", m=match_id
        ).value()]


def resolve_entities(driver: Driver, question: str) -> list[str]:
    """Nomes de Jogador/Time efetivamente citados na pergunta."""
    names = extract_candidate_names(question)
    if not names:
        return []
    with driver.session() as session:
        return session.run(
            """UNWIND $names AS name
               MATCH (n) WHERE (n:Jogador OR n:Time)
                 AND toLower(n.nome) CONTAINS toLower(name)
               RETURN DISTINCT n.nome AS nome""",
            names=names,
        ).value()


def patterns_for_entities(driver: Driver, match_id: int, entities: list[str]) -> list[dict]:
    """Padrões da camada 2 que envolvem as entidades citadas."""
    if not entities:
        return []
    with driver.session() as session:
        patterns = session.run(
            """MATCH (p:PadraoTatico {match_id: $m})
               WHERE any(e IN $entities WHERE
                     e IN coalesce(p.jogadores_envolvidos, [])
                     OR p.time = e
                     OR p.descricao_curta CONTAINS e)
               RETURN p ORDER BY p.tipo""",
            m=match_id,
            entities=entities,
        ).value()
    return [dict(p) for p in patterns]


def stats_for_entities(driver: Driver, match_id: int, entities: list[str]) -> list[dict]:
    """Súmulas (camada 1b) dos jogadores e times citados na pergunta.

    Sem entidade citada, devolve as súmulas dos DOIS times: são duas linhas,
    cabem sempre no contexto, e cobrem as perguntas de placar/posse/pressão
    sem custar consulta.
    """
    with driver.session() as session:
        if entities:
            jogadores = session.run(
                """MATCH (e:EstatisticaJogador {match_id: $m})
                   WHERE e.nome IN $entities OR e.time IN $entities
                   RETURN properties(e) AS p ORDER BY e.toques DESC LIMIT 15""",
                m=match_id,
                entities=entities,
            ).value()
        else:
            jogadores = []
        times = session.run(
            """MATCH (e:EstatisticaTime {match_id: $m})
               RETURN properties(e) AS p ORDER BY e.nome""",
            m=match_id,
        ).value()
    return [_limpa(p) for p in list(times) + list(jogadores)]


def _limpa(props: dict) -> dict:
    """Tira chaves internas antes de mandar para o contexto do modelo."""
    return {k: v for k, v in props.items() if k not in ("uid", "player_id", "team_id")}


def structured_retrieval(driver: Driver, match_id: int, question: str) -> list[dict]:
    """Compatibilidade: só os padrões, como antes."""
    return patterns_for_entities(driver, match_id, resolve_entities(driver, question))


async def retrieve_context(
    driver: Driver, match_id: int, question: str, graphiti=None
) -> tuple[list[dict], list[dict], list[str], dict]:
    """Recuperação completa para o Q&A.

    Retorna (padrões, súmulas, fatos_extra, timings).
    """
    t0 = time.perf_counter()
    entities = resolve_entities(driver, question)
    patterns = patterns_for_entities(driver, match_id, entities)
    stats = stats_for_entities(driver, match_id, entities)
    used = "estruturada+sumula"
    extra_facts: list[str] = []
    if graphiti is not None:
        from football_graphrag.graph.communities import hybrid_search

        try:
            extra_facts = await hybrid_search(graphiti, match_id, question)
            used += "+hibrida_graphiti"
        except Exception:
            logger.exception("busca híbrida indisponível; seguindo só com a estruturada")
    if not patterns:
        patterns = fetch_all_patterns(driver, match_id)
        used += "+fallback_todos_padroes"
    timings = {"retrieval_seconds": round(time.perf_counter() - t0, 4), "estrategia": used}
    return patterns, stats, extra_facts, timings

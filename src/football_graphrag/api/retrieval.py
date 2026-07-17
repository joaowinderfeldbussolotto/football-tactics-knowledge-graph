"""Recuperação para o Q&A (camada 3). Sem LLM nesta etapa.

Aprendizado incorporado do trabalho de Heredia (2025): quando a pergunta
nomeia uma entidade (jogador, time), filtro estruturado bate busca semântica
(100% vs 70% de acurácia de recuperação). Então a ordem é:

1. SEMPRE: resolver entidades nomeadas por identificador (Cypher CONTAINS
   sobre nomes de Jogador/Time) e recuperar os PadraoTatico que as envolvem.
2. COMPLEMENTO: busca híbrida do Graphiti (semântica + BM25 + travessia)
   para perguntas conceituais — apenas se houver credenciais configuradas.
3. FALLBACK: se nada foi recuperado, todos os padrões da partida (são
   dezenas, cabem no contexto).
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


def structured_retrieval(driver: Driver, match_id: int, question: str) -> list[dict]:
    """Filtro estruturado: padrões que envolvem entidades nomeadas na pergunta."""
    names = extract_candidate_names(question)
    if not names:
        return []
    with driver.session() as session:
        entities = session.run(
            """UNWIND $names AS name
               MATCH (n) WHERE (n:Jogador OR n:Time)
                 AND toLower(n.nome) CONTAINS toLower(name)
               RETURN DISTINCT n.nome AS nome""",
            names=names,
        ).value()
        if not entities:
            return []
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


async def retrieve_context(driver: Driver, match_id: int, question: str, graphiti=None) -> tuple[list[dict], list[str], dict]:
    """Recuperação completa para o Q&A. Retorna (padrões, fatos_extra, timings)."""
    t0 = time.perf_counter()
    patterns = structured_retrieval(driver, match_id, question)
    used = "estruturada"
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
    return patterns, extra_facts, timings

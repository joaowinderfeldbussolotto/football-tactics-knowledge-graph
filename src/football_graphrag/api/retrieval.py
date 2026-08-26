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

A súmula no contexto é CONDIÇÃO EXPERIMENTAL, não decisão fechada
----------------------------------------------------------------
Entregar a súmula pronta faz a pergunta factual ser respondida sem nenhuma
consulta — o que economiza uma ida e volta de ferramenta, mas cala
exatamente o mecanismo que o ADR-8 (text-to-Cypher autônomo) existe para
demonstrar. Ou seja: ganha em eficiência e perde em evidência.

Como não dá para decidir isso no olho, ``incluir_sumula`` existe para que a
avaliação rode os DOIS braços na mesma rodada e com o mesmo modelo — ver
ADR-10 em ``docs/05-decisoes.md`` e a seção de ablação em
``docs/07-validacao.md``. O default é ``True`` (o comportamento da API);
o braço de controle é quem passa ``False``.
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


# Intenção da pergunta: gatilhos determinísticos, sem LLM na recuperação.
# Existe porque resolve_entities só enxerga NOME PRÓPRIO. "Quem fez os gols da
# final?" não cita jogador nem time, resolvia zero entidades, e a recuperação
# entregava só a súmula dos dois times — que tem o TOTAL de gols, não quem fez.
# O baseline vetorial, esse, tinha a linha dos gols pronta no resumo
# (evaluation/match_facts.py). A paridade de fatos que a ADR-10 exige estava
# quebrada para o lado do grafo.
INTENCOES: dict[str, set[str]] = {
    "gols": {"gol", "gols", "marcou", "marcaram", "marcados", "placar", "artilheiro",
             "empatou", "empate", "abriu", "virada", "virou"},
    "assistencias": {"assistencia", "assistencias", "assistiu", "assistiram", "assistente"},
    "cartoes": {"cartao", "cartoes", "amarelo", "amarelos", "advertido", "advertidos",
                "advertencia"},
}

# As mesmas arestas que uma consulta ad-hoc percorreria — nada pré-calculado
# aqui, ao contrário da súmula da camada 1b.
_FICHA_CYPHER = {
    "gols": """
        MATCH (j:Jogador)-[f:FINALIZOU {match_id: $m}]->(:Partida)
        WHERE f.gol
        RETURN j.nome AS jogador, j.time AS time, f.minuto AS minuto,
               f.periodo_nome AS periodo, f.acao AS acao
        ORDER BY f.periodo, f.minuto
    """,
    "assistencias": """
        MATCH (a:Jogador)-[d:DEU_ASSISTENCIA {match_id: $m}]->(g:Jogador)
        RETURN a.nome AS jogador, a.time AS time, g.nome AS para,
               d.minuto AS minuto, d.periodo_nome AS periodo
        ORDER BY d.periodo, d.minuto
    """,
    "cartoes": """
        MATCH (j:Jogador)-[r:REALIZOU {match_id: $m}]->(:Partida)
        WHERE r.cartao_amarelo
        RETURN j.nome AS jogador, j.time AS time, r.minuto AS minuto,
               r.periodo_nome AS periodo
        ORDER BY r.periodo, r.minuto
    """,
}


def detectar_intencoes(question: str) -> set[str]:
    """Que fatos de súmula a pergunta pede, pelo vocabulário que ela usa."""
    tokens = set(re.findall(r"[a-z]+", _normalize(question)))
    return {nome for nome, gatilhos in INTENCOES.items() if tokens & gatilhos}


def ficha_do_jogo(driver: Driver, match_id: int, intencoes: set[str]) -> list[str]:
    """Gols, assistências e cartões — só o que a pergunta pediu.

    Devolve frases prontas, no mesmo formato do resumo que o baseline recebe,
    para que a comparação seja de REPRESENTAÇÃO e não de quem tem o dado.
    """
    if not intencoes:
        return []
    fatos: list[str] = []
    with driver.session() as session:
        for chave in sorted(intencoes):
            linhas = session.run(_FICHA_CYPHER[chave], m=match_id).data()
            if not linhas:
                continue
            if chave == "gols":
                itens = [
                    f"{r['jogador']} ({r['time']}) aos {r['minuto']} min do {r['periodo']}"
                    + (" de pênalti" if r["acao"] == "penalti" else "")
                    for r in linhas
                ]
                fatos.append(f"Gols da partida ({len(itens)}): " + "; ".join(itens) + ".")
            elif chave == "assistencias":
                itens = [
                    f"{r['jogador']} ({r['time']}) para {r['para']} aos {r['minuto']} min"
                    for r in linhas
                ]
                fatos.append("Assistências: " + "; ".join(itens) + ".")
            else:
                itens = [f"{r['jogador']} ({r['time']}) aos {r['minuto']} min" for r in linhas]
                fatos.append("Cartões amarelos: " + "; ".join(itens) + ".")
    return fatos


def padroes_relevantes(driver: Driver, match_id: int, question: str, limite: int = 8) -> list[dict]:
    """Fallback com pontaria: os padrões que casam lexicalmente com a pergunta.

    O fallback antigo despejava TODOS os padrões da partida (~24). Isso diluía
    o contexto e, medido, era o que mais pesava no custo por pergunta. Quando
    não há casamento lexical nenhum, devolve tudo como antes — não se remove
    informação sem ter um motivo para removê-la.
    """
    todos = fetch_all_patterns(driver, match_id)
    termos = {_normalize(t) for t in extract_candidate_names(question)}

    def pontos(p: dict) -> int:
        texto = _normalize(
            " ".join(str(p.get(k, "")) for k in ("tipo", "descricao_curta", "time", "nome_metrica"))
        )
        return sum(1 for t in termos if t in texto)

    marcados = [(pontos(p), p) for p in todos]
    if not any(n for n, _ in marcados):
        return todos
    return [p for n, p in sorted(marcados, key=lambda x: -x[0]) if n][:limite]


def structured_retrieval(driver: Driver, match_id: int, question: str) -> list[dict]:
    """Compatibilidade: só os padrões, como antes."""
    return patterns_for_entities(driver, match_id, resolve_entities(driver, question))


async def retrieve_context(
    driver: Driver, match_id: int, question: str, graphiti=None, incluir_sumula: bool = True
) -> tuple[list[dict], list[dict], list[str], dict]:
    """Recuperação completa para o Q&A.

    Retorna (padrões, súmulas, fatos_extra, timings).

    ``incluir_sumula=False`` devolve a lista de súmulas vazia — o braço de
    controle da ablação, em que o agente só chega aos números factuais
    escrevendo Cypher. Ver a docstring do módulo.
    """
    t0 = time.perf_counter()
    entities = resolve_entities(driver, question)
    intencoes = detectar_intencoes(question)
    patterns = patterns_for_entities(driver, match_id, entities)
    stats = stats_for_entities(driver, match_id, entities) if incluir_sumula else []
    extra_facts = ficha_do_jogo(driver, match_id, intencoes)
    used = "estruturada+sumula" if incluir_sumula else "estruturada"
    if extra_facts:
        used += "+ficha(" + ",".join(sorted(intencoes)) + ")"
    if graphiti is not None:
        from football_graphrag.graph.communities import hybrid_search

        try:
            extra_facts = extra_facts + await hybrid_search(graphiti, match_id, question)
            used += "+hibrida_graphiti"
        except Exception:
            logger.exception("busca híbrida indisponível; seguindo só com a estruturada")
    # Só cai no fallback quando nada mais foi recuperado: numa pergunta de
    # ficha ("quem fez os gols"), padrão tático é ruído puro.
    if not patterns and not extra_facts:
        patterns = padroes_relevantes(driver, match_id, question)
        used += "+fallback_padroes"
    timings = {"retrieval_seconds": round(time.perf_counter() - t0, 4), "estrategia": used}
    return patterns, stats, extra_facts, timings

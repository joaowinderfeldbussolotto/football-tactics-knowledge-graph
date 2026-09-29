"""CAMADA 1b: súmula pré-agregada. Determinística, sem LLM.

Por que este módulo existe
--------------------------
Antes dele, "quem fez mais desarmes na final?" obrigava quem consulta a
escrever uma agregação e a acertar DUAS decisões que o dado não explicitava:
filtrar o tipo de ação certo e decidir se "desarme" é tentativa ou acerto. Na
avaliação real o modelo errou: respondeu 9 (tentativas do Enzo) quando a
resposta é 5 (desarmes certos). Não foi falta de instrução no prompt — foi o
dado exigir uma decisão que ele não ajudava a tomar.

Aqui essa decisão é tomada UMA vez, por código determinístico, e vira
propriedade nomeada: ``desarmes_certos`` e ``desarmes_tentados`` são campos
distintos, e não há como confundi-los. A pergunta vira uma consulta de um
hop, sem agregação e sem conhecimento prévio:

    MATCH (e:EstatisticaJogador {match_id: 3869685})
    RETURN e.nome, e.desarmes_certos ORDER BY e.desarmes_certos DESC LIMIT 3

Por que agregar em Cypher e não em pandas
------------------------------------------
As contagens são feitas pelo PRÓPRIO Neo4j, sobre as MESMAS arestas que uma
consulta ad-hoc percorreria. Se fossem calculadas em pandas, uma diferença
sutil de filtro faria a súmula discordar de uma contagem manual sobre o
grafo — que é o pior resultado possível: duas respostas certas e
incompatíveis. Aqui isso é impossível por construção.

Isto não viola o contrato "nada é calculado depois da camada 0": nenhuma
métrica nova nasce aqui. São contagens de linhas que já existem — exatamente
o que o agente faria, feito uma vez e conferido.
"""

import logging

from neo4j import Driver

from football_graphrag.graph import db
from football_graphrag.graph.entities import uid_for

logger = logging.getLogger(__name__)

# Contagens por jogador, direto das arestas REALIZOU. Cada linha é uma
# definição fechada: o nome do campo diz exatamente o que ele conta.
_AGG_JOGADOR = """
MATCH (j:Jogador)-[r:REALIZOU {match_id: $m}]->(:Partida)
WITH j,
  count(r)                                                                       AS toques,
  sum(CASE WHEN r.grupo_acao IN ['passe','bola_parada']                THEN 1 ELSE 0 END) AS passes_tentados,
  sum(CASE WHEN r.grupo_acao IN ['passe','bola_parada'] AND r.sucesso  THEN 1 ELSE 0 END) AS passes_certos,
  sum(CASE WHEN r.grupo_acao IN ['passe','bola_parada'] AND r.progressivo
                                                       AND r.sucesso  THEN 1 ELSE 0 END) AS passes_progressivos,
  sum(CASE WHEN r.acao = 'cruzamento'                                  THEN 1 ELSE 0 END) AS cruzamentos_tentados,
  sum(CASE WHEN r.acao = 'cruzamento'          AND r.sucesso           THEN 1 ELSE 0 END) AS cruzamentos_certos,
  sum(CASE WHEN r.acao = 'conducao'                                    THEN 1 ELSE 0 END) AS conducoes,
  sum(CASE WHEN r.acao = 'drible'                                      THEN 1 ELSE 0 END) AS dribles_tentados,
  sum(CASE WHEN r.acao = 'drible'              AND r.sucesso           THEN 1 ELSE 0 END) AS dribles_certos,
  sum(CASE WHEN r.acao = 'desarme'                                     THEN 1 ELSE 0 END) AS desarmes_tentados,
  sum(CASE WHEN r.acao = 'desarme'             AND r.sucesso           THEN 1 ELSE 0 END) AS desarmes_certos,
  sum(CASE WHEN r.acao = 'interceptacao'       AND r.sucesso           THEN 1 ELSE 0 END) AS interceptacoes,
  sum(CASE WHEN r.acao = 'corte'                                       THEN 1 ELSE 0 END) AS cortes,
  sum(CASE WHEN r.acao = 'falta_cometida'                              THEN 1 ELSE 0 END) AS faltas_cometidas,
  sum(CASE WHEN r.cartao_amarelo                                       THEN 1 ELSE 0 END) AS cartoes_amarelos,
  sum(CASE WHEN r.grupo_acao = 'finalizacao'                           THEN 1 ELSE 0 END) AS finalizacoes,
  sum(CASE WHEN r.grupo_acao = 'finalizacao'   AND r.no_gol            THEN 1 ELSE 0 END) AS finalizacoes_no_gol,
  sum(CASE WHEN r.gol                                                  THEN 1 ELSE 0 END) AS gols,
  sum(CASE WHEN r.acao = 'penalti'             AND r.gol               THEN 1 ELSE 0 END) AS gols_de_penalti,
  sum(CASE WHEN r.acao = 'defesa_do_goleiro'                           THEN 1 ELSE 0 END) AS defesas_do_goleiro,
  sum(CASE WHEN r.acao = 'erro_de_dominio'                             THEN 1 ELSE 0 END) AS erros_de_dominio,
  sum(r.xt_gerado)                                                                 AS xt_total,
  sum(r.vaep)                                                                      AS vaep_total
RETURN j.player_id AS player_id, j.nome AS nome, j.time AS time,
       j.posicao_nominal AS posicao, toques, passes_tentados, passes_certos,
       passes_progressivos, cruzamentos_tentados, cruzamentos_certos, conducoes,
       dribles_tentados, dribles_certos, desarmes_tentados, desarmes_certos,
       interceptacoes, cortes, faltas_cometidas, cartoes_amarelos, finalizacoes,
       finalizacoes_no_gol, gols, gols_de_penalti, defesas_do_goleiro,
       erros_de_dominio, xt_total, vaep_total
"""

_AGG_ASSISTENCIAS = """
MATCH (j:Jogador)-[a:DEU_ASSISTENCIA {match_id: $m}]->(:Jogador)
RETURN j.player_id AS player_id, count(a) AS assistencias
"""

# Pressões exercidas e sofridas: vêm da rede de pressão, não do log de ações.
_AGG_PRESSOES = """
MATCH (j:Jogador)
OPTIONAL MATCH (j)-[fez:PRESSIONOU {match_id: $m}]->(:Jogador)
OPTIONAL MATCH (:Jogador)-[sofreu:PRESSIONOU {match_id: $m}]->(j)
WITH j, count(DISTINCT fez) AS pressoes_feitas, count(DISTINCT sofreu) AS pressoes_sofridas
WHERE pressoes_feitas > 0 OR pressoes_sofridas > 0
RETURN j.player_id AS player_id, pressoes_feitas, pressoes_sofridas
"""


def build_player_stats(driver: Driver, match_id: int) -> int:
    """Cria um nó EstatisticaJogador por jogador que agiu na partida.

    Saída:
        número de nós escritos. Idempotente (uid determinístico + MERGE).
    """
    with db.session_scope(driver) as session:
        base = session.run(_AGG_JOGADOR, m=match_id).data()
        assists = {r["player_id"]: r["assistencias"] for r in session.run(_AGG_ASSISTENCIAS, m=match_id).data()}
        pressures = {r["player_id"]: r for r in session.run(_AGG_PRESSOES, m=match_id).data()}

    rows = []
    for r in base:
        pid = r["player_id"]
        pressao = pressures.get(pid, {})
        stats = dict(r)
        stats.pop("player_id")
        stats.update(
            {
                "uid": uid_for("estatistica_jogador", match_id, pid),
                "match_id": match_id,
                "player_id": pid,
                "assistencias": assists.get(pid, 0),
                "pressoes_feitas": pressao.get("pressoes_feitas", 0),
                "pressoes_sofridas": pressao.get("pressoes_sofridas", 0),
                # arredondado: xT/VAEP são probabilidades, 4 casas bastam e
                # evitam ruído de ponto flutuante na resposta do agente.
                "xt_total": round(float(r["xt_total"] or 0.0), 4),
                "vaep_total": round(float(r["vaep_total"] or 0.0), 4),
                "precisao_passe_pct": (
                    round(100.0 * r["passes_certos"] / r["passes_tentados"], 1)
                    if r["passes_tentados"]
                    else None
                ),
            }
        )
        rows.append(stats)

    written = db.run_batched(
        driver,
        """UNWIND $rows AS r
           MERGE (e:EstatisticaJogador {uid: r.uid})
           SET e += r
           WITH e, r
           MATCH (j:Jogador {player_id: r.player_id})
           MERGE (j)-[:TEM_ESTATISTICA]->(e)""",
        rows,
    )
    logger.info("estatísticas de jogador %s: %d nós", match_id, written)
    return written


_AGG_TIME = """
MATCH (j:Jogador {time: $time})-[r:REALIZOU {match_id: $m}]->(:Partida)
WITH count(r)                                                                       AS acoes,
  sum(CASE WHEN r.grupo_acao IN ['passe','bola_parada']                THEN 1 ELSE 0 END) AS passes_tentados,
  sum(CASE WHEN r.grupo_acao IN ['passe','bola_parada'] AND r.sucesso  THEN 1 ELSE 0 END) AS passes_certos,
  sum(CASE WHEN r.grupo_acao = 'finalizacao'                           THEN 1 ELSE 0 END) AS finalizacoes,
  sum(CASE WHEN r.grupo_acao = 'finalizacao'   AND r.no_gol            THEN 1 ELSE 0 END) AS finalizacoes_no_gol,
  sum(CASE WHEN r.gol                                                  THEN 1 ELSE 0 END) AS gols,
  sum(CASE WHEN r.acao = 'desarme'             AND r.sucesso           THEN 1 ELSE 0 END) AS desarmes_certos,
  sum(CASE WHEN r.acao = 'interceptacao'       AND r.sucesso           THEN 1 ELSE 0 END) AS interceptacoes,
  sum(CASE WHEN r.acao = 'drible'              AND r.sucesso           THEN 1 ELSE 0 END) AS dribles_certos,
  sum(CASE WHEN r.acao = 'falta_cometida'                              THEN 1 ELSE 0 END) AS faltas_cometidas,
  sum(CASE WHEN r.cartao_amarelo                                       THEN 1 ELSE 0 END) AS cartoes_amarelos,
  sum(CASE WHEN r.terco = 'ataque'                                     THEN 1 ELSE 0 END) AS acoes_no_terco_final,
  sum(r.xt_gerado)                                                                  AS xt_total
RETURN acoes, passes_tentados, passes_certos, finalizacoes, finalizacoes_no_gol,
       gols, desarmes_certos, interceptacoes, dribles_certos, faltas_cometidas,
       cartoes_amarelos, acoes_no_terco_final, xt_total
"""

# Posse de bola por TEMPO: soma da duração das fases de posse de cada time,
# dividida pelo total. É a definição usada nas transmissões, e não uma
# proporção de eventos (que superestima quem toca muito na bola).
_AGG_POSSE = """
MATCH (f:FaseDePosse {match_id: $m})
WITH f.team_id AS team_id, sum(f.minuto_fim - f.minuto_inicio) AS minutos
WITH collect({team_id: team_id, minutos: minutos}) AS partes,
     sum(minutos) AS total
UNWIND partes AS p
RETURN p.team_id AS team_id,
       CASE WHEN total > 0 THEN round(100.0 * p.minutos / total, 1) ELSE null END AS posse_pct
"""


def build_team_stats(driver: Driver, match_id: int, team_metrics: dict | None = None) -> int:
    """Cria um nó EstatisticaTime por time da partida.

    Entrada:
        team_metrics: bloco ``team_metrics`` do ``{match_id}_meta.json``
        (PPDA por tempo e field tilt, calculados na camada 0). Opcional —
        sem ele os campos ficam nulos em vez de inventados.
    """
    with db.session_scope(driver) as session:
        partida = session.run(
            "MATCH (p:Partida {match_id: $m}) RETURN p.times AS times", m=match_id
        ).single()
        times = partida["times"] if partida else []
        posse = {r["team_id"]: r["posse_pct"] for r in session.run(_AGG_POSSE, m=match_id).data()}
        ids = {
            r["nome"]: r["team_id"]
            for r in session.run("MATCH (t:Time) RETURN t.nome AS nome, t.team_id AS team_id").data()
        }

        rows = []
        for nome in times:
            team_id = ids.get(nome)
            agg = session.run(_AGG_TIME, m=match_id, time=nome).single()
            if agg is None:
                continue
            metrics = (team_metrics or {}).get(str(team_id), (team_metrics or {}).get(team_id, {}))
            stats = dict(agg)
            stats.update(
                {
                    "uid": uid_for("estatistica_time", match_id, team_id),
                    "match_id": match_id,
                    "team_id": team_id,
                    "nome": nome,
                    "posse_pct": posse.get(team_id),
                    "xt_total": round(float(agg["xt_total"] or 0.0), 4),
                    "precisao_passe_pct": (
                        round(100.0 * agg["passes_certos"] / agg["passes_tentados"], 1)
                        if agg["passes_tentados"]
                        else None
                    ),
                    "ppda_1o_tempo": _finite(metrics.get("ppda_p1")),
                    "ppda_2o_tempo": _finite(metrics.get("ppda_p2")),
                    "field_tilt_pct": _pct(metrics.get("field_tilt")),
                }
            )
            rows.append(stats)

    written = db.run_batched(
        driver,
        """UNWIND $rows AS r
           MERGE (e:EstatisticaTime {uid: r.uid})
           SET e += r
           WITH e, r
           MATCH (t:Time {team_id: r.team_id})
           MERGE (t)-[:TEM_ESTATISTICA]->(e)""",
        rows,
    )
    logger.info("estatísticas de time %s: %d nós", match_id, written)
    return written


def _finite(value) -> float | None:
    """NaN vira null explícito: ausência de dado não é zero."""
    if value is None:
        return None
    value = float(value)
    return None if value != value else round(value, 2)


def _pct(value) -> float | None:
    value = _finite(value)
    return None if value is None else round(value * 100.0, 1)

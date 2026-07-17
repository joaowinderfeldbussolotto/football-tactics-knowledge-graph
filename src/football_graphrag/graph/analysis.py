"""CAMADA 2: análise estrutural. AQUI NASCEM OS INSIGHTS. Sem LLM.

Cada função recebe um match_id, roda procedures do GDS (ou Cypher puro) e
grava o resultado DE VOLTA no grafo como nós ``PadraoTatico`` — a camada 3
recupera padrões já calculados, e a checagem de fidelidade (evaluation/
faithfulness.py) tem contra o que comparar.

``algoritmo_origem`` é obrigatório em todo padrão: rastreabilidade de qual
procedure produziu o quê. Catálogo completo com exemplos reais em
docs/03-insights.md.
"""

import json
import logging
from pathlib import Path

import pandas as pd
from neo4j import Driver

from football_graphrag.graph import projections
from football_graphrag.graph.entities import PadraoTatico
from football_graphrag.ingestion.tactical_metrics import GRID_ROWS, zone_band, zone_channel

logger = logging.getLogger(__name__)

# Linha tática nominal por posição StatsBomb (para o insight 7.5).
POSITION_LINES = {
    "Goalkeeper": "gol",
    "Back": "defesa",
    "Midfield": "meio",
    "Wing": "ataque",
    "Forward": "ataque",
    "Striker": "ataque",
    "Attacking Midfield": "ataque",
}


def nominal_line(position: str | None) -> str | None:
    """Linha (defesa/meio/ataque) a partir do nome da posição StatsBomb."""
    if not position or position == "Substitute":
        return None
    if "Goalkeeper" in position:
        return "gol"
    if "Attacking Midfield" in position or "Wing" in position and "Back" not in position:
        return "ataque"
    if "Back" in position or "Wing Back" in position:
        return "defesa"
    if "Midfield" in position:
        return "meio"
    return "ataque"  # Center Forward, Striker, Second Striker...


def save_pattern(driver: Driver, pattern: PadraoTatico) -> None:
    """MERGE idempotente do PadraoTatico no grafo."""
    props = pattern.model_dump()
    with driver.session() as session:
        session.run(
            """MERGE (p:PadraoTatico {uid: $uid}) SET p += $props
               WITH p MATCH (m:Partida {match_id: $match_id}) MERGE (p)-[:OBSERVADO_EM]->(m)""",
            uid=pattern.uid,
            props=props,
            match_id=pattern.match_id,
        ).consume()


def teams_of_match(driver: Driver, match_id: int) -> list[str]:
    with driver.session() as session:
        rec = session.run("MATCH (p:Partida {match_id: $m}) RETURN p.times AS times", m=match_id).single()
    return rec["times"]


# ---------------------------------------------------------------------------
# 7.1 O pivô invisível (betweenness centrality)
# ---------------------------------------------------------------------------

def pivo_estrutural(driver: Driver, match_id: int) -> list[PadraoTatico]:
    """Insight 7.1: qual jogador é o gargalo estrutural da progressão?

    Algoritmo: gds.betweenness.stream sobre a rede de passes do time,
    direcionada, com custo 1/(1+xT) (conexões de maior ameaça = caminhos
    mais curtos). PageRank calculado junto como contraste (mostra que
    betweenness != volume != prestígio de rede).
    """
    patterns = []
    for team in teams_of_match(driver, match_id):
        with projections.pass_network(driver, match_id, team) as graph_name:
            with driver.session() as session:
                rows = session.run(
                    """CALL gds.betweenness.stream($g, {relationshipWeightProperty: 'cost'})
                       YIELD nodeId, score
                       WITH gds.util.asNode(nodeId) AS j, score
                       RETURN j.nome AS nome, j.uid AS uid, score ORDER BY score DESC""",
                    g=graph_name,
                ).data()
                pagerank = {
                    r["nome"]: r["score"]
                    for r in session.run(
                        """CALL gds.pageRank.stream($g, {relationshipWeightProperty: 'n_passes'})
                           YIELD nodeId, score RETURN gds.util.asNode(nodeId).nome AS nome, score""",
                        g=graph_name,
                    ).data()
                }
                touches = {
                    r["nome"]: r["n"]
                    for r in session.run(
                        """MATCH (j:Jogador {time: $team})-[a:ATUOU_EM {match_id: $m}]->()
                           RETURN j.nome AS nome, sum(a.contagem_acoes) AS n""",
                        team=team,
                        m=match_id,
                    ).data()
                }
        if not rows or rows[0]["score"] <= 0:
            continue
        top = rows[0]
        second_score = rows[1]["score"] if len(rows) > 1 else 0.0
        pattern = PadraoTatico.make(
            tipo="pivo_estrutural",
            match_id=match_id,
            time=team,
            chave_extra=top["nome"],
            descricao_curta=(
                f"{top['nome']} é o gargalo estrutural da progressão de {team}: "
                f"betweenness {top['score']:.1f} (2º colocado: {second_score:.1f}), "
                f"com {touches.get(top['nome'], 0)} ações e pageRank {pagerank.get(top['nome'], 0):.3f}"
            ),
            valor_metrica=float(top["score"]),
            nome_metrica="betweenness_centrality",
            algoritmo_origem="gds.betweenness.stream",
            jogadores_envolvidos=[top["nome"]],
        )
        save_pattern(driver, pattern)
        patterns.append(pattern)
    return patterns


# ---------------------------------------------------------------------------
# 7.2 Padrão do terceiro homem (caminho multi-hop)
# ---------------------------------------------------------------------------

def terceiro_homem(driver: Driver, match_id: int, min_occurrences: int = 2) -> list[PadraoTatico]:
    """Insight 7.2: combinações A->B->C recorrentes que progridem de faixa.

    Algoritmo: Cypher puro — caminho de 2 arestas PASSOU_PARA na MESMA fase
    de posse, quase consecutivas (diferença de até 3 action_ids, tolerando
    uma condução no meio), exigindo que a faixa da zona final seja mais
    avançada que a da zona inicial. Conta recorrência por trio ordenado.
    """
    query = """
    MATCH (a:Jogador)-[p1:PASSOU_PARA {match_id: $m}]->(b:Jogador)-[p2:PASSOU_PARA {match_id: $m}]->(c:Jogador)
    WHERE p1.fase_posse_id = p2.fase_posse_id
      AND p2.action_id > p1.action_id AND p2.action_id - p1.action_id <= 3
      AND a <> b AND b <> c AND a <> c
      AND (p2.zona_destino / 8) / 4 > (p1.zona_origem / 8) / 4
    RETURN a.nome AS a, b.nome AS b, c.nome AS c, a.time AS team,
           count(*) AS n, sum(p1.xt_gerado + p2.xt_gerado) AS xt_total
    ORDER BY n DESC, xt_total DESC
    """
    patterns = []
    with driver.session() as session:
        rows = session.run(query, m=match_id).data()
    by_team: dict[str, list] = {}
    for r in rows:
        if r["n"] >= min_occurrences:
            by_team.setdefault(r["team"], []).append(r)
    for team, combos in by_team.items():
        for combo in combos[:3]:  # até 3 trios por time
            pattern = PadraoTatico.make(
                tipo="terceiro_homem",
                match_id=match_id,
                time=team,
                chave_extra=f"{combo['a']}|{combo['b']}|{combo['c']}",
                descricao_curta=(
                    f"Trio recorrente de quebra de linha de {team}: {combo['a']} -> "
                    f"{combo['b']} -> {combo['c']} ({combo['n']}x, xT acumulado {combo['xt_total']:.3f})"
                ),
                valor_metrica=float(combo["n"]),
                nome_metrica="ocorrencias_trio_progressivo",
                algoritmo_origem="cypher.path_pattern",
                jogadores_envolvidos=[combo["a"], combo["b"], combo["c"]],
            )
            save_pattern(driver, pattern)
            patterns.append(pattern)
    return patterns


# ---------------------------------------------------------------------------
# 7.3 Gatilho de pressão (co-ocorrência temporal)
# ---------------------------------------------------------------------------

def gatilho_pressao(driver: Driver, match_id: int, window_seconds: float = 8.0, min_triggers: int = 5) -> list[PadraoTatico]:
    """Insight 7.3: o que dispara a pressão do adversário?

    Algoritmo: Cypher com janela temporal — para cada PRESSIONOU, o
    PASSOU_PARA do time pressionado imediatamente anterior (mesmo período,
    até ``window_seconds`` antes); agrega por (faixa, corredor) da zona de
    destino do passe. Taxa de disparo = pressões disparadas / passes para a
    região.
    """
    query = """
    MATCH (presser:Jogador)-[pr:PRESSIONOU {match_id: $m}]->(alvo:Jogador)
    MATCH (:Jogador)-[p:PASSOU_PARA {match_id: $m}]->(recebedor:Jogador)
    WHERE recebedor.time = alvo.time AND p.periodo = pr.periodo
      AND p.minuto <= pr.minuto AND pr.minuto - p.minuto <= $w / 60.0
    WITH presser.time AS pressing_team, pr, p, recebedor
    ORDER BY p.minuto DESC
    WITH pressing_team, pr, head(collect({zona: p.zona_destino, recebedor: recebedor.nome})) AS gatilho
    RETURN pressing_team, gatilho.zona AS zona, count(*) AS n_disparos
    ORDER BY n_disparos DESC
    """
    passes_by_zone_query = """
    MATCH (:Jogador)-[p:PASSOU_PARA {match_id: $m}]->(r:Jogador)
    WHERE r.time = $target_team
    RETURN p.zona_destino AS zona, count(*) AS n
    """
    patterns = []
    with driver.session() as session:
        rows = session.run(query, m=match_id, w=window_seconds).data()
        teams = teams_of_match(driver, match_id)
        for pressing_team in {r["pressing_team"] for r in rows}:
            target_team = next(t for t in teams if t != pressing_team)
            zone_passes = {
                r["zona"]: r["n"]
                for r in session.run(passes_by_zone_query, m=match_id, target_team=target_team).data()
            }
            # agrega zonas por (faixa, corredor) da perspectiva do pressionado
            region: dict[tuple[str, str], dict] = {}
            for r in rows:
                if r["pressing_team"] != pressing_team or r["zona"] is None:
                    continue
                key = (zone_band(r["zona"]), zone_channel(r["zona"]))
                slot = region.setdefault(key, {"disparos": 0, "zonas": set()})
                slot["disparos"] += r["n_disparos"]
                slot["zonas"].add(r["zona"])
            best = None
            for key, slot in region.items():
                n_passes = sum(zone_passes.get(z, 0) for z in slot["zonas"])
                if slot["disparos"] < min_triggers or n_passes == 0:
                    continue
                rate = slot["disparos"] / n_passes
                if best is None or rate > best[2]:
                    best = (key, slot, rate)
            if best is None:
                continue
            (faixa, corredor), slot, rate = best
            pattern = PadraoTatico.make(
                tipo="gatilho_pressao",
                match_id=match_id,
                time=pressing_team,
                chave_extra=f"{faixa}|{corredor}",
                descricao_curta=(
                    f"{pressing_team} dispara pressão quando a bola chega ao corredor "
                    f"{corredor} na faixa de {faixa} do campo adversário: {slot['disparos']} "
                    f"pressões em até {window_seconds:.0f}s após o passe ({rate:.0%} dos passes para a região)"
                ),
                valor_metrica=float(round(rate, 4)),
                nome_metrica="taxa_disparo_pressao",
                algoritmo_origem="cypher.temporal_window",
                zonas_envolvidas=sorted(int(z) for z in slot["zonas"]),
            )
            save_pattern(driver, pattern)
            patterns.append(pattern)
    return patterns


# ---------------------------------------------------------------------------
# 7.4 Ligação estrutural frágil (ponte)
# ---------------------------------------------------------------------------

def ligacao_fragil(driver: Driver, match_id: int) -> list[PadraoTatico]:
    """Insight 7.4: a conexão que, cortada, separa a defesa do ataque.

    Algoritmo: gds.bridges.stream sobre a rede de passes NÃO-direcionada
    (ponte clássica de teoria de grafos). Se a rede for densa demais para
    ter ponte, cai para o par de comunidades (Louvain) cuja ligação está
    mais concentrada num único par de jogadores (share do fluxo entre
    comunidades), via Cypher — documentado como fallback no catálogo.
    """
    patterns = []
    for team in teams_of_match(driver, match_id):
        with projections.pass_network(driver, match_id, team, undirected=True) as graph_name:
            with driver.session() as session:
                bridges = session.run(
                    """CALL gds.bridges.stream($g) YIELD from, to
                       RETURN gds.util.asNode(from).nome AS a, gds.util.asNode(to).nome AS b""",
                    g=graph_name,
                ).data()
                communities = {
                    r["nome"]: r["communityId"]
                    for r in session.run(
                        """CALL gds.louvain.stream($g, {relationshipWeightProperty: 'n_passes'})
                           YIELD nodeId, communityId
                           RETURN gds.util.asNode(nodeId).nome AS nome, communityId""",
                        g=graph_name,
                    ).data()
                }
                flows = session.run(
                    """MATCH (a:Jogador)-[p:PASSOU_PARA {match_id: $m}]->(b:Jogador)
                       WHERE a.time = $team AND b.time = $team
                       WITH a.nome AS a, b.nome AS b, count(*) AS n
                       RETURN a, b, n""",
                    m=match_id,
                    team=team,
                ).data()
        if bridges:
            a, b = bridges[0]["a"], bridges[0]["b"]
            valor, metrica, algoritmo = 1.0, "ponte_estrutural", "gds.bridges.stream"
            descricao = (
                f"A ligação {a} <-> {b} é uma ponte na rede de passes de {team}: "
                "removida, desconecta dois blocos do time"
            )
        else:
            # fluxo entre pares de comunidades concentrado num único par de jogadores
            inter = {}
            for f in flows:
                ca, cb = communities.get(f["a"]), communities.get(f["b"])
                if ca is None or cb is None or ca == cb:
                    continue
                key = tuple(sorted((ca, cb)))
                inter.setdefault(key, []).append(f)
            best = None
            for key, edges in inter.items():
                total = sum(e["n"] for e in edges)
                pair_flow: dict[tuple[str, str], int] = {}
                for e in edges:
                    pk = tuple(sorted((e["a"], e["b"])))
                    pair_flow[pk] = pair_flow.get(pk, 0) + e["n"]
                (a, b), top_n = max(pair_flow.items(), key=lambda kv: kv[1])
                share = top_n / total
                if total >= 10 and (best is None or share > best[2]):
                    best = ((a, b), total, share)
            if best is None:
                continue
            (a, b), total, share = best
            valor, metrica, algoritmo = round(share, 4), "share_fluxo_entre_comunidades", "gds.louvain.stream + cypher.flow_share"
            descricao = (
                f"{share:.0%} de todo o fluxo de passes entre dois blocos de {team} "
                f"passa por um único par: {a} <-> {b} ({total} passes entre os blocos). "
                "É onde uma pressão dirigida desconectaria construção de ataque"
            )
        pattern = PadraoTatico.make(
            tipo="ligacao_fragil",
            match_id=match_id,
            time=team,
            chave_extra=f"{a}|{b}",
            descricao_curta=descricao,
            valor_metrica=float(valor),
            nome_metrica=metrica,
            algoritmo_origem=algoritmo,
            jogadores_envolvidos=[a, b],
        )
        save_pattern(driver, pattern)
        patterns.append(pattern)
    return patterns


# ---------------------------------------------------------------------------
# 7.5 Papel real versus posição nominal (comunidade)
# ---------------------------------------------------------------------------

def papel_divergente(driver: Driver, match_id: int, min_actions: int = 15) -> list[PadraoTatico]:
    """Insight 7.5: quem joga numa função diferente da escalação?

    Algoritmo: gds.louvain.stream na rede de passes; a comunidade de cada
    jogador é comparada com a comunidade MODAL da sua linha nominal
    (defesa/meio/ataque, da escalação StatsBomb). Divergência com volume
    mínimo de ações = papel divergente.
    """
    patterns = []
    for team in teams_of_match(driver, match_id):
        with projections.pass_network(driver, match_id, team, undirected=True) as graph_name:
            with driver.session() as session:
                rows = session.run(
                    """CALL gds.louvain.stream($g, {relationshipWeightProperty: 'n_passes'})
                       YIELD nodeId, communityId
                       WITH gds.util.asNode(nodeId) AS j, communityId
                       OPTIONAL MATCH (j)-[a:ATUOU_EM {match_id: $m}]->()
                       RETURN j.nome AS nome, j.posicao_nominal AS posicao, communityId,
                              sum(a.contagem_acoes) AS n_acoes""",
                    g=graph_name,
                    m=match_id,
                ).data()
        lines: dict[str, list[int]] = {}
        for r in rows:
            line = nominal_line(r["posicao"])
            if line and line != "gol":
                lines.setdefault(line, []).append(r["communityId"])
        modal = {line: max(set(cs), key=cs.count) for line, cs in lines.items() if cs}
        for r in rows:
            line = nominal_line(r["posicao"])
            if not line or line == "gol" or line not in modal:
                continue
            if r["communityId"] == modal[line] or (r["n_acoes"] or 0) < min_actions:
                continue
            # a qual linha corresponde a comunidade onde ele de fato está?
            # Se a comunidade não é a modal de NENHUMA linha, é fragmentação
            # do Louvain, não um papel identificável — não vira padrão.
            real_lines = [ln for ln, cid in modal.items() if cid == r["communityId"] and ln != line]
            if not real_lines:
                continue
            real = real_lines[0]
            pattern = PadraoTatico.make(
                tipo="papel_divergente",
                match_id=match_id,
                time=team,
                chave_extra=r["nome"],
                descricao_curta=(
                    f"{r['nome']} ({r['posicao']}) escalado na linha de {line}, mas a "
                    f"comunidade de passes o agrupa com a linha de {real} "
                    f"({r['n_acoes']} ações)"
                ),
                valor_metrica=float(r["n_acoes"]),
                nome_metrica="acoes_na_comunidade_divergente",
                algoritmo_origem="gds.louvain.stream",
                jogadores_envolvidos=[r["nome"]],
            )
            save_pattern(driver, pattern)
            patterns.append(pattern)
    return patterns


# ---------------------------------------------------------------------------
# 7.6 Assimetria entre construção e finalização
# ---------------------------------------------------------------------------

def assimetria_construcao(driver: Driver, match_id: int, min_gap: float = 0.20) -> list[PadraoTatico]:
    """Insight 7.6: constrói por um lado, finaliza pelo outro?

    Algoritmo: agregação Cypher sobre PROGREDIU_PARA — share de cada corredor
    na construção (contagem de progressões com origem em defesa/meio) versus
    na chegada (fluxo de xT com destino no ataque). O padrão existe quando
    algum corredor diverge >= min_gap (20 p.p.) entre os dois papéis: ou
    concentra a chegada sem concentrar a construção, ou constrói sem chegar.
    A zona de transferência é o destino do maior fluxo que troca de corredor.
    """
    query = """
    MATCH (t:Time {nome: $team})
    MATCH (a:Zona)-[p:PROGREDIU_PARA {match_id: $m, team_id: t.team_id}]->(b:Zona)
    RETURN a.id_zona AS origem, a.faixa AS faixa_origem, a.corredor AS corr_origem,
           b.id_zona AS destino, b.faixa AS faixa_destino, b.corredor AS corr_destino,
           p.contagem AS n, p.contagem * p.xt_medio AS fluxo_xt
    """
    patterns = []
    for team in teams_of_match(driver, match_id):
        with driver.session() as session:
            rows = session.run(query, m=match_id, team=team).data()
        if not rows:
            continue
        build = {"esquerda": 0.0, "centro": 0.0, "direita": 0.0}
        finish = dict(build)
        for r in rows:
            if r["faixa_origem"] in ("defesa", "meio"):
                build[r["corr_origem"]] += r["n"]
            if r["faixa_destino"] == "ataque":
                finish[r["corr_destino"]] += max(r["fluxo_xt"], 0.0)
        total_build, total_finish = sum(build.values()), sum(finish.values())
        if total_build == 0 or total_finish == 0:
            continue
        deltas = {c: finish[c] / total_finish - build[c] / total_build for c in build}
        corredor, delta = max(deltas.items(), key=lambda kv: abs(kv[1]))
        if abs(delta) < min_gap:
            continue
        build_share = build[corredor] / total_build
        finish_share = finish[corredor] / total_finish
        if delta > 0:
            descricao = (
                f"O xT de chegada de {team} ao ataque concentra no corredor {corredor} "
                f"({finish_share:.0%}) de forma desproporcional à construção, que passa por lá "
                f"só {build_share:.0%} das vezes: a bola atravessa de corredor antes de finalizar"
            )
        else:
            descricao = (
                f"{team} constrói pelo corredor {corredor} ({build_share:.0%} das progressões "
                f"de defesa/meio) mas quase não chega ao ataque por ele ({finish_share:.0%} do xT "
                f"de chegada): corredor de construção estéril, a finalização acontece do outro lado"
            )
        transfers = [
            r for r in rows
            if r["faixa_destino"] == "ataque" and r["corr_origem"] != r["corr_destino"]
            and (r["corr_destino"] == corredor if delta > 0 else r["corr_origem"] == corredor)
        ]
        transfer_zone = max(transfers, key=lambda r: r["fluxo_xt"])["destino"] if transfers else None
        pattern = PadraoTatico.make(
            tipo="assimetria_construcao",
            match_id=match_id,
            time=team,
            chave_extra=corredor,
            descricao_curta=descricao,
            valor_metrica=float(round(delta, 4)),
            nome_metrica="delta_share_construcao_vs_chegada",
            algoritmo_origem="cypher.flow_aggregation(PROGREDIU_PARA)",
            zonas_envolvidas=[int(transfer_zone)] if transfer_zone is not None else [],
        )
        save_pattern(driver, pattern)
        patterns.append(pattern)
    return patterns


# ---------------------------------------------------------------------------
# 7.7 Estado tático que mudou no meio do jogo (bitemporal)
# ---------------------------------------------------------------------------

def mudanca_estado(driver: Driver, match_id: int, data_dir: Path, k: int = 3, ppda_threshold: float = 6.0, tilt_threshold: float = 0.18) -> list[PadraoTatico]:
    """Insight 7.7: o time mudou de comportamento durante o jogo?

    Algoritmo: detecção de ponto de mudança sobre a série de janelas móveis
    (calculada no passo 0.4e, NUNCA aqui — contrato da camada 0): a quebra é
    o ponto que maximiza |média(k janelas seguintes) - média(k anteriores)|,
    aceita se acima do limiar. Cada estado vira um PadraoTatico com
    intervalo de validade explícito (valid_at/invalid_at): o fato antigo é
    INVALIDADO, não apagado — modelo bitemporal.
    """
    windows = pd.read_parquet(data_dir / "processed" / f"{match_id}_windows.parquet")
    meta = json.loads((data_dir / "processed" / f"{match_id}_meta.json").read_text())
    patterns = []
    for team_id, team_name in meta["teams"].items():
        df = windows[windows["team_id"] == int(team_id)].sort_values("window_start_min").reset_index(drop=True)
        for metric, threshold, fmt in (("ppda", ppda_threshold, "{:.1f}"), ("field_tilt", tilt_threshold, "{:.0%}")):
            series = df[metric]
            best = None
            for i in range(k, len(df) - k):
                before = series.iloc[i - k : i].dropna()
                after = series.iloc[i : i + k].dropna()
                if len(before) < k or len(after) < k:
                    continue
                diff = abs(after.mean() - before.mean())
                if diff >= threshold and (best is None or diff > best[1]):
                    best = (i, diff, before.mean(), after.mean())
            if best is None:
                continue
            i, diff, mean_before, mean_after = best
            break_minute = float(df.loc[i, "window_start_min"])
            end_minute = float(df["window_end_min"].max())
            label = "PPDA" if metric == "ppda" else "field tilt"
            if metric == "ppda":
                estado_antes = "pressão alta" if mean_before < mean_after else "bloco baixo"
                estado_depois = "bloco baixo" if mean_before < mean_after else "pressão alta"
            else:
                estado_antes = "domínio territorial" if mean_before > mean_after else "campo cedido"
                estado_depois = "campo cedido" if mean_before > mean_after else "domínio territorial"
            old_state = PadraoTatico.make(
                tipo="mudanca_estado",
                match_id=match_id,
                time=team_name,
                chave_extra=f"{metric}|antes",
                descricao_curta=(
                    f"{team_name} em {estado_antes} até o minuto {break_minute:.0f} "
                    f"({label} médio {fmt.format(mean_before)}) — estado invalidado aos {break_minute:.0f}"
                ),
                minuto_inicio=0.0,
                minuto_fim=break_minute,
                valor_metrica=float(round(mean_before, 4)),
                nome_metrica=f"{metric}_janela_movel",
                algoritmo_origem="pipeline.windowed_metrics + cypher.changepoint(diff_medias)",
                valid_at=0.0,
                invalid_at=break_minute,
            )
            new_state = PadraoTatico.make(
                tipo="mudanca_estado",
                match_id=match_id,
                time=team_name,
                chave_extra=f"{metric}|depois",
                descricao_curta=(
                    f"{team_name} muda para {estado_depois} a partir do minuto {break_minute:.0f} "
                    f"({label} médio {fmt.format(mean_after)} contra {fmt.format(mean_before)} antes)"
                ),
                minuto_inicio=break_minute,
                minuto_fim=end_minute,
                valor_metrica=float(round(mean_after, 4)),
                nome_metrica=f"{metric}_janela_movel",
                algoritmo_origem="pipeline.windowed_metrics + cypher.changepoint(diff_medias)",
                valid_at=break_minute,
                invalid_at=None,
            )
            save_pattern(driver, old_state)
            save_pattern(driver, new_state)
            patterns.extend([old_state, new_state])
    return patterns


# ---------------------------------------------------------------------------
# 7.8 O alvo real da pressão adversária (grau de entrada)
# ---------------------------------------------------------------------------

def alvo_de_pressao(driver: Driver, match_id: int, min_pressures: int = 10) -> list[PadraoTatico]:
    """Insight 7.8: o adversário está caçando um jogador específico?

    Algoritmo: gds.degree.stream (orientação REVERSE, peso = contagem de
    pressões) na rede de pressão, normalizado por toques do alvo — senão o
    jogador que mais toca na bola sempre "vence".
    """
    patterns = []
    for pressing_team in teams_of_match(driver, match_id):
        with projections.pressure_network(driver, match_id, pressing_team) as graph_name:
            with driver.session() as session:
                rows = session.run(
                    """CALL gds.degree.stream($g, {orientation: 'REVERSE', relationshipWeightProperty: 'n_pressoes'})
                       YIELD nodeId, score
                       WITH gds.util.asNode(nodeId) AS j, score
                       WHERE score > 0 AND j.time <> $pressing_team
                       OPTIONAL MATCH (j)-[a:ATUOU_EM {match_id: $m}]->()
                       RETURN j.nome AS nome, score AS pressoes_recebidas,
                              sum(a.contagem_acoes) AS toques""",
                    g=graph_name,
                    m=match_id,
                    pressing_team=pressing_team,
                ).data()
        candidates = [
            (r["nome"], r["pressoes_recebidas"], r["toques"], r["pressoes_recebidas"] / r["toques"])
            for r in rows
            if (r["toques"] or 0) >= 10 and r["pressoes_recebidas"] >= min_pressures
        ]
        if not candidates:
            continue
        team_avg = sum(c[3] for c in candidates) / len(candidates)
        nome, n_pressoes, toques, rate = max(candidates, key=lambda c: c[3])
        if rate < 1.5 * team_avg:
            continue  # sem concentração: não há caça direcionada (resultado honesto)
        pattern = PadraoTatico.make(
            tipo="alvo_de_pressao",
            match_id=match_id,
            time=pressing_team,
            chave_extra=nome,
            descricao_curta=(
                f"{pressing_team} concentra pressão em {nome}: {n_pressoes:.0f} pressões em "
                f"{toques} toques ({rate:.2f} por toque, {rate / team_avg:.1f}x a média dos companheiros)"
            ),
            valor_metrica=float(round(rate, 4)),
            nome_metrica="pressoes_por_toque",
            algoritmo_origem="gds.degree.stream",
            jogadores_envolvidos=[nome],
        )
        save_pattern(driver, pattern)
        patterns.append(pattern)
    return patterns


ALL_INSIGHTS = {
    "pivo_estrutural": pivo_estrutural,
    "terceiro_homem": terceiro_homem,
    "gatilho_pressao": gatilho_pressao,
    "ligacao_fragil": ligacao_fragil,
    "papel_divergente": papel_divergente,
    "assimetria_construcao": assimetria_construcao,
    "alvo_de_pressao": alvo_de_pressao,
    # mudanca_estado precisa de data_dir; tratado à parte em run_all
}


def run_all(driver: Driver, match_id: int, data_dir: Path) -> dict[str, int]:
    """Roda a camada 2 inteira para uma partida. Retorna contagem por tipo."""
    results = {}
    for name, fn in ALL_INSIGHTS.items():
        patterns = fn(driver, match_id)
        results[name] = len(patterns)
        logger.info("insight %s: %d padrões", name, len(patterns))
    patterns = mudanca_estado(driver, match_id, data_dir)
    results["mudanca_estado"] = len(patterns)
    logger.info("insight mudanca_estado: %d padrões", len(patterns))
    return results

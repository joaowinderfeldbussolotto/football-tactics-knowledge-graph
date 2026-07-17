"""CAMADA 1: construção do grafo factual. Determinística, sem LLM.

Cada linha do parquet vira nó/aresta com valores EXATOS. Zero chamada de
LLM, zero risco de alucinação. A escrita é idempotente: os nós têm uid
determinístico (uuid5 da chave natural) e as arestas fazem MERGE por chave
(match_id + action_id / índice), então rodar duas vezes não duplica nada.

Decisão de arquitetura (ADR em docs/05-decisoes.md): a escrita usa o driver
Neo4j direto (Cypher em lotes UNWIND) em vez de ``graphiti.add_triplet``.
O add_triplet dispara uma chamada de embedding por fato — ordem de milhares
por partida — o que viola o orçamento de custo/latência da camada factual e
acopla a camada determinística a um serviço externo. O Graphiti entra nas
camadas 2/3 (indexação dos PadraoTatico e busca híbrida), onde o volume é
de dezenas de fatos e a semântica importa.
"""

import json
import logging
import time
from pathlib import Path

import pandas as pd
from neo4j import Driver

from football_graphrag.graph import db
from football_graphrag.graph.entities import uid_for
from football_graphrag.ingestion.tactical_metrics import GRID_COLS, GRID_ROWS, zone_band, zone_channel

logger = logging.getLogger(__name__)

PASS_TYPES = ["pass", "cross", "freekick_short", "corner_short", "throw_in", "goalkick", "freekick_crossed", "corner_crossed"]
MOVE_TYPES = ["pass", "cross", "dribble", "carry"]
SHOT_TYPES = ["shot", "shot_penalty", "shot_freekick"]


def build_factual_graph(match_id: int, data_dir: Path, driver: Driver) -> dict:
    """Constrói (idempotente) o grafo factual de uma partida a partir dos parquets.

    Saída:
        dict com contagens por tipo de nó/aresta e tempo total — os números
        que alimentam docs/02-modelo-grafo.md e a decisão do ADR de escrita.
    """
    t0 = time.perf_counter()
    processed = data_dir / "processed"
    actions = pd.read_parquet(processed / f"{match_id}.parquet")
    phases = pd.read_parquet(processed / f"{match_id}_phases.parquet")
    pressures = pd.read_parquet(processed / f"{match_id}_pressures.parquet")
    meta = json.loads((processed / f"{match_id}_meta.json").read_text())

    db.ensure_constraints(driver)
    counts: dict[str, int] = {}

    # --- Nós ---
    counts["Partida"] = _write_partida(driver, match_id, meta)
    counts["Time"] = _write_times(driver, meta)
    counts["Jogador"] = _write_jogadores(driver, actions, meta)
    counts["Zona"] = _write_zonas(driver)
    counts["FaseDePosse"] = _write_fases(driver, match_id, phases)

    # --- Arestas factuais ---
    counts["MEMBRO_DE"] = _write_membro_de(driver, match_id, actions)
    counts["PASSOU_PARA"] = _write_passes(driver, match_id, actions)
    counts["PRESSIONOU"] = _write_pressoes(driver, match_id, pressures)
    counts["FINALIZOU"] = _write_finalizacoes(driver, match_id, actions)
    counts["DEU_ASSISTENCIA"] = _write_assistencias(driver, match_id, actions)
    counts["ATUOU_EM"] = _write_atuou_em(driver, match_id, actions)
    counts["PARTICIPOU_DE"] = _write_participou_de(driver, match_id, actions)
    counts["PROGREDIU_PARA"] = _write_progrediu_para(driver, match_id, actions)

    elapsed = round(time.perf_counter() - t0, 2)
    total = sum(counts.values())
    logger.info("grafo factual %s: %d nós/arestas em %.2fs (%s)", match_id, total, elapsed, counts)
    return {"match_id": match_id, "counts": counts, "total_writes": total, "elapsed_seconds": elapsed}


def _write_partida(driver: Driver, match_id: int, meta: dict) -> int:
    query = """
    MERGE (p:Partida {uid: $uid})
    SET p.match_id = $match_id, p.competicao = $competicao, p.times = $times
    """
    with db.session_scope(driver) as session:
        session.run(
            query,
            uid=uid_for("partida", match_id),
            match_id=match_id,
            competicao="FIFA World Cup 2022",
            times=list(meta["teams"].values()),
        ).consume()
    return 1


def _write_times(driver: Driver, meta: dict) -> int:
    rows = [
        {"uid": uid_for("time", team_id), "team_id": int(team_id), "nome": nome}
        for team_id, nome in meta["teams"].items()
    ]
    return db.run_batched(
        driver,
        "UNWIND $rows AS r MERGE (t:Time {uid: r.uid}) SET t.team_id = r.team_id, t.nome = r.nome",
        rows,
    )


def _write_jogadores(driver: Driver, actions: pd.DataFrame, meta: dict) -> int:
    players = (
        actions.dropna(subset=["player_id"])
        .groupby("player_id")
        .agg(nome=("player_name", "first"), team_id=("team_id", "first"))
        .reset_index()
    )
    positions = meta.get("player_positions", {})
    rows = [
        {
            "uid": uid_for("jogador", int(p.player_id)),
            "player_id": int(p.player_id),
            "nome": p.nome,
            "posicao_nominal": positions.get(str(int(p.player_id))),
            "time": meta["teams"].get(str(int(p.team_id))),
        }
        for p in players.itertuples()
    ]
    return db.run_batched(
        driver,
        """UNWIND $rows AS r MERGE (j:Jogador {uid: r.uid})
           SET j.player_id = r.player_id, j.nome = r.nome,
               j.posicao_nominal = r.posicao_nominal, j.time = r.time""",
        rows,
    )


def _write_zonas(driver: Driver) -> int:
    rows = [
        {
            "uid": uid_for("zona", z),
            "id_zona": z,
            "faixa": zone_band(z),
            "corredor": zone_channel(z),
        }
        for z in range(GRID_COLS * GRID_ROWS)
    ]
    return db.run_batched(
        driver,
        """UNWIND $rows AS r MERGE (z:Zona {uid: r.uid})
           SET z.id_zona = r.id_zona, z.faixa = r.faixa, z.corredor = r.corredor""",
        rows,
    )


def _write_fases(driver: Driver, match_id: int, phases: pd.DataFrame) -> int:
    rows = [
        {
            "uid": uid_for("fase", f"{match_id}:{int(p.possession_id)}"),
            "fase_id": f"{match_id}:{int(p.possession_id)}",
            "match_id": match_id,
            "team_id": int(p.team_id),
            "minuto_inicio": float(p.minute_start),
            "minuto_fim": float(p.minute_end),
            "xt_total": float(p.xt_total),
            "zona_inicio": int(p.zone_start),
            "zona_fim": int(p.zone_end),
            "n_acoes": int(p.n_actions),
        }
        for p in phases.itertuples()
    ]
    return db.run_batched(
        driver,
        """UNWIND $rows AS r MERGE (f:FaseDePosse {uid: r.uid})
           SET f += r""",
        rows,
    )


def _write_membro_de(driver: Driver, match_id: int, actions: pd.DataFrame) -> int:
    players = actions.dropna(subset=["player_id"]).groupby("player_id").agg(team_id=("team_id", "first")).reset_index()
    rows = [
        {
            "jogador": uid_for("jogador", int(p.player_id)),
            "time": uid_for("time", int(p.team_id)),
            "match_id": match_id,
        }
        for p in players.itertuples()
    ]
    return db.run_batched(
        driver,
        """UNWIND $rows AS r
           MATCH (j:Jogador {uid: r.jogador}), (t:Time {uid: r.time})
           MERGE (j)-[m:MEMBRO_DE {match_id: r.match_id}]->(t)""",
        rows,
    )


def _write_passes(driver: Driver, match_id: int, actions: pd.DataFrame) -> int:
    passes = actions[actions["receiver_player_id"].notna() & actions["type_name"].isin(PASS_TYPES)]
    rows = [
        {
            "origem": uid_for("jogador", int(a.player_id)),
            "destino": uid_for("jogador", int(a.receiver_player_id)),
            "match_id": match_id,
            "action_id": int(a.action_id),
            "minuto": float(a.time_seconds) / 60.0,
            "periodo": int(a.period_id),
            "xt_gerado": float(a.xt_value),
            "vaep": float(a.vaep_value),
            "progressivo": bool(a.progressive),
            "sucesso": a.result_name == "success",
            "zona_origem": int(a.zone_start),
            "zona_destino": int(a.zone_end),
            "fase_posse_id": f"{match_id}:{int(a.possession_id)}",
        }
        for a in passes.itertuples()
    ]
    return db.run_batched(
        driver,
        """UNWIND $rows AS r
           MATCH (a:Jogador {uid: r.origem}), (b:Jogador {uid: r.destino})
           MERGE (a)-[p:PASSOU_PARA {match_id: r.match_id, action_id: r.action_id}]->(b)
           SET p.minuto = r.minuto, p.periodo = r.periodo, p.xt_gerado = r.xt_gerado,
               p.vaep = r.vaep, p.progressivo = r.progressivo, p.sucesso = r.sucesso,
               p.zona_origem = r.zona_origem, p.zona_destino = r.zona_destino,
               p.fase_posse_id = r.fase_posse_id""",
        rows,
    )


def _write_pressoes(driver: Driver, match_id: int, pressures: pd.DataFrame) -> int:
    valid = pressures[pressures["target_player_id"].notna()]
    rows = [
        {
            "origem": uid_for("jogador", int(p.presser_player_id)),
            "destino": uid_for("jogador", int(p.target_player_id)),
            "match_id": match_id,
            "pressure_idx": int(idx),
            "minuto": float(p.minute),
            "periodo": int(p.period_id),
            "zona": int(p.zone) if pd.notna(p.zone) else None,
        }
        for idx, p in zip(valid.index, valid.itertuples())
    ]
    return db.run_batched(
        driver,
        """UNWIND $rows AS r
           MATCH (a:Jogador {uid: r.origem}), (b:Jogador {uid: r.destino})
           MERGE (a)-[p:PRESSIONOU {match_id: r.match_id, pressure_idx: r.pressure_idx}]->(b)
           SET p.minuto = r.minuto, p.periodo = r.periodo, p.zona = r.zona""",
        rows,
    )


def _write_finalizacoes(driver: Driver, match_id: int, actions: pd.DataFrame) -> int:
    """Jogador -[FINALIZOU]-> Partida: uma aresta por finalização (chute,
    pênalti em jogo, falta direta), com ``gol`` booleano. Seleção direta de
    linhas do parquet — nada calculado aqui."""
    shots = actions[actions["type_name"].isin(SHOT_TYPES)]
    rows = [
        {
            "jogador": uid_for("jogador", int(s.player_id)),
            "partida": uid_for("partida", match_id),
            "match_id": match_id,
            "action_id": int(s.action_id),
            "minuto": float(s.time_seconds) / 60.0,
            "periodo": int(s.period_id),
            "tipo": s.type_name,
            "resultado": s.result_name,
            "gol": s.result_name == "success",
            "zona": int(s.zone_start),
        }
        for s in shots.itertuples()
        if pd.notna(s.player_id)
    ]
    return db.run_batched(
        driver,
        """UNWIND $rows AS r
           MATCH (j:Jogador {uid: r.jogador}), (m:Partida {uid: r.partida})
           MERGE (j)-[f:FINALIZOU {match_id: r.match_id, action_id: r.action_id}]->(m)
           SET f.minuto = r.minuto, f.periodo = r.periodo, f.tipo = r.tipo,
               f.resultado = r.resultado, f.gol = r.gol, f.zona = r.zona""",
        rows,
    )


def _write_assistencias(driver: Driver, match_id: int, actions: pd.DataFrame) -> int:
    """Jogador -[DEU_ASSISTENCIA]-> Jogador (autor do gol).

    Assistência = último passe bem-sucedido do mesmo time, na mesma fase de
    posse, cujo recebedor é o autor do gol (gols de pênalti não têm
    assistência). Seleção sobre colunas já existentes do parquet
    (possession_id, receiver_player_id) — sem métrica nova.
    """
    goals = actions[
        actions["type_name"].isin(["shot", "shot_freekick"]) & (actions["result_name"] == "success")
    ]
    rows = []
    for g in goals.itertuples():
        prev = actions[
            (actions["possession_id"] == g.possession_id)
            & (actions["action_id"] < g.action_id)
            & (actions["team_id"] == g.team_id)
            & (actions["receiver_player_id"] == g.player_id)
        ]
        if len(prev) == 0:
            continue
        p = prev.iloc[-1]
        rows.append(
            {
                "assistente": uid_for("jogador", int(p.player_id)),
                "autor": uid_for("jogador", int(g.player_id)),
                "match_id": match_id,
                "action_id": int(g.action_id),
                "minuto": float(g.time_seconds) / 60.0,
                "periodo": int(g.period_id),
            }
        )
    return db.run_batched(
        driver,
        """UNWIND $rows AS r
           MATCH (a:Jogador {uid: r.assistente}), (b:Jogador {uid: r.autor})
           MERGE (a)-[s:DEU_ASSISTENCIA {match_id: r.match_id, action_id: r.action_id}]->(b)
           SET s.minuto = r.minuto, s.periodo = r.periodo""",
        rows,
    )


def _write_atuou_em(driver: Driver, match_id: int, actions: pd.DataFrame) -> int:
    agg = (
        actions.dropna(subset=["player_id"])
        .groupby(["player_id", "zone_start"])
        .agg(contagem_acoes=("type_name", "size"), xt_acumulado=("xt_value", "sum"))
        .reset_index()
    )
    rows = [
        {
            "jogador": uid_for("jogador", int(a.player_id)),
            "zona": uid_for("zona", int(a.zone_start)),
            "match_id": match_id,
            "contagem_acoes": int(a.contagem_acoes),
            "xt_acumulado": float(a.xt_acumulado),
        }
        for a in agg.itertuples()
    ]
    return db.run_batched(
        driver,
        """UNWIND $rows AS r
           MATCH (j:Jogador {uid: r.jogador}), (z:Zona {uid: r.zona})
           MERGE (j)-[a:ATUOU_EM {match_id: r.match_id}]->(z)
           SET a.contagem_acoes = r.contagem_acoes, a.xt_acumulado = r.xt_acumulado""",
        rows,
    )


def _write_participou_de(driver: Driver, match_id: int, actions: pd.DataFrame) -> int:
    agg = (
        actions.dropna(subset=["player_id"])
        .groupby(["player_id", "possession_id"])
        .size()
        .reset_index(name="numero_de_toques")
    )
    rows = [
        {
            "jogador": uid_for("jogador", int(a.player_id)),
            "fase": uid_for("fase", f"{match_id}:{int(a.possession_id)}"),
            "match_id": match_id,
            "numero_de_toques": int(a.numero_de_toques),
        }
        for a in agg.itertuples()
    ]
    return db.run_batched(
        driver,
        """UNWIND $rows AS r
           MATCH (j:Jogador {uid: r.jogador}), (f:FaseDePosse {uid: r.fase})
           MERGE (j)-[p:PARTICIPOU_DE {match_id: r.match_id}]->(f)
           SET p.numero_de_toques = r.numero_de_toques""",
        rows,
    )


def _write_progrediu_para(driver: Driver, match_id: int, actions: pd.DataFrame) -> int:
    moves = actions[
        actions["type_name"].isin(MOVE_TYPES)
        & (actions["result_name"] == "success")
        & (actions["zone_start"] != actions["zone_end"])
    ]
    agg = (
        moves.groupby(["zone_start", "zone_end", "team_id"])
        .agg(contagem=("type_name", "size"), xt_medio=("xt_value", "mean"))
        .reset_index()
    )
    rows = [
        {
            "origem": uid_for("zona", int(a.zone_start)),
            "destino": uid_for("zona", int(a.zone_end)),
            "match_id": match_id,
            "team_id": int(a.team_id),
            "contagem": int(a.contagem),
            "xt_medio": float(a.xt_medio),
        }
        for a in agg.itertuples()
    ]
    return db.run_batched(
        driver,
        """UNWIND $rows AS r
           MATCH (a:Zona {uid: r.origem}), (b:Zona {uid: r.destino})
           MERGE (a)-[p:PROGREDIU_PARA {match_id: r.match_id, team_id: r.team_id}]->(b)
           SET p.contagem = r.contagem, p.xt_medio = r.xt_medio""",
        rows,
    )


def graph_stats(driver: Driver, match_id: int) -> dict:
    """Contagem de nós e arestas por tipo (endpoint /graph/{match_id}/stats)."""
    with db.session_scope(driver) as session:
        nodes = session.run(
            """MATCH (n) WHERE n.match_id = $m OR n:Jogador OR n:Time OR n:Zona
               RETURN labels(n)[0] AS label, count(*) AS n ORDER BY label""",
            m=match_id,
        ).data()
        edges = session.run(
            """MATCH ()-[r]->() WHERE r.match_id = $m
               RETURN type(r) AS type, count(*) AS n ORDER BY type""",
            m=match_id,
        ).data()
    return {
        "match_id": match_id,
        "nodes": {r["label"]: r["n"] for r in nodes},
        "edges": {r["type"]: r["n"] for r in edges},
    }

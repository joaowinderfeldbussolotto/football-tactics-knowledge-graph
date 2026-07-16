"""Orquestra o pipeline offline completo: download -> SPADL -> xT/VAEP ->
métricas táticas -> parquet processado.

Chamado por `scripts/run_ingestion.py`. Mantido como módulo importável (em
vez de lógica só dentro do script) para poder ser reaproveitado em testes e,
futuramente, por outros pontos de entrada (ex.: um endpoint de ingestão).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from football_graphrag.ingestion import tactical_metrics as tm
from football_graphrag.ingestion.spadl_transform import (
    MatchContext,
    build_match_context,
    convert_to_spadl,
    enrich_actions,
    fit_vaep_model,
)
from football_graphrag.ingestion.statsbomb_loader import load_match_dataset

logger = logging.getLogger(__name__)

DATA_PROCESSED_DIR = Path("data/processed")


def _json_default(value: Any):
    if hasattr(value, "item"):  # numpy scalars (int64, float64, bool_...)
        return value.item()
    raise TypeError(f"Object of type {type(value)} is not JSON serializable")


def _build_processed_dataframe(ctx: MatchContext, enriched: pd.DataFrame) -> pd.DataFrame:
    team_grounds = {t.team_id: t.ground for t in ctx.teams.values()}
    progressive = tm.compute_progressive_passes(enriched, team_grounds)
    phase_id = tm.assign_possession_phase_id(enriched)

    df = enriched.copy()
    df["progressive"] = progressive["progressive"].values
    df["corridor"] = progressive["corridor"].values
    df["phase_id"] = phase_id.values
    df["team_name"] = df["team_id"].map(lambda tid: ctx.teams[tid].name if tid in ctx.teams else None)
    df["team_ground"] = df["team_id"].map(lambda tid: ctx.teams[tid].ground if tid in ctx.teams else None)
    df["player_name"] = df["player_id"].map(lambda pid: ctx.players[pid].name if pid in ctx.players else None)
    df["player_position"] = df["player_id"].map(
        lambda pid: ctx.players[pid].position if pid in ctx.players else None
    )
    return df


def _build_match_summary(ctx: MatchContext, processed: pd.DataFrame) -> dict:
    teams = list(ctx.teams.values())
    home = next(t for t in teams if t.ground == "home")
    away = next(t for t in teams if t.ground == "away")

    team_summaries = [
        tm.team_match_summary(processed, home.team_id, away.team_id, "home"),
        tm.team_match_summary(processed, away.team_id, home.team_id, "away"),
    ]

    passing_networks = {}
    for team in teams:
        players = {p.player_id: p.name for p in ctx.players.values() if p.team_id == team.team_id}
        graph = tm.build_passing_network(processed, team.team_id, players)
        centrality = tm.passing_network_centrality(graph)
        passing_networks[team.team_id] = centrality.to_dict(orient="records")

    phases = tm.segment_possession_phases(processed)

    return {
        "match_id": ctx.match_id,
        "teams": {t.team_id: {"name": t.name, "ground": t.ground} for t in teams},
        "team_summaries": team_summaries,
        "passing_networks": passing_networks,
        "n_possession_phases": len(phases),
    }


def load_match_summary(match_id: str, processed_dir: Path = DATA_PROCESSED_DIR) -> dict | None:
    """Lê `{match_id}_summary.json` de volta, sem recalcular nada.

    Usado por `graph.client.ingest_match_batch` para injetar PPDA/field
    tilt/VAEP agregados por time no grafo (ver seção 6.3 do plano). Retorna
    `None` se o arquivo não existir, em vez de levantar — uma partida
    processada por uma versão anterior do pipeline pode não ter esse
    sidecar ainda, e isso não deveria impedir a ingestão por fase de posse.
    """
    summary_path = processed_dir / f"{match_id}_summary.json"
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text())


def process_match(match_id: str, vaep_model=None, raw_dir: Path | None = None) -> tuple[pd.DataFrame, MatchContext]:
    """Baixa (se preciso), converte para SPADL e enriquece uma única partida.

    Não calcula VAEP se `vaep_model` for None (fica com colunas de VAEP
    vazias) — útil na etapa 1 do pipeline, antes de treinar o modelo
    combinado em `fit_vaep_model`.
    """
    kwargs = {"raw_dir": raw_dir} if raw_dir is not None else {}
    dataset = load_match_dataset(match_id, **kwargs)
    ctx = build_match_context(dataset, match_id)
    actions = convert_to_spadl(dataset, match_id)
    enriched = enrich_actions(actions, ctx.game_row, vaep_model=vaep_model)
    return enriched, ctx


def run_ingestion_pipeline(
    match_ids: list[str],
    processed_dir: Path = DATA_PROCESSED_DIR,
    raw_dir: Path | None = None,
) -> list[Path]:
    """Roda o pipeline completo (seção 6.1/6.2) para uma lista de partidas.

    O modelo de VAEP é treinado uma única vez, combinando as ações de todas
    as partidas informadas (ver docstring de `fit_vaep_model`).
    """
    processed_dir.mkdir(parents=True, exist_ok=True)

    raw_actions: dict[str, tuple[pd.Series, pd.DataFrame]] = {}
    contexts: dict[str, MatchContext] = {}
    for match_id in match_ids:
        kwargs = {"raw_dir": raw_dir} if raw_dir is not None else {}
        dataset = load_match_dataset(match_id, **kwargs)
        ctx = build_match_context(dataset, match_id)
        actions = convert_to_spadl(dataset, match_id)
        contexts[match_id] = ctx
        raw_actions[match_id] = (ctx.game_row, actions)

    logger.info("Treinando modelo VAEP combinado em %d partida(s)...", len(raw_actions))
    vaep_model = fit_vaep_model(raw_actions)

    output_paths = []
    for match_id, (game_row, actions) in raw_actions.items():
        ctx = contexts[match_id]
        enriched = enrich_actions(actions, game_row, vaep_model=vaep_model)
        processed = _build_processed_dataframe(ctx, enriched)

        parquet_path = processed_dir / f"{match_id}.parquet"
        processed.to_parquet(parquet_path, index=False)
        output_paths.append(parquet_path)
        logger.info("Partida %s processada -> %s (%d ações)", match_id, parquet_path, len(processed))

        summary = _build_match_summary(ctx, processed)
        summary_path = processed_dir / f"{match_id}_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, default=_json_default, ensure_ascii=False))
        logger.info("Resumo tático salvo -> %s", summary_path)

    return output_paths

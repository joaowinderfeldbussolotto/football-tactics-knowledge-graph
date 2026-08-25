"""Passo 0.5: orquestração da camada 0 e materialização em Parquet.

Contrato duro do projeto: a partir do parquet gerado aqui, NADA mais é
calculado. Camadas 1-3 apenas leem. Se um insight precisar de um número
novo, ele entra no passo 0.4 e o parquet é regenerado.

Saídas por partida em ``data/processed/``:
- ``{match_id}.parquet``          1 linha por ação SPADL, com métricas.
- ``{match_id}_phases.parquet``   1 linha por fase de posse.
- ``{match_id}_windows.parquet``  métricas de time em janelas móveis.
- ``{match_id}_meta.json``        metadados da partida + contagens da pipeline.
- ``{match_id}_schema.json``      dicionário de dados gerado por código.
"""

import json
import logging
import time
from pathlib import Path

import pandas as pd
from socceraction.data.statsbomb import StatsBombLoader

from football_graphrag.ingestion import (
    football_semantics,
    pressure_events,
    spadl_transform,
    statsbomb_loader,
    tactical_metrics,
)

logger = logging.getLogger(__name__)

# Partidas usadas SÓ para treinar xT/VAEP quando não há modelo cacheado
# (mata-mata da Copa 2022; ver ADR "modelos de valoração" em docs/05-decisoes.md).
DEFAULT_TRAINING_MATCH_IDS = [
    3869151, 3869117, 3869118, 3869152, 3869219, 3869220, 3869253, 3869254,
    3869321, 3869354, 3869420, 3869486, 3869519, 3869552, 3869684, 3869685,
]

# Colunas do parquet principal: (nome, descrição, unidade, passo de origem).
SCHEMA_DOC: list[tuple[str, str, str, str]] = [
    ("game_id", "id StatsBomb da partida", "-", "0.2"),
    ("original_event_id", "id do evento StatsBomb de origem", "-", "0.2"),
    ("action_id", "índice sequencial da ação na partida", "-", "0.2"),
    ("period_id", "período (1=1º tempo, 2=2º, 3+=prorrogação)", "-", "0.2"),
    ("time_seconds", "segundos desde o início do período", "s", "0.2"),
    ("team_id", "id do time executor", "-", "0.2"),
    ("player_id", "id do jogador executor", "-", "0.2"),
    ("start_x", "x inicial, ataque sempre esq->dir", "m (0-105)", "0.2"),
    ("start_y", "y inicial, origem canto inferior esquerdo", "m (0-68)", "0.2"),
    ("end_x", "x final da ação", "m (0-105)", "0.2"),
    ("end_y", "y final da ação", "m (0-68)", "0.2"),
    ("type_id", "tipo SPADL (id)", "-", "0.2"),
    ("type_name", "tipo SPADL (nome, ~23 valores)", "-", "0.2"),
    ("result_id", "resultado (id)", "-", "0.2"),
    ("result_name", "resultado: success/fail/offside/owngoal/...", "-", "0.2"),
    ("bodypart_id", "parte do corpo (id)", "-", "0.2"),
    ("bodypart_name", "parte do corpo (nome)", "-", "0.2"),
    ("player_name", "nome do jogador executor", "-", "0.5"),
    ("team_name", "nome do time executor", "-", "0.5"),
    ("xt_value", "delta de Expected Threat da ação (0 se não move a bola com sucesso)", "prob. de gol", "0.3a"),
    ("vaep_offensive", "componente ofensivo do VAEP", "prob. de gol", "0.3b"),
    ("vaep_defensive", "componente defensivo do VAEP", "prob. de gol", "0.3b"),
    ("vaep_value", "VAEP total = ofensivo - defensivo", "prob. de gol", "0.3b"),
    ("zone_start", "zona inicial na grade 12x8 (0-95)", "-", "0.4a"),
    ("zone_end", "zona final na grade 12x8 (0-95)", "-", "0.4a"),
    ("possession_id", "id da fase de posse (sequencial na partida)", "-", "0.4b"),
    ("progressive", "ação progressiva (definição Wyscout)", "bool", "0.4c"),
    ("receiver_player_id", "recebedor do passe (NaN se não aplicável)", "-", "0.4d"),
    # --- vocabulário de futebol (passo 0.4h): é o que vai para o grafo ---
    ("acao", "ação em português, vocabulário fechado (desarme, drible, conducao...)", "-", "0.4h"),
    ("grupo_acao", "categoria grossa: passe/finalizacao/defensiva/conducao/drible/...", "-", "0.4h"),
    ("sucesso", "a ação deu certo? (result_name == success, explicitado)", "bool", "0.4h"),
    ("minuto", "minuto de jogo como na transmissão (1-120+), já com offset de período", "min", "0.4h"),
    ("periodo_nome", "'1º tempo', '2ª prorrogação'...", "-", "0.4h"),
    ("gol", "esta ação foi um gol?", "bool", "0.4h"),
    ("cartao_amarelo", "esta ação gerou cartão amarelo?", "bool", "0.4h"),
    ("corpo", "parte do corpo em português (pe, cabeca...)", "-", "0.4h"),
    ("terco", "terço do campo onde a ação começou: defesa/meio/ataque", "-", "0.4h"),
    ("corredor", "corredor onde a ação começou: esquerda/centro/direita", "-", "0.4h"),
    ("desfecho", "desfecho da finalização: gol/defendida/para_fora/bloqueada/na_trave", "-", "0.4h"),
    ("no_gol", "finalização que exigiu o goleiro ou entrou", "bool", "0.4h"),
]


def run_pipeline(match_id: int, data_dir: Path) -> dict:
    """Roda a camada 0 completa para uma partida e materializa os artefatos.

    Saída:
        dict de contagens/tempos da execução (vai para o _meta.json e para
        as tabelas de docs/01-pipeline.md).
    """
    t0 = time.perf_counter()
    raw_dir = data_dir / "raw"
    processed = data_dir / "processed"
    models_dir = data_dir / "models"
    processed.mkdir(parents=True, exist_ok=True)

    # Passo 0.1: aquisição + kloppy
    files = statsbomb_loader.download_match(match_id, raw_dir)
    dataset = statsbomb_loader.load_kloppy_events(files)
    kloppy_counts = statsbomb_loader.event_type_counts(dataset)
    n_events = sum(kloppy_counts.values())

    # Passo 0.2: SPADL
    actions = spadl_transform.convert_to_spadl(dataset, match_id)
    spadl_counts = actions["type_name"].value_counts().to_dict()

    # nomes de jogador/time via loader local do socceraction (mesmo cache bruto)
    loader = StatsBombLoader(getter="local", root=str(raw_dir / "statsbomb"))
    comp_id, season_id = statsbomb_loader.WORLD_CUP_2022
    games = loader.games(comp_id, season_id)
    game = games[games.game_id == match_id].iloc[0]
    players = loader.players(match_id)
    teams = loader.teams(match_id)
    actions = actions.merge(players[["player_id", "player_name"]], on="player_id", how="left")
    actions = actions.merge(teams[["team_id", "team_name"]], on="team_id", how="left")

    # Passo 0.3: valoração (modelos cacheados; treina uma vez se necessário)
    xt_model, vaep_model = _load_models(models_dir, raw_dir, loader, games)
    actions = spadl_transform.add_xt(actions, xt_model)
    actions = spadl_transform.add_vaep(actions, vaep_model, game)

    # Passo 0.4: métricas contextuais
    actions = tactical_metrics.add_zones(actions)
    actions = tactical_metrics.add_possession_phases(actions)
    actions = tactical_metrics.add_progressive_flag(actions)
    actions = tactical_metrics.add_pass_receivers(actions)
    phases = tactical_metrics.phase_summary(actions)
    windows = tactical_metrics.windowed_team_metrics(actions)
    pressures = pressure_events.extract_pressures(files.events)

    team_ids = list(actions["team_id"].unique())
    team_metrics = {
        int(t): {
            "ppda_p1": tactical_metrics.compute_ppda(actions, t, 1),
            "ppda_p2": tactical_metrics.compute_ppda(actions, t, 2),
            "field_tilt": tactical_metrics.compute_field_tilt(actions, t),
        }
        for t in team_ids
    }

    # Passo 0.4h: vocabulário de futebol + resgate do que o SPADL descarta.
    # Fica por último de propósito: as linhas de cartão recuperadas do bruto
    # não têm bola e não podem entrar em segmentação de posse, janela móvel
    # nem PPDA — só no log de ações do grafo.
    actions = football_semantics.add_football_semantics(actions)
    actions = football_semantics.enrich_from_statsbomb(actions, files.events)

    # Passo 0.5: materialização
    actions.to_parquet(processed / f"{match_id}.parquet", index=False)
    phases.to_parquet(processed / f"{match_id}_phases.parquet", index=False)
    windows.to_parquet(processed / f"{match_id}_windows.parquet", index=False)
    pressures.to_parquet(processed / f"{match_id}_pressures.parquet", index=False)

    schema = [
        {"coluna": name, "tipo": str(actions[name].dtype) if name in actions else "?", "descricao": desc, "unidade": unit, "passo_origem": step}
        for name, desc, unit, step in SCHEMA_DOC
    ]
    (processed / f"{match_id}_schema.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False))

    meta = {
        "match_id": match_id,
        "home_team": str(game.home_team_id),
        "teams": {int(t.team_id): t.team_name for t in teams.itertuples()},
        # posição nominal da escalação (para o insight 7.5, papel_divergente)
        "player_positions": {
            str(int(p.player_id)): p.starting_position_name for p in players.itertuples()
        },
        "kloppy_event_counts": kloppy_counts,
        "n_kloppy_events": n_events,
        "n_spadl_actions": len(actions),
        "n_discarded": n_events - len(actions),
        "spadl_type_counts": {k: int(v) for k, v in spadl_counts.items()},
        "n_phases": len(phases),
        # contagens do passo 0.4h — o que o vocabulário de futebol enxerga
        "acao_counts": {k: int(v) for k, v in actions["acao"].value_counts().items()},
        "n_gols": int(actions["gol"].sum()),
        "n_cartoes_amarelos": int(actions["cartao_amarelo"].sum()),
        "n_finalizacoes_no_gol": int(actions["no_gol"].sum()),
        "n_passes_with_receiver": int(actions["receiver_player_id"].notna().sum()),
        "n_pressures": len(pressures),
        "n_pressures_with_target": int(pressures["target_player_id"].notna().sum()) if len(pressures) else 0,
        "team_metrics": team_metrics,
        "elapsed_seconds": round(time.perf_counter() - t0, 2),
    }
    (processed / f"{match_id}_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=float))
    logger.info("pipeline %s: %d eventos -> %d ações em %.1fs", match_id, n_events, len(actions), meta["elapsed_seconds"])
    return meta


def _load_models(models_dir: Path, raw_dir: Path, loader: StatsBombLoader, games: pd.DataFrame):
    """Carrega (ou treina uma vez e cacheia) os modelos de xT e VAEP."""
    training_games = games[games.game_id.isin(DEFAULT_TRAINING_MATCH_IDS)]
    need_xt_fit = not (models_dir / spadl_transform.XT_GRID_FILE).exists() and not (
        models_dir / spadl_transform.XT_FITTED_FILE
    ).exists()
    need_vaep_fit = not (models_dir / spadl_transform.VAEP_MODEL_FILE).exists()

    training_actions = None
    if need_xt_fit or need_vaep_fit:
        for gid in training_games.game_id:
            statsbomb_loader.download_match(int(gid), raw_dir)
    if need_xt_fit:
        import socceraction.spadl as spadl

        parts = []
        for _, g in training_games.iterrows():
            events = loader.events(g.game_id)
            acts = spadl.statsbomb.convert_to_actions(events, home_team_id=g.home_team_id)
            parts.append(spadl.add_names(acts))
        training_actions = pd.concat(parts, ignore_index=True)

    xt_model = spadl_transform.load_or_fit_xt(models_dir, training_actions)
    vaep_model = spadl_transform.load_or_train_vaep(models_dir, loader, training_games)
    return xt_model, vaep_model

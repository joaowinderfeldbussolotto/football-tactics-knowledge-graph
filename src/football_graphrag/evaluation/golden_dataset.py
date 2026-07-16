"""Golden dataset de perguntas táticas (seção 8 do plano).

As respostas de referência não são hardcoded: são computadas em cima do
parquet/JSON já processados (`data/processed/{match_id}.parquet` e
`{match_id}_summary.json`), usando as mesmas funções de `tactical_metrics`
já validadas no pipeline de ingestão. Isso é o que torna a resposta
"verificada contra os dados reais" da partida efetivamente ingerida,
em vez de um número fixo que poderia não bater com outra partida.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from football_graphrag.ingestion.pipeline import DATA_PROCESSED_DIR


@dataclass
class GoldenQuestion:
    id: str
    match_id: str
    question: str
    reference_answer: str


def _load_match_data(match_id: str, processed_dir: Path) -> tuple[pd.DataFrame, dict]:
    actions = pd.read_parquet(processed_dir / f"{match_id}.parquet")
    summary = json.loads((processed_dir / f"{match_id}_summary.json").read_text())
    return actions, summary


def _team_name(summary: dict, team_id: str) -> str:
    return summary["teams"][team_id]["name"]


def build_golden_dataset(match_id: str, processed_dir: Path = DATA_PROCESSED_DIR) -> list[GoldenQuestion]:
    """Gera as perguntas do golden dataset para uma partida já processada."""
    actions, summary = _load_match_data(match_id, processed_dir)
    team_ids = list(summary["teams"].keys())
    team_summaries = {ts["team_id"]: ts for ts in summary["team_summaries"]}

    questions: list[GoldenQuestion] = []

    # 1. Time mandante / visitante.
    home_id = next(tid for tid, t in summary["teams"].items() if t["ground"] == "home")
    away_id = next(tid for tid, t in summary["teams"].items() if t["ground"] == "away")
    questions.append(
        GoldenQuestion(
            id="mandante_visitante",
            match_id=match_id,
            question=f"Na partida {match_id}, qual time era o mandante e qual era o visitante?",
            reference_answer=f"Mandante: {_team_name(summary, home_id)}. Visitante: {_team_name(summary, away_id)}.",
        )
    )

    # 2. Time com pressão mais intensa (menor PPDA).
    ppda_by_team = {tid: team_summaries[tid]["ppda"] for tid in team_ids if team_summaries[tid]["ppda"] is not None}
    if ppda_by_team:
        most_intense = min(ppda_by_team, key=ppda_by_team.get)
        questions.append(
            GoldenQuestion(
                id="ppda_mais_intenso",
                match_id=match_id,
                question=f"Na partida {match_id}, qual time pressionou com mais intensidade (menor PPDA)?",
                reference_answer=f"{_team_name(summary, most_intense)} (PPDA={ppda_by_team[most_intense]:.2f}).",
            )
        )

    # 3. Time com maior field tilt.
    tilt_by_team = {
        tid: team_summaries[tid]["field_tilt_pct"] for tid in team_ids if team_summaries[tid]["field_tilt_pct"] is not None
    }
    if tilt_by_team:
        dominant = max(tilt_by_team, key=tilt_by_team.get)
        questions.append(
            GoldenQuestion(
                id="field_tilt_dominante",
                match_id=match_id,
                question=f"Na partida {match_id}, qual time dominou territorialmente o terço de ataque (maior field tilt)?",
                reference_answer=f"{_team_name(summary, dominant)} ({tilt_by_team[dominant]:.1f}% de field tilt).",
            )
        )

    # 4. Corredor de progressão mais usado por cada time.
    for team_id in team_ids:
        team_progressive = actions[(actions["team_id"] == team_id) & actions["progressive"]]
        if len(team_progressive) == 0:
            continue
        top_corridor = team_progressive["corridor"].value_counts().idxmax()
        questions.append(
            GoldenQuestion(
                id=f"corredor_progressao_{team_id}",
                match_id=match_id,
                question=(
                    f"Na partida {match_id}, qual foi o corredor de progressão mais usado pelo "
                    f"{_team_name(summary, team_id)}?"
                ),
                reference_answer=f"Corredor {top_corridor}.",
            )
        )

    # 5. Número de fases de posse da partida.
    questions.append(
        GoldenQuestion(
            id="n_fases_posse",
            match_id=match_id,
            question=f"Quantas fases de posse teve a partida {match_id}?",
            reference_answer=f"{summary['n_possession_phases']} fases de posse.",
        )
    )

    # 6. Jogador com maior xT total gerado via passes.
    xt_by_player = (
        actions[actions["type_name"] == "pass"].groupby("player_name")["xt_value"].sum().sort_values(ascending=False)
    )
    if len(xt_by_player) > 0 and xt_by_player.iloc[0] != 0:
        top_player = xt_by_player.index[0]
        questions.append(
            GoldenQuestion(
                id="maior_xt_passes",
                match_id=match_id,
                question=f"Na partida {match_id}, qual jogador gerou mais xT total com passes?",
                reference_answer=f"{top_player} (xT total={xt_by_player.iloc[0]:.3f}).",
            )
        )

    # 7. Jogador com maior VAEP total.
    vaep_by_player = actions.groupby("player_name")["vaep_value"].sum().sort_values(ascending=False)
    if len(vaep_by_player) > 0:
        top_vaep_player = vaep_by_player.index[0]
        questions.append(
            GoldenQuestion(
                id="maior_vaep",
                match_id=match_id,
                question=f"Na partida {match_id}, qual jogador teve o maior VAEP total?",
                reference_answer=f"{top_vaep_player} (VAEP total={vaep_by_player.iloc[0]:.3f}).",
            )
        )

    # 8. Jogador com maior centralidade de intermediação na rede de passes.
    for team_id in team_ids:
        network = summary["passing_networks"].get(team_id, [])
        if not network:
            continue
        top_betweenness = max(network, key=lambda row: row["betweenness"])
        questions.append(
            GoldenQuestion(
                id=f"maior_betweenness_{team_id}",
                match_id=match_id,
                question=(
                    f"Na partida {match_id}, qual jogador do {_team_name(summary, team_id)} teve maior "
                    f"centralidade de intermediação (betweenness) na rede de passes?"
                ),
                reference_answer=f"{top_betweenness['name']} (betweenness={top_betweenness['betweenness']:.3f}).",
            )
        )

    # 9. Ação mais comum de encerramento de fase de posse.
    phase_endings = actions.drop_duplicates(subset="phase_id", keep="last")["type_name"].value_counts()
    if len(phase_endings) > 0:
        questions.append(
            GoldenQuestion(
                id="fim_fase_mais_comum",
                match_id=match_id,
                question=f"Na partida {match_id}, qual ação encerrou mais fases de posse?",
                reference_answer=f"{phase_endings.idxmax()} ({int(phase_endings.max())} vezes).",
            )
        )

    return questions

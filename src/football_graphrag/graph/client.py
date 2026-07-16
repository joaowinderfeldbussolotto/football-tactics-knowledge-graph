"""Inicialização do Graphiti e ingestão de partidas processadas no grafo.

`ingest_match` cobre os dois modos descritos na seção 6.4 do plano da PoC:

- `batch`: itera o parquet processado inteiro de uma partida, fase de posse
  por fase de posse, em ordem cronológica.
- `replay`: ingere uma única fase de posse por chamada — é o que o worker
  consumidor da fila Redis (`ingestion/replay.py`) chama a cada evento
  retirado da fila.

As duas rotas convergem no mesmo `ingest_possession_phase`, para que o texto
do episode e os tipos de entidade/aresta usados sejam idênticos nos dois
modos; a única diferença é de onde vêm os dados (arquivo vs. fila).

Ações são agrupadas por fase de posse (em vez de uma ação = um episode) para
reduzir o número de chamadas de LLM na extração, conforme sugerido na seção
6.4 do plano.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from graphiti_core import Graphiti
from graphiti_core.edges import EntityEdge
from graphiti_core.graphiti import AddEpisodeResults
from graphiti_core.nodes import EpisodeType

from football_graphrag.config import Settings
from football_graphrag.graph.edges import EDGE_TYPE_MAP, EDGE_TYPES
from football_graphrag.graph.entities import ENTITY_TYPES
from football_graphrag.ingestion.pipeline import DATA_PROCESSED_DIR, load_match_summary
from football_graphrag.llm.provider import build_graphiti as _build_graphiti

logger = logging.getLogger(__name__)

# Data-âncora usada quando não há data real de partida disponível: só a
# ordem relativa entre reference_time importa para o Graphiti resolver
# temporalidade dentro de um `group_id`, não a data em si.
_DEFAULT_KICKOFF = datetime(2000, 1, 1, tzinfo=timezone.utc)

MATCH_GROUP_PREFIX = "match-"


def group_id_for_match(match_id: str) -> str:
    return f"{MATCH_GROUP_PREFIX}{match_id}"


def build_graphiti(settings: Settings) -> Graphiti:
    """Reexporta `llm.provider.build_graphiti` por conveniência (ver seção 5.1
    do plano: a escolha de provedor não deve vazar para fora de `llm/`)."""
    return _build_graphiti(settings)


async def get_match_facts(
    graphiti: Graphiti,
    match_id: str,
    query: str,
    num_results: int = 15,
) -> list[EntityEdge]:
    """Busca híbrida (bm25 + similaridade de embeddings, sem LLM) restrita ao
    `group_id` da partida. Usada tanto para os "fatos candidatos" que
    embasam `TacticalReport.cited_metrics` (seções 7/8) quanto para o
    retrieval de `/live/{match_id}/insights` (seção 9, critério 3: deve
    responder em menos de 1s)."""
    return await graphiti.search(query=query, group_ids=[group_id_for_match(match_id)], num_results=num_results)


@dataclass
class PhaseIngestSummary:
    match_id: str
    phase_id: int
    n_actions: int
    result: AddEpisodeResults


def _phase_reference_time(period_id: int, start_time_seconds: float, kickoff: datetime) -> datetime:
    period_offset = timedelta(minutes=45 * max(int(period_id) - 1, 0))
    return kickoff + period_offset + timedelta(seconds=float(start_time_seconds))


def _format_action_line(row: pd.Series) -> str:
    player = row.get("player_name") or "jogador não identificado"
    parts = [f"- {player} ({row['type_name']}, {row['result_name']})"]
    if row.get("corridor"):
        parts.append(f"corredor {row['corridor']}")
    if bool(row.get("progressive")):
        parts.append("progressivo")
    xt = row.get("xt_value")
    if pd.notna(xt) and xt:
        parts.append(f"xT {xt:+.3f}")
    vaep = row.get("vaep_value")
    if pd.notna(vaep):
        parts.append(f"VAEP {vaep:+.3f}")
    return " | ".join(parts)


def build_phase_episode_body(phase_actions: pd.DataFrame) -> str:
    """Narrativa em português de uma fase de posse, usada como corpo do
    episode. O texto precisa mencionar explicitamente os fatos que os tipos
    de entidade/aresta em `graph/entities.py`/`graph/edges.py` esperam
    extrair (nomes, times, corredores, valores de xT/VAEP)."""
    first = phase_actions.iloc[0]
    last = phase_actions.iloc[-1]

    team = first.get("team_name") or first["team_id"]
    minute = first["time_seconds"] / 60.0
    duration = last["time_seconds"] - first["time_seconds"]

    header = (
        f"Fase de posse do {team} no {int(first['period_id'])}º tempo, "
        f"a partir do minuto {minute:.1f} (duração de {duration:.1f}s, {len(phase_actions)} ações). "
        f"A fase terminou em: {last['type_name']} ({last['result_name']})."
    )
    lines = [_format_action_line(row) for _, row in phase_actions.iterrows()]
    return header + "\n" + "\n".join(lines)


async def ingest_possession_phase(
    graphiti: Graphiti,
    match_id: str,
    phase_id: int,
    phase_actions: pd.DataFrame,
    kickoff: datetime = _DEFAULT_KICKOFF,
) -> PhaseIngestSummary:
    """Ingere uma única fase de posse como um episode do Graphiti."""
    first = phase_actions.iloc[0]
    reference_time = _phase_reference_time(first["period_id"], first["time_seconds"], kickoff)
    body = build_phase_episode_body(phase_actions)
    team = first.get("team_name") or str(first["team_id"])

    result = await graphiti.add_episode(
        name=f"{match_id}-phase-{phase_id}",
        episode_body=body,
        source_description=f"StatsBomb match {match_id}, fase de posse {phase_id} ({team})",
        reference_time=reference_time,
        source=EpisodeType.text,
        group_id=group_id_for_match(match_id),
        entity_types=ENTITY_TYPES,
        edge_types=EDGE_TYPES,
        edge_type_map=EDGE_TYPE_MAP,
    )
    logger.info(
        "Ingerida fase %s da partida %s: %d nós, %d arestas novas",
        phase_id, match_id, len(result.nodes), len(result.edges),
    )
    return PhaseIngestSummary(match_id=match_id, phase_id=phase_id, n_actions=len(phase_actions), result=result)


def build_match_summary_episode_body(summary: dict) -> str:
    """Narrativa comparativa com PPDA/field tilt/VAEP agregados por time.

    Sem isso, esses números só existem em `{match_id}_summary.json`, fora do
    grafo: nenhuma pergunta sobre pressão ou dominância territorial pode ser
    respondida via `/report` ou `/ask`, porque o texto de nenhum episode de
    fase de posse os menciona (eles são agregados de partida/período, não de
    ação). Comparar os dois times no mesmo texto também dá ao LLM o contexto
    necessário para extrair `Time -[Pressiona]-> Time` (ver `EDGE_TYPE_MAP`).
    """
    lines = ["Resumo tático agregado da partida (tempo integral), por time."]
    for team_summary in summary.get("team_summaries", []):
        team_id = team_summary.get("team_id")
        team_name = summary.get("teams", {}).get(team_id, {}).get("name", team_id)
        parts = [team_name]
        if team_summary.get("ppda") is not None:
            parts.append(
                f"PPDA {team_summary['ppda']:.2f} "
                "(passes permitidos por ação defensiva; quanto menor, mais intensa a pressão exercida por este time)"
            )
        if team_summary.get("field_tilt_pct") is not None:
            parts.append(f"field tilt {team_summary['field_tilt_pct']:.1f}% (dominância no terço de ataque)")
        if team_summary.get("vaep_total") is not None:
            parts.append(f"VAEP total {team_summary['vaep_total']:.3f}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


async def ingest_match_summary_facts(
    graphiti: Graphiti,
    match_id: str,
    summary: dict,
    kickoff: datetime = _DEFAULT_KICKOFF,
) -> PhaseIngestSummary:
    """Ingere um único episode extra com os agregados por time da partida.

    `reference_time` fica depois de qualquer fase de posse real (2 tempos de
    45min cabem em `_phase_reference_time` com `period_id<=2`), então este
    fato aparece como algo dito "depois" da partida — condizente com só
    fazer sentido chamar isso em modo batch, com a partida já encerrada.
    """
    reference_time = kickoff + timedelta(minutes=200)
    body = build_match_summary_episode_body(summary)

    result = await graphiti.add_episode(
        name=f"{match_id}-team-summary",
        episode_body=body,
        source_description=f"StatsBomb match {match_id}, resumo tático agregado (tempo integral)",
        reference_time=reference_time,
        source=EpisodeType.text,
        group_id=group_id_for_match(match_id),
        entity_types=ENTITY_TYPES,
        edge_types=EDGE_TYPES,
        edge_type_map=EDGE_TYPE_MAP,
    )
    logger.info(
        "Ingerido resumo agregado da partida %s: %d nós, %d arestas novas",
        match_id, len(result.nodes), len(result.edges),
    )
    return PhaseIngestSummary(match_id=match_id, phase_id=-1, n_actions=0, result=result)


async def ingest_match_batch(
    graphiti: Graphiti,
    match_id: str,
    processed_dir: Path = DATA_PROCESSED_DIR,
    kickoff: datetime = _DEFAULT_KICKOFF,
) -> list[PhaseIngestSummary]:
    """Modo batch (seção 6.4): itera o parquet inteiro, fase por fase, em
    ordem cronológica, e depois injeta os agregados por time (PPDA, field
    tilt, VAEP) como um episode final — ver `ingest_match_summary_facts`.
    Só roda em modo batch, nunca em replay: injetar o total da partida no
    meio de uma simulação "ao vivo" vazaria informação do futuro pro grafo
    incremental."""
    parquet_path = processed_dir / f"{match_id}.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"{parquet_path} não existe. Rode `scripts/run_ingestion.py {match_id}` primeiro."
        )

    actions = pd.read_parquet(parquet_path)
    actions = actions.sort_values(["period_id", "time_seconds"])

    summaries = []
    for phase_id, phase_actions in actions.groupby("phase_id", sort=True):
        summary = await ingest_possession_phase(graphiti, match_id, int(phase_id), phase_actions, kickoff)
        summaries.append(summary)

    match_summary = load_match_summary(match_id, processed_dir)
    if match_summary is not None:
        summaries.append(await ingest_match_summary_facts(graphiti, match_id, match_summary, kickoff))
    else:
        logger.warning(
            "Sem %s_summary.json em %s; PPDA/field tilt não serão citáveis no grafo desta partida.",
            match_id, processed_dir,
        )
    return summaries

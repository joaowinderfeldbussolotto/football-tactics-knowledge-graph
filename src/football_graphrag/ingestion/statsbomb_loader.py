"""Passo 0.1: aquisição de dados do StatsBomb Open Data.

Baixa o JSON bruto (events, lineups, three-sixty, matches) para
``data/raw/statsbomb/`` no mesmo layout do repositório open-data, de modo que
o ``StatsBombLoader(getter="local")`` do socceraction e o ``kloppy`` leiam
direto do cache. Nunca rebaixa se o arquivo já existe (contrato do passo 0.1).

Fonte: https://github.com/statsbomb/open-data (licença CC BY-NC 4.0 — uso
não comercial com atribuição; este projeto é acadêmico).
"""

import json
import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from kloppy import statsbomb as kloppy_statsbomb
from kloppy.domain import EventDataset

logger = logging.getLogger(__name__)

OPEN_DATA_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

# Copa do Mundo 2022 (dados 360 disponíveis): competition_id=43, season_id=106.
WORLD_CUP_2022 = (43, 106)


@dataclass(frozen=True)
class RawMatchFiles:
    """Caminhos locais dos arquivos brutos de uma partida."""

    match_id: int
    events: Path
    lineups: Path
    three_sixty: Path | None  # nem toda partida tem 360


def _download(url: str, dest: Path) -> bool:
    """Baixa ``url`` para ``dest`` se ainda não existir. Retorna se baixou."""
    if dest.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    with urllib.request.urlopen(url) as resp:  # noqa: S310 - host fixo do open-data
        tmp.write_bytes(resp.read())
    tmp.rename(dest)
    logger.info("baixado %s -> %s", url, dest)
    return True


def download_match(match_id: int, raw_dir: Path, competition: tuple[int, int] = WORLD_CUP_2022) -> RawMatchFiles:
    """Baixa (com cache) os arquivos brutos de uma partida do open-data.

    Conceito:
        Passo 0.1 da pipeline. O layout de saída replica o repositório
        statsbomb/open-data para que loaders de terceiros funcionem sem
        transformação nenhuma nesta etapa.

    Entrada:
        match_id: id StatsBomb da partida (ex.: 3869685 = final da Copa 2022).
        raw_dir: ``data/raw`` do projeto; os arquivos vão para ``raw_dir/statsbomb/``.
        competition: (competition_id, season_id) para baixar o matches.json.

    Saída:
        RawMatchFiles com os caminhos locais. ``three_sixty`` é None se a
        partida não tiver dados 360 publicados (HTTP 404 é tolerado só aqui).

    Vai para o grafo em:
        Nada diretamente; alimenta os passos 0.2+.
    """
    base = raw_dir / "statsbomb"
    comp_id, season_id = competition
    _download(f"{OPEN_DATA_BASE}/matches/{comp_id}/{season_id}.json", base / "matches" / str(comp_id) / f"{season_id}.json")
    events = base / "events" / f"{match_id}.json"
    lineups = base / "lineups" / f"{match_id}.json"
    _download(f"{OPEN_DATA_BASE}/events/{match_id}.json", events)
    _download(f"{OPEN_DATA_BASE}/lineups/{match_id}.json", lineups)

    three_sixty: Path | None = base / "three-sixty" / f"{match_id}.json"
    assert three_sixty is not None
    try:
        _download(f"{OPEN_DATA_BASE}/three-sixty/{match_id}.json", three_sixty)
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        if exc.code == 404:
            logger.warning("partida %s sem dados 360", match_id)
            three_sixty = None
        else:
            raise
    return RawMatchFiles(match_id=match_id, events=events, lineups=lineups, three_sixty=three_sixty)


def load_kloppy_events(files: RawMatchFiles) -> EventDataset:
    """Passo 0.1b: carrega os eventos brutos no modelo agnóstico do kloppy.

    Conceito:
        O kloppy normaliza eventos de qualquer fornecedor num modelo único
        (EventDataset), com coordenadas padronizadas. É a fronteira entre
        "JSON do fornecedor" e "modelo de eventos do projeto".

    Entrada:
        files: caminhos locais retornados por ``download_match``.

    Saída:
        kloppy EventDataset com todos os tipos de evento (sem filtro de tipo).
        Períodos 1-4 apenas: disputa de pênaltis (período 5) é excluída por
        não ser jogo corrido — não há tática de posse/pressão a modelar
        (contado em docs/01-pipeline.md).

    Vai para o grafo em:
        Nada diretamente; é a entrada do passo 0.2 (SPADL).
    """
    dataset = kloppy_statsbomb.load(
        event_data=str(files.events),
        lineup_data=str(files.lineups),
        # sem filtro de tipos: o descarte acontece (e é contado) no passo 0.2
        event_types=None,
        coordinates="statsbomb",
    )
    return dataset.filter(lambda event: event.period.id <= 4)


def event_type_counts(dataset: EventDataset) -> dict[str, int]:
    """Contagem de eventos por tipo no dataset kloppy (para docs/01-pipeline.md)."""
    counts: dict[str, int] = {}
    for event in dataset.events:
        name = event.event_name or type(event).__name__
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def match_metadata(match_id: int, raw_dir: Path, competition: tuple[int, int] = WORLD_CUP_2022) -> dict:
    """Metadados da partida (times, data, placar) a partir do matches.json bruto."""
    comp_id, season_id = competition
    matches_file = raw_dir / "statsbomb" / "matches" / str(comp_id) / f"{season_id}.json"
    matches = json.loads(matches_file.read_text())
    for match in matches:
        if match["match_id"] == match_id:
            return match
    raise KeyError(f"partida {match_id} não encontrada em {matches_file}")

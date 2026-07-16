"""Download e carregamento de partidas do StatsBomb Open Data.

O JSON bruto é baixado diretamente do repositório GitHub
`statsbomb/open-data` e cacheado em `data/raw/{match_id}/`, para não
depender de re-download em toda execução (seção 6.1 do plano da PoC). O
carregamento em si delega para `kloppy.statsbomb.load`, que normaliza os
eventos para o modelo de domínio vendor-agnostic do kloppy.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from kloppy.domain import EventDataset
from kloppy.io import Source

logger = logging.getLogger(__name__)

_OPEN_DATA_BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

DATA_RAW_DIR = Path("data/raw")


def _raw_match_dir(match_id: str, raw_dir: Path = DATA_RAW_DIR) -> Path:
    match_dir = raw_dir / str(match_id)
    match_dir.mkdir(parents=True, exist_ok=True)
    return match_dir


def download_match(match_id: str, raw_dir: Path = DATA_RAW_DIR, force: bool = False) -> dict[str, Path]:
    """Baixa (ou reaproveita do cache) events/lineups/three-sixty de uma partida.

    Retorna os caminhos locais dos arquivos baixados. `three-sixty` é
    opcional: nem toda partida do StatsBomb Open Data tem dados 360, então
    a ausência (HTTP 404) não é um erro.
    """
    match_dir = _raw_match_dir(match_id, raw_dir)
    paths: dict[str, Path] = {}

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for kind, required in (("events", True), ("lineups", True), ("three-sixty", False)):
            dest = match_dir / f"{kind}.json"
            key = kind.replace("-", "_")
            if dest.exists() and not force:
                paths[key] = dest
                continue

            url = f"{_OPEN_DATA_BASE_URL}/{kind}/{match_id}.json"
            response = client.get(url)
            if response.status_code == 404:
                if required:
                    raise FileNotFoundError(f"StatsBomb open-data não tem '{kind}' para o match {match_id}: {url}")
                logger.info("Sem dados 360 para o match %s, seguindo sem eles.", match_id)
                continue
            response.raise_for_status()
            dest.write_bytes(response.content)
            paths[key] = dest
            logger.info("Baixado %s -> %s", url, dest)

    return paths


def load_match_dataset(match_id: str, raw_dir: Path = DATA_RAW_DIR, force_download: bool = False) -> EventDataset:
    """Baixa (se necessário) e carrega a partida como um `EventDataset` do kloppy."""
    import kloppy.statsbomb as sb

    paths = download_match(match_id, raw_dir, force=force_download)

    three_sixty_source: Source | None = None
    if "three_sixty" in paths:
        three_sixty_source = Source(paths["three_sixty"], skip_if_missing=True)

    return sb.load(
        event_data=paths["events"],
        lineup_data=paths["lineups"],
        three_sixty_data=three_sixty_source,
    )

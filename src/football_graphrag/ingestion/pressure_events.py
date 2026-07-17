"""Passo 0.4g: extração de eventos de pressão do JSON bruto do StatsBomb.

A conversão SPADL descarta eventos de pressão por definição (SPADL só modela
ações com bola). Mas a rede de pressão é insumo dos insights 7.3 (gatilho de
pressão) e 7.8 (alvo real da pressão), então a pressão é materializada aqui
como artefato próprio: ``{match_id}_pressures.parquet``.

Resolução do alvo: o evento Pressure do StatsBomb traz ``related_events``
apontando para o evento sob pressão (passe, condução, recepção do adversário).
O alvo é o ``player`` desse evento relacionado. Pressões sem related_events
resolvível são mantidas com alvo nulo e contadas (docs/01-pipeline.md).

Coordenadas: o StatsBomb registra todo evento no referencial do time
executor atacando da esquerda para a direita (campo 120x80, origem no canto
superior esquerdo, y para baixo). Convertemos para o referencial SPADL
(105x68, y para cima): x_m = x/120*105; y_m = 68 - y/80*68 — a MESMA
convenção das ações, então as zonas são comparáveis.
"""

import json
from pathlib import Path

import pandas as pd

from football_graphrag.ingestion.tactical_metrics import zone_of

STATSBOMB_PRESSURE_TYPE = 17


def extract_pressures(events_file: Path) -> pd.DataFrame:
    """Extrai a rede de pressão de uma partida a partir do JSON bruto.

    Entrada:
        events_file: data/raw/statsbomb/events/{match_id}.json.

    Saída:
        DataFrame: period_id, time_seconds, presser_player_id, presser_player_name,
        presser_team_id, target_player_id, target_player_name, target_team_id,
        x, y (metros, referencial SPADL), zone, duration.

    Vai para o grafo em:
        Aresta PRESSIONOU (Jogador -> Jogador), propriedades minuto/zona.
    """
    events = json.loads(events_file.read_text())
    by_id = {e["id"]: e for e in events}
    rows = []
    for e in events:
        if e["type"]["id"] != STATSBOMB_PRESSURE_TYPE:
            continue
        target = None
        for rel_id in e.get("related_events", []):
            rel = by_id.get(rel_id)
            if rel and rel.get("player") and rel["team"]["id"] != e["team"]["id"]:
                target = rel
                break
        x_raw, y_raw = e.get("location", [None, None])
        x_m = x_raw / 120.0 * 105.0 if x_raw is not None else None
        y_m = 68.0 - (y_raw / 80.0 * 68.0) if y_raw is not None else None
        rows.append(
            {
                "period_id": e["period"],
                "time_seconds": e["minute"] * 60 + e["second"] - (45 * 60 if e["period"] == 2 else 0)
                - (90 * 60 if e["period"] == 3 else 0) - (105 * 60 if e["period"] == 4 else 0),
                "minute": e["minute"],
                "presser_player_id": e["player"]["id"],
                "presser_player_name": e["player"]["name"],
                "presser_team_id": e["team"]["id"],
                "target_player_id": target["player"]["id"] if target else None,
                "target_player_name": target["player"]["name"] if target else None,
                "target_team_id": target["team"]["id"] if target else None,
                "x": x_m,
                "y": y_m,
                "duration": e.get("duration"),
            }
        )
    df = pd.DataFrame(rows)
    if len(df) > 0:
        df["zone"] = zone_of(df["x"].fillna(0), df["y"].fillna(0)).where(df["x"].notna())
    else:
        df["zone"] = pd.Series(dtype="float64")
    return df

"""Passo 0.4: métricas contextuais determinísticas sobre as ações SPADL.

Todas as fórmulas têm referência citada na docstring. Métrica sem fórmula
documentada não entra (regra da seção 10 do plano). A partir do passo 0.5
nada mais é calculado: se um insight precisar de um número novo, ele nasce
aqui e é rematerializado no parquet.

Convenção de coordenadas (herdada do SPADL): campo 105x68m, origem no canto
inferior esquerdo, ataque SEMPRE da esquerda para a direita para os dois
times. Com essa convenção, o corredor "esquerdo" do ataque é y alto
(y > 45.33) e o "direito" é y baixo (y < 22.67).
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
GRID_COLS = 12  # alinhado à grade 12x8 do xT (Karun Singh, 2018)
GRID_ROWS = 8

# Tipos SPADL considerados "ação defensiva" no PPDA (Trainor/StatsBomb 2014
# usa tackles + interceptions + challenges + fouls; em SPADL: tackle,
# interception, foul; "challenge" não existe como tipo separado).
DEFENSIVE_ACTION_TYPES = ("tackle", "interception", "foul")

# Tipos SPADL que encerram uma fase de posse mesmo sem troca de time.
PHASE_BREAKERS = ("foul", "shot", "shot_penalty", "shot_freekick", "keeper_save", "clearance", "bad_touch")


def zone_of(x: pd.Series, y: pd.Series) -> pd.Series:
    """Discretiza coordenadas na grade 12x8 (zona 0..95).

    Fórmula:
        col = floor(x / (105/12)), clip [0,11]; row = floor(y / (68/8)),
        clip [0,7]; zona = col * 8 + row. Grade idêntica à do xT para que
        zona do grafo e célula de xT sejam a mesma entidade.

    Vai para o grafo em:
        Nó ``Zona`` (id_zona) e propriedades zona_origem/zona_destino
        das arestas.
    """
    col = np.clip((x / (PITCH_LENGTH / GRID_COLS)).astype(int), 0, GRID_COLS - 1)
    row = np.clip((y / (PITCH_WIDTH / GRID_ROWS)).astype(int), 0, GRID_ROWS - 1)
    return col * GRID_ROWS + row


def zone_band(zone: int) -> str:
    """Faixa longitudinal da zona: defesa (cols 0-3), meio (4-7), ataque (8-11)."""
    col = zone // GRID_ROWS
    return "defesa" if col < 4 else ("meio" if col < 8 else "ataque")


def zone_channel(zone: int) -> str:
    """Corredor da zona na convenção SPADL: rows 0-2 direita, 3-4 centro, 5-7 esquerda."""
    row = zone % GRID_ROWS
    return "direita" if row < 3 else ("centro" if row < 5 else "esquerda")


def add_zones(actions: pd.DataFrame) -> pd.DataFrame:
    """Adiciona zone_start e zone_end a cada ação (passo 0.4a)."""
    out = actions.copy()
    out["zone_start"] = zone_of(out["start_x"], out["start_y"])
    out["zone_end"] = zone_of(out["end_x"], out["end_y"])
    return out


def add_possession_phases(actions: pd.DataFrame) -> pd.DataFrame:
    """Segmenta a partida em fases de posse ininterruptas (passo 0.4b).

    Conceito:
        Uma fase de posse é uma sequência de ações do mesmo time, no mesmo
        período, sem interrupção. Nova fase quando: (a) o time da ação muda;
        (b) o período muda; (c) a ação anterior é um encerrador (falta,
        finalização, defesa do goleiro, corte — PHASE_BREAKERS).

    Fórmula:
        possession_id = soma cumulativa dos pontos de quebra definidos acima.
        Determinístico e reprodutível linha a linha.

    Referência:
        Definição própria simplificada, inspirada na segmentação de posse do
        StatsBomb (possession chains) — documentada em docs/01-pipeline.md.

    Vai para o grafo em:
        Nó ``FaseDePosse`` e propriedade fase_posse_id das arestas.
    """
    out = actions.copy()
    team_changed = out["team_id"].ne(out["team_id"].shift())
    period_changed = out["period_id"].ne(out["period_id"].shift())
    prev_breaker = out["type_name"].shift().isin(PHASE_BREAKERS)
    out["possession_id"] = (team_changed | period_changed | prev_breaker).cumsum()
    return out


def add_progressive_flag(actions: pd.DataFrame) -> pd.DataFrame:
    """Marca passes/conduções progressivos (passo 0.4c), definição Wyscout.

    Conceito:
        Uma ação de movimento é progressiva se aproxima a bola do gol
        adversário de forma substancial, com limiares que dependem de onde
        ela acontece.

    Fórmula (Wyscout glossary, "progressive pass"):
        dist(p) = distância euclidiana de p ao centro do gol adversário
        (105, 34). Progressivo se dist(start) - dist(end) >=
          30m se início e fim no campo próprio;
          15m se cruzando a linha do meio;
          10m se início e fim no campo adversário.

    Referência:
        https://dataglossary.wyscout.com/progressive_pass/

    Vai para o grafo em:
        Propriedade ``progressivo`` da aresta PASSOU_PARA.
    """
    out = actions.copy()
    goal_x, goal_y = PITCH_LENGTH, PITCH_WIDTH / 2
    d_start = np.hypot(goal_x - out["start_x"], goal_y - out["start_y"])
    d_end = np.hypot(goal_x - out["end_x"], goal_y - out["end_y"])
    gain = d_start - d_end
    own_half = (out["start_x"] < PITCH_LENGTH / 2) & (out["end_x"] < PITCH_LENGTH / 2)
    opp_half = (out["start_x"] >= PITCH_LENGTH / 2) & (out["end_x"] >= PITCH_LENGTH / 2)
    threshold = np.where(own_half, 30.0, np.where(opp_half, 10.0, 15.0))
    movable = out["type_name"].isin(["pass", "cross", "dribble", "carry", "freekick_short", "corner_short", "throw_in", "goalkick"])
    out["progressive"] = movable & (gain >= threshold)
    return out


def add_pass_receivers(actions: pd.DataFrame) -> pd.DataFrame:
    """Resolve o recebedor de cada passe bem-sucedido (passo 0.4d).

    Conceito:
        SPADL não traz o recebedor explícito; por construção, o recebedor de
        um passe bem-sucedido é o jogador do MESMO time que executa a ação
        seguinte. Se a ação seguinte é de outro time (apesar de result=success),
        o recebedor fica indefinido (NaN) e o passe não vira aresta
        PASSOU_PARA — contado em docs/01-pipeline.md.

    Vai para o grafo em:
        Extremidade destino da aresta PASSOU_PARA.
    """
    out = actions.copy()
    next_player = out["player_id"].shift(-1)
    next_team = out["team_id"].shift(-1)
    pass_like = out["type_name"].isin(
        ["pass", "cross", "freekick_short", "corner_short", "throw_in", "goalkick", "freekick_crossed", "corner_crossed"]
    )
    ok = pass_like & (out["result_name"] == "success") & (next_team == out["team_id"])
    out["receiver_player_id"] = np.where(ok, next_player, np.nan)
    return out


def compute_ppda(actions: pd.DataFrame, team_id: int, period_id: int | None = None) -> float:
    """Calcula PPDA (Passes Permitidos Por Ação Defensiva).

    Conceito:
        Mede intensidade de pressão. Quanto MENOR, mais o time pressiona:
        poucos passes do adversário são permitidos antes de uma ação
        defensiva. Valor típico na elite europeia: 8 a 14.

    Fórmula:
        PPDA = (passes do adversário nos 60% iniciais do campo DELE)
               / (ações defensivas do time analisado nesse mesmo espaço).
        Como o SPADL normaliza ataque da esquerda para a direita por time:
        passes do adversário com start_x <= 63m (60% de 105) no referencial
        dele; ações defensivas do time analisado com start_x >= 42m no
        referencial do analisado (os dois recortes são o mesmo espaço físico).

    Entrada:
        actions: DataFrame SPADL com type_name/team_id/start_x/period_id.
        team_id: time analisado (que pressiona).
        period_id: 1 ou 2; None = partida inteira.

    Saída:
        float adimensional. NaN se não houver ação defensiva no recorte
        (caso documentado, não silenciado).

    Referência:
        Colin Trainor & Constantinos Chappas, StatsBomb, 2014
        ("Defensive Metrics: Measuring the Intensity of a High Press").

    Vai para o grafo em:
        Propriedade ``ppda`` (por período) do nó Time, e série em janelas
        para o insight 7.7 (mudanca_estado).
    """
    df = actions if period_id is None else actions[actions["period_id"] == period_id]
    opp_passes = df[
        (df["team_id"] != team_id) & (df["type_name"] == "pass") & (df["start_x"] <= 0.6 * PITCH_LENGTH)
    ]
    def_actions = df[
        (df["team_id"] == team_id)
        & df["type_name"].isin(DEFENSIVE_ACTION_TYPES)
        & (df["start_x"] >= 0.4 * PITCH_LENGTH)
    ]
    if len(def_actions) == 0:
        return float("nan")
    return len(opp_passes) / len(def_actions)


def compute_field_tilt(actions: pd.DataFrame, team_id: int, period_id: int | None = None) -> float:
    """Calcula field tilt (% dos passes no terço final que são do time).

    Conceito:
        Mede domínio territorial: quem joga no campo de quem. 50% = equilíbrio.

    Fórmula:
        field_tilt(T) = passes de T no terço final de T
                        / (passes de T no terço final de T +
                           passes do adversário no terço final do adversário).
        Terço final no SPADL: start_x >= 70m no referencial de quem passa.

    Saída:
        float em [0,1]. NaN se nenhum dos dois times passou no terço final.

    Referência:
        Definição popularizada por analistas do StatsBomb/The Athletic
        (ex.: https://theanalyst.com/eu/2021/07/what-is-field-tilt/, Opta).

    Vai para o grafo em:
        Propriedade ``field_tilt`` do nó Time e série em janelas (insight 7.7).
    """
    df = actions if period_id is None else actions[actions["period_id"] == period_id]
    final_third = df[(df["type_name"] == "pass") & (df["start_x"] >= 2 / 3 * PITCH_LENGTH)]
    own = (final_third["team_id"] == team_id).sum()
    total = len(final_third)
    if total == 0:
        return float("nan")
    return own / total


def windowed_team_metrics(actions: pd.DataFrame, window_min: float = 10.0, step_min: float = 5.0) -> pd.DataFrame:
    """Série de métricas por janela móvel, insumo do insight 7.7 (passo 0.4e).

    Conceito:
        PPDA e field tilt da partida inteira são médias que escondem mudanças
        de comportamento. Janelas móveis (10 min, passo 5) preservam a
        dinâmica; a detecção de ponto de quebra acontece na camada 2, mas o
        NÚMERO nasce aqui (contrato do passo 0.5).

    Saída:
        DataFrame: team_id, window_start_min, window_end_min, ppda,
        field_tilt, n_actions. Janela sem ação defensiva tem ppda NaN.
    """
    out = []
    df = actions.copy()
    # minuto absoluto de jogo: períodos concatenados pelo tempo real decorrido
    period_offset = df.groupby("period_id")["time_seconds"].max().cumsum().shift(fill_value=0.0)
    df["abs_minute"] = (df["period_id"].map(period_offset) + df["time_seconds"]) / 60.0
    max_min = df["abs_minute"].max()
    for team_id in df["team_id"].unique():
        start = 0.0
        while start < max_min:
            end = start + window_min
            window = df[(df["abs_minute"] >= start) & (df["abs_minute"] < end)]
            out.append(
                {
                    "team_id": team_id,
                    "window_start_min": start,
                    "window_end_min": min(end, max_min),
                    "ppda": compute_ppda(window, team_id),
                    "field_tilt": compute_field_tilt(window, team_id),
                    "n_actions": int((window["team_id"] == team_id).sum()),
                }
            )
            start += step_min
    return pd.DataFrame(out)


def phase_summary(actions: pd.DataFrame) -> pd.DataFrame:
    """Resumo por fase de posse (passo 0.4f): vira o nó FaseDePosse.

    Saída:
        DataFrame: possession_id, team_id, period_id, minute_start,
        minute_end, zone_start, zone_end, xt_total, n_actions, n_players.
    """
    grouped = actions.groupby("possession_id")
    summary = grouped.agg(
        team_id=("team_id", "first"),
        period_id=("period_id", "first"),
        second_start=("time_seconds", "first"),
        second_end=("time_seconds", "last"),
        zone_start=("zone_start", "first"),
        zone_end=("zone_end", "last"),
        xt_total=("xt_value", "sum"),
        n_actions=("type_name", "size"),
        n_players=("player_id", "nunique"),
    ).reset_index()
    summary["minute_start"] = summary["second_start"] / 60.0
    summary["minute_end"] = summary["second_end"] / 60.0
    return summary.drop(columns=["second_start", "second_end"])

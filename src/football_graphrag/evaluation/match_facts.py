"""Súmula da partida em pandas, para alimentar o BASELINE.

Por que este módulo existe
--------------------------
A comparação central do trabalho é grafo versus RAG vetorial plano. Para ela
significar alguma coisa, os dois lados precisam ter os MESMOS FATOS —
a diferença tem que ser a REPRESENTAÇÃO (grafo consultável versus texto
embeddado), não o volume de dado disponível.

Sem este módulo a comparação estava desequilibrada: a camada 1b deu ao grafo
um ``EstatisticaJogador`` com ~30 contagens por jogador, enquanto o resumo do
baseline tinha passes, PPDA, field tilt, xT/VAEP e os 5 maiores passadores.
Nas perguntas factuais o baseline perdia porque o dado NÃO EXISTIA para ele —
o que não é evidência de nada sobre grafos.

Relação com graph/statistics.py
-------------------------------
As contagens abaixo espelham, campo a campo, as de ``_AGG_JOGADOR`` e
``_AGG_TIME``. Lá elas são feitas em Cypher sobre as arestas; aqui em pandas
sobre o parquet. A duplicação é deliberada: o baseline não pode depender do
grafo, senão deixa de ser um baseline independente.

O que impede as duas de divergirem em silêncio é
``tests/test_baseline_parity.py``, que compara jogador a jogador os números
daqui com os do nó ``EstatisticaJogador`` e falha em qualquer diferença.
"""

import pandas as pd

# Mesmos grupos que _AGG_JOGADOR usa no Cypher.
GRUPOS_PASSE = ("passe", "bola_parada")


def _flag(df: pd.DataFrame, mask: pd.Series) -> int:
    return int(mask.sum()) if len(df) else 0


def resumo_por_jogador(actions: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por jogador, com as mesmas contagens de EstatisticaJogador.

    Entrada:
        actions: parquet da partida já com o vocabulário de futebol
        (passo 0.4h — colunas ``acao``, ``grupo_acao``, ``sucesso``...).

    Saída:
        DataFrame indexado por player_id, colunas com os mesmos nomes do nó
        EstatisticaJogador.
    """
    df = actions.dropna(subset=["player_id"]).copy()
    passe = df["grupo_acao"].isin(GRUPOS_PASSE)
    final = df["grupo_acao"].eq("finalizacao")

    df["_passe_tent"] = passe
    df["_passe_certo"] = passe & df["sucesso"]
    df["_passe_prog"] = passe & df["sucesso"] & df["progressive"].fillna(False)
    df["_cruz_tent"] = df["acao"].eq("cruzamento")
    df["_cruz_certo"] = df["_cruz_tent"] & df["sucesso"]
    df["_conducao"] = df["acao"].eq("conducao")
    df["_drible_tent"] = df["acao"].eq("drible")
    df["_drible_certo"] = df["_drible_tent"] & df["sucesso"]
    df["_desarme_tent"] = df["acao"].eq("desarme")
    df["_desarme_certo"] = df["_desarme_tent"] & df["sucesso"]
    df["_interceptacao"] = df["acao"].eq("interceptacao") & df["sucesso"]
    df["_corte"] = df["acao"].eq("corte")
    df["_falta"] = df["acao"].eq("falta_cometida")
    df["_final"] = final
    df["_final_no_gol"] = final & df["no_gol"].fillna(False)
    df["_gol_penalti"] = df["acao"].eq("penalti") & df["gol"]
    df["_defesa_gk"] = df["acao"].eq("defesa_do_goleiro")
    df["_erro_dominio"] = df["acao"].eq("erro_de_dominio")

    agg = df.groupby("player_id").agg(
        nome=("player_name", "first"),
        time=("team_name", "first"),
        toques=("acao", "size"),
        passes_tentados=("_passe_tent", "sum"),
        passes_certos=("_passe_certo", "sum"),
        passes_progressivos=("_passe_prog", "sum"),
        cruzamentos_tentados=("_cruz_tent", "sum"),
        cruzamentos_certos=("_cruz_certo", "sum"),
        conducoes=("_conducao", "sum"),
        dribles_tentados=("_drible_tent", "sum"),
        dribles_certos=("_drible_certo", "sum"),
        desarmes_tentados=("_desarme_tent", "sum"),
        desarmes_certos=("_desarme_certo", "sum"),
        interceptacoes=("_interceptacao", "sum"),
        cortes=("_corte", "sum"),
        faltas_cometidas=("_falta", "sum"),
        cartoes_amarelos=("cartao_amarelo", "sum"),
        finalizacoes=("_final", "sum"),
        finalizacoes_no_gol=("_final_no_gol", "sum"),
        gols=("gol", "sum"),
        gols_de_penalti=("_gol_penalti", "sum"),
        defesas_do_goleiro=("_defesa_gk", "sum"),
        erros_de_dominio=("_erro_dominio", "sum"),
        xt_total=("xt_value", "sum"),
        vaep_total=("vaep_value", "sum"),
    )
    inteiros = [c for c in agg.columns if c not in ("nome", "time", "xt_total", "vaep_total")]
    agg[inteiros] = agg[inteiros].astype(int)
    agg["xt_total"] = agg["xt_total"].round(4)
    agg["vaep_total"] = agg["vaep_total"].round(4)
    agg["assistencias"] = pd.Series(assistencias(actions)).reindex(agg.index).fillna(0).astype(int)
    agg["precisao_passe_pct"] = (
        (100.0 * agg["passes_certos"] / agg["passes_tentados"]).round(1).where(agg["passes_tentados"] > 0)
    )
    return agg


def assistencias(actions: pd.DataFrame) -> dict[int, int]:
    """Assistências por jogador, pela MESMA regra de graph/build.py.

    Assistência = último passe bem-sucedido do mesmo time, na mesma fase de
    posse, cujo recebedor é o autor do gol. Pênalti não tem assistência.
    """
    gols = actions[actions["acao"].isin(["finalizacao", "falta_direta"]) & actions["gol"]]
    contagem: dict[int, int] = {}
    for g in gols.itertuples():
        anteriores = actions[
            (actions["possession_id"] == g.possession_id)
            & (actions["action_id"] < g.action_id)
            & (actions["team_id"] == g.team_id)
            & (actions["receiver_player_id"] == g.player_id)
        ]
        if len(anteriores) == 0:
            continue
        pid = int(anteriores.iloc[-1].player_id)
        contagem[pid] = contagem.get(pid, 0) + 1
    return contagem


def gols_da_partida(actions: pd.DataFrame) -> pd.DataFrame:
    """Os gols em ordem, com autor, time, minuto e tipo."""
    g = actions[actions["gol"]].sort_values(["period_id", "time_seconds"])
    return g[["player_name", "team_name", "minuto", "periodo_nome", "acao"]]


def cartoes_da_partida(actions: pd.DataFrame) -> pd.DataFrame:
    """Os cartões amarelos, com jogador, time e minuto."""
    c = actions[actions["cartao_amarelo"]].sort_values(["period_id", "time_seconds"])
    return c[["player_name", "team_name", "minuto"]]


def resumo_por_time(actions: pd.DataFrame, phases: pd.DataFrame | None = None) -> pd.DataFrame:
    """Uma linha por time, espelhando EstatisticaTime."""
    df = actions.dropna(subset=["team_name"]).copy()
    passe = df["grupo_acao"].isin(GRUPOS_PASSE)
    final = df["grupo_acao"].eq("finalizacao")
    df["_passe_tent"] = passe
    df["_passe_certo"] = passe & df["sucesso"]
    df["_final"] = final
    df["_final_no_gol"] = final & df["no_gol"].fillna(False)
    df["_desarme_certo"] = df["acao"].eq("desarme") & df["sucesso"]
    df["_interceptacao"] = df["acao"].eq("interceptacao") & df["sucesso"]
    df["_drible_certo"] = df["acao"].eq("drible") & df["sucesso"]
    df["_falta"] = df["acao"].eq("falta_cometida")
    df["_terco_final"] = df["terco"].eq("ataque")

    agg = df.groupby("team_name").agg(
        acoes=("acao", "size"),
        passes_tentados=("_passe_tent", "sum"),
        passes_certos=("_passe_certo", "sum"),
        finalizacoes=("_final", "sum"),
        finalizacoes_no_gol=("_final_no_gol", "sum"),
        gols=("gol", "sum"),
        desarmes_certos=("_desarme_certo", "sum"),
        interceptacoes=("_interceptacao", "sum"),
        dribles_certos=("_drible_certo", "sum"),
        faltas_cometidas=("_falta", "sum"),
        cartoes_amarelos=("cartao_amarelo", "sum"),
        acoes_no_terco_final=("_terco_final", "sum"),
        xt_total=("xt_value", "sum"),
        team_id=("team_id", "first"),
    )
    agg = agg.astype({c: int for c in agg.columns if c != "xt_total"})
    agg["xt_total"] = agg["xt_total"].round(4)
    agg["precisao_passe_pct"] = (
        (100.0 * agg["passes_certos"] / agg["passes_tentados"]).round(1).where(agg["passes_tentados"] > 0)
    )
    if phases is not None and len(phases):
        dur = phases.assign(d=phases["minute_end"] - phases["minute_start"]).groupby("team_id")["d"].sum()
        total = dur.sum()
        agg["posse_pct"] = agg["team_id"].map((100.0 * dur / total).round(1)) if total else None
    return agg

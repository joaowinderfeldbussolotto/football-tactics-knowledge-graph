"""Passo 0.4h: tradução do vocabulário SPADL para o vocabulário do futebol.

Por que este módulo existe
--------------------------
O SPADL é um formato de pesquisa. Os nomes dos tipos de ação são em inglês,
alguns são contraintuitivos e o "sucesso" da ação fica escondido numa coluna
separada (``result_name``). Enquanto o grafo falar SPADL, quem consulta o
grafo — humano ou LLM — precisa saber de cor três armadilhas:

1. ``dribble`` NÃO é drible: é CONDUÇÃO de bola (o jogador correndo com ela).
   O drible sobre o marcador é ``take_on``. Na final da Copa há 1005
   ``dribble`` e 54 ``take_on``: quem confunde os dois erra por 20x.
2. ``tackle`` conta TENTATIVAS de desarme, certas e erradas. "Quantos
   desarmes o Enzo fez?" tem duas respostas possíveis (9 tentativas, 5
   certos) e nada no dado diz qual é a certa em português.
3. ``time_seconds`` reinicia a cada período. O gol do Mbappé aos 80 minutos
   está gravado como "minuto 34.4", porque é o minuto 34 do 2º tempo.

A solução adotada aqui é deslocar essa tradução para o DADO, e não para o
prompt: cada ação passa a carregar o nome que um brasileiro usaria, um
booleano ``sucesso`` explícito e o minuto de jogo como aparece na
transmissão. Depois disso, "quantos desarmes certos o Enzo fez" é uma
consulta literal, sem conhecimento prévio nenhum.

Contrato da camada 0 (docs/01-pipeline.md): tudo aqui é determinístico e
materializado no parquet. As camadas 1-3 apenas leem.
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from football_graphrag.ingestion.tactical_metrics import zone_band, zone_channel

logger = logging.getLogger(__name__)

# Minuto em que cada período COMEÇA no relógio da partida. É a mesma
# convenção que o StatsBomb usa no campo ``minute`` e que a transmissão
# mostra na tela: o 2º tempo começa aos 45, a 1ª prorrogação aos 90 e a 2ª
# aos 105 — mesmo que o tempo anterior tenha tido acréscimos.
PERIODO_COMECA_NO_MINUTO = {1: 0, 2: 45, 3: 90, 4: 105, 5: 120}

# Nome de cada período como um torcedor diria.
NOME_DO_PERIODO = {
    1: "1º tempo",
    2: "2º tempo",
    3: "1ª prorrogação",
    4: "2ª prorrogação",
    5: "pênaltis",
}

# SPADL -> português. Vocabulário FECHADO: estes são todos os valores que a
# propriedade ``acao`` pode assumir no grafo. Sem acentos de propósito, para
# que ninguém erre a consulta por causa de cedilha ou til.
ACAO_POR_TIPO_SPADL = {
    # --- bola parada e passes ---
    "pass": "passe",
    "cross": "cruzamento",
    "throw_in": "arremesso_lateral",
    "freekick_short": "falta_cobrada_curta",
    "freekick_crossed": "falta_cobrada_na_area",
    "corner_short": "escanteio_curto",
    "corner_crossed": "escanteio_na_area",
    "goalkick": "tiro_de_meta",
    # --- finalizações ---
    "shot": "finalizacao",
    "shot_penalty": "penalti",
    "shot_freekick": "falta_direta",
    # --- carregar a bola (as duas armadilhas clássicas) ---
    "dribble": "conducao",  # correr com a bola dominada, SEM adversário em cima
    "take_on": "drible",  # passar pelo marcador
    # --- defensivas ---
    "tackle": "desarme",
    "interception": "interceptacao",
    "clearance": "corte",
    # --- erros e infrações ---
    "foul": "falta_cometida",
    "bad_touch": "erro_de_dominio",
    # --- goleiro ---
    "keeper_save": "defesa_do_goleiro",
    "keeper_claim": "goleiro_encaixa",
    "keeper_punch": "goleiro_soca",
    "keeper_pick_up": "goleiro_recolhe",
}

# Agrupamento grosso, para perguntas do tipo "quantas ações defensivas".
GRUPO_POR_ACAO = {
    "passe": "passe",
    "cruzamento": "passe",
    "arremesso_lateral": "passe",
    "falta_cobrada_curta": "bola_parada",
    "falta_cobrada_na_area": "bola_parada",
    "escanteio_curto": "bola_parada",
    "escanteio_na_area": "bola_parada",
    "tiro_de_meta": "passe",
    "finalizacao": "finalizacao",
    "penalti": "finalizacao",
    "falta_direta": "finalizacao",
    "conducao": "conducao",
    "drible": "drible",
    "desarme": "defensiva",
    "interceptacao": "defensiva",
    "corte": "defensiva",
    "falta_cometida": "infracao",
    "erro_de_dominio": "erro",
    "defesa_do_goleiro": "goleiro",
    "goleiro_encaixa": "goleiro",
    "goleiro_soca": "goleiro",
    "goleiro_recolhe": "goleiro",
}

# Parte do corpo, em português.
CORPO_POR_BODYPART = {
    "foot": "pe",
    "head": "cabeca",
    "other": "outro",
    "head/other": "cabeca_ou_outro",
    "foot_left": "pe_esquerdo",
    "foot_right": "pe_direito",
}

# Desfecho da finalização, vindo do StatsBomb bruto (o SPADL só guarda
# gol/não-gol e perde a diferença entre defendida, para fora e bloqueada).
DESFECHO_FINALIZACAO = {
    "Goal": "gol",
    "Saved": "defendida",
    "Saved to Post": "defendida",
    "Saved Off Target": "defendida",
    "Off T": "para_fora",
    "Wayward": "para_fora",
    "Post": "na_trave",
    "Blocked": "bloqueada",
}

# Desfechos que contam como finalização NO GOL (exigiria intervenção do
# goleiro ou entrou). Bola na trave não conta como no gol, por convenção
# Opta/StatsBomb.
DESFECHOS_NO_GOL = {"gol", "defendida"}

ACOES_DEFENSIVAS = ("desarme", "interceptacao", "corte")


def minuto_de_jogo(period_id: pd.Series, time_seconds: pd.Series) -> pd.Series:
    """Minuto de jogo como aparece na transmissão (1, 2, ... 45, 46, ... 120).

    Conceito:
        O relógio de futebol é 1-indexado: o intervalo entre 0:00 e 0:59 é
        "o primeiro minuto", exibido como 1'. E cada período começa num
        minuto fixo, independente dos acréscimos do período anterior.

    Fórmula:
        minuto = comeco_do_periodo + floor(time_seconds / 60) + 1

    Conferência (final da Copa 2022, os 6 gols):
        Messi 22:24 -> 23' | Di María 35:22 -> 36' | Mbappé 79:24 -> 80'
        Mbappé 80:59 -> 81' | Messi 107:58 -> 108' | Mbappé 117:05 -> 118'
        — todos batem com a súmula da FIFA.

    Atenção:
        Nos acréscimos os minutos se sobrepõem entre períodos (o 1º tempo
        pode chegar ao minuto 52 e o 2º começa no 46). Isso é o
        comportamento correto do futebol, não um defeito. Para ORDENAR
        cronologicamente use ``action_id``, que é estritamente sequencial.
    """
    comeco = period_id.map(PERIODO_COMECA_NO_MINUTO).fillna(0)
    return (comeco + np.floor(time_seconds / 60.0) + 1).astype(int)


def segundo_de_jogo(period_id: pd.Series, time_seconds: pd.Series) -> pd.Series:
    """Segundos desde o apito inicial, numa escala contínua e comparável.

    Por que existe além de ``minuto``:
        ``minuto`` é para LER (é o que a transmissão mostra). Este campo é
        para COMPARAR. Qualquer janela temporal — "a pressão veio até 8
        segundos depois do passe" — precisa de uma escala contínua e única.

        Sem ele, o insight de gatilho de pressão comparava o minuto do passe
        (contado dentro do período) com o minuto da pressão (contado desde o
        início da partida). No 1º tempo as duas escalas coincidem por acaso;
        do 2º em diante diferem em 45, 90 ou 105 minutos, e a janela de 8
        segundos nunca fechava. O padrão saía de um join quebrado.

    Fórmula:
        segundo = comeco_do_periodo * 60 + time_seconds
    """
    comeco = period_id.map(PERIODO_COMECA_NO_MINUTO).fillna(0) * 60.0
    return (comeco + time_seconds).astype(float)


def add_football_semantics(actions: pd.DataFrame) -> pd.DataFrame:
    """Adiciona as colunas de vocabulário de futebol ao DataFrame SPADL.

    Colunas criadas:
        acao            nome da ação em português (vocabulário fechado)
        grupo_acao      categoria grossa (passe, defensiva, finalizacao...)
        sucesso         booleano explícito: a ação deu certo?
        minuto          minuto de jogo como na transmissão (para LER)
        segundo         segundos desde o apito inicial (para COMPARAR)
        periodo_nome    "1º tempo", "2ª prorrogação"...
        gol             booleano: esta ação foi um gol?
        cartao_amarelo  booleano: esta ação gerou cartão amarelo
        corpo           parte do corpo em português
        terco           terço do campo onde a ação começou
        corredor        corredor do campo onde a ação começou

    Vai para o grafo em:
        Propriedades da aresta REALIZOU (camada 1) e insumo das
        estatísticas pré-agregadas (camada 1b).
    """
    out = actions.copy()

    desconhecidos = set(out["type_name"].unique()) - set(ACAO_POR_TIPO_SPADL)
    if desconhecidos:
        # Falha alto: um tipo SPADL sem tradução viraria um buraco silencioso
        # no grafo, exatamente o problema que este módulo existe para evitar.
        raise ValueError(
            f"tipos SPADL sem tradução para português: {sorted(desconhecidos)}. "
            "Adicione-os a ACAO_POR_TIPO_SPADL antes de seguir."
        )

    out["acao"] = out["type_name"].map(ACAO_POR_TIPO_SPADL)
    out["grupo_acao"] = out["acao"].map(GRUPO_POR_ACAO)
    out["sucesso"] = out["result_name"] == "success"
    out["minuto"] = minuto_de_jogo(out["period_id"], out["time_seconds"])
    out["segundo"] = segundo_de_jogo(out["period_id"], out["time_seconds"])
    out["periodo_nome"] = out["period_id"].map(NOME_DO_PERIODO)
    out["gol"] = out["grupo_acao"].eq("finalizacao") & out["sucesso"]
    out["cartao_amarelo"] = out["result_name"] == "yellow_card"
    out["corpo"] = out["bodypart_name"].map(CORPO_POR_BODYPART).fillna(out["bodypart_name"])
    out["terco"] = out["zone_start"].map(zone_band)
    out["corredor"] = out["zone_start"].map(zone_channel)
    return out


def enrich_from_statsbomb(actions: pd.DataFrame, events_file: Path) -> pd.DataFrame:
    """Recupera do JSON bruto dois fatos que o SPADL descarta.

    1. Desfecho da finalização (``desfecho`` e ``no_gol``). O SPADL só guarda
       gol/não-gol; StatsBomb distingue defendida, para fora, bloqueada e na
       trave. Sem isso, "quantas finalizações no gol?" não tem resposta.

    2. Cartões de ``bad_behaviour`` (``cartao_amarelo``). O SPADL só enxerga
       cartão que veio junto de uma falta com bola em jogo. Na final da Copa
       2022 isso perde o amarelo do Giroud aos 94' — o grafo dizia 6 amarelos
       quando foram 7 em campo. Cartões de reclamação viram uma linha própria
       de ação (``cartao_por_reclamacao``), já que não há ação com bola
       correspondente no SPADL.

    A junção é por ``original_event_id``, que a conversão SPADL preserva —
    determinística e sem heurística.
    """
    out = actions.copy()
    out["desfecho"] = pd.NA
    out["no_gol"] = False

    if not events_file.exists():
        logger.warning("JSON bruto ausente em %s; sem desfecho de finalização nem cartões extras", events_file)
        return out

    events = json.loads(events_file.read_text())

    # --- 1. desfecho das finalizações ---
    desfecho_por_evento = {
        e["id"]: DESFECHO_FINALIZACAO.get(e["shot"]["outcome"]["name"], "outro")
        for e in events
        if e["type"]["name"] == "Shot" and "shot" in e
    }
    desfechos = out["original_event_id"].map(desfecho_por_evento)
    out["desfecho"] = desfechos
    out["no_gol"] = desfechos.isin(DESFECHOS_NO_GOL).fillna(False)

    # --- 2. cartões que o SPADL não viu ---
    ids_ja_no_spadl = set(out.loc[out["cartao_amarelo"], "original_event_id"].dropna())
    extras = []
    for e in events:
        cartao = None
        for chave in ("foul_committed", "bad_behaviour"):
            detalhe = e.get(chave, {})
            if isinstance(detalhe, dict) and "card" in detalhe:
                cartao = detalhe["card"]["name"]
                break
        if cartao != "Yellow Card" or e["id"] in ids_ja_no_spadl:
            continue
        if e["period"] not in PERIODO_COMECA_NO_MINUTO or e["period"] == 5:
            continue  # disputa de pênaltis não faz parte da partida modelada
        if not e.get("player"):
            continue
        extras.append(
            {
                "game_id": out["game_id"].iloc[0] if len(out) else None,
                "original_event_id": e["id"],
                "period_id": e["period"],
                "time_seconds": e["minute"] * 60 + e["second"]
                - PERIODO_COMECA_NO_MINUTO[e["period"]] * 60,
                "team_id": e["team"]["id"],
                "player_id": e["player"]["id"],
                "player_name": e["player"]["name"],
                "team_name": e["team"]["name"],
                "type_name": "foul",
                "result_name": "yellow_card",
                "acao": "cartao_por_reclamacao",
                "grupo_acao": "infracao",
                "sucesso": False,
                "cartao_amarelo": True,
                "gol": False,
                "no_gol": False,
            }
        )

    if not extras:
        return out

    novos = pd.DataFrame(extras)
    novos["minuto"] = minuto_de_jogo(novos["period_id"], novos["time_seconds"])
    novos["segundo"] = segundo_de_jogo(novos["period_id"], novos["time_seconds"])
    novos["periodo_nome"] = novos["period_id"].map(NOME_DO_PERIODO)
    # action_id continua a numeração da partida; estas linhas são apêndices
    # sem posição na sequência de bola (não têm ação SPADL correspondente).
    novos["action_id"] = range(int(out["action_id"].max()) + 1, int(out["action_id"].max()) + 1 + len(novos))
    for coluna in ("xt_value", "vaep_value", "vaep_offensive", "vaep_defensive"):
        novos[coluna] = 0.0
    for coluna in ("progressive",):
        novos[coluna] = False
    logger.info("recuperados %d cartões que o SPADL descartou", len(novos))
    return pd.concat([out, novos], ignore_index=True)

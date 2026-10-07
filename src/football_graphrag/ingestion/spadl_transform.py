"""Passos 0.2 e 0.3: normalização para SPADL e valoração de ações (xT, VAEP).

SPADL (Soccer Player Action Description Language) unifica toda ação em
``(jogador, time, tipo, x_inicial, y_inicial, x_final, y_final, resultado,
tempo)`` num campo padronizado de 105x68m com ataque da esquerda para a
direita para os dois times. Referência: Decroos et al., "Actions Speak Louder
than Goals: Valuing Player Actions in Soccer", KDD 2019.

Sobre os modelos de valoração (ver ADR em docs/05-decisoes.md):
- xT: preferimos a grade pública 12x8 de Karun Singh
  (https://karun.in/blog/expected-threat.html). Se o arquivo não estiver em
  ``data/models/open_xt_12x8_v1.json``, ajustamos ``ExpectedThreat`` do
  socceraction sobre as partidas de treino baixadas e cacheamos o resultado.
- VAEP: o socceraction não distribui modelo pré-treinado; treinamos uma vez
  sobre um conjunto de partidas da mesma competição e cacheamos em
  ``data/models/``. O treino é parte da pipeline determinística (seed fixa).
"""

import logging
import pickle
from pathlib import Path

import pandas as pd
import socceraction.spadl as spadl
import socceraction.spadl.kloppy as spadl_kloppy
import socceraction.xthreat as xthreat
from kloppy.domain import EventDataset
from socceraction.data.statsbomb import StatsBombLoader
from socceraction.vaep import VAEP

logger = logging.getLogger(__name__)

XT_GRID_FILE = "open_xt_12x8_v1.json"
XT_FITTED_FILE = "xt_fitted_12x8.json"
VAEP_MODEL_FILE = "vaep_model.pkl"


def convert_to_spadl(dataset: EventDataset, match_id: int) -> pd.DataFrame:
    """Passo 0.2: converte o EventDataset do kloppy para ações SPADL.

    Conceito:
        SPADL descarta eventos que não são ações com bola (pressão, bloqueio,
        posicionamento tático...) e normaliza o resto num vocabulário fechado
        de ~23 tipos. O que se perde e o que se mantém está contado em
        docs/01-pipeline.md.

    Entrada:
        dataset: EventDataset do kloppy (passo 0.1b), coordenadas statsbomb.
        match_id: usado como game_id nas linhas SPADL.

    Saída:
        DataFrame SPADL com nomes legíveis (type_name, result_name,
        bodypart_name) via ``spadl.add_names``. Coordenadas em metros,
        campo 105x68, ataque sempre da esquerda para a direita.

    Referência:
        Decroos et al. 2019 (KDD); https://socceraction.readthedocs.io/en/latest/documentation/spadl/spadl.html

    Vai para o grafo em:
        Cada linha vira uma aresta factual (PASSOU_PARA etc.) na camada 1.
    """
    actions = spadl_kloppy.convert_to_actions(dataset, game_id=match_id)
    actions = _play_left_to_right(actions, dataset.metadata.teams[0].team_id)
    actions = spadl.add_names(actions)
    # kloppy expõe ids como string; StatsBomb usa ids inteiros — normalizamos
    # aqui para casar com os loaders do socceraction (players/teams/games).
    for col in ("game_id", "team_id", "player_id"):
        actions[col] = pd.to_numeric(actions[col], errors="coerce").astype("Int64")
    return actions.reset_index(drop=True)


def _play_left_to_right(actions: pd.DataFrame, home_team_id: str) -> pd.DataFrame:
    """Make every action attack left to right.

    socceraction's kloppy converter leaves the coordinates in kloppy's
    ``HOME_AWAY`` orientation: the home team attacks left to right in odd
    periods (1st half, 1st half of extra time) and the teams switch sides
    every period. Without this flip, the away team's actions in odd periods
    and the home team's in even periods were mirrored (e.g. Messi's 108'
    goal in the 2022 final sat on his own goal line).
    """
    out = actions.copy()
    home = out["team_id"].astype(str) == str(home_team_id)
    odd_period = out["period_id"] % 2 == 1
    flip = (home & ~odd_period) | (~home & odd_period)
    for col, length in (("start_x", spadl.config.field_length), ("end_x", spadl.config.field_length),
                        ("start_y", spadl.config.field_width), ("end_y", spadl.config.field_width)):
        out.loc[flip, col] = length - out.loc[flip, col]
    return out


def _fit_xt_on_matches(training_actions: pd.DataFrame, models_dir: Path) -> xthreat.ExpectedThreat:
    # Mesma resolução da grade canônica de Karun Singh: 12 colunas x 8 linhas.
    model = xthreat.ExpectedThreat(l=12, w=8)
    model.fit(training_actions)
    models_dir.mkdir(parents=True, exist_ok=True)
    model.save_model(str(models_dir / XT_FITTED_FILE), overwrite=True)
    return model


def load_or_fit_xt(models_dir: Path, training_actions: pd.DataFrame | None = None) -> xthreat.ExpectedThreat:
    """Passo 0.3a: obtém o modelo de xT (grade 12x8 de valor de campo).

    Ordem de preferência (ADR em docs/05-decisoes.md):
    1. ``data/models/open_xt_12x8_v1.json`` — grade pública de Karun Singh,
       colocada manualmente ou baixada quando a rede permite.
    2. ``data/models/xt_fitted_12x8.json`` — grade ajustada localmente e cacheada.
    3. Ajustar agora sobre ``training_actions`` e cachear (determinístico:
       o ajuste de xT é uma iteração de ponto fixo sem aleatoriedade).
    """
    canonical = models_dir / XT_GRID_FILE
    if canonical.exists():
        return xthreat.load_model(str(canonical))
    fitted = models_dir / XT_FITTED_FILE
    if fitted.exists():
        return xthreat.load_model(str(fitted))
    if training_actions is None:
        raise FileNotFoundError(
            f"nenhum modelo de xT em {models_dir}; forneça training_actions para ajustar"
        )
    logger.info("grade xT canônica ausente; ajustando ExpectedThreat em %d ações", len(training_actions))
    return _fit_xt_on_matches(training_actions, models_dir)


def add_xt(actions: pd.DataFrame, model: xthreat.ExpectedThreat) -> pd.DataFrame:
    """Passo 0.3a: adiciona a coluna ``xt_value`` (delta de ameaça esperada).

    Conceito:
        xT valora a PROGRESSÃO espacial: xT(zona_destino) - xT(zona_origem)
        para ações de condução/passe bem-sucedidas que movem a bola. Ações
        que não movem a bola com sucesso recebem 0.0 (não NaN: ausência de
        progressão é valor zero, não dado faltante).

    Fórmula:
        xt_value = xT[celula(end_x, end_y)] - xT[celula(start_x, start_y)]
        sobre a grade 12x8 do modelo. Referência: Karun Singh, "Introducing
        Expected Threat", 2018.

    Vai para o grafo em:
        Propriedade ``xt_gerado`` das arestas PASSOU_PARA e agregados de
        Zona/FaseDePosse.
    """
    out = actions.copy()
    out["xt_value"] = 0.0
    successful_moves = xthreat.get_successful_move_actions(actions)
    if len(successful_moves) > 0:
        values = model.rate(successful_moves)
        out.loc[successful_moves.index, "xt_value"] = values
    return out


def load_or_train_vaep(
    models_dir: Path,
    loader: StatsBombLoader | None = None,
    training_games: pd.DataFrame | None = None,
) -> VAEP:
    """Passo 0.3b: obtém o modelo VAEP (treina uma vez e cacheia).

    Conceito:
        VAEP valora cada ação pela mudança que provoca na probabilidade do
        time marcar (componente ofensivo) e sofrer (componente defensivo) gol
        nas próximas 10 ações. Diferente do xT, valora a ação no contexto da
        sequência, incluindo ações defensivas e falhas.

    Fórmula:
        VAEP(a) = ΔP(marcar | estado) - ΔP(sofrer | estado), com P estimado
        por dois classificadores xgboost sobre features das últimas 3 ações.
        Referência: Decroos et al., KDD 2019.

    Entrada:
        models_dir: onde fica o cache ``vaep_model.pkl``.
        loader/training_games: necessários apenas no primeiro treino; games
        vem de ``StatsBombLoader.games(competition, season)``.

    Saída:
        VAEP treinado. Determinístico dado o mesmo conjunto de treino
        (random_state fixo no xgboost).

    Vai para o grafo em:
        Propriedade ``vaep`` das arestas PASSOU_PARA.
    """
    cache = models_dir / VAEP_MODEL_FILE
    if cache.exists():
        with cache.open("rb") as fh:
            return pickle.load(fh)
    if loader is None or training_games is None:
        raise FileNotFoundError(f"sem cache VAEP em {cache}; forneça loader e training_games")

    model = VAEP(nb_prev_actions=3)
    all_x, all_y = [], []
    for _, game in training_games.iterrows():
        events = loader.events(game.game_id)
        actions = spadl.statsbomb.convert_to_actions(events, home_team_id=game.home_team_id)
        actions = spadl.add_names(actions)
        all_x.append(model.compute_features(game, actions))
        all_y.append(model.compute_labels(game, actions))
    features = pd.concat(all_x)
    labels = pd.concat(all_y)
    logger.info("treinando VAEP em %d partidas / %d ações", len(training_games), len(features))
    model.fit(features, labels, tree_params={"random_state": 42, "n_jobs": 4})
    models_dir.mkdir(parents=True, exist_ok=True)
    with cache.open("wb") as fh:
        pickle.dump(model, fh)
    return model


def add_vaep(actions: pd.DataFrame, model: VAEP, game: pd.Series) -> pd.DataFrame:
    """Passo 0.3b: adiciona colunas vaep_offensive, vaep_defensive, vaep_value."""
    # VAEP expects SPADL's native orientation (home team left to right, away
    # team right to left) and turns it left to right itself; our actions are
    # already left to right, so the away team's go back first.
    ratings = model.rate(game, spadl.play_left_to_right(actions, game.home_team_id))
    out = actions.copy()
    out["vaep_offensive"] = ratings["offensive_value"].to_numpy()
    out["vaep_defensive"] = ratings["defensive_value"].to_numpy()
    out["vaep_value"] = ratings["vaep_value"].to_numpy()
    return out

"""Esquema das quatro tabelas canonicas e validacao.

Esquemas normativos: docs/02-dados.md "Esquema interno" e
docs/fatias/01-plano.md §4. Os `dtype` abaixo tem de ser identicos nos tres
jogos (criterio de aceite do plano §8.2).
"""

import numpy as np
import pandas as pd

from src.io.coordenadas import x_para_metros, y_para_metros

# Um registro por quadro e jogo. `ball_x`/`ball_y` preservam NaN (D1).
FRAMES = {
    "game": "int64",
    "period": "int64",
    "frame": "int64",
    "t": "float64",
    "ball_x": "float64",
    "ball_y": "float64",
    "ball_live": "bool",
}

# Um registro por quadro, jogo e jogador PRESENTE. Jogador com NaN nao tem
# linha: ausencia de linha, nunca zero, nunca visible=False.
TRACKING = {
    "game": "int64",
    "period": "int64",
    "frame": "int64",
    "player_id": "str",
    "team": "str",
    "is_gk": "bool",
    "x": "float64",
    "y": "float64",
    "visible": "bool",
}

# Sentido de ataque, uma linha por (jogo, periodo, time). Nao ha rotacao do
# tracking (plano §2.2).
PERIODS = {
    "game": "int64",
    "period": "int64",
    "team": "str",
    "attack_dir": "int64",
    "gk_mean_x": "float64",
}

# Gabarito. `frame` e o quadro canonico (ancorado); `annotated_frame` e o
# Start Frame cru, que a Fatia 2 usa para medir a defasagem tau.
EVENTS = {
    "game": "int64",
    "period": "int64",
    "frame": "int64",
    "t": "float64",
    "type": "str",
    "team": "str",
    "player_id": "str",
    "annotated_frame": "int64",
    "anchor_shift": "int64",
    "no_dead_ball_before": "bool",
    "pass_secundario": "bool",
    "metrica_type": "str",
    "metrica_subtype": "str",
    "source_rows": "str",
}


def validar(df: pd.DataFrame, esquema: dict, nome: str) -> pd.DataFrame:
    """Confere nomes, ordem e dtype das colunas. Estoura na primeira diferenca."""
    if list(df.columns) != list(esquema):
        raise ValueError(f"{nome}: colunas {list(df.columns)} != esquema {list(esquema)}")
    for col, dtype in esquema.items():
        if str(df[col].dtype) != dtype:
            raise ValueError(f"{nome}.{col}: dtype {df[col].dtype} != {dtype}")
    return df


def montar_tracking(
    game: int,
    period: np.ndarray,
    frame: np.ndarray,
    x_norm: np.ndarray,
    y_norm: np.ndarray,
    player_ids: np.ndarray,
    team: np.ndarray,
    is_gk: np.ndarray,
    comprimento_m: float,
    largura_m: float,
) -> pd.DataFrame:
    """Converte uma matriz (quadro x jogador) de coordenadas normalizadas em
    formato longo, descartando as celulas NaN.

    Entrada: `x_norm` e `y_norm` com forma (n_quadros, n_jogadores); `period` e
    `frame` com forma (n_quadros,); `player_ids`, `team` e `is_gk` com forma
    (n_jogadores,).

    Saida: DataFrame no esquema TRACKING, com uma linha por celula nao-NaN.
    `visible` e sempre True nesta fatia: nada foi imputado (plano §4).
    """
    presente = ~np.isnan(x_norm)
    if not np.array_equal(presente, ~np.isnan(y_norm)):
        raise ValueError(f"jogo {game}: NaN de x e de y de jogador nao coincidem")
    fi, pi = np.nonzero(presente)
    n = fi.size
    return pd.DataFrame(
        {
            "game": np.full(n, game, dtype="int64"),
            "period": period[fi].astype("int64"),
            "frame": frame[fi].astype("int64"),
            "player_id": np.asarray(player_ids, dtype=object)[pi],
            "team": np.asarray(team, dtype=object)[pi],
            "is_gk": np.asarray(is_gk, dtype=bool)[pi],
            "x": x_para_metros(x_norm[fi, pi], comprimento_m),
            "y": y_para_metros(y_norm[fi, pi], largura_m),
            "visible": np.ones(n, dtype=bool),
        }
    )


def montar_frames(
    game: int,
    period: np.ndarray,
    frame: np.ndarray,
    ball_x_norm: np.ndarray,
    ball_y_norm: np.ndarray,
    comprimento_m: float,
    largura_m: float,
    fps: int,
) -> pd.DataFrame:
    """Monta a tabela `frames`. `ball_live = not isna(ball_x)` (D1)."""
    ball_x = x_para_metros(ball_x_norm, comprimento_m)
    ball_y = y_para_metros(ball_y_norm, largura_m)
    df = pd.DataFrame(
        {
            "game": np.full(frame.size, game, dtype="int64"),
            "period": period.astype("int64"),
            "frame": frame.astype("int64"),
            "t": frame.astype("float64") / fps,
            "ball_x": ball_x,
            "ball_y": ball_y,
            "ball_live": ~np.isnan(ball_x),
        }
    )
    return validar(df, FRAMES, f"frames(jogo {game})")


def montar_periods(game: int, tracking: pd.DataFrame) -> pd.DataFrame:
    """Deriva o sentido de ataque do proprio dado, por jogo e por periodo.

    Criterio (plano §10, revisado no G3 de 2026-10-29): x medio do GOLEIRO do
    time no periodo, guardado em `gk_mean_x`. `attack_dir = -sign(gk_mean_x)`:
    o time cujo goleiro ocupa o lado negativo do campo ataca para +x.

    O goleiro e identificavel nos tres jogos (primeira coluna de cada arquivo
    nos jogos 1 e 2, `position_type = Goalkeeper` no XML do jogo 3). A media de
    TODOS os jogadores do time tem o mesmo sinal, mas margem de so 2,24 m no pior
    caso contra ~40 m do goleiro; fica como checagem cruzada no teste.
    """
    goleiros = tracking[tracking["is_gk"]]
    if goleiros.empty:
        raise ValueError(f"jogo {game}: nenhuma linha com is_gk=True")
    medias = goleiros.groupby(["period", "team"], sort=True)["x"].mean()
    linhas = []
    for (period, team), mean_x in medias.items():
        if mean_x == 0.0 or np.isnan(mean_x):
            raise ValueError(f"jogo {game} periodo {period} time {team}: x medio {mean_x}")
        linhas.append(
            {
                "game": game,
                "period": int(period),
                "team": team,
                "attack_dir": -1 if mean_x > 0 else 1,
                "gk_mean_x": float(mean_x),
            }
        )
    df = pd.DataFrame(linhas)[list(PERIODS)].astype(PERIODS)
    return validar(df, PERIODS, f"periods(jogo {game})")

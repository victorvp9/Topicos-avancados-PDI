"""Suavizacao Savitzky-Golay da posicao da bola, por corrida viva contigua.

Regra normativa: `docs/01-definicoes.md`, Passo 1, "Suavizacao" -- polinomio de
segunda ordem, janela de sete quadros (Vidal-Codina §2.3.1, p. 5), aplicada as
coordenadas x-y da bola.

Lacuna 6 (`docs/fatias/03-plano.md` §3.6): a suavizacao e aplicada **por corrida
viva contigua, nunca atraves de uma bola morta**, porque `savgol_filter` sobre
serie com buraco de NaN propaga NaN; corrida mais curta que a janela fica sem
suavizar, e isso e contado. Fica DESLIGADA por padrao (`posse.suavizar: false`),
porque a bola da Metrica e verdade de terreno multicamera.
"""

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter


def aplicar(frames: pd.DataFrame, cfg: dict, inicios: np.ndarray,
            comprimentos: np.ndarray):
    """Suaviza `ball_x`/`ball_y` dentro de cada corrida viva.

    Entrada: `frames` no esquema `src.io.schema.FRAMES`; `inicios` e
    `comprimentos` das corridas vivas (de `src.possession.corridas_vivas`).
    Saida: (`frames`, `contagens`).

    Com `posse.suavizar` falso devolve o **mesmo objeto** `frames` e zero em
    todos os contadores: a identidade e bit a bit, por construcao.

    Com `posse.suavizar` verdadeiro devolve uma copia com a bola suavizada
    dentro de cada corrida de pelo menos `savgol_janela_quadros` quadros. Os
    quadros de bola morta seguem NaN (nao estao em nenhuma corrida), logo a
    fracao de NaN nao muda. Borda: `mode='interp'` (o padrao do
    `savgol_filter`), que ajusta o polinomio aos quadros da propria corrida --
    o artigo nao especifica o tratamento de borda.

    O laco e sobre CORRIDAS (~155 por jogo), nunca sobre quadros: segmentos de
    comprimento variavel nao tem forma vetorizavel em `savgol_filter`.
    """
    janela = cfg["posse"]["savgol_janela_quadros"]
    ordem = cfg["posse"]["savgol_ordem"]
    if not cfg["posse"]["suavizar"]:
        return frames, {"corridas_suavizadas": 0, "corridas_curtas_sem_suavizar": 0}

    ball_x = frames["ball_x"].to_numpy().copy()
    ball_y = frames["ball_y"].to_numpy().copy()
    longa = comprimentos >= janela
    for i0, n in zip(inicios[longa], comprimentos[longa]):
        fatia = slice(int(i0), int(i0 + n))
        ball_x[fatia] = savgol_filter(ball_x[fatia], janela, ordem)
        ball_y[fatia] = savgol_filter(ball_y[fatia], janela, ordem)

    saida = frames.copy()
    saida["ball_x"] = ball_x
    saida["ball_y"] = ball_y
    return saida, {
        "corridas_suavizadas": int(longa.sum()),
        "corridas_curtas_sem_suavizar": int((~longa).sum()),
    }

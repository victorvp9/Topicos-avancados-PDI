"""Passes de jogo corrido: rotulo das perdas de posse do Passo 1.

Regra normativa: `docs/01-definicoes.md`, "Passe -- corrigido (V16)": o
algoritmo rotula como passe **toda perda de posse** que nao e finalizacao nem
cruzamento (§2.4.3, p. 9); o desfecho e ATRIBUTO, nao condicao (supl. S5,
p. 9). As decisoes desta fatia estao em `docs/fatias/05-plano.md` §3 e em
`docs/decisoes.md` (2026-11-04).

Tres funcoes, sem classe nem registry (plano §4): `suprimir` (a perda que e o
proprio evento de bola parada), `rotular` (monta a tabela, com o desfecho) e
`para_casador`. Nenhuma constante: este modulo so le tabelas do Passo 1 e da
Fatia 4. Vetorizado: buscas binarias, nenhum laco sobre quadros.

Finalizacao sai rotulada passe, porque nao detectamos finalizacao (plano
§3.5.2); contra o gabarito ela e falso positivo. Declarado, nao filtrado.
"""

import numpy as np
import pandas as pd

from src import possession
from src.evaluate import DETECTIONS
from src.io.schema import validar as validar_esquema

# Dominio FECHADO de `desfecho` (plano §3.3). Valor fora disto estoura.
DESFECHOS = ("completo", "interceptado", "proprio", "bola_morta", "fim_de_periodo")

# Uma linha por perda de posse, INCLUSIVE as suprimidas (plano §5): quem avalia
# filtra `~e_bola_parada`. `frame` e o quadro da perda (§2.3.2, p. 5).
PASSES = {
    "game": "int64",
    "period": "int64",
    "frame": "int64",
    "t": "float64",
    "type": "str",
    "team": "str",
    "player_id": "str",
    "run_id": "int64",
    "e_bola_parada": "bool",
    "desfecho": "str",
    "receptor_id": "str",
    "recepcao_em_duelo": "bool",
    "de_lacuna_5": "bool",
}


def suprimir(perdas: pd.DataFrame, deteccoes: pd.DataFrame, frames: pd.DataFrame) -> np.ndarray:
    """Posicao (em `deteccoes`) da bola parada que cada perda E, ou -1.

    Entrada, todas do MESMO jogo: `perdas` no esquema `src.possession.PERDAS`,
    em ordem de `frame`; `deteccoes` com `frame` = primeiro quadro em jogo
    (esquema `src.events.bola_parada.DETECCOES`); `frames` com `frame` e
    `ball_live`, em ordem de `frame`.
    Saida: array (n_perdas,) int64.

    Regra (plano §3.1, [LACUNA] decidida pelo orquestrador): para cada deteccao
    de bola parada, a PRIMEIRA perda da mesma corrida viva com `frame >=` o da
    deteccao e o evento de bola parada -- *"Set piece events are passing events
    that resume the game"* (S2, p. 3). **Independe do jogador**: uma por
    intervalo morto (correspondencia um-para-um, §2.4.1, p. 7). Corrida sem
    perda: nada a suprimir.
    """
    quadro = frames["frame"].to_numpy()
    run_id = possession.corridas_vivas(frames["ball_live"].to_numpy())[0]
    f_det = deteccoes["frame"].to_numpy()
    run_det = run_id[np.searchsorted(quadro, f_det)]
    f_perda = perdas["frame"].to_numpy()
    # A busca binaria abaixo so vale com as perdas em ordem de quadro.
    if (np.diff(f_perda) < 0).any():
        raise ValueError("suprimir: `perdas` fora de ordem de `frame`")
    origem = np.full(f_perda.size, -1, dtype="int64")
    if f_perda.size == 0:
        return origem
    k = np.searchsorted(f_perda, f_det, side="left")
    seguro = np.minimum(k, f_perda.size - 1)
    # `run_det` e 0 se a deteccao caisse em quadro morto, e `run_id` de perda e
    # sempre >= 1: nunca casa.
    ok = (k < f_perda.size) & (perdas["run_id"].to_numpy()[seguro] == run_det)
    origem[k[ok]] = np.flatnonzero(ok)
    return origem


def validar(passes: pd.DataFrame) -> pd.DataFrame:
    """Esquema `PASSES` e dominio fechado de `desfecho`; estoura se violar."""
    validar_esquema(passes, PASSES, "passes")
    fora = sorted(set(passes["desfecho"]) - set(DESFECHOS))
    if fora:
        raise ValueError("passes: desfecho(s) {!r} fora de {}".format(fora, DESFECHOS))
    return passes


def rotular(perdas, ganhos, control, frames, deteccoes) -> pd.DataFrame:
    """Monta a tabela `PASSES` de um jogo.

    Entrada, do MESMO jogo: `perdas`, `ganhos` e `control` de
    `src.possession.calcular`; `frames` (esquema `FRAMES`); `deteccoes` de
    `src.events.bola_parada.detectar`.
    Saida: DataFrame no esquema `PASSES`, uma linha por perda, em ordem de
    quadro.

    `desfecho` vem do PROXIMO ganho com `frame >` o da perda, na mesma corrida
    viva e no mesmo periodo (plano §3.3):
      `completo`       ganho de companheiro (S5, p. 9, *"reaches a teammate"*);
      `interceptado`   ganho de adversario (S5, p. 9);
      `proprio`        ganho do proprio passador. [LACUNA] do plano: nao e
                       "teammate", logo nao e completo;
      `bola_morta`     sem ganho, e o trecho vivo termina em quadro morto
                       (o passe que vira gol cai aqui: nao detectamos gol);
      `fim_de_periodo` sem ganho ate o ultimo quadro do periodo ou do jogo.
    O desfecho *"duel at reception"* do S5 e a coluna `recepcao_em_duelo`, nao
    um desfecho: o D10 define o principal pelo proximo ganho, sem excecao.
    """
    perdas = perdas.sort_values("frame", kind="stable").reset_index(drop=True)
    ganhos = ganhos.sort_values("frame", kind="stable").reset_index(drop=True)
    frames = frames.sort_values("frame", kind="stable")
    quadro = frames["frame"].to_numpy()
    period = frames["period"].to_numpy()
    vivo = frames["ball_live"].to_numpy()
    n = quadro.size

    origem = suprimir(perdas, deteccoes, frames)

    # --- proximo ganho na mesma corrida e no mesmo periodo -----------------
    f_perda = perdas["frame"].to_numpy()
    f_ganho = ganhos["frame"].to_numpy()
    k = np.searchsorted(f_ganho, f_perda, side="right")
    seguro = np.minimum(k, max(f_ganho.size - 1, 0))
    if f_ganho.size:
        tem = (
            (k < f_ganho.size)
            & (ganhos["run_id"].to_numpy()[seguro] == perdas["run_id"].to_numpy())
            & (ganhos["period"].to_numpy()[seguro] == perdas["period"].to_numpy())
        )
        receptor = np.where(tem, ganhos["player_id"].to_numpy()[seguro], "")
        time_receptor = np.where(tem, ganhos["team"].to_numpy()[seguro], "")
        duelos = control.loc[control["ball_control"] == possession.DUEL, "frame"]
        em_duelo = tem & np.isin(f_ganho[seguro], duelos.to_numpy())
    else:
        tem = np.zeros(f_perda.size, dtype=bool)
        receptor = time_receptor = np.full(f_perda.size, "", dtype=object)
        em_duelo = tem

    # --- sem ganho: como termina o trecho vivo da perda --------------------
    # `para[i]`: o quadro i e o ultimo do seu trecho vivo (o seguinte e morto,
    # e de outro periodo, ou nao existe).
    para = np.r_[~vivo[1:] | (period[1:] != period[:-1]), True]
    paradas = np.flatnonzero(para)
    fim = paradas[np.searchsorted(paradas, np.searchsorted(quadro, f_perda))]
    seguinte = np.minimum(fim + 1, n - 1)
    fim_de_periodo = (fim == n - 1) | (period[seguinte] != period[fim])

    jogador = perdas["player_id"].to_numpy()
    desfecho = np.select(
        [tem & (receptor == jogador), tem & (time_receptor == perdas["team"].to_numpy()), tem],
        ["proprio", "completo", "interceptado"],
        default=np.where(fim_de_periodo, "fim_de_periodo", "bola_morta"),
    )

    passes = pd.DataFrame(
        {
            "game": perdas["game"].to_numpy(),
            "period": perdas["period"].to_numpy(),
            "frame": f_perda,
            "t": perdas["t"].to_numpy(),
            "type": "pass",
            "team": perdas["team"].to_numpy(),
            "player_id": jogador,
            "run_id": perdas["run_id"].to_numpy(),
            "e_bola_parada": origem >= 0,
            "desfecho": desfecho,
            "receptor_id": receptor,
            "recepcao_em_duelo": em_duelo,
            "de_lacuna_5": perdas["so_por_lacuna_5"].to_numpy(),
        }
    ).astype(PASSES)
    return validar(passes)


def para_casador(passes: pd.DataFrame, so_completo: bool = False) -> pd.DataFrame:
    """Projeta os passes NAO suprimidos no esquema `src.evaluate.DETECTIONS`.

    `so_completo=True` e o criterio principal (plano §3.3: `desfecho ==
    "completo"` contra o `PASS`); `False` e o secundario e o diagnostico.
    """
    manter = ~passes["e_bola_parada"]
    if so_completo:
        manter &= passes["desfecho"] == "completo"
    return passes.loc[manter, list(DETECTIONS)].reset_index(drop=True).astype(DETECTIONS)

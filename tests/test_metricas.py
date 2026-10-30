"""Testes das metricas: contagem absoluta, denominador zero e agregado.

Criterios de aceite: docs/fatias/02-plano.md §9.2 e §9.4.
"""

import numpy as np
import pandas as pd
import pytest

from src import evaluate

JOGOS = (1, 2, 3)

# docs/inspecao-metrica.md §3.2 (bola parada), §3.3 (tiro de meta) e a contagem
# de passe do gabarito depois da fusao (plano §6: 722 + 889 + 1039 = 2650).
N_GABARITO = {
    "kickoff": (6, 8, 4),
    "corner_kick": (11, 7, 8),
    "throw_in": (28, 32, 50),
    "free_kick": (32, 32, 28),
    "goal_kick": (22, 16, 11),
    "pass": (722, 889, 1039),
    "free_kick?": (0, 0, 0),
}


@pytest.fixture(scope="module")
def gab(eventos):
    return pd.concat([eventos(g)[1] for g in JOGOS], ignore_index=True)


@pytest.fixture(scope="module")
def identidade(gab, cfg):
    """Gabarito contra si mesmo, na ancora `frame`."""
    return evaluate.avaliar(gab, evaluate.deteccoes_do_gabarito(gab, "frame", cfg), cfg)


def _deteccoes(linhas, fps=25):
    """`linhas`: (game, frame, type, player_id)."""
    df = pd.DataFrame(linhas, columns=["game", "frame", "type", "player_id"])
    df = df.assign(period=1, t=df["frame"] / fps, team="home")
    return df[list(evaluate.DETECTIONS)].astype(evaluate.DETECTIONS)


def _gabarito(linhas, fps=25):
    """`linhas`: (game, frame, type, player_id)."""
    df = pd.DataFrame(linhas, columns=["game", "frame", "type", "player_id"])
    return df.assign(
        period=1, t=df["frame"] / fps, annotated_frame=df["frame"], team="home"
    )


def test_contagem_absoluta_por_tipo_e_jogo(identidade):
    """`n_gabarito` bate com docs/inspecao-metrica.md §3.2/§3.3 nos 3 jogos."""
    res = identidade[0]
    res = res[(res["criterio"] == "estrito") & (res["ancora"] == "frame")]
    for tipo, esperado in N_GABARITO.items():
        obtido = tuple(
            int(res[(res["game"] == g) & (res["type"] == tipo)]["n_gabarito"].iloc[0])
            for g in JOGOS
        )
        assert obtido == esperado, tipo
        agregado = int(res[(res["game"] == 0) & (res["type"] == tipo)]["n_gabarito"].iloc[0])
        assert agregado == sum(esperado), tipo


def test_identidades_das_contagens(identidade):
    """`tp + fn = n_gabarito` e `tp_det + fp = n_detectado` em toda linha."""
    res = identidade[0]
    assert (res["tp"] + res["fn"] == res["n_gabarito"]).all()
    assert (res["tp_det"] + res["fp"] == res["n_detectado"]).all()
    assert (res["tp"] >= 0).all() and (res["fp"] >= 0).all() and (res["fn"] >= 0).all()


def test_precisao_com_zero_deteccoes_e_nan(cfg):
    """Precisao de uma classe sem nenhuma deteccao e indefinida, nao 0,0."""
    gab = _gabarito([(1, 1000, "corner_kick", "g1_home_7")])
    det = _deteccoes([(1, 1000, "throw_in", "g1_home_7")])
    res, _ = evaluate.avaliar(gab, det, cfg)
    linha = res[
        (res["criterio"] == "estrito")
        & (res["ancora"] == "frame")
        & (res["game"] == 0)
        & (res["type"] == "corner_kick")
    ].iloc[0]
    assert linha["n_detectado"] == 0
    assert np.isnan(linha["precisao"]), linha["precisao"]
    assert linha["revocacao"] == 0.0
    assert np.isnan(linha["f1"])


def test_revocacao_com_zero_anotados_e_nan(cfg):
    gab = _gabarito([(1, 1000, "corner_kick", "g1_home_7")])
    det = _deteccoes([(1, 1000, "throw_in", "g1_home_7")])
    res, _ = evaluate.avaliar(gab, det, cfg)
    linha = res[
        (res["criterio"] == "estrito")
        & (res["ancora"] == "frame")
        & (res["game"] == 0)
        & (res["type"] == "throw_in")
    ].iloc[0]
    assert linha["n_gabarito"] == 0
    assert np.isnan(linha["revocacao"])
    assert linha["precisao"] == 0.0
    assert np.isnan(linha["f1"])


def test_f1_zero_quando_definido_e_nan_quando_indefinido(cfg):
    """F1 = 0,0 com precisao e revocacao definidas e nulas; `NaN` so quando um
    dos dois denominadores e zero. Nao confundir os dois casos."""
    gab = _gabarito([(1, 1000, "throw_in", "g1_home_7")])
    det = _deteccoes([(1, 2000, "throw_in", "g1_home_7")])  # 40 s depois
    res, _ = evaluate.avaliar(gab, det, cfg)
    linha = res[
        (res["criterio"] == "estrito")
        & (res["ancora"] == "frame")
        & (res["game"] == 0)
        & (res["type"] == "throw_in")
    ].iloc[0]
    assert (linha["n_gabarito"], linha["n_detectado"], linha["tp"]) == (1, 1, 0)
    assert linha["precisao"] == 0.0 and linha["revocacao"] == 0.0
    assert linha["f1"] == 0.0  # NAO NaN: os dois denominadores existem

    vazio = res[
        (res["criterio"] == "estrito")
        & (res["ancora"] == "frame")
        & (res["game"] == 0)
        & (res["type"] == "free_kick?")
    ].iloc[0]
    assert (vazio["n_gabarito"], vazio["n_detectado"]) == (0, 0)
    assert np.isnan(vazio["f1"])  # NaN: nenhum denominador existe


def test_nan_nunca_entra_em_tp(cfg):
    """Deteccao e evento com `t = NaN` nunca viram acerto, e os dois ficam nas
    contagens absolutas."""
    gab = _gabarito([(1, 1000, "pass", "g1_home_1")]).astype(
        {"frame": "float64", "annotated_frame": "float64"}
    )
    gab.loc[0, ["frame", "annotated_frame", "t"]] = np.nan
    det = _deteccoes([(1, 1000, "pass", "g1_home_1")])
    det.loc[0, "t"] = np.nan
    res, _ = evaluate.avaliar(gab, det, cfg)
    for criterio in cfg["avaliacao"]["criterios"]:
        linha = res[
            (res["criterio"] == criterio)
            & (res["ancora"] == "frame")
            & (res["game"] == 0)
            & (res["type"] == "pass")
        ].iloc[0]
        assert (linha["n_gabarito"], linha["n_detectado"]) == (1, 1), criterio
        assert (linha["tp"], linha["tp_det"], linha["fp"], linha["fn"]) == (0, 0, 1, 1), criterio
        assert linha["f1"] == 0.0


def test_agregado_e_soma_nao_media_dos_f1(cfg):
    """A linha `game = 0` e a soma das contagens, reavaliada; nao a media dos
    F1 por jogo (plano §9.2)."""
    gab = _gabarito(
        [(1, 1000, "throw_in", "g1_home_7")]
        + [(2, 1000 + 1000 * i, "throw_in", "g2_home_7") for i in range(4)]
    )
    det = _deteccoes(
        [(1, 1000, "throw_in", "g1_home_7")]
        + [(2, 1000 + 1000 * i, "throw_in", "g2_home_7") for i in range(2)]
    )
    res, _ = evaluate.avaliar(gab, det, cfg)
    sel = res[
        (res["criterio"] == "estrito")
        & (res["ancora"] == "frame")
        & (res["type"] == "throw_in")
    ].set_index("game")
    assert sel.loc[1, "f1"] == 1.0
    assert sel.loc[2, "f1"] == pytest.approx(2 / 3)  # P=1, R=0,5
    assert sel.loc[0, "n_gabarito"] == 5 and sel.loc[0, "tp"] == 3
    assert sel.loc[0, "f1"] == pytest.approx(0.75)  # P=1, R=0,6 agrupados
    media = (sel.loc[1, "f1"] + sel.loc[2, "f1"]) / 2
    assert abs(sel.loc[0, "f1"] - media) > 0.05  # a media daria 0,833


def test_agregado_e_a_soma_das_contagens_dos_jogos(identidade):
    """Em dado real: toda contagem da linha `game = 0` e a soma dos 3 jogos."""
    res = identidade[0]
    por_jogo = (
        res[res["game"] != 0]
        .groupby(["criterio", "ancora", "type"], sort=True)[
            ["n_gabarito", "n_detectado", "tp", "tp_det", "fp", "fn"]
        ]
        .sum()
    )
    agregado = (
        res[res["game"] == 0].set_index(["criterio", "ancora", "type"]).sort_index()[
            ["n_gabarito", "n_detectado", "tp", "tp_det", "fp", "fn"]
        ]
    )
    pd.testing.assert_frame_equal(por_jogo.sort_index(), agregado)

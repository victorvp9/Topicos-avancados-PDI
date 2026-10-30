"""Conversao de coordenadas (plano §8.1).

Os valores em metros do teste "sem clamp" estao HARDCODED de proposito: um teste
que recalcula a formula a partir do dado cru nao detecta um clamp aplicado antes
dela.
"""

import math

import numpy as np
import pytest

from src.io.coordenadas import (
    x_para_metros,
    x_para_normalizado,
    y_para_metros,
    y_para_normalizado,
)

COMPRIMENTO = 105.0
LARGURA = 68.0

# Medido por script independente, docs/inspecao-metrica.md §2.2, convertido com
# a formula do plano §2.3. Plano §8.1.
MAX_BALL_X_JOGO1_M = 58.7958
MIN_BALL_X_JOGO1_M = -57.2754
MAX_ABS_Y_JOGADOR_M = 37.4000
TOL_METROS = 1e-4


def test_bandeirinhas():
    """Os 4 cantos normalizados projetam nos 4 cantos em metros."""
    cantos = {
        (0.0, 0.0): (-52.5, +34.0),
        (1.0, 0.0): (+52.5, +34.0),
        (0.0, 1.0): (-52.5, -34.0),
        (1.0, 1.0): (+52.5, -34.0),
    }
    for (xn, yn), (xm, ym) in cantos.items():
        assert x_para_metros(xn, COMPRIMENTO) == pytest.approx(xm, abs=1e-9)
        assert y_para_metros(yn, LARGURA) == pytest.approx(ym, abs=1e-9)


def test_centro_exato():
    assert float(x_para_metros(0.5, COMPRIMENTO)) == 0.0
    assert float(y_para_metros(0.5, LARGURA)) == 0.0


def test_sinal_de_y_cresce_para_cima():
    """A Metrica tem (0,0) no canto SUPERIOR esquerdo (plano §2.3)."""
    assert float(y_para_metros(0.0, LARGURA)) == pytest.approx(+34.0, abs=1e-9)
    assert float(y_para_metros(1.0, LARGURA)) == pytest.approx(-34.0, abs=1e-9)


def test_ida_e_volta():
    rng = np.random.default_rng(20261029)  # semente explicita: determinismo
    norm = rng.uniform(-0.1, 1.1, size=1000)
    assert np.allclose(
        x_para_normalizado(x_para_metros(norm, COMPRIMENTO), COMPRIMENTO), norm, atol=1e-12
    )
    assert np.allclose(
        y_para_normalizado(y_para_metros(norm, LARGURA), LARGURA), norm, atol=1e-12
    )


def test_nan_preservado():
    """NaN nao vira zero nem valor finito em nenhuma direcao."""
    assert math.isnan(float(x_para_metros(np.nan, COMPRIMENTO)))
    assert math.isnan(float(y_para_metros(np.nan, LARGURA)))
    assert math.isnan(float(x_para_normalizado(np.nan, COMPRIMENTO)))
    assert math.isnan(float(y_para_normalizado(np.nan, LARGURA)))


def test_dimensoes_do_campo_sao_usadas(cfg):
    """Falha se as constantes campo.* de config.yaml forem ignoradas."""
    assert cfg["campo"]["comprimento_m"] == COMPRIMENTO
    assert cfg["campo"]["largura_m"] == LARGURA
    assert float(x_para_metros(1.0, 100.0)) != float(x_para_metros(1.0, COMPRIMENTO))
    assert float(y_para_metros(1.0, 60.0)) != float(y_para_metros(1.0, LARGURA))


def test_sem_clamp_bola_jogo1(jogo):
    """max/min de `ball_x` do jogo 1 em metros, valores hardcoded (plano §8.1)."""
    frames = jogo(1)[0]
    assert frames["ball_x"].max() == pytest.approx(MAX_BALL_X_JOGO1_M, abs=TOL_METROS)
    assert frames["ball_x"].min() == pytest.approx(MIN_BALL_X_JOGO1_M, abs=TOL_METROS)


@pytest.mark.parametrize("game", [1, 2])
def test_sem_clamp_jogador(jogo, game):
    """max|y| de jogador = 37,4000 m nos jogos 1 e 2 (recorte em +-0,05)."""
    tracking = jogo(game)[1]
    assert tracking["y"].abs().max() == pytest.approx(MAX_ABS_Y_JOGADOR_M, abs=TOL_METROS)


@pytest.mark.parametrize("game", [1, 2, 3])
def test_coordenadas_saem_do_campo(jogo, game):
    """Confirma que nada foi recortado para dentro das linhas."""
    frames, tracking, _ = jogo(game)
    assert tracking["x"].abs().max() > COMPRIMENTO / 2
    assert frames["ball_x"].abs().max() > COMPRIMENTO / 2

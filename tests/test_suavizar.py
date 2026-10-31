"""Suavizacao Savitzky-Golay por corrida viva (lacuna 6).

Criterios e CAMINHO de cada teste: docs/fatias/03-plano.md §9.4.
`cenario` e `posse_real` sao fixtures de `tests/conftest.py`.
"""

import numpy as np
import pytest
from scipy.signal import savgol_filter

from src import possession, suavizar

NAN = (np.nan, np.nan)


def _zigue(n, inicio=0):
    """Parabola com zigue-zague: a suavizacao tem de mudar os valores."""
    i = np.arange(inicio, inicio + n, dtype="float64")
    return [(0.01 * v * v + 0.05 * (k % 2), 0.02 * v + 0.03 * (k % 2))
            for k, v in enumerate(i)]


def _aplicar(cenario, bola, **posse):
    frames, _, c = cenario(bola, {}, **posse)
    run_id, inicios, comprimentos = possession.corridas_vivas(
        frames["ball_live"].to_numpy()
    )
    return (frames,) + suavizar.aplicar(frames, c, inicios, comprimentos)


def test_nao_atravessa_buraco(cenario, cfg):
    """Duas corridas separadas por NaN: cada uma suavizada como se estivesse
    sozinha, bit a bit, e os quadros mortos seguem NaN."""
    bola = _zigue(10) + [NAN] * 3 + _zigue(12, inicio=50)
    frames, saida, contagens = _aplicar(cenario, bola, suavizar=True)
    janela, ordem = cfg["posse"]["savgol_janela_quadros"], cfg["posse"]["savgol_ordem"]
    for coluna in ("ball_x", "ball_y"):
        cru, suave = frames[coluna].to_numpy(), saida[coluna].to_numpy()
        for fatia in (slice(0, 10), slice(13, 25)):
            assert np.array_equal(suave[fatia], savgol_filter(cru[fatia], janela, ordem))
        assert np.isnan(suave[10:13]).all()
    assert contagens == {"corridas_suavizadas": 2, "corridas_curtas_sem_suavizar": 0}


def test_corrida_mais_curta_que_a_janela_fica_sem_suavizar(cenario):
    """Corrida de 5 quadros com janela de 7: fica intacta, e e CONTADA."""
    bola = _zigue(5) + [NAN] + _zigue(9, inicio=50)
    frames, saida, contagens = _aplicar(cenario, bola, suavizar=True)
    assert np.array_equal(saida["ball_x"].to_numpy()[0:5], frames["ball_x"].to_numpy()[0:5])
    assert not np.array_equal(saida["ball_x"].to_numpy()[6:], frames["ball_x"].to_numpy()[6:])
    assert contagens == {"corridas_suavizadas": 1, "corridas_curtas_sem_suavizar": 1}


def test_valor_da_janela_decide_a_corrida_curta(cenario):
    """A MESMA corrida de 5 quadros e suavizada com `savgol_janela_quadros` = 5."""
    bola = _zigue(5)
    frames, saida, contagens = _aplicar(cenario, bola, suavizar=True, savgol_janela_quadros=5)
    assert contagens == {"corridas_suavizadas": 1, "corridas_curtas_sem_suavizar": 0}
    assert not np.array_equal(saida["ball_x"].to_numpy(), frames["ball_x"].to_numpy())


def test_valor_da_ordem_muda_a_saida(cenario):
    """Trocar `savgol_ordem` muda o resultado: o valor nao pode ser ignorado."""
    bola = _zigue(9)
    segunda = _aplicar(cenario, bola, suavizar=True)[1]["ball_x"].to_numpy()
    primeira = _aplicar(cenario, bola, suavizar=True, savgol_ordem=1)[1]["ball_x"].to_numpy()
    assert not np.allclose(segunda, primeira)


@pytest.mark.parametrize("game", [1, 2, 3])
def test_desligada_e_identidade_bit_a_bit(jogo, posse_real, game):
    """Com `suavizar: false`, a bola e a MESMA tabela da Fatia 1."""
    frames = jogo(game)[0]
    usado = posse_real(game)["frames"]
    assert usado is frames
    for coluna in ("ball_x", "ball_y"):
        assert np.array_equal(usado[coluna].to_numpy(), frames[coluna].to_numpy(),
                              equal_nan=True)


def test_nan_preservado_no_dado_real(jogo, posse_real):
    """A fracao de bola NaN e identica antes e depois da suavizacao."""
    frames = jogo(1)[0]
    suave = posse_real(1, suavizar=True)["frames"]
    for coluna in ("ball_x", "ball_y"):
        antes = np.isnan(frames[coluna].to_numpy())
        depois = np.isnan(suave[coluna].to_numpy())
        assert np.array_equal(antes, depois)
    assert suave["ball_live"].equals(frames["ball_live"])


def test_ligada_muda_o_numero_de_control_frames(posse_real):
    desligada = posse_real(1)["contagens"]
    ligada = posse_real(1, suavizar=True)["contagens"]
    assert desligada["control_frames"] != ligada["control_frames"]
    assert ligada["corridas_suavizadas"] + ligada["corridas_curtas_sem_suavizar"] == (
        ligada["corridas_vivas"]
    )

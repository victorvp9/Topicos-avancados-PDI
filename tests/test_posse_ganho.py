"""Ganho de posse: direcao, velocidade, vetores unitarios e o NaN da lacuna 3.

Criterios e CAMINHO de cada teste: docs/fatias/03-plano.md §9.3. O teste dos
vetores unitarios roda com velocidades MUITO diferentes (0,25 e 50 m/s), que e o
caminho em que o produto escalar sem normalizar daria a resposta oposta.

`cenario` e `posse_real` sao fixtures de `tests/conftest.py`.
"""

import numpy as np
import pytest

from src import possession

NAN = (np.nan, np.nan)
PARADO = [(0, 0)]


def _resultado(cenario, bola, jogadores, **posse):
    frames, tracking, c = cenario(bola, jogadores, **posse)
    return possession.calcular(frames, tracking, c)


def test_fig3c1_muda_trajetoria_e_velocidade_ha_ganho_em_f0(cenario):
    """Fig. 3c1: a bola chega em +x, toca `pa` no quadro 3 e volta em -x com
    outra velocidade -> ganho no quadro 3, pelas duas vias."""
    r = _resultado(cenario, [(-2., 0), (-1., 0), (-.3, 0), (-1.2, 0), (-2.5, 0)],
                   {"pa": ("home", PARADO * 5)})
    ganhos = r["ganhos"]
    assert ganhos["frame"].tolist() == [3]
    assert ganhos["player_id"].tolist() == ["pa"]
    assert bool(ganhos["mudou_direcao"].iloc[0]) and bool(ganhos["mudou_velocidade"].iloc[0])
    assert ganhos["d0d1"].iloc[0] == pytest.approx(-1.0)
    assert ganhos["dv_max"].iloc[0] == pytest.approx(5.0)


def test_fig3c2_trajetoria_e_velocidade_constantes_nao_ha_ganho(cenario):
    """Fig. 3c2: a bola passa a 0,3 m de `pa` em linha reta e a velocidade
    constante -> sem ganho, e os control frames SAEM do passo de posse
    (§2.3.3, p. 5): nao viram posse, nao geram perda, viram `no_possession`.
    """
    bola = [(x, 0.0) for x in np.arange(-1.0, 1.01, 0.25)]
    r = _resultado(cenario, bola, {"pa": ("home", [(0, .3)] * len(bola))})
    assert r["ganhos"].empty
    assert r["perdas"].empty
    assert r["control"].empty
    assert r["sequencias"]["ganho"].tolist() == [False]
    assert r["contagens"]["quadros_falso_positivo"] == 3
    assert r["contagens"]["control_frames_zona"] == 3
    assert r["contagens"]["no_possession"] == len(bola)


def test_so_direcao_muda_ha_ganho(cenario):
    """Mesmo modulo de passo em todos os quadros (velocidade constante), com
    curva de 90 graus -> ganho so pela direcao."""
    r = _resultado(cenario, [(-.8, 0), (-.4, 0), (0, 0), (0, .4), (0, .8)],
                   {"pa": ("home", PARADO * 5)})
    g = r["ganhos"]
    assert g["frame"].tolist() == [2]
    assert bool(g["mudou_direcao"].iloc[0]) and not bool(g["mudou_velocidade"].iloc[0])
    assert g["d0d1"].iloc[0] == pytest.approx(0.0)
    assert g["dv_max"].iloc[0] == pytest.approx(0.0, abs=1e-9)


def test_so_velocidade_muda_ha_ganho(cenario):
    """Linha reta (direcao constante e NAO NaN) com passos diferentes -> ganho
    so pela velocidade. `d0d1` vale 1, isto e o teste de direcao rodou e disse
    "nao mudou" -- nao caiu no caminho do NaN."""
    r = _resultado(cenario, [(-1., 0), (-.45, 0), (-.2, 0), (.3, 0), (1., 0)],
                   {"pa": ("home", PARADO * 5)})
    g = r["ganhos"]
    assert g["frame"].tolist() == [2]
    assert not bool(g["mudou_direcao"].iloc[0]) and bool(g["mudou_velocidade"].iloc[0])
    assert g["d0d1"].iloc[0] == pytest.approx(1.0)
    assert g["dv_max"].iloc[0] == pytest.approx(7.5)


def test_produto_escalar_usa_vetores_unitarios(cenario):
    """Passo de entrada de 0,01 m (0,25 m/s) e de saida de 2,0 m (50 m/s), com
    5 graus entre eles.

    Com vetores unitarios o produto escalar e cos 5 = 0,9962 > eps_theta, logo a
    direcao NAO mudou. Sem normalizar daria 0,01 x 2,0 x cos 5 = 0,0199 <
    eps_theta, isto e "mudou". O caminho esta escolhido para que as duas
    implementacoes divirjam.
    """
    cinco = np.radians(5.0)
    r = _resultado(
        cenario,
        [(0.0, -0.01), (0.0, 0.0), (2.0 * np.sin(cinco), 2.0 * np.cos(cinco))],
        {"pa": ("home", [(0.0, 0.495)] * 3)},
    )
    g = r["ganhos"]
    assert g["frame"].tolist() == [2]
    assert g["d0d1"].iloc[0] == pytest.approx(np.cos(cinco))
    assert not bool(g["mudou_direcao"].iloc[0])
    assert bool(g["mudou_velocidade"].iloc[0])
    assert g["dv_max"].iloc[0] == pytest.approx(49.75)


def test_nan_no_primeiro_quadro_da_corrida_nao_e_mudanca_de_direcao(cenario):
    """Lacuna 3: a bola nasce no quadro 2 (quadro 1 morto), logo `d0` do primeiro
    quadro da sequencia e NaN -> a direcao NAO mudou, e o ganho sai so pela
    velocidade."""
    r = _resultado(cenario, [NAN, (.3, 0), (.1, 0), (.45, 0), (1.5, 0)],
                   {"pa": ("home", PARADO * 5)})
    g = r["ganhos"]
    assert g["frame"].tolist() == [2]
    assert np.isnan(g["d0d1"].iloc[0])
    assert not bool(g["mudou_direcao"].iloc[0])
    assert bool(g["mudou_velocidade"].iloc[0])


def test_nan_mais_velocidade_constante_nao_da_ganho(cenario):
    """Mesmo caminho do teste anterior, mas com velocidade constante: `d0` NaN
    nao conta como mudanca, `dv_max` = 0 nao passa de eps_v, e a sequencia
    inteira sai do passo de posse."""
    r = _resultado(cenario, [NAN, (-.25, 0), (0, 0), (.25, 0), (.5, 0)],
                   {"pa": ("home", [(0, .3)] * 5)})
    assert r["ganhos"].empty
    assert r["control"].empty
    assert r["contagens"]["quadros_falso_positivo"] == 3
    assert np.isnan(r["sequencias"]["d0d1"].iloc[0])
    assert r["sequencias"]["dv_max"].iloc[0] == pytest.approx(0.0, abs=1e-9)


def test_sequencia_nao_quebra_em_quadro_de_duelo(cenario):
    """A sequencia e geometrica e atravessa o duelo (§2.3.3, p. 5).

    A bola passa pela PZ de `pa` nos quadros 2 a 4 com passo constante de 0,4 m
    e VIRA 90 graus no quadro 3, que e exatamente o quadro em que `pb` entra na
    DZ e faz duelo. Com a sequencia atravessando o duelo, ha UMA sequencia [2,4]
    com `d0d1` = 0 -> ganho por direcao.

    Na leitura antiga (quebrar no duelo) seriam duas sequencias de um quadro,
    [2,2] e [4,4], cada uma com `d0d1` = 1 e `dv_max` = 0: nenhum ganho, e os
    dois quadros de posse sairiam do passo de posse como falso-positivos. O
    caminho esta escolhido para que as duas leituras divirjam no resultado.
    """
    r = _resultado(
        cenario,
        [(-0.8, 0), (-0.4, 0), (0.0, 0.0), (0.0, 0.4), (0.0, 0.8)],
        {"pa": ("home", PARADO * 5),
         "pb": ("away", [(3., 0), (2., 0), (0.9, 0), (2., 0), (3., 0)])},
    )
    assert r["sequencias"]["n_quadros"].tolist() == [3]
    assert r["sequencias"]["frame_f0"].tolist() == [2]
    assert r["sequencias"]["frame_fn"].tolist() == [4]
    g = r["ganhos"]
    assert g["frame"].tolist() == [2] and g["player_id"].tolist() == ["pa"]
    assert g["d0d1"].iloc[0] == pytest.approx(0.0)
    assert bool(g["mudou_direcao"].iloc[0]) and not bool(g["mudou_velocidade"].iloc[0])
    assert r["contagens"]["quadros_falso_positivo"] == 0
    assert r["control"]["ball_control"].tolist() == ["possession", "duel", "possession"]


def test_no_duelo_so_o_mais_proximo_tem_sequencia(cenario):
    """Um jogador em controle por quadro, mesmo em duelo: nenhum quadro tem dois
    ganhos.

    Os dois duelistas tem a bola na PZ nos quadros 2 e 3 (`pa` a 0,45 e 0,20 m;
    `pb` a 0,47 e 0,25 m), e `pa` e sempre o mais proximo. A lacuna 1 vale no
    duelo tambem (§2.4.1, p. 7), e o suplementar S5, p. 9, fala de recepcao em
    que *UM* jogador ganha a posse -> UMA sequencia, UM ganho.

    Este e o caminho que separa a leitura adotada da alternativa "todo jogador
    com a bola na PZ tem a sua sequencia": nela `pb` teria a sequencia [2,3] e
    haveria DOIS ganhos no quadro 2. Medida das duas no relatorio da revisao de
    2026-10-31.
    """
    r = _resultado(
        cenario,
        [(-0.8, 0), (-0.4, 0), (0.0, 0.0), (0.0, 0.4), (0.0, 0.8)],
        {"pa": ("home", [(0, 0.20)] * 5), "pb": ("away", [(0, -0.25)] * 5)},
    )
    assert len(r["sequencias"]) == 1
    assert r["sequencias"]["player_id"].tolist() == ["pa"]
    g = r["ganhos"]
    assert g["frame"].tolist() == [2] and g["player_id"].tolist() == ["pa"]
    assert r["contagens"]["quadros_com_mais_de_um_ganho"] == 0
    assert r["contagens"]["ganhos_em_quadro_de_duelo"] == 1
    assert r["contagens"]["possession"] == 0 and r["contagens"]["duel"] == 4


def test_eps_theta_varrido_muda_a_saida(posse_real):
    """nº de ganhos muda ao mexer SO em eps_theta (eps_v no valor congelado)."""
    congelado = posse_real(1)["contagens"]["ganhos"]
    assert congelado != posse_real(1, eps_theta=0.0)["contagens"]["ganhos"]


def test_eps_v_varrido_muda_a_saida(posse_real, cfg):
    """nº de ganhos muda ao mexer SO em eps_v (eps_theta no valor congelado)."""
    congelado = posse_real(1)["contagens"]["ganhos"]
    alternativo = posse_real(
        1, eps_v_ms=cfg["posse"]["diagnostico_eps_v_alt_ms"]
    )["contagens"]["ganhos"]
    assert congelado != alternativo

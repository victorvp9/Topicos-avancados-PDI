"""O padrao no primeiro quadro em jogo: a bola na `R_pz` e o executor.

Criterios e CAMINHO de cada teste: docs/fatias/04-plano.md §7.2.

O teste do executor roda com **dois candidatos no gatilho, a 0,2 e 0,4 m da
bola**, e com o `player_id` MENOR no candidato errado -- e o caminho em que "o
primeiro da zona" daria outra resposta (mesma construcao do teste do dono da
Fatia 3).
"""

import numpy as np
import pandas as pd

from src.events import bola_parada, gatilhos, padroes
from src.io import schema

BOLA_MORTA = [(0.0, 0.0)] + [(np.nan, np.nan)] * 8


def _periods(dir_home: int = 1) -> pd.DataFrame:
    """`periods` sintetico do jogo 1, periodo 1 (esquema PERIODS)."""
    return pd.DataFrame(
        [(1, 1, "away", -dir_home, 40.0 * dir_home),
         (1, 1, "home", dir_home, -40.0 * dir_home)],
        columns=list(schema.PERIODS),
    ).astype(schema.PERIODS)


def _passes(*pares) -> pd.DataFrame:
    """`passes` sintetico: pares `(player_id, quadro)`. Quem passa importa --
    o problema 1 do S1 mede o deslocamento do jogador que passa a bola."""
    return pd.DataFrame(
        {
            "player_id": pd.Series([p for p, _ in pares], dtype="str"),
            "frame": pd.Series([f for _, f in pares], dtype="int64"),
        }
    )


def _detectar(cenario, bola, jogadores, passes=(), dir_home=1):
    frames, tracking, cfg = cenario(bola, jogadores)
    return bola_parada.detectar(
        frames, tracking, _periods(dir_home), _passes(*passes), cfg
    )


def test_padrao_exige_a_bola_na_r_pz(cenario, cfg):
    """SINTETICO. `R_pz` = 0,50 m: bola a 0,3 m confirma o padrao, a 0,8 m nao.

    Com 0,8 m o TIPO sobrevive, mas por outro caminho: ninguem tem a bola na PZ,
    logo nao se pode checar padrao algum e o problema 3 do S1 decide pelo gatilho
    completo (`via = reserva_3`). E a `via` que separa os dois casos, e e por
    isso que ela existe.
    """
    assert cfg["posse"]["r_pz_m"] == 0.50
    assert padroes.na_pz(0.3, cfg) and not padroes.na_pz(0.8, cfg)
    meia = cfg["campo"]["largura_m"] / 2.0
    jogador = {"g1_home_1": ("home", [(0.0, meia - 0.2)] * 10),
               "g1_away_1": ("away", [(-20.0, -20.0)] * 10)}
    perto = _detectar(cenario, BOLA_MORTA + [(0.3, meia - 0.2)], jogador,
                      passes=[("g1_home_1", 10)])
    assert perto["type"].iloc[0] == "throw_in"
    assert perto["via"].iloc[0] == "padrao"
    longe = _detectar(cenario, BOLA_MORTA + [(0.8, meia - 0.2)], jogador,
                      passes=[("g1_home_1", 10)])
    assert longe["via"].iloc[0] != "padrao"


def test_executor_e_o_mais_proximo_da_bola(cenario, cfg):
    """SINTETICO, DOIS candidatos no gatilho a 0,2 e 0,4 m da bola.

    O `player_id` menor (`g1_home_1`) esta no candidato ERRADO, a 0,4 m: assim o
    teste falha se o codigo pegar o primeiro da zona em vez do mais proximo.
    """
    meia = cfg["campo"]["largura_m"] / 2.0
    det = _detectar(
        cenario,
        BOLA_MORTA + [(0.0, meia - 0.1)],
        {"g1_home_1": ("home", [(-0.4, meia - 0.1)] * 10),
         "g1_home_2": ("home", [(0.2, meia - 0.1)] * 10),
         "g1_away_1": ("away", [(-20.0, -20.0)] * 10)},
        passes=[("g1_home_2", 10)],
    )
    assert det["type"].iloc[0] == "throw_in"
    assert det["player_id"].iloc[0] == "g1_home_2"


def test_zona_do_padrao_coincide_com_a_do_gatilho_nos_tres_tipos(cfg):
    """SINTETICO. Fig. 4, p. 6: *"trigger and pattern zones coincide for
    corners, throw-ins and goal kicks"*. Falha se alguem mexer em uma das duas
    sem mexer na outra."""
    semente = np.random.default_rng(20261101)   # semente explicita
    x = semente.uniform(-60.0, 60.0, 500)
    y = semente.uniform(-40.0, 40.0, 500)
    lado = semente.choice([-1, 1], 500)
    zonas = padroes.zonas_padrao(x, y, lado, cfg)
    assert np.array_equal(zonas["corner_kick"], gatilhos.zona_escanteio(x, y, lado, cfg))
    assert np.array_equal(zonas["throw_in"], gatilhos.zona_lateral(y, cfg))
    assert np.array_equal(
        zonas["goal_kick"], gatilhos.zona_tiro_de_meta(x, y, lado, cfg)
    )


def test_nan_nunca_e_executor_e_nunca_esta_na_pz(cfg):
    """BORDA DE NaN. Jogador sem dado nao esta na PZ e nunca vence o desempate,
    mesmo marcado como candidato."""
    d = padroes.distancia_bola(np.array([np.nan, 2.0]), np.array([np.nan, 0.0]), 0.0, 0.0)
    assert not padroes.na_pz(d, cfg).any()
    candidatos = np.array([True, True])
    assert padroes.executor(candidatos, d) == 1          # o NaN perde para 2,0 m
    assert padroes.executor(candidatos, np.array([np.nan, np.nan])) == -1
    assert padroes.executor(np.array([False, False]), d) == -1


def test_executor_ausente_no_primeiro_quadro_vivo_nao_e_escolhido(cenario, cfg):
    """SINTETICO, BORDA DE NaN no primeiro quadro EM JOGO.

    O jogador do gatilho completo desaparece exatamente em `f1`: o padrao nao
    pode ser confirmado (nao ha posicao), e a deteccao sai por outra via -- nunca
    com ele como executor por `padrao`.
    """
    meia = cfg["campo"]["largura_m"] / 2.0
    det = _detectar(
        cenario,
        BOLA_MORTA + [(0.0, meia - 0.2)],
        {"g1_home_1": ("home", [(0.0, meia - 0.2)] * 9 + [(np.nan, np.nan)]),
         "g1_away_1": ("away", [(-20.0, -20.0)] * 10)},
        passes=[("g1_home_1", 10)],
    )
    assert det["via"].iloc[0] != "padrao"

"""Perda de posse: as duas condicoes, as figuras 3b e as lacunas 4 e 5.

Criterios e CAMINHO de cada teste: docs/fatias/03-plano.md §9.2.
`cenario` e `posse_real` sao fixtures de `tests/conftest.py`.

As duas colunas booleanas de `perdas` respondem a perguntas diferentes e os
testes asseveram as duas: `termina_corrida` (e a perda do ultimo quadro de posse
da corrida) e `so_por_lacuna_5` (e, ALEM disso, a regra literal nao dispara
ali). `so_por_lacuna_5 = False` numa perda de fim de corrida significa que as
condicoes 1 e 2 tambem estavam satisfeitas.
"""

import numpy as np
import pandas as pd
import pytest

from src import possession, run

NAN = (np.nan, np.nan)
PARADO = [(0, 0)]


def _perdas(cenario, bola, jogadores, **posse):
    frames, tracking, c = cenario(bola, jogadores, **posse)
    resultado = possession.calcular(frames, tracking, c)
    return resultado["perdas"], resultado


def test_fig3b1_bola_parada_e_jogador_se_afastando_nao_e_perda(cenario):
    """Fig. 3b1: a bola fica parada e o jogador se afasta -> sem perda.

    `pa` tem posse nos quadros 1 a 5 (com ganho, logo a sequencia sobrevive) e
    sai da PZ no quadro 6 porque ELE se move; `ds` no quadro 5 e 0 <= eps_s,
    logo a condicao 1 falha. A unica perda e a do fim da corrida, e ela e
    `so_por_lacuna_5` -- prova que a regra literal NAO disparou ali.
    """
    perdas, _ = _perdas(
        cenario,
        [(0.0, 0), (0.3, 0), (0.4, 0), (0.8, 0), (1.0, 0), (1.0, 0), (1.0, 0), (1.0, 0)],
        {"pa": ("home", [(0, .4), (.3, .4), (.4, .4), (.8, .4), (1., .4),
                         (1., .8), (1., 1.2), (1., 1.6)])},
    )
    assert perdas["frame"].tolist() == [5]
    assert perdas["termina_corrida"].tolist() == [True]
    assert perdas["so_por_lacuna_5"].tolist() == [True]
    assert perdas["ds_m"].to_numpy() == pytest.approx(0.0)


def test_fig3b2_bola_sai_da_pz_e_volta_sem_ninguem_tocar_nao_e_perda(cenario):
    """Fig. 3b2: a bola sai da PZ e volta sem ninguem tocar -> sem perda."""
    perdas, _ = _perdas(
        cenario,
        [(.4, 0), (.2, 0), (.3, 0), (.45, 0), (1., 0), (2., 0), (1.5, 0), (1., 0),
         (.45, 0), (.2, 0), (.3, 0), (.1, 0)],
        {"pa": ("home", PARADO * 12)},
    )
    assert perdas["frame"].tolist() == [12]
    assert perdas["termina_corrida"].tolist() == [True]
    assert perdas["so_por_lacuna_5"].tolist() == [True]


@pytest.mark.parametrize("time_de_pb", ["home", "away"])
def test_fig3b3_e_3b4_proximo_em_controle_e_outro_jogador_e_perda(cenario, time_de_pb):
    """Fig. 3b3/3b4: a bola sai e o proximo em controle e companheiro (3b3) ou
    adversario (3b4) -> perda nos dois casos."""
    perdas, _ = _perdas(
        cenario,
        [(.4, 0), (.2, 0), (.3, 0), (.45, 0), (1.5, 0), (3., 0), (4., 0),
         (4.6, 0), (4.8, 0), (5.2, 0), (5.1, 0)],
        {"pa": ("home", PARADO * 11), "pb": (time_de_pb, [(5., 0)] * 11)},
    )
    assert perdas["player_id"].tolist() == ["pa", "pb"]
    assert perdas["frame"].tolist() == [4, 11]
    assert perdas["termina_corrida"].tolist() == [False, True]
    assert perdas["so_por_lacuna_5"].tolist() == [False, True]
    assert perdas["ds_m"].iloc[0] == pytest.approx(1.05)


def test_condicao_1_isolada_sem_deslocamento_nao_ha_perda(cenario):
    """As duas condicoes sao CONJUNTAS: a bola sai da PZ de `pa` no quadro 6
    (porque `pa` se move) com `ds` = 0,03 m < eps_s = 0,05 m, e `pa` nao
    reaparece em control frame algum -> a condicao 2 esta satisfeita e so a 1
    falha. `pa` nao tem perda nenhuma; a do fim da corrida e de `pb`.
    """
    perdas, _ = _perdas(
        cenario,
        [(0, 0), (.3, 0), (.4, 0), (.8, 0), (.82, 0), (.85, 0), (2., 0), (3.5, 0),
         (4.6, 0), (4.8, 0), (5.2, 0), (5.1, 0)],
        {"pa": ("home", [(0, .45), (.3, .45), (.4, .45), (.8, .45), (.82, .45)]
                + [(.85, .6)] * 7),
         "pb": ("home", [(5., 0)] * 12)},
    )
    assert "pa" not in perdas["player_id"].tolist()
    assert perdas["player_id"].tolist() == ["pb"]
    assert perdas["termina_corrida"].tolist() == [True]


def test_condicao_2_isolada_a_reaparece_no_control_frame_seguinte(cenario):
    """Condicao 1 satisfeita e 2 nao: `ds` no quadro 3 e 0,25 m > eps_s e a bola
    sai da PZ no quadro 4, mas o control frame SEGUINTE (quadro 5) e de `pa` ->
    sem perda. So sobra a do fim da corrida.
    """
    perdas, resultado = _perdas(
        cenario,
        [(.3, 0), (.1, 0), (.45, 0), (.7, 0), (.45, 0), (.2, 0), (.3, 0)],
        {"pa": ("home", PARADO * 7)},
    )
    control = resultado["control"].set_index("frame")
    assert 4 not in control.index                      # a bola saiu da PZ
    assert control.loc[3, "ds_m"] > 0.05               # condicao 1 valia
    assert perdas["frame"].tolist() == [7]
    assert perdas["termina_corrida"].tolist() == [True]


def test_perda_quando_outro_toca_entre_duas_posses_de_a(cenario):
    """`pa` -> `pb` -> `pa` na MESMA corrida: `pa` perde no quadro 3.

    O control frame SEGUINTE ao quadro 3 e do `pb`, logo a condicao 2 esta
    satisfeita mesmo que `pa` recupere a bola depois. Este e o caminho que
    separa "o control frame seguinte" (docs/01, Passo 1, e §2.3.2, p. 5, no
    singular) de "algum control frame posterior na corrida": a segunda leitura
    nao emitiria perda aqui.
    """
    perdas, _ = _perdas(
        cenario,
        [(.3, 0), (.1, 0), (.45, 0), (1.5, 0), (2.1, 0), (2.3, 0), (2.6, 0),
         (1.5, 0), (.45, 0), (.2, 0), (.3, 0)],
        {"pa": ("home", PARADO * 11), "pb": ("away", [(2.5, 0)] * 11)},
    )
    assert perdas["frame"].tolist() == [3, 7, 11]
    assert perdas["player_id"].tolist() == ["pa", "pb", "pa"]
    assert perdas["termina_corrida"].tolist() == [False, False, True]
    assert perdas["so_por_lacuna_5"].tolist() == [False, False, True]


def test_fc_nao_atravessa_bola_morta(cenario):
    """Lacuna 4: `pa` sai no quadro 3, a bola morre, e `pa` volta na corrida 2.

    A perda fica registrada na corrida anterior. A asercao que DISCRIMINA e
    `so_por_lacuna_5 == False` no quadro 3: ela so vale False se as condicoes 1
    e 2 foram satisfeitas ali, isto e se a busca do `fc` NAO atravessou a bola
    morta. Se atravessasse, `pa` apareceria no quadro 7, a condicao 2 falharia e
    a linha do quadro 3 existiria de todo modo -- porque a lacuna 5 a produz --
    mas marcada `so_por_lacuna_5 = True`. Sem essa coluna o teste nao
    distinguiria as duas leituras.
    """
    perdas, resultado = _perdas(
        cenario,
        [(.3, 0), (.1, 0), (.45, 0), (1.5, 0), NAN, NAN, (.45, 0), (.2, 0), (.3, 0)],
        {"pa": ("home", PARADO * 9)},
    )
    assert perdas["frame"].tolist() == [3, 9]
    assert perdas["run_id"].tolist() == [1, 2]
    assert perdas["termina_corrida"].tolist() == [True, True]
    assert perdas["so_por_lacuna_5"].tolist() == [False, True]
    assert resultado["contagens"]["corridas_vivas"] == 2


@pytest.mark.parametrize("game", [1, 2, 3])
def test_toda_corrida_viva_com_posse_termina_em_perda(posse_real, game):
    """Lacuna 5, no dado real.

    DIVERGENCIA DO PLANO §9.2, aceita pelo orquestrador em 2026-10-30: o
    criterio escrito era "nº de forcadas igual ao nº de corridas vivas". No dado
    isso nao vale, porque ha corridas vivas sem nenhum quadro de posse (3, 9 e
    5 nos jogos 1, 2 e 3 com R_pz = 0,50 m). O invariante que vale e: **uma
    perda `termina_corrida` por corrida viva QUE TEM POSSE**, no ultimo quadro
    de posse dela.
    """
    resultado = posse_real(game)
    k, perdas = resultado["contagens"], resultado["perdas"]
    fim = perdas[perdas["termina_corrida"]]
    assert len(fim) == k["corridas_vivas"] - k["corridas_vivas_sem_posse"]
    assert len(fim) == k["perdas_termina_corrida"]
    assert not fim["run_id"].duplicated().any()
    # `so_por_lacuna_5` e um subconjunto proprio de `termina_corrida`.
    assert (perdas["so_por_lacuna_5"] <= perdas["termina_corrida"]).all()
    assert int(perdas["so_por_lacuna_5"].sum()) == k["perdas_so_por_lacuna_5"]
    assert 0 < k["perdas_so_por_lacuna_5"] < k["perdas_termina_corrida"]

    control = resultado["control"]
    ultima_posse = (
        control[control["ball_control"] == possession.POSSESSION]
        .groupby("run_id")["frame"].max()
    )
    assert fim.set_index("run_id")["frame"].equals(
        ultima_posse.reindex(fim["run_id"]).rename("frame")
    )


def test_reinicio_depois_da_perda(cfg):
    """O diagnostico da lacuna 5 casa cada perda com o PROXIMO reinicio.

    Perda em 100 -> tiro livre em 150; perda em 200 -> lateral em 250; perda em
    300 -> nao ha reinicio depois, logo `nenhum`. O `pass` em 120 nao e
    reinicio e nao pode roubar o casamento.
    """
    perdas = pd.DataFrame({"game": [1, 1, 1], "frame": [100, 200, 300]}).astype("int64")
    eventos = pd.DataFrame(
        {
            "game": np.ones(3, dtype="int64"),
            "frame": np.array([120, 150, 250], dtype="int64"),
            "type": ["pass", "free_kick", "throw_in"],
        }
    )
    contagem = run.reinicio_depois_da_perda(perdas, eventos, cfg)
    assert contagem.to_dict() == {"free_kick": 1, "throw_in": 1, "nenhum": 1}


def test_eps_s_varrido_muda_a_saida(posse_real, cfg):
    """nº de perdas muda entre eps_s = 5 cm (congelado) e 10 cm (provedores B/C)."""
    congelado = posse_real(1)["contagens"]["perdas"]
    alternativo = posse_real(
        1, eps_s_m=cfg["posse"]["diagnostico_eps_s_alt_m"]
    )["contagens"]["perdas"]
    assert congelado != alternativo

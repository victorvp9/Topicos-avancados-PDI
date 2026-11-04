"""Rotulo e supressao dos passes. Criterios e CAMINHO: docs/fatias/05-plano.md §7.1.

Os testes sinteticos montam as tabelas do Passo 1 (`perdas`, `ganhos`,
`control`) A MAO, porque `passes.rotular` so as le: assim cada caso isola a
regra do rotulo. Consequencia declarada no "A -> B -> C": pelo Passo 1 real o
ultimo jogador em controle SEMPRE recebe perda no fim da corrida (lacuna 5 da
Fatia 3), logo "exatamente dois passes" so e alcancavel com a tabela montada a
mao, em que C nao perde a bola. A integracao com o Passo 1 roda nos testes de
dado real (`passes_real`, `posse_real` em `tests/conftest.py`).
"""

import numpy as np
import pandas as pd
import pytest

from src import possession
from src.events import passes

FPS = 25


def _frames(n, mortos=(), troca_de_periodo=None):
    """Quadros 1..n; `mortos` e a lista de quadros com bola morta; a partir de
    `troca_de_periodo` o periodo e 2."""
    quadro = np.arange(1, n + 1)
    vivo = ~np.isin(quadro, list(mortos))
    period = np.ones(n, dtype="int64")
    if troca_de_periodo is not None:
        period[quadro >= troca_de_periodo] = 2
    return pd.DataFrame({"game": 1, "period": period, "frame": quadro, "t": quadro / FPS,
                         "ball_x": np.where(vivo, 0.0, np.nan),
                         "ball_y": np.where(vivo, 0.0, np.nan), "ball_live": vivo})


def _linhas(frames, linhas, esquema, extra):
    """`linhas` = [(quadro, jogador, time), ...] no esquema `esquema` do Passo 1."""
    run_id = possession.corridas_vivas(frames["ball_live"].to_numpy())[0]
    por_quadro = frames.set_index("frame")["period"]
    df = pd.DataFrame(
        [
            {"game": 1, "period": int(por_quadro[f]), "frame": f, "t": f / FPS,
             "player_id": p, "team": time, "run_id": int(run_id[f - 1]), **extra}
            for f, p, time in linhas
        ],
        columns=list(esquema),
    )
    return df.astype(esquema)


def _perdas(frames, linhas):
    return _linhas(frames, linhas, possession.PERDAS,
                   {"termina_corrida": False, "so_por_lacuna_5": False, "ds_m": 1.0})


def _ganhos(frames, linhas):
    return _linhas(frames, linhas, possession.GANHOS,
                   {"mudou_direcao": True, "mudou_velocidade": True, "d0d1": -1.0,
                    "dv_max": 5.0})


def _control(duelos=()):
    """So as duas colunas que `rotular` le: os quadros de duelo."""
    return pd.DataFrame({"frame": list(duelos), "ball_control": possession.DUEL})


def _det(linhas=()):
    """Deteccoes de bola parada: [(quadro do 1o quadro vivo, executor), ...]."""
    return pd.DataFrame(list(linhas), columns=["frame", "player_id"])


def _rotular(frames, perdas, ganhos=(), duelos=(), det=()):
    return passes.rotular(_perdas(frames, perdas), _ganhos(frames, list(ganhos)),
                          _control(duelos), frames, _det(det))


# --- desfecho ----------------------------------------------------------------


def test_a_b_c_dois_passes_completos():
    """Sintetico, um time: A perde, B ganha, B perde, C ganha -> exatamente dois
    passes, `completo` e `completo`, com os receptores certos."""
    f = _frames(30)
    p = _rotular(f, [(5, "A", "home"), (15, "B", "home")],
                 [(8, "B", "home"), (20, "C", "home")])
    assert len(p) == 2 and not p["e_bola_parada"].any()
    assert p["desfecho"].tolist() == ["completo", "completo"]
    assert p["receptor_id"].tolist() == ["B", "C"]
    assert (p["type"] == "pass").all()


def test_adversario_ganha_e_interceptado():
    p = _rotular(_frames(20), [(5, "A", "home")], [(8, "X", "away")])
    assert p["desfecho"].tolist() == ["interceptado"]
    assert p["receptor_id"].tolist() == ["X"]


def test_bola_sai_ainda_e_passe_bola_morta():
    """A perde e a bola sai: o passe EXISTE, com desfecho `bola_morta`, e vai
    ao casador (nunca e excluido)."""
    f = _frames(20, mortos=range(11, 16))
    p = _rotular(f, [(10, "A", "home")])
    assert p["desfecho"].tolist() == ["bola_morta"]
    assert p["receptor_id"].tolist() == [""]
    assert len(passes.para_casador(p)) == 1


def test_fim_do_jogo_sem_ganho_e_fim_de_periodo():
    p = _rotular(_frames(20), [(15, "A", "home")])
    assert p["desfecho"].tolist() == ["fim_de_periodo"]


def test_troca_de_periodo_com_bola_viva_e_fim_de_periodo_nao_bola_morta():
    """O periodo 1 termina com a bola VIVA no quadro 10: `fim_de_periodo`. A
    mesma perda com um quadro morto no fim do periodo daria `bola_morta`."""
    assert _rotular(_frames(20, troca_de_periodo=11),
                    [(5, "A", "home")])["desfecho"].tolist() == ["fim_de_periodo"]
    assert _rotular(_frames(20, mortos=[10], troca_de_periodo=11),
                    [(5, "A", "home")])["desfecho"].tolist() == ["bola_morta"]


def test_a_recupera_com_duelo_no_meio_e_proprio_e_fica_fora_do_principal():
    """A perde, ha duelo (outro jogador perto, sem ganho dele) e A ganha de
    novo -> `proprio`, nao `completo`; o principal nao o ve."""
    p = _rotular(_frames(20), [(5, "A", "home")], [(10, "A", "home")], duelos=[7, 8])
    assert p["desfecho"].tolist() == ["proprio"]
    assert not bool(p["recepcao_em_duelo"].iloc[0])
    assert passes.para_casador(p, so_completo=True).empty
    assert len(passes.para_casador(p)) == 1


@pytest.mark.parametrize("time_receptor,esperado", [("home", "completo"),
                                                    ("away", "interceptado")])
def test_ganho_em_quadro_de_duelo(time_receptor, esperado):
    """`recepcao_em_duelo` liga, e o desfecho segue o time do receptor."""
    p = _rotular(_frames(20), [(5, "A", "home")], [(8, "B", time_receptor)], duelos=[8, 9])
    assert bool(p["recepcao_em_duelo"].iloc[0])
    assert p["desfecho"].tolist() == [esperado]


def test_proximo_ganho_nao_atravessa_corrida():
    """O unico ganho depois da perda esta na corrida viva SEGUINTE."""
    f = _frames(20, mortos=range(11, 14))
    p = _rotular(f, [(8, "A", "home")], [(16, "B", "home")])
    assert p["desfecho"].tolist() == ["bola_morta"]
    assert p["receptor_id"].tolist() == [""]


def test_proximo_ganho_nao_atravessa_periodo():
    """Bola viva atravessando a troca de periodo: perda e ganho tem o MESMO
    `run_id` (`corridas_vivas` nao corta por periodo), so o periodo difere.
    Sem a checagem de periodo isto daria `completo`."""
    f = _frames(20, troca_de_periodo=11)
    p = _rotular(f, [(8, "A", "home")], [(13, "B", "home")])
    assert p["desfecho"].tolist() == ["fim_de_periodo"]


def test_so_o_proximo_ganho_decide():
    """Primeiro ganho adversario, depois de companheiro: `interceptado`."""
    p = _rotular(_frames(20), [(5, "A", "home")], [(8, "X", "away"), (12, "B", "home")])
    assert p["desfecho"].tolist() == ["interceptado"]


def test_desfecho_fora_do_dominio_estoura():
    p = _rotular(_frames(20), [(5, "A", "home")], [(8, "B", "home")])
    p.loc[0, "desfecho"] = "gol"
    with pytest.raises(ValueError, match="fora de"):
        passes.validar(p)


# --- supressao da perda de reinicio -------------------------------------------


def test_supressao_independe_do_jogador():
    """A primeira perda da corrida e de jogador != executor detectado: e ela que
    sai. A regra "so do executor" suprimiria a do quadro 15."""
    f = _frames(30, mortos=range(1, 6))
    p = _rotular(f, [(9, "outro", "home"), (15, "exec", "home")], det=[(6, "exec")])
    assert p["e_bola_parada"].tolist() == [True, False]


def test_uma_supressao_por_bola_parada():
    f = _frames(30, mortos=range(1, 6))
    p = _rotular(f, [(8, "A", "home"), (12, "B", "home"), (20, "C", "home")],
                 det=[(6, "A")])
    assert p["e_bola_parada"].tolist() == [True, False, False]
    assert len(passes.para_casador(p)) == 2


def test_perda_no_proprio_quadro_da_deteccao_e_suprimida():
    """`frame >=` o da deteccao: inclusiva."""
    f = _frames(20, mortos=range(1, 6))
    p = _rotular(f, [(6, "A", "home"), (10, "A", "home")], det=[(6, "A")])
    assert p["e_bola_parada"].tolist() == [True, False]


def test_corrida_sem_perda_nao_suprime_a_da_corrida_seguinte():
    """A bola parada do quadro 6 abre uma corrida sem perda; a perda do quadro
    16 e de OUTRA corrida e nao pode ser suprimida por ela."""
    f = _frames(30, mortos=list(range(1, 6)) + list(range(11, 14)))
    p = _rotular(f, [(16, "A", "home")], det=[(6, "A")])
    assert p["e_bola_parada"].tolist() == [False]


def test_suprimir_estoura_com_perdas_fora_de_ordem():
    f = _frames(30, mortos=range(1, 6))
    perdas = _perdas(f, [(15, "B", "home"), (9, "A", "home")])
    with pytest.raises(ValueError, match="fora de ordem"):
        passes.suprimir(perdas, _det([(6, "A")]), f)


def test_sem_perda_nenhuma_nada_quebra():
    f = _frames(20, mortos=range(1, 6))
    p = _rotular(f, [], det=[(6, "A")])
    assert p.empty
    passes.validar(p)


def test_sem_deteccao_e_sem_ganho():
    p = _rotular(_frames(20), [(5, "A", "home")])
    assert p["e_bola_parada"].tolist() == [False]


# --- dado real ----------------------------------------------------------------

JOGOS = (1, 2, 3)


@pytest.mark.parametrize("game", JOGOS)
def test_unclear_e_inalcancavel_nenhuma_perda_em_quadro_de_duelo(posse_real, game):
    """Dado real, 3 jogos: o Passo 1 so emite perda em quadro de POSSE, logo o
    desfecho *"unclear if there is a duel at passing time"* (S5, p. 9) e
    inalcancavel. Trava isso contra mudanca futura no Passo 1."""
    r = posse_real(game)
    rotulo = r["control"].set_index("frame")["ball_control"]
    assert (rotulo.reindex(r["perdas"]["frame"]) == possession.POSSESSION).all()


@pytest.mark.parametrize("game", JOGOS)
def test_identidade_das_contagens(passes_real, posse_real, game):
    """Dado real: passes = perdas - suprimidas; suprimidas <= deteccoes de bola
    parada; soma dos desfechos = passes; uma linha por perda."""
    p, det = passes_real(game)
    perdas = posse_real(game)["perdas"]
    assert len(p) == len(perdas)
    suprimidas = int(p["e_bola_parada"].sum())
    n_passes = len(passes.para_casador(p))
    assert n_passes == len(perdas) - suprimidas
    assert 0 < suprimidas <= len(det)
    assert int(p.loc[~p["e_bola_parada"], "desfecho"].value_counts().sum()) == n_passes
    assert set(p["desfecho"]) <= set(passes.DESFECHOS)


def test_mudar_r_pz_muda_a_saida(passes_real):
    """Dado real, jogo 1: `R_pz` 0,50 -> 1,00 m muda o numero de passes."""
    a = len(passes.para_casador(passes_real(1)[0]))
    b = len(passes.para_casador(passes_real(1, r_pz_m=1.00)[0]))
    assert a != b

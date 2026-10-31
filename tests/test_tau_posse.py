"""`tau_posse` e a escada pre-registrada que decide a janela do criterio.

Criterios e CAMINHO de cada teste: docs/fatias/03-plano.md §9.5. A separacao do
plano §6.1 e testada explicitamente: a fracao da regra usa SO os passes com
perda, e a fracao sem perda sai em separado -- misturar as duas foi o erro da
Fatia 2.
"""

import copy

import numpy as np
import pandas as pd
import pytest

from src import possession, run, tau_posse

FPS = 25  # so para montar os cenarios sinteticos em quadros; o codigo usa o cfg


def eventos_de(linhas) -> pd.DataFrame:
    """[(game, annotated_frame, player_id)] -> projecao minima de EVENTS.

    `tau_posse.medir` le so `type`, `game`, `annotated_frame` e `player_id`; o
    teste nao monta o esquema EVENTS inteiro de proposito.
    """
    df = pd.DataFrame(linhas, columns=["game", "annotated_frame", "player_id"])
    df["type"] = "pass"
    return df.astype({"game": "int64", "annotated_frame": "int64",
                      "player_id": "str", "type": "str"})


def perdas_de(linhas) -> pd.DataFrame:
    """[(game, frame, player_id)] -> projecao minima de PERDAS."""
    return pd.DataFrame(linhas, columns=["game", "frame", "player_id"]).astype(
        {"game": "int64", "frame": "int64", "player_id": "str"}
    )


def control_de(linhas) -> pd.DataFrame:
    """[(game, frame, owner_id)] -> projecao minima de CONTROL, toda de posse."""
    df = pd.DataFrame(linhas, columns=["game", "frame", "owner_id"])
    df["ball_control"] = possession.POSSESSION
    return df.astype({"game": "int64", "frame": "int64", "owner_id": "str",
                      "ball_control": "str"})


def tabela_sintetica(taus_s, n_sem_perda=0):
    """Tabela TAU_POSSE com `tau` dado em segundos e `n_sem_perda` sem perda."""
    linhas = [
        (1, 1000 + 1000 * i, "p{}".format(i), 1000 + 1000 * i - round(tau * FPS), tau, True)
        for i, tau in enumerate(taus_s)
    ]
    linhas += [
        (1, 500000 + i, "sem{}".format(i), np.nan, np.nan, False) for i in range(n_sem_perda)
    ]
    return pd.DataFrame(linhas, columns=list(tau_posse.TAU_POSSE)).astype(
        tau_posse.TAU_POSSE
    )


# --- medicao ----------------------------------------------------------------

def test_sinal_de_tau(cfg):
    """Perda 2 s ANTES do quadro anotado -> tau = +2,0 s (convencao da Fatia 2)."""
    tabela = tau_posse.medir(
        eventos_de([(1, 1000, "pa")]), perdas_de([(1, 950, "pa")]), cfg
    )
    assert tabela["tau_posse_s"].tolist() == [pytest.approx(2.0)]
    assert tabela["loss_frame"].tolist() == [950.0]
    assert tabela["tem_perda"].tolist() == [True]


def test_passe_sem_perda_fica_na_tabela(cfg):
    """Perda existe, mas de OUTRO jogador: a linha fica, com NaN."""
    tabela = tau_posse.medir(
        eventos_de([(1, 1000, "pa")]), perdas_de([(1, 1000, "pb")]), cfg
    )
    assert len(tabela) == 1
    assert not bool(tabela["tem_perda"].iloc[0])
    assert np.isnan(tabela["tau_posse_s"].iloc[0])


@pytest.mark.parametrize("desloc, esperado", [(225, True), (250, True), (275, False)])
def test_janela_de_busca_e_o_valor_do_config(cfg, desloc, esperado):
    """A janela e `tau_posse.janela_busca_s` = 10 s = 250 quadros, INCLUSIVA."""
    assert cfg["tau_posse"]["janela_busca_s"] * cfg["tracking"]["fps"] == 250
    tabela = tau_posse.medir(
        eventos_de([(1, 1000, "pa")]), perdas_de([(1, 1000 + desloc, "pa")]), cfg
    )
    assert bool(tabela["tem_perda"].iloc[0]) is esperado


def test_empate_fica_com_a_perda_anterior(cfg):
    """Perdas a 50 quadros antes e 50 depois: vence a anterior (deterministico)."""
    tabela = tau_posse.medir(
        eventos_de([(1, 1000, "pa")]),
        perdas_de([(1, 950, "pa"), (1, 1050, "pa")]),
        cfg,
    )
    assert tabela["loss_frame"].tolist() == [950.0]
    assert tabela["tau_posse_s"].tolist() == [pytest.approx(2.0)]


def test_outro_jogo_nao_casa(cfg):
    """A busca e por (jogo, jogador): mesma numeracao de quadro em outro jogo
    nao pode casar."""
    tabela = tau_posse.medir(
        eventos_de([(1, 1000, "pa")]), perdas_de([(2, 1000, "pa")]), cfg
    )
    assert not bool(tabela["tem_perda"].iloc[0])


# --- o portao ---------------------------------------------------------------

def test_denominador_do_portao_usa_so_os_que_tem_perda(cfg):
    """5 com perda (1 acima de 1 s) e 5 sem perda.

    A fracao da regra e 1/5 = 20 %, NAO 1/10 = 10 %: o denominador e o dos
    passes COM perda (plano §6.1). A fracao sem perda sai em separado.
    """
    tabela = tabela_sintetica([0.0, 0.04, -0.08, 0.2, 3.0], n_sem_perda=5)
    d = tau_posse.decidir_janela(tabela, cfg)
    assert d["n"] == 10 and d["n_com_perda"] == 5
    assert d["fracoes"][1.0] == pytest.approx(0.2)
    assert d["frac_sem_perda"] == pytest.approx(0.5)
    resumo = tau_posse.resumir(tabela, cfg).set_index("game")
    assert resumo.loc[0, "frac_tau_gt_1s"] == pytest.approx(0.2)
    assert resumo.loc[0, "frac_sem_perda"] == pytest.approx(0.5)


def test_escada_escolhe_o_menor_degrau_que_satisfaz(cfg):
    """10 % acima de 1 s e 3 % acima de 1,5 s -> a escada devolve 1,5 s."""
    tabela = tabela_sintetica([0.0] * 90 + [1.2] * 7 + [2.0] * 3)
    d = tau_posse.decidir_janela(tabela, cfg)
    assert d["fracoes"][1.0] == pytest.approx(0.10)
    assert d["fracoes"][1.5] == pytest.approx(0.03)
    assert d["janela_s"] == 1.5
    assert d["esgotada"] is False and d["g3"] is False


def test_escada_esgotada_devolve_none_e_g3(cfg):
    """10 % acima de 3,0 s -> nenhum degrau serve: `None` e `g3 = True`."""
    d = tau_posse.decidir_janela(tabela_sintetica([0.0] * 90 + [4.0] * 10), cfg)
    assert d["janela_s"] is None
    assert d["esgotada"] is True and d["g3"] is True


def test_nunca_devolve_valor_fora_da_escada(cfg):
    """200 distribuicoes aleatorias (semente fixa): a saida esta sempre na
    escada ou e `None`. Mata o mutante que interpola ou devolve percentil."""
    rng = np.random.default_rng(20261030)
    escada = [float(v) for v in cfg["tau_posse"]["escada_janela_s"]]
    for _ in range(200):
        taus = rng.normal(0.0, rng.uniform(0.05, 4.0), size=rng.integers(5, 300))
        janela = tau_posse.decidir_janela(tabela_sintetica(taus.tolist()), cfg)["janela_s"]
        assert janela is None or janela in escada


def test_fracao_sem_perda_alta_leva_ao_g3_mesmo_com_a_escada_satisfeita(cfg):
    """Portao e teto de revocacao sao coisas diferentes: aqui a escada fecha em
    1,0 s e ainda assim e G3, porque 25 % dos passes nao tem perda nenhuma."""
    tabela = tabela_sintetica([0.0] * 75, n_sem_perda=25)
    d = tau_posse.decidir_janela(tabela, cfg)
    assert d["janela_s"] == 1.0
    assert d["frac_sem_perda"] == pytest.approx(0.25)
    assert d["sem_perda_acima_do_limiar"] is True and d["g3"] is True


@pytest.mark.parametrize("dono_da_perda, esperado", [("pa", 0), ("pb", 1)])
def test_casou_outro_jogador_e_medido_nao_assumido(cfg, dono_da_perda, esperado):
    """(iii) tem de PEGAR um casamento com perda de outro jogador.

    A tabela `TAU_POSSE` diz que o passe do `pa` casou com a perda do quadro
    950. Se essa perda for do `pb`, (iii) = 1. Sem este caminho, trocar a
    medicao por `zeros(n)` passaria na suite -- o zero do dado real nao seria
    evidencia de nada.
    """
    tabela = pd.DataFrame(
        [(1, 1000, "pa", 950.0, 2.0, True)], columns=list(tau_posse.TAU_POSSE)
    ).astype(tau_posse.TAU_POSSE)
    dec = tau_posse.decompor_sem_perda(
        tabela,
        control_de([(1, 1000, "pa")]),
        perdas_de([(1, 950, dono_da_perda)]),
        cfg,
    ).set_index("game")
    assert dec.loc[0, "casou_outro_jogador"] == esperado


@pytest.mark.parametrize(
    "desloc_control, sem_control, com_control", [(0, 1, 1), (275, 2, 0)]
)
def test_decomposicao_dos_sem_perda(cfg, desloc_control, sem_control, com_control):
    """`pa` tem perda; `pb` nao tem perda mas foi dono de control frame; `pc`
    nao tem control frame nenhum.

    No segundo caso o control frame do `pb` esta a 11 s (275 quadros) do quadro
    anotado, isto e FORA da janela, e `pb` cai em (i) junto com `pc`: o teste
    roda nos dois lados da janela, senao nao distinguiria (i) de (ii).
    """
    tabela = tau_posse.medir(
        eventos_de([(1, 1000, "pa"), (1, 5000, "pb"), (1, 9000, "pc")]),
        perdas_de([(1, 1001, "pa")]),
        cfg,
    )
    dec = tau_posse.decompor_sem_perda(
        tabela,
        control_de([(1, 1000, "pa"), (1, 5000 + desloc_control, "pb")]),
        perdas_de([(1, 1001, "pa")]),
        cfg,
    ).set_index("game")
    assert dec.loc[0, "n"] == 3 and dec.loc[0, "n_sem_perda"] == 2
    assert dec.loc[0, "sem_control_frame"] == sem_control
    assert dec.loc[0, "com_control_sem_perda"] == com_control
    assert dec.loc[0, "casou_outro_jogador"] == 0


# --- cada chave de config, com teste sensivel ao VALOR ----------------------
# Plano §2: nao basta o teste passar com o valor atual; ele tem de FALHAR se o
# valor for ignorado. Cada teste abaixo roda com um valor DIFERENTE do que esta
# no `config.yaml`, logo mata o mutante que fixa a constante no codigo.

def _cfg_tau(cfg, **troca):
    novo = copy.deepcopy(cfg)
    novo["tau_posse"].update(troca)
    return novo


@pytest.mark.parametrize("janela_s, desloc, esperado", [(4.0, 100, True), (4.0, 150, False)])
def test_valor_de_janela_busca_s_e_usado(cfg, janela_s, desloc, esperado):
    """Com `janela_busca_s` = 4 s (100 quadros), uma perda a 150 quadros fica
    FORA -- o que o mutante "250 quadros fixos" aceitaria."""
    tabela = tau_posse.medir(
        eventos_de([(1, 1000, "pa")]),
        perdas_de([(1, 1000 + desloc, "pa")]),
        _cfg_tau(cfg, janela_busca_s=janela_s),
    )
    assert bool(tabela["tem_perda"].iloc[0]) is esperado


@pytest.mark.parametrize("limiar, esperado", [(0.01, 2.0), (0.05, 1.5), (0.15, 1.0)])
def test_valor_de_limiar_fracao_e_usado(cfg, limiar, esperado):
    """A MESMA distribuicao (10 % acima de 1 s, 3 % acima de 1,5 s) escolhe
    degrau diferente para cada `limiar_fracao`.

    Com limiar de 1 % o degrau e 2,0 s e nao `None`: a comparacao da regra e
    ESTRITA (`|tau| > janela`) e os tres atrasos valem exatamente 2,0 s.
    """
    tabela = tabela_sintetica([0.0] * 90 + [1.2] * 7 + [2.0] * 3)
    d = tau_posse.decidir_janela(tabela, _cfg_tau(cfg, limiar_fracao=limiar))
    assert d["janela_s"] == esperado


def test_valor_de_escada_janela_s_e_usado(cfg):
    """Com a escada [0,5; 2,5], a saida tem de ser 2,5 s -- valor que NAO esta
    na escada do `config.yaml`."""
    tabela = tabela_sintetica([0.0] * 90 + [1.2] * 7 + [2.0] * 3)
    d = tau_posse.decidir_janela(tabela, _cfg_tau(cfg, escada_janela_s=[0.5, 2.5]))
    assert d["janela_s"] == 2.5
    assert sorted(d["fracoes"]) == [0.5, 2.5]


@pytest.mark.parametrize("limiar, esperado", [(0.20, True), (0.50, False)])
def test_valor_de_limiar_sem_perda_g3_e_usado(cfg, limiar, esperado):
    """25 % sem perda: G3 com limiar de 20 %, nao com 50 %."""
    d = tau_posse.decidir_janela(
        tabela_sintetica([0.0] * 75, n_sem_perda=25),
        _cfg_tau(cfg, limiar_sem_perda_g3=limiar),
    )
    assert d["sem_perda_acima_do_limiar"] is esperado and d["g3"] is esperado


def test_valor_de_r_pz_da_decisao_e_usado(posse_real, cfg, mapeamento, eventos, tmp_path):
    """Com `r_pz_da_decisao_m` = 3,00 m, a medicao tem de ser a de 3,00 m.

    Mata o mutante que fixa 0,50 m: o par com o teste
    `test_decisao_usa_o_r_pz_travado` (que prova a igualdade com 0,50 m) prende
    o VALOR, nao so o nome da chave.
    """
    tabela = run.medir_tau_posse(
        _cfg_tau(cfg, r_pz_da_decisao_m=3.00, r_pz_sensibilidade_m=[3.00]),
        mapeamento, [1], gravar_em=tmp_path / "c.csv",
    )
    esperada = tau_posse.medir(eventos(1)[1], posse_real(1, r_pz_m=3.00)["perdas"], cfg)
    assert tabela.equals(esperada)


# --- dado real --------------------------------------------------------------

def test_decisao_usa_o_r_pz_travado(posse_real, cfg, mapeamento, eventos, tmp_path):
    """A decisao usa `tau_posse.r_pz_da_decisao_m` mesmo que `posse.r_pz_m`
    esteja em outro valor -- e 3,00 m DARIA outro resultado se fosse usado,
    o que e o que torna o teste nao-vazio.

    LIMITE DECLARADO: o travamento e do `R_pz`. O `R_dz` da medicao sai de
    `src.possession.raios`, logo mexer em `posse.r_dz_m` ou em
    `posse.r_dz_politica` -- e so neles -- moveria a decisao. A asercao abaixo
    deixa explicito que `com_r_pz` nao toca nenhum dos dois.
    """
    outro = copy.deepcopy(cfg)
    outro["posse"]["r_pz_m"] = 3.00
    assert run.com_r_pz(outro, cfg["tau_posse"]["r_pz_da_decisao_m"])["posse"] == (
        run.com_r_pz(cfg, cfg["tau_posse"]["r_pz_da_decisao_m"])["posse"]
    )
    com_outro = run.medir_tau_posse(outro, mapeamento, [1], gravar_em=tmp_path / "a.csv")
    padrao = run.medir_tau_posse(cfg, mapeamento, [1], gravar_em=tmp_path / "b.csv")
    assert com_outro.equals(padrao)

    perdas_3m = posse_real(1, r_pz_m=3.00)["perdas"]
    a_3m = tau_posse.medir(eventos(1)[1], perdas_3m, cfg)
    assert not a_3m.equals(padrao)


def test_medicao_real_fecha_com_o_gabarito(posse_real, cfg, eventos):
    """n = numero de passes do gabarito, e nenhuma linha e descartada."""
    ev = eventos(1)[1]
    perdas = posse_real(1)["perdas"]
    tabela = tau_posse.medir(ev, perdas, cfg)
    assert len(tabela) == int((ev["type"] == "pass").sum())
    assert tabela["tem_perda"].sum() == tabela["loss_frame"].notna().sum()
    casadas = tabela.loc[tabela["tem_perda"], "loss_frame"]
    assert casadas.isin(perdas["frame"].to_numpy()).all()
    assert possession.PERDAS["frame"] == "int64"


def test_decomposicao_real_fecha_e_nao_casa_outro_jogador(posse_real, cfg, eventos):
    """As tres parcelas somam `n_sem_perda`, e (iii) e zero no dado real."""
    resultado = posse_real(1)
    tabela = tau_posse.medir(eventos(1)[1], resultado["perdas"], cfg)
    dec = tau_posse.decompor_sem_perda(
        tabela, resultado["control"], resultado["perdas"], cfg
    ).set_index("game")
    assert dec.loc[1, "sem_control_frame"] + dec.loc[1, "com_control_sem_perda"] == (
        dec.loc[1, "n_sem_perda"]
    )
    assert dec.loc[1, "n_sem_perda"] == int((~tabela["tem_perda"]).sum())
    assert dec.loc[1, "casou_outro_jogador"] == 0
    assert dec.loc[1, "com_control_sem_perda"] > 0 and dec.loc[1, "sem_control_frame"] > 0

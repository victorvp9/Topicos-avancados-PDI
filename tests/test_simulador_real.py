"""Testes do simulador de broadcast nos dados reais (plano 06 §7: T1, T2, T3,
T4, T8, T11). Nenhum teste aqui calcula ou asserta P/R/F1 (plano §6)."""

import copy
from functools import lru_cache

import numpy as np
import pandas as pd
import pytest

from src import broadcast, possession
from src.config import carregar_config, carregar_mapeamento
from src.events import passes as passes_mod
from src.io import schema
from src.run import _carregar_base, detectar_jogos, rotular_jogos

NIVEIS = [(v, n) for v in ("B", "A") for n in range(1, 9)]


@lru_cache(maxsize=None)
def _pipeline(degradacao):
    """(`base`, deteccoes de bola parada, passes) do jogo 1, memorizado."""
    cfg = carregar_config()
    base = _carregar_base(cfg, carregar_mapeamento(cfg), [1], degradacao)
    det = detectar_jogos(base, cfg, [1])
    return base, det, rotular_jogos(base, det, [1])


# --- T1 -------------------------------------------------------------------------

@pytest.mark.parametrize("game", [1, 2, 3])
@pytest.mark.parametrize("variante", ["A", "B"])
def test_t1_nivel_1_reproduz_o_tracking_bit_a_bit(jogo, cfg, game, variante):
    frames, tracking, _ = jogo(game)
    saida = broadcast.degradar(tracking, frames, cfg, variante, 1, 0)
    pd.testing.assert_frame_equal(saida, tracking, check_exact=True)


@pytest.mark.parametrize("variante", ["A", "B"])
def test_t1_nivel_1_reproduz_o_pipeline_no_jogo_1(variante):
    teto, det0, pas0 = _pipeline(None)
    base, det, pas = _pipeline((variante, 1, 0))
    for chave in ("perdas", "ganhos"):
        pd.testing.assert_frame_equal(base[1][chave], teto[1][chave], check_exact=True)
    pd.testing.assert_frame_equal(det, det0, check_exact=True)
    pd.testing.assert_frame_equal(pas, pas0, check_exact=True)


# --- T2 -------------------------------------------------------------------------

def test_t2_bola_e_oraculos_intactos_e_subconjunto(jogo, cfg):
    frames, tracking, periods = jogo(1)
    f0, p0, t0 = frames.copy(), periods.copy(), tracking.copy()
    for variante, nivel in NIVEIS:
        saida = broadcast.degradar(tracking, frames, cfg, variante, nivel, 0)
        assert saida.index.isin(tracking.index).all()
        pd.testing.assert_frame_equal(saida, tracking.loc[saida.index], check_exact=True)
        if nivel > 1:
            assert len(saida) < len(tracking)
    pd.testing.assert_frame_equal(frames, f0, check_exact=True)
    pd.testing.assert_frame_equal(periods, p0, check_exact=True)
    pd.testing.assert_frame_equal(tracking, t0, check_exact=True)


@pytest.mark.parametrize("variante", ["A", "B"])
def test_t2_carregar_base_degradado_mantem_frames_periods_eventos(variante):
    teto, _, _ = _pipeline(None)
    base, _, _ = _pipeline((variante, 8, 0))
    for chave in ("frames", "periods", "eventos"):
        pd.testing.assert_frame_equal(base[1][chave], teto[1][chave], check_exact=True)
    assert len(base[1]["tracking"]) < len(teto[1]["tracking"])


# --- T3 -------------------------------------------------------------------------

def test_t3_mascaras_aninhadas_e_taxas_monotonas(jogo, cfg):
    frames, tracking, _ = jogo(1)
    for variante in ("A", "B"):
        anterior = None
        for nivel in range(1, 9):
            m = broadcast.mascara(tracking, frames, cfg, variante, nivel, 0)
            if anterior is not None:
                assert (m <= anterior).all(), (variante, nivel)
            anterior = m
        taxas = [lv["taxa"] for lv in cfg["simulador"]["calibrado"]["niveis"][variante]]
        assert all(a > b for a, b in zip(taxas, taxas[1:]))
    niveis_b = cfg["simulador"]["calibrado"]["niveis"]["B"]
    assert all(a["theta_graus"] >= b["theta_graus"] and a["c"] <= b["c"]
               for a, b in zip(niveis_b, niveis_b[1:]))


# --- T4 -------------------------------------------------------------------------

def _com(cfg, caminho, valor):
    novo = copy.deepcopy(cfg)
    alvo = novo
    for k in caminho[:-1]:
        alvo = alvo[k]
    alvo[caminho[-1]] = valor
    return novo


CAL = ("simulador", "calibrado")
VARREDURA = [
    ("B", CAL + ("niveis", "B", 7, "theta_graus"), 20.0),
    ("A", CAL + ("niveis", "A", 7, "L_m"), 25.0),
    ("B", CAL + ("niveis", "B", 7, "c"), 0.5),
    ("B", ("simulador", "d_cam_m"), 15.0),
    ("B", CAL + ("a_vivo",), 0.02),
    ("B", CAL + ("a_morto",), 0.3),
    ("B", CAL + ("b",), 0.2),
    ("B", ("simulador", "sg_janela"), 61),
    ("B", ("simulador", "sg_grau"), 5),      # 2 e 3 dao o mesmo filtro no centro
    ("A", ("simulador", "sg_janela"), 61),
]


@pytest.mark.parametrize("variante,caminho,valor", VARREDURA,
                         ids=["{}-{}".format(v, c[-1]) for v, c, _ in VARREDURA])
def test_t4_parametro_varrido_muda_a_mascara(jogo, cfg, variante, caminho, valor):
    frames, tracking, _ = jogo(1)
    antes = broadcast.mascara(tracking, frames, cfg, variante, 8, 0)
    depois = broadcast.mascara(tracking, frames, _com(cfg, caminho, valor), variante, 8, 0)
    assert not np.array_equal(antes, depois)


def test_t4_semente_so_importa_com_cortes(jogo, cfg):
    frames, tracking, _ = jogo(1)
    m = {r: broadcast.mascara(tracking, frames, cfg, "B", 8, r) for r in (0, 1)}
    assert not np.array_equal(m[0], m[1])
    m = {r: broadcast.mascara(tracking, frames, cfg, "B", 5, r) for r in (0, 1)}
    np.testing.assert_array_equal(m[0], m[1])


# --- T8 -------------------------------------------------------------------------

def _base(jogo, eventos, cfg) -> dict:
    base = {}
    for g in cfg["dados"]["jogos"]:
        frames, tracking, periods = jogo(g)
        base[g] = {"frames": frames, "tracking": tracking, "periods": periods,
                   "eventos": eventos(g)[1]}
    return base


@pytest.fixture(scope="module")
def calibracao(jogo, eventos, cfg):
    """`broadcast.calibrar` nos 3 jogos, uma vez por modulo (~1 min)."""
    return broadcast.calibrar(_base(jogo, eventos, cfg), cfg)


def test_t8_config_reproduz_a_calibracao(calibracao, cfg):
    cal = calibracao
    s = cfg["simulador"]
    salvo = s["calibrado"]
    # rel 1e-4 / abs 1e-9 (revisao I1): a dispersao do otimizador entre pontos
    # iniciais e ~2e-5 relativo; 1e-6 so media ruido.
    perto = {"rel": s["tol_confere_rel"], "abs": s["tol_confere_abs"]}
    for k in ("a_vivo", "a_morto", "b", "theta_estrela_graus"):
        assert cal[k] == pytest.approx(salvo[k], **perto), k
    tol = s["bissecao_tol_taxa"]
    for variante, chave in (("B", "theta_graus"), ("A", "L_m")):
        for novo, velho in zip(cal["niveis"][variante], salvo["niveis"][variante], strict=True):
            assert abs(novo["taxa"] - velho["taxa"]) < tol
            assert novo[chave] == pytest.approx(velho[chave], **perto)
    # criterio de parada do plano §4.5: GK e o papel menos visivel em B8
    dist = cal["diag"]["dist_visivel"]
    assert min(dist, key=dist.get) == "GK"


# --- T11 ------------------------------------------------------------------------

@pytest.mark.parametrize("variante", ["A", "B"])
def test_t11_pipeline_roda_sob_degradacao(variante):
    base, det, pas = _pipeline((variante, 8, 0))
    schema.validar(base[1]["tracking"], schema.TRACKING, "tracking degradado")
    schema.validar(base[1]["perdas"], possession.PERDAS, "perdas")
    schema.validar(base[1]["ganhos"], possession.GANHOS, "ganhos")
    passes_mod.validar(pas)
    assert len(base[1]["perdas"]) > 0 and len(det) > 0


# --- emenda §10: restricao de trocas por minuto ---------------------------------

def test_cortes_calibrados_respeitam_a_restricao(calibracao, jogo, eventos, cfg):
    s = cfg["simulador"]
    tol = s["tol_restricao"]
    frames, _ = broadcast.cortes_juntos(_base(jogo, eventos, cfg), cfg["dados"]["jogos"])
    # recalculado de forma independente, com os parametros que estao no config
    trocas = broadcast.trocas_por_minuto(frames, s["calibrado"], 1.0, cfg["tracking"]["fps"])
    assert trocas <= s["cortes_por_minuto_max"] + tol
    assert calibracao["diag"]["cortes_por_min"] <= s["cortes_por_minuto_max"] + tol
    for k in ("a_vivo", "a_morto"):
        assert s["calibrado"][k] <= 1.0 - s["calibrado"]["b"] + tol


def test_teto_de_trocas_por_minuto_e_lido(jogo, eventos, cfg):
    """Mudar `cortes_por_minuto_max` muda a calibracao: com teto abaixo do
    otimo atual (~2,87/min) a restricao fica ativa e a solucao a respeita."""
    s = cfg["simulador"]
    teto = 2.0
    assert teto < s["cortes_por_minuto_max"]
    outro = copy.deepcopy(cfg)
    outro["simulador"]["cortes_por_minuto_max"] = teto
    frames, lateral = broadcast.cortes_juntos(_base(jogo, eventos, cfg), cfg["dados"]["jogos"])
    novo = broadcast.calibrar_cortes(frames, lateral, outro)
    assert novo["trocas_por_min"] <= teto + s["tol_restricao"]
    assert novo["b"] != pytest.approx(s["calibrado"]["b"], rel=1e-3)
    assert novo["a_morto"] != pytest.approx(s["calibrado"]["a_morto"], rel=1e-3)


# --- revisao I3: calibracao (codigo vetorial proprio) x degradar --------------

def _taxa_amostrada(jogo, cfg, variante, nivel, sementes):
    """Media de `mascara` sobre as linhas dos 3 jogos e as `sementes`."""
    vis = n = 0
    for g in cfg["dados"]["jogos"]:
        frames, tracking, _ = jogo(g)
        for r in sementes:
            m = broadcast.mascara(tracking, frames, cfg, variante, nivel, r)
            vis, n = vis + int(m.sum()), n + m.size
    return vis / n


@pytest.mark.parametrize("variante,nivel", [(v, k) for v, k in NIVEIS
                                            if not (v == "B" and k >= 6)])
def test_degradar_reproduz_a_taxa_do_config_sem_cortes(jogo, cfg, variante, nivel):
    """Com c = 0 a mascara e deterministica: a taxa de `degradar` nos 3 jogos e
    a `taxa` que a calibracao escreveu, ate o arredondamento (1e-9)."""
    taxa = cfg["simulador"]["calibrado"]["niveis"][variante][nivel - 1]["taxa"]
    assert abs(_taxa_amostrada(jogo, cfg, variante, nivel, [0]) - taxa) < 1e-9


@pytest.mark.parametrize("nivel", [6, 7, 8])
def test_degradar_com_cortes_fica_perto_da_taxa_esperada(jogo, cfg, nivel):
    """Com c > 0, media das 5 sementes a <= 0,02 da taxa esperada (revisao I3)."""
    taxa = cfg["simulador"]["calibrado"]["niveis"]["B"][nivel - 1]["taxa"]
    sementes = range(cfg["simulador"]["n_sementes"])
    assert abs(_taxa_amostrada(jogo, cfg, "B", nivel, sementes) - taxa) <= 0.02

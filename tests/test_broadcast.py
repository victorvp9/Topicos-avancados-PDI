"""Testes sinteticos do simulador de broadcast (plano 06 §7: T3, T5, T6, T7,
T9, T10, T12, mais bordas com NaN)."""

import ast
import copy

import numpy as np
import pandas as pd
import pytest

from src import broadcast
from src.config import RAIZ_REPO
from src.io import schema


def _frames(vivo, game=1, period=None, bola=None):
    """FRAMES sintetico: `vivo` (n,) bool; bola em `bola` (n, 2) ou (0,0) nos vivos."""
    vivo = np.asarray(vivo, dtype=bool)
    n = vivo.size
    bola = np.zeros((n, 2)) if bola is None else np.asarray(bola, dtype=float).copy()
    bola[~vivo] = np.nan
    quadro = np.arange(1, n + 1, dtype="int64")
    return schema.validar(pd.DataFrame({
        "game": np.full(n, game, dtype="int64"),
        "period": np.ones(n, dtype="int64") if period is None else np.asarray(period, dtype="int64"),
        "frame": quadro,
        "t": quadro / 25.0,
        "ball_x": bola[:, 0], "ball_y": bola[:, 1],
        "ball_live": vivo,
    }), schema.FRAMES, "frames")


def _alternado(n, bloco_vivo, bloco_morto):
    padrao = np.r_[np.ones(bloco_vivo, bool), np.zeros(bloco_morto, bool)]
    return np.resize(padrao, n)


PARAMS = {"a_vivo": 0.05, "a_morto": 0.3, "b": 0.3}


# --- T6: geometria ----------------------------------------------------------

def test_t6_cunha_borda_theta_meio(cfg):
    d_cam, theta, eps = 30.0, 40.0, 1e-6
    cam_y = -(cfg["campo"]["largura_m"] / 2 + d_cam)
    alvo = np.array([10.0, 5.0])
    base_ang = np.arctan2(alvo[1] - cam_y, alvo[0])
    r = 50.0
    for delta, esperado in ((theta / 2 - eps, True), (theta / 2 + eps, False)):
        for sinal in (+1, -1):
            a = base_ang + sinal * np.radians(delta)
            x, y = r * np.cos(a), cam_y + r * np.sin(a)
            assert broadcast.na_cunha(x, y, *alvo, theta, d_cam, cfg) == esperado
    # theta infinito: tudo dentro, pelo mesmo caminho
    assert broadcast.na_cunha(-52.5, 34.0, 52.5, -34.0, np.inf, d_cam, cfg)


def test_t6_janela_borda_inclusiva():
    assert broadcast.na_janela(15.0, 0.0, 0.0, 0.0, 30.0)
    assert broadcast.na_janela(-15.0, 15.0, 0.0, 0.0, 30.0)
    assert not broadcast.na_janela(15.0 + 1e-9, 0.0, 0.0, 0.0, 30.0)
    assert not broadcast.na_janela(0.0, -15.0 - 1e-9, 0.0, 0.0, 30.0)
    assert broadcast.na_janela(1e6, 1e6, 0.0, 0.0, np.inf)


def test_nan_na_posicao_nunca_e_visivel(cfg):
    assert not broadcast.na_cunha(np.nan, 0.0, 0.0, 0.0, 40.0, 30.0, cfg)
    assert not broadcast.na_janela(np.nan, 0.0, 0.0, 0.0, 30.0)
    assert not broadcast.na_janela(np.nan, 0.0, 0.0, 0.0, np.inf)


def test_t6_alvo_interpolacao_linear_exata(cfg):
    n = 400
    k = np.arange(n)
    bola = np.c_[0.1 * k - 20.0, 0.05 * k - 10.0]
    vivo = np.ones(n, bool)
    vivo[150:230] = False                     # corrida morta no meio
    alvo = broadcast.alvo_camera(_frames(vivo, bola=bola), cfg)
    assert list(alvo.columns) == ["game", "period", "frame", "cx", "cy"]
    assert not alvo[["cx", "cy"]].isna().any().any()
    np.testing.assert_allclose(alvo["cx"], bola[:, 0], atol=1e-9)
    np.testing.assert_allclose(alvo["cy"], bola[:, 1], atol=1e-9)


def test_t6_alvo_bordas_do_periodo_mantidas(cfg):
    n = 500
    bola = np.zeros((n, 2))
    bola[:250] = (10.0, 5.0)
    bola[250:] = (-20.0, 3.0)
    vivo = np.ones(n, bool)
    vivo[:100] = False                        # morta no inicio do periodo
    vivo[400:] = False                        # morta no fim
    alvo = broadcast.alvo_camera(_frames(vivo, bola=bola), cfg)
    assert not alvo[["cx", "cy"]].isna().any().any()
    np.testing.assert_allclose(alvo[["cx", "cy"]].to_numpy()[:200], [[10.0, 5.0]] * 200, atol=1e-9)
    np.testing.assert_allclose(alvo[["cx", "cy"]].to_numpy()[300:], [[-20.0, 3.0]] * 200, atol=1e-9)


def test_alvo_por_periodo_e_periodo_sem_bola_viva_estoura(cfg):
    n = 200
    per = np.r_[np.ones(100), np.full(100, 2)]
    bola = np.r_[np.tile([5.0, 0.0], (100, 1)), np.tile([-5.0, 0.0], (100, 1))]
    vivo = np.ones(n, bool)
    vivo[95:105] = False
    alvo = broadcast.alvo_camera(_frames(vivo, period=per, bola=bola), cfg)
    # a interpolacao nao atravessa o intervalo: cada periodo fica no seu ponto
    np.testing.assert_allclose(alvo["cx"][:100], 5.0, atol=1e-9)
    np.testing.assert_allclose(alvo["cx"][100:], -5.0, atol=1e-9)
    vivo[100:] = False
    with pytest.raises(ValueError):
        broadcast.alvo_camera(_frames(vivo, period=per, bola=bola), cfg)


def test_sg_janela_e_lido(cfg):
    n = 300
    rng = np.random.default_rng(0)
    bola = rng.normal(size=(n, 2))
    fr = _frames(np.ones(n, bool), bola=bola)
    outro = copy.deepcopy(cfg)
    outro["simulador"]["sg_janela"] = 11
    assert not np.allclose(broadcast.alvo_camera(fr, cfg)["cx"],
                           broadcast.alvo_camera(fr, outro)["cx"])


# --- T7: recursao exata = Monte Carlo ------------------------------------------

def test_t7_recursao_exata_contra_monte_carlo():
    vivo = _alternado(10_000, 300, 120)
    fr = _frames(vivo)
    p = broadcast.p_off(fr, PARAMS, 1.0)
    amostras = np.array([broadcast.amostrar_off(fr, PARAMS, 1.0, [7, 1, r])
                         for r in range(1000)])
    delta = amostras.mean(axis=0) - p
    # LACUNA (criterio do plano "|delta| < 0,01 por quadro, em media"): com 1000
    # amostras e p ~ 0,5 o ruido de MC sozinho da E|delta| ~ 0,013, logo a
    # leitura "media de |delta|" e inviavel. Lido como (1) |media de delta| <
    # 0,01 e (2) |delta| normalizado pelo desvio de MC com media < 1 (ruido puro
    # da sqrt(2/pi) = 0,80; um vies de 1 desvio passaria de 1).
    assert abs(delta.mean()) < 0.01
    sd = np.sqrt(p * (1 - p) / 1000)
    assert np.mean(np.abs(delta[sd > 0]) / sd[sd > 0]) < 1.0
    # (3) o mesmo so nos quadros de transicao vivo <-> morto, onde um erro de
    # um quadro na recursao (q de s_{t-1} em vez de s_t) se concentra e se
    # diluiria na media global (verificado por mutacao).
    troca = np.flatnonzero(vivo[1:] != vivo[:-1]) + 1
    assert np.mean(np.abs(delta[troca]) / sd[troca]) < 1.0


def test_t7_c_zero_da_p_off_nulo():
    fr = _frames(_alternado(5000, 200, 100))
    assert np.all(broadcast.p_off(fr, PARAMS, 0.0) == 0.0)
    assert not broadcast.amostrar_off(fr, PARAMS, 0.0, [1, 1, 0]).any()


def test_trocas_por_minuto_contra_monte_carlo():
    """`trocas_por_minuto` = media MC das transicoes on<->off de `amostrar_off`,
    com o `on` inicial de cada periodo contando (revisao I2). Mata o mutante
    "trocas em dobro" (e qualquer erro de fator), que antes so morria por ruido."""
    per = np.r_[np.ones(4000), np.full(4000, 2)]
    fr = _frames(_alternado(8000, 300, 120), period=per)
    params = {"a_vivo": 0.01, "a_morto": 0.04, "b": 0.05}
    esperado = broadcast.trocas_por_minuto(fr, params, 1.0, 25.0)
    inicio = np.r_[True, per[1:] != per[:-1]]
    n_amostras = 1000
    contagens = np.empty(n_amostras)
    for r in range(n_amostras):
        off = broadcast.amostrar_off(fr, params, 1.0, [9, 1, r])
        anterior = np.r_[False, off[:-1]]
        anterior[inicio] = False                  # estado `on` antes de cada periodo
        contagens[r] = (off != anterior).sum()
    minutos = len(fr) / 25.0 / 60.0
    mc = contagens.mean() / minutos
    erro_padrao = contagens.std(ddof=1) / np.sqrt(n_amostras) / minutos
    # 4 erros-padrao: falso alarme ~6e-5 se a formula estiver certa; o mutante
    # "em dobro" fica a ~420 erros-padrao (medido por mutacao).
    assert abs(esperado - mc) < 4 * erro_padrao
    assert esperado > 10 * erro_padrao             # o teste tem poder: nao e ~0


def test_p_off_reinicia_em_cada_periodo():
    per = np.r_[np.ones(500), np.full(500, 2)]
    fr = _frames(np.zeros(1000, bool), period=per)
    p = broadcast.p_off(fr, PARAMS, 1.0)
    assert p[500] == pytest.approx(PARAMS["a_morto"])     # 1o quadro: p_{-1} = 0
    assert p[0] == p[500]


def test_acoplamento_violado_estoura():
    fr = _frames(np.zeros(10, bool))
    with pytest.raises(ValueError, match="acoplamento"):
        broadcast.amostrar_off(fr, {"a_vivo": 0.1, "a_morto": 0.8, "b": 0.3}, 1.0, [1, 1, 0])


# --- T3 sintetico: monotonia ------------------------------------------------------

def test_t3_monotonia_sintetica(cfg):
    rng = np.random.default_rng(3)
    x, y = rng.uniform(-52.5, 52.5, 5000), rng.uniform(-34, 34, 5000)
    cx, cy = rng.uniform(-52.5, 52.5, 5000), rng.uniform(-34, 34, 5000)
    anterior = None
    for theta in (5.0, 20.0, 40.0, 90.0, 180.0, np.inf):
        m = broadcast.na_cunha(x, y, cx, cy, theta, 30.0, cfg)
        if anterior is not None:
            assert (anterior <= m).all()
        anterior = m
    anterior = None
    for L in (10.0, 30.0, 60.0, 120.0, np.inf):
        m = broadcast.na_janela(x, y, cx, cy, L)
        if anterior is not None:
            assert (anterior <= m).all()
        anterior = m
    fr = _frames(_alternado(20_000, 400, 150))
    cs = (0.0, 1 / 3, 2 / 3, 1.0)
    taxas = [1 - broadcast.p_off(fr, PARAMS, c).mean() for c in cs]
    assert all(a >= b for a, b in zip(taxas, taxas[1:]))
    offs = [broadcast.amostrar_off(fr, PARAMS, c, [5, 1, 0]) for c in cs]
    for menor, maior in zip(offs, offs[1:]):
        assert (menor <= maior).all()           # aninhado: off cresce com c
    assert offs[-1].sum() > offs[1].sum() > 0


# --- T5: sementes ------------------------------------------------------------------

def _cfg_sintetico(cfg):
    novo = copy.deepcopy(cfg)
    novo["simulador"]["calibrado"] = {
        **PARAMS, "theta_estrela_graus": 30.0,
        "niveis": {"B": [{"theta_graus": 30.0, "c": c, "taxa": 0.0} for c in (0.0, 0.5, 1.0)],
                   "A": [{"L_m": 40.0, "taxa": 0.0}]},
    }
    return novo


def _jogo_sintetico(n=3000, n_jog=6):
    rng = np.random.default_rng(11)
    vivo = _alternado(n, 250, 100)
    fr = _frames(vivo, game=2, bola=rng.uniform(-30, 30, (n, 2)))
    linhas = [(2, 1, f + 1, "p{}".format(j), "home" if j % 2 else "away", j == 0,
               float(rng.uniform(-52, 52)), float(rng.uniform(-34, 34)), True)
              for f in range(n) for j in range(n_jog)]
    tr = pd.DataFrame(linhas, columns=list(schema.TRACKING)).astype(schema.TRACKING)
    return fr, tr


def test_t5_mesma_semente_mesma_saida_e_rng_global_irrelevante(cfg):
    c = _cfg_sintetico(cfg)
    fr, tr = _jogo_sintetico()
    a = broadcast.degradar(tr, fr, c, "B", 3, 0)
    np.random.seed(123)
    np.random.random(1000)
    b = broadcast.degradar(tr, fr, c, "B", 3, 0)
    pd.testing.assert_frame_equal(a, b, check_exact=True)
    assert not broadcast.degradar(tr, fr, c, "B", 3, 1).index.equals(a.index)


def test_t5_uniformes_iguais_entre_niveis_e_variantes(cfg, monkeypatch):
    c = _cfg_sintetico(cfg)
    fr, tr = _jogo_sintetico()
    chamadas = []
    original = broadcast.amostrar_off

    def espiao(frames, params, cc, semente):
        chamadas.append(list(semente))
        return original(frames, params, cc, semente)

    monkeypatch.setattr(broadcast, "amostrar_off", espiao)
    for nivel in (1, 2, 3):
        broadcast.mascara(tr, fr, c, "B", nivel, 4)
    broadcast.mascara(tr, fr, c, "A", 1, 4)          # A nao sorteia nada
    assert chamadas == [[c["simulador"]["semente_base"], 2, 4]] * 3
    # e o sorteio usa exatamente os uniformes de SeedSequence([base, game, rep])
    u = np.random.default_rng(np.random.SeedSequence(chamadas[0])).random(len(fr))
    np.testing.assert_array_equal(u, broadcast.uniformes(len(fr), chamadas[0]))


def test_degradar_exige_semente(cfg):
    fr, tr = _jogo_sintetico(n=100)
    with pytest.raises(TypeError):
        broadcast.degradar(tr, fr, _cfg_sintetico(cfg), "B", 1)


# --- T9: papeis ----------------------------------------------------------------------

def _tracking_papeis(attack_dir):
    linhas = []
    for f in range(1, 4):
        linhas.append((1, 1, f, "gk", "home", True, -50.0, 0.0, True))
        for j in range(10):
            linhas.append((1, 1, f, "j{:02d}".format(j), "home", False, -40.0 + 8.0 * j, 0.0, True))
    tr = pd.DataFrame(linhas, columns=list(schema.TRACKING)).astype(schema.TRACKING)
    per = pd.DataFrame({"game": [1], "period": [1], "team": ["home"], "attack_dir": [attack_dir],
                        "gk_mean_x": [0.0]}).astype(schema.PERIODS)
    return tr, per


def test_t9_papeis_5_3_2_e_inversao(cfg):
    tr, per = _tracking_papeis(+1)
    p = broadcast.papeis(tr, per, cfg).set_index("player_id")["papel"]
    assert p["gk"] == "GK"
    assert list(p[["j{:02d}".format(j) for j in range(10)]]) == ["DEF"] * 5 + ["MID"] * 3 + ["OFF"] * 2
    tr, per = _tracking_papeis(-1)
    p = broadcast.papeis(tr, per, cfg).set_index("player_id")["papel"]
    assert list(p[["j{:02d}".format(j) for j in range(10)]]) == ["OFF"] * 2 + ["MID"] * 3 + ["DEF"] * 5


def test_t9_proporcoes_sao_lidas(cfg):
    tr, per = _tracking_papeis(+1)
    outro = copy.deepcopy(cfg)
    outro["simulador"]["proporcoes_papel"] = {"DEF": 10, "MID": 10, "OFF": 10}
    p = broadcast.papeis(tr, per, outro)["papel"].value_counts()
    assert p["DEF"] == 3 and p["OFF"] == 3


# --- T10: distancia visivel ---------------------------------------------------------------

def _corrida(n=1000, v=0.2):
    k = np.arange(n)
    return pd.DataFrame({
        "game": 1, "period": 1, "frame": k + 1, "player_id": "a", "team": "home",
        "is_gk": False, "x": -40.0 + v * k, "y": 0.5 * v * k - 10.0, "visible": True,
    }).astype(schema.TRACKING)


def test_t10_filtro_preserva_distancia_em_velocidade_constante(cfg):
    tr = _corrida()
    passo, curtos, n_seg = broadcast.passos(tr, cfg)
    verdade = np.hypot(tr["x"].iloc[-1] - tr["x"].iloc[0], tr["y"].iloc[-1] - tr["y"].iloc[0])
    assert abs(passo.sum() / verdade - 1) < 0.01
    assert passo[0] == 0.0 and curtos == 0 and n_seg == 1
    vis = np.zeros(len(tr))
    vis[: len(tr) // 2 + 1] = 1.0           # metade dos PASSOS chega num quadro visivel
    assert (passo * vis).sum() / passo.sum() == pytest.approx(0.5, abs=1.0 / (len(tr) - 1))


def test_t10_segmentos_curtos_e_lacunas(cfg):
    tr = _corrida(n=80)
    tr = tr[(tr["frame"] <= 30) | (tr["frame"] >= 51)]        # lacuna: 2 segmentos
    curto = _corrida(n=8).assign(player_id="b")
    tr = pd.concat([tr, curto], ignore_index=True)
    passo, curtos, n_seg = broadcast.passos(tr, cfg)
    assert n_seg == 3 and curtos == 1
    assert not np.isnan(passo).any()
    assert passo[tr.index[(tr["player_id"] == "a") & (tr["frame"] == 51)][0]] == 0.0
    for chave, valor in (("butter_corte_hz", 0.2), ("butter_ordem", 5)):
        outro = copy.deepcopy(cfg)
        outro["simulador"][chave] = valor
        assert not np.allclose(passo, broadcast.passos(tr, outro)[0]), chave


# --- T12: proibicao da §6 ----------------------------------------------------------------------

def test_t12_broadcast_nao_importa_evaluate():
    arvore = ast.parse((RAIZ_REPO / "src" / "broadcast.py").read_text(encoding="utf-8"))
    nomes = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes.update(a.name for a in no.names)
        elif isinstance(no, ast.ImportFrom):
            nomes.add(no.module or "")
            nomes.update("{}.{}".format(no.module, a.name) for a in no.names)
    assert not any("evaluate" in n for n in nomes), nomes

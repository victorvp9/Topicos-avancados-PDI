"""Testes sinteticos da reconstrucao (plano 07 §6: T1, T2, T3, T4, T5, T6, T7,
T8, T9, T11, mais bordas com NaN e a equivalencia do filtro)."""

import copy

import numpy as np
import pandas as pd
import pytest

from src import broadcast, reconstruct, run
from src.io import schema

DT = 1.0 / 25.0


def _tracking(jogadores, inicio_indice=0):
    """TRACKING sintetico em ordem de quadro (como o loader). `jogadores`:
    lista de `(game, player_id, team, is_gk, period (n,), frame (n,), x (n,),
    y (n,))`. Indice comeca em `inicio_indice` (nao-RangeIndex de proposito
    quando != 0)."""
    partes = []
    for game, pid, team, gk, per, fr, x, y in jogadores:
        n = len(fr)
        partes.append(pd.DataFrame({
            "game": np.full(n, game, "int64"), "period": np.asarray(per, "int64"),
            "frame": np.asarray(fr, "int64"), "player_id": pid, "team": team,
            "is_gk": np.full(n, gk), "x": np.asarray(x, float), "y": np.asarray(y, float),
            "visible": np.ones(n, bool)}))
    df = pd.concat(partes, ignore_index=True).sort_values(["game", "frame", "player_id"], kind="stable")
    df.index = np.arange(len(df)) * 3 + inicio_indice if inicio_indice else pd.RangeIndex(len(df))
    return schema.validar(df.astype(schema.TRACKING), schema.TRACKING, "tracking sintetico")


def _um(x, y=None, per=None, pid="p1", game=1, gk=False, f0=1):
    n = len(x)
    y = np.zeros(n) if y is None else y
    per = np.ones(n, "int64") if per is None else per
    return (game, pid, "home", gk, per, np.arange(f0, f0 + n), x, y)


def _presenca(teto):
    return teto[reconstruct.CHAVES]


# --- T1 / T2 ------------------------------------------------------------------

def _rmse_buraco(x, inicio, n_buraco):
    teto = _tracking([_um(x)])
    deg = teto.drop(teto.index[inicio:inicio + n_buraco])
    rec, cont = reconstruct.reconstruir(deg, _presenca(teto))
    assert cont["n_imputadas"] == n_buraco
    m = ~rec["visible"].to_numpy()
    return np.sqrt(np.mean((rec["x"].to_numpy()[m] - teto["x"].to_numpy()[m]) ** 2))


def test_t1_aceleracao_constante_erro_analitico_e_crescente():
    a = 3.0
    n_total = 400
    t = np.arange(1, n_total + 1) * DT
    x = 0.5 * a * t ** 2
    rmses = []
    for n in (1, 5, 25, 125):
        inicio = (n_total - n) // 2
        r = _rmse_buraco(x, inicio, n)
        k = np.arange(1, n + 1)
        analitico = np.sqrt(np.mean((a * k * (n + 1 - k) / 2.0 * DT ** 2) ** 2))
        assert abs(r - analitico) <= 1e-9
        rmses.append(r)
    assert all(np.diff(rmses) > 0)


def test_t2_trajetoria_linear_reconstruida_exata():
    f = np.arange(1, 301)
    teto = _tracking([_um(2.0 + 0.3 * f * DT * 25, -1.0 - 0.1 * f)])
    deg = teto.drop(teto.index[100:180])
    rec, _ = reconstruct.reconstruir(deg, _presenca(teto))
    assert np.abs(rec["x"].to_numpy() - teto["x"].to_numpy()).max() <= 1e-9
    assert np.abs(rec["y"].to_numpy() - teto["y"].to_numpy()).max() <= 1e-9


# --- T3 -------------------------------------------------------------------------

@pytest.mark.parametrize("inicio_indice", [0, 7])
def test_t3_buraco_zero_reproduz_o_teto_bit_a_bit(inicio_indice):
    rng = np.random.default_rng(0)
    teto = _tracking([_um(rng.normal(size=50), rng.normal(size=50), pid="a"),
                      _um(rng.normal(size=30), rng.normal(size=30), pid="b", f0=11, gk=True)],
                     inicio_indice)
    rec, cont = reconstruct.reconstruir(teto, _presenca(teto))
    pd.testing.assert_frame_equal(rec, teto, check_exact=True, check_index_type=True)
    assert cont == {"n_imputadas": 0, "n_sem_ancora": 0, "n_jogadores_periodo_sem_ancora": 0}


# --- T4 -------------------------------------------------------------------------

def test_t4_visible_sobrevive():
    rng = np.random.default_rng(1)
    teto = _tracking([_um(rng.normal(size=60), rng.normal(size=60), pid="a"),
                      _um(rng.normal(size=60), rng.normal(size=60), pid="b")], 5)
    deg = teto.iloc[::3].copy()
    deg.iloc[::2, deg.columns.get_loc("visible")] = False     # entrada ja com imputadas
    rec, cont = reconstruct.reconstruir(deg, _presenca(teto))
    veio = rec.loc[deg.index]
    pd.testing.assert_frame_equal(veio, deg, check_exact=True)
    novas = rec.drop(deg.index)
    assert len(novas) == cont["n_imputadas"] > 0
    assert not novas["visible"].any()
    assert rec["visible"].sum() == deg["visible"].sum()      # nenhum True virou False
    assert list(rec.index) == [i for i in teto.index if i in rec.index]  # ordem do teto


# --- T5 -------------------------------------------------------------------------

def test_t5_sem_vazamento_de_x_y_do_teto():
    rng = np.random.default_rng(2)
    teto = _tracking([_um(rng.normal(size=80), rng.normal(size=80))])
    deg = teto.iloc[[0, 10, 40, 79]]
    pres = _presenca(teto)
    assert "x" not in pres.columns and "y" not in pres.columns
    rec_limpo, c1 = reconstruct.reconstruir(deg, pres)
    lixo = teto.assign(x=1e6, y=-1e6, visible=False)
    rec_lixo, c2 = reconstruct.reconstruir(deg, lixo)
    pd.testing.assert_frame_equal(rec_limpo, rec_lixo, check_exact=True)
    assert c1 == c2


# --- T6 -------------------------------------------------------------------------

def test_t6_bordas_constantes_e_nao_atravessa_periodo_nem_jogo():
    n = 40
    per = np.r_[np.ones(n, "int64"), np.full(n, 2, "int64")]
    x = np.r_[np.linspace(-40, -30, n), np.linspace(30, 40, n)]
    teto = _tracking([_um(x, per=per, game=1), _um(-x, per=per, game=2)])
    # no periodo 1: ancoras so nos quadros 10..20; no 2: so nos quadros 50..60
    f = teto["frame"].to_numpy()
    deg = teto[((f >= 10) & (f <= 20)) | ((f >= 50) & (f <= 60))]
    rec, cont = reconstruct.reconstruir(deg, _presenca(teto))
    info = reconstruct.buracos(_presenca(teto), deg)
    for game, sinal in ((1, 1.0), (2, -1.0)):
        r = rec[rec["game"] == game].set_index("frame")["x"]
        t = teto[teto["game"] == game].set_index("frame")["x"]
        assert (r.loc[1:9] == t.loc[10]).all() and (r.loc[21:40] == t.loc[20]).all()
        assert (r.loc[41:49] == t.loc[50]).all() and (r.loc[61:80] == t.loc[60]).all()
        assert (sinal * r.loc[1:40] < 0).all() and (sinal * r.loc[41:80] > 0).all()
    assert cont["n_imputadas"] == int(info["borda"].sum()) == 2 * (2 * n - 22)


def test_t6_nao_cruza_jogo_no_mesmo_periodo():
    """Mesmo player_id e mesmo periodo (1) em dois jogos, posicoes distantes: a
    quebra por jogo e a unica que separa os grupos."""
    n = 40
    teto = _tracking([_um(np.full(n, -40.0), game=1), _um(np.full(n, 40.0), game=2)])
    g, f = teto["game"].to_numpy(), teto["frame"].to_numpy()
    deg = teto[((g == 1) & (f <= 10)) | ((g == 2) & (f >= 31))]
    rec, cont = reconstruct.reconstruir(deg, _presenca(teto))
    info = reconstruct.buracos(_presenca(teto), deg)
    pd.testing.assert_series_equal(rec["x"], teto["x"], check_exact=True)
    assert cont["n_imputadas"] == 60 and cont["n_jogadores_periodo_sem_ancora"] == 0
    assert int(info["borda"].sum()) == 60


def test_buracos_comprimento_e_borda():
    teto = _tracking([_um(np.arange(20.0))])
    manter = np.zeros(20, bool)
    manter[[3, 4, 10, 15]] = True
    deg = teto[manter]
    info = reconstruct.buracos(_presenca(teto), deg)
    assert info["ancora"].tolist() == manter.tolist()
    esperado = [3, 3, 3, 0, 0, 5, 5, 5, 5, 5, 0, 4, 4, 4, 4, 0, 4, 4, 4, 4]
    assert info["buraco_quadros"].tolist() == esperado
    assert info["borda"].to_numpy().nonzero()[0].tolist() == [0, 1, 2, 16, 17, 18, 19]
    assert not info["sem_ancora"].any()


# --- T7 / T8 --------------------------------------------------------------------

def test_t7_sem_ancora_fica_ausente_e_contado():
    per = np.r_[np.ones(10, "int64"), np.full(10, 2, "int64")]
    teto = _tracking([_um(np.arange(20.0), per=per, pid="a"), _um(np.arange(20.0), per=per, pid="b")])
    # "b" nao tem nenhuma linha no periodo 2; "a" nenhuma no periodo 1
    p = teto["period"].to_numpy()
    pid = teto["player_id"].to_numpy()
    deg = teto[((pid == "a") & (p == 2)) | ((pid == "b") & (p == 1))].iloc[::2]
    rec, cont = reconstruct.reconstruir(deg, _presenca(teto))
    assert cont["n_sem_ancora"] == 20 and cont["n_jogadores_periodo_sem_ancora"] == 2
    assert len(rec) == 20 and cont["n_imputadas"] == 20 - len(deg)
    assert not rec[["x", "y"]].isna().any().any()
    assert set(zip(rec["player_id"], rec["period"])) == {("a", 2), ("b", 1)}


@pytest.mark.parametrize("coluna", ["x", "y"])
def test_t8_nan_na_entrada_estoura(coluna):
    teto = _tracking([_um(np.arange(10.0))])
    deg = teto.copy()
    deg.iloc[4, deg.columns.get_loc(coluna)] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        reconstruct.reconstruir(deg, _presenca(teto))


def test_linha_de_degradado_fora_da_presenca_estoura():
    teto = _tracking([_um(np.arange(10.0))])
    with pytest.raises(ValueError, match="fora de presenca"):
        reconstruct.reconstruir(teto, _presenca(teto.iloc[:5]))


def test_presenca_duplicada_estoura():
    teto = _tracking([_um(np.arange(10.0))])
    with pytest.raises(ValueError, match="duplicado"):
        reconstruct.reconstruir(teto.iloc[:3], _presenca(pd.concat([teto, teto.iloc[[0]]])))


# --- velocidade -----------------------------------------------------------------

def test_filtro_igual_ao_de_passos(cfg):
    rng = np.random.default_rng(3)
    per = np.r_[np.ones(150, "int64"), np.full(150, 2, "int64")]
    tr = _tracking([_um(np.cumsum(rng.normal(size=300)), np.cumsum(rng.normal(size=300)), per=per),
                    _um(np.cumsum(rng.normal(size=8)), np.cumsum(rng.normal(size=8)), pid="curto")])
    ordem, quebra, fx, fy = reconstruct.filtradas(tr, cfg)
    d = np.r_[0.0, np.hypot(np.diff(fx), np.diff(fy))]
    d[quebra] = 0.0
    passo = np.empty(d.size)
    passo[ordem] = d
    assert np.array_equal(passo, broadcast.passos(tr, cfg)[0])


def test_velocidade_de_movimento_uniforme(cfg):
    v = 4.0
    tr = _tracking([_um(np.arange(500) * v * DT, np.zeros(500))])
    vel = reconstruct.velocidade(tr, cfg)
    # o filtfilt tem transiente nas pontas do segmento; no meio a rampa passa intacta
    assert np.abs(vel[150:-150] - v).max() < 1e-6


def test_velocidade_segmento_de_um_quadro_estoura(cfg):
    tr = _tracking([_um(np.arange(10.0)), _um(np.array([1.0]), pid="solo")])
    with pytest.raises(ValueError, match="1 quadro"):
        reconstruct.velocidade(tr, cfg)


# --- T9: parametros ignorados ---------------------------------------------------

def _com(cfg, secao, chave, valor):
    novo = copy.deepcopy(cfg)
    novo[secao][chave] = valor
    return novo


def test_t9_butter_corte_muda_a_velocidade(cfg):
    rng = np.random.default_rng(4)
    tr = _tracking([_um(np.cumsum(rng.normal(size=400)), np.cumsum(rng.normal(size=400)))])
    v1 = reconstruct.velocidade(tr, cfg)
    v2 = reconstruct.velocidade(tr, _com(cfg, "simulador", "butter_corte_hz", 3.0))
    assert not np.allclose(v1, v2)


def test_t9_limiar_muda_a_tabela_5b(cfg):
    rng = np.random.default_rng(5)
    vt = rng.uniform(0, 10, 1000)
    vr = vt * 0.5
    pt, pr = vt * DT, vr * DT
    f1, r1, _ = run.vies_velocidade(vt, vr, pt, pr, cfg)
    f2, r2, _ = run.vies_velocidade(vt, vr, pt, pr, _com(cfg, "reconstrucao", "limiar_alta_velocidade_ms", 3.0))
    assert f1["n"].tolist() != f2["n"].tolist()
    assert r1["razao_dist_alta"] == pytest.approx(0.5) and r2["razao_dist_alta"] == pytest.approx(0.5)
    _, _, q = run.vies_velocidade(vt, vr, pt, pr, _com(cfg, "reconstrucao", "n_quantis_velocidade", 4))
    assert len(q) == 4 and q["n"].sum() == 1000


def test_t9_limiar_muda_o_5a(cfg):
    passo = np.ones(10)
    v = np.arange(10.0)
    vis = v >= 5
    a = run.dist_visivel(passo, v, vis, cfg)
    b = run.dist_visivel(passo, v, vis, _com(cfg, "reconstrucao", "limiar_alta_velocidade_ms", 2.0))
    assert a["dist"] == b["dist"] == 0.5
    assert a["dist_alta"] != b["dist_alta"]


def test_t9_faixas_buraco_mudam_o_bloco_3(cfg):
    teto = _tracking([_um(0.5 * 3.0 * (np.arange(1, 3001) * DT) ** 2)])
    manter = np.zeros(3000, bool)
    manter[[0, 20, 200, 1000, 2999]] = True
    deg = teto[manter]
    rec, _ = reconstruct.reconstruir(deg, _presenca(teto))
    info = reconstruct.buracos(_presenca(teto), deg)
    d2 = run.erro2(teto, rec, info)
    t1 = run.tabela_buraco(run.faixa_buraco(info, cfg), d2, cfg)
    novo = _com(cfg, "reconstrucao", "faixas_buraco_s", [0.5, 2.0, 10.0, 100.0])
    t2 = run.tabela_buraco(run.faixa_buraco(info, novo), d2, novo)
    assert t1["n"].tolist() != t2["n"].tolist()
    # os rotulos saem de `faixas_buraco_s`, nunca fixos
    assert t1["faixa"].tolist() == ["<=1s", "(1,5]s", "(5,15]s", "(15,60]s", ">60s", "borda"]
    assert t2["faixa"].tolist() == ["<=0.5s", "(0.5,2]s", "(2,10]s", "(10,100]s", ">100s", "borda"]
    assert set(run.faixa_buraco(info, novo)) - {""} <= set(t2["faixa"])
    assert t1["n"].sum() == t2["n"].sum() == 3000 - 5
    assert t1.loc[t1["faixa"] == "borda", "n"].item() == 0
    r = t1.loc[t1["n"] > 0, "rmse_m"].to_numpy()
    assert (np.diff(r) > 0).all()


def test_faixa_buraco_borda_e_nao_imputadas(cfg):
    teto = _tracking([_um(np.arange(100.0))])
    deg = teto.iloc[[10, 50]]
    info = reconstruct.buracos(_presenca(teto), deg)
    fa = run.faixa_buraco(info, cfg)
    assert (fa[[10, 50]] == "").all()
    assert (fa[:10] == "borda").all() and (fa[51:] == "borda").all()
    assert (fa[11:50] == "(1,5]s").all()       # 39 quadros = 1,56 s


# --- T11: denominador do bloco 6 ------------------------------------------------

def _eventos(linhas):
    df = pd.DataFrame([{"game": g, "period": 1, "frame": f, "t": f * DT, "type": t, "team": "home",
                        "player_id": p, "annotated_frame": f, "anchor_shift": 0,
                        "no_dead_ball_before": False, "pass_secundario": False,
                        "metrica_type": "", "metrica_subtype": "", "source_rows": ""}
                       for g, f, t, p in linhas])
    return schema.validar(df.astype(schema.EVENTS), schema.EVENTS, "eventos")


def _frames(n, bola_x, bola_y):
    q = np.arange(1, n + 1)
    return schema.validar(pd.DataFrame({
        "game": np.ones(n, "int64"), "period": np.ones(n, "int64"), "frame": q, "t": q * DT,
        "ball_x": np.asarray(bola_x, float), "ball_y": np.asarray(bola_y, float),
        "ball_live": ~np.isnan(np.asarray(bola_x, float))}), schema.FRAMES, "frames")


def test_t11_executor_sem_linha_fica_no_denominador(cfg):
    n = 10
    tr = _tracking([_um(np.full(n, 0.3), pid="perto"), _um(np.full(n, 2.0), pid="longe")])
    tr = tr[~((tr["player_id"] == "longe") & (tr["frame"] == 5))]          # sem linha no quadro 5
    tr.loc[(tr["player_id"] == "perto") & (tr["frame"] == 3), "visible"] = False
    ev = _eventos([(1, 3, "pass", "perto"), (1, 5, "pass", "longe"), (1, 6, "pass", "longe"),
                   (1, 7, "pass", "perto")])
    bola_x = np.zeros(n)
    bola_x[6] = np.nan                     # quadro 7 sem bola: NaN, nunca e acerto
    res = run.executor_bola(ev, tr, _frames(n, bola_x, np.zeros(n)))
    assert res["sem_linha"].tolist() == [False, True, False, False]
    assert res["imputada"].tolist() == [True, False, False, False]
    r = run.resumo_executor(res, cfg)
    assert r["n"] == 4 and r["frac_sem_linha"] == 0.25 and r["frac_imputada"] == 0.25
    grade = cfg["posse"]["grade_r_pz_m"]
    le = dict(zip(grade, r["le_R"]))
    assert le[0.5] == 0.25            # so o "perto" no quadro 3; denominador 4
    assert le[2.0] == 0.5             # + o "longe" no quadro 6
    assert r["n_d"] == 2 and r["mediana_d_m"] == pytest.approx(1.15)


# --- bloco 2: agregacao ---------------------------------------------------------

def _info(ancora, sem_ancora, borda):
    return pd.DataFrame({"ancora": ancora, "sem_ancora": sem_ancora, "borda": borda,
                         "buraco_quadros": np.zeros(len(ancora), "int64")})


def test_bloco2_agregacao_calculada_a_mao():
    # jogo 1, sem GK: 2 ancoras, 2 imputadas (d2 = 9 e 16, a 2a de borda). As
    # ancoras levam d2 = 1 SO para separar as somas: no dado real e 0 por construcao.
    i1 = _info([True, True, False, False], [False] * 4, [False, False, False, True])
    s1 = run.somas_bloco2(np.zeros(4, bool), i1, np.array([1.0, 1.0, 9.0, 16.0]))
    # jogo 2: GK ancora (0) e GK imputado (4); jogador de linha sem ancora (NaN)
    i2 = _info([True, False, False], [False, False, True], [False] * 3)
    s2 = run.somas_bloco2(np.array([True, True, False]), i2, np.array([0.0, 4.0, np.nan]))
    lin = pd.DataFrame(run.linhas_bloco2({1: s1, 2: s2}, "B", 8, 0, {1: [9, 1, 0], 2: [9, 2, 0]}))
    r = lin.set_index(["jogo", "grupo"])
    assert len(lin) == 3 * 3
    a = r.loc[(1, "sem_gk")]
    assert a["rmse_imputado"] == pytest.approx(np.sqrt(25 / 2))   # so imputadas; != sqrt(27/4)
    assert a["rmse_geral"] == pytest.approx(np.sqrt(27 / 4))
    assert (a["taxa_visivel"], a["frac_imputada"], a["n_imputadas"], a["n_borda"]) == (0.5, 0.5, 2, 1)
    b = r.loc[(2, "sem_gk")]
    assert np.isnan(b["rmse_imputado"]) and np.isnan(b["rmse_geral"])
    assert (b["n_presenca"], b["n_sem_ancora"], b["taxa_visivel"], b["frac_imputada"]) == (1, 1, 0.0, 0.0)
    c = r.loc[(2, "so_gk")]
    assert c["rmse_imputado"] == pytest.approx(2.0) and c["rmse_geral"] == pytest.approx(np.sqrt(2.0))
    t = r.loc[(0, "todos")]
    assert t["rmse_imputado"] == pytest.approx(np.sqrt(29 / 3))
    assert t["rmse_geral"] == pytest.approx(np.sqrt(31 / 6))
    assert (t["n_presenca"], t["n_imputadas"], t["n_borda"], t["n_sem_ancora"]) == (7, 3, 1, 1)
    assert t["frac_imputada"] == pytest.approx(3 / 7) and t["taxa_visivel"] == pytest.approx(3 / 7)
    assert t["semente_efetiva"] == "[9, 1, 0];[9, 2, 0]" and r.loc[(2, "todos"), "semente_efetiva"] == "[9, 2, 0]"
    g = r.loc[(0, "sem_gk")]                 # soma ANTES de dividir: (25 + 0) / (2 + 0)
    assert g["rmse_imputado"] == pytest.approx(np.sqrt(25 / 2)) and g["n_presenca"] == 5

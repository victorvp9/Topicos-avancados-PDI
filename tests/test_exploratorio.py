"""Fatia 9, apendice EXPLORATORIO: os 7 testes do docs/fatias/09-plano.md §3.

As unidades reais rodam so em R0 e no jogo 1, o recorte da §1 do plano."""

import copy
import json

import numpy as np
import pandas as pd
import pytest

from src import broadcast, experiment as ex, possession, run
from src.config import RAIZ_REPO
from src.events import bola_parada, passes
from src.io import schema

R0 = 0.50
PONTOS_EXP = RAIZ_REPO / "outputs" / "experimento" / "pontos.csv"
CHAVES_FRENTE = ("bola_some_no_apagao", "presentes_por_visible", "supressao_exige_executor")


def _cfg_r0(cfg, **liga):
    c = ex._trocar(cfg, posse__grade_r_pz_m=[R0])
    for k, v in liga.items():
        c["exploratorio"][k] = v
    return c


@pytest.fixture(scope="module")
def base1(jogo, eventos):
    frames, tracking, periods = jogo(1)
    return {1: {"frames": frames, "tracking": tracking, "periods": periods, "eventos": eventos(1)[1]}}


_UNID = {}


@pytest.fixture(scope="module")
def unidade1(base1, cfg):
    """(condicao, variante, nivel, rep, **chaves) -> tabela do jogo 1 em R0, memorizada."""
    def rodar(condicao, variante, nivel, rep, **liga):
        k = (condicao, variante, nivel, rep, tuple(sorted(liga.items())))
        if k not in _UNID:
            tab = ex.rodar_unidade(1, variante, nivel, rep, condicao, _cfg_r0(cfg, **liga), base1)
            _UNID[k] = ex._ler_tabela(tab.to_csv(index=False))      # o caminho da maquina
        return _UNID[k]
    return rodar


def _contagens_principais(tab, cfg):
    p = ex._principal(tab, cfg)
    return p.set_index("alvo").loc[list(ex.ALVOS_PRIMARIOS), ex.CONTAGENS]


# --- 1. linha base -------------------------------------------------------------------

@pytest.mark.parametrize("u", [("reconstruido", "B", 8, 0), ("reconstruido", "AB", 1, 0), ("bruto", "B", 8, 0)])
def test_1_chaves_desligadas_reproduzem_a_rodada_final(unidade1, cfg, u):
    """Com as quatro chaves desligadas (o config.yaml), a unidade reproduz
    `outputs/experimento/pontos.csv` bit a bit (texto CSV) em R0, e nao ganha
    coluna de estrato."""
    assert not any(cfg["exploratorio"][k] for k in ex.EXPLORATORIO_LIDO)
    tab = unidade1(*u)
    assert not set(ex.COLUNAS_ESTRATO) & set(tab.columns)
    assert ex.conferir_linha_base(tab, PONTOS_EXP, cfg) == len(tab) > 0


def test_1_linha_base_estoura_se_um_numero_mudar(unidade1, cfg):
    tab = unidade1("reconstruido", "B", 8, 0).copy()
    tab.loc[tab.index[0], "tp_diag"] += 1
    with pytest.raises(RuntimeError, match="linha base"):
        ex.conferir_linha_base(tab, PONTOS_EXP, cfg)


# --- 2. cada chave muda a saida --------------------------------------------------------

def _frames_sint(n, mortos=()):
    quadro = np.arange(1, n + 1)
    vivo = ~np.isin(quadro, list(mortos))
    return pd.DataFrame({"game": 1, "period": 1, "frame": quadro, "t": quadro / 25,
                         "ball_x": np.where(vivo, 0.0, np.nan), "ball_y": np.where(vivo, 0.0, np.nan),
                         "ball_live": vivo}).astype(schema.FRAMES)


def _perdas_sint(frames, linhas):
    run_id = possession.corridas_vivas(frames["ball_live"].to_numpy())[0]
    return pd.DataFrame([{"game": 1, "period": 1, "frame": f, "t": f / 25, "player_id": p, "team": "home",
                          "run_id": int(run_id[f - 1]), "termina_corrida": False, "so_por_lacuna_5": False,
                          "ds_m": 1.0} for f, p in linhas], columns=list(possession.PERDAS)).astype(possession.PERDAS)


def _det_sint(linhas):
    return pd.DataFrame(list(linhas), columns=["frame", "player_id"])


def _gabarito_sintetico(linhas):
    return pd.DataFrame(
        [{"game": 1, "period": 1, "frame": f, "t": f / 25, "type": t, "team": "home", "player_id": p,
          "annotated_frame": f, "anchor_shift": 0, "no_dead_ball_before": False, "pass_secundario": False,
          "metrica_type": "SET PIECE", "metrica_subtype": "", "source_rows": str(i)}
         for i, (f, t, p) in enumerate(linhas)]).astype(schema.EVENTS)


def test_2_presentes_por_visible_acorda_o_problema_2(cenario, cfg):
    """SINTETICO (variante do T14 da Fatia 8): `A` ativa o escanteio nos
    quadros 2 a 4, some em 5..11 e reaparece longe no 12. Reconstruido, a
    linha dele e imputada (interpolada para longe do canto, logo o gatilho fica
    incompleto): desligada, ele conta como presente e o problema 2 nao
    dispara; ligada, conta como nao detectado, o problema 2 dispara e acerta."""
    canto_x, canto_y = cfg["campo"]["comprimento_m"] / 2, cfg["campo"]["largura_m"] / 2
    bola = [(0.0, 0.0)] + [(np.nan, np.nan)] * 8 + [(0.0, 0.0)] * 3
    jog = {"g1_home_1": ("home", [(canto_x, canto_y - 1.0)] * 4 + [(20.0, 10.0)] * 8),
           "g1_home_2": ("home", [(20.0, 0.0)] * 12),
           "g1_away_1": ("away", [(-20.0, -20.0)] * 12)}
    frames, teto, cfg_s = cenario(bola, jog)
    deg = teto[~((teto["player_id"] == "g1_home_1") & teto["frame"].between(5, 11))]
    periods = pd.DataFrame([(1, 1, "away", -1, 40.0), (1, 1, "home", 1, -40.0)],
                           columns=list(schema.PERIODS)).astype(schema.PERIODS)
    dados = {"frames": frames, "periods": periods,
             "eventos": _gabarito_sintetico([(10, "corner_kick", "g1_home_1")])}
    trk = ex.tracking_da_condicao(teto, deg, "reconstruido")
    assert (~trk["visible"]).sum() == 7
    linha = {}
    for liga in (False, True):
        c = copy.deepcopy(cfg_s)
        c["exploratorio"]["presentes_por_visible"] = liga
        t = ex.pontos_de_r(dados, trk, c, ["frame"])
        linha[liga] = ex._principal(t, c).set_index("alvo").loc["corner_kick"]
    assert linha[False]["via_reserva_2"] == 0
    assert linha[True]["via_reserva_2"] == 1 and linha[True]["tp_diag"] == 1


def test_2_bola_some_zera_a_bola_so_no_apagao():
    """SINTETICO: quadros 3 e 4 sem jogador visivel (um imputado, outro sem
    linha). `bola_some` zera so eles."""
    frames = _frames_sint(6)
    trk = pd.DataFrame([(1, 1, f, "a", "home", False, 0.0, 0.0, f not in (3, 4)) for f in range(1, 7)],
                       columns=list(schema.TRACKING)).astype(schema.TRACKING)
    apagao = ex.apagao_total(trk, frames)
    assert apagao.tolist() == [False, False, True, True, False, False]
    out = ex.bola_some(frames, apagao)
    assert out["ball_x"].isna().tolist() == apagao.tolist()
    assert out["ball_live"].equals(frames["ball_live"]) and not frames["ball_x"].isna().any()


def test_2_cada_chave_muda_a_unidade_real(unidade1, cfg):
    """Fiacao: cada chave de frente, ligada sozinha, muda as contagens da
    unidade B8 rep 0 do jogo 1 (o parametro nao e ignorado no caminho
    `rodar_unidade`)."""
    base = _contagens_principais(unidade1("reconstruido", "B", 8, 0), cfg)
    for k in CHAVES_FRENTE:
        outra = _contagens_principais(unidade1("reconstruido", "B", 8, 0, **{k: True}), cfg)
        assert not outra.equals(base), k


# --- 3. C no teto e no bruto -------------------------------------------------------------

@pytest.mark.parametrize("condicao, nivel", [("bruto", 1), ("bruto", 8), ("reconstruido", 1)])
def test_3_presentes_por_visible_nao_muda_teto_nem_bruto(jogo, cfg, condicao, nivel):
    """No teto tudo e visivel e no `bruto` linha existente e linha visivel:
    a deteccao de bola parada e identica com a chave ligada."""
    frames, teto, periods = jogo(1)
    deg = teto if nivel == 1 else broadcast.degradar(teto, frames, cfg, "B", nivel, 0)
    trk = ex.tracking_da_condicao(teto, deg, condicao)
    c = _cfg_r0(cfg)
    perdas = possession.calcular(frames, trk, c)["perdas"]
    det = {}
    for liga in (False, True):
        c["exploratorio"]["presentes_por_visible"] = liga
        det[liga] = bola_parada.detectar(frames, trk, periods, perdas, c)
    pd.testing.assert_frame_equal(det[False], det[True])


# --- 4. B: a bola some so no apagao ---------------------------------------------------------

def test_4_bola_some_so_no_apagao_e_nan_nunca_acerta(base1, cfg, monkeypatch):
    """Unidade real B8 rep 0 (jogo 1) com a frente B: o `frames` que o Passo 1
    e a bola parada recebem tem NaN exatamente nos quadros ja sem bola mais os
    de apagao total; `ball_live` e o do teto; nenhum quadro de controle cai
    num quadro sem bola."""
    vistos = []
    calcular, detectar = ex.possession.calcular, bola_parada.detectar

    def espia_c(frames, tracking, c):
        out = calcular(frames, tracking, c)
        vistos.append((frames.copy(), tracking, out["control"]))
        return out

    def espia_d(frames, *a, **k):
        vistos.append((frames.copy(), None, None))
        return detectar(frames, *a, **k)

    monkeypatch.setattr(ex.possession, "calcular", espia_c)
    monkeypatch.setattr(bola_parada, "detectar", espia_d)
    ex.rodar_unidade(1, "B", 8, 0, "reconstruido", _cfg_r0(cfg, bola_some_no_apagao=True), base1)
    teto = base1[1]["frames"]
    assert len(vistos) == 3
    trk = vistos[0][1]
    apagao = ex.apagao_total(trk, teto)
    assert apagao.any() and not apagao.all()
    for fr, _, control in vistos:
        np.testing.assert_array_equal(fr["ball_live"].to_numpy(), teto["ball_live"].to_numpy())
        np.testing.assert_array_equal(fr["ball_x"].isna().to_numpy(), teto["ball_x"].isna().to_numpy() | apagao)
        np.testing.assert_array_equal(fr["ball_y"].isna().to_numpy(), fr["ball_x"].isna().to_numpy())
        fora = ~fr["ball_x"].isna().to_numpy()
        np.testing.assert_array_equal(fr["ball_x"].to_numpy()[fora], teto["ball_x"].to_numpy()[fora])
        if control is not None:
            assert not fr["ball_x"].isna().to_numpy()[control["frame"].to_numpy() - 1].any()


def test_4_distancia_nan_nunca_e_posse_nem_duelo():
    d = np.array([[np.nan, 0.1], [np.nan, 5.0]])
    duelo, dono, _, _ = possession._zonas(d, np.array(["home", "away"]), 0.5, 1.0, 1e-9)
    assert dono.tolist() == [-1, 0] and not duelo[0]


# --- 5. D: a supressao exige a perda do executor -----------------------------------------------

def test_5_supressao_exige_o_executor():
    """Corrida viva 6..30 com duas perdas, de B (quadro 8) e de A (quadro 12);
    a deteccao do quadro 6 tem executor A. Desligada: suprime a primeira (B).
    Ligada: suprime a de A e nao a primeira."""
    f = _frames_sint(30, mortos=range(1, 6))
    perdas = _perdas_sint(f, [(8, "B"), (12, "A")])
    det = _det_sint([(6, "A")])
    assert passes.suprimir(perdas, det, f).tolist() == [0, -1]
    assert passes.suprimir(perdas, det, f, exige_executor=True).tolist() == [-1, 0]


def test_5_sem_perda_do_executor_nada_e_sem_executor_a_regra_atual():
    f = _frames_sint(40, mortos=list(range(1, 6)) + list(range(20, 23)))
    perdas = _perdas_sint(f, [(8, "B"), (12, "C"), (25, "B"), (28, "A")])
    # 1a corrida: executor A nao perde a bola -> nada; 2a: sem executor -> a primeira
    det = _det_sint([(6, "A"), (23, "")])
    assert passes.suprimir(perdas, det, f).tolist() == [0, -1, 1, -1]
    assert passes.suprimir(perdas, det, f, exige_executor=True).tolist() == [-1, -1, 1, -1]


# --- 6. A: os estratos somam o total ---------------------------------------------------------

def test_6_estratos_somam_o_total_e_fn_fica_no_seu_estrato(cfg):
    """SINTETICO: 3 passes do gabarito (quadros 10, 50, 90), o do 50 em
    apagao; 2 deteccoes, uma casando o do 10 e uma solta no apagao (quadro
    55). O do 50 e FN no estrato `apagao`, nao some; o do 90 e FN em `fora`."""
    gab = _gabarito_sintetico([(10, "pass", "a"), (50, "pass", "b"), (90, "pass", "c")])
    det = pd.DataFrame([(1, 1, 10, 0.4, "pass", "home", "a"), (1, 1, 55, 2.2, "pass", "home", "x")],
                       columns=list(ex.evaluate.DETECTIONS)).astype(ex.evaluate.DETECTIONS)
    apagao = np.zeros(100, bool)
    apagao[45:60] = True
    est = ex._estratos(gab, det, "annotated_frame", apagao, {ex.ALVO_PASSE: ["pass"]}, cfg)[ex.ALVO_PASSE]
    assert est == {"apagao_n_gabarito": 1, "apagao_tp_gab": 0, "apagao_n_detectado": 1, "apagao_tp_det": 0,
                   "fora_n_gabarito": 2, "fora_tp_gab": 1, "fora_n_detectado": 1, "fora_tp_det": 1}


def test_6_estratos_da_unidade_real_somam_as_contagens(unidade1, cfg):
    tab = ex._principal(unidade1("reconstruido", "B", 8, 0, estratos_apagao=True), cfg)
    # estratos so nos alvos da §1 do plano 09 (o passe secundario fica NaN)
    assert set(tab.loc[tab["apagao_n_gabarito"].isna(), "alvo"]) == {ex.ALVO_PASSE_SEC}
    tab = tab[tab["alvo"] != ex.ALVO_PASSE_SEC]
    for c, (a, f) in (("n_gabarito", ("apagao_n_gabarito", "fora_n_gabarito")),
                      ("n_detectado", ("apagao_n_detectado", "fora_n_detectado")),
                      ("tp_diag", ("apagao_tp_gab", "fora_tp_gab")), ("tp_diag", ("apagao_tp_det", "fora_tp_det"))):
        np.testing.assert_array_equal(tab[a] + tab[f], tab[c])
    passe = tab.set_index("alvo").loc[ex.ALVO_PASSE]
    assert passe["apagao_n_gabarito"] > 0
    # os estratos nao mexem nas contagens
    base = _contagens_principais(unidade1("reconstruido", "B", 8, 0), cfg)
    assert _contagens_principais(tab.assign(), cfg).equals(base)


# --- 7. manifesto e cache ---------------------------------------------------------------------

def test_7_cache_inclui_as_chaves_novas(cfg):
    u = ("reconstruido", 1, "B", 8, 0)
    chave = ex.chave_unidade(cfg, u)[1]
    for k in ex.EXPLORATORIO_LIDO:
        c = copy.deepcopy(cfg)
        c["exploratorio"][k] = True
        assert ex.chave_unidade(c, u)[1] != chave, k
    # a grade e as frentes nao sao lidas pela unidade: nao mudam a chave
    c = copy.deepcopy(cfg)
    c["exploratorio"]["niveis"] = {"B": [8]}
    assert ex.chave_unidade(c, u)[1] == chave


def test_7_grade_da_secao_1(cfg):
    g = ex.grade_exploratoria(cfg, "reconstruido")
    n = cfg["simulador"]["n_sementes"]
    assert len(g) == 3 + 4 * n * 3 + 1 * 3
    assert {(u[2], u[3]) for u in g} == {("AB", 1), ("B", 5), ("B", 6), ("B", 7), ("B", 8), ("A", 8)}
    with pytest.raises(ValueError):
        ex.cfg_frente(cfg, "estratos_apagao")


def test_7_rodar_exploratorio_grava_semente_frente_e_estratos(cfg, mapeamento, tmp_path):
    """Ponta a ponta, recortado (jogo 1, B8 rep 0, base e D, sem cache,
    n_workers 1): a base confere, o manifesto traz semente e frente de cada
    unidade, `pontos.csv` tem `frente` e nao tem estrato, `apagao.csv` soma."""
    c = copy.deepcopy(cfg)
    c["dados"]["jogos"] = [1]
    c["simulador"]["n_sementes"] = 1
    c["experimento"]["n_workers"] = 1
    c["exploratorio"]["niveis"] = {"B": [8]}
    c["exploratorio"]["frentes"] = {"base": {"chave": None, "condicoes": ["reconstruido"]},
                                    "D": {"chave": "supressao_exige_executor", "condicoes": ["reconstruido"]}}
    ex.rodar_exploratorio(c, mapeamento, RAIZ_REPO / "config.yaml", tmp_path, None, PONTOS_EXP)
    m = json.loads((tmp_path / "manifesto.json").read_text(encoding="utf-8"))
    assert len(m["unidades"]) == 4
    for u in m["unidades"]:
        esperado = ex.SEM_SEMENTE if u["nivel"] == 1 else ";".join(
            str(s) for s in broadcast.semente_efetiva(cfg, u["jogo"], u["rep"]))
        assert u["semente_efetiva"] == esperado and u["frente"] in ("base", "D")
    p = pd.read_csv(tmp_path / "pontos.csv")
    assert set(p["frente"]) == {"base", "D"} and not set(ex.COLUNAS_ESTRATO) & set(p.columns)
    a = pd.read_csv(tmp_path / "apagao.csv")
    tot = ex.agregar(ex._principal(p, c), ["frente", "variante", "nivel", "alvo"]).set_index(
        ["frente", "variante", "nivel", "alvo"])
    s = a.groupby(["frente", "variante", "nivel", "alvo"])[["n_gabarito", "n_detectado", "tp_gab", "tp_det"]].sum()
    for col, ref in (("n_gabarito", "n_gabarito"), ("n_detectado", "n_detectado"), ("tp_gab", "tp_diag"),
                     ("tp_det", "tp_diag")):
        assert (s[col] == tot.loc[s.index, ref]).all(), col
    prim = a[a["alvo"].isin(ex.ALVOS_PRIMARIOS)]
    assert np.allclose(prim.groupby(["frente", "variante", "nivel", "alvo"])["frac_eventos"].sum(), 1.0)

"""Fatia 8a: a maquina do experimento. Testes T1-T14 do docs/fatias/08-plano.md §3.

As unidades reais rodam com a grade de `R_pz` reduzida (R0, e 3,00 m no T2)
para caber no suite; o caminho e o mesmo da grade inteira (`rodar_unidade` le
`posse.grade_r_pz_m`)."""

import copy
import json

import numpy as np
import pandas as pd
import pytest

from src import broadcast, evaluate, experiment as ex, run
from src.config import RAIZ_REPO
from src.events import bola_parada, passes as passes_mod
from src.io import schema

JOGOS = (1, 2, 3)
R0 = 0.50
R_ALTO = 3.00
# Contagens aceitas do teto, estrito, ancora `frame`, 3 jogos (decisoes.md,
# Fatia 4 e Fatia 5; outputs/origem-dos-numeros.md).
TETO = {ex.ALVO_MICRO: (232, 481, 295), ex.ALVO_PASSE: (2187, 2262, 2650)}


def _cfg_grade(cfg, *grade):
    return ex._trocar(cfg, posse__grade_r_pz_m=list(grade))


@pytest.fixture(scope="module")
def base(jogo, eventos):
    out = {}
    for g in JOGOS:
        frames, tracking, periods = jogo(g)
        out[g] = {"frames": frames, "tracking": tracking, "periods": periods, "eventos": eventos(g)[1]}
    return out


_UNIDADES = {}


@pytest.fixture(scope="module")
def unidade(base, cfg):
    """(condicao, jogo, variante, nivel, rep, *grade) -> pontos, memorizado."""
    def rodar(condicao, jogo, variante, nivel, rep, *grade):
        chave = (condicao, jogo, variante, nivel, rep, grade)
        if chave not in _UNIDADES:
            _UNIDADES[chave] = ex.rodar_unidade(jogo, variante, nivel, rep, condicao,
                                                _cfg_grade(cfg, *grade), base)
        return _UNIDADES[chave]
    return rodar


def _principal(tab, cfg):
    return tab[(tab["criterio"] == cfg["avaliacao"]["criterio_principal"]) & (tab["ancora"] == "frame")
               & (tab["lacuna5"] == "com") & (tab["politica"] == cfg["posse"]["r_dz_politica"])]


def _contagens(tab, cfg, r_pz, **filtro):
    sel = _principal(tab, cfg)
    sel = sel[sel["r_pz"] == r_pz]
    for k, v in filtro.items():
        sel = sel[sel[k] == v]
    assert len(sel) == len(set(sel["alvo"])) > 0       # o ponto existe e e um so
    return sel.set_index("alvo")[ex.CONTAGENS].sort_index()


# --- T1 ---------------------------------------------------------------------------

@pytest.mark.parametrize("condicao", ex.CONDICOES)
def test_t1_nivel_1_reproduz_o_teto(unidade, cfg, condicao):
    """Igualdade EXATA com o `--bola-parada` e o `--passes` aceitos."""
    tab = pd.concat([unidade(condicao, g, "B", 1, 3, R0) for g in JOGOS], ignore_index=True)
    assert set(tab["variante"]) == {ex.VARIANTE_TETO} and set(tab["rep"]) == {0}
    assert set(tab["semente_efetiva"]) == {ex.SEM_SEMENTE}
    agg = ex.agregar(_principal(tab, cfg), ["condicao", "alvo"]).set_index("alvo")
    for alvo, (tp, n_det, n_gab) in TETO.items():
        assert (agg.loc[alvo, "tp_diag"], agg.loc[alvo, "n_detectado"], agg.loc[alvo, "n_gabarito"]) == (
            tp, n_det, n_gab), alvo
    assert (tab["taxa_todos"] == 1.0).all() and (tab["taxa_sem_gk"] == 1.0).all()


def test_t1_nivel_1_tem_a_ancora_anotada_so_em_r0(unidade, cfg):
    tab = unidade("bruto", 1, "AB", 1, 0, R0, R_ALTO)
    assert set(tab.loc[tab["r_pz"] == R0, "ancora"]) == set(cfg["avaliacao"]["ancoras"])
    assert set(tab.loc[tab["r_pz"] == R_ALTO, "ancora"]) == {"frame"}


# --- T2 ---------------------------------------------------------------------------

def test_t2_parametros_varridos_mudam_as_contagens(unidade, cfg):
    b8 = unidade("reconstruido", 1, "B", 8, 0, R0, R_ALTO)
    b8_rep1 = unidade("reconstruido", 1, "B", 8, 1, R0)
    a8 = unidade("reconstruido", 1, "A", 8, 0, R0)
    em_r0 = _contagens(b8, cfg, R0)
    assert not em_r0.equals(_contagens(b8, cfg, R_ALTO))          # R_pz
    assert not em_r0.equals(_contagens(b8_rep1, cfg, R0))         # rep
    assert not em_r0.equals(_contagens(a8, cfg, R0))              # variante
    assert b8_rep1["semente_efetiva"].iloc[0] == "{};1;1".format(cfg["simulador"]["semente_base"])


def test_t2_fixo_1m_so_acima_de_r_dz_e_identico_abaixo(unidade, base, cfg):
    b8 = unidade("reconstruido", 1, "B", 8, 0, R0, R_ALTO)
    assert set(b8.loc[b8["politica"] == ex.FIXO, "r_pz"]) == {R_ALTO}
    assert R_ALTO > cfg["posse"]["r_dz_m"] >= R0
    acompanha = b8[(b8["politica"] == cfg["posse"]["r_dz_politica"]) & (b8["r_pz"] == R_ALTO)]
    fixo = b8[(b8["politica"] == ex.FIXO) & (b8["r_pz"] == R_ALTO)]
    colunas = ["lacuna5", "criterio", "ancora", "alvo"] + ex.CONTAGENS
    assert not acompanha[colunas].reset_index(drop=True).equals(fixo[colunas].reset_index(drop=True))
    # abaixo de r_dz_m: tabela IDENTICA, por construcao
    d = base[1]
    trk = ex.tracking_da_condicao(d["tracking"], broadcast.degradar(d["tracking"], d["frames"], cfg, "B", 8, 0),
                                  "reconstruido")
    t_a = ex.pontos_de_r(d, trk, run.com_r_pz(cfg, R0, cfg["posse"]["r_dz_politica"]), ["frame"])
    t_f = ex.pontos_de_r(d, trk, run.com_r_pz(cfg, R0, ex.FIXO), ["frame"])
    pd.testing.assert_frame_equal(t_a.drop(columns="politica"), t_f.drop(columns="politica"))


def test_t2_fixo_1m_so_nos_niveis_do_config(base, cfg):
    cfg_sem = ex._trocar(_cfg_grade(cfg, R_ALTO), experimento__niveis_fixo_1m=[1, 5])
    tab = ex.rodar_unidade(1, "B", 8, 0, "bruto", cfg_sem, base)
    assert set(tab["politica"]) == {cfg["posse"]["r_dz_politica"]}


# --- T3, T7, T13, T14 e invariantes nas unidades reais ------------------------------

def _todas(unidade):
    for g in JOGOS:
        unidade("reconstruido", g, "B", 8, 0, R0)
    unidade("bruto", 1, "B", 8, 0, R0)
    return pd.concat(list(_UNIDADES.values()), ignore_index=True)


def test_t3_n_gabarito_constante_em_todos_os_pontos(unidade):
    todas = _todas(unidade)
    assert todas["jogo"].nunique() == 3 and todas["nivel"].nunique() == 2
    ex.conferir_n_gabarito(todas)
    adulterada = todas.copy()
    adulterada.loc[adulterada.index[0], "n_gabarito"] += 1
    with pytest.raises(ValueError, match="n_gabarito"):
        ex.conferir_n_gabarito(adulterada)


def test_r9_fn_por_executor_fecha_com_as_contagens(unidade, cfg):
    """Em toda linha principal: soma de `fn_exec_*` = `n_gabarito - tp_diag` e
    soma de `gab_exec_*` = `n_gabarito`; nas outras, NaN."""
    todas = _todas(unidade)
    p = (todas["criterio"] == cfg["avaliacao"]["criterio_principal"]) & (todas["ancora"] == "frame")
    fn = todas.loc[p, [f"fn_exec_{e}" for e in ex.ESTADOS]].sum(axis=1)
    gab = todas.loc[p, [f"gab_exec_{e}" for e in ex.ESTADOS]].sum(axis=1)
    assert (fn == todas.loc[p, "n_gabarito"] - todas.loc[p, "tp_diag"]).all()
    assert (gab == todas.loc[p, "n_gabarito"]).all()
    assert todas.loc[~p, ex.DECOMP].isna().all().all()
    passe = todas[p & (todas["alvo"] == ex.ALVO_PASSE)]
    causas = passe[[f"fn_causa_{c}" for c in "abcd"]].sum(axis=1)
    assert (causas == passe["n_gabarito"] - passe["tp_diag"]).all()
    # reconstruido nunca tem executor ausente; bruto nunca tem imputado
    rec, bru = todas[p & (todas["condicao"] == "reconstruido")], todas[p & (todas["condicao"] == "bruto")]
    assert (rec["gab_exec_ausente"] == 0).all() and (bru["gab_exec_imputado"] == 0).all()
    assert bru.loc[bru["nivel"] == 8, "gab_exec_ausente"].sum() > 0


def test_t7_ball_live_e_o_do_teto_em_toda_unidade(base, cfg, monkeypatch):
    vistos = []
    calcular, detectar = ex.possession.calcular, bola_parada.detectar

    def espia_c(frames, tracking, c):
        vistos.append(frames["ball_live"].to_numpy().copy())
        return calcular(frames, tracking, c)

    def espia_d(frames, *a, **k):
        vistos.append(frames["ball_live"].to_numpy().copy())
        return detectar(frames, *a, **k)

    monkeypatch.setattr(ex.possession, "calcular", espia_c)
    monkeypatch.setattr(bola_parada, "detectar", espia_d)
    for condicao in ex.CONDICOES:
        ex.rodar_unidade(1, "B", 8, 0, condicao, _cfg_grade(cfg, R0), base)
    assert len(vistos) == 2 * 3        # por condicao: posse + deteccao com e sem lacuna 5
    for v in vistos:
        np.testing.assert_array_equal(v, base[1]["frames"]["ball_live"].to_numpy())


def test_t13_taxa_amostrada_igual_a_da_reconstrucao(unidade):
    csv = pd.read_csv(RAIZ_REPO / "outputs" / "reconstrucao.csv")
    csv = csv[(csv["variante"] == "B") & (csv["nivel"] == 8) & (csv["grupo"] == "sem_gk")].set_index("jogo")
    for g in JOGOS:
        assert unidade("reconstruido", g, "B", 8, 0, R0)["taxa_sem_gk"].iloc[0] == csv.loc[g, "taxa_visivel"]
    assert round(csv.loc[0, "taxa_visivel"], 4) == 0.3766


def test_t14_bruto_roda_com_linhas_ausentes(unidade, cfg):
    tab = unidade("bruto", 1, "B", 8, 0, R0)
    p = _principal(tab, cfg)
    assert p["gab_exec_ausente"].sum() > 0
    assert tab["n_dist"].iloc[0] < unidade("reconstruido", 1, "B", 8, 0, R0)["n_dist"].iloc[0]


def _gabarito_sintetico(linhas):
    return pd.DataFrame(
        [{"game": 1, "period": 1, "frame": f, "t": f / 25, "type": t, "team": "home", "player_id": p,
          "annotated_frame": f, "anchor_shift": 0, "no_dead_ball_before": False, "pass_secundario": False,
          "metrica_type": "SET PIECE", "metrica_subtype": "", "source_rows": str(i)}
         for i, (f, t, p) in enumerate(linhas)]).astype(schema.EVENTS)


def test_t14_executor_ausente_dispara_o_problema_2(cenario, cfg):
    """SINTETICO: `A` ativa o escanteio nos quadros 2 a 4 e some (bruto). O
    caminho do experimento (condicao `bruto` -> `pontos_de_r`) leva a deteccao
    pela `reserva_2` e conta o executor como ausente no quadro anotado."""
    canto_x, canto_y = cfg["campo"]["comprimento_m"] / 2, cfg["campo"]["largura_m"] / 2
    ausente = (np.nan, np.nan)
    bola = [(0.0, 0.0)] + [ausente] * 8 + [(0.0, 0.0)] * 3
    jog = {"g1_home_1": ("home", [(canto_x, canto_y - 1.0)] * 4 + [(20.0, 10.0)] * 8),
           "g1_home_2": ("home", [(20.0, 0.0)] * 12),
           "g1_away_1": ("away", [(-20.0, -20.0)] * 12)}
    frames, teto, cfg_s = cenario(bola, jog)
    deg = teto[~((teto["player_id"] == "g1_home_1") & (teto["frame"] > 4))]
    periods = pd.DataFrame([(1, 1, "away", -1, 40.0), (1, 1, "home", 1, -40.0)],
                           columns=list(schema.PERIODS)).astype(schema.PERIODS)
    dados = {"frames": frames, "periods": periods,
             "eventos": _gabarito_sintetico([(10, "corner_kick", "g1_home_1")])}
    linhas = {}
    for condicao in ex.CONDICOES:
        trk = ex.tracking_da_condicao(teto, deg, condicao)
        t = ex.pontos_de_r(dados, trk, cfg_s, ["frame"])
        linhas[condicao] = _principal(t, cfg_s).set_index("alvo").loc["corner_kick"]
    assert linhas["bruto"]["via_reserva_2"] == 1 and linhas["bruto"]["tp_diag"] == 1
    assert linhas["bruto"]["gab_exec_ausente"] == 1
    assert linhas["reconstruido"]["via_reserva_2"] == 0
    assert linhas["reconstruido"]["gab_exec_imputado"] == 1


def test_lacuna5_varrido_muda_as_contagens(unidade, cfg):
    """No teto (os 3 jogos, R0): passe principal n_det 2262 com e 2261 sem
    (N5); bola parada com contagens por tipo diferentes. Mata os mutantes que
    fazem o `sem` igual ao `com` (redeteccao sem o filtro; passes sem o N5)."""
    tab = pd.concat([unidade("bruto", g, "AB", 1, 0, R0) for g in JOGOS], ignore_index=True)
    p = tab[(tab["criterio"] == cfg["avaliacao"]["criterio_principal"]) & (tab["ancora"] == "frame")]
    agg = ex.agregar(p, ["lacuna5", "alvo"]).set_index(["lacuna5", "alvo"])
    assert agg.loc[("com", ex.ALVO_PASSE), "n_detectado"] == 2262
    assert agg.loc[("sem", ex.ALVO_PASSE), "n_detectado"] == 2261
    tipos = [t for t in cfg["avaliacao"]["grupos"]["bola_parada"]]
    com = agg.loc["com"].loc[tipos, ex.CONTAGENS]
    sem = agg.loc["sem"].loc[tipos, ex.CONTAGENS]
    assert not com.equals(sem)


class _Registra(dict):
    """dict que registra o caminho de toda chave lida (sobrevive ao deepcopy)."""
    lidas = set()

    def __init__(self, d, caminho=()):
        super().__init__({k: _Registra(v, caminho + (k,)) if isinstance(v, dict) else v for k, v in d.items()})
        self.caminho = caminho

    def __getitem__(self, k):
        _Registra.lidas.add(self.caminho + (k,))
        return super().__getitem__(k)

    def get(self, k, padrao=None):
        _Registra.lidas.add(self.caminho + (k,))
        return super().get(k, padrao)


def test_cache_cobre_toda_chave_lida_pela_unidade(cfg, mapeamento):
    """Roda `_base_leve` e `rodar_unidade` (B8 nas duas condicoes e o nivel 1,
    com R_pz acima de r_dz para passar pelo `fixo_1m`) com o config embrulhado:
    toda chave lida (ate o 2o nivel) tem de estar em `config_lido`. Mata os
    mutantes "cache sem `posse`", "sem `avaliacao`" e "sem as chaves de
    `experimento`"."""
    _Registra.lidas = set()
    reg = _Registra(_cfg_grade(cfg, R0, R_ALTO))
    base = run._base_leve(reg, mapeamento, [1])
    for u in (("reconstruido", 1, "B", 8, 0), ("bruto", 1, "B", 8, 0), ("bruto", 1, "AB", 1, 0)):
        ex.rodar_unidade(u[1], u[2], u[3], u[4], u[0], reg, base)
    lido = ex.config_lido(cfg)
    lidas = _Registra.lidas
    assert ("posse", "r_pz_m") in lidas and ("experimento", "niveis_fixo_1m") in lidas
    fora = sorted(c for c in lidas if c[0] not in lido or (len(c) > 1 and c[1] not in lido[c[0]]))
    assert not fora, fora


# --- T4 e T12: agregar --------------------------------------------------------------

def _pontos_sinteticos(linhas, **fixo):
    """`linhas`: [(jogo, rep, tp_diag, n_detectado, n_gabarito), ...]."""
    padrao = dict(condicao="reconstruido", variante="B", nivel=8, r_pz=R0, politica="acompanha_r_pz",
                  lacuna5="com", criterio="estrito", ancora="frame", alvo=ex.ALVO_PASSE, taxa_todos=0.5,
                  taxa_sem_gk=0.5)
    padrao.update(fixo)
    return pd.DataFrame([{**padrao, "jogo": j, "rep": r, "tp_diag": tp, "tp": tp, "n_detectado": nd,
                          "n_gabarito": ng} for j, r, tp, nd, ng in linhas])


def test_t4_unidade_sem_deteccao_e_nan_e_entra_na_soma():
    """Sem deteccao: P = NaN. F1 = 2 tp / (n_det + n_gab) (plano 08 §8) da 0
    com n_gab > 0 e NaN so com n_det + n_gab = 0; o jogo NaN nao some."""
    pts = _pontos_sinteticos([(1, 0, 0, 0, 5), (2, 0, 8, 10, 10), (3, 0, 0, 0, 0)])
    por_jogo = ex.agregar(pts, ["alvo", "jogo"]).set_index("jogo")
    assert np.isnan(por_jogo.loc[1, "precisao"]) and por_jogo.loc[1, "f1"] == 0.0
    assert por_jogo.loc[1, "revocacao"] == 0.0
    assert np.isnan(por_jogo.loc[3, "f1"]) and np.isnan(por_jogo.loc[3, "revocacao"])
    tudo = ex.agregar(pts, ["alvo"]).iloc[0]
    assert (tudo["tp_diag"], tudo["n_detectado"], tudo["n_gabarito"], tudo["n_linhas"]) == (8, 10, 15, 3)
    assert tudo["f1"] == 2 * 8 / (10 + 15)                     # a mao: 0,64, a mesma divisao
    assert np.isnan(tudo["f1_jogo_min"]) and np.isnan(tudo["f1_jogo_max"])   # o jogo NaN nao some


def test_f1_e_uma_divisao_so():
    """600/700/800 e 640/800/800 sao 0,8 em fracao e tem de ser o MESMO float
    (2PR/(P+R) da 0,7999999999999999 e 0,8000000000000002)."""
    f1 = ex._prf([600, 640], [700, 800], [800, 800])[2]
    assert f1[0] == f1[1] == 0.8


def test_t12_agregar_soma_antes_de_dividir():
    pts = _pontos_sinteticos([(1, 0, 1, 1, 1), (2, 0, 0, 9, 9)])
    tudo = ex.agregar(pts, ["alvo"]).iloc[0]
    assert tudo["f1"] == pytest.approx(2 / 20)          # media de F1 daria 0,5
    assert (tudo["f1_jogo_min"], tudo["f1_jogo_max"]) == (0.0, 1.0)


def test_agregar_recusa_mistura_de_chaves():
    pts = pd.concat([_pontos_sinteticos([(1, 0, 1, 1, 1)]),
                     _pontos_sinteticos([(1, 0, 1, 1, 1)], criterio="mills")])
    with pytest.raises(ValueError, match="criterio"):
        ex.agregar(pts, ["alvo"])
    assert len(ex.agregar(pts, ["alvo", "criterio"])) == 2


# --- T5 e T6: cache e determinismo ----------------------------------------------------

UNID_CACHE = ("bruto", 1, "AB", 1, 0)


def test_t5_cache(cfg, mapeamento, tmp_path):
    c = _cfg_grade(cfg, R0)
    p1, l1 = ex.rodar_unidades([UNID_CACHE], c, mapeamento, 1, tmp_path)
    p2, l2 = ex.rodar_unidades([UNID_CACHE], c, mapeamento, 1, tmp_path)
    assert (l1[0]["cache"], l2[0]["cache"]) == ("miss", "hit")
    pd.testing.assert_frame_equal(p1, p2)
    assert p1.to_csv(index=False) == p2.to_csv(index=False)
    # chave NAO lida pela unidade: hit
    nao_lida = ex._trocar(c, relatorio__limiar_celula_lenta_s=99.0, experimento__n_workers=7,
                          simulador__n_sementes=10)
    assert ex.rodar_unidades([UNID_CACHE], nao_lida, mapeamento, 1, tmp_path)[1][0]["cache"] == "hit"
    # chave lida: miss, e o resultado muda
    lida = ex._trocar(c, bola_parada__eps_c_m=8.0)
    p3, l3 = ex.rodar_unidades([UNID_CACHE], lida, mapeamento, 1, tmp_path)
    assert l3[0]["cache"] == "miss" and len(list(tmp_path.glob("*.json"))) == 2
    assert not p3[ex.CONTAGENS].equals(p1[ex.CONTAGENS])
    # src e dados entram na chave
    material, chave = ex.chave_unidade(c, UNID_CACHE)
    assert set(material["dados"]["jogo_1"]) == {
        "Sample_Game_1_RawEventsData.csv", "Sample_Game_1_RawTrackingData_Away_Team.csv",
        "Sample_Game_1_RawTrackingData_Home_Team.csv"}
    assert "experiment.py" in material["src"] and "mapeamento" in material["dados"]
    outro_src = dict(material["src"], **{"experiment.py": "0" * 64})
    assert ex.chave_unidade(c, UNID_CACHE, outro_src)[1] != chave
    assert ex.chave_unidade(c, ("bruto", 2, "AB", 1, 0))[1] != chave
    # entrada adulterada estoura: tabela e chave
    arquivo = tmp_path / f"{chave}.json"
    original = arquivo.read_text(encoding="utf-8")
    entrada = json.loads(original)
    entrada["tabela_csv"] = entrada["tabela_csv"].replace("\n", "\n9", 1)    # um digito a mais
    arquivo.write_text(json.dumps(entrada), encoding="utf-8")
    with pytest.raises(RuntimeError, match="adulterada"):
        ex.rodar_unidades([UNID_CACHE], c, mapeamento, 1, tmp_path)
    entrada = json.loads(original)
    entrada["material"]["unidade"][1] = 2
    arquivo.write_text(json.dumps(entrada), encoding="utf-8")
    with pytest.raises(RuntimeError, match="outra chave"):
        ex.rodar_unidades([UNID_CACHE], c, mapeamento, 1, tmp_path)


def test_t6_n_workers_1_e_2_dao_o_mesmo_csv(cfg, mapeamento):
    c = _cfg_grade(cfg, R0)
    unidades = [("reconstruido", 1, "B", 8, 1), ("bruto", 1, "B", 8, 0), ("reconstruido", 1, "B", 8, 0)]
    p1, l1 = ex.rodar_unidades(unidades, c, mapeamento, 1, None)
    p2, l2 = ex.rodar_unidades(unidades, c, mapeamento, 2, None)
    assert p1.to_csv(index=False).encode() == p2.to_csv(index=False).encode()
    assert [u["semente_efetiva"] for u in l1] == [
        ";".join(str(s) for s in broadcast.semente_efetiva(cfg, u[1], u[4])) for u in sorted(unidades)]
    assert [u["semente_efetiva"] for u in l1] == [u["semente_efetiva"] for u in l2]
    m = ex.manifesto(c, RAIZ_REPO / "config.yaml", l1)
    assert len(m["unidades"]) == 3 and all(u["semente_efetiva"] for u in m["unidades"])
    assert set(m["versoes"]) == {"python", "numpy", "pandas", "scipy"} and len(m["commit"]) == 40


def test_grade_r3(cfg):
    g = ex.grade(cfg)
    n_sem = cfg["simulador"]["n_sementes"]
    assert cfg["experimento"]["variantes_sem_semente"] == ["A"]
    por_cond = 3 + 7 * n_sem * 3 + 7 * 1 * 3          # teto + B com sementes + A so rep 0
    assert len(g) == por_cond * len(cfg["experimento"]["condicoes"])
    assert len({ex.normalizar(u) for u in g}) == len(g)
    assert {u[4] for u in g if u[2] == "A"} == {0}
    assert {u[4] for u in g if u[2] == "B"} == set(range(n_sem))


@pytest.mark.parametrize("nivel", [2, 8])
def test_variante_sem_semente_tem_mascara_igual_entre_reps(jogo, cfg, nivel):
    """O fato que deixa A so com rep 0: se alguem puser cortes em A, cai."""
    frames, tracking, _ = jogo(1)
    for v in cfg["experimento"]["variantes_sem_semente"]:
        np.testing.assert_array_equal(broadcast.mascara(tracking, frames, cfg, v, nivel, 0),
                                      broadcast.mascara(tracking, frames, cfg, v, nivel, 1))
    # e B depende da semente (senao o teste nao discrimina nada)
    assert not np.array_equal(broadcast.mascara(tracking, frames, cfg, "B", 8, 0),
                              broadcast.mascara(tracking, frames, cfg, "B", 8, 1))


# --- T8: guarda de micro() ----------------------------------------------------------

def _resultado(**troca):
    linha = dict(criterio="estrito", ancora="frame", game=0, type="throw_in", n_gabarito=10,
                 n_detectado=10, tp_diag=5, f1=0.5)
    return pd.DataFrame([linha, {**linha, "type": "corner_kick", **troca}])


@pytest.mark.parametrize("troca", [{"criterio": "mills"}, {"ancora": "annotated_frame"}, {"game": 1}])
def test_t8_micro_recusa_mistura(troca):
    for funcao in (evaluate.micro, evaluate.media_ponderada_f1):
        with pytest.raises(ValueError, match=list(troca)[0]):
            funcao(_resultado(**troca))
    assert evaluate.micro(_resultado())["tp_diag"] == 10
    assert evaluate.media_ponderada_f1(_resultado()) == 0.5


# --- T9: N4 e N5 --------------------------------------------------------------------

def _tp(gab, det, cfg):
    res, _ = evaluate.avaliar(gab, det, cfg)
    linha = res[(res["criterio"] == "estrito") & (res["ancora"] == "frame") & (res["game"] == 0)
                & (res["type"] == "pass")].iloc[0]
    return int(linha["tp_diag"]), int(linha["n_detectado"]), round(float(linha["f1"]), 3)


def test_t9_n4_e_n5_travados(passes_real, eventos, jogo, cfg):
    """`decisoes.md` 2026-11-04 e `origem-dos-numeros.md` (Fatia 5, blocos 7 e 9)."""
    ev = pd.concat([eventos(g)[1] for g in JOGOS], ignore_index=True)
    sec = evaluate.gabarito_secundario(ev, cfg)
    p = pd.concat([passes_real(g)[0] for g in JOGOS], ignore_index=True)
    det = pd.concat([passes_real(g)[1] for g in JOGOS], ignore_index=True)
    # N5: sem lacuna 5, 2884 passes; F1 principal 0,890, secundario 0,859
    sem = run.passes_sem_lacuna_5(p)
    assert len(passes_mod.para_casador(sem)) == 2884
    assert _tp(ev, passes_mod.para_casador(sem, so_completo=True), cfg) == (2186, 2261, 0.890)
    assert _tp(sec, passes_mod.para_casador(sem), cfg) == (2719, 2884, 0.859)
    # N4: so o executor suprime, 3132 / 2282 / 2886 (EXPLORATORIO)
    alt = run.passes_so_executor({g: {"frames": jogo(g)[0]} for g in JOGOS}, det, p, JOGOS)
    assert len(passes_mod.para_casador(alt)) == 3132
    assert _tp(ev, passes_mod.para_casador(alt, so_completo=True), cfg)[0] == 2282
    assert _tp(sec, passes_mod.para_casador(alt), cfg)[0] == 2886
    assert not p["e_bola_parada"].equals(alt["e_bola_parada"])     # nao muta a entrada


# --- T10: selecionar_logo (R6 com a emenda do plano 08 §8) -------------------------

def _logo(tabela, **fixo):
    """`tabela`: {(nivel, alvo): {jogo: {r_pz: (tp, n_det, n_gab)}}} -> pontos;
    o nivel 1 vira a variante AB."""
    linhas = []
    for (nivel, alvo), por_jogo in tabela.items():
        for j, por_r in por_jogo.items():
            for r, (tp, nd, ng) in por_r.items():
                linhas.append(_pontos_sinteticos([(j, 0, tp, nd, ng)], r_pz=r, alvo=alvo, nivel=nivel,
                                                 variante="AB" if nivel == 1 else "B", **fixo))
    return pd.concat(linhas, ignore_index=True)


def _uma(s, alvo, nivel=8, condicao="reconstruido"):
    return s[(s["alvo"] == alvo) & (s["nivel"] == nivel) & (s["condicao"] == condicao)].set_index("jogo_teste")


SIMPSON = {   # dobra 3 (treino 1 e 2): ver o docstring
    1: {0.5: (10, 10, 100), 1.0: (60, 110, 100), 2.0: (30, 110, 100)},
    2: {0.5: (900, 1000, 1000), 1.0: (899, 1000, 1000), 2.0: (901, 1001, 1000)},
    3: {0.5: (10, 10, 100), 1.0: (10, 10, 100), 2.0: (10, 10, 100)},
}


def test_t10_candidato_exige_ganho_em_cada_jogo_e_no_treino_somado(cfg):
    """Dobra 3, treino {1, 2}. 1,0 m ganha so no jogo 1 (perde no 2) mas ganha no
    treino somado; 2,0 m ganha nos DOIS jogos mas perde no treino somado
    (Simpson: 1862/2211 < 1820/2110). Sem candidato -> R0.
    Mutantes que morrem: `.all` -> `.any` (daria 1,0); sem a guarda de Simpson
    (daria 2,0); sem candidato -> argmax do treino (daria 1,0)."""
    s = ex.selecionar_logo(_logo({(8, ex.ALVO_PASSE): SIMPSON}), cfg)
    assert _uma(s, ex.ALVO_PASSE).loc[3, "r_estrela"] == R0


def test_t10_simpson_com_igualdade_exata_nao_e_candidato(cfg):
    """Dobra 3: 2,0 m ganha nos jogos 1 e 2, e no treino somado empata EXATO com
    R0 (2002/2321 = 1820/2110 = 182/211). Empate nao e ganho: R0. Mata `>=` na
    guarda de Simpson."""
    por_jogo = {1: {0.5: (10, 10, 100), 2.0: (30, 110, 100)},
                2: {0.5: (900, 1000, 1000), 2.0: (971, 1111, 1000)},
                3: {0.5: (10, 10, 100), 2.0: (10, 10, 100)}}
    assert ex._prf(1001, 1221, 1100)[2] == ex._prf(910, 1010, 1100)[2]
    s = ex.selecionar_logo(_logo({(8, ex.ALVO_PASSE): por_jogo}), cfg)
    assert _uma(s, ex.ALVO_PASSE).loc[3, "r_estrela"] == R0


def test_t10_fracao_com_denominador_menor_que_lambda_e_nan(cfg):
    """F1_LOGO(teto) - F1_B8(R0) = 0,805 - 0,8 = 0,005, entre 0 e lambda: a
    fracao sai NaN (com `> 0` no lugar de `> lambda` sairia 0,05/0,005 = 10)."""
    t = {(8, "corner_kick"): {j: _sobe(800, 850, 1000, 1000) for j in JOGOS},
         (1, "corner_kick"): {j: _plano(805, 1000, 1000) for j in JOGOS}}
    c = _uma(ex.selecionar_logo(_logo(t), cfg), "corner_kick")
    assert c["delta_agregado"].iloc[0] == pytest.approx(0.05) and (c["ajuda"] == "sim").all()
    assert c["fracao_recuperada"].isna().all()


def test_t10_empate_de_float_fica_com_o_menor(cfg):
    """Dobra 3: no treino somado, 1,0 m = 600/700/800 e 2,0 m = 640/800/800,
    os dois 0,8 em fracao. Tem de empatar e ficar 1,0 m. Mutante: F1 como
    2PR/(P+R) da 0,7999999999999999 contra 0,8000000000000002 e escolhe 2,0."""
    por_jogo = {j: {0.5: (200, 400, 400), 1.0: (300, 350, 400), 2.0: (320, 400, 400)} for j in (1, 2)}
    por_jogo[3] = {r: (200, 400, 400) for r in (0.5, 1.0, 2.0)}
    s = ex.selecionar_logo(_logo({(8, ex.ALVO_PASSE): por_jogo}), cfg)
    assert _uma(s, ex.ALVO_PASSE).loc[3, "r_estrela"] == 1.0


def _plano(tp, nd, ng):
    return {0.5: (tp, nd, ng), 2.0: (tp, nd, ng)}


def _sobe(a, b, nd, ng):
    return {0.5: (a, nd, ng), 2.0: (b, nd, ng)}


def _cenario_conclusoes():
    t = {
        # passe: n DIFERENTE por jogo; Delta_g = 0,3 / 0,002 / 0,002 (media 0,101),
        # Delta_agregado = 14/4020 = 0,0035 < lambda
        (8, ex.ALVO_PASSE): {1: _sobe(5, 8, 10, 10), 2: _sobe(800, 802, 1000, 1000),
                             3: _sobe(800, 802, 1000, 1000)},
        (1, ex.ALVO_PASSE): {1: _plano(9, 10, 10), 2: _plano(900, 1000, 1000), 3: _plano(900, 1000, 1000)},
        # micro: nivel 8 ganha 0,05, o teto ganha 0,045 -> ajuda, nao compensa
        (8, ex.ALVO_MICRO): {j: _sobe(500, 550, 1000, 1000) for j in JOGOS},
        (1, ex.ALVO_MICRO): {j: _sobe(800, 845, 1000, 1000) for j in JOGOS},
        # secundario: nivel 8 ganha 0,05, o teto nao ganha -> compensa
        (8, ex.ALVO_PASSE_SEC): {j: _sobe(500, 550, 1000, 1000) for j in JOGOS},
        (1, ex.ALVO_PASSE_SEC): {j: _plano(800, 1000, 1000) for j in JOGOS},
    }
    # o teto de OUTRA condicao nao ganha nada: se a busca do nivel 1 ignorasse a
    # condicao, o micro passaria a "compensa"
    outra = _logo({(1, ex.ALVO_MICRO): {j: _plano(800, 1000, 1000) for j in JOGOS}}, condicao="bruto")
    return pd.concat([_logo(t), outra], ignore_index=True)


def test_t10_conclusoes_e_fracao(cfg):
    """Mutantes que morrem: Delta_agregado como media dos Delta_g (passe daria
    "ajuda"); sem `Delta_agregado > lambda` (idem); "compensa" sem comparar com
    o nivel 1 (micro daria "compensa"); nivel 1 de outra condicao (idem)."""
    s = ex.selecionar_logo(_cenario_conclusoes(), cfg)
    p = _uma(s, ex.ALVO_PASSE)
    assert (p["r_estrela"] == 2.0).all() and (p["n_delta_pos"] == 3).all()
    assert p["delta"].to_numpy() == pytest.approx([0.3, 0.002, 0.002])
    assert p["delta_agregado"].iloc[0] == 3224 / 4020 - 3210 / 4020
    assert (p["ajuda"] == "nao").all() and (p["compensa"] == "nao").all()
    m = _uma(s, ex.ALVO_MICRO)
    assert m["delta_agregado"].iloc[0] == pytest.approx(0.05)
    assert m["delta_agregado_nivel_1"].iloc[0] == pytest.approx(0.045)
    assert (m["ajuda"] == "sim").all() and (m["compensa"] == "nao").all()
    # fracao = 0,05 / (F1_LOGO(teto) 0,845 - F1_B8(R0) 0,5)
    assert m["fracao_recuperada"].iloc[0] == pytest.approx(0.05 / (0.845 - 0.5))
    sec = _uma(s, ex.ALVO_PASSE_SEC)
    assert (sec["ajuda"] == "sim").all() and (sec["compensa"] == "sim").all()
    assert sec["fracao_recuperada"].iloc[0] == pytest.approx(0.05 / (0.8 - 0.5))
    teto = s[s["nivel"] == 1]
    assert (teto["compensa"] == "nao_se_aplica").all() and teto["fracao_recuperada"].isna().all()
    assert (_uma(s, ex.ALVO_MICRO, 1)["ajuda"] == "sim").all()
    assert (_uma(s, ex.ALVO_PASSE, 1)["r_estrela"] == R0).all()       # sem ganho, R0
    assert (p["r_dentro_amostra_EXPLORATORIO"] == 2.0).all()


@pytest.mark.parametrize("n_pos, d_agg, d_teto, esperado", [
    (2, 0.02, 0.0, ("sim", "sim")),
    (1, 0.02, 0.0, ("nao", "nao")),           # mata "sem exigir >= 2 jogos"
    (3, 0.01, 0.0, ("nao", "nao")),           # > lambda e estrito
    (3, 0.005, 0.0, ("nao", "nao")),          # mata "sem exigir Delta_agregado > lambda"
    (3, 0.05, 0.045, ("sim", "nao")),         # mata "compensa sem o nivel 1"
    (3, 0.023, 0.013, ("sim", "nao")),        # 0.023 - 0.013 == 0.01 exato: mata `>=` no compensa
    (3, 0.05, None, ("sim", "nao_se_aplica")),
    (3, np.nan, 0.0, ("nao", "nao")),         # NaN nunca passa
    (3, 0.05, np.nan, ("sim", "nao")),
])
def test_t10_conclusoes_diretas(cfg, n_pos, d_agg, d_teto, esperado):
    assert cfg["experimento"]["ep_max_f1"] == 0.01 and cfg["experimento"]["min_jogos_compensa"] == 2
    assert ex.conclusoes(n_pos, d_agg, d_teto, cfg) == esperado


# --- T11: regra_sementes ------------------------------------------------------------

def _piloto(a_ruido, a_escanteio=2000, nan_em=None):
    """F1 por semente = 0,5 +- a (alternado), n = 10000; o escanteio com ruido
    grande. A (sem semente) so com rep 0 e ruido enorme: fica fora da regra."""
    linhas = []
    for v in ("A", "B"):
        for alvo in (*ex.ALVOS_PRIMARIOS, "corner_kick"):
            a = a_escanteio if alvo == "corner_kick" or v == "A" else a_ruido
            for rep in range(1 if v == "A" else 10):
                tp = 5000 + (a if rep % 2 else -a)
                # nan_em: n_det = n_gab = 0 -> F1 NaN (com n_gab > 0 o F1 seria 0)
                nd = ng = 0 if (v, alvo, rep) == nan_em else 10000
                linhas.append(_pontos_sinteticos([(1, rep, tp if nd else 0, nd, ng)], variante=v, alvo=alvo))
    return pd.concat(linhas, ignore_index=True)


def test_t11_regra_sementes_dos_dois_lados_do_limiar(cfg):
    # s = a * sqrt(10/9) / 10000; EP5 = s / sqrt(5): a = 210 -> 0,00990; a = 215 -> 0,01014
    assert cfg["experimento"]["ep_max_f1"] == 0.01 and cfg["experimento"]["n_ref_ep"] == 5
    # EP5 nao depende de simulador.n_sementes (a saida da regra), plano 08 §8
    outro = ex._trocar(cfg, simulador__n_sementes=10)
    pd.testing.assert_frame_equal(ex.regra_sementes(_piloto(210), cfg), ex.regra_sementes(_piloto(210), outro))
    baixo = ex.regra_sementes(_piloto(210), cfg)
    alto = ex.regra_sementes(_piloto(215), cfg)
    assert baixo["ep5"].iloc[0] == pytest.approx(0.0210 * np.sqrt(10 / 9) / np.sqrt(5))
    assert (baixo["n_sementes_decidido"] == 5).all() and (alto["n_sementes_decidido"] == 10).all()
    assert not baixo.loc[baixo["alvo"] == "corner_kick", "decide"].any()
    assert not baixo.loc[baixo["alvo"] == "corner_kick", "ep5_ok"].any()   # reportado, nao decide
    assert set(baixo["variante"]) == {"B"}                                  # A fora da regra
    # Semente com F1 NaN: s NaN e a regra cai para 10. As outras 9 tem EP5 0,0094
    # <= 0,01, logo `std(skipna=True)` decidiria 5 (o mutante morre aqui).
    nan = ex.regra_sementes(_piloto(200, nan_em=("B", ex.ALVO_MICRO, 3)), cfg)
    micro = nan.set_index("alvo").loc[ex.ALVO_MICRO]
    assert np.isnan(micro["s"]) and np.isnan(micro["ep5"]) and not micro["ep5_ok"]
    assert (nan["n_sementes_decidido"] == 10).all()
    assert (ex.regra_sementes(_piloto(200), cfg)["n_sementes_decidido"] == 5).all()
    with pytest.raises(ValueError, match="sementes"):
        ex.regra_sementes(_piloto(210).query("rep < 9"), cfg)


# --- --tabelas-figuras: so le os CSV ------------------------------------------------

def test_tabelas_figuras_le_os_csv_e_grava(unidade, cfg, tmp_path):
    """Fumaca sobre unidades reais pequenas (teto e B8 rep 0, R0): as 5
    tabelas e as 2 figuras saem, a Tabela 1 confere com `agregar`, e o
    penalti fica sem F1."""
    pontos = pd.concat([unidade(c, g, "AB", 1, 0, R0) for c in ex.CONDICOES for g in JOGOS]
                       + [unidade("reconstruido", g, "B", 8, 0, R0) for g in JOGOS], ignore_index=True)
    texto = pontos.to_csv(index=False)
    (tmp_path / "pontos.csv").write_bytes(texto.encode())
    ex.selecionar_logo(pontos, cfg).to_csv(tmp_path / "selecao_logo.csv", index=False)
    # o recorte que `rodar_experimento` grava em eps_c.csv
    eps = pontos[(pontos["nivel"] == 1) & (pontos["condicao"] == "reconstruido") & (pontos["ancora"] == "frame")]
    eps.assign(eps_c_m=3.0).to_csv(tmp_path / "eps_c.csv", index=False)
    ex.tabelas_figuras(cfg, tmp_path)
    for k in range(1, 6):
        assert (tmp_path / "tabelas" / f"tabela{k}.csv").exists()
    for k in (1, 2):
        assert (tmp_path / "figuras" / f"figura{k}.png").stat().st_size > 0
    t1p = pd.read_csv(tmp_path / "tabelas" / "tabela1.csv")
    responde = t1p[t1p["papel"] == "responde"]
    assert set(responde["alvo"]) == set(ex.ALVOS_PRIMARIOS) and set(responde["nivel"]) == {8}
    assert set(t1p.loc[t1p["nivel"] == 1, "papel"]) == {"secundario"}
    assert (tmp_path / "pontos.csv").read_bytes() == texto.encode()      # nao reescreve
    t1 = pd.read_csv(tmp_path / "tabelas" / "tabela1.csv").set_index(["variante", "alvo"])
    assert (t1.loc[("AB", ex.ALVO_MICRO), "tp_diag"], t1.loc[("AB", ex.ALVO_MICRO), "n_detectado"]) == (232, 481)
    assert np.isnan(t1.loc[("AB", "penalty"), "f1"]) and t1.loc[("AB", "penalty"), "n_gabarito"] == 1


def test_papel_so_responde_no_recorte_do_plano(cfg):
    """Plano 08 §8, item 6: `responde` SO em `reconstruido`, B, nivel 5 ou 8,
    alvo primario, criterio principal, `frame`, politica principal e lacuna 5
    `com`. Mata: sem o filtro de condicao; sem os de criterio, ancora, politica
    e lacuna 5; "so B8" no lugar de [5, 8]."""
    base = dict(alvo=ex.ALVO_PASSE, condicao="reconstruido", variante="B", nivel=8,
                criterio=cfg["avaliacao"]["criterio_principal"], ancora="frame",
                politica=cfg["posse"]["r_dz_politica"], lacuna5="com")
    casos = [
        ({}, True), ({"nivel": 5}, True), ({"alvo": ex.ALVO_MICRO}, True),
        ({"alvo": ex.ALVO_MICRO, "nivel": 5}, True),
        ({"condicao": "bruto"}, False), ({"condicao": "bruto", "nivel": 5}, False),
        ({"nivel": 3}, False), ({"variante": "A"}, False), ({"variante": "A", "nivel": 5}, False),
        ({"variante": "AB", "nivel": 1}, False), ({"alvo": "corner_kick"}, False),
        ({"alvo": ex.ALVO_PASSE_SEC}, False), ({"criterio": "mills"}, False),
        ({"criterio": "vidal_codina", "nivel": 5}, False), ({"ancora": "annotated_frame"}, False),
        ({"politica": ex.FIXO}, False), ({"lacuna5": "sem"}, False), ({"lacuna5": "sem", "nivel": 5}, False),
    ]
    tabela = pd.DataFrame([{**base, **troca} for troca, _ in casos])
    esperado = ["responde" if r else "secundario" for _, r in casos]
    assert ex.papel(tabela, cfg).tolist() == esperado
    # sem as colunas de ponto (Tabela 1, ja filtrada no principal): so o recorte
    curta = tabela.loc[[0, 1, 4, 6, 7], ["alvo", "condicao", "variante", "nivel"]]
    assert ex.papel(curta, cfg).tolist() == ["responde", "responde", "secundario", "secundario", "secundario"]


def test_curva_eps_c_usa_a_grade_de_bola_parada(cfg):
    """R7 com a emenda: a curva varre exatamente `bola_parada.grade_eps_c_m`,
    no teto, em R0, nos jogos do config. Mata o laco com outra grade."""
    curva = ex.unidades_eps_c(cfg)
    assert [e for e, _, _ in curva] == cfg["bola_parada"]["grade_eps_c_m"] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]
    assert "grade_eps_c_m" not in cfg["experimento"]
    for eps, c, unid in curva:
        assert c["bola_parada"]["eps_c_m"] == eps
        assert c["posse"]["grade_r_pz_m"] == [cfg["experimento"]["r0_m"]]
        assert unid == [(ex.CONDICOES[0], g, ex.VARIANTE_TETO, 1, 0) for g in cfg["dados"]["jogos"]]

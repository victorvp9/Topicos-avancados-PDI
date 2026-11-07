"""Fatia 12: StatsBomb 360 contra o simulador (docs/fatias/12-plano.md §3 e §5)."""

import copy

import numpy as np
import pandas as pd
import pytest

from src import statsbomb360 as s360
from src.config import RAIZ_REPO, carregar_config, carregar_mapeamento
from src.io import statsbomb

APAGAO = RAIZ_REPO / "outputs" / "exploratorio" / "apagao.csv"
BOLA_PARADA = ["throw_in", "free_kick", "goal_kick", "corner_kick", "kickoff"]


@pytest.fixture(scope="module")
def cfg():
    return carregar_config()


def _passe(uid, pass_type=None, tipo="Pass"):
    e = {"id": uid, "type": {"name": tipo}}
    if tipo == "Pass":
        e["pass"] = {} if pass_type is None else {"type": {"name": pass_type}}
    return e


def _ff(n, actor_em=None):
    return [{"teammate": True, "actor": i == actor_em, "keeper": False, "location": [1.0, 1.0]}
            for i in range(n)]


QUADRADO = [10.0, 20.0, 30.0, 20.0, 30.0, 60.0, 10.0, 60.0]       # 20 x 40 = 800 jardas^2


def _sintetico():
    eventos = [_passe("a"), _passe("b", "Recovery"), _passe("c", "Throw-in"), _passe("d", "Corner"),
               _passe("e", "Interception"), _passe("f", tipo="Shot")]
    sessenta = [{"event_uuid": "a", "visible_area": QUADRADO, "freeze_frame": _ff(3, actor_em=0)},
                {"event_uuid": "b", "visible_area": QUADRADO, "freeze_frame": _ff(2)},
                {"event_uuid": "c", "visible_area": QUADRADO, "freeze_frame": []},
                {"event_uuid": "f", "visible_area": QUADRADO, "freeze_frame": _ff(5, actor_em=1)}]
    return eventos, sessenta          # "d" e "e" sem 360; "f" (Shot) fora do escopo


# --- 1: contagens de um JSON sintetico -------------------------------------------

def test_1_json_sintetico_da_as_contagens_certas(cfg):
    tab = statsbomb.tabela_jogo(7, *_sintetico(), cfg)
    assert list(tab.columns) == statsbomb.COLUNAS
    assert tab["event_uuid"].tolist() == ["a", "b", "c", "d", "e"]          # o Shot fica fora
    assert tab["tipo"].tolist() == ["pass", "pass", "throw_in", "corner_kick", "pass"]
    assert tab["tem_360"].tolist() == [True, True, True, False, False]
    r = s360.resumo_copa(tab, ["tipo"], cfg).set_index("tipo")
    assert list(r.index) == s360.tipos(cfg)                                  # os 6, mesmo vazios
    p = r.loc["pass"]
    assert (p["n_eventos"], p["n_sem_360"], p["n_com_360"]) == (3, 1, 2)
    assert p["frac_sem_360"] == pytest.approx(1 / 3)
    assert (p["n_actor_visivel"], p["frac_actor_visivel"]) == (1, 0.5)
    assert p["visiveis_p50"] == 2.5 and p["n_0_visiveis"] == 0
    assert p["area_media"] == pytest.approx(800 / 9600)
    t = r.loc["throw_in"]
    assert (t["n_0_visiveis"], t["frac_0_visiveis"], t["frac_actor_visivel"]) == (1, 1.0, 0.0)
    c = r.loc["corner_kick"]
    assert (c["n_eventos"], c["n_sem_360"], c["frac_sem_360"], c["n_com_360"]) == (1, 1, 1.0, 0)
    # NaN: grupo sem nenhum 360 da percentis e fracoes NaN, sem estourar
    assert np.isnan(c["visiveis_p50"]) and np.isnan(c["frac_actor_visivel"]) and np.isnan(c["area_media"])
    assert r.loc["kickoff", "n_eventos"] == 0 and np.isnan(r.loc["kickoff", "frac_sem_360"])


def test_1_evento_sem_360_entra_no_denominador_e_nao_e_descartado(cfg):
    eventos, sessenta = _sintetico()
    tab = statsbomb.tabela_jogo(7, eventos, sessenta, cfg)
    sem = tab[~tab["tem_360"]]
    assert sem["event_uuid"].tolist() == ["d", "e"]
    assert sem[["n_visiveis", "actor_visivel", "frac_area"]].isna().all().all()
    # tirar o 360 de "a" so move "a" de com para sem 360: o total nao muda
    tab2 = statsbomb.tabela_jogo(7, eventos, sessenta[1:], cfg)
    r1 = s360.resumo_copa(tab, ["tipo"], cfg).set_index("tipo").loc["pass"]
    r2 = s360.resumo_copa(tab2, ["tipo"], cfg).set_index("tipo").loc["pass"]
    assert r2["n_eventos"] == r1["n_eventos"] == 3
    assert (r2["n_sem_360"], r2["frac_sem_360"]) == (2, pytest.approx(2 / 3))
    # o NaN do evento sem 360 nao entra nos percentis nem nas fracoes "com 360"
    assert (r2["n_com_360"], r2["visiveis_p50"], r2["frac_actor_visivel"]) == (1, 2.0, 0.0)


def test_1_event_uuid_repetido_no_360_estoura(cfg):
    eventos, sessenta = _sintetico()
    with pytest.raises(ValueError, match="repetido"):
        statsbomb.tabela_jogo(7, eventos, sessenta + sessenta[:1], cfg)


def test_1_percentis_vem_do_config(cfg):
    c = copy.deepcopy(cfg)
    c["statsbomb360"]["percentis"] = [10, 90]
    r = s360.resumo_copa(statsbomb.tabela_jogo(7, *_sintetico(), c), ["tipo"], c)
    assert {"visiveis_p10", "visiveis_p90", "area_p10"} <= set(r.columns)
    assert "visiveis_p50" not in r.columns


# --- 2: area do poligono -----------------------------------------------------------

def test_2_area_de_poligono_dentro_do_campo():
    assert statsbomb.frac_area(QUADRADO, 120.0, 80.0) == pytest.approx(800 / 9600)


def test_2_area_recortada_de_poligono_que_sai_do_campo():
    # triangulo retangulo (60,40), (180,40), (60,160): area 7200, mas so o
    # retangulo [60,120] x [40,80] fica no campo (a hipotenusa x + y = 220 nao o corta)
    tri = [60.0, 40.0, 180.0, 40.0, 60.0, 160.0]
    assert statsbomb.area_cadarco(np.reshape(tri, (-1, 2))) == pytest.approx(7200.0)
    assert statsbomb.frac_area(tri, 120.0, 80.0) == pytest.approx(2400 / 9600)
    # quadrado que sai pelo canto (0, 0): sobra [0, 20] x [0, 20]
    assert statsbomb.frac_area([-10, -10, 20, -10, 20, 20, -10, 20], 120.0, 80.0) == pytest.approx(400 / 9600)
    # hipotenusa cortando o campo: (100,0), (140,0), (100,40) -> x <= 120 corta;
    # sobra o trapezio (100,0), (120,0), (120,20), (100,40), area 600
    assert statsbomb.frac_area([100, 0, 140, 0, 100, 40], 120.0, 80.0) == pytest.approx(600 / 9600)
    # inteiro fora do campo
    assert statsbomb.frac_area([130, 10, 150, 10, 150, 30], 120.0, 80.0) == 0.0


def test_2_campo_vem_do_config(cfg):
    c = copy.deepcopy(cfg)
    c["statsbomb360"]["campo_jardas"] = [60.0, 40.0]
    a = statsbomb.tabela_jogo(7, *_sintetico(), cfg)["frac_area"].iloc[0]
    b = statsbomb.tabela_jogo(7, *_sintetico(), c)["frac_area"].iloc[0]
    assert a == pytest.approx(800 / 9600) and b == pytest.approx(400 / 2400)   # recorta em y <= 40


def test_2_visible_area_com_nan_ou_degenerada_estoura():
    with pytest.raises(ValueError):
        statsbomb.frac_area([0, 0, np.nan, 1, 1, 1], 120.0, 80.0)
    with pytest.raises(ValueError):
        statsbomb.frac_area([0, 0, 1, 1], 120.0, 80.0)


# --- 3: o tipo vem de pass.type -----------------------------------------------------

@pytest.mark.parametrize("nome, tipo", [("Throw-in", "throw_in"), ("Free Kick", "free_kick"),
                                         ("Goal Kick", "goal_kick"), ("Corner", "corner_kick"),
                                         ("Kick Off", "kickoff"), (None, "pass"), ("Recovery", "pass"),
                                         ("Interception", "pass")])
def test_3_tipo_vem_de_pass_type(cfg, nome, tipo):
    assert statsbomb.tipo_do_passe(_passe("x", nome), cfg["statsbomb360"]) == tipo


def test_3_passe_corrido_exclui_os_5_tipos(cfg):
    eventos = [_passe(str(i), n) for i, n in enumerate(cfg["statsbomb360"]["pass_type_bola_parada"])]
    tab = statsbomb.tabela_jogo(7, eventos + [_passe("z")], [], cfg)
    r = s360.resumo_copa(tab, ["tipo"], cfg).set_index("tipo")["n_eventos"]
    assert r["pass"] == 1 and all(r[t] == 1 for t in BOLA_PARADA)


def test_3_pass_type_desconhecido_estoura(cfg):
    with pytest.raises(ValueError, match="desconhecido"):
        statsbomb.tipo_do_passe(_passe("x", "Penalty"), cfg["statsbomb360"])
    with pytest.raises(ValueError, match="desconhecido"):
        statsbomb.tabela_jogo(7, [_passe("x", "Goal Kick "), _passe("y")], [], cfg)


# --- simulador, sintetico -----------------------------------------------------------

def test_visibilidade_eventos_ancora_executor_e_nan(cfg):
    frames = pd.DataFrame({"frame": np.arange(1, 6)})
    trk = pd.DataFrame({"frame": [1, 1, 2, 3, 3, 4, 4],
                        "player_id": ["p1", "p2", "p1", "p1", "p2", "p1", "p2"],
                        "visible": [True, True, False, True, False, True, True]})
    ev = pd.DataFrame({"type": ["pass", "throw_in", "penalty", "corner_kick", "pass"],
                       "frame": [4, 3, 3, 1, 5], "annotated_frame": [2, 1, 3, 1, 4],
                       "player_id": ["p1", "p2", "p1", None, "p2"]})
    out = s360.visibilidade_eventos(ev, trk, frames, cfg)
    assert out["tipo"].tolist() == ["pass", "throw_in", "corner_kick", "pass"]      # penalti fora
    assert out["quadro"].tolist() == [2, 3, 1, 4]       # passe no anotado, bola parada no `frame`
    assert out["n_visiveis"].tolist() == [0, 1, 2, 2]   # quadro 2: apagao total
    assert out["executor_visivel"].tolist() == [False, False, False, True]
    assert out["executor_anotado"].tolist() == [True, True, False, True]   # NaN: nao anotado, nao visivel


def test_unidades_niveis_e_reps(cfg):
    u = s360.unidades(cfg)
    n_jogos = len(cfg["dados"]["jogos"])
    assert len(u) == (4 * cfg["simulador"]["n_sementes"] + 4) * n_jogos
    assert {r for v, k, r, g in u if v == "A"} == {0}
    c = copy.deepcopy(cfg)
    c["statsbomb360"]["niveis"] = {"B": [8]}
    assert {(v, k) for v, k, r, g in s360.unidades(c)} == {("B", 8)}


def _dados_metrica(cfg):
    return all((cfg["dados"]["raiz"] / f"Sample_Game_{g}").exists() for g in cfg["dados"]["jogos"])


def test_semente_base_do_simulador_e_lida(cfg):
    if not _dados_metrica(cfg):
        pytest.skip("dados da Metrica ausentes")
    from src import run
    base = run._base_leve(cfg, carregar_mapeamento(cfg), [1])
    outra = copy.deepcopy(cfg)
    outra["simulador"]["semente_base"] = cfg["simulador"]["semente_base"] + 1
    a = s360.rodar_unidade("B", 8, 0, 1, cfg, base)[0]
    b = s360.rodar_unidade("B", 8, 0, 1, outra, base)[0]
    assert not np.array_equal(a["n_visiveis"].to_numpy(), b["n_visiveis"].to_numpy())


# --- 4: reproduz a fracao em apagao da Fatia 9 ---------------------------------------

def test_4_simulador_reproduz_apagao_da_fatia_9(cfg):
    if not APAGAO.exists():
        pytest.skip("outputs/exploratorio/apagao.csv ausente: rode --exploratorio para o teste 4")
    if not _dados_metrica(cfg):
        pytest.skip("dados da Metrica ausentes")
    ref = pd.read_csv(APAGAO)
    ref = ref[(ref["frente"] == "base") & (ref["condicao"] == "reconstruido")]
    so = [(v, k, rep, g) for v, k, rep, g in s360.unidades(cfg) if v == "B" and k in (6, 7, 8)]
    sim = s360.rodar_simulador(cfg, carregar_mapeamento(cfg), None, so=so)
    esperado = {}
    for k in (6, 7, 8):
        for alvo, ts in (("passe_principal", ["pass"]), ("bola_parada_micro", BOLA_PARADA)):
            r = ref[(ref["variante"] == "B") & (ref["nivel"] == k) & (ref["alvo"] == alvo)].set_index("estrato")
            s = sim[(sim["nivel"] == k) & sim["tipo"].isin(ts)]
            n_ap, n_tot = int(s["n_apagao"].sum()), int(s["n_eventos"].sum())
            assert n_ap == r.loc["apagao", "n_gabarito"]
            assert n_tot == r.loc["apagao", "n_gabarito"] + r.loc["fora", "n_gabarito"]
            assert n_ap / n_tot == r.loc["apagao", "frac_eventos"]
            esperado[(k, alvo)] = round(n_ap / n_tot, 3)
    # origem-dos-numeros.md, Fatia 9
    assert [esperado[(k, "passe_principal")] for k in (6, 7, 8)] == [0.088, 0.131, 0.158]
    assert [esperado[(k, "bola_parada_micro")] for k in (6, 7, 8)] == [0.335, 0.498, 0.598]


@pytest.mark.parametrize("argv", [["--dados", "idsse", "--statsbomb360"],
                                  ["--dados", "idsse", "--visibilidade-eventos"],
                                  ["--statsbomb360", "--perfil", "provedor_b"]])
def test_cli_recusa_combinacoes(argv):
    from src import run
    with pytest.raises(SystemExit):
        run.main(argv)


def test_visiveis_cond_exclui_o_apagao(cfg):
    # 3 passes em apagao (0 visiveis) e 2 com 7 visiveis: o `_cond` so ve os de 7
    ev = pd.DataFrame({"variante": "B", "nivel": 8, "tipo": "pass", "n_visiveis": [0, 0, 0, 7, 7],
                       "executor_visivel": [False, False, False, True, True], "executor_anotado": True})
    taxas = pd.DataFrame({"variante": ["B"], "nivel": [8], "vis_sem_gk": [1], "teto_sem_gk": [2]})
    r = s360.resumo_simulador(ev, taxas, cfg).set_index("tipo")
    pcs = cfg["statsbomb360"]["percentis"]
    assert all(r.loc["pass", f"visiveis_p{p:02d}_cond"] == 7.0 for p in pcs)
    assert r.loc["pass", "visiveis_p05"] == 0.0 and r.loc["pass", "visiveis_p50"] == 0.0   # incondicional intacto
    assert r.loc["pass", "frac_apagao"] == 0.6
    # tipo sem evento fora do apagao: `_cond` NaN, sem estourar
    assert np.isnan(r.loc["throw_in", "visiveis_p50_cond"])


def test_comparacao_sem_colunas_fixas_do_360(cfg):
    copa = s360.resumo_copa(statsbomb.tabela_jogo(7, *_sintetico(), cfg), ["tipo"], cfg)
    ev = pd.DataFrame({"variante": "B", "nivel": 8, "tipo": "pass", "n_visiveis": [0, 7],
                       "executor_visivel": [False, True], "executor_anotado": True})
    sim = s360.resumo_simulador(ev, pd.DataFrame({"variante": ["B"], "nivel": [8], "vis_sem_gk": [1],
                                                  "teto_sem_gk": [2]}), cfg)
    c = s360.comparar(copa, sim)
    assert not any("actor" in k or "0_visiveis" in k for k in c.columns)
    assert {"copa2022_frac_sem_360", "copa2022_visiveis_p50", "B8_visiveis_p50_cond"} <= set(c.columns)

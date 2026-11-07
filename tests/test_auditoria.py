"""Fatia 10, auditoria EXPLORATORIA no teto: os 6 testes do docs/fatias/10-plano.md §5."""

import copy
import json

import numpy as np
import pandas as pd
import pytest

from src import audit, gabarito, run
from src.config import RAIZ_REPO
from src.events import bola_parada

JOGOS = (1, 2, 3)
TABELA1 = RAIZ_REPO / "outputs" / "experimento" / "tabelas" / "tabela1.csv"


def _cfg_ab1(cfg):
    return run.com_r_pz(cfg, float(cfg["experimento"]["r0_m"]), cfg["posse"]["r_dz_politica"])


_AUD = {}


@pytest.fixture(scope="module")
def auditado(jogo, eventos, cfg, mapeamento):
    """Tabelas da auditoria nos 3 jogos, no ponto AB1 (memorizado)."""
    if not _AUD:
        c = _cfg_ab1(cfg)
        partes, cont = {}, np.zeros(3, "int64")
        for g in JOGOS:
            frames, tracking, periods = jogo(g)
            crus, ev = eventos(g)
            r = audit.auditar_jogo({"frames": frames, "tracking": tracking, "periods": periods, "eventos": ev},
                                   crus, c, mapeamento["separador_subtipo_csv"])
            cont += np.asarray(r.pop("contagem_passe"))
            for k, v in r.items():
                partes.setdefault(k, []).append(v)
        _AUD.update({k: pd.concat(v, ignore_index=True) for k, v in partes.items()})
        _AUD["contagem_passe"] = tuple(int(v) for v in cont)
    return _AUD


# --- 1. exaustivas e exclusivas -------------------------------------------------------

def test_1_categorias_exaustivas_e_exclusivas(auditado, eventos, cfg):
    """Uma categoria por linha, do vocabulario do plano. 481 deteccoes (a micro
    da AB1: nao ha deteccao de penalti) e TODOS os 296 reinicios de bola
    parada do gabarito (295 da micro + o penalti; os 13 `no_dead_ball_before`
    JA estao dentro dos 295)."""
    d, g = auditado["deteccoes_bp"], auditado["gabarito_bp"]
    assert set(d["categoria"]) <= set(audit.CATEGORIAS_DET) and d["categoria"].notna().all()
    assert set(g["categoria"]) <= set(audit.CATEGORIAS_GAB) and g["categoria"].notna().all()
    assert len(d) == d["categoria"].value_counts().sum() == 481
    assert len(g) == g["categoria"].value_counts().sum() == 296
    assert (g["type"] != "penalty").sum() == 295
    n_bp = sum(eventos(k)[1]["type"].isin(cfg["avaliacao"]["grupos"]["bola_parada"]).sum() for k in JOGOS)
    assert len(g) == n_bp


# --- 2. TP = tp_diag da AB1 ----------------------------------------------------------------

def test_2_tp_iguais_ao_tp_diag_da_ab1_por_tipo(auditado):
    tab = audit.conferir_ab1(auditado["deteccoes_bp"], auditado["gabarito_bp"], auditado["contagem_passe"],
                             TABELA1).set_index("alvo")
    t1 = pd.read_csv(TABELA1)
    t1 = t1[(t1["variante"] == "AB") & (t1["nivel"] == 1)].set_index("alvo")
    d = auditado["deteccoes_bp"]
    for tipo in ("corner_kick", "free_kick", "free_kick?", "goal_kick", "kickoff", "penalty", "throw_in"):
        assert ((d["type"] == tipo) & (d["categoria"] == "tp")).sum() == t1.loc[tipo, "tp_diag"], tipo
    assert tuple(tab.loc["bola_parada_micro"]) == (232, 481, 295)
    assert tuple(tab.loc["passe_principal"]) == (2187, 2262, 2650)
    assert len(auditado["passes_fn"]) == 2650 - 2187 and len(auditado["passes_fp"]) == 2262 - 2187


def test_2_conferencia_estoura_se_nao_bater(auditado, tmp_path):
    t1 = pd.read_csv(TABELA1)
    t1.loc[(t1["variante"] == "AB") & (t1["alvo"] == "throw_in"), "tp_diag"] += 1
    t1.to_csv(tmp_path / "t1.csv", index=False)
    with pytest.raises(RuntimeError, match="AB1"):
        audit.conferir_ab1(auditado["deteccoes_bp"], auditado["gabarito_bp"], auditado["contagem_passe"],
                           tmp_path / "t1.csv")


# --- 3 e 6. subcategorias 4a-4d (sintetico) --------------------------------------------------

def test_3_subcategorias_e_desempate_pela_ordem(cfg):
    """Cada linha ativa a evidencia indicada; a primeira regra vence:
    fora/BALL OUT > falta > corrida curta > outro."""
    fora = [True, False, False, False, True, False, False]
    saida = [False, True, False, False, False, False, False]
    falta = [False, False, True, False, True, True, False]
    dur = [0.2, 0.2, 0.2, 0.2, 0.2, 0.5, 5.0]
    sub = audit.subcategoria_sem_reinicio(fora, saida, falta, dur, cfg)
    assert sub.tolist() == ["4a_saida", "4a_saida", "4b_falta", "4c_buraco", "4a_saida", "4b_falta", "4d_outro"]


def test_3_fora_do_campo_sem_margem_e_nan_nunca_fora(cfg):
    a = cfg["auditoria"]
    x = np.array([a["limite_x_m"], np.nextafter(a["limite_x_m"], 99), 0.0, np.nan, 0.0])
    y = np.array([0.0, 0.0, -np.nextafter(a["limite_y_m"], 99), 0.0, a["limite_y_m"]])
    assert audit.fora_do_campo(x, y, cfg).tolist() == [False, True, True, False, False]


def test_3_falta_le_fault_received_e_challenge_com_fault(cfg, mapeamento):
    crus = pd.DataFrame({"metrica_type": ["FAULT RECEIVED", "CHALLENGE", "CHALLENGE", "CHALLENGE", "BALL OUT"],
                         "metrica_subtype": ["", "TACKLE-FAULT-WON", "FAULT+GROUND+LOST", "GROUND-ADVANTAGE-LOST",
                                             ""]})
    assert audit.e_falta(crus, cfg, mapeamento["separador_subtipo_csv"]).tolist() == [True, True, True, False,
                                                                                      False]
    assert audit.e_saida(crus, cfg).tolist() == [False] * 4 + [True]


def _caso_sintetico(x_antes=50.0, f_falta=40 - 37, dur=0.8):
    """Jogo de 100 quadros, bola morta em 40..59 (a corrida que gera a deteccao
    do quadro 60), ultima posicao viva `(x_antes, 0)`, um `FAULT RECEIVED`
    cru no quadro `f_falta` e uma deteccao com `dur_morta_s = dur`."""
    q = np.arange(1, 101)
    vivo = ~((q >= 40) & (q <= 59))
    frames = pd.DataFrame({"game": 1, "period": 1, "frame": q, "t": q / 25,
                           "ball_x": np.where(vivo, x_antes, np.nan), "ball_y": np.where(vivo, 0.0, np.nan),
                           "ball_live": vivo})
    _, _, ids = bola_parada.corridas_mortas(vivo)
    det = pd.DataFrame({"game": [1], "frame": [60], "type": ["free_kick"], "player_id": ["p"], "via": ["reserva_1"],
                        "motivo_reserva1": ["confirmado"], "dur_morta_s": [dur], "dead_run_id": [int(ids[0])]})
    crus = pd.DataFrame({"row": [0], "annotated_frame": [f_falta], "metrica_type": ["FAULT RECEIVED"],
                         "metrica_subtype": [""], "player_id": ["p"]})
    gab = pd.DataFrame({"frame": pd.Series([], dtype="int64"), "type": pd.Series([], dtype=str),
                        "player_id": pd.Series([], dtype=str)})
    return det, gab, frames, crus


def _categoria(cfg, mapeamento, limiares=None, **troca):
    c = copy.deepcopy(cfg)
    c["auditoria"].update(limiares or {})
    det, gab, frames, crus = _caso_sintetico(**troca)
    out = audit.categorizar_deteccoes(det, gab, np.zeros(1, bool), frames, crus, c, mapeamento["separador_subtipo_csv"])
    return out["categoria"].iloc[0]


def test_3_caso_sintetico_por_subcategoria(cfg, mapeamento):
    """Falta 37 quadros (1,48 s) antes do inicio da corrida morta e corrida de
    0,8 s: 4b (a falta vence o buraco). Falta 5,6 s antes: 4c. Corrida longa: 4d.
    Bola fora antes: 4a (vence a falta)."""
    assert _categoria(cfg, mapeamento) == "4b_falta"
    assert _categoria(cfg, mapeamento, f_falta=-100) == "4c_buraco"
    assert _categoria(cfg, mapeamento, f_falta=-100, dur=3.0) == "4d_outro"
    assert _categoria(cfg, mapeamento, x_antes=53.0) == "4a_saida"


def test_6_cada_limiar_do_config_muda_a_categoria(cfg, mapeamento):
    """Os quatro limiares da §3.1 nao sao ignorados."""
    assert _categoria(cfg, mapeamento, limiares={"janela_evento_cru_s": 1.0}) == "4c_buraco"
    assert _categoria(cfg, mapeamento, f_falta=-100, limiares={"corrida_curta_s": 0.5}) == "4d_outro"
    assert _categoria(cfg, mapeamento, limiares={"limite_x_m": 49.0}) == "4a_saida"
    det, gab, frames, crus = _caso_sintetico(x_antes=0.0)
    frames.loc[frames["ball_live"], "ball_y"] = 30.0
    c = copy.deepcopy(cfg)
    base = audit.categorizar_deteccoes(det, gab, np.zeros(1, bool), frames, crus, c, "-")["categoria"].iloc[0]
    c["auditoria"]["limite_y_m"] = 29.0
    assert base == "4b_falta"
    assert audit.categorizar_deteccoes(det, gab, np.zeros(1, bool), frames, crus, c, "-")["categoria"].iloc[0] == \
        "4a_saida"


# --- 4. nenhum evento descartado; os 13 na categoria 5 -----------------------------------------

def test_4_os_13_sem_transicao_na_categoria_5(auditado):
    g = auditado["gabarito_bp"]
    cinco = g[g["categoria"] == "5_sem_transicao"]
    assert len(cinco) == 13 and cinco["no_dead_ball_before"].all()
    assert g.loc[g["no_dead_ball_before"], "categoria"].eq("5_sem_transicao").all()


def test_4_tp_pelo_gabarito_e_pelas_deteccoes_coincidem(auditado):
    g, d = auditado["gabarito_bp"], auditado["deteccoes_bp"]
    assert (g["categoria"] == "1_tp").sum() == (d["categoria"] == "tp").sum() == g["casou_na_diagonal"].sum()


# --- 5. amostra deterministica, semente no manifesto ----------------------------------------------

def test_5_amostra_deterministica():
    casos = pd.DataFrame({"grupo": ["a"] * 30 + ["b"] * 3, "frame": range(33)})
    s1 = audit.amostrar(casos, "grupo", 10, 7)
    assert s1.equals(audit.amostrar(casos, "grupo", 10, 7))
    assert not s1.equals(audit.amostrar(casos, "grupo", 10, 8))
    assert s1.groupby("grupo").size().to_dict() == {"a": 10, "b": 3}


def test_5_semente_no_manifesto_e_pngs_repetiveis(cfg, mapeamento, tmp_path):
    """`rodar_auditoria` recortado (jogo 1, 1 caso por categoria), com uma
    tabela1 de referencia do proprio jogo 1: o manifesto traz a semente do
    config, e duas execucoes sorteiam os mesmos casos."""
    c = copy.deepcopy(cfg)
    c["dados"]["jogos"] = [1]
    c["auditoria"]["amostra_por_categoria"] = 1
    base = run._base_leve(_cfg_ab1(c), mapeamento, [1])
    crus = gabarito.carregar_eventos_crus(1, c, mapeamento)
    r = audit.auditar_jogo(base[1], crus, _cfg_ab1(c), mapeamento["separador_subtipo_csv"])
    t1 = pd.read_csv(TABELA1)
    ab1 = t1[(t1["variante"] == "AB") & (t1["nivel"] == 1)].copy()
    d, g = r["deteccoes_bp"], r["gabarito_bp"]
    for i, alvo in ab1["alvo"].items():
        if alvo == "passe_principal":
            v = r["contagem_passe"]
        elif alvo == "bola_parada_micro":
            v = (int(((d["type"] != "penalty") & (d["categoria"] == "tp")).sum()), int((d["type"] != "penalty").sum()),
                 int((g["type"] != "penalty").sum()))
        else:
            v = (int(((d["type"] == alvo) & (d["categoria"] == "tp")).sum()), int((d["type"] == alvo).sum()),
                 int((g["type"] == alvo).sum()))
        ab1.loc[i, ["tp_diag", "n_detectado", "n_gabarito"]] = v
    ab1.to_csv(tmp_path / "t1.csv", index=False)
    amostras = []
    for k in (1, 2):
        out = tmp_path / f"saida{k}"
        audit.rodar_auditoria(c, mapeamento, RAIZ_REPO / "config.yaml", out, tmp_path / "t1.csv")
        m = json.loads((out / "manifesto.json").read_text(encoding="utf-8"))
        assert m["semente_amostra"] == cfg["auditoria"]["semente"] and m["n_png"] == len(list((out / "casos").glob("*.png")))
        amostras.append(pd.read_csv(out / "amostra.csv"))
    pd.testing.assert_frame_equal(amostras[0], amostras[1])

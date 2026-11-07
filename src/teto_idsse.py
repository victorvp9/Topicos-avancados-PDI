"""Teto no IDSSE e teste das hipoteses H1-H3 (Fatia 11b).

Plano normativo: docs/fatias/11-plano.md §4a; hipoteses congeladas em
docs/fatias/10-hipoteses.md; criterio principal do IDSSE = `vidal_codina`
(decisoes.md 2026-11-07, `config.yaml:idsse.criterio_principal`).

Nada de detector novo: cada jogo passa pela MESMA unidade do experimento
(`experiment.rodar_unidade`, nivel 1 = teto, `R0`, condicao principal), com o
config da tag `final` e so duas trocas: o criterio principal do IDSSE e a
grade de `R_pz` reduzida a `R0`. A H2 e a mesma unidade com
`exploratorio.supressao_exige_executor` ligada; a curva de `eps_c` (R7) e a
mesma unidade em cada valor de `bola_parada.grade_eps_c_m`. A H3 (precisao
por via) e as conferencias refazem a deteccao no MESMO cfg e tracking e
conferem que o micro bate com o da unidade.

Saidas em `outputs/idsse/teto/`: `pontos.csv`, `pontos_h2.csv`, `eps_c.csv`,
`tabela.csv`, `via.csv`, `mortos.csv`, `hipoteses.csv`.

Com `perfil` (`--teto-idsse --perfil provedor_b`): sensibilidade EXPLORATORIA
com `idsse.perfil_<perfil>` (R0 e `eps` trocados). So a unidade base e o
diagnostico de via; sem H2, sem curva de `eps_c`, sem hipoteses. Saida em
`outputs/idsse/teto_<perfil>/`, toda tabela com `rotulo = EXPLORATORIO`.
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd

from src import evaluate, experiment as ex, possession, run
from src.config import RAIZ_REPO
from src.events import bola_parada, hierarquia
from src.io import idsse, schema


def cfg_teto(cfg: dict, h2: bool = False) -> dict:
    """Copia do cfg do teto no IDSSE: grade de `R_pz` = [R0], criterio principal
    = `idsse.criterio_principal`, todas as chaves `exploratorio` lidas pela
    unidade desligadas, salvo `supressao_exige_executor = h2`. O cfg de
    entrada (e o principal da Metrica) nao muda."""
    c = ex._trocar(cfg, posse__grade_r_pz_m=[cfg["experimento"]["r0_m"]])
    c["avaliacao"]["criterio_principal"] = cfg["idsse"]["criterio_principal"]
    for k in ex.EXPLORATORIO_LIDO:
        c["exploratorio"][k] = False
    c["exploratorio"]["supressao_exige_executor"] = bool(h2)
    return c


def aplicar_perfil(cfg: dict, perfil: str) -> dict:
    """Copia do cfg com `idsse.perfil_<perfil>`: `r_pz_m` vira o R0 (e o
    `posse.r_pz_m`), `eps_s_m` e `eps_v_ms` vao para `posse`."""
    p = cfg["idsse"]["perfil_" + perfil]
    return ex._trocar(cfg, experimento__r0_m=p["r_pz_m"], posse__r_pz_m=p["r_pz_m"],
                      posse__eps_s_m=p["eps_s_m"], posse__eps_v_ms=p["eps_v_ms"])


def _sel(pontos: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Ancora `frame`, politica principal, lacuna 5 `com` (o ponto da tag final)."""
    return pontos[(pontos["ancora"] == "frame") & (pontos["politica"] == cfg["posse"]["r_dz_politica"])
                  & (pontos["lacuna5"] == "com")]


def _casamento_bp(ev: pd.DataFrame, det_c: pd.DataFrame, c: dict):
    """Casamento de bola parada no criterio principal (o de `evaluate.avaliar`,
    ancora `frame`). Devolve (gab, i_gab, i_det, diag)."""
    eixos = c["avaliacao"]["criterios"][c["avaliacao"]["criterio_principal"]]
    grupo_de = evaluate.grupo_por_tipo(c)
    g = ev[ev["type"].isin(c["avaliacao"]["grupos"]["bola_parada"])].reset_index(drop=True)
    g = g.assign(grupo=g["type"].map(grupo_de), t=g["frame"] / c["tracking"]["fps"])
    d = det_c.assign(grupo=det_c["type"].map(grupo_de))
    i_gab, i_det = evaluate.casar(g, d, eixos["janela_s"], eixos["casa_tipo"], eixos["casa_jogador"])
    diag = g["type"].to_numpy()[i_gab] == d["type"].to_numpy()[i_det]
    return g, i_gab, i_det, diag


def diagnostico_jogo(game: int, base: dict, ev_diag: pd.DataFrame, c: dict) -> tuple:
    """(via, mortos, conf) de um jogo, com a deteccao refeita no cfg `c` e no
    mesmo tracking da unidade (`experiment.tracking_da_condicao`, nivel 1).

    `via`: por via, deteccoes de bola parada sem penalti e o `tp_diag` delas
    (H3). `mortos`: as bolas paradas que ficaram em quadro morto com
    `no_dead_ball_before` (lacuna D1), com o casamento e a deteccao mais
    proxima. `conf`: `tp_micro` (para conferir com a unidade) e `tp_sem_jogador`
    (pares casados com `player_id` vazio ou NaN; tem de ser 0)."""
    d = base[game]
    trk = ex.tracking_da_condicao(d["tracking"], d["tracking"], ex.CONDICOES[0])
    cr = run.com_r_pz(c, c["experimento"]["r0_m"], c["posse"]["r_dz_politica"])
    p1 = possession.calcular(d["frames"], trk, cr)
    b = {game: {"frames": d["frames"], "tracking": trk, "periods": d["periods"], "perdas": p1["perdas"],
                "ganhos": p1["ganhos"], "control": p1["control"]}}
    det = run.detectar_jogos(b, cr, [game])
    det_c = bola_parada.para_casador(det)
    g, i_gab, i_det, diag = _casamento_bp(d["eventos"], det_c, cr)
    acerto_d = np.zeros(len(det_c), bool)
    acerto_d[i_det[diag]] = True
    acerto_g = np.zeros(len(g), bool)
    acerto_g[i_gab[diag]] = True
    # TODO(divida): a H3 diz "precisao das deteccoes pela via, bola parada micro"
    # sem dar a populacao. Uso a mesma do alvo `bola_parada_micro` (todo tipo de
    # deteccao menos `penalty`, logo `free_kick?` entra), para que a soma das
    # vias feche com o `tp_diag` micro da unidade (conferido abaixo).
    micro = (det_c["type"] != "penalty").to_numpy()
    vias = det["via"].to_numpy()
    via = pd.DataFrame([{"game": game, "via": v, "n_detectado": int((micro & (vias == v)).sum()),
                         "tp_diag": int((micro & (vias == v) & acerto_d).sum())} for v in hierarquia.VIAS])
    jog_g, jog_d = g["player_id"].to_numpy()[i_gab], det_c["player_id"].to_numpy()[i_det]
    vazio = pd.isna(jog_g) | (jog_g == "") | pd.isna(jog_d) | (jog_d == "")
    conf = {"game": game, "tp_micro": int((acerto_d & micro).sum()), "tp_sem_jogador": int(vazio.sum()),
            "n_det_frame_nan": int(det_c["t"].isna().sum())}
    em_morto = ev_diag.set_index("source_rows")["anotado_em_morto"]
    alvo = (g["no_dead_ball_before"] & g["source_rows"].map(em_morto).fillna(False).astype(bool)).to_numpy()
    fps = c["tracking"]["fps"]
    linhas = []
    for k in np.flatnonzero(alvo):
        dt = (det_c["frame"].to_numpy() - g["frame"].iloc[k]) / fps
        j = int(np.argmin(np.abs(dt))) if dt.size else -1
        par = i_det[i_gab == k]
        linhas.append({"game": game, "type": g["type"].iloc[k], "frame": int(g["frame"].iloc[k]),
                       "player_id": g["player_id"].iloc[k],
                       "ball_live_no_quadro": bool(d["frames"]["ball_live"].to_numpy()[g["frame"].iloc[k] - 1]),
                       "casado": bool(par.size), "acerto_diag": bool(acerto_g[k]),
                       "tipo_casado": det_c["type"].iloc[par[0]] if par.size else "",
                       "det_mais_proxima_dt_s": float(dt[j]) if j >= 0 else np.nan,
                       "det_mais_proxima_tipo": det_c["type"].iloc[j] if j >= 0 else ""})
    return via, pd.DataFrame(linhas), conf


def conferir_gabarito(pontos: pd.DataFrame, ev: pd.DataFrame, c: dict) -> None:
    """Nenhum evento do gabarito descartado: `n_gabarito` de cada alvo (ancora
    `frame`) e a contagem do gabarito. Estoura se nao bater."""
    tipos_bp = c["avaliacao"]["grupos"]["bola_parada"]
    esperado = {t: int((ev["type"] == t).sum()) for t in tipos_bp}
    esperado[ex.ALVO_MICRO] = sum(v for t, v in esperado.items() if t != "penalty")
    esperado[ex.ALVO_PASSE] = int((ev["type"] == "pass").sum())
    esperado[ex.ALVO_PASSE_SEC] = len(evaluate.gabarito_secundario(ev, c))
    sub = pontos[pontos["ancora"] == "frame"]
    obtido = sub.groupby("alvo")["n_gabarito"].agg(["min", "max"])
    for alvo, n in esperado.items():
        if not (obtido.loc[alvo, "min"] == obtido.loc[alvo, "max"] == n):
            raise RuntimeError("n_gabarito de {} = {} != gabarito {}".format(alvo, obtido.loc[alvo].tolist(), n))


def hipoteses(base: pd.DataFrame, h2: pd.DataFrame, via: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """H1-H3 (10-hipoteses.md), no criterio principal do IDSSE, ancora `frame`,
    politica principal, lacuna 5 com. Limiares em `config.yaml:idsse.hipoteses`.
    NaN nunca passa."""
    hip = cfg["idsse"]["hipoteses"]
    princ = cfg["idsse"]["criterio_principal"]
    pb = _sel(base, cfg)
    pb = pb[pb["criterio"] == princ]
    ph = _sel(h2, cfg)
    ph = ph[ph["criterio"] == princ]
    micro = ex.agregar(pb[pb["alvo"] == ex.ALVO_MICRO], ["alvo"])
    p_micro = float(micro["precisao"].iloc[0])
    linhas = [{"hipotese": "H1", "medida": "precisao_micro", "valor": p_micro,
               "limiar": hip["h1_precisao_micro_min"], "passa": bool(p_micro >= hip["h1_precisao_micro_min"])}]
    f1 = {}
    for nome, p in (("base", pb), ("h2", ph)):
        pp = p[p["alvo"] == ex.ALVO_PASSE]
        f1[nome] = (ex.agregar(pp, ["alvo"])["f1"].iloc[0], ex.agregar(pp, ["jogo"]).set_index("jogo")["f1"])
    d_agg = float(f1["h2"][0] - f1["base"][0])
    d_jogo = f1["h2"][1] - f1["base"][1]
    n_pos = int((d_jogo > 0).sum())
    for g, v in d_jogo.items():
        linhas.append({"hipotese": "H2", "medida": "delta_f1_passe_jogo_{}".format(g), "valor": float(v),
                       "limiar": 0.0, "passa": bool(v > 0)})
    linhas.append({"hipotese": "H2", "medida": "delta_f1_passe_agregado", "valor": d_agg, "limiar": 0.0,
                   "passa": bool(d_agg > 0)})
    linhas.append({"hipotese": "H2", "medida": "jogos_com_delta_pos", "valor": n_pos,
                   "limiar": hip["h2_min_jogos"], "passa": bool(d_agg > 0 and n_pos >= hip["h2_min_jogos"])})
    v = via.groupby("via")[["n_detectado", "tp_diag"]].sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        prec = (v["tp_diag"] / v["n_detectado"].where(v["n_detectado"] > 0)).reindex(list(hierarquia.VIAS))
    for nome, valor in prec.items():
        linhas.append({"hipotese": "H3", "medida": "precisao_via_" + nome, "valor": float(valor),
                       "limiar": np.nan, "passa": np.nan})
    padrao = prec["padrao"]
    linhas.append({"hipotese": "H3", "medida": "padrao_maior_que_reserva_1_e_3", "valor": float(padrao),
                   "limiar": np.nan,
                   "passa": bool(padrao > prec["reserva_1"] and padrao > prec["reserva_3"])})
    linhas.append({"hipotese": "H3", "medida": "padrao_maior_de_todas", "valor": float(padrao), "limiar": np.nan,
                   "passa": bool(all(padrao > prec[o] for o in hierarquia.VIAS if o != "padrao"))})
    return pd.DataFrame(linhas)


def _gravar_perfil(pontos, via, morto, c0, saida, perfil, parede) -> dict:
    """Tabela por tipo e via da sensibilidade EXPLORATORIA, rotuladas."""
    ex.conferir_n_gabarito(pontos)
    tabela = ex.agregar(_sel(pontos, c0), ["criterio", "alvo"])
    rot = c0["idsse"]["perfil_" + perfil]["rotulo"]
    saidas = {n: t.assign(rotulo=rot) for n, t in (("pontos", pontos), ("tabela", tabela), ("via", via),
                                                  ("mortos", morto))}
    for nome, tab in saidas.items():
        ex._gravar(tab, saida / (nome + ".csv"))
    print("=" * 78)
    print("{}: teto IDSSE, perfil {} (R0 = {} m, eps_s = {} m, eps_v = {} m/s); principal = {}".format(
        rot, perfil, c0["experimento"]["r0_m"], c0["posse"]["eps_s_m"], c0["posse"]["eps_v_ms"],
        c0["avaliacao"]["criterio_principal"]))
    col = ["criterio", "alvo", "n_gabarito", "n_detectado", "tp_diag", "precisao", "revocacao", "f1",
           "f1_jogo_min", "f1_jogo_max"]
    print(tabela[col].to_string(index=False, float_format="{:.3f}".format))
    v = via.groupby("via")[["n_detectado", "tp_diag"]].sum()
    print(v.assign(precisao=v["tp_diag"] / v["n_detectado"].where(v["n_detectado"] > 0)).to_string())
    print("parede total: {:.1f} s".format(parede))
    return {**saidas, "parede_s": parede}


def rodar_teto_idsse(cfg: dict, saida: Path = None, pasta_cache=None, perfil: str = None) -> dict:
    """`--teto-idsse`: os jogos de `idsse.jogos`, um por vez na memoria. Grava os
    CSV do docstring do modulo, imprime o resumo e devolve as tabelas. Com
    `perfil`, a sensibilidade EXPLORATORIA do docstring do modulo."""
    t0 = time.perf_counter()
    pasta = "teto" if perfil is None else "teto_" + perfil
    saida = RAIZ_REPO / "outputs" / "idsse" / pasta if saida is None else Path(saida)
    cfg_p = cfg if perfil is None else aplicar_perfil(cfg, perfil)
    c0, c_h2 = cfg_teto(cfg_p), cfg_teto(cfg_p, h2=True)
    unidade = (ex.CONDICOES[0], ex.VARIANTE_TETO, 1, 0)
    pontos, pontos_h2, curva, vias, mortos, confs = [], [], [], [], [], []
    for game in range(1, len(cfg["idsse"]["jogos"]) + 1):
        j = idsse.carregar_jogo(game, cfg, pasta_cache)
        ev = j["eventos"][list(schema.EVENTS)]
        base = {game: {"frames": j["frames"], "tracking": j["tracking"], "periods": j["periods"], "eventos": ev}}
        u = lambda c: ex.rodar_unidade(game, unidade[1], unidade[2], unidade[3], unidade[0], c, base)  # noqa: E731
        p = u(c0)
        conferir_gabarito(p, ev, c0)
        pontos.append(p)
        if perfil is None:
            pontos_h2.append(u(c_h2))
        for eps in (cfg["bola_parada"]["grade_eps_c_m"] if perfil is None else []):
            pe = u(ex._trocar(c0, bola_parada__eps_c_m=eps))
            curva.append(pe[(pe["ancora"] == "frame") & pe["alvo"].isin(["corner_kick", ex.ALVO_MICRO])]
                         .assign(eps_c_m=eps))
        via, morto, conf = diagnostico_jogo(game, base, j["eventos"], c0)
        tp_unidade = _sel(p, c0)
        tp_unidade = int(tp_unidade.loc[(tp_unidade["criterio"] == c0["avaliacao"]["criterio_principal"])
                                        & (tp_unidade["alvo"] == ex.ALVO_MICRO), "tp_diag"].iloc[0])
        if conf["tp_micro"] != tp_unidade:
            raise RuntimeError("jogo {}: tp micro do diagnostico {} != unidade {}".format(
                game, conf["tp_micro"], tp_unidade))
        if conf["tp_sem_jogador"] or conf["n_det_frame_nan"]:
            raise RuntimeError("jogo {}: acerto com jogador vazio/NaN ou deteccao sem t: {}".format(game, conf))
        vias.append(via)
        mortos.append(morto)
        confs.append(conf)
        print("jogo {} ({}) pronto: {:.1f} s".format(game, j["match_id"], time.perf_counter() - t0))
        del j, base, ev
    pontos = pd.concat(pontos, ignore_index=True)
    via, morto = pd.concat(vias, ignore_index=True), pd.concat(mortos, ignore_index=True)
    if perfil is not None:
        return _gravar_perfil(pontos, via, morto, c0, saida, perfil, time.perf_counter() - t0)
    pontos_h2, curva = pd.concat(pontos_h2, ignore_index=True), pd.concat(curva, ignore_index=True)
    ex.conferir_n_gabarito(pd.concat([pontos, pontos_h2, curva.drop(columns="eps_c_m")], ignore_index=True))
    sel = _sel(pontos, c0)
    tabela = ex.agregar(sel, ["criterio", "alvo"])
    r9 = ex.agregar(sel[sel["criterio"] == c0["avaliacao"]["criterio_principal"]], ["alvo"])
    eps = ex.agregar(curva[(curva["lacuna5"] == "com")
                           & (curva["politica"] == c0["posse"]["r_dz_politica"])], ["eps_c_m", "criterio", "alvo"])
    hip = hipoteses(pontos, pontos_h2, via, cfg)
    for nome, tab in (("pontos", pontos), ("pontos_h2", pontos_h2), ("eps_c", curva), ("tabela", tabela),
                      ("via", via), ("mortos", morto), ("hipoteses", hip)):
        ex._gravar(tab, saida / (nome + ".csv"))
    parede = time.perf_counter() - t0

    print("=" * 78)
    print("TETO IDSSE (AB1, R0, ancora frame, {}, lacuna 5 com); principal = {}".format(
        c0["posse"]["r_dz_politica"], c0["avaliacao"]["criterio_principal"]))
    col = ["criterio", "alvo", "n_gabarito", "n_detectado", "tp_diag", "precisao", "revocacao", "f1",
           "f1_jogo_min", "f1_jogo_max"]
    print(tabela[col].to_string(index=False, float_format="{:.3f}".format))
    print("-- hipoteses")
    print(hip.to_string(index=False, float_format="{:.4f}".format))
    print("-- R9 (criterio principal)")
    r9c = ["alvo"] + [k for k in ex.DECOMP if k in r9.columns and r9[k].notna().any() and r9[k].sum() > 0]
    print(r9[r9c].to_string(index=False, float_format="{:.0f}".format))
    print("-- curva eps_c (criterio principal)")
    e = eps[eps["criterio"] == c0["avaliacao"]["criterio_principal"]]
    print(e[["eps_c_m", "alvo", "n_detectado", "tp_diag", "precisao", "revocacao", "f1"]]
          .to_string(index=False, float_format="{:.3f}".format))
    print("-- bolas paradas em quadro morto com no_dead_ball_before")
    print(morto.to_string(index=False) if len(morto) else "  nenhuma")
    print("-- conferencias: n_gabarito = gabarito em todo alvo e em todas as rodadas; "
          "tp micro do diagnostico = unidade; 0 acertos com jogador vazio/NaN")
    print("parede total: {:.1f} s".format(parede))
    return {"pontos": pontos, "pontos_h2": pontos_h2, "eps_c": curva, "tabela": tabela, "via": via,
            "mortos": morto, "hipoteses": hip, "r9": r9, "curva": eps, "parede_s": parede}

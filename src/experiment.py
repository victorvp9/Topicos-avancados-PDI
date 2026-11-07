"""A maquina do experimento (Fatia 8). Plano normativo: docs/fatias/08-plano.md.

Uma UNIDADE e uma degradacao `(condicao, jogo, variante, nivel, rep)`: degrada
o teto (`broadcast.degradar`), reconstroi ou nao (`reconstruct.reconstruir`),
e para cada `R_pz` da grade e cada politica de `R_dz` aplicavel roda posse ->
bola parada -> passes -> avaliacao com o codigo das Fatias 3 a 5, sem
reimplementar o detector. O nivel 1 e o teto: sem semente, uma vez por jogo,
compartilhado pelas variantes (`variante = "AB"`, `rep = 0`).

`pontos` (a tabela que sai de `rodar_unidade`, de `pontos.csv` e do cache) tem
uma linha por `(unidade, r_pz, politica, lacuna5, criterio, ancora, alvo)`:

  unidade     `condicao, jogo, variante, nivel, rep, semente_efetiva`
              (`"nenhuma"` no nivel 1), `taxa_todos`, `taxa_sem_gk` (linhas
              visiveis / linhas presentes, R4), `n_dist`, `n_dist_igual_grade`
              (diagnostico (h) da Fatia 7: distancias jogador-bola, no tracking
              que o detector ve, exatamente iguais a um valor da grade de `R_pz`)
  ponto       `r_pz` (m), `politica` (de `R_dz`), `lacuna5` (`com`/`sem`),
              `criterio`, `ancora` (`annotated_frame` so no nivel 1 em R0),
              `alvo` (os tipos de bola parada, `bola_parada_micro` sem
              penalti, `passe_principal`, `passe_secundario`)
  contagens   `n_gabarito`, `n_detectado`, `tp_diag`, `tp`
  R9          so nas linhas do criterio principal com ancora `frame` (NaN nas
              demais): `motivo_*` e `via_*` (deteccoes de bola parada daquele
              tipo), `fn_causa_a..d` (passe principal, `run.decompor_fn`),
              `gab_exec_*` e `fn_exec_*` (eventos e FN pelo estado do executor
              no quadro anotado: `visivel`, `imputado`, `ausente`)

Nunca se faz media de F1: `agregar` soma as contagens e so depois divide (R5).
"""

import copy
import hashlib
import io
import json
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

from src import broadcast, evaluate, possession, reconstruct, run
from src.config import RAIZ_REPO
from src.events import bola_parada, hierarquia, passes as passes_mod
from src.io import idsse, schema

CONDICOES = ("reconstruido", "bruto")
VARIANTE_TETO = "AB"
SEM_SEMENTE = "nenhuma"
FIXO = "fixo_1m"
ALVO_MICRO = "bola_parada_micro"
ALVO_PASSE = "passe_principal"
ALVO_PASSE_SEC = "passe_secundario"
ALVOS_PRIMARIOS = (ALVO_PASSE, ALVO_MICRO)
ESTADOS = ("visivel", "imputado", "ausente")

CHAVES_UNIDADE = ["condicao", "jogo", "variante", "nivel", "rep"]
CHAVES_PONTO = CHAVES_UNIDADE + ["r_pz", "politica", "lacuna5", "criterio", "ancora", "alvo"]
CONTAGENS = ["n_gabarito", "n_detectado", "tp_diag", "tp"]
DECOMP = ([f"motivo_{m}" for m in bola_parada.MOTIVOS] + [f"via_{v}" for v in hierarquia.VIAS]
          + [f"fn_causa_{c}" for c in "abcd"]
          + [f"gab_exec_{e}" for e in ESTADOS] + [f"fn_exec_{e}" for e in ESTADOS])
SOMAVEIS = CONTAGENS + DECOMP + ["n_dist", "n_dist_igual_grade"]
# `agregar` soma sobre estas chaves; toda outra chave ausente de `por` tem de
# ter um valor so.
SOMA_SOBRE = ("jogo", "rep")
# Fatia 9, frente A (EXPLORATORIO): por estrato do quadro de referencia,
# eventos do gabarito e seus acertos (revocacao) e deteccoes e seus acertos
# (precisao). So com `exploratorio.estratos_apagao`; nunca entra em `SOMAVEIS`.
ESTRATOS = ("apagao", "fora")
COLUNAS_ESTRATO = [f"{e}_{c}" for e in ESTRATOS for c in ("n_gabarito", "tp_gab", "n_detectado", "tp_det")]


# --- uma unidade ---------------------------------------------------------------

def _prf(tp, n_det, n_gab):
    """P, R, F1 vetorizados das contagens. P e R NaN com denominador 0. F1 =
    `2 tp / (n_det + n_gab)`, UMA divisao de inteiros (plano 08 §8, item 2):
    F1 iguais em fracao saem iguais em ponto flutuante; NaN so se
    `n_det + n_gab = 0`. Difere de `evaluate._f1` so quando um de P e R e NaN
    (ali o F1 e NaN; aqui, com n_det = 0 e n_gab > 0, e 0)."""
    tp, n_det, n_gab = (np.asarray(v, dtype="float64") for v in (tp, n_det, n_gab))
    with np.errstate(invalid="ignore", divide="ignore"):
        p = np.where(n_det > 0, tp / n_det, np.nan)
        r = np.where(n_gab > 0, tp / n_gab, np.nan)
        soma = n_det + n_gab
        f1 = np.where(soma > 0, 2 * tp / np.where(soma > 0, soma, 1), np.nan)
    return p, r, f1


def _estado_executor(gab: pd.DataFrame, det: pd.DataFrame, tracking: pd.DataFrame,
                     frames: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Por evento de `gab` (tipos dos grupos): `type`, `estado` do executor no
    `annotated_frame` em `tracking` (`run.executor_bola`: sem linha = ausente,
    `visible = False` = imputado) e `fn` (nao casou na diagonal no criterio
    principal, ancora `frame`, o mesmo casamento de `evaluate.avaliar`)."""
    principal = cfg["avaliacao"]["criterio_principal"]
    eixos = cfg["avaliacao"]["criterios"][principal]
    grupo_de = evaluate.grupo_por_tipo(cfg)
    g = gab[gab["type"].isin(grupo_de)].reset_index(drop=True)
    g = g.assign(grupo=g["type"].map(grupo_de), t=g["frame"] / cfg["tracking"]["fps"])
    d = det.reset_index(drop=True)
    d = d.assign(grupo=d["type"].map(grupo_de))
    i_gab, i_det = evaluate.casar(g, d, eixos["janela_s"], eixos["casa_tipo"], eixos["casa_jogador"])
    acerto = np.zeros(len(g), bool)
    acerto[i_gab] = g["type"].to_numpy()[i_gab] == d["type"].to_numpy()[i_det]
    ex = run.executor_bola(g, tracking, frames)
    estado = np.select([ex["sem_linha"].to_numpy(), ex["imputada"].to_numpy()],
                       ["ausente", "imputado"], "visivel")
    return pd.DataFrame({"type": g["type"].to_numpy(), "estado": estado, "fn": ~acerto})


def _contar_estado(est: pd.DataFrame, tipo: str) -> dict:
    sub = est[est["type"] == tipo] if tipo is not None else est
    return {**{f"gab_exec_{e}": int((sub["estado"] == e).sum()) for e in ESTADOS},
            **{f"fn_exec_{e}": int(((sub["estado"] == e) & sub["fn"]).sum()) for e in ESTADOS}}


def _linhas_resultado(res: pd.DataFrame, game: int, tipos, ancoras, alvo=None) -> pd.DataFrame:
    """Linhas de `evaluate.avaliar` do jogo, dos `tipos` e `ancoras`, com a
    coluna `alvo` (= `type`, ou o rotulo dado)."""
    sel = res[(res["game"] == game) & res["type"].isin(tipos) & res["ancora"].isin(ancoras)]
    return sel.assign(alvo=sel["type"] if alvo is None else alvo)[
        ["criterio", "ancora", "alvo"] + CONTAGENS]


def apagao_total(tracking: pd.DataFrame, frames: pd.DataFrame) -> np.ndarray:
    """(n_quadros,) bool, indexado por `frame - 1` (grade 1..N contigua): o
    quadro e de APAGAO TOTAL, nenhum jogador com `visible = True` em
    `tracking` (plano 09 §2.A). No teto nunca; no `bruto`, quadro sem linha."""
    n = len(frames)
    vis = tracking.loc[tracking["visible"].to_numpy(), "frame"].to_numpy()
    return np.bincount(vis - 1, minlength=n)[:n] == 0


def bola_some(frames: pd.DataFrame, apagao: np.ndarray) -> pd.DataFrame:
    """Frente B (plano 09 §2.B): copia de `frames` com `ball_x`/`ball_y` NaN nos
    quadros de `apagao`. `ball_live` e o resto ficam intactos (D1b)."""
    m = apagao[frames["frame"].to_numpy() - 1]
    out = frames.copy()
    out.loc[m, ["ball_x", "ball_y"]] = np.nan
    return out


def _estratos(gab: pd.DataFrame, det: pd.DataFrame, quadro_gab: str, apagao: np.ndarray,
              tipos: dict, cfg: dict) -> dict:
    """Frente A (plano 09 §2.A): `alvo -> {coluna de COLUNAS_ESTRATO: n}`.

    Mesmo casamento de `_estado_executor` (criterio principal, ancora `frame`,
    acerto = diagonal). O evento cai no estrato do seu `quadro_gab`
    (`annotated_frame` no passe, `frame` na bola parada); a deteccao, no do
    seu `frame`. `tipos`: `alvo -> lista de tipos`. Nada e excluido: evento
    sem deteccao e FN no seu estrato."""
    principal = cfg["avaliacao"]["criterio_principal"]
    eixos = cfg["avaliacao"]["criterios"][principal]
    grupo_de = evaluate.grupo_por_tipo(cfg)
    g = gab[gab["type"].isin(grupo_de)].reset_index(drop=True)
    g = g.assign(grupo=g["type"].map(grupo_de), t=g["frame"] / cfg["tracking"]["fps"])
    d = det.reset_index(drop=True)
    d = d.assign(grupo=d["type"].map(grupo_de))
    i_gab, i_det = evaluate.casar(g, d, eixos["janela_s"], eixos["casa_tipo"], eixos["casa_jogador"])
    diag = g["type"].to_numpy()[i_gab] == d["type"].to_numpy()[i_det]
    acerto_g, acerto_d = np.zeros(len(g), bool), np.zeros(len(d), bool)
    acerto_g[i_gab[diag]] = True
    acerto_d[i_det[diag]] = True
    em_g = apagao[g[quadro_gab].to_numpy() - 1]
    em_d = apagao[d["frame"].to_numpy() - 1]
    out = {}
    for alvo, ts in tipos.items():
        mg, md = g["type"].isin(ts).to_numpy(), d["type"].isin(ts).to_numpy()
        out[alvo] = {}
        for e, eg, ed in (("apagao", em_g, em_d), ("fora", ~em_g, ~em_d)):
            out[alvo].update({f"{e}_n_gabarito": int((mg & eg).sum()),
                              f"{e}_tp_gab": int((mg & eg & acerto_g).sum()),
                              f"{e}_n_detectado": int((md & ed).sum()),
                              f"{e}_tp_det": int((md & ed & acerto_d).sum())})
    return out


def pontos_de_r(dados: dict, tracking: pd.DataFrame, cfg_r: dict, ancoras) -> pd.DataFrame:
    """Um ponto `(R_pz, politica)` de UM jogo, com e sem lacuna 5.

    Entrada: `dados` com `frames`, `periods`, `eventos` do teto (nunca
    degradados, D1b); `tracking` = o que o detector ve; `cfg_r` com
    `posse.r_pz_m` e `posse.r_dz_politica` do ponto (`run.com_r_pz`); `ancoras`
    a manter. Saida: as colunas de ponto, contagens e R9 do docstring do modulo.

    `lacuna5 = sem`: bola parada com as perdas `so_por_lacuna_5` filtradas
    (`run.detectar_jogos(sem_lacuna_5=True)`, bloco 6 de `--bola-parada`) e
    passes = `run.passes_sem_lacuna_5` sobre a tabela da deteccao principal
    (N5, bloco 7 de `--passes`).
    """
    fr, ev = dados["frames"], dados["eventos"]
    game = int(fr["game"].iloc[0])
    principal = cfg_r["avaliacao"]["criterio_principal"]
    tipos_bp = cfg_r["avaliacao"]["grupos"]["bola_parada"]
    p1 = possession.calcular(fr, tracking, cfg_r)
    b = {game: {"frames": fr, "tracking": tracking, "periods": dados["periods"],
                "perdas": p1["perdas"], "ganhos": p1["ganhos"], "control": p1["control"]}}
    det_com = run.detectar_jogos(b, cfg_r, [game])
    expl = cfg_r["exploratorio"]
    passes_com = run.rotular_jogos(b, det_com, [game], expl["supressao_exige_executor"])
    apagao = apagao_total(tracking, fr) if expl["estratos_apagao"] else None
    variantes = {"com": (det_com, passes_com),
                 "sem": (run.detectar_jogos(b, cfg_r, [game], sem_lacuna_5=True),
                         run.passes_sem_lacuna_5(passes_com))}
    gab_sec = evaluate.gabarito_secundario(ev, cfg_r)
    gab_passe = ev[ev["type"] == "pass"]
    blocos = []
    for lacuna5, (det, pas) in variantes.items():
        det_c = bola_parada.para_casador(det)
        pp_c = passes_mod.para_casador(pas, so_completo=True)
        ps_c = passes_mod.para_casador(pas)
        res_bp, _ = evaluate.avaliar(ev, det_c, cfg_r)
        res_pp, _ = evaluate.avaliar(ev, pp_c, cfg_r)
        res_ps, _ = evaluate.avaliar(gab_sec, ps_c, cfg_r)
        bp = _linhas_resultado(res_bp, game, tipos_bp, ancoras)
        sem_pen = res_bp[(res_bp["game"] == game) & res_bp["type"].isin(tipos_bp)
                         & (res_bp["type"] != "penalty") & res_bp["ancora"].isin(ancoras)]
        micro = [{"criterio": c, "ancora": a, "alvo": ALVO_MICRO,
                  **{k: v for k, v in evaluate.micro(s).items() if k in CONTAGENS},
                  "tp": int(s["tp"].sum())}
                 for (c, a), s in sem_pen.groupby(["criterio", "ancora"], sort=True)]
        tab = pd.concat([bp, pd.DataFrame(micro),
                         _linhas_resultado(res_pp, game, ["pass"], ancoras, ALVO_PASSE),
                         _linhas_resultado(res_ps, game, ["pass"], ancoras, ALVO_PASSE_SEC)],
                        ignore_index=True)
        # R9, so no criterio principal e ancora `frame`
        est_bp = _estado_executor(ev[ev["type"].isin(tipos_bp)], det_c, tracking, fr, cfg_r)
        dec = {t: {**{f"motivo_{m}": int(((det["type"] == t) & (det["motivo_reserva1"] == m)).sum())
                      for m in bola_parada.MOTIVOS},
                   **{f"via_{v}": int(((det["type"] == t) & (det["via"] == v)).sum())
                      for v in hierarquia.VIAS},
                   **_contar_estado(est_bp, t)} for t in tipos_bp}
        dec[ALVO_MICRO] = {k: sum(dec[t][k] for t in tipos_bp if t != "penalty") for k in dec[tipos_bp[0]]}
        causa = run.decompor_fn(ev, pas, cfg_r)["causa"]
        dec[ALVO_PASSE] = {**{f"fn_causa_{c}": int((causa == c).sum()) for c in "abcd"},
                           **_contar_estado(_estado_executor(gab_passe, pp_c, tracking, fr, cfg_r), None)}
        dec[ALVO_PASSE_SEC] = _contar_estado(_estado_executor(gab_sec, ps_c, tracking, fr, cfg_r), None)
        decomp = pd.DataFrame.from_dict(dec, orient="index").reindex(columns=DECOMP)
        e_principal = ((tab["criterio"] == principal) & (tab["ancora"] == "frame")).to_numpy()
        valores = decomp.reindex(tab["alvo"]).to_numpy(dtype="float64")
        valores[~e_principal] = np.nan
        tab[DECOMP] = valores
        if apagao is not None:
            micro = [t for t in tipos_bp if t != "penalty"]
            est = {**_estratos(ev[ev["type"].isin(tipos_bp)], det_c, "frame", apagao,
                               {**{t: [t] for t in tipos_bp}, ALVO_MICRO: micro}, cfg_r),
                   **_estratos(gab_passe, pp_c, "annotated_frame", apagao, {ALVO_PASSE: ["pass"]}, cfg_r)}
            v = pd.DataFrame.from_dict(est, orient="index").reindex(
                index=tab["alvo"], columns=COLUNAS_ESTRATO).to_numpy(dtype="float64", copy=True)
            v[~e_principal] = np.nan
            tab[COLUNAS_ESTRATO] = v
            # os dois estratos somam o total da linha (plano 09 §2.A)
            ok = ~np.isnan(v[:, 0])
            for c, (a, f) in (("n_gabarito", (0, 4)), ("tp_diag", (1, 5)), ("n_detectado", (2, 6)),
                              ("tp_diag", (3, 7))):
                if not np.array_equal(v[ok, a] + v[ok, f], tab[c].to_numpy(dtype="float64")[ok]):
                    raise RuntimeError("estratos nao somam `{}`".format(c))
        blocos.append(tab.assign(lacuna5=lacuna5))
    out = pd.concat(blocos, ignore_index=True)
    out.insert(0, "r_pz", float(cfg_r["posse"]["r_pz_m"]))
    out.insert(1, "politica", cfg_r["posse"]["r_dz_politica"])
    extra = COLUNAS_ESTRATO if apagao is not None else []
    return out[["r_pz", "politica", "lacuna5", "criterio", "ancora", "alvo"] + CONTAGENS + DECOMP + extra]


def normalizar(unidade: tuple) -> tuple:
    """`(condicao, jogo, variante, nivel, rep)`; o nivel 1 vira `(.., "AB", 1, 0)`:
    determinístico, sem semente, compartilhado pelas variantes (R3)."""
    condicao, jogo, variante, nivel, rep = unidade
    if condicao not in CONDICOES:
        raise ValueError("condicao {!r} fora de {}".format(condicao, CONDICOES))
    if int(nivel) == 1:
        return (condicao, int(jogo), VARIANTE_TETO, 1, 0)
    return (condicao, int(jogo), str(variante), int(nivel), int(rep))


def tracking_da_condicao(teto: pd.DataFrame, degradado: pd.DataFrame, condicao: str) -> pd.DataFrame:
    """O tracking que o detector ve: o degradado com as linhas ausentes (`bruto`)
    ou reconstruido com a presenca do teto (`reconstruido`, Fatia 7)."""
    if condicao == "bruto":
        return degradado
    if condicao == "reconstruido":
        return reconstruct.reconstruir(degradado, teto[reconstruct.CHAVES])[0]
    raise ValueError("condicao {!r} fora de {}".format(condicao, CONDICOES))


def _dist_na_grade(tracking: pd.DataFrame, frames: pd.DataFrame, grade) -> tuple:
    """(n com distancia finita, n exatamente igual a um valor de `grade`)."""
    i = tracking["frame"].to_numpy() - 1
    d = np.hypot(tracking["x"].to_numpy() - frames["ball_x"].to_numpy()[i],
                 tracking["y"].to_numpy() - frames["ball_y"].to_numpy()[i])
    ok = np.isfinite(d)
    return int(ok.sum()), int(np.isin(d[ok], np.asarray(grade, dtype="float64")).sum())


def rodar_unidade(jogo, variante, nivel, rep, condicao, cfg: dict, base: dict) -> pd.DataFrame:
    """Uma unidade (docstring do modulo). `base[jogo]` com `frames`,
    `tracking` (teto), `periods`, `eventos` (`run._base_leve`). A grade de
    `R_pz` e `posse.grade_r_pz_m`; `fixo_1m` roda alem da politica principal
    nos `experimento.niveis_fixo_1m` e so em `R_pz > posse.r_dz_m` (abaixo as
    duas sao identicas por construcao, R3). `annotated_frame` so no nivel 1 em
    `experimento.r0_m` (R3)."""
    condicao, jogo, variante, nivel, rep = normalizar((condicao, jogo, variante, nivel, rep))
    dados = base[jogo]
    teto, fr = dados["tracking"], dados["frames"]
    if nivel == 1:
        # nivel 1 = teto bit a bit nas duas variantes (test_t3_nivel_1_reconstruido_e_o_teto)
        deg, semente = teto, SEM_SEMENTE
    else:
        deg = broadcast.degradar(teto, fr, cfg, variante, nivel, rep)
        semente = ";".join(str(s) for s in broadcast.semente_efetiva(cfg, jogo, rep))
    trk = tracking_da_condicao(teto, deg, condicao)
    if cfg["exploratorio"]["bola_some_no_apagao"]:
        # frente B (plano 09 §2.B): depois do simulador e da reconstrucao
        fr = bola_some(fr, apagao_total(trk, fr))
        dados = {**dados, "frames": fr}
    gk_teto, gk_deg = teto["is_gk"].to_numpy(), deg["is_gk"].to_numpy()
    grade = cfg["posse"]["grade_r_pz_m"]
    n_dist, n_igual = _dist_na_grade(trk, fr, grade)
    ex = cfg["experimento"]
    principal = cfg["posse"]["r_dz_politica"]
    blocos = []
    for r in grade:
        politicas = [principal] + ([FIXO] if nivel in ex["niveis_fixo_1m"]
                                   and r > cfg["posse"]["r_dz_m"] and principal != FIXO else [])
        ancoras = cfg["avaliacao"]["ancoras"] if (nivel == 1 and r == ex["r0_m"]) else ["frame"]
        for pol in politicas:
            blocos.append(pontos_de_r(dados, trk, run.com_r_pz(cfg, r, pol), ancoras))
    out = pd.concat(blocos, ignore_index=True)
    unidade = {"condicao": condicao, "jogo": jogo, "variante": variante, "nivel": nivel, "rep": rep,
               "semente_efetiva": semente,
               "taxa_todos": len(deg) / len(teto),
               "taxa_sem_gk": float((~gk_deg).sum() / (~gk_teto).sum()),
               "n_dist": n_dist, "n_dist_igual_grade": n_igual}
    for k, (nome, valor) in enumerate(unidade.items()):
        out.insert(k, nome, valor)
    return out


# --- agregacao (R5), a unica porta ---------------------------------------------

def agregar(pontos: pd.DataFrame, por) -> pd.DataFrame:
    """Soma as contagens (e as colunas de R9) sobre `jogo` e `rep` dentro de
    cada grupo de `por`, e SO DEPOIS calcula `precisao`, `revocacao`, `f1`
    (`_prf`): P e R NaN com denominador 0; F1 = `2 tp / (n_det + n_gab)`
    (plano 08 §8, item 2), logo 0 com zero deteccoes e `n_gab > 0`, e NaN so
    com `n_det + n_gab = 0`. NaN nunca vira 0 nem e descartado. E a unica
    porta de agregacao do experimento (R5); nunca faz media de F1.

    Toda chave de ponto que nao esteja em `por` nem em `SOMA_SOBRE` tem de ter
    um valor so na entrada, senao estoura (a armadilha do `micro()`). Saida:
    `por`, as somas, `n_linhas`, a media de `taxa_todos`/`taxa_sem_gk` (a media
    das taxas amostradas, R4), P/R/F1 e, quando `jogo` e somado, o minimo e o
    maximo do F1 por jogo (D4; NaN se algum jogo for NaN).
    """
    por = list(por)
    if not por:
        raise ValueError("agregar: `por` vazio")
    mistura = [c for c in CHAVES_PONTO if c in pontos.columns and c not in por
               and c not in SOMA_SOBRE and pontos[c].nunique() > 1]
    if mistura:
        raise ValueError("agregar: mais de um valor de {} fora de `por`".format(mistura))
    soma = [c for c in SOMAVEIS if c in pontos.columns]
    g = pontos.groupby(por, sort=True, dropna=False)
    out = g[soma].sum(min_count=1)
    out["n_linhas"] = g.size()
    for c in ("taxa_todos", "taxa_sem_gk"):
        if c in pontos.columns:
            out[c] = g[c].mean()
    out["precisao"], out["revocacao"], out["f1"] = _prf(out["tp_diag"], out["n_detectado"], out["n_gabarito"])
    if "jogo" in pontos.columns and "jogo" not in por:
        pj = pontos.groupby(por + ["jogo"], sort=True, dropna=False)[CONTAGENS].sum()
        f1j = pd.Series(_prf(pj["tp_diag"], pj["n_detectado"], pj["n_gabarito"])[2], index=pj.index)
        nivel = list(range(len(por)))
        out["f1_jogo_min"] = f1j.groupby(level=nivel).agg(lambda s: np.nan if s.isna().any() else s.min())
        out["f1_jogo_max"] = f1j.groupby(level=nivel).agg(lambda s: np.nan if s.isna().any() else s.max())
    return out.reset_index()


def conferir_n_gabarito(pontos: pd.DataFrame) -> None:
    """Evento nao detectado e FN, nunca excluido: `n_gabarito` e constante em
    todos os pontos para cada `(jogo, alvo, criterio, ancora)`. Estoura se nao."""
    n = pontos.groupby(["jogo", "alvo", "criterio", "ancora"])["n_gabarito"].nunique()
    if (n > 1).any():
        raise ValueError("n_gabarito varia entre pontos em {}".format(n[n > 1].index.tolist()))


# --- R6 e R8 -------------------------------------------------------------------

def _principal(pontos: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    return pontos[(pontos["criterio"] == cfg["avaliacao"]["criterio_principal"])
                  & (pontos["ancora"] == "frame")
                  & (pontos["politica"] == cfg["posse"]["r_dz_politica"])
                  & (pontos["lacuna5"] == "com")]


def _argmax_menor(f1: pd.Series) -> float:
    """O `r_pz` de maior F1; empate fica com o menor (indice crescente)."""
    f1 = f1.sort_index()
    return float(f1.idxmax())


def _sim_nao(v: bool) -> str:
    return "sim" if v else "nao"


def conclusoes(n_pos: int, d_agg: float, d_agg_teto: float, cfg: dict) -> tuple:
    """(ajuda, compensa) da R6, plano 08 §8, item 4, com `lambda` =
    `experimento.ep_max_f1`. "ajuda": `Delta_g > 0` em >=
    `experimento.min_jogos_compensa` jogos de teste (2 dos 3 na Metrica, 5 dos
    7 no IDSSE, plano 11 §4b) e `Delta_agregado > lambda`.
    "compensa": "ajuda" e `Delta_agregado(nivel) - Delta_agregado(nivel 1) >
    lambda`; `d_agg_teto = None` (o proprio nivel 1) da "nao_se_aplica". NaN
    nunca passa."""
    ex = cfg["experimento"]
    lam = ex["ep_max_f1"]
    ajuda = n_pos >= ex["min_jogos_compensa"] and d_agg > lam
    if d_agg_teto is None:
        return _sim_nao(ajuda), "nao_se_aplica"
    return _sim_nao(ajuda), _sim_nao(ajuda and d_agg - d_agg_teto > lam)


def selecionar_logo(pontos: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """R6 com a emenda do plano 08 §8, leave-one-game-out, por `(condicao,
    variante, nivel, alvo)` no criterio principal, ancora `frame`, politica
    principal, com lacuna 5; `penalty` fica fora (n = 1). F1 sempre de `_prf`
    (`2 tp / (n_det + n_gab)`). Uma linha por jogo de teste `g`:

    `r_estrela`: candidatos = `R` com F1_t(R) > F1_t(R0) em pelo menos
    `experimento.min_jogos_candidato` jogos de treino `t` (2 de 2 na Metrica =
    cada um; 4 de 6 no IDSSE, plano 11 §4b) E F1_T(R) > F1_T(R0) no treino
    somado (guarda contra Simpson); F1 NaN
    nunca e candidato; argmax de F1_T entre eles, empate -> menor; sem
    candidato -> R0; o jogo `g` nunca entra. Com `f1_teste_r_estrela`,
    `f1_teste_r0`, `delta`.

    Repetidos no grupo: `n_delta_pos`; `f1_logo` (F1 dos jogos de teste
    somados, cada um no seu `R*`); `delta_agregado` = `f1_logo` - F1 deles
    somados em R0; `delta_agregado_nivel_1` (o do nivel 1 da mesma condicao e
    alvo); `ajuda` e `compensa` (`conclusoes`); `fracao_recuperada` =
    `delta_agregado / (f1_logo(nivel 1) - F1_nivel(R0))`, so com denominador >
    lambda (senao NaN); e `r_dentro_amostra_EXPLORATORIO` (argmax do F1 dos 3
    jogos juntos, rotulado exploratorio)."""
    ex = cfg["experimento"]
    r0 = float(ex["r0_m"])
    lam = ex["ep_max_f1"]
    k = int(ex["min_jogos_candidato"])
    sel = _principal(pontos, cfg)
    sel = sel[sel["alvo"] != "penalty"]
    grupo = ["condicao", "variante", "nivel", "alvo"]
    por_jogo = agregar(sel, grupo + ["jogo", "r_pz"])
    todos = agregar(sel, grupo + ["r_pz"]).set_index(grupo + ["r_pz"])["f1"]
    linhas, resumo = [], {}
    for chave, bloco in por_jogo.groupby(grupo, sort=True):
        f1 = bloco.pivot(index="r_pz", columns="jogo", values="f1").sort_index()
        sub = sel[(sel[grupo] == pd.Series(chave, index=grupo)).all(axis=1)]
        jogos = sorted(f1.columns)
        teste = []
        for g in jogos:
            treino = [t for t in jogos if t != g]
            if k > len(treino):
                raise ValueError("selecionar_logo: min_jogos_candidato = {} > {} jogos de treino".format(
                    k, len(treino)))
            ganho = (f1[treino].sub(f1.loc[r0, treino], axis=1) > 0).sum(axis=1) >= k
            f1_treino = agregar(sub[sub["jogo"].isin(treino)], grupo + ["r_pz"]).set_index("r_pz")["f1"]
            ganho &= (f1_treino > f1_treino.loc[r0]).reindex(ganho.index, fill_value=False)
            cand = f1_treino[ganho.reindex(f1_treino.index, fill_value=False)]
            r_est = _argmax_menor(cand) if len(cand) else r0
            teste.append((g, r_est))
            linhas.append(dict(zip(grupo, chave), jogo_teste=g, r_estrela=r_est,
                               f1_teste_r_estrela=f1.loc[r_est, g], f1_teste_r0=f1.loc[r0, g],
                               delta=f1.loc[r_est, g] - f1.loc[r0, g]))
        em_r_est = pd.concat([sub[(sub["jogo"] == g) & (sub["r_pz"] == r)] for g, r in teste])
        f1_logo = agregar(em_r_est.drop(columns="r_pz"), grupo)["f1"].iloc[0]
        f1_r0 = todos.loc[(*chave, r0)]
        bloco_linhas = linhas[-len(jogos):]
        resumo[chave] = {"n_delta_pos": int(sum(l["delta"] > 0 for l in bloco_linhas)),
                         "f1_logo": f1_logo, "f1_r0": f1_r0, "delta_agregado": f1_logo - f1_r0,
                         "r_dentro_amostra_EXPLORATORIO": _argmax_menor(todos.loc[chave].dropna())
                         if todos.loc[chave].notna().any() else np.nan}
    for l in linhas:
        chave = tuple(l[c] for c in grupo)
        r = resumo[chave]
        teto = resumo.get((chave[0], VARIANTE_TETO, 1, chave[3]))
        e_teto = chave[2] == 1
        d_teto = None if e_teto else (teto["delta_agregado"] if teto else np.nan)
        ajuda, compensa = conclusoes(r["n_delta_pos"], r["delta_agregado"], d_teto, cfg)
        den = (teto["f1_logo"] if teto else np.nan) - r["f1_r0"]
        l.update(n_delta_pos=r["n_delta_pos"], f1_logo=r["f1_logo"], delta_agregado=r["delta_agregado"],
                 delta_agregado_nivel_1=np.nan if d_teto is None else d_teto, ajuda=ajuda, compensa=compensa,
                 fracao_recuperada=r["delta_agregado"] / den if (not e_teto and den > lam) else np.nan,
                 r_dentro_amostra_EXPLORATORIO=r["r_dentro_amostra_EXPLORATORIO"])
    return pd.DataFrame(linhas)


def regra_sementes(piloto: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """R8. Por `(variante, alvo)` do piloto (criterio principal, `frame`,
    politica principal, com lacuna 5, `R0`): F1 por semente com os jogos
    somados (`agregar`), `s` = desvio-padrao amostral (ddof = 1) das sementes,
    `ep5 = s / sqrt(experimento.n_ref_ep)` (plano 08 §8). Decidem so os alvos primarios; o
    escanteio sai reportado. `n_sementes_decidido` = `experimento.n_ref_ep` se
    `ep5 <= experimento.ep_max_f1` em todos os que decidem, senao
    `experimento.n_sementes_piloto`. NaN nunca passa no limiar. As
    `experimento.variantes_sem_semente` ficam fora (nao tem ruido de semente)."""
    ex = cfg["experimento"]
    n_ref = int(ex["n_ref_ep"])
    sel = _principal(piloto, cfg)
    sel = sel[(sel["r_pz"] == ex["r0_m"]) & sel["alvo"].isin(ALVOS_PRIMARIOS + ("corner_kick",))
              & ~sel["variante"].isin(ex["variantes_sem_semente"])]
    grupo = ["condicao", "variante", "nivel", "alvo"]
    por_semente = agregar(sel, grupo + ["rep"])
    linhas = []
    for chave, b in por_semente.groupby(grupo, sort=True):
        if len(b) != ex["n_sementes_piloto"]:
            raise ValueError("regra_sementes: {} tem {} sementes, nao {}".format(
                chave, len(b), ex["n_sementes_piloto"]))
        f1 = b["f1"]      # skipna=False: semente com F1 NaN deixa s NaN (R5), nunca some
        s = float(f1.std(ddof=1, skipna=False))
        linhas.append(dict(zip(grupo, chave), n_sementes=len(b), f1_media=float(f1.mean(skipna=False)),
                           f1_min=float(f1.min(skipna=False)), f1_max=float(f1.max(skipna=False)), s=s,
                           ep5=s / np.sqrt(n_ref), decide=chave[3] in ALVOS_PRIMARIOS))
    tab = pd.DataFrame(linhas)
    tab["ep5_ok"] = tab["ep5"] <= ex["ep_max_f1"]
    ok = bool(tab.loc[tab["decide"], "ep5_ok"].all()) and tab["decide"].any()
    tab["n_sementes_decidido"] = n_ref if ok else int(ex["n_sementes_piloto"])
    return tab


# --- cache, manifesto e execucao -----------------------------------------------

def _sha(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


@lru_cache(maxsize=None)
def _hashes_jogo(raiz: str, jogo: int) -> tuple:
    pasta = Path(raiz) / f"Sample_Game_{jogo}"
    return tuple((p.name, _sha(p)) for p in sorted(pasta.iterdir()) if p.is_file())


# TODO(divida): sha256 memorizado por (caminho, mtime, tamanho) no processo; um
# XML reescrito com o mesmo mtime e tamanho passaria sem ser visto. Aceito porque
# data/ e somente leitura; refazer o sha a cada chamada custa ~2,5 GB por chave.
@lru_cache(maxsize=None)
def _sha_arquivo(caminho: str, mtime_ns: int, tamanho: int) -> str:
    return _sha(Path(caminho))


def hashes_dados(cfg: dict, jogos) -> dict:
    """sha256 dos arquivos de `data/` de cada jogo e do mapeamento de eventos.
    No IDSSE, os 3 XML do jogo (o mapeamento DFL vive em `idsse:`, que entra
    no config lido)."""
    if cfg["dados"]["conjunto"] == "idsse":
        arqs = {g: idsse.caminhos(cfg, int(g)).values() for g in jogos}
        return {f"jogo_{g}": {p.name: _sha_arquivo(str(p), p.stat().st_mtime_ns, p.stat().st_size)
                              for p in sorted(a)} for g, a in arqs.items()}
    out = {f"jogo_{g}": dict(_hashes_jogo(str(cfg["dados"]["raiz"]), int(g))) for g in jogos}
    out["mapeamento"] = _sha(Path(cfg["gabarito"]["mapeamento"]))
    return out


def hashes_src() -> dict:
    """sha256 de cada `src/**/*.py`, lido agora (editar o codigo invalida o cache)."""
    raiz = RAIZ_REPO / "src"
    return {p.relative_to(raiz).as_posix(): _sha(p) for p in sorted(raiz.rglob("*.py"))}


# Secoes do config que a unidade le. `simulador.n_sementes` nao e lida por ela
# (so monta a lista de unidades), e de `experimento` so estas duas chaves.
SECOES_LIDAS = ("dados", "tracking", "campo", "gabarito", "avaliacao", "posse", "bola_parada", "simulador")
EXPERIMENTO_LIDO = ("r0_m", "niveis_fixo_1m")
# Fatia 9: as quatro chaves que a unidade le (a grade e as frentes nao).
EXPLORATORIO_LIDO = ("bola_some_no_apagao", "presentes_por_visible", "supressao_exige_executor",
                     "estratos_apagao")


def config_lido(cfg: dict) -> dict:
    sub = {s: copy.deepcopy(cfg[s]) for s in SECOES_LIDAS}
    sub["simulador"].pop("n_sementes")
    sub["experimento"] = {k: cfg["experimento"][k] for k in EXPERIMENTO_LIDO}
    sub["exploratorio"] = {k: cfg["exploratorio"][k] for k in EXPLORATORIO_LIDO}
    if cfg["dados"]["conjunto"] == "idsse":
        sub["idsse"] = copy.deepcopy(cfg["idsse"])     # o leitor e o mapeamento DFL
    return sub


def chave_unidade(cfg: dict, unidade: tuple, src: dict = None) -> tuple:
    """(material, sha256): material = hashes dos dados do jogo + config lido +
    hashes de `src/**/*.py` + a tupla normalizada."""
    unidade = normalizar(unidade)
    material = {"dados": hashes_dados(cfg, [unidade[1]]), "config": config_lido(cfg),
                "src": src if src is not None else hashes_src(), "unidade": list(unidade)}
    texto = json.dumps(material, sort_keys=True, default=str)
    return json.loads(texto), hashlib.sha256(texto.encode()).hexdigest()


def _ler_tabela(texto: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(texto))


def ler_cache(pasta: Path, material: dict, chave: str):
    """(tabela, tempo_s) ou None. Estoura se a entrada guardar outra chave ou
    se a tabela nao bater com o seu sha256 (entrada adulterada)."""
    caminho = Path(pasta) / f"{chave}.json"
    if not caminho.exists():
        return None
    entrada = json.loads(caminho.read_text(encoding="utf-8"))
    guardada = hashlib.sha256(json.dumps(entrada["material"], sort_keys=True).encode()).hexdigest()
    if entrada["chave"] != chave or guardada != chave or entrada["material"] != material:
        raise RuntimeError("cache: entrada {} guarda outra chave".format(caminho))
    if hashlib.sha256(entrada["tabela_csv"].encode()).hexdigest() != entrada["sha256_tabela"]:
        raise RuntimeError("cache: tabela adulterada em {}".format(caminho))
    return _ler_tabela(entrada["tabela_csv"]), entrada["tempo_s"]


def gravar_cache(pasta: Path, material: dict, chave: str, texto: str, tempo_s: float) -> None:
    Path(pasta).mkdir(parents=True, exist_ok=True)
    entrada = {"chave": chave, "material": material, "sha256_tabela": hashlib.sha256(texto.encode()).hexdigest(),
               "tempo_s": tempo_s, "tabela_csv": texto}
    (Path(pasta) / f"{chave}.json").write_text(json.dumps(entrada), encoding="utf-8")


_TRABALHO = {}


def base_idsse(jogo: int, cfg: dict, pasta_cache=None) -> dict:
    """`{jogo: {frames, tracking, periods, eventos}}` do IDSSE, como
    `run._base_leve` (eventos no esquema EVENTS, sem o diagnostico)."""
    j = idsse.carregar_jogo(jogo, cfg, pasta_cache)
    return {jogo: {"frames": j["frames"], "tracking": j["tracking"], "periods": j["periods"],
                   "eventos": j["eventos"][list(schema.EVENTS)]}}


def _iniciar(cfg, mapeamento, jogos, pasta_cache=None):
    _TRABALHO["cfg"] = cfg
    if cfg["dados"]["conjunto"] == "idsse":
        # um jogo por vez por processo, carregado sob demanda em `_trabalhar`:
        # os 7 jogos nao cabem em cada worker (16 GB)
        _TRABALHO["base"], _TRABALHO["pasta_cache"] = {}, pasta_cache
    else:
        _TRABALHO["base"] = run._base_leve(cfg, mapeamento, jogos)


def _trabalhar(unidade):
    base = _TRABALHO["base"]
    if _TRABALHO["cfg"]["dados"]["conjunto"] == "idsse" and unidade[1] not in base:
        base.clear()
        base.update(base_idsse(unidade[1], _TRABALHO["cfg"], _TRABALHO["pasta_cache"]))
    t0 = time.perf_counter()
    tab = rodar_unidade(*unidade[1:], unidade[0], _TRABALHO["cfg"], _TRABALHO["base"])
    return unidade, tab.to_csv(index=False), time.perf_counter() - t0


def _calcular(faltam, cfg, mapeamento, n_workers, pasta_cache=None):
    """Gera `(unidade, csv, tempo_s)` na ordem em que as unidades terminam.
    `pasta_cache` so serve ao leitor do IDSSE (a conversao do XML)."""
    if not faltam:
        return
    jogos = sorted({u[1] for u in faltam})
    if n_workers <= 1:
        _iniciar(cfg, mapeamento, jogos, pasta_cache)
        for u in faltam:
            yield _trabalhar(u)
        return
    with ProcessPoolExecutor(max_workers=n_workers, initializer=_iniciar,
                             initargs=(cfg, mapeamento, jogos, pasta_cache)) as pool:
        for futuro in as_completed([pool.submit(_trabalhar, u) for u in faltam]):
            yield futuro.result()


def rodar_unidades(unidades, cfg: dict, mapeamento: dict, n_workers: int, pasta_cache=None):
    """Roda (ou le do cache) cada unidade `(condicao, jogo, variante, nivel,
    rep)`. Saida: (pontos, info), `pontos` na ordem das unidades normalizadas
    ordenadas, sempre pelo mesmo caminho texto -> DataFrame (o resultado nao
    depende de hit/miss nem de `n_workers`); `info` uma entrada por unidade com
    `semente_efetiva`, `cache` (hit/miss/desligado) e `tempo_s`.
    `pasta_cache = None` desliga o cache."""
    unidades = sorted({normalizar(u) for u in unidades})
    src = hashes_src()
    chaves = {u: chave_unidade(cfg, u, src) for u in unidades}
    textos, info = {}, {}
    faltam = []
    for u in unidades:
        achado = ler_cache(pasta_cache, *chaves[u]) if pasta_cache is not None else None
        if achado is None:
            faltam.append(u)
        else:
            textos[u] = achado[0]
            info[u] = ("hit", achado[1])
    # Cada unidade vai ao cache assim que termina (uma rodada interrompida nao
    # perde o que ja fez); a montagem abaixo e na ordem ordenada, nao na de chegada.
    for u, texto, tempo in _calcular(faltam, cfg, mapeamento, n_workers, pasta_cache):
        if pasta_cache is not None:
            gravar_cache(pasta_cache, *chaves[u], texto, tempo)
        textos[u] = _ler_tabela(texto)
        info[u] = ("miss" if pasta_cache is not None else "desligado", tempo)
    pontos = pd.concat([textos[u] for u in unidades], ignore_index=True)
    lista = [{**dict(zip(CHAVES_UNIDADE, u)),
              "semente_efetiva": SEM_SEMENTE if u[3] == 1 else
              ";".join(str(s) for s in broadcast.semente_efetiva(cfg, u[1], u[4])),
              "cache": info[u][0], "tempo_s": info[u][1]} for u in unidades]
    return pontos, lista


def manifesto(cfg: dict, caminho_config: Path, unidades: list) -> dict:
    def git(*args):
        return subprocess.run(["git", *args], cwd=RAIZ_REPO, capture_output=True, text=True).stdout.strip()
    return {"commit": git("rev-parse", "HEAD"), "working_tree_sujo": bool(git("status", "--porcelain")),
            "sha256_config": _sha(Path(caminho_config)), "dados": hashes_dados(cfg, cfg["dados"]["jogos"]),
            **{k: cfg["dados"][k] for k in ("conjunto", "perfil", "rotulo") if k in cfg["dados"]},
            "versoes": {"python": platform.python_version(), "numpy": np.__version__,
                        "pandas": pd.__version__, "scipy": scipy.__version__},
            "unidades": unidades}


def grade(cfg: dict, condicoes=None) -> list:
    """As unidades da grade R3: por condicao, o nivel 1 por jogo e cada
    (variante, nivel 2..8, rep, jogo), com rep 0..simulador.n_sementes-1, ou
    so rep 0 nas `experimento.variantes_sem_semente`."""
    jogos = cfg["dados"]["jogos"]
    niveis = cfg["simulador"]["calibrado"]["niveis"]
    out = []
    for c in condicoes or cfg["experimento"]["condicoes"]:
        out += [(c, g, VARIANTE_TETO, 1, 0) for g in jogos]
        out += [(c, g, v, k, rep) for v in broadcast.VARIANTES for k in range(2, len(niveis[v]) + 1)
                for rep in range(_n_reps(cfg, v, int(cfg["simulador"]["n_sementes"]))) for g in jogos]
    return out


def _n_reps(cfg: dict, variante: str, n: int) -> int:
    return 1 if variante in cfg["experimento"]["variantes_sem_semente"] else n


def _trocar(cfg: dict, **troca) -> dict:
    novo = copy.deepcopy(cfg)
    for secao_chave, valor in troca.items():
        secao, chave = secao_chave.split("__")
        novo[secao][chave] = valor
    return novo


def _gravar(tabela: pd.DataFrame, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tabela.to_csv(destino, index=False)
    print("gravado: {} ({} linhas)".format(destino, len(tabela)))


def _gravar_manifesto(cfg, caminho_config, lista, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(manifesto(cfg, caminho_config, lista), indent=1, default=str),
                       encoding="utf-8")
    print("gravado: {}".format(destino))


def _tempo_unidade(lista) -> pd.DataFrame:
    return pd.DataFrame(lista)[CHAVES_UNIDADE + ["cache", "tempo_s"]]


def rodar_piloto(cfg: dict, mapeamento: dict, caminho_config: Path, saida: Path, pasta_cache) -> pd.DataFrame:
    """R8: o piloto em R0 (`experimento.piloto`, `rep` 0..n_sementes_piloto-1,
    os jogos do config), a regra de sementes e, para o orcamento do G4, o tempo
    de parede de uma unidade B8 da grade inteira por jogo nas duas condicoes
    (`n_workers` = 1, para o tempo ser de uma unidade so)."""
    ex = cfg["experimento"]
    pc = ex["piloto"]
    jogos = cfg["dados"]["jogos"]
    cfg_p = _trocar(cfg, posse__grade_r_pz_m=[ex["r0_m"]])
    unidades = [(pc["condicao"], g, v, pc["nivel"], rep) for v in pc["variantes"]
                for rep in range(_n_reps(cfg, v, ex["n_sementes_piloto"])) for g in jogos]
    t0 = time.perf_counter()
    pontos, lista = rodar_unidades(unidades, cfg_p, mapeamento, ex["n_workers"], pasta_cache)
    t_piloto = time.perf_counter() - t0
    conferir_n_gabarito(pontos)
    tabela = regra_sementes(pontos, cfg)
    print("=" * 78)
    print("PILOTO (R8): {} {}{}, R0 = {:g} m, rep 0..{}, jogos {}".format(
        pc["condicao"], "/".join(pc["variantes"]), pc["nivel"], ex["r0_m"], ex["n_sementes_piloto"] - 1, jogos))
    print(tabela.to_string(index=False, float_format="{:.4f}".format))
    fixas = _principal(pontos, cfg)
    fixas = fixas[fixas["variante"].isin(ex["variantes_sem_semente"]) & fixas["alvo"].isin(
        ALVOS_PRIMARIOS + ("corner_kick",))]
    if len(fixas):
        print("  variantes sem semente (rep 0, fora da regra):")
        print(agregar(fixas, ["condicao", "variante", "nivel", "alvo"])[
            ["variante", "nivel", "alvo", "tp_diag", "n_detectado", "n_gabarito", "f1"]].to_string(
                index=False, float_format="{:.4f}".format))
    print("  decisao: {} sementes (EP5 <= {} nos alvos primarios e nas variantes: {})".format(
        tabela["n_sementes_decidido"].iloc[0], ex["ep_max_f1"],
        bool(tabela.loc[tabela["decide"], "ep5_ok"].all())))
    cpu = sum(u["tempo_s"] for u in lista)
    print("  piloto: {} unidades ({} do cache), parede desta execucao {:.1f} s com {} workers; soma do tempo "
          "por unidade {:.1f} s (o do cache e o gravado quando a unidade foi calculada)".format(
              len(lista), sum(u["cache"] == "hit" for u in lista), t_piloto, ex["n_workers"], cpu))
    _gravar(tabela, saida / "piloto.csv")
    _gravar(pontos, saida / "piloto_pontos.csv")
    _gravar_manifesto(cfg_p, caminho_config, lista, saida / "manifesto_piloto.json")

    print("=" * 78)
    print("TEMPO POR UNIDADE DA GRADE INTEIRA (B8 rep 0, {} pontos de R_pz, n_workers = 1)".format(
        len(cfg["posse"]["grade_r_pz_m"])))
    medir = [(c, g, "B", 8, 0) for c in CONDICOES for g in jogos]
    _, lista_t = rodar_unidades(medir, cfg, mapeamento, 1, pasta_cache)
    tempos = _tempo_unidade(lista_t)
    print(tempos.to_string(index=False, float_format="{:.1f}".format))
    _gravar_manifesto(cfg, caminho_config, lista_t, saida / "manifesto_tempo.json")
    tab = orcamento(cfg, tempos, pasta_cache)
    if len(tab):          # nunca grava tabela vazia por cima da medida
        _gravar(tab, saida / "orcamento.csv")
    return tabela


def orcamento(cfg: dict, tempos: pd.DataFrame, pasta_cache) -> pd.DataFrame:
    """Unidades x tempo / `n_workers` por condicao, com `n_sementes` do config
    e com o teto do piloto (`n_sementes_piloto`). Tempo = a unidade B8 COMPLETA
    medida (todos os `R_pz`, politicas e lacuna 5), media e maximo por
    condicao; B8 tem os pontos de `fixo_1m`, que os niveis fora de
    `niveis_fixo_1m` nao tem, logo ate a media tende a superestimar. `com
    cache` desconta as unidades ja no cache. Unidade vinda do cache entra com o
    tempo gravado na entrada quando ela foi calculada."""
    ex = cfg["experimento"]
    w = ex["n_workers"]
    if tempos.empty:
        return pd.DataFrame()
    t = tempos.groupby("condicao")["tempo_s"].agg(["mean", "max"])
    src = hashes_src()
    linhas = []
    for n_sem in sorted({int(cfg["simulador"]["n_sementes"]), int(ex["n_sementes_piloto"])}):
        cfg_n = _trocar(cfg, simulador__n_sementes=n_sem)
        for c in CONDICOES:
            unid = grade(cfg_n, [c])
            no_cache = sum(1 for u in unid if pasta_cache is not None
                           and (Path(pasta_cache) / "{}.json".format(chave_unidade(cfg, u, src)[1])).exists())
            linha = {"n_sementes": n_sem, "condicao": c, "unidades": len(unid), "ja_no_cache": no_cache,
                     "t_medio_s": t.loc[c, "mean"], "t_max_s": t.loc[c, "max"]}
            for k in ("medio", "max"):
                tk = linha[f"t_{k}_s"]
                linha[f"cpu_h_{k}"] = len(unid) * tk / 3600
                linha[f"parede_h_{k}"] = len(unid) * tk / w / 3600
                linha[f"parede_h_{k}_com_cache"] = (len(unid) - no_cache) * tk / w / 3600
            linhas.append(linha)
    tab = pd.DataFrame(linhas)
    print("  ORCAMENTO DA GRADE R3 (n_workers = {}; tempo da unidade B8 completa, media e maximo):".format(w))
    print(tab.to_string(index=False, float_format="{:.2f}".format))
    for n_sem, b in tab.groupby("n_sementes"):
        rec = b[b["condicao"] == CONDICOES[0]]
        print("  n_sementes {}: sem bruto {:.2f}-{:.2f} h de parede ({:.2f}-{:.2f} h CPU); com bruto "
              "{:.2f}-{:.2f} h de parede ({:.2f}-{:.2f} h CPU) [media-maximo]".format(
                  n_sem, rec["parede_h_medio"].sum(), rec["parede_h_max"].sum(), rec["cpu_h_medio"].sum(),
                  rec["cpu_h_max"].sum(), b["parede_h_medio"].sum(), b["parede_h_max"].sum(),
                  b["cpu_h_medio"].sum(), b["cpu_h_max"].sum()))
    return tab


def unidades_eps_c(cfg: dict) -> list:
    """R7 com a emenda do plano 08 §8: `(eps_c, cfg, unidades)` para cada valor
    de `bola_parada.grade_eps_c_m`, no teto (nivel 1), condicao principal, so
    em `experimento.r0_m`."""
    r0 = cfg["experimento"]["r0_m"]
    return [(eps, _trocar(cfg, posse__grade_r_pz_m=[r0], bola_parada__eps_c_m=eps),
             [(CONDICOES[0], g, VARIANTE_TETO, 1, 0) for g in cfg["dados"]["jogos"]])
            for eps in cfg["bola_parada"]["grade_eps_c_m"]]


def cfg_idsse(cfg: dict, perfil: str = None) -> dict:
    """Copia do `cfg` para o experimento no IDSSE (plano 11 §4b e §7). O `cfg`
    de entrada (o da Metrica) nao muda.

    - `dados` = `{conjunto: idsse, perfil, rotulo, jogos: 1..7}`;
    - `simulador.semente_base` = `idsse_experimento.semente_base`: sementes
      `[20261107, jogo, rep]`; o resto do simulador (a calibracao da Metrica)
      fica congelado;
    - `avaliacao.criterio_principal` = `idsse.criterio_principal`;
    - `idsse_experimento.trocas` sobre `experimento` (condicoes, k/n do LOGO,
      sem curva de `eps_c`);
    - com `perfil`: `idsse.perfil_<perfil>` (`R0`, `eps_s`, `eps_v`;
      `teto_idsse.aplicar_perfil`) e o rotulo dele; sem, o rotulo da A."""
    from src import teto_idsse     # importa este modulo; aqui evita o ciclo
    ie = cfg["idsse_experimento"]
    fora = sorted(set(ie["trocas"]) - set(cfg["experimento"]))
    if fora:
        raise ValueError("idsse_experimento.trocas fora de `experimento`: {}".format(fora))
    c = copy.deepcopy(cfg) if perfil is None else teto_idsse.aplicar_perfil(cfg, perfil)
    c["dados"] = {"conjunto": "idsse", "perfil": perfil,
                  "rotulo": ie["rotulo"] if perfil is None else cfg["idsse"]["perfil_" + perfil]["rotulo"],
                  "jogos": list(range(1, len(cfg["idsse"]["jogos"]) + 1))}
    c["simulador"]["semente_base"] = ie["semente_base"]
    c["avaliacao"]["criterio_principal"] = cfg["idsse"]["criterio_principal"]
    c["experimento"].update(copy.deepcopy(ie["trocas"]))
    # TODO(divida): o plano 11 §7 diz "5 sementes"; a variante A continua so com
    # rep 0 (`experimento.variantes_sem_semente`, decisoes.md 2026-11-05: a
    # mascara de A nao depende da semente). E a maquina da Fatia 8 sem mudanca.
    return c


def saida_idsse(cfg: dict, perfil: str = None) -> Path:
    """Pasta do experimento no IDSSE: A sem perfil, a do perfil com ele."""
    ie = cfg["idsse_experimento"]
    return RAIZ_REPO / (ie["saida"] if perfil is None else ie["saida_perfil"][perfil])


def rodar_experimento(cfg: dict, mapeamento: dict, caminho_config: Path, saida: Path, pasta_cache) -> None:
    """A grade inteira (R3, `experimento.condicoes`, `simulador.n_sementes`), a
    selecao R6, a curva de `eps_c` (R7, se `experimento.curva_eps_c`) e a
    sensibilidade da ancora. Grava `pontos.csv`, `selecao_logo.csv`,
    `eps_c.csv`, `ancora.csv` e o `manifesto.json`. SO na rodada final (8b).
    No IDSSE, com o `cfg` de `cfg_idsse`."""
    ex = cfg["experimento"]
    pontos, lista = rodar_unidades(grade(cfg), cfg, mapeamento, ex["n_workers"], pasta_cache)
    conferir_n_gabarito(pontos)
    _gravar(pontos, saida / "pontos.csv")
    _gravar(selecionar_logo(pontos, cfg), saida / "selecao_logo.csv")
    _gravar(pontos[(pontos["nivel"] == 1) & (pontos["r_pz"] == ex["r0_m"])
                   & (pontos["politica"] == cfg["posse"]["r_dz_politica"])], saida / "ancora.csv")
    if ex["curva_eps_c"]:          # fora no IDSSE (plano 11 §7)
        curva = []
        for eps, cfg_e, unid in unidades_eps_c(cfg):
            p, l = rodar_unidades(unid, cfg_e, mapeamento, ex["n_workers"], pasta_cache)
            curva.append(p[(p["ancora"] == "frame") & p["alvo"].isin(["corner_kick", ALVO_MICRO])]
                         .assign(eps_c_m=eps))
            lista += [{**u, "eps_c_m": eps} for u in l]
        _gravar(pd.concat(curva, ignore_index=True), saida / "eps_c.csv")
    _gravar_manifesto(cfg, caminho_config, lista, saida / "manifesto.json")


# --- Fatia 9: apendice EXPLORATORIO (docs/fatias/09-plano.md) -------------------

def grade_exploratoria(cfg: dict, condicao: str) -> list:
    """Unidades da §1 do plano 09 numa condicao: o nivel 1 por jogo e os
    `exploratorio.niveis` de cada variante, com `simulador.n_sementes` sementes
    (rep 0 so nas `experimento.variantes_sem_semente`)."""
    jogos = cfg["dados"]["jogos"]
    out = [(condicao, g, VARIANTE_TETO, 1, 0) for g in jogos]
    for v, niveis in cfg["exploratorio"]["niveis"].items():
        out += [(condicao, g, v, int(k), rep) for k in niveis
                for rep in range(_n_reps(cfg, v, int(cfg["simulador"]["n_sementes"]))) for g in jogos]
    return out


def cfg_frente(cfg: dict, chave) -> dict:
    """Copia do `cfg` com a grade de `R_pz` = [R0], os estratos (frente A)
    ligados e, se `chave` nao for None, a chave da frente ligada. Uma chave
    por vez: as frentes nunca sao combinadas (plano 09 §2)."""
    c = _trocar(cfg, posse__grade_r_pz_m=[cfg["experimento"]["r0_m"]], exploratorio__estratos_apagao=True)
    if chave is not None:
        if chave not in EXPLORATORIO_LIDO or chave == "estratos_apagao":
            raise ValueError("frente com chave {!r} fora de {}".format(chave, EXPLORATORIO_LIDO[:3]))
        c["exploratorio"][chave] = True
    return c


def conferir_linha_base(base: pd.DataFrame, pontos_experimento: Path, cfg: dict) -> int:
    """A linha base (tudo desligado) tem de bater linha a linha, nas colunas do
    experimento, com `pontos_experimento` nas mesmas unidades, `R0` e politica
    principal (plano 09 §1). Estoura se nao bater; devolve o numero de linhas."""
    ref = pd.read_csv(pontos_experimento)
    colunas = list(ref.columns)
    b = base[colunas]
    ref = ref.merge(b[CHAVES_UNIDADE].drop_duplicates(), on=CHAVES_UNIDADE)
    ref = ref[(ref["r_pz"] == cfg["experimento"]["r0_m"]) & (ref["politica"] == cfg["posse"]["r_dz_politica"])]
    texto = [t.sort_values(CHAVES_PONTO, kind="stable").to_csv(index=False) for t in (b, ref)]
    if len(b) != len(ref) or texto[0] != texto[1]:
        raise RuntimeError("linha base nao reproduz {} ({} contra {} linhas)".format(
            pontos_experimento, len(b), len(ref)))
    return len(b)


def estratos_apagao(pontos: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """`apagao.csv` (frente A): linhas do criterio principal, ancora `frame`,
    politica principal, lacuna 5 com; contagens de estrato somadas sobre jogos
    e sementes por `(frente, condicao, variante, nivel, alvo)`, em formato
    longo por `estrato`. Revocacao = `tp_gab / n_gabarito` (eventos pelo
    estrato do evento); precisao = `tp_det / n_detectado` (deteccoes pelo
    estrato da deteccao); `frac_eventos` = `n_gabarito` do estrato / total."""
    p = _principal(pontos, cfg)
    p = p[p["alvo"].isin(list(cfg["avaliacao"]["grupos"]["bola_parada"]) + [ALVO_MICRO, ALVO_PASSE])]
    chaves = ["frente", "condicao", "variante", "nivel", "alvo"]
    soma = p.groupby(chaves, sort=True)[COLUNAS_ESTRATO].sum(min_count=1).reset_index()
    total = soma[[f"{e}_n_gabarito" for e in ESTRATOS]].sum(axis=1)
    blocos = []
    for e in ESTRATOS:
        b = soma[chaves].copy()
        b["estrato"] = e
        for c in ("n_gabarito", "tp_gab", "n_detectado", "tp_det"):
            b[c] = soma[f"{e}_{c}"]
        with np.errstate(invalid="ignore", divide="ignore"):
            b["revocacao"] = np.where(b["n_gabarito"] > 0, b["tp_gab"] / b["n_gabarito"], np.nan)
            b["precisao"] = np.where(b["n_detectado"] > 0, b["tp_det"] / b["n_detectado"], np.nan)
            # TODO(divida): o plano 09 §2.A pede "P/R/F1 por estrato" sem dizer
            # qual F1. Os acertos de P e de R podem cair em estratos diferentes
            # (par evento/deteccao que cruza a fronteira), logo nao ha um `tp`
            # unico para `2 tp / (n_det + n_gab)`; uso a media harmonica de P e
            # R, NaN se um dos dois for NaN. Decisao do codificador.
            pr = b["precisao"] + b["revocacao"]
            b["f1"] = np.where(pr > 0, 2 * b["precisao"] * b["revocacao"] / pr.where(pr > 0, 1), 0.0)
            b.loc[b["precisao"].isna() | b["revocacao"].isna(), "f1"] = np.nan
            b["frac_eventos"] = np.where(total > 0, b["n_gabarito"] / total.where(total > 0, 1), np.nan)
        blocos.append(b)
    out = pd.concat(blocos, ignore_index=True).sort_values(chaves + ["estrato"], kind="stable")
    out.loc[out["alvo"] == "penalty", ["revocacao", "precisao", "f1"]] = np.nan
    return out.reset_index(drop=True)


def rodar_exploratorio(cfg: dict, mapeamento: dict, caminho_config: Path, saida: Path, pasta_cache,
                       pontos_experimento: Path) -> None:
    """Plano 09: a `base` primeiro, conferida contra `pontos_experimento`
    (para se nao bater); depois cada frente com a sua chave, uma por vez.
    Grava em `saida`: `pontos.csv` (colunas do experimento + `frente`),
    `apagao.csv` (frente A) e `manifesto.json`. Nunca escreve fora de `saida`."""
    ex = cfg["experimento"]
    frentes = cfg["exploratorio"]["frentes"]
    if list(frentes)[0] != "base" or frentes["base"]["chave"] is not None:
        raise ValueError("exploratorio.frentes: a primeira tem de ser `base`, sem chave")
    pontos, lista = [], []
    for frente, f in frentes.items():
        unid = [u for c in f["condicoes"] for u in grade_exploratoria(cfg, c)]
        p, l = rodar_unidades(unid, cfg_frente(cfg, f["chave"]), mapeamento, ex["n_workers"], pasta_cache)
        conferir_n_gabarito(p)
        if frente == "base":
            n = conferir_linha_base(p, pontos_experimento, cfg)
            print("linha base: {} linhas identicas a {}".format(n, pontos_experimento))
        pontos.append(p.assign(frente=frente))
        lista += [{**u, "frente": frente} for u in l]
    todos = pd.concat(pontos, ignore_index=True)
    _gravar(todos.drop(columns=COLUNAS_ESTRATO), saida / "pontos.csv")
    _gravar(estratos_apagao(todos, cfg), saida / "apagao.csv")
    _gravar_manifesto(cfg, caminho_config, lista, saida / "manifesto.json")
    t = agregar(_principal(todos, cfg)[lambda d: d["alvo"].isin(ALVOS_PRIMARIOS)],
                ["frente", "condicao", "variante", "nivel", "alvo"])
    print(t[["frente", "condicao", "variante", "nivel", "alvo", "tp_diag", "n_detectado", "n_gabarito",
             "precisao", "revocacao", "f1"]].to_string(index=False, float_format="{:.4f}".format))
    print("CPU somada: {:.1f} s em {} unidades".format(sum(u["tempo_s"] for u in lista), len(lista)))


# --- tabelas e figuras (plano 08 §5): so le os CSV, nunca recalcula -------------

def papel(tabela: pd.DataFrame, cfg: dict) -> pd.Series:
    """`responde` nas linhas que respondem a pergunta do projeto (plano 08 §8,
    item 6: `experimento.resposta` -- alvos primarios, `reconstruido`, B5 e
    B8 -- no criterio principal, ancora `frame`, politica principal, com
    lacuna 5, nas colunas que existirem); `secundario` no resto."""
    r = cfg["experimento"]["resposta"]
    ok = (tabela["alvo"].isin(ALVOS_PRIMARIOS) & (tabela["condicao"] == r["condicao"])
          & (tabela["variante"] == r["variante"]) & tabela["nivel"].isin(r["niveis"]))
    for coluna, valor in (("criterio", cfg["avaliacao"]["criterio_principal"]), ("ancora", "frame"),
                          ("politica", cfg["posse"]["r_dz_politica"]), ("lacuna5", "com")):
        if coluna in tabela.columns:
            ok &= tabela[coluna] == valor
    return pd.Series(np.where(ok, "responde", "secundario"), index=tabela.index)


def tabelas_figuras(cfg: dict, saida: Path) -> None:
    """Le `pontos.csv`, `selecao_logo.csv` e `eps_c.csv` de `saida` e grava
    `saida/tabelas/tabela{1..5}.csv` e `saida/figuras/figura{1,2}.png` (sem
    `eps_c.csv` nem Tabela 4 se `experimento.curva_eps_c` for falso; com a
    coluna `rotulo` e o rotulo nos titulos se `dados` tiver `rotulo`). Toda
    agregacao passa por `agregar`. `penalty` sai so com contagens (P/R/F1 NaN).
    As Tabelas 1, 2, 3 e 5 levam a coluna `papel` (`responde`/`secundario`);
    a 4 (R7) e toda descritiva.
    A Figura 3 (vies de velocidade) esta fora do escopo (decisoes.md,
    2026-11-05): o 5(b) da Fatia 7 so existe no stdout do `--reconstrucao`.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ex = cfg["experimento"]
    r0 = float(ex["r0_m"])
    pontos = pd.read_csv(saida / "pontos.csv")
    selecao = pd.read_csv(saida / "selecao_logo.csv")
    tab_dir, fig_dir = saida / "tabelas", saida / "figuras"
    rotulo_cfg = cfg["dados"].get("rotulo")     # so no IDSSE (cfg_idsse)

    def gravar(tabela, destino):
        _gravar(tabela if rotulo_cfg is None else tabela.assign(rotulo=rotulo_cfg), destino)
    principal = _principal(pontos, cfg)
    rec = principal[(principal["condicao"] == CONDICOES[0]) & (principal["r_pz"] == r0)]

    def sem_f1_penalti(t):
        t.loc[t["alvo"] == "penalty", ["precisao", "revocacao", "f1"]] = np.nan
        return t

    t1 = sem_f1_penalti(agregar(rec, ["condicao", "variante", "nivel", "alvo"]))
    gravar(t1.assign(papel=papel(t1, cfg)), tab_dir / "tabela1.csv")
    gravar(selecao.assign(papel=papel(selecao, cfg)), tab_dir / "tabela2.csv")
    usados = selecao[["condicao", "variante", "nivel", "alvo", "r_estrela"]].drop_duplicates()
    t3 = agregar(principal[principal["alvo"] != "penalty"], ["condicao", "variante", "nivel", "alvo", "r_pz"])
    t3 = t3.merge(usados.rename(columns={"r_estrela": "r_pz"}).assign(papel_r_estrela=True), how="left")
    t3 = t3[(t3["r_pz"] == r0) | t3["papel_r_estrela"].fillna(False).astype(bool)]
    gravar(t3.assign(papel_r0=t3["r_pz"] == r0, papel=papel(t3, cfg)), tab_dir / "tabela3.csv")
    if ex["curva_eps_c"]:
        eps = pd.read_csv(saida / "eps_c.csv")
        jogos_vistos = eps["jogo"].isin([1, 2])
        t4 = pd.concat([agregar(eps[jogos_vistos], ["eps_c_m", "lacuna5", "criterio", "alvo"]).assign(jogos="1+2"),
                        agregar(eps[~jogos_vistos], ["eps_c_m", "lacuna5", "criterio", "alvo"]).assign(jogos="3")])
        gravar(t4.assign(papel="secundario"), tab_dir / "tabela4.csv")
    t5 = sem_f1_penalti(agregar(pontos, [c for c in CHAVES_PONTO if c not in SOMA_SOBRE]))
    gravar(t5.assign(papel=papel(t5, cfg)), tab_dir / "tabela5.csv")

    fig_dir.mkdir(parents=True, exist_ok=True)
    alvos = [a for a in rec["alvo"].unique() if a not in ("penalty", hierarquia.FREE_KICK_DUVIDA)]
    por_semente = agregar(rec, ["variante", "nivel", "rep", "alvo"])
    fig, eixos = plt.subplots(2, (len(alvos) + 1) // 2, figsize=(4 * ((len(alvos) + 1) // 2), 7), squeeze=False)
    for eixo, alvo in zip(eixos.flat, sorted(alvos)):
        for v, b in por_semente[por_semente["alvo"] == alvo].groupby("variante"):
            eixo.plot(b["taxa_todos"], b["f1"], "o", ms=3, label=v)
        eixo.set(title=alvo, xlabel="taxa amostrada", ylabel="F1", ylim=(0, 1))
        eixo.legend(fontsize=7)
    virg = lambda x, f="{:g}": f.format(x).replace(".", ",")   # decimal com virgula so na figura
    criterio = cfg["avaliacao"]["criterio_principal"]
    prefixo = "" if rotulo_cfg is None else rotulo_cfg + ": "
    fig.suptitle(prefixo + "F1 x taxa amostrada: condicao {}, criterio {}, ancora frame, R0 = {} m; "
                 "cada ponto e uma semente ({} jogos somados)".format(
                     CONDICOES[0], criterio, virg(r0), len(cfg["dados"]["jogos"])), fontsize=10)
    fig.tight_layout()
    fig.savefig(fig_dir / "figura1.png", dpi=120)
    plt.close(fig)
    sup = agregar(principal[(principal["condicao"] == CONDICOES[0]) & principal["alvo"].isin(ALVOS_PRIMARIOS)],
                  ["variante", "nivel", "alvo", "r_pz"])
    # o nivel 1 (teto, variante AB) entra como primeira linha dos paineis A e B
    grupos = sorted(sup.loc[sup["variante"] != VARIANTE_TETO, ["alvo", "variante"]].drop_duplicates()
                    .itertuples(index=False, name=None))
    fig, eixos = plt.subplots(1, len(grupos), figsize=(5 * len(grupos), 5), squeeze=False)
    for eixo, (alvo, v) in zip(eixos.flat, grupos):
        b = sup[(sup["alvo"] == alvo) & sup["variante"].isin([v, VARIANTE_TETO])]
        m = b.pivot(index="nivel", columns="r_pz", values="f1")
        taxa = b.groupby("nivel")["taxa_todos"].mean().reindex(m.index)
        rotulo = {n: (VARIANTE_TETO if n == 1 else v) + str(n) for n in m.index}
        z = m.to_numpy(dtype=float)
        # escala por painel: diferencas de 0,01-0,02 ficam visiveis
        im = eixo.imshow(z, aspect="auto", vmin=np.nanmin(z), vmax=np.nanmax(z), cmap="viridis")
        meio = (np.nanmin(z) + np.nanmax(z)) / 2
        for (i, j), f in np.ndenumerate(z):
            eixo.text(j, i, "nan" if np.isnan(f) else virg(f, "{:.3f}"), ha="center", va="center",
                      fontsize=7, color="white" if f < meio else "black")
        eixo.set(title="{} {}".format(alvo, v), xlabel="R_pz (m)", ylabel="nivel (taxa amostrada media)",
                 xticks=range(m.shape[1]), xticklabels=[virg(r) for r in m.columns],
                 yticks=range(m.shape[0]),
                 yticklabels=["{} ({})".format(rotulo[n], virg(t, "{:.2f}")) for n, t in taxa.items()])
        fig.colorbar(im, ax=eixo)
    fig.suptitle(prefixo + "F1(taxa, R_pz): condicao {}, criterio {}, lacuna 5 com, politica {}; "
                 "escala de cor por painel".format(CONDICOES[0], criterio, cfg["posse"]["r_dz_politica"]),
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(fig_dir / "figura2.png", dpi=120)
    plt.close(fig)
    print("gravado: {} (figura1.png, figura2.png)".format(fig_dir))

"""Auditoria EXPLORATORIA de erros no teto da Metrica (Fatia 10).

Plano normativo: `docs/fatias/10-plano.md`. Constantes em `config.yaml:auditoria`.

So DIAGNOSTICO: reusa o detector, o casador e os carregadores; nao muda nenhuma
regra, nao altera o gabarito e nenhuma categoria entra no F1. Ponto: teto, `R0`,
criterio principal (estrito), ancora `frame`, lacuna 5 com, politica principal
de `R_dz` -- a linha AB1 da `outputs/experimento/tabelas/tabela1.csv`, cujas
contagens a auditoria confere e, se nao baterem, para.

Categorias (plano §3), exaustivas e exclusivas, a primeira regra que se aplica:

  deteccao de bola parada (§3.1)   `tp`, `tipo_errado`, `jogador_errado`,
                                   `4a_saida`, `4b_falta`, `4c_buraco`, `4d_outro`
  reinicio do gabarito (§3.2)      `1_tp`, `2_outro_tipo`, `3_outro_jogador`,
                                   `4_sem_deteccao_na_ancora`, `5_sem_transicao`

"Na ancora" = o mesmo `frame` (primeiro quadro em jogo) no mesmo jogo: a
deteccao de bola parada e o gabarito ancorado moram ambos nele.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import evaluate, gabarito, possession, run
from src.events import bola_parada, passes as passes_mod

CATEGORIAS_DET = ("tp", "tipo_errado", "jogador_errado", "4a_saida", "4b_falta", "4c_buraco", "4d_outro")
CATEGORIAS_GAB = ("1_tp", "2_outro_tipo", "3_outro_jogador", "4_sem_deteccao_na_ancora", "5_sem_transicao")
NENHUM = "nenhum"


# --- casamento (o mesmo de evaluate.avaliar, criterio principal, ancora frame) --

def casar_principal(gab: pd.DataFrame, det: pd.DataFrame, cfg: dict):
    """(acerto_g, acerto_d): por posicao, o evento/deteccao casou na DIAGONAL
    (mesmo tipo) no criterio principal com o gabarito na ancora `frame`. E o
    acerto de `tp_diag` (o mesmo de `experiment._estado_executor`)."""
    eixos = cfg["avaliacao"]["criterios"][cfg["avaliacao"]["criterio_principal"]]
    grupo_de = evaluate.grupo_por_tipo(cfg)
    g = gab.reset_index(drop=True)
    g = g.assign(grupo=g["type"].map(grupo_de), t=g["frame"] / cfg["tracking"]["fps"])
    d = det.reset_index(drop=True)
    d = d.assign(grupo=d["type"].map(grupo_de))
    i_gab, i_det = evaluate.casar(g, d, eixos["janela_s"], eixos["casa_tipo"], eixos["casa_jogador"])
    diag = g["type"].to_numpy()[i_gab] == d["type"].to_numpy()[i_det]
    acerto_g, acerto_d = np.zeros(len(g), bool), np.zeros(len(d), bool)
    acerto_g[i_gab[diag]] = True
    acerto_d[i_det[diag]] = True
    return acerto_g, acerto_d


# --- evidencia da categoria 4 (§3.1) ------------------------------------------

def e_saida(crus: pd.DataFrame, cfg: dict) -> np.ndarray:
    """Linha crua e saida de bola (`auditoria.eventos_saida`)."""
    return crus["metrica_type"].isin(cfg["auditoria"]["eventos_saida"]).to_numpy()


def e_falta(crus: pd.DataFrame, cfg: dict, separador: str) -> np.ndarray:
    """Linha crua e falta: `auditoria.eventos_falta`, ou `CHALLENGE` com o atomo
    `FAULT` no subtipo (`auditoria.challenge_falta`)."""
    a = cfg["auditoria"]
    ch = a["challenge_falta"]
    com_falta = np.array([ch["atomo"] in gabarito._subtipos(s, separador) for s in crus["metrica_subtype"]],
                         dtype=bool)
    return (crus["metrica_type"].isin(a["eventos_falta"]).to_numpy()
            | ((crus["metrica_type"] == ch["type"]).to_numpy() & com_falta))


def evento_antes(f_inicio: np.ndarray, f_eventos: np.ndarray, janela_quadros: int) -> np.ndarray:
    """(n,) bool: ha evento com quadro em `[f_inicio - janela, f_inicio]`
    (inclusivo nos dois lados: "a <= janela ANTES do inicio")."""
    f = np.sort(np.asarray(f_eventos, dtype="int64"))
    f_inicio = np.asarray(f_inicio, dtype="int64")
    lo = np.searchsorted(f, f_inicio - janela_quadros, side="left")
    hi = np.searchsorted(f, f_inicio, side="right")
    return hi > lo


def fora_do_campo(x, y, cfg: dict) -> np.ndarray:
    """|x| > limite_x ou |y| > limite_y, sem margem; NaN nunca esta fora."""
    a = cfg["auditoria"]
    with np.errstate(invalid="ignore"):
        return (np.abs(np.asarray(x, float)) > a["limite_x_m"]) | (np.abs(np.asarray(y, float)) > a["limite_y_m"])


def subcategoria_sem_reinicio(fora, saida, falta, dur_morta_s, cfg: dict) -> np.ndarray:
    """4a a 4d, a primeira que se aplica (plano §3.1): saida (posicao fora ou
    `BALL OUT`) -> falta -> corrida morta < `corrida_curta_s` -> outro."""
    curta = np.asarray(dur_morta_s, float) < cfg["auditoria"]["corrida_curta_s"]
    saida_ou_fora = np.asarray(fora, bool) | np.asarray(saida, bool)
    return np.select([saida_ou_fora, np.asarray(falta, bool), curta],
                     ["4a_saida", "4b_falta", "4c_buraco"], "4d_outro")


# --- §3.1 e §3.2 ----------------------------------------------------------------

def categorizar_deteccoes(det: pd.DataFrame, gab: pd.DataFrame, acerto_d: np.ndarray, frames: pd.DataFrame,
                          crus: pd.DataFrame, cfg: dict, separador: str) -> pd.DataFrame:
    """Uma linha por deteccao de bola parada de UM jogo (`det` no esquema
    `bola_parada.DETECCOES`), com `categoria` (§3.1) e a evidencia: o
    reinicio anotado na ancora (tipo/jogador), o inicio da corrida morta, a
    ultima posicao da bola antes dela, e os eventos crus de saida/falta."""
    fps = cfg["tracking"]["fps"]
    a = cfg["auditoria"]
    fr = frames.sort_values("frame")
    d0, _, ids = bola_parada.corridas_mortas(fr["ball_live"].to_numpy())
    d0_de = pd.Series(d0, index=ids)
    i0 = d0_de.reindex(det["dead_run_id"]).to_numpy()
    if np.isnan(i0.astype(float)).any():
        raise ValueError("deteccao sem corrida morta conhecida")
    i0 = i0.astype("int64")
    f_inicio = fr["frame"].to_numpy()[i0]                  # primeiro quadro morto
    antes = np.maximum(i0 - 1, 0)
    bx = np.where(i0 > 0, fr["ball_x"].to_numpy()[antes], np.nan)
    by = np.where(i0 > 0, fr["ball_y"].to_numpy()[antes], np.nan)
    jan = round(a["janela_evento_cru_s"] * fps)
    f_cru = crus["annotated_frame"].to_numpy()
    saida = evento_antes(f_inicio, f_cru[e_saida(crus, cfg)], jan)
    falta = evento_antes(f_inicio, f_cru[e_falta(crus, cfg, separador)], jan)
    fora = fora_do_campo(bx, by, cfg)

    na_ancora = gab.groupby("frame")
    tipos_anc = na_ancora["type"].agg(lambda s: "|".join(sorted(s))).reindex(det["frame"]).fillna("")
    mesmo_tipo = np.array([t in tipos.split("|") for t, tipos in zip(det["type"], tipos_anc)], bool)
    tem_anc = (tipos_anc != "").to_numpy()
    jog_anc = na_ancora["player_id"].agg(lambda s: "|".join(sorted(s))).reindex(det["frame"]).fillna("")
    sub = subcategoria_sem_reinicio(fora, saida, falta, det["dur_morta_s"].to_numpy(), cfg)
    # TODO(divida): "jogador errado" (§3.1, 3) cobre tambem o caso, nao previsto
    # no plano, de mesmo tipo E mesmo jogador na ancora sem casar (o evento ja
    # casou com outra deteccao); a coluna `mesmo_jogador_na_ancora` o expoe.
    categoria = np.select([acerto_d, tem_anc & ~mesmo_tipo, tem_anc & mesmo_tipo],
                          ["tp", "tipo_errado", "jogador_errado"], sub)
    mesmo_jog = np.array([p != "" and p in js.split("|") for p, js in zip(det["player_id"], jog_anc)], bool)
    return pd.DataFrame({
        "game": det["game"].to_numpy(), "frame": det["frame"].to_numpy(), "type": det["type"].to_numpy(),
        "player_id": det["player_id"].to_numpy(), "via": det["via"].to_numpy(),
        "motivo_reserva1": det["motivo_reserva1"].to_numpy(), "dur_morta_s": det["dur_morta_s"].to_numpy(),
        "categoria": categoria, "tipos_na_ancora": tipos_anc.to_numpy(), "jogadores_na_ancora": jog_anc.to_numpy(),
        "mesmo_jogador_na_ancora": mesmo_jog, "inicio_morta_frame": f_inicio,
        "bola_antes_x": bx, "bola_antes_y": by, "bola_fora": fora, "ball_out_antes": saida, "falta_antes": falta,
    })


def categorizar_gabarito(gab: pd.DataFrame, det: pd.DataFrame, acerto_g: np.ndarray) -> pd.DataFrame:
    """Uma linha por reinicio do gabarito de UM jogo, com `categoria` (§3.2).
    Os `no_dead_ball_before` (sem transicao morta -> viva) vao para
    `5_sem_transicao` ANTES de qualquer outra regra (decisao do orquestrador:
    "os 13 ficam na categoria 5")."""
    por_quadro = det.set_index("frame")
    if por_quadro.index.duplicated().any():
        raise ValueError("duas deteccoes de bola parada no mesmo quadro")
    t_det = por_quadro["type"].reindex(gab["frame"]).to_numpy()
    p_det = por_quadro["player_id"].reindex(gab["frame"]).to_numpy()
    tem = pd.notna(t_det)
    mesmo_tipo = tem & (t_det == gab["type"].to_numpy())
    sem_transicao = gab["no_dead_ball_before"].to_numpy()
    # TODO(divida): o plano lista 5 por ultimo, mas manda os 13 inteiros para a
    # categoria 5; com 5 por ultimo um deles poderia sair como TP. Aplico 5
    # primeiro; `casou_na_diagonal` mostra se algum dos 13 casou.
    categoria = np.select([sem_transicao, acerto_g, tem & ~mesmo_tipo, mesmo_tipo],
                          ["5_sem_transicao", "1_tp", "2_outro_tipo", "3_outro_jogador"],
                          "4_sem_deteccao_na_ancora")
    return pd.DataFrame({
        "game": gab["game"].to_numpy(), "frame": gab["frame"].to_numpy(),
        "annotated_frame": gab["annotated_frame"].to_numpy(), "type": gab["type"].to_numpy(),
        "player_id": gab["player_id"].to_numpy(), "no_dead_ball_before": sem_transicao,
        "casou_na_diagonal": acerto_g, "categoria": categoria,
        "tipo_detectado_na_ancora": np.where(tem, t_det, ""), "jogador_detectado_na_ancora": np.where(tem, p_det, ""),
    })


def confusao(det_cat: pd.DataFrame, gab_cat: pd.DataFrame) -> pd.DataFrame:
    """§3.3: tipo detectado x tipo anotado nas ancoras em comum (mesmo jogo e
    `frame`), com a `via` da deteccao (estagio da hierarquia/reserva S1)."""
    m = det_cat[["game", "frame", "type", "via"]].merge(
        gab_cat[["game", "frame", "type"]], on=["game", "frame"], suffixes=("_detectado", "_anotado"))
    return (m.groupby(["game", "type_detectado", "type_anotado", "via"]).size()
            .rename("n").reset_index().rename(columns={"type_detectado": "tipo_detectado",
                                                       "type_anotado": "tipo_anotado"}))


# --- §3.4 passe ----------------------------------------------------------------

def _cru_mais_proximo(f_ref: np.ndarray, crus: pd.DataFrame, excluir=None, jogador=None, janela=None):
    """Para cada `f_ref[i]`: o evento cru de menor |dt| (empate: o anterior),
    opcionalmente so do `jogador[i]`, sem as linhas `excluir[i]` (conjunto de
    `row`), e a <= `janela` quadros. Saida: DataFrame (row, tipo, subtipo, dt)."""
    out = []
    f_cru = crus["annotated_frame"].to_numpy()
    for i, f in enumerate(f_ref):                      # ~500 por jogo, nao quadros
        ok = np.ones(len(crus), bool)
        if jogador is not None:
            ok &= (crus["player_id"] == jogador[i]).to_numpy()
        if excluir is not None:
            ok &= ~crus["row"].isin(excluir[i]).to_numpy()
        dt = f_cru - f
        if janela is not None:
            ok &= np.abs(dt) <= janela
        if not ok.any():
            out.append((-1, NENHUM, "", np.nan))
            continue
        k = np.flatnonzero(ok)
        k = k[np.lexsort((dt[k], np.abs(dt[k])))][0]
        out.append((int(crus["row"].iloc[k]), crus["metrica_type"].iloc[k], crus["metrica_subtype"].iloc[k],
                    float(dt[k])))
    return pd.DataFrame(out, columns=["cru_row", "cru_tipo", "cru_subtipo", "cru_dt_quadros"])


def passes_fn(ev: pd.DataFrame, pas: pd.DataFrame, acerto_g: np.ndarray, crus: pd.DataFrame,
              cfg: dict) -> pd.DataFrame:
    """§3.4: cada `pass` do gabarito nao casado, com a causa a-d
    (`run.decompor_fn`), o subtipo cru dele e o evento cru anotado mais
    proximo (qualquer jogador, sem as linhas cruas do proprio evento)."""
    gp = ev[ev["type"] == "pass"].reset_index(drop=True)
    fn = gp[~acerto_g].reset_index(drop=True)
    causa = run.decompor_fn(ev, pas, cfg)
    fn = fn.merge(causa[["game", "frame", "player_id", "causa", "desfecho"]],
                  on=["game", "frame", "player_id"], how="left", validate="one_to_one")
    if fn["causa"].isna().any() or len(causa) != len(fn):
        raise RuntimeError("passes_fn: FN sem causa ou causa sem FN")
    # TODO(divida): "o tipo do evento cru anotado mais proximo" (plano §3.4) e
    # lido como o evento cru mais proximo no tempo DIFERENTE das linhas do
    # proprio passe, de qualquer jogador e sem janela; o subtipo do proprio
    # passe vai em `metrica_subtype`.
    excluir = [set(int(r) for r in s.split(",")) for s in fn["source_rows"]]
    viz = _cru_mais_proximo(fn["annotated_frame"].to_numpy(), crus, excluir=excluir)
    return pd.concat([fn[["game", "frame", "player_id", "metrica_type", "metrica_subtype", "causa", "desfecho"]],
                      viz], axis=1)


def passes_fp(pp_c: pd.DataFrame, acerto_d: np.ndarray, crus: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """§3.4: cada passe detectado (principal) nao casado, com o evento cru mais
    proximo DO MESMO JOGADOR a <= `auditoria.janela_fp_passe_s` (ou `nenhum`)."""
    fp = pp_c[~acerto_d].reset_index(drop=True)
    jan = round(cfg["auditoria"]["janela_fp_passe_s"] * cfg["tracking"]["fps"])
    viz = _cru_mais_proximo(fp["frame"].to_numpy(), crus, jogador=fp["player_id"].to_numpy(), janela=jan)
    return pd.concat([fp[["game", "frame", "player_id", "team"]], viz], axis=1)


# --- um jogo ---------------------------------------------------------------------

def auditar_jogo(dados: dict, crus: pd.DataFrame, cfg: dict, separador: str) -> dict:
    """Roda o detector no teto de UM jogo no ponto AB1 e devolve as tabelas da
    auditoria e as contagens para a conferencia. `cfg` ja no ponto (R0)."""
    fr, trk, ev = dados["frames"], dados["tracking"], dados["eventos"]
    game = int(fr["game"].iloc[0])
    p1 = possession.calcular(fr, trk, cfg)
    b = {game: {"frames": fr, "tracking": trk, "periods": dados["periods"], "perdas": p1["perdas"],
                "ganhos": p1["ganhos"], "control": p1["control"]}}
    det = run.detectar_jogos(b, cfg, [game])
    pas = run.rotular_jogos(b, det, [game])
    tipos_bp = cfg["avaliacao"]["grupos"]["bola_parada"]
    gab_bp = ev[ev["type"].isin(tipos_bp)].reset_index(drop=True)
    ag, ad = casar_principal(gab_bp, bola_parada.para_casador(det), cfg)
    det_cat = categorizar_deteccoes(det, gab_bp, ad, fr, crus, cfg, separador)
    gab_cat = categorizar_gabarito(gab_bp, det, ag)
    pp_c = passes_mod.para_casador(pas, so_completo=True)
    gab_p = ev[ev["type"] == "pass"].reset_index(drop=True)
    pg, pd_ = casar_principal(gab_p, pp_c, cfg)
    return {"deteccoes_bp": det_cat, "gabarito_bp": gab_cat,
            "passes_fn": passes_fn(ev, pas, pg, crus, cfg), "passes_fp": passes_fp(pp_c, pd_, crus, cfg),
            "contagem_passe": (int(pg.sum()), len(pp_c), len(gab_p))}


# --- conferencia, resumo, amostra e PNG ----------------------------------------------

def conferir_ab1(det_cat: pd.DataFrame, gab_cat: pd.DataFrame, contagem_passe: tuple, tabela1: Path) -> pd.DataFrame:
    """As contagens da auditoria contra a linha AB1 de `tabela1` (plano §2): por
    tipo de bola parada (`tp_diag`, `n_detectado`, `n_gabarito`), a micro e o
    passe principal. Estoura se nao baterem; devolve a tabela conferida."""
    t1 = pd.read_csv(tabela1)
    t1 = t1[(t1["variante"] == "AB") & (t1["nivel"] == 1)].set_index("alvo")
    linhas = []
    tipos = sorted(set(det_cat["type"]) | set(gab_cat["type"]))
    for tipo in tipos:
        linhas.append((tipo, int(((det_cat["type"] == tipo) & (det_cat["categoria"] == "tp")).sum()),
                       int((det_cat["type"] == tipo).sum()), int((gab_cat["type"] == tipo).sum())))
    sem_pen_d, sem_pen_g = det_cat["type"] != "penalty", gab_cat["type"] != "penalty"
    linhas.append(("bola_parada_micro", int((sem_pen_d & (det_cat["categoria"] == "tp")).sum()),
                   int(sem_pen_d.sum()), int(sem_pen_g.sum())))
    linhas.append(("passe_principal",) + tuple(contagem_passe))
    tab = pd.DataFrame(linhas, columns=["alvo", "tp_diag", "n_detectado", "n_gabarito"]).set_index("alvo")
    ref = t1.reindex(tab.index)[["tp_diag", "n_detectado", "n_gabarito"]]
    if ref.isna().any().any() or not (ref.astype("int64") == tab).all().all():
        raise RuntimeError("auditoria nao reproduz a linha AB1 de {}:\n{}\n{}".format(tabela1, tab, ref))
    # o tp da auditoria pelo lado do gabarito tem de ser o mesmo
    tp_g = gab_cat[gab_cat["casou_na_diagonal"]].groupby("type").size()
    if not tp_g.reindex(tipos, fill_value=0).equals(tab.loc[tipos, "tp_diag"]):
        raise RuntimeError("auditoria: tp pelo gabarito difere do tp pelas deteccoes")
    return tab.reset_index()


def resumo(det_cat, gab_cat, fn, fp) -> pd.DataFrame:
    """Contagens por `tabela` x `categoria` x `game`, com todas as categorias
    (zero incluido) e o total `game = 0`."""
    blocos = []
    for nome, t, col, cats in (("3.1_deteccoes_bp", det_cat, "categoria", CATEGORIAS_DET),
                               ("3.2_gabarito_bp", gab_cat, "categoria", CATEGORIAS_GAB),
                               ("3.4_passe_fn_causa", fn, "causa", tuple("abcd")),
                               ("3.4_passe_fp", fp.assign(c="fp"), "c", ("fp",))):
        jogos = sorted(t["game"].unique())
        n = t.groupby(["game", col]).size().reindex(pd.MultiIndex.from_product([jogos, cats]), fill_value=0)
        b = n.rename("n").reset_index()
        b.columns = ["game", "categoria", "n"]
        tot = b.groupby("categoria", sort=False)["n"].sum().reset_index().assign(game=0)
        blocos.append(pd.concat([b, tot], ignore_index=True).assign(tabela=nome))
    return pd.concat(blocos, ignore_index=True)[["tabela", "categoria", "game", "n"]]


def amostrar(casos: pd.DataFrame, coluna: str, n: int, semente: int) -> pd.DataFrame:
    """Ate `n` casos por valor de `coluna`, sem reposicao, com
    `np.random.default_rng(semente)`; categorias em ordem alfabetica e casos
    na ordem de entrada: o sorteio so depende da semente e da tabela."""
    rng = np.random.default_rng(semente)
    out = []
    for cat in sorted(casos[coluna].unique()):
        sub = casos[casos[coluna] == cat]
        k = rng.choice(len(sub), size=min(n, len(sub)), replace=False)
        out.append(sub.iloc[np.sort(k)])
    return pd.concat(out) if out else casos.iloc[:0]


def desenhar_caso(dados: dict, crus: pd.DataFrame, f_centro: int, titulo: str, destino: Path,
                  cfg: dict, destaque: str = "") -> None:
    """PNG com bola e jogadores em `f_centro +- auditoria.janela_png_s` e a lista
    dos eventos crus da janela (§3.5). `destaque`: o jogador marcado."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fps = cfg["tracking"]["fps"]
    jan = round(cfg["auditoria"]["janela_png_s"] * fps)
    lo, hi = f_centro - jan, f_centro + jan
    fr, trk = dados["frames"], dados["tracking"]
    fj = fr[fr["frame"].between(lo, hi)]
    tj = trk[trk["frame"].between(lo, hi)]
    L, W = cfg["campo"]["comprimento_m"], cfg["campo"]["largura_m"]
    fig, (ax, tx) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [3, 1.3]})
    ax.add_patch(plt.Rectangle((-L / 2, -W / 2), L, W, fill=False, color="gray"))
    ax.axvline(0, color="gray", lw=0.5)
    cores = {"home": "tab:red", "away": "tab:blue"}
    for (pid, team), s in tj.groupby(["player_id", "team"]):
        ax.plot(s["x"], s["y"], "-", color=cores.get(team, "k"), lw=0.6, alpha=0.5)
        agora = s[s["frame"] == f_centro]
        if len(agora):
            ax.plot(agora["x"], agora["y"], "o", color=cores.get(team, "k"), ms=8 if pid == destaque else 4,
                    mec="k" if pid == destaque else "none")
            ax.annotate(pid.split("_")[-1], (agora["x"].iloc[0], agora["y"].iloc[0]), fontsize=6)
    ax.plot(fj["ball_x"], fj["ball_y"], "k.-", lw=0.8, ms=2)
    b = fj[fj["frame"] == f_centro]
    if len(b):
        ax.plot(b["ball_x"], b["ball_y"], "k*", ms=12)
    ax.set(xlim=(-L / 2 - 5, L / 2 + 5), ylim=(-W / 2 - 5, W / 2 + 5), aspect="equal", title=titulo)
    ax.title.set_fontsize(9)
    cr = crus[crus["annotated_frame"].between(lo, hi)]
    texto = "\n".join("{:+.2f} s  {} / {}  {}".format((r.annotated_frame - f_centro) / fps, r.metrica_type,
                                                     r.metrica_subtype, r.player_id) for r in cr.itertuples())
    vivo = fj["ball_live"].to_numpy()
    tx.axis("off")
    tx.text(0, 1, "eventos crus em +-{:g} s:\n{}\n\nquadros vivos na janela: {}/{}".format(
        cfg["auditoria"]["janela_png_s"], texto or "(nenhum)", int(vivo.sum()), vivo.size),
        va="top", fontsize=7, family="monospace")
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(destino, dpi=90)
    plt.close(fig)


# --- modo --auditoria -------------------------------------------------------------

def rodar_auditoria(cfg: dict, mapeamento: dict, caminho_config: Path, saida: Path, tabela1: Path) -> None:
    """Plano 10 §5: roda os jogos de `dados.jogos` no ponto AB1, confere
    contra `tabela1`, grava os CSV, o resumo, os PNGs da amostra e o manifesto
    em `saida`."""
    from src import experiment
    a = cfg["auditoria"]
    c = run.com_r_pz(cfg, float(cfg["experimento"]["r0_m"]), cfg["posse"]["r_dz_politica"])
    sep = mapeamento["separador_subtipo_csv"]
    jogos = cfg["dados"]["jogos"]
    base = run._base_leve(c, mapeamento, jogos)
    partes, crus_de, cont_p = {}, {}, np.zeros(3, "int64")
    for g in jogos:
        crus_de[g] = gabarito.carregar_eventos_crus(g, c, mapeamento)
        r = auditar_jogo(base[g], crus_de[g], c, sep)
        for k, v in r.items():
            if k == "contagem_passe":
                cont_p += np.asarray(v)
            else:
                partes.setdefault(k, []).append(v)
    t = {k: pd.concat(v, ignore_index=True) for k, v in partes.items()}
    conferida = conferir_ab1(t["deteccoes_bp"], t["gabarito_bp"], tuple(int(v) for v in cont_p), tabela1)
    print("contagens AB1 conferidas com {}:\n{}".format(tabela1, conferida.to_string(index=False)))
    saida.mkdir(parents=True, exist_ok=True)
    conf = confusao(t["deteccoes_bp"], t["gabarito_bp"])
    res = resumo(t["deteccoes_bp"], t["gabarito_bp"], t["passes_fn"], t["passes_fp"])
    for nome, tab in (("deteccoes_bp", t["deteccoes_bp"]), ("gabarito_bp", t["gabarito_bp"]),
                      ("confusao_bp", conf), ("passes_fp", t["passes_fp"]), ("passes_fn", t["passes_fn"]),
                      ("resumo", res), ("conferencia_ab1", conferida)):
        experiment._gravar(tab, saida / f"{nome}.csv")

    # §3.5: amostra visual
    n, semente = int(a["amostra_por_categoria"]), int(a["semente"])
    casos = pd.concat([
        t["deteccoes_bp"].assign(grupo="det_" + t["deteccoes_bp"]["categoria"], destaque=t["deteccoes_bp"]["player_id"]),
        t["gabarito_bp"].assign(grupo="gab_" + t["gabarito_bp"]["categoria"], destaque=t["gabarito_bp"]["player_id"]),
        t["passes_fn"].assign(grupo="passe_fn_" + t["passes_fn"]["causa"], destaque=t["passes_fn"]["player_id"]),
        t["passes_fp"].assign(grupo="passe_fp", destaque=t["passes_fp"]["player_id"]),
    ], ignore_index=True)[["grupo", "game", "frame", "type", "destaque", "categoria", "causa"]]
    amostra = amostrar(casos, "grupo", n, semente)
    pasta = saida / "casos"
    for r in amostra.itertuples():
        nome = "{}_j{}_q{}.png".format(r.grupo, r.game, r.frame)
        titulo = "{} | jogo {} quadro {} | {} {}".format(r.grupo, r.game, r.frame,
                                                       r.type if isinstance(r.type, str) else "pass", r.destaque)
        desenhar_caso(base[r.game], crus_de[r.game], int(r.frame), titulo, pasta / nome, c, r.destaque)
    experiment._gravar(amostra, saida / "amostra.csv")
    m = experiment.manifesto(c, caminho_config, [])
    m.pop("unidades")
    m.update({"semente_amostra": semente, "amostra_por_categoria": n, "n_png": len(amostra),
              "tabela1": str(tabela1), "sha256_tabela1": experiment._sha(Path(tabela1))})
    (saida / "manifesto.json").write_text(json.dumps(m, indent=1, default=str), encoding="utf-8")
    print("gravado: {} ({} PNGs em {})".format(saida / "manifesto.json", len(amostra), pasta))
    for nome in ("3.1_deteccoes_bp", "3.2_gabarito_bp", "3.4_passe_fn_causa"):
        print(res[res["tabela"] == nome].pivot(index="categoria", columns="game", values="n").to_string())

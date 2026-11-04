"""Simulador de broadcast (Fatia 6): o tracking que uma camera de TV teria visto.

Plano normativo: `docs/fatias/06-plano.md`. Constantes em `config.yaml:simulador`.

- Saida = SUBCONJUNTO das linhas de `tracking`, colunas identicas. Jogador fora
  da visao nao tem linha. `visible` NAO e tocado (docs/02: False = imputado).
- `frames`, `periods` e `events` nunca sao tocados: sao oraculo declarado.
- Variante A: janela fixa L x L centrada no alvo da camera, sem cortes.
- Variante B: cunha 2D de abertura theta a partir de uma camera fixa em
  `(0, -(W/2 + d_cam))`, mais cortes editoriais por uma cadeia de Markov de dois
  estados com acoplamento monotono em `c` (plano §4.3).
- Semente: `SeedSequence([semente_base, game, rep])`, nunca dependente de nivel
  nem de variante (numeros aleatorios comuns). Nenhum uso de `np.random` global.

Este modulo nao avalia nada: nao importa `src.evaluate` (plano §6, teste T12).
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.signal import butter, filtfilt, savgol_filter

from src.events import gatilhos
from src.events.bola_parada import corridas_mortas
from src.io.schema import TRACKING, validar

PAPEIS = ("GK", "DEF", "MID", "OFF")
VARIANTES = ("A", "B")


# --- utilitarios de grade -------------------------------------------------

def _limites_periodo(frames: pd.DataFrame):
    """(inicio, fim) das linhas de cada (game, period); exige `frames` ordenado
    por (game, frame) com `frame` = 1..N contiguo em cada jogo."""
    g = frames["game"].to_numpy()
    f = frames["frame"].to_numpy()
    jogo_novo = np.r_[True, g[1:] != g[:-1]]
    if (np.diff(g) < 0).any() or (f[jogo_novo] != 1).any() or \
            (np.diff(f)[~jogo_novo[1:]] != 1).any():
        raise ValueError("frames tem de estar ordenado por (game, frame), 1..N contiguo")
    p = frames["period"].to_numpy()
    novo = jogo_novo | np.r_[True, p[1:] != p[:-1]]
    inicio = np.flatnonzero(novo)
    return inicio, np.r_[inicio[1:], g.size]


# --- alvo da camera (§4.1) -------------------------------------------------

def alvo_camera(frames: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Ponto para onde a camera aponta, por quadro.

    Entrada: `frames` no esquema FRAMES (um ou mais jogos, ordenado por
    (game, frame)). Saida: DataFrame `game, period, frame, cx, cy` (m), mesma
    ordem e tamanho de `frames`, nunca NaN.

    Por periodo: bola nos quadros vivos; interpolacao linear na corrida morta;
    corrida morta na borda do periodo fica na primeira/ultima posicao viva
    (`np.interp` faz as duas coisas). Depois Savitzky-Golay em x e y.
    """
    s = cfg["simulador"]
    vivo = frames["ball_live"].to_numpy()
    bx, by = frames["ball_x"].to_numpy(), frames["ball_y"].to_numpy()
    cx, cy = np.empty(vivo.size), np.empty(vivo.size)
    for i0, i1 in zip(*_limites_periodo(frames)):
        v = vivo[i0:i1]
        if not v.any():
            raise ValueError("periodo sem nenhum quadro vivo: alvo da camera indefinido")
        k = np.arange(i1 - i0)
        for bruto, saida in ((bx, cx), (by, cy)):
            # LACUNA: modo de borda do Savitzky-Golay nao vem do Bassek; usado o
            # padrao do scipy ('interp'). Descartado: 'nearest'/'mirror'.
            saida[i0:i1] = savgol_filter(
                np.interp(k, k[v], bruto[i0:i1][v]), s["sg_janela"], s["sg_grau"]
            )
    return pd.DataFrame({"game": frames["game"].to_numpy(), "period": frames["period"].to_numpy(),
                         "frame": frames["frame"].to_numpy(), "cx": cx, "cy": cy})


# --- geometria (§4.2, §4.3) -------------------------------------------------

def angulo_cunha(x, y, cx, cy, d_cam_m: float, cfg: dict):
    """Angulo (graus, em [0, 180]) entre `(p - camera)` e `(alvo - camera)`,
    com a camera em `(0, -(W/2 + d_cam))`. Elemento a elemento."""
    cam_y = -(cfg["campo"]["largura_m"] / 2.0 + d_cam_m)
    uy, vy = np.asarray(y) - cam_y, np.asarray(cy) - cam_y
    ux, vx = np.asarray(x), np.asarray(cx)
    return np.degrees(np.abs(np.arctan2(ux * vy - uy * vx, ux * vx + uy * vy)))


def na_cunha(x, y, cx, cy, theta_graus: float, d_cam_m: float, cfg: dict):
    """bool: o ponto esta na cunha de abertura `theta` (inclusiva). `theta = inf`
    deixa tudo dentro pelo mesmo caminho."""
    return angulo_cunha(x, y, cx, cy, d_cam_m, cfg) <= theta_graus / 2.0


def _dist_janela(x, y, cx, cy):
    """Distancia de Chebyshev ao alvo (m)."""
    return np.maximum(np.abs(np.asarray(x) - cx), np.abs(np.asarray(y) - cy))


def na_janela(x, y, cx, cy, L_m: float):
    """bool: `|x - cx| <= L/2` e `|y - cy| <= L/2` (borda inclusiva). `L = inf`
    deixa tudo dentro pelo mesmo caminho."""
    return _dist_janela(x, y, cx, cy) <= L_m / 2.0


# --- cortes (§4.3) -----------------------------------------------------------

def _entrada(frames: pd.DataFrame, params: dict, c: float) -> np.ndarray:
    """(n,) `q(on) = c * a_s`, com a checagem do acoplamento `c a_s <= 1 - b`."""
    a = c * np.where(frames["ball_live"].to_numpy(), params["a_vivo"], params["a_morto"])
    if (a > 1.0 - params["b"]).any():
        raise ValueError("acoplamento violado: c * a_s > 1 - b (plano 06 §4.3)")
    return a


def p_off(frames: pd.DataFrame, params: dict, c: float) -> np.ndarray:
    """(n,) `P(off_t)` exato: `p_t = (1 - p_{t-1}) c a_{s_t} + p_{t-1} (1 - b)`,
    com `p = 0` antes do primeiro quadro de cada (game, period).

    Entrada: `frames` (FRAMES, ordenado), `params` com `a_vivo`, `a_morto`, `b`.
    Forma fechada por corrida de estado constante (laco por corrida, nao por
    quadro): `p_t = p* + (p_0 - p*) alpha^k`, `alpha = 1 - b - c a`, `p* = c a / (1 - alpha)`.
    """
    beta = _entrada(frames, params, c)
    alpha = 1.0 - params["b"] - beta
    vivo = frames["ball_live"].to_numpy()
    inicio_p, _ = _limites_periodo(frames)
    quebra = np.r_[True, vivo[1:] != vivo[:-1]]
    quebra[inicio_p] = True
    ini = np.flatnonzero(quebra)
    fim = np.r_[ini[1:], vivo.size]
    zera = np.zeros(vivo.size, dtype=bool)
    zera[inicio_p] = True
    p = np.empty(vivo.size)
    anterior = 0.0
    for i0, i1 in zip(ini, fim):
        if zera[i0]:
            anterior = 0.0
        al, be = alpha[i0], beta[i0]
        k = np.arange(1, i1 - i0 + 1)
        if 1.0 - al > 0.0:
            estrela = be / (1.0 - al)
            p[i0:i1] = estrela + (anterior - estrela) * al ** k
        else:                       # b = 0 e c a = 0: estado congelado
            p[i0:i1] = anterior
        anterior = p[i1 - 1]
    return p


def uniformes(n: int, semente) -> np.ndarray:
    """(n,) U[0,1) de `SeedSequence(semente)`; `semente` = `[base, game, rep]`."""
    return np.random.default_rng(np.random.SeedSequence(semente)).random(n)


def amostrar_off(frames: pd.DataFrame, params: dict, c: float, semente) -> np.ndarray:
    """(n,) bool `off_t = u_t < q(estado_{t-1})`, estado `on` antes de cada periodo.

    Vetorizado: como `c a_s <= 1 - b`, `u < c a_s` (entra) implica `u < 1 - b`
    (fica). Logo o quadro com `entra` ou com `nao fica` e DECISIVO (off = entra,
    seja qual for o estado anterior) e os demais repetem o anterior: `off` e o
    `entra` do ultimo quadro decisivo do periodo, ou False se nao houve. Isso e
    monotono em `c` com os mesmos `u` (aninhamento, teste T3).
    """
    a = _entrada(frames, params, c)
    u = uniformes(a.size, semente)
    entra = u < a
    decisivo = entra | ~(u < 1.0 - params["b"])
    idx = np.arange(a.size)
    ultimo = np.maximum.accumulate(np.where(decisivo, idx, -1))
    inicio_p, fim_p = _limites_periodo(frames)
    inicio = np.repeat(inicio_p, fim_p - inicio_p)
    return (ultimo >= inicio) & entra[np.maximum(ultimo, 0)]


# --- papeis (§4.4 passo 2) ----------------------------------------------------

def papeis(tracking: pd.DataFrame, periods: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Papel de cada jogador por (jogo, time).

    Entrada: `tracking` (TRACKING) e `periods` (PERIODS), um ou mais jogos.
    Saida: DataFrame `game, team, player_id, papel, x_medio` (x_medio em m, no
    sentido de ataque: media de `x * attack_dir` nos quadros presentes).
    Jogadores de linha ordenados por `x_medio`; `q = (posto - 0,5)/n`; DEF se
    `q < DEF/total`, OFF se `q > 1 - OFF/total`, MID nos demais. GK de `is_gk`.
    Empate de `x_medio` decidido por `player_id` (deterministico).
    """
    soma = (
        tracking.groupby(["game", "team", "player_id", "period"], sort=True)
        .agg(sx=("x", "sum"), n=("x", "size"), gk=("is_gk", "max"))
        .reset_index()
        .merge(periods[["game", "period", "team", "attack_dir"]], how="left",
               on=["game", "period", "team"], validate="many_to_one")
    )
    if soma["attack_dir"].isna().any():
        raise ValueError("periods sem attack_dir para algum (jogo, periodo, time)")
    soma["sx"] = soma["sx"] * soma["attack_dir"]
    jog = soma.groupby(["game", "team", "player_id"], sort=True).agg(
        sx=("sx", "sum"), n=("n", "sum"), gk=("gk", "max")).reset_index()
    jog["x_medio"] = jog["sx"] / jog["n"]
    prop = cfg["simulador"]["proporcoes_papel"]
    total = float(sum(prop.values()))
    linha = jog[~jog["gk"]].sort_values(["game", "team", "x_medio", "player_id"])
    grupo = linha.groupby(["game", "team"], sort=False)
    q = (grupo.cumcount().to_numpy() + 0.5) / grupo["player_id"].transform("size").to_numpy()
    papel = pd.Series("GK", index=jog.index, dtype=object)
    papel.loc[linha.index] = np.where(
        q < prop["DEF"] / total, "DEF", np.where(q > 1.0 - prop["OFF"] / total, "OFF", "MID"))
    jog["papel"] = papel
    return jog[["game", "team", "player_id", "papel", "x_medio"]].reset_index(drop=True)


# --- distancia percorrida (§4.4 passo 3) ------------------------------------

def passos(tracking: pd.DataFrame, cfg: dict):
    """Comprimento do passo filtrado que CHEGA em cada linha.

    Entrada: `tracking` (TRACKING), um ou mais jogos. Saida: (`passo_m` (n,)
    alinhado as linhas de `tracking`, 0 na primeira linha de cada segmento;
    `n_curtos`, `n_segmentos`). Segmento = presenca contigua de um jogador num
    periodo. Butterworth com `filtfilt` por segmento; segmento com tamanho <=
    `padlen` padrao (3 * max(len(a), len(b))) usa `padlen = len - 1` e conta em
    `n_curtos`.
    """
    s = cfg["simulador"]
    b, a = butter(s["butter_ordem"], s["butter_corte_hz"], fs=cfg["tracking"]["fps"])
    pad_padrao = 3 * max(len(a), len(b))
    codigo = pd.factorize(tracking["player_id"])[0]
    g = tracking["game"].to_numpy()
    f = tracking["frame"].to_numpy()
    ordem = np.lexsort((f, codigo, g))
    g, f, codigo = g[ordem], f[ordem], codigo[ordem]
    per = tracking["period"].to_numpy()[ordem]
    x = tracking["x"].to_numpy()[ordem]
    y = tracking["y"].to_numpy()[ordem]
    quebra = np.r_[True, (g[1:] != g[:-1]) | (codigo[1:] != codigo[:-1])
                   | (per[1:] != per[:-1]) | (np.diff(f) != 1)]
    ini = np.flatnonzero(quebra)
    fim = np.r_[ini[1:], f.size]
    fx, fy = x.copy(), y.copy()
    curtos = 0
    for i0, i1 in zip(ini, fim):
        m = i1 - i0
        pad = pad_padrao
        if m <= pad_padrao:
            curtos += 1
            pad = m - 1
        if m >= 2:
            fx[i0:i1] = filtfilt(b, a, x[i0:i1], padlen=pad)
            fy[i0:i1] = filtfilt(b, a, y[i0:i1], padlen=pad)
    d = np.r_[0.0, np.hypot(np.diff(fx), np.diff(fy))]
    d[quebra] = 0.0
    passo = np.empty(f.size)
    passo[ordem] = d
    return passo, curtos, int(ini.size)


# --- degradacao ----------------------------------------------------------------

def _nivel(cfg: dict, variante: str, nivel: int) -> dict:
    if variante not in VARIANTES:
        raise ValueError("variante {} fora de {}".format(variante, VARIANTES))
    niveis = cfg["simulador"]["calibrado"]["niveis"][variante]
    if not 1 <= nivel <= len(niveis):
        raise ValueError("nivel {} fora de 1..{}".format(nivel, len(niveis)))
    return niveis[nivel - 1]


def semente_efetiva(cfg: dict, game: int, rep: int) -> list:
    """`[semente_base, game, rep]`, a entropia do `SeedSequence` (plano §5)."""
    return [int(cfg["simulador"]["semente_base"]), int(game), int(rep)]


def mascara(tracking, frames, cfg: dict, variante: str, nivel: int, semente: int) -> np.ndarray:
    """(n_linhas,) bool: a linha de `tracking` fica visivel no nivel.

    Entrada: `tracking` e `frames` de UM jogo (`carregar_jogo`); `semente` = rep
    (0..n_sementes-1), obrigatoria. Parametros do nivel e dos cortes em
    `cfg['simulador']['calibrado']`.
    """
    s = cfg["simulador"]
    lv = _nivel(cfg, variante, nivel)
    alvo = alvo_camera(frames, cfg)
    if frames["game"].nunique() != 1:
        raise ValueError("mascara: um jogo por vez")
    i = tracking["frame"].to_numpy() - 1
    x, y = tracking["x"].to_numpy(), tracking["y"].to_numpy()
    cx, cy = alvo["cx"].to_numpy()[i], alvo["cy"].to_numpy()[i]
    if variante == "A":
        return na_janela(x, y, cx, cy, lv["L_m"])
    geo = na_cunha(x, y, cx, cy, lv["theta_graus"], s["d_cam_m"], cfg)
    game = int(frames["game"].iloc[0])
    off = amostrar_off(frames, s["calibrado"], lv["c"], semente_efetiva(cfg, game, semente))
    return geo & ~off[i]


def degradar(tracking, frames, cfg: dict, variante: str, nivel: int, semente: int) -> pd.DataFrame:
    """`tracking` degradado: o subconjunto das linhas visiveis, colunas e indice
    originais (nada e reescrito). Entrada como em `mascara`. Saida no esquema
    TRACKING."""
    m = mascara(tracking, frames, cfg, variante, nivel, semente)
    return validar(tracking[m], TRACKING, "tracking degradado")


# --- calibracao (§4.4) --------------------------------------------------------

def _linhas(base: dict, cfg: dict, jogos) -> dict:
    """Junta os jogos: `frames` concatenado e arrays por linha de tracking."""
    frames, lateral = cortes_juntos(base, jogos)
    track, alvos, off = [], [], 0
    for g in jogos:
        fr, tr = base[g]["frames"], base[g]["tracking"]
        track.append(tr.assign(_iq=tr["frame"].to_numpy() - 1 + off))
        alvos.append(alvo_camera(fr, cfg))
        off += len(fr)
    tr = pd.concat(track, ignore_index=True)
    alvo = pd.concat(alvos, ignore_index=True)
    iq = tr["_iq"].to_numpy()
    papel = papeis(tr, pd.concat([base[g]["periods"] for g in jogos]), cfg)
    passo, curtos, n_seg = passos(tr, cfg)
    return {
        "frames": frames,
        "iq": iq,
        "x": tr["x"].to_numpy(), "y": tr["y"].to_numpy(),
        "cx": alvo["cx"].to_numpy()[iq], "cy": alvo["cy"].to_numpy()[iq],
        "gk": tr["is_gk"].to_numpy(),
        "vivo": frames["ball_live"].to_numpy()[iq],
        "time": (tr["team"].to_numpy() == "home").astype("int64"),
        "papel": tr["player_id"].map(papel.set_index("player_id")["papel"]).to_numpy(),
        "papeis": papel,
        "passo": passo, "n_curtos": curtos, "n_segmentos": n_seg,
        "lateral": lateral,
    }


def _alvos_cortes(cfg: dict) -> np.ndarray:
    a = cfg["simulador"]["alvos"]
    return np.array([
        a["frac_ativo_quando_0"] * a["frac_0_visiveis"] / a["frac_ativo"],
        a["frac_parado_quando_0"] * a["frac_0_visiveis"] / a["frac_parado"],
        a["p_off_lateral"],
    ])


def _obtidos_cortes(frames, lateral, params, p=None) -> np.ndarray:
    p = p_off(frames, params, 1.0) if p is None else p
    vivo = frames["ball_live"].to_numpy()
    return np.array([p[vivo].mean(), p[~vivo].mean(), p[lateral].mean()])


def transicoes(frames: pd.DataFrame, params: dict, c: float, p=None):
    """(entra, sai) (n,): probabilidade de a cadeia passar on -> off e off -> on
    no quadro t, `(1 - p_{t-1}) c a_s` e `p_{t-1} b`, com `p = 0` antes de cada
    periodo (a saida do `on` inicial conta). `p` opcional: o `p_off` ja calculado."""
    p = p_off(frames, params, c) if p is None else p
    anterior = np.r_[0.0, p[:-1]]
    anterior[_limites_periodo(frames)[0]] = 0.0
    return (1.0 - anterior) * _entrada(frames, params, c), anterior * params["b"]


def trocas_por_minuto(frames: pd.DataFrame, params: dict, c: float, fps: float, p=None) -> float:
    """Trocas on<->off ESPERADAS por minuto: soma de `entra + sai`
    (`transicoes`) sobre todos os quadros, sobre a duracao."""
    entra, sai = transicoes(frames, params, c, p)
    return float((entra + sai).sum() / (len(frames) / fps / 60.0))


def cortes_juntos(base: dict, jogos) -> tuple:
    """(frames concatenado dos `jogos`, indices nele das ancoras `frame` das
    laterais do gabarito): a entrada de `calibrar_cortes`."""
    frames, lat, off = [], [], 0
    for g in jogos:
        fr, ev = base[g]["frames"], base[g]["eventos"]
        frames.append(fr)
        lat.append(ev.loc[ev["type"] == "throw_in", "frame"].to_numpy() - 1 + off)
        off += len(fr)
    return pd.concat(frames, ignore_index=True), np.concatenate(lat)


def calibrar_cortes(frames: pd.DataFrame, lateral: np.ndarray, cfg: dict) -> dict:
    """Passo 1 da calibracao (plano 06 §4.4, emenda §10).

    Minimiza `0,5 * soma(residuo^2)` dos tres alvos (pesos iguais) sujeito a
    `trocas_por_minuto(c = 1) <= cortes_por_minuto_max` e ao acoplamento
    `a_s <= 1 - b`. O acoplamento vale POR CONSTRUCAO: `a_s = (1 - b) alpha_s`,
    `alpha_s, b` em [0, 1] (o SLSQP avalia pontos inviaveis nas diferencas
    finitas, e `p_off` estoura fora do acoplamento). SLSQP de cada ponto de
    `cortes_pontos_iniciais`; fica o de menor custo (empate: o primeiro).
    `cortes_por_minuto_max = inf` roda SEM a restricao (diagnostico do bloco 1).

    Entrada: `frames` (FRAMES, os jogos concatenados) e `lateral` os indices
    das ancoras `frame` das laterais. Saida: dict com `a_vivo`, `a_morto`, `b`,
    `obtidos`, `custo`, `trocas_por_min`, `folga` (max - trocas) e `partidas`
    (uma entrada por ponto inicial, para auditoria).
    """
    s = cfg["simulador"]
    fps = cfg["tracking"]["fps"]
    alvos = _alvos_cortes(cfg)
    teto = s["cortes_por_minuto_max"]
    memo = {}

    def params(z):
        return {"a_vivo": (1 - z[2]) * z[0], "a_morto": (1 - z[2]) * z[1], "b": z[2]}

    def avaliar(z):
        # memo por ponto: objetivo e restricao (e suas diferencas finitas) sao
        # avaliados nos mesmos pontos; um p_off por ponto, nao quatro.
        chave = tuple(z)
        if chave not in memo:
            pr = params(z)
            p = p_off(frames, pr, 1.0)
            r = _obtidos_cortes(frames, lateral, pr, p) - alvos
            memo[chave] = (0.5 * float(r @ r), trocas_por_minuto(frames, pr, 1.0, fps, p))
        return memo[chave]

    partidas = []
    for x0 in s["cortes_pontos_iniciais"]:
        restricao = [] if np.isinf(teto) else             [{"type": "ineq", "fun": lambda z: (teto - avaliar(z)[1]) / teto}]
        sol = minimize(lambda z: avaliar(z)[0], np.asarray(x0, dtype=float), method="SLSQP",
                       bounds=[(0.0, 1.0)] * 3, constraints=restricao,
                       options={"ftol": s["cortes_ftol"]})
        pr = {k: float(v) for k, v in params(sol.x).items()}
        custo, trocas = avaliar(sol.x)
        partidas.append({"x0": list(x0), **pr, "custo": custo, "trocas_por_min": trocas,
                         "sucesso": bool(sol.success), "mensagem": str(sol.message)})
    viaveis = [q for q in partidas if q["sucesso"]
               and q["trocas_por_min"] <= teto + s["tol_restricao"]]
    if not viaveis:
        raise ValueError("calibracao dos cortes: nenhum ponto inicial convergiu para solucao viavel")
    melhor = min(viaveis, key=lambda q: q["custo"])
    cortes = {k: melhor[k] for k in ("a_vivo", "a_morto", "b")}
    return {**cortes, "obtidos": _obtidos_cortes(frames, lateral, cortes),
            "custo": melhor["custo"], "trocas_por_min": melhor["trocas_por_min"],
            "folga": teto - melhor["trocas_por_min"], "partidas": partidas}


def _cdf(valor: np.ndarray, peso: np.ndarray):
    """(ordenado, soma acumulada com 0 na frente) para `F(v) = soma(peso[valor <= v])`."""
    o = np.argsort(valor, kind="stable")
    return valor[o], np.r_[0.0, np.cumsum(peso[o])]


def _theta_estrela(L: dict, phi: np.ndarray, p1: np.ndarray, cfg: dict):
    """theta* (graus) e a distancia visivel esperada por papel nele (c = 1)."""
    s = cfg["simulador"]
    w = L["passo"] * (1.0 - p1)
    cdfs = {}
    for papel in PAPEIS:
        m = L["papel"] == papel
        cdfs[papel] = (*_cdf(phi[m], w[m]), L["passo"][m].sum())

    def dist(theta):
        return {k: acum[np.searchsorted(v, theta / 2.0, "right")] / tot
                for k, (v, acum, tot) in cdfs.items()}

    def erro(theta):
        d = dist(theta)
        return sum((d[k] - s["alvos"]["dist_visivel"][k]) ** 2 for k in PAPEIS)

    theta = float(minimize_scalar(erro, bounds=tuple(s["theta_busca_graus"]),
                                  method="bounded").x)
    return theta, dist(theta)


def _bissecao(taxa, alvo: float, lo: float, hi: float, tol: float) -> tuple:
    """Bissecao num `taxa` nao decrescente ate `|taxa - alvo| < tol`."""
    while True:
        meio = 0.5 * (lo + hi)
        r = taxa(meio)
        if abs(r - alvo) < tol:
            return meio, r
        if meio in (lo, hi):
            raise ValueError("bissecao nao atingiu a tolerancia")
        lo, hi = (meio, hi) if r < alvo else (lo, meio)


def _taxas(vis: np.ndarray, L: dict) -> dict:
    """Taxa (esperada se `vis` for probabilidade) em todas as linhas, sem GK e
    so em bola viva."""
    return {"todas": float(vis.mean()), "sem_gk": float(vis[~L["gk"]].mean()),
            "viva": float(vis[L["vivo"]].mean())}


def calibrar(base: dict, cfg: dict, jogos=None) -> dict:
    """Calibra cortes, theta* e os 8 niveis por variante, em valor esperado.

    Entrada: `base` = `game -> dict` com `frames`, `tracking`, `periods`,
    `eventos` (o `_carregar_base` serve); `jogos` padrao = todas as chaves.
    Saida: dict com `a_vivo`, `a_morto`, `b`, `theta_estrela_graus`, `niveis`
    (`{'B': [{theta_graus, c, taxa}], 'A': [{L_m, taxa}]}`) -- o que vai ao
    `config.yaml` -- e `diag` (tudo o que o `--simulador` imprime).
    Deterministica: nao sorteia nada.
    """
    s = cfg["simulador"]
    jogos = sorted(base) if jogos is None else list(jogos)
    L = _linhas(base, cfg, jogos)
    fr = L["frames"]

    # 1. cortes, com a restricao de trocas por minuto (emenda §10)
    ajuste = calibrar_cortes(fr, L["lateral"], cfg)
    cortes = {k: ajuste[k] for k in ("a_vivo", "a_morto", "b")}

    # 3. theta*
    phi = angulo_cunha(L["x"], L["y"], L["cx"], L["cy"], s["d_cam_m"], cfg)
    p_c = {c: p_off(fr, cortes, c)[L["iq"]] for c in sorted(set(s["escada"]["c"]))}
    theta, dist = _theta_estrela(L, phi, p_c[1.0], cfg)
    geo_estrela = phi <= theta / 2.0
    vis8 = geo_estrela * (1.0 - p_c[1.0])
    tempo = {k: float(vis8[L["papel"] == k].mean()) for k in PAPEIS}

    # 4. niveis
    tol = s["bissecao_tol_taxa"]
    phi_ord = np.sort(phi)
    n = phi.size
    r5 = float(np.searchsorted(phi_ord, theta / 2.0, "right") / n)
    cheb = np.sort(_dist_janela(L["x"], L["y"], L["cx"], L["cy"]))
    nivB, nivA, taxasB, taxasA = [], [], [], []
    for fg, c in zip(s["escada"]["fracao_geometrica"], s["escada"]["c"]):
        if fg == 0.0:
            th = np.inf
        elif fg == 1.0:
            th = theta
        else:
            th, _ = _bissecao(lambda t: np.searchsorted(phi_ord, t / 2.0, "right") / n,
                              1.0 - fg * (1.0 - r5), 0.0, 360.0, tol)
        visB = (phi <= th / 2.0) * (1.0 - p_c[c])
        tB = _taxas(visB, L)
        if tB["todas"] == 1.0:
            lm = np.inf
        else:
            lm, _ = _bissecao(lambda l: np.searchsorted(cheb, l / 2.0, "right") / n,
                              tB["todas"], 0.0, 2.0 * cheb[-1], tol)
        tA = _taxas(_dist_janela(L["x"], L["y"], L["cx"], L["cy"]) <= lm / 2.0, L)
        nivB.append({"theta_graus": float(th), "c": float(c), "taxa": tB["todas"]})
        nivA.append({"L_m": float(lm), "taxa": tA["todas"]})
        taxasB.append(tB)
        taxasA.append(tA)

    # validacoes de B8 (esperadas): visiveis por (quadro, time)
    p8 = p_off(fr, cortes, 1.0)
    chave = L["iq"] * 2 + L["time"]
    n_geo = np.bincount(chave, weights=geo_estrela, minlength=2 * len(fr)).astype("int64")
    p_fr = np.repeat(p8, 2)
    dist_vis = np.bincount(n_geo, weights=1.0 - p_fr, minlength=12)
    dist_vis[0] += p_fr.sum()
    dist_vis = dist_vis / (2 * len(fr))

    # 6. sensibilidade a d_cam (diagnostico; nao troca d_cam)
    sens = {}
    for d in s["sensibilidade_d_cam_m"]:
        phi_d = angulo_cunha(L["x"], L["y"], L["cx"], L["cy"], d, cfg)
        sens[d] = _theta_estrela(L, phi_d, p_c[1.0], cfg)

    vivo_fr = fr["ball_live"].to_numpy()
    return {
        **cortes,
        "theta_estrela_graus": theta,
        "niveis": {"B": nivB, "A": nivA},
        "diag": {
            "alvos_cortes": _alvos_cortes(cfg), "obtidos_cortes": ajuste["obtidos"],
            "custo": ajuste["custo"], "folga": ajuste["folga"], "partidas": ajuste["partidas"],
            "papeis": L["papeis"], "dist_visivel": dist, "tempo_visivel": tempo,
            "n_curtos": L["n_curtos"], "n_segmentos": L["n_segmentos"],
            "taxas": {"B": taxasB, "A": taxasA},
            "dist_visiveis_por_time": dist_vis,
            "cortes_por_min": ajuste["trocas_por_min"],
            "f_viva": float(vivo_fr.mean()),
            "sensibilidade": sens,
            "n_laterais": int(L["lateral"].size),
        },
    }


# --- precursor da previsao (§6 bloco 7), so visibilidade -----------------------

def precursor(base: dict, cfg: dict, tipos, jogos=None) -> pd.DataFrame:
    """Visibilidade ESPERADA ligada a bola parada do gabarito, sem detector.

    Entrada: `base` como em `calibrar`; `cfg` com `simulador.calibrado`;
    `tipos` = tipos de bola parada. Saida: DataFrame `variante, nivel, type, n,
    exec_frame, exec_anotado, n_corrida, area_time, area_gk`:
      `exec_frame`/`exec_anotado` media de P(executor anotado visivel) na ancora
        `frame` / no `annotated_frame` (executor sem linha conta 0);
      `area_time`/`area_gk` media, sobre os eventos com corrida morta antes da
        ancora (`n_corrida` deles), da fracao esperada de quadros da corrida com
        algum jogador do time do executor (so o GK, no segundo) na zona do
        gatilho de tiro de meta (propria pequena area + eps_g) visivel.
    """
    s = cfg["simulador"]
    jogos = sorted(base) if jogos is None else list(jogos)
    pre = []
    for g in jogos:
        fr, tr, per, ev = (base[g][k] for k in ("frames", "tracking", "periods", "eventos"))
        ev = ev[ev["type"].isin(tipos)]
        alvo = alvo_camera(fr, cfg)
        cx, cy = alvo["cx"].to_numpy(), alvo["cy"].to_numpy()
        lado = tr[["period", "team"]].merge(per[["period", "team", "attack_dir"]], how="left",
                                           on=["period", "team"])["attack_dir"].to_numpy()
        zona = gatilhos.zona_tiro_de_meta(tr["x"].to_numpy(), tr["y"].to_numpy(), lado, cfg)
        z = tr[zona]
        d0, dc, _ = corridas_mortas(fr["ball_live"].to_numpy())
        ancora = ev["frame"].to_numpy() - 1
        k = np.searchsorted(dc + 1, ancora)
        tem = (k < dc.size) & (dc[np.minimum(k, dc.size - 1)] + 1 == ancora)
        idx = tr.set_index(["player_id", "frame"]).index
        pos = {}
        for col in ("frame", "annotated_frame"):
            j = idx.get_indexer(pd.MultiIndex.from_arrays([ev["player_id"], ev[col]]))
            pos[col] = j
        pre.append((g, fr, tr, ev, cx, cy, z, d0, dc, k, tem, pos))

    linhas = []
    for variante in VARIANTES:
        for nivel, lv in enumerate(s["calibrado"]["niveis"][variante], start=1):
            acc = []
            for g, fr, tr, ev, cx, cy, z, d0, dc, k, tem, pos in pre:
                c = lv.get("c", 0.0) if variante == "B" else 0.0
                livre = 1.0 - (p_off(fr, s["calibrado"], c) if variante == "B" else 0.0)

                def vis(xs, ys, iq):
                    if variante == "A":
                        return na_janela(xs, ys, cx[iq], cy[iq], lv["L_m"])
                    return na_cunha(xs, ys, cx[iq], cy[iq], lv["theta_graus"], s["d_cam_m"], cfg)

                livre = np.broadcast_to(livre, (len(fr),))
                ex = {}
                for col, j in pos.items():
                    ok = j >= 0
                    jj = np.maximum(j, 0)
                    iq = tr["frame"].to_numpy()[jj] - 1
                    v = vis(tr["x"].to_numpy()[jj], tr["y"].to_numpy()[jj], iq) * livre[iq]
                    ex[col] = np.where(ok, v, 0.0)
                iqz = z["frame"].to_numpy() - 1
                vz = vis(z["x"].to_numpy(), z["y"].to_numpy(), iqz)
                area = {}
                for nome, filtro in (("area_time", np.ones(len(z), bool)),
                                     ("area_gk", z["is_gk"].to_numpy())):
                    por_time = {}
                    for time in ("home", "away"):
                        m = vz & filtro & (z["team"].to_numpy() == time)
                        algum = np.zeros(len(fr))
                        algum[iqz[m]] = 1.0
                        por_time[time] = np.r_[0.0, np.cumsum(algum * livre)]
                    kk = np.minimum(k, dc.size - 1)
                    a0, a1 = d0[kk], dc[kk] + 1
                    casa = ev["team"].to_numpy() == "home"
                    soma = np.where(casa, por_time["home"][a1] - por_time["home"][a0],
                                    por_time["away"][a1] - por_time["away"][a0])
                    frac = soma / (a1 - a0)
                    area[nome] = np.where(tem, frac, np.nan)
                acc.append(pd.DataFrame({"type": ev["type"].to_numpy(),
                                         "exec_frame": ex["frame"],
                                         "exec_anotado": ex["annotated_frame"], **area}))
            todos = pd.concat(acc, ignore_index=True)
            for tipo, b in todos.groupby("type", sort=True):
                linhas.append({"variante": variante, "nivel": nivel, "type": tipo, "n": len(b),
                               "exec_frame": b["exec_frame"].mean(),
                               "exec_anotado": b["exec_anotado"].mean(),
                               "n_corrida": int(b["area_time"].notna().sum()),
                               "area_time": b["area_time"].mean(),
                               "area_gk": b["area_gk"].mean()})
    return pd.DataFrame(linhas)

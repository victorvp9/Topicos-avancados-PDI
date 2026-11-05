"""Reconstrucao do tracking degradado (Fatia 7).

Plano normativo: `docs/fatias/07-plano.md` §3. Constantes em
`config.yaml:reconstrucao`.

- `reconstruir` preenche, por interpolacao linear no tempo (`np.interp` sobre
  `frame`), as linhas de `presenca` que faltam em `degradado`, por
  `(game, period, player_id)`. As linhas que vieram em `degradado` saem bit a
  bit (`x`, `y`, `visible`); as imputadas saem com `visible = False` (docs/02:
  False = imputado).
- `presenca` so tem as colunas-chave do teto: este modulo NUNCA le `x`/`y` de
  `presenca` (plano §3, vazamento).
- Jogador sem nenhuma ancora no periodo fica AUSENTE (nunca NaN) e e contado.
- `velocidade` e o filtro de Butterworth por segmento de `broadcast.passos`
  seguido de diferencas centrais (plano §4, bloco 5).
"""

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt

from src.io.schema import TRACKING, validar

CHAVES = ["game", "period", "frame", "player_id", "team", "is_gk"]
_ESQ_CHAVES = {k: TRACKING[k] for k in CHAVES}


def _estrutura(presenca: pd.DataFrame, degradado: pd.DataFrame) -> dict:
    """Casa as linhas de `degradado` com as de `presenca` pela chave
    `(game, player_id, frame)` e ordena `presenca` por `(game, player_id, frame)`.

    Saida (tudo na ORDEM ORDENADA, exceto `ordem`): `ordem` (permutacao de
    `presenca` para a ordem ordenada), `pos` (posicao ordenada de cada linha de
    `degradado`), `ancora` (bool), `ini`/`fim` dos grupos `(game, player_id,
    period)`, `gid` (grupo de cada linha) e `frame`. Estoura em chave duplicada,
    em linha de `degradado` fora de `presenca` e em `period` divergente.
    """
    validar(presenca[CHAVES], _ESQ_CHAVES, "presenca")
    jog, uniq = pd.factorize(presenca["player_id"])
    cod_d = pd.Index(uniq).get_indexer(degradado["player_id"])
    if (cod_d < 0).any():
        raise ValueError("degradado tem player_id fora de presenca")
    gp, gu = pd.factorize(presenca["game"])
    gd = pd.Index(gu).get_indexer(degradado["game"])
    if (gd < 0).any():
        raise ValueError("degradado tem game fora de presenca")
    fp = presenca["frame"].to_numpy()
    fd = degradado["frame"].to_numpy()
    if (fp < 0).any() or (fd < 0).any():
        raise ValueError("frame negativo")
    base_f = int(max(fp.max(initial=0), fd.max(initial=0))) + 1
    nj = max(len(uniq), 1)
    chave_p = (gp.astype("int64") * nj + jog) * base_f + fp
    chave_d = (gd.astype("int64") * nj + cod_d) * base_f + fd
    ordem = np.argsort(chave_p, kind="stable")
    ks = chave_p[ordem]
    if (np.diff(ks) == 0).any():
        raise ValueError("presenca com (game, player_id, frame) duplicado")
    pos = np.searchsorted(ks, chave_d)
    if ((pos >= ks.size) | (ks[np.minimum(pos, ks.size - 1)] != chave_d)).any():
        raise ValueError("degradado tem linha fora de presenca")
    if (np.diff(np.sort(pos)) == 0).any():
        raise ValueError("degradado com (game, player_id, frame) duplicado")
    per = presenca["period"].to_numpy()[ordem]
    if (per[pos] != degradado["period"].to_numpy()).any():
        raise ValueError("degradado com period diferente de presenca na mesma chave")
    g_s, j_s = gp[ordem], jog[ordem]
    quebra = np.r_[True, (g_s[1:] != g_s[:-1]) | (j_s[1:] != j_s[:-1]) | (per[1:] != per[:-1])] \
        if ks.size else np.zeros(0, bool)
    ini = np.flatnonzero(quebra)
    ancora = np.zeros(ks.size, bool)
    ancora[pos] = True
    return {"ordem": ordem, "pos": pos, "ancora": ancora, "ini": ini,
            "fim": np.r_[ini[1:], ks.size].astype("int64"),
            "gid": np.cumsum(quebra) - 1, "frame": fp[ordem]}


def buracos(presenca: pd.DataFrame, degradado: pd.DataFrame) -> pd.DataFrame:
    """Diagnostico por linha de `presenca` (mesmo indice e ordem).

    Entrada: `presenca` com as colunas `CHAVES` (esquema TRACKING) e
    `degradado` (TRACKING). Saida: DataFrame com
      `ancora` bool: a linha veio em `degradado`;
      `sem_ancora` bool: o jogador nao tem nenhuma ancora naquele periodo;
      `borda` bool: imputada antes da primeira ou depois da ultima ancora;
      `buraco_quadros` int64: comprimento da corrida contigua de linhas
        ausentes (na ordem de `frame`, dentro do grupo) a que a linha pertence;
        0 nas ancoras. No teto da Metrica a presenca e contigua por periodo
        (segmentos = grupos nos 3 jogos), logo linhas = quadros.
    """
    e = _estrutura(presenca, degradado)
    a, gid = e["ancora"], e["gid"]
    n_grupos = e["ini"].size
    na = np.bincount(gid, weights=a, minlength=n_grupos)
    sem = na[gid] == 0
    acum = np.cumsum(a)
    antes = acum - np.r_[0, acum][e["ini"]][gid]     # ancoras ate a linha, no grupo
    borda = ~a & ~sem & ((antes == 0) | (antes == na[gid]))
    inicio_grupo = np.zeros(a.size, bool)
    inicio_grupo[e["ini"]] = True
    inicio_corrida = ~a & (inicio_grupo | np.r_[True, a[:-1]])
    rid = np.cumsum(inicio_corrida) - 1
    comp = np.bincount(rid[~a], minlength=max(int(inicio_corrida.sum()), 1))
    buraco = np.where(a, 0, comp[np.maximum(rid, 0)]) if a.size else np.zeros(0, "int64")
    saida = {}
    for nome, valor in (("ancora", a), ("sem_ancora", sem), ("borda", borda),
                        ("buraco_quadros", buraco.astype("int64"))):
        col = np.empty(a.size, dtype=valor.dtype)
        col[e["ordem"]] = valor
        saida[nome] = col
    return pd.DataFrame(saida, index=presenca.index)


def reconstruir(degradado: pd.DataFrame, presenca: pd.DataFrame):
    """Preenche os buracos de `degradado` por interpolacao linear (plano 07 §3).

    Entrada: `degradado` (TRACKING; saida de `broadcast.degradar` ou o teto) e
    `presenca` (as colunas `CHAVES` do teto, com o indice do teto; outras
    colunas sao ignoradas e NUNCA lidas). Saida: (TRACKING com as linhas de
    `presenca` que tem ancora, no indice e na ordem de `presenca`; dict com
    `n_imputadas`, `n_sem_ancora`, `n_jogadores_periodo_sem_ancora`).

    Linha de `degradado`: `x`, `y`, `visible` copiados bit a bit. Linha
    ausente: `np.interp` sobre `frame` com as ancoras do mesmo
    `(game, period, player_id)`; constante antes da primeira e depois da ultima
    ancora; `visible = False`. Grupo sem ancora: linhas ausentes, contadas.
    NaN em `x`/`y` de `degradado` estoura.
    """
    validar(degradado, TRACKING, "degradado")
    if degradado[["x", "y"]].isna().to_numpy().any():
        raise ValueError("degradado com NaN em x/y: NaN nao serve de ancora")
    e = _estrutura(presenca, degradado)
    ordem, pos, a = e["ordem"], e["pos"], e["ancora"]
    n = a.size
    xs, ys = np.zeros(n), np.zeros(n)
    xs[pos] = degradado["x"].to_numpy()
    ys[pos] = degradado["y"].to_numpy()
    vis = np.zeros(n, bool)
    vis[pos] = degradado["visible"].to_numpy()
    tem = np.zeros(n, bool)
    f = e["frame"].astype("float64")
    n_grupos_sem = 0
    for i0, i1 in zip(e["ini"], e["fim"]):
        m = a[i0:i1]
        if not m.any():
            n_grupos_sem += 1
            continue
        tem[i0:i1] = True
        if m.all():
            continue
        falta = ~m
        for v in (xs, ys):
            seg = v[i0:i1]
            seg[falta] = np.interp(f[i0:i1][falta], f[i0:i1][m], seg[m])
    manter = np.empty(n, bool)
    manter[ordem] = tem
    x, y, visible = np.empty(n), np.empty(n), np.empty(n, bool)
    x[ordem], y[ordem], visible[ordem] = xs, ys, vis
    saida = presenca.loc[manter, CHAVES].copy() if not manter.all() else presenca[CHAVES].copy()
    saida["x"] = x[manter]
    saida["y"] = y[manter]
    saida["visible"] = visible[manter]
    contagens = {"n_imputadas": int((tem & ~a).sum()), "n_sem_ancora": int((~tem).sum()),
                 "n_jogadores_periodo_sem_ancora": n_grupos_sem}
    return validar(saida, TRACKING, "tracking reconstruido"), contagens


def filtradas(tracking: pd.DataFrame, cfg: dict):
    """Posicoes filtradas como em `broadcast.passos`.

    Entrada: `tracking` (TRACKING). Saida: (`ordem`, `quebra`, `fx`, `fy`), com
    `ordem` = permutacao por (game, player_id, frame), `quebra` (n,) bool no
    inicio de cada segmento (troca de jogo, jogador, periodo ou quadro nao
    consecutivo) e `fx`, `fy` (m) na ordem `ordem`. Butterworth
    `simulador.butter_*` com `filtfilt` por segmento; segmento com tamanho <=
    `padlen` padrao usa `padlen = len - 1`; segmento de 1 linha fica cru.
    """
    # TODO(divida): repete o laco de `broadcast.passos`; um helper comum exigiria
    # tocar o simulador, proibido nesta fatia (plano 07 §7). O teste
    # `test_filtro_igual_ao_de_passos` trava a equivalencia bit a bit.
    s = cfg["simulador"]
    b, a = butter(s["butter_ordem"], s["butter_corte_hz"], fs=cfg["tracking"]["fps"])
    pad_padrao = 3 * max(len(a), len(b))
    codigo = pd.factorize(tracking["player_id"])[0]
    g = tracking["game"].to_numpy()
    f = tracking["frame"].to_numpy()
    ordem = np.lexsort((f, codigo, g))
    g, f, codigo = g[ordem], f[ordem], codigo[ordem]
    per = tracking["period"].to_numpy()[ordem]
    quebra = np.r_[True, (g[1:] != g[:-1]) | (codigo[1:] != codigo[:-1])
                   | (per[1:] != per[:-1]) | (np.diff(f) != 1)]
    fx = tracking["x"].to_numpy()[ordem].copy()
    fy = tracking["y"].to_numpy()[ordem].copy()
    ini = np.flatnonzero(quebra)
    for i0, i1 in zip(ini, np.r_[ini[1:], f.size]):
        m = i1 - i0
        pad = m - 1 if m <= pad_padrao else pad_padrao
        if m >= 2:
            fx[i0:i1] = filtfilt(b, a, fx[i0:i1], padlen=pad)
            fy[i0:i1] = filtfilt(b, a, fy[i0:i1], padlen=pad)
    return ordem, quebra, fx, fy


def velocidade(tracking: pd.DataFrame, cfg: dict) -> np.ndarray:
    """(n,) velocidade escalar em m/s, alinhada as linhas de `tracking`.

    `filtradas` (o filtro de `broadcast.passos`) e depois diferencas centrais
    (`np.gradient`, ordem 1 nas pontas) dentro do segmento, vezes `fps`.
    Bassek, Metodos, p. 4. Segmento de 1 linha estoura: a velocidade e
    indefinida, e ele nao existe no teto da Metrica (segmentos = grupos).
    """
    ordem, quebra, fx, fy = filtradas(tracking, cfg)
    ini = np.flatnonzero(quebra)
    v = np.empty(fx.size)
    for i0, i1 in zip(ini, np.r_[ini[1:], fx.size]):
        if i1 - i0 < 2:
            raise ValueError("segmento de 1 quadro: velocidade indefinida")
        v[i0:i1] = np.hypot(np.gradient(fx[i0:i1]), np.gradient(fy[i0:i1]))
    saida = np.empty(fx.size)
    saida[ordem] = v * cfg["tracking"]["fps"]
    return saida

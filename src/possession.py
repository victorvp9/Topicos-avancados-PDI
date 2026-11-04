"""Passo 1 da especificacao: zonas, control frames, perda e ganho de posse.

Regra normativa: `docs/01-definicoes.md`, Passo 1. As seis lacunas que o artigo
nao cobre estao resolvidas em `docs/fatias/03-plano.md` §3 (e em
`docs/decisoes.md`); cada uma esta citada no ponto do codigo que a aplica.

Nenhuma constante aqui: `R_pz`, `R_dz`, `eps_s`, `eps_v`, `eps_theta` e a
tolerancia de empate vem de `config.yaml:posse`. Para varrer um parametro,
copie o `cfg` e troque o valor -- nao existe argumento de atalho.

Vetorizado: **nenhum laco sobre quadros**. Tudo e operacao sobre matrizes
(jogador x quadro) ou reducao por segmento (`np.maximum.reduceat` sobre as
corridas vivas e sobre as sequencias de controle).
"""

import numpy as np
import pandas as pd

from src import suavizar
from src.io.schema import validar
from src.tau import grade_de_posicoes

POSSESSION = "possession"
DUEL = "duel"
# Dominio fechado de `team` no esquema TRACKING (docs/fatias/01-plano.md §4).
TIMES = ("home", "away")
# Politicas de `R_dz` ao varrer `R_pz`. Ver `raios`.
POLITICAS_R_DZ = ("acompanha_r_pz", "fixo_1m")

# Um registro por control frame (quadro em jogo com posse ou duelo). Plano §5.
# `d0`/`d1` sao vetores UNITARIOS (docs/01-definicoes.md), e e isso que torna o
# produto escalar comparavel a um cosseno.
CONTROL = {
    "game": "int64",
    "period": "int64",
    "frame": "int64",
    "t": "float64",
    "ball_control": "str",
    "owner_id": "str",
    "owner_team": "str",
    "d_owner_m": "float64",
    "ds_m": "float64",
    "d0_x": "float64",
    "d0_y": "float64",
    "v0": "float64",
    "d1_x": "float64",
    "d1_y": "float64",
    "v1": "float64",
    "run_id": "int64",
}

# Uma linha por perda de posse. As duas colunas booleanas respondem a perguntas
# DIFERENTES, e por isso sao duas (lacuna 5, plano §3.5):
#   `termina_corrida`  = e a perda do ultimo quadro de posse da corrida viva.
#                        Uma por corrida com posse. E o DBE que a Fatia 4 consome.
#   `so_por_lacuna_5`  = `termina_corrida` E as condicoes 1 e 2 NAO sao
#                        satisfeitas ali. Sao as perdas que existem apenas pela
#                        decisao da lacuna 5; o resto das `termina_corrida` sao
#                        perdas que a regra literal tambem emitiria.
PERDAS = {
    "game": "int64",
    "period": "int64",
    "frame": "int64",
    "t": "float64",
    "player_id": "str",
    "team": "str",
    "run_id": "int64",
    "termina_corrida": "bool",
    "so_por_lacuna_5": "bool",
    "ds_m": "float64",
}

# Uma linha por ganho de posse, no quadro `f0` da sequencia.
GANHOS = {
    "game": "int64",
    "period": "int64",
    "frame": "int64",
    "t": "float64",
    "player_id": "str",
    "team": "str",
    "run_id": "int64",
    "mudou_direcao": "bool",
    "mudou_velocidade": "bool",
    "d0d1": "float64",
    "dv_max": "float64",
}

# Uma linha por sequencia de control frames consecutivos do MESMO dono. Nao esta
# no plano §5: existe porque o diagnostico do §7 precisa de `d0d1` e `dv_max`
# TAMBEM das sequencias descartadas, que por definicao nao estao em `ganhos`.
SEQUENCIAS = {
    "game": "int64",
    "period": "int64",
    "run_id": "int64",
    "frame_f0": "int64",
    "frame_fn": "int64",
    "n_quadros": "int64",
    "player_id": "str",
    "team": "str",
    "d0d1": "float64",
    "dv_max": "float64",
    "mudou_direcao": "bool",
    "mudou_velocidade": "bool",
    "ganho": "bool",
}


def corridas_vivas(ball_live: np.ndarray):
    """Segmenta a serie em corridas vivas contiguas.

    Entrada: `ball_live` (n_quadros,) booleano, na ordem do quadro.
    Saida: (`run_id`, `inicios`, `comprimentos`), com `run_id` (n_quadros,)
    int64 valendo 1..R nos quadros vivos e 0 nos mortos; `inicios` os indices do
    primeiro quadro de cada corrida; `comprimentos` o numero de quadros de cada
    corrida.
    """
    ball_live = np.asarray(ball_live, dtype=bool)
    inicio = ball_live & ~np.r_[False, ball_live[:-1]]
    run_id = np.where(ball_live, np.cumsum(inicio), 0).astype("int64")
    return run_id, np.flatnonzero(inicio), np.bincount(run_id)[1:].astype("int64")


def _cinematica(ball_x: np.ndarray, ball_y: np.ndarray, dt: float) -> dict:
    """Deslocamento, direcao e velocidade de entrada e de saida da bola.

    Entrada: `ball_x`/`ball_y` (n_quadros,) em metros, NaN onde a bola nao tem
    dado; `dt` em segundos.
    Saida: dict de arrays (n_quadros,) com `ds` (= |bola(f+1) - bola(f)|),
    `d0_x`, `d0_y`, `v0` (entrada, de `f-1`) e `d1_x`, `d1_y`, `v1` (saida, para
    `f+1`). `d0`/`d1` sao unitarios.

    `d0`/`v0` sao NaN no primeiro quadro de cada corrida viva e `d1`/`v1` no
    ultimo, automaticamente: `f-1` (ou `f+1`) morto tem a bola em NaN. Lacuna 3
    (plano §3.3) -- NaN **nunca** conta como mudanca e nunca e descartado.

    Deslocamento exatamente nulo tambem deixa a direcao NaN (0/0) e cai na mesma
    regra: direcao indefinida vale "nao mudou".
    """
    passo_x = np.r_[np.nan, np.diff(ball_x)]
    passo_y = np.r_[np.nan, np.diff(ball_y)]
    norma = np.hypot(passo_x, passo_y)
    with np.errstate(invalid="ignore", divide="ignore"):
        d0_x = passo_x / norma
        d0_y = passo_y / norma
    v0 = norma / dt
    nan = np.array([np.nan])
    return {
        "ds": np.r_[norma[1:], nan],
        "d0_x": d0_x,
        "d0_y": d0_y,
        "v0": v0,
        "d1_x": np.r_[d0_x[1:], nan],
        "d1_y": np.r_[d0_y[1:], nan],
        "v1": np.r_[v0[1:], nan],
    }


def _zonas(d: np.ndarray, times: np.ndarray, r_pz: float, r_dz: float, tol: float):
    """Classifica cada quadro em posse/duelo e escolhe o dono.

    Entrada: `d` (n_jogadores, n_quadros) com a distancia jogador-bola em
    metros, NaN onde falta dado; `times` (n_jogadores,) com o time de cada
    jogador; os dois raios em metros; `tol` a tolerancia de empate de distancia.
    Saida: (`duelo`, `dono`, `d_dono`, `empates`), com `duelo`
    (n_quadros,) booleano, `dono` (n_quadros,) o indice do jogador mais proximo
    com a bola na PZ ou -1, `d_dono` a distancia dele (NaN se nao ha dono) e
    `empates` (total, em_posse) o numero de quadros com dois ou mais candidatos
    a `tol` do minimo -- `em_posse` conta so os quadros que nao sao de duelo,
    isto e aqueles em que o desempate realmente escolhe um dono.

    Comparacao INCLUSIVA (`d <= R`): a bola exatamente sobre o circulo esta
    dentro. NaN fica fora das duas zonas, logo quadro de bola morta nunca tem
    posse nem duelo -- e isso vem da propria definicao de `ball_live` (D1).

    Dono = o mais proximo da bola (lacuna 1, plano §3.1, pela regra analoga do
    artigo §2.4.1, p. 7). Empate exato fica com o `player_id` menor porque as
    linhas de `d` estao em ordem de `player_id` e `argmin` devolve a primeira.

    Duelo = pelo menos um jogador de CADA time dentro de `R_dz` da bola
    (lacuna 2, plano §3.2); dois do mesmo time nao formam duelo. O duelo
    prevalece sobre a posse (§2.3.1, p. 4).
    """
    na_pz = d <= r_pz
    na_dz = d <= r_dz
    duelo = np.logical_and.reduce([na_dz[times == time].any(axis=0) for time in TIMES])

    d_pz = np.where(na_pz, d, np.inf)
    dono = d_pz.argmin(axis=0)
    d_dono = d_pz[dono, np.arange(d.shape[1])]
    tem_dono = np.isfinite(d_dono)
    empatado = ((d_pz <= d_dono + tol).sum(axis=0) >= 2) & tem_dono
    return (
        duelo,
        np.where(tem_dono, dono, -1),
        np.where(tem_dono, d_dono, np.nan),
        (int(empatado.sum()), int((empatado & ~duelo).sum())),
    )


def _sequencias(em_controle: np.ndarray):
    """Segmenta cada jogador em sequencias de control frames contiguos.

    Entrada: `em_controle` (n_jogadores, n_quadros) booleano -- o jogador esta
    em controle naquele control frame (ver `calcular`).
    Saida: (`jogador`, `f0`, `fn`), uma entrada por sequencia, ordenadas por
    `f0`; `jogador` e o indice da linha.

    A sequencia e a do §2.3.3, p. 5: *"a given sequence of control frames
    f0,...,fn where the ball is within the PZ of the same player"*. A condicao e
    geometrica e **NAO quebra em quadro de duelo**: quadro de duelo E control
    frame (§2.3.1, p. 4), eventos ocorrem em posse OU duelo (§2.2, p. 4), e o
    suplementar S5, p. 9, registra recepcao que nasce de duelo. Revisao de
    2026-10-31.

    Consequencia: um quadro de duelo pode pertencer a sequencia de DOIS
    jogadores (cada um com a bola na sua PZ), logo pode haver mais de um ganho
    no mesmo quadro. Isso e contado e reportado.

    A grade de quadros e contigua (exigencia de `grade_de_posicoes`). A coluna de
    False no fim de cada linha impede que uma corrida do jogador `p` se junte a
    uma do jogador `p+1` no vetor achatado.
    """
    n_jogadores, n_quadros = em_controle.shape
    plano = np.concatenate(
        [em_controle, np.zeros((n_jogadores, 1), dtype=bool)], axis=1
    ).ravel()
    i0 = np.flatnonzero(plano & ~np.r_[False, plano[:-1]])
    i1 = np.flatnonzero(plano & ~np.r_[plano[1:], False])
    ordem = np.argsort(i0 % (n_quadros + 1), kind="stable")
    i0, i1 = i0[ordem], i1[ordem]
    return i0 // (n_quadros + 1), i0 % (n_quadros + 1), i1 % (n_quadros + 1)


def _expandir(f0: np.ndarray, fn: np.ndarray, rotulo: np.ndarray):
    """Expande segmentos fechados [f0_i, fn_i] na lista de quadros que os compoem.

    Entrada: `f0`/`fn` os limites e `rotulo` um valor por segmento.
    Saida: (`quadros`, `rotulos`), do mesmo tamanho, com o rotulo repetido em
    cada quadro do seu segmento.
    """
    larguras = fn - f0 + 1
    deslocamento = np.arange(int(larguras.sum())) - np.repeat(
        np.cumsum(larguras) - larguras, larguras
    )
    return np.repeat(f0, larguras) + deslocamento, np.repeat(rotulo, larguras)


def _max_por_segmento(valores: np.ndarray, f0: np.ndarray, fn: np.ndarray) -> np.ndarray:
    """Maximo de `valores` em cada segmento fechado [f0_i, fn_i], ignorando NaN.

    Segmento todo NaN devolve NaN. Usa `-inf` no lugar de NaN porque quadro sem
    medida nunca pode ser o maximo (lacuna 3: NaN nao conta como mudanca).
    """
    if f0.size == 0:
        return np.zeros(0)
    bordas = np.empty(2 * f0.size, dtype="int64")
    bordas[0::2] = f0
    # O limite superior e exclusivo; o clip so morde quando fn e o ultimo quadro
    # do jogo, onde `v1` (logo `dv`) e NaN de todo modo.
    bordas[1::2] = np.minimum(fn + 1, valores.size - 1)
    maximos = np.maximum.reduceat(np.where(np.isnan(valores), -np.inf, valores), bordas)
    return np.where(np.isinf(maximos[0::2]), np.nan, maximos[0::2])


def raios(p: dict) -> tuple:
    """(`R_pz`, `R_dz`) efetivos, pela politica de `R_dz`.

    Entrada: `cfg['posse']`. Saida: os dois raios em metros.

    `r_dz_m` e o `R_dz` **base** do artigo (1,00 m para todos os provedores,
    supl. S4.1, p. 6). A politica decide como ele se combina com `R_pz`:

    - `acompanha_r_pz` (padrao): `R_dz` = max(base; `R_pz`), que e o D3. A
      exigencia `R_dz >= R_pz` do artigo (§2.3.1, p. 4) vale por construcao.
    - `fixo_1m`: `R_dz` = base, sempre. Acima de 1 m isso VIOLA
      `R_dz >= R_pz` de proposito: e a "checagem de sensibilidade com `R_dz`
      fixo em 1,0 m" que o proprio D3 previu como secundaria, e existe para
      DESCONFUNDIR as duas coisas -- com `R_dz` arrastado por `R_pz`, nao se
      separa "o `R_pz` ficou grande demais" de "o duelo, que prevalece, comeu os
      quadros de posse". Medido: as perdas crescem ate `R_pz` = 1,00 m e caem
      depois.

    Politica desconhecida estoura: nao ha valor padrao silencioso.
    """
    r_pz, base = p["r_pz_m"], p["r_dz_m"]
    politica = p["r_dz_politica"]
    if politica == "acompanha_r_pz":
        return r_pz, max(base, r_pz)
    if politica == "fixo_1m":
        return r_pz, base
    raise ValueError(
        "r_dz_politica {!r} fora de {}".format(politica, POLITICAS_R_DZ)
    )


def calcular(frames: pd.DataFrame, tracking: pd.DataFrame, cfg: dict) -> dict:
    """Roda o Passo 1 inteiro num jogo.

    Entrada: `frames` no esquema `src.io.schema.FRAMES` e `tracking` em
    `TRACKING`, como `src.io.carregar_jogo` devolve; `cfg` de
    `src.config.carregar_config`.

    Saida: dict com
      `control`    DataFrame no esquema `CONTROL`, uma linha por control frame,
                   em ordem de quadro, **sem** as sequencias falso-positivas;
      `perdas`     `PERDAS`; `ganhos` `GANHOS`; `sequencias` `SEQUENCIAS`;
      `frames`     o `frames` efetivamente usado (suavizado ou o original);
      `ds_m`       (n_quadros,) o deslocamento da bola de `f` para `f+1`;
      `contagens`  dict de contagens estruturais, para teste e relatorio.

    Ordem do pipeline: suavizacao -> zonas -> sequencias -> descarte das
    sequencias falso-positivas (§2.3.3, p. 5: elas "saem do passo de posse")
    -> perdas. As perdas saem dos control frames que sobraram; calcula-las antes
    do descarte faria o detector emitir perda de um jogador que nunca teve a
    bola.
    """
    p = cfg["posse"]
    r_pz, r_dz = raios(p)
    game = int(frames["game"].iloc[0])
    dt = 1.0 / cfg["tracking"]["fps"]

    run_id, inicios, comprimentos = corridas_vivas(frames["ball_live"].to_numpy())
    frames, cont_suav = suavizar.aplicar(frames, cfg, inicios, comprimentos)

    jogadores, px, py, ball_x, ball_y = grade_de_posicoes(frames, tracking)
    nomes = np.asarray(jogadores, dtype=object)
    times = (
        tracking.drop_duplicates("player_id")
        .set_index("player_id")["team"]
        .reindex(jogadores)
        .to_numpy()
    )
    if not np.isin(times, TIMES).all():
        raise ValueError("jogo {}: `team` fora de {} em `tracking`".format(game, TIMES))

    cin = _cinematica(ball_x, ball_y, dt)
    d = np.hypot(px - ball_x, py - ball_y)
    duelo, dono, d_dono, empates = _zonas(
        d, times, r_pz, r_dz, p["empate_distancia_m"]
    )
    posse_zona = (dono >= 0) & ~duelo

    # --- ganho de posse, uma decisao por sequencia (§2.3.3, p. 5) ---------
    # "Em controle" = ser o jogador MAIS PROXIMO com a bola na propria PZ, em
    # qualquer control frame -- de posse ou de DUELO. Duas coisas aqui:
    #  (1) a sequencia NAO quebra em duelo (revisao de 2026-10-31): quadro de
    #      duelo e control frame (§2.3.1, p. 4) e pode ter a bola na PZ;
    #  (2) continua havendo UM jogador em controle por quadro: o desempate da
    #      lacuna 1 (§2.4.1, p. 7, "we choose the closest player to the ball")
    #      vale no duelo tambem, e o suplementar S5, p. 9, fala de recepcao em
    #      que *"ONE player gains possession"*. Logo nenhum quadro tem dois
    #      ganhos. A leitura alternativa (todo jogador com a bola na PZ ganha a
    #      sua propria sequencia no duelo) esta medida no relatorio da revisao.
    # `dono` ja e -1 onde a bola nao esta na PZ de ninguem, o que quebra a
    # sequencia -- inclusive num duelo em que a bola nao esta na PZ de ninguem.
    em_controle = np.arange(jogadores.size)[:, None] == dono[None, :]
    jogador_seq, f0, fn = _sequencias(em_controle)
    d0d1 = cin["d0_x"][f0] * cin["d1_x"][fn] + cin["d0_y"][f0] * cin["d1_y"][fn]
    dv_max = _max_por_segmento(np.abs(cin["v0"] - cin["v1"]), f0, fn)
    # NaN em qualquer dos dois testes da False, isto e "nao mudou" (lacuna 3).
    with np.errstate(invalid="ignore"):
        mudou_direcao = d0d1 < p["eps_theta"]
        mudou_velocidade = dv_max > p["eps_v_ms"]
    ganho = mudou_direcao | mudou_velocidade

    # O descarte do §2.3.3 ("sao falsos positivos e saem do passo de posse") so
    # atinge quadro de POSSE: quadro de duelo e control frame de todo modo, e o
    # duelo prevalece. Quadro de posse pertence a uma unica sequencia -- a do seu
    # dono --, logo o descarte segue sendo 1:1.
    falso = np.zeros(frames.shape[0], dtype=bool)
    if (~ganho).any():
        # Sem filtro por dono: o quadro da sequencia JA e um quadro em que
        # `dono` e aquele jogador (e assim que `em_controle` foi construido), e
        # `falso` so e lido na linha seguinte, contra `posse_zona` -- marcar um
        # quadro de duelo ali nao muda nada, porque `posse_zona` ja e False
        # nele. A guarda anterior era codigo morto (limpeza da Fatia 4,
        # autorizada em decisoes.md de 2026-10-31, com dois mutantes do revisor
        # passando 319/319).
        quadros, _ = _expandir(f0[~ganho], fn[~ganho], jogador_seq[~ganho])
        falso[quadros] = True
    posse = posse_zona & ~falso
    controle = posse | duelo

    # --- perda de posse (§2.3.2, p. 5) -----------------------------------
    n_quadros = frames.shape[0]
    idx = np.arange(n_quadros)
    if inicios.size:
        # Os segmentos [inicios_i, inicios_{i+1}) incluem os quadros mortos do
        # fim da corrida, onde `posse` e False -- nao contaminam o maximo.
        ultima_posse = np.maximum.reduceat(np.where(posse, idx, -1), inicios)
    else:
        ultima_posse = np.zeros(0, dtype="int64")

    fp = np.flatnonzero(posse)
    ap = dono[fp]
    tem_seguinte = fp + 1 < n_quadros
    d_seguinte = np.where(tem_seguinte, d[ap, np.where(tem_seguinte, fp + 1, fp)], np.nan)
    with np.errstate(invalid="ignore"):
        cond1 = (d_seguinte > r_pz) & (cin["ds"][fp] > p["eps_s_m"])

    # Condicao 2: A nao aparece no control frame SEGUINTE `fc > f` -- o
    # IMEDIATAMENTE seguinte, nao "algum posterior na corrida". A condicao
    # existe para permitir posse longa em que a bola sai da PZ e volta "sem que
    # ninguem mais a toque" (docs/01, Passo 1); se outro jogador toca a bola em
    # `fc`, A perdeu a posse em `f` mesmo que recupere depois.
    f_controle = np.flatnonzero(controle)
    k = np.searchsorted(f_controle, fp, side="right")
    tem_fc = k < f_controle.size
    fc = f_controle[np.where(tem_fc, k, 0)]
    # Lacuna 4 (plano §3.4): `fc` tem de estar na MESMA corrida viva contigua.
    # Sem control frame posterior na corrida, a condicao 2 esta satisfeita.
    ha_fc = tem_fc & (run_id[fc] == run_id[fp])
    # "A aparece em `fc` com posse ou duelo" (docs/01; *"player A is not present
    # on the subsequent control frame"*, §2.3.2, p. 5). Os dois ramos usam
    # criterios DIFERENTES, e isso e deliberado:
    #   posse: A tem de ser o DONO de `fc`. Por propriedade, nao por geometria --
    #          se `fc` e de posse de outro jogador, a bola passou a ser dele,
    #          mesmo que ainda esteja dentro da PZ de A;
    #   duelo: A tem de estar dentro de `R_dz`, que e a propria definicao de
    #          participar do duelo -- em duelo nao existe dono.
    # A leitura alternativa (presente = a bola esta na PZ de A, tambem no ramo de
    # posse) foi MEDIDA na revisao de 2026-10-31: o predicado difere em 0, 0 e 1
    # quadros com `R_pz` = 0,50 m e em 18, 38 e 21 com 3,00 m, mas o numero de
    # perdas e IDENTICO nos 6 casos, porque nenhum desses quadros e candidato a
    # perda (a condicao 1 falha neles). Nao mudo o comportamento; declaro.
    aparece_em_fc = (posse[fc] & (dono[fc] == ap)) | (duelo[fc] & (d[ap, fc] <= r_dz))
    cond2 = ~ha_fc | ~aparece_em_fc
    regular = fp[cond1 & cond2]

    # Lacuna 5 (plano §3.5): no fim de cada corrida viva o ultimo jogador em
    # controle recebe perda no seu ultimo control frame, independente das
    # condicoes 1 e 2. Em duelo nao existe dono, logo "ultimo jogador em
    # controle" e o dono do ultimo quadro de POSSE da corrida.
    fim_f = ultima_posse[ultima_posse >= 0]
    # Um quadro tem um dono so: a perda de fim de corrida e a regular do mesmo
    # quadro sao a MESMA linha. `so_por_lacuna_5` separa as duas perguntas.
    outras_f = regular[~np.isin(regular, fim_f)]
    f_perdas = np.r_[outras_f, fim_f]
    zeros = np.zeros(outras_f.size, bool)
    termina_corrida = np.r_[zeros, np.ones(fim_f.size, bool)]
    so_por_lacuna_5 = np.r_[zeros, ~np.isin(fim_f, regular)]
    ordem = np.argsort(f_perdas, kind="stable")
    f_perdas = f_perdas[ordem]
    termina_corrida, so_por_lacuna_5 = termina_corrida[ordem], so_por_lacuna_5[ordem]

    # --- tabelas ----------------------------------------------------------
    period = frames["period"].to_numpy()
    n_frame = frames["frame"].to_numpy()
    tempo = frames["t"].to_numpy()

    fc = np.flatnonzero(controle)
    em_duelo = duelo[fc]
    dono_c = np.where(em_duelo, -1, dono[fc])
    control = pd.DataFrame(
        {
            "game": np.full(fc.size, game),
            "period": period[fc],
            "frame": n_frame[fc],
            "t": tempo[fc],
            "ball_control": np.where(em_duelo, DUEL, POSSESSION),
            "owner_id": np.where(dono_c >= 0, nomes[dono_c], None),
            "owner_team": np.where(dono_c >= 0, times[dono_c], None),
            "d_owner_m": np.where(em_duelo, np.nan, d_dono[fc]),
            "ds_m": cin["ds"][fc],
            "d0_x": cin["d0_x"][fc],
            "d0_y": cin["d0_y"][fc],
            "v0": cin["v0"][fc],
            "d1_x": cin["d1_x"][fc],
            "d1_y": cin["d1_y"][fc],
            "v1": cin["v1"][fc],
            "run_id": run_id[fc],
        }
    ).astype(CONTROL)

    dono_p = dono[f_perdas]
    perdas = pd.DataFrame(
        {
            "game": np.full(f_perdas.size, game),
            "period": period[f_perdas],
            "frame": n_frame[f_perdas],
            "t": tempo[f_perdas],
            "player_id": nomes[dono_p],
            "team": times[dono_p],
            "run_id": run_id[f_perdas],
            "termina_corrida": termina_corrida,
            "so_por_lacuna_5": so_por_lacuna_5,
            "ds_m": cin["ds"][f_perdas],
        }
    ).astype(PERDAS)

    sequencias = pd.DataFrame(
        {
            "game": np.full(f0.size, game),
            "period": period[f0],
            "run_id": run_id[f0],
            "frame_f0": n_frame[f0],
            "frame_fn": n_frame[fn],
            "n_quadros": fn - f0 + 1,
            "player_id": nomes[jogador_seq],
            "team": times[jogador_seq],
            "d0d1": d0d1,
            "dv_max": dv_max,
            "mudou_direcao": mudou_direcao,
            "mudou_velocidade": mudou_velocidade,
            "ganho": ganho,
        }
    ).astype(SEQUENCIAS)

    fg, jg = f0[ganho], jogador_seq[ganho]
    ganhos = pd.DataFrame(
        {
            "game": np.full(fg.size, game),
            "period": period[fg],
            "frame": n_frame[fg],
            "t": tempo[fg],
            "player_id": nomes[jg],
            "team": times[jg],
            "run_id": run_id[fg],
            "mudou_direcao": mudou_direcao[ganho],
            "mudou_velocidade": mudou_velocidade[ganho],
            "d0d1": d0d1[ganho],
            "dv_max": dv_max[ganho],
        }
    ).astype(GANHOS)

    contagens = {
        "game": game,
        "r_pz_m": r_pz,
        "r_dz_m": r_dz,
        "n_quadros": n_quadros,
        "dead_ball": int((~frames["ball_live"]).sum()),
        "possession": int(posse.sum()),
        "duel": int(duelo.sum()),
        "no_possession": int((frames["ball_live"].to_numpy() & ~controle).sum()),
        "control_frames": int(controle.sum()),
        "control_frames_zona": int((posse_zona | duelo).sum()),
        "quadros_falso_positivo": int((posse_zona & ~posse).sum()),
        "sequencias": int(f0.size),
        "sequencias_sem_mudanca": int((~ganho).sum()),
        "perdas": int(f_perdas.size),
        "perdas_termina_corrida": int(termina_corrida.sum()),
        "perdas_so_por_lacuna_5": int(so_por_lacuna_5.sum()),
        "ganhos": int(ganho.sum()),
        # CANARIO, nao medicao (comentario corrigido na Fatia 4): sob a leitura
        # implementada em `em_controle` -- UM dono por quadro, o mais proximo,
        # inclusive em duelo -- duas sequencias nao podem comecar no mesmo
        # quadro, logo este contador e identicamente 0 por construcao. Fica como
        # guarda: se virar > 0, a unicidade do dono quebrou. A ambiguidade que a
        # revisao de 2026-10-31 levantou (o controle alternando entre duelistas)
        # aparece em `ganhos_em_quadro_de_duelo` e no contador de trocas de dono
        # por duelo de `src.run`, nao aqui.
        "quadros_com_mais_de_um_ganho": int(
            (np.bincount(fg) > 1).sum() if fg.size else 0
        ),
        "ganhos_em_quadro_de_duelo": int(duelo[fg].sum()),
        "empates_distancia": empates[0],
        "empates_distancia_em_posse": empates[1],
        "corridas_vivas": int(inicios.size),
        "corridas_vivas_sem_posse": int((ultima_posse < 0).sum()),
        **cont_suav,
    }
    return {
        "control": validar(control, CONTROL, "control(jogo {})".format(game)),
        "perdas": validar(perdas, PERDAS, "perdas(jogo {})".format(game)),
        "ganhos": validar(ganhos, GANHOS, "ganhos(jogo {})".format(game)),
        "sequencias": validar(sequencias, SEQUENCIAS, "sequencias(jogo {})".format(game)),
        "frames": frames,
        "ds_m": cin["ds"],
        "contagens": contagens,
    }

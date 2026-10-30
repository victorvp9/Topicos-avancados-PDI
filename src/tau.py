"""Medicao da defasagem `tau` da anotacao, com o gatilho de G3.

Replica deliberada da analise do suplementar S3, p. 5, do Vidal-Codina, para ser
comparavel: para cada passe do gabarito, procura numa janela de +-10 s em torno
do quadro anotado o quadro de MENOR distancia entre a bola e o jogador anotado,
e mede `tau_s = (annotated_frame - frame_d) / fps`.

Sinal (S3, p. 5): *"Positive time lags indicate minimum distance in tracking
data occurred before the annotated event time"* -- logo `tau > 0` significa que a
anotacao veio DEPOIS do instante de minima distancia.

Regra normativa: docs/fatias/02-plano.md §6. Nenhuma constante aqui: janela,
limiar e faixa ambigua vem de `config.yaml:tau`.

O evento sem medida (jogador anotado sem dado em nenhum quadro da janela) fica
na tabela com `tau_s = NaN` e **conta no denominador** de toda fracao. Nunca
descartado (docs/01-definicoes.md, Avaliacao).
"""

import numpy as np
import pandas as pd

# Uma linha por passe do gabarito. `frame_d` e float porque e NaN quando nao ha
# medida -- um quadro inexistente nao pode ser representado por um int.
TAU = {
    "game": "int64",
    "period": "int64",
    "annotated_frame": "int64",
    "player_id": "str",
    "frame_d": "float64",
    "tau_s": "float64",
    "d_min_m": "float64",
    "d_no_quadro_anotado_m": "float64",
}



def _grade_de_posicoes(frames: pd.DataFrame, tracking: pd.DataFrame):
    """Densifica o tracking em matrizes indexadas por (jogador, quadro - 1).

    Entrada: `frames` e `tracking` de `src.io.carregar_jogo`.
    Saida: (jogadores, px, py, ball_x, ball_y), com `jogadores` um Index de
    `player_id` e `px`/`py` de forma (n_jogadores, n_quadros), NaN onde o
    jogador nao tem linha.

    Exige a grade de quadros contigua e 1-based (criterio de aceite da Fatia 1,
    plano §8.2); a indexacao por `frame - 1` depende disso.
    """
    frames = frames.sort_values("frame")
    grade = frames["frame"].to_numpy()
    n_quadros = grade.size
    if not np.array_equal(grade, np.arange(1, n_quadros + 1)):
        raise ValueError("grade de quadros nao e 1..N contigua; tau.py depende disso")

    jogadores = pd.Index(sorted(tracking["player_id"].unique()))
    px = np.full((jogadores.size, n_quadros), np.nan)
    py = np.full((jogadores.size, n_quadros), np.nan)
    linha = jogadores.get_indexer(tracking["player_id"])
    coluna = tracking["frame"].to_numpy() - 1
    px[linha, coluna] = tracking["x"].to_numpy()
    py[linha, coluna] = tracking["y"].to_numpy()
    return jogadores, px, py, frames["ball_x"].to_numpy(), frames["ball_y"].to_numpy()


def medir(game: int, eventos: pd.DataFrame, frames: pd.DataFrame,
          tracking: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Mede `tau` em todos os eventos `pass` do gabarito de um jogo (plano §6).

    Entrada: `eventos` no esquema `src.io.schema.EVENTS`; `frames` e `tracking`
    de `src.io.carregar_jogo`.
    Saida: DataFrame no esquema `TAU`, uma linha por passe, na ordem do gabarito.

    A janela e de `+-cfg['tau']['janela_s']` quadros em torno de
    `annotated_frame`, recortada nas bordas do JOGO (nao nas bordas de periodo:
    a grade de quadros e contigua entre os dois periodos e o plano §9.3 diz
    "recortado nas bordas do jogo").

    Empate de distancia minima: fica o quadro mais antigo da janela
    (`argmin` devolve a primeira ocorrencia) -- deterministico.
    """
    fps = cfg["tracking"]["fps"]
    meia_janela = round(cfg["tau"]["janela_s"] * fps)
    jogadores, px, py, ball_x, ball_y = _grade_de_posicoes(frames, tracking)
    n_quadros = ball_x.size

    passes = eventos[eventos["type"] == "pass"]
    anotado = passes["annotated_frame"].to_numpy()
    jog = jogadores.get_indexer(passes["player_id"])  # -1 se o jogador nao tem tracking

    deslocamentos = np.arange(-meia_janela, meia_janela + 1)
    janela = anotado[:, None] + deslocamentos[None, :]
    valido = (janela >= 1) & (janela <= n_quadros) & (jog >= 0)[:, None]
    col = np.where(valido, janela - 1, 0)
    lin = np.where(jog >= 0, jog, 0)[:, None]
    dx = ball_x[col] - px[lin, col]
    dy = ball_y[col] - py[lin, col]
    d = np.where(valido, np.sqrt(dx * dx + dy * dy), np.nan)

    # inf em vez de NaN para o argmin: quadro sem dado nunca pode ser o minimo.
    d_busca = np.where(np.isnan(d), np.inf, d)
    i = np.arange(len(passes))
    k = d_busca.argmin(axis=1)
    d_min = d_busca[i, k]
    sem_medida = np.isinf(d_min)
    frame_d = np.where(sem_medida, np.nan, janela[i, k].astype("float64"))

    saida = pd.DataFrame(
        {
            "game": passes["game"].to_numpy(),
            "period": passes["period"].to_numpy(),
            "annotated_frame": anotado,
            "player_id": passes["player_id"].to_numpy(),
            "frame_d": frame_d,
            "tau_s": (anotado - frame_d) / fps,
            "d_min_m": np.where(sem_medida, np.nan, d_min),
            "d_no_quadro_anotado_m": d[:, meia_janela],
        }
    ).astype(TAU)
    if list(saida.columns) != list(TAU):
        raise ValueError("tau(jogo " + str(game) + "): colunas fora do esquema TAU")
    return saida


def resumir(tabela: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Resumo por jogo mais a linha agregada `game = 0` (plano §6 e §9.5).

    Entrada: concatenacao das tabelas `TAU` dos jogos.
    Saida: uma linha por jogo (mais `game = 0`), com `n` (todos os passes),
    `n_medidos`, media e mediana de `tau_s` sobre os medidos, as fracoes de
    `|tau|` acima de cada faixa de `cfg['tau']['faixas_tau_s']`, as fracoes de
    `d_min_m` abaixo de cada faixa de `cfg['tau']['faixas_d_m']`, e a reproducao
    de docs/inspecao-metrica.md §6.4 (`d` no QUADRO ANOTADO, na faixa
    `cfg['tau']['faixa_sanidade_d_m']`).

    O nome de cada coluna de fracao sai do valor da faixa, logo mexer na faixa
    no `config.yaml` muda a coluna -- a constante nao pode ser ignorada.

    **Toda fracao tem por denominador `n`, nao `n_medidos`**: o "sem medida"
    sai do numerador, nunca do denominador (plano §6.1).
    """
    linhas = []
    for game, bloco in list(tabela.groupby("game", sort=True)) + [(0, tabela)]:
        tau = bloco["tau_s"].to_numpy()
        d_min = bloco["d_min_m"].to_numpy()
        d_anot = bloco["d_no_quadro_anotado_m"].to_numpy()
        n = tau.size
        medido = ~np.isnan(tau)
        linha = {
            "game": int(game),
            "n": n,
            "n_medidos": int(medido.sum()),
            "media_tau_s": float(np.nanmean(tau)) if medido.any() else np.nan,
            "mediana_tau_s": float(np.nanmedian(tau)) if medido.any() else np.nan,
        }
        for faixa in cfg["tau"]["faixas_tau_s"]:
            linha["frac_tau_gt_{:g}s".format(faixa)] = float((np.abs(tau) > faixa).sum()) / n
        for faixa in cfg["tau"]["faixas_d_m"]:
            linha["frac_d_min_lt_{:g}m".format(faixa)] = float((d_min < faixa).sum()) / n
        # Sanidade (plano §6.2): a mesma rotina no quadro anotado reproduz §6.4.
        sanidade = cfg["tau"]["faixa_sanidade_d_m"]
        linha["frac_d_anotado_lt_{:g}m".format(sanidade)] = float((d_anot < sanidade).sum()) / n
        linha["mediana_d_anotado_m"] = (
            float(np.nanmedian(d_anot)) if (~np.isnan(d_anot)).any() else np.nan
        )
        linhas.append(linha)
    return pd.DataFrame(linhas)


def gatilho_g3(tabela: pd.DataFrame, cfg: dict) -> dict:
    """Avalia o gatilho de G3 escrito ANTES de medir (plano §6.1).

    Entrada: concatenacao das tabelas `TAU` dos tres jogos.
    Saida: dict com `fracao` (|tau| > `limiar_g3_tau_s` sobre TODOS os passes),
    `limiar`, `disparou` (fracao > `limiar_g3_fracao`) e `ambiguo` (dentro de
    `faixa_ambigua`, caso em que se leva ao G3 de todo modo).

    A `faixa_ambigua` e FECHADA nas duas pontas: com [0,03, 0,08], uma fracao de
    exatamente 3,0 % ou 8,0 % e ambigua. Declarado aqui porque o plano §6.1 diz
    so "entre 3 % e 8 %", e a escolha conservadora -- a que leva mais casos ao
    G3 em vez de passar raspando -- e incluir as pontas.

    Se `disparou`, a janela de +-1 s do critario principal (D8) esta contradita e
    o projeto PARA antes de qualquer detector. A decisao e do Victor, nao do
    codigo.
    """
    limiar_tau = cfg["tau"]["limiar_g3_tau_s"]
    limiar_fracao = cfg["tau"]["limiar_g3_fracao"]
    baixo, alto = cfg["tau"]["faixa_ambigua"]
    tau = tabela["tau_s"].to_numpy()
    fracao = float((np.abs(tau) > limiar_tau).sum()) / tau.size
    return {
        "n": int(tau.size),
        "limiar_tau_s": limiar_tau,
        "limiar_fracao": limiar_fracao,
        "fracao": fracao,
        "disparou": bool(fracao > limiar_fracao),
        "ambiguo": bool(baixo <= fracao <= alto),
    }

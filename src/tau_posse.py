"""Medicao de `tau_posse` e a escada que decide a janela do criterio principal.

`tau_posse = (annotated_frame - loss_frame) / fps`: a defasagem entre o quadro
anotado de um passe e o quadro em que o Passo 1 emite a PERDA DE POSSE do
jogador anotado. E a grandeza que `docs/03-plano.md` (Fatia 3) exige, e e
comparavel ao instante que o detector de passe da Fatia 5 vai emitir -- ao
contrario do argmin de distancia da Fatia 2, que o G3 concluiu invalido neste
dataset.

Duas grandezas, separadas de proposito (plano 03 §6.1), porque junta-las foi o
erro da Fatia 2:

- **fracao sem perda** (`tem_perda = False`): teto de REVOCACAO. O detector nao
  produziu perda alguma daquele jogador perto dali. Resultado, nao portao.
- **distribuicao de `|tau_posse|` ENTRE OS QUE TEM PERDA**: e o portao, e o
  denominador da regra da escada.

A regra da escada esta PRE-REGISTRADA em `docs/03-plano.md` (Fatia 3) e em
`docs/decisoes.md`, escrita antes desta medicao: a janela e o MENOR valor de
`tau_posse.escada_janela_s` com no maximo `limiar_fracao` dos passes com perda
acima dela; nenhum valor fora da escada; se nem o maior satisfaz, para no G3.

Este modulo nao aplica a decisao a lugar nenhum: devolve o numero e a
recomendacao. Quem registra a mudanca e o orquestrador (plano §6.3).
"""

import numpy as np
import pandas as pd

# Uma linha por evento `pass` do gabarito (plano §5). `loss_frame` e float
# porque e NaN quando nao ha perda: quadro inexistente nao e int.
TAU_POSSE = {
    "game": "int64",
    "annotated_frame": "int64",
    "player_id": "str",
    "loss_frame": "float64",
    "tau_posse_s": "float64",
    "tem_perda": "bool",
}


def _mais_proximo(esquerda: pd.DataFrame, direita: pd.DataFrame, tol: int) -> np.ndarray:
    """Para cada linha de `esquerda`, o `frame` da linha de `direita` mais
    proxima do `annotated_frame`, no mesmo (`game`, `player_id`).

    Entrada: `esquerda` com (`game`, `annotated_frame`, `player_id`) e ORDENADA
    por `annotated_frame`; `direita` com (`game`, `player_id`, `frame`) e
    ordenada por `frame`; `tol` a meia-janela em quadros.
    Saida: array float64 com o `frame` casado, NaN onde nao ha candidato dentro
    de `tol` -- a janela e INCLUSIVA (`tolerance` do `merge_asof` e `<=`).

    Empate exato (um candidato `k` quadros antes e outro `k` depois) fica com o
    ANTERIOR, que e a convencao de `src/tau.py` ("o quadro mais antigo") e e
    deterministica.
    """
    if direita.empty:
        return np.full(len(esquerda), np.nan)
    anotado = esquerda["annotated_frame"].to_numpy()
    antes, depois = (
        pd.merge_asof(
            esquerda,
            direita,
            left_on="annotated_frame",
            right_on="frame",
            by=["game", "player_id"],
            direction=direcao,
            tolerance=tol,
        )["frame"].to_numpy(dtype="float64")
        for direcao in ("backward", "forward")
    )
    with np.errstate(invalid="ignore"):
        usa_antes = ~np.isnan(antes) & (
            np.isnan(depois) | (np.abs(anotado - antes) <= np.abs(anotado - depois))
        )
    return np.where(usa_antes, antes, depois)


def medir(eventos: pd.DataFrame, perdas: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Casa cada passe anotado com a perda de posse mais proxima do mesmo jogador.

    Entrada: `eventos` no esquema `src.io.schema.EVENTS` (um ou mais jogos) e
    `perdas` no esquema `src.possession.PERDAS` dos mesmos jogos.
    Saida: DataFrame no esquema `TAU_POSSE`, uma linha por evento `pass`, em
    ordem de (`game`, `annotated_frame`).

    A busca e por (`game`, `player_id`) numa janela INCLUSIVA de
    `+-tau_posse.janela_busca_s`, convertida em quadros (ver `_mais_proximo`).
    Passe sem perda nenhuma na janela FICA na tabela com `tem_perda = False` e
    `tau_posse_s = NaN` (plano §6.1): NaN nunca e descartado.

    A janela nao e recortada na borda de periodo, so na do jogo, como em
    `src/tau.py`: a grade de quadros e contigua entre os dois periodos.
    """
    fps = cfg["tracking"]["fps"]
    tol = int(round(cfg["tau_posse"]["janela_busca_s"] * fps))
    passes = (
        eventos[eventos["type"] == "pass"][["game", "annotated_frame", "player_id"]]
        .sort_values(["annotated_frame", "game"], kind="stable")
        .reset_index(drop=True)
    )
    anotado = passes["annotated_frame"].to_numpy()
    loss_frame = _mais_proximo(
        passes, perdas[["game", "player_id", "frame"]].sort_values("frame", kind="stable"),
        tol,
    )

    return pd.DataFrame(
        {
            "game": passes["game"].to_numpy(),
            "annotated_frame": anotado,
            "player_id": passes["player_id"].to_numpy(),
            "loss_frame": loss_frame,
            "tau_posse_s": (anotado - loss_frame) / fps,
            "tem_perda": ~np.isnan(loss_frame),
        }
    ).sort_values(["game", "annotated_frame"], kind="stable").reset_index(drop=True).astype(
        TAU_POSSE
    )


def resumir(tabela: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Resumo por jogo mais a linha agregada `game = 0`.

    Entrada: a tabela `TAU_POSSE` dos tres jogos.
    Saida: uma linha por jogo (mais `game = 0`, que e o conjunto agrupado da
    decisao), com `n`, `n_sem_perda`, `frac_sem_perda` (sobre TODOS os passes) e,
    **so entre os que tem perda**, `n_com_perda`, media, mediana, media de
    `|tau|` e as fracoes de `|tau|` acima de cada degrau da escada e de cada
    faixa de `tau.faixas_tau_s` (estas ultimas para comparar com o suplementar
    S3, p. 5, e com o que a Fatia 2 reportou).

    As duas familias de denominador estao separadas de proposito: `frac_sem_*`
    tem denominador `n`; toda `frac_tau_gt_*` tem denominador `n_com_perda`, que
    e o denominador da regra pre-registrada (plano §6.1).

    O nome de cada coluna de fracao sai do VALOR da faixa, logo mexer na faixa no
    `config.yaml` muda a coluna -- a constante nao pode ser ignorada.
    """
    faixas = list(cfg["tau_posse"]["escada_janela_s"]) + [
        f for f in cfg["tau"]["faixas_tau_s"] if f not in cfg["tau_posse"]["escada_janela_s"]
    ]
    linhas = []
    for game, bloco in list(tabela.groupby("game", sort=True)) + [(0, tabela)]:
        tau = bloco.loc[bloco["tem_perda"], "tau_posse_s"].to_numpy()
        n, n_com = len(bloco), tau.size
        linha = {
            "game": int(game),
            "n": n,
            "n_sem_perda": n - n_com,
            "frac_sem_perda": (n - n_com) / n if n else np.nan,
            "n_com_perda": n_com,
            "media_tau_s": float(tau.mean()) if n_com else np.nan,
            "mediana_tau_s": float(np.median(tau)) if n_com else np.nan,
            "media_abs_tau_s": float(np.abs(tau).mean()) if n_com else np.nan,
        }
        for faixa in faixas:
            linha["frac_tau_gt_{:g}s".format(faixa)] = (
                float((np.abs(tau) > faixa).sum()) / n_com if n_com else np.nan
            )
        linhas.append(linha)
    return pd.DataFrame(linhas)


def decompor_sem_perda(tabela: pd.DataFrame, control: pd.DataFrame,
                       perdas: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Decompoe os passes SEM perda, para dizer QUAL restricao morde.

    Entrada: `tabela` no esquema `TAU_POSSE`, e `control` e `perdas` dos mesmos
    jogos (esquemas de `src.possession`).
    Saida: uma linha por jogo mais `game = 0`, com `n`, `n_sem_perda` e as tres
    parcelas:

    - `sem_control_frame` **(i)**: o jogador anotado nao foi dono de control
      frame algum na janela -> a restricao e a PZ, isto e `R_pz`;
    - `com_control_sem_perda` **(ii)**: foi dono de algum control frame e ainda
      assim nenhuma perda saiu -> a restricao e a regra de perda (`eps_s` ou a
      condicao 2);
    - `casou_outro_jogador` **(iii)**: perda casada que NAO e do jogador
      anotado. Tem de ser zero: `medir` casa por (`game`, `player_id`). Medido,
      nao assumido.

    LIMITE DECLARADO de (i): "ser dono de control frame" exclui o duelo, onde
    nao existe dono. Um jogador que so participou de duelos perto do passe cai
    em (i), junto com quem nunca teve a bola na PZ. Separar os dois exigiria a
    matriz de distancias, que `control` nao carrega.

    E DIAGNOSTICO: nao recomenda mudar `R_pz` nem `eps_s`.
    """
    tol = int(round(cfg["tau_posse"]["janela_busca_s"] * cfg["tracking"]["fps"]))
    do_dono = (
        control.loc[control["ball_control"] == "possession", ["game", "owner_id", "frame"]]
        .rename(columns={"owner_id": "player_id"})
        .sort_values("frame", kind="stable")
    )
    esquerda = tabela.sort_values("annotated_frame", kind="stable")
    tem_control = ~np.isnan(_mais_proximo(esquerda, do_dono, tol))

    casadas = esquerda.loc[esquerda["tem_perda"], ["game", "player_id", "loss_frame"]]
    legitimas = (
        perdas[["game", "player_id", "frame"]]
        .rename(columns={"frame": "loss_frame"})
        .astype({"loss_frame": "float64"})
        .drop_duplicates()
    )
    de_outro = casadas.merge(legitimas, on=list(casadas), how="left", indicator=True)
    esquerda = esquerda.assign(
        tem_control=tem_control,
        de_outro=pd.Series(
            (de_outro["_merge"] == "left_only").to_numpy(), index=casadas.index
        ).reindex(esquerda.index, fill_value=False),
    )

    linhas = []
    for game, bloco in list(esquerda.groupby("game", sort=True)) + [(0, esquerda)]:
        sem = ~bloco["tem_perda"]
        linhas.append(
            {
                "game": int(game),
                "n": len(bloco),
                "n_sem_perda": int(sem.sum()),
                "sem_control_frame": int((sem & ~bloco["tem_control"]).sum()),
                "com_control_sem_perda": int((sem & bloco["tem_control"]).sum()),
                "casou_outro_jogador": int(bloco["de_outro"].sum()),
            }
        )
    return pd.DataFrame(linhas)


def decidir_janela(tabela: pd.DataFrame, cfg: dict) -> dict:
    """Aplica a escada PRE-REGISTRADA e devolve a recomendacao (plano §6.2).

    Entrada: a tabela `TAU_POSSE` dos tres jogos AGRUPADOS (o por jogo entra no
    relatorio, nao na decisao).
    Saida: dict com `janela_s` (o menor degrau de `escada_janela_s` com fracao
    `<= limiar_fracao`, ou `None`), `fracoes` (por degrau), `n`, `n_com_perda`,
    `frac_sem_perda`, `esgotada`, `sem_perda_acima_do_limiar` e `g3`.

    `g3` e verdadeiro quando a escada esgota OU quando a fracao sem perda passa
    de `limiar_sem_perda_g3` -- nesse segundo caso o portao mede pouca coisa e o
    plano manda levar ao G3 de todo modo.

    A funcao NUNCA devolve valor fora de `escada_janela_s`: sem interpolacao, sem
    percentil arredondado. O `assert` final existe para matar esse mutante.
    """
    t = cfg["tau_posse"]
    escada = list(t["escada_janela_s"])
    com_perda = tabela.loc[tabela["tem_perda"], "tau_posse_s"].to_numpy()
    n, n_com = len(tabela), com_perda.size
    fracoes = {
        float(j): float((np.abs(com_perda) > j).sum()) / n_com if n_com else np.nan
        for j in escada
    }
    janela = next((float(j) for j in escada if fracoes[float(j)] <= t["limiar_fracao"]), None)
    frac_sem_perda = (n - n_com) / n if n else np.nan
    sem_perda_acima = bool(frac_sem_perda > t["limiar_sem_perda_g3"])
    assert janela is None or janela in [float(j) for j in escada]
    return {
        "janela_s": janela,
        "fracoes": fracoes,
        "escada": escada,
        "limiar_fracao": t["limiar_fracao"],
        "limiar_sem_perda_g3": t["limiar_sem_perda_g3"],
        "n": n,
        "n_com_perda": n_com,
        "frac_sem_perda": frac_sem_perda,
        "esgotada": janela is None,
        "sem_perda_acima_do_limiar": sem_perda_acima,
        "g3": bool(janela is None or sem_perda_acima),
    }

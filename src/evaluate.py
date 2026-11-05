"""Casador de eventos, metricas P/R/F1 e matriz de confusao.

Regras normativas: docs/fatias/02-plano.md §2, §3, §5 e §7, e
docs/01-definicoes.md (Avaliacao). Nenhuma constante aqui: janelas e eixos dos
criterios vem de `config.yaml:avaliacao`.

Os tres criterios sao tres escolhas em tres eixos, NAO tres nomes para a mesma
coisa (correcao de leitura do S2, p. 3, registrada em decisoes.md):

    criterio       casa tipo?  casa jogador?  janela
    estrito        sim         sim            +-1,0 s   <- NOSSO, D8, nao de artigo
    vidal_codina   NAO         sim            +-10,0 s  supl. S2, p. 3
    mills          sim         NAO            +-3,0 s   Mills §2.2, p. 4

No criterio do Vidal-Codina a comparacao de tipo E a matriz de confusao, nao uma
condicao de casamento: *"A discrete event is correctly detected if it is executed
by the annotated player and is within a +-10 s window of the annotated time"*
(S2, p. 3), seguido de *"present the detection results using confusion
matrices"*.

O casamento e um-para-um e OTIMO, com objetivo lexicografico: (1) maximiza o
numero de pares; (2) entre os maximos, minimiza `sum |dt|`. Guloso por "mais
proximo no tempo" pode consumir a unica deteccao compativel com outro evento
anotado (plano §3).

Nada sai do denominador: evento nao detectado e perda de revocacao, nunca
exclusao -- inclusive os 13 eventos com `no_dead_ball_before = True`
(decisoes.md, armadilha da Fatia 1). Precisao e revocacao com denominador zero
sao `NaN`, nunca 0,0.
"""

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from src.io import schema

# Rotulo da linha de falso positivo e da coluna de falso negativo da matriz
# (plano §2.1).
NONE = "none"

# Entrada do casador (plano §5). Mesmo dominio de `events`, com o minimo.
DETECTIONS = {
    "game": "int64",
    "period": "int64",
    "frame": "int64",
    "t": "float64",
    "type": "str",
    "team": "str",
    "player_id": "str",
}

# Saida do casador (plano §5). `game = 0` e a linha agregada (soma, nao media).
#
# TRES contagens de acerto, porque sob casamento sem tipo elas divergem:
#
#   `tp_diag`  pares casados em que `tipo_gabarito == tipo_detectado`. E A
#              DIAGONAL DA MATRIZ DE CONFUSAO, e e o UNICO numerador de
#              `precisao`, `revocacao` e `f1`, nos TRES criterios.
#   `tp`       pares casados contados pelo tipo do GABARITO, ignorando o tipo
#              detectado. Diagnostico: "quantos eventos deste tipo o criterio
#              casou com alguma deteccao".
#   `tp_det`   os mesmos pares contados pelo tipo da DETECCAO. Diagnostico.
#
# Em `estrito` e `mills`, que casam por tipo, `tp_diag == tp == tp_det` por
# construcao. Em `vidal_codina` nao: um escanteio anotado casado com um tiro
# livre detectado entra em `tp` e em `tp_det`, mas NAO em `tp_diag` -- conta
# contra a revocacao do escanteio e contra a precisao do tiro livre.
#
# Isto e o que o artigo faz: P e R saem da diagonal da matriz (§3.1, p. 9, Fig.
# 7a), e no mesmo paragrafo os 254 chutes rotulados como passe contam CONTRA a
# revocacao de chute (78 de precisao vs 53 de revocacao). Usar `tp` como
# numerador daria F1 = 1,00 para um detector que erra TODOS os tipos, isto e
# esconderia exatamente o modo de erro que este projeto existe para medir
# (escanteio virando tiro livre, §2.4.1, p. 8). Corrigido na revisao da Fatia 2;
# o esquema do plano §5 nao previa a assimetria.
#
# Identidades, sempre: `tp_diag + fn = n_gabarito` e `tp_diag + fp = n_detectado`.
RESULTADO = {
    "criterio": "str",
    "ancora": "str",
    "game": "int64",
    "type": "str",
    "n_gabarito": "int64",
    "n_detectado": "int64",
    "tp_diag": "int64",
    "tp": "int64",
    "tp_det": "int64",
    "fp": "int64",
    "fn": "int64",
    "precisao": "float64",
    "revocacao": "float64",
    "f1": "float64",
}

# Matriz de confusao em formato longo, uma por grupo (plano §2.1). Linha = tipo
# anotado, coluna = tipo detectado; so as celulas nao vazias aparecem.
CONFUSAO = {
    "criterio": "str",
    "ancora": "str",
    "grupo": "str",
    "game": "int64",
    "type_gabarito": "str",
    "type_detectado": "str",
    "n": "int64",
}


def grupo_por_tipo(cfg: dict) -> dict:
    """`tipo -> nome do grupo`, de `config.yaml:avaliacao.grupos` (S2, p. 3)."""
    return {
        tipo: nome
        for nome, tipos in cfg["avaliacao"]["grupos"].items()
        for tipo in tipos
    }


def casar(gab: pd.DataFrame, det: pd.DataFrame, janela_s: float,
          casa_tipo: bool, casa_jogador: bool):
    """Casamento um-para-um otimo entre gabarito e deteccoes (plano §3).

    Entrada: dois DataFrames com as colunas `game`, `grupo`, `type`,
    `player_id` e `t` (segundos, JA na ancora desejada). O indice e ignorado.
    Saida: `(i_gab, i_det)`, dois arrays de indices POSICIONAIS de mesmo
    tamanho, ordenados por `i_gab`.

    Um par e permitido quando cai no mesmo bloco -- sempre o mesmo `game` e o
    mesmo `grupo`, mais o mesmo `type` se `casa_tipo` e o mesmo `player_id` se
    `casa_jogador` -- e `|dt| <= janela_s` (janela INCLUSIVA,
    `config.yaml:avaliacao.janela_inclusiva`). `t = NaN` nunca e permitido.

    Casar so dentro do grupo e decisao do codificador, nao do plano: sem ela um
    par entre grupos (p. ex. passe anotado x escanteio detectado, que o
    `vidal_codina` permitiria por ignorar o tipo) quebraria a identidade "toda
    linha da matriz do grupo soma a contagem do gabarito", porque a matriz e uma
    por grupo. Ver o relatorio da Fatia 2.

    Como par proibido nunca cruza bloco, o problema se decompoe por bloco sem
    perder a otimalidade, e nenhuma matriz global e construida (plano §11.4).
    Dentro do bloco, `custo = |dt|` para par permitido e `custo = M` para par
    proibido, com `M = 1 + sum |dt| permitidos`; `linear_sum_assignment` da o
    otimo lexicografico e todo par de custo `M` e descartado depois.
    """
    chaves = ["game", "grupo"]
    if casa_tipo:
        chaves.append("type")
    if casa_jogador:
        chaves.append("player_id")
    blocos_gab = gab.reset_index(drop=True).groupby(chaves, sort=True).indices
    blocos_det = det.reset_index(drop=True).groupby(chaves, sort=True).indices
    t_gab = gab["t"].to_numpy()
    t_det = det["t"].to_numpy()

    pares_g, pares_d = [], []
    for chave in sorted(blocos_gab):
        if chave not in blocos_det:
            continue
        gi = blocos_gab[chave]
        dj = blocos_det[chave]
        dt = np.abs(t_gab[gi][:, None] - t_det[dj][None, :])
        permitido = np.isfinite(dt) & (dt <= janela_s)
        if not permitido.any():
            continue
        grande = 1.0 + dt[permitido].sum()
        custo = np.where(permitido, dt, grande)
        linha, coluna = linear_sum_assignment(custo)
        casado = custo[linha, coluna] < grande  # descarta todo par proibido
        pares_g.append(gi[linha[casado]])
        pares_d.append(dj[coluna[casado]])

    if not pares_g:
        return np.empty(0, dtype="int64"), np.empty(0, dtype="int64")
    i_gab = np.concatenate(pares_g)
    i_det = np.concatenate(pares_d)
    ordem = np.argsort(i_gab, kind="stable")
    return i_gab[ordem], i_det[ordem]


def _razao(numerador: int, denominador: int) -> float:
    """`NaN` quando o denominador e zero, nunca 0,0 (plano §5)."""
    return float(numerador) / denominador if denominador > 0 else np.nan


def _f1(precisao: float, revocacao: float) -> float:
    """`NaN` se precisao ou revocacao for indefinida; 0,0 se as duas forem 0."""
    if np.isnan(precisao) or np.isnan(revocacao):
        return np.nan
    if precisao + revocacao == 0.0:
        return 0.0
    return 2.0 * precisao * revocacao / (precisao + revocacao)


def _recusar_penalty(resultado: pd.DataFrame, funcao: str) -> None:
    """`penalty` tem n = 1 nos tres jogos: num agregado ele nao sustenta F1.

    A proibicao e guarda de codigo, nao comentario: um relatorio que juntasse
    todos os tipos de `bola_parada` incluiria o penalti em silencio.
    """
    if (resultado["type"] == "penalty").any():
        raise ValueError(
            "{}: `penalty` tem n = 1 nos tres jogos e nunca entra em agregado; "
            "reporte a contagem absoluta dele e filtre-o antes de agregar".format(funcao)
        )


def _recusar_mistura(resultado: pd.DataFrame, funcao: str) -> None:
    """Somar linhas de dois criterios, duas ancoras ou dois jogos produz um
    agregado sem sentido em silencio (decisoes.md, 2026-10-30). Quem agrega
    jogos chama a funcao por jogo e soma contagens, ou usa
    `src.experiment.agregar` (plano 08 §3)."""
    for coluna in ("criterio", "ancora", "game"):
        if coluna in resultado.columns and resultado[coluna].nunique() > 1:
            raise ValueError(
                "{}: mais de um valor de `{}` ({}); agregue um por vez".format(
                    funcao, coluna, sorted(resultado[coluna].unique().tolist()))
            )


def micro(resultado: pd.DataFrame) -> dict:
    """Agregacao MICRO de um conjunto de linhas de `resultado`: soma `tp_diag`,
    `n_gabarito` e `n_detectado` e so DEPOIS calcula P/R/F1.

    Entrada: um subconjunto de linhas de `resultado` (um criterio, uma ancora,
    um `game`, os tipos que se quer juntar). Saida: dict com as somas e P/R/F1.

    **Nao e** `media_ponderada_f1`, e as duas dao numero diferente: nos 13
    eventos `no_dead_ball_before`, filtra-los move o F1 de bola parada em
    +2,2530 pontos no micro e +2,3709 na media ponderada. "Agregado" sem
    qualificar e ambiguo e ja produziu um erro de escrita no projeto; chamar
    pelo nome e a correcao (revisao da Fatia 2).

    **Nunca inclua `penalty`** (n = 1 nos tres jogos) num agregado: a guarda
    abaixo estoura, em vez de deixar a proibicao so no docstring. Linhas de
    mais de um `criterio`, `ancora` ou `game` tambem estouram.
    """
    _recusar_penalty(resultado, "micro")
    _recusar_mistura(resultado, "micro")
    n_gabarito = int(resultado["n_gabarito"].sum())
    n_detectado = int(resultado["n_detectado"].sum())
    tp_diag = int(resultado["tp_diag"].sum())
    precisao = _razao(tp_diag, n_detectado)
    revocacao = _razao(tp_diag, n_gabarito)
    return {
        "n_gabarito": n_gabarito,
        "n_detectado": n_detectado,
        "tp_diag": tp_diag,
        "precisao": precisao,
        "revocacao": revocacao,
        "f1": _f1(precisao, revocacao),
    }


def media_ponderada_f1(resultado: pd.DataFrame) -> float:
    """Media dos F1 por tipo, ponderada por `n_gabarito`, ignorando os `NaN`.

    A outra leitura de "agregado"; ver `micro`, que e a que os documentos do
    projeto usam. `penalty` tambem e recusado aqui, e a mistura de `criterio`,
    `ancora` ou `game` tambem.
    """
    _recusar_penalty(resultado, "media_ponderada_f1")
    _recusar_mistura(resultado, "media_ponderada_f1")
    peso = resultado["n_gabarito"].to_numpy()
    if peso.sum() == 0:
        return np.nan
    return float(np.nansum(resultado["f1"].to_numpy() * peso) / peso.sum())


def _conferir_denominador_secundario(cfg: dict) -> None:
    """So `events_sem_bola_parada` esta implementado. O valor antigo `events`
    (1009/1131/1358) ESTOURA: nao ha caminho silencioso para o numero velho
    (plano 05 §3.2; decisoes.md, 2026-11-04)."""
    valor = cfg["avaliacao"]["denominador_passe_secundario"]
    if valor != "events_sem_bola_parada":
        raise NotImplementedError(
            "avaliacao.denominador_passe_secundario={!r} nao implementado; o normativo e "
            "`events_sem_bola_parada` (987/1115/1347, decisoes.md 2026-11-04)".format(valor)
        )


def gabarito_secundario(eventos: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Gabarito SECUNDARIO de passe (D10, refinado em 2026-11-04).

    Entrada: `eventos` no esquema `src.io.schema.EVENTS`. Saida: as linhas com
    `pass_secundario` e `type` fora do grupo `bola_parada` de
    `config.yaml:avaliacao.grupos`, com `type` reescrito para `pass` (a uniao
    `PASS` U `BALL LOST` U `BALL OUT` sem `THEFT` e o que o detector chama de
    passe), mesmo esquema. Nos tres jogos: 987 / 1115 / 1347.

    O tiro de meta sai porque o detector o rotula `goal_kick` e suprime a perda
    correspondente (plano 05 §3.2): mante-lo seria falso negativo estrutural.
    """
    _conferir_denominador_secundario(cfg)
    fora = eventos["type"].isin(cfg["avaliacao"]["grupos"]["bola_parada"])
    return eventos[eventos["pass_secundario"] & ~fora].assign(type="pass").reset_index(drop=True)


def avaliar(eventos: pd.DataFrame, deteccoes: pd.DataFrame, cfg: dict):
    """Casa, conta e devolve `(resultado, confusao)` nos esquemas deste modulo.

    Entrada:
      `eventos`    gabarito da Fatia 1 (esquema `src.io.schema.EVENTS`); precisa
                   das colunas `game`, `type`, `player_id` e das duas ancoras
                   (`config.yaml:avaliacao.ancoras`). Eventos de tipo fora dos
                   grupos (`fora_do_escopo`) **nao sao avaliados** e nao entram
                   em nenhum denominador: nao sao evento do nosso vocabulario.
      `deteccoes`  esquema `DETECTIONS`. Tipo fora dos grupos e erro duro.

    Avalia todo criterio de `config.yaml:avaliacao.criterios` em toda ancora de
    `config.yaml:avaliacao.ancoras` (plano §7: o risco declarado da ancoragem
    exige reportar bola parada nas duas). A ancora muda o instante do GABARITO:
    `t = eventos[ancora] / fps`. Para `pass`, `anchor_shift = 0` e as duas
    ancoras coincidem.

    Toda linha de `resultado` existe para todo tipo dos grupos, mesmo com
    contagem zero -- inclusive `free_kick?`, que o gabarito nunca produz e que
    **nunca e somado em `free_kick`** (S2, p. 3, e Fig. S1, p. 2), e `penalty`,
    que tem n = 1 nos tres jogos e por isso e reportado como contagem absoluta e
    **nunca entra num agregado** (ver `micro`).
    """
    fps = cfg["tracking"]["fps"]
    grupo_de = grupo_por_tipo(cfg)
    avaliacao = cfg["avaliacao"]
    # As tres chaves declarativas do config sao conferidas, nao ignoradas: a
    # alternativa de cada uma nao esta implementada (plano §10, nao generalizar).
    if not avaliacao["janela_inclusiva"]:
        raise NotImplementedError("avaliacao.janela_inclusiva=false nao implementado")
    _conferir_denominador_secundario(cfg)
    if avaliacao["criterio_principal"] not in avaliacao["criterios"]:
        raise ValueError(
            "avaliacao.criterio_principal={!r} nao esta em avaliacao.criterios".format(
                avaliacao["criterio_principal"]
            )
        )
    schema.validar(deteccoes, DETECTIONS, "deteccoes")
    faltando = [c for c in ("game", "type", "player_id") if c not in eventos.columns]
    if faltando:
        raise ValueError("eventos: faltam as colunas " + str(faltando))
    desconhecidos = sorted(set(deteccoes["type"]) - set(grupo_de))
    if desconhecidos:
        raise ValueError(
            "deteccoes: tipo(s) {!r} fora de config.yaml:avaliacao.grupos".format(desconhecidos)
        )

    gab_todo = eventos[eventos["type"].isin(grupo_de)].reset_index(drop=True)
    det = deteccoes.reset_index(drop=True)
    det = det.assign(grupo=det["type"].map(grupo_de))
    jogos = sorted(set(gab_todo["game"]) | set(det["game"]))
    tipos = [(nome, tipo) for nome, lista in cfg["avaliacao"]["grupos"].items() for tipo in lista]

    n_det = det.value_counts(["game", "type"])
    linhas, celulas = [], []
    for criterio, eixos in cfg["avaliacao"]["criterios"].items():
        for ancora in cfg["avaliacao"]["ancoras"]:
            gab = gab_todo.assign(
                grupo=gab_todo["type"].map(grupo_de),
                t=gab_todo[ancora] / fps,
            )
            i_gab, i_det = casar(
                gab, det, eixos["janela_s"], eixos["casa_tipo"], eixos["casa_jogador"]
            )

            casados = pd.DataFrame(
                {
                    "grupo": gab["grupo"].to_numpy()[i_gab],
                    "game": gab["game"].to_numpy()[i_gab],
                    "type_gabarito": gab["type"].to_numpy()[i_gab],
                    "type_detectado": det["type"].to_numpy()[i_det],
                }
            )
            sem_par_g = np.setdiff1d(np.arange(len(gab)), i_gab)
            sem_par_d = np.setdiff1d(np.arange(len(det)), i_det)
            cel = pd.concat(
                [
                    casados,
                    pd.DataFrame(
                        {
                            "grupo": gab["grupo"].to_numpy()[sem_par_g],
                            "game": gab["game"].to_numpy()[sem_par_g],
                            "type_gabarito": gab["type"].to_numpy()[sem_par_g],
                            "type_detectado": NONE,
                        }
                    ),
                    pd.DataFrame(
                        {
                            "grupo": det["grupo"].to_numpy()[sem_par_d],
                            "game": det["game"].to_numpy()[sem_par_d],
                            "type_gabarito": NONE,
                            "type_detectado": det["type"].to_numpy()[sem_par_d],
                        }
                    ),
                ],
                ignore_index=True,
            ).value_counts(["grupo", "game", "type_gabarito", "type_detectado"])
            for (grupo, game, tipo_g, tipo_d), n in cel.items():
                celulas.append((criterio, ancora, grupo, int(game), tipo_g, tipo_d, int(n)))

            n_gab = gab.value_counts(["game", "type"])
            tp_gab = casados.value_counts(["game", "type_gabarito"])
            tp_det = casados.value_counts(["game", "type_detectado"])
            tp_diag = casados[
                casados["type_gabarito"] == casados["type_detectado"]
            ].value_counts(["game", "type_gabarito"])
            for _, tipo in tipos:
                total = dict.fromkeys(
                    ("n_gabarito", "n_detectado", "tp_diag", "tp", "tp_det"), 0
                )
                for game in jogos:
                    conta = {
                        "n_gabarito": int(n_gab.get((game, tipo), 0)),
                        "n_detectado": int(n_det.get((game, tipo), 0)),
                        "tp_diag": int(tp_diag.get((game, tipo), 0)),
                        "tp": int(tp_gab.get((game, tipo), 0)),
                        "tp_det": int(tp_det.get((game, tipo), 0)),
                    }
                    linhas.append((criterio, ancora, game, tipo, conta))
                    for chave, valor in conta.items():
                        total[chave] += valor
                linhas.append((criterio, ancora, 0, tipo, total))

    resultado = pd.DataFrame(
        [
            {
                "criterio": criterio,
                "ancora": ancora,
                "game": game,
                "type": tipo,
                "n_gabarito": conta["n_gabarito"],
                "n_detectado": conta["n_detectado"],
                "tp_diag": conta["tp_diag"],
                "tp": conta["tp"],
                "tp_det": conta["tp_det"],
                "fp": conta["n_detectado"] - conta["tp_diag"],
                "fn": conta["n_gabarito"] - conta["tp_diag"],
                "precisao": _razao(conta["tp_diag"], conta["n_detectado"]),
                "revocacao": _razao(conta["tp_diag"], conta["n_gabarito"]),
                "f1": _f1(
                    _razao(conta["tp_diag"], conta["n_detectado"]),
                    _razao(conta["tp_diag"], conta["n_gabarito"]),
                ),
            }
            for criterio, ancora, game, tipo, conta in linhas
        ]
    ).astype(RESULTADO)
    confusao = pd.DataFrame(celulas, columns=list(CONFUSAO)).astype(CONFUSAO)
    return (
        schema.validar(resultado, RESULTADO, "resultado"),
        schema.validar(confusao, CONFUSAO, "confusao"),
    )


def deteccoes_do_gabarito(eventos: pd.DataFrame, ancora: str, cfg: dict) -> pd.DataFrame:
    """Converte o gabarito em deteccoes perfeitas (esquema `DETECTIONS`).

    So existe porque a Fatia 2 nao tem detector: toda deteccao vem de fixture ou
    de perturbacao do gabarito (plano §10). `t = eventos[ancora] / fps`, para que
    o gabarito contra si mesmo seja identidade na ancora avaliada.
    """
    grupo_de = grupo_por_tipo(cfg)
    base = eventos[eventos["type"].isin(grupo_de)]
    return (
        pd.DataFrame(
            {
                "game": base["game"].to_numpy(),
                "period": base["period"].to_numpy(),
                "frame": base[ancora].to_numpy(),
                "t": base[ancora].to_numpy() / cfg["tracking"]["fps"],
                "type": base["type"].to_numpy(),
                "team": base["team"].to_numpy(),
                "player_id": base["player_id"].to_numpy(),
            }
        )
        .astype(DETECTIONS)
        .reset_index(drop=True)
    )

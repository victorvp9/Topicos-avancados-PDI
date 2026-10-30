"""Gabarito de eventos: mapeamento Metrica -> vocabulario interno, fusao do
`SET PIECE` com a linha de execucao e ancoragem no primeiro quadro em jogo.

Regras normativas: docs/fatias/01-plano.md §5 e §6; contagens de referencia em
docs/inspecao-metrica.md §3. Nenhuma regra e inventada aqui; o mapeamento vem
de `mapeamento-eventos.yaml`.

Nenhum evento e descartado: o que nao cai no vocabulario interno fica na tabela
com `type = "fora_do_escopo"`, porque a Fatia 2 precisa dele para contar falsos
positivos.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.io import metrica_csv, metrica_epts, schema

FORA_DO_ESCOPO = "fora_do_escopo"


def _subtipos(subtype, separador: str) -> frozenset:
    """Conjunto de subtipos atomicos de uma linha crua.

    Jogos 1 e 2 juntam os subtipos numa string separada por `separador`; o jogo
    3 ja chega normalizado em `"A+B"` (plano §5 regra 1).
    """
    if not isinstance(subtype, str) or not subtype:
        return frozenset()
    return frozenset(subtype.replace("+", separador).split(separador))


def _normalizar_subtypes_json(subtypes) -> str:
    """`subtypes` do jogo 3 e None, dict ou LISTA de dicts. Une ordenado por `+`."""
    if subtypes is None:
        return ""
    if isinstance(subtypes, dict):
        return subtypes["name"]
    return "+".join(sorted(s["name"] for s in subtypes))


def _ler_linhas_cruas(game: int, cfg: dict) -> list:
    """Le a tabela de eventos crua do disco, sem classificar nada."""
    raiz = cfg["dados"]["raiz"]
    if game in (1, 2):
        bruto = pd.read_csv(metrica_csv.caminho_eventos(raiz, game))
        return [
            {
                "period": int(p),
                "annotated_frame": int(f),
                "metrica_type": str(t),
                "metrica_subtype": s if isinstance(s, str) else "",
                "team": str(team).lower(),
                "camisa": metrica_csv.numero_camisa(str(frm)),
            }
            for p, f, t, s, team, frm in zip(
                bruto["Period"],
                bruto["Start Frame"],
                bruto["Type"],
                bruto["Subtype"],
                bruto["Team"],
                bruto["From"],
            )
        ]
    if game == 3:
        meta = metrica_epts.ler_metadata(metrica_epts.caminho_metadata(raiz))
        dados = json.loads(Path(metrica_epts.caminho_eventos(raiz)).read_text(encoding="utf-8"))
        linhas = []
        for ev in dados["data"]:
            jogador = meta["jogadores"][ev["from"]["id"]]
            linhas.append(
                {
                    "period": int(ev["period"]),
                    "annotated_frame": int(ev["start"]["frame"]),
                    "metrica_type": ev["type"]["name"],
                    "metrica_subtype": _normalizar_subtypes_json(ev["subtypes"]),
                    "team": jogador["team"],
                    "camisa": jogador["camisa"],
                }
            )
        return linhas
    raise ValueError("jogo " + str(game) + " desconhecido")


def carregar_eventos_crus(game: int, cfg: dict, mapeamento: dict) -> pd.DataFrame:
    """Le a tabela de eventos crua e aplica o mapeamento linha a linha.

    Saida (uma linha por linha crua, na ordem original):
      `row` int        indice 0-based da linha crua
      `game`, `period` int
      `annotated_frame` int   `Start Frame` cru
      `type` str       vocabulario interno ou `fora_do_escopo`
      `team` str       `home` / `away`
      `player_id` str  mesmo dominio de `tracking`
      `metrica_type`, `metrica_subtype` str  strings cruas (jogo 3: lista unida por `+`)
      `pass_secundario` bool  criterio secundario de passe (D10), por linha CRUA

    `pass_secundario` aqui e DESCRITIVO do vocabulario da Metrica: 1086 / 1208 /
    1447 linhas cruas (`PASS` U `BALL LOST` U `BALL OUT` sem `THEFT`,
    docs/inspecao-metrica.md §3.5). O DENOMINADOR DE AVALIACAO e o da tabela
    `events` (1009 / 1131 / 1358), menor porque a execucao de uma bola parada e
    fundida no evento de bola parada e deixa de contar como passe. Ver
    `construir_gabarito`.

    Estoura se a Metrica trouxer um `Type` ou um subtipo atomico que nao esta
    em `mapeamento-eventos.yaml` (plano §5).
    """
    linhas = _ler_linhas_cruas(game, cfg)

    separador = mapeamento["separador_subtipo_csv"]
    modificadores = frozenset(mapeamento["modificadores"])
    tipos_conhecidos = frozenset(mapeamento["tipos_conhecidos"])
    subtipos_conhecidos = frozenset(mapeamento["subtipos_conhecidos"])
    mapa_set_piece = mapeamento["set_piece"]
    marcador_goal_kick = mapeamento["goal_kick"]["subtipo"]
    tipos_goal_kick = frozenset(mapeamento["goal_kick"]["tipos"])
    tipo_passe = mapeamento["passe"]["tipo"]
    tipos_secundario = frozenset(mapeamento["passe_secundario"]["tipos"])
    excluir_secundario = frozenset(mapeamento["passe_secundario"]["excluir_subtipos"])

    for row, linha in enumerate(linhas):
        tipo_cru = linha["metrica_type"]
        if tipo_cru not in tipos_conhecidos:
            raise ValueError(
                "jogo {} linha {}: Type {!r} nao esta em "
                "mapeamento-eventos.yaml:tipos_conhecidos".format(game, row, tipo_cru)
            )
        subs = _subtipos(linha["metrica_subtype"], separador)
        desconhecidos = subs - subtipos_conhecidos
        if desconhecidos:
            raise ValueError(
                "jogo {} linha {}: subtipo(s) {!r} de {!r} nao estao em "
                "mapeamento-eventos.yaml:subtipos_conhecidos".format(
                    game, row, sorted(desconhecidos), linha["metrica_subtype"]
                )
            )

        if tipo_cru == "SET PIECE":
            principal = subs - modificadores
            if len(principal) != 1:
                raise ValueError(
                    "jogo {} linha {}: SET PIECE com subtipo principal {!r}, "
                    "esperado exatamente um".format(game, row, sorted(principal))
                )
            chave = next(iter(principal))
            if chave not in mapa_set_piece:
                raise ValueError(
                    "jogo {} linha {}: SET PIECE/{!r} nao esta em "
                    "mapeamento-eventos.yaml:set_piece".format(game, row, chave)
                )
            linha["type"] = mapa_set_piece[chave]
        elif marcador_goal_kick in subs and tipo_cru in tipos_goal_kick:
            linha["type"] = "goal_kick"
        elif tipo_cru == tipo_passe:
            linha["type"] = "pass"
        else:
            linha["type"] = FORA_DO_ESCOPO

        linha["pass_secundario"] = bool(
            tipo_cru in tipos_secundario and not (subs & excluir_secundario)
        )
        linha["row"] = row
        linha["game"] = game
        linha["player_id"] = "g{}_{}_{}".format(game, linha["team"], linha["camisa"])

    colunas = [
        "row",
        "game",
        "period",
        "annotated_frame",
        "type",
        "team",
        "player_id",
        "metrica_type",
        "metrica_subtype",
        "pass_secundario",
    ]
    return pd.DataFrame(linhas)[colunas].astype(
        {
            "row": "int64",
            "game": "int64",
            "period": "int64",
            "annotated_frame": "int64",
            "pass_secundario": "bool",
        }
    )


def ancorar(annotated_frames: np.ndarray, ball_live: np.ndarray, guarda_quadros: int):
    """Primeiro quadro em jogo apos o intervalo de bola morta (plano §6.2).

        i = annotated_frame
        j = maior quadro <= i com ball_live[j] == False    # ultimo quadro morto
        frame = j + 1                                      # primeiro quadro em jogo

        # GUARDA (G3 de 2026-10-29): a ancora nao pode mover o evento mais de 10 s
        if (i - frame) > guarda_quadros:
            frame = i
            no_dead_ball_before = True

    Se nao existir tal `j`, `frame = i` e `no_dead_ball_before = True`
    (o pontape inicial do quadro 1 do jogo 1, plano §6.3).

    A guarda existe porque em 12 de 296 bolas paradas a bola nunca fica NaN
    antes do evento (limitacao declarada do D1, docs/inspecao-metrica.md §5.3) e
    a busca "ultimo quadro morto <= i" volta ate o inicio da corrida viva
    inteira -- saltos de ate 169,7 s e dois pares de eventos no mesmo quadro.
    Origem dos 10 s: janela do critério oficial de benchmarking (Vidal-Codina
    suplementar S2, p. 3); `config.yaml:gabarito.guarda_ancora_s`.

    `ball_live` e indexado por `frame - 1`; `frame` e 1-based e contiguo.
    Devolve (frames, sem_morto_antes).

    Estoura se o quadro ancorado sair da grade ou nao estiver em jogo: erro
    silencioso aqui envenenaria o gabarito inteiro.
    """
    annotated_frames = np.asarray(annotated_frames, dtype="int64")
    vivo_por_quadro = np.asarray(ball_live, dtype=bool)
    n_quadros = vivo_por_quadro.size
    mortos = np.flatnonzero(~vivo_por_quadro)  # posicoes 0-based
    if mortos.size == 0:
        return annotated_frames.copy(), np.ones(annotated_frames.size, dtype=bool)
    k = np.searchsorted(mortos, annotated_frames - 1, side="right") - 1
    sem_morto_antes = k < 0
    frames = np.where(sem_morto_antes, annotated_frames, mortos[np.maximum(k, 0)] + 2)

    longe = (annotated_frames - frames) > guarda_quadros
    frames = np.where(longe, annotated_frames, frames)
    sem_morto_antes = sem_morto_antes | longe

    fora = frames > n_quadros
    if fora.any():
        raise ValueError(
            "ancoragem apontou para o quadro {} fora da grade de {} quadros "
            "(annotated_frame {})".format(
                frames[fora].tolist(), n_quadros, annotated_frames[fora].tolist()
            )
        )
    vivo = vivo_por_quadro[frames - 1]
    if not vivo[~sem_morto_antes].all():
        ruins = annotated_frames[~sem_morto_antes & ~vivo]
        raise ValueError(
            "ancoragem caiu em quadro morto para annotated_frame " + str(ruins.tolist())
        )
    return frames.astype("int64"), sem_morto_antes


def construir_gabarito(
    game: int, eventos_crus: pd.DataFrame, frames: pd.DataFrame, cfg: dict
) -> pd.DataFrame:
    """Funde `SET PIECE` com a execucao seguinte e ancora a bola parada.

    Entrada: `eventos_crus` de `carregar_eventos_crus`, `frames` do loader.
    Saida: DataFrame no esquema `src.io.schema.EVENTS`.

    Fusao (plano §6.1): a linha `SET PIECE` no indice `i` e a linha `i+1` formam
    UM evento quando `i+1` tem o mesmo `From` e o mesmo `Period`; o `type` vem do
    `SET PIECE` e a linha `i+1` nao gera evento proprio. Se nao casar, `raise`.

    `annotated_frame` do evento fundido e o `Start Frame` da linha de EXECUCAO,
    nao o da linha `SET PIECE`: a execucao e o instante do contato
    (docs/inspecao-metrica.md §3.4) e e nela que a ancoragem fica <= 0.

    `pass_secundario` de um evento fundido e o da linha PRIMARIA, isto e do
    `SET PIECE`, logo `False`. Esta tabela e a NORMATIVA para avaliacao
    (1009 / 1131 / 1358 eventos `True`): no nosso vocabulario a execucao de uma
    bola parada e avaliada como bola parada, e conta-la tambem como passe criaria
    falso negativo sistematico, porque o detector vai rotula-la bola parada.
    A contagem crua (1086 / 1208 / 1447) fica em `carregar_eventos_crus` e e so
    descritiva do vocabulario da Metrica. Decisao do G3 de 2026-10-29.
    """
    if not cfg["gabarito"]["fundir_set_piece_com_execucao"]:
        raise NotImplementedError("gabarito.fundir_set_piece_com_execucao=false nao implementado")
    if not cfg["gabarito"]["ancorar_bola_parada_no_primeiro_quadro_vivo"]:
        raise NotImplementedError("gabarito.ancorar_...=false nao implementado")

    cruas = eventos_crus.to_dict("records")
    consumidas = set()
    eventos = []
    for i, linha in enumerate(cruas):
        if i in consumidas:
            continue
        if linha["metrica_type"] != "SET PIECE":
            eventos.append(dict(linha, source_rows=str(linha["row"])))
            continue
        if i + 1 >= len(cruas):
            raise ValueError(
                "jogo {} linha {}: SET PIECE sem linha de execucao seguinte".format(game, i)
            )
        execucao = cruas[i + 1]
        if (execucao["player_id"], execucao["period"]) != (linha["player_id"], linha["period"]):
            raise ValueError(
                "jogo {} linha {}: SET PIECE de {} periodo {} nao casa com a linha {} "
                "({}, periodo {}, {}/{})".format(
                    game,
                    i,
                    linha["player_id"],
                    linha["period"],
                    i + 1,
                    execucao["player_id"],
                    execucao["period"],
                    execucao["metrica_type"],
                    execucao["metrica_subtype"],
                )
            )
        consumidas.add(i + 1)
        eventos.append(
            dict(
                linha,
                annotated_frame=execucao["annotated_frame"],
                source_rows="{},{}".format(linha["row"], execucao["row"]),
            )
        )

    df = pd.DataFrame(eventos)
    ball_live = frames.sort_values("frame")["ball_live"].to_numpy()
    annotated = df["annotated_frame"].to_numpy()

    # Ancorado: todo SET PIECE (inclui PENALTY, fora do escopo) e todo goal_kick.
    fps = cfg["tracking"]["fps"]
    guarda_quadros = round(cfg["gabarito"]["guarda_ancora_s"] * fps)
    alvo = (df["metrica_type"].to_numpy() == "SET PIECE") | (df["type"].to_numpy() == "goal_kick")
    frame = annotated.copy()
    sem_morto = np.zeros(len(df), dtype=bool)
    frame[alvo], sem_morto[alvo] = ancorar(annotated[alvo], ball_live, guarda_quadros)

    saida = pd.DataFrame(
        {
            "game": df["game"],
            "period": df["period"],
            "frame": frame,
            "t": frame / fps,
            "type": df["type"],
            "team": df["team"],
            "player_id": df["player_id"],
            "annotated_frame": annotated,
            "anchor_shift": frame - annotated,
            "no_dead_ball_before": sem_morto,
            "pass_secundario": df["pass_secundario"],
            "metrica_type": df["metrica_type"],
            "metrica_subtype": df["metrica_subtype"],
            "source_rows": df["source_rows"],
        }
    ).astype({c: t for c, t in schema.EVENTS.items()})
    return schema.validar(saida, schema.EVENTS, "events(jogo " + str(game) + ")")

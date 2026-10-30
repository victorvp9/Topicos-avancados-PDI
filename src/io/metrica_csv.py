"""Loader dos jogos 1 e 2 (CSV padrao da Metrica).

Formato (docs/02-dados.md, docs/inspecao-metrica.md §2): tres linhas de
cabecalho; a linha 3 traz `Period, Frame, Time [s]`, depois um par x,y por
jogador com o nome aparecendo SO no primeiro dos dois campos, e por fim `Ball`
com x,y. A bola aparece nos arquivos Home E Away, bit a bit identica; o loader
usa o arquivo Home.

Armadilhas cobertas: nome de coluna com espaco (`Player 26`, jogo 2),
coordenadas fora de [0,1] (nenhum clamp), NaN de jogador (= substituicao, vira
ausencia de linha).
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.io import schema

LINHAS_CABECALHO = 3  # docs/02-dados.md

# Nos jogos 1 e 2 o goleiro e a PRIMEIRA coluna de jogador de cada arquivo
# (`Player11` em casa, `Player25` fora) -- docs/fatias/01-plano.md §10.
INDICE_GOLEIRO = 0


def caminho_tracking(raiz: Path, game: int, team: str) -> Path:
    nome = {"home": "Home", "away": "Away"}[team]
    return Path(raiz) / f"Sample_Game_{game}" / f"Sample_Game_{game}_RawTrackingData_{nome}_Team.csv"


def caminho_eventos(raiz: Path, game: int) -> Path:
    return Path(raiz) / f"Sample_Game_{game}" / f"Sample_Game_{game}_RawEventsData.csv"


def numero_camisa(nome_coluna: str) -> int:
    """`Player11` -> 11; `Player 26` -> 26 (o espaco do jogo 2 e normalizado)."""
    digitos = re.sub(r"\D", "", nome_coluna)
    if not digitos:
        raise ValueError(f"coluna de jogador sem numero: {nome_coluna!r}")
    return int(digitos)


def ler_arquivo_time(caminho: Path) -> dict:
    """Le um CSV de tracking de um time, sem converter unidade.

    Devolve dict com `period`, `frame`, `time_s` (forma (N,)), `nomes` (lista de
    N_jog nomes de coluna crus), `x_norm`/`y_norm` (forma (N, N_jog)) e
    `ball_x_norm`/`ball_y_norm` (forma (N,)), tudo em coordenada NORMALIZADA.
    """
    caminho = Path(caminho)
    with caminho.open(encoding="utf-8") as fh:
        for _ in range(LINHAS_CABECALHO - 1):
            fh.readline()
        cabecalho = [campo.strip() for campo in fh.readline().rstrip("\n").split(",")]

    if cabecalho[:3] != ["Period", "Frame", "Time [s]"]:
        raise ValueError(f"{caminho.name}: cabecalho inesperado {cabecalho[:3]}")

    nomes = [c for c in cabecalho[3:] if c and c != "Ball"]
    n_jog = len(nomes)
    for k, nome in enumerate(nomes):
        if cabecalho[3 + 2 * k] != nome or cabecalho[4 + 2 * k] != "":
            raise ValueError(f"{caminho.name}: par x,y quebrado no jogador {nome!r}")
    if cabecalho[3 + 2 * n_jog] != "Ball":
        raise ValueError(f"{caminho.name}: coluna Ball nao esta na posicao {3 + 2 * n_jog}")

    bruto = pd.read_csv(caminho, skiprows=LINHAS_CABECALHO, header=None).to_numpy(dtype=float)
    esperado = 3 + 2 * n_jog + 2
    if bruto.shape[1] != esperado:
        raise ValueError(f"{caminho.name}: {bruto.shape[1]} colunas, esperado {esperado}")

    return {
        "period": bruto[:, 0].astype("int64"),
        "frame": bruto[:, 1].astype("int64"),
        "time_s": bruto[:, 2],
        "nomes": nomes,
        "x_norm": bruto[:, 3 : 3 + 2 * n_jog : 2],
        "y_norm": bruto[:, 4 : 4 + 2 * n_jog : 2],
        "ball_x_norm": bruto[:, 3 + 2 * n_jog],
        "ball_y_norm": bruto[:, 4 + 2 * n_jog],
    }


def carregar(game: int, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Carrega o jogo 1 ou 2 e devolve (frames, tracking, periods).

    Esquemas: `src.io.schema.FRAMES`, `TRACKING`, `PERIODS`.
    """
    if game not in (1, 2):
        raise ValueError(f"metrica_csv so le os jogos 1 e 2, recebeu {game}")
    raiz = cfg["dados"]["raiz"]
    campo = cfg["campo"]
    fps = cfg["tracking"]["fps"]

    lados = {lado: ler_arquivo_time(caminho_tracking(raiz, game, lado)) for lado in ("home", "away")}
    home, away = lados["home"], lados["away"]
    if not np.array_equal(home["frame"], away["frame"]) or not np.array_equal(
        home["period"], away["period"]
    ):
        raise ValueError(f"jogo {game}: grade de quadros difere entre Home e Away")

    frame = home["frame"]
    if not np.array_equal(frame, np.arange(1, frame.size + 1)):
        raise ValueError(f"jogo {game}: `Frame` nao e 1..N sem buraco nem duplicata")

    # Conferencia do relogio contra a coluna `Time [s]` crua do proprio CSV.
    for lado, dados in lados.items():
        desvio = np.max(np.abs(dados["time_s"] - frame / fps))
        if desvio != 0.0:
            raise ValueError(f"jogo {game} {lado}: max|Time - Frame/{fps}| = {desvio}")

    frames = schema.montar_frames(
        game,
        home["period"],
        frame,
        home["ball_x_norm"],
        home["ball_y_norm"],
        campo["comprimento_m"],
        campo["largura_m"],
        fps,
    )

    pedacos = []
    for lado, dados in lados.items():
        camisas = [numero_camisa(nome) for nome in dados["nomes"]]
        pedacos.append(
            schema.montar_tracking(
                game,
                dados["period"],
                frame,
                dados["x_norm"],
                dados["y_norm"],
                [f"g{game}_{lado}_{c}" for c in camisas],
                np.full(len(camisas), lado, dtype=object),
                np.arange(len(camisas)) == INDICE_GOLEIRO,
                campo["comprimento_m"],
                campo["largura_m"],
            )
        )
    tracking = (
        pd.concat(pedacos, ignore_index=True)
        .sort_values("frame", kind="stable", ignore_index=True)
        .astype({c: t for c, t in schema.TRACKING.items()})
    )
    schema.validar(tracking, schema.TRACKING, f"tracking(jogo {game})")

    return frames, tracking, schema.montar_periods(game, tracking)

"""Loader do jogo 3 (EPTS FIFA para o tracking, JSON para os eventos).

Lido com `xml.etree` e `str.split` da biblioteca padrao -- sem `kloppy`, sem
`floodlight` (D6, docs/inspecao-metrica.md §4).

Tracking (`Sample_Game_3_tracking.txt`): uma linha por quadro, no formato
`frame:p1x,p1y;...;p22x,p22y:bolax,bolay`, com `NaN` literal.

Metadados (`Sample_Game_3_metadata.xml`): 11 blocos `DataFormatSpecification`
com `startFrame`/`endFrame` e 44 `PlayerChannelRef` dando a ORDEM dos campos da
linha; as faixas mudam nas substituicoes. `PlayerChannel` liga o canal ao
`playerId`, e `Player` traz `teamId`, `ShirtNumber` e `position_type`.
"""

import xml.etree.ElementTree as ET
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

from src.io import schema

N_JOGADORES = 22  # 22 canais por bloco = 44 PlayerChannelRef


def caminho_tracking(raiz: Path) -> Path:
    return Path(raiz) / "Sample_Game_3" / "Sample_Game_3_tracking.txt"


def caminho_metadata(raiz: Path) -> Path:
    return Path(raiz) / "Sample_Game_3" / "Sample_Game_3_metadata.xml"


def caminho_eventos(raiz: Path) -> Path:
    return Path(raiz) / "Sample_Game_3" / "Sample_Game_3_events.json"


def ler_metadata(caminho: Path) -> dict:
    """Le o XML EPTS.

    Devolve dict com:
      `fps`, `comprimento_m`, `largura_m` -- FrameRate e FieldSize;
      `periodos` -- [(period, start_frame, end_frame)];
      `jogadores` -- playerId -> {"team": "home"/"away", "camisa": int, "is_gk": bool};
      `blocos` -- [(start_frame, end_frame, [playerId] * 22)] na ordem dos campos.
    """
    raiz_xml = ET.parse(caminho).getroot()

    config_global = next(raiz_xml.iter("GlobalConfig"))
    globais = {
        p.findtext("Name"): p.findtext("Value")
        for p in config_global.iter("ProviderParameter")
    }
    periodos = [
        (1, int(globais["first_half_start"]), int(globais["first_half_end"])),
        (2, int(globais["second_half_start"]), int(globais["second_half_end"])),
    ]

    score = next(raiz_xml.iter("Score"))
    lado_do_time = {score.get("idLocalTeam"): "home", score.get("idVisitingTeam"): "away"}

    jogadores = {}
    for jog in raiz_xml.iter("Player"):
        params = {p.findtext("Name"): p.findtext("Value") for p in jog.iter("ProviderParameter")}
        jogadores[jog.get("id")] = {
            "team": lado_do_time[jog.get("teamId")],
            "camisa": int(jog.findtext("ShirtNumber")),
            "is_gk": params.get("position_type") == "Goalkeeper",
        }

    canais = {c.get("id"): c.get("playerId") for c in raiz_xml.iter("PlayerChannel")}

    blocos = []
    for bloco in raiz_xml.iter("DataFormatSpecification"):
        refs = [r.get("playerChannelId") for r in bloco.iter("PlayerChannelRef")]
        if len(refs) != 2 * N_JOGADORES:
            raise ValueError(f"bloco {bloco.get('startFrame')}: {len(refs)} PlayerChannelRef")
        ordem = []
        for k in range(N_JOGADORES):
            ref_x, ref_y = refs[2 * k], refs[2 * k + 1]
            if not ref_x.endswith("_x") or not ref_y.endswith("_y"):
                raise ValueError(f"bloco {bloco.get('startFrame')}: par {ref_x},{ref_y} nao e x,y")
            if canais[ref_x] != canais[ref_y]:
                raise ValueError(f"bloco {bloco.get('startFrame')}: {ref_x} e {ref_y} de jogadores diferentes")
            ordem.append(canais[ref_x])
        blocos.append((int(bloco.get("startFrame")), int(bloco.get("endFrame")), ordem))

    tamanho = next(raiz_xml.iter("FieldSize"))
    return {
        "fps": int(raiz_xml.findtext(".//FrameRate")),
        "comprimento_m": float(tamanho.findtext("Width")),
        "largura_m": float(tamanho.findtext("Height")),
        "periodos": periodos,
        "jogadores": jogadores,
        "blocos": blocos,
    }


def ler_tracking(caminho: Path) -> np.ndarray:
    """Le o .txt do jogo 3 numa matriz (N, 1 + 44 + 2) de float.

    Vetorizado: troca os separadores `;` e `:` por `,` e entrega o texto inteiro
    ao parser do pandas. Nenhum laco por quadro em Python.
    """
    texto = Path(caminho).read_text(encoding="utf-8").replace(";", ",").replace(":", ",")
    bruto = pd.read_csv(StringIO(texto), header=None).to_numpy(dtype=float)
    esperado = 1 + 2 * N_JOGADORES + 2
    if bruto.shape[1] != esperado:
        raise ValueError(f"tracking do jogo 3: {bruto.shape[1]} campos, esperado {esperado}")
    return bruto


def carregar(game: int, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Carrega o jogo 3 e devolve (frames, tracking, periods).

    Esquemas: `src.io.schema.FRAMES`, `TRACKING`, `PERIODS`.
    """
    if game != 3:
        raise ValueError(f"metrica_epts so le o jogo 3, recebeu {game}")
    raiz = cfg["dados"]["raiz"]
    campo = cfg["campo"]
    meta = ler_metadata(caminho_metadata(raiz))

    for chave, nome_xml in (("comprimento_m", "Width"), ("largura_m", "Height")):
        if meta[chave] != campo[chave]:
            raise ValueError(f"jogo 3: {nome_xml}={meta[chave]} difere de config.yaml campo.{chave}")
    if meta["fps"] != cfg["tracking"]["fps"]:
        raise ValueError(f"jogo 3: FrameRate={meta['fps']} difere de config.yaml tracking.fps")
    fps = meta["fps"]

    bruto = ler_tracking(caminho_tracking(raiz))
    frame = bruto[:, 0].astype("int64")
    if not np.array_equal(frame, np.arange(1, frame.size + 1)):
        raise ValueError("jogo 3: `frame` nao e 1..N sem buraco nem duplicata")

    period = np.zeros(frame.size, dtype="int64")
    for numero, inicio, fim in meta["periodos"]:
        period[inicio - 1 : fim] = numero
    if (period == 0).any():
        raise ValueError("jogo 3: ha quadro fora das faixas de periodo do XML")

    frames = schema.montar_frames(
        game,
        period,
        frame,
        bruto[:, 1 + 2 * N_JOGADORES],
        bruto[:, 2 + 2 * N_JOGADORES],
        campo["comprimento_m"],
        campo["largura_m"],
        fps,
    )

    coberto = np.zeros(frame.size, dtype=bool)
    pedacos = []
    for inicio, fim, ordem in meta["blocos"]:
        if coberto[inicio - 1 : fim].any():
            raise ValueError(f"jogo 3: faixas de DataFormatSpecification se sobrepoem em {inicio}")
        coberto[inicio - 1 : fim] = True
        fatia = slice(inicio - 1, fim)
        jogs = [meta["jogadores"][pid] for pid in ordem]
        pedacos.append(
            schema.montar_tracking(
                game,
                period[fatia],
                frame[fatia],
                bruto[fatia, 1 : 1 + 2 * N_JOGADORES : 2],
                bruto[fatia, 2 : 2 + 2 * N_JOGADORES : 2],
                [f"g{game}_{j['team']}_{j['camisa']}" for j in jogs],
                np.array([j["team"] for j in jogs], dtype=object),
                np.array([j["is_gk"] for j in jogs], dtype=bool),
                campo["comprimento_m"],
                campo["largura_m"],
            )
        )
    if not coberto.all():
        raise ValueError("jogo 3: as faixas de DataFormatSpecification deixam lacuna")

    tracking = (
        pd.concat(pedacos, ignore_index=True)
        .sort_values("frame", kind="stable", ignore_index=True)
        .astype({c: t for c, t in schema.TRACKING.items()})
    )
    schema.validar(tracking, schema.TRACKING, "tracking(jogo 3)")

    return frames, tracking, schema.montar_periods(game, tracking)

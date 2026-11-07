"""Leitor StatsBomb 360 da Copa de 2022 (Fatia 12).

Plano normativo: `docs/fatias/12-plano.md` §1 e §5. Constantes em
`config.yaml:statsbomb360`. So a biblioteca padrao (`json`, `hashlib`) e numpy.

Saida de `ler_jogo`: uma linha por evento `Pass` do jogo (o escopo do §5), com

  match_id       int    id StatsBomb do jogo
  event_uuid     str    `id` do evento (= `event_uuid` do 360)
  tipo           str    `pass` (jogo corrido) ou o tipo de bola parada, nos
                        nomes do gabarito da Metrica (`throw_in`, ...)
  tem_360        bool   ha entrada no `three-sixty/<id>.json`
  n_visiveis     float  entradas do `freeze_frame` (todos os jogadores); NaN sem 360
  actor_visivel  float  1.0 se ha entrada com `actor` = true, 0.0 se nao; NaN sem 360
  frac_area      float  area de `visible_area` recortada ao campo / area do campo;
                        NaN sem 360

As coordenadas ficam em jardas e nao saem daqui: a unica grandeza geometrica
que sai e `frac_area`, adimensional (a conversao para metros nao a muda).
Evento sem 360 NAO e descartado: entra com `tem_360` = False (plano 12 §1, a
hipotese "sem imagem utilizavel").
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import RAIZ_REPO

COLUNAS = ["match_id", "event_uuid", "tipo", "tem_360", "n_visiveis", "actor_visivel", "frac_area"]


def raiz(cfg: dict) -> Path:
    return RAIZ_REPO / cfg["statsbomb360"]["raiz"]


def _ler_json(caminho: Path):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def partidas(cfg: dict) -> list:
    """Os `match_id` de `matches.json` da competicao e temporada do config, em
    ordem crescente. Estoura se nao forem `statsbomb360.n_jogos`."""
    sb = cfg["statsbomb360"]
    ids = sorted(int(m["match_id"]) for m in _ler_json(raiz(cfg) / "matches.json")
                 if m["competition"]["competition_id"] == sb["competition_id"]
                 and m["season"]["season_id"] == sb["season_id"])
    if len(ids) != sb["n_jogos"]:
        raise ValueError("matches.json: {} jogos, esperado {}".format(len(ids), sb["n_jogos"]))
    return ids


def tipo_do_passe(evento: dict, sb: dict) -> str:
    """Nosso tipo a partir de `pass.type.name` (plano 12 §5). Ausente ou
    `pass_type_corrido` -> `tipo_corrido`; `pass_type_bola_parada` -> o tipo;
    qualquer outro valor estoura."""
    t = evento.get("pass", {}).get("type")
    if t is None or t["name"] in sb["pass_type_corrido"]:
        return sb["tipo_corrido"]
    if t["name"] in sb["pass_type_bola_parada"]:
        return sb["pass_type_bola_parada"][t["name"]]
    raise ValueError("pass.type desconhecido: {!r} (evento {})".format(t["name"], evento.get("id")))


def recortar(xy: np.ndarray, largura: float, altura: float) -> np.ndarray:
    """Sutherland-Hodgman: o poligono `xy` (n, 2) recortado ao retangulo
    [0, largura] x [0, altura]. Saida (m, 2), vazia se nada sobra."""
    pts = [tuple(p) for p in np.asarray(xy, dtype="float64").reshape(-1, 2)]
    # (eixo, limite, lado): lado +1 mantem coord >= limite, -1 mantem <= limite
    for eixo, limite, lado in ((0, 0.0, 1), (0, largura, -1), (1, 0.0, 1), (1, altura, -1)):
        if not pts:
            break
        dentro = [lado * (p[eixo] - limite) >= 0 for p in pts]
        out = []
        for i, cur in enumerate(pts):
            prev, prev_in = pts[i - 1], dentro[i - 1]
            if dentro[i] != prev_in:
                s = (limite - prev[eixo]) / (cur[eixo] - prev[eixo])
                out.append(tuple(prev[k] + s * (cur[k] - prev[k]) for k in (0, 1)))
            if dentro[i]:
                out.append(cur)
        pts = out
    return np.asarray(pts, dtype="float64").reshape(-1, 2)


def area_cadarco(xy: np.ndarray) -> float:
    """Area pela formula do cadarco (shoelace), em unidades^2 de `xy`."""
    x, y = np.asarray(xy, dtype="float64").reshape(-1, 2).T
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y)))


def frac_area(visible_area, largura: float, altura: float) -> float:
    """`visible_area` (lista plana x1, y1, x2, y2, ... em jardas) recortada ao
    campo, area / (largura * altura). Poligono com < 3 vertices: estoura."""
    xy = np.asarray(visible_area, dtype="float64").reshape(-1, 2)
    if len(xy) < 3 or not np.isfinite(xy).all():
        raise ValueError("visible_area invalida: {} vertices".format(len(xy)))
    return area_cadarco(recortar(xy, largura, altura)) / (largura * altura)


def tabela_jogo(match_id: int, eventos: list, sessenta: list, cfg: dict) -> pd.DataFrame:
    """As linhas de `COLUNAS` (docstring do modulo) a partir dos JSON ja lidos."""
    sb = cfg["statsbomb360"]
    largura, altura = sb["campo_jardas"]
    por_uuid = {}
    for s in sessenta:
        if s["event_uuid"] in por_uuid:
            raise ValueError("jogo {}: event_uuid repetido no 360: {}".format(match_id, s["event_uuid"]))
        por_uuid[s["event_uuid"]] = s
    linhas = []
    for e in eventos:
        if e["type"]["name"] != sb["type_name_escopo"]:
            continue
        s = por_uuid.get(e["id"])
        if s is None:
            linhas.append((match_id, e["id"], tipo_do_passe(e, sb), False, np.nan, np.nan, np.nan))
            continue
        ff = s["freeze_frame"]
        linhas.append((match_id, e["id"], tipo_do_passe(e, sb), True, float(len(ff)),
                       float(any(p["actor"] for p in ff)), frac_area(s["visible_area"], largura, altura)))
    return pd.DataFrame(linhas, columns=COLUNAS).astype(
        {"match_id": "int64", "tem_360": "bool", "n_visiveis": "float64",
         "actor_visivel": "float64", "frac_area": "float64"})


def ler_jogo(match_id: int, cfg: dict) -> pd.DataFrame:
    """`events/<id>.json` e `three-sixty/<id>.json` -> `tabela_jogo`. Os dois
    arquivos tem de existir."""
    r = raiz(cfg)
    return tabela_jogo(match_id, _ler_json(r / "events" / f"{match_id}.json"),
                       _ler_json(r / "three-sixty" / f"{match_id}.json"), cfg)


def conferir_sha(cfg: dict, match_ids) -> dict:
    """Confere o sha256 de `matches.json` e dos JSON de eventos e 360 lidos
    contra `SHA256SUMS.txt`; estoura em qualquer divergencia ou ausencia.
    Saida: sha256 de `SHA256SUMS.txt` e o numero de arquivos conferidos."""
    r = raiz(cfg)
    somas = {}
    for linha in (r / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if linha.strip():
            h, nome = linha.split(maxsplit=1)
            somas[nome.lstrip("*").removeprefix("./")] = h
    nomes = ["matches.json"] + [f"{d}/{m}.json" for m in match_ids for d in ("events", "three-sixty")]
    for nome in nomes:
        h = hashlib.sha256((r / nome).read_bytes()).hexdigest()
        if somas.get(nome) != h:
            raise ValueError("sha256 de {} nao confere com SHA256SUMS.txt".format(nome))
    return {"sha256_SHA256SUMS.txt": hashlib.sha256((r / "SHA256SUMS.txt").read_bytes()).hexdigest(),
            "n_arquivos_conferidos": len(nomes)}

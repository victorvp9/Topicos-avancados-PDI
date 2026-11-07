"""Loader do IDSSE (7 jogos da Bundesliga, formato XML da DFL). Fatia 11a.

Plano normativo: docs/fatias/11-plano.md §2 e §5. Tudo com a biblioteca padrao
(`xml.etree.ElementTree.iterparse` com `clear()`, porque o XML de posicoes tem
~370 MB) mais numpy e pandas. Nenhum detector roda aqui.

Arquivos por jogo, em `cfg['idsse']['raiz']`:
  `DFL_02_01_matchinformation_*_<MatchId>.xml`  ficha: home/guest, goleiro, campo
  `DFL_03_02_events_raw_*_<MatchId>.xml`        eventos, `EventTime` local com fuso
  `DFL_04_03_positions_raw_observed_*_<MatchId>.xml`  posicoes: uma `FrameSet`
      por pessoa e por tempo, `<Frame N T X Y ...>`; a bola tem `TeamId="BALL"`
      e `BallStatus` (0/1).

Saida nos esquemas de `src.io.schema` (FRAMES, TRACKING, PERIODS, EVENTS):
  - quadros remapeados para 1..N contiguos (1o tempo e depois o 2o), `period`
    1/2 e `t = frame / fps`, como na Metrica;
  - `X`/`Y` da DFL ja vem em metros, origem no centro: so copiados;
  - `ball_live = BallStatus == 1` (plano §2, "Estado da bola"), NAO derivado de NaN;
  - `player_id = g<jogo>_<home|away>_<PersonId>` (plano §5; `I` = numero do jogo, G3 2026-11-07).
"""

import hashlib
import json
import pickle
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import RAIZ_REPO
from src.gabarito import ancorar
from src.io import schema

FORA_DO_ESCOPO = "fora_do_escopo"
SECOES = {"firstHalf": 1, "secondHalf": 2}   # nomes do XML da DFL; outro valor estoura


def raiz(cfg: dict) -> Path:
    return RAIZ_REPO / cfg["idsse"]["raiz"]


def caminhos(cfg: dict, game: int) -> dict:
    """Os tres XML do jogo `game` (1-based na ordem de `cfg['idsse']['jogos']`)."""
    match_id = cfg["idsse"]["jogos"][game - 1]
    saida = {}
    for chave, prefixo in (("ficha", "DFL_02_01_matchinformation_"), ("eventos", "DFL_03_02_events_raw_"),
                           ("posicoes", "DFL_04_03_positions_raw_observed_")):
        achados = sorted(raiz(cfg).glob(f"{prefixo}*_DFL-MAT-{match_id}.xml"))
        if len(achados) != 1:
            raise FileNotFoundError(f"IDSSE {match_id}: {len(achados)} arquivos {prefixo}*")
        saida[chave] = achados[0]
    return saida


def player_id(game: int, team: str, person_id: str) -> str:
    return f"g{game}_{team}_{person_id}"


# --- ficha ------------------------------------------------------------------------

def ler_ficha(caminho: Path, cfg: dict) -> dict:
    """Ficha DFL -> {"lado": TeamId -> home/away, "goleiros": set(PersonId),
    "jogadores": set(PersonId), "pitch": (X, Y)}.

    Goleiro = `PlayingPosition` igual a `cfg['idsse']['posicao_goleiro']`.
    """
    geral = None
    lado, goleiros, jogadores = {}, set(), set()
    raiz_xml = ET.parse(caminho).getroot()
    for el in raiz_xml.iter():
        if el.tag == "Environment":
            geral = (float(el.get("PitchX")), float(el.get("PitchY")))
        elif el.tag == "Team":
            papel = {"home": "home", "guest": "away"}.get(el.get("Role"))
            if papel is None:
                raise ValueError(f"{caminho.name}: Team Role={el.get('Role')!r}")
            lado[el.get("TeamId")] = papel
            for jog in el.iter("Player"):
                jogadores.add(jog.get("PersonId"))
                if jog.get("PlayingPosition") == cfg["idsse"]["posicao_goleiro"]:
                    goleiros.add(jog.get("PersonId"))
    if sorted(lado.values()) != ["away", "home"]:
        raise ValueError(f"{caminho.name}: times {lado}")
    if geral != (cfg["campo"]["comprimento_m"], cfg["campo"]["largura_m"]):
        raise ValueError(f"{caminho.name}: PitchX/PitchY={geral} difere de config.yaml campo")
    return {"lado": lado, "goleiros": goleiros, "jogadores": jogadores, "pitch": geral}


# --- posicoes ---------------------------------------------------------------------

def _ler_framesets(caminho: Path, cfg: dict) -> list:
    """Varre o XML de posicoes com `iterparse` + `clear()`. Devolve uma lista de
    (secao, team_id, person_id, dict de arrays crus) por `FrameSet`; arbitros sao
    pulados. A bola guarda tambem `T` e `BallStatus`."""
    bola = cfg["idsse"]["team_id_bola"]
    pular = set(cfg["idsse"]["team_ids_ignorados"])
    saida = []
    atual = None
    for evento, el in ET.iterparse(str(caminho), events=("start", "end")):
        if evento == "start":
            if el.tag == "FrameSet":
                team = el.get("TeamId")
                atual = None if team in pular else (el.get("GameSection"), team, el.get("PersonId"),
                                                    {"N": [], "X": [], "Y": [], "T": [], "S": []})
            continue
        if el.tag == "Frame":
            if atual is not None:
                col = atual[3]
                col["N"].append(el.get("N"))
                col["X"].append(el.get("X"))
                col["Y"].append(el.get("Y"))
                if atual[1] == bola:
                    col["T"].append(el.get("T"))
                    col["S"].append(el.get("BallStatus"))
            el.clear()
        elif el.tag == "FrameSet":
            if atual is not None:
                col = atual[3]
                arr = {"N": np.asarray(col["N"], dtype="int64"),
                       "X": np.asarray(col["X"], dtype="float64"),
                       "Y": np.asarray(col["Y"], dtype="float64")}
                if atual[1] == bola:
                    arr["T"] = pd.to_datetime(col["T"], utc=True, format="ISO8601").as_unit("ns").asi8
                    arr["S"] = np.asarray(col["S"], dtype="int64")
                saida.append(atual[:3] + (arr,))
            atual = None
            el.clear()
    return saida


def converter_posicoes(caminho: Path, ficha: dict, game: int, cfg: dict):
    """XML de posicoes -> (frames, tracking, t_utc_ns, nan).

    `frames`/`tracking` nos esquemas FRAMES e TRACKING; `t_utc_ns` (n_quadros,)
    int64 com o `T` UTC da bola em ns, indexado por `frame - 1`; `nan` dict com
    as contagens de coordenada nao finita (`jogador_linhas`, `bola_quadros`).

    A grade de quadros de cada tempo e a `N` da bola: tem de ser contigua, com
    `T` avancando exatamente 1/fps. Quadro de jogador fora dessa grade estoura.
    Jogador com X ou Y nao finito vira ausencia de linha (esquema TRACKING) e e
    contado; a bola preserva NaN (D1), mas `ball_live` vem so do `BallStatus`.
    """
    fps = cfg["tracking"]["fps"]
    passo_ns = round(1e9 / fps)
    bola = cfg["idsse"]["team_id_bola"]
    framesets = _ler_framesets(caminho, cfg)

    grades = {}
    for secao, team, _, arr in framesets:
        if secao not in SECOES:
            raise ValueError(f"{caminho.name}: GameSection {secao!r}")
        if team == bola:
            if secao in grades:
                raise ValueError(f"{caminho.name}: duas FrameSet da bola em {secao}")
            if not (np.diff(arr["N"]) == 1).all():
                raise ValueError(f"{caminho.name}: N da bola nao contiguo em {secao}")
            if not (np.diff(arr["T"]) == passo_ns).all():
                raise ValueError(f"{caminho.name}: T da bola nao avanca 1/{fps} s em {secao}")
            grades[secao] = arr
    if sorted(grades, key=SECOES.get) != list(SECOES):
        raise ValueError(f"{caminho.name}: bola so em {sorted(grades)}")

    ordem = sorted(grades, key=SECOES.get)
    inicio = {}
    total = 0
    for secao in ordem:
        inicio[secao] = total
        total += grades[secao]["N"].size
    frame = np.arange(1, total + 1, dtype="int64")
    period = np.concatenate([np.full(grades[s]["N"].size, SECOES[s], dtype="int64") for s in ordem])
    ball_x = np.concatenate([grades[s]["X"] for s in ordem])
    ball_y = np.concatenate([grades[s]["Y"] for s in ordem])
    status = np.concatenate([grades[s]["S"] for s in ordem])
    t_utc_ns = np.concatenate([grades[s]["T"] for s in ordem])
    if np.isin(status, [0, 1], invert=True).any():
        raise ValueError(f"{caminho.name}: BallStatus fora de {{0, 1}}")
    frames = pd.DataFrame({
        "game": np.full(total, game, dtype="int64"),
        "period": period,
        "frame": frame,
        "t": frame / fps,
        "ball_x": ball_x,
        "ball_y": ball_y,
        "ball_live": status == cfg["idsse"]["ball_status_vivo"],
    })
    schema.validar(frames, schema.FRAMES, f"frames(idsse {game})")

    pedacos = []
    nan_jog = 0
    for secao, team, pessoa, arr in framesets:
        if team == bola:
            continue
        if team not in ficha["lado"] or pessoa not in ficha["jogadores"]:
            raise ValueError(f"{caminho.name}: FrameSet {team}/{pessoa} fora da ficha")
        grade = grades[secao]["N"]
        k = np.searchsorted(grade, arr["N"])
        if (k >= grade.size).any() or not np.array_equal(grade[np.minimum(k, grade.size - 1)], arr["N"]):
            raise ValueError(f"{caminho.name}: {pessoa} tem quadro fora da grade da bola em {secao}")
        ok = np.isfinite(arr["X"]) & np.isfinite(arr["Y"])
        nan_jog += int((~ok).sum())
        f = k[ok] + inicio[secao] + 1
        lado = ficha["lado"][team]
        pedacos.append(pd.DataFrame({
            "game": np.full(f.size, game, dtype="int64"),
            "period": np.full(f.size, SECOES[secao], dtype="int64"),
            "frame": f.astype("int64"),
            "player_id": player_id(game, lado, pessoa),
            "team": lado,
            "is_gk": pessoa in ficha["goleiros"],
            "x": arr["X"][ok],
            "y": arr["Y"][ok],
            "visible": True,
        }))
    tracking = (
        pd.concat(pedacos, ignore_index=True)
        .sort_values(["frame", "player_id"], kind="stable", ignore_index=True)
        .astype(schema.TRACKING)
    )
    if tracking.duplicated(["frame", "player_id"]).any():
        raise ValueError(f"{caminho.name}: jogador repetido no mesmo quadro")
    schema.validar(tracking, schema.TRACKING, f"tracking(idsse {game})")
    nan = {"jogador_linhas": nan_jog, "bola_quadros": int((~np.isfinite(ball_x) | ~np.isfinite(ball_y)).sum())}
    return frames, tracking, t_utc_ns, nan


def _sha(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def chave_cache(caminho_pos: Path, caminho_ficha: Path, game: int, cfg: dict) -> str:
    """sha256 dos dois XML de entrada + deste modulo + do config que a conversao le."""
    material = {
        "posicoes": _sha(caminho_pos),
        "ficha": _sha(caminho_ficha),
        "codigo": _sha(Path(__file__)),
        "game": game,
        "config": {k: cfg[k] for k in ("tracking", "campo")} | {"idsse": cfg["idsse"]},
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, default=str).encode()).hexdigest()


def posicoes_cacheadas(caminho_pos: Path, caminho_ficha: Path, game: int, cfg: dict, pasta_cache=None):
    """`converter_posicoes` com cache em `pasta_cache` (None desliga).
    Devolve (frames, tracking, t_utc_ns, nan, "hit"/"miss"/"desligado")."""
    ficha = ler_ficha(caminho_ficha, cfg)
    if pasta_cache is None:
        return converter_posicoes(caminho_pos, ficha, game, cfg) + ("desligado",)
    arquivo = Path(pasta_cache) / f"idsse_{chave_cache(caminho_pos, caminho_ficha, game, cfg)}.pkl"
    if arquivo.exists():
        with open(arquivo, "rb") as f:
            return pickle.load(f) + ("hit",)
    saida = converter_posicoes(caminho_pos, ficha, game, cfg)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".tmp")
    with open(temporario, "wb") as f:
        pickle.dump(saida, f, protocol=pickle.HIGHEST_PROTOCOL)
    temporario.replace(arquivo)
    return saida + ("miss",)


# --- eventos ----------------------------------------------------------------------

def _caminho_tags(el) -> str:
    """`ThrowIn/Play/Pass`: a cadeia de filhos unicos abaixo do elemento."""
    partes = [el.tag]
    while len(el) == 1:
        el = el[0]
        partes.append(el.tag)
    return "/".join(partes)


def ler_eventos(caminho: Path, ficha: dict, game: int, cfg: dict):
    """XML de eventos -> (crus, n_delete).

    `crus`: uma linha por `Event` nao descartado, na ordem do arquivo, com
      `event_id` str, `utc_ns` int64 (`EventTime` com fuso convertido para UTC),
      `type` (vocabulario interno ou `fora_do_escopo`), `team`, `player_id`,
      `dfl_type` (tag do filho do `Event`), `dfl_path` (cadeia de tags) e
      `pass_secundario` bool.

    Mapeamento (plano §2, `cfg['idsse']`): tag de bola parada -> tipo interno,
    executor = `Player` do filho; `Play` de topo com `Pass`/`Cross` ->
    `pass_secundario = True`, e `type = pass` so com `Evaluation` completo
    (senao `fora_do_escopo`), I1 de decisoes.md 2026-11-07, como o D10 da
    Metrica; `Delete` descartado e contado; tag conhecida fora disso ->
    `fora_do_escopo`. Tag de `Event` desconhecida, `Play` com outro filho,
    `Evaluation` desconhecido, ou bola parada sem filho executor conhecido:
    estoura.
    """
    m = cfg["idsse"]
    conhecidos = set(m["tipos_conhecidos"])
    descartar = set(m["descartar"])
    bolas_paradas = m["bola_parada"]
    filhos_passe = set(m["passe"]["filhos"])
    tag_play = m["passe"]["tag"]
    completo = set(m["passe"]["evaluation_completo"])
    incompleto = set(m["passe"]["evaluation_incompleto"])
    executores = set(m["executor_bola_parada"])
    lado = ficha["lado"]

    linhas, tempos, n_delete = [], [], 0
    for ev in ET.parse(caminho).getroot():
        if ev.tag != "Event":
            raise ValueError(f"{caminho.name}: elemento {ev.tag!r} fora de Event")
        if len(ev) != 1:
            raise ValueError(f"{caminho.name}: Event {ev.get('EventId')} com {len(ev)} filhos")
        top = ev[0]
        if top.tag not in conhecidos:
            raise ValueError(f"{caminho.name}: Event {ev.get('EventId')}: tipo DFL {top.tag!r} nao esta "
                             "em config.yaml:idsse.tipos_conhecidos")
        if top.tag in descartar:
            n_delete += 1
            continue
        if top.tag in bolas_paradas:
            if len(top) != 1 or top[0].tag not in executores:
                raise ValueError(f"{caminho.name}: Event {ev.get('EventId')}: {_caminho_tags(top)} sem "
                                 "executor em config.yaml:idsse.executor_bola_parada")
            exe = top[0]
            if exe.tag == tag_play and (len(exe) != 1 or exe[0].tag not in filhos_passe):
                raise ValueError(f"{caminho.name}: Event {ev.get('EventId')}: {_caminho_tags(top)}")
            tipo, pessoa, time = bolas_paradas[top.tag], exe.get("Player"), exe.get("Team")
        elif top.tag == tag_play:
            if len(top) != 1 or top[0].tag not in filhos_passe:
                raise ValueError(f"{caminho.name}: Event {ev.get('EventId')}: {_caminho_tags(top)} nao "
                                 "esta em config.yaml:idsse.passe.filhos")
            avaliacao = top.get("Evaluation")
            if avaliacao not in completo | incompleto:
                raise ValueError(f"{caminho.name}: Event {ev.get('EventId')}: Evaluation {avaliacao!r} nao "
                                 "esta em config.yaml:idsse.passe.evaluation_*")
            tipo = "pass" if avaliacao in completo else FORA_DO_ESCOPO
            pessoa, time = top.get("Player"), top.get("Team")
        else:
            tipo = FORA_DO_ESCOPO
            com_jogador = next((e for e in top.iter() if e.get("Player")), None)
            pessoa = com_jogador.get("Player") if com_jogador is not None else None
            time = com_jogador.get("Team") if com_jogador is not None else top.get("Team")
        if tipo != FORA_DO_ESCOPO and (not pessoa or time not in lado):
            raise ValueError(f"{caminho.name}: Event {ev.get('EventId')} ({tipo}) sem Player/Team da ficha")
        team = lado.get(time, "")
        linhas.append({
            "event_id": ev.get("EventId"),
            "type": tipo,
            "team": team,
            "player_id": player_id(game, team, pessoa) if pessoa and team else "",
            "dfl_type": top.tag,
            "dfl_path": _caminho_tags(top),
            "pass_secundario": top.tag == tag_play,
        })
        tempos.append(ev.get("EventTime"))
    crus = pd.DataFrame(linhas, columns=["event_id", "type", "team", "player_id", "dfl_type", "dfl_path",
                                         "pass_secundario"]).astype({"pass_secundario": "bool"})
    crus.insert(1, "utc_ns", pd.to_datetime(tempos, utc=True, format="ISO8601").as_unit("ns").asi8)
    return crus, n_delete


def quadro_do_instante(utc_ns: np.ndarray, t_utc_ns: np.ndarray):
    """Quadro (1-based) cujo `T` UTC e o mais proximo de cada instante, sobre a
    grade inteira do jogo, e a diferenca `instante - T` em s.

    # TODO(divida): o plano 11 §5 so diz "convertidos pelo T UTC das posicoes".
    # Instante fora da grade (antes do 1o quadro de um tempo, no intervalo ou
    # depois do apito) cai no quadro mais proximo; `dt_s` fica para a inspecao
    # contar quantos. Empate: o quadro mais antigo.
    """
    utc_ns = np.asarray(utc_ns, dtype="int64")
    k = np.clip(np.searchsorted(t_utc_ns, utc_ns), 1, max(t_utc_ns.size - 1, 1))
    antes = (utc_ns - t_utc_ns[k - 1]) <= (t_utc_ns[np.minimum(k, t_utc_ns.size - 1)] - utc_ns)
    k = np.where(antes, k - 1, k)
    return k + 1, (utc_ns - t_utc_ns[k]) / 1e9


def ancorar_idsse(annotated: np.ndarray, ball_live: np.ndarray, guarda_quadros: int):
    """Ancoragem da bola parada no IDSSE (plano 11 §2: "a mesma regra da
    Metrica. O quadro anotado vai para o primeiro quadro vivo da corrida morta
    mais recente, com a guarda de 10 s"). Devolve
    (frames, sem_morto_antes, anotado_em_morto).

    Anotado em quadro VIVO: exatamente `gabarito.ancorar` (recua ate o primeiro
    quadro vivo depois do ultimo quadro morto).

    # TODO(divida): anotado em quadro MORTO. Na Metrica a execucao anotada cai
    # sempre em quadro vivo; no IDSSE o `EventTime` e codificado ao vivo e cai
    # dentro da corrida morta em 433/691 = 62,7 % das bolas paradas, onde
    # `gabarito.ancorar` estoura. Minimo decidido, pela letra do plano: a
    # "corrida morta mais recente" e a que contem o quadro anotado, e o evento
    # AVANCA para o primeiro quadro vivo depois dela. A guarda vale nos dois
    # sentidos ("a ancora nao pode mover o evento mais de 10 s"): avanco maior
    # que a guarda, ou sem quadro vivo depois, fica no quadro anotado com
    # `no_dead_ball_before = True`. A confirmar no G3.
    """
    annotated = np.asarray(annotated, dtype="int64")
    em_morto = ~ball_live[annotated - 1]
    frames = annotated.copy()
    sem_morto = np.ones(annotated.size, dtype=bool)
    if (~em_morto).any():
        frames[~em_morto], sem_morto[~em_morto] = ancorar(annotated[~em_morto], ball_live, guarda_quadros)
    if em_morto.any():
        a = annotated[em_morto]
        vivos = np.flatnonzero(ball_live)          # posicoes 0-based
        k = np.searchsorted(vivos, a - 1)          # 1o vivo depois de a - 1 (que e morto)
        sem_vivo = k >= vivos.size
        prox = vivos[np.minimum(k, max(vivos.size - 1, 0))] + 1 if vivos.size else a
        longe = sem_vivo | ((prox - a) > guarda_quadros)
        frames[em_morto] = np.where(longe, a, prox)
        sem_morto[em_morto] = longe
    return frames, sem_morto, em_morto


def construir_gabarito(game: int, crus: pd.DataFrame, frames: pd.DataFrame, t_utc_ns: np.ndarray,
                       cfg: dict) -> pd.DataFrame:
    """Eventos crus -> tabela no esquema EVENTS, mais duas colunas de diagnostico
    no fim: `dt_sync_s` (instante do evento - `T` do quadro anotado) e
    `anotado_em_morto` (bola parada anotada em quadro morto).

    `metrica_type`/`metrica_subtype`/`source_rows` guardam a tag DFL, a cadeia
    de tags e o `EventId` (as colunas sao do esquema comum). Ancoradas: as seis
    bolas paradas de `cfg['idsse']['bola_parada']`.

    `pass_secundario` vem de `ler_eventos` (todo `Play` de topo, completo ou
    nao; I1 de decisoes.md 2026-11-07).
    """
    fps = cfg["tracking"]["fps"]
    ball_live = frames.sort_values("frame")["ball_live"].to_numpy()
    annotated, dt = quadro_do_instante(crus["utc_ns"].to_numpy(), t_utc_ns)
    alvo = crus["type"].isin(list(cfg["idsse"]["bola_parada"].values())).to_numpy()
    guarda = round(cfg["gabarito"]["guarda_ancora_s"] * fps)
    frame = annotated.copy()
    sem_morto = np.zeros(len(crus), dtype=bool)
    em_morto = np.zeros(len(crus), dtype=bool)
    frame[alvo], sem_morto[alvo], em_morto[alvo] = ancorar_idsse(annotated[alvo], ball_live, guarda)
    period = frames.sort_values("frame")["period"].to_numpy()
    saida = pd.DataFrame({
        "game": np.full(len(crus), game, dtype="int64"),
        "period": period[frame - 1],
        "frame": frame,
        "t": frame / fps,
        "type": crus["type"].to_numpy(),
        "team": crus["team"].to_numpy(),
        "player_id": crus["player_id"].to_numpy(),
        "annotated_frame": annotated,
        "anchor_shift": frame - annotated,
        "no_dead_ball_before": sem_morto,
        "pass_secundario": crus["pass_secundario"].to_numpy(),
        "metrica_type": crus["dfl_type"].to_numpy(),
        "metrica_subtype": crus["dfl_path"].to_numpy(),
        "source_rows": crus["event_id"].to_numpy(),
    }).astype(schema.EVENTS)
    schema.validar(saida, schema.EVENTS, f"events(idsse {game})")
    return saida.assign(dt_sync_s=dt, anotado_em_morto=em_morto)


def carregar_jogo(game: int, cfg: dict, pasta_cache=None) -> dict:
    """Um jogo inteiro: dict com `frames`, `tracking`, `periods`, `eventos`
    (EVENTS + diagnostico), `t_utc_ns`, `nan`, `n_delete`, `cache`, `match_id`."""
    arq = caminhos(cfg, game)
    frames, tracking, t_utc_ns, nan, estado = posicoes_cacheadas(arq["posicoes"], arq["ficha"], game, cfg,
                                                                 pasta_cache)
    ficha = ler_ficha(arq["ficha"], cfg)
    crus, n_delete = ler_eventos(arq["eventos"], ficha, game, cfg)
    return {
        "match_id": cfg["idsse"]["jogos"][game - 1],
        "frames": frames,
        "tracking": tracking,
        "periods": schema.montar_periods(game, tracking),
        "eventos": construir_gabarito(game, crus, frames, t_utc_ns, cfg),
        "t_utc_ns": t_utc_ns,
        "nan": nan,
        "n_delete": n_delete,
        "cache": estado,
    }

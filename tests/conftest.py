"""Fixtures compartilhadas. Cada jogo e carregado uma vez por sessao.

Aqui tambem vivem o construtor de dado sintetico (`cenario`) e o
`possession.calcular` memorizado no dado real (`posse_real`), usados pelos
quatro testes do Passo 1. Ficam no `conftest.py` porque e o lugar canonico de
fixture compartilhada: nenhum arquivo de teste importa de outro.
"""

import copy
from functools import lru_cache

import numpy as np
import pandas as pd
import pytest

from src import gabarito, possession
from src.config import carregar_config, carregar_mapeamento
from src.events import bola_parada, passes
from src.io import carregar_jogo, schema

JOGOS = (1, 2, 3)


@lru_cache(maxsize=1)
def _cfg():
    return carregar_config()


@lru_cache(maxsize=1)
def _mapeamento():
    return carregar_mapeamento(_cfg())


@lru_cache(maxsize=len(JOGOS))
def _jogo(game: int):
    """(frames, tracking, periods) do jogo."""
    return carregar_jogo(game, _cfg())


@lru_cache(maxsize=len(JOGOS))
def _eventos(game: int):
    """(eventos_crus, gabarito) do jogo."""
    crus = gabarito.carregar_eventos_crus(game, _cfg(), _mapeamento())
    frames = _jogo(game)[0]
    return crus, gabarito.construir_gabarito(game, crus, frames, _cfg())


def _cenario(bola, jogadores, **posse):
    """Monta (frames, tracking, cfg) sinteticos de um jogo de teste.

    `bola`: lista de `(x, y)` em metros, um par por quadro; `(nan, nan)` e bola
    morta. `jogadores`: dict `player_id -> (team, [(x, y), ...])` com um par por
    quadro; `(nan, nan)` e jogador ausente. `posse`: sobrescreve chaves de
    `cfg['posse']`.
    Saida: (frames, tracking, cfg) nos esquemas FRAMES e TRACKING.
    """
    cfg = _cfg()
    bola = np.asarray(bola, dtype="float64")
    n = len(bola)
    quadro = np.arange(1, n + 1, dtype="int64")
    frames = pd.DataFrame(
        {
            "game": np.ones(n, dtype="int64"),
            "period": np.ones(n, dtype="int64"),
            "frame": quadro,
            "t": quadro / cfg["tracking"]["fps"],
            "ball_x": bola[:, 0],
            "ball_y": bola[:, 1],
            "ball_live": ~np.isnan(bola[:, 0]),
        }
    )
    linhas = [
        (1, 1, i + 1, pid, team, False, x, y, True)
        for pid, (team, pos) in jogadores.items()
        for i, (x, y) in enumerate(pos)
        if not np.isnan(x)
    ]
    tracking = pd.DataFrame(linhas, columns=list(schema.TRACKING)).astype(schema.TRACKING)
    novo = copy.deepcopy(cfg)
    novo["posse"].update(posse)
    return schema.validar(frames, schema.FRAMES, "frames sintetico"), tracking, novo


_POSSE_REAL = {}


def _posse_real(game: int, **posse):
    """`possession.calcular` no dado real, memorizado por (jogo, parametros)."""
    chave = (game, tuple(sorted(posse.items())))
    if chave not in _POSSE_REAL:
        novo = copy.deepcopy(_cfg())
        novo["posse"].update(posse)
        frames, tracking, _ = _jogo(game)
        _POSSE_REAL[chave] = possession.calcular(frames, tracking, novo)
    return _POSSE_REAL[chave]


_PASSES_REAL = {}


def _passes_real(game: int, **posse):
    """(passes, deteccoes de bola parada) no dado real, memorizado por (jogo,
    parametros de `posse`). As deteccoes usam o MESMO `cfg`, porque o padrao
    de bola parada tambem depende de `R_pz`."""
    chave = (game, tuple(sorted(posse.items())))
    if chave not in _PASSES_REAL:
        novo = copy.deepcopy(_cfg())
        novo["posse"].update(posse)
        frames, tracking, periods = _jogo(game)
        p1 = _posse_real(game, **posse)
        det = bola_parada.detectar(frames, tracking, periods, p1["perdas"], novo)
        _PASSES_REAL[chave] = (
            passes.rotular(p1["perdas"], p1["ganhos"], p1["control"], frames, det),
            det,
        )
    return _PASSES_REAL[chave]


@pytest.fixture(scope="session")
def passes_real():
    """Funcao (game, **posse) -> (passes, deteccoes de bola parada), memorizado."""
    return _passes_real


@pytest.fixture(scope="session")
def cfg():
    return _cfg()


@pytest.fixture(scope="session")
def mapeamento():
    return _mapeamento()


@pytest.fixture(scope="session")
def jogo():
    """Funcao game -> (frames, tracking, periods)."""
    return _jogo


@pytest.fixture(scope="session")
def eventos():
    """Funcao game -> (eventos_crus, gabarito)."""
    return _eventos


@pytest.fixture(scope="session")
def cenario():
    """Funcao (bola, jogadores, **posse) -> (frames, tracking, cfg) sinteticos."""
    return _cenario


@pytest.fixture(scope="session")
def posse_real():
    """Funcao (game, **posse) -> `possession.calcular`, memorizado."""
    return _posse_real

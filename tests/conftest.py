"""Fixtures compartilhadas. Cada jogo e carregado uma vez por sessao."""

from functools import lru_cache

import pytest

from src import gabarito
from src.config import carregar_config, carregar_mapeamento
from src.io import carregar_jogo

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

"""Camada de I/O: le os formatos da Metrica e devolve as tabelas canonicas.

Toda conversao de unidade e de sistema de coordenadas acontece aqui, nunca no
meio do pipeline (CLAUDE.md).
"""


def carregar_jogo(game: int, cfg: dict):
    """Devolve (frames, tracking, periods) do jogo pedido.

    Jogos 1 e 2 vem do CSV padrao, o jogo 3 do EPTS FIFA. Esquemas em
    `src.io.schema`.
    """
    from src.io import metrica_csv, metrica_epts

    modulo = metrica_csv if game in (1, 2) else metrica_epts
    return modulo.carregar(game, cfg)

"""Conversao entre o sistema normalizado da Metrica e o sistema interno em metros.

Sistema interno (CLAUDE.md, docs/02-dados.md "Esquema interno"): origem no centro
do campo, `x` no sentido do comprimento, `y` no sentido da largura e crescendo
PARA CIMA. A Metrica tem (0,0) no canto SUPERIOR esquerdo, logo o `y`
normalizado cresce para baixo e a conversao leva sinal negativo
(docs/fatias/01-plano.md §2.3).

**Nenhum clamp.** As coordenadas da Metrica saem de [0,1] de proposito: os
jogadores estao recortados em -0,05 e 1,05 e a bola vai de -0,0455 a 1,0600
(docs/inspecao-metrica.md §2.2). Recortar destruiria exatamente os laterais e
escanteios que o projeto mede.

As dimensoes do campo vem de config.yaml (`campo.comprimento_m`,
`campo.largura_m`), nunca hardcoded.
"""

import numpy as np


def x_para_metros(x_norm, comprimento_m: float):
    """x normalizado (0 = fundo esquerdo, 1 = fundo direito) -> metros do centro."""
    return (np.asarray(x_norm, dtype=float) - 0.5) * comprimento_m


def y_para_metros(y_norm, largura_m: float):
    """y normalizado (0 = lateral de cima) -> metros do centro, crescendo para cima."""
    return -(np.asarray(y_norm, dtype=float) - 0.5) * largura_m


def x_para_normalizado(x_m, comprimento_m: float):
    """Inversa de `x_para_metros`."""
    return np.asarray(x_m, dtype=float) / comprimento_m + 0.5


def y_para_normalizado(y_m, largura_m: float):
    """Inversa de `y_para_metros`."""
    return -np.asarray(y_m, dtype=float) / largura_m + 0.5

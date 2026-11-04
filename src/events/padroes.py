"""O padrao: o primeiro quadro em jogo, com a bola.

**Padrao** = no primeiro quadro em jogo, o jogador do gatilho esta dentro da
**zona do padrao** E a bola esta dentro da `R_pz` dele (§2.4.1, p. 7). Havendo
varios, o **mais proximo da bola** e o executor.

Para escanteio, lateral e tiro de meta a zona do padrao e **a mesma** do gatilho
(Fig. 4, p. 6, legenda: *"trigger and pattern zones coincide for corners,
throw-ins and goal kicks"*). O que muda e **quem** se avalia (os jogadores,
durante a bola morta, no gatilho) e **quando** (o primeiro quadro em jogo, com a
bola, no padrao).

Para pontape inicial e penalti a zona do padrao e a parte do gatilho que fala do
jogador -- o circulo de `eps_k2` em torno da marca central e a caixa do cobrador
--, SEM as condicoes sobre o conjunto dos jogadores: estas sao do gatilho, que
se avalia na bola morta.

O tiro livre nao tem zona: o padrao dele e so a bola na `R_pz` de um jogador
(`docs/01-definicoes.md`, "Tiro livre -- categoria residual").

`R_pz` vem de `config.yaml:posse.r_pz_m` -- e a MESMA PZ do Passo 1. O texto
principal nao define PZ propria de bola parada; a PZ especifica com outro
conjunto de hiperparametros e do Mills, §2.2, p. 4, e a decisao do projeto e
seguir o Vidal-Codina (V13, `decisoes.md`). Consequencia declarada: varrer
`R_pz` move tambem as bolas paradas.
"""

import numpy as np

from src.events import gatilhos


def zonas_padrao(px, py, attack_dir, cfg: dict) -> dict:
    """Zona do padrao por tipo, elemento a elemento (qualquer forma).

    Entrada: posicoes em metros no quadro que se quer avaliar e o `attack_dir`
    DO JOGADOR (no penalti o cobrador ataca o gol ativo, logo e o dele mesmo).
    """
    return {
        "kickoff": gatilhos.zona_marca_central(px, py, cfg),
        "penalty": gatilhos.zona_cobrador_penalti(px, py, attack_dir, cfg),
        "corner_kick": gatilhos.zona_escanteio(px, py, attack_dir, cfg),
        "throw_in": gatilhos.zona_lateral(py, cfg),
        "goal_kick": gatilhos.zona_tiro_de_meta(px, py, attack_dir, cfg),
    }


def distancia_bola(px, py, ball_x, ball_y):
    """Distancia jogador-bola, `NaN` onde falta dado de um dos dois."""
    return np.hypot(px - ball_x, py - ball_y)


def na_pz(distancia, cfg: dict):
    """A bola esta na PZ do jogador: `d <= R_pz`, comparacao INCLUSIVA.

    Igual ao Passo 1 (`src.possession._zonas`): a bola exatamente sobre o
    circulo esta dentro, e `NaN` fica fora.
    """
    return distancia <= cfg["posse"]["r_pz_m"]


def executor(candidatos: np.ndarray, distancia: np.ndarray) -> int:
    """Indice do candidato de menor `distancia`, ou -1 se nao ha candidato.

    Desempate: o primeiro indice, que e o menor `player_id` porque as linhas
    estao em ordem de `player_id` (mesma convencao da Fatia 3, lacuna 1).
    `NaN` em `distancia` nunca ganha: vai para `+inf`.
    """
    if not candidatos.any():
        return -1
    d = np.where(candidatos & ~np.isnan(distancia), distancia, np.inf)
    if not np.isfinite(d).any():
        return -1
    return int(d.argmin())

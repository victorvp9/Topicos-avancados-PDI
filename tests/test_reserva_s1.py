"""A hierarquia de RESERVA do suplementar S1, inteira e so sintetica.

Criterios: docs/fatias/04-plano.md §7.3. Esta tabela e **obrigatoria**: sem a
reserva o F1 medio de bola parada do artigo cai de 95 % para 85 % (S1, p. 2).

Por que tudo aqui e sintetico: o **problema 2 esta DORMENTE na Metrica**, que
tem 22 jogadores com dado em todos os quadros, logo nenhum executor "deixa de ser
detectado em `[di+1, dc]`". Ele acorda no simulador da Fatia 6, e se estiver
errado o simulador mediria o algoritmo errado sem ninguem notar. Dois pares de
testes rodam no caminho em que a decisao DIVERGE:

- problema 1: a MESMA cena com o jogador andando 0,5 m e 2,0 m antes do passe da
  `(corner_kick, A, reserva_1)` e `(corner_kick, B, reserva_3)` -- muda o
  executor e a via, nao so o rotulo;
- problema 2: a MESMA cena com o jogador AUSENTE e com ele presente fora da zona
  da `(corner_kick, A, reserva_2)` e `(corner_kick, A, reserva_3)` -- e a
  discriminacao que a Fatia 6 vai exercitar.

Todas as cenas tem 12 quadros: 1 vivo, 2 a 9 mortos (`dc` = 9), 10 a 12 vivos
(`f1` = 10, e o passe no quadro 11 quando existe).
"""

import copy

import numpy as np
import pandas as pd
import pytest

from src.events import bola_parada, hierarquia
from src.io import schema

AUSENTE = (np.nan, np.nan)


def _periods(dir_home: int = 1) -> pd.DataFrame:
    """`periods` sintetico do jogo 1, periodo 1 (esquema PERIODS)."""
    return pd.DataFrame(
        [(1, 1, "away", -dir_home, 40.0 * dir_home),
         (1, 1, "home", dir_home, -40.0 * dir_home)],
        columns=list(schema.PERIODS),
    ).astype(schema.PERIODS)


def _passes(*pares) -> pd.DataFrame:
    """`passes` sintetico: pares `(player_id, quadro)`. Quem passa importa --
    o problema 1 do S1 mede o deslocamento do jogador que passa a bola."""
    return pd.DataFrame(
        {
            "player_id": pd.Series([p for p, _ in pares], dtype="str"),
            "frame": pd.Series([f for _, f in pares], dtype="int64"),
        }
    )


def _detectar(cenario, bola, jogadores, passes=(), **bola_parada_cfg):
    frames, tracking, cfg = cenario(bola, jogadores)
    cfg["bola_parada"].update(bola_parada_cfg)
    det = bola_parada.detectar(
        frames, tracking, _periods(), _passes(*passes), cfg
    )
    assert len(det) == 1                       # uma transicao, uma deteccao
    assert det["via"].iloc[0] in hierarquia.VIAS
    return det.iloc[0]


def _cena_problema_1(cfg, desloca: float):
    """Cena do problema 1: o booleano diz morta mas o jogo ja voltou.

    `A` tem a bola no primeiro quadro em jogo FORA da zona de escanteio, e entra
    nela ao andar `desloca` metros ate o passe. `B` ativa o gatilho de escanteio
    o intervalo morto inteiro, e o padrao dele NAO pode ser confirmado porque a
    bola esta com `A`.
    """
    canto_x = cfg["campo"]["comprimento_m"] / 2.0
    canto_y = cfg["campo"]["largura_m"] / 2.0
    # 3,5 m do vertice em `f1`; 3,5 - desloca no quadro do passe.
    a = [(canto_x, canto_y - 6.0)] * 9 + [
        (canto_x, canto_y - 3.5),
        (canto_x, canto_y - 3.5 + desloca),
        (canto_x, canto_y - 3.5 + desloca),
    ]
    bola = [(0.0, 0.0)] + [AUSENTE] * 8 + a[9:]
    jogadores = {
        "g1_home_1": ("home", a),
        "g1_home_2": ("home", [(canto_x, canto_y)] * 12),      # `B`, no vertice
        "g1_away_1": ("away", [(-20.0, -20.0)] * 12),
    }
    return bola, jogadores


def test_problema_1_jogador_parado_e_o_executor(cenario, cfg):
    """SINTETICO. Anda 0,5 m < `eps_f` = 1 m antes do passe: ele e o executor, e
    os gatilhos e padroes sao REAVALIADOS para ele no quadro do passe -- onde ele
    ja esta na zona de escanteio."""
    bola, jogadores = _cena_problema_1(cfg, 0.5)
    linha = _detectar(cenario, bola, jogadores, passes=[("g1_home_1", 11)])
    assert linha["type"] == "corner_kick"
    assert linha["player_id"] == "g1_home_1"
    assert linha["via"] == "reserva_1"


def test_problema_1_jogador_anda_demais_cai_no_problema_3(cenario, cfg):
    """SINTETICO, MESMA cena com 2,0 m > `eps_f`: ele NAO e o executor.

    Cai no problema 3, que usa so gatilhos: o escanteio completo de `B` decide, e
    o executor passa a ser `B`.
    """
    bola, jogadores = _cena_problema_1(cfg, 2.0)
    linha = _detectar(cenario, bola, jogadores, passes=[("g1_home_1", 11)])
    assert linha["type"] == "corner_kick"
    assert linha["player_id"] == "g1_home_2"
    assert linha["via"] == "reserva_3"


def test_problema_1_sem_passe_nenhum_nao_confirma(cenario, cfg):
    """SINTETICO, MESMA cena sem passe na corrida viva: nao ha deslocamento para
    medir, logo o jogador nao e confirmado como executor e o caso cai no
    problema 3. Borda declarada no `src/events/hierarquia.py`."""
    bola, jogadores = _cena_problema_1(cfg, 0.5)
    linha = _detectar(cenario, bola, jogadores, passes=[])
    assert linha["via"] == "reserva_3"
    assert linha["player_id"] == "g1_home_2"


@pytest.mark.parametrize(
    "passes, esperado",
    [
        # `A` passa no 12 (anda 0,5 m), outro jogador passa ANTES, no 11 (onde
        # `A` esta a 2,0 m): mede-se o 12 e `A` e confirmado.
        ([("g1_away_1", 11), ("g1_home_1", 12)], ("g1_home_1", "reserva_1")),
        # mesma cena com os passes trocados: mede-se o 11 e `A` nao e confirmado.
        ([("g1_home_1", 11), ("g1_away_1", 12)], ("g1_home_2", "reserva_3")),
    ],
)
def test_problema_1_mede_so_o_passe_do_executor(cenario, cfg, passes, esperado):
    """SINTETICO, regressao do mutante M6 (revisao de 2026-11-02).

    O S1, p. 1: *"does not move more than eps_f before the ball is passed"* --
    o passe e o do executor putativo, nao o de qualquer jogador. `A` anda 2,0 m
    ate o quadro 11 e volta a 0,5 m do ponto de partida no quadro 12, logo os
    dois quadros ficam em lados opostos de `eps_f` = 1 m. Com "primeiro passe de
    qualquer jogador" as duas cenas mediriam o quadro 11 e a primeira sairia
    `(g1_home_2, reserva_3)`.
    """
    canto_x = cfg["campo"]["comprimento_m"] / 2.0
    canto_y = cfg["campo"]["largura_m"] / 2.0
    a = [(canto_x, canto_y - 6.0)] * 9 + [
        (canto_x, canto_y - 3.5),      # f1
        (canto_x, canto_y - 1.5),      # 2,0 m de f1
        (canto_x, canto_y - 3.0),      # 0,5 m de f1, a 3,0 m do vertice
    ]
    bola = [(0.0, 0.0)] + [AUSENTE] * 8 + a[9:]
    jogadores = {
        "g1_home_1": ("home", a),
        "g1_home_2": ("home", [(canto_x, canto_y)] * 12),
        "g1_away_1": ("away", [(-20.0, -20.0)] * 12),
    }
    linha = _detectar(cenario, bola, jogadores, passes=passes)
    assert linha["type"] == "corner_kick"
    assert (linha["player_id"], linha["via"]) == esperado


def _cena_problema_2(cfg, depois_do_gatilho):
    """Cena do problema 2: `A` ativa o escanteio nos quadros 2 a 4 e depois
    `depois_do_gatilho` (ausente, ou presente fora da zona). A bola reaparece
    longe de todos, logo o padrao de tiro livre NAO e ativado."""
    canto_x = cfg["campo"]["comprimento_m"] / 2.0
    canto_y = cfg["campo"]["largura_m"] / 2.0
    a = [(canto_x, canto_y - 1.0)] * 4 + [depois_do_gatilho] * 8
    bola = [(0.0, 0.0)] + [AUSENTE] * 8 + [(0.0, 0.0)] * 3
    jogadores = {
        "g1_home_1": ("home", a),
        "g1_home_2": ("home", [(20.0, 0.0)] * 12),
        "g1_away_1": ("away", [(-20.0, -20.0)] * 12),
    }
    return bola, jogadores


def test_problema_2_executor_nao_rastreado_recebe_o_evento(cenario, cfg):
    """SINTETICO. O gatilho de escanteio ficou incompleto porque o jogador que o
    ativava DEIXOU DE SER DETECTADO em `[di+1, dc]`: o evento e imputado a ele.

    E o teste que a Fatia 6 vai exercitar de verdade -- na Metrica o problema 2
    nunca dispara, porque ninguem desaparece.
    """
    bola, jogadores = _cena_problema_2(cfg, AUSENTE)
    linha = _detectar(cenario, bola, jogadores, passes=[("g1_home_2", 11)])
    assert linha["type"] == "corner_kick"
    assert linha["player_id"] == "g1_home_1"
    assert linha["team"] == "home"
    assert linha["via"] == "reserva_2"
    assert linha["gatilhos_incompletos"] == "corner_kick"
    assert linha["gatilhos_completos"] == ""


def test_problema_2_nao_dispara_se_o_jogador_segue_rastreado(cenario, cfg):
    """SINTETICO, MESMA cena com o jogador PRESENTE fora da zona.

    O gatilho tambem ficou incompleto, mas por outro motivo: ele nao desapareceu,
    saiu da zona. O problema 2 nao se aplica e a decisao cai no problema 3, que
    usa o gatilho incompleto. Mesmo rotulo e mesmo executor, `via` diferente --
    e essa diferenca e o que a Fatia 6 mede.
    """
    bola, jogadores = _cena_problema_2(cfg, (20.0, 10.0))
    linha = _detectar(cenario, bola, jogadores, passes=[("g1_home_2", 11)])
    assert linha["type"] == "corner_kick"
    assert linha["player_id"] == "g1_home_1"
    assert linha["via"] == "reserva_3"


def test_problema_3_lateral_completo_antes_de_escanteio_incompleto(cenario, cfg):
    """SINTETICO. S1, p. 2: *"higher detection rate when favoring complete
    throw-in over incomplete corner"*. Escanteio INCOMPLETO e lateral COMPLETO
    ao mesmo tempo: sai lateral."""
    canto_x = cfg["campo"]["comprimento_m"] / 2.0
    canto_y = cfg["campo"]["largura_m"] / 2.0
    bola = [(0.0, 0.0)] + [AUSENTE] * 8 + [(0.0, 0.0)] * 3
    linha = _detectar(
        cenario,
        bola,
        {"g1_home_1": ("home", [(canto_x, canto_y - 1.0)] * 4 + [(20.0, 0.0)] * 8),
         "g1_home_2": ("home", [(0.0, canto_y - 0.1)] * 12),
         "g1_away_1": ("away", [(-20.0, -20.0)] * 12)},
        passes=[("g1_home_2", 11)],
    )
    assert linha["gatilhos_completos"] == "throw_in"
    assert linha["gatilhos_incompletos"] == "corner_kick"
    assert linha["type"] == "throw_in"
    assert linha["player_id"] == "g1_home_2"
    assert linha["via"] == "reserva_3"


def test_problema_3_sem_gatilho_nenhum_sai_free_kick_duvida(cenario, cfg):
    """SINTETICO. Nenhum gatilho ativa e a bola nao esta na PZ de ninguem: o
    rotulo e `free_kick?`, sem executor.

    `free_kick?` e categoria PROPRIA e **nunca** e somada em `free_kick`
    (S2, p. 3; plano 04 §3.4).
    """
    bola = [(0.0, 0.0)] + [AUSENTE] * 8 + [(0.0, 0.0)] * 3
    linha = _detectar(
        cenario,
        bola,
        {"g1_home_1": ("home", [(20.0, 0.0)] * 12),
         "g1_away_1": ("away", [(-20.0, 0.0)] * 12)},
        passes=[("g1_home_1", 11)],
    )
    assert linha["type"] == hierarquia.FREE_KICK_DUVIDA == "free_kick?"
    assert linha["type"] != hierarquia.FREE_KICK
    assert linha["player_id"] == "" and linha["team"] == ""
    assert linha["via"] == "reserva_3"
    assert linha["gatilhos_completos"] == "" and linha["gatilhos_incompletos"] == ""


def _cena_so_tiro_de_meta(cfg):
    """Cena do problema 3 com SO o tiro de meta completo.

    `A` (home, ataca +x) esta dentro da propria pequena area o intervalo morto
    inteiro; `B` (away) esta no meio do campo. A bola reaparece longe dos dois,
    logo nenhum padrao pode ser checado. Nenhum outro gatilho ativa: ninguem a
    `eps_k2` do centro, ninguem no vertice, ninguem alem da lateral, e a caixa
    da linha de gol fica vazia nos dois lados ativos.
    """
    meio = cfg["campo"]["comprimento_m"] / 2.0
    bola = [(0.0, 0.0)] + [AUSENTE] * 8 + [(0.0, -20.0)] * 3
    jogadores = {
        "g1_home_1": ("home", [(-meio + 2.5, 0.0)] * 12),
        "g1_away_1": ("away", [(20.0, 5.0)] * 12),
    }
    return bola, jogadores


def test_goal_kick_no_problema_3_muda_a_saida(cenario, cfg):
    """SINTETICO. Mesma cena, so o valor de `bola_parada.goal_kick_no_problema_3`
    muda, e cada leitura e pedida PELA CHAVE:

      `nao`           (prosa do S1, que omite o `G`) -> `free_kick?`, sem executor;
      `antes_de_cto`  -> `goal_kick`, executor `A`, via `reserva_3`;
      `depois_de_cto` (Fig. S1 lida: `K P C T Ci Ti G F?`, o PADRAO) -> idem.

    Falha se a chave for ignorada, nos dois sentidos.
    """
    assert cfg["bola_parada"]["goal_kick_no_problema_3"] == "depois_de_cto"
    bola, jogadores = _cena_so_tiro_de_meta(cfg)
    prosa = _detectar(cenario, bola, jogadores, passes=[("g1_home_1", 11)],
                      goal_kick_no_problema_3="nao")
    assert prosa["gatilhos_completos"] == "goal_kick"
    assert prosa["type"] == hierarquia.FREE_KICK_DUVIDA
    assert prosa["player_id"] == ""
    assert prosa["via"] == "reserva_3"

    # nesta cena nenhum escanteio nem lateral ativa, logo as DUAS posicoes do
    # tiro de meta dao o mesmo resultado -- o que muda entre elas e a disputa
    # com C/T, medida no dado real.
    for posicao in ("antes_de_cto", "depois_de_cto"):
        figura = _detectar(
            cenario, bola, jogadores, passes=[("g1_home_1", 11)],
            goal_kick_no_problema_3=posicao,
        )
        assert figura["type"] == "goal_kick", posicao
        assert figura["player_id"] == "g1_home_1"
        assert figura["via"] == "reserva_3"


def _com_posicao(cfg, posicao):
    novo = copy.deepcopy(cfg)
    novo["bola_parada"]["goal_kick_no_problema_3"] = posicao
    return novo


def test_as_tres_posicoes_do_tiro_de_meta_na_ordem_do_problema_3(cfg):
    """As tres leituras, por extenso, e nenhuma mexe em mais nada da ordem.

    O padrao e a Fig. S1 lida, `K P C T Ci Ti G` (`free_kick?` e a saida
    quando nada ativa, nao entra na ordem).
    """
    k, p = ("kickoff", "completo"), ("penalty", "completo")
    c, t = ("corner_kick", "completo"), ("throw_in", "completo")
    ci, ti = ("corner_kick", "incompleto"), ("throw_in", "incompleto")
    g = ("goal_kick", "completo")
    depois = (k, p, c, t, ci, ti, g)
    assert hierarquia.ordem_reserva_3(_com_posicao(cfg, "depois_de_cto")) == depois
    assert hierarquia.ordem_reserva_3(_com_posicao(cfg, "nao")) == (k, p, c, t, ci, ti)
    assert hierarquia.ordem_reserva_3(_com_posicao(cfg, "antes_de_cto")) == (
        k, p, g, c, t, ci, ti
    )
    assert hierarquia.ordem_reserva_3(cfg) == depois


def test_posicao_desconhecida_estoura(cenario, cfg):
    """Valor fora do dominio estoura: nao ha ordem padrao silenciosa."""
    with pytest.raises(ValueError):
        hierarquia.ordem_reserva_3(_com_posicao(cfg, "talvez"))
    bola, jogadores = _cena_so_tiro_de_meta(cfg)
    with pytest.raises(ValueError):
        _detectar(cenario, bola, jogadores, goal_kick_no_problema_3="talvez")


def test_as_quatro_vias_sao_alcancaveis(cenario, cfg):
    """SINTETICO. As quatro `via` aparecem, e `reserva_2` so aqui: no dado real
    ela e inalcancavel, porque ninguem deixa de ser rastreado."""
    canto_x = cfg["campo"]["comprimento_m"] / 2.0
    canto_y = cfg["campo"]["largura_m"] / 2.0
    vias = set()
    # padrao: gatilho completo confirmado pelo padrao
    vias.add(_detectar(
        cenario,
        [(0.0, 0.0)] + [AUSENTE] * 8 + [(canto_x, canto_y)] * 3,
        {"g1_home_1": ("home", [(canto_x, canto_y)] * 12),
         "g1_away_1": ("away", [(-20.0, -20.0)] * 12)},
        passes=[("g1_home_1", 11)],
    )["via"])
    vias.add(_detectar(cenario, *_cena_problema_1(cfg, 0.5),
                       passes=[("g1_home_1", 11)])["via"])
    vias.add(_detectar(cenario, *_cena_problema_2(cfg, AUSENTE),
                       passes=[("g1_home_2", 11)])["via"])
    vias.add(_detectar(cenario, *_cena_problema_2(cfg, (20.0, 10.0)),
                       passes=[("g1_home_2", 11)])["via"])
    assert vias == set(hierarquia.VIAS)

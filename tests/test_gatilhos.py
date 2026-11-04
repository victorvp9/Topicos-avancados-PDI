"""Os seis gatilhos: zonas, LADO ATIVO, completo x incompleto, e a varredura de
cada tolerancia.

Criterios e CAMINHO de cada teste: docs/fatias/04-plano.md §7.1.

Dois caminhos valem registro:

- o teste do vertice ativo roda com o jogador no vertice do **lado errado**, e a
  segunda asserticao mostra que o MESMO ponto dispara com o `attack_dir`
  trocado: e o caminho em que ignorar o lado daria o resultado oposto;
- o teste de completo x incompleto roda com um gatilho que **cai 5 quadros antes
  de `dc`** e outro que fica, e le as duas colunas de auditoria, que e onde a
  diferenca aparece sem passar pela hierarquia.

As varreduras rodam no **dado real** (jogo 1) para as seis tolerancias de
escanteio, lateral, tiro de meta, pontape inicial e `eps_f`, um teste por
tolerancia, isoladamente. As tres do penalti rodam no **sintetico**, e o motivo
esta medido no docstring do teste: com a caixa quadrada do §2.3.4, p. 6, o
gatilho de penalti nao dispara em nenhuma das 481 transicoes dos tres jogos.
"""

import copy

import numpy as np
import pandas as pd
import pytest

from src.events import bola_parada, gatilhos
from src.io import schema

# Um intervalo morto so: quadro 1 vivo, 2 a 9 mortos, 10 vivo (`f1` = 10).
BOLA_MORTA = [(0.0, 0.0)] + [(np.nan, np.nan)] * 8
_CACHE = {}


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


def _detectar_sintetico(cenario, bola, jogadores, passes=(), dir_home=1, **tolerancias):
    """Roda `bola_parada.detectar` num cenario sintetico."""
    frames, tracking, cfg = cenario(bola, jogadores)
    cfg["bola_parada"].update(tolerancias)
    return bola_parada.detectar(
        frames, tracking, _periods(dir_home), _passes(*passes), cfg
    )


def _detectar_real(jogo, posse_real, cfg, game, **tolerancias):
    """`detectar` no dado real, memorizado por (jogo, tolerancias trocadas)."""
    chave = (game, tuple(sorted(tolerancias.items())))
    if chave not in _CACHE:
        novo = copy.deepcopy(cfg)
        novo["bola_parada"].update(tolerancias)
        frames, tracking, periods = jogo(game)
        perdas = posse_real(game)["perdas"]
        _CACHE[chave] = bola_parada.detectar(frames, tracking, periods, perdas, novo)
    return _CACHE[chave]


# --- zonas, sinteticas -----------------------------------------------------


def test_escanteio_dispara_a_2_m_e_nao_a_4_m(cfg):
    """SINTETICO. `eps_c` = 3 m: 2 m do vertice ativo dispara, 4 m nao."""
    meia_largura = cfg["campo"]["largura_m"] / 2.0
    canto_x = cfg["campo"]["comprimento_m"] / 2.0
    assert cfg["bola_parada"]["eps_c_m"] == 3.0
    assert gatilhos.zona_escanteio(canto_x, meia_largura - 2.0, 1, cfg)
    assert not gatilhos.zona_escanteio(canto_x, meia_largura - 4.0, 1, cfg)


def test_escanteio_usa_o_vertice_ATIVO(cfg):
    """SINTETICO, jogador no vertice do LADO ERRADO: nao dispara.

    Caminho em que ignorar `attack_dir` daria o resultado oposto: o mesmo ponto
    dispara para quem ataca o outro lado.
    """
    meia_largura = cfg["campo"]["largura_m"] / 2.0
    canto_x = cfg["campo"]["comprimento_m"] / 2.0
    assert not gatilhos.zona_escanteio(-canto_x, meia_largura - 1.0, 1, cfg)
    assert gatilhos.zona_escanteio(-canto_x, meia_largura - 1.0, -1, cfg)


def test_lateral_dispara_em_338_e_nao_em_332(cfg):
    """SINTETICO. `eps_t` = 0,5 m: |y| = 33,8 dispara, 33,2 nao, nos dois lados."""
    assert cfg["bola_parada"]["eps_t_m"] == 0.5
    assert gatilhos.zona_lateral(33.8, cfg)
    assert gatilhos.zona_lateral(-33.8, cfg)
    assert not gatilhos.zona_lateral(33.2, cfg)
    assert not gatilhos.zona_lateral(-33.2, cfg)


def test_tiro_de_meta_usa_a_PROPRIA_area(cfg):
    """SINTETICO, jogador na pequena area ADVERSARIA: nao dispara."""
    meio = cfg["campo"]["comprimento_m"] / 2.0
    assert gatilhos.zona_tiro_de_meta(-meio + 3.0, 0.0, 1, cfg)
    assert not gatilhos.zona_tiro_de_meta(meio - 3.0, 0.0, 1, cfg)


def test_tiro_de_meta_respeita_a_caixa_de_eps_g(cfg):
    """SINTETICO. Caixa = pequena area inflada por `eps_g` = 0,5 m nos 4 lados."""
    campo = cfg["campo"]
    meio = campo["comprimento_m"] / 2.0
    limite = campo["pequena_area_profundidade_m"] + cfg["bola_parada"]["eps_g_m"]
    assert gatilhos.zona_tiro_de_meta(-meio + limite, 0.0, 1, cfg)
    assert not gatilhos.zona_tiro_de_meta(-meio + limite + 0.1, 0.0, 1, cfg)
    largura = campo["pequena_area_meia_largura_m"] + cfg["bola_parada"]["eps_g_m"]
    assert gatilhos.zona_tiro_de_meta(-meio + 3.0, largura, 1, cfg)
    assert not gatilhos.zona_tiro_de_meta(-meio + 3.0, largura + 0.1, 1, cfg)


def test_tiro_de_meta_limite_atras_da_propria_linha(cfg):
    """SINTETICO, regressao do mutante M12 (revisao de 2026-11-02): o LIMITE
    INFERIOR da caixa. A profundidade e ORIENTADA; com `abs()` nela o jogador
    atras da propria linha de fundo contaria como dentro da pequena area.

    Caso real: jogo 2, quadro 27994, executor a -0,56 m da propria linha
    (`docs/inspecao-metrica.md` §6.2), com `eps_g` = 0,5 m: NAO completa. Os
    dois lados de ataque, e pelo gatilho inteiro (`ativacoes`), nao so a zona.
    """
    eps = cfg["bola_parada"]["eps_g_m"]
    assert eps == 0.5
    meio = cfg["campo"]["comprimento_m"] / 2.0
    profundidade = np.array([-0.56, -eps - 0.01, -eps + 0.01, 0.0])
    esperado = [False, False, True, True]
    for lado in (1, -1):
        x = (lado * (profundidade - meio))[:, None]   # (jogador, quadro)
        y = np.zeros_like(x)
        times = np.array(["home"] * x.shape[0])
        ativo = gatilhos.ativacoes(x, y, times, lado, cfg)["goal_kick"][:, 0]
        assert ativo.tolist() == esperado, lado
        assert gatilhos.zona_tiro_de_meta(x[:, 0], y[:, 0], lado, cfg).tolist() == esperado


def test_pontape_inicial_as_duas_condicoes_isoladas(cfg):
    """SINTETICO, cada condicao isolada derruba o gatilho.

    `eps_k1` = 3 m (invasao da metade adversaria) e `eps_k2` = 2 m (alguem na
    marca central). Os dois jogadores atacam para +x.
    """
    lado = np.ones((2, 1), dtype="int8")
    def dispara(xs, ys):
        x = np.asarray(xs, dtype="float64").reshape(2, 1)
        y = np.asarray(ys, dtype="float64").reshape(2, 1)
        return bool(gatilhos.gatilho_pontape_inicial(x, y, lado, cfg).any())

    assert dispara([0.0, -10.0], [0.0, 0.0])          # as duas condicoes valem
    assert not dispara([0.0, 3.5], [0.0, 0.0])        # invasao 3,5 m > eps_k1
    assert not dispara([2.5, -10.0], [0.0, 0.0])      # ninguem a 2 m do centro


def _cena_de_penalti(cfg):
    """Cena de penalti VALIDA, com um jogador por condicao da Lei 14.

    `home` ataca +x. Ordem das linhas: cobrador `home` 1 m atras da marca ativa,
    um `home` longe, goleiro `away` 0,5 m a frente da linha de gol ativa, e um
    `away` a 14,0 m da linha de gol -- dentro da grande area, mas na faixa que a
    tolerancia `eps_p3` = 4 m perdoa, e a 10,44 m da marca, logo fora do raio de
    9,15 m. Devolve (posicoes, times, lado).
    """
    campo = cfg["campo"]
    meio = campo["comprimento_m"] / 2.0
    marca = meio - campo["marca_penal_m"]
    return (
        [(marca - 1.0, 0.0), (10.0, 0.0), (meio - 0.5, 0.0), (meio - 14.0, 10.0)],
        np.array(["home", "home", "away", "away"], dtype=object),
        np.array([[1], [1], [-1], [-1]], dtype="int8"),
    )


def _dispara_penalti(posicoes, times, lado, cfg):
    p = np.asarray(posicoes, dtype="float64")
    return bool(
        gatilhos.gatilho_penalti(
            p[:, 0].reshape(-1, 1), p[:, 1].reshape(-1, 1), times, lado, cfg
        ).any()
    )


def test_penalti_as_tres_condicoes_isoladas(cfg):
    """SINTETICO, cada condicao isolada derruba o gatilho. As quatro variantes
    mexem em UM jogador por vez."""
    campo = cfg["campo"]
    meio = campo["comprimento_m"] / 2.0
    marca = meio - campo["marca_penal_m"]
    base, times, lado = _cena_de_penalti(cfg)

    def dispara(posicoes):
        return _dispara_penalti(posicoes, times, lado, cfg)

    assert dispara(base)
    # condicao 1: dois jogadores na caixa da linha de gol
    assert not dispara([base[0], base[1], base[2], (meio - 0.5, 1.0)])
    # condicao 2: dois adversarios na caixa do cobrador
    assert not dispara([base[0], (marca - 1.0, 0.5), base[2], base[3]])
    # condicao 3, parte da grande area: um dos demais dentro dela
    assert not dispara([base[0], base[1], base[2], (meio - 7.5, 10.0)])
    # condicao 3, parte dos 9,15 m: um dos demais perto da marca
    assert not dispara([base[0], base[1], base[2], (marca - 4.5, 0.0)])


@pytest.mark.parametrize(
    "chave,valor",
    [("eps_p1_m", 0.0), ("eps_p2_m", 1.0), ("eps_p3_m", 0.0)],
)
def test_cada_tolerancia_do_penalti_muda_o_gatilho(cfg, chave, valor):
    """SINTETICO, um teste por tolerancia de penalti, ISOLADAMENTE.

    **Por que nao roda no dado real**, ao contrario das outras seis: com a caixa
    QUADRADA do §2.3.4, p. 6 (meia-largura `eps_p2/2` = 1,00 m), o gatilho de
    penalti **nao dispara em nenhuma das 481 transicoes dos tres jogos** -- o
    cobrador do unico penalti anotado esta a |y| = 1,478 m da linha da marca no
    ultimo quadro morto. Medido; esta no relatorio da fatia. Logo as tres
    tolerancias sao inertes no dado real por motivo de dado, e so um caminho
    sintetico pode mostrar que nenhuma delas e ignorada.
    """
    base, times, lado = _cena_de_penalti(cfg)
    assert _dispara_penalti(base, times, lado, cfg)
    perturbado = copy.deepcopy(cfg)
    perturbado["bola_parada"][chave] = valor
    assert not _dispara_penalti(base, times, lado, perturbado), chave


def test_gatilho_completo_e_incompleto(cenario, cfg):
    """SINTETICO, gatilho que CAI 5 QUADROS ANTES de `dc`.

    O lateral fica ativo ate `dc` (completo); o escanteio cai no quadro 4 e nao
    volta (incompleto). As duas colunas de auditoria mostram a diferenca sem
    passar pela hierarquia.
    """
    meia = cfg["campo"]["largura_m"] / 2.0
    canto = cfg["campo"]["comprimento_m"] / 2.0
    # `a` no vertice ativo nos quadros 1 a 4 e no meio do campo a partir do 5.
    a = [(canto, meia)] * 4 + [(0.0, 0.0)] * 6
    # `b` alem da linha lateral auxiliar o tempo todo, longe do vertice.
    b = [(0.0, meia - 0.2)] * 10
    det = _detectar_sintetico(
        cenario,
        BOLA_MORTA + [(20.0, 20.0)],
        {"g1_home_1": ("home", a), "g1_home_2": ("home", b),
         "g1_away_1": ("away", [(-20.0, -20.0)] * 10)},
    )
    assert len(det) == 1
    assert det["gatilhos_completos"].iloc[0] == "throw_in"
    assert det["gatilhos_incompletos"].iloc[0] == "corner_kick"


def test_jogador_ausente_nao_ativa_nem_derruba_gatilho(cenario, cfg):
    """SINTETICO, BORDA DE NaN. Jogador sem dado nao ativa gatilho nenhum e nao
    conta como invasao no pontape inicial."""
    nan = (np.nan, np.nan)
    canto = cfg["campo"]["comprimento_m"] / 2.0
    assert not bool(np.asarray(gatilhos.zona_escanteio(np.nan, np.nan, 1, cfg)).any())
    assert not bool(np.asarray(gatilhos.zona_lateral(np.nan, cfg)).any())
    assert not bool(np.asarray(gatilhos.zona_tiro_de_meta(np.nan, np.nan, 1, cfg)).any())
    # pontape inicial: o ausente estaria na metade adversaria se tivesse dado
    lado = np.ones((2, 1), dtype="int8")
    x = np.array([[0.0], [np.nan]])
    y = np.array([[0.0], [np.nan]])
    assert bool(gatilhos.gatilho_pontape_inicial(x, y, lado, cfg).any())
    # e, no detector, o ausente no vertice ativo nao gera escanteio
    det = _detectar_sintetico(
        cenario,
        BOLA_MORTA + [(canto, 0.0)],
        {"g1_home_1": ("home", [nan] * 9 + [(canto, 0.0)]),
         "g1_away_1": ("away", [(-20.0, -20.0)] * 10)},
    )
    assert det["gatilhos_completos"].iloc[0] == ""


# --- varredura de cada tolerancia, no dado real ----------------------------


def test_eps_c_varrido_muda_o_numero_de_escanteios(jogo, posse_real, cfg):
    """DADO REAL (jogo 1). O numero de escanteios detectados muda ao longo de
    `grade_eps_c_m`, e e monotono nao-decrescente na grade."""
    contagem = [
        int((_detectar_real(jogo, posse_real, cfg, 1, eps_c_m=eps)["type"]
             == "corner_kick").sum())
        for eps in cfg["bola_parada"]["grade_eps_c_m"]
    ]
    assert len(set(contagem)) > 1, contagem
    assert contagem == sorted(contagem), contagem


@pytest.mark.parametrize(
    "game,chave,valor",
    [
        (1, "eps_k1_m", 0.0),
        (1, "eps_k2_m", 0.5),
        (1, "eps_c_m", 1.0),
        (1, "eps_t_m", 2.0),
        (1, "eps_g_m", 2.0),
        (1, "eps_f_m", 100.0),
    ],
)
def test_cada_tolerancia_varrida_muda_a_saida(jogo, posse_real, cfg, game, chave, valor):
    """DADO REAL, um teste por tolerancia, ISOLADAMENTE. Falha se o parametro
    for ignorado em algum ponto do caminho.

    As tres tolerancias de penalti NAO estao aqui: com a caixa quadrada do
    §2.3.4, p. 6, o gatilho de penalti nao dispara em nenhuma das 481 transicoes
    dos tres jogos, logo no dado real elas sao inertes por motivo de dado. Elas
    tem o teste sintetico `test_cada_tolerancia_do_penalti_muda_o_gatilho`."""
    base = _detectar_real(jogo, posse_real, cfg, game)
    trocado = _detectar_real(jogo, posse_real, cfg, game, **{chave: valor})
    assert len(base) == len(trocado)   # a tolerancia nao muda as transicoes
    assert not base["type"].equals(trocado["type"]), chave

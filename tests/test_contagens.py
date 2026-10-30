"""Contagens contra docs/inspecao-metrica.md (plano §8.4).

Estes numeros foram medidos por um script independente, antes de existir codigo
do projeto. Se divergirem, um dos dois esta errado e a fatia nao passa.
"""

import hashlib

import numpy as np
import pytest

# docs/inspecao-metrica.md §3.1
POR_TYPE = {
    1: {
        "PASS": 799,
        "RECOVERY": 278,
        "BALL LOST": 257,
        "CHALLENGE": 233,
        "SET PIECE": 77,
        "BALL OUT": 51,
        "SHOT": 24,
        "FAULT RECEIVED": 22,
        "CARD": 4,
    },
    2: {
        "PASS": 964,
        "RECOVERY": 248,
        "BALL LOST": 233,
        "CHALLENGE": 311,
        "SET PIECE": 80,
        "BALL OUT": 49,
        "SHOT": 24,
        "FAULT RECEIVED": 20,
        "CARD": 6,
    },
    3: {
        "PASS": 1121,
        "CARRY": 1395,
        "RECOVERY": 294,
        "BALL LOST": 288,
        "CHALLENGE": 335,
        "SET PIECE": 90,
        "BALL OUT": 64,
        "SHOT": 20,
        "FAULT RECEIVED": 12,
        "CARD": 1,
    },
}
TOTAL_CRUS = {1: 1745, 2: 1935, 3: 3620}

# docs/inspecao-metrica.md §3.2 (subtipo principal) e §3.3 (tiro de meta)
BOLA_PARADA = {
    1: {"corner_kick": 11, "throw_in": 28, "free_kick": 32, "kickoff": 6, "goal_kick": 22},
    2: {"corner_kick": 7, "throw_in": 32, "free_kick": 32, "kickoff": 8, "goal_kick": 16},
    3: {"corner_kick": 8, "throw_in": 50, "free_kick": 28, "kickoff": 4, "goal_kick": 11},
}
PENALTY = {1: 0, 2: 1, 3: 0}

# Criterio secundario de passe (D10). Duas contagens, decisao do G3 2026-10-29:
# CRU = descritivo do vocabulario da Metrica (plano §8.4, docs/02-dados.md);
# EVENTS = NORMATIVO para avaliacao -- a execucao de uma bola parada e fundida no
# evento de bola parada e deixa de contar como passe.
PASS_SECUNDARIO_CRU = {1: 1086, 2: 1208, 3: 1447}
PASS_SECUNDARIO_EVENTS = {1: 1009, 2: 1131, 3: 1358}
THEFT = {1: 21, 2: 38}


@pytest.mark.parametrize("game", [1, 2, 3])
def test_contagem_por_type_cru(eventos, game):
    crus, _ = eventos(game)
    assert crus["metrica_type"].value_counts().to_dict() == POR_TYPE[game]
    assert len(crus) == TOTAL_CRUS[game]


@pytest.mark.parametrize("game", [1, 2, 3])
def test_bola_parada_por_tipo(eventos, game):
    _, gab = eventos(game)
    contagem = gab["type"].value_counts().to_dict()
    for tipo, esperado in BOLA_PARADA[game].items():
        assert contagem.get(tipo, 0) == esperado, tipo


@pytest.mark.parametrize("game", [1, 2, 3])
def test_set_piece_fecha_com_a_soma_dos_subtipos(eventos, game):
    """77 / 80 / 90: os 4 subtipos no escopo mais PENALTY (fora do escopo)."""
    _, gab = eventos(game)
    no_escopo = sum(
        v for k, v in BOLA_PARADA[game].items() if k != "goal_kick"
    )
    assert int((gab["metrica_type"] == "SET PIECE").sum()) == no_escopo + PENALTY[game]
    penaltis = gab[
        (gab["metrica_type"] == "SET PIECE") & (gab["metrica_subtype"].str.contains("PENALTY"))
    ]
    assert len(penaltis) == PENALTY[game]
    assert (penaltis["type"] == "fora_do_escopo").all()


@pytest.mark.parametrize("game", [1, 2, 3])
def test_pass_secundario_cru(eventos, game):
    """Contagem descritiva, nas linhas CRUAS: 1086 / 1208 / 1447."""
    crus, _ = eventos(game)
    assert int(crus["pass_secundario"].sum()) == PASS_SECUNDARIO_CRU[game]


@pytest.mark.parametrize("game", [1, 2, 3])
def test_pass_secundario_events(eventos, game):
    """Denominador NORMATIVO de avaliacao, na tabela `events`: 1009 / 1131 / 1358.

    A diferenca em relacao a contagem crua e exatamente o nº de execucoes de
    bola parada fundidas que eram `PASS`/`BALL LOST`/`BALL OUT` sem `THEFT`.
    """
    crus, gab = eventos(game)
    assert int(gab["pass_secundario"].sum()) == PASS_SECUNDARIO_EVENTS[game]
    consumidas = {int(s.split(",")[1]) for s in gab["source_rows"] if "," in s}
    consumidas_true = int(crus.set_index("row").loc[sorted(consumidas), "pass_secundario"].sum())
    assert (
        PASS_SECUNDARIO_CRU[game] - consumidas_true == PASS_SECUNDARIO_EVENTS[game]
    )
    # nenhum evento fundido conta como passe secundario
    assert not gab.loc[gab["metrica_type"] == "SET PIECE", "pass_secundario"].any()


@pytest.mark.parametrize("game", [1, 2])
def test_theft_fora_do_criterio_secundario(eventos, game):
    crus, _ = eventos(game)
    com_theft = crus[crus["metrica_subtype"].str.contains("THEFT")]
    assert len(com_theft[com_theft["metrica_type"] == "BALL LOST"]) == THEFT[game]
    assert not com_theft.loc[com_theft["metrica_type"] == "BALL LOST", "pass_secundario"].any()


@pytest.mark.parametrize("game", [1, 2, 3])
def test_fora_do_escopo_nao_perde_nada(eventos, game):
    """Todo evento cru aparece no gabarito, no escopo ou fora dele."""
    crus, gab = eventos(game)
    tipos = set(gab["type"].unique())
    assert "fora_do_escopo" in tipos
    assert tipos <= {
        "fora_do_escopo",
        "pass",
        "kickoff",
        "corner_kick",
        "throw_in",
        "free_kick",
        "goal_kick",
    }


def hash_ball_live(frames) -> str:
    """sha256 de `ball_live` na ordem de `frame`."""
    arranjo = frames.sort_values("frame")["ball_live"].to_numpy(dtype=np.uint8)
    return hashlib.sha256(arranjo.tobytes()).hexdigest()


# Valor de referencia para a Fatia 6 (plano §8.5 item 7): a tabela `frames` e o
# teto e o simulador nunca a recalcula, logo `ball_live` tem de ser identico em
# todos os niveis de degradacao. Gerado por `hash_ball_live` em 2026-10-29.
HASH_ESPERADO = {
    1: "437927c27f8f8600deb31104a8c12c6b2ec4ef53137407c40175caaf53dbb25f",
    2: "98263d3f03d61372e9129961a268bea6d9d30d4aba6e10625be21f334f90b6bf",
    3: "2b43ba7f1d84b98ab20f208148902b1d7118bea6bfb5ecc0e03c69a8fe228f7a",
}


@pytest.mark.parametrize("game", [1, 2, 3])
def test_hash_de_ball_live_estavel(jogo, game):
    """Registra o hash do teto. A Fatia 6 compara contra este valor."""
    assert hash_ball_live(jogo(game)[0]) == HASH_ESPERADO[game]


# --- config.yaml e mapeamento-eventos.yaml nao podem ser ignorados -----------


def test_config_tem_as_chaves_que_o_codigo_usa(cfg):
    assert cfg["dados"]["jogos"] == [1, 2, 3]
    assert cfg["dados"]["commit"] == "e706dd506b360d69d9d123d5b8026e7294b13996"
    assert cfg["dados"]["raiz"].is_dir()
    assert cfg["gabarito"]["ancorar_bola_parada_no_primeiro_quadro_vivo"] is True
    assert cfg["gabarito"]["fundir_set_piece_com_execucao"] is True
    assert cfg["gabarito"]["guarda_ancora_s"] == 10.0


def test_guarda_ancora_de_config_e_usada(cfg, eventos, jogo):
    """Falha se `gabarito.guarda_ancora_s` for ignorada.

    Com guarda de 0 s nenhuma ancoragem sobrevive; com 1e6 s todas sobrevivem.
    """
    from src import gabarito

    crus, _ = eventos(1)
    frames = jogo(1)[0]
    frouxa = dict(cfg, gabarito=dict(cfg["gabarito"], guarda_ancora_s=1e6))
    apertada = dict(cfg, gabarito=dict(cfg["gabarito"], guarda_ancora_s=0.0))
    n_frouxa = int(gabarito.construir_gabarito(1, crus, frames, frouxa)["no_dead_ball_before"].sum())
    n_padrao = int(eventos(1)[1]["no_dead_ball_before"].sum())
    n_apertada = int(
        gabarito.construir_gabarito(1, crus, frames, apertada)["no_dead_ball_before"].sum()
    )
    assert n_frouxa == 1  # guarda infinita: so o quadro 1, como antes do G3
    assert n_padrao == 10  # guarda de 10 s: + 9 cortados no jogo 1
    assert n_apertada > n_padrao  # guarda de 0 s: nenhuma ancoragem sobrevive


def test_flags_do_gabarito_sao_respeitadas(cfg, eventos, jogo):
    """Falha se as chaves `gabarito.*` de config.yaml forem ignoradas."""
    from src import gabarito

    crus, _ = eventos(1)
    for chave in ("fundir_set_piece_com_execucao", "ancorar_bola_parada_no_primeiro_quadro_vivo"):
        desligado = dict(cfg, gabarito=dict(cfg["gabarito"], **{chave: False}))
        with pytest.raises(NotImplementedError):
            gabarito.construir_gabarito(1, crus, jogo(1)[0], desligado)


def test_mapeamento_sem_subtipo_estoura(cfg, mapeamento):
    """Falha se o YAML de mapeamento for ignorado (lista de subtipos vazia)."""
    from src import gabarito

    vazio = dict(mapeamento, subtipos_conhecidos=[])
    with pytest.raises(ValueError, match="subtipos_conhecidos"):
        gabarito.carregar_eventos_crus(1, cfg, vazio)


def test_cli_exige_inspect():
    from src.run import main

    with pytest.raises(SystemExit):
        main([])


def test_cli_inspect_imprime_as_contagens(capsys, cfg, mapeamento):
    """Plano §8.6: a saida do --inspect e a conferencia manual."""
    from src.run import inspecionar

    inspecionar(cfg, mapeamento, [1])
    saida = capsys.readouterr().out
    assert "quadros: 145006" in saida
    assert "56755 quadros (39.14 %)" in saida
    assert "22 jogadores: 145000 quadros" in saida
    assert "PASS             799" in saida

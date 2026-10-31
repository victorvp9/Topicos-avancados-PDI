"""Zonas de posse e duelo, dono unico e varredura de `R_pz`/`R_dz`.

Criterios e CAMINHO de cada teste: docs/fatias/03-plano.md §9.1. A coluna
"caminho" do plano e obrigatoria: o teste do dono mais proximo roda com dois
candidatos a distancias DIFERENTES e com o `player_id` menor no candidato
ERRADO, que e o caminho em que "o primeiro da PZ" daria outra resposta.

`cenario` e `posse_real` sao fixtures de `tests/conftest.py`.

O tempo de parede por jogo e por `R_pz` (§9.6) nao e teste: sai em
`python -m src.run --posse`, que e onde o plano manda reportar sem travar.
"""

import copy

import numpy as np
import pytest

from src import possession, run

# Bola andando em linha reta com velocidade variavel: a variacao garante
# `mudou_velocidade`, logo a sequencia sobrevive ao filtro de falso-positivo do
# §2.3.3 e o teste mede a ZONA, nao o ganho.
BOLA_RETA = [(0.0, 0.0), (0.3, 0.0), (0.4, 0.0), (0.8, 0.0)]


def _sombra(desloc_y, bola=BOLA_RETA):
    """Jogador que acompanha a bola a `desloc_y` metros dela, em y."""
    return [(x, y + desloc_y) for x, y in bola]


# --- sintetico ---------------------------------------------------------------

def test_bola_a_04_m_tem_posse_com_r_pz_05(cenario):
    frames, tracking, c = cenario(BOLA_RETA, {"p1": ("home", _sombra(0.4))}, r_pz_m=0.50)
    control = possession.calcular(frames, tracking, c)["control"]
    assert len(control) == 4
    assert set(control["ball_control"]) == {"possession"}
    assert set(control["owner_id"]) == {"p1"}
    assert control["d_owner_m"].to_numpy() == pytest.approx(0.4)


def test_bola_a_04_m_nao_tem_posse_com_r_pz_025(cenario):
    frames, tracking, c = cenario(BOLA_RETA, {"p1": ("home", _sombra(0.4))}, r_pz_m=0.25)
    resultado = possession.calcular(frames, tracking, c)
    assert resultado["control"].empty
    assert resultado["contagens"]["no_possession"] == 4


def test_duelo_prevalece_sobre_posse(cenario):
    """Um jogador com a bola na PZ e um ADVERSARIO na DZ -> duelo, sem dono."""
    frames, tracking, c = cenario(
        BOLA_RETA,
        {"p1": ("home", _sombra(0.4)), "p2": ("away", _sombra(-0.9))},
        r_pz_m=0.50, r_dz_m=1.00,
    )
    resultado = possession.calcular(frames, tracking, c)
    control = resultado["control"]
    assert set(control["ball_control"]) == {"duel"}
    assert control["owner_id"].isna().all()
    assert control["d_owner_m"].isna().all()
    assert resultado["contagens"]["possession"] == 0
    assert resultado["contagens"]["duel"] == 4


def test_duelo_exige_um_jogador_de_cada_time(cenario):
    """Dois do MESMO time dentro de `R_dz` nao formam duelo (lacuna 2)."""
    frames, tracking, c = cenario(
        BOLA_RETA,
        {"p1": ("home", _sombra(0.4)), "p2": ("home", _sombra(-0.9))},
        r_pz_m=0.50, r_dz_m=1.00,
    )
    control = possession.calcular(frames, tracking, c)["control"]
    assert set(control["ball_control"]) == {"possession"}
    assert set(control["owner_id"]) == {"p1"}


def test_dono_e_o_mais_proximo_com_dois_candidatos(cenario):
    """Candidatos a 0,3 e 0,4 m: o dono e o de 0,3 m (lacuna 1).

    O candidato ERRADO (0,4 m) tem o `player_id` MENOR, de proposito: assim o
    caminho divide "o mais proximo" de "o primeiro da lista", que e a
    implementacao errada mais provavel.
    """
    frames, tracking, c = cenario(
        BOLA_RETA,
        {"p01": ("home", _sombra(0.4)), "p02": ("home", _sombra(0.3))},
        r_pz_m=0.50,
    )
    control = possession.calcular(frames, tracking, c)["control"]
    assert set(control["owner_id"]) == {"p02"}
    assert control["d_owner_m"].to_numpy() == pytest.approx(0.3)


def test_empate_exato_fica_com_o_player_id_menor(cenario):
    """Dois candidatos a 0,3 m exatos: vence o `player_id` menor, e conta-se."""
    frames, tracking, c = cenario(
        BOLA_RETA,
        {"p01": ("home", _sombra(0.3)), "p02": ("home", _sombra(-0.3))},
        r_pz_m=0.50,
    )
    resultado = possession.calcular(frames, tracking, c)
    assert set(resultado["control"]["owner_id"]) == {"p01"}
    assert resultado["contagens"]["empates_distancia"] == 4
    assert resultado["contagens"]["empates_distancia_em_posse"] == 4


@pytest.mark.parametrize("tolerancia, esperado", [(1.0e-9, 0), (1.0e-3, 4)])
def test_tolerancia_de_empate_e_o_valor_do_config(cenario, tolerancia, esperado):
    """Com os candidatos a 0,3 e 0,3 + 1e-6 m, o VALOR da tolerancia decide."""
    frames, tracking, c = cenario(
        BOLA_RETA,
        {"p01": ("home", _sombra(0.3)), "p02": ("home", _sombra(-(0.3 + 1e-6)))},
        r_pz_m=0.50, empate_distancia_m=tolerancia,
    )
    assert possession.calcular(frames, tracking, c)["contagens"]["empates_distancia"] == esperado


@pytest.mark.parametrize(
    "nome, bola",
    [
        ("tudo morto", [(np.nan, np.nan)] * 5),
        ("um quadro vivo", [(0.0, 0.0)]),
        ("vivo sem ninguem perto", [(10.0, 10.0), (10.5, 10.0), (11.0, 10.0)]),
    ],
)
def test_entrada_degenerada_nao_estoura(cenario, nome, bola):
    """Corrida sem posse nenhuma, jogo de um quadro e jogo todo morto.

    Nao e capricho: a Fatia 7 degrada a visibilidade e a Fatia 8 roda 240
    combinacoes, logo estes casos vao aparecer. Tudo vazio, sem excecao.
    """
    frames, tracking, c = cenario(bola, {"pa": ("home", [(0, 0)] * len(bola))})
    resultado = possession.calcular(frames, tracking, c)
    assert resultado["control"].empty and resultado["perdas"].empty
    assert resultado["ganhos"].empty
    assert resultado["contagens"]["n_quadros"] == len(bola)


def test_politica_de_r_dz_desconhecida_estoura(cenario):
    frames, tracking, c = cenario(BOLA_RETA, {"p1": ("home", _sombra(0.4))},
                                  r_dz_politica="o_que_eu_achar_melhor")
    with pytest.raises(ValueError, match="r_dz_politica"):
        possession.calcular(frames, tracking, c)


# --- dado real ---------------------------------------------------------------

@pytest.mark.parametrize("game", [1, 2, 3])
def test_soma_das_classes_fecha_exato(jogo, posse_real, game):
    """possession + duel + no_possession + dead_ball = total, EXATO.

    A serie e derivada de `frames` + `control` (plano §5), nao de uma terceira
    tabela: `no_possession` sai dos quadros vivos que NAO estao em `control`.
    """
    frames = jogo(game)[0]
    resultado = posse_real(game)
    control = resultado["control"]
    k = resultado["contagens"]

    vivos = set(frames.loc[frames["ball_live"], "frame"])
    com_controle = set(control["frame"])
    assert com_controle <= vivos
    morto = int((~frames["ball_live"]).sum())
    posse = int((control["ball_control"] == possession.POSSESSION).sum())
    duelo = int((control["ball_control"] == possession.DUEL).sum())
    sem_posse = len(vivos - com_controle)
    assert morto + posse + duelo + sem_posse == len(frames)
    assert (k["dead_ball"], k["possession"], k["duel"], k["no_possession"]) == (
        morto, posse, duelo, sem_posse
    )


@pytest.mark.parametrize("game", [1, 2, 3])
def test_nenhum_quadro_com_dois_donos(posse_real, game):
    control = posse_real(game)["control"]
    assert not control["frame"].duplicated().any()


@pytest.mark.parametrize("game", [1, 2, 3])
def test_bola_morta_nunca_tem_posse(jogo, posse_real, game):
    frames = jogo(game)[0]
    control = posse_real(game)["control"]
    vivo = frames.set_index("frame")["ball_live"]
    assert bool(vivo.reindex(control["frame"]).all())
    assert control["run_id"].min() >= 1


def test_r_pz_varrido_muda_a_saida(posse_real, cfg):
    """nº de control frames estritamente crescente nos 8 valores da grade de D3.

    `R_dz` acompanha por D3, pela politica padrao: e a varredura principal.
    """
    contagem = [
        posse_real(1, r_pz_m=r)["contagens"]["control_frames"]
        for r in cfg["posse"]["grade_r_pz_m"]
    ]
    assert all(a < b for a, b in zip(contagem, contagem[1:])), contagem


def test_r_dz_varrido_muda_a_saida(posse_real, cfg):
    """nº de duelos estritamente crescente em `R_dz`, com `R_pz` fixo.

    Com `R_pz` = 0,50 m e a politica padrao, `R_dz` efetivo = `r_dz_m` para todo
    valor da grade (todos >= 1,0 m), logo varrer `r_dz_m` varre `R_dz`.
    """
    raios = [r for r in cfg["posse"]["grade_r_pz_m"] if r >= cfg["posse"]["r_dz_m"]]
    contagem = [posse_real(1, r_dz_m=r)["contagens"]["duel"] for r in raios]
    assert all(a < b for a, b in zip(contagem, contagem[1:])), (raios, contagem)


@pytest.mark.parametrize("game", [1, 2, 3])
@pytest.mark.parametrize("r_pz", [1.50, 3.00])
def test_ganhos_nao_dependem_de_r_dz(posse_real, game, r_pz):
    """O passo de GANHO e independente de `R_dz`, nos 3 jogos e acima de 1 m.

    Depois da revisao de 2026-10-31 a sequencia e definida por `dono` -- o mais
    proximo com a bola na PZ --, e `dono` sai de `d <= R_pz` apenas. O `R_dz` nao
    entra em ponto nenhum do §2.3.3: ele decide o rotulo `ball_control`, e por
    essa via as perdas e os control frames, mas nao a sequencia.

    Consequencia: o efeito de `R_dz` sobre os ganhos e EXATAMENTE zero, e o
    confundimento que a politica `fixo_1m` existia para desconfundir nao existe
    nos ganhos. A asercao e de tabela IDENTICA, nao de contagem igual.
    """
    acompanha = posse_real(game, r_pz_m=r_pz)
    fixo = posse_real(game, r_pz_m=r_pz, r_dz_politica="fixo_1m")
    assert acompanha["contagens"]["r_dz_m"] != fixo["contagens"]["r_dz_m"]
    assert acompanha["ganhos"].equals(fixo["ganhos"])
    assert acompanha["sequencias"].equals(fixo["sequencias"])
    # ... e o resto do passo de posse DEPENDE de `R_dz`, senao a asercao acima
    # seria vacua (a politica poderia estar sendo ignorada).
    assert acompanha["contagens"]["duel"] != fixo["contagens"]["duel"]
    assert acompanha["contagens"]["perdas"] != fixo["contagens"]["perdas"]


def test_valor_de_percentis_do_relatorio_e_usado(cfg):
    """A linha de percentis do relatorio sai de `relatorio.percentis`.

    Mata o mutante que fixa a tupla no codigo: com `[50]` a linha tem UM
    percentil, nao cinco.
    """
    valores = np.arange(100.0)
    assert run._percentis(valores, cfg).count("p") == len(cfg["relatorio"]["percentis"])
    so_mediana = copy.deepcopy(cfg)
    so_mediana["relatorio"]["percentis"] = [50]
    linha = run._percentis(valores, so_mediana)
    assert linha.count("p") == 1 and linha.startswith("p50") and "49.5000" in linha


def test_politicas_de_r_dz_divergem_so_acima_de_1_m(posse_real, cfg):
    """`acompanha_r_pz` e `fixo_1m` sao identicas para `R_pz` <= 1,00 m e
    diferentes acima disso.

    E o teste que sustenta a desconfundicao: so com `R_dz` parado se separa o
    efeito de aumentar `R_pz` do efeito de arrastar o `R_dz` junto, e o duelo
    prevalece sobre a posse.
    """
    base = cfg["posse"]["r_dz_m"]
    chaves = ("possession", "duel", "perdas")
    for r_pz in cfg["posse"]["grade_r_pz_m"]:
        acompanha = posse_real(1, r_pz_m=r_pz)
        fixo = posse_real(1, r_pz_m=r_pz, r_dz_politica="fixo_1m")
        assert acompanha["contagens"]["r_dz_m"] == max(base, r_pz)
        assert fixo["contagens"]["r_dz_m"] == base
        iguais = {k: acompanha["contagens"][k] == fixo["contagens"][k] for k in chaves}
        if r_pz <= base:
            assert all(iguais.values()), (r_pz, acompanha, fixo)
        else:
            assert not any(iguais.values()), (r_pz, acompanha, fixo)
        # Os GANHOS ficam de fora da comparacao de proposito: depois da revisao
        # de 2026-10-31 a sequencia e definida por `dono`, que depende so de
        # `R_pz` -- logo a tabela de ganhos e IDENTICA nas duas politicas, em
        # todo raio. E a desconfundicao que o orquestrador queria: o ganho passa
        # a medir `R_pz` e nada mais.
        assert acompanha["ganhos"].equals(fixo["ganhos"]), r_pz

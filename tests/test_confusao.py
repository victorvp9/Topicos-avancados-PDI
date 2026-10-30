"""Testes da matriz de confusao: uma por grupo, com `free_kick?` a parte.

Criterios de aceite: docs/fatias/02-plano.md §9.2. As duas identidades (toda
linha soma a contagem do gabarito, toda coluna soma a de deteccoes) sao a
checagem de que nada foi perdido nem inventado.
"""

import numpy as np
import pandas as pd
import pytest

from src import evaluate

JOGOS = (1, 2, 3)


@pytest.fixture(scope="module")
def gab(eventos):
    return pd.concat([eventos(g)[1] for g in JOGOS], ignore_index=True)


@pytest.fixture(scope="module")
def perturbado(gab, cfg):
    """Deteccoes perturbadas de proposito, para a matriz ter celula fora da
    diagonal, linha `none` e coluna `none`: deslocamento de 0,5 s, um em cada 5
    rotulado `free_kick?`, uma em cada 7 descartada, uma em cada 11 duplicada."""
    det = evaluate.deteccoes_do_gabarito(gab, "frame", cfg)
    det = det.assign(t=det["t"] + 0.5, frame=det["frame"] + 13)
    bola_parada = det["type"].isin(cfg["avaliacao"]["grupos"]["bola_parada"])
    posicao = np.arange(len(det))
    det.loc[bola_parada & (posicao % 5 == 0), "type"] = "free_kick?"
    det = pd.concat(
        [det[posicao % 7 != 0], det[posicao % 11 == 0]], ignore_index=True
    ).astype(evaluate.DETECTIONS)
    return evaluate.avaliar(gab, det, cfg)


def _chaves(conf):
    return sorted(set(map(tuple, conf[["criterio", "ancora", "grupo", "game"]].to_numpy())))


def test_toda_linha_soma_a_contagem_do_gabarito(perturbado, cfg):
    res, conf = perturbado
    for criterio, ancora, grupo, game in _chaves(conf):
        tipos = cfg["avaliacao"]["grupos"][grupo]
        bloco = conf[
            (conf["criterio"] == criterio)
            & (conf["ancora"] == ancora)
            & (conf["grupo"] == grupo)
            & (conf["game"] == game)
        ]
        linhas = bloco.groupby("type_gabarito", sort=True)["n"].sum()
        esperado = (
            res[
                (res["criterio"] == criterio)
                & (res["ancora"] == ancora)
                & (res["game"] == game)
                & res["type"].isin(tipos)
            ]
            .set_index("type")["n_gabarito"]
        )
        for tipo in tipos:
            assert int(linhas.get(tipo, 0)) == int(esperado[tipo]), (criterio, grupo, game, tipo)


def test_toda_coluna_soma_a_contagem_de_deteccoes(perturbado, cfg):
    res, conf = perturbado
    for criterio, ancora, grupo, game in _chaves(conf):
        tipos = cfg["avaliacao"]["grupos"][grupo]
        bloco = conf[
            (conf["criterio"] == criterio)
            & (conf["ancora"] == ancora)
            & (conf["grupo"] == grupo)
            & (conf["game"] == game)
        ]
        colunas = bloco.groupby("type_detectado", sort=True)["n"].sum()
        esperado = (
            res[
                (res["criterio"] == criterio)
                & (res["ancora"] == ancora)
                & (res["game"] == game)
                & res["type"].isin(tipos)
            ]
            .set_index("type")["n_detectado"]
        )
        for tipo in tipos:
            assert int(colunas.get(tipo, 0)) == int(esperado[tipo]), (criterio, grupo, game, tipo)


def test_grupos_saem_em_matrizes_distintas(perturbado, cfg):
    """Como no S2, p. 3: uma matriz por grupo. Nenhuma celula cruza grupo."""
    _, conf = perturbado
    assert set(conf["grupo"]) == set(cfg["avaliacao"]["grupos"])
    for grupo, tipos in cfg["avaliacao"]["grupos"].items():
        bloco = conf[conf["grupo"] == grupo]
        permitidos = set(tipos) | {evaluate.NONE}
        assert set(bloco["type_gabarito"]) <= permitidos, grupo
        assert set(bloco["type_detectado"]) <= permitidos, grupo


def test_matriz_tem_celula_fora_da_diagonal_so_no_vidal_codina(perturbado):
    """Prova que a matriz nao e vacuamente diagonal e que casar por tipo
    (estrito, mills) impede a celula fora da diagonal entre dois tipos reais."""
    _, conf = perturbado
    fora = conf[
        (conf["type_gabarito"] != conf["type_detectado"])
        & (conf["type_gabarito"] != evaluate.NONE)
        & (conf["type_detectado"] != evaluate.NONE)
    ]
    assert set(fora["criterio"]) == {"vidal_codina"}
    assert int(fora["n"].sum()) > 0


def test_free_kick_interrogacao_nunca_e_somado_em_free_kick(cfg):
    """`free_kick?` e categoria de primeira classe (S2, p. 3, Fig. S1, p. 2)."""
    gab = pd.DataFrame(
        {
            "game": [1],
            "period": [1],
            "frame": [1000],
            "t": [40.0],
            "type": ["free_kick"],
            "team": ["home"],
            "player_id": ["g1_home_7"],
            "annotated_frame": [1000],
        }
    )
    det = (
        pd.DataFrame(
            {
                "game": [1],
                "period": [1],
                "frame": [1000],
                "t": [40.0],
                "type": ["free_kick?"],
                "team": ["home"],
                "player_id": ["g1_home_7"],
            }
        )
        .astype(evaluate.DETECTIONS)
    )
    res, conf = evaluate.avaliar(gab, det, cfg)
    res = res[(res["ancora"] == "frame") & (res["game"] == 0)].set_index(["criterio", "type"])
    for criterio in cfg["avaliacao"]["criterios"]:
        assert res.loc[(criterio, "free_kick"), "n_detectado"] == 0, criterio
        assert res.loc[(criterio, "free_kick?"), "n_detectado"] == 1, criterio
        assert res.loc[(criterio, "free_kick"), "n_gabarito"] == 1, criterio
        assert res.loc[(criterio, "free_kick?"), "n_gabarito"] == 0, criterio
    # casando por tipo, `free_kick?` nao e `free_kick`: nao casa.
    assert res.loc[("estrito", "free_kick"), "tp"] == 0
    assert res.loc[("mills", "free_kick"), "tp"] == 0
    # no vidal_codina casa (tipo nao e condicao) e a confusao fica visivel.
    assert res.loc[("vidal_codina", "free_kick"), "tp"] == 1
    cel = conf[(conf["criterio"] == "vidal_codina") & (conf["ancora"] == "frame")]
    assert cel.set_index(["type_gabarito", "type_detectado"])["n"].to_dict() == {
        ("free_kick", "free_kick?"): 1
    }


def test_celulas_nao_negativas_e_sem_duplicata(perturbado):
    _, conf = perturbado
    assert (conf["n"] > 0).all()
    chaves = ["criterio", "ancora", "grupo", "game", "type_gabarito", "type_detectado"]
    assert not conf.duplicated(chaves).any()
    assert ((conf["type_gabarito"] == evaluate.NONE) & (conf["type_detectado"] == evaluate.NONE)).sum() == 0

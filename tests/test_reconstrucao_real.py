"""Testes da reconstrucao nos dados reais (plano 07 §6: T3, T10, T12, e as
regras do contrato no B8). Nenhum teste aqui roda o detector nem calcula F1."""

import numpy as np
import pandas as pd
import pytest

from src import broadcast, reconstruct, run

JOGOS = (1, 2, 3)


@pytest.mark.parametrize("game", JOGOS)
def test_t3_teto_reconstruido_e_o_teto_bit_a_bit(jogo, game):
    _, tr, _ = jogo(game)
    rec, cont = reconstruct.reconstruir(tr, tr[reconstruct.CHAVES])
    pd.testing.assert_frame_equal(rec, tr, check_exact=True, check_index_type=True)
    assert cont["n_imputadas"] == cont["n_sem_ancora"] == 0


@pytest.mark.parametrize("variante", ["B", "A"])
def test_t3_nivel_1_reconstruido_e_o_teto(jogo, cfg, variante):
    fr, tr, _ = jogo(1)
    rec, _, _ = run.reconstruir_nivel(tr, fr, cfg, variante, 1, 0)
    pd.testing.assert_frame_equal(rec, tr, check_exact=True, check_index_type=True)


def test_contrato_no_b8(jogo, cfg):
    fr, tr, _ = jogo(1)
    deg = broadcast.degradar(tr, fr, cfg, "B", 8, 0)
    rec, cont = reconstruct.reconstruir(deg, tr[reconstruct.CHAVES])
    assert not rec[["x", "y"]].isna().to_numpy().any()
    pd.testing.assert_frame_equal(rec.loc[deg.index], deg, check_exact=True)
    assert int((~rec["visible"]).sum()) == cont["n_imputadas"] == len(rec) - len(deg)
    assert len(rec) + cont["n_sem_ancora"] == len(tr)
    assert rec.index.is_monotonic_increasing


def test_t10_erro_cresce_com_o_buraco_b8_sem_gk(jogo, cfg):
    """Se falhar, NAO afrouxar: parar e reportar (plano 07 §6, T10)."""
    faixas, d2s = [], []
    for g in JOGOS:
        fr, tr, _ = jogo(g)
        rec, _, info = run.reconstruir_nivel(tr, fr, cfg, "B", 8, 0)
        gk = tr["is_gk"].to_numpy()
        faixas.append(run.faixa_buraco(info, cfg)[~gk])
        d2s.append(run.erro2(tr, rec, info)[~gk])
    tab = run.tabela_buraco(np.concatenate(faixas), np.concatenate(d2s), cfg)
    interno = tab[tab["faixa"] != "borda"]
    assert len(interno) == len(cfg["reconstrucao"]["faixas_buraco_s"]) + 1
    assert (interno["n"] > 0).all()
    assert (np.diff(interno["rmse_m"].to_numpy()) > 0).all()


def test_t12_semente_efetiva_em_toda_linha_do_csv(cfg, mapeamento, tmp_path):
    destino = tmp_path / "reconstrucao.csv"
    run.rodar_reconstrucao(cfg, mapeamento, [1], gravar_em=destino, niveis=[("B", 8)])
    csv = pd.read_csv(destino)
    assert len(csv) == 2 * len(run.GRUPOS_GK)            # jogo 1 e o agregado (jogo 0)
    assert (csv["rep"] == 0).all()
    assert (csv["semente_efetiva"] == str(broadcast.semente_efetiva(cfg, 1, 0))).all()

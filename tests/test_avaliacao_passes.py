"""Avaliacao dos passes. Criterios e CAMINHO: docs/fatias/05-plano.md §7.2.

Os numeros exatos sao o CONTRATO do plano §2 (medidos pelo orquestrador em
2026-11-04, antes de existir detector de passe): igualdade exata, sem banda.
"""

import copy

import numpy as np
import pandas as pd
import pytest

from src import evaluate, run
from src.events import bola_parada, passes
from src.io import schema

JOGOS = (1, 2, 3)
# Plano 05 §2.1.
PRINCIPAL = {1: 722, 2: 889, 3: 1039}
SECUNDARIO = {1: 987, 2: 1115, 3: 1347}
# Plano 05 §2.2: teto de `tp_diag` contra qualquer subconjunto das perdas.
TETO_ESTRITO = 2353
TETO_VIDAL_CODINA = 2430
# Plano 05 §2.3 (decisoes.md, 2026-11-04): bola parada nao pode mudar.
BOLA_PARADA = {"deteccoes": 481, "tp_diag": 232, "f1": 0.5979}
# Decomposicao dos FN do principal estrito por causa, por jogo. Pedido da
# revisao da Fatia 5 (2026-11-04): o mutante que troca os rotulos b e c
# sobrevivia ao teste que so conferia a soma.
DECOMPOSICAO = {
    1: {"a": 60, "b": 45, "c": 6, "d": 0},
    2: {"a": 90, "b": 51, "c": 7, "d": 0},
    3: {"a": 147, "b": 48, "c": 9, "d": 0},
}


def _eventos(eventos):
    return pd.concat([eventos(g)[1] for g in JOGOS], ignore_index=True)


def _passes(passes_real, **posse):
    return pd.concat([passes_real(g, **posse)[0] for g in JOGOS], ignore_index=True)


def _linha(res, criterio, game=0, ancora="frame", tipo="pass"):
    return res[(res["criterio"] == criterio) & (res["ancora"] == ancora)
               & (res["game"] == game) & (res["type"] == tipo)].iloc[0]


# --- sinteticos ---------------------------------------------------------------


def _gabarito(linhas):
    """EVENTS minimo: [(quadro, metrica_type, player_id), ...]; `PASS` e passe."""
    return pd.DataFrame(
        [
            {"game": 1, "period": 1, "frame": f, "t": f / 25,
             "type": "pass" if m == "PASS" else "fora_do_escopo", "team": "home",
             "player_id": p, "annotated_frame": f, "anchor_shift": 0,
             "no_dead_ball_before": False, "pass_secundario": True,
             "metrica_type": m, "metrica_subtype": "", "source_rows": str(i)}
            for i, (f, m, p) in enumerate(linhas)
        ]
    ).astype(schema.EVENTS)


def _passe(frame, player, desfecho, t=None):
    return pd.DataFrame(
        [{"game": 1, "period": 1, "frame": frame, "t": frame / 25 if t is None else t,
          "type": "pass", "team": "home", "player_id": player, "run_id": 1,
          "e_bola_parada": False, "desfecho": desfecho, "receptor_id": "",
          "recepcao_em_duelo": False, "de_lacuna_5": False}]
    ).astype(passes.PASSES)


def test_principal_usa_so_completo(cfg):
    """Sintetico: passe `interceptado` no instante e jogador CERTOS de um `PASS`
    -> nao casa no principal, casa no secundario."""
    gab = _gabarito([(1000, "PASS", "a")])
    p = _passe(1000, "a", "interceptado")
    res_p, _ = evaluate.avaliar(gab, passes.para_casador(p, so_completo=True), cfg)
    res_s, _ = evaluate.avaliar(evaluate.gabarito_secundario(gab, cfg),
                                passes.para_casador(p), cfg)
    for criterio in cfg["avaliacao"]["criterios"]:
        assert _linha(res_p, criterio)["tp_diag"] == 0
        assert _linha(res_s, criterio)["tp_diag"] == 1


def test_ball_lost_entra_no_secundario_como_passe(cfg):
    """`BALL LOST` com `pass_secundario` vira `pass` no secundario."""
    gab = _gabarito([(1000, "PASS", "a"), (2000, "BALL LOST", "a")])
    sec = evaluate.gabarito_secundario(gab, cfg)
    assert sec["type"].tolist() == ["pass", "pass"]
    assert gab["type"].tolist() == ["pass", "fora_do_escopo"]   # nao mutou


def test_passe_com_t_nan_nao_casa_e_nao_some(cfg):
    """Sintetico: passe com `t` NaN no jogador e quadro certos nao casa, e
    continua no denominador de precisao; o `PASS` continua no de revocacao."""
    gab = _gabarito([(1000, "PASS", "a")])
    p = _passe(1000, "a", "completo", t=np.nan)
    res, _ = evaluate.avaliar(gab, passes.para_casador(p, so_completo=True), cfg)
    for criterio in cfg["avaliacao"]["criterios"]:
        linha = _linha(res, criterio)
        assert (linha["tp_diag"], linha["n_detectado"], linha["n_gabarito"]) == (0, 1, 1)


@pytest.mark.parametrize("valor", ["events", "cruas"])
def test_valor_antigo_da_chave_estoura(cfg, valor):
    """`denominador_passe_secundario: events` (o valor antigo) estoura, no
    gabarito secundario E no `avaliar`: nao ha caminho para o numero velho."""
    cfg_alt = copy.deepcopy(cfg)
    cfg_alt["avaliacao"]["denominador_passe_secundario"] = valor
    gab = _gabarito([(1000, "PASS", "a")])
    with pytest.raises(NotImplementedError):
        evaluate.gabarito_secundario(gab, cfg_alt)
    with pytest.raises(NotImplementedError):
        evaluate.avaliar(gab, passes.para_casador(_passe(1000, "a", "completo")), cfg_alt)


# --- dado real ----------------------------------------------------------------


def test_denominadores_exatos(eventos, cfg):
    ev = _eventos(eventos)
    sec = evaluate.gabarito_secundario(ev, cfg)
    vazio = pd.DataFrame({c: pd.Series(dtype=t) for c, t in evaluate.DETECTIONS.items()})
    res_p, _ = evaluate.avaliar(ev, vazio, cfg)
    res_s, _ = evaluate.avaliar(sec, vazio, cfg)
    for g in JOGOS:
        assert int((ev[ev["game"] == g]["type"] == "pass").sum()) == PRINCIPAL[g]
        assert int((sec["game"] == g).sum()) == SECUNDARIO[g]
        assert _linha(res_p, "estrito", g)["n_gabarito"] == PRINCIPAL[g]
        assert _linha(res_s, "estrito", g)["n_gabarito"] == SECUNDARIO[g]


def test_tiro_de_meta_fora_do_secundario_e_dentro_da_bola_parada(eventos, cfg):
    """Os 49 `goal_kick` estao no grupo `bola_parada` e em nenhum denominador
    de passe; sao exatamente a diferenca 1009+1131+1358 - 3449."""
    ev = _eventos(eventos)
    tiro = ev[ev["type"] == "goal_kick"]
    assert len(tiro) == 49
    assert "goal_kick" in cfg["avaliacao"]["grupos"]["bola_parada"]
    assert "goal_kick" not in cfg["avaliacao"]["grupos"]["jogo_corrido"]
    sec = evaluate.gabarito_secundario(ev, cfg)
    chave = ["game", "source_rows"]
    assert not tiro[chave].merge(sec[chave]).shape[0]
    assert int(tiro["pass_secundario"].sum()) == 49
    assert int(ev["pass_secundario"].sum()) - len(sec) == 49


def test_teto_do_plano(passes_real, eventos, cfg):
    """`tp_diag` <= 2353 (estrito) e <= 2430 (vidal_codina), no principal e no
    diagnostico (todos os passes contra `PASS`)."""
    ev = _eventos(eventos)
    p = _passes(passes_real)
    for det in (passes.para_casador(p, so_completo=True), passes.para_casador(p)):
        res, _ = evaluate.avaliar(ev, det, cfg)
        assert _linha(res, "estrito")["tp_diag"] <= TETO_ESTRITO
        assert _linha(res, "vidal_codina")["tp_diag"] <= TETO_VIDAL_CODINA


def test_evento_nao_detectado_e_perda_de_revocacao(passes_real, eventos, cfg):
    """`n_gabarito` = 2650 e 3449 em todo criterio e ancora, com deteccao vazia
    e com a real."""
    ev = _eventos(eventos)
    sec = evaluate.gabarito_secundario(ev, cfg)
    p = _passes(passes_real)
    vazio = passes.para_casador(p.iloc[:0])
    for det_p, det_s in ((vazio, vazio),
                         (passes.para_casador(p, so_completo=True), passes.para_casador(p))):
        res_p, _ = evaluate.avaliar(ev, det_p, cfg)
        res_s, _ = evaluate.avaliar(sec, det_s, cfg)
        for criterio in cfg["avaliacao"]["criterios"]:
            for ancora in cfg["avaliacao"]["ancoras"]:
                assert _linha(res_p, criterio, ancora=ancora)["n_gabarito"] == 2650
                assert _linha(res_s, criterio, ancora=ancora)["n_gabarito"] == 3449


def test_decomposicao_fecha_por_jogo(passes_real, eventos, cfg):
    """(a)+(b)+(c)+(d) = `fn` do principal estrito, EXATO, por jogo. O `fn` vem
    do `avaliar`; a decomposicao refaz o casamento por conta propria."""
    ev = _eventos(eventos)
    p = _passes(passes_real)
    res, _ = evaluate.avaliar(ev, passes.para_casador(p, so_completo=True), cfg)
    dec = run.decompor_fn(ev, p, cfg)
    assert set(dec["causa"]) <= set("abcd")
    for g in JOGOS:
        assert int((dec["game"] == g).sum()) == _linha(res, "estrito", g)["fn"]
        # A CLASSIFICACAO, nao so a soma: trocar dois rotulos preservaria a soma.
        # (a) = passes do gabarito - passes com perda a <= 1 s (Fatia 3,
        # `--tau-posse`): 722-662, 889-799, 1039-892.
        contagem = dec[dec["game"] == g]["causa"].value_counts()
        assert {c: int(contagem.get(c, 0)) for c in "abcd"} == DECOMPOSICAO[g]


def test_ancoras_iguais_para_passe(passes_real, eventos, cfg):
    """Para passe `anchor_shift = 0`: `frame` e `annotated_frame` dao o mesmo
    resultado, no principal e no secundario, em todo criterio e jogo."""
    ev = _eventos(eventos)
    p = _passes(passes_real)
    colunas = ["n_gabarito", "n_detectado", "tp_diag", "tp", "tp_det", "fp", "fn"]
    for gab, det in ((ev, passes.para_casador(p, so_completo=True)),
                     (evaluate.gabarito_secundario(ev, cfg), passes.para_casador(p))):
        res, _ = evaluate.avaliar(gab, det, cfg)
        res = res[res["type"] == "pass"]
        a = res[res["ancora"] == "frame"].set_index(["criterio", "game"])[colunas]
        b = res[res["ancora"] == "annotated_frame"].set_index(["criterio", "game"])[colunas]
        pd.testing.assert_frame_equal(a, b)


def test_sem_lacuna_5(passes_real, posse_real, jogo, cfg):
    """Refazendo a supressao SEM as perdas `so_por_lacuna_5` (e a bola parada
    com elas filtradas, como `detectar_jogos(sem_lacuna_5=True)`), o numero de
    passes cai exatamente do numero de perdas de lacuna 5 nao suprimidas."""
    for g in JOGOS:
        p, _ = passes_real(g)
        r = posse_real(g)
        frames, tracking, periods = jogo(g)
        perdas = r["perdas"][~r["perdas"]["so_por_lacuna_5"]]
        det = bola_parada.detectar(frames, tracking, periods, perdas, cfg)
        sem = passes.rotular(perdas, r["ganhos"], r["control"], frames, det)
        queda = int((p["de_lacuna_5"] & ~p["e_bola_parada"]).sum())
        assert queda > 0
        assert len(passes.para_casador(sem)) == len(passes.para_casador(p)) - queda
        # O caminho do bloco 7 de `--passes` (filtrar a tabela pronta) da as
        # MESMAS deteccoes que refazer a supressao sem as perdas.
        pd.testing.assert_frame_equal(
            passes.para_casador(p[~p["de_lacuna_5"]]), passes.para_casador(sem))


def test_bloco_9_nao_altera_os_blocos_1_a_8(cfg, mapeamento, capsys, tmp_path):
    """Dado real: `--passes` com e sem o bloco 9 exploratorio imprime blocos
    1-8 IDENTICOS e devolve as mesmas tabelas; o bloco 9 vem depois do 8 e
    traz o rotulo exigido."""
    sem = run.rodar_passes(cfg, mapeamento, JOGOS, tmp_path / "a.csv", exploratorio=False)
    saida_sem = capsys.readouterr().out.splitlines()
    com = run.rodar_passes(cfg, mapeamento, JOGOS, tmp_path / "b.csv", exploratorio=True)
    saida_com = capsys.readouterr().out.splitlines()
    fim = max(i for i, linha in enumerate(saida_sem) if linha == "=" * 78)
    assert saida_com[:fim] == saida_sem[:fim]
    assert ("  (9) EXPLORATÓRIO — decidido depois de ver o resultado; "
            "o principal não muda") in saida_com[fim:]
    for a, b in zip(sem, com):
        pd.testing.assert_frame_equal(a, b)


def test_bola_parada_intacta(passes_real, eventos, cfg):
    """481 deteccoes, `tp_diag` 232, micro F1 0,5979 (estrito, `frame`, sem
    penalty), como antes desta fatia."""
    det = pd.concat([passes_real(g)[1] for g in JOGOS], ignore_index=True)
    assert len(det) == BOLA_PARADA["deteccoes"]
    res, _ = evaluate.avaliar(_eventos(eventos), bola_parada.para_casador(det), cfg)
    bloco = res[(res["criterio"] == "estrito") & (res["ancora"] == "frame")
                & (res["game"] == 0)
                & res["type"].isin(cfg["avaliacao"]["grupos"]["bola_parada"])
                & (res["type"] != "penalty")]
    micro = evaluate.micro(bloco)
    assert micro["tp_diag"] == BOLA_PARADA["tp_diag"]
    assert round(micro["f1"], 4) == BOLA_PARADA["f1"]

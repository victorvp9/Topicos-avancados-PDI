"""Testes do casador: os tres criterios, o otimo-vs-guloso e as armadilhas.

Criterios de aceite: docs/fatias/02-plano.md §9.1 e §9.4.

As deteccoes perturbadas (deslocamento, remocao, duplicacao) usam o gabarito
real dos tres jogos; os casos construidos (borda da janela, um-para-um,
otimo-vs-guloso, NaN) usam gabarito sintetico, porque num gabarito real de 2650
passes um deslocamento de 2 s ou 30 s pode cair em cima de OUTRO evento do mesmo
jogador -- o que testaria a densidade do dado, nao o criterio.
"""

import numpy as np
import pandas as pd
import pytest

from src import evaluate

JOGOS = (1, 2, 3)
CRITERIOS = ("estrito", "vidal_codina", "mills")


@pytest.fixture(scope="module")
def gab(eventos):
    """Gabarito dos tres jogos concatenado (esquema EVENTS)."""
    return pd.concat([eventos(g)[1] for g in JOGOS], ignore_index=True)


def _gabarito(linhas, game=1, fps=25):
    """Gabarito sintetico. `linhas`: (frame, type, player_id). t = frame/fps.

    `annotated_frame = frame`: sem ancoragem, as duas ancoras coincidem.
    """
    df = pd.DataFrame(linhas, columns=["frame", "type", "player_id"])
    return df.assign(
        game=game, period=1, t=df["frame"] / fps, annotated_frame=df["frame"], team="home"
    )


def _deteccoes(linhas, game=1, fps=25, t=None):
    """Deteccoes no esquema DETECTIONS. `linhas`: (frame, type, player_id).

    `t` explicito so para o teste de borda da janela, que precisa de um `dt` que
    nao e multiplo de 1/fps.
    """
    df = pd.DataFrame(linhas, columns=["frame", "type", "player_id"])
    df = df.assign(game=game, period=1, t=df["frame"] / fps if t is None else t, team="home")
    return df[list(evaluate.DETECTIONS)].astype(evaluate.DETECTIONS)


def _celula(res, criterio, tipo, game=0, ancora="frame"):
    """A linha unica de `resultado` para (criterio, ancora, game, tipo)."""
    sel = res[
        (res["criterio"] == criterio)
        & (res["ancora"] == ancora)
        & (res["game"] == game)
        & (res["type"] == tipo)
    ]
    assert len(sel) == 1, (criterio, ancora, game, tipo, len(sel))
    return sel.iloc[0]


def _deslocar(det, segundos, fps=25):
    """Desloca toda deteccao no tempo, mantendo `frame` coerente com `t`."""
    return det.assign(
        t=det["t"] + segundos, frame=det["frame"] + round(segundos * fps)
    ).astype(evaluate.DETECTIONS)


# --- gabarito contra si mesmo -------------------------------------------------


@pytest.mark.parametrize("ancora", ["frame", "annotated_frame"])
def test_gabarito_contra_si_mesmo_da_f1_1(gab, cfg, ancora):
    """F1 = 1,0 em todos os tipos, nos tres criterios e nos tres jogos."""
    det = evaluate.deteccoes_do_gabarito(gab, ancora, cfg)
    res, _ = evaluate.avaliar(gab, det, cfg)
    res = res[(res["ancora"] == ancora) & (res["n_gabarito"] > 0)]
    # 6 tipos nos 3 jogos + agregado, mais `penalty`, que so existe no jogo 2
    assert len(res) == len(CRITERIOS) * (6 * 4 + 2)
    assert (res["f1"] == 1.0).all(), res[res["f1"] != 1.0]
    assert (res["fp"] == 0).all() and (res["fn"] == 0).all()


def test_ancora_frame_concorda_com_a_coluna_t_do_gabarito(gab, cfg):
    """A ancora `frame` reproduz `events.t` -- a conversao nao foi reinventada."""
    assert (gab["t"] == gab["frame"] / cfg["tracking"]["fps"]).all()


# --- os tres criterios sao distintos -----------------------------------------


def test_deslocado_30s_da_f1_zero(cfg):
    """F1 = 0,0 em todos os tipos e criterios (eventos espacados de 60 s)."""
    linhas = [
        (1 + 1500 * i, tipo, "g1_home_1")
        for i, tipo in enumerate(["pass", "throw_in", "corner_kick", "free_kick", "goal_kick"])
    ]
    gab = _gabarito(linhas)
    det = _deslocar(_deteccoes(linhas), 30.0)
    res, _ = evaluate.avaliar(gab, det, cfg)
    presentes = res[(res["ancora"] == "frame") & (res["n_gabarito"] > 0)]
    assert len(presentes) == len(CRITERIOS) * 5 * 2  # 5 tipos x (1 jogo + agregado)
    assert (presentes["f1"] == 0.0).all(), presentes[presentes["f1"] != 0.0]
    assert (presentes["tp"] == 0).all()


def test_deslocado_2s_separa_estrito_de_vidal_codina(cfg):
    """O teste que denuncia tres criterios implementados iguais (plano §9.1)."""
    linhas = [(1 + 1500 * i, "throw_in", "g1_home_1") for i in range(4)]
    gab = _gabarito(linhas)
    det = _deslocar(_deteccoes(linhas), 2.0)
    res, _ = evaluate.avaliar(gab, det, cfg)
    assert _celula(res, "estrito", "throw_in")["f1"] == 0.0
    assert _celula(res, "vidal_codina", "throw_in")["f1"] == 1.0
    assert _celula(res, "mills", "throw_in")["f1"] == 1.0  # janela de 3 s


@pytest.mark.parametrize("criterio,casa", [("estrito", 0.0), ("vidal_codina", 1.0), ("mills", 1.0)])
def test_deslocado_2s_por_criterio(cfg, criterio, casa):
    """Mesma perturbacao, um criterio por vez, com o passe de jogo corrido."""
    linhas = [(1 + 1500 * i, "pass", "g1_home_1") for i in range(4)]
    res, _ = evaluate.avaliar(_gabarito(linhas), _deslocar(_deteccoes(linhas), 2.0), cfg)
    assert _celula(res, criterio, "pass")["f1"] == casa


def test_borda_da_janela_e_inclusiva(cfg):
    """dt = 1,000 s casa no estrito; 1,001 s nao casa (janela inclusiva)."""
    linhas = [(1000, "pass", "g1_home_1")]
    gab = _gabarito(linhas)
    fps = cfg["tracking"]["fps"]
    for dt, esperado in [(1.0, 1), (1.001, 0), (1.04, 0)]:
        det = _deteccoes(linhas, t=[1000 / fps + dt])
        res, _ = evaluate.avaliar(gab, det, cfg)
        assert _celula(res, "estrito", "pass")["tp"] == esperado, dt


def test_jogador_errado(cfg):
    """Mesmo tipo e tempo, jogador diferente: FN+FP no estrito e no
    vidal_codina (casam por jogador); acerto no mills (nao casa)."""
    gab = _gabarito([(1000, "throw_in", "g1_home_7")])
    det = _deteccoes([(1000, "throw_in", "g1_home_9")])
    res, _ = evaluate.avaliar(gab, det, cfg)
    for criterio in ("estrito", "vidal_codina"):
        linha = _celula(res, criterio, "throw_in")
        assert (linha["tp"], linha["fp"], linha["fn"]) == (0, 1, 1), criterio
    linha = _celula(res, "mills", "throw_in")
    assert (linha["tp"], linha["fp"], linha["fn"]) == (1, 0, 0)


def test_tipo_errado(cfg):
    """Mesmo jogador e tempo, tipo diferente.

    `estrito` e `mills` casam por tipo: o par nem existe, FN + FP.
    `vidal_codina` CASA o par (ignora o tipo) e a confusao aparece na celula
    (anotado, detectado) -- mas o par NAO conta como acerto na metrica, porque
    o numerador e `tp_diag`, a diagonal. Esta e a correcao da revisao da Fatia 2:
    com `tp` como numerador, um detector que erra todos os tipos reportaria
    F1 = 1,00.
    """
    gab = _gabarito([(1000, "throw_in", "g1_home_7")])
    det = _deteccoes([(1000, "corner_kick", "g1_home_7")])
    res, conf = evaluate.avaliar(gab, det, cfg)
    for criterio in ("estrito", "mills"):
        anotado = _celula(res, criterio, "throw_in")
        detectado = _celula(res, criterio, "corner_kick")
        assert (anotado["tp"], anotado["tp_diag"], anotado["fn"]) == (0, 0, 1), criterio
        assert (detectado["tp_det"], detectado["tp_diag"], detectado["fp"]) == (0, 0, 1), criterio

    anotado = _celula(res, "vidal_codina", "throw_in")
    detectado = _celula(res, "vidal_codina", "corner_kick")
    assert anotado["tp"] == 1  # o par existe: casou
    assert anotado["tp_diag"] == 0  # mas nao esta na diagonal
    assert (anotado["fn"], anotado["revocacao"]) == (1, 0.0)
    # precisao de throw_in e indefinida (0 deteccoes do tipo), logo F1 tambem:
    # `NaN` com denominador zero, nunca 0,0.
    assert np.isnan(anotado["precisao"]) and np.isnan(anotado["f1"])
    assert (detectado["tp_det"], detectado["tp_diag"], detectado["fp"]) == (1, 0, 1)
    # O NUMERADOR de `precisao` e `tp_diag`, nao `tp_det` (revisao, item 2):
    assert detectado["precisao"] == 0.0
    # e a revocacao de corner_kick e indefinida (0 anotados do tipo)
    assert np.isnan(detectado["revocacao"]) and np.isnan(detectado["f1"])
    cel = conf[(conf["criterio"] == "vidal_codina") & (conf["ancora"] == "frame")]
    cel = cel[cel["game"] == 1]
    assert cel.set_index(["type_gabarito", "type_detectado"])["n"].to_dict() == {
        ("throw_in", "corner_kick"): 1
    }


def test_todos_os_tipos_trocados_da_f1_zero(cfg):
    """TESTE OBRIGATORIO da revisao da Fatia 2, item 1.

    10 escanteios e 10 laterais anotados, detectados com os tipos TROCADOS, no
    mesmo instante e com o mesmo jogador. Um detector que erra 100 % dos tipos
    tem de dar F1 = 0,0 nas duas classes, nos TRES criterios. Com `tp` como
    numerador (o furo que a revisao achou) isto dava precisao 1,0 e revocacao
    1,0 no `vidal_codina`.
    """
    anotados, detectados = [], []
    for i in range(10):
        anotados.append((1000 + 300 * i, "corner_kick", "g1_home_7"))
        detectados.append((1000 + 300 * i, "throw_in", "g1_home_7"))
        anotados.append((1150 + 300 * i, "throw_in", "g1_home_9"))
        detectados.append((1150 + 300 * i, "corner_kick", "g1_home_9"))
    res, conf = evaluate.avaliar(_gabarito(anotados), _deteccoes(detectados), cfg)
    for criterio in CRITERIOS:
        for tipo in ("corner_kick", "throw_in"):
            linha = _celula(res, criterio, tipo)
            assert (linha["n_gabarito"], linha["n_detectado"]) == (10, 10), (criterio, tipo)
            assert linha["tp_diag"] == 0, (criterio, tipo)
            assert (linha["fp"], linha["fn"]) == (10, 10), (criterio, tipo)
            assert linha["precisao"] == 0.0 and linha["revocacao"] == 0.0, (criterio, tipo)
            assert linha["f1"] == 0.0, (criterio, tipo)
    # no vidal_codina os 20 pares existem e a confusao fica visivel na matriz
    cel = conf[
        (conf["criterio"] == "vidal_codina") & (conf["ancora"] == "frame") & (conf["game"] == 1)
    ]
    assert cel.set_index(["type_gabarito", "type_detectado"])["n"].to_dict() == {
        ("corner_kick", "throw_in"): 10,
        ("throw_in", "corner_kick"): 10,
    }
    assert int(_celula(res, "vidal_codina", "corner_kick")["tp"]) == 10  # casou, sem acertar
    # ITEM 1 DA RE-REVISAO: `micro()` e quem vai produzir o agregado do
    # relatorio da Fatia 8. Com `tp` no lugar de `tp_diag` ela devolveria
    # F1 = 1,0 aqui -- o mesmo furo, um nivel acima.
    for criterio in CRITERIOS:
        agregado = evaluate.micro(
            res[
                (res["criterio"] == criterio)
                & (res["ancora"] == "frame")
                & (res["game"] == 0)
                & res["type"].isin(["corner_kick", "throw_in"])
            ]
        )
        assert agregado["tp_diag"] == 0, criterio
        assert agregado["n_gabarito"] == 20 and agregado["n_detectado"] == 20, criterio
        assert agregado["precisao"] == 0.0 and agregado["revocacao"] == 0.0, criterio
        assert agregado["f1"] == 0.0, criterio
    # nos criterios que casam por tipo nenhum par existe: 20 FN e 20 FP soltos
    cel = conf[(conf["criterio"] == "estrito") & (conf["ancora"] == "frame")]
    assert set(cel["type_gabarito"]) | set(cel["type_detectado"]) == {
        "corner_kick",
        "throw_in",
        evaluate.NONE,
    }
    assert int(cel[cel["type_detectado"] == evaluate.NONE]["n"].sum()) == 20
    assert int(cel[cel["type_gabarito"] == evaluate.NONE]["n"].sum()) == 20


def test_tipo_errado_entre_grupos_nunca_casa(cfg):
    """DECISAO DO CODIFICADOR, nao do plano: o vidal_codina ignora o tipo, mas
    so dentro do grupo. Passe anotado x escanteio detectado nao casa."""
    gab = _gabarito([(1000, "pass", "g1_home_7")])
    det = _deteccoes([(1000, "corner_kick", "g1_home_7")])
    res, conf = evaluate.avaliar(gab, det, cfg)
    linha = _celula(res, "vidal_codina", "pass")
    assert (linha["tp"], linha["fn"]) == (0, 1)
    assert _celula(res, "vidal_codina", "corner_kick")["fp"] == 1
    grupos = set(conf[conf["criterio"] == "vidal_codina"]["grupo"])
    assert grupos == {"jogo_corrido", "bola_parada"}


# --- o casamento e otimo, um-para-um -----------------------------------------


def _guloso(gab, det, janela_s):
    """Guloso de referencia: evento anotado em ordem de tempo, cada um pega a
    deteccao livre mais proxima no tempo. E o algoritmo que o D8 dizia e que o
    plano §3 rejeita. So existe para o teste otimo-vs-guloso."""
    livres = list(range(len(det)))
    pares = 0
    for i in np.argsort(gab["t"].to_numpy(), kind="stable"):
        candidatos = [j for j in livres if abs(gab["t"].iloc[i] - det["t"].iloc[j]) <= janela_s]
        if not candidatos:
            continue
        melhor = min(candidatos, key=lambda j: abs(gab["t"].iloc[i] - det["t"].iloc[j]))
        livres.remove(melhor)
        pares += 1
    return pares


def test_otimo_casa_dois_onde_o_guloso_casa_um(cfg):
    """Caso construido do plano §3: o guloso casa 1 par, o otimo casa 2.

    Anotados A (quadro 1000, t=40,00 s) e B (1025, t=41,00 s); deteccoes
    Y (978, t=39,12 s) e X (1012, t=40,48 s). Janela do estrito = +-1 s.
    Permitidos: A-Y (0,88 s), A-X (0,48 s), B-X (0,52 s); B-Y (1,88 s) NAO.
    O guloso processa A primeiro e pega X, a mais proxima, e B fica sem par.
    O otimo casa A-Y e B-X: 2 pares, soma |dt| = 1,40 s.
    """
    gab = _gabarito([(1000, "pass", "g1_home_1"), (1025, "pass", "g1_home_1")])
    det = _deteccoes([(978, "pass", "g1_home_1"), (1012, "pass", "g1_home_1")])
    janela = cfg["avaliacao"]["criterios"]["estrito"]["janela_s"]
    assert _guloso(gab, det, janela) == 1

    gab_t = gab.assign(grupo="jogo_corrido")
    i_gab, i_det = evaluate.casar(gab_t, det.assign(grupo="jogo_corrido"), janela, True, True)
    assert len(i_gab) == 2
    assert sorted(zip(i_gab.tolist(), i_det.tolist())) == [(0, 0), (1, 1)]
    soma = float(np.abs(gab["t"].to_numpy()[i_gab] - det["t"].to_numpy()[i_det]).sum())
    assert soma == pytest.approx(1.40)

    res, _ = evaluate.avaliar(gab, det, cfg)
    assert _celula(res, "estrito", "pass")["tp"] == 2


def test_um_para_um_duas_deteccoes_para_um_anotado(cfg):
    gab = _gabarito([(1000, "pass", "g1_home_1")])
    det = _deteccoes([(1000, "pass", "g1_home_1"), (1005, "pass", "g1_home_1")])
    res, _ = evaluate.avaliar(gab, det, cfg)
    linha = _celula(res, "estrito", "pass")
    assert (linha["tp"], linha["fp"], linha["fn"]) == (1, 1, 0)


def test_um_para_um_dois_anotados_para_uma_deteccao(cfg):
    gab = _gabarito([(1000, "pass", "g1_home_1"), (1005, "pass", "g1_home_1")])
    det = _deteccoes([(1000, "pass", "g1_home_1")])
    res, _ = evaluate.avaliar(gab, det, cfg)
    linha = _celula(res, "estrito", "pass")
    assert (linha["tp"], linha["fp"], linha["fn"]) == (1, 0, 1)


def test_nenhum_par_proibido_sobrevive(cfg):
    """Risco §11.3: o custo `M` nao pode virar par casado. Aqui todos os pares
    sao proibidos por tempo, menos um; `M` e grande porque ha um |dt| grande."""
    gab = _gabarito([(1000, "pass", "g1_home_1"), (2000, "pass", "g1_home_1")])
    det = _deteccoes([(1010, "pass", "g1_home_1"), (5000, "pass", "g1_home_1")])
    i_gab, i_det = evaluate.casar(
        gab.assign(grupo="jogo_corrido"), det.assign(grupo="jogo_corrido"), 10.0, True, True
    )
    assert list(zip(i_gab.tolist(), i_det.tolist())) == [(0, 0)]


def _bloco(tempos, grupo="jogo_corrido"):
    """DataFrame minimo para `casar`: so as 5 colunas que ela le."""
    return pd.DataFrame(
        {
            "game": 1,
            "grupo": grupo,
            "type": "pass",
            "player_id": "g1_home_1",
            "t": tempos,
        }
    )


def test_M_dimensionado_para_o_otimo_lexicografico(cfg):
    """Revisao da Fatia 2, item 3: `M` tem de ser maior que a SOMA de todos os
    |dt| permitidos, nao so maior que a janela.

    Contraexemplo do revisor, janela de 1,0 s:
        gab t = [0,6; 0,0]   det t = [0,0; -0,6]
        |dt| = [[0,6  1,2],
                [0,0  0,6]]
    O casamento de cardinalidade MAXIMA (2 pares) custa 1,2, mais que o de
    cardinalidade 1 (0,0). Com `M = janela + eps` o solver prefere 1 par, e a
    maximizacao da cardinalidade -- o primeiro objetivo lexicografico -- cai.
    """
    i_gab, i_det = evaluate.casar(_bloco([0.6, 0.0]), _bloco([0.0, -0.6]), 1.0, True, True)
    assert len(i_gab) == 2, "o primeiro objetivo e MAXIMIZAR o numero de pares"
    assert sorted(zip(i_gab.tolist(), i_det.tolist())) == [(0, 0), (1, 1)]
    assert abs(0.6 - 0.0) + abs(0.0 - (-0.6)) == pytest.approx(1.2)  # pior soma, melhor n


def test_pares_devolvidos_respeitam_as_restricoes(gab, cfg):
    """Nenhum par casado viola janela, tipo, jogador ou jogo, em nenhum criterio."""
    det = evaluate.deteccoes_do_gabarito(gab, "frame", cfg)
    det = _deslocar(det, 0.6).assign(grupo=lambda d: d["type"].map(evaluate.grupo_por_tipo(cfg)))
    base = gab[gab["type"].isin(evaluate.grupo_por_tipo(cfg))].reset_index(drop=True)
    base = base.assign(grupo=base["type"].map(evaluate.grupo_por_tipo(cfg)))
    for criterio, eixos in cfg["avaliacao"]["criterios"].items():
        i_gab, i_det = evaluate.casar(
            base, det, eixos["janela_s"], eixos["casa_tipo"], eixos["casa_jogador"]
        )
        assert len(i_gab) == len(set(i_gab.tolist())) == len(set(i_det.tolist()))
        dt = np.abs(base["t"].to_numpy()[i_gab] - det["t"].to_numpy()[i_det])
        assert (dt <= eixos["janela_s"]).all(), criterio
        assert (base["game"].to_numpy()[i_gab] == det["game"].to_numpy()[i_det]).all()
        assert (base["grupo"].to_numpy()[i_gab] == det["grupo"].to_numpy()[i_det]).all()
        if eixos["casa_tipo"]:
            assert (base["type"].to_numpy()[i_gab] == det["type"].to_numpy()[i_det]).all()
        if eixos["casa_jogador"]:
            assert (
                base["player_id"].to_numpy()[i_gab] == det["player_id"].to_numpy()[i_det]
            ).all()


# --- perturbacoes do gabarito real -------------------------------------------


def test_metade_removida_da_revocacao_meio_e_precisao_um(gab, cfg):
    """Revocacao = fracao mantida por tipo (0,5 exato onde n e par);
    precisao = 1,0."""
    det = evaluate.deteccoes_do_gabarito(gab, "frame", cfg)
    ordem = det.groupby(["game", "type"], sort=False).cumcount()
    metade = det[ordem % 2 == 0].reset_index(drop=True)
    res, _ = evaluate.avaliar(gab, metade, cfg)
    res = res[(res["ancora"] == "frame") & (res["n_detectado"] > 0)]
    assert (res["precisao"] == 1.0).all(), res[res["precisao"] != 1.0]
    assert (res["revocacao"] == res["n_detectado"] / res["n_gabarito"]).all()
    # throw_in do jogo 2 tem n = 32 (par): revocacao exatamente 0,5.
    for criterio in CRITERIOS:
        linha = _celula(res, criterio, "throw_in", game=2)
        assert linha["n_gabarito"] == 32 and linha["revocacao"] == 0.5


def test_duplicadas_dao_precisao_meio_e_revocacao_um(gab, cfg):
    """Toda deteccao duplicada: precisao = 0,5 e revocacao = 1,0."""
    det = evaluate.deteccoes_do_gabarito(gab, "frame", cfg)
    dobro = pd.concat([det, det], ignore_index=True).astype(evaluate.DETECTIONS)
    res, _ = evaluate.avaliar(gab, dobro, cfg)
    res = res[(res["ancora"] == "frame") & (res["n_gabarito"] > 0)]
    assert (res["precisao"] == 0.5).all(), res[res["precisao"] != 0.5]
    assert (res["revocacao"] == 1.0).all()


def test_no_dead_ball_before_continua_no_denominador(gab, cfg):
    """Os 13 eventos com a marca ficam no denominador (decisoes.md, armadilha da
    Fatia 1). Filtra-los subiria o F1 de bola parada -- com os numeros exatos
    das DUAS agregacoes, porque "agregado" sem qualificar e ambiguo (revisao da
    Fatia 2, item 6). `penalty` fica FORA de todo agregado (n = 1)."""
    marcados = gab[gab["no_dead_ball_before"]]
    assert len(marcados) == 13
    assert marcados["type"].value_counts().to_dict() == {
        "goal_kick": 9,
        "free_kick": 3,
        "kickoff": 1,
    }

    det = evaluate.deteccoes_do_gabarito(gab[~gab["no_dead_ball_before"]], "frame", cfg)
    completo, _ = evaluate.avaliar(gab, det, cfg)
    filtrado, _ = evaluate.avaliar(gab[~gab["no_dead_ball_before"]], det, cfg)

    agregaveis = [t for t in cfg["avaliacao"]["grupos"]["bola_parada"] if t != "penalty"]

    def bola_parada(res):
        return res[
            (res["criterio"] == "estrito")
            & (res["ancora"] == "frame")
            & (res["game"] == 0)
            & res["type"].isin(agregaveis)
        ]

    com = bola_parada(completo)
    sem = bola_parada(filtrado)
    assert int(com["n_gabarito"].sum()) - int(sem["n_gabarito"].sum()) == 13
    assert int(com["fn"].sum()) == 13 and int(sem["fn"].sum()) == 0

    # (a) MICRO: 0,977470 -> 1,0, diferenca de 2,2530 pontos
    micro_com = evaluate.micro(com)
    micro_sem = evaluate.micro(sem)
    assert micro_com["n_gabarito"] == 295 and micro_com["tp_diag"] == 282
    assert micro_com["f1"] == pytest.approx(0.977470, abs=1e-6)
    assert micro_sem["f1"] == 1.0
    assert 100 * (micro_sem["f1"] - micro_com["f1"]) == pytest.approx(2.2530, abs=1e-3)

    # a outra leitura de "agregado" da OUTRO numero: 2,3709 pontos
    ponderada = 100 * (
        evaluate.media_ponderada_f1(sem) - evaluate.media_ponderada_f1(com)
    )
    assert ponderada == pytest.approx(2.3709, abs=1e-3)
    assert abs(ponderada - 2.2530) > 0.1  # as duas agregacoes NAO sao a mesma

    # (b) a classe mais afetada: tiro de meta, +18,367 pontos de revocacao
    gk_com = _celula(completo, "estrito", "goal_kick")
    gk_sem = _celula(filtrado, "estrito", "goal_kick")
    assert (int(gk_com["n_gabarito"]), int(gk_com["tp_diag"])) == (49, 40)
    assert (int(gk_sem["n_gabarito"]), int(gk_sem["tp_diag"])) == (40, 40)
    assert gk_com["revocacao"] == pytest.approx(0.816327, abs=1e-6)
    assert gk_sem["revocacao"] == 1.0
    assert 100 * (gk_sem["revocacao"] - gk_com["revocacao"]) == pytest.approx(18.367, abs=1e-3)


def test_empate_de_quadro_59923(eventos, cfg):
    """Jogo 1, quadro 59923: duas linhas `pass` de jogadores diferentes. As duas
    sao avaliadas e as duas casam, nos tres criterios."""
    gab = eventos(1)[1]
    empate = gab[(gab["frame"] == 59923) & (gab["type"] == "pass")]
    assert len(empate) == 2
    assert set(empate["player_id"]) == {"g1_home_10", "g1_home_12"}

    det = evaluate.deteccoes_do_gabarito(gab, "frame", cfg)
    grupo_de = evaluate.grupo_por_tipo(cfg)
    base = gab[gab["type"].isin(grupo_de)].reset_index(drop=True)
    base = base.assign(grupo=base["type"].map(grupo_de))
    det_g = det.assign(grupo=det["type"].map(grupo_de))
    for criterio, eixos in cfg["avaliacao"]["criterios"].items():
        i_gab, i_det = evaluate.casar(
            base, det_g, eixos["janela_s"], eixos["casa_tipo"], eixos["casa_jogador"]
        )
        alvo = base.index[(base["frame"] == 59923) & (base["type"] == "pass")]
        casados = set(i_gab.tolist()) & set(alvo.tolist())
        assert len(casados) == 2, criterio


def test_determinismo_sob_permutacao(gab, cfg):
    """Permutar as linhas de entrada nao muda nenhum numero (semente fixa)."""
    det = _deslocar(evaluate.deteccoes_do_gabarito(gab, "frame", cfg), 0.6)
    res, conf = evaluate.avaliar(gab, det, cfg)
    rng = np.random.default_rng(20261030)
    gab_p = gab.sample(frac=1.0, random_state=rng.integers(2**31)).reset_index(drop=True)
    det_p = det.sample(frac=1.0, random_state=rng.integers(2**31)).reset_index(drop=True)
    res_p, conf_p = evaluate.avaliar(gab_p, det_p.astype(evaluate.DETECTIONS), cfg)
    pd.testing.assert_frame_equal(res, res_p)
    chaves = ["criterio", "ancora", "grupo", "game", "type_gabarito", "type_detectado"]
    pd.testing.assert_frame_equal(
        conf.sort_values(chaves).reset_index(drop=True),
        conf_p.sort_values(chaves).reset_index(drop=True),
    )


# --- NaN ----------------------------------------------------------------------


def test_nan_no_tempo_do_gabarito_nao_casa_e_nao_sai_do_denominador(cfg):
    gab = _gabarito([(1000, "pass", "g1_home_1"), (2000, "pass", "g1_home_1")])
    gab = gab.astype({"frame": "float64", "annotated_frame": "float64"})
    gab.loc[1, ["frame", "annotated_frame"]] = np.nan
    det = _deteccoes([(1000, "pass", "g1_home_1"), (2000, "pass", "g1_home_1")])
    res, _ = evaluate.avaliar(gab, det, cfg)
    for criterio in CRITERIOS:
        linha = _celula(res, criterio, "pass")
        assert linha["n_gabarito"] == 2, criterio  # o NaN fica no denominador
        assert (linha["tp"], linha["fn"], linha["fp"]) == (1, 1, 1), criterio
        assert linha["revocacao"] == 0.5


def test_nan_no_tempo_da_deteccao_nao_casa_e_conta_como_fp(cfg):
    gab = _gabarito([(1000, "pass", "g1_home_1")])
    det = _deteccoes([(1000, "pass", "g1_home_1"), (2000, "pass", "g1_home_1")])
    det.loc[1, "t"] = np.nan
    res, _ = evaluate.avaliar(gab, det, cfg)
    linha = _celula(res, "estrito", "pass")
    assert (linha["n_detectado"], linha["tp"], linha["fp"]) == (2, 1, 1)
    assert linha["precisao"] == 0.5


# --- cada parametro varrido tem de mudar a saida (plano §9.4) -----------------


@pytest.mark.parametrize("criterio", CRITERIOS)
def test_janela_s_de_cada_criterio_muda_a_saida(cfg, criterio):
    """Encolher `janela_s` de QUALQUER criterio muda o numero daquele criterio."""
    linhas = [(1 + 1500 * i, "pass", "g1_home_1") for i in range(4)]
    gab = _gabarito(linhas)
    janela = cfg["avaliacao"]["criterios"][criterio]["janela_s"]
    det = _deslocar(_deteccoes(linhas), janela * 0.9)
    res, _ = evaluate.avaliar(gab, det, cfg)
    assert _celula(res, criterio, "pass")["tp"] == 4

    menor = {
        k: (dict(v, janela_s=janela * 0.5) if k == criterio else v)
        for k, v in cfg["avaliacao"]["criterios"].items()
    }
    cfg_menor = dict(cfg, avaliacao=dict(cfg["avaliacao"], criterios=menor))
    res_menor, _ = evaluate.avaliar(gab, det, cfg_menor)
    assert _celula(res_menor, criterio, "pass")["tp"] == 0
    for outro in CRITERIOS:
        if outro != criterio:
            assert (
                _celula(res_menor, outro, "pass")["tp"] == _celula(res, outro, "pass")["tp"]
            ), outro


@pytest.mark.parametrize("eixo", ["casa_tipo", "casa_jogador"])
def test_cada_eixo_do_criterio_muda_a_saida(cfg, eixo):
    """`casa_tipo` e `casa_jogador` nao podem ser ignorados."""
    gab = _gabarito([(1000, "throw_in", "g1_home_7")])
    errado = {"casa_tipo": (1000, "corner_kick", "g1_home_7"),
              "casa_jogador": (1000, "throw_in", "g1_home_9")}[eixo]
    det = _deteccoes([errado])
    estrito = cfg["avaliacao"]["criterios"]["estrito"]
    i_com, _ = evaluate.casar(
        gab.assign(grupo="bola_parada"),
        det.assign(grupo="bola_parada"),
        estrito["janela_s"],
        estrito["casa_tipo"],
        estrito["casa_jogador"],
    )
    eixos = dict(estrito, **{eixo: False})
    i_sem, _ = evaluate.casar(
        gab.assign(grupo="bola_parada"),
        det.assign(grupo="bola_parada"),
        eixos["janela_s"],
        eixos["casa_tipo"],
        eixos["casa_jogador"],
    )
    assert len(i_com) == 0 and len(i_sem) == 1


def test_ancoras_do_config_sao_usadas(gab, cfg):
    """As duas ancoras saem no resultado, e sao numeros diferentes quando as
    deteccoes vem de uma delas (sensibilidade do plano §7)."""
    det = evaluate.deteccoes_do_gabarito(gab, "frame", cfg)
    res, _ = evaluate.avaliar(gab, det, cfg)
    assert set(res["ancora"]) == set(cfg["avaliacao"]["ancoras"])
    com_frame = _celula(res, "estrito", "goal_kick", ancora="frame")
    com_anot = _celula(res, "estrito", "goal_kick", ancora="annotated_frame")
    assert com_frame["tp"] == 49 and com_anot["tp"] == 48


# --- entradas invalidas -------------------------------------------------------


def test_deteccao_de_tipo_desconhecido_estoura(cfg):
    gab = _gabarito([(1000, "pass", "g1_home_1")])
    det = _deteccoes([(1000, "pass", "g1_home_1")])
    det.loc[0, "type"] = "nutmeg"
    with pytest.raises(ValueError, match="fora de config"):
        evaluate.avaliar(gab, det, cfg)


def test_fora_do_escopo_nao_entra_em_denominador_nenhum(gab, cfg):
    """`fora_do_escopo` fica no gabarito (Fatia 1) mas nao e tipo avaliavel."""
    assert (gab["type"] == "fora_do_escopo").sum() > 0
    det = evaluate.deteccoes_do_gabarito(gab, "frame", cfg)
    res, _ = evaluate.avaliar(gab, det, cfg)
    assert "fora_do_escopo" not in set(res["type"])
    agregado = res[
        (res["criterio"] == "estrito") & (res["ancora"] == "frame") & (res["game"] == 0)
    ]
    assert int(agregado["n_gabarito"].sum()) == len(det) < len(gab)


@pytest.mark.parametrize("chave,valor,erro", [
    ("janela_inclusiva", False, NotImplementedError),
    ("denominador_passe_secundario", "cruas", NotImplementedError),
    ("criterio_principal", "footpass", ValueError),
])
def test_chaves_declarativas_do_config_sao_conferidas(cfg, chave, valor, erro):
    """Nenhuma chave de `avaliacao` fica decorativa: trocar qualquer uma destas
    tres estoura, porque a alternativa nao esta implementada."""
    gab = _gabarito([(1000, "pass", "g1_home_1")])
    det = _deteccoes([(1000, "pass", "g1_home_1")])
    cfg_alt = dict(cfg, avaliacao=dict(cfg["avaliacao"], **{chave: valor}))
    with pytest.raises(erro):
        evaluate.avaliar(gab, det, cfg_alt)


def test_grupos_do_config_sao_usados(cfg):
    """Tirar um tipo de `avaliacao.grupos` tira ele da avaliacao."""
    gab = _gabarito([(1000, "pass", "g1_home_1"), (2000, "throw_in", "g1_home_1")])
    det = _deteccoes([(1000, "pass", "g1_home_1"), (2000, "throw_in", "g1_home_1")])
    res, _ = evaluate.avaliar(gab, det, cfg)
    assert set(res["type"]) == set(evaluate.grupo_por_tipo(cfg))

    grupos = dict(cfg["avaliacao"]["grupos"], jogo_corrido=["pass"], bola_parada=["kickoff"])
    cfg_alt = dict(cfg, avaliacao=dict(cfg["avaliacao"], grupos=grupos))
    with pytest.raises(ValueError, match="fora de config"):
        evaluate.avaliar(gab, det, cfg_alt)


def test_penalty_e_classe_propria_e_nunca_agregada(gab, cfg):
    """Revisao da Fatia 2, item 7: `penalty` saiu de `fora_do_escopo` e entrou
    no grupo de bola parada, com n = 1 (jogo 2). Contagem absoluta sim,
    agregado nunca."""
    assert "penalty" in cfg["avaliacao"]["grupos"]["bola_parada"]
    det = evaluate.deteccoes_do_gabarito(gab, "frame", cfg)
    res, conf = evaluate.avaliar(gab, det, cfg)
    linha = {
        int(g): int(_celula(res, "estrito", "penalty", game=g)["n_gabarito"])
        for g in (1, 2, 3)
    }
    assert linha == {1: 0, 2: 1, 3: 0}
    assert int(_celula(res, "estrito", "penalty")["n_gabarito"]) == 1
    assert int(_celula(res, "estrito", "penalty", game=2)["tp_diag"]) == 1
    assert (
        conf[(conf["type_gabarito"] == "penalty") & (conf["grupo"] != "bola_parada")].empty
    )
    # ITEM 4 DA RE-REVISAO: a metade "nunca agregada" do nome deste teste.
    # A proibicao e guarda de codigo, nao docstring.
    bola_parada = res[
        (res["criterio"] == "estrito") & (res["ancora"] == "frame") & (res["game"] == 0)
        & res["type"].isin(cfg["avaliacao"]["grupos"]["bola_parada"])
    ]
    assert "penalty" in set(bola_parada["type"])
    for funcao in (evaluate.micro, evaluate.media_ponderada_f1):
        with pytest.raises(ValueError, match="nunca entra em agregado"):
            funcao(bola_parada)
    # e sem o penalti as duas agregam normalmente
    sem_penalty = bola_parada[bola_parada["type"] != "penalty"]
    assert evaluate.micro(sem_penalty)["f1"] == 1.0
    assert evaluate.media_ponderada_f1(sem_penalty) == 1.0


def test_f1_e_a_media_harmonica_de_precisao_e_revocacao(gab, cfg):
    """ITEM 2 DA RE-REVISAO: `f1` tem de sair de `precisao` e `revocacao`, nao
    de outra contagem. Invariante sobre o DADO REAL dos 3 jogos, com deteccoes
    perturbadas de proposito para que haja linha com P != R e com tipo trocado
    (senao a media harmonica seria trivialmente igual aos dois)."""
    det = evaluate.deteccoes_do_gabarito(gab, "frame", cfg)
    det = det.assign(t=det["t"] + 0.5, frame=det["frame"] + 13)
    posicao = np.arange(len(det))
    det.loc[(det["type"] == "throw_in") & (posicao % 3 == 0), "type"] = "corner_kick"
    det = det[posicao % 7 != 0].astype(evaluate.DETECTIONS)
    res, _ = evaluate.avaliar(gab, det, cfg)

    vale = (res["n_gabarito"] > 0) & (res["n_detectado"] > 0)
    assert int(vale.sum()) > 50
    p = res.loc[vale, "precisao"].to_numpy()
    r = res.loc[vale, "revocacao"].to_numpy()
    esperado = np.where(p + r == 0, 0.0, 2 * p * r / np.where(p + r == 0, 1.0, p + r))
    np.testing.assert_allclose(res.loc[vale, "f1"].to_numpy(), esperado, rtol=0, atol=1e-12)
    # o teste nao e vacuo: ha linha com precisao != revocacao
    assert (p != r).any()

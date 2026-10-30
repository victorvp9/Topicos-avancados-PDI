"""Testes da medicao de `tau`, inclusive a sanidade contra a inspecao e o
gatilho de G3.

Criterios de aceite: docs/fatias/02-plano.md §9.3 e §6.2.
"""

import numpy as np
import pandas as pd
import pytest

from src import tau

JOGOS = (1, 2, 3)
JOGADOR = "g1_home_1"

# Medicao desta fatia, travada como regressao. O numero vai ao relatorio do G3.
FRAC_TAU_GT_1S = {1: 339 / 722, 2: 414 / 889, 3: 449 / 1039, 0: 1202 / 2650}
N_PASSES = {1: 722, 2: 889, 3: 1039}


def _mundo(n_quadros, x, y=None, ball_x=None, ball_y=None, jogador=JOGADOR, game=1):
    """Mundo sintetico: um jogador e a bola em `n_quadros` quadros.

    `x`/`y` sao arrays de posicao do jogador (NaN = jogador sem linha, como no
    loader da Fatia 1); a bola fica em (0, 0) por omissao. Devolve
    (frames, tracking) nos esquemas da Fatia 1.
    """
    frame = np.arange(1, n_quadros + 1)
    x = np.asarray(x, dtype="float64")
    y = np.zeros(n_quadros) if y is None else np.asarray(y, dtype="float64")
    frames = pd.DataFrame(
        {
            "game": game,
            "period": 1,
            "frame": frame,
            "t": frame / 25.0,
            "ball_x": np.zeros(n_quadros) if ball_x is None else np.asarray(ball_x, "float64"),
            "ball_y": np.zeros(n_quadros) if ball_y is None else np.asarray(ball_y, "float64"),
        }
    )
    frames["ball_live"] = ~frames["ball_x"].isna()
    presente = ~np.isnan(x)
    tracking = pd.DataFrame(
        {
            "game": game,
            "period": 1,
            "frame": frame[presente],
            "player_id": jogador,
            "team": "home",
            "is_gk": False,
            "x": x[presente],
            "y": y[presente],
            "visible": True,
        }
    )
    return frames, tracking


def _evento(annotated_frame, jogador=JOGADOR, game=1):
    """Gabarito sintetico com um unico passe."""
    return pd.DataFrame(
        {
            "game": [game],
            "period": [1],
            "frame": [annotated_frame],
            "t": [annotated_frame / 25.0],
            "type": ["pass"],
            "team": ["home"],
            "player_id": [jogador],
            "annotated_frame": [annotated_frame],
        }
    )


def _vale(d_minimo_em, n_quadros):
    """Distancia em V com minimo em `d_minimo_em` (1-based), passo 0,01 m."""
    return 0.01 * np.abs(np.arange(1, n_quadros + 1) - d_minimo_em)


# --- convencao de sinal -------------------------------------------------------


def test_tau_positivo_quando_o_minimo_vem_antes_do_instante_anotado(cfg):
    """Convencao do suplementar S3, p. 5: minimo 2 s ANTES -> tau = +2,0 s."""
    frames, tracking = _mundo(1000, _vale(450, 1000))
    saida = tau.medir(1, _evento(500), frames, tracking, cfg)
    assert saida["frame_d"].iloc[0] == 450.0
    assert saida["tau_s"].iloc[0] == pytest.approx(2.0)
    assert saida["d_min_m"].iloc[0] == pytest.approx(0.0)
    assert saida["d_no_quadro_anotado_m"].iloc[0] == pytest.approx(0.5)


def test_tau_negativo_quando_o_minimo_vem_depois(cfg):
    frames, tracking = _mundo(1000, _vale(550, 1000))
    saida = tau.medir(1, _evento(500), frames, tracking, cfg)
    assert saida["tau_s"].iloc[0] == pytest.approx(-2.0)


def test_empate_de_distancia_fica_com_o_quadro_mais_antigo(cfg):
    """Determinismo: dois quadros com a mesma distancia minima."""
    x = np.full(1000, 5.0)
    x[[400, 600]] = 0.0  # quadros 401 e 601
    frames, tracking = _mundo(1000, x)
    saida = tau.medir(1, _evento(500), frames, tracking, cfg)
    assert saida["frame_d"].iloc[0] == 401.0


# --- janela -------------------------------------------------------------------


def test_janela_e_de_exatamente_250_quadros(cfg):
    """O minimo em 250 quadros de distancia entra; em 251, nao."""
    for distancia, esperado in [(250, 250.0), (251, 500.0)]:
        x = np.full(1000, 5.0)
        x[500 - distancia - 1] = 0.0  # quadro 500 - distancia
        x[499] = 1.0  # o melhor DENTRO da janela, se o outro ficar fora
        frames, tracking = _mundo(1000, x)
        saida = tau.medir(1, _evento(500), frames, tracking, cfg)
        assert saida["frame_d"].iloc[0] == esperado, distancia


def test_janela_recortada_na_borda_do_jogo(cfg):
    """Evento no quadro 10: a janela comeca em 1, sem estourar nem dar a volta."""
    frames, tracking = _mundo(300, _vale(5, 300))
    saida = tau.medir(1, _evento(10), frames, tracking, cfg)
    assert saida["frame_d"].iloc[0] == 5.0
    assert saida["tau_s"].iloc[0] == pytest.approx(0.2)


def test_janela_s_do_config_e_usada(cfg):
    """Encolher `tau.janela_s` muda o quadro de minimo."""
    x = np.full(1000, 5.0)
    x[299] = 0.0  # quadro 300, a 8 s do evento
    x[499] = 1.0
    frames, tracking = _mundo(1000, x)
    assert tau.medir(1, _evento(500), frames, tracking, cfg)["frame_d"].iloc[0] == 300.0
    cfg_curto = dict(cfg, tau=dict(cfg["tau"], janela_s=5.0))
    assert tau.medir(1, _evento(500), frames, tracking, cfg_curto)["frame_d"].iloc[0] == 500.0


# --- NaN ----------------------------------------------------------------------


def test_sem_medida_fica_na_tabela(cfg):
    """Jogador sem dado na janela: `tau = NaN` e a linha CONTINUA na tabela."""
    frames, tracking = _mundo(1000, _vale(450, 1000))
    eventos = pd.concat([_evento(500), _evento(600, jogador="g1_away_99")], ignore_index=True)
    saida = tau.medir(1, eventos, frames, tracking, cfg)
    assert len(saida) == 2
    assert np.isnan(saida["tau_s"].iloc[1])
    assert np.isnan(saida["d_min_m"].iloc[1])
    assert np.isnan(saida["frame_d"].iloc[1])
    resumo = tau.resumir(saida, cfg)
    assert int(resumo["n"].iloc[0]) == 2 and int(resumo["n_medidos"].iloc[0]) == 1
    # denominador = n, nao n_medidos: 1 de 2 passes tem |tau| > 1 s
    assert resumo["frac_tau_gt_1s"].iloc[0] == 0.5


def test_quadro_sem_jogador_nao_pode_ser_o_minimo(cfg):
    """Jogador ausente no quadro em que estaria mais perto: o minimo e outro."""
    x = _vale(450, 1000)
    x[440:460] = np.nan  # quadros 441..460, inclusive o 450
    frames, tracking = _mundo(1000, x)
    saida = tau.medir(1, _evento(500), frames, tracking, cfg)
    # 440 (d = 0,10 m) e 461 (d = 0,11 m) sao as bordas do buraco; vence 440.
    assert saida["frame_d"].iloc[0] == 440.0


def test_quadro_com_bola_nan_nao_pode_ser_o_minimo(cfg):
    """Bola NaN (bola morta, D1) no quadro do minimo: o minimo e outro."""
    bola = np.zeros(1000)
    bola[440:460] = np.nan
    frames, tracking = _mundo(1000, _vale(450, 1000), ball_x=bola)
    saida = tau.medir(1, _evento(500), frames, tracking, cfg)
    assert saida["frame_d"].iloc[0] == 440.0
    assert not frames["ball_live"].iloc[449]


def test_grade_de_quadros_nao_contigua_estoura(cfg):
    frames, tracking = _mundo(1000, _vale(450, 1000))
    with pytest.raises(ValueError, match="grade de quadros"):
        tau.medir(1, _evento(500), frames.iloc[1:], tracking, cfg)


# --- gatilho de G3 ------------------------------------------------------------


def test_gatilho_g3_dispara_com_10_por_cento_acima_de_1s(cfg):
    """Teste sintetico do plano §9.3: 10 % acima de 1 s -> g3 = True."""
    tabela = pd.DataFrame({"tau_s": [2.0] * 10 + [0.1] * 90})
    g3 = tau.gatilho_g3(tabela, cfg)
    assert g3["fracao"] == pytest.approx(0.10)
    assert g3["disparou"] is True
    assert g3["ambiguo"] is False  # 10 % esta acima da faixa [3 %, 8 %]


def test_gatilho_g3_nao_dispara_com_1_por_cento(cfg):
    tabela = pd.DataFrame({"tau_s": [2.0] + [0.1] * 99})
    g3 = tau.gatilho_g3(tabela, cfg)
    assert g3["fracao"] == pytest.approx(0.01)
    assert g3["disparou"] is False
    assert g3["ambiguo"] is False


def test_faixa_ambigua_do_config_e_usada(cfg):
    """5 % esta na faixa [3 %, 8 %]: ambiguo, e vai ao G3 de todo modo."""
    tabela = pd.DataFrame({"tau_s": [2.0] * 5 + [0.1] * 95})
    g3 = tau.gatilho_g3(tabela, cfg)
    assert g3["disparou"] is False  # 0,05 nao e > 0,05
    assert g3["ambiguo"] is True


def test_sem_medida_nao_sai_do_denominador_do_gatilho(cfg):
    """`NaN` fica no denominador: 5 acima de 1 s em 100 passes, 50 sem medida."""
    tabela = pd.DataFrame({"tau_s": [2.0] * 5 + [0.1] * 45 + [np.nan] * 50})
    assert tau.gatilho_g3(tabela, cfg)["fracao"] == pytest.approx(0.05)


@pytest.mark.parametrize("chave,valor,esperado", [
    ("limiar_g3_fracao", 0.5, False),
    ("limiar_g3_tau_s", 3.0, False),
])
def test_limiares_do_config_sao_usados(cfg, chave, valor, esperado):
    tabela = pd.DataFrame({"tau_s": [2.0] * 10 + [0.1] * 90})
    cfg_alt = dict(cfg, tau=dict(cfg["tau"], **{chave: valor}))
    assert tau.gatilho_g3(tabela, cfg_alt)["disparou"] is esperado


# --- dado real ----------------------------------------------------------------


@pytest.fixture(scope="module")
def medido(eventos, jogo, cfg):
    """Tabela `tau` dos tres jogos, concatenada."""
    return pd.concat(
        [tau.medir(g, eventos(g)[1], jogo(g)[0], jogo(g)[1], cfg) for g in JOGOS],
        ignore_index=True,
    )


def test_n_de_passes_por_jogo(medido):
    """722 / 889 / 1039 passes medidos, total 2650 (plano §6)."""
    assert medido["game"].value_counts().sort_index().to_dict() == N_PASSES
    assert len(medido) == 2650
    assert list(medido.columns) == list(tau.TAU)


def test_sanidade_reproduz_a_inspecao_6_4(eventos, jogo, cfg):
    """A mesma rotina, no QUADRO ANOTADO, sobre a MESMA populacao da inspecao:
    as linhas cruas `PASS` (n = 799 / 964), nao os passes do gabarito.

    docs/inspecao-metrica.md §6.4: < 0,5 m em 96,7 % / 97,4 %, mediana
    0,08-0,09 m, < 1 m em 97,7 % / 98,2 %, p99 3,21 / 2,21 m.
    """
    esperado = {1: (799, 773, 0.977, 3.21), 2: (964, 939, 0.982, 2.21)}
    for game, (n, menos_de_meio_metro, frac_1m, p99) in esperado.items():
        crus = eventos(game)[0]
        passes = crus[crus["metrica_type"] == "PASS"].assign(type="pass")
        saida = tau.medir(game, passes, jogo(game)[0], jogo(game)[1], cfg)
        d = saida["d_no_quadro_anotado_m"].to_numpy()
        assert len(d) == n, game
        assert int((d < 0.5).sum()) == menos_de_meio_metro, game
        assert round(100 * (d < 0.5).mean(), 1) == (96.7 if game == 1 else 97.4), game
        assert 0.08 <= np.nanmedian(d) <= 0.09, game
        assert round((d < 1.0).mean(), 3) == frac_1m, game
        assert round(np.nanpercentile(d, 99), 2) == p99, game


def test_sanidade_na_populacao_do_gabarito(medido, cfg):
    """A mesma grandeza na populacao do GABARITO (722 / 889 / 1039 passes) da
    numero diferente, porque e outra populacao: a fusao do `SET PIECE` e o
    `PASS/GOAL KICK` tiram 77 e 75 linhas `PASS`. Travado como regressao para
    que ninguem confunda as duas contagens."""
    resumo = tau.resumir(medido, cfg).set_index("game")
    assert resumo.loc[1, "frac_d_anotado_lt_0.5m"] == pytest.approx(696 / 722)
    assert resumo.loc[2, "frac_d_anotado_lt_0.5m"] == pytest.approx(864 / 889)
    assert resumo.loc[3, "frac_d_anotado_lt_0.5m"] == pytest.approx(931 / 1039)
    assert 0.08 <= resumo.loc[0, "mediana_d_anotado_m"] <= 0.10


def test_o_gatilho_de_g3_disparou_no_dado_real(medido, cfg):
    """RESULTADO DA FATIA 2, travado: 1202 de 2650 passes (45,36 %) tem
    |tau| > 1 s, contra o limiar de 5 % escrito antes de medir. O gatilho
    DISPAROU; a decisao sobre o D8 e do Victor no G3."""
    g3 = tau.gatilho_g3(medido, cfg)
    assert g3["n"] == 2650
    assert g3["fracao"] == pytest.approx(FRAC_TAU_GT_1S[0], abs=1e-9)
    assert g3["fracao"] > 0.05 and g3["disparou"] is True
    resumo = tau.resumir(medido, cfg).set_index("game")
    for game, fracao in FRAC_TAU_GT_1S.items():
        assert resumo.loc[game, "frac_tau_gt_1s"] == pytest.approx(fracao, abs=1e-9), game


def test_distribuicao_de_tau_no_dado_real(medido, cfg):
    """Media, mediana e as faixas de |tau| e de `d_min` (plano §6)."""
    resumo = tau.resumir(medido, cfg).set_index("game")
    assert resumo.loc[0, "media_tau_s"] == pytest.approx(0.698943, abs=1e-6)
    assert resumo.loc[0, "mediana_tau_s"] == pytest.approx(0.12, abs=1e-9)
    assert resumo.loc[0, "frac_tau_gt_3s"] == pytest.approx(586 / 2650, abs=1e-9)
    assert resumo.loc[0, "frac_tau_gt_5s"] == pytest.approx(345 / 2650, abs=1e-9)
    assert resumo.loc[0, "frac_tau_gt_7.5s"] == pytest.approx(166 / 2650, abs=1e-9)
    assert resumo.loc[0, "frac_d_min_lt_0.5m"] == pytest.approx(2595 / 2650, abs=1e-9)
    assert int(resumo.loc[0, "n_medidos"]) == 2650  # nenhum passe sem medida


def test_tau_e_consistente_com_frame_d(medido, cfg):
    """`tau_s = (annotated_frame - frame_d) / fps`, sem excecao."""
    esperado = (medido["annotated_frame"] - medido["frame_d"]) / cfg["tracking"]["fps"]
    pd.testing.assert_series_equal(medido["tau_s"], esperado, check_names=False)


def test_o_gabarito_nao_foi_tocado(eventos, medido):
    """A medicao nao filtra nem reordena o gabarito: uma linha por passe, na
    mesma ordem."""
    for game in JOGOS:
        gab = eventos(game)[1]
        passes = gab[gab["type"] == "pass"]
        bloco = medido[medido["game"] == game]
        assert bloco["annotated_frame"].tolist() == passes["annotated_frame"].tolist()
        assert bloco["player_id"].tolist() == passes["player_id"].tolist()


# --- saida da CLI (plano §9.5) ------------------------------------------------


def test_cli_tau_imprime_o_gatilho_e_grava_o_csv(capsys, cfg, mapeamento, tmp_path):
    from src.run import medir_tau

    destino = tmp_path / "tau.csv"
    tabela = medir_tau(cfg, mapeamento, [1], gravar_em=destino)
    saida = capsys.readouterr().out
    assert "GATILHO DE G3: DISPAROU" in saida
    assert "|tau| > 1 s em 339 de 722 passes = 46.95%" in saida
    assert "limiar escrito antes de medir: 5.00%" in saida
    assert "D8) esta CONTRADITA" in saida
    # as duas populacoes da reproducao da 6.4, lado a lado
    assert "linhas cruas PASS" in saida and "n =  799  < 0.5 m 96.75%" in saida
    assert "passes do gabarito" in saida and "n =  722  < 0.5 m 96.40%" in saida
    assert len(pd.read_csv(destino)) == len(tabela) == 722


def test_cli_exige_um_subcomando():
    from src.run import main

    with pytest.raises(SystemExit):
        main([])


def test_faixa_ambigua_e_fechada_nas_duas_pontas(cfg):
    """Revisao da Fatia 2, item 4: a semantica das pontas, declarada e fixada.

    `faixa_ambigua = [0,03; 0,08]` e FECHADA: exatamente 3,0 % e exatamente
    8,0 % SAO ambiguos. E a escolha conservadora -- leva ao G3 em vez de passar
    raspando. Logo abaixo e logo acima, nao.
    """
    baixo, alto = cfg["tau"]["faixa_ambigua"]
    assert (baixo, alto) == (0.03, 0.08)
    casos = {
        0.029: False,   # 2,9 %: abaixo da faixa
        0.030: True,    # ponta inferior: AMBIGUO
        0.050: True,
        0.080: True,    # ponta superior: AMBIGUO
        0.081: False,   # 8,1 %: acima da faixa
    }
    for fracao, esperado in casos.items():
        n = 1000
        acima = round(fracao * n)
        tabela = pd.DataFrame({"tau_s": [2.0] * acima + [0.1] * (n - acima)})
        g3 = tau.gatilho_g3(tabela, cfg)
        assert g3["fracao"] == pytest.approx(fracao)
        assert g3["ambiguo"] is esperado, fracao


def test_faixas_do_config_dao_nome_as_colunas(cfg, medido):
    """Revisao da Fatia 2, item 5: as faixas sairam do `src/` e foram para o
    `config.yaml`. O nome de cada coluna vem do valor da faixa, logo mexer no
    config muda a saida e a constante nao pode ser ignorada."""
    assert cfg["tau"]["faixas_tau_s"] == [1.0, 3.0, 5.0, 7.5]
    assert cfg["tau"]["faixas_d_m"] == [0.5, 1.0, 1.5]
    assert cfg["tau"]["faixa_sanidade_d_m"] == 0.5
    colunas = set(tau.resumir(medido, cfg).columns)
    assert {"frac_tau_gt_1s", "frac_tau_gt_3s", "frac_tau_gt_5s", "frac_tau_gt_7.5s"} <= colunas
    assert {"frac_d_min_lt_0.5m", "frac_d_min_lt_1m", "frac_d_min_lt_1.5m"} <= colunas
    assert "frac_d_anotado_lt_0.5m" in colunas

    cfg_alt = dict(
        cfg,
        tau=dict(cfg["tau"], faixas_tau_s=[2.0], faixas_d_m=[0.25], faixa_sanidade_d_m=0.25),
    )
    outras = set(tau.resumir(medido, cfg_alt).columns)
    assert "frac_tau_gt_2s" in outras and "frac_tau_gt_1s" not in outras
    assert "frac_d_min_lt_0.25m" in outras and "frac_d_min_lt_0.5m" not in outras
    assert "frac_d_anotado_lt_0.25m" in outras


def test_faixa_de_sanidade_muda_o_VALOR_nao_so_o_nome_da_coluna(medido, cfg):
    """ITEM 3 DA RE-REVISAO: o teste anterior conferia quais colunas existem, o
    que um literal `0.5` na comparacao nao quebraria. Aqui a comparacao e de
    VALOR entre duas faixas, sobre os 2650 passes reais."""
    base = tau.resumir(medido, cfg).set_index("game")
    menor = tau.resumir(
        medido, dict(cfg, tau=dict(cfg["tau"], faixa_sanidade_d_m=0.25, faixas_d_m=[0.25, 0.5]))
    ).set_index("game")
    assert base.loc[0, "frac_d_anotado_lt_0.5m"] == pytest.approx(0.94, abs=1e-9)
    frac_025 = menor.loc[0, "frac_d_anotado_lt_0.25m"]
    assert frac_025 < base.loc[0, "frac_d_anotado_lt_0.5m"]
    assert 0.5 < frac_025 < 0.94  # faixa menor, fracao estritamente menor
    # idem para as faixas de d_min: 0,25 m e subconjunto de 0,5 m
    assert menor.loc[0, "frac_d_min_lt_0.25m"] < menor.loc[0, "frac_d_min_lt_0.5m"]
    # e para |tau|: 3 s e subconjunto de 1 s
    assert base.loc[0, "frac_tau_gt_3s"] < base.loc[0, "frac_tau_gt_1s"]

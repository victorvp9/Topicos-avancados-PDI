"""Loader dos jogos 1 e 2 e sentido de ataque (plano §8.2 e §8.3).

Todos os numeros esperados vem de docs/inspecao-metrica.md §2.
"""

import numpy as np
import pytest

from src.io import metrica_csv, schema
from src.io.coordenadas import x_para_metros

N_QUADROS = {1: 145006, 2: 141156}
QUADROS_POR_PERIODO = {1: {1: 71268, 2: 73738}, 2: {1: 67941, 2: 73215}}
QUADROS_MORTOS = {1: 56755, 2: 57884}
FRACAO_MORTA = {1: 0.3914, 2: 0.4101}
QUADROS_COM_22 = {1: 145000, 2: 141152}
QUADROS_COM_23 = {1: 6, 2: 4}
# Celulas (quadro, jogador) com x nao-NaN nos arquivos crus. Hardcoded: e o
# numero que o §8.2 manda comparar com len(tracking).
LINHAS_NAO_NAN = {1: 3190138, 2: 3105436, 3: 3162742}

# docs/inspecao-metrica.md §2.3: x medio do goleiro, por jogo/periodo/time.
ATTACK_DIR = {
    (1, 1, "home"): +1,
    (1, 2, "home"): -1,
    (1, 1, "away"): -1,
    (1, 2, "away"): +1,
    (2, 1, "home"): -1,
    (2, 2, "home"): +1,
    (2, 1, "away"): +1,
    (2, 2, "away"): -1,
}


def contar_nao_nan_no_arquivo_cru(game: int) -> int:
    """Conta as celulas (quadro, jogador) com x nao-NaN relendo os arquivos crus."""
    from src.config import carregar_config
    from src.io import metrica_epts

    raiz = carregar_config()["dados"]["raiz"]
    if game == 3:
        bruto = metrica_epts.ler_tracking(metrica_epts.caminho_tracking(raiz))
        return int((~np.isnan(bruto[:, 1:45:2])).sum())
    total = 0
    for lado in ("home", "away"):
        dados = metrica_csv.ler_arquivo_time(metrica_csv.caminho_tracking(raiz, game, lado))
        total += int((~np.isnan(dados["x_norm"])).sum())
    return total


@pytest.mark.parametrize("game", [1, 2])
def test_numero_de_quadros(jogo, game):
    frames = jogo(game)[0]
    assert len(frames) == N_QUADROS[game]


@pytest.mark.parametrize("game", [1, 2])
def test_quadros_por_periodo(jogo, game):
    frames = jogo(game)[0]
    contagem = frames["period"].value_counts().sort_index().to_dict()
    assert contagem == QUADROS_POR_PERIODO[game]


@pytest.mark.parametrize("game", [1, 2, 3])
def test_grade_de_quadros(jogo, game):
    """`frame` de 1 a N, sem buraco e sem duplicata."""
    frames = jogo(game)[0]
    assert np.array_equal(frames["frame"].to_numpy(), np.arange(1, len(frames) + 1))


@pytest.mark.parametrize("game", [1, 2, 3])
def test_relogio(jogo, game, cfg):
    frames = jogo(game)[0]
    desvio = (frames["t"] - frames["frame"] / cfg["tracking"]["fps"]).abs().max()
    assert desvio == 0.0


@pytest.mark.parametrize("game", [1, 2])
def test_relogio_contra_coluna_crua(cfg, game):
    """`Time [s]` cru do CSV == frame/fps, bit a bit (inspecao §2)."""
    dados = metrica_csv.ler_arquivo_time(
        metrica_csv.caminho_tracking(cfg["dados"]["raiz"], game, "home")
    )
    desvio = np.max(np.abs(dados["time_s"] - dados["frame"] / cfg["tracking"]["fps"]))
    assert desvio == 0.0


def test_fps_de_config_e_usado(jogo, cfg):
    """Falha se tracking.fps for ignorado na coluna `t`."""
    frames = jogo(1)[0]
    assert cfg["tracking"]["fps"] == 25
    assert frames["t"].iloc[0] == pytest.approx(1 / 25)
    assert frames["t"].iloc[-1] != frames["frame"].iloc[-1] / 50


@pytest.mark.parametrize("game", [1, 2])
def test_bola_morta(jogo, game):
    frames = jogo(game)[0]
    mortos = int((~frames["ball_live"]).sum())
    assert mortos == QUADROS_MORTOS[game]
    assert mortos / len(frames) == pytest.approx(FRACAO_MORTA[game], abs=5e-5)


@pytest.mark.parametrize("game", [1, 2, 3])
def test_ball_live_e_nan_da_bola(jogo, game):
    """`ball_live = not isna(ball_x)` (D1) e o NaN de x e y da bola coincide."""
    frames = jogo(game)[0]
    assert np.array_equal(frames["ball_live"].to_numpy(), ~frames["ball_x"].isna().to_numpy())
    assert np.array_equal(frames["ball_x"].isna().to_numpy(), frames["ball_y"].isna().to_numpy())


@pytest.mark.parametrize("game", [1, 2])
def test_jogadores_por_quadro(jogo, game):
    """Exatamente 22 ou 23 jogadores por quadro, nenhum outro valor."""
    tracking = jogo(game)[1]
    contagem = tracking.groupby("frame").size().value_counts().to_dict()
    assert contagem == {22: QUADROS_COM_22[game], 23: QUADROS_COM_23[game]}


@pytest.mark.parametrize("game", [1, 2, 3])
def test_nan_nao_virou_zero(jogo, game):
    """nº de linhas de `tracking` = jogadores nao-NaN nos arquivos CRUS (§8.2)."""
    frames, tracking, _ = jogo(game)
    assert len(tracking) == LINHAS_NAO_NAN[game]
    assert len(tracking) == contar_nao_nan_no_arquivo_cru(game)
    assert not tracking[["x", "y"]].isna().to_numpy().any()
    # x == 0.0 e y == 0.0 ao mesmo tempo seria o centro exato do campo: nao e
    # plausivel e denunciaria imputacao por zero.
    assert not ((tracking["x"] == 0.0) & (tracking["y"] == 0.0)).any()


@pytest.mark.parametrize("game", [1, 2, 3])
def test_visible_sempre_true(jogo, game):
    """Plano §8.5(8): nesta fatia nada foi imputado."""
    assert jogo(game)[1]["visible"].all()


def test_nome_de_coluna_com_espaco(cfg, jogo):
    """O jogo 2 traz `Player 26`; o id tem de ser `g2_away_26`."""
    dados = metrica_csv.ler_arquivo_time(
        metrica_csv.caminho_tracking(cfg["dados"]["raiz"], 2, "away")
    )
    assert "Player 26" in dados["nomes"]
    assert metrica_csv.numero_camisa("Player 26") == 26
    ids = set(jogo(2)[1]["player_id"].unique())
    assert "g2_away_26" in ids
    assert not any(" " in pid for pid in ids)


@pytest.mark.parametrize("game", [1, 2])
def test_bola_identica_nos_dois_arquivos(cfg, game):
    """O loader usa o arquivo Home; aqui conferimos o Away, bit a bit."""
    raiz = cfg["dados"]["raiz"]
    home = metrica_csv.ler_arquivo_time(metrica_csv.caminho_tracking(raiz, game, "home"))
    away = metrica_csv.ler_arquivo_time(metrica_csv.caminho_tracking(raiz, game, "away"))
    assert np.array_equal(home["ball_x_norm"], away["ball_x_norm"], equal_nan=True)
    assert np.array_equal(home["ball_y_norm"], away["ball_y_norm"], equal_nan=True)
    assert np.array_equal(home["frame"], away["frame"])
    assert np.array_equal(home["period"], away["period"])


@pytest.mark.parametrize("game,period,team", list(ATTACK_DIR))
def test_attack_dir(jogo, game, period, team):
    periods = jogo(game)[2]
    linha = periods[(periods["period"] == period) & (periods["team"] == team)]
    assert len(linha) == 1
    assert int(linha["attack_dir"].iloc[0]) == ATTACK_DIR[(game, period, team)]


@pytest.mark.parametrize("game", [1, 2, 3])
def test_attack_dir_inverte_entre_periodos(jogo, game):
    periods = jogo(game)[2]
    for team in ("home", "away"):
        por_periodo = periods[periods["team"] == team].set_index("period")["attack_dir"]
        assert por_periodo[1] == -por_periodo[2]


@pytest.mark.parametrize("game", [1, 2, 3])
def test_attack_dir_times_opostos(jogo, game):
    periods = jogo(game)[2]
    for period in (1, 2):
        por_time = periods[periods["period"] == period].set_index("team")["attack_dir"]
        assert por_time["home"] == -por_time["away"]


@pytest.mark.parametrize("game", [1, 2, 3])
def test_attack_dir_concorda_com_a_media_do_time(jogo, game):
    """Plano §10 (G3): a decisao sai do goleiro; a media do time e a checagem cruzada.

    Exige concordancia nas 12 combinacoes de (jogo, periodo, time). `gk_mean_x`
    tem de ser mesmo a media do goleiro, logo bem longe do centro.
    """
    tracking, periods = jogo(game)[1], jogo(game)[2]
    media_time = tracking.groupby(["period", "team"])["x"].mean()
    media_gk = tracking[tracking["is_gk"]].groupby(["period", "team"])["x"].mean()
    assert len(periods) == 4
    for linha in periods.itertuples():
        chave = (linha.period, linha.team)
        assert linha.gk_mean_x == pytest.approx(float(media_gk[chave]))
        assert linha.attack_dir == (-1 if media_time[chave] > 0 else 1)
        assert abs(linha.gk_mean_x) > 35.0  # goleiro, nao media do time


@pytest.mark.parametrize("game", [1, 2, 3])
def test_exatamente_dois_goleiros_por_quadro(jogo, game):
    """Um goleiro por time em todo quadro, nos tres jogos."""
    tracking = jogo(game)[1]
    gks = tracking[tracking["is_gk"]]
    assert gks.groupby("frame").size().value_counts().to_dict() == {2: len(jogo(game)[0])}
    assert set(gks.groupby("frame")["team"].nunique().unique()) == {2}
    assert gks["player_id"].nunique() == 2


@pytest.mark.parametrize("game", [1, 2])
def test_sem_rotacao(cfg, jogo, game):
    """`tracking.x` e a conversao direta do CSV cru, sem sinal trocado."""
    raiz = cfg["dados"]["raiz"]
    tracking = jogo(game)[1]
    for lado in ("home", "away"):
        dados = metrica_csv.ler_arquivo_time(metrica_csv.caminho_tracking(raiz, game, lado))
        camisa = metrica_csv.numero_camisa(dados["nomes"][0])
        esperado = x_para_metros(dados["x_norm"][:, 0], cfg["campo"]["comprimento_m"])
        obtido = tracking[tracking["player_id"] == f"g{game}_{lado}_{camisa}"].set_index("frame")[
            "x"
        ]
        presente = ~np.isnan(esperado)
        quadros = dados["frame"][presente]
        assert np.allclose(obtido.loc[quadros].to_numpy(), esperado[presente], atol=0.0)


@pytest.mark.parametrize("game", [1, 2, 3])
def test_esquema(jogo, game):
    frames, tracking, periods = jogo(game)
    schema.validar(frames, schema.FRAMES, "frames")
    schema.validar(tracking, schema.TRACKING, "tracking")
    schema.validar(periods, schema.PERIODS, "periods")


def test_esquema_identico_entre_jogos(jogo):
    """Colunas e dtypes iguais nos tres jogos (plano §8.2)."""
    assinaturas = []
    for game in (1, 2, 3):
        frames, tracking, _ = jogo(game)
        assinaturas.append(
            (
                tuple(frames.columns),
                tuple(str(d) for d in frames.dtypes),
                tuple(tracking.columns),
                tuple(str(d) for d in tracking.dtypes),
            )
        )
    assert assinaturas[0] == assinaturas[1] == assinaturas[2]


def test_numero_camisa_sem_digito_estoura():
    with pytest.raises(ValueError):
        metrica_csv.numero_camisa("Ball")

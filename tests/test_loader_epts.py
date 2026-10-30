"""Loader do jogo 3 (EPTS FIFA). Plano §8.2, docs/inspecao-metrica.md §4."""

import numpy as np
import pytest

from src.io import metrica_epts

N_QUADROS = 143761
QUADROS_MORTOS = 46325
FRACAO_MORTA = 0.3222
N_BLOCOS = 11
QUADROS_POR_PERIODO = {1: 69661, 2: 74100}


@pytest.fixture(scope="module")
def meta(cfg):
    return metrica_epts.ler_metadata(metrica_epts.caminho_metadata(cfg["dados"]["raiz"]))


def test_metadata_global(meta):
    assert meta["fps"] == 25
    assert meta["comprimento_m"] == 105.0
    assert meta["largura_m"] == 68.0
    assert meta["periodos"] == [(1, 1, 69661), (2, 69662, 143761)]


def test_blocos_cobrem_tudo_sem_lacuna_nem_sobreposicao(meta):
    blocos = meta["blocos"]
    assert len(blocos) == N_BLOCOS
    faixas = sorted((inicio, fim) for inicio, fim, _ in blocos)
    assert faixas[0][0] == 1
    assert faixas[-1][1] == N_QUADROS
    for (_, fim_anterior), (inicio, _) in zip(faixas, faixas[1:]):
        assert inicio == fim_anterior + 1


def test_44_canais_por_bloco(cfg, meta):
    """44 PlayerChannelRef por bloco = 22 jogadores x 2 coordenadas."""
    import xml.etree.ElementTree as ET

    raiz = ET.parse(metrica_epts.caminho_metadata(cfg["dados"]["raiz"])).getroot()
    blocos_xml = list(raiz.iter("DataFormatSpecification"))
    assert len(blocos_xml) == N_BLOCOS
    for bloco in blocos_xml:
        assert len(list(bloco.iter("PlayerChannelRef"))) == 44
    for _, _, ordem in meta["blocos"]:
        assert len(ordem) == 22
        assert len(set(ordem)) == 22


def test_ordem_dos_campos_segue_o_bloco_vigente(cfg, meta, jogo):
    """Confere o tracking lido contra o .txt cru, no bloco e no quadro certos.

    Pega o primeiro quadro de cada bloco e compara o par (x, y) do primeiro
    canal do bloco com a linha crua. Se a ordem fosse a do bloco errado, as
    substituicoes trocariam de jogador aqui.
    """
    bruto = metrica_epts.ler_tracking(metrica_epts.caminho_tracking(cfg["dados"]["raiz"]))
    tracking = jogo(3)[1]
    comprimento = cfg["campo"]["comprimento_m"]
    for inicio, _, ordem in meta["blocos"]:
        jogador = meta["jogadores"][ordem[0]]
        pid = f"g3_{jogador['team']}_{jogador['camisa']}"
        x_cru = bruto[inicio - 1, 1]
        linha = tracking[(tracking["frame"] == inicio) & (tracking["player_id"] == pid)]
        assert len(linha) == 1
        assert float(linha["x"].iloc[0]) == pytest.approx((x_cru - 0.5) * comprimento, abs=1e-9)


def test_goleiros_identificados(meta, jogo):
    gks = {pid for pid, j in meta["jogadores"].items() if j["is_gk"]}
    assert len(gks) == 2
    tracking = jogo(3)[1]
    ids_gk = set(tracking.loc[tracking["is_gk"], "player_id"].unique())
    assert ids_gk == {"g3_home_11", "g3_away_28"}


def test_numero_de_quadros(jogo):
    frames = jogo(3)[0]
    assert len(frames) == N_QUADROS
    assert frames["period"].value_counts().sort_index().to_dict() == QUADROS_POR_PERIODO


def test_bola_morta(jogo):
    frames = jogo(3)[0]
    mortos = int((~frames["ball_live"]).sum())
    assert mortos == QUADROS_MORTOS
    assert mortos / len(frames) == pytest.approx(FRACAO_MORTA, abs=5e-5)


def test_sempre_22_jogadores(jogo):
    """Inspecao §4: 22 jogadores com dado em TODOS os quadros do jogo 3."""
    tracking = jogo(3)[1]
    contagem = tracking.groupby("frame").size().value_counts().to_dict()
    assert contagem == {22: N_QUADROS}
    assert len(tracking) == 22 * N_QUADROS


def test_tracking_cru_tem_47_campos(cfg):
    bruto = metrica_epts.ler_tracking(metrica_epts.caminho_tracking(cfg["dados"]["raiz"]))
    assert bruto.shape == (N_QUADROS, 1 + 44 + 2)
    assert np.array_equal(bruto[:, 0].astype(int), np.arange(1, N_QUADROS + 1))


def test_nan_literal_preservado(cfg):
    """`NaN` escrito literalmente no .txt vira NaN, nao 0.0."""
    bruto = metrica_epts.ler_tracking(metrica_epts.caminho_tracking(cfg["dados"]["raiz"]))
    assert np.isnan(bruto[0, 45]) and np.isnan(bruto[0, 46])  # quadro 1: bola NaN


def test_carregar_rejeita_outro_jogo(cfg):
    with pytest.raises(ValueError):
        metrica_epts.carregar(1, cfg)


def test_montar_tracking_estoura_se_nan_de_x_e_y_divergirem():
    """NaN de jogador nunca e imputado; x e y tem de faltar juntos."""
    from src.io import schema

    x = np.array([[1.0, np.nan]])
    y = np.array([[1.0, 0.5]])
    with pytest.raises(ValueError, match="NaN de x e de y"):
        schema.montar_tracking(
            9,
            np.array([1]),
            np.array([1]),
            x,
            y,
            ["a", "b"],
            np.array(["home", "home"], dtype=object),
            np.array([True, False]),
            105.0,
            68.0,
        )


def test_montar_tracking_descarta_so_as_celulas_nan():
    """Jogador ausente = linha ausente, nunca zero, nunca visible=False."""
    from src.io import schema

    x = np.array([[0.5, np.nan], [0.5, 0.5]])
    y = np.array([[0.5, np.nan], [0.5, 0.5]])
    df = schema.montar_tracking(
        9,
        np.array([1, 1]),
        np.array([1, 2]),
        x,
        y,
        ["a", "b"],
        np.array(["home", "away"], dtype=object),
        np.array([True, False]),
        105.0,
        68.0,
    )
    assert len(df) == 3
    assert df["visible"].all()
    assert df.groupby("frame").size().to_dict() == {1: 1, 2: 2}

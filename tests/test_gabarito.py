"""Construcao do gabarito: mapeamento, fusao e ancoragem (plano §8.4)."""

import shutil

import numpy as np
import pytest

from src import gabarito
from src.io import metrica_csv

TOTAL_SET_PIECE = 247  # 77 + 80 + 90, inspecao §3.2
DISTANCIA_MAX_LINHA_DE_FUNDO_M = 6.0  # plano §8.4, caso 77582
DISTANCIA_MEDIDA_77582_M = 4.52  # inspecao §6.3, valor apos a ancoragem

# Guarda de 10 s (plano §6.2, G3 de 2026-10-29): 1 pontape inicial sem bola morta
# antes (quadro 1 do jogo 1) + 12 bolas paradas cuja ancora saltaria mais de 10 s.
TOTAL_NO_DEAD_BALL_BEFORE = 13
AFETADOS_PELA_GUARDA = {"goal_kick": 9, "free_kick": 3}


def _cfg_com_raiz(cfg, raiz):
    novo = {k: dict(v) if isinstance(v, dict) else v for k, v in cfg.items()}
    novo["dados"] = dict(cfg["dados"])
    novo["dados"]["raiz"] = raiz
    return novo


@pytest.fixture
def raiz_falsa(tmp_path, cfg):
    """Copia o CSV de eventos do jogo 1 para um diretorio temporario editavel."""
    destino = tmp_path / "Sample_Game_1"
    destino.mkdir()
    origem = metrica_csv.caminho_eventos(cfg["dados"]["raiz"], 1)
    shutil.copy(origem, destino / origem.name)
    return tmp_path


def test_subtipo_desconhecido_estoura(cfg, mapeamento, raiz_falsa):
    """Plano §8.4: subtipo inventado estoura, nunca cai em fora_do_escopo."""
    caminho = metrica_csv.caminho_eventos(raiz_falsa, 1)
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    linhas[1] = linhas[1].replace("KICK OFF", "BANANA SPLIT", 1)
    assert "BANANA SPLIT" in linhas[1]
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    with pytest.raises(ValueError, match="BANANA SPLIT"):
        gabarito.carregar_eventos_crus(1, _cfg_com_raiz(cfg, raiz_falsa), mapeamento)


def test_type_desconhecido_estoura(cfg, mapeamento, raiz_falsa):
    caminho = metrica_csv.caminho_eventos(raiz_falsa, 1)
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    linhas[1] = linhas[1].replace("SET PIECE", "TELETRANSPORTE", 1)
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    with pytest.raises(ValueError, match="TELETRANSPORTE"):
        gabarito.carregar_eventos_crus(1, _cfg_com_raiz(cfg, raiz_falsa), mapeamento)


def test_fusao_sem_casamento_estoura(cfg, mapeamento, raiz_falsa, jogo):
    """Plano §6.1: se a linha i+1 nao casar, raise. Nenhuma heuristica."""
    caminho = metrica_csv.caminho_eventos(raiz_falsa, 1)
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    campos = linhas[2].split(",")
    campos[8] = "Player99"  # coluna `From` da linha de execucao
    linhas[2] = ",".join(campos)
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    cfg_falso = _cfg_com_raiz(cfg, raiz_falsa)
    crus = gabarito.carregar_eventos_crus(1, cfg_falso, mapeamento)
    with pytest.raises(ValueError, match="nao casa"):
        gabarito.construir_gabarito(1, crus, jogo(1)[0], cfg_falso)


@pytest.mark.parametrize("game", [1, 2, 3])
def test_nada_e_apagado(eventos, game):
    """eventos no gabarito + linhas fundidas = linhas cruas."""
    crus, gab = eventos(game)
    fundidas = sum(1 for s in gab["source_rows"] if "," in s)
    assert len(gab) + fundidas == len(crus)
    indices = sorted(int(i) for s in gab["source_rows"] for i in s.split(","))
    assert indices == list(range(len(crus)))


def test_total_de_bola_parada_e_247(eventos):
    """Plano §8.4: 247 eventos de SET PIECE, nao 494."""
    total = sum((eventos(g)[1]["metrica_type"] == "SET PIECE").sum() for g in (1, 2, 3))
    assert total == TOTAL_SET_PIECE
    fundidas = sum(
        sum(1 for s in eventos(g)[1]["source_rows"] if "," in s) for g in (1, 2, 3)
    )
    assert fundidas == TOTAL_SET_PIECE


@pytest.mark.parametrize("game", [1, 2, 3])
def test_fusao_casa_from_e_period(eventos, game):
    """Para todo SET PIECE, `source_rows` tem 2 indices com mesmo From e Period."""
    crus, gab = eventos(game)
    por_row = crus.set_index("row")
    fundidos = gab[gab["metrica_type"] == "SET PIECE"]
    assert len(fundidos) > 0
    for fonte in fundidos["source_rows"]:
        indices = [int(i) for i in fonte.split(",")]
        assert len(indices) == 2
        assert indices[1] == indices[0] + 1
        a, b = por_row.loc[indices[0]], por_row.loc[indices[1]]
        assert a["player_id"] == b["player_id"]
        assert a["period"] == b["period"]
        assert a["metrica_type"] == "SET PIECE"
        assert b["metrica_type"] != "SET PIECE"


@pytest.mark.parametrize("game", [1, 2, 3])
def test_execucao_fundida_nao_gera_passe_extra(eventos, game):
    """Nenhuma linha de execucao fundida aparece como evento proprio."""
    crus, gab = eventos(game)
    consumidas = {
        int(fonte.split(",")[1]) for fonte in gab["source_rows"] if "," in fonte
    }
    sozinhas = {int(fonte) for fonte in gab["source_rows"] if "," not in fonte}
    assert consumidas & sozinhas == set()
    # as execucoes consumidas eram PASS / BALL LOST / BALL OUT / SHOT
    tipos = set(crus.set_index("row").loc[sorted(consumidas), "metrica_type"])
    assert tipos <= {"PASS", "BALL LOST", "BALL OUT", "SHOT"}


@pytest.mark.parametrize("game", [1, 2, 3])
def test_ancoragem(eventos, jogo, game):
    """anchor_shift <= 0 e ball_live[frame], exceto no_dead_ball_before."""
    _, gab = eventos(game)
    ball_live = jogo(game)[0].sort_values("frame")["ball_live"].to_numpy()
    ancorados = gab[
        (gab["metrica_type"] == "SET PIECE") | (gab["type"] == "goal_kick")
    ]
    assert len(ancorados) > 0
    normais = ancorados[~ancorados["no_dead_ball_before"]]
    assert (normais["anchor_shift"] <= 0).all()
    assert ball_live[normais["frame"].to_numpy() - 1].all()
    # evento de jogo corrido nao e ancorado
    corridos = gab[(gab["metrica_type"] != "SET PIECE") & (gab["type"] != "goal_kick")]
    assert (corridos["anchor_shift"] == 0).all()
    assert (corridos["frame"] == corridos["annotated_frame"]).all()


def test_quadro_1_do_jogo_1(eventos):
    """Plano §6.3: o pontape inicial do quadro 1 permanece no gabarito."""
    _, gab = eventos(1)
    alvo = gab[gab["no_dead_ball_before"] & (gab["annotated_frame"] == 1)]
    assert len(alvo) == 1
    assert alvo["type"].iloc[0] == "kickoff"
    assert int(alvo["frame"].iloc[0]) == 1
    assert int(alvo["game"].iloc[0]) == 1
    # e o unico sem bola morta antes; os demais `ndb` vem da guarda de 10 s
    for game in (1, 2, 3):
        _, outro = eventos(game)
        semeados = outro[outro["no_dead_ball_before"] & (outro["annotated_frame"] == 1)]
        assert len(semeados) == (1 if game == 1 else 0)


def test_no_dead_ball_before_total(eventos):
    """1 pontape inicial estrutural + 12 cortados pela guarda de 10 s."""
    total = sum(int(eventos(g)[1]["no_dead_ball_before"].sum()) for g in (1, 2, 3))
    assert total == TOTAL_NO_DEAD_BALL_BEFORE


def test_guarda_de_10s_corta_9_goal_kick_e_3_free_kick(eventos, cfg):
    """Plano §6.2 / G3: a guarda nao ancora quem saltaria mais de 10 s.

    Os 12 passam a ser perda de revocacao declarada, com `frame` no quadro
    anotado. O quadro 1 do jogo 1 (sem bola morta antes) fica fora da contagem.
    """
    guarda_quadros = round(cfg["gabarito"]["guarda_ancora_s"] * cfg["tracking"]["fps"])
    assert guarda_quadros == 250
    contagem = {}
    for game in (1, 2, 3):
        _, gab = eventos(game)
        cortados = gab[gab["no_dead_ball_before"] & (gab["annotated_frame"] > 1)]
        # nao ancorado: ficou no quadro anotado
        assert (cortados["frame"] == cortados["annotated_frame"]).all()
        assert (cortados["anchor_shift"] == 0).all()
        for tipo, n in cortados["type"].value_counts().items():
            contagem[tipo] = contagem.get(tipo, 0) + int(n)
    assert contagem == AFETADOS_PELA_GUARDA


def test_guarda_elimina_as_colisoes_de_quadro(eventos):
    """Depois da guarda, nenhum par de bolas paradas compartilha (game, frame).

    Sem a guarda havia 2 colisoes: jogo 1, os tiros de meta 125558 e 125622
    caiam ambos em 124787; jogo 2, o tiro de meta 56958 caia em 54472, que e o
    quadro de um KICK OFF.
    """
    for game in (1, 2, 3):
        _, gab = eventos(game)
        parada = gab[(gab["metrica_type"] == "SET PIECE") | (gab["type"] == "goal_kick")]
        repetidos = parada["frame"].value_counts()
        assert repetidos.max() == 1, repetidos[repetidos > 1].to_dict()


def test_sem_guarda_as_colisoes_reaparecem(eventos, jogo):
    """Contraprova: o teste acima nao e vacuo."""
    _, gab = eventos(1)
    ball_live = jogo(1)[0].sort_values("frame")["ball_live"].to_numpy()
    parada = gab[(gab["metrica_type"] == "SET PIECE") | (gab["type"] == "goal_kick")]
    sem_guarda, _ = gabarito.ancorar(
        parada["annotated_frame"].to_numpy(), ball_live, 10**9
    )
    assert np.bincount(sem_guarda).max() == 2  # 125558 e 125622 -> 124787


def test_caso_77582(eventos, jogo, cfg):
    """O goal_kick com annotated_frame=77582 (jogo 1) fica dentro da pequena area.

    docs/inspecao-metrica.md §6.3: o `Start Frame` dessas linhas e o ponto da
    interceptacao; ancorado no primeiro quadro em jogo, o executor passa de
    49,55 m para 4,52 m da propria linha de fundo.
    """
    _, gab = eventos(1)
    frames, tracking, periods = jogo(1)
    alvo = gab[(gab["annotated_frame"] == 77582) & (gab["type"] == "goal_kick")]
    assert len(alvo) == 1
    evento = alvo.iloc[0]
    attack_dir = int(
        periods[(periods["period"] == evento["period"]) & (periods["team"] == evento["team"])][
            "attack_dir"
        ].iloc[0]
    )
    linha_de_fundo = -attack_dir * cfg["campo"]["comprimento_m"] / 2
    pos = tracking[
        (tracking["frame"] == evento["frame"]) & (tracking["player_id"] == evento["player_id"])
    ]
    assert len(pos) == 1
    distancia = abs(float(pos["x"].iloc[0]) - linha_de_fundo)
    assert distancia < DISTANCIA_MAX_LINHA_DE_FUNDO_M
    # valor exato medido pelo script independente: pina a ancoragem, nao so o limite
    assert distancia == pytest.approx(DISTANCIA_MEDIDA_77582_M, abs=0.01)
    assert int(evento["anchor_shift"]) == -72


@pytest.mark.parametrize("game", [1, 2, 3])
def test_player_id_existe_no_tracking(eventos, jogo, game):
    _, gab = eventos(game)
    ids_tracking = set(jogo(game)[1]["player_id"].unique())
    assert set(gab["player_id"].unique()) <= ids_tracking


@pytest.mark.parametrize("game", [1, 2, 3])
def test_subtipo_ausente_vira_string_vazia(eventos, game):
    """NaN de `Subtype` (jogos 1/2) e `None` de `subtypes` (jogo 3) -> ""."""
    crus, _ = eventos(game)
    assert not crus["metrica_subtype"].isna().any()
    assert (crus["metrica_subtype"] == "").sum() > 0


def test_subtypes_json_aceita_none_dict_e_lista():
    """Plano/briefing: `subtypes` do jogo 3 pode ser None, dict ou lista."""
    assert gabarito._normalizar_subtypes_json(None) == ""
    assert gabarito._normalizar_subtypes_json({"name": "THROW IN"}) == "THROW IN"
    assert (
        gabarito._normalizar_subtypes_json([{"name": "INDIRECT"}, {"name": "FREE KICK"}])
        == "FREE KICK+INDIRECT"
    )


def test_ancorar_sem_quadro_morto():
    """Sem nenhum quadro morto, tudo e no_dead_ball_before."""
    ball_live = np.ones(10, dtype=bool)
    frames, sem_morto = gabarito.ancorar(np.array([1, 5, 10]), ball_live, 250)
    assert frames.tolist() == [1, 5, 10]
    assert sem_morto.all()


def test_ancorar_volta_para_o_inicio_da_sequencia_viva():
    #        frame: 1      2      3      4     5     6
    ball_live = np.array([True, False, False, True, True, True])
    frames, sem_morto = gabarito.ancorar(np.array([1, 4, 5, 6]), ball_live, 250)
    assert frames.tolist() == [1, 4, 4, 4]
    assert sem_morto.tolist() == [True, False, False, False]


def test_ancorar_respeita_a_guarda():
    """Com guarda 2, o salto de 3 quadros nao e aceito e o evento fica no lugar."""
    ball_live = np.array([False, True, True, True, True, True])
    frames, sem_morto = gabarito.ancorar(np.array([3, 5]), ball_live, 2)
    assert frames.tolist() == [2, 5]  # salto de 1 passa, salto de 3 nao
    assert sem_morto.tolist() == [False, True]


def test_ancorar_estoura_se_cair_em_quadro_morto():
    ball_live = np.array([True, False, False, True])
    with pytest.raises(ValueError, match="quadro morto"):
        gabarito.ancorar(np.array([2]), ball_live, 250)


def test_ancorar_estoura_se_sair_da_grade():
    """`annotated_frame` no ultimo quadro, morto: j+1 cai fora. Mensagem limpa."""
    ball_live = np.array([True, True, False])
    with pytest.raises(ValueError, match="fora da grade"):
        gabarito.ancorar(np.array([3]), ball_live, 250)

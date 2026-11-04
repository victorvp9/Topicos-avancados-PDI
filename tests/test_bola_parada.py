"""O detector de bola parada contra os TETOS PREVISTOS do plano 04 §2.

Criterios: docs/fatias/04-plano.md §7.4 e §7.5. Tudo aqui roda no **dado real**.
Os numeros previstos vem de medicao do orquestrador sobre o dado cru, feita
independentemente deste codigo: sao o instrumento para pegar bug por divergencia,
e por isso estao escritos como constante do teste, com a fonte.

Tres divergencias encontradas e registradas AQUI, nao ajustadas no codigo (ver o
relatorio da fatia):

- `kickoff` tem **n = 14** nos jogos 1 e 2 (6 + 8, `docs/inspecao-metrica.md`
  §3.2), nao 13 como diz o §2.1 do plano. A taxa (13/14 = 92,9 %) bate com os
  92 % previstos; o denominador previsto e que esta errado.
- `penalty`: com a caixa QUADRADA do cobrador (correcao do orquestrador de
  2026-11-01, `eps_p2/2` = 1,00 m de meia-largura), o unico penalti anotado
  **deixa de ser detectado** -- o cobrador esta a |y| = 1,478 m da linha da
  marca. Vira perda de revocacao declarada, e tem teste proprio.
- `goal_kick` da **33/38**, nao 34/38. Com `eps_g` = 0,5 m a caixa chega a 6,0 m
  da propria linha de fundo, e tres executores do jogo 2 estao a 6,24, 6,24 e
  6,35 m -- a propria §6.2 da inspecao cita esses casos como "6,2 a 6,4 m", logo
  14/16 e aritmeticamente impossivel com essa caixa.

O teto de gatilho e travado por IGUALDADE, nao pela banda de +-1 do §7.4 do
plano: na revisao de 2026-11-02 a banda aceitava `goal_kick` 34 e `kickoff` 12
quando o medido e 33 e 13 -- banda num teste de contrato e onde numero errado se
esconde.
"""

import copy

import pandas as pd
import pytest

from src import evaluate
from src.events import bola_parada, gatilhos, hierarquia
from src.tau import grade_de_posicoes

# Plano 04 §2.2: transicoes morta -> viva por jogo, e reinicios anotados.
DETECCOES_PREVISTAS = {1: 154, 2: 168, 3: 159}
REINICIOS_PREVISTOS = 296
# Plano 04 §2.2: com minimo de 1 s sobram 312 transicoes e a precisao vai a 94,9 %.
DETECCOES_COM_MINIMO_DE_1_S = 312
# Plano 04 §2.1: revocacao de gatilho dos jogos 1 e 2 somados, (ativa, n), EXATA.
# Medido em 2026-11-04 e conferido contra a revisao de 2026-11-02 (33 e 13).
TETO_DE_GATILHO = {
    "corner_kick": (10, 18),
    "throw_in": (55, 60),
    "goal_kick": (33, 38),   # o plano dizia 34; ver docstring.
    "kickoff": (13, 14),     # o plano diz n = 13; o gabarito tem 14. Ver docstring.
}
JOGOS = (1, 2, 3)
_CACHE = {}


def _detectar(jogo, posse_real, cfg, game, **tolerancias):
    """`detectar` no dado real, memorizado por (jogo, tolerancias trocadas)."""
    chave = (game, tuple(sorted(tolerancias.items())))
    if chave not in _CACHE:
        novo = copy.deepcopy(cfg)
        novo["bola_parada"].update(tolerancias)
        frames, tracking, periods = jogo(game)
        perdas = posse_real(game)["perdas"]
        _CACHE[chave] = bola_parada.detectar(frames, tracking, periods, perdas, novo)
    return _CACHE[chave]


def _todos(jogo, posse_real, cfg, **tolerancias):
    return pd.concat(
        [_detectar(jogo, posse_real, cfg, g, **tolerancias) for g in JOGOS],
        ignore_index=True,
    )


def _gabarito(eventos):
    return pd.concat([eventos(g)[1] for g in JOGOS], ignore_index=True)


def _avaliar(jogo, posse_real, eventos, cfg, **tolerancias):
    det = _todos(jogo, posse_real, cfg, **tolerancias)
    return det, *evaluate.avaliar(
        _gabarito(eventos), bola_parada.para_casador(det), cfg
    )


def _bloco(resultado, criterio, ancora="frame"):
    """As linhas agregadas (`game = 0`) de um criterio e ancora."""
    return resultado[
        (resultado["criterio"] == criterio)
        & (resultado["ancora"] == ancora)
        & (resultado["game"] == 0)
    ].set_index("type")


def test_numero_de_deteccoes_por_jogo(jogo, posse_real, cfg):
    """Nº de deteccoes = nº de transicoes morta -> viva, EXATO (154/168/159)."""
    for game in JOGOS:
        det = _detectar(jogo, posse_real, cfg, game)
        assert len(det) == DETECCOES_PREVISTAS[game]
    assert len(_todos(jogo, posse_real, cfg)) == sum(DETECCOES_PREVISTAS.values())


def test_teto_de_precisao(jogo, posse_real, eventos, cfg):
    """481 deteccoes contra 296 reinicios anotados = 61,5 % de teto."""
    det = _todos(jogo, posse_real, cfg)
    gab = _gabarito(eventos)
    reinicios = gab[gab["type"].isin(cfg["avaliacao"]["grupos"]["bola_parada"])]
    assert len(reinicios) == REINICIOS_PREVISTOS
    assert len(det) == 481
    assert round(100.0 * len(reinicios) / len(det), 1) == 61.5


@pytest.mark.parametrize("tipo", sorted(TETO_DE_GATILHO))
def test_revocacao_de_gatilho_bate_com_o_teto(jogo, eventos, cfg, tipo):
    """JOGOS 1+2. O executor anotado ativa o gatilho do proprio tipo no primeiro
    quadro em jogo? Igualdade exata (ver docstring do modulo).

    Mede a GEOMETRIA contra o gabarito, sem hierarquia, sem posse e sem padrao.
    O denominador e o gabarito inteiro, inclusive os eventos com
    `no_dead_ball_before`: evento nao detectado e perda de revocacao, nunca
    exclusao.
    """
    ativa_previsto, n_previsto = TETO_DE_GATILHO[tipo]
    ativa = n = 0
    for game in (1, 2):
        frames, tracking, periods = jogo(game)
        jogadores, px, py, _, _ = grade_de_posicoes(frames, tracking)
        times = (
            tracking.drop_duplicates("player_id")
            .set_index("player_id")["team"]
            .reindex(jogadores)
            .to_numpy()
        )
        lado = bola_parada.attack_dir_por_jogador(frames, periods, times)
        ativo = gatilhos.ativacoes(px, py, times, lado, cfg)[tipo]
        gab = eventos(game)[1]
        sub = gab[gab["type"] == tipo]
        linha = jogadores.get_indexer(sub["player_id"])
        assert (linha >= 0).all()
        ativa += int(ativo[linha, sub["frame"].to_numpy() - 1].sum())
        n += len(sub)
    assert (ativa, n) == (ativa_previsto, n_previsto), tipo


def test_escanteios_perdidos_caem_em_tiro_livre(jogo, posse_real, eventos, cfg):
    """A matriz de confusao mostra `(corner_kick, free_kick) > 0`.

    So no criterio `vidal_codina`, que **nao casa por tipo**: nele a comparacao
    de tipo E a matriz (S2, p. 3). Em `estrito` e `mills` a celula fora da
    diagonal e impossivel por construcao, porque o casamento exige o mesmo tipo.
    """
    _, _, confusao = _avaliar(jogo, posse_real, eventos, cfg)
    def celula(criterio, gabarito, detectado):
        return int(confusao[
            (confusao["criterio"] == criterio)
            & (confusao["ancora"] == "frame")
            & (confusao["type_gabarito"] == gabarito)
            & (confusao["type_detectado"] == detectado)
        ]["n"].sum())

    assert celula("vidal_codina", "corner_kick", "free_kick") > 0
    assert celula("estrito", "corner_kick", "free_kick") == 0


def test_os_13_no_dead_ball_before_ficam_no_denominador(jogo, posse_real, eventos, cfg):
    """Evento nao detectado e perda de revocacao, nunca exclusao: os 13 eventos
    com `no_dead_ball_before` contam no `n_gabarito`."""
    gab = _gabarito(eventos)
    tipos = cfg["avaliacao"]["grupos"]["bola_parada"]
    sem_ancora = gab[gab["no_dead_ball_before"] & gab["type"].isin(tipos)]
    assert len(sem_ancora) == 13
    _, resultado, _ = _avaliar(jogo, posse_real, eventos, cfg)
    bloco = _bloco(resultado, cfg["avaliacao"]["criterio_principal"])
    assert int(bloco.loc[tipos, "n_gabarito"].sum()) == REINICIOS_PREVISTOS


def test_free_kick_duvida_e_categoria_propria(jogo, posse_real, eventos, cfg):
    """`free_kick?` tem linha propria, com `n_gabarito = 0`, e NUNCA e somado em
    `free_kick`: a soma das duas colunas de deteccao bate com a contagem crua."""
    det, resultado, _ = _avaliar(jogo, posse_real, eventos, cfg)
    bloco = _bloco(resultado, cfg["avaliacao"]["criterio_principal"])
    duvida = bloco.loc[hierarquia.FREE_KICK_DUVIDA]
    assert duvida["n_gabarito"] == 0
    assert duvida["tp_diag"] == 0
    assert duvida["n_detectado"] == int((det["type"] == "free_kick?").sum())
    assert bloco.loc["free_kick", "n_detectado"] == int(
        (det["type"] == "free_kick").sum()
    )
    assert duvida["n_detectado"] > 0           # o algoritmo se confunde, e conta


def test_penalty_nao_e_detectado_e_isso_e_perda_de_revocacao(jogo, posse_real,
                                                             eventos, cfg):
    """O penalti anotado (jogo 2, quadro 115009) **nao e detectado**, e isso e
    perda de revocacao declarada, nunca exclusao.

    Motivo medido: a caixa do cobrador e QUADRADA (§2.3.4, p. 6), meia-largura
    `eps_p2/2` = 1,00 m, e o cobrador anotado esta a **|y| = 1,478 m** da linha
    da marca no ultimo quadro morto (1,449 m no primeiro quadro em jogo). A
    condicao 2 da Lei 14 falha por 0,48 m. Com a caixa errada de meia-largura
    `eps_p2` = 2,00 m, que esta fatia usou antes da correcao do orquestrador em
    2026-11-01, ele era detectado.

    O evento continua no denominador com `n_gabarito = 1`, e `micro()` continua
    levantando se receber `penalty`.
    """
    det = _todos(jogo, posse_real, cfg)
    assert int((det["type"] == "penalty").sum()) == 0
    _, resultado, _ = _avaliar(jogo, posse_real, eventos, cfg)
    bloco_p = _bloco(resultado, cfg["avaliacao"]["criterio_principal"]).loc["penalty"]
    assert bloco_p["n_gabarito"] == 1 and bloco_p["n_detectado"] == 0
    assert bloco_p["fn"] == 1 and bloco_p["tp_diag"] == 0
    bloco = _bloco(resultado, cfg["avaliacao"]["criterio_principal"]).reset_index()
    # a guarda do agregado vale mesmo com n_detectado = 0: a classe existe
    with pytest.raises(ValueError):
        evaluate.micro(bloco[bloco["type"].isin(["penalty", "throw_in"])])
    evaluate.micro(bloco[bloco["type"] != "penalty"])


def test_sensibilidade_da_duracao_minima(jogo, posse_real, eventos, cfg):
    """Com minimo de 1 s: 312 deteccoes nos tres jogos e precisao ~94,9 %.

    O principal NAO aplica minimo (plano §3.1); este e o teste da variante
    declarada. O corte e INCLUSIVO (`dur >= 1 s`), e e o que reproduz os 312.
    """
    minimos = cfg["bola_parada"]["sensibilidade_duracao_minima_s"]
    assert minimos == [0.0, 1.0]
    det = _todos(jogo, posse_real, cfg, duracao_minima_morta_s=1.0)
    assert len(det) == DETECCOES_COM_MINIMO_DE_1_S
    assert (det["dur_morta_s"] >= 1.0).all()
    assert round(100.0 * REINICIOS_PREVISTOS / len(det), 1) == 94.9
    # e o minimo e de fato um parametro: 0,0 devolve as 481
    assert len(_todos(jogo, posse_real, cfg, duracao_minima_morta_s=0.0)) == 481


def test_sensibilidade_goal_kick_no_problema_3(jogo, posse_real, eventos, cfg):
    """DADO REAL, TRES JOGOS. A leitura `antes_de_cto` contra `nao`: muda a
    saida, e muda SO onde pode mudar.

    A Fig. S1 foi LIDA (revisao de 2026-11-02, rotulos do stream da pagina 2):
    o problema 3 e `K P C T Ci Ti G F?`, logo o padrao e `depois_de_cto`. As
    outras duas leituras (`nao`, a prosa que omite o `G`, e `antes_de_cto`)
    seguem implementadas e medidas. Este teste compara as leituras PELA CHAVE e
    so depende do padrao na primeira assercao.

    O que trava: `antes_de_cto` **nao** cria nem destroi deteccao (seguem 481),
    **nao** toca pontape inicial nem tiro livre, e so pode mover rotulo PARA
    `goal_kick` -- nunca o contrario, porque a leitura so insere um tipo na
    ordem do problema 3. E nao compra acerto nenhum: o tiro de meta e o unico
    gatilho que um jogador ocupa o tempo todo (o goleiro mora na propria
    pequena area), logo ele fica completo em quase todo intervalo morto e,
    posto antes de escanteio e lateral, engole os dois.
    """
    assert cfg["bola_parada"]["goal_kick_no_problema_3"] == "depois_de_cto"
    nao = _todos(jogo, posse_real, cfg, goal_kick_no_problema_3="nao")
    antes = _todos(jogo, posse_real, cfg, goal_kick_no_problema_3="antes_de_cto")
    assert len(antes) == len(nao) == 481
    mudou = nao["type"].to_numpy() != antes["type"].to_numpy()
    assert mudou.any()
    # a leitura so pode mover rotulo que o problema 3 decidiu, e so para goal_kick
    assert set(antes.loc[mudou, "type"]) == {"goal_kick"}
    assert set(nao.loc[mudou, "type"]) <= {
        hierarquia.FREE_KICK_DUVIDA, "corner_kick", "throw_in"
    }
    assert (antes.loc[mudou, "via"] == "reserva_3").all()
    for tipo in ("kickoff", "free_kick"):
        assert int((nao["type"] == tipo).sum()) == int((antes["type"] == tipo).sum())
    # mais deteccoes de tiro de meta e NENHUM acerto novo
    _, res_n, _ = _avaliar(jogo, posse_real, eventos, cfg,
                           goal_kick_no_problema_3="nao")
    _, res_a, _ = _avaliar(jogo, posse_real, eventos, cfg,
                           goal_kick_no_problema_3="antes_de_cto")
    linha_n = _bloco(res_n, cfg["avaliacao"]["criterio_principal"]).loc["goal_kick"]
    linha_a = _bloco(res_a, cfg["avaliacao"]["criterio_principal"]).loc["goal_kick"]
    assert linha_a["n_detectado"] > linha_n["n_detectado"]
    assert linha_a["tp_diag"] <= linha_n["tp_diag"]
    for tabela in (nao, antes):
        assert set(tabela["via"]) <= set(hierarquia.VIAS)
        assert int((tabela["via"] == "reserva_2").sum()) == 0
        assert int(tabela["via"].value_counts().sum()) == 481


def test_goal_kick_depois_de_cto_micro_igual_f1_por_tipo_muda(jogo, posse_real,
                                                              eventos, cfg):
    """DADO REAL, TRES JOGOS. `depois_de_cto` (a figura, padrao) contra `nao`
    (a prosa): **o micro e identico, o F1 de tiro de meta NAO**.

    `free_kick?` tem `n_gabarito` = 0, logo toda deteccao dele ja e falso
    positivo; mover 71 delas para `goal_kick` nao cria nem destroi acerto nem
    muda o numero de deteccoes -- o micro e o mesmo por construcao. Mas a
    precisao de tiro de meta se dilui, e o entregavel e o F1 POR TIPO.

    Medido em 2026-11-04 (relatorio da rodada de correcao da Fatia 4; criterio
    principal, tres jogos): micro de bola parada F1 0,598, `tp_diag` 232 e 481
    deteccoes nas duas; F1 de `goal_kick` 0,649 (`nao`, 36/62) contra 0,396
    (`depois_de_cto`, 36/133). O teste trava a igualdade do micro e o sentido
    da queda, nao os valores.
    """
    nao = _todos(jogo, posse_real, cfg, goal_kick_no_problema_3="nao")
    depois = _todos(jogo, posse_real, cfg, goal_kick_no_problema_3="depois_de_cto")
    assert len(nao) == len(depois) == 481
    mudou = nao["type"].to_numpy() != depois["type"].to_numpy()
    assert set(nao.loc[mudou, "type"]) == {hierarquia.FREE_KICK_DUVIDA}
    assert set(depois.loc[mudou, "type"]) == {"goal_kick"}
    for tipo in ("kickoff", "corner_kick", "throw_in", "free_kick"):
        assert int((nao["type"] == tipo).sum()) == int(
            (depois["type"] == tipo).sum()
        ), tipo
    _, res_n, _ = _avaliar(jogo, posse_real, eventos, cfg,
                           goal_kick_no_problema_3="nao")
    _, res_d, _ = _avaliar(jogo, posse_real, eventos, cfg,
                           goal_kick_no_problema_3="depois_de_cto")
    principal = cfg["avaliacao"]["criterio_principal"]
    bloco_n = _bloco(res_n, principal).reset_index()
    bloco_d = _bloco(res_d, principal).reset_index()
    # micro de bola parada igual: mesmo tp_diag, n_detectado e n_gabarito.
    # `penalty` fica fora: n = 1, fora de todo agregado, e `micro()` levanta.
    grupo = [t for t in cfg["avaliacao"]["grupos"]["bola_parada"] if t != "penalty"]
    micro_n = evaluate.micro(bloco_n[bloco_n["type"].isin(grupo)])
    micro_d = evaluate.micro(bloco_d[bloco_d["type"].isin(grupo)])
    assert micro_n == micro_d
    # por tipo muda: mesmo acerto de tiro de meta, mais deteccao, F1 menor
    linha_n = _bloco(res_n, principal).loc["goal_kick"]
    linha_d = _bloco(res_d, principal).loc["goal_kick"]
    assert linha_d["tp_diag"] == linha_n["tp_diag"]
    assert linha_d["n_detectado"] > linha_n["n_detectado"]
    assert linha_d["f1"] < linha_n["f1"]


def test_via_quantifica_a_reserva(jogo, posse_real, cfg):
    """A distribuicao de `via` e o analogo dos 85 % -> 95 % do S1.

    Nao fixo os valores (nao sao teto previsto do plano); fixo o que seria BUG:
    toda deteccao tem `via` valida, a principal decide uma parte e a reserva
    decide outra parte -- se uma das duas fosse zero, ou a reserva estaria morta
    ou a principal nunca confirmaria padrao. `reserva_2` NAO aparece no dado
    real, porque ninguem deixa de ser rastreado na Metrica (ela tem teste
    sintetico proprio em `test_reserva_s1.py`).
    """
    det = _todos(jogo, posse_real, cfg)
    contagem = det["via"].value_counts()
    assert set(contagem.index) <= set(hierarquia.VIAS)
    assert contagem.get("padrao", 0) > 0
    assert contagem.get("reserva_1", 0) + contagem.get("reserva_3", 0) > 0
    assert contagem.get("reserva_2", 0) == 0
    assert int(contagem.sum()) == 481


def test_nan_nunca_conta_como_acerto(jogo, posse_real, eventos, cfg):
    """`NaN` nunca conta como acerto nem e descartado (plano §7.5).

    No dado real a bola e `NaN` em 32 a 41 % dos quadros e o executor pode nao
    ter dado no quadro anotado. O que nao pode acontecer: deteccao com `t` ou
    `frame` invalido, par casado com `|dt|` indefinido, e identidade de contagem
    quebrada.
    """
    det, resultado, _ = _avaliar(jogo, posse_real, eventos, cfg)
    assert det["t"].notna().all()
    assert (det["frame"] > 0).all()
    assert det["dur_morta_s"].notna().all()
    for criterio in cfg["avaliacao"]["criterios"]:
        bloco = _bloco(resultado, criterio)
        # identidades do esquema: tp_diag + fp = n_detectado e tp_diag + fn = n_gabarito
        assert (bloco["tp_diag"] + bloco["fp"] == bloco["n_detectado"]).all()
        assert (bloco["tp_diag"] + bloco["fn"] == bloco["n_gabarito"]).all()
        assert (bloco["tp_diag"] <= bloco["tp"]).all()

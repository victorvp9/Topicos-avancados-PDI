"""Orquestra o Passo 2 e emite a tabela de deteccoes de bola parada.

**Uma deteccao por transicao morta -> viva** (§2.4.1, p. 7). Nenhuma transicao
fica sem deteccao e nenhuma deteccao e inventada: o numero de linhas e
exatamente o numero de transicoes, e isso tem teste no dado real dos tres jogos.

Ordem interna: gatilhos no intervalo morto -> padrao no primeiro quadro em jogo
-> hierarquia principal -> hierarquia de reserva do S1. A geometria toda e
vetorizada sobre `(jogador, quadro)`; **o unico laco e sobre os intervalos
mortos** (~160 por jogo), onde mora a logica da hierarquia.

Esquema `DETECCOES`: o dominio de `src.evaluate.DETECTIONS` (plano 02 §5) mais
as colunas de auditoria do plano 04 §5. `para_casador` projeta no esquema que o
casador da Fatia 2 consome.

Nenhuma constante aqui. As tolerancias vem de `config.yaml:bola_parada`, a
geometria do campo de `config.yaml:campo` e o `R_pz` do padrao de
`config.yaml:posse`.
"""

import numpy as np
import pandas as pd

from src.events import gatilhos, hierarquia, padroes
from src.evaluate import DETECTIONS
from src.io.schema import validar
from src.tau import grade_de_posicoes

# Uma linha por transicao morta -> viva. `frame` e o PRIMEIRO QUADRO EM JOGO,
# que e tambem onde o gabarito de bola parada esta ancorado (Fatia 1).
# `player_id` e `team` ficam vazios so em `free_kick?`, que por definicao nao
# tem executor identificado.
DETECCOES = {
    "game": "int64",
    "period": "int64",
    "frame": "int64",
    "t": "float64",
    "type": "str",
    "team": "str",
    "player_id": "str",
    "dead_run_id": "int64",
    "dur_morta_s": "float64",
    "via": "str",
    "gatilhos_completos": "str",
    "gatilhos_incompletos": "str",
    "motivo_reserva1": "str",
}

# Valores de `motivo_reserva1`: o estado do PORTAO do problema 1 do S1 nesta
# transicao, independente de a principal ter decidido antes. Pedido na revisao
# de 2026-11-02 para que a decomposicao das decisoes por causa seja auditavel na
# propria tabela, em vez de recalculada no relatorio.
MOTIVOS = (
    "confirmado",              # anda <= eps_f ate o proprio passe: e o executor
    "anda_mais_que_eps_f",     # anda mais: nao e o executor, cai no problema 3
    "sem_passe_do_executor",   # nao passa a bola na corrida viva: ver `detectar`
    "sem_padrao_de_tiro_livre",  # a bola nao esta na PZ de ninguem em `f1`
)


def corridas_mortas(ball_live: np.ndarray):
    """Segmenta a serie em corridas de bola MORTA contiguas.

    Entrada: `ball_live` (n_quadros,) booleano, na ordem do quadro.
    Saida: (`d0`, `dc`, `dead_run_id`), indices 0-based do primeiro e do ultimo
    quadro morto de cada corrida que tem **transicao morta -> viva**, isto e que
    e seguida por um quadro vivo, e o id 1-based da corrida entre TODAS as
    corridas mortas (a ultima do jogo, sem transicao, consome um id e nao gera
    deteccao).

    Corrida morta que termina no ultimo quadro do jogo nao tem transicao, logo
    nao gera deteccao -- nao ha primeiro quadro em jogo para ela.
    """
    morta = ~np.asarray(ball_live, dtype=bool)
    inicio = morta & ~np.r_[False, morta[:-1]]
    fim = morta & ~np.r_[morta[1:], False]
    d0 = np.flatnonzero(inicio)
    dc = np.flatnonzero(fim)
    ids = np.arange(1, d0.size + 1, dtype="int64")
    tem_transicao = dc + 1 < morta.size
    return d0[tem_transicao], dc[tem_transicao], ids[tem_transicao]


def attack_dir_por_jogador(frames, periods, times: np.ndarray) -> np.ndarray:
    """`attack_dir` (n_jogadores, n_quadros), de `periods` por (periodo, time).

    Ignorar isto trocaria de lado o canto ativo e a propria pequena area; ha
    teste que roda com o jogador no vertice do lado errado.
    """
    period = frames["period"].to_numpy()
    nomes = sorted(set(times))
    por_time = np.empty((len(nomes), period.size), dtype="int8")
    for i, time in enumerate(nomes):
        tabela = periods[periods["team"] == time].set_index("period")["attack_dir"]
        valores = tabela.reindex(period)
        if valores.isna().any():
            raise ValueError(
                "periods: falta attack_dir de algum (periodo, time={})".format(time)
            )
        por_time[i] = valores.to_numpy()
    indice = np.searchsorted(np.asarray(nomes), times)
    return por_time[indice]


def _reduzir_por_corrida(mascara: np.ndarray, d0, dc) -> tuple:
    """(ativo em algum quadro da corrida, ultimo quadro ativo) por corrida.

    Entrada: `mascara` (n_jogadores, n_quadros) e os limites das corridas.
    Saida: duas matrizes (n_jogadores, n_corridas); `ultimo` vale -1 onde o
    jogador nunca ativou o gatilho naquela corrida.
    """
    bordas = np.empty(2 * d0.size, dtype="int64")
    bordas[0::2] = d0
    bordas[1::2] = dc + 1   # `dc + 1` e o primeiro quadro em jogo, logo existe
    idx = np.arange(mascara.shape[1], dtype="int32")
    em_algum = np.logical_or.reduceat(mascara, bordas, axis=1)[:, 0::2]
    ultimo = np.maximum.reduceat(
        np.where(mascara, idx, np.int32(-1)), bordas, axis=1
    )[:, 0::2]
    return em_algum, ultimo


def _fim_da_corrida_viva(morta: np.ndarray, f1: np.ndarray) -> np.ndarray:
    """Ultimo quadro vivo da corrida viva que comeca em cada `f1`."""
    mortos = np.flatnonzero(morta)
    k = np.searchsorted(mortos, f1, side="left")
    return np.where(
        k < mortos.size, mortos[np.minimum(k, max(mortos.size - 1, 0))] - 1, morta.size - 1
    )


def _primeiro_passe(passes, jogadores, executor, f1, fim_vivo, n_quadros: int):
    """Primeiro passe DO EXECUTOR PUTATIVO depois de `f1`, na mesma corrida viva.

    Entrada: `passes` com `player_id` e `frame` (1-based); `executor` o indice do
    jogador que ativou o padrao de tiro livre em cada corrida.
    Saida: (`fp`, `tem_passe`), com `fp` o indice 0-based do quadro do passe
    (ou `f1` onde nao ha passe, valor que `tem_passe` invalida).

    **Quem passa e o putativo executor**, nao qualquer jogador: o S1, p. 1, diz
    *"activated by a player that does not move more than eps_f before the ball
    is passed"* -- o deslocamento medido e o dele, ate o passe dele. Corrigido
    pelo orquestrador em 2026-11-01; a versao anterior usava o primeiro passe de
    qualquer jogador, o que fazia a janela variar por motivo alheio a regra.

    A busca e uma `searchsorted` sobre a chave `jogador * (n_quadros + 1) +
    quadro`, que ordena por (jogador, quadro) de uma vez; o sentinela no fim
    garante indice valido, e a conferencia do jogador decodificado garante que
    nao se pegou o passe do jogador seguinte.

    **[LACUNA] Executor que nao passa a bola.** O S1 nao diz o que fazer quando
    o jogador do padrao de tiro livre nunca passa na corrida viva. Decisao: ele
    **nao e confirmado** e o caso cai no problema 3. Justificativa normativa,
    acrescentada na revisao de 2026-11-02: o S2, p. 3, define *"Set piece events
    are **passing events** that resume the game"* -- quem nao passa nao
    reinicia o jogo. Medido: a lacuna vale **14 acertos** e responde por uma
    parte grande dos `free_kick?`; tratar "sem passe" como "nao se deslocou"
    daria micro 0,634 em vez de 0,598. **Nao foi mudada** justamente porque o
    numero ja era conhecido: mudar depois de ver +14 acertos seria ajuste por
    resultado. A decomposicao por causa sai em `motivo_reserva1` e no bloco 3 de
    `python -m src.run --bola-parada`.

    **Consequencia declarada: isto ACOPLA a deteccao de bola parada a revocacao
    de perda do Passo 1.** "Sem passe do executor" depende de o Passo 1 ter
    emitido perda para aquele jogador, e isso muda com `R_pz`. Logo, na
    varredura da Fatia 8, parte da variacao da curva de bola parada vem da
    deteccao de passe, nao da geometria do gatilho -- confundimento no mesmo
    espirito do que a Fatia 3 achou com `R_dz`.
    """
    indice = jogadores.get_indexer(passes["player_id"])
    quadro = np.asarray(passes["frame"], dtype="int64") - 1
    # Jogador fora do tracking nao tem posicao e nao pode ser executor.
    valido = indice >= 0
    chaves = np.r_[
        np.sort(indice[valido] * (n_quadros + 1) + quadro[valido]),
        jogadores.size * (n_quadros + 1),           # sentinela
    ]
    achado = chaves[np.searchsorted(chaves, executor * (n_quadros + 1) + f1, "left")]
    fp = achado % (n_quadros + 1)
    tem_passe = (achado // (n_quadros + 1) == executor) & (fp <= fim_vivo)
    return np.where(tem_passe, fp, f1), tem_passe


def detectar(frames, tracking, periods, passes, cfg: dict):
    """Detecta uma bola parada por transicao morta -> viva.

    Entrada:
      `frames`, `tracking`, `periods`  de `src.io.carregar_jogo`;
      `passes`            DataFrame com `player_id` e `frame` (1-based) dos
                          passes detectados, isto e
                          `possession.calcular(...)['perdas']` -- passe = toda
                          perda de posse (§2.4.3, p. 9). O chamador decide se
                          filtra `so_por_lacuna_5` (plano 04 §3.6.1); so o
                          problema 1 do S1 usa isto;
      `cfg`               de `src.config.carregar_config`.
    Saida: DataFrame no esquema `DETECCOES` deste modulo, uma linha por
    transicao com `dur_morta_s >= bola_parada.duracao_minima_morta_s`.

    O minimo de duracao e NOSSO e vale 0,0 no principal (plano 04 §3.1): o
    §2.3.4, p. 6, sinaliza bola morta pela ausencia de dado da bola, mas o S1,
    p. 1, reconhece que a bola falta tambem **com o jogo em andamento**
    (problema 2 dele) e nao da regra para separar os dois casos.
    """
    p = cfg["bola_parada"]
    game = int(frames["game"].iloc[0])
    fps = cfg["tracking"]["fps"]
    jogadores, px, py, ball_x, ball_y = grade_de_posicoes(frames, tracking)
    nomes = np.asarray(jogadores, dtype=object)
    times = (
        tracking.drop_duplicates("player_id")
        .set_index("player_id")["team"]
        .reindex(jogadores)
        .to_numpy()
    )
    lado = attack_dir_por_jogador(frames, periods, times)

    morta = ~frames["ball_live"].to_numpy()
    d0, dc, ids = corridas_mortas(~morta)
    dur = (dc - d0 + 1) / fps
    longa = dur >= p["duracao_minima_morta_s"]
    d0, dc, ids, dur = d0[longa], dc[longa], ids[longa], dur[longa]
    f1 = dc + 1                      # primeiro quadro em jogo
    n_corridas = f1.size
    linhas = np.arange(jogadores.size)[:, None]

    # --- gatilhos, no intervalo morto ------------------------------------
    ativo = gatilhos.ativacoes(px, py, times, lado, cfg)
    presentes = np.cumsum(~np.isnan(px), axis=1, dtype="int32")
    completo, incompleto, ausente_apos, d_geom_dc, d_geom_ultimo = {}, {}, {}, {}, {}
    ref_dc = gatilhos.distancias_de_referencia(
        px[:, dc], py[:, dc], lado[:, dc], cfg
    )
    for tipo in gatilhos.TIPOS:
        em_algum, ultimo = _reduzir_por_corrida(ativo[tipo], d0, dc)
        completo[tipo] = ativo[tipo][:, dc]
        incompleto[tipo] = em_algum & ~completo[tipo]
        # Problema 2 do S1: o jogador que ativava deixou de ser DETECTADO em
        # `(ultimo ativo, dc]`. Nenhum quadro com dado naquele intervalo.
        col = np.maximum(ultimo, 0)
        ausente_apos[tipo] = (presentes[:, dc] - presentes[linhas, col]) == 0
        d_geom_dc[tipo] = ref_dc[tipo]
        d_geom_ultimo[tipo] = gatilhos.distancias_de_referencia(
            px[linhas, col], py[linhas, col], lado[linhas, col], cfg
        )[tipo]

    # --- padrao, no primeiro quadro em jogo -------------------------------
    d_bola = padroes.distancia_bola(px[:, f1], py[:, f1], ball_x[f1], ball_y[f1])
    na_pz = padroes.na_pz(d_bola, cfg)
    zona_padrao = padroes.zonas_padrao(px[:, f1], py[:, f1], lado[:, f1], cfg)

    # --- problema 1 do S1: o executor do padrao de tiro livre -------------
    # O proprio padrao de tiro livre: a bola na PZ de alguem, o mais proximo.
    candidato = np.where(na_pz, d_bola, np.inf)
    exec0 = candidato.argmin(axis=0)
    tem_exec0 = np.isfinite(candidato[exec0, np.arange(n_corridas)])
    # O primeiro passe depois da bola morta, DENTRO da corrida viva que comeca
    # em `f1`: passe de outra corrida viva ja esta depois de outra bola morta.
    fim_vivo = _fim_da_corrida_viva(morta, f1)
    fp, tem_passe = _primeiro_passe(passes, jogadores, exec0, f1, fim_vivo, morta.size)
    desloca = np.hypot(
        px[exec0, fp] - px[exec0, f1], py[exec0, fp] - py[exec0, f1]
    )
    confirmado = tem_exec0 & tem_passe & (desloca <= p["eps_f_m"])
    motivo = np.where(
        ~tem_exec0, "sem_padrao_de_tiro_livre",
        np.where(
            ~tem_passe, "sem_passe_do_executor",
            np.where(confirmado, "confirmado", "anda_mais_que_eps_f"),
        ),
    )
    # Reavaliacao de TODOS os gatilhos e padroes para esse executor, no quadro
    # do passe (S1, p. 1).
    na_pz_fp = padroes.na_pz(
        padroes.distancia_bola(px[exec0, fp], py[exec0, fp], ball_x[fp], ball_y[fp]), cfg
    )
    zona_fp = padroes.zonas_padrao(px[exec0, fp], py[exec0, fp], lado[exec0, fp], cfg)
    reavaliado = np.stack(
        [
            ativo[tipo][exec0, fp] & zona_fp[tipo] & na_pz_fp
            for tipo in gatilhos.TIPOS
        ]
    )
    tem_reavaliado = reavaliado.any(axis=0)
    qual_reavaliado = reavaliado.argmax(axis=0)

    # --- hierarquia, uma decisao por intervalo morto ----------------------
    ordem_3 = hierarquia.ordem_reserva_3(cfg)
    period = frames["period"].to_numpy()
    n_frame = frames["frame"].to_numpy()
    tempo = frames["t"].to_numpy()
    saida = []
    for r in range(n_corridas):
        por_tipo = {
            "completo": {t: completo[t][:, r] for t in gatilhos.TIPOS},
            "incompleto": {t: incompleto[t][:, r] for t in gatilhos.TIPOS},
            "ausente_apos": {t: ausente_apos[t][:, r] for t in gatilhos.TIPOS},
            "zona_padrao": {t: zona_padrao[t][:, r] for t in gatilhos.TIPOS},
            "d_geom_dc": {t: d_geom_dc[t][:, r] for t in gatilhos.TIPOS},
            "d_geom_ultimo": {t: d_geom_ultimo[t][:, r] for t in gatilhos.TIPOS},
        }
        tipo, jogador, via = hierarquia.decidir(
            {
                **por_tipo,
                "na_pz": na_pz[:, r],
                "d_bola": d_bola[:, r],
                "reserva1": {
                    "executor": int(exec0[r]) if tem_exec0[r] else -1,
                    "confirmado": bool(confirmado[r]),
                    "tipo": (
                        gatilhos.TIPOS[qual_reavaliado[r]]
                        if tem_reavaliado[r] else None
                    ),
                },
            },
            ordem_3,
        )
        saida.append(
            (
                game,
                int(period[f1[r]]),
                int(n_frame[f1[r]]),
                float(tempo[f1[r]]),
                tipo,
                str(times[jogador]) if jogador >= 0 else "",
                str(nomes[jogador]) if jogador >= 0 else "",
                int(ids[r]),
                float(dur[r]),
                via,
                hierarquia.rotular(por_tipo["completo"]),
                hierarquia.rotular(por_tipo["incompleto"], por_tipo["completo"]),
                str(motivo[r]),
            )
        )
    deteccoes = pd.DataFrame(saida, columns=list(DETECCOES)).astype(DETECCOES)
    return validar(deteccoes, DETECCOES, "deteccoes(jogo {})".format(game))


def para_casador(deteccoes):
    """Projeta no esquema `src.evaluate.DETECTIONS` que o casador consome."""
    return deteccoes[list(DETECTIONS)].reset_index(drop=True).astype(DETECTIONS)

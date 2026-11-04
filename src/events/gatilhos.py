"""Os seis gatilhos do Passo 2, e so eles.

**Gatilho = configuracao espacial DOS JOGADORES**, avaliada durante o intervalo
de bola morta `[d0, dc]`. **A bola nao entra no gatilho** -- e nao poderia,
porque e justamente a ausencia de dado da bola que sinaliza a bola morta
(Vidal-Codina §2.3.4, p. 6; nosso D1). Quem usa a bola e `padroes`.

Regra normativa: `docs/01-definicoes.md`, Passo 2, "Os gatilhos (§2.3.4, p. 6)".
Nenhuma constante aqui: as tolerancias vem de `config.yaml:bola_parada` e a
geometria de `config.yaml:campo`.

"Ativo" = do lado para o qual o time ataca (§2.3.4, p. 6: *"we shall refer to
the goal a team is attacking as active goal, and analogously for other notable
locations"*). Por isso toda funcao dependente de lado recebe `attack_dir`, que
vem da tabela `periods` da Fatia 1 por (jogo, periodo, time) -- **ignorar
`attack_dir` troca escanteio e tiro de meta de lado**, e ha teste que roda com o
jogador no lado errado.

Convencoes deste modulo:

- as funcoes de zona e de distancia sao **elemento a elemento** e aceitam
  qualquer forma broadcastavel; `NaN` (jogador ausente) devolve `False` em toda
  comparacao, logo jogador sem dado nunca ativa gatilho e nunca viola condicao
  de "todos os jogadores" -- ele simplesmente nao conta (lacuna 3 da Fatia 3:
  `NaN` nunca conta como acerto nem e descartado);
- `gatilho_pontape_inicial` e `gatilho_penalti` tem condicao sobre o CONJUNTO
  dos jogadores, logo exigem forma `(n_jogadores, n_quadros)` e reduzem no
  eixo 0;
- `ativacoes` devolve, por tipo, a mascara `(n_jogadores, n_quadros)` dos
  jogadores que ATIVAM aquele gatilho naquele quadro. O tiro livre nao aparece:
  ele nao tem gatilho (so padrao).
"""

import numpy as np

# Ordem da hierarquia principal (Fig. 5, p. 7, e Fig. S1, p. 2: `K P C T G F`).
# `free_kick` nao esta aqui porque nao tem gatilho.
TIPOS = ("kickoff", "penalty", "corner_kick", "throw_in", "goal_kick")


def dist_marca_central(x, y):
    """Distancia a marca central (origem do sistema interno)."""
    return np.hypot(x, y)


def dist_canto_ativo(x, y, attack_dir, cfg: dict):
    """Distancia a marca de canto ATIVA mais proxima (uma das duas do lado que
    o time ataca).

    As duas marcas ativas sao `(attack_dir * L/2, +-W/2)`; o minimo das duas
    distancias e `hypot(x - attack_dir*L/2, | |y| - W/2 |)`.
    """
    campo = cfg["campo"]
    return np.hypot(
        x - attack_dir * (campo["comprimento_m"] / 2.0),
        np.abs(np.abs(y) - campo["largura_m"] / 2.0),
    )


def dist_linha_lateral(y, cfg: dict):
    """Distancia a linha lateral mais proxima (0 em cima da linha)."""
    return np.abs(cfg["campo"]["largura_m"] / 2.0 - np.abs(y))


def profundidade_propria(x, attack_dir, cfg: dict):
    """Distancia ORIENTADA da propria linha de fundo para dentro do campo.

    0 em cima da linha, positiva para dentro, negativa atras da linha. A linha
    propria e a oposta a que o time ataca: `-attack_dir * L/2`.
    """
    return attack_dir * x + cfg["campo"]["comprimento_m"] / 2.0


def dist_linha_de_fundo_propria(x, attack_dir, cfg: dict):
    """Distancia (nao orientada) a propria linha de fundo."""
    return np.abs(profundidade_propria(x, attack_dir, cfg))


def dist_marca_penal_ativa(x, y, attack_dir, cfg: dict):
    """Distancia a marca penal ATIVA (a do gol que o time ataca)."""
    campo = cfg["campo"]
    marca_x = attack_dir * (campo["comprimento_m"] / 2.0 - campo["marca_penal_m"])
    return np.hypot(x - marca_x, y)


def zona_escanteio(x, y, attack_dir, cfg: dict):
    """Lei 17: a `eps_c` de uma das marcas de canto ATIVAS."""
    return dist_canto_ativo(x, y, attack_dir, cfg) <= cfg["bola_parada"]["eps_c_m"]


def zona_lateral(y, cfg: dict):
    """Lei 15: alem da linha lateral auxiliar, isto e `|y| >= W/2 - eps_t`."""
    campo = cfg["campo"]
    return np.abs(y) >= campo["largura_m"] / 2.0 - cfg["bola_parada"]["eps_t_m"]


def zona_tiro_de_meta(x, y, attack_dir, cfg: dict):
    """Lei 16: dentro da PROPRIA pequena area, caixa de tolerancia `eps_g`.

    A caixa e o retangulo da pequena area inflado por `eps_g` nos quatro lados,
    inclusive para TRAS da linha de fundo (o jogador recortado em x < -52,5 m
    conta se estiver a menos de `eps_g` da linha). `eps_g` existe para acomodar
    regra nao cumprida, nao so ruido: S4.2, p. 7, cita *"a goal kick pass from
    beyond the goal area"*.

    ATENCAO (V14): o §2.3.4, p. 6, escreve `eps_c` aqui por erro de digitacao;
    vale a Fig. 4, p. 6, e o S4.2: a tolerancia e `eps_g`.

    **PREVISAO PRE-REGISTRADA PARA A FATIA 6, antes de o simulador existir**
    (`docs/decisoes.md`, 2026-11-01): este e o unico gatilho que um jogador
    ocupa o tempo todo -- o goleiro mora na propria pequena area --, e foi isso
    que a medicao da ambiguidade do problema 3 mostrou (a leitura
    `goal_kick_no_problema_3: antes_de_cto` da +77 deteccoes e zero acertos). O Bassek mediu
    que **o goleiro e o jogador MENOS visivel em video de TV: 14 % da distancia
    percorrida, contra 40 a 52 % dos jogadores de linha**. Logo o simulador vai
    remover o goleiro mais que qualquer outro e **a deteccao de tiro de meta
    deve colapsar sob degradacao**, por um motivo especifico: o gatilho depende
    de um jogador que a camera de broadcast quase nao mostra. Nada da Fatia 6
    esta implementado aqui.
    """
    campo = cfg["campo"]
    eps = cfg["bola_parada"]["eps_g_m"]
    dentro = profundidade_propria(x, attack_dir, cfg)
    return (
        (dentro >= -eps)
        & (dentro <= campo["pequena_area_profundidade_m"] + eps)
        & (np.abs(y) <= campo["pequena_area_meia_largura_m"] + eps)
    )


def zona_marca_central(x, y, cfg: dict):
    """Lei 8, segunda condicao: a `eps_k2` da marca central."""
    return dist_marca_central(x, y) <= cfg["bola_parada"]["eps_k2_m"]


def zona_cobrador_penalti(x, y, attack_dir, cfg: dict):
    """Lei 14: a caixa do cobrador em torno da marca penal ATIVA.

    `eps_p2/4` a frente (para o gol ativo) a `3*eps_p2/4` atras da marca
    (`docs/01-definicoes.md`, Passo 2).

    A caixa e **QUADRADA**: o §2.3.4, p. 6, diz *"only one opponent is within a
    **square** bounding box from `eps_p2/4` in front to `3 eps_p2/4` behind the
    active penalty mark"*. Logo o lado e `eps_p2/4 + 3 eps_p2/4 = eps_p2` e a
    meia-largura em `y` e **`eps_p2/2`**. Corrigido pelo orquestrador em
    2026-11-01, com a citacao; a versao anterior usava `eps_p2` e era 2x larga.
    """
    campo = cfg["campo"]
    eps = cfg["bola_parada"]["eps_p2_m"]
    marca_x = attack_dir * (campo["comprimento_m"] / 2.0 - campo["marca_penal_m"])
    frente = attack_dir * (x - marca_x)
    return (
        (frente <= eps / 4.0) & (frente >= -3.0 * eps / 4.0) & (np.abs(y) <= eps / 2.0)
    )


def _caixa_linha_de_gol(x, y, attack_dir, cfg: dict):
    """Caixa `eps_p1` sobre a linha do gol ATIVO, entre as traves."""
    campo = cfg["campo"]
    eps = cfg["bola_parada"]["eps_p1_m"]
    return (
        np.abs(x - attack_dir * campo["comprimento_m"] / 2.0) <= eps
    ) & (np.abs(y) <= campo["gol_meia_largura_m"] + eps)


def _dentro_da_grande_area_ativa(x, y, attack_dir, cfg: dict, folga: float):
    """Dentro da grande area ATIVA, ENCOLHIDA por `folga` (tolerancia `eps_p3`).

    **[LACUNA] O sentido da tolerancia `eps_p3`.** O `docs/01-definicoes.md` diz
    que os demais jogadores nao podem estar "nem na area nem a menos de 9,15 m
    da marca (tolerancia `eps_p3`)", sem dizer para que lado a tolerancia
    afrouxa. Leitura adotada: ela **encolhe a zona proibida** -- o jogador so
    viola se estiver mais de `eps_p3` dentro da area, e o raio proibido cai de
    9,15 m para 9,15 - `eps_p3`. E a leitura que faz `eps_p3` ser tolerancia (e
    nao exigencia extra), coerente com as outras cinco.

    **Peso medido**: com `eps_p3` = 8 m o penalti do jogo 2 passa a ser
    detectado; com os 4 m congelados, nao. Marcado como lacuna na revisao de
    2026-11-02 por carregar esse peso. Efeito confinado ao penalti (n = 1, fora
    de todo agregado).
    """
    campo = cfg["campo"]
    dentro = campo["comprimento_m"] / 2.0 - attack_dir * x   # 0 na linha de gol ativa
    return (
        (dentro >= 0.0)
        & (dentro <= campo["grande_area_profundidade_m"] - folga)
        & (np.abs(y) <= campo["grande_area_meia_largura_m"] - folga)
    )


def gatilho_pontape_inicial(x, y, attack_dir, cfg: dict):
    """Lei 8: todos na propria metade (tolerancia `eps_k1`) **e** >= 1 jogador a
    `eps_k2` da marca central.

    Entrada `(n_jogadores, n_quadros)`. Saida: mascara dos jogadores que ativam
    o gatilho, isto e os que estao a `eps_k2` do centro nos quadros em que
    ninguem invadiu a metade adversaria por mais de `eps_k1`.

    Jogador ausente (`NaN`) nao invade: `NaN > eps_k1` e `False`.
    """
    invasao = attack_dir * x
    sem_invasao = ~np.any(invasao > cfg["bola_parada"]["eps_k1_m"], axis=0)
    return zona_marca_central(x, y, cfg) & sem_invasao[None, :]


def gatilho_penalti(x, y, times: np.ndarray, attack_dir, cfg: dict):
    """Lei 14, as tres condicoes, avaliadas para cada time como atacante.

    Entrada `(n_jogadores, n_quadros)`; `times` `(n_jogadores,)`; `attack_dir`
    com a MESMA forma (o lado ativo e o do time atacante, logo a geometria e a
    mesma para os 22 jogadores e nao a de cada um).
    Saida: mascara do COBRADOR -- o unico adversario na caixa da marca --, nos
    quadros em que as tres condicoes valem:

    1. so **1** jogador na linha do gol ativo, entre as traves (caixa `eps_p1`),
       e ele e do time que defende;
    2. so **1** adversario dele na caixa do cobrador (`eps_p2`);
    3. os demais nem na grande area ativa nem a menos de `9,15 m` da marca
       ativa, com tolerancia `eps_p3` nas duas condicoes.

    As duas leituras de time atacante sao avaliadas e combinadas com `|`.
    """
    eps_p3 = cfg["bola_parada"]["eps_p3_m"]
    raio = cfg["campo"]["raio_impedido_penalti_m"]
    attack_dir = np.broadcast_to(attack_dir, x.shape)
    saida = np.zeros(x.shape, dtype=bool)
    for time in np.unique(times):
        do_time = (times == time)[:, None]
        # O lado ativo e o do time ATACANTE, para todos os jogadores.
        lado = attack_dir[np.flatnonzero(times == time)[0]][None, :]
        na_linha = _caixa_linha_de_gol(x, y, lado, cfg)
        cobrador = zona_cobrador_penalti(x, y, lado, cfg) & do_time
        # Condicao 3 vale para "os demais": nem o da linha de gol nem o cobrador.
        proibido = _dentro_da_grande_area_ativa(x, y, lado, cfg, eps_p3) | (
            dist_marca_penal_ativa(x, y, lado, cfg) < raio - eps_p3
        )
        viola = proibido & ~na_linha & ~cobrador
        ok = (
            (na_linha.sum(axis=0) == 1)
            & ((na_linha & ~do_time).sum(axis=0) == 1)
            & (cobrador.sum(axis=0) == 1)
            & ~np.any(viola, axis=0)
        )
        saida |= cobrador & ok[None, :]
    return saida


def ativacoes(px, py, times: np.ndarray, attack_dir, cfg: dict) -> dict:
    """Mascara `(n_jogadores, n_quadros)` por tipo: o jogador ATIVA aquele
    gatilho naquele quadro.

    Entrada: `px`/`py` de `src.tau.grade_de_posicoes` (metros, `NaN` onde o
    jogador nao tem linha), `times` `(n_jogadores,)` e `attack_dir`
    broadcastavel para a mesma forma.

    O tiro livre nao tem gatilho (`docs/01-definicoes.md`, "Tiro livre --
    categoria residual") e por isso nao esta no dict.
    """
    return {
        "kickoff": gatilho_pontape_inicial(px, py, attack_dir, cfg),
        "penalty": gatilho_penalti(px, py, times, attack_dir, cfg),
        "corner_kick": zona_escanteio(px, py, attack_dir, cfg),
        "throw_in": zona_lateral(py, cfg),
        "goal_kick": zona_tiro_de_meta(px, py, attack_dir, cfg),
    }


def distancias_de_referencia(px, py, attack_dir, cfg: dict) -> dict:
    """Distancia de cada jogador a GEOMETRIA DE REFERENCIA de cada gatilho.

    **[LACUNA, plano 04 §3.2]** O S1, p. 2, usa so gatilhos no problema 3 e nao
    diz quem e o executor. Decisao registrada em `decisoes.md` (2026-11-01): o
    jogador do gatilho mais proximo da geometria que DEFINE aquele gatilho --
    marca de canto ativa, linha lateral, propria linha de fundo, marca central,
    marca penal ativa --, pela mesma logica do desempate do §2.4.1, p. 7 ("o
    mais proximo"), aplicada a geometria porque a bola e justamente o que falta.
    """
    return {
        "kickoff": dist_marca_central(px, py),
        "penalty": dist_marca_penal_ativa(px, py, attack_dir, cfg),
        "corner_kick": dist_canto_ativo(px, py, attack_dir, cfg),
        "throw_in": dist_linha_lateral(py, cfg),
        "goal_kick": dist_linha_de_fundo_propria(px, attack_dir, cfg),
    }

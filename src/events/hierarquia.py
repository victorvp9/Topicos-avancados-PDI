"""A hierarquia principal (Fig. 5, p. 7) e a hierarquia de RESERVA do
suplementar S1, que e obrigatoria.

Decide UMA bola parada por transicao morta -> viva. Toda a geometria ja vem
resolvida em mascaras por jogador (`src.events.bola_parada` as monta); aqui so
ha ordem e logica, o que e deliberado: **a ordem e o que erra** e ela tem de
ficar legivel e testavel sozinha.

Principal (§2.4.1, p. 7, e Fig. 5, p. 7):

    pontape inicial -> penalti -> escanteio -> lateral -> tiro de meta -> tiro livre

Um tipo sai pela principal quando um gatilho **completo** (ativo no ultimo
quadro morto `dc`) e **confirmado pelo padrao** no primeiro quadro em jogo.

Reserva (S1, pp. 1-2, e Fig. S1, p. 2), aplicada **so quando nenhum gatilho
completo foi confirmado por padrao**. Sem ela o F1 medio de bola parada do
artigo cai de **95 % para 85 %** (S1, p. 2):

1. **Problema 1 -- booleano fora de sincronia.** O padrao de tiro livre esta
   ativado (a bola esta na PZ de alguem). Se esse jogador **nao se desloca mais
   que `eps_f`** antes de passar a bola, ele e o executor, e **reavalia-se todos
   os gatilhos e padroes para ele** no quadro do primeiro passe depois da bola
   morta. Se a reavaliacao confirma um tipo, e esse tipo; se nao confirma nada,
   o rotulo fica **`free_kick`**, que e a categoria residual.
   Se ele se desloca mais que `eps_f` -- ou se nao ha passe nenhum na corrida
   viva, logo nao se pode medir o deslocamento --, ele **nao** e o executor e o
   caso cai no problema 3.
2. **Problema 2 -- executor nao rastreado.** O padrao de tiro livre **nao** esta
   ativado. Procura-se gatilho de escanteio ou lateral que ficou **incompleto**
   porque o jogador que o ativava deixou de ser detectado em `[di+1, dc]`, e o
   evento e **imputado a esse jogador ausente**.
   **Dormente na Metrica** (22 jogadores com dado em todos os quadros) e acorda
   no simulador da Fatia 6; testado so sinteticamente, e e por isso que o S1 e
   obrigatorio (V10, `decisoes.md`).
3. **Problema 3 -- so gatilhos.** *"We cannot investigate patterns (the ball is
   not close to any player when the game resumes)"* (S1, p. 2). Ordem:
   pontape inicial -> penalti -> **escanteio completo -> lateral completo ->
   escanteio incompleto -> lateral incompleto**; os autores registram
   *"higher detection rate when favoring complete throw-in over incomplete
   corner"* (S1, p. 2). Se nenhum gatilho ativa, o rotulo e **`free_kick?`**,
   que sinaliza confusao do algoritmo (S2, p. 3) e **nunca** e somado em
   `free_kick`.
   **O tiro de meta entra nesta ordem, depois de escanteio e lateral**: os
   rotulos decodificados da Fig. S1 dao `K P C T Ci Ti G F?` no issue 3. A
   prosa omite o `G` e a figura manda; as tres leituras seguem implementadas
   como sensibilidade -- ver `ordem_reserva_3` e
   `config.yaml:bola_parada.goal_kick_no_problema_3`.

**[LACUNA] O que a coluna `via` significa.** O plano 04 §5 pede `via` para medir
"quanto a reserva compra", mas nao define o rotulo caso a caso. Regra adotada,
sem juizo de valor: `via` e **o estagio que decidiu**. `padrao` so quando um
gatilho completo foi confirmado por padrao (a principal); `reserva_1`,
`reserva_2` e `reserva_3` quando quem decidiu foi o problema correspondente do
S1 -- **inclusive quando o rotulo que sai do problema 1 e `free_kick`**, porque
foi o teste de `eps_f` que escolheu o executor. Consequencia declarada: a
contagem de `reserva_1` NAO e "o que a reserva comprou"; o que a reserva compra
e a tabela `via` x `type`, que o relatorio traz inteira.

**[LACUNA] Ordem do problema 2 entre escanteio e lateral.** O S1 nao a fixa.
Uso a da principal (escanteio antes de lateral), que e a unica ordem que o
artigo define entre os dois; nao e invencao nova.
"""

import numpy as np

from src.events import padroes
from src.events.gatilhos import TIPOS

# A principal, incluindo o `else`. `TIPOS` ja esta na ordem `K P C T G`.
ORDEM_PRINCIPAL = TIPOS
FREE_KICK = "free_kick"
# Confusao do algoritmo (S2, p. 3). NUNCA somado em `free_kick` (plano §3.4).
FREE_KICK_DUVIDA = "free_kick?"
# Problema 2: so escanteio e lateral (S1, p. 2).
ORDEM_RESERVA_2 = ("corner_kick", "throw_in")
# Problema 3: completo de escanteio e lateral ANTES do incompleto dos dois.
# Esta e a ordem da PROSA do S1, p. 2 (leitura `nao`), NAO o padrao: o padrao e
# `depois_de_cto` (Fig. S1 lida), e a ordem em uso sai sempre de
# `ordem_reserva_3(cfg)`.
ORDEM_RESERVA_3 = (
    ("kickoff", "completo"),
    ("penalty", "completo"),
    ("corner_kick", "completo"),
    ("throw_in", "completo"),
    ("corner_kick", "incompleto"),
    ("throw_in", "incompleto"),
)
VIAS = ("padrao", "reserva_1", "reserva_2", "reserva_3")
# As tres leituras da posicao do tiro de meta no problema 3. Ver `ordem_reserva_3`.
POSICOES_GOAL_KICK_NO_PROBLEMA_3 = ("nao", "antes_de_cto", "depois_de_cto")


def ordem_reserva_3(cfg: dict) -> tuple:
    """A ordem do problema 3, pela chave `bola_parada.goal_kick_no_problema_3`.

    **A FIGURA S1 FOI LIDA** (revisao de 2026-11-02): os rotulos do lado direito
    da pagina 2 saem dos operadores de texto do stream da pagina, e no issue 3
    a sequencia e **`K P C T Ci Ti G F?`** -- tiro de meta **depois** de
    escanteio e lateral (completos e incompletos) e **antes** de `free_kick?`.
    O `G` que parecia aparecer duas vezes era o no de checagem e o no de saida
    da mesma coluna.

    A **prosa** do S1, p. 2, omite o `G` ao listar o problema 3, mas ela remete
    a *"the dead ball hierarchy **shown in** issue 3 of Fig. S1"*: a figura e o
    artefato normativo e a prosa e o resumo. Por isso o padrao e
    `depois_de_cto` desde 2026-11-02 -- **correcao de leitura, nao ajuste por
    resultado**: ela derruba o F1 de tiro de meta de 0,649 para 0,396 e deixa o
    micro igual (0,598).

    As tres leituras seguem implementadas e medidas (bloco 8 de
    `python -m src.run --bola-parada`), no padrao das duas politicas de `R_dz`
    (Fatia 3) e do minimo de duracao de bola morta (plano 04 §3.1):

      `depois_de_cto`  K P C/T completo C/T incompleto **G**. A figura, PADRAO;
      `nao`            K P C/T completo C/T incompleto. A prosa;
      `antes_de_cto`   K P **G** C/T completo C/T incompleto.

    **Valor desconhecido estoura**: nao ha ordem padrao silenciosa.
    """
    posicao = cfg["bola_parada"]["goal_kick_no_problema_3"]
    tiro_de_meta = (("goal_kick", "completo"),)
    if posicao == "nao":
        return ORDEM_RESERVA_3
    if posicao == "antes_de_cto":
        return ORDEM_RESERVA_3[:2] + tiro_de_meta + ORDEM_RESERVA_3[2:]
    if posicao == "depois_de_cto":
        return ORDEM_RESERVA_3 + tiro_de_meta
    raise ValueError(
        "bola_parada.goal_kick_no_problema_3 {!r} fora de {}".format(
            posicao, POSICOES_GOAL_KICK_NO_PROBLEMA_3
        )
    )


def decidir(estado: dict, ordem_3: tuple) -> tuple:
    """Decide `(type, jogador, via)` de uma transicao morta -> viva.

    `ordem_3` e a ordem do problema 3, que sai de `ordem_reserva_3(cfg)`.
    **Obrigatorio, sem valor padrao**: um padrao aqui seria a ordem silenciosa
    que `ordem_reserva_3` proibe.

    Entrada: dict com, por jogador (arrays `(n_jogadores,)` booleanos ou de
    distancia, montados em `src.events.bola_parada`):

      `completo[tipo]`      ativa o gatilho no ultimo quadro morto `dc`;
      `incompleto[tipo]`    ativava em algum quadro de `[d0, dc-1]` e nao em `dc`;
      `ausente_apos[tipo]`  nao tem dado nenhum em `(ultimo ativo, dc]`;
      `zona_padrao[tipo]`   esta na zona do padrao no primeiro quadro em jogo;
      `na_pz`               a bola esta na PZ dele no primeiro quadro em jogo;
      `d_bola`              distancia dele a bola no primeiro quadro em jogo;
      `d_geom_dc[tipo]`     distancia a geometria de referencia do gatilho em `dc`;
      `d_geom_ultimo[tipo]` idem, no ultimo quadro em que ele ativava o gatilho;
      `reserva1`            dict `executor` (indice ou -1), `confirmado` (bool) e
                            `tipo` (str ou None) -- ver o problema 1 acima.

    Saida: `(type, jogador, via)`, com `jogador` o indice da linha ou **-1**
    quando nao ha executor identificado, que acontece so em `free_kick?`.
    """
    for tipo in ORDEM_PRINCIPAL:
        candidatos = (
            estado["completo"][tipo] & estado["zona_padrao"][tipo] & estado["na_pz"]
        )
        jogador = padroes.executor(candidatos, estado["d_bola"])
        if jogador >= 0:
            return tipo, jogador, "padrao"

    reserva1 = estado["reserva1"]
    if reserva1["executor"] >= 0:
        # Problema 1: o padrao de tiro livre esta ativado.
        if reserva1["confirmado"]:
            tipo = reserva1["tipo"]
            return (tipo if tipo is not None else FREE_KICK), reserva1["executor"], "reserva_1"
        # Anda mais que `eps_f` (ou nao ha passe para medir): nao e o executor.
    else:
        # Problema 2: o padrao de tiro livre NAO esta ativado.
        for tipo in ORDEM_RESERVA_2:
            candidatos = estado["incompleto"][tipo] & estado["ausente_apos"][tipo]
            jogador = padroes.executor(candidatos, estado["d_geom_ultimo"][tipo])
            if jogador >= 0:
                return tipo, jogador, "reserva_2"

    # Problema 3: so gatilhos, sem padrao.
    for tipo, estagio in ordem_3:
        distancia = (
            estado["d_geom_dc"][tipo] if estagio == "completo"
            else estado["d_geom_ultimo"][tipo]
        )
        jogador = padroes.executor(estado[estagio][tipo], distancia)
        if jogador >= 0:
            return tipo, jogador, "reserva_3"
    return FREE_KICK_DUVIDA, -1, "reserva_3"


def rotular(mascara_por_tipo: dict, excluir: dict = None) -> str:
    """Lista os tipos ativos, na ordem da hierarquia, para as colunas de
    auditoria `gatilhos_completos` e `gatilhos_incompletos`.

    `excluir` tira da lista o tipo que tambem esta ativo na outra mascara. Serve
    a `gatilhos_incompletos`: um gatilho COMPLETO nao e listado como incompleto
    so porque um segundo jogador o ativou e deixou cair antes de `dc` -- a
    coluna e por TIPO, enquanto a decisao da reserva e por JOGADOR.
    """
    return "|".join(
        tipo for tipo in TIPOS
        if np.any(mascara_por_tipo[tipo])
        and not (excluir is not None and np.any(excluir[tipo]))
    )

# Fatia 5 — Passes

Plano escrito pelo orquestrador em 2026-11-04. Portões delegados a mim
(`docs/decisoes.md`, 2026-10-30); G2 desta fatia decidido por mim, com registro.
Lacunas que eu resolvi vão marcadas **[LACUNA]**.

Fonte de verdade: `docs/01-definicoes.md` (Passo 1, "Passe — corrigido (V16)",
Avaliação), `docs/decisoes.md` (D8, D10 e o refinamento de 2026-10-29 do
denominador secundário), `docs/briefing-adendo-2026-10-29.md` (V16, D10), e do
Vidal-Codina: §2.4.3, p. 9; Fig. 1b, p. 3, com o texto da p. 4; suplementar S2,
p. 3, e S5, p. 9.

> **Esta fatia fecha o marco `teto`.** O Passo 1 já existe (Fatia 3) e já emite
> as perdas de posse. A detecção de passe é quase só **rotular** essas perdas. O
> trabalho de verdade é a avaliação: qual perda é passe de jogo corrido, qual
> gabarito vale para cada critério, e decompor os erros.

---

## 1. Objetivo

1. Emitir um **passe** por perda de posse do Passo 1, **exceto** a perda que é o
   próprio evento de bola parada (§3.1).
2. Dar a cada passe o **desfecho** (§3.3), que decide quais passes entram no
   critério principal.
3. Avaliar nos três critérios (`estrito` principal, `vidal_codina`, `mills`), com
   o **gabarito principal** (`PASS`) e o **secundário** (união do D10), e
   **decompor os falsos negativos por causa**.
4. Atualizar `outputs/origem-dos-numeros.md` com os números das Fatias 3, 4 e 5
   (§8): ele parou na Fatia 2, o que viola a regra do projeto.

---

## 2. CONTRATO DE VERIFICAÇÃO — números medidos antes, para pegar bug

Medidos por mim em 2026-11-04 com o código atual (`R_pz` = 0,50 m), **antes**
de existir detector de passe.

### 2.1 Denominadores, exatos

| gabarito | j1 | j2 | j3 | total | origem |
|---|---|---|---|---|---|
| principal: `type == "pass"` na tabela `events` | 722 | 889 | 1039 | **2650** | `construir_gabarito`, contado por mim |
| secundário: `pass_secundario` **e** `type != "goal_kick"` | 987 | 1115 | 1347 | **3449** | idem; ver §3.2 |

A tabela `events` tem `pass_secundario` = 1009 / 1131 / 1358, dos quais
**22 / 16 / 11 são `goal_kick`**, 722 / 889 / 1039 são `pass` e 265 / 226 / 308
são `fora_do_escopo` (`BALL LOST`/`BALL OUT`). Em tipo cru: `PASS` 735/901/1047,
`BALL LOST` 226/181/247, `BALL OUT` 48/49/64.

### 2.2 Limite superior de revocação, pela medição da Fatia 3

`python -m src.run --tau-posse`, rodado hoje: dos 2650 passes do gabarito, **220
não têm perda** do jogador anotado em ±10 s (8,30 %), e **2353** têm perda a
`|τ_posse| ≤ 1,0 s` (662 / 799 / 892). Logo:

- no critério **`estrito`**, `tp_diag` de passe **≤ 2353** (R ≤ 0,888), contra
  qualquer conjunto de detecções que seja subconjunto das perdas;
- no **`vidal_codina`**, `tp_diag` **≤ 2430** (R ≤ 0,917).

Os dois só podem **cair** com a supressão do §3.1 e o filtro de desfecho do
§3.3. **Se passarem desses tetos, o bug é nosso.** Não vale para o secundário
(outro gabarito).

> **A expectativa do `docs/03-plano.md` (revocação ~97 % com 0,50 m, ~98 % com
> 1,00 m) está OBSOLETA.** Ela vinha da distância passador-bola no quadro
> anotado (`docs/inspecao-metrica.md` §6.4), que a Fatia 3 substituiu pela
> grandeza certa (perda de posse). É a mesma classe do erro nº 5: número medido
> antes de uma decisão posterior, propagado como contrato. O contrato é o de
> cima.

### 2.3 Bola parada não pode mudar

Esta fatia **não toca** a detecção de bola parada. `python -m src.run
--bola-parada` tem de dar o mesmo resultado de antes: 481 detecções, `tp_diag`
232, micro F1 0,5979 (`docs/decisoes.md`, 2026-11-04).

---

## 3. Decisões que esta fatia fixa

### 3.1 [LACUNA] A perda que é o evento de bola parada NÃO é passe de jogo corrido

O evento de bola parada **é** um evento de passe: *"Set piece events are passing
events that resume the game after a dead ball interval"* (S2, p. 3), e a Fig. 1b
(p. 3, texto na p. 4) define o atributo *from set piece* como *"the event (pass,
shot or cross) that resumes the game after a dead ball interval"*. A categoria
avaliada como passe é a de **jogo corrido**: *"Open play (not from set piece)
passing events"* (S2, p. 3). O nosso gabarito já segue isso: a linha de execução
é fundida no evento de bola parada (`docs/decisoes.md`, G1) e não é `pass`.

Se a perda de reinício saísse também como passe, **toda bola parada viraria um
falso positivo de passe** — o mesmo defeito que a fusão evita do lado do
gabarito.

**Regra:** para **cada detecção de bola parada** (as 481 da Fatia 4, inclusive
`free_kick?` e `penalty`), a **primeira perda de posse da mesma corrida viva**,
com `frame >= frame da detecção`, é o evento de bola parada e **sai** da lista de
passes. **Independe do jogador**: a regra é "o evento que reinicia o jogo", e é
uma por intervalo morto (correspondência um-para-um DBE-SPE, §2.4.1, p. 7).
Corrida viva sem perda nenhuma: nada a suprimir.

**Alternativa descartada:** suprimir só se a perda for do executor detectado.
Quando a reserva do S1 imputa o executor pela geometria (problema 3), ele pode
não ser quem passa, e aí o passe de reinício sairia como passe de jogo corrido.
**Reportar** quantas das perdas suprimidas são de jogador ≠ executor
(diagnóstico, não decisão).

Consequências declaradas, que vão ao relatório como falso positivo esperado:
- o pontapé inicial do quadro 1 do jogo 1 não tem detecção de bola parada, logo a
  perda do cobrador sai como passe;
- os 12 eventos sem âncora (`no_dead_ball_before`, guarda de 10 s) não têm
  intervalo morto antes, logo a execução deles sai como passe;
- os intervalos mortos espúrios (os 185 FP estruturais da Fatia 4) também
  suprimem uma perda cada — que era passe de verdade. **Medir quantas** dessas
  supressões caem a ≤ 1 s de um `PASS` anotado do mesmo jogador: é o custo, em
  revocação de passe, do D1 sem duração mínima.

### 3.2 O denominador secundário perde os 49 tiros de meta (refinamento do D10)

O refinamento de 2026-10-29 tirou do denominador secundário as linhas de
execução de bola parada, porque *"contá-la também no denominador de passe
criaria falso negativo sistemático, porque o nosso detector a rotula bola
parada"*. **O tiro de meta é o mesmo caso** e ficou de fora daquela conta porque
não é `SET PIECE` na Metrica (V9) e por isso não é fundido. O nosso detector
rotula a execução do tiro de meta como `goal_kick` e, pelo §3.1, **suprime** a
perda correspondente. Mantê-lo no denominador de passe seria falso negativo
estrutural, e é exatamente a inconsistência que a Fatia 1 marcou "a vigiar na
Fatia 2" (`docs/decisoes.md`, `pass_secundario` exclui somente `THEFT`).

**Decisão:** gabarito secundário = `pass_secundario` **e** `type` fora do grupo
`bola_parada`, isto é **987 / 1115 / 1347**. Decidido **antes** de existir
qualquer número de passe, logo é refinamento, não mudança por resultado; nada
passa a exploratório. Chave: `avaliacao.denominador_passe_secundario` passa de
`events` para `events_sem_bola_parada`, com o valor antigo **estourando** (não
há caminho silencioso para o número velho).

### 3.3 O desfecho do passe, e qual passe entra no critério principal

O D10 congelado (adendo, D10) diz: **principal** = *"o passe detectado cujo
próximo ganho é de companheiro contra o `PASS` da Metrica"*; **secundário** =
todo passe detectado contra a união. A Metrica define `PASS` como passe
**completo**; passe errado vira `BALL LOST`/`BALL OUT` (V16).

`desfecho` de cada passe detectado, a partir do **próximo ganho** de posse
(tabela `ganhos` do Passo 1) com `frame > frame da perda`, **na mesma corrida
viva e no mesmo período**:

| `desfecho` | regra | origem |
|---|---|---|
| `completo` | próximo ganho de **companheiro** (mesmo time, outro jogador) | S5, p. 9: *"completed if it reaches a teammate"*; D10 |
| `interceptado` | próximo ganho de **adversário** | S5, p. 9: *"intercepted if it reaches an opponent"* |
| `proprio` | próximo ganho do **próprio passador** | **[LACUNA]**: o S5 não cobre; não é "teammate", logo não é completo |
| `bola_morta` | nenhum ganho até o fim da corrida, e ela termina em quadro morto | S5, p. 9: *"dead ball if a dead ball interval follows"* |
| `fim_de_periodo` | nenhum ganho até o último quadro do período ou do jogo | S5, p. 9: *"end of half"* |

E duas colunas booleanas de auditoria: `recepcao_em_duelo` (o quadro do ganho é
de duelo) e `de_lacuna_5` (a perda é `so_por_lacuna_5`).

**Duas categorias do S5 ficam fora, com motivo:**
- *"goal"*: não detectamos gol (finalização fora do escopo); o passe que vira
  gol cai em `bola_morta`. Declarado.
- *"unclear if there is a duel at passing time"*: **inalcançável por
  construção** — o Passo 1 só emite perda em quadro de posse (`fp =
  flatnonzero(posse)`, inclusive a da lacuna 5), nunca em quadro de duelo. Um
  teste trava isso, para que mudança futura no Passo 1 não reabra a categoria
  em silêncio.

**Divergência declarada:** o S5 trata *"duel if there is a duel at reception
time"* como desfecho próprio. O D10 congelado define o principal pelo **próximo
ganho de companheiro**, sem exceção para duelo, e é o que aplicamos; o duelo na
recepção fica como coluna `recepcao_em_duelo`, reportada.

**Critério principal = passes com `desfecho == "completo"` contra o gabarito
principal. Secundário = todos os passes contra o gabarito secundário.**

### 3.4 Instante, jogador e janela

- Instante do passe = **quadro da perda** (§2.3.2, p. 5). É a grandeza que a
  Fatia 3 mediu para confirmar a janela de ±1 s do D8 (mediana de `τ_posse` =
  um quadro).
- Jogador = o dono que perdeu; `team` = o time dele.
- Âncora: para `pass`, `anchor_shift = 0` (Fatia 2), logo as duas âncoras dão o
  mesmo número. **Reportar só `frame`** e um teste prova a igualdade.

### 3.5 Requisitos herdados

1. **Com e sem as perdas `so_por_lacuna_5`** (Fatias 3 e 4). As duas tabelas.
   Sem elas, a Fatia 8 não separa a regra inventada do resto.
2. **Finalização é rotulada passe**, porque não detectamos finalização. Contra o
   gabarito ela é falso positivo nos dois critérios (`SHOT` não está na união).
   É o que o próprio artigo registra para chute bloqueado (§3.1, p. 9: 70 % das
   254 confusões). Declarado; não filtrar.
3. **Nenhuma constante nova** além da chave do §3.2. Se precisar de uma, pare.

---

## 4. Arquivos

```
src/events/passes.py      # suprimir SPE, desfecho, montar a tabela de passes
src/evaluate.py           # gabarito secundario (funcao pequena) + guarda da chave nova
src/run.py                # + --passes
config.yaml               # denominador_passe_secundario: events_sem_bola_parada
tests/test_passes.py
tests/test_avaliacao_passes.py
outputs/origem-dos-numeros.md
```

Sem classe `Pass`, sem registry de desfechos. Uma função que rotula, uma que
suprime, uma que monta o gabarito secundário. `src/possession.py`,
`src/events/bola_parada.py`, `src/io/**`, `src/gabarito.py` **não mudam**.

---

## 5. Esquema de saída

`passes` — uma linha por perda de posse, **inclusive as suprimidas** (para
auditoria; quem avalia filtra):

| coluna | tipo | observação |
|---|---|---|
| `game`, `period`, `frame`, `t` | — | `frame` = quadro da perda |
| `type` | str | sempre `pass` |
| `team`, `player_id` | str | quem perdeu |
| `run_id` | int | corrida viva |
| `e_bola_parada` | bool | suprimida pelo §3.1 |
| `desfecho` | str | domínio fechado do §3.3; valor fora estoura |
| `receptor_id` | str | quem fez o próximo ganho; vazio se não houve |
| `recepcao_em_duelo` | bool | |
| `de_lacuna_5` | bool | `so_por_lacuna_5` da perda |

Para o casador: `passes[~e_bola_parada]` no esquema `DETECTIONS`; o principal
filtra ainda `desfecho == "completo"`. Gravar em `outputs/passes.csv`
(`outputs/*.csv` já está no `.gitignore`).

---

## 6. `python -m src.run --passes` — o que imprime

1. **Contagens por jogo:** perdas; suprimidas como bola parada (e quantas de
   jogador ≠ executor); passes. Identidade `passes = perdas − suprimidas`.
2. **Distribuição de `desfecho`** por jogo, com `recepcao_em_duelo`.
3. **Principal** (`completo` × `PASS`): P/R/F1 e contagem absoluta, três
   critérios, por jogo e agregado.
4. **Secundário** (todos × união sem tiro de meta): idem.
5. **Diagnóstico** (todos × `PASS`): o mesmo gabarito do principal sem o filtro
   de desfecho, para separar "não detectou" de "desfecho errado".
6. **Decomposição dos falsos negativos do principal, critério `estrito`**, cada
   `PASS` não casado em **exatamente uma** causa, nesta ordem:
   (a) nenhuma perda do jogador anotado a ≤ 1 s;
   (b) a perda existe mas foi suprimida como bola parada;
   (c) a perda existe mas `desfecho != completo` (quebrar por desfecho);
   (d) a perda existe, é `completo`, e foi consumida por outro evento no
   casamento um-para-um.
   **A soma das quatro é o `fn`, exato.**
7. As tabelas 3 e 4 **sem** as perdas `de_lacuna_5`.
8. Custo dos intervalos mortos espúrios (§3.1, último item).

---

## 7. Testes obrigatórios, com critério de aceite e caminho

> Regra da Fatia 2: **cada teste declara o caminho em que roda**, e todo teste
> de razão ou agregação roda pelo menos uma vez num caminho em que as leituras
> candidatas **divergem**.

### 7.1 Rótulo e supressão (`test_passes.py`, sintético salvo indicação)

| teste | caminho | critério de aceite |
|---|---|---|
| A → B → C | sintético, um time | **exatamente dois** passes, desfecho `completo` e `completo` |
| A perde, adversário ganha | sintético | um passe `interceptado`, `receptor_id` = o adversário |
| A perde e a bola sai | sintético | **ainda é passe**, desfecho `bola_morta`; nunca excluído |
| fim do período sem ganho | sintético | `fim_de_periodo`, não `bola_morta` |
| A perde e A recupera | sintético, **outro jogador em duelo no meio**, sem ganho dele | `proprio`, e **não** entra no principal |
| ganho em quadro de duelo | sintético | `recepcao_em_duelo = True` e desfecho decidido pelo time do receptor |
| supressão independe do jogador | sintético, **primeira perda da corrida é de jogador ≠ executor** | essa perda é suprimida; a regra "só do executor" daria o oposto |
| uma supressão por bola parada | sintético, corrida com 3 perdas | só a **primeira** sai |
| corrida sem perda | sintético | nada suprimido, nada quebra |
| próximo ganho não atravessa corrida nem período | sintético, ganho na corrida seguinte | desfecho `bola_morta` |
| `unclear` é inalcançável | **dado real, 3 jogos** | nenhum quadro de perda é quadro de duelo |
| desfecho fora do domínio estoura | sintético | `ValueError` |
| identidade das contagens | **dado real, 3 jogos** | `passes = perdas − suprimidas`; `suprimidas ≤` detecções de bola parada; soma dos desfechos = passes |
| mudar `R_pz` muda a saída | **dado real**, 0,50 → 1,00 m | o número de passes muda |

### 7.2 Avaliação (`test_avaliacao_passes.py`)

| teste | caminho | critério de aceite |
|---|---|---|
| denominadores exatos | **dado real** | principal **722 / 889 / 1039**; secundário **987 / 1115 / 1347** |
| valor antigo da chave estoura | config | `denominador_passe_secundario: events` → erro |
| tiro de meta fora do secundário e dentro da bola parada | dado real | os 49 `goal_kick` estão em `bola_parada` e em nenhum denominador de passe |
| principal usa só `completo` | sintético, **passe `interceptado` no instante e jogador certos** | não casa no principal; casa no secundário |
| teto do §2.2 | **dado real** | `tp_diag` estrito ≤ **2353**; vidal_codina ≤ **2430** |
| evento não detectado é perda de revocação | dado real | `n_gabarito` = 2650 e 3449 em todos os critérios, com qualquer detecção, inclusive vazia |
| NaN | sintético | passe com `t` NaN não casa e não some do denominador |
| decomposição fecha | **dado real** | (a)+(b)+(c)+(d) = `fn` do estrito principal, **exato**, por jogo |
| âncoras iguais para passe | dado real | `frame` e `annotated_frame` dão o mesmo resultado de passe |
| sem lacuna 5 | dado real | o nº de passes cai exatamente do nº de perdas `so_por_lacuna_5` não suprimidas |
| bola parada intacta | **dado real** | 481 detecções, `tp_diag` 232, micro F1 0,5979, como antes |

---

## 8. `outputs/origem-dos-numeros.md`

Acrescentar três seções, **Fatia 3**, **Fatia 4** e **Fatia 5**, no formato das
existentes (número → onde). Os números das Fatias 3 e 4 estão em
`docs/decisoes.md` (blocos de 2026-10-30 a 2026-11-04) e em `docs/estado.md`;
**cada número entra com o bloco e a data de onde vem, e com o comando que o
reproduz**. Onde `decisoes.md` tiver dois valores para a mesma grandeza (houve
números intermediários superados), vale o **último registrado como aceito** —
liste a divergência em vez de escolher em silêncio. **Não invente número**: se
não achar a origem, escreva "origem não encontrada" e me reporte.

---

## 8b. O que fica FORA

- Cruzamento, finalização, defesa, recepção e interceptação **como eventos
  avaliados** (o desfecho é atributo do passe, não evento).
- Varredura de `R_pz` (Fatia 8). Só o teste do §7.1 troca o raio.
- Simulador, reconstrução, cache, manifesto, figura, relatório.
- **Não mudar nenhuma constante congelada**, nem `eps_s`/`eps_v`/`eps_theta`,
  mesmo que o teto de passe fique abaixo de ~90 %: o D9c diz que o reajuste seria
  **mudança declarada**, e isso é decisão minha depois do relatório, não do
  codificador.
- Não tocar em `src/possession.py`, `src/events/bola_parada.py`, `src/io/**`,
  `src/gabarito.py`, `src/tau*.py`.

---

## 9. Riscos conhecidos

1. **O filtro de desfecho pode custar mais revocação que a detecção.** Se o
   próximo ganho for perdido pelo Passo 1 (bola passa perto sem mudar de
   direção — Fig. 3c2), o passe sai `bola_morta` ou `interceptado` e cai fora do
   principal. A tabela 5 do §6 existe para medir isso.
2. **O jogo 3 tem anotação mais frouxa** (`d` < 0,5 m em 90,0 % contra 96,7 % e
   97,4 %; `docs/decisoes.md`, 2026-10-30). Espere revocação menor nele. **Não é
   motivo para tratá-lo diferente.**
3. **Os intervalos mortos espúrios suprimem passes verdadeiros.** É o custo do
   D1 sem duração mínima, agora do lado do passe. Medido no bloco 8, não
   corrigido.
4. **Precisão** não tem teto previsto: eu não tenho medida independente do
   número de perdas que não são passe anotado. Reportar e explicar, não prever.

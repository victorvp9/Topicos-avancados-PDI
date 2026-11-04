# Fatia 4 — Bolas paradas

Plano escrito pelo orquestrador em 2026-11-01. Portões delegados a mim
(`docs/decisoes.md`, 2026-10-30); as decisões são minhas e estão todas registradas
com a alternativa descartada. Lacunas que eu resolvi vão marcadas **[LACUNA]**.

Fonte de verdade: `docs/01-definicoes.md` **Passo 2 inteiro** (reescrito no G1),
`docs/decisoes.md`, `docs/inspecao-metrica.md` §6, e o suplementar **S1** e
**S4.2** do Vidal-Codina.

> **Esta é a fatia mais algorítmica do projeto e a primeira que produz F1 real.**
> A ordem interna importa: gatilho → padrão → hierarquia → hierarquia de reserva.

---

## 1. Objetivo

1. Detectar **pontapé inicial, pênalti, escanteio, lateral, tiro de meta e tiro
   livre**, mais a categoria **`free_kick?`**, na transição morta → viva.
2. Implementar a **hierarquia de reserva do suplementar S1**, que é
   **obrigatória** e não opcional: sem ela o F1 médio de bola parada do artigo cai
   de 95 % para 85 % (S1, p. 2), e o nosso simulador cria exatamente os erros que
   ela trata.
3. Produzir a **primeira tabela de F1 real** do projeto, usando o casador da
   Fatia 2 nos três critérios e nas duas âncoras.

---

## 2. TETOS PREVISTOS — o contrato de verificação desta fatia

Estes números vêm de medição minha sobre o dado cru, independente do código do
projeto. **São o principal instrumento para pegar bug.** Se a sua tabela
divergir deles, pare e relate; não ajuste o código para fechar.

### 2.1 Teto de revocação por gatilho (jogos 1 e 2 somados)

Medido em `docs/inspecao-metrica.md` §6.2, com as tolerâncias publicadas e
tracking perfeito, avaliando o executor anotado no **primeiro quadro em jogo**:

| evento | teto | n | tolerância |
|---|---|---|---|
| lateral | **92 %** (55/60) | 60 | `eps_t` = 0,5 m |
| pontapé inicial | **93 %** (13/14) | **14** | `eps_k1` = 3 m, `eps_k2` = 2 m |
| tiro de meta | **86,8 %** (33/38) | 38 | `eps_g` = 0,5 m |
| **escanteio** | **56 %** (10/18) | 18 | `eps_c` = 3 m |

> **Corrigido em 2026-11-01.** A primeira versão deste plano dizia 89 % para tiro
> de meta e n = 13 para pontapé inicial. **Os dois estavam errados** — o tiro de
> meta por bug de geometria (`abs()` em vez de profundidade com sinal) **e** por
> número obsoleto (medido antes da guarda de 10 s, que deixa 9 tiros de meta sem
> ancorar), e o pontapé inicial por eu ter conflacionado duas populações. Ver a
> nota em `docs/inspecao-metrica.md` §6.2.

> **O jogo 3 NÃO está nestes números, de propósito.** Ele é o único conjunto não
> visto para ajustar `eps_c` (D9b), e eu não medi a geometria dele. **Não me peça
> o número do jogo 3 e não o use para calibrar nada.**

O **padrão não é o gargalo**: a Metrica encaixa a bola na posição do executor nas
bolas paradas, `d(bola, executor)` = 0,00 m, logo o padrão é satisfeito sempre que
a bola não é `NaN` no primeiro quadro vivo (91 a 100 % dos casos).

### 2.2 Teto de PRECISÃO — e ele é baixo por motivo de dado

O detector emite **uma bola parada por transição morta → viva**. Medido:

| jogo | transições | reinícios anotados | teto de precisão | FP estruturais |
|---|---|---|---|---|
| 1 | 154 | 99 | 64,3 % | 55 |
| 2 | 168 | 96 | 57,1 % | 72 |
| 3 | 159 | 101 | 63,5 % | 58 |
| **total** | **481** | **296** | **61,5 %** | **185** |

Causa: a bola da Metrica fica `NaN` em buracos curtos de rastreamento que **não
são paradas de jogo**. A distribuição de duração das corridas mortas é bimodal, com
**p10 = 0,04 s, isto é UM QUADRO**. Com um corte mínimo de 1 s sobrariam 312
transições e o teto de precisão subiria a **94,9 %**.

**Os 185 falsos positivos vão cair quase todos em `free_kick`**, porque é o ramo
`else` da hierarquia. Espere precisão de tiro livre muito baixa, e isso é
consistente com o artigo, onde tiro livre é a pior categoria (§3.1, p. 9).

---

## 3. As decisões que esta fatia fixa

### 3.1 [LACUNA] Duração mínima de bola morta: NENHUMA no principal, ≥ 1 s como sensibilidade declarada

**Tensão real na especificação, não invenção nossa.** O §2.3.4, p. 6, diz que a
bola morta é sinalizada "pela ausência de dado da bola" — é o nosso D1. Mas o
suplementar **S1, p. 1, lista como problema (2) a "missing ball data during
in-play intervals"**, isto é o próprio artigo reconhece que a bola pode faltar
**com o jogo em andamento**, e trata isso como erro a mitigar. O artigo não dá
regra para separar os dois casos.

**Decisão: o resultado principal NÃO aplica mínimo** (fiel à letra do §2.3.4), e
a variante com mínimo de **1 s** entra como **sensibilidade declarada**, no mesmo
padrão das duas políticas de `R_dz` da Fatia 3.

- Origem do 1 s: é o limiar que o Bassek usa para interpolar buraco temporal em
  vez de tratá-lo como ausência real (*"Temporal gaps … of up to 25 frames
  (1 second) were interpolated linearly"*, Bassek, Métodos, p. 4), e é a convenção
  que a nossa própria inspeção já usava (`docs/inspecao-metrica.md` §5.2 analisa
  sequências ≥ 1 s). **É constante nossa, declarada como tal**, não do artigo.
- Por que isso não muda a resposta do projeto: `ball_live` é **congelado e
  idêntico em todos os níveis de degradação** (D1b), logo os 185 falsos positivos
  são um **deslocamento constante** da curva, não uma mudança de forma. A resposta
  à pergunta do projeto depende da forma. Mas os valores absolutos ficam
  incomparáveis com o artigo, o que o D7 já declara.
- `config.yaml`: `bola_parada.duracao_minima_morta_s: 0.0` (principal) e a
  sensibilidade em `[0.0, 1.0]`.

### 3.2 [LACUNA] Executor quando o padrão não pode ser checado (S1, problema 3)

O S1, p. 2, diz que no problema 3 *"we cannot investigate patterns (the ball is
not close to any player when the game resumes)"* e só os gatilhos são usados. Ele
não diz **quem** é o executor nesse caso.

**Decisão: o executor é o jogador do gatilho mais próximo da geometria de
referência daquele gatilho** — a marca de canto ativa para escanteio, a linha
lateral para lateral, a linha de fundo própria para tiro de meta, a marca central
para pontapé inicial. É a mesma lógica do desempate do §2.4.1, p. 7 ("o mais
próximo"), aplicada à geometria que define o gatilho em vez de à bola, porque a
bola é justamente o que falta. Havendo empate, o `player_id` menor, como na
Fatia 3.

### 3.3 Ordem da hierarquia, e ela é checada em teste

**Principal** (Fig. 5, p. 7): pontapé inicial → pênalti → escanteio → lateral →
tiro de meta → tiro livre.

**Reserva** (S1, p. 2, e Fig. S1), aplicada **só quando nenhum gatilho completo
foi confirmado por padrão**:

1. **Problema 1 — booleano fora de sincronia.** Se o padrão de tiro livre é
   ativado por um jogador que **não se desloca mais que `eps_f` = 1 m** antes de
   passar a bola, ele é o executor; então **reavalia-se todos os gatilhos e
   padrões para esse executor** no quadro em jogo em que o primeiro passe após a
   bola morta é feito.
2. **Problema 2 — executor não rastreado.** Se o padrão de tiro livre **não** é
   ativado, procura-se gatilho de escanteio ou lateral que ficou **incompleto**
   porque o jogador que o ativava deixou de ser detectado em `[di+1, dc]`, e
   **imputa-se o evento a esse jogador ausente**.
3. **Problema 3 — bola ausente ou fora da PZ do repositor.** Só gatilhos, nesta
   ordem: pontapé inicial → pênalti → **escanteio completo → lateral completo →
   escanteio incompleto → lateral incompleto → tiro de meta** (corrigido em
   2026-11-04: a Fig. S1, issue 3, diz `K P C T Ci Ti G F?`; a prosa omite o `G`
   e remete à figura; ver `docs/decisoes.md`, revisão da Fatia 4). Os autores registram
   explicitamente *"higher detection rate when favoring complete throw-in over
   incomplete corner"* (S1, p. 2). Se nenhum gatilho ativa, o rótulo é
   **`free_kick?`**.

> **O problema 2 está DORMENTE no teto e acorda na Fatia 6.** A Metrica tem 22
> jogadores com dado em todos os quadros, logo nenhum executor "deixa de ser
> detectado". Implemente e **teste sinteticamente**; ele é a razão pela qual o S1
> é obrigatório (V10), e sem ele o simulador mediria o algoritmo errado.

### 3.4 `free_kick?` é categoria própria, nunca somada em `free_kick`

Já está no vocabulário da Fatia 2 e na matriz de confusão por grupo. O detector
emite `free_kick?` e ele aparece como **coluna** da matriz; o gabarito nunca o
tem, logo toda `free_kick?` é falso positivo — e isso é informativo, porque é o
sinal de que o algoritmo se confundiu (S2, p. 3).

### 3.5 `penalty` é emitido e avaliado com n = 1, nunca agregado

A hierarquia **mantém** o pênalti (decisão da Fatia 2). São 1 evento, no jogo 2.
A linha vai à tabela com a contagem absoluta; `micro()` e
`media_ponderada_f1()` já levantam `ValueError` se receberem `penalty`.

### 3.6 Requisitos que vêm das revisões anteriores

1. **Reportar o resultado COM e SEM as perdas `so_por_lacuna_5`** (Fatia 3). Acima
   de `R_pz` = 1 m a variante "sem" **não é opcional**: a regra inventada chega a
   13–14 % de todas as perdas a 3 m.
2. **Contador de trocas de dono por duelo.** A 3 m, 62 a 65 % dos duelos têm 2+
   donos e um deles tem 9 — é a origem provável de recepção espúria. Reportar ao
   lado do F1.
3. **Duas limpezas cosméticas**, com prova do revisor de que são inócuas:
   remover o código morto `do_dono` em `src/possession.py:373`, e corrigir o
   comentário de `quadros_com_mais_de_um_ganho`, que é **identidade** sob a
   leitura B e não medição.

---

## 4. Arquivos

```
src/events/__init__.py
src/events/gatilhos.py       # os 6 gatilhos, so jogadores, no intervalo morto
src/events/padroes.py        # o padrao no primeiro quadro vivo
src/events/hierarquia.py     # principal + a reserva do S1
src/events/bola_parada.py    # orquestra e emite a tabela de deteccoes
src/run.py                   # + --bola-parada
config.yaml                  # + bloco bola_parada com as tolerancias
tests/test_gatilhos.py
tests/test_padroes.py
tests/test_hierarquia.py
tests/test_reserva_s1.py
tests/test_bola_parada.py
```

Não criar classe `SetPiece`, não criar registry de gatilhos, não generalizar para
"N tipos de bola parada plugáveis". Seis gatilhos concretos e uma função de
hierarquia.

---

## 5. Esquema de saída

`deteccoes` — mesmo domínio do `detections` da Fatia 2 (`docs/fatias/02-plano.md`
§5), mais colunas de auditoria:

| coluna | tipo | observação |
|---|---|---|
| `game`, `period`, `frame`, `t` | — | `frame` = primeiro quadro em jogo |
| `type` | str | `kickoff`/`penalty`/`corner_kick`/`throw_in`/`goal_kick`/`free_kick`/`free_kick?` |
| `team`, `player_id` | str | o executor |
| `dead_run_id` | int | o intervalo morto que originou |
| `dur_morta_s` | float | duração do intervalo morto |
| `via` | str | `padrao` / `reserva_1` / `reserva_2` / `reserva_3` |
| `gatilhos_completos` | str | lista dos que estavam completos, para auditoria |
| `gatilhos_incompletos` | str | idem |

A coluna `via` é o que permite medir **quanto a hierarquia de reserva compra** —
o número análogo aos "85 % → 95 %" do S1, p. 2.

---

## 6. `config.yaml` — acréscimos

```yaml
bola_parada:
  # tolerancias: supl. S4.2, pp. 7-8. Congeladas no G1 (D9a/D9b).
  eps_k1_m: 3.0          # faixa 3 a 5 m; F1 cai a 9/82/95% com 0/0,5/1 m
  eps_k2_m: 2.0          # >= 2 m
  eps_c_m: 3.0           # escanteio. TAMBEM 2o parametro livre (D9b)
  eps_t_m: 0.5           # lateral
  eps_g_m: 0.5           # tiro de meta. ATENCAO: o texto do 2.3.4 p. 6 escreve
                         # eps_c por erro de digitacao; vale a Fig. 4 p. 6 (V14)
  eps_f_m: 1.0           # deslocamento do jogador no problema 1 do S1 (V12)
  eps_p1_m: 2.0          # penalti, fora do escopo de avaliacao agregada
  eps_p2_m: 2.0
  eps_p3_m: 4.0
  # NOSSA, declarada. Ver plano 04 secao 3.1
  duracao_minima_morta_s: 0.0
  sensibilidade_duracao_minima_s: [0.0, 1.0]
  grade_eps_c_m: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]   # D9b, baixa confianca
```

A geometria do campo (pequena área, grande área, marca penal) já está no
`config.yaml` desde a Fatia 1, **rotulada `[IFAB Lei 1, nao conferido]`** — é a
única constante do projeto sem fonte primária, e **só o tiro de meta e o pênalti
dependem dela**. Escanteio, lateral e pontapé inicial não.

---

## 7. Testes obrigatórios, com critério de aceite E o caminho em que rodam

> Regra da Fatia 3, que vale agora para tudo: **cada teste declara em que caminho
> roda**, e todo teste de razão ou agregação roda pelo menos uma vez num caminho
> em que os numeradores candidatos **divergem**.

### 7.1 Gatilhos (`test_gatilhos.py`)

| teste | caminho | critério de aceite |
|---|---|---|
| escanteio dispara | sintético | jogador a 2 m de um vértice **ativo** → dispara; a 4 m → não, com `eps_c` = 3 m |
| escanteio usa o vértice **ATIVO** | sintético, **jogador no vértice do lado errado** | **não** dispara. Roda no caminho em que ignorar `attack_dir` daria o resultado oposto |
| lateral | sintético | `|y|` = 33,8 m → dispara; 33,2 m → não, com `eps_t` = 0,5 m |
| tiro de meta usa a **PRÓPRIA** área | sintético, **jogador na pequena área adversária** | **não** dispara |
| pontapé inicial, as duas condições | sintético | separadamente: invasão > `eps_k1` → não; ninguém a `eps_k2` do centro → não |
| pênalti, as três condições | sintético | cada uma isolada derruba o gatilho |
| gatilho **completo** vs **incompleto** | sintético, **gatilho que cai 5 quadros antes de `dc`** | completo = ativo até `dc`; aquele é incompleto |
| `eps_c` varrido muda a saída | **dado real** | nº de escanteios detectados muda ao longo de `grade_eps_c_m` |
| cada `eps_*` varrido | **dado real** | um teste por tolerância, isoladamente |

### 7.2 Padrão e hierarquia (`test_padroes.py`, `test_hierarquia.py`)

| teste | caminho | critério de aceite |
|---|---|---|
| padrão exige bola na `R_pz` | sintético | bola a 0,3 m → confirma com `R_pz` = 0,5; a 0,8 m → não |
| executor = o mais próximo da bola | sintético, **dois candidatos no gatilho a 0,2 e 0,4 m** | o de 0,2 m |
| ordem da hierarquia | sintético, **gatilhos de escanteio E lateral completos ao mesmo tempo** | sai **escanteio**, porque vem antes. Roda no caminho em que a ordem importa |
| pênalti antes de escanteio | sintético, os dois completos | sai **pênalti** |
| tiro livre é o `else` | sintético | nenhum gatilho → `free_kick` |
| nada é silenciosamente descartado | **dado real, 3 jogos** | nº de detecções = nº de transições morta → viva, **exato** |

### 7.3 Hierarquia de reserva (`test_reserva_s1.py`) — toda sintética, e é obrigatória

| teste | critério de aceite |
|---|---|
| problema 1 | padrão de tiro livre ativado por jogador que anda < `eps_f` → ele é o executor, e os gatilhos são reavaliados para ele |
| problema 1, jogador anda demais | anda > `eps_f` → **não** é o executor, cai no problema 3 |
| **problema 2** | gatilho de escanteio incompleto + executor **deixa de ser detectado** em `[di+1, dc]` → evento **imputado ao jogador ausente**. É o teste que a Fatia 6 vai exercitar de verdade |
| problema 3, ordem | escanteio incompleto **e** lateral completo → sai **lateral**, pela ordem do S1 ("complete throw-in over incomplete corner") |
| problema 3, nada ativa | → **`free_kick?`** |
| `free_kick?` não vira `free_kick` | a detecção sai com `type == "free_kick?"` e **nunca** é somada em `free_kick` |
| `via` é preenchida | toda detecção tem `via` em {`padrao`, `reserva_1`, `reserva_2`, `reserva_3`} |

### 7.4 Contra os tetos previstos (`test_bola_parada.py`) — **dado real, jogos 1 e 2**

| teste | critério de aceite |
|---|---|
| nº de detecções | **154 / 168 / 159**, igual ao nº de transições morta → viva |
| teto de precisão | detecções = 481 contra 296 reinícios anotados nos 3 jogos |
| revocação de gatilho, jogos 1+2 | lateral ~92 % (n=60), pontapé inicial ~92 % (n=13), tiro de meta ~89 % (n=38), **escanteio ~56 % (n=18)**, tolerância de ±1 evento |
| escanteios perdidos caem em tiro livre | a matriz de confusão mostra `(corner_kick, free_kick)` > 0 |
| os 13 `no_dead_ball_before` ficam no denominador | revocação calculada sobre o gabarito inteiro |
| pênalti | 1 detecção possível no jogo 2; `micro()` levanta se receber `penalty` |
| sensibilidade de duração | com mínimo de 1 s: **312** detecções nos 3 jogos e precisão ~94,9 % |
| `via` quantifica a reserva | reportar a distribuição de `via`; é o nosso análogo dos "85 % → 95 %" do S1 |

### 7.5 Contra falha silenciosa

Da lista de `docs/03-plano.md`: parâmetro varrido muda a saída (cada `eps_*`);
evento não detectado é perda de revocação, **nunca** exclusão; `NaN` nunca conta
como acerto; e **nenhuma detecção é descartada** — o nº de detecções é exatamente
o nº de transições.

---

## 8. O que fica FORA

- **Passes, recepções, interceptações, cruzamentos, finalizações, defesas.**
  Fatia 5 e fora de escopo.
- Simulador, `visible=False`, interpolação, varredura completa, cache, manifesto,
  figura, relatório markdown.
- **Não ajustar nenhuma tolerância.** `eps_c` é varrido (D9b) e reportado como
  curva de **baixa confiança**; nunca escolhido como estimativa pontual.
- Não tocar em `src/evaluate.py`, `src/tau.py`, `src/io/**`, `src/gabarito.py`.
  `src/possession.py` só para as duas limpezas do §3.6.3.

---

## 9. Riscos conhecidos

1. **O teto de precisão de 61,5 % vai dominar o F1 agregado.** É esperado e
   medido; não é bug. O que seria bug é o nº de detecções divergir do nº de
   transições.
2. **O escanteio a 56 % é o resultado mais citável e o mais frágil.** n = 18 nos
   jogos 1 e 2. Reportar contagem absoluta sempre.
3. **A reserva do S1 é a parte mais difícil e a menos testável no teto**, porque
   o problema 2 está dormente. Teste sintético rigoroso ou a Fatia 6 mede o
   algoritmo errado.
4. **A geometria da pequena área não está conferida.** Afeta tiro de meta e
   pênalti. Se o tiro de meta divergir muito dos 89 % previstos, suspeitar dela
   antes de suspeitar do código.
5. **O jogo 3 é conjunto não visto para `eps_c`.** Não calibrar nada nele.

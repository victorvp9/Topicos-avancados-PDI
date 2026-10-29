# Inspeção da Metrica Sports sample-data

Feita em 2026-10-29 pelo orquestrador, antes do G1. **Nenhum código do projeto foi
escrito.** Tudo aqui saiu de scripts efêmeros (`uv run --no-project --with pandas
--with numpy`) em pasta temporária fora do repositório.

Objetivo: responder às perguntas da última seção do
`docs/briefing-adendo-2026-10-29.md` e fechar as decisões D1, D6, D8 e D9.

---

## 1. Procedência e integridade

```
git clone --depth 1 https://github.com/metrica-sports/sample-data data/metrica-sample-data
```

Commit `e706dd506b360d69d9d123d5b8026e7294b13996` ("Added Sample Game 3",
2021-04-15). **Nenhum arquivo é ponteiro de Git LFS** (conferido lendo os
primeiros 200 bytes de cada um).

sha256:

| arquivo | sha256 |
|---|---|
| `Sample_Game_1_RawEventsData.csv` | `803f312a07572912b9ca2dc9482d31a75e573eae825773253b4ca9472e7760c0` |
| `Sample_Game_1_RawTrackingData_Away_Team.csv` | `380e1b23affe778a7e1e8480983291798f118f71b1dbcf8f9729c06977669101` |
| `Sample_Game_1_RawTrackingData_Home_Team.csv` | `ed7289a72d41f280b5316647655b1934575d3506c34e181c343294ceafdcb280` |
| `Sample_Game_2_RawEventsData.csv` | `c2296e8e0caf6f5bb832d5ecf9ebb52c13b18815b1fdbbf79a886238a01d6472` |
| `Sample_Game_2_RawTrackingData_Away_Team.csv` | `f887c6c9227e56c01d1bf62d8d5bc66cdbc1da0c3e9b397c0e9499a0bc6dcb20` |
| `Sample_Game_2_RawTrackingData_Home_Team.csv` | `92cc3ae1b5ac74530e21a899ab71cf12ee3a58c16592e87add6197f88a042b31` |
| `Sample_Game_3_events.json` | `ce12d8bf2b8242825e343fe12a06a0731f2d35e0ffb130603ef746f79fbf0b09` |
| `Sample_Game_3_metadata.xml` | `0011881426043ff4d404b3445381eafb69086a02d95ac3bcf213a062fae74502` |
| `Sample_Game_3_tracking.txt` | `bd33b0a6f89d5617275eac373b3fd043247c581759484e8f566f7701d09975c9` |
| `documentation/events-definitions.pdf` | `5afb1ee34931447223ef8b9dc6a30b827fd0ba57ac9b6e2d7125ee87b083a866` |

O `events-definitions.pdf` de `documentation/` tem o mesmo nome do que está em
`refs/`; os hashes não foram comparados entre as duas pastas.

---

## 2. Tracking dos jogos 1 e 2 (CSV)

Três linhas de cabeçalho. A linha 3 traz os nomes:
`Period, Frame, Time [s]`, depois um par `x,y` por jogador (coluna nomeada só no
primeiro dos dois campos) e, por último, `Ball` com `x,y`.

- **Não existe coluna de z da bola. Não existe booleano vivo/morto.** Confirmado
  nos dois jogos.
- A bola aparece nos dois arquivos (Home e Away) e é **bit a bit idêntica**.
- `Frame` vai de 1 a 145006 (jogo 1) e 1 a 141156 (jogo 2), **sem buracos e sem
  duplicatas** (todos os `diff` iguais a 1), e é idêntico entre Home e Away.
- Frequência **exatamente 25 Hz**: todos os `dt` iguais a 0,04 s, e
  `max |Time [s] − Frame/25| = 0,000000` nos dois jogos.
- Períodos: jogo 1 → P1 com 71 268 quadros (0,04 a 2850,72 s) e P2 com 73 738
  (2850,76 a 5800,24 s). Jogo 2 → 67 941 e 73 215.
- Jogadores na planilha: 15 por time no jogo 1 (11 + 4 substitutos); 15 Home e 13
  Away no jogo 2. Uma coluna do jogo 2 vem como `Player 26` (com espaço) — o
  loader tem de normalizar o nome.

### 2.1 Jogadores: o tracking é completo

| | jogo 1 | jogo 2 |
|---|---|---|
| jogadores visíveis por quadro (mín.–máx.) | 22–23 | 22–23 |
| quadros com 22 visíveis | 145 000 | 141 152 |
| quadros com 23 visíveis | 6 | 4 |

**São sempre 22 jogadores em campo.** O NaN por jogador (de 0 % a 89 %) é só
substituição: o titular tem dado até sair, o reserva a partir de quando entra.
Os 6 e 4 quadros com 23 são sobreposição na janela da substituição.

Consequência: a Metrica é o "teto" perfeito que o projeto precisa. **Toda a
perda de visibilidade do experimento vem do nosso simulador**, não do dado.

### 2.2 Coordenadas

Normalizadas, mas **extrapolam [0,1]**:

| | jogo 1 | jogo 2 |
|---|---|---|
| jogador x | −0,02973 a 1,04722 | −0,03339 a 1,05000 |
| jogador y | −0,05000 a 1,05000 | −0,05000 a 1,05000 |
| bola x | −0,04548 a 1,05996 | −0,03568 a 1,02586 |
| bola y | −0,03991 a 1,03782 | −0,03891 a 1,03102 |
| quadros com bola fora de [0,1] | 2423 (1,671 %) | 550 (0,390 %) |

Os valores de jogador batem **exatamente** em −0,05 e 1,05 (jogo 1: 71 e 663
ocorrências; jogo 2: 819 e 215), o que indica recorte (*clipping*) em ±0,05, isto
é ±5,25 m em x e ±3,40 m em y. O conversor não pode assumir [0,1].

### 2.3 Sentido de ataque

Pelo x médio do goleiro (`Player11` em casa, `Player25` fora):

| | P1 | P2 |
|---|---|---|
| jogo 1, Home GK | 0,125 | 0,905 |
| jogo 1, Away GK | 0,894 | 0,117 |
| jogo 2, Home GK | 0,872 | 0,123 |
| jogo 2, Away GK | 0,113 | 0,878 |

Inverte entre os períodos **e o sentido do Home difere entre os jogos**. A
normalização tem de ser por jogo e por período, nunca por convenção fixa.

### 2.4 NaN da bola

| | jogo 1 | jogo 2 | jogo 3 |
|---|---|---|---|
| quadros com bola NaN | 56 755 (**39,14 %**) | 57 884 (**41,01 %**) | 46 325 (**32,22 %**) |
| nº de sequências | 155 | 169 | — |
| duração mediana | 7,84 s | 5,08 s | — |
| p90 / máx. | 34,36 / 131,68 s | 38,38 / 129,80 s | — |
| sequências ≥ 1 s | 100 | 108 | — |
| sequências ≥ 5 s | 84 | 85 | — |
| tempo total em NaN | 2270,2 s | 2315,4 s | — |

---

## 3. Eventos dos jogos 1 e 2

Colunas: `Team, Type, Subtype, Period, Start Frame, Start Time [s], End Frame,
End Time [s], From, To, Start X, Start Y, End X, End Y`.

- `max |Start Time − Start Frame/25| = 0,000000` nos dois jogos: **gabarito e
  tracking compartilham a mesma grade de quadros**, sem defasagem de
  sincronização. Isso é diferente do caso do Vidal-Codina, onde a anotação da STS
  vem em média 1,5 s atrasada (suplementar S3, p. 5). Ver §6.2.
- Ordenado por `Start Frame` nos dois jogos. Jogo 1 tem 1 linha com
  `End Frame = 0` e `End < Start`.
- `From` **nunca** é nulo. `To` só existe em `PASS`.
- **`Start X`/`Start Y` são sempre NaN nas linhas `SET PIECE`** (0 de 77 e 0 de
  80) e em `CARD`. Nos demais tipos estão sempre preenchidos. A posição de uma
  bola parada tem de vir do tracking, não do gabarito.

### 3.1 Contagem por Type

| Type | jogo 1 | jogo 2 | jogo 3 |
|---|---|---|---|
| PASS | 799 | 964 | 1121 |
| CARRY | — | — | 1395 |
| RECOVERY | 278 | 248 | 294 |
| BALL LOST | 257 | 233 | 288 |
| CHALLENGE | 233 | 311 | 335 |
| SET PIECE | 77 | 80 | 90 |
| BALL OUT | 51 | 49 | 64 |
| SHOT | 24 | 24 | 20 |
| FAULT RECEIVED | 22 | 20 | 12 |
| CARD | 4 | 6 | 1 |
| **total** | **1745** | **1935** | **3620** |

O jogo 3 tem um tipo que os jogos 1 e 2 não têm: **`CARRY` (1395)**. É um esquema
de anotação mais novo. Os subtipos do jogo 3 vêm como **lista** (`["FREE KICK",
"INDIRECT"]`), não como string única.

### 3.2 SET PIECE por subtipo (= gabarito de bola parada)

Contado por subtipo **principal**, ignorando os modificadores `RETAKEN`,
`INDIRECT` e `DIRECT` (que no jogo 3 vêm na mesma lista):

| subtipo | jogo 1 | jogo 2 | jogo 3 | total |
|---|---|---|---|---|
| THROW IN | 28 | 32 | 50 | **110** |
| FREE KICK | 32 | 32 | 28 | **92** |
| CORNER KICK | **11** | **7** | **8** | **26** |
| KICK OFF | 6 | 8 | 4 | **18** |
| PENALTY | 0 | 1 | 0 | 1 |
| **total `SET PIECE`** | 77 | 80 | 90 | 247 |

Cru, com os modificadores, no jogo 3: `THROW IN` 49, `FREE KICK+INDIRECT` 26,
`CORNER KICK` 8, `KICK OFF` 4, `DIRECT+FREE KICK` 1, `RETAKEN+THROW IN` 1,
`FREE KICK+INDIRECT+RETAKEN` 1.

Escanteio: **26 nos três jogos somados**. Confirma V6: as classes de bola parada
são minúsculas. Um acerto move o F1 em 4 a 9 pontos.

**Os 8 escanteios do jogo 3** (o único conjunto não visto para ajustar `ε_c`, ver
§7):

| período | quadro | t (s) | time | cobrador |
|---|---|---|---|---|
| 1 | 6449 | 257,96 | Team A | Player 7 |
| 1 | 22782 | 911,28 | Team A | Player 7 |
| 1 | 68306 | 2732,24 | Team A | Player 7 |
| 2 | 87590 | 3503,60 | Team A | Player 7 |
| 2 | 98829 | 3953,16 | Team B | Player 22 |
| 2 | 125624 | 5024,96 | Team A | Player 5 |
| 2 | 130320 | 5212,80 | Team A | Player 5 |
| 2 | 141872 | 5674,88 | Team B | Player 22 |

**São 8 observações de 3 cobradores, 6 delas de um só time.** Como o que `ε_c`
mede é a posição do cobrador no instante do contato — isto é o hábito de corrida
de aproximação dele —, as 8 não são independentes no que importa. **1 escanteio
move a taxa em 12,5 pontos percentuais.** Daí a declaração de baixa confiança em
`docs/decisoes.md`.

### 3.3 Tiro de meta: não é SET PIECE

Confirma V9 e V16. O `GOAL KICK` aparece como subtipo de três `Type` diferentes:

| Type / Subtype | jogo 1 | jogo 2 | jogo 3 |
|---|---|---|---|
| `PASS` / `GOAL KICK` | 13 | 12 | 8 |
| `BALL LOST` / `GOAL KICK` | 3 | 0 | 1 |
| `BALL LOST` / `GOAL KICK-INTERCEPTION` | 5 | 4 | 1 |
| `BALL LOST` / `END HALF+GOAL KICK` | 0 | 0 | 1 |
| `BALL OUT` / `GOAL KICK` | 1 | 0 | 0 |
| **total** | **22** | **16** | **11** |

O mapeamento aprovado pelo Victor (tiro de meta = `GOAL KICK` em `PASS` ∪
`BALL LOST` ∪ `BALL OUT`) é o único que recupera todos. Mas ver §6.3: nessas
linhas o `Start Frame` **não é sempre o instante do chute**.

### 3.4 SET PIECE vem sempre em par com a ação

Para **todos** os 77 + 80 `SET PIECE`, o evento seguinte é do **mesmo jogador**
(`From` igual) e o Δquadro mediano é **0**. O tipo seguinte é `PASS`,
`BALL LOST`, `BALL OUT` ou `SHOT`:

| subtipo | seguinte | jogo 1 | jogo 2 |
|---|---|---|---|
| CORNER KICK | PASS | 7 | 1 |
| | BALL LOST/*INTERCEPTION | 3 | 6 |
| | BALL OUT | 1 | 0 |
| FREE KICK | PASS | 24 | 21 |
| | BALL LOST | 6 | 7 |
| | BALL OUT | 2 | 0 |
| | SHOT | 0 | 2 |
| KICK OFF | PASS | 6 | 7 |
| THROW IN | PASS | 27 | 31 |
| | BALL LOST | 1 | 1 |

Δquadro máximo observado: 81 (um FREE KICK do jogo 2). Logo, **a linha `SET
PIECE` é o rótulo e a linha seguinte é a execução**; as duas têm de ser tratadas
como um só evento no gabarito, senão o detector gera um falso positivo de passe
para cada bola parada.

### 3.5 BALL LOST e BALL OUT por subtipo (para D10)

| subtipo | jogo 1 | jogo 2 |
|---|---|---|
| BALL LOST / INTERCEPTION | 128 | 114 |
| BALL LOST / (vazio) | 51 | 30 |
| BALL LOST / THEFT | **21** | **38** |
| BALL LOST / HEAD-INTERCEPTION | 5 | 15 |
| BALL LOST / CROSS-INTERCEPTION | 14 | 8 |
| BALL LOST / HEAD | 14 | 10 |
| BALL LOST / outros | 24 | 18 |
| BALL OUT / (vazio) | 39 | 38 |
| BALL OUT / CLEARANCE | 4 | 5 |
| BALL OUT / HEAD | 3 | 4 |
| BALL OUT / outros | 5 | 2 |

`PASS ∪ BALL LOST ∪ BALL OUT` = **1107** (jogo 1) e **1246** (jogo 2). Só `PASS` =
799 e 964. `THEFT` (21 e 38) é bola roubada em condução: não houve passe, e por
isso a proposta de excluí-lo do critério secundário se sustenta.

---

## 4. Jogo 3

- `Sample_Game_3_metadata.xml`: EPTS FIFA. `FrameRate = 25`, `Width = 105`,
  `Height = 68`, `ProviderName = Metrica Sports`, `TrackingType = Optical`.
  35 `Player`, 2 `Team`.
- `Sample_Game_3_tracking.txt`: uma linha por quadro, no formato
  `frame:p1x,p1y;p2x,p2y;…;p22x,p22y:bolax,bolay`. 143 761 linhas, `Frame` de 1 a
  143 761 **sem buracos**, **22 jogadores com dado em todos os quadros**, bola
  NaN em 32,22 %. `ball x` de −0,0193 a 1,0178; `ball y` de −0,0339 a 1,0298.
- O XML traz **11 blocos `DataFormatSpecification`**, cada um com `startFrame`,
  `endFrame` e 44 `PlayerChannelRef` (= 22 jogadores × 2 coordenadas) na ordem
  dos campos da linha. As faixas mudam nas substituições (1–69661, 69662–89697,
  …, 129832–143761).
- `Sample_Game_3_events.json`: `{"data": [...], "metadata": [...]}`. Cada evento
  tem `index, team, type, subtypes, start, end, period, from, to`, com
  `start = {frame, time, x, y}`. `start.x` não nulo em 3529 de 3620.

**É legível sem `kloppy`**: basta `xml.etree` + `str.split` da biblioteca padrão.
Um loader de ~40 linhas resolve. **D6 fechada: nenhuma dependência nova.**

---

## 5. Decisão D1 — estado da bola

### 5.1 O que as fontes exigem

- Mills, §2.2, p. 4: *"The algorithm uses three inputs: x, y, z coordinate
  tracking data of the ball and x, y coordinates of players' center of mass,
  along with the frame-by-frame ball status ('live' or 'dead')."* Confirma V1.
- Vidal-Codina, §2.1, p. 3: o estado vem *"either directly with a boolean that
  switches between in-play or dead ball (Tracab) or indirectly with **missing
  ball data when the game is dead** (Track160 and Hawk-Eye)"*.
- Vidal-Codina, §2.3.4, p. 6: *"dead ball trigger: the ball is dead, signaled by
  either a binary boolean or **by the absence of ball tracking data**."*

Ou seja, **a ausência de dado da bola é um mecanismo de primeira classe do
algoritmo original**, usado em 12 das 31 partidas do artigo. Confirma V15.

### 5.2 O que o dado mostra

- **0 de 799 e 0 de 964 eventos `PASS` caem num quadro com bola NaN.**
  **0 de 233 `BALL LOST`** (jogo 2; 1 de 257 no jogo 1).
  Nenhum evento de toque em jogo corrido ocorre durante NaN.
- Dos 1935 eventos do jogo 2, só **32 (1,7 %)** caem dentro de NaN, e todos são
  de bola morta: `CARD` (6), `SET PIECE` (9), `CHALLENGE` com falta (17).
- Evento imediatamente **depois** de cada sequência de NaN ≥ 1 s (jogo 2, 108
  sequências): `SET PIECE/THROW IN` 28, `RECOVERY` 25, `SET PIECE/FREE KICK` 23,
  `KICK OFF` 7, `CORNER KICK` 7, `PASS` 7, resto ≤ 2.
- Evento imediatamente **antes**: `BALL OUT` 28+5+3+1+1, `FAULT RECEIVED` 17,
  `SHOT` 7, `BALL LOST/THEFT` 9, `CHALLENGE/*-LOST` 14, `BALL LOST/FORCED` 6,
  `HAND BALL` 3.
- Fração de NaN nos 2 s **antes** de cada bola parada: `CORNER KICK` 1,00;
  `KICK OFF` 1,00; `THROW IN` 0,98–0,99; `FREE KICK` 0,93–0,97;
  `PASS/GOAL KICK` 0,62–0,92.

### 5.3 Decisão

**Estado da bola = `NaN(bola)`, quadro a quadro, derivado só do tracking.**

- Não é circular: não toca o gabarito de eventos em momento algum.
- É exatamente o mecanismo dos provedores A (Track160) e C (Hawk-Eye) do
  Vidal-Codina, logo reproduz o algoritmo, não o contorna.
- Fica **congelado e idêntico em todos os níveis de degradação**: o simulador
  remove jogadores, nunca a bola (D2). Declarar como oráculo, igual aos
  provedores 2 e 3 do Mills.
- Limitação a declarar: 25 das 108 sequências ≥ 1 s do jogo 2 são seguidas de
  `RECOVERY` e 7 de `PASS`, sem bola parada. Nesses casos o algoritmo verá uma
  bola morta que a anotação não reconhece como tal, e tentará detectar uma bola
  parada que não existe → **falso positivo estrutural de tiro livre**. Não
  corrigir: é o comportamento do algoritmo original sobre esse tipo de dado.

---

## 6. O que o dado diz sobre o teto (e sobre D8 e D9)

As três subseções abaixo são o achado mais importante da inspeção. **Elas medem
o teto antes de qualquer código do projeto**: quantas bolas paradas as
tolerâncias publicadas conseguem pegar com tracking perfeito.

### 6.1 Como o algoritmo realmente decide (correção de `docs/01`)

Conferido no texto principal, e **o `docs/01` está errado**:

- **Gatilho = configuração dos JOGADORES durante o intervalo de bola morta.** A
  bola não entra no gatilho (Vidal-Codina §2.3.4, p. 6):
  - pontapé inicial: todos na própria metade com tolerância `ε_k1`, **e** pelo
    menos um jogador a `ε_k2` da marca central (Lei 8);
  - escanteio: ≥ 1 jogador a `ε_c` de uma das suas marcas de canto **ativas**
    (Lei 17);
  - lateral: ≥ 1 jogador **além da linha lateral auxiliar** (lateral menos
    `ε_t`) (Lei 15);
  - tiro de meta: ≥ 1 jogador dentro da **própria** pequena área, com caixa de
    tolerância `ε_g` (Lei 16).
- `ε_c` **não** é a distância da bola ao canto, e `ε_t` **não** é a distância da
  bola à lateral. O `docs/01` descreve as duas como "padrão de bola".
- **Padrão** (§2.4.1, p. 7) = *"o jogador do gatilho está dentro da zona do
  padrão **e** a bola está na zona de posse dele no primeiro quadro em jogo"*.
  Havendo vários, o **mais próximo da bola** é o executor. Fig. 4, p. 6: *"trigger
  and pattern zones coincide for corners, throw-ins and goal kicks."*
- **Gatilho completo** = ativo de um quadro intermediário `d_1` qualquer até o
  último quadro morto `d_c` (§2.4.1, p. 7). Como `d_1` pode ser `d_c`, basta
  estar ativo no último quadro morto.
- Ordem da hierarquia (Fig. 5, p. 7, e Fig. S1, p. 2): **pontapé inicial →
  pênalti → escanteio → lateral → tiro de meta → tiro livre**. O `docs/01` omite
  o pênalti e não fixa a posição do tiro de meta.
- Erro de digitação confirmado (V14): o §2.3.4, p. 6, escreve `ε_c` para a caixa
  da pequena área, mas a legenda da Fig. 4, p. 6, escreve `ε_g`. **Usar `ε_g`.**
- V13 confirmado: o texto principal **não** define PZ própria de bola parada —
  só exige a bola dentro de `R_pz` do executor no primeiro quadro em jogo. A "PZ
  específica de bola parada com outro conjunto de hiperparâmetros" é do Mills
  (§2.2, p. 4). Seguindo a decisão do Victor de 28/10: **vale o Vidal-Codina**.
  Consequência registrada no plano: **varrer `R_pz` também move as bolas
  paradas.**
- V12 confirmado (suplementar S1, p. 1): `ε_f` = deslocamento máximo do jogador
  que ativa o padrão de tiro livre antes de passar a bola. Não é tolerância de
  tiro livre.

### 6.2 Medição dos gatilhos na Metrica, com tracking perfeito

Medido para cada bola parada anotada: posição do executor (`From`) no **primeiro
quadro em jogo** após o intervalo de NaN, com o sentido de ataque normalizado por
jogo e por período.

**Padrão (bola na PZ do executor).** `d(bola, executor) = 0,00 m` em
praticamente todos os casos — a Metrica encaixa a bola na posição do executor nas
bolas paradas. O padrão é satisfeito sempre que a bola não é NaN:

| | jogo 1 | jogo 2 |
|---|---|---|
| escanteio, bola ≤ 1 m do executor | 10/11 (91 %) | 7/7 (100 %) |
| lateral | 26/28 (93 %) | 28/32 (88 %) |
| pontapé inicial | 6/6 (100 %) | 7/7 (100 %) |

As falhas são só quadros em que a bola segue NaN no primeiro quadro "vivo". **O
padrão não é o gargalo.**

**Gatilho de escanteio, `ε_c` = 3 m** (distância do executor à marca de canto
ativa):

| | jogo 1 (n=11) | jogo 2 (n=7) | somados |
|---|---|---|---|
| ≤ 3 m (valor publicado) | 6 (55 %) | 4 (57 %) | **10/18 = 56 %** |
| ≤ 5 m | 9 (82 %) | 6 (86 %) | 15/18 = 83 % |

Distâncias observadas (m): 0,66 0,74 1,01 1,18 1,27 1,28 1,33 2,24 2,52 2,68
3,46 3,84 4,48 4,58 4,75 6,01 6,98 8,15.

**Este é o achado central.** Com a tolerância publicada e tracking perfeito, o
teto de revocação de escanteio na Metrica é ~56 %. A causa não é ruído: é que o
quadro em que a bola reaparece é o do **contato**, não o da bola parada na
bandeirinha, e nele o cobrador já completou a corrida de aproximação. Os
escanteios perdidos caem no `else` e viram **tiro livre** — exatamente o erro (1)
que o Vidal-Codina lista em §2.4.1, p. 8.

**Gatilho de lateral, `ε_t` = 0,5 m** (executor com |y| ≥ 34 − `ε_t` = 33,5 m):

| | jogo 1 (n=28) | jogo 2 (n=32) | somados |
|---|---|---|---|
| `ε_t` = 0,5 m | 27 (96 %) | 28 (88 %) | **55/60 = 92 %** |
| `ε_t` = 1,0 m | 28 (100 %) | 31 (97 %) | 59/60 = 98 % |

**O lateral está bem servido pelo valor publicado.** (Uma medição anterior, da
distância da **bola** à lateral, dava 29–41 % — era a grandeza errada, ver §6.1.)

**Gatilho de pontapé inicial, `ε_k1` e `ε_k2`:**

| | jogo 1 (n=6) | jogo 2 (n=7) |
|---|---|---|
| invasão da metade adversária ≤ 3 m (`ε_k1`=3) | 5 (83 %) | 7 (100 %) |
| alguém ≤ 2 m do centro (`ε_k2`=2) | 5 (83 %) | 7 (100 %) |

A única falha é o `KICK OFF` do **quadro 1** do jogo 1: o tracking começa
exatamente no chute, sem intervalo de bola morta antes, e com os jogadores já
movidos (invasão de 12,78 m, ninguém a menos de 7,16 m do centro). Como o
algoritmo detecta bolas paradas **na transição morta → viva**, esse pontapé
inicial é **estruturalmente indetectável**. No jogo 2 há 2,00 s de bola morta
antes (quadro 51) e ele é detectável. Registrar: 1 de 13 pontapés iniciais é
perda obrigatória de revocação, nunca excluído do denominador.

**Gatilho de tiro de meta, `ε_g`** (executor dentro da própria pequena área,
5,5 m × 18,32 m):

| | jogo 1 (n=22) | jogo 2 (n=16) | somados |
|---|---|---|---|
| `ε_g` = 0 | 20 (91 %) | 13 (81 %) | 33/38 = 87 % |
| `ε_g` = 0,5 m (publicado) | 20 (91 %) | 14 (88 %) | **34/38 = 89 %** |
| `ε_g` = 2 m | 20 (91 %) | 16 (100 %) | 36/38 = 95 % |

O suplementar (S4.2, p. 7) diz que `ε_g` existe justamente para acomodar *"a goal
kick pass from beyond the goal area"*. Os casos do jogo 2 a 6,2–6,4 m da linha de
fundo são isso.

**Teto de revocação por geometria, com as tolerâncias publicadas** (soma dos
jogos 1 e 2, antes de qualquer degradação, antes de posse e hierarquia):

| evento | teto | n |
|---|---|---|
| lateral | 92 % | 60 |
| tiro de meta | 89 % | 38 |
| pontapé inicial | 92 % | 13 |
| **escanteio** | **56 %** | **18** |

### 6.3 Dois problemas de gabarito encontrados

1. **`BALL LOST`/`GOAL KICK-INTERCEPTION`**: o `Start Frame` dessas linhas é o
   ponto da **interceptação**, não o do chute. No jogo 1, quadro 125622, o
   executor anotado está a 23,17 m da própria linha de fundo. Medindo no
   **primeiro quadro em jogo** depois da bola morta, o quadro 77582 passa de
   49,55 m para 4,52 m — dentro da pequena área. Logo o gabarito de tiro de meta
   tem de ser ancorado no **primeiro quadro em jogo**, não no `Start Frame`.
2. **Lateral do jogo 2, quadro 107548**: o executor anotado está a |y| = 26,67 m,
   7,3 m da lateral, e nenhum jogador do time passa de 30,82 m. Candidato a erro
   de anotação (jogador errado). Não corrigir o gabarito — contar como perda.

### 6.4 De qual provedor a Metrica se parece (réplica do S3)

Distância do jogador anotado à bola **no `Start Frame`** do evento (o suplementar
mede o **mínimo** numa janela de ±10 s, logo a nossa medição é mais estrita):

| | < 0,5 m | < 1 m | mediana | p99 |
|---|---|---|---|---|
| jogo 1, `PASS` (n=799) | 96,7 % | 97,7 % | 0,08 m | 3,21 m |
| jogo 2, `PASS` (n=964) | 97,4 % | 98,2 % | 0,09 m | 2,21 m |
| jogo 1, `BALL LOST` (n=256) | 87,9 % | 89,1 % | 0,11 m | 5,48 m |
| jogo 2, `BALL LOST` (n=233) | 83,7 % | 88,8 % | 0,10 m | 4,99 m |
| `SET PIECE` (n=65+71) | 100 % | 100 % | 0,00 m | 0,01 m |

Referência do suplementar (S3, pp. 5–6): provedor A (Track160) 99 % **exatamente
0**; B (Tracab) 80 % < 50 cm e 99 % < 1 m; C (Hawk-Eye) 67 % < 50 cm e 99 % < 1 m.

**A Metrica fica entre A e B, muito mais perto de A.** Logo:
- `R_pz` = 0,50 m (o ótimo do provedor A) é o ponto de partida correto para o
  teto, e `R_pz` = 1,00 m é a alternativa óbvia;
- com `R_pz` = 0,50 m o teto de revocação de passe fica em ~97 %, e com 1,00 m em
  ~98 %. Esses dois números são previsão, não medida: saem da distribuição de
  distância, não de uma execução do detector.

### 6.5 Consequência para D8 (critério de acerto)

> **Argumento corrigido em 2026-10-29** (apontado pelo Victor). A versão original
> desta seção argumentava por `|Start Time − Frame/25| = 0`. **Isso não serve**:
> prova apenas que a tabela de eventos usa a mesma grade de quadros e a mesma
> unidade do tracking — consistência de unidade —, e nada diz sobre a acurácia do
> **instante** anotado. Uma anotação atrasada 3 s satisfaria a identidade
> exatamente.

A evidência válida é a de §6.4, e é de **distância**, não de relógio: **no próprio
quadro anotado**, o passador anotado está a menos de 0,5 m da bola em 96,7 % e
97,4 % dos passes, com mediana de 0,08–0,09 m. A bola percorre vários metros em
1,5 s a qualquer velocidade de passe, logo 8 cm de separação mediana no instante
anotado é incompatível com uma defasagem da ordem da que a STS exibe.

O contraste de método reforça: o suplementar S3 (p. 5) mede o **mínimo numa janela
de ±10 s** precisamente porque, na STS, no instante anotado o passador costuma
estar longe da bola. Aqui a medição no instante anotado já dá 0,08 m.

Portanto a janela de ±10 s do critério oficial (suplementar S2, p. 3) é
larguíssima para este dataset e corre o risco de casar o evento errado numa
sequência densa de passes (~1000 passes por partida, um a cada ~6 s de jogo).
Recomendação em §7, D8.

**Isto continua sendo evidência indireta.** A medida direta — a distribuição de
`τ = t_anotado − t_D`, com `t_D` o quadro de menor distância passador-bola numa
janela de ±10 s — **não foi feita** e é entregável obrigatório da Fatia 2, com
gatilho de G3 se mais de 5 % dos passes tiverem |τ| > 1 s. Ver `docs/decisoes.md`
e `docs/03-plano.md`, Fatia 2.

---

## 7. Decisões que esta inspeção fecha ou reabre

| | situação |
|---|---|
| **D1** estado da bola | **fechada**: `NaN(bola)`. Ver §5. |
| **D2** bola perfeita | mantida: o simulador só remove jogadores. §2.1 mostra que a Metrica é teto perfeito de jogador. |
| **D6** loaders | **fechada**: jogo 3 legível com a biblioteca padrão. Sem `kloppy`, sem `floodlight`. §4. |
| **D8** critério de acerto | **fechada no G1**: principal = estrito (tipo + jogador + ±1 s); secundários = Vidal-Codina (±10 s) e Mills (3 s). Justificativa corrigida em §6.5. **Verificação direta da defasagem é entregável da Fatia 2, com gatilho de G3.** |
| **D9** tolerâncias | **fechada no G1** por §6.2. `ε_t`, `ε_g`, `ε_k1`, `ε_k2` publicados servem (89–92 %). `ε_c` = 3 m fica no teto limpo **e** vira 2º parâmetro livre — com **baixa confiança declarada**: o conjunto não visto tem 8 escanteios de 3 cobradores (§3.2). |
| **D10** critério de passe | contagens em §3.5. |
| **novo** | o gabarito de bola parada tem de ser ancorado no **primeiro quadro em jogo**, e a linha `SET PIECE` fundida com a linha de execução seguinte. §3.4 e §6.3. |

---

## 8. O que não foi feito

- **Não medi a defasagem `τ` da anotação** (o equivalente direto do S3). É
  entregável obrigatório da Fatia 2 e pode derrubar a janela de ±1 s do D8.
- Não comparei o `events-definitions.pdf` de `documentation/` com o de `refs/`.
- Não medi distância jogador-bola no jogo 3 nem seus gatilhos de bola parada. As
  **contagens** do jogo 3 estão em §3.1 e §3.2; a geometria ficou de propósito
  sem medir, para o jogo 3 continuar sendo conjunto não visto para `ε_c`.
- Não verifiquei o mapeamento `Player` → time no XML do jogo 3 (meu parser de
  `Team` voltou vazio; é detalhe do loader, não da decisão).
- Não medi a distribuição de `ε_s`, `ε_v`, `ε_θ` na Metrica (depende de
  implementar a suavização e as derivadas — é a Fatia 3).
- Não baixei nem abri a SkillCorner nem o suplementar do Bassek.

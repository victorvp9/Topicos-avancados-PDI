# 02 — Dados

Nada em `data/` entra no Git. Baixe os datasets manualmente e coloque nos
caminhos abaixo.

> **Este arquivo foi conferido contra os dados reais em 2026-10-29.** Os esquemas,
> hashes, contagens e armadilhas verificadas estão em
> **`docs/inspecao-metrica.md`**, que prevalece sobre as descrições abaixo onde
> divergirem. Em particular: o caminho é `data/metrica-sample-data` (clone do
> repositório), não arquivos soltos.

---

## Metrica Sports — fonte principal

Repositório: `github.com/metrica-sports/sample-data`

Três partidas. Tracking e event data **sincronizados**. Dados anonimizados (sem
nomes de jogadores, times ou competições). A pasta `documentation/` traz um PDF
com a definição de todos os tipos e subtipos de evento — leia antes de mapear as
classes.

- **Jogos 1 e 2**: CSV padrão da Metrica. 3 linhas de cabeçalho; a linha 3 traz
  `Period, Frame, Time [s]`, depois um par `x,y` por jogador (nome só no primeiro
  dos dois campos) e por fim `Ball` com `x,y`. A bola aparece nos dois arquivos
  (Home e Away), bit a bit idêntica. **Não há z da bola nem booleano
  vivo/morto.** 25 Hz exatos, sem buraco de quadro, `Frame` idêntico entre Home e
  Away. Uma coluna do jogo 2 vem como `Player 26`, com espaço: normalizar o nome.
- **Jogo 3**: EPTS FIFA para o tracking, JSON para os eventos. A Metrica recomenda
  `kloppy`, **mas não é necessário** — `docs/inspecao-metrica.md` §4 e decisão D6.
  O tracking é `frame:p1x,p1y;…;p22x,p22y:bolax,bolay`; o XML traz 11 blocos
  `DataFormatSpecification` com `startFrame`/`endFrame` e 44 `PlayerChannelRef`
  dando a ordem dos campos (as faixas mudam nas substituições). Esquema de
  eventos mais novo: tem `CARRY` (1395), e os subtipos vêm como **lista**.

**Coordenadas.** Normalizadas, `(0,0)` no canto superior esquerdo, `(1,1)` no
inferior direito, `(0.5,0.5)` no centro. Campo de **105 × 68 m** nos três jogos
(no jogo 3 está no XML: `Width = 105`, `Height = 68`, `FrameRate = 25`).

**Conversão obrigatória para o sistema interno** (origem no centro, metros):

```
x_m = (x_norm - 0.5) * 105
y_m = (y_norm - 0.5) * 68   # conferir o sinal: y cresce para baixo na origem
```

O sinal de `y` é armadilha clássica. Escreva um teste que projeta as quatro
bandeirinhas de escanteio e confere que caem em `(±52.5, ±34)`.

> **Não assuma [0,1].** Conferido: jogadores chegam **exatamente** a −0,05 e 1,05
> (recorte em ±0,05, isto é ±5,25 m em x e ±3,40 m em y) e a bola vai de −0,0455
> a 1,0600. **1,671 %** dos quadros do jogo 1 e 0,390 % do jogo 2 têm a bola fora
> de [0,1]. Um clamp silencioso destruiria exatamente os laterais e escanteios,
> que é o que o projeto mede.

**O gabarito e o tracking compartilham a grade de quadros**:
`max |Start Time − Start Frame/25| = 0,000000`. Não há defasagem a estimar — e é
isso que motiva o critério de acerto estrito (D8).

**`Start X`/`Start Y` são sempre NaN nas linhas `SET PIECE`** (0 de 77 e 0 de 80).
A posição de uma bola parada vem do tracking, nunca do gabarito.

**Atenção:** o sistema de coordenadas da Metrica mudou entre as primeiras lições
do Friends of Tracking e as posteriores. Não copie fórmula de tutorial sem
validar contra o dado que você baixou.

**Sentido de ataque.** Inverte no segundo tempo **e difere entre os jogos**:
medido pelo x médio do goleiro, o Home do jogo 1 ataca para +x no P1, e o Home do
jogo 2 ataca para −x no P1 (`docs/inspecao-metrica.md` §2.3). Logo a normalização
é **por jogo e por período, lida do próprio dado**, nunca por convenção fixa.
Registrado em `docs/decisoes.md`.

> Isso importa além da conversão: os gatilhos de escanteio e tiro de meta se
> referem à marca de canto **ativa** e à **própria** pequena área, isto é
> dependem do sentido de ataque (`docs/01-definicoes.md`, Passo 2).

**O tracking de jogador é completo.** São sempre **22 jogadores com dado em todos
os quadros** nos três jogos (22–23 por sobreposição de substituição em 6 e 4
quadros). O NaN por jogador, de 0 % a 89 %, é só substituição. A Metrica é
portanto o teto perfeito que o projeto precisa: **toda perda de visibilidade do
experimento vem do nosso simulador.**

**NaN da bola = bola morta** (decisão D1). 39,14 % / 41,01 % / 32,22 % dos quadros
nos jogos 1 / 2 / 3. Justificativa completa em `docs/inspecao-metrica.md` §5.

---

## Calibração do simulador — alvos publicados vêm primeiro

O alvo de calibração **não depende de baixar dataset nenhum**. Está publicado:

| alvo | valor | origem |
|---|---|---|
| frames sem nenhum jogador visível (TV) | **38 %** (a Discussão, p. 8, diz 41 %) | Bassek, Resultados, p. 6 |
| moda de jogadores visíveis por time (TV) | ~7 (9 % dos frames) | Bassek, p. 6 |
| ≥ 9 por time visíveis (TV) | 20 % do tempo | Bassek, p. 6 |
| 11 de um time visíveis (TV) | 3 % do tempo | Bassek, p. 8 |
| ≥ 9 por time visíveis (scouting feed) | 97 % do tempo | Bassek, p. 6 |
| cortes por partida | **981, ou 10,9/min** | Bassek, p. 8 |
| jogo ativo quando 0 jogadores visíveis (TV) | 21 % ativo, 79 % parado | Bassek, p. 6 |
| tempo de jogo ativo | 56 % ativo, 44 % parado | Bassek, p. 6 |
| visibilidade por posição (TV, distância visível) | GK 14 %, DEF 40 %, MID 52 %, OFF 46 % | Bassek, Tabela 1, p. 6 |
| laterais caindo em replay | **46,8 %** | FOOTPASS, §3.2, p. 6 |
| taxa de detecção por feed | tático 89–96 %, Camera 1 56–64 %, PGM 36–42 % | Crang, Tabela 1, p. 5 |
| RMSE de posição em quadro **não detectado** | 4,58 a 19,38 m | Crang, Tabela 2, p. 6 |
| RMSE de posição em quadro **detectado** | 0,44 a 16,24 m | Crang, Tabela 2, p. 6 |

As duas últimas linhas são o alvo da **Fatia 7**: o erro da nossa interpolação
tem de ser comparado a esses, não a zero.

Achado útil do Bassek para a Fatia 7 (Discussão, p. 8): *"the percentage of time
visible is similar to the percentage of total and high-speed distance covered
while visible in outfield players. This suggests that players are equally active
inside and outside of the field of view."* Ou seja, para jogadores de linha a
ausência é aproximadamente aleatória quanto à velocidade — o que **contraria**
Mortensen e Bornn. É exatamente a hipótese que o nosso entregável "viés da
imputação por faixa de velocidade" testa.

**V7, corrigido:** o suplementar do Bassek **não** promete séries de visibilidade
por jogador. Promete *"All preprocessed intermediate data required to reproduce
the analyses"* (Bassek, *Data and code availability*, p. 10). Código em
`github.com/spoho-datascience/broadcast-analytics`; registro de campo em
`mm4spa.github.io/tvcalib`. **Não depender disso.**

> **Dataset alternativo, não decidido.** O FOOTPASS (§2.1, p. 4) cita o
> *Integrated Dataset of Spatiotemporal and Event Data in Elite Soccer*, de
> Bassek et al. 2025: **7 partidas da Bundesliga** com game-state quadro a quadro
> de sistema multicâmera (verdade de terreno) mais eventos discretos
> hierárquicos, formações e números de camisa. Com 7 partidas o leave-one-game-out
> ficaria bem mais forte que com 3. **Não conferi licença nem disponibilidade.**
> Decisão para depois da Fatia 5, se houver tempo (G3).

---

## SkillCorner — verificação secundária

Repositório atual: `github.com/skillcorner/opendata`

**O repositório mudou de conteúdo.** Hoje traz 10 partidas da A-League
australiana 2024/25, com tracking extrapolado em JSONL, eventos dinâmicos e
fases de jogo em CSV, mais agregados físicos de temporada. Tem módulos Python em
`src/` para carregar e visualizar.

O conjunto **antigo** — 9 partidas das cinco grandes ligas europeias em 2019/20 —
é o mais próximo do que este projeto precisa e continua acessível em forks e via
a biblioteca `floodlight` (`floodlight.io.skillcorner.read_position_data_json`).
Formato antigo, por partida:
- `match_data.json` — escalações, árbitro, dimensões do campo
- `structured_data.json` — lista de frames

Cada frame: `period` (1 ou 2), `frame` (**10 fps**), `timestamp` (precisão de
1/10 s), `data` (lista com jogadores, árbitro principal e bola).

**Coordenadas:** metros, origem no centro do campo. Já é o sistema interno — não
converta.

**O que interessa aqui:** o dado é real de broadcast, então jogadores faltam em
muitos frames. Não é gabarito de evento — é referência de visibilidade, e
**secundária**, porque os alvos numéricos do Bassek e do Crang já bastam e não
exigem download. `floodlight` só entraria se a SkillCorner antiga for usada, e
nesse caso a dependência precisa de justificativa em `docs/decisoes.md`
(CLAUDE.md). **Hoje a decisão D6 é: sem `kloppy` e sem `floodlight`.**

**Primeiro item a cortar se atrasar** — ver `docs/03-plano.md`.

---

## Esquema interno

Todo loader converte para estes dois DataFrames.

> **Esquema revisado e aprovado no G2 da Fatia 1 (2026-10-29).** A versão anterior
> tinha uma tabela só, com a bola como linha `player_id = "ball"` e `team =
> "ball"`, mais rotação global do sentido de ataque. Trocado por três tabelas e
> **nenhuma rotação**. Justificativa em `docs/fatias/01-plano.md` §2.

### `frames` — um registro por quadro e jogo
| coluna | tipo | unidade |
|---|---|---|
| `game` | int | 1, 2, 3 |
| `period` | int | 1 ou 2 |
| `frame` | int | numeração original da Metrica, 1-based |
| `t` | float | s desde o início do **jogo** (= `frame`/25) |
| `ball_x`, `ball_y` | float | m, origem no centro; **NaN preservado** |
| `ball_live` | bool | `not isna(ball_x)` (D1). **Idêntico em todos os níveis de degradação.** |

### `tracking` — um registro por quadro, jogo e jogador **presente**
| coluna | tipo | unidade |
|---|---|---|
| `game` | int | 1, 2, 3 |
| `period` | int | 1 ou 2 |
| `frame` | int | — |
| `player_id` | str | ex. `g1_home_11` |
| `team` | str | `home` / `away` |
| `is_gk` | bool | — |
| `x`, `y` | float | m, origem no centro |
| `visible` | bool | False quando imputado |

### `periods` — sentido de ataque, em vez de rotacionar
| coluna | tipo | domínio |
|---|---|---|
| `game`, `period` | int | — |
| `team` | str | `home` / `away` |
| `attack_dir` | int | `+1` ataca para `+x`; `−1` para `−x` |
| `gk_mean_x` | float | m; o valor que gerou a decisão, para auditoria |

**Não há rotação do tracking.** Os gatilhos do algoritmo são **por time** e já
dependem do sentido ("marca de canto **ativa**", "**própria** pequena área"), logo
`attack_dir` é necessário de qualquer forma e a rotação seria um transform
destrutivo a mais. E há a armadilha: inverter **só** `x` espelha o campo e troca
as pontas; uma rotação correta mexe em `x` **e** `y`.

**Sinal de `y`: cresce para cima.** `y_m = −(y_norm − 0.5) × 68`, porque a Metrica
tem `(0,0)` no canto **superior** esquerdo. Fixado no G2 da Fatia 1.

`visible` tem um só significado: **False = a posição foi imputada**. Nunca
sobrescrever, nunca reaproveitar para "jogador ausente por substituição" — para
isso a linha simplesmente não existe. A distinção medido/imputado tem de
sobreviver até o relatório.

`ball_live` é derivado uma única vez, do tracking completo, por `not NaN(bola)`
(D1), e **congelado**. O simulador não o recalcula. Um teste tem de falhar se
algum nível de degradação produzir `ball_live` diferente do teto.

### `events` (gabarito)
| coluna | tipo | unidade |
|---|---|---|
| `t` | float | s |
| `period` | int | — |
| `type` | str | vocabulário de `docs/01-definicoes.md` |
| `team` | str | — |
| `player_id` | str | — |

O mapeamento das classes da Metrica para o vocabulário interno vai num YAML
explícito, não espalhado em `if`s. Conferido contra os CSVs reais:

| vocabulário interno | Metrica | contagem (j1 / j2 / j3) |
|---|---|---|
| `kickoff` | `SET PIECE`/`KICK OFF` (+ `KICK OFF-RETAKEN`) | 6 / 8 / 4 |
| `corner_kick` | `SET PIECE`/`CORNER KICK` | 11 / 7 / 8 |
| `throw_in` | `SET PIECE`/`THROW IN` (+ `RETAKEN`) | 28 / 32 / 50 |
| `free_kick` | `SET PIECE`/`FREE KICK` (+ `RETAKEN`, `INDIRECT`, `DIRECT`) | 32 / 32 / 28 |
| `goal_kick` | `GOAL KICK` em `PASS` ∪ `BALL LOST` ∪ `BALL OUT` | 22 / 16 / 11 |
| `pass` (principal) | `PASS`, com `CROSS` fundido | 799 / 964 / 1121 |
| `pass` (secundário) | `PASS` ∪ `BALL LOST` ∪ `BALL OUT`, sem `SHOT` e sem `THEFT` | 1086 / 1208 / — |
| fora do escopo | `SHOT`, `CHALLENGE`, `RECOVERY`, `CARD`, `FAULT RECEIVED`, `CARRY`, `SET PIECE`/`PENALTY` | — |

**Duas regras de construção do gabarito, congeladas no G1:**

1. A linha `SET PIECE` e a **linha de execução seguinte** são **um só evento**.
   Em todos os 77 + 80 casos o seguinte é do mesmo jogador, com Δquadro mediano 0
   (`docs/inspecao-metrica.md` §3.4). Tratá-las como duas gera um falso positivo
   de passe por bola parada.
2. Todo evento de bola parada é ancorado no **primeiro quadro em jogo** após o
   intervalo de bola morta, **não** no `Start Frame`. Em
   `BALL LOST`/`GOAL KICK-INTERCEPTION` o `Start Frame` é o ponto da
   interceptação: no quadro 77582 do jogo 1 o executor passa de 49,55 m para
   4,52 m da linha de fundo quando medido corretamente (§6.3).

---

## Armadilhas registradas

- **Coordenadas saem de [0,1].** Nos jogos 1 e 2 os jogadores estão recortados em
  ±0,05 (`max|y|` = 37,4000 m); **o jogo 3 não tem esse recorte** (`max|y|` =
  39,2952 m). Não fazer clamp em nenhum dos casos.
- Unidades: normalizado (Metrica) vs. metros (SkillCorner).
- Frequência: Metrica a 25 fps exatos (`Time = Frame/25` bit a bit), SkillCorner
  a 10 fps. Reamostrar, não assumir.
- Sinal de `y` invertido entre convenções.
- **Sentido de ataque inverte no 2º tempo E difere entre jogos.** Ler do dado.
- **`Start X`/`Start Y` são NaN em todo `SET PIECE`.**
- **Nome de coluna com espaço** (`Player 26`, jogo 2).
- Jogo 3 em formato diferente, com `CARRY` e subtipos em lista — loader separado,
  **dentro** do escopo (D6).
- O `events-definitions.pdf` existe em `refs/` e em
  `data/metrica-sample-data/documentation/`. Não conferi se são o mesmo arquivo.

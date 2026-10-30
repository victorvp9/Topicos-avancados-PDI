# Fatia 1 — Carregar, normalizar e construir o gabarito

Plano para aprovação no **G2**. Escrito pelo orquestrador em 2026-10-29.
Fonte de verdade: `docs/01-definicoes.md`, `docs/02-dados.md`,
`docs/inspecao-metrica.md`, `docs/decisoes.md`.

---

## 1. Objetivo

Transformar os três jogos da Metrica em duas tabelas canônicas mais um gabarito,
com **toda** armadilha conhecida já coberta por teste. Nada de posse, nada de
detecção, nada de simulador.

O critério de aceite global é duro de propósito: **as contagens produzidas pelo
código têm de bater exatamente com as tabelas de `docs/inspecao-metrica.md`**, que
foram medidas por um script independente. Se divergirem, um dos dois está errado e
a fatia não passa.

---

## 2. Decisões de desenho que esta fatia fixa

Três pontos em que eu me afasto da letra do `docs/02-dados.md`. **São o item
principal a aprovar no G2.**

### 2.1 Duas tabelas, e a bola sai da tabela de jogadores

O `docs/02-dados.md` descreve uma só tabela `tracking` com a bola como uma linha
de `player_id = "ball"` e `team = "ball"`, mais uma coluna `ball_live`.

**Proposta:** separar em `tracking` (só jogadores) e `frames` (um registro por
quadro, com a bola e o estado).

Por quê:
- Em formato longo são ~3,3 M de linhas por jogo. Pôr `ball_live`, `ball_x` e
  `ball_y` ali duplica o mesmo valor 22 vezes por quadro, sem ganho.
- O pseudo-time `"ball"` força um caso especial em toda operação por time
  (gatilho de escanteio ativo, pequena área própria, duelo). Tirá-lo é **menos**
  código, não mais.
- O teste do D1b ("`ball_live` idêntico em todos os níveis de degradação") fica
  trivial: compara-se a tabela `frames`, que o simulador nunca toca.

### 2.2 Não rotacionar o tracking; guardar o sentido de ataque como metadado

O `docs/02-dados.md` pede para "normalizar para que o time da casa ataque sempre
no mesmo sentido".

**Proposta:** **não aplicar rotação nenhuma.** Guardar o sentido numa tabela
`periods`, com uma linha por (jogo, período, time) e a coluna
`attack_dir ∈ {+1, −1}`.

Por quê:
- Os gatilhos do algoritmo são **por time** e já dependem do sentido: "marca de
  canto **ativa**", "**própria** pequena área" (`docs/01-definicoes.md`, Passo 2).
  Uma rotação global não resolve isso — o detector precisa de `attack_dir` de
  qualquer jeito. Rotacionar seria um transform destrutivo **a mais**.
- Evita um bug silencioso e feio: inverter **só** `x` espelha o campo e troca as
  pontas esquerda e direita. Se algum dia rotacionarmos, tem de ser `x` **e** `y`
  (giro de 180°), não só `x`.
- Menos código e um transform menos para testar.

### 2.3 Sinal de `y` para cima

`y_m = −(y_norm − 0.5) × 68`, isto é `y` cresce para cima, sistema destro com
`z` para cima. O `docs/02-dados.md` traz a fórmula sem o sinal e com o comentário
"conferir o sinal". **Fixo aqui com o sinal negativo**, porque a Metrica tem
`(0,0)` no canto **superior** esquerdo (README do dataset).

Nada no nosso escopo depende da quiralidade (os gatilhos usam `|y|` e
distâncias), mas a convenção tem de estar escrita uma vez e testada.

---

## 3. Arquivos

```
pyproject.toml                  # uv; pandas, numpy, pyyaml, pytest
config.yaml                     # constantes, cada uma com origem
src/__init__.py
src/io/__init__.py
src/io/metrica_csv.py           # jogos 1 e 2
src/io/metrica_epts.py          # jogo 3
src/io/schema.py                # dataclasses/validação das 4 tabelas
src/gabarito.py                 # mapeamento + fusão + ancoragem
src/run.py                      # argparse; só --inspect nesta fatia
mapeamento-eventos.yaml         # Metrica -> vocabulário interno
tests/test_coordenadas.py
tests/test_loader_csv.py
tests/test_loader_epts.py
tests/test_gabarito.py
tests/test_contagens.py         # bate contra docs/inspecao-metrica.md
```

`uv` apenas. **Nada de pip.** `pyyaml` é dependência nova e é justificada: o
`CLAUDE.md` manda as constantes em `config.yaml` e o `docs/02-dados.md` manda o
mapeamento em "YAML explícito, não espalhado em `if`s". Registrar em
`docs/decisoes.md`.

---

## 4. Esquemas

### `frames` — um registro por quadro e jogo

| coluna | tipo | unidade / domínio |
|---|---|---|
| `game` | int | 1, 2, 3 |
| `period` | int | 1, 2 |
| `frame` | int | numeração original da Metrica, 1-based |
| `t` | float | s desde o início do **jogo** (= `frame`/25) |
| `ball_x`, `ball_y` | float | m, origem no centro; **NaN preservado** |
| `ball_live` | bool | `not isna(ball_x)` (D1) |

### `tracking` — um registro por quadro, jogo e jogador **presente**

| coluna | tipo | unidade / domínio |
|---|---|---|
| `game` | int | 1, 2, 3 |
| `period` | int | 1, 2 |
| `frame` | int | — |
| `player_id` | str | `"g1_home_11"`, estável entre jogos |
| `team` | str | `"home"` / `"away"` |
| `is_gk` | bool | — |
| `x`, `y` | float | m, origem no centro |
| `visible` | bool | **sempre `True` nesta fatia** (nada foi imputado) |

> **Linha de jogador com NaN simplesmente não existe.** Substituição é ausência
> de linha, não `visible = False`, não zero. `visible` tem um único significado:
> `False` = posição imputada (Fatia 7).

### `periods` — sentido de ataque

| coluna | tipo | domínio |
|---|---|---|
| `game`, `period` | int | — |
| `team` | str | `home` / `away` |
| `attack_dir` | int | `+1` ataca para `+x`; `−1` para `−x` |
| `gk_mean_x` | float | m; o valor que gerou a decisão, para auditoria |

### `events` — gabarito

| coluna | tipo | observação |
|---|---|---|
| `game`, `period` | int | — |
| `frame` | int | **quadro canônico do evento** (ver §6) |
| `t` | float | `frame`/25 |
| `type` | str | vocabulário interno (§5) |
| `team` | str | `home` / `away` |
| `player_id` | str | mesmo domínio de `tracking` |
| `annotated_frame` | int | o `Start Frame` cru da Metrica |
| `anchor_shift` | int | `frame − annotated_frame` |
| `no_dead_ball_before` | bool | só bola parada; ver §6.3 |
| `metrica_type` | str | string crua, para auditoria |
| `metrica_subtype` | str | string crua (jogo 3: lista unida por `+`, ordenada) |
| `source_rows` | str | índices das linhas cruas fundidas, ex. `"12,13"` |

`annotated_frame` e `anchor_shift` **não** são enfeite: a Fatia 2 precisa deles
para medir a defasagem `τ` (gatilho de G3).

---

## 5. Mapeamento `mapeamento-eventos.yaml`

Vocabulário interno: `kickoff`, `corner_kick`, `throw_in`, `free_kick`,
`goal_kick`, `pass`. Tudo o mais é `fora_do_escopo` e **fica na tabela** com esse
rótulo (nunca é apagado — precisamos dele para contar falsos positivos).

Regras, nesta ordem:

1. Normalizar o subtipo: no jogo 3 vem **lista**; unir ordenado por `+`. Depois
   separar em `{subtipo principal}` e `{modificadores}`, com
   `modificadores = {RETAKEN, INDIRECT, DIRECT}`.
2. `SET PIECE` + subtipo principal → `kickoff`, `corner_kick`, `throw_in`,
   `free_kick`. `PENALTY` → `fora_do_escopo` (mas ver §6.2).
3. **`goal_kick`**: qualquer evento cujo conjunto de subtipos contenha
   `GOAL KICK`, em `PASS` ∪ `BALL LOST` ∪ `BALL OUT`. (D10 / V16; o `GOAL KICK`
   do jogo 3 aparece até em `END HALF+GOAL KICK`.)
4. **`pass` principal**: `Type == PASS` e `GOAL KICK` ∉ subtipos. Inclui
   `CROSS` (fundido, V9/D10).
5. `pass_secundario`: coluna booleana adicional, `True` para
   `PASS ∪ BALL LOST ∪ BALL OUT` sem `SHOT` e sem `THEFT` e sem `GOAL KICK`
   (D10, critério secundário). **Não** cria linhas novas.
6. Resto → `fora_do_escopo`.

O YAML lista os subtipos **literais** esperados. **Subtipo não listado é erro
duro (`raise`), não aviso.** Se a Metrica tiver uma string que eu não vi, quero
que quebre, não que caia silenciosamente em `fora_do_escopo`.

---

## 6. Construção do gabarito — as duas regras congeladas no G1

### 6.1 Fundir `SET PIECE` com a linha de execução seguinte

Em todos os 247 `SET PIECE` dos três jogos, a linha seguinte é do **mesmo
jogador** com Δquadro mediano 0 (`docs/inspecao-metrica.md` §3.4).

Algoritmo: para cada linha `SET PIECE` no índice `i`, se a linha `i+1` tem o mesmo
`From` e o mesmo `Period`, as duas formam **um** evento: o `type` vem do
`SET PIECE`, e a linha `i+1` **não** gera um evento `pass` próprio.
`source_rows = "i,i+1"`.

Se a linha `i+1` **não** casar (mesmo `From` e `Period`), **`raise`**. Eu medi 157
de 157 casos nos jogos 1 e 2; no jogo 3 não medi essa propriedade. Se o jogo 3
quebrar, quero saber, não contornar.

### 6.2 Ancorar no primeiro quadro em jogo

Para todo evento de bola parada (`kickoff`, `corner_kick`, `throw_in`,
`free_kick`, `goal_kick`, e também `PENALTY` embora fora do escopo):

```
i  = annotated_frame
j  = maior índice <= i com ball_live[j] == False      # último quadro morto
frame = j + 1                                          # primeiro quadro em jogo
```

Se não existir tal `j` (nenhum quadro morto em ou antes de `i`): `frame = i`,
`no_dead_ball_before = True`.

Justificativa e caso concreto em `docs/inspecao-metrica.md` §6.3: em
`BALL LOST`/`GOAL KICK-INTERCEPTION` o `Start Frame` é o ponto da interceptação, e
o quadro 77582 do jogo 1 passa de 49,55 m para 4,52 m da linha de fundo quando
ancorado certo.

Eventos de jogo corrido (`pass`) **não** são ancorados: `frame = annotated_frame`.

### 6.3 O pontapé inicial do quadro 1 do jogo 1

É o único caso conhecido de `no_dead_ball_before = True`. **Permanece no
gabarito**, com `frame = 1`. Nunca removido, nunca excluído do denominador
(`docs/decisoes.md`). Um teste garante que ele está lá.

---

## 7. `config.yaml`

Só o que esta fatia usa, mais a geometria que a Fatia 4 vai precisar (é o mesmo
bloco). As tolerâncias `eps_*` **não** entram agora — entram na Fatia 4, com as
origens já documentadas em `docs/01-definicoes.md`.

```yaml
dados:
  raiz: data/metrica-sample-data/data
  commit: e706dd506b360d69d9d123d5b8026e7294b13996   # inspecao-metrica.md §1
  jogos: [1, 2, 3]

tracking:
  fps: 25            # medido: todos os dt = 0,04 s; max|Time - Frame/25| = 0
                     # inspecao-metrica.md §2; jogo 3: FrameRate=25 no XML

campo:
  # conferido: README do dataset e XML do jogo 3 (Width=105, Height=68)
  comprimento_m: 105.0
  largura_m: 68.0
  # IFAB Lei 1, valores padrão. NAO CONFERIDO em fonte primária:
  # nenhum PDF das Regras do Jogo está em refs/. Marcado para conferência.
  pequena_area_profundidade_m: 5.5     # [IFAB Lei 1, nao conferido]
  pequena_area_meia_largura_m: 9.16    # = (7.32 + 2*5.5)/2 [IFAB Lei 1, nao conferido]
  grande_area_profundidade_m: 16.5     # [IFAB Lei 1, nao conferido]
  grande_area_meia_largura_m: 20.16    # [IFAB Lei 1, nao conferido]
  marca_penal_m: 11.0                  # [IFAB Lei 1, nao conferido]
  raio_impedido_penalti_m: 9.15        # CONFERIDO: Vidal-Codina 2.3.4, p. 6

gabarito:
  mapeamento: mapeamento-eventos.yaml
  ancorar_bola_parada_no_primeiro_quadro_vivo: true   # decisoes.md, G1
  fundir_set_piece_com_execucao: true                 # decisoes.md, G1
```

> **Dívida explícita:** a geometria da pequena e da grande área está marcada
> `[IFAB Lei 1, nao conferido]`. É a única constante da Fatia 4 que não tem fonte
> primária em `refs/`. Entra em `outputs/origem-dos-numeros.md` com esse rótulo.
> **O escanteio e o lateral não dependem dela**; só o tiro de meta depende.

---

## 8. Testes obrigatórios, com critério de aceite

Todos têm de passar. Um teste que "quase passa" reprova a fatia.

### 8.1 Coordenadas (`test_coordenadas.py`)

| teste | critério de aceite |
|---|---|
| bandeirinhas | os 4 cantos normalizados `(0,0) (1,0) (0,1) (1,1)` projetam em `(−52.5, +34) (+52.5, +34) (−52.5, −34) (+52.5, −34)`, tolerância `1e-9` |
| centro | `(0.5, 0.5)` → `(0.0, 0.0)` exato |
| sinal de `y` | `y_norm = 0` → `y_m = +34`; isto é, `y` cresce para cima |
| **sem clamp** | `max(ball_x)` do jogo 1 = **58,7958 m** e `min(ball_x)` = **−57,2754 m**; `max\|y\|` de jogador = **37,4000 m** nos jogos 1 e 2. Tolerância `1e-4`. Hardcoded de propósito: um teste que recalcula a fórmula não detecta clamp aplicado antes dela. |
| ida e volta | converter e desconverter devolve o valor normalizado original, `1e-12` |

### 8.2 Loaders (`test_loader_csv.py`, `test_loader_epts.py`)

| teste | critério de aceite |
|---|---|
| nº de quadros | 145006 / 141156 / 143761 |
| quadros por período | jogo 1: 71268 e 73738; jogo 2: 67941 e 73215 |
| grade de quadros | `frame` de 1 a N, sem buraco e sem duplicata, nos 3 jogos |
| relógio | `max \|t − frame/25\| == 0.0` exatamente |
| jogadores por quadro | exatamente 22 em 145000 / 141152 / 143761 quadros; exatamente 23 em 6 / 4 / 0 quadros; **nenhum outro valor** |
| `ball_live` | quadros mortos = 56755 / 57884 / 46325 (frações 39,14 % / 41,01 % / 32,22 %) |
| NaN não virou zero | nenhum `x` ou `y` de jogador é exatamente `0.0` por imputação; o nº de linhas de `tracking` = soma dos jogadores presentes por quadro |
| nome com espaço | o jogo 2 tem o jogador `Player 26` e ele aparece como `g2_away_26`, não `g2_away_ 26` |
| bola nos 2 arquivos | o `Ball_x`/`Ball_y` do arquivo Home e do Away são **bit a bit idênticos**; o loader usa um e o teste confere o outro |
| jogo 3, faixas | 11 blocos `DataFormatSpecification` lidos; as faixas cobrem 1..143761 sem lacuna nem sobreposição |
| jogo 3, canais | 44 `PlayerChannelRef` por bloco; a ordem dos campos da linha segue o bloco vigente para aquele quadro |
| esquema idêntico | as colunas e os `dtype` de `frames`/`tracking` são iguais nos três jogos |

### 8.3 Sentido de ataque (`test_loader_csv.py`)

| teste | critério de aceite |
|---|---|
| `attack_dir` | as 8 combinações de (jogo 1 e 2) × período × time batem com `docs/inspecao-metrica.md` §2.3: jogo 1 Home `+1` no P1 e `−1` no P2; jogo 1 Away `−1` e `+1`; jogo 2 Home `−1` e `+1`; jogo 2 Away `+1` e `−1` |
| inverte | para todo (jogo, time): `attack_dir[P1] == −attack_dir[P2]` |
| times opostos | para todo (jogo, período): `attack_dir[home] == −attack_dir[away]` |
| sem rotação | `tracking.x` é igual à conversão direta do CSV cru, sem sinal trocado |

### 8.4 Gabarito (`test_gabarito.py`, `test_contagens.py`)

| teste | critério de aceite |
|---|---|
| contagens por `Type` | batem **exatamente** com `docs/inspecao-metrica.md` §3.1 nos 3 jogos (ex.: `PASS` 799 / 964 / 1121) |
| bola parada por tipo | `corner_kick` 11 / 7 / 8; `throw_in` 28 / 32 / 50; `free_kick` 32 / 32 / 28; `kickoff` 6 / 8 / 4; total `SET PIECE` 77 / 80 / 90 |
| `goal_kick` | 22 / 16 / 11 |
| **fusão** | o gabarito tem **247** eventos de bola parada no total, **não 494**; nenhuma linha de execução fundida gera um `pass` extra |
| fusão, casamento | para todos os 247, `source_rows` tem 2 índices e os dois têm o mesmo `From` e `Period` |
| ancoragem | todo evento de bola parada tem `anchor_shift <= 0` (o primeiro quadro vivo nunca é depois do anotado) e `ball_live[frame] == True`, **exceto** o caso de `no_dead_ball_before` |
| quadro 1 do jogo 1 | existe um `kickoff` com `game=1, frame=1, no_dead_ball_before=True`. É o **único** `no_dead_ball_before` nos 3 jogos |
| caso 77582 | o `goal_kick` com `annotated_frame=77582` (jogo 1) tem `frame` tal que o executor está a menos de 6,0 m da própria linha de fundo |
| subtipo desconhecido | injetar um subtipo inventado num CSV de teste faz o loader **levantar exceção**, não cair em `fora_do_escopo` |
| nada é apagado | nº de eventos no gabarito + nº de linhas fundidas = nº de linhas cruas, nos 3 jogos |
| `pass_secundario` | 1086 / 1208 eventos `True` nos jogos 1 e 2 |
| `THEFT` | 21 / 38 eventos com `THEFT` no subtipo, todos com `pass_secundario = False` |

### 8.5 Contra falha silenciosa

Da lista de `docs/03-plano.md`, os itens que já se aplicam:

- **(2) evento não detectado é perda de revocação** — o teste do quadro 1 do
  jogo 1 garante que ele não desaparece.
- **(3) NaN nunca conta como acerto nem é descartado** — `ball_y` NaN preservado;
  linhas de jogador ausente não viram zero.
- **(7) `ball_live` idêntico entre níveis** — nesta fatia só existe o teto; o
  teste é um `hash` da tabela `frames` por jogo, gravado como valor esperado para
  a Fatia 6 comparar.
- **(8) `visible` nunca sobrescrito** — assert `tracking.visible.all()` nesta
  fatia.

### 8.6 Saída

`python -m src.run --inspect` imprime, por jogo: nº de quadros, períodos,
fração de bola morta, jogadores por quadro, `attack_dir`, contagens de evento por
tipo interno e por `Type` cru. **O que ele imprime tem de bater com
`docs/inspecao-metrica.md`** — é a conferência manual do Victor.

---

## 9. O que fica FORA desta fatia

- Posse, PZ, DZ, control frames, Savitzky-Golay, derivadas, `eps_s`, `eps_v`,
  `eps_theta` → **Fatia 3**.
- Qualquer detecção de evento, gatilho, padrão, hierarquia, `eps_c`, `eps_t`,
  `eps_g`, `eps_k1`, `eps_k2`, `eps_f` → **Fatia 4**.
- O casador de eventos, as métricas P/R/F1 e a medição da defasagem `τ` →
  **Fatia 2**.
- Simulador, `visible = False`, interpolação → **Fatias 6 e 7**.
- SkillCorner, Bassek, figuras, `--all`.
- Reamostragem de frequência: os três jogos são 25 Hz. **Não escrever
  reamostrador** (regra do `CLAUDE.md`: sem abstração antes de dois casos reais).
- Cache e manifesto de semente: não há execução longa aqui. **Fatia 8.**

---

## 10. Riscos conhecidos

1. **O jogo 3 pode quebrar a fusão `SET PIECE` + execução.** Medi 157 de 157 nos
   jogos 1 e 2; no jogo 3 só contei os totais. O plano manda `raise`. Se quebrar,
   é G3 e eu decido a regra com o dado na mão.
2. **O jogo 3 tem `CARRY` (1395).** Vai para `fora_do_escopo`. Mas se um `CARRY`
   aparecer entre um `SET PIECE` e a execução, a fusão falha. Coberto pelo
   `raise`.
3. **Geometria da pequena área não conferida** (§7). Não afeta esta fatia.
4. **`attack_dir` pelo x médio do goleiro** pressupõe identificar o goleiro.
   Nos jogos 1 e 2 é a primeira coluna de cada arquivo (`Player11`, `Player25`).
   No jogo 3 **não conferi** qual canal é o goleiro. Alternativa robusta e sem
   essa dependência: usar o x médio de **todos** os jogadores do time, cujo sinal
   é o mesmo. O codificador deve usar a média do time inteiro e **testar que as
   duas formas concordam** nos jogos 1 e 2.

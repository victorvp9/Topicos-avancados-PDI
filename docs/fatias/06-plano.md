# Fatia 6 — Simulador de broadcast

Plano do orquestrador, 2026-11-04. G2 decidido por mim (delegação de 2026-10-30),
com registro em `docs/decisoes.md`, seção "Fatia 6 — plano".

## 1. Objetivo

Produzir, para cada jogo, variante, nível e semente, o **tracking degradado** que um
broadcast teria visto, com calibração contra alvos publicados e validação contra
outros alvos publicados **não usados no ajuste**. A fatia **não mede F1 sob
degradação**: isso é a Fatia 8, depois que a regra de escolha de `R_pz` por
leave-one-game-out estiver escrita (D4). Olhar F1 degradado agora seria olhar o
resultado antes da regra.

## 2. Fontes conferidas nesta data (página = página do PDF)

| fato | valor | origem |
|---|---|---|
| quadros sem jogador visível, por time (TV) | 38 % | Bassek, Resultados, p. 6 (a Discussão, p. 8, diz 41 %) |
| quando 0 visíveis (TV): ativo / parado | 21 % / 79 % | Bassek, Resultados, p. 6 |
| tempo ativo / parado | 56 % / 44 % | Bassek, Resultados, p. 6 |
| moda de visíveis por time (TV) | ~7 (9 %) | Bassek, Resultados, p. 6 |
| ≥ 9 visíveis por time (TV) | 20 % | Bassek, Resultados, p. 6 |
| 11 visíveis de um time (TV) | 3 % | Bassek, Discussão, p. 8 |
| cortes | 981 por jogo, 10,9/min | Bassek, Discussão, p. 8 |
| **distância percorrida visível** (TV) | GK 14 %, DEF 40 %, MID 52 %, OFF 46 % | Bassek, Resultados, **p. 6, texto** |
| n por posição | GK 8, DEF 28, MID 17, OFF 14 | Bassek, Tabela 1, **p. 7** |
| "tempo visível ≈ distância visível" nos de linha | — | Bassek, Discussão, p. 8 |
| filtro das posições | Butterworth 3ª ordem, corte 1 Hz | Bassek, Métodos, p. 4 |
| suavização da câmera estimada | Savitzky-Golay, janela 31, grau 3 | Bassek, Métodos, p. 4 |
| janela 40 × 40 m centrada em eventos | Mortensen e Bornn, criticada | Bassek, Introdução, p. 3 |
| player-frames **detectados** (GK excluídos) | PGM 36–42 %, Camera 1 56–64 %, tático 89–96 % | Crang, Tabela 1, p. 5; GK fora, p. 3 |
| Camera 1 = a maior parte do PGM, **sem replays nem troca de ângulo** | — | Crang, Métodos, p. 2 |
| "detected" ≠ "visible" (oclusão também tira) | — | Crang, Métodos, p. 3 |
| laterais cujo quadro cai em replay | 46,8 % | FOOTPASS, §3.2, p. 6 |

**Três achados da conferência, que mudam o plano:**

1. **Os 14/40/52/46 % estão no texto da p. 6, não na Tabela 1 (p. 7).** O `docs/02`
   citava "Tabela 1, p. 6". Pior: a **razão das médias** da Tabela 1 (visível ativo +
   inativo sobre GT ativo + inativo, coluna TV) dá **13,9 / 36,6 / 46,2 / 42,1 %**,
   isto é 4 a 6 pontos abaixo do texto nos jogadores de linha. Provavelmente o texto
   é média de razões por jogador; não conferi. **Alvo = o texto**, que é a afirmação
   explícita; a versão da Tabela 1 é reportada ao lado como incerteza do alvo.
2. **O Crang mede detecção, não visibilidade, e exclui o goleiro.** Logo as faixas
   dele são **limite inferior** da nossa taxa de visibilidade sem GK, não alvo pontual.
3. **"Camera 1" do Crang é exatamente "geometria sem cortes", e PGM é "geometria +
   cortes".** Isso dá à varredura um caminho com dois pontos de ancoragem publicados
   (§4.4), em vez de um parâmetro inventado.

## 3. O que o simulador produz, e o que nunca toca

- **Saída = subconjunto das linhas de `tracking`**, com todas as colunas idênticas
  ao original. Jogador fora da visão **não tem linha** naquele quadro.
- **`visible` não é usado para marcar "fora da câmera".** O `docs/02-dados.md` dá a
  `visible` um único significado (False = posição imputada), e o "jogador ausente
  por substituição" já é linha inexistente. O `docs/03-plano.md` dizia "marca
  `visible=False` para quem cai fora", em conflito com o esquema congelado; o esquema
  prevalece e o texto do `03` foi corrigido. Quem escreve `visible=False` é a
  reconstrução da Fatia 7.
- **Nunca tocados:** `frames` (bola e `ball_live`, D1b e D2), `periods`
  (`attack_dir`), `events`. Os três vêm do carregamento completo e são oráculo,
  declarado. `attack_dir` é oráculo porque um sistema real conhece o lado de cada
  time sem precisar ver o goleiro.

## 4. Modelo

### 4.1 Alvo da câmera (as duas variantes)

Por período: nos quadros vivos, `(ball_x, ball_y)`; em cada corrida morta,
**interpolação linear** entre a última posição viva antes e a primeira depois (o
operador já leva a câmera ao ponto do reinício: a câmera não teleporta). Corrida
morta no início do período usa a primeira posição viva; no fim, a última. Depois,
**Savitzky-Golay janela 31, grau 3** em `x` e `y` por período (constante do Bassek,
p. 4, que suavizou com ela a homografia estimada; aqui reaproveitada como suavidade
do movimento da câmera; **reaproveitamento declarado**, sem fonte para este uso). O
alvo **nunca** é NaN.

### 4.2 Variante A — janela fixa (linha de base ingênua)

Visível ⇔ `|x − cx| ≤ L/2` e `|y − cy| ≤ L/2`. Parâmetro do nível: `L` (m); `L = ∞`
deixa todos visíveis **pelo mesmo caminho de código**. Sem cortes. Desvio
declarado: Mortensen e Bornn centram em locais de **evento**, nós no alvo da §4.1.
O ponto `L = 40` m é reportado como referência.

### 4.3 Variante B — cunha (frustum 2D) mais cortes editoriais

**Geometria.** Câmera fixa em `(0, −(W/2 + d_cam))`, com `W` = 68 m do config.
Visível ⇔ o ângulo entre `(p − câmera)` e `(alvo − câmera)` é ≤ `θ/2`. Parâmetro
do nível: `θ`; `θ = ∞` deixa todos visíveis pelo mesmo caminho.
**`d_cam` = 30 m é suposição de modelagem sem fonte publicada (não conferi
nenhuma)**, fixada **antes** de medir e **não** escolhida pelo ajuste; a
sensibilidade a 15 e 60 m é reportada (bloco 6).

**Cortes.** Cadeia de Markov de dois estados por quadro, `on` (câmera principal) e
`off` (close, replay, outra câmera: **nenhum jogador visível**, a bola continua).
O estado começa `on` em cada período. Com `s` = estado da bola no quadro, `c` =
intensidade do nível e `u_t` ~ U[0,1):

```
off_t = u_t < q(estado_{t-1}),   q(on) = c · a_s,   q(off) = 1 − b
```

Três parâmetros calibrados: `a_vivo`, `a_morto` e `b`, este último comum aos dois
estados. **Esta forma de acoplamento é obrigatória**: com `c·a_s ≤ 1 − b`, o
conjunto de quadros `off` é **monótono em `c` para a mesma semente**, o que torna os
níveis comparáveis quadro a quadro (números aleatórios comuns). O teste da §7 trava
isso.

**Usar `ball_live` para dirigir os cortes não é vazamento**: o diretor conhece o
estado do jogo. O D1b já declara `ball_live` oráculo.

### 4.4 Calibração (alvos externos; nenhum evento detectado é olhado)

Tudo em **valor esperado, sem sorteio**. A probabilidade `p_t = P(off_t)` sai da
recursão exata da cadeia, logo a calibração é determinística e não depende de
semente. Os 3 jogos vão juntos.

Usar o jogo 3 aqui **não** viola o D9b. A calibração olha só posições e os
instantes anotados de lateral; não olha escanteio nem saída de detector.

1. **Cortes** `(a_vivo, a_morto, b)` por mínimos quadrados, pesos iguais, com três
   alvos:
   - `P(off | vivo)` = 0,21 × 0,38 / 0,56 = **0,1425**;
   - `P(off | morto)` = 0,79 × 0,38 / 0,44 = **0,6823**;
   - `P(off)` nos quadros-âncora `frame` das laterais do gabarito = **0,468**
     (FOOTPASS).

   Calibra-se pelas **condicionais**, não pela marginal de 38 %, porque a nossa
   fração de bola morta (39/41/32 %) difere dos 44 % do Bassek; a condicional
   transfere, a marginal não. Aproximação declarada: "0 jogadores visíveis do
   time" ≈ quadro `off`.
2. **Papéis.** Por (jogo, time), os jogadores de linha são ordenados pelo `x`
   médio no sentido de ataque (`x · attack_dir`, nos quadros em que estão
   presentes). Com quantil `q = (posto − 0,5)/n`:
   - DEF se `q < 28/59`;
   - OFF se `q > 1 − 14/59`;
   - MID nos demais.

   As proporções 28/17/14 são as do próprio Bassek (Tabela 1, p. 7); com n = 10
   dão 5/3/2. GK vem de `is_gk`.
3. **`θ*`** minimiza, com `c = 1` e os cortes do passo 1, o erro quadrático entre a
   distância visível esperada por papel e **0,14 / 0,40 / 0,52 / 0,46**, com pesos
   iguais. É busca escalar em `θ` ∈ [5°, 180°].
   - Distância visível = Σ passos com o jogador visível no quadro de chegada / Σ
     passos.
   - Posições filtradas por Butterworth de 3ª ordem e 1 Hz com `filtfilt`, por
     segmento contíguo de presença em cada período.
   - Segmento curto demais para o `padlen` padrão: `padlen = len − 1`. Os casos
     são contados e reportados.
4. **Níveis**, 8 por variante, fixados uma vez e escritos no `config.yaml` com a
   origem "saída de `python -m src.run --simulador`":

| nível | B (cunha + cortes) | A (janela) |
|---|---|---|
| 1 | `θ = ∞`, `c = 0` | `L = ∞` |
| 2–4 | `θ` com taxa esperada `1 − k(1 − r₅)/4`, k = 1, 2, 3; `c = 0` | `L` com a mesma taxa esperada de B_k |
| 5 | `θ*`, `c = 0` ("Camera 1") | idem |
| 6, 7 | `θ*`, `c` = 1/3, 2/3 | idem |
| 8 | `θ*`, `c = 1` ("PGM/TV") | idem |

- `r₅` é a taxa esperada de B5.
- **Taxa de detecção** = linhas visíveis / linhas presentes, com todos os quadros e
  todos os jogadores, GK incluído. Também é reportada sem GK, para comparar com o
  Crang, e só em bola viva.
- Bisseção até |Δtaxa| < 1e-4.
- O nível de A tem a **mesma taxa** do nível de B. Com isso a comparação entre
  variantes isola a **estrutura** da falta do dado, e não o volume dela.

### 4.5 Validações pré-registradas (não entram no ajuste; reportar, nunca reajustar)

| validação | alvo | leitura |
|---|---|---|
| B5 sem GK | Crang Camera 1: 56–64 % | limite inferior (detecção ≤ visibilidade) |
| B8 sem GK | Crang PGM: 36–42 % | limite inferior |
| B8, distribuição de visíveis por time | moda ~7; ≥ 9 em ~20 %; 11 em ~3 % | ordem de grandeza |
| B8, cortes por minuto (trocas on↔off) | ≤ 10,9 | o Bassek conta também troca de ângulo, que não modelamos |
| B8, `P(0 visíveis)` marginal | ≠ 38 % **por desenho** | esperado ≈ 0,1425 × f_viva + 0,6823 × f_morta |
| resíduo da calibração dos cortes | — | resíduo > 5 pontos: limitação registrada, **não** troca de modelo |

**Critério de parada, escrito antes:** se em B8 o **GK não sair o papel menos
visível**, o simulador não reproduz o mecanismo que motivou o requisito (`docs/03`,
Fatia 6), e a fatia para em G3 (eu, com registro) antes de qualquer uso.

### 4.6 Observação de desenho, escrita ANTES de medir

A cunha segue a bola. No tiro de meta, a bola está perto do goleiro, logo **a
geometria tende a mostrar o goleiro exatamente quando o gatilho precisa dele**. O GK
é o menos visível **na média** porque a bola costuma estar longe dele, e não
necessariamente no tiro de meta.

Se isso valer, o colapso do tiro de meta previsto em 2026-11-01 só pode vir dos
**cortes**, que atingem toda bola parada. Nesse caso a previsão "o tiro de meta
degrada mais rápido que lateral e escanteio" **pode falhar**, e isso valerá como
desmentido.

O bloco 7 mede o precursor **só em visibilidade, sem detector**. Não altero o
simulador por causa disso: a cunha vem da estrutura publicada (TV segue a bola), e
não da previsão.

## 5. Arquivos

- `src/broadcast.py` (nome já previsto em `docs/03`):
  - `alvo_camera(frames, cfg) -> DataFrame[game, period, frame, cx, cy]`;
  - `p_off(frames, params, c) -> ndarray` (recursão exata);
  - `amostrar_off(frames, params, c, semente) -> ndarray[bool]`;
  - `na_cunha(...)`, `na_janela(...)`, `papeis(tracking, periods, cfg)`;
  - `degradar(tracking, frames, cfg, variante, nivel, semente) -> tracking`;
  - `calibrar(base, cfg) -> dict`.

  Cada função tem esquema no docstring.
- `src/run.py`:
  - `_carregar_base(..., degradacao=None)`, onde `degradacao = (variante, nivel,
    semente)`. Troca **só** o `tracking` antes do Passo 1 e da grade de posições.
    `frames`, `periods` e `eventos` vêm do carregamento completo, intactos.
  - `--simulador`, com os blocos da §6.
- `config.yaml`, seção `simulador:` com:
  - `d_cam_m`: 30, suposição;
  - `sg_janela`: 31 e `sg_grau`: 3 (Bassek, p. 4);
  - `butter_ordem`: 3 e `butter_corte_hz`: 1 (Bassek, p. 4);
  - os alvos da §4.4 com a página;
  - `proporcoes_papel` 28/17/14;
  - `semente_base`: 20261104;
  - `n_sementes`: 5 (`docs/03`, Fatia 8);
  - os parâmetros calibrados e os 8 níveis por variante.

  Cada constante leva a origem.
- `tests/test_broadcast.py` (sintético) e `tests/test_simulador_real.py` (dados
  reais).
- `outputs/origem-dos-numeros.md`: seção da Fatia 6, com cada número → bloco do
  `--simulador`.

**Semente.** `SeedSequence([semente_base, game, rep])`, com `rep` de 0 a
`n_sementes − 1`. **Não depende de nível nem de variante** (números aleatórios
comuns). Nenhum uso do estado global do `np.random`. `degradar` exige `semente`
explícita, sem padrão.

## 6. Blocos de `python -m src.run --simulador`

1. Cortes: parâmetros ajustados, cada alvo contra o obtido, resíduos.
2. Papéis: contagem por (jogo, time, papel) e o `x` médio de cada jogador.
3. `θ*`: distância visível por papel contra 14/40/52/46 do texto e contra
   13,9/36,6/46,2/42,1 da Tabela 1; tempo visível por papel; segmentos curtos
   contados.
4. Níveis A1–A8 e B1–B8:
   - o parâmetro e a taxa esperada de cada nível;
   - a taxa amostrada por jogo, mín.–máx. nas 5 sementes;
   - a mesma taxa sem GK e só em bola viva;
   - a lista das sementes efetivas;
   - a comparação com os valores do `config.yaml`, com a marca "confere" ou "DIFERE".
5. Validações da §4.5, cada uma com "dentro", "acima" ou "abaixo".
6. Sensibilidade, diagnóstica: `θ*` e resíduos por papel com `d_cam` = 15 e 60 m.
   **Não** troca o `d_cam`.
7. Precursor da previsão, só visibilidade, sem detector. Para cada nível e cada
   tipo de bola parada do gabarito:
   - a fração esperada de visibilidade do **executor anotado** no quadro anotado;
   - a fração esperada de quadros da corrida morta anterior com **algum jogador do
     time do executor na própria pequena área** visível;
   - o mesmo do item anterior, só para o GK.

**Proibido nesta fatia:** chamar `avaliar` ou `micro` sobre tracking degradado,
imprimir P/R/F1 degradado, e contar detecções degradadas por tipo.

## 7. Testes obrigatórios (critério de aceite = o teste falha se a coisa quebrar)

| # | teste | arquivo | aceite |
|---|---|---|---|
| T1 | **A1 e B1 reproduzem o teto bit a bit**, pelo caminho geométrico normal (`θ = ∞`, `L = ∞`, `c = 0` pela cadeia, sem atalho `if infinito: return`) | real | `assert_frame_equal(check_exact=True)` do tracking nos 3 jogos. No jogo 1, `perdas`, `ganhos`, detecções de bola parada e passes rotulados iguais aos de `_carregar_base(degradacao=None)` |
| T2 | bola e oráculos intactos | real | Nos 16 níveis, semente 0, jogo 1: `frames` (bola e `ball_live`), `periods` e `eventos` iguais ao original. A saída é **subconjunto** das linhas originais, com `x`/`y` idênticos nas linhas mantidas |
| T3 | monotonia | real + sintético | Taxa esperada não decrescente em `θ` e em `L` (grade) e não crescente em `c`. Máscara amostrada **aninhada** com a mesma semente: B1 ⊇ … ⊇ B5 ⊇ B6 ⊇ B7 ⊇ B8 e A1 ⊇ … ⊇ A8 |
| T4 | parâmetro varrido e ignorado faz teste falhar | real, jogo 1 | Mudar `θ`, `L`, `c`, `d_cam`, `a_vivo`, `a_morto`, `b`, `sg_janela` ou a semente (com `c > 0`) **muda** a máscara. Com `c = 0`, mudar a semente **não** muda |
| T5 | sementes | sintético | Mesma semente dá a mesma saída. Mexer no `np.random` global entre chamadas não muda nada. Os uniformes de (jogo, rep) são iguais entre níveis e variantes |
| T6 | geometria | sintético | Cunha: ponto a `θ/2 − ε` dentro e a `θ/2 + ε` fora. Janela: borda inclusiva. Alvo: interpolação linear exata na corrida morta, sem NaN, e as bordas do período mantidas |
| T7 | recursão exata = Monte Carlo | sintético | Média de 1000 amostras de `off` contra `p_off` com \|Δ\| < 0,01 por quadro, em média, numa série de 10 mil quadros com troca vivo/morto. `c = 0` dá `p_off ≡ 0` |
| T8 | config reproduz a calibração | real | Recalibrar reproduz `a_*`, `b` e `θ*` com tolerância de 1e-6 relativa, e os níveis com \|Δtaxa\| < 1e-4 |
| T9 | papéis | sintético | 10 de linha com `x` crescente → 5 DEF, 3 MID, 2 OFF. Com `attack_dir = −1` a ordem inverte |
| T10 | distância visível | sintético | Velocidade constante: o filtro preserva a distância (erro < 1 %). Metade dos quadros visíveis em bloco dá 0,5 |
| T11 | pipeline sob degradação | real, jogo 1 | B8 e A8 com semente 0 rodam Passo 1, bola parada e passes sem exceção, com o esquema validado. **Não** imprime nem asserta F1 |
| T12 | proibição da §6 | — | Teste ou `grep` que falha se `src/broadcast.py` importar `evaluate` |

Não se aplicam aqui, de propósito:

- **cache por hash**: a Fatia 6 não cacheia; o cache é da Fatia 8;
- **NaN como acerto e evento não detectado**: a Fatia 6 não avalia nada.

**Custo:** a suíte nova deve rodar em menos de 3 min e o `--simulador` em menos de
5 min. Bem abaixo do G4.

## 8. Fora do escopo

- F1 degradado (Fatia 8).
- Reconstrução (Fatia 7).
- Cache.
- SkillCorner (corte nº 3 do `docs/03`).
- Zoom variável dentro de um nível e troca para outras câmeras com o campo à vista.
- Oclusão (o Crang mede detecção, e a nossa taxa é de visibilidade).
- Degradação da bola (D2).
- Trocar `d_cam`, os alvos ou a forma da cadeia depois de ver a calibração; isso
  seria mudança declarada, com o que depender dela virando exploratório.

## 9. Relatório do codificador

- Saída integral do `--simulador`.
- `pytest` com a contagem.
- Lista de arquivos tocados.
- Toda lacuna que ele tiver preenchido, cada uma com a alternativa descartada.
- Tempo de parede do `--simulador`.

## 10. Emenda de 2026-11-04 — MUDANÇA DECLARADA (G3 por mim), antes de qualquer F1 degradado

**O que se viu.** O ajuste da §4.4, passo 1, convergiu, com mínimo único em três
pontos iniciais, para `b` = 0,3245 e `a_morto` no limite do acoplamento. Os três
alvos ficaram com resíduo < 1 ponto, mas os episódios `off` duram ~3 quadros:
**332,5 trocas on↔off por minuto contra ≤ 10,9 do Bassek** (p. 8). É um pisca-pisca
quadro a quadro, não corte editorial.

**Causa.** O quadro-âncora da lateral é o primeiro quadro vivo. Com uma taxa
`b` sem memória, o alvo de 0,468 nele contra 0,68 na bola morta só fecha com
`1 − b ≈ 0,468/0,68`.

**Por que muda.** Pisca-pisca e corte longo atingem o detector de modos opostos:
- o gatilho "completo" exige o jogador visível até o último quadro morto;
- o problema 2 do S1 exige o executor sumir em `[di+1, dc]`.

Com o modelo como está, a Fatia 8 mediria um artefato da calibração.

**Mudança.** A taxa de trocas deixa de ser validação e vira **restrição do ajuste**:
minimizar os mesmos três resíduos, com pesos iguais, sujeito a:
- trocas on↔off esperadas por minuto em B8 (`c` = 1), nos 3 jogos juntos e em
  todos os quadros, **≤ 10,9** (Bassek, Discussão, p. 8);
- o acoplamento `c·a_s ≤ 1 − b`.

É limite superior, porque o Bassek conta também as trocas de ângulo.

**O que não muda:**
- a forma da cadeia;
- os alvos;
- `θ*` pelo mesmo procedimento, recalculado com os novos cortes;
- os níveis, que são regerados;
- a regra da §4.5, que segue de pé: resíduo > 5 pontos é limitação registrada, não
  troca de modelo. O resíduo da lateral deve crescer (a sondagem do codificador
  com `b` pequeno deu 9 a 23 pontos), e isso vai para o relatório.

**Rótulo.** Nenhum F1 degradado foi visto. O que se viu foi um diagnóstico do próprio
simulador, previsto como validação. Por isso o que depender deste simulador continua
**limpo**, com esta emenda citada.

Alternativas descartadas:
- **Tirar o alvo da lateral:** joga fora o único alvo publicado sobre o mecanismo
  que mais importa para bola parada.
- **Trocar para uma cadeia com duração explícita:** constantes novas sem fonte.

**B5 sem GK = 0,5321 depois da emenda (era 0,545 antes dela), abaixo do limite inferior de 0,56 do Crang Camera 1.** Fica
como validação reprovada por 2,8 pontos, só registrada (§4.5). Jogo e estádio são
outros, e `θ*` vem do Bassek.

**T7.** O meu critério "|Δ| < 0,01 por quadro em média com 1000 amostras" era
inviável: só o ruído de Monte Carlo dá ≈ 0,013. Fica a leitura do codificador
(|média Δ| < 0,01; média |Δ|/σ_MC < 1; idem nos quadros de transição). Erro meu de
plano.

### 10.1 Resultado da emenda e leitura da revisão (2026-11-04)

- **A restrição fica INATIVA no ótimo (2,87 trocas/min), mas é ela que escolhe a
  bacia.** Sem ela, o ótimo volta ao pisca-pisca (`b` = 0,3245, custo 3,8e-5, 332
  trocas/min). Com ela, todos os pontos iniciais caem no mínimo interior (custo
  0,0112). Os parâmetros ficam assim:
  - `a_vivo` ≈ 0: nenhum corte começa com a bola viva;
  - `a_morto` = 0,00595;
  - `b` = 0,00301, o que dá episódios `off` de ~13 s.
- **Os resíduos de −11 pontos em `P(off|morto)` e +9,6 pontos na lateral são
  ESTRUTURAIS, não falha de ajuste** (demonstração do revisor):
  - dentro de uma corrida morta, `p` sobe de forma monotônica;
  - logo `P(off)` no primeiro quadro vivo é maior ou igual à média da corrida morta;
  - os alvos pedem o contrário: 0,468 na âncora contra 0,682 na bola morta.

  O menor resíduo máximo possível é ~10,3 pontos, com ou sem restrição. Leitura: o
  modelo esconde a lateral **mais** que o FOOTPASS e a bola morta **menos** que o
  Bassek. Causa provável: a bola morta do Bassek pesa as paradas longas, e as
  definições de "inativo" diferem. Fica como limitação, pela §4.5.
- **Validações reprovadas, todas registradas e nenhuma reajustada:**
  - B5 sem GK: 0,532 contra ≥ 0,56;
  - B8 P(≥ 9 por time): 0,073 contra ~0,20;
  - B8 P(11): 0,007 contra ~0,03;
  - GK +5,1 pontos acima do alvo.

  O padrão sugere que a cunha de abertura fixa sub-representa os planos abertos
  (zoom, fora do escopo pela §8).

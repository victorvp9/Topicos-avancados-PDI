# Fatia 2 — Avaliação

Plano para aprovação no **G2**. Escrito pelo orquestrador em 2026-10-29.
Fonte de verdade: `docs/01-definicoes.md` (Avaliação), `docs/03-plano.md`
(Fatia 2), `docs/decisoes.md` (D8, D10 e as armadilhas da Fatia 1),
`docs/inspecao-metrica.md`.

**A avaliação vem antes de detectar qualquer coisa.** É a regra não negociável do
`docs/03-plano.md`, e a razão é que queremos um número desde o primeiro dia, e
queremos que o casador esteja certo antes de haver qualquer F1 para ele proteger.

---

## 1. Objetivo

Duas coisas, uma de biblioteca e uma de medição.

1. **Casador de eventos e métricas.** Entra um gabarito e um conjunto de
   detecções; sai precisão, revocação, F1, contagem absoluta e **matriz de
   confusão**, por tipo, por jogo e por critério. Não existe detector ainda: a
   entrada de detecções vem só de fixtures e de perturbações do gabarito.
2. **Medir a defasagem `τ` da anotação**, nos três jogos. Esta é a parte que
   produz número de verdade agora, e ela carrega um **gatilho de G3**: se mais de
   5 % dos passes tiverem `|τ| > 1 s`, a janela de ±1 s do D8 está contradita e eu
   **paro antes de qualquer detector**.

---

## 2. Os três critérios, com a correção que eu descobri relendo o S2

**Correção importante.** O `docs/01-definicoes.md` apresentava os três critérios
numa tabela que sugeria que todos casam por tipo. **Não é verdade.** Conferido no
suplementar S2, p. 3:

> *"A discrete event is correctly detected if it is executed by the annotated
> player and is within a ±10 s window of the annotated time."*

Não há exigência de tipo. E a seguir: *"present the detection results using
confusion matrices"*. Ou seja, **no critério do Vidal-Codina a comparação de tipo
É a matriz de confusão**, não uma condição de casamento. Isso é o que permite ver
escanteio virando tiro livre — exatamente o erro (1) que o artigo lista (§2.4.1,
p. 8) e que a nossa inspeção prevê em 44 % dos escanteios.

Os três critérios diferem em três escolhas binárias:

| critério | casa por tipo? | casa por jogador? | janela | origem |
|---|---|---|---|---|
| **estrito** (principal) | **sim** | **sim** | **±1,0 s** | **nosso**, D8 |
| Vidal-Codina | **não** (vai para a matriz) | sim | ±10,0 s | supl. S2, p. 3 |
| Mills | sim | **não** | 3,0 s | Mills §2.2, p. 4 |

O critério estrito **é nosso**, não de nenhum artigo: é a conjunção das duas
restrições com a janela apertada que o D8 justifica. Tem de aparecer rotulado
assim em todo lugar onde for reportado.

Janela **inclusiva**: casa se `|Δt| <= janela`. Declarado aqui porque é a
diferença entre um acerto e um erro nos casos de borda, e um teste fixa isso.

### 2.1 Matriz de confusão, por grupo

O S2, p. 3, agrupa os eventos e apresenta **uma matriz por grupo**, não uma
matriz gigante. Seguimos:

- **Grupo bola parada:** `kickoff`, `corner_kick`, `throw_in`, `goal_kick`,
  `free_kick`, **`free_kick?`**, e a linha/coluna `none`.
- **Grupo jogo corrido:** `pass` e `none`.

`free_kick?` é categoria de primeira classe (S2, p. 3, e Fig. S1, p. 2): sinaliza
que o algoritmo se confundiu. **Nunca somar em `free_kick`.** Na Fatia 2 ela só
existe como coluna possível de detecção; quem a produz é a Fatia 4.

Linha = tipo anotado, coluna = tipo detectado. A linha `none` são os falsos
positivos; a coluna `none` são os falsos negativos. **Toda linha soma a contagem
do gabarito; toda coluna soma a contagem de detecções.** Dois testes fixam essas
duas identidades — é a checagem de que nada foi perdido nem inventado.

---

## 3. O casamento é um-para-um e ÓTIMO, não guloso

O Mills diz só "iterative comparison" (§2.2, p. 4), o que não especifica o
algoritmo. Guloso por "mais próximo no tempo" é o óbvio, e **está errado em casos
que vão acontecer aqui**: com ~1000 passes por partida e uma janela de ±10 s, há
muitos candidatos, e o guloso pode consumir uma detecção que era a única opção de
outro evento anotado, perdendo um casamento que existia.

**Decisão: atribuição ótima**, com objetivo lexicográfico —
**(1) maximizar o número de pares casados; (2) entre os casamentos máximos,
minimizar `Σ|Δt|`.** Implementação padrão com
`scipy.optimize.linear_sum_assignment` sobre uma matriz de custo em que:

- par permitido (passa pelas restrições de tipo/jogador/janela) → custo `|Δt|`;
- par proibido → custo `M`, com `M` maior que a soma de todos os `|Δt|`
  possíveis;
- depois da atribuição, **descartar todo par cujo custo seja `M`**.

Isso é determinístico e dá o ótimo lexicográfico. **Teste obrigatório:** um caso
construído em que o guloso casa 1 par e o ótimo casa 2, provando que a escolha
importa e que a implementação é a ótima.

`scipy` é dependência nova, mas **já está na pilha aprovada do `CLAUDE.md`**
("pandas, numpy, scipy, matplotlib, pytest"). Justificar em `docs/decisoes.md`
mesmo assim.

---

## 4. Arquivos

```
src/evaluate.py          # casador, métricas, matriz de confusão
src/tau.py               # medição da defasagem da anotação
src/run.py               # + subcomando --tau
config.yaml              # + blocos avaliacao e tau
tests/test_casador.py
tests/test_metricas.py
tests/test_confusao.py
tests/test_tau.py
```

Nada mais. Não criar `src/report.py`, não criar camada de "backend de métrica",
não generalizar o casador para N critérios configuráveis além dos três.

---

## 5. Esquemas

### `detections` — entrada do casador

Mesmo domínio de `events` (`docs/02-dados.md`), com o mínimo:

| coluna | tipo | observação |
|---|---|---|
| `game`, `period` | int | — |
| `frame` | int | — |
| `t` | float | s, = `frame`/25 |
| `type` | str | vocabulário interno, mais `free_kick?` |
| `team` | str | `home` / `away` |
| `player_id` | str | mesmo domínio de `tracking` |

### `resultado` — saída do casador

| coluna | tipo | observação |
|---|---|---|
| `criterio` | str | `estrito` / `vidal_codina` / `mills` |
| `ancora` | str | `frame` / `annotated_frame` (ver §7) |
| `game` | int | e uma linha agregada com `game = 0` |
| `type` | str | tipo do **gabarito** |
| `n_gabarito` | int | **contagem absoluta, sempre reportada** |
| `n_detectado` | int | — |
| `tp`, `fp`, `fn` | int | — |
| `precisao`, `revocacao`, `f1` | float | `NaN` quando o denominador é 0 |

**`NaN` quando o denominador é zero, nunca 0,0.** Precisão de uma classe sem
nenhuma detecção é indefinida, não zero; tratá-la como zero mente na média. E
`NaN` nunca conta como acerto nem é descartado.

### `tau` — saída da medição

Uma linha por passe: `game, period, annotated_frame, player_id, frame_d,
tau_s, d_min_m, d_no_quadro_anotado_m`.

---

## 6. A medição de `τ` — o entregável com gatilho de G3

Réplica deliberada da análise do suplementar S3, p. 5, para ser comparável.

Para cada evento de tipo `pass` do gabarito (os três jogos, n = 722 + 889 + 1039
= **2650**), com o jogador anotado:

1. Janela de `±10 s` (±250 quadros) centrada em `annotated_frame`.
2. Em cada quadro da janela em que **a bola e o jogador anotado têm dado**,
   calcular a distância entre os dois.
3. `frame_d` = quadro de **distância mínima**. `d_min_m` = essa distância.
4. **`tau_s = (annotated_frame − frame_d) / 25`.** Sinal conferido no S3, p. 5:
   *"Positive time lags indicate minimum distance in tracking data occurred
   before the annotated event time"* — logo `τ > 0` significa que a anotação veio
   **depois**.
5. Se o jogador anotado não tiver dado em nenhum quadro da janela, `tau_s` e
   `d_min_m` ficam `NaN` e o evento **continua na tabela**, contado como
   "sem medida". Nunca descartado.

**Reportar:** média, mediana, e as frações com `|τ| > 1 s`, `> 3 s`, `> 5 s`,
`> 7,5 s`, por jogo e no total. Mais a distribuição de `d_min_m` nas faixas
`< 0,5 m`, `< 1 m`, `< 1,5 m`, para comparar com os provedores do S3.

### 6.1 O gatilho de G3, escrito antes de medir

> **Se mais de 5 % dos passes (sobre o total dos três jogos, excluindo os "sem
> medida" do numerador mas **não** do denominador) tiverem `|τ| > 1 s`, a janela
> de ±1 s do critério principal está contradita. O codificador PARA, relata, e
> eu levo ao Victor no G3 antes de qualquer detector rodar.**

Referências para interpretar o número: na STS, a média é **+1,5 s**, com **16 %**
acima de 5 s e **8 %** acima de 7,5 s (supl. S3, p. 5). Se a Metrica der algo
parecido com isso, o D8 cai.

O limiar de 5 % é meu e é arbitrário dentro de uma ordem de grandeza; está escrito
antes de medir, que é o que importa. **Se o resultado cair entre 3 % e 8 %, tratar
como ambíguo e trazer ao G3 de todo modo**, em vez de passar raspando.

### 6.2 Checagem de sanidade da própria medição

A mesma rotina, avaliada **no quadro anotado** em vez do de mínimo, tem de
reproduzir a §6.4 da inspeção: `d < 0,5 m` em **96,7 %** (jogo 1) e **97,4 %**
(jogo 2) dos passes, mediana **0,08–0,09 m**. Se não reproduzir, a medição está
errada e não se tira conclusão nenhuma dela. **Teste obrigatório.**

---

## 7. Sensibilidade da âncora

`docs/01-definicoes.md` declara o risco: a ancoragem faz o instante do gabarito de
bola parada vir de `ball_live`, o mesmo sinal que dispara o detector, o que
trivializa a dimensão temporal do casamento.

**Todo resultado de bola parada é reportado nas duas âncoras**, em `frame` e em
`annotated_frame` (as duas colunas já existem desde a Fatia 1). Daí a coluna
`ancora` no esquema de saída. Jogo corrido não precisa: `anchor_shift = 0` sempre
para `pass`.

---

## 8. `config.yaml` — acréscimos

```yaml
avaliacao:
  criterio_principal: estrito        # D8, decisoes.md
  janela_inclusiva: true             # casa se |dt| <= janela
  criterios:
    estrito:                         # NOSSO, nao de artigo. D8.
      janela_s: 1.0
      casa_tipo: true
      casa_jogador: true
    vidal_codina:                    # suplementar S2, p. 3
      janela_s: 10.0
      casa_tipo: false               # o tipo vai para a matriz de confusao
      casa_jogador: true
    mills:                           # Mills, secao 2.2, p. 4
      janela_s: 3.0
      casa_tipo: true
      casa_jogador: false
  denominador_passe_secundario: events   # 1009/1131/1358. decisoes.md
  ancoras: [frame, annotated_frame]      # sensibilidade, 01-definicoes.md

tau:
  janela_s: 10.0                 # mesma do suplementar S3, p. 5, para comparar
  limiar_g3_tau_s: 1.0           # a janela do criterio principal
  limiar_g3_fracao: 0.05         # criterio escrito antes de medir. decisoes.md
  faixa_ambigua: [0.03, 0.08]    # dentro disto, levar ao G3 de todo modo
```

---

## 9. Testes obrigatórios, com critério de aceite

### 9.1 Casador (`test_casador.py`)

| teste | critério de aceite |
|---|---|
| gabarito contra si mesmo | F1 = 1,0 em **todos** os tipos e nos **três** critérios, nos 3 jogos |
| deslocado 30 s | F1 = 0,0 em todos os tipos e critérios |
| deslocado 2 s | **F1 = 0 no estrito e 1,0 no Vidal-Codina** — prova que os critérios são distintos de verdade, não três nomes para a mesma coisa |
| deslocado 2 s, Mills (3 s) | F1 = 1,0 |
| metade removida | revocação = 0,5, precisão = 1,0 |
| **todas** duplicadas | precisão = 0,5, revocação = 1,0. (Corrigido em 2026-10-30: o rótulo dizia "metade duplicada", que daria 0,667. Vale o número.) |
| borda da janela | `Δt` exatamente 1,000 s casa no estrito; 1,001 s não casa |
| jogador errado | mesmo tipo e tempo, jogador diferente → **FN + FP** no estrito e no Vidal-Codina; **acerto** no Mills |
| tipo errado | mesmo jogador e tempo, tipo diferente → **FN + FP** no estrito; **acerto** no Vidal-Codina, caindo na célula (anotado, detectado) da matriz |
| **ótimo vs guloso** | caso construído em que o guloso casa 1 e o ótimo casa 2; o casador tem de casar 2 |
| um-para-um | duas detecções válidas para um anotado → 1 TP e 1 FP; dois anotados para uma detecção → 1 TP e 1 FN |
| **`no_dead_ball_before` não filtra** | os **13** eventos com a marca continuam no denominador. Impacto medido de filtrá-los: **+2,25 pontos** no F1 agrupado de bola parada e **+18,4 pontos na revocação de tiro de meta** (9 dos 13 são `goal_kick`). A estimativa anterior de "até 4 %" estava errada nos dois sentidos. |
| **empate de quadro** | o jogo 1 tem duas linhas `pass` no quadro **59923** com jogadores diferentes; o casador não quebra e as duas são avaliadas |
| NaN no tempo | um evento com `t = NaN` **não** casa e **não** sai do denominador |
| determinismo | permutar a ordem das linhas de entrada não muda nenhum número |

### 9.2 Métricas e matriz (`test_metricas.py`, `test_confusao.py`)

| teste | critério de aceite |
|---|---|
| denominador zero | precisão com 0 detecções = `NaN`, **não** 0,0; idem revocação com 0 anotados |
| `NaN` não propaga como acerto | `NaN` nunca entra em `tp` |
| contagem absoluta | `n_gabarito` por tipo bate com `docs/inspecao-metrica.md` §3.2 nos 3 jogos |
| linhas da matriz | toda linha soma `n_gabarito` daquele tipo |
| colunas da matriz | toda coluna soma `n_detectado` daquele tipo |
| `free_kick?` separado | um `free_kick?` detectado **nunca** é somado em `free_kick` |
| grupos separados | bola parada e jogo corrido saem em matrizes distintas, como no S2, p. 3 |
| agregado | a linha `game = 0` é a soma das três, não a média dos F1 |

### 9.3 `τ` (`test_tau.py`)

| teste | critério de aceite |
|---|---|
| sinal de `τ` | trajetória sintética com mínimo 2 s **antes** do instante anotado → `τ = +2,0 s` (convenção do S3, p. 5) |
| sanidade, jogo 1 | `d` no quadro anotado `< 0,5 m` em **96,7 %** dos passes, mediana 0,08–0,09 m |
| sanidade, jogo 2 | idem, **97,4 %** |
| n | 722 / 889 / 1039 passes medidos, total **2650** |
| "sem medida" fica | passe cujo jogador não tem dado na janela → `τ = NaN`, e **continua na tabela** |
| janela | o mínimo é buscado em exatamente ±250 quadros, recortado nas bordas do jogo |
| gatilho de G3 | a função devolve a fração com `|τ| > 1 s` e um booleano `g3`; teste sintético com 10 % acima de 1 s → `g3 = True` |

### 9.4 Contra falha silenciosa

Da lista de `docs/03-plano.md`: **(1)** mudar `janela_s` de qualquer critério tem
de mudar a saída — um teste por critério; **(3)** `NaN` nunca conta como acerto
nem é descartado; **(2)** nada é excluído do denominador, inclusive os 13
`no_dead_ball_before`.

### 9.5 Saída

`python -m src.run --tau` imprime, por jogo e no total: n, média, mediana, as
quatro frações de `|τ|`, as três faixas de `d_min`, a reprodução da §6.4, e **em
destaque** se o gatilho de G3 disparou. Grava `outputs/tau.csv`.

---

## 10. O que fica FORA

- **Qualquer detector.** Nada de posse, PZ, gatilho, padrão, hierarquia, `eps_*`.
  As detecções da Fatia 2 vêm só de fixtures e de perturbações do gabarito.
- Simulador, `visible=False`, interpolação, varredura, cache, manifesto.
- Figuras. A Fatia 2 produz tabela e CSV, não gráfico.
- Relatório em markdown (Fatia 8).
- Não generalizar o casador para critérios arbitrários além dos três do
  `config.yaml`.

---

## 11. Riscos conhecidos

1. **O gatilho de G3 pode disparar.** É o ponto da fatia. Se disparar, a Fatia 2
   entrega o casador e a medição, e o D8 vai ao Victor antes de qualquer detector.
2. **A sanidade da §6.2 pode não reproduzir.** Eu medi 96,7 % / 97,4 % com um
   script efêmero e o `From` normalizado por `replace(" ", "")`. Se o código bater
   em 96,5 % ou 97,6 %, não é "quase": é sinal de que uma das duas medições está
   errada, e o codificador **para e relata** em vez de afrouxar a tolerância.
3. **`M` grande na matriz de custo** pode dar problema numérico se mal
   dimensionado. Usar `M = 1 + soma de todos os |Δt| permitidos`, e um teste que
   verifica que nenhum par com custo `M` sobrevive.
4. **Memória do casador** com ±10 s e ~1000 passes: a matriz de custo por (jogo,
   tipo, critério) é no máximo ~1000×1000, trivial. Mas **não** construir uma
   matriz global de todos os jogos juntos.

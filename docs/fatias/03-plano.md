# Fatia 3 — Posse (Passo 1 da especificação)

Plano escrito pelo orquestrador em 2026-10-30. **Decisões tomadas por mim**, com
o Victor delegando ("pode seguir tomando as decisões com o que achar melhor",
30/10). Todas as lacunas de especificação que eu resolvi estão marcadas
**[LACUNA]** e vão para `docs/decisoes.md`.

Fonte de verdade: `docs/01-definicoes.md` (Passo 1), `docs/decisoes.md`
(D1, D3, D9c), `docs/03-plano.md` (Fatia 3).

---

## 1. Objetivo

1. **Implementar o Passo 1**: PZ/DZ, control frames, suavização, perda e ganho de
   posse. Entrada: as tabelas da Fatia 1. Saída: série de `ball_control` quadro a
   quadro e tabelas de perdas e ganhos.
2. **Medir `τ_posse` e DECIDIR A JANELA DO D8**, pela regra já pré-registrada em
   `docs/03-plano.md`, Fatia 3. Esta é a dívida que a Fatia 2 deixou.
3. **Medir as distribuições reais de `ε_s`, `ε_v` e `ε_θ`** na Metrica —
   diagnóstico, não ajuste (D9c).
4. **Medir o tempo de parede por jogo e por `R_pz`**, que substitui a minha
   extrapolação de "3 min por partida" no orçamento do G4 da Fatia 8.

Nenhuma detecção de evento. Isso é a Fatia 4.

---

## 2. Regra nova de exigência de teste

A Fatia 2 ensinou que **"existe teste e ele passa" não basta**: três vezes um
teste rodava no caminho em que o erro é invisível. Portanto, neste plano **cada
teste obrigatório declara em que caminho roda**, e em particular:

- todo teste de uma função de agregação ou de razão roda **pelo menos uma vez num
  caminho em que os numeradores candidatos divergem**;
- todo parâmetro de `config.yaml` tem teste que falha se o **valor** for ignorado,
  não só se o nome mudar.

---

## 3. As lacunas de especificação, e como eu as resolvi

O artigo não cobre cinco casos de borda que o dado real produz. Resolvi todos
pelas restrições estruturais do próprio artigo, nunca por heurística nova.

### 3.1 [LACUNA] Dono único quando vários jogadores têm a bola na PZ

Com `R_pz` até 3,00 m (D3), vários jogadores terão a bola na PZ ao mesmo tempo. O
artigo define a PZ por jogador e não diz quem é o dono.

**Decisão: o dono é o jogador MAIS PRÓXIMO da bola.** É a regra de desempate que o
próprio artigo usa no caso análogo (§2.4.1, p. 7: *"If there are multiple
triggering players within the pattern zone and within `R_pz` of the ball, we
choose the closest player to the ball as the executor"*). Empate exato de
distância: o de `player_id` menor, para ser determinístico; registrar quantas
vezes ocorre (espero zero).

### 3.2 [LACUNA] "Dois adversários na DZ"

**Decisão: duelo quando há pelo menos um jogador de CADA time dentro de `R_dz`
da bola.** É a leitura literal de "two opponents" — dois jogadores que são
adversários entre si. E o duelo prevalece sobre a posse (§2.3.1, p. 4).

### 3.3 [LACUNA] `d0`/`v0` no primeiro quadro de uma corrida viva

`d0_f` usa `f−1` e `d1_f` usa `f+1`. No primeiro quadro em jogo após uma bola
morta não existe `f−1` com dado de bola.

**Decisão: `d0`/`v0` são `NaN` no primeiro quadro de cada corrida viva, e
`d1`/`v1` são `NaN` no último. `NaN` NUNCA conta como mudança.** O teste de
direção `d0_f0 · d1_fn < ε_θ` com qualquer dos dois `NaN` é **indefinido** e é
tratado como "não mudou de direção"; o ganho então depende só do teste de
velocidade. Isso é conservador e é consistente com a regra congelada "NaN nunca
conta como acerto nem é descartado".

Consequência registrada: o **primeiro toque de uma bola parada** pode não ter
teste de direção. Isso não é problema, porque bola parada é detectada por gatilho
e padrão (§2.4.1, p. 7), não por ganho de posse.

### 3.4 [LACUNA] Até onde buscar o "control frame seguinte `fc > f`"

A condição 2 da perda (§2.3.2, p. 5) exige que A **não** apareça no control frame
seguinte. O artigo não diz se a busca atravessa um intervalo de bola morta.

**Decisão: `fc` é buscado SÓ dentro da mesma corrida viva contígua.** Se não
houver control frame posterior na mesma corrida, a condição 2 está satisfeita.

Justificativa estrutural, não conveniência: o §2.4.1, p. 7, estabelece
**correspondência um-para-um entre evento de bola morta (DBE) e bola parada
(SPE)**, e o DBE é *"the event immediately preceding a dead ball interval"*
(§2.2, p. 4). Logo **toda** corrida viva tem de terminar num evento, isto é numa
perda. Se a busca atravessasse a bola morta, uma bola que sai de campo não geraria
perda sempre que o mesmo jogador reaparecesse em controle depois do reinício — e a
correspondência um-para-um quebraria.

### 3.5 [LACUNA] A perda no último quadro de uma corrida viva

No último quadro em jogo, `f+1` é morto, logo "a bola está fora da PZ de A em
`f+1`" e `Δs_f` são os dois **indefinidos**. A regra literal não se aplica.

**Decisão: ao fim de cada corrida viva, o último jogador em controle recebe uma
perda no seu último control frame, independentemente das condições 1 e 2.** Pela
mesma correspondência um-para-um do §3.4: o intervalo de bola morta exige um DBE
imediatamente antes.

Alternativa descartada: avaliar a regra literal no penúltimo quadro. Descartada
porque deixaria corridas de 1 quadro sem perda e porque a condição 1 existe para
distinguir "bola parada e jogador se afastando" de perda real (Fig. 3b1) — uma
distinção que não faz sentido no instante em que o jogo para.

**Marcar essas perdas com `forcada_por_bola_morta = True`**, para que a Fatia 4
possa distinguir e para que o relatório possa reportar quantas são. Espero ~155 e
~169 (o número de corridas de NaN de `docs/inspecao-metrica.md` §2.4).

### 3.6 [LACUNA] Suavização atravessando buracos

`savgol_filter` sobre uma série com buracos de `NaN` produz lixo, ou propaga
`NaN`. E a bola é `NaN` em 32 a 41 % dos quadros (D1).

**Decisão: a suavização é aplicada por corrida viva contígua, nunca através de uma
bola morta. Corrida mais curta que a janela (7 quadros) fica sem suavizar**, e
isso é contado e reportado.

**Decisão: a suavização fica DESLIGADA por padrão no teto.** O artigo a condiciona
(*"If the ball positional data has been smoothed"*, §2.3.1, p. 5) e a bola da
Metrica é verdade de terreno multicâmera, não ruidosa. Fica como chave de
`config.yaml` e o relatório traz os dois números — é o experimento barato que o
`docs/01-definicoes.md` recomenda, e importa de verdade na Fatia 7, onde a
interpolação introduz ruído.

---

## 4. Arquivos

```
src/possession.py        # PZ/DZ, control frames, perdas e ganhos
src/suavizar.py          # Savitzky-Golay por corrida viva
src/tau_posse.py         # a medicao com o gatilho de G3 e a escada
src/run.py               # + --posse e --tau-posse
config.yaml              # + bloco posse
tests/test_posse_zonas.py
tests/test_posse_perda.py
tests/test_posse_ganho.py
tests/test_suavizar.py
tests/test_tau_posse.py
```

Nada mais. Não criar `src/kinematics.py`, não criar classe `Possession`, não
generalizar para "N estratégias de suavização".

---

## 5. Esquemas

### `control` — um registro por quadro em jogo que tem posse ou duelo

| coluna | tipo | observação |
|---|---|---|
| `game`, `period`, `frame`, `t` | — | — |
| `ball_control` | str | `possession` / `duel` |
| `owner_id` | str | dono (mais próximo); `NaN` se `duel` |
| `owner_team` | str | — |
| `d_owner_m` | float | distância do dono à bola |
| `ds_m` | float | deslocamento da bola de `f` a `f+1`; `NaN` no último quadro da corrida |
| `d0_x`, `d0_y`, `v0` | float | entrada, de `f−1`; `NaN` no primeiro da corrida |
| `d1_x`, `d1_y`, `v1` | float | saída, para `f+1`; `NaN` no último |
| `run_id` | int | identificador da corrida viva contígua |

`d0`/`d1` são **vetores unitários** (`docs/01-definicoes.md`): é isso que torna o
produto escalar comparável a um cosseno.

A série completa de `ball_control` por quadro, incluindo `dead_ball` e
`no_possession`, é derivável de `frames` + `control`; **não** materializar uma
terceira tabela de 435 mil linhas só para isso.

### `perdas` e `ganhos`

| coluna | tipo | observação |
|---|---|---|
| `game`, `period`, `frame`, `t` | — | — |
| `player_id`, `team` | str | — |
| `run_id` | int | — |
| `forcada_por_bola_morta` | bool | só em `perdas`, ver §3.5 |
| `ds_m` | float | só em `perdas`: o `Δs` que passou de `ε_s` |
| `mudou_direcao`, `mudou_velocidade` | bool | só em `ganhos` |
| `d0d1` | float | só em `ganhos`: o produto escalar; `NaN` se indefinido |
| `dv_max` | float | só em `ganhos`: o máximo de `\|v0−v1\|` na sequência |

### `tau_posse`

Uma linha por evento `pass` do gabarito: `game, annotated_frame, player_id,
loss_frame, tau_posse_s, tem_perda`.

---

## 6. A medição de `τ_posse` e a decisão da janela

### 6.1 Definição, construída para NÃO repetir o erro da Fatia 2

Na Fatia 2 eu misturei duas coisas num só número e o resultado foi inútil. Aqui a
decomposição é explícita **antes** de medir:

Para cada evento `pass` do gabarito (n = 2650), com o jogador anotado:

1. Procurar perdas de posse **desse jogador** numa janela de ±10 s em torno de
   `annotated_frame`.
2. Se não houver nenhuma → `tem_perda = False`, `tau_posse_s = NaN`. A linha
   **fica na tabela**.
3. Se houver, `loss_frame` = a mais próxima no tempo, e
   `tau_posse_s = (annotated_frame − loss_frame) / 25`.

**Duas grandezas, reportadas separadas, e elas respondem a perguntas diferentes:**

| grandeza | o que mede | onde entra |
|---|---|---|
| fração com `tem_perda = False` | **teto de revocação de passe**: o detector não produziu perda alguma para aquele jogador perto dali | resultado, não portão |
| distribuição de `\|τ_posse\|` **entre os que têm perda** | **a janela é larga o bastante?** dado que o detector disparou para o jogador certo | **o portão** |

Um passe sem perda é problema de **revocação**, não de janela. Misturar os dois
foi exatamente o meu erro da Fatia 2.

### 6.2 A regra de decisão, já pré-registrada

De `docs/03-plano.md`, Fatia 3, escrita **antes** desta medição:

> A janela passa a ser o **menor valor da escada {1,0; 1,5; 2,0; 3,0} s** tal que
> **no máximo 5 %** dos passes tenham `|τ_posse|` maior que a janela. Se 1,0 s já
> satisfaz, o D8 está confirmado. Se nem 3,0 s satisfaz, **parar e levar ao G3**.
> Nenhum valor fora da escada. Se a janela mudar, todo número já reportado com
> ±1 s é **recalculado**, não rerrotulado.

**Denominador da regra: os passes COM perda** (§6.1). A fração sem perda é
reportada em destaque ao lado, e se ela for alta (digamos acima de 20 %) eu levo
ao G3 de todo modo, porque aí o portão está medindo pouca coisa.

**A medição da regra usa `R_pz` = 0,50 m**, o valor congelado de partida (D9c).
Sensibilidade em `R_pz` = 1,00 m vai ao relatório, mas **não** decide — senão a
escolha da janela passaria a depender de um parâmetro que ainda vamos varrer.

### 6.3 O que fazer com o resultado

O codificador **reporta e para**. Quem aplica a escada sou eu, e registro em
`docs/decisoes.md` antes de qualquer recálculo.

---

## 7. Diagnóstico das constantes (D9c), sem ajustar nada

Medir e reportar, sobre o dado real:

- distribuição de `ds_m` nos control frames, e qual fração dos passes anotados
  teria `Δs > ε_s` com `ε_s` = 5 cm (congelado) e com 10 cm (o valor dos
  provedores B e C);
- distribuição de `dv_max` nas sequências de controle, contra `ε_v` = 1 m/s
  (congelado) e 5 m/s;
- distribuição de `d0d1`, contra `ε_θ` = cos 10° ≈ 0,9848.

**Isto é diagnóstico.** Mudar qualquer um dos três depois de ver estas
distribuições seria **mudança declarada** (D9c) e tornaria exploratório tudo o que
dependesse. O relatório diz isso explicitamente.

---

## 8. `config.yaml` — acréscimos

```yaml
posse:
  r_pz_m: 0.50                 # valor de partida, D9c; grade em D3
  r_dz_m: 1.00                 # = max(1,0; r_pz), D3
  eps_s_m: 0.05                # supl. S4.2, p. 8 (provedor A). D9c
  eps_v_ms: 1.0                # supl. S4.2, p. 8 (provedor A). D9c
  eps_theta: 0.984807753012208 # cos 10 graus. supl. S4.2, p. 8. D9c
  suavizar: false              # DESLIGADA no teto; ver plano 03 §3.6
  savgol_ordem: 2              # sec. 2.3.1, p. 5
  savgol_janela_quadros: 7     # sec. 2.3.1, p. 5
  empate_distancia_m: 1e-9     # tolerancia de empate no dono mais proximo

tau_posse:
  janela_busca_s: 10.0         # mesma da Fatia 2, para comparabilidade
  escada_janela_s: [1.0, 1.5, 2.0, 3.0]   # pre-registrada, 03-plano Fatia 3
  limiar_fracao: 0.05                     # pre-registrado
  limiar_sem_perda_g3: 0.20               # acima disto, G3 de todo modo
  r_pz_da_decisao_m: 0.50                 # a decisao nao depende da varredura
```

---

## 9. Testes obrigatórios, com critério de aceite E o caminho em que rodam

### 9.1 Zonas (`test_posse_zonas.py`) — sintético e dado real

| teste | caminho | critério de aceite |
|---|---|---|
| bola a 0,4 m de um jogador | sintético | posse dele com `R_pz` = 0,5; **sem** posse com `R_pz` = 0,25 |
| soma das classes | **dado real, 3 jogos** | quadros com `possession` + `duel` + `no_possession` + `dead_ball` = total de quadros, **exato** |
| nenhum quadro com dois donos | **dado real, 3 jogos** | `control` tem no máximo uma linha por (jogo, quadro) |
| duelo prevalece | sintético | um jogador com a bola na PZ **e** um adversário na DZ → `duel`, `owner_id` é `NaN` |
| duelo exige os dois times | sintético | dois jogadores do **mesmo** time dentro de `R_dz` → **não** é duelo |
| dono é o mais próximo | sintético, **com dois candidatos a 0,3 e 0,4 m** | o dono é o de 0,3 m. Roda no caminho em que os candidatos divergem (regra §2) |
| empate exato | sintético | determinístico pelo `player_id` menor; e contador de empates reportado |
| **`R_pz` varrido muda a saída** | **dado real** | nº de control frames é **estritamente crescente** em `R_pz` ao longo dos 8 valores da grade de D3 |
| `R_dz` varrido muda a saída | dado real | nº de duelos é estritamente crescente em `R_dz` |
| bola morta nunca tem posse | **dado real** | nenhuma linha de `control` cai em quadro com `ball_live = False` |

### 9.2 Perda (`test_posse_perda.py`)

| teste | caminho | critério de aceite |
|---|---|---|
| Fig. 3b1 | sintético | bola **parada** e jogador se afastando → **sem** perda (`Δs <= ε_s`) |
| Fig. 3b2 | sintético | bola sai da PZ e volta sem ninguém tocá-la → **sem** perda |
| Fig. 3b3/3b4 | sintético | bola sai e o próximo em controle é companheiro, e adversário → **perda** nos dois |
| condição 1 isolada | sintético | bola fora da PZ em `f+1` mas `Δs < ε_s` → **sem** perda; prova que as duas condições são conjuntas |
| condição 2 isolada | sintético | `Δs > ε_s` mas A reaparece no control frame seguinte → **sem** perda |
| `fc` não atravessa bola morta | sintético, **com A reaparecendo depois do reinício** | **perda registrada** na corrida anterior (§3.4). Roda exatamente no caminho que a lacuna resolve |
| perda forçada no fim da corrida | **dado real, 3 jogos** | toda corrida viva termina em perda; nº de `forcada_por_bola_morta` igual ao nº de corridas vivas |
| `ε_s` varrido muda a saída | **dado real** | nº de perdas muda entre `ε_s` = 5 cm e 10 cm |

### 9.3 Ganho (`test_posse_ganho.py`)

| teste | caminho | critério de aceite |
|---|---|---|
| Fig. 3c1 | sintético | bola muda trajetória e velocidade → ganho em `f0` |
| Fig. 3c2 | sintético | trajetória e velocidade **constantes** → **sem** ganho, e os control frames **saem** do passo de posse (§2.3.3, p. 5) |
| só direção | sintético | muda direção, velocidade constante → ganho |
| só velocidade | sintético | direção constante, velocidade muda → ganho |
| vetores unitários | sintético, **com velocidades muito diferentes** | o produto escalar não depende do módulo. Roda no caminho em que vetores não normalizados dariam outro resultado |
| `NaN` não é mudança | sintético, **primeiro quadro de corrida** | `d0` `NaN` → direção **não** mudou; o ganho sai só se a velocidade mudar |
| `ε_θ` e `ε_v` varridos | **dado real** | nº de ganhos muda ao mexer em cada um, separadamente |

### 9.4 Suavização (`test_suavizar.py`)

| teste | caminho | critério de aceite |
|---|---|---|
| não atravessa buraco | sintético, **duas corridas separadas por `NaN`** | o valor suavizado de cada corrida é idêntico ao de suavizar a corrida isolada |
| corrida curta | sintético, **corrida de 5 quadros** | fica **sem** suavizar, e é contada |
| `NaN` preservado | dado real | a fração de bola `NaN` é **idêntica** antes e depois |
| desligada é identidade | **dado real, 3 jogos** | com `suavizar: false` a posição da bola é **bit a bit** a da Fatia 1 |
| ligada muda a saída | dado real | com `suavizar: true` o nº de control frames muda |

### 9.5 `τ_posse` (`test_tau_posse.py`)

| teste | caminho | critério de aceite |
|---|---|---|
| sinal | sintético, **perda 2 s antes do anotado** | `τ_posse = +2,0 s`, mesma convenção da Fatia 2 |
| sem perda fica | sintético | passe sem perda do jogador na janela → `tem_perda = False`, `τ = NaN`, **linha na tabela** |
| denominador do portão | sintético | a fração da regra usa **só** os que têm perda; a fração sem perda é devolvida em separado |
| escada | sintético | com 10 % acima de 1 s e 3 % acima de 1,5 s, a escada devolve **1,5 s** |
| escada esgotada | sintético | com 10 % acima de 3,0 s, devolve `None` e `g3 = True` |
| **nenhum valor fora da escada** | sintético | a função **nunca** devolve valor que não esteja em `escada_janela_s`; mutante que interpola é morto |
| `R_pz` da decisão | dado real | a decisão usa 0,50 m mesmo que `posse.r_pz_m` esteja em outro valor |

### 9.6 Desempenho (`test_posse_zonas.py` ou script)

Reportar, não travar em teste: **tempo de parede por jogo e por `R_pz`**. Se um
jogo com um `R_pz` passar de 30 s, relatar — a grade da Fatia 8 tem 8 valores × 3
jogos × 8 níveis × 2 variantes × 5 sementes, e esse número é a base do orçamento
do G4. **Vetorizar em numpy; proibido laço sobre quadros.**

---

## 10. O que fica FORA

- **Qualquer detecção de evento**: gatilho, padrão, hierarquia, hierarquia de
  reserva, `eps_c`/`eps_t`/`eps_g`/`eps_k1`/`eps_k2`/`eps_f`, `free_kick?`. Fatia 4.
- Simulador, `visible=False`, interpolação, varredura completa, cache, manifesto,
  figura, relatório markdown.
- Não tocar em `src/evaluate.py` nem em `src/tau.py` (Fatia 2), nem nos loaders.
- Não implementar `cross`, `shot`, `save`, `claim`, `reception`, `interception`.
- Não **ajustar** `ε_s`, `ε_v`, `ε_θ`: o §7 é diagnóstico.

---

## 11. Riscos conhecidos

1. **A escada pode esgotar.** Se nem 3,0 s deixar ≤5 % fora, é G3 e o critério de
   casamento inteiro volta à mesa. É o desenho funcionando.
2. **A fração sem perda pode ser alta.** Aí o portão mede pouco e eu levo ao G3 de
   todo modo (limiar de 20 %, pré-registrado em §8).
3. **As cinco lacunas do §3 são minhas decisões.** Cada uma tem justificativa
   estrutural no artigo, mas nenhuma é texto do artigo. Se o revisor achar que
   alguma não se sustenta, é melhor descobrir agora do que depois da Fatia 4.
4. **Desempenho.** Se a implementação for lenta, a Fatia 8 fica inviável. Medir
   agora, não depois.
5. **`τ_posse` depende de `R_pz`**, que é a variável independente do projeto. Por
   isso a decisão é travada em 0,50 m, declaradamente.

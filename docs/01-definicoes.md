# 01 — Definições de evento (especificação normativa)

Fonte única de verdade para as regras de detecção. Nenhuma regra pode ser
inventada em código. Se um caso não estiver coberto, pare e pergunte.

Origem: Vidal-Codina et al., *Automatic event detection in football using
tracking data* (2022), **e o material suplementar (Online Resource 1)**.

> **Suplementar lido por inteiro em 2026-10-29** (`refs/12283_2022_381_MOESM1_ESM.pdf`,
> 14 páginas). S1 = bolas paradas com erro de tracking; S2 = critério de
> benchmarking; S3 = qualidade de dado para passes; S4 = escolha de parâmetros;
> S5–S6 = atributos contextuais e aplicações.
>
> **Correção**: este arquivo marcava `eps_s`, `eps_theta` e `eps_v` como `[S3]` e
> as tolerâncias de bola parada como `[S4]`. No suplementar **todas** estão em
> **S4.2, pp. 7–8**; S3 é outra análise (distância jogador-bola). Toda constante
> abaixo traz agora seção e página.
>
> As regras deste arquivo foram **congeladas no G1 (tag `plano-congelado`)**.
> Mudá-las depois de ver resultado é mudança declarada; ver `docs/decisoes.md`.

---

## Vocabulário

**Ball control** tem quatro valores: `dead ball`, `no possession`,
`possession`, `duel`. Eventos só ocorrem quando é `possession` ou `duel`.

**Event name** (em jogo): `pass`, `cross`, `shot on target`,
`shot off target`, `reception`, `interception`, `own goal`. Goleiro adiciona:
`save` (deflect/retain), `claim` (deflect/retain), `unsuccessful save`,
`reception from loose ball`.

**Dead ball event** — atributo do evento imediatamente *anterior* a um intervalo
de bola morta: `out for corner kick`, `out for goal kick`,
`out for throw-in`, `foul`, `penalty awarded`, `goal`.

**From set piece** — atributo do evento que *reinicia* o jogo: `corner kick`,
`goal kick`, `throw-in`, `free kick`, `penalty kick`, `kickoff`.

> Note a assimetria: **falta é dead ball event, tiro livre é set piece.** São
> coisas diferentes. Existe ainda o par `foul?`/`free kick?` para quando o
> algoritmo se confunde por imprecisão do tracking — ver `[S1]`.

---

## Passo 1 — Posse

### Zonas

- **PZ (possession zone)** — círculo de raio `R_pz` em torno de **cada jogador**.
  Se a bola cai dentro, o jogador está em posse.
- **DZ (duel zone)** — círculo de raio `R_dz >= R_pz` em torno da **bola**. Se
  pelo menos dois adversários estão dentro, é duelo.
- **Se as duas condições disparam, o duelo prevalece.** `[OK]`

Valores do artigo: `R_pz` = 0,50 m para o provedor A (Track160); 1,00 m para B
(Tracab) e C (Hawk-Eye). `R_dz` = 1,00 m para todos. **Suplementar S4.1, p. 6.**
A grade varrida pelos autores foi {50, 75, 100, 125, 150} cm, faixa escolhida
"after discussions with experts at FIFA" (S4.1, p. 6).

> `R_pz` é **a variável independente deste projeto.** Os autores afirmam que o
> framework se aplica a dados de qualidade inferior aumentando esse raio, mas
> nunca varreram acima de 150 cm nem testaram perda de visibilidade. É essa
> afirmação que vamos testar.

**Congelado no G1 (D3):** grade `R_pz` = {0,50 0,75 1,00 1,25 1,50 2,00 2,50
3,00} m, com `R_dz` = max(1,0 m; `R_pz`). Checagem de sensibilidade com `R_dz`
fixo em 1,0 m entra como secundária.

**Valor de partida na Metrica: `R_pz` = 0,50 m**, o ótimo do provedor A, porque a
Metrica se parece com A: distância do jogador anotado à bola no instante do passe
abaixo de 0,5 m em 96,7 % e 97,4 % dos casos, mediana 0,08–0,09 m
(`docs/inspecao-metrica.md` §6.4; comparar com S3, pp. 5–6).

> **Varrer `R_pz` também move as bolas paradas**, porque o padrão de bola parada
> exige a bola dentro de `R_pz` do executor (ver Passo 2). Não é um parâmetro só
> de jogo corrido.

### Control frame

Frame em que há posse ou duelo. Para cada um, armazenar:
- distância de cada jogador à bola;
- deslocamento da bola `ds` de `f` para `f+1`;
- direção e velocidade de **entrada** (`d0_f`, `v0_f`, usando `f-1`);
- direção e velocidade de **saída** (`d1_f`, `v1_f`, usando `f+1`).

### Suavização

Se a posição da bola for ruidosa, filtro **Savitzky-Golay** nas coordenadas x-y:
polinômio de **segunda ordem**, janela de **sete frames**. A 25 Hz equivale a
suavizar com os 0,25 s vizinhos. **Conferido: §2.3.1, p. 5.**

> Relevante para nós: depois da simulação de broadcast e da interpolação, o sinal
> fica mais ruidoso. Avaliar a suavização ligada e desligada é um experimento
> barato e informativo.

### Perda de posse

O jogador A perde a posse no control frame `f` se **ambas**:

1. a bola está fora da PZ de A em `f+1` **e** o deslocamento `ds_f` supera o
   limiar `eps_s`;
2. A **não** aparece no control frame seguinte `fc > f` com posse ou duelo.

A condição 1 evita registrar perda quando a bola fica parada e o jogador se
afasta. A condição 2 permite posses longas em que a bola sai da PZ e volta sem
que ninguém mais a toque.

`eps_s` = **5 cm** (provedor A) / 10 cm (B e C). **Suplementar S4.2, p. 8.**
Congelado no G1 (D9c) em **5 cm**, porque a Metrica se parece com A.
Significado conferido: deslocamento da bola de `f` para `f+1` (§2.3.2, p. 5).

### Ganho de posse

Proximidade não basta — é preciso inferir **contato**, e sem a coordenada z isso
se faz pela mudança da trajetória da bola.

Para uma sequência de control frames `f0 ... fn` com a bola na PZ do mesmo
jogador:

- **mudou de direção** se `d0_f0 . d1_fn < eps_theta`;
- **mudou de velocidade** se `|v0_fi - v1_fi| > eps_v` em pelo menos um frame.

Se **direção ou velocidade** mudou, há ganho de posse em `f0`. Se nenhuma das
duas mudou, os control frames são **falsos positivos e saem do passo de posse**
(§2.3.3, p. 5) — a bola passou perto sem ninguém tocá-la.

`eps_theta` = **cos 10°** para todos os provedores · `eps_v` = **1 m/s**
(provedor A) / 5 m/s (B e C). **Suplementar S4.2, p. 8**, obtidos por validação
cruzada. Congelados no G1 (D9c) em cos 10° e **1 m/s**.

> `d0_f0 · d1_fn` é produto escalar de **vetores unitários** — é isso que torna o
> limiar comparável a um cosseno. Declarado aqui porque o artigo não o diz
> explicitamente (§2.3.3, p. 5).

> Consequência direta para o projeto: o ganho de posse depende de **derivadas** da
> posição da bola. Interpolação linear zera a curvatura, então é de esperar que a
> degradação ataque o ganho de posse mais do que a perda. Hipótese a testar.

---

## Passo 2 — Eventos

> **Esta seção foi reescrita em 2026-10-29.** A versão anterior trocava gatilho
> por padrão: descrevia `eps_c` como distância **da bola** ao canto e `eps_t`
> como posição **da bola** sobre a lateral. Está errado. Conferido em
> Vidal-Codina §2.3.4 (p. 6), §2.4.1 (p. 7) e Fig. 4 (p. 6).

### Gatilho e padrão: o que é cada coisa

**Gatilho** = configuração espacial **dos jogadores**, avaliada **durante o
intervalo de bola morta** `[d0, dc]`. **A bola não entra no gatilho** — e não
poderia, porque na maioria dos provedores é justamente a ausência de dado da bola
que sinaliza a bola morta (§2.3.4, p. 6).

Um gatilho é **completo** se está ativo de um quadro intermediário qualquer `d1`
(`d0 <= d1 <= dc`) **até o último quadro morto `dc`** (§2.4.1, p. 7). Como `d1`
pode ser igual a `dc`, basta estar ativo em `dc`. Um gatilho ativo até um
`di < dc` é **incompleto** e só é usado pela hierarquia de reserva (S1).

**Padrão** = no **primeiro quadro em jogo**, o jogador do gatilho está dentro da
zona do padrão **e a bola está dentro da `R_pz` dele** (§2.4.1, p. 7). Havendo
vários jogadores no gatilho com a bola na PZ, o **mais próximo da bola** é o
executor.

> Fig. 4, p. 6, legenda: *"trigger and pattern zones coincide for corners,
> throw-ins and goal kicks."* Para esses três, gatilho e padrão são a mesma zona
> — o que muda é **quem** se avalia (jogadores, durante a bola morta) e **quando**
> (primeiro quadro vivo, com a bola).

### Hierarquia, nesta ordem

**pontapé inicial → pênalti → escanteio → lateral → tiro de meta → tiro livre**

Fig. 5, p. 7, e Fig. S1, p. 2 (`K P C T G F`). A ordem resolve empate entre
gatilhos completos. Pênalti está fora do nosso escopo, mas **continua na
hierarquia** — tirá-lo mudaria o comportamento do algoritmo.

### Os gatilhos (§2.3.4, p. 6)

| evento | gatilho (só jogadores, durante a bola morta) | lei IFAB |
|---|---|---|
| **bola morta** | booleano **ou ausência de dado da bola** | — |
| **pontapé inicial** | todos na própria metade, tolerância `eps_k1`, **e** ≥ 1 jogador a `eps_k2` da marca central | 8 |
| **pênalti** | só 1 jogador na linha de gol entre as traves (caixa `eps_p1`); só 1 adversário na caixa de `eps_p2/4` à frente a `3·eps_p2/4` atrás da marca ativa; os demais nem na área nem a menos de 9,15 m da marca (tolerância `eps_p3`) | 14 |
| **escanteio** | ≥ 1 jogador a `eps_c` de uma das suas marcas de canto **ativas** | 17 |
| **lateral** | ≥ 1 jogador **além da linha lateral auxiliar** (lateral menos `eps_t`) | 15 |
| **tiro de meta** | ≥ 1 jogador dentro da **própria** pequena área, caixa de tolerância `eps_g` | 16 |
| **tiro livre** | **nenhum** — não tem gatilho, só padrão | — |

"Ativo" = do lado para o qual o time ataca (§2.3.4, p. 6: *"we shall refer to the
goal a team is attacking as active goal, and analogously for other notable
locations"*).

### As tolerâncias (suplementar S4.2, pp. 7–8)

| constante | valor | origem | estado no G1 |
|---|---|---|---|
| `eps_k1` | 3 a 5 m | S4.2, p. 7 | fixo em **3 m** |
| `eps_k2` | ≥ 2 m | S4.2, p. 7 | fixo em **2 m** |
| `eps_c` | 3 m | S4.2, p. 8 | **3 m no teto limpo; também parâmetro livre (D9b)** |
| `eps_t` | 0,5 m | S4.2, p. 8 | fixo em **0,5 m** |
| `eps_g` | 0,5 m | S4.2, p. 8 | fixo em **0,5 m** |
| `eps_f` | 1 m | S4.2, p. 8 | fixo em **1 m** |
| `eps_p1`, `eps_p2`, `eps_p3` | 2 m, 2 m, 4 m | S4.2, p. 8 | fora do escopo, só 13 pênaltis no artigo |

`eps_c`, `eps_t`, `eps_g` e `eps_f` foram otimizados **em conjunto**, F1 ponderado
93,4 % (S4.2, p. 8). Sensibilidade medida de `eps_k1` com `eps_k2` = 2 m: o F1 de
pontapé inicial cai para **9 %, 82 % e 95 %** com `eps_k1` = 0, 0,5 e 1 m
(S4.2, p. 7).

**Erro de digitação no artigo (V14):** o §2.3.4, p. 6, escreve `eps_c` para a
caixa da pequena área, mas a legenda da Fig. 4, p. 6, escreve `eps_g`, e o S4.2
também. **Usar `eps_g` = 0,5 m.** Declarado aqui.

**`eps_f` não é tolerância de tiro livre (V12).** É o deslocamento máximo do
jogador que ativa o padrão de tiro livre antes de passar a bola, usado só no
fluxo de erros de tracking: *"If the free kick pattern … is activated by a player
that does not move more than eps_f before the ball is passed, we conclude that
this player was the set piece executor"* (S1, p. 1).

**`eps_g` existe para acomodar regra não cumprida**, não só ruído: S4.2, p. 7,
cita explicitamente *"a goal kick pass from beyond the goal area"*.

### Tiro livre — categoria residual

Transição morta → viva em que nenhum gatilho completo foi confirmado por um
padrão. Padrão próprio: um jogador com a bola na sua PZ no primeiro quadro em
jogo. É sempre o `else` e o pior resultado do artigo (§3.1, p. 9).

### Hierarquia de reserva na presença de erro de tracking — **obrigatória**

Suplementar S1, pp. 1–2, e Fig. S1, p. 2. **Não é opcional**: o nosso simulador
cria exatamente os três problemas que ela trata, e sem ela o F1 médio de bola
parada do artigo cai de **95 % para 85 %** (S1, p. 2).

Aplica-se **só quando nenhum gatilho completo foi detectado**.

1. **Problema 1 — booleano fora de sincronia** (jogo já voltou mas o booleano
   diz morta). Se o padrão de tiro livre é ativado por um jogador que **não se
   desloca mais que `eps_f`** antes de passar a bola, ele é o executor; então
   reavalia-se **todos** os gatilhos e padrões para esse executor no quadro em
   jogo em que o primeiro passe após a bola morta é feito.
2. **Problema 2 — executor não rastreado** (fora das linhas). Se o padrão de tiro
   livre **não** é ativado, procura-se um gatilho de escanteio ou lateral que
   ficou **incompleto** porque o jogador que o ativava deixou de ser detectado em
   `[di+1, dc]`. Nesse caso **imputa-se o evento a esse jogador ausente**.
3. **Problema 3 — bola ausente no quadro de reposição**, ou bola fora da PZ do
   repositor. Aí **não se pode checar padrão algum** e só restam gatilhos, nesta
   ordem: pontapé inicial → pênalti → escanteio completo → lateral completo →
   escanteio incompleto → lateral incompleto → **tiro de meta**. **Corrigido em
   2026-11-04:** a prosa do S1, p. 2, omite o tiro de meta, mas remete a *"the
   dead ball hierarchy shown in issue 3 of Fig. S1"*, e a figura, lida no
   stream da página, diz `K P C T Ci Ti G F?`. A figura é a norma (leitura
   `depois_de_cto`; `docs/decisoes.md`, revisão da Fatia 4). Os autores registram que
   *"we have observed higher detection rate when favoring complete throw-in over
   incomplete corner"* (S1, p. 2). Se nenhum gatilho ativa, o rótulo é
   **`free kick?`**, que sinaliza confusão do algoritmo e entra no relatório como
   categoria própria.

### Passe — **corrigido (V16)**

> A versão anterior dizia "perda de posse de A seguida de ganho de B, mesmo
> time". **Está errado.**

O algoritmo rotula como **passe toda perda de posse que não é finalização nem
cruzamento** (§2.4.3, p. 9), inclusive a interceptada e a que sai de campo. O
desfecho (completo, interceptado, duelo, gol, bola morta, fim de tempo) é um
**atributo** do passe, não condição para ele existir (suplementar S5, p. 9).

O **ganho** correspondente é recepção se o anterior era companheiro, e
interceptação se era adversário (§2.4.3, p. 9).

Como o nosso escopo exclui cruzamento e não implementa *cross zone*, o detector
rotula **todo cruzamento como passe**. Por isso o gabarito funde `PASS`+`CROSS`
(D10, V9).

### Atribuição ao jogador — **corrigido (V13)**

O texto principal **não** define PZ própria de bola parada. Exige só a bola dentro
de `R_pz` do executor no primeiro quadro em jogo, e o mais próximo se houver
vários (§2.4.1, p. 7). A "PZ específica de bola parada, com seu próprio conjunto
de hiperparâmetros" aparece no **Mills, §2.2, p. 4**, e é de onde vinha o texto
anterior deste arquivo (junto com o escanteio "até 3 m" e o Mills §2.2, p. 4:
*"both are positioned no further than 3 m away from a corner of the pitch"*).

**Decisão do Victor, 28/10, congelada no G1: seguir o Vidal-Codina.** Divergência
registrada em `docs/decisoes.md`.

### Cruzamento — fora do escopo
Exige origem na *cross zone*, próximo controlador dentro da área ativa e ao menos
um atacante na área. Sem definição padrão-ouro; fica fora.

### Finalização e defesa — fora do escopo
Dependem de sequência com desfecho e, na prática, da coordenada z. Fora.

---

## Avaliação

Três critérios existem na literatura e **não são o mesmo critério**, apesar de o
Mills dizer que segue o Vidal-Codina:

Cada um é uma escolha diferente em três eixos. **Esta tabela foi corrigida em
2026-10-29**: a versão anterior sugeria que todos casam por tipo, e **o do
Vidal-Codina não casa**.

| critério | casa por tipo? | casa por jogador? | janela | origem |
|---|---|---|---|---|
| **Vidal-Codina** | **não** | sim | ±10 s | suplementar S2, p. 3 |
| **Mills** | sim | **não** | 3 s | Mills §2.2, p. 4 |
| **FOOTPASS** | sim | sim | ±12 quadros (0,48 s) | FOOTPASS §4.1, p. 6 |

> **No critério do Vidal-Codina a comparação de tipo É a matriz de confusão.** O
> S2, p. 3, diz literalmente *"A discrete event is correctly detected if it is
> executed by the annotated player and is within a ±10 s window of the annotated
> time"* — sem mencionar tipo — e em seguida *"present the detection results using
> confusion matrices"*. É isso que permite ver escanteio virando tiro livre, que é
> o erro (1) da lista do §2.4.1, p. 8, e o que a nossa inspeção prevê em 44 % dos
> escanteios.
>
> O S2 agrupa os eventos e usa **uma matriz por grupo** (passes de jogo corrido;
> bolas paradas; gols; defesas), não uma matriz única. E inclui **`free kick?`**
> como categoria própria.

A janela de ±10 s existe porque a anotação manual da STS vem em média **1,5 s
atrasada**, e 16 % dos passes têm |τ| > 5 s e 8 % > 7,5 s (suplementar S3, p. 5).

**Na Metrica essa defasagem parece não existir**, e a evidência é a distância, não
o relógio: **no próprio quadro anotado**, o passador anotado está a menos de 0,5 m
da bola em **96,7 % e 97,4 %** dos passes, com mediana de **0,08–0,09 m**
(`docs/inspecao-metrica.md` §6.4). A bola percorre vários metros em 1,5 s a
qualquer velocidade de passe, o que é incompatível com 8 cm de separação mediana
no instante anotado. Note o contraste de método: o S3 mede o **mínimo numa janela
de ±10 s** porque, na STS, no instante anotado o passador costuma estar longe da
bola. Somado a isso, com ~1000 passes por partida — um a cada ~6 s de jogo — uma
janela de ±10 s casaria o evento errado.

> **Não use `max |Start Time − Start Frame/25| = 0,000000` como justificativa
> disto.** Esse fato prova só que a tabela de eventos usa a mesma grade de quadros
> e a mesma unidade do tracking. Uma anotação atrasada 3 s satisfaria a identidade
> exatamente. Corrigido em 2026-10-29.

**Congelado no G1 (D8):**

- **Principal:** mesmo tipo + mesmo jogador + janela de **±1 s** (inclusiva),
  casamento um-para-um. **Este critério é NOSSO**, não de nenhum artigo: é a
  conjunção das duas restrições com a janela que o D8 justifica. Rotular como tal
  em todo lugar onde for reportado.

  > **A janela de ±1 s está CONFIRMADA (2026-10-30), e o rótulo "provisória" caiu.**
  > A medição certa — `quadro anotado − quadro de perda de posse`, §2.3.2, p. 5 —
  > foi feita na Fatia 3 sobre os 2650 passes dos 3 jogos: **mediana de `τ_posse`
  > = −0,040 s, exatamente um quadro**, p95 de `|τ_posse|` = 0,16 s, e apenas
  > **3,27 %** acima de 1,0 s, contra o limiar de 5 % pré-registrado. A regra da
  > escada selecionou o **primeiro degrau**, logo nada mudou e nada foi
  > recalculado. A mesma conclusão em `R_pz` = 1,00 m.
  >
  > Alargar não ajudaria: a distribuição é bimodal e ir de 1,0 para 3,0 s
  > recuperaria 0,9 ponto percentual — o resíduo é casamento com o toque errado,
  > não defasagem de anotação.
  >
  > Para contraste, o estimador **inválido** da Fatia 2 (argmin de distância em
  > ±10 s) dava média +0,699 s e 45,36 % acima de 1 s. A diferença entre as duas
  > medidas não é de grau: é de grandeza medida. Ver `docs/decisoes.md`.
- **Secundários, sempre reportados:** Vidal-Codina (jogador + ±10 s, tipo na
  matriz) e Mills (tipo + 3 s, sem jogador).

**O casamento é um-para-um e ótimo**, não guloso: maximiza o número de pares e,
entre os casamentos máximos, minimiza `Σ|Δt|`. Guloso por "mais próximo no tempo"
pode consumir a única detecção compatível com outro evento anotado e perder um
casamento que existia. Ver `docs/fatias/02-plano.md` §3.

> **A janela de ±1 s é verificada na Fatia 2, antes de rodar qualquer detector.**
> A evidência acima é indireta: mede distância, não defasagem. A medida direta é a
> distribuição de `τ = t_anotado − t_D`, com `t_D` o quadro de menor distância
> passador-bola numa janela de ±10 s — deliberadamente a mesma grandeza do S3,
> p. 5, para ser comparável aos 1,5 s da STS.
> **Critério escrito antes de medir: se mais de 5 % dos passes tiverem
> |τ| > 1 s, PARAR e levar ao Victor (G3).**

Reclassificações do S2, p. 3, para a comparação: `fair play`, `nutmeg`,
`backheel`, `possession loss before goal` e `bicyclekick` → **pass**;
`goal disallowed` → **shot**. (Vocabulário da STS, não da Metrica; registrado
porque define o que o artigo chama de "passe".)

Reportar precisão, revocação, F1 e a **contagem absoluta** por tipo. Com classes
pequenas, um único acerto move o F1 de forma dramática: são **26 escanteios, 18
pontapés iniciais e 109 laterais nos três jogos somados**
(`docs/inspecao-metrica.md` §3.2).

**Evento não detectado é perda de revocação, nunca exclusão.** Vale inclusive
para o pontapé inicial do quadro 1 do jogo 1, que é estruturalmente indetectável
porque não há intervalo de bola morta antes dele (`docs/inspecao-metrica.md`
§6.2), e para os 12 eventos que a guarda de 10 s deixa sem ancorar.
**NaN nunca conta como acerto nem é descartado.**

> ### Risco declarado: a ancoragem trivializa o tempo nas bolas paradas
>
> O detector dispara bola parada na transição morto → vivo (§2.4.1, p. 7). Como
> o gabarito de bola parada é ancorado no primeiro quadro em jogo, o **instante**
> do gabarito vem de `ball_live` — o mesmo sinal que o detector usa. Logo, para
> bola parada, a dimensão temporal do casamento fica largamente trivializada e o
> critério de acerto testa sobretudo **tipo + jogador**.
>
> É defensável: corrige um artefato documentado da anotação (o `Start Frame` de
> `BALL LOST`/`GOAL KICK` é o instante da **perda**, não o do chute — no quadro
> 77582 a bola já viajou ~47 m) e `ball_live` já é oráculo declarado (D1b). Mas
> não fica implícito.
>
> **Mitigação obrigatória:** reportar P/R/F1 de bola parada nas **duas** âncoras,
> em `frame` e em `annotated_frame`, como análise de sensibilidade. A Fatia 1 já
> guarda as duas colunas, então não custa código. Espera-se diferença pequena: os
> tetos de gatilho são **idênticos** nas duas âncoras (tiro de meta 33/38 e 34/38
> com `eps_g` = 0 e 0,5; lateral 27 e 28; escanteio 6 e 4).

---

## Ressalvas

**O gabarito tem erros.** Os autores relatam eventos não anotados, timestamps
errados e jogadores errados: *"we have observed several instances of
non-annotated events, wrong timestamps or wrong players"* (§3.1, p. 9). A taxa de
detecção nunca chega a 100 %. Ao analisar falsos positivos, considere que o
algoritmo pode estar certo. Um candidato concreto já encontrado na Metrica está em
`docs/inspecao-metrica.md` §6.3. **Não "consertar" o gabarito.**

**Hiperparâmetros são por provedor.** Os autores recomendam validação cruzada num
subconjunto de partidas. Com 3 partidas e classes de bola parada minúsculas,
ajustar em 1 e medir em 2 dá F1 muito ruidoso. **Congelado no G1 (D4):
leave-one-game-out, 3 dobras, critério escrito antes, várias sementes do
simulador por nível, reportando contagem absoluta e mín.–máx. por jogo. Sem
bootstrap por jogo** (com 3 jogos há só 10 reamostragens distintas).

**O teto já está limitado pela geometria, antes de qualquer degradação.** Medido
na Metrica com tracking perfeito e as tolerâncias publicadas
(`docs/inspecao-metrica.md` §6.2): lateral 92 % (n=60), pontapé inicial 92 %
(n=13), tiro de meta 89 % (n=38), **escanteio 56 % (n=18)**. Não interprete o
teto como limite do algoritmo: é limite da convenção de anotação deste dataset.

**Comparação com o artigo é indicativa (D7).** Vidal-Codina reporta escanteio
acima de 90 % de precisão e revocação (§3.1, p. 9) com o mesmo `eps_c` = 3 m.
Diferem dados, anotador, critério de casamento e definição de evento. **Nunca
escrever que "reproduzimos" ou "superamos" nada.**

**Erros que o próprio artigo assume** (§2.4.1, p. 8), e que devemos esperar ver:
(1) lateral e tiro livre perto do canto virando escanteio; (2) tiro livre perto
da lateral virando lateral; (3) tiro livre dentro da pequena área virando tiro de
meta; (4) impedimento classificado como falta. No nosso caso a direção dominante
é a **inversa de (1)**: escanteio cujo gatilho falha cai no `else` e vira **tiro
livre**.

**Custo computacional.** No artigo, 3 minutos de tempo médio de parede para uma
partida de 90 minutos, em 1 CPU e 4 GB de RAM. Se a sua implementação levar muito
mais, há algo errado — provavelmente um laço sobre frames que deveria ser
vetorizado.

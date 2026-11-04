# 03 — Plano de implementação

Oito fatias verticais. Cada uma entrega algo executável e testável. A ordem não é
negociável: **a avaliação vem antes da detecção**, para que exista um número
desde o primeiro dia.

> **Congelado no G1, tag `plano-congelado` (2026-10-29).** As semanas abaixo
> valem como **ordem**, não como calendário: não há prazo fixo (Victor, 28/10).
> As regras de decisão estão em `docs/decisoes.md`; mudar qualquer uma depois de
> ver resultado é mudança declarada e torna o que depende dela **exploratório**.

## Testes obrigatórios contra falha silenciosa

**Toda fatia** que toque um destes pontos entrega o teste correspondente. São
regras, não sugestões — cada uma corresponde a um erro que já custou caro no
projeto anterior.

1. **Parâmetro varrido e ignorado faz o teste falhar.** Mudar `R_pz` tem de
   mudar a saída; mudar `eps_c` tem de mudar a saída. Um teste por parâmetro
   varrido.
2. **Evento não detectado é perda de revocação, nunca exclusão.** Inclui o
   pontapé inicial do quadro 1 do jogo 1, estruturalmente indetectável.
3. **NaN nunca conta como acerto nem é descartado.**
4. **Abertura infinita e sem cortes reproduz o teto bit a bit.** Igualdade
   exata, não aproximada.
5. **Cache por hash do conteúdo de entrada *e* da configuração.** Um teste que
   muda um parâmetro e verifica que o cache não é reaproveitado.
6. **Semente de cada execução no manifesto.**
7. **`ball_live` idêntico em todos os níveis de degradação** (D1b). Teste que
   falha se algum nível o alterar.
8. **`visible` nunca é sobrescrito** (Fatia 7).

---

### Fatia 1 — Carregar e normalizar (ordem 1)
Loaders da Metrica → os DataFrames de `docs/02-dados.md`. **Três jogos** (D6).

- Dois loaders: CSV (jogos 1 e 2) e EPTS/JSON (jogo 3), sem dependência nova.
- Conversão de coordenadas **sem clamp**; sentido de ataque lido do x médio do
  goleiro, por jogo e por período; `ball_live = not NaN(bola)` (D1), derivado uma
  vez e congelado.
- Gabarito: mapeamento YAML de `docs/02-dados.md`, com as duas regras de
  construção (fundir `SET PIECE` + execução; ancorar bola parada no primeiro
  quadro em jogo).
- **Testes:** (a) as quatro bandeirinhas projetam em `(±52.5, ±34)`; (b) a bola
  no pontapé inicial fica a menos de 1 m do centro em 12 dos 13 pontapés (o do
  quadro 1 do jogo 1 é a exceção conhecida); (c) as contagens por `Type` e por
  `SET PIECE`/subtipo batem **exatamente** com as tabelas de
  `docs/inspecao-metrica.md` §3.1 e §3.2, nos três jogos; (d) nenhum valor de
  coordenada é alterado por clamp; (e) `ball_live` tem 39,14 % / 41,01 % /
  32,22 % de quadros mortos.
- **Saída:** `python -m src.run --inspect` imprime o resumo da partida.

### Fatia 2 — Avaliação (ordem 2)
Casador de eventos e métricas, **antes de detectar qualquer coisa**.

- **Três critérios** (`docs/01-definicoes.md`, Avaliação), com o principal
  declarado em `config.yaml`: estrito (tipo + jogador + ±1 s) **principal**;
  Vidal-Codina (jogador + ±10 s) e Mills (tipo + 3 s) secundários. Casamento
  um-para-um, o mais próximo no tempo.
- Precisão, revocação, F1 **e contagem absoluta** por tipo e por jogo.
- **Medição obrigatória, com gatilho de G3: a defasagem da anotação.** Para cada
  passe dos **três** jogos, calcular `τ = t_anotado − t_D`, onde `t_D` é o quadro
  de **menor distância passador-bola numa janela de ±10 s** em torno do instante
  anotado — a mesma grandeza do suplementar S3, p. 5, para comparar com os 1,5 s
  de média e os 16 % com |τ| > 5 s da STS. Reportar média, mediana, e as frações
  com |τ| > 1 s, > 3 s, > 5 s e > 7,5 s, por jogo.
  **Critério escrito antes de medir: se mais de 5 % dos passes tiverem |τ| > 1 s,
  a janela de ±1 s do D8 está contradita — PARAR e levar ao Victor (G3) antes de
  executar qualquer detector.** A evidência que hoje sustenta o D8 é indireta
  (distância no instante anotado, `docs/inspecao-metrica.md` §6.4); esta é a
  direta.
- **Sensibilidade obrigatória da âncora.** Reportar P/R/F1 de bola parada nas
  duas âncoras: em `frame` (primeiro quadro em jogo) e em `annotated_frame`. A
  ancoragem faz o instante do gabarito vir de `ball_live`, o mesmo sinal que o
  detector usa para disparar bola parada, logo trivializa a dimensão temporal do
  casamento — ver o risco declarado em `docs/01-definicoes.md`, Avaliação. As duas
  colunas já existem desde a Fatia 1; não custa código.
- **Denominador do critério secundário de passe:** usar a contagem da tabela
  `events` (1009 / 1131 / 1358), **não** a crua (1086 / 1208 / 1447). Ver
  `docs/decisoes.md`.
- **Testes:** (a) gabarito contra si mesmo → F1 = 1,0 em tudo, nos três
  critérios; (b) gabarito deslocado 30 s → F1 = 0 nos três; (c) deslocado 2 s →
  F1 = 0 no estrito e 1,0 no de ±10 s (prova que os critérios são distintos);
  (d) metade dos eventos removidos → revocação = 0,5; (e) um evento com NaN no
  tempo **não** casa e **não** desaparece do denominador; (f) casamento é
  um-para-um: dois detectados perto de um anotado dão 1 acerto e 1 falso
  positivo; (g) **os 13 eventos com `no_dead_ball_before = True` permanecem no
  denominador** — se forem filtrados, o F1 agrupado de bola parada sobe 2,25 pontos e a
  revocação de tiro de meta sobe 18,4 pontos, e a coluna é informativa, nunca filtro; (h) **dois eventos no mesmo
  quadro não quebram o casador** — jogo 1, quadro 59923, tem duas linhas `PASS`
  com jogadores diferentes no mesmo `Start Frame`.

### Fatia 3 — Posse (ordem 3)
Implementa o Passo 1 da especificação. `ball_live` já veio da Fatia 1.

- PZ/DZ, control frames, Savitzky-Golay (2ª ordem, 7 quadros), perda e ganho de
  posse. Control frames sem mudança de direção **nem** de velocidade **saem** do
  passo de posse (§2.3.3, p. 5).
- Vetores **unitários** no produto escalar de `eps_theta`.
- **Testes:** (a) quadros com posse + com duelo + sem posse + bola morta = total;
  (b) nenhum quadro tem dois donos; (c) duelo prevalece sobre posse; (d) mudar
  `R_pz` muda o número de control frames; (e) bola parada + jogador se afastando
  → **sem** perda de posse (Fig. 3b1); (f) bola sai e volta à PZ sem ninguém
  tocá-la → **sem** perda (Fig. 3b2); (g) bola passando perto sem mudar direção
  nem velocidade → **sem** ganho (Fig. 3c2).
- **Medir e reportar:** a distribuição real de `eps_s`, `eps_v` e `eps_theta` na
  Metrica, para confirmar ou não a escolha dos valores do provedor A (D9c).
- **GATILHO DE G3 REARMADO: a janela do D8 se decide aqui.** A Fatia 2 mediu a
  defasagem `τ` pelo argmin de distância em ±10 s e o gatilho disparou (45,36 %
  dos passes acima de 1 s), mas eu concluí que **a grandeza é inválida** neste
  dataset: com um passe a cada ~6 s, o argmin frequentemente aponta para outro
  toque do mesmo jogador, e a defasagem persiste mesmo dentro do episódio de
  contato, porque conduzir a bola mantém `d < 0,5 m` por segundos. Ver
  `docs/decisoes.md`, bloco "Fatia 2 — G3 da defasagem".

  **A grandeza certa só existe aqui:** `quadro anotado − quadro de PERDA DE
  POSSE`, isto é o quadro em que a bola sai da PZ do jogador anotado **e**
  `Δs > eps_s` (§2.3.2, p. 5). É o instante que o detector de passe vai emitir.
  Medir para os passes dos 3 jogos, reportar média, mediana e as frações acima de
  1 s, 3 s, 5 s e 7,5 s.

  **REGRA DE DECISAO DA JANELA, ESCRITA ANTES DE MEDIR (2026-10-30).** Isto fecha
  o viés que o revisor da Fatia 2 apontou: rearmar o gatilho sem fixar a regra
  faria a escolha do valor ser feita **olhando o resultado**, que é exatamente o
  que eu recusei ao descartar "alargar para 3 s" agora.

  1. Medir `|τ_posse|` para todos os passes dos **3 jogos juntos** (agrupado; o
     por jogo entra no relatório para transparência, não na decisão).
  2. A janela passa a ser o **menor valor da escada {1,0; 1,5; 2,0; 3,0} s** tal
     que **no máximo 5 %** dos passes tenham `|τ_posse|` maior que a janela.
  3. Se 1,0 s já satisfaz, **o D8 está confirmado** e nada muda.
  4. Se nem 3,0 s satisfaz, **PARAR e levar ao Victor (G3)**: aí o problema é o
     critério de casamento, não a largura da janela, e alargar mais seria só
     esconder.
  5. **Nenhum valor fora da escada pode ser escolhido.** Sem interpolação, sem
     "p95 arredondado", sem valor intermediário.
  6. O teto da escada é 3,0 s porque é o valor publicado do Mills (§2.2, p. 4);
     acima disso o nosso critério principal deixaria de ser mais estrito que a
     literatura e de se distinguir do secundário.
  7. Se a janela mudar, **todo número já reportado com ±1 s é recalculado**, não
     rerrotulado.

  Até esta medição, **a janela de ±1 s do critério principal é PROVISORIA** e tem
  de ser rotulada assim em qualquer número reportado antes da Fatia 3.
- **Saída:** série temporal de posse, visualizável.

### Fatia 4 — Bolas paradas (ordem 4)
Pontapé inicial, escanteio, lateral, tiro de meta, tiro livre residual **e
`free kick?`**. Pênalti fica na hierarquia mas fora do escopo de avaliação.

- **Gatilho** = jogadores durante a bola morta; **padrão** = jogador na zona +
  bola na `R_pz` dele no primeiro quadro em jogo; executor = o mais próximo da
  bola. Hierarquia: pontapé inicial → pênalti → escanteio → lateral → tiro de
  meta → tiro livre. Ver `docs/01-definicoes.md`, Passo 2 — **o documento foi
  reescrito; a versão antiga trocava gatilho por padrão.**
- **A hierarquia de reserva do suplementar S1 é obrigatória**, com os três
  problemas e, no problema 3, a ordem "escanteio completo → lateral completo →
  escanteio incompleto → lateral incompleto → tiro de meta" (Fig. S1; corrigido
  em 2026-11-04, ver `docs/01-definicoes.md`). Sem ela o F1 médio de bola parada do artigo
  cai de 95 % para 85 % (S1, p. 2), e o nosso simulador cria exatamente esses
  erros.
- **Testes:** (a) um jogador a 2 m de um vértice ativo, durante a bola morta, com
  a bola na PZ dele no primeiro quadro vivo → escanteio; a 4 m → **não**
  escanteio com `eps_c` = 3 m; (b) jogador em `|y| = 33,8 m` → lateral; (c) todos
  na própria metade e um no centro → pontapé inicial; (d) nada disso → tiro
  livre; (e) gatilho incompleto de escanteio + executor deixando de ser detectado
  → **evento imputado ao jogador ausente** (problema 2 do S1); (f) bola NaN no
  quadro de reposição → cai no problema 3, e com nenhum gatilho ativo o rótulo é
  `free kick?`, que **aparece na tabela** e não é silenciosamente convertido em
  tiro livre; (g) mudar `eps_c` muda a contagem de escanteios.
- **Marco `teto`:** primeira tabela de F1 real. **Esperado**, pela geometria
  medida (`docs/inspecao-metrica.md` §6.2): revocação próxima de 92 % em lateral
  e pontapé inicial, ~~89 %~~ 86,8 % em tiro de meta [corrigido 2026-11-04, auditoria pós-Fatia 6] e **~56 % em escanteio**, com os
  escanteios perdidos aparecendo como falsos positivos de tiro livre. Se a tabela
  divergir muito disso, o bug é nosso. Comparar com o artigo **só como indicação**
  (D7).

### Fatia 5 — Passes (ordem 5)
O evento de maior volume e o que mais vale acertar.

- **Passe = toda perda de posse que não é finalização nem cruzamento** (§2.4.3,
  p. 9), inclusive interceptada e que sai. O desfecho é atributo, não condição.
  Ver a correção V16 em `docs/01-definicoes.md`.
- Gabarito: `PASS` principal, união secundária (D10).
- **Testes:** (a) sequência sintética A → B → C gera exatamente dois passes;
  (b) A perde e um adversário ganha → passe + interceptação; (c) A perde e a bola
  sai → **ainda é passe**, não exclusão; (d) mudar `R_pz` muda a contagem.
- **Marco `teto`:** o teto está estabelecido. ~~Esperado: revocação de passe
  próxima de 97 % com `R_pz` = 0,50 m e 98 % com 1,00 m, pela distribuição de
  distância jogador-bola (`docs/inspecao-metrica.md` §6.4).~~ **Obsoleto
  (2026-11-04):** a distância no quadro anotado foi substituída pela perda de
  posse na Fatia 3. O contrato vale de `docs/fatias/05-plano.md` §2: no critério
  estrito, `tp_diag` de passe ≤ 2353 de 2650 (R ≤ 0,888). Acima disso = bug nosso.

### Fatia 6 — Simulador de broadcast (ordem 6)
O coração da contribuição. **Duas variantes**, as duas com origem publicada
(`docs/00-problema.md`, A estratégia):

1. **Janela fixa 40×40 m centrada na bola** — linha de base de Mortensen e Bornn
   (2020), que o Bassek critica por ignorar zoom e edição (p. 3).
2. **Frustum 2D que segue a bola**, abertura parametrizável, movimento suavizado
   (câmera real não teleporta) **e cortes editoriais**.

- ~~Marca `visible=False` para quem cai fora.~~ **Corrigido em 2026-11-04:** quem cai fora **perde a linha** naquele quadro; `visible` mantém o significado único do `docs/02` (False = imputado, escrito pela Fatia 7). Caminho dos níveis e calibração em `docs/fatias/06-plano.md`. Um parâmetro varre a taxa de detecção
  de ~100 % a ~35 %. **A bola nunca é removida** (D2) e `ball_live` nunca muda
  (D1b).
- **Testes:** (a) **abertura infinita e sem cortes → taxa 100 % e saída idêntica
  ao teto bit a bit**; (b) a taxa de detecção resultante é monótona na abertura;
  (c) `ball_live` idêntico ao teto em todos os níveis; (d) a bola nunca é marcada
  invisível.
- **Calibração contra alvos publicados** (tabela em `docs/02-dados.md`): 38 % de
  frames sem jogador, moda ~7 por time, 10,9 cortes/min, visibilidade por
  posição GK 14 % / DEF 40 % / MID 52 % / OFF 46 %. Verificação contra a
  SkillCorner é secundária.
- **A visibilidade POR POSIÇÃO é requisito, não calibração opcional.** Descoberto
  na Fatia 4: o gatilho de tiro de meta exige um jogador na própria pequena área,
  e na prática esse jogador é o **goleiro** — que é o menos visível em TV (14 %
  contra 40–52 % dos jogadores de linha). Um simulador que remova jogadores
  **uniformemente** não reproduziria o colapso do tiro de meta, e a Fatia 8
  mediria a degradação errada. Ver a previsão pré-registrada em
  `docs/decisoes.md`, 2026-11-01.

### Fatia 7 — Reconstrução (ordem 7)
Preenche os buracos, como fazem os sistemas reais.

- Interpolação linear como base. Segunda estratégia só se sobrar tempo.
- **Nunca sobrescreva `visible`.**
- **Testes:** (a) buraco artificial de N quadros numa trajetória conhecida → o
  erro cresce com N; (b) `visible` sobrevive à reconstrução; (c) buraco de 0
  quadros → saída idêntica à entrada.
- **Comparar o erro com o alvo publicado**, não com zero: Crang mede RMSE de
  4,58 a 19,38 m em quadro não detectado, contra 0,44 a 16,24 m em quadro
  detectado (Tabela 2, p. 6); o melhor imputador observado faz 4,6 m
  (Discussão, pp. 10–11).
- **Entregável próprio: viés da imputação por faixa de velocidade.** O Bassek
  (p. 8) encontra que jogadores de linha são igualmente ativos dentro e fora do
  quadro, contrariando Mortensen e Bornn. Medir qual dos dois vale aqui.

### Fatia 8 — Experimento e relatório (ordem 8)
- **G4 antes de rodar:** orçamento explícito (execuções × tempo medido por
  execução) e lembrete de pausar Windows Update e suspensão. Referência do
  artigo: 3 min de parede por partida de 90 min em 1 CPU e 4 GB (§3, p. 9). Uma
  grade de 8 níveis × 8 `R_pz` × 2 variantes × 5 sementes × 3 jogos = 1920
  execuções, ou seja ~96 h se cada uma levar 3 min. **Vetorizar, cachear a posse
  por (degradação, `R_pz`) e paralelizar antes de rodar.**
- Varredura em duas dimensões: taxa de detecção × `R_pz`, por tipo de evento.
  `R_pz` ∈ {0,50 0,75 1,00 1,25 1,50 2,00 2,50 3,00} m, `R_dz` = max(1, `R_pz`)
  (D3).
- `R_pz` ótimo por nível escolhido por **leave-one-game-out, 3 dobras, critério
  escrito antes** (D4).
- `eps_c` segue o mesmo protocolo (D9b), mas **o resultado é de baixa confiança e
  o rótulo acompanha o número**: o único conjunto não visto é o jogo 3, com
  **8 escanteios de 3 cobradores** (`Player 7` ×4, `Player 5` ×2, `Player 22` ×2),
  e 1 escanteio move a taxa em 12,5 pontos. **Reportar a curva F1(`eps_c`)
  inteira com as contagens absolutas; não escolher um `eps_c` "ótimo" como se
  fosse estimativa pontual.** O número limpo e principal continua sendo o teto com
  `eps_c` = 3 m.
- **G5 antes da rodada final:** config congelada, tag `pre-rodada-final`, **uma
  única rodada**.
- Superfície F1, tabela final, relatório em markdown, `outputs/origem-dos-numeros.md`
  atualizado. Cada número rotulado **limpo** ou **exploratório**.
- **Saída:** `python -m src.run --all` reproduz tudo do zero.

---

## Estrutura

```
.
├── CLAUDE.md
├── config.yaml              # todas as constantes, cada uma com origem citada
├── docs/
│   ├── 00-problema.md
│   ├── 01-definicoes.md
│   ├── 02-dados.md
│   ├── 03-plano.md
│   ├── decisoes.md          # log; uma linha por decisão
│   ├── inspecao-metrica.md  # dados reais conferidos, com hashes
│   └── fatias/NN-plano.md   # plano de cada fatia, aprovado no G2
├── data/                    # gitignored
├── src/
│   ├── io/                  # loaders
│   ├── possession.py
│   ├── events/              # um módulo por família de evento
│   ├── broadcast.py         # simulador de visibilidade
│   ├── reconstruct.py
│   ├── evaluate.py
│   └── run.py
├── tests/
└── outputs/
    ├── origem-dos-numeros.md   # número → arquivo/linha/página
    └── ...                     # tabelas e figuras geradas
```

`outputs/origem-dos-numeros.md` existe desde o primeiro número reportado e é
atualizado em toda fatia que produza número.

## Folga

Não há prazo fixo. A folga não é para adicionar escopo — é para o jogo 3 estar num
formato diferente, para o sinal de `y` estar invertido e para a hierarquia de
reserva do S1 dar mais trabalho do que parece. Três coisas que a inspeção de
2026-10-29 já resolveu antes de custarem tempo: o formato do jogo 3 (não precisa
de `kloppy`), o estado da bola (é o NaN) e o fato de o tracking de jogador ser
completo.

## Se atrasar, corte nesta ordem

1. A segunda estratégia de reconstrução (Fatia 7).
2. A variante "janela fixa 40×40 m" da Fatia 6 — fica a do frustum, que é a que
   responde à crítica do Bassek.
3. A verificação contra a SkillCorner (Fatia 6) — vira trabalho futuro. A
   calibração contra os alvos publicados do Bassek **não** se corta.
4. Passes (Fatia 5). Doloroso, mas bolas paradas sozinhas já respondem à pergunta
   do projeto.

**A varredura de `R_pz` nunca se corta — é a pergunta do projeto.**
**A hierarquia de reserva do S1 (Fatia 4) nunca se corta** — sem ela o nosso
simulador mede o algoritmo errado.
**Nunca corte a Fatia 2.** Sem avaliação, não há projeto.

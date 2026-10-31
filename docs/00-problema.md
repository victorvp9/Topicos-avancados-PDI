# 00 — O problema

## Contexto em cinco parágrafos

Dados posicionais de futebol vêm em duas formas. **Event data** é a lista do que
aconteceu — passe de A para B aos 12min37s — historicamente produzida à mão por
operadores treinados. **Tracking data** são as coordenadas de todos os jogadores e
da bola, várias vezes por segundo, geradas automaticamente.

Sistemas de tracking dedicados usam doze ou mais câmeras fixas instaladas no
estádio e chegam a erros da ordem de 0,15 m em posição e 0,15 m/s em velocidade
(Mills, Introdução, p. 1, citando FIFA 2024). Contra captura de movimento 3D em
laboratório, o TRACAB Gen 5 fica em RMSE de 0,08 m para posição e 0,08 m/s para
velocidade (Crang, Métodos, p. 3, citando Linke et al. 2020). São precisos e caros.
A alternativa barata é derivar tracking do próprio vídeo de transmissão, que já
existe de qualquer forma. A FIFA reconheceu essa categoria como EPTS em 2021.

O problema é que a câmera de broadcast tem função editorial: ela segue a bola.
Isso produz três efeitos — a câmera se move continuamente, o campo não cabe no
quadro (jogadores somem por longos períodos), e a edição interrompe a
continuidade com replays e close-ups. A consequência mensurável é a **taxa de
detecção**: a fração de frames em que um dado jogador é efetivamente visto.

Crang et al. (2026) mostraram que essa taxa é a variável que organiza tudo. Com o
feed tático, os sistemas detectam o jogador em **89–96%** dos frames; com o
Camera 1, 56–64%; com o PGM, 36–42% (Tabela 1, p. 5). O resto é preenchido por
interpolação, e é ali que o erro mora: o RMSE geral de posição variou de **1,68 m
a 16,39 m** (Tabela 2, p. 6), mas separando por frame o contraste é brutal —
**0,44 a 16,24 m quando o jogador é detectado, contra 4,58 a 19,38 m quando não
é** (Tabela 2, p. 6). O melhor modelo de imputação observado foi do Provedor 1 no
PGM, com 4,6 m contra 10,0–11,6 m dos outros (Discussão, pp. 10–11).

Bassek et al. (2025) isolaram a causa: com vídeo de TV, **nenhum jogador está
visível em 38% dos frames** (Resultados, p. 6; a Discussão, p. 8, diz 41% —
divergência interna do artigo), a visibilidade se concentra em ~7 jogadores por
time, e os 11 de um time só aparecem juntos 3% do tempo. São **981 cortes por
partida, 10,9 por minuto** (p. 8). Com o scouting feed, ≥9 jogadores por time
aparecem em 97% do tempo.

Vidal-Codina et al. (2022) mostraram que é possível derivar eventos de tracking
com uma árvore de decisão determinística, atingindo mais de 90% de precisão e
revocação para passes, pontapés iniciais, pênaltis, escanteios, laterais e tiros
de meta (§3.1, p. 9). Mills et al. (2026) aplicaram esse mesmo algoritmo a
tracking derivado de broadcast, numa única partida e com três provedores
comerciais fechados.

**Correção (V2): "a no máximo 0,05 de F1 do multicâmera" vale "para a maioria dos
eventos", no melhor caso, e esconde a dispersão.** Os números do Mills
(Resultados, pp. 6–7):

| evento | multicâmera | melhor broadcast | pior feed (PGM) |
|---|---|---|---|
| escanteio | 1,00 | **1,00** | 0,00 em algumas configurações |
| pontapé inicial | 1,00 | **1,00** | 1 ou 2 de 4 detectados |
| tiro de meta | 0,94 | **0,97** (Camera 1) | 0,62 |
| tiro livre | 0,93 | 0,85+ | 0,57 |
| lateral | 0,97 | 0,87 | 0,60 |
| passe + cruzamento | 0,93 | ≥ 0,90 nos três feeds | média 0,78 |
| finalização | 0,48 | **0,24** | — |
| defesa | 0,67 | **0,00** | 0,00 |

Média por feed em passes e cruzamentos: 0,81 (Camera 1), 0,78 (PGM), 0,69
(Tactical). O PGM é muito pior porque os replays rompem a continuidade.

## A pergunta deste projeto

Vidal-Codina et al. afirmam, na discussão, que o framework pode ser aplicado a
tracking de qualidade inferior — de câmera tática ou de broadcast — **aumentando
o raio da zona de posse**. E listam, como trabalho futuro item 8, exatamente
isto: aplicar o algoritmo a tracking de broadcast, o que exigirá ajustar os
hiperparâmetros e os padrões de bola morta.

É uma hipótese declarada e nunca testada de forma controlada. Daí a pergunta:

> Aumentar o raio da zona de posse compensa a perda de taxa de detecção? Até que
> ponto, e para quais tipos de evento?

Mills mediu o desempenho em broadcast de forma agregada, com provedores fechados
e sem controle sobre a variável. Crang mediu a taxa de detecção, mas para posição
e velocidade, não para eventos. Ninguém cruzou as duas coisas, e ninguém testou a
compensação por `R_pz`.

## A estratégia

Fazer o experimento controlado, com dados abertos:

1. **Teto.** Rodar o auto-eventing sobre a Metrica, onde o tracking é completo e
   os eventos são anotados por humanos e sincronizados. Isso estabelece o
   desempenho máximo do algoritmo, sem degradação.
2. **Degradação controlada.** Simular a visibilidade de uma câmera de broadcast —
   um frustum que segue a bola — e descartar quem cai fora. Um parâmetro de
   abertura controla a taxa de detecção resultante.
3. **Reconstrução.** Preencher os buracos por interpolação, como fazem os
   sistemas reais.
4. **Medição em duas dimensões.** Varrer a taxa de detecção de ~100% a ~35% **e**
   o raio da zona de posse `R_pz`. O resultado é uma superfície F1(detecção,
   `R_pz`) por tipo de evento — e a resposta direta à hipótese dos autores é se,
   para cada nível de degradação, existe um `R_pz` que recupera o desempenho.

A calibração do simulador tem alvo numérico publicado, o que é melhor do que
depender de um dataset: as distribuições de visibilidade por frame do Bassek
(Resultados, p. 6, e Fig. 2) e a visibilidade por posição (Fig. 3, Tabela 1). O
dataset aberto da SkillCorner entra como verificação secundária, se sobrar tempo.

Duas variantes do simulador, e as duas têm origem:

1. **Janela fixa de 40×40 m centrada na bola.** É o que Mortensen e Bornn (2020)
   usaram. O Bassek critica explicitamente, e com razão: *"this analysis assumed
   that the field of view follows a 40 × 40 m window centered around subsequent
   event locations which does not account for zooms and editorial choices"*
   (p. 3). Fica como linha de base deliberadamente ingênua.
2. **Frustum com cortes editoriais.** Responde à crítica. Alvo: 38% de frames
   sem nenhum jogador visível e 10,9 cortes por minuto (Bassek, pp. 6 e 8). O
   FOOTPASS mede o efeito disso sobre um evento do nosso escopo: **46,8% dos
   laterais caem em segmento de replay**, porque o diretor corta para o replay
   depois de a bola sair e volta quando o lateral já foi cobrado (§3.2, p. 6).
   Lateral é também o evento com pior cobertura de caixa do jogador ativo:
   **43,8%, contra 81,5% na média** (§3.2, p. 6).

> ### Como a resposta tem de ser lida (achado da Fatia 3, 2026-10-31)
>
> Medimos que **o colapso dos eventos acima de `R_pz` = 1 m vem majoritariamente
> da regra de duelo, não da zona de posse.** O artigo exige `R_dz >= R_pz`
> (§2.3.1, p. 4), e essa exigência não é convenção: ela **garante que bola
> disputada seja classificada como duelo**. Como o duelo prevalece sobre a posse e
> não gera ganho nem perda, subir `R_pz` arrasta `R_dz` e converte posse em duelo.
>
> Com `R_dz` parado em 1 m, os ganhos **crescem** monotonicamente com `R_pz`
> (jogo 1: 1113 → 1199); com `R_dz` acompanhando, **sobem e caem** (1113 → 1138 →
> 976). Ou seja: aumentar a PZ **captura** mais contato, como os autores dizem — o
> que destrói o ganho é o duelo.
>
> **Portanto o resultado principal usa a configuração fiel ao artigo
> (`R_dz` = max(1 m; `R_pz`)), e a variante de `R_dz` fixo entra como
> decomposição de mecanismo, nunca como configuração de detector.** Se a resposta
> à pergunta do projeto for "não compensa", a razão a escrever é que a regra de
> duelo converte posse em duelo, e não que a PZ maior falhe em capturar contato.

> **Ressalva estrutural (V3), e ela vale para todo o projeto.** O nosso desenho
> remove **só jogadores**. A bola fica perfeita. No Mills, o erro de posição da
> bola vai de **RMSE 3,5 a 16,2 m** (Tabela 1, p. 5), muito acima de qualquer
> `R_pz` que vamos varrer (0,5 a 3 m). Logo todas as conclusões deste trabalho
> valem **"com bola perfeita e estado da bola oráculo"**, e isso tem de aparecer
> no relatório, não numa nota de pé. O que medimos é o efeito isolado da
> visibilidade de jogador — que é exatamente a variável que ninguém controlou.

## Escopo

**Dentro:** pontapé inicial, tiro de meta, escanteio, lateral, passe.

**Fora:** finalização, defesa, domínio. Justificativa: sem a coordenada z da
bola, que o tracking de broadcast não fornece, essas categorias não são
detectáveis de forma confiável — é a limitação que tanto Vidal-Codina quanto
Mills reportam explicitamente. Cruzamento também fica fora, porque não existe
definição padrão-ouro.

## Critério de sucesso

O projeto está pronto quando `python -m src.run --all` produz, do zero:

- uma tabela de precisão/revocação/F1 por evento e por nível de degradação;
- a superfície F1 × taxa de detecção × `R_pz`, por tipo de evento;
- o `R_pz` ótimo para cada nível de degradação, escolhido por **leave-one-game-out
  com critério escrito antes** (D4), não "ajustado numa partida e medido nas
  outras duas";
- o viés da imputação por faixa de velocidade;
- um relatório curto em markdown com os números, cada um rastreável em
  `outputs/origem-dos-numeros.md`.

Não é necessário que os números sejam bons. É necessário que sejam corretos,
reprodutíveis e explicáveis. **Resultado negativo é resultado** e entra no
relatório: se nenhum `R_pz` recupera o desempenho, essa é a resposta à pergunta
dos autores.

Dois rótulos, nunca misturados:

- **limpo** — parâmetros livres ajustados só em desenvolvimento, método
  congelado, **uma única rodada** no teste;
- **exploratório** — qualquer coisa decidida depois de ver o resultado.

Uma regra mudada depois de ver resultado é declarada como mudança, e tudo que
depende dela vira exploratório. Ver `docs/decisoes.md`.

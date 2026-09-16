# 00 — O problema

## Contexto em cinco parágrafos

Dados posicionais de futebol vêm em duas formas. **Event data** é a lista do que
aconteceu — passe de A para B aos 12min37s — historicamente produzida à mão por
operadores treinados. **Tracking data** são as coordenadas de todos os jogadores e
da bola, várias vezes por segundo, geradas automaticamente.

Sistemas de tracking dedicados usam doze ou mais câmeras fixas instaladas no
estádio e chegam a erros da ordem de 0,15 m em posição. São precisos e caros.
A alternativa barata é derivar tracking do próprio vídeo de transmissão, que já
existe de qualquer forma. A FIFA reconheceu essa categoria como EPTS em 2021.

O problema é que a câmera de broadcast tem função editorial: ela segue a bola.
Isso produz três efeitos — a câmera se move continuamente, o campo não cabe no
quadro (jogadores somem por longos períodos), e a edição interrompe a
continuidade com replays e close-ups. A consequência mensurável é a **taxa de
detecção**: a fração de frames em que um dado jogador é efetivamente visto.

Crang et al. (2025) mostraram que essa taxa é a variável que organiza tudo. Com o
feed tático, os sistemas detectam o jogador em 89–96% dos frames; com os demais
feeds, entre 36 e 64%. O resto é preenchido por interpolação, e é ali que o erro
mora. O RMSE de posição entre provedores variou de 1,68 m a 16,39 m.

Vidal-Codina et al. (2022) mostraram que é possível derivar eventos de tracking
com uma árvore de decisão determinística, atingindo mais de 90% na maioria das
categorias. Mills et al. (2026) aplicaram esse mesmo algoritmo a tracking
derivado de broadcast e encontraram que o melhor caso fica a no máximo 0,05 de F1
do sistema multicâmera — mas testaram uma única partida, com provedores
comerciais fechados.

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

A SkillCorner entra como calibração: o dataset aberto deles tem tracking real de
broadcast, e permite verificar se a distribuição de visibilidade produzida pelo
simulador se parece com a de um sistema de verdade.

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
- o `R_pz` ótimo para cada nível de degradação, ajustado numa partida e medido
  nas outras duas;
- um relatório curto em markdown com os números.

Não é necessário que os números sejam bons. É necessário que sejam corretos,
reprodutíveis e explicáveis.

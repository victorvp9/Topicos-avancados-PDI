# 01 — Definições de evento (especificação normativa)

Fonte única de verdade para as regras de detecção. Nenhuma regra pode ser
inventada em código. Se um caso não estiver coberto, pare e pergunte.

Origem: Vidal-Codina et al., *Automatic event detection in football using
tracking data* (2022), **e o material suplementar (Online Resource 1)**.

> **Leia o suplementar.** O artigo principal remete a ele para a discussão de
> hiperparâmetros e tolerâncias (S3–S4), o critério de benchmarking (S2), os
> atributos contextuais (S5) e o par ambíguo `foul?`/`free kick?` (S1). Sem ele,
> metade das constantes deste arquivo fica sem origem. Baixe na página do artigo.

Valores marcados `[S1]`…`[S4]` estão no suplementar. `[OK]` já foi confirmado no
artigo principal.

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

Valores do artigo `[OK]`: `R_pz` = 0,50 m para o provedor A; 1,00 m para B e C.
`R_dz` = 1,00 m para todos. Discussão completa em `[S3]`/`[S4]`.

> `R_pz` é **a variável independente deste projeto.** Os autores afirmam que o
> framework se aplica a dados de qualidade inferior aumentando esse raio. É essa
> afirmação que vamos testar.

### Control frame

Frame em que há posse ou duelo. Para cada um, armazenar:
- distância de cada jogador à bola;
- deslocamento da bola `ds` de `f` para `f+1`;
- direção e velocidade de **entrada** (`d0_f`, `v0_f`, usando `f-1`);
- direção e velocidade de **saída** (`d1_f`, `v1_f`, usando `f+1`).

### Suavização

Se a posição da bola for ruidosa, filtro **Savitzky-Golay** nas coordenadas x-y:
polinômio de **segunda ordem**, janela de **sete frames**. A 25 Hz equivale a
suavizar com os 0,25 s vizinhos. `[OK]`

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

`eps_s` = `[S3]`

### Ganho de posse

Proximidade não basta — é preciso inferir **contato**, e sem a coordenada z isso
se faz pela mudança da trajetória da bola.

Para uma sequência de control frames `f0 ... fn` com a bola na PZ do mesmo
jogador:

- **mudou de direção** se `d0_f0 . d1_fn < eps_theta`;
- **mudou de velocidade** se `|v0_fi - v1_fi| > eps_v` em pelo menos um frame.

Se **direção ou velocidade** mudou, há ganho de posse em `f0`.

`eps_theta` = `[S3]` · `eps_v` = `[S3]`

> Consequência direta para o projeto: o ganho de posse depende de **derivadas** da
> posição da bola. Interpolação linear zera a curvatura, então é de esperar que a
> degradação ataque o ganho de posse mais do que a perda. Hipótese a testar.

---

## Passo 2 — Eventos

Set pieces são detectados na transição `dead ball -> live`, por **gatilho**
(posição dos jogadores) e **padrão** (posição da bola). A checagem é **ordenada**;
tiro livre é o último ramo.

### Pontapé inicial
- **Padrão:** bola próxima ao ponto central.
- **Gatilho:** todos os jogadores em seus respectivos lados do campo.
- Tolerância do ponto central: `[S4]`

### Escanteio
- **Gatilho:** jogador e bola compartilham PZ.
- **Padrão:** ambos a **no máximo 3 m** de um vértice do campo. `[OK]`

### Lateral
- **Padrão:** bola sobre a linha lateral, fora da região dos vértices. `[S4]`

### Tiro de meta
- **Padrão:** bola na pequena área. `[S4]`

### Tiro livre — categoria residual
Transição `dead ball -> live` sem nenhum padrão acima reconhecido. Sem padrão
espacial próprio, é o pior resultado do artigo. Sempre o `else`.

### Atribuição ao jogador
Set pieces são atribuídos por uma **PZ específica de bola parada**, com seu
próprio conjunto de hiperparâmetros — distinta da `R_pz` de jogo corrido. `[S4]`

### Passe
- Perda de posse de A seguida de ganho de B, mesmo time.
- A mudança de trajetória no ganho é o que indica o toque de B.
- Se B for adversário, é interceptação. Se for companheiro, é recepção.

### Cruzamento — fora do escopo
Exige origem na *cross zone*, próximo controlador dentro da área ativa e ao menos
um atacante na área. Sem definição padrão-ouro; fica fora.

### Finalização e defesa — fora do escopo
Dependem de sequência com desfecho e, na prática, da coordenada z. Fora.

---

## Avaliação

O critério oficial de benchmarking está em `[S2]` — **use o deles**, não o meu.
Enquanto não tiver o suplementar, use o critério do Mills et al.: mesmo tipo,
dentro de **3 s**, casamento um-para-um, o mais próximo no tempo.

Reportar precisão, revocação, F1 e a **contagem absoluta** por tipo. Com classes
pequenas, um único acerto move o F1 de forma dramática.

---

## Ressalvas

**O gabarito tem erros.** Os autores relatam eventos não anotados, timestamps
errados em mais de 10 s e jogadores errados. A taxa de detecção nunca chega a
100%. Ao analisar falsos positivos, considere que o algoritmo pode estar certo.

**Hiperparâmetros são por provedor.** Os autores recomendam validação cruzada num
subconjunto de partidas para otimizá-los a cada fonte de dados. Como temos três
partidas da Metrica, reserve uma para ajuste e duas para teste — e nunca ajuste
no conjunto de teste.

**Custo computacional.** No artigo, 3 minutos de tempo médio de parede para uma
partida de 90 minutos, em 1 CPU e 4 GB de RAM. Se a sua implementação levar muito
mais, há algo errado — provavelmente um laço sobre frames que deveria ser
vetorizado.

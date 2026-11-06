# Fatia 10 — Auditoria de erros no teto da Metrica (EXPLORATÓRIO)

Data: 2026-11-06. Pedido do Victor: comparar os resultados com o gabarito, inferir
o que está errado e testar variações. G2 é meu, por delegação.

**Rótulo: EXPLORATÓRIO.** A auditoria é diagnóstico. **O gabarito nunca é
alterado** e nenhuma categoria entra no F1 (`CLAUDE.md`). As hipóteses que ela
gerar são congeladas e testadas no IDSSE (Fatia 11), não aqui.

## 1. Por que no teto

O maior espaço para melhorar está no teto, não no broadcast:
- bola parada micro: F1 0,598 contra 93,4 % no artigo (S4.2, p. 8);
- só 283 das 481 detecções caem num reinício anotado (`origem-dos-numeros.md`,
  Fatia 4);
- já se sabe que buracos curtos da bola NaN geram transições espúrias. Com um
  mínimo de 1 s de bola morta, o teto de precisão iria a 90,4 % (282/312).

A auditoria mede o resto: confusão de tipos, jogador errado e FN.

## 2. População e ponto

Os 3 jogos da Metrica, teto, `R0` = 0,5 m, estrito, âncora `frame`, lacuna 5 com,
`acompanha_r_pz`: o ponto da linha AB1 da `tabela1.csv`. As contagens têm de bater
com ela (bola parada 232 / 481 / 295; passe principal 2187 / 2262 / 2650), ou a
fatia para.

## 3. Categorias, definidas antes de olhar a distribuição

### 3.1 Cada detecção de bola parada (481)
1. **TP**: casa no estrito.
2. **Tipo errado**: há reinício anotado na âncora dela, mas de outro tipo.
3. **Jogador errado**: mesmo tipo e âncora, outro executor.
4. **Sem reinício anotado na âncora**, subdividida pela evidência do tracking e
   dos eventos crus. Para cada detecção vale a primeira regra que se aplicar, na
   ordem abaixo:
   - 4a. **Saída de bola**: a última posição da bola antes da corrida morta está
     fora do campo (|x| > 52,5 m ou |y| > 34,0 m, sem margem), ou há `BALL OUT`
     cru a ≤ 2 s antes do início da corrida morta;
   - 4b. **Falta**: há `FAULT RECEIVED`, ou `CHALLENGE` com falta, cru a ≤ 2 s
     antes do início da corrida morta;
   - 4c. **Buraco de rastreamento**: corrida morta com menos de 1 s;
   - 4d. **Outro**: o resto.

   Os limiares de 2 s e 1 s são **nossos**, de diagnóstico, sem fonte. O 1 s é o
   da sensibilidade já declarada (Bassek, Métodos, p. 4). Nenhum vira regra do
   detector.

### 3.2 Cada reinício do gabarito (295, mais os 13 `no_dead_ball_before`)
1. **TP**.
2. **Detectado com outro tipo**.
3. **Detectado com outro jogador**.
4. **Sem detecção na âncora**: há transição, mas a detecção está noutra âncora
   ou falta.
5. **Sem transição morta → viva** (os 13): perda declarada, já conhecida.

### 3.3 Matriz de confusão
Tipo detectado × tipo anotado, nas âncoras em comum, por jogo, mais a reserva (S1)
que produziu cada detecção.

### 3.4 Passe
- **FN (463):** a decomposição a–d existente, cruzada com o tipo do evento cru
  anotado mais próximo.
- **FP (75):** o evento cru mais próximo do mesmo jogador a ≤ 1 s, se existir, e o
  tipo dele. Pergunta: o "passe" detectado é cruzamento, finalização, desarme ou
  nada?

### 3.5 Inspeção visual
Uma amostra de **até 10 casos por categoria**, sorteada com semente fixa, cada um
num PNG com bola e jogadores nos ±3 s em volta da âncora, mais os eventos crus da
janela. Serve para eu e o Victor conferirmos se a regra da categoria diz a
verdade. Se uma categoria se mostrar mal definida, isso é registrado como achado;
a regra não é mudada para "encaixar".

## 4. Hipóteses

A auditoria roda nos 3 jogos, mas **as hipóteses são escritas olhando só os jogos
1 e 2**:
- **Arquivo:** `docs/fatias/10-hipoteses.md`, escrito por mim antes de abrir os
  números do jogo 3.
- **Conteúdo de cada uma:** a mudança no detector, a origem (artigo ou nossa) e o
  efeito esperado com sinal.
- **Teste no jogo 3:** uma vez só, rotulado exploratório.
- **O que sobreviver:** entra no pré-registro da Fatia 11 (IDSSE).

## 5. Implementação (codificador)

- **`src/audit.py`** e o modo `python -m src.run --auditoria`. Reusam o detector,
  o casador e os carregadores existentes; não mudam nenhuma regra.
- **Saídas em `outputs/auditoria/`:**
  - `deteccoes_bp.csv`, uma linha por detecção, com categoria e evidência;
  - `gabarito_bp.csv`, uma linha por reinício;
  - `confusao_bp.csv`;
  - `passes_fp.csv` e `passes_fn.csv`;
  - `resumo.csv`, com as contagens por categoria × jogo;
  - `casos/`, com os PNGs da §3.5.
- **Constantes:** as da §3.1 (2 s, 1 s, |x| 52,5, |y| 34,0) vão para
  `config.yaml`, num bloco `auditoria:`, com a origem.
- **Testes obrigatórios:**
  1. As categorias de 3.1 e 3.2 são exaustivas e mutuamente exclusivas: as somas
     fecham com 481 e 308.
  2. Os TP da auditoria são iguais ao `tp_diag` da `tabela1.csv` AB1, por tipo.
  3. Um caso sintético para cada subcategoria 4a a 4d, inclusive o desempate pela
     ordem.
  4. Nenhum evento do gabarito é descartado; os 13 aparecem na categoria 5.
  5. O sorteio da amostra visual é determinístico (semente no código e no
     manifesto).
  6. Um limiar da §3.1 alterado no config muda a contagem num caso sintético (o
     parâmetro não é ignorado).

## 6. Fora
- Mudar o detector nesta fatia.
- Alterar o gabarito.
- Rodar nas condições degradadas.
- Escolher limiar olhando um caso.

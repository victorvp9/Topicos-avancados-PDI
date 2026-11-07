# Fatia 10 — Hipóteses da auditoria, congeladas para o IDSSE (Fatia 11)

Data: 2026-11-07. **Contaminação declarada:** antes de escrever isto, vi as
contagens por categoria do jogo 3 e o achado do revisor sobre ele (a troca de
IDs). Por isso o jogo 3 não serve de teste fora da amostra. O teste que vale é o
IDSSE, e estas hipóteses ficam congeladas antes de eu abrir qualquer resultado de
lá. Base: `outputs/auditoria/` e a revisão da Fatia 10, na leitura dos jogos 1 e 2.

## O que a auditoria mostrou (Metrica, teto)

1. **O falso positivo de bola parada é, quase todo, artefato do estado da bola
   derivado de NaN.** Das 198 detecções sem reinício anotado, 168 vêm de uma
   corrida morta com menos de 1 s, num buraco de rastreamento em jogo corrido
   (PNGs 2/22522, 1/5520). Outras 20 (4d) são o mesmo fenômeno, com 1–4 s
   (2/46389). Saída de bola não anotada (13) e falta (3) são minoria.
2. **A confusão de tipos é o segundo erro** (49 detecções), e ocorre quase toda
   pelas reservas:
   - tiro livre anotado e detectado como tiro de meta (10), `free_kick?` (11) ou
     lateral (7);
   - escanteio detectado como tiro livre (6) ou lateral (3); no PNG 1/18203 a bola
     rastreada está na lateral, a ~6 m da bandeirinha, fora do `ε_c` = 3 m.
3. **Jogador errado é raro** (2, ambos no jogo 3: troca de IDs, item 5).
4. **Passe:** dos FN, 297 são da causa a e 144 da b. O evento cru vizinho mais
   comum é `CHALLENGE` ou `RECOVERY` (243 de 463), isto é, passes no meio de
   disputa. A causa b é a supressão que "come" o passe seguinte, a mesma da
   Fatia 9.
5. **Achado de dado, jogo 3:** os IDs `g3_home_6` e `g3_home_13` parecem trocados
   entre tracking e eventos no 2º tempo (~50 FN e ~53 FP de passe). Não verificado
   de que lado está o erro. **Não corrijo nada**: é registrado e reportado (regra
   de ouro do `CLAUDE.md`).

## Hipóteses congeladas para o IDSSE

O IDSSE traz o estado da bola explícito (`BallStatus`, quadro a quadro), como o
provedor B do Vidal-Codina (Tracab, booleano; §2.1, p. 3). Na Fatia 11, o D1 lá é
esse booleano, sem NaN. Isso transforma o achado 1 num teste natural.

- **H1 (achado 1). Com o estado da bola booleano do provedor, a precisão de bola
  parada no teto fica muito acima da Metrica (0,482).**
  - Predição: precisão micro ≥ 0,75 no IDSSE.
  - Fonte do limiar: **nossa**. É o teto de 90,4 % (282/312), medido na Metrica
    com o mínimo de 1 s, menos uma folga de 15 pontos, porque não sei a taxa de
    reinícios não anotados da DFL.
  - Se falhar, o achado 1 não explica o teto baixo, ou a DFL anota menos
    reinícios.
- **H2 (achado 4, regra D da Fatia 9). A supressão que exige a perda do executor
  aumenta o F1 do passe principal no teto do IDSSE.**
  - Predição: Δ F1 > 0 nos 7 jogos agregados e em pelo menos 5 dos 7.
  - Sem parâmetro livre.
  - Na Metrica, exploratório: +0,010 no teto.
- **H3 (achado 2). Os erros de tipo concentram-se nas reservas.**
  - Predição: no IDSSE, a precisão das detecções pela via `padrao` é maior que a
    das reservas 1 e 3, para bola parada micro.
  - É descritiva e não muda método.

## Fora (não vira regra, nem no IDSSE)
- **Mínimo de 1 s de bola morta.** Só faz sentido com estado derivado de NaN; no
  IDSSE não se aplica.
- **`ε_c` maior.** Continua sem ótimo escolhido, D9b(ii); a curva é reportada.
- **Corrigir a troca de IDs do jogo 3.**

# Análise de alternativas para melhorar a detecção sob degradação (pós-`final`)

Data: 2026-11-06. **Tudo aqui é EXPLORATÓRIO**: feito depois de ver a rodada final,
nos mesmos 3 jogos. Nada foi implementado; nenhum número de `docs/relatorio.md`
muda. Fontes: diagnóstico meu em `tabela3.csv` e `pontos.csv`; medições M1 e M2 do
codificador (B8, `rep` 0 apenas, `reconstruido`, `R0`, estrito, `frame`; scripts
fora do repositório, reprodução bate com `pontos.csv` jogo a jogo); revisão cética
do revisor.

## 1. Onde o F1 se perde (B8)

- **Passe.** Os FN com passador imputado no quadro anotado caem quase todos num
  **apagão total**, sem nenhum jogador visível: 406 de 418 (M1, `rep` 0). Num
  apagão, o passe é praticamente indetectável (3 TP em 409 eventos). A
  visibilidade parcial com o passador imputado quase não existe (12 casos). Com
  o critério `mills`, que não exige jogador, o F1 é 0,818, contra 0,799 no
  estrito: o passe não é detectado, não é atribuído ao jogador errado.
- **Bola parada.** 109 de 140 FN caem em apagão; 101 saem pela reserva 3 ("sem
  padrão de tiro livre"), e 54 viram `goal_kick` por engano. O tipo e o tempo
  costumam sair certos e o **jogador sai errado** (a folga do `mills` sobe de
  +0,005 no teto para +0,057 em B8; na lateral, de +0,009 para +0,155).
- **Distâncias na posição reconstruída** (passe FN em apagão, mediana / p90):
  executor–bola 10,3 / 28,4 m. O executor é o jogador mais próximo da bola em
  35 % dos casos.
- Os apagões que contêm um FN duram 21–25 s em mediana. A média de 13,3 s é por
  episódio; um evento tem mais chance de cair num episódio longo (efeito de
  amostragem por comprimento).

**Leitura:** na variante B, a perda é a fração de eventos que caem num apagão
total. No broadcast real, a bola também some nesses quadros (replay; D2 e D1b), e
nenhum método baseado em posição de jogador recupera esses eventos sem a bola
oráculo.

## 2. Alternativas avaliadas

Conta de equilíbrio (codificador): somar detecções cuja fração de acerto é q só
sobe o F1 se q > F1/2 (≈ 0,40 para o passe em B8).

| alternativa | dependência da bola perfeita (D2) | ganho esperado | veredito |
|---|---|---|---|
| 1. `R_pz` que cresce com a incerteza da linha imputada | alta | baixo: o raio vira "o mais próximo", que acerta 35 % < 40 %; o `R_dz` acompanha e o duelo apaga a posse | não |
| 2a. Reconstrução sem bola (velocidade constante nas bordas; relativa aos colegas) | nenhuma | ~0: só 4 de 529 casos são de borda; em 97–98 % dos FN imputados não há colega visível para ancorar | não, na variante B |
| 2b. Imputação guiada pela bola | total, e circular | inflado | **não fazer** |
| 3. Padrão de bola parada caindo para o mais próximo | alta | pequeno: contraria o problema 3 do S1, e o passe do executor continua morto no apagão | não |
| 4. Toque detectado pela trajetória da bola | total | negativo no estrito (35 % < 40 %); é outro algoritmo | não |
| 5a. `presentes` calculado por `visible`, não por "não-NaN" (hoje a reconstrução desliga o problema 2 do S1: a reserva 2 sai 282 vezes no `bruto` B8 contra 8 no `reconstruido`) | baixa | desconhecido | candidata, depende de decisão (G3) |
| 5b. A supressão de bola parada exige a perda do executor (ou uma janela de tempo), em vez de "a primeira perda da corrida viva" | nenhuma | ≤ +0,016 no passe (61 FN, todos com passador visível; `rep` 0) | candidata; muda uma [LACUNA] decidida e pode mudar o teto |
| 6. Estratificar P/R/F1 em dentro e fora do apagão (descritivo, sem filtrar evento) | — | não melhora; explica | **recomendada** |
| 7. Controle "a bola some no corte" (bola NaN no apagão, `ball_live` mantido oráculo) | mede a dependência | não melhora; mostra quanto do resultado é artefato do D2 | recomendada antes de qualquer 1, 3 ou 4 |
| 8. Marcar com flag de confiança os eventos com executor imputado (número principal no conjunto inteiro) | nenhuma | produto mais honesto | opcional |

**Divergência entre os agentes:** o revisor punha a 2a (reconstrução sem bola,
escolhida pelo RMSE contra o teto) em primeiro lugar, por ser a única que ataca a
causa sem depender do D2. A medição M1 do codificador mostra que, na variante B,
não há colega visível para ancorar em 97–98 % dos casos. Prevalece o dado: a 2a
ajudaria a variante A, que quase não perde nada.

## 3. Não fazer: melhoraria o número, não o método

Mudar o simulador (menos cortes, apagões mais curtos ou descolados dos
reinícios); trocar o critério principal pelo `mills`; tirar do denominador os
eventos com executor imputado; usar a identidade anotada ou as posições do teto
na reconstrução; afinar `R_pz`, `ε_c` ou janela por nível; acrescentar sementes
até um resultado de borda passar; reportar F1 sem P e R quando o ganho vem de
cortar falsos positivos (`bruto` A8 tiro de meta 0,571 contra 0,396 no teto).

## 4. Como um resultado poderia deixar de ser exploratório

Pré-registrar agora e rodar LOGO nos mesmos 3 jogos **não** limpa o resultado: a
escolha da alternativa já foi guiada pela `tabela3`. O caminho limpo é dado novo
com eventos anotados, com código, método e regra congelados numa tag e uma única
rodada. Candidato: o Integrated Dataset do Bassek 2025, 7 jogos
(`docs/02-dados.md`; licença não conferida). O SkillCorner aberto não tem
gabarito de evento e serve só para conferir a visibilidade do simulador.

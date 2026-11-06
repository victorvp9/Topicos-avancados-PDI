# Fatia 9 — Apêndice EXPLORATÓRIO: onde a detecção se perde, e duas correções

Data: 2026-11-06. Pedido do Victor depois da análise `docs/analise-alternativas.md`:
fazer as frentes 1 a 4 e **encerrar** o projeto em seguida. G2 é meu, por delegação
(`docs/estado.md`, "Portões").

**Rótulo: tudo nesta fatia é EXPLORATÓRIO.** As frentes foram escolhidas depois de
ver a rodada final, nos mesmos 3 jogos. Nada aqui altera `docs/relatorio.md` §1–§4
nem as saídas em `outputs/experimento/`. O resultado entra no relatório como
apêndice, com o rótulo em cada número.

## 1. Regras escritas antes de medir

- **Não há regra de "melhorou".** Reporta-se P, R e F1, com as contagens, ao lado
  da linha base da rodada final. Nenhuma variante substitui a original.
- **Pontos medidos:** `R_pz` = `R0` = 0,50 m; estrito; âncora `frame`;
  `acompanha_r_pz`; lacuna 5 com; condição `reconstruido` (a frente C também em
  `bruto`, onde ela é a regra atual). Níveis: 1 (teto), B5, B6, B7, B8 (5 sementes,
  `rep` 0–4) e A8 (`rep` 0). Os 3 jogos, somando contagens e depois dividindo
  (R5). Alvos: os dois primários e cada tipo de bola parada.
- **Linha base:** recomputada pela mesma máquina com tudo desligado. Ela tem de
  bater, linha a linha, com `outputs/experimento/pontos.csv` nos mesmos pontos.
  Se não bater, a fatia para.
- **Nível 1:** cada frente reporta se o teto mudou (contagens). Se mudar, a
  mudança é resultado e é reportada; nada é ajustado para que não mude.

## 2. As frentes

### A. Descritivo: dentro e fora do apagão
Para cada evento do gabarito, nos pontos acima, registrar se o quadro de
referência cai num **apagão total**, isto é, nenhum jogador com `visible = True`
naquele quadro. O quadro de referência é o anotado para passe e o primeiro quadro
vivo (`frame`) para bola parada. P/R/F1 por estrato:
- a revocação divide os eventos do gabarito pelo estrato do evento;
- a precisão divide as detecções pelo estrato do quadro da detecção.

Nenhum evento é filtrado: os dois estratos somam o total. Reportar também a fração
de eventos em apagão por nível.

### B. Controle "a bola some no corte"
Em cada quadro de apagão total, `ball_x` e `ball_y` viram NaN **depois** do
simulador e da reconstrução. O `ball_live` continua oráculo (D1b), porque não é
recalculado. É o mesmo detector, sem mudança de código fora do ponto que zera a
bola. Mede quanto do resultado atual depende da bola perfeita (D2) nos quadros em
que, no broadcast real, ela também some.

### C. Problema 2 do S1 conta só linhas visíveis (`presentes` por `visible`)
Em `bola_parada.detectar`, o "executor deixou de ser detectado" passa a usar a
visibilidade, não "linha não-NaN". Na condição `reconstruido`, isso devolve ao
detector a informação de que a linha foi imputada. No teto e no `bruto` o
resultado é idêntico por construção: no teto tudo é visível, e no `bruto` linha
existente é linha visível. Isso vira teste.

### D. A supressão de bola parada exige a perda do executor
Em `passes.suprimir`: quando a detecção tem executor, a perda suprimida é a
primeira da mesma corrida viva, com `frame >=` o da detecção **e do mesmo
jogador**. Sem perda dele na corrida, nada é suprimido. Quando a detecção não tem
executor, vale a regra atual. Muda uma [LACUNA] decidida em 2026-11-01; por isso é
exploratória e reporta o teto.

As frentes B, C e D são medidas uma por vez contra a linha base, e não combinadas.
A frente A é medida na linha base e em cada uma das outras.

## 3. Implementação (codificador)

- **Chaves novas em `config.yaml`**, num bloco `exploratorio:`, todas **desligadas
  por padrão**:
  - `bola_some_no_apagao: false`;
  - `presentes_por_visible: false`;
  - `supressao_exige_executor: false`.
  Com as três desligadas, todo número aceito, inclusive o da rodada final, fica
  idêntico.
- **`grade_de_posicoes`** pode passar a devolver também a visibilidade. Se mudar a
  assinatura, todos os chamadores são atualizados; um teto com tudo visível fica
  igual.
- **Novo modo `python -m src.run --exploratorio`.** Roda a grade da §1 para
  linha base, B, C e D e grava em `outputs/exploratorio/`:
  - `pontos.csv`, no mesmo esquema do experimento mais a coluna `frente`;
  - `apagao.csv`, com os estratos da frente A;
  - `manifesto.json`.
  Ele reaproveita `rodar_unidade`, cache e manifesto do experimento. Não toca
  `outputs/experimento/`.
- **Orçamento:** cerca de 66 unidades por frente × 4 frentes, com um ponto por
  unidade. Peço ao codificador o tempo medido de uma unidade antes de rodar. Se
  passar de 2 h de CPU, vai ao Victor (G4). `n_workers` fica em 2.

### Testes obrigatórios
1. Com as chaves desligadas, uma unidade B8 `rep` 0 e o nível 1 reproduzem
   `outputs/experimento/pontos.csv` bit a bit nos pontos da §1.
2. Cada chave ligada muda a saída num caso sintético construído para isso: o
   parâmetro não pode ser ignorado.
3. C: no teto e no `bruto`, ligar a chave não muda nada.
4. B: a bola vira NaN só nos quadros de apagão total; `ball_live` fica inalterado;
   nenhum NaN conta como acerto.
5. D: caso sintético com duas perdas na corrida; com a chave ligada, suprime a do
   executor e não a primeira.
6. A: os estratos somam o total; evento sem detecção conta como FN no seu estrato
   e não é excluído.
7. Semente de cada unidade no manifesto; o cache inclui as chaves novas no hash.

## 4. Fora
Qualquer alternativa marcada "não" em `docs/analise-alternativas.md` (1, 2a, 2b,
3, 4). Combinações de frentes. Varredura de `R_pz`. Mudanças no simulador.

## 5. Fim
Revisão independente, commit, apêndice exploratório no relatório e `estado.md`
encerrado. Não há tag nova: a `final` continua marcando o resultado limpo.

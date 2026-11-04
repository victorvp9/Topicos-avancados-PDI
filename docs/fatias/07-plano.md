# Fatia 7 — Reconstrução

Plano escrito pelo orquestrador em 2026-11-04. Os portões foram delegados a mim
(`docs/decisoes.md`, 2026-10-30), e o G2 desta fatia foi decidido por mim, com
registro. As lacunas que eu resolvi vão marcadas **[LACUNA]**.

Fonte de verdade: `docs/03-plano.md` (Fatia 7 e as regras transversais 1 a 8);
`docs/02-dados.md` (esquema `tracking`, significado de `visible`, a tabela de
alvos publicados); `docs/fatias/06-plano.md` §3 (a saída do simulador).

---

## 1. Objetivo

1. **`reconstruir`:** preencher as linhas que o simulador removeu, por
   interpolação linear no tempo, marcando-as `visible = False`. Nada que veio da
   entrada é reescrito.
2. **Medir o erro da reconstrução** e compará-lo ao publicado (Crang), não a zero.
3. **Entregável próprio: viés por faixa de velocidade**, em duas perguntas:
   - **(a)** a ausência no nosso simulador depende da velocidade? É o teste
     Bassek contra Mortensen e Bornn, aplicado ao simulador.
   - **(b)** a interpolação linear subestima a velocidade, e em que faixa?
4. **Diagnóstico para a Fatia 8:** a distância executor–bola no quadro anotado,
   depois da reconstrução.

Fora desta fatia: rodar o detector sobre o tracking reconstruído e qualquer F1
degradado (Fatia 8). Segunda estratégia de reconstrução só se sobrar tempo, que é
o que o `docs/03` manda.

---

## 2. Fontes conferidas (PDF, página)

Todos os números abaixo foram conferidos por mim em 2026-11-04 no texto extraído
do PDF, com pypdf. As páginas são as do PDF.

| o quê | valor | fonte |
|---|---|---|
| RMSE de posição, **não detectado**, PGM (3 provedores, 720p e 1080p) | 4,58 a 11,56 m | Crang, Tabela 2, p. 6 |
| idem, **Cam 1** | 9,08 a 10,27 m | Crang, Tabela 2, p. 6 |
| RMSE de posição, **geral**, PGM | 3,10 a 9,24 m | Crang, Tabela 2, p. 6 |
| idem, **Cam 1** | 5,89 a 7,37 m | Crang, Tabela 2, p. 6 |
| RMSE de posição, **detectado**, PGM / Cam 1 | 1,02 a 3,62 / 0,66 a 5,03 m | Crang, Tabela 2, p. 6 |
| melhor imputador, não detectado | 4,6 m (Provedor 1, PGM), contra 10,0 a 11,6 m dos outros | Crang, Discussão, p. 11 |
| goleiros excluídos da validação | — | Crang, p. 3 (já registrado em `docs/02-dados.md`) |
| filtro das posições | Butterworth de 3ª ordem, corte de 1 Hz | Bassek, Métodos, p. 4 (já em `config.yaml`: `simulador.butter_*`) |
| velocidade por diferenças centrais | — | Bassek, Métodos, p. 4 (Winter 2009) |
| limiar de alta velocidade | **> 6,9 m/s** | Bassek, Métodos, p. 4 (Giménez et al. 2019) |
| TV: fração da distância visível, GK/DEF/MID/OFF | 14 / 40 / 52 / 46 % | Bassek, Resultados, p. 6 (alvo da calibração na Fatia 6) |
| TV: fração da distância **em alta velocidade** visível, GK/DEF/MID/OFF | **31 / 49 / 48 / 52 %** | Bassek, Resultados, p. 6 |
| "players are equally active inside and outside of the field of view" | — | Bassek, Discussão, p. 8 |
| Mortensen e Bornn: o dado *"is not missing at random"*; com escala linear, tempo em baixa velocidade superestimado, distância total subestimada | — | **Via Bassek, p. 3.** O original não está em `refs/`; não conferi. |

**Duas leituras que valem para a fatia inteira:**

1. **O nosso RMSE "detectado" é 0 por construção.** O simulador remove linhas,
   não as perturba. Logo o nosso RMSE geral é um **limite inferior** do RMSE
   geral do Crang com a mesma taxa. **A comparação justa é a da linha "não
   detectado".**
2. **A pergunta 3(a) mede o simulador, não o mundo.** Se a ausência depender da
   velocidade, isso vem da cunha e dos cortes que nós calibramos. A comparação
   com os 31/49/48/52 % do Bassek é uma **validação a mais** do simulador. Ela
   não entrou na calibração, então é validação livre.

**Previsão registrada antes de medir (não decide nada):** em B8, o RMSE não
detectado da interpolação linear, sem GK, sai **acima** dos 4,6 m do melhor
imputador do Crang. Não prevejo se cai dentro ou fora da faixa dos outros
provedores (10,0 a 11,6 m).

---

## 3. `reconstruir` — contrato

```
reconstruir(degradado: TRACKING, presenca: DataFrame) -> (TRACKING, dict)
```

### Entradas

- **`degradado`:** a saída de `broadcast.degradar` (esquema TRACKING), ou o teto.
- **`presenca`:** as linhas `(game, period, frame, player_id, team, is_gk)` do
  **teto**, com o índice do teto.
  - **Proibido ler `x`/`y` do teto aqui.** `presenca` **não tem** essas colunas.
    Um teste passa `presenca` sem elas e outro passa com `x`/`y` lixo, para
    provar que não há vazamento.
  - **[LACUNA] Usar a presença do teto é declarado.** Equivale a conhecer a
    escalação e os horários de substituição, que estão na súmula oficial. Os
    provedores do Crang entregam posição para todo jogador-quadro: as contagens
    "Overall" do PGM e do tático são praticamente iguais (Tabela 1, p. 5).

### Saída

- **TRACKING** com as linhas de `presenca` que têm âncora, no **índice e na
  ordem do teto**.
- **dict de contagens:** `n_imputadas`, `n_sem_ancora`, `n_jogadores_periodo_sem_ancora`.

### Regras

1. **Linha que veio em `degradado`:** `x`, `y` e `visible` copiados **bit a bit**.
   `visible` nunca é sobrescrito, nem de True para False nem o contrário.
2. **Linha de `presenca` ausente em `degradado`:**
   - `x` e `y` saem de `np.interp` sobre `frame`, por `(game, period, player_id)`;
   - as âncoras são as linhas desse jogador naquele período em `degradado`;
   - `visible = False`.
   Nunca atravessa o intervalo nem cruza jogos.
3. **Bordas:** antes da primeira âncora e depois da última, a posição fica
   **constante**, igual à âncora mais próxima. É o comportamento padrão do
   `np.interp`. **[LACUNA]** Linear não extrapola, e extrapolar velocidade
   inventaria movimento. As linhas de borda são contadas à parte (§4).
4. **Jogador sem nenhuma âncora no período:** as linhas **ficam ausentes**.
   - Nunca viram NaN e nunca recebem posição inventada.
   - Entram em `n_sem_ancora` e são reportadas.
   - Na Fatia 8, o jogador ausente é perda de revocação, pela regra transversal 2.
5. **Sem NaN na saída.** Se `degradado` trouxer NaN em `x`/`y`, `reconstruir`
   **estoura**, porque NaN não pode servir de âncora.
6. **Entrada idêntica ao teto** (buraco de 0): a saída é igual ao teto bit a bit,
   no índice, nas colunas, nos dtypes e nos valores.
7. **Valida** a saída com `validar(..., TRACKING, ...)`, como o resto do código.

---

## 4. Medidas: `python -m src.run --reconstrucao`

**Escopo comum a todos os blocos:**
- Tracking reconstruído de cada `(variante, nível)`, nos 3 jogos, semente
  `rep = 0` (`broadcast.semente_efetiva`).
- A semente efetiva sai impressa em cada bloco e no CSV.
- O tempo de parede por `(jogo, nível)` sai impresso.

**Erro de posição:** `d = hypot(x_rec − x_teto, y_rec − y_teto)` e
`RMSE = sqrt(mean(d²))`. **[LACUNA]** O Crang não escreve a fórmula de posição; a
da p. 4 é a de velocidade. Uso o erro euclidiano, o mesmo `d` que ele usa como
"positional error" (p. 4).

**Bloco 1 — sanidade.** Para cada jogo, `reconstruir(teto, presenca)` tem de ser
igual ao teto bit a bit. Também vale para B1 e A1 degradados. Falha estoura.

**Bloco 2 — RMSE por nível** (gravado em `outputs/reconstrucao.csv`). Uma linha
por variante × nível × {sem GK, só GK, todos} × {jogo 1, 2, 3, os três}, com:
- `taxa_visivel`, `frac_imputada`;
- `rmse_imputado` (é o "não detectado") e `rmse_geral`;
- `n_imputadas`, `n_borda` e `n_sem_ancora`;
- a semente.

Ao lado, as faixas do Crang da §2: **B5 contra Cam 1** e **B8 contra PGM**. Os
níveis intermediários não têm alvo publicado.

**Bloco 3 — erro pelo comprimento do buraco.**
- Buraco = corrida contígua de quadros ausentes de um jogador num período.
- Linhas imputadas agrupadas pela duração, em s:
  - faixas `reconstrucao.faixas_buraco_s` = [1, 5, 15, 60], as quatro bordas
    que formam cinco faixas;
  - **descritivo, sem fonte, não decide nada**;
  - borda de período numa categoria à parte.
- Por faixa: n e RMSE, em B5 e B8, sem GK.
- **Critério de aceite:** o RMSE cresce com a faixa. Se não crescer, é achado e
  vai no relatório; não se ajusta nada para que cresça.

**Bloco 4 — sementes.** B8, sem GK, `rep` de 0 a `n_sementes − 1`: o RMSE
imputado e a taxa visível de cada uma, com mínimo e máximo.

**Bloco 5 — velocidade.**
- **Como se calcula a velocidade:**
  - posições filtradas por Butterworth (`simulador.butter_*`), com `filtfilt`
    por segmento contíguo, igual a `broadcast.passos`;
  - velocidade por diferenças centrais (`np.gradient` dentro do segmento);
  - o mesmo cálculo no teto e no reconstruído.
  - Na reconstrução, o segmento é a presença contígua inteira: a reconstrução
    fecha os buracos.
- **5(a) — a ausência depende da velocidade?** Por papel (GK/DEF/MID/OFF,
  `broadcast.papeis`) e por nível B e A:
  - a fração da distância do teto percorrida em linhas visíveis;
  - a fração da distância **em alta velocidade** (> `reconstrucao.limiar_alta_velocidade_ms` = 6,9) percorrida em linhas visíveis;
  - a diferença entre as duas.
  - Distância por linha = `passo_m` de `broadcast.passos` no teto.
  - Ao lado, os alvos do Bassek: TV 14/40/52/46 e 31/49/48/52. A comparação é
    em B8.
- **5(b) — viés da interpolação.** Só nas linhas imputadas, sem GK e por nível:
  - na faixa ≤ 6,9 m/s e na faixa > 6,9 m/s da velocidade **verdadeira**: n, a
    velocidade média verdadeira e a reconstruída, e a razão entre elas;
  - a razão entre a distância reconstruída e a verdadeira;
  - a razão entre a distância em alta velocidade reconstruída e a verdadeira;
  - a mesma tabela em `reconstrucao.n_quantis_velocidade` = 10 quantis da
    velocidade verdadeira, **descritivo, sem fonte**.

**Bloco 6 — distância executor–bola no quadro anotado (diagnóstico para a Fatia 8).**
- **População:**
  - o gabarito principal de passe da Fatia 5 (`completo` × `PASS`);
  - as bolas paradas do gabarito da Fatia 4, por tipo;
  - executor e quadro anotados, como o `src/` já os lê.
- **Por nível B e A:**
  - a fração de executores com a linha **imputada** naquele quadro;
  - a fração **sem linha** (sem âncora);
  - a mediana da distância à bola, no teto e no reconstruído;
  - a fração a ≤ cada `R_pz` da grade congelada (`posse.grade_r_pz_m`, D3).
- Executor sem linha conta como "não está a ≤ R" no denominador. **Nunca sai
  do denominador.**
- **Não muda a grade.** D3 está congelada. O bloco serve para a Fatia 8 ler a
  superfície. Se ele sugerir que a grade é curta, isso é G3 e mudança declarada,
  não ajuste.

**Orçamento:** espero bem menos de 2 h de CPU, porque é 16 pares
`(variante, nível)` × 3 jogos, mais 5 sementes. O codificador mede um
`(jogo, nível)` antes de rodar tudo. Se a estimativa passar de 2 h, ele **para e
reporta**, por causa do G4.

---

## 5. Arquivos

- `src/reconstruct.py`: `reconstruir` e, se precisar, uma função de velocidade.
  O nome do arquivo está em `docs/03-plano.md`, árvore de pastas.
- `src/run.py`: `--reconstrucao` com os blocos 1 a 6. Sem tocar nos outros
  modos.
- `config.yaml`: nova seção `reconstrucao:`, cada chave com a origem:
  - `metodo: linear`;
  - `limiar_alta_velocidade_ms: 6.9` (Bassek p. 4);
  - `faixas_buraco_s` e `n_quantis_velocidade`, descritivos;
  - as faixas do Crang da §2, só para impressão.
- `tests/test_reconstruct.py` (sintético) e `tests/test_reconstrucao_real.py`
  (dados reais, marcado como os outros testes reais).
- `outputs/reconstrucao.csv` e a seção "Fatia 7" de `outputs/origem-dos-numeros.md`.

Dependência nova: nenhuma.

---

## 6. Testes obrigatórios (critério de aceite)

| # | o quê | dado | aceite |
|---|---|---|---|
| T1 | buraco de N quadros numa trajetória de aceleração constante, N ∈ {1, 5, 25, 125}, no meio do segmento | sintético | RMSE **estritamente crescente** em N, e igual ao valor analítico `a·t(N+1−t)/2·Δt²` a 1e-9 |
| T2 | trajetória linear com buraco | sintético | erro ≤ 1e-9: prova que é linear, não constante nem spline |
| T3 | buraco de 0 (`degradado` = teto) | sintético **e** real (3 jogos) | `assert_frame_equal(check_exact=True)` contra o teto, com índice, colunas e dtypes |
| T4 | `visible` sobrevive | sintético, com linhas de entrada já `visible=False` | as linhas de entrada mantêm `x`, `y` e `visible` bit a bit; as imputadas são todas `False`; nenhuma `True` vira `False` |
| T5 | sem vazamento | sintético | `presenca` sem `x`/`y` funciona; com `x`/`y` lixo, a saída é idêntica |
| T6 | bordas | sintético | antes da 1ª e depois da última âncora, posição constante igual à âncora; não atravessa período nem jogo (dois períodos com posições distantes não se misturam) |
| T7 | sem âncora | sintético | as linhas ficam ausentes, `n_sem_ancora` correto, nenhum NaN na saída |
| T8 | NaN na entrada | sintético | estoura |
| T9 | parâmetro ignorado | sintético | mudar `limiar_alta_velocidade_ms` muda a tabela 5(b); mudar `faixas_buraco_s` muda o bloco 3; mudar `simulador.butter_corte_hz` muda a velocidade |
| T10 | erro cresce com o buraco nos dados reais | real, B8 sem GK | o RMSE do bloco 3 é crescente nas 4 faixas internas (borda à parte). **Se falhar, o teste não é afrouxado:** o codificador para e reporta |
| T11 | denominador do bloco 6 | sintético | executor sem linha conta no denominador e não está a ≤ R |
| T12 | semente no manifesto | real | o CSV tem a semente efetiva em toda linha |

**Regras transversais do `docs/03-plano.md`:**
- **4** (abertura infinita reproduz o teto bit a bit): T3 + bloco 1.
- **8** (`visible` nunca sobrescrito): T4.
- **2** e **3** (sem exclusão, sem NaN): T7 e T11.

**Cache:** esta fatia não cacheia. Se o codificador criar cache, o teste de hash
de entrada + configuração passa a ser obrigatório.

---

## 7. Fora

- O detector sobre o tracking reconstruído e o F1 degradado (Fatia 8).
- A segunda estratégia de reconstrução.
- Suavizar a bola (D2: bola perfeita).
- Mexer no simulador e na calibração da Fatia 6.
- Qualquer mudança na grade de `R_pz`.

---

## 8. Relatório do codificador

1. Arquivos tocados e número de testes (antes 483).
2. Saída dos blocos 1 a 6 colada, com o tempo de parede.
3. Toda **[LACUNA]** nova que ele precisou decidir, com a razão. Nenhuma decisão
   de metodologia sem me consultar.
4. O que falhou ou ficou de fora.

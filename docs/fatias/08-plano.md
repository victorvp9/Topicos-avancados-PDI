# Fatia 8 — Experimento e relatório

Plano escrito pelo orquestrador em 2026-11-05. O G2 foi decidido por mim, com
registro (portões delegados em 2026-10-30). **O G4 e o G5 vão ao Victor.**
As lacunas que eu resolvi estão marcadas **[LACUNA]**.

Fonte de verdade:
- `docs/03-plano.md`: Fatia 8 e as regras transversais 1 a 8;
- `docs/00-problema.md`: critério de sucesso;
- `docs/decisoes.md`: D1b, D2, D3, D4, D8, D9b; as dívidas para a Fatia 8 (N4/N5 da Fatia 5; (a)–(d) da Fatia 6; (e)–(h) e a agregação por semente da Fatia 7); as armadilhas de `micro()` (2026-10-30); a âncora calculada uma única vez (2026-10-30); a decomposição por causa em cada ponto (2026-11-02).

> **Esta é a fatia que responde à pergunta do projeto.** Por isso as regras de
> decisão da §2 ficam escritas **antes** de existir qualquer F1 degradado. Até
> hoje nenhum foi medido (`decisoes.md`, 2026-11-04, "Nenhum F1 degradado na
> Fatia 6").

A fatia tem três etapas:
- **8a:** o codificador constrói a máquina e roda o piloto. Termina com a tag `baseline`.
- **G4 + G5 ao Victor:** orçamento, config congelada, tag `pre-rodada-final`.
- **8b:** **uma única rodada** limpa, depois tabelas e figuras. Termina com a tag `final`.

Depois vem o relatório, que eu escrevo em `docs/relatorio.md` citando só
`outputs/`.

---

## 1. Objetivo

Medir o F1 por tipo de evento em função da taxa de detecção amostrada e de
`R_pz`, nas duas variantes do simulador. E responder, com regra escrita antes:
**aumentar `R_pz` compensa a perda de detecção? Para quais eventos?**

---

## 2. Regras de decisão: congeladas neste plano, antes de medir

Tudo que a rodada final produzir **conforme esta seção** é **limpo**. Qualquer
coisa decidida depois de ver a rodada final é **exploratório** e leva o rótulo.

### R1. Condições
- **Principal: `reconstruido`.** Simulador (Fatia 6) → `reconstruir` (Fatia 7)
  → detector. É o que um provedor entrega.
- **Secundária: `bruto`.** Simulador → detector, com as linhas ausentes.
  - **[LACUNA]** É a única condição em que o problema 2 do S1 ("evento imputado
    ao jogador ausente") é exercido. Com a presença do teto, a reconstrução
    nunca deixa jogador ausente (`n_sem_ancora` = 0, Fatia 7).
  - Rodar `bruto` na grade inteira ou reduzida é decisão de orçamento, tomada
    no G4. Não depende de resultado.

### R2. O que se mede em cada ponto
- **Critério principal:** `estrito` (D8), âncora `frame`.
- **Secundários**, sempre gravados como contagens:
  - `vidal_codina` e `mills`;
  - o passe secundário (a união do D10).
- **Alvos primários:**
  - **passe principal**: `completo` × `PASS`, n = 2650 (Fatia 5);
  - **bola parada micro, sem pênalti** (`micro()`).
- **Por tipo**, secundário e de **baixa confiança**: `kickoff` (18), `throw_in`
  (110), `corner_kick` (26), `goal_kick` (49) e `free_kick` (92). Os n vêm de
  `decisoes.md`, 2026-11-01, e cada número leva o seu n ao lado.
- **Pênalti** (n = 1): só a contagem, nunca agregado (guarda existente).

### R3. Grade
- **Variante × nível:** A e B, níveis 1–8 (Fatia 6).
  - O **nível 1 é o teto**: determinístico, sem semente, calculado uma vez por
    `(jogo, R_pz)` e compartilhado pelas duas variantes.
- **Sementes:** `rep` de 0 a `n_sementes − 1`, com `semente_efetiva` da Fatia 6.
  É a mesma degradação em todos os `R_pz` (números aleatórios comuns).
- **`R_pz`:** a grade de D3.
- **`R_dz`:** `acompanha_r_pz` no principal.
  - `fixo_1m` é a decomposição de mecanismo (`decisoes.md`, 2026-10-31). Roda nos
    níveis {1, 5, 8} das duas variantes e só em `R_pz` > 1,00 m; abaixo disso as
    duas políticas são idênticas por construção, e isso vira teste.
- **Lacuna 5:** com e sem, em todos os pontos, como filtro sobre a mesma
  detecção (`decisoes.md`, 2026-10-31).
- **Sensibilidade da âncora** (`annotated_frame`): **uma vez**, só no teto e em
  `R_pz` = 0,50 m, fora da varredura (`decisoes.md`, 2026-10-30).

### R4. Eixo x
- O eixo é a **taxa amostrada** de cada `(jogo, variante, nível, rep)`, não o
  nível nominal (dívida (b) da Fatia 6).
- Taxa = linhas visíveis / linhas presentes, com todos os jogadores. A taxa sem
  GK também é gravada.
- O ponto do nível nas tabelas usa a média das taxas amostradas.

### R5. Agregação
- **Somam-se contagens** (`tp_diag`, `n_detectado`, `n_gabarito`) sobre jogos e
  sementes, **depois** divide-se.
- Nunca se faz média de F1. A exceção é `media_ponderada_f1`, que já existe e
  só é usada onde o Vidal-Codina usa.
- Por jogo, sempre o **mínimo e o máximo** (D4). Sem bootstrap (D4).
- **F1 indefinido fica NaN** e é reportado como NaN, nunca descartado nem
  convertido em 0.

### R6. Escolha de `R_pz` por leave-one-game-out (D4)

Vale para cada `(condição, variante, nível, alvo)` e **inclui o nível 1**, para
saber se `R_pz` maior ajuda até com tracking perfeito. Notação: `R0` = 0,50 m, o
valor do teto (D3, primeiro da grade do artigo, S4.1, p. 6).

Para cada dobra `g` (o jogo fora), com os outros dois jogos como treino `T`:
1. `F1_t(R)` = F1 micro do jogo `t ∈ T`, com as sementes somadas.
   `F1_T(R)` = F1 micro de `T` somado.
2. **Candidatos:** os `R` com **ganho nos dois jogos de treino**,
   `F1_t(R) − F1_t(R0) > 0` para cada `t ∈ T`. Ganho em ≥ k de n, com k = n = 2;
   é o "ganho em ≥ k de n jogos" do briefing, linha 58.
3. `R*_g` = argmax de `F1_T(R)` entre os candidatos.
   - **Empate:** fica o `R` menor, o mais próximo do publicado.
   - **Sem candidato:** `R*_g = R0`.
4. **O jogo `g` nunca entra na escolha.** Reporta-se `F1_g(R*_g)`, `F1_g(R0)` e
   `Δ_g`.

**Resultado por `(condição, variante, nível, alvo)`:**
- `R*_1`, `R*_2` e `R*_3`;
- `Δ_agregado` = F1 dos 3 jogos de teste somados, cada um no seu `R*_g`, menos o
  F1 deles somados em `R0`;
- quantos `Δ_g > 0`.

**Conclusão "aumentar `R_pz` compensa":** só se `Δ_g > 0` em **≥ 2 dos 3 jogos**
**e** `Δ_agregado > 0`. Fora disso, **"não compensa"**, que é resultado
negativo e entra no relatório.

**Fração recuperada** = `Δ_agregado / (F1_teto(R0) − F1_nível(R0))`, reportada
quando o denominador for > 0. Com F1 somado sobre os 3 jogos.

**Exploratório, rotulado:** o `R*` escolhido com os 3 jogos juntos, dentro da
amostra, só para mostrar quanto a escolha dentro da amostra otimiza.

### R7. `ε_c` (D9b(ii), baixa confiança)
- Curva F1 de escanteio e bola parada micro em função de `ε_c`, no teto, em
  `R0`, com `ε_c` ∈ `experimento.grade_eps_c_m` = {2, 3, 4, 5, 6, 8} m.
- **[LACUNA]** A grade é descritiva. Só o 3 é publicado (S4.2, p. 7); o 5 e o 8
  são os que a inspeção mediu (`inspecao-metrica.md` §6.2).
- Reporta-se o jogo 3 (o único não visto) à parte dos jogos 1+2, com contagens
  absolutas e com a frase "8 escanteios de 3 cobradores".
- **Nenhum `ε_c` ótimo é escolhido** (`decisoes.md`, 2026-10-29). O limpo e
  principal continua sendo `ε_c` = 3 m.

### R8. Número de sementes: regra do piloto (dívida (c) da Fatia 6)
- **Piloto:** condição `reconstruido`, A8 e B8, `R0`, `rep` de 0 a 9, 3 jogos.
- Para cada alvo primário: F1 por semente (jogos somados); desvio-padrão `s`
  das 10; `EP5 = s/√5`.
- **Se `EP5` ≤ `experimento.ep_max_f1` = 0,01 nos dois alvos primários e nas
  duas variantes**, ficam 5 sementes. **Senão, 10.** O teto é 10 por custo, e o
  ruído residual fica declarado.
- O escanteio tem `EP5` reportado, mas não decide: com n = 26, é baixa confiança
  de qualquer forma.
- **[LACUNA]** O 0,01 é escolha minha, sem fonte: ruído de semente menor que um
  ponto de F1 no alvo agregado.
- **O piloto é desenvolvimento**, não resultado. A rodada final recalcula as
  mesmas sementes, de forma determinística. Ver o F1 de B8 em `R0` antes da
  rodada final **não altera regra nenhuma**, porque todas estão escritas aqui.

### R9. Decomposições obrigatórias, em cada ponto
- **Bola parada:** contagens por `motivo_reserva1` (`confirmado` /
  `anda_mais_que_eps_f` / `sem_passe_do_executor`). É o confundimento de
  2026-11-02.
- **Passe:** FN por causa (sem perda a ≤ 1 s / suprimido como bola parada /
  desfecho errado), como em `decompor_fn`.
- **FN pelo estado do executor** no quadro anotado: visível, imputado ou ausente
  (dívida (g) da Fatia 7).
- **Diagnóstico (h)** da Fatia 7, uma vez em B8, `rep` 0: a fração de
  distâncias jogador–bola exatamente iguais a um valor da grade de `R_pz`
  depois da reconstrução.

### R10. Declarações obrigatórias no relatório (não são regras, são leituras)
1. **Bola perfeita e estado da bola oráculo** (D2, D1b).
2. **A degradação é correlacionada com os eventos:** os cortes se concentram
   cerca de 13 s depois dos reinícios (dívida (a)).
3. **A calibração dos cortes usou as âncoras de lateral dos 3 jogos,** inclusive
   as de teste: 3 escalares, sem detector (dívida (d)).
4. **A validação 5(a) foi reprovada:** o simulador mostra demais quem corre, logo
   a queda de F1 tende a ser **otimista** (dívida (e)).
5. **Os desvios conhecidos do simulador:** B5 abaixo do Crang; ≥ 9 por time em
   7 % contra 20 %; os resíduos estruturais de −11 e +9,6 pontos.
6. **A interpolação recupera 54 % da distância** (dívida (f)).
7. **A pergunta Bassek × Mortensen e Bornn fica sem resposta sobre o mundo.**

---

## 3. 8a — a máquina (codificador)

### Arquivos
- **`src/experiment.py`** (novo):
  - `rodar_unidade(jogo, variante, nivel, rep, condicao, cfg, base) -> pd.DataFrame`
    - Uma unidade = uma degradação: degrada, reconstrói ou não, e então, para
      cada `R_pz` da grade e cada política aplicável, roda posse → bola parada →
      passes → avaliação.
    - Devolve **contagens**, uma linha por `(R_pz, politica, lacuna5, criterio,
      alvo/tipo)`, com:
      - a taxa amostrada (com e sem GK) e a semente efetiva;
      - as decomposições de R9;
      - o tempo de parede.
    - Reusa `broadcast.degradar`, `reconstruct.reconstruir`,
      `run.com_r_pz`/`possession.calcular`, `detectar_jogos`, `rotular_jogos`,
      `evaluate.avaliar` e `decompor_fn`. **Nada de reimplementar o detector.**
  - `agregar(pontos, por) -> DataFrame`: soma de contagens e depois razão (R5).
    É a **única** porta de agregação, e o bloco de sementes também passa por ela
    (dívida da Fatia 7).
  - `selecionar_logo(pontos, cfg) -> DataFrame` (R6) e `regra_sementes(piloto, cfg)` (R8).
- **`src/evaluate.py`:** guarda em `micro()` e `media_ponderada_f1()` que
  **recusa** entrada com mais de um valor distinto de `criterio`, `ancora` ou
  `game` (`decisoes.md`, 2026-10-30). Quem agrega jogos chama a função por jogo
  e soma contagens, ou usa `agregar`.
- **N4 e N5** (Fatia 5): a variante sem lacuna 5 e o bloco 9 passam a ser
  **funções** chamadas pelo caminho de produção, com os números travados em teste.
- **Cache** em `outputs/cache/`, uma entrada por unidade.
  - Chave: sha256 de (sha256 dos arquivos de `data/` usados + subconjunto
    canônico do config que a unidade lê + sha256 dos `src/**/*.py` + a tupla da
    unidade).
  - A entrada guarda a própria chave. Se ler uma entrada com chave diferente,
    **estoura**.
- **Paralelismo:** `concurrent.futures.ProcessPoolExecutor`, com
  `experimento.n_workers` = 4. **[LACUNA]** São 16 GB de RAM e 6 núcleos; cada
  processo carrega os 3 jogos. O resultado tem de ser idêntico com qualquer
  número de workers.
- **Manifesto** `outputs/experimento/manifesto.json`, com:
  - o commit e se o working tree está sujo;
  - o sha256 do config e dos dados;
  - as versões de Python, numpy, pandas e scipy;
  - por unidade: a semente efetiva, o hit/miss de cache e o tempo.
- **Saídas:**
  - `outputs/experimento/pontos.csv` (todas as contagens);
  - `selecao_logo.csv`;
  - `piloto.csv`;
  - `eps_c.csv`;
  - `ancora.csv`.
- **CLI:**
  - `--piloto` (R8);
  - `--experimento` (grade inteira; lê `n_sementes` e `condicoes` do config);
  - `--tabelas-figuras` (só lê os CSV, nunca recalcula);
  - **`--all`**: todos os modos existentes em ordem, mais `--experimento` e
    `--tabelas-figuras`, do zero (`docs/03`, "Saída").
- **`config.yaml`**, nova seção `experimento:`, cada chave com origem:
  `grade_eps_c_m`, `ep_max_f1`, `n_sementes_piloto` = 10, `n_workers`,
  `condicoes`, `niveis_fixo_1m` = [1, 5, 8] e `r0_m` = 0,50.
- **matplotlib** para as figuras. Entra com `uv add matplotlib`: já está na
  pilha aprovada do `CLAUDE.md`, e eu registro em `decisoes.md`.

### Testes obrigatórios (8a), com o caminho em que o erro aparece

| # | o quê | aceite |
|---|---|---|
| T1 | o nível 1 reproduz o teto, nas duas condições, `R0`, 3 jogos | as contagens são iguais às do `--bola-parada` e do `--passes` aceitos: bola parada tp 232 / n_det 481 / n_gab 295; passe tp 2187 / n_det 2262 / n_gab 2650. Igualdade **exata** |
| T2 | parâmetro varrido e ignorado | em B8, jogo 1, `rep` 0: as contagens diferem entre `R0` e 3,00 m, entre `rep` 0 e 1 e entre B8 e A8; `fixo_1m` difere de `acompanha` acima de 1 m e é **tabela idêntica** abaixo. Mutação: fixar `r_pz` dentro de `rodar_unidade` → falha |
| T3 | não detectado = FN, nunca excluído | `n_gabarito` é constante em todos os pontos para cada `(jogo, tipo, criterio)`, em toda a grade do piloto |
| T4 | NaN | uma unidade sintética sem nenhuma detecção dá P = NaN; `agregar` soma as contagens dela (não descarta) e o F1 agregado sai certo à mão |
| T5 | cache | a mesma unidade dá hit e resultado idêntico; mudar uma chave lida pela unidade (ex.: `eps_c`) dá miss; mudar uma chave não lida dá hit; entrada adulterada → estoura |
| T6 | semente e determinismo | o manifesto tem a semente de toda unidade; `n_workers` = 1 e 2 dão `pontos.csv` idêntico byte a byte |
| T7 | `ball_live` | idêntico ao teto em toda unidade (D1b) |
| T8 | guarda de `micro()` | estoura com dois `criterio`, duas `ancora` ou dois `game`; mutação removendo a guarda → falha |
| T9 | N4 e N5 | as funções produzem os números travados da Fatia 5 (`decisoes.md`, 2026-11-04); o mutante N5 (sem o filtro) e o N4 (executor ignorado) morrem |
| T10 | `selecionar_logo` | tabela sintética com escolha calculada à mão: empate → menor; ganho num só jogo de treino → excluído; sem candidato → `R0`. **Mutação usando o jogo de teste na escolha → falha** |
| T11 | `regra_sementes` | casos sintéticos dos dois lados do 0,01 |
| T12 | `agregar` | soma antes de dividir; mutação "média de F1" → falha |
| T13 | eixo x | a taxa amostrada de B8, `rep` 0, sem GK, é igual à do `outputs/reconstrucao.csv` (0,3766) |
| T14 | `bruto` | unidade B8 de um jogo roda sem erro com linhas ausentes; teste sintético: executor ausente → problema 2 do S1 dispara |

### Fim da 8a
1. `uv run pytest` inteiro passa.
2. O **piloto** roda e aplica R8.
3. O **tempo por unidade** é medido nas duas condições, e o orçamento é estimado
   como unidades × tempo / workers, com e sem cache.
4. Revisão independente.
5. Tag `baseline`.

---

## 4. Portões ao Victor (G4 + G5, juntos)

Levo ao Victor:
- o orçamento medido;
- a decisão `bruto` em grade inteira ou reduzida;
- o lembrete de **pausar o Windows Update e a suspensão**;
- a config congelada.

Com o ok dele: tag `pre-rodada-final` e **uma** rodada de `--all`.

---

## 5. 8b — rodada final, tabelas e figuras

Tudo pré-especificado aqui. Muda só a apresentação, nunca o número.

| saída | conteúdo |
|---|---|
| Tabela 1 | P/R/F1 por tipo × nível (A e B), `R0`, `reconstruido`, estrito, com n, contagens e mín.–máx. por jogo |
| Tabela 2 | leave-one-game-out (R6) por condição × variante × nível × alvo: `R*_g`, F1 de teste em `R*` e em `R0`, `Δ_g`, nº de `Δ_g > 0`, `Δ_agregado`, conclusão e fração recuperada |
| Tabela 3 | decomposições (R9) em `R0` e em `R*`, por nível |
| Tabela 4 | curva de `ε_c` (R7), jogos 1+2 e jogo 3 separados |
| Tabela 5 | secundários: `vidal_codina` e `mills`; `fixo_1m`; sem lacuna 5; âncora; `bruto` |
| Figura 1 | F1 × taxa amostrada, por tipo, `R0`, as duas variantes, um ponto por semente |
| Figura 2 | superfície F1(taxa, `R_pz`) por alvo e variante (mapa de calor) |
| Figura 3 | viés de velocidade (da Fatia 7, `outputs/reconstrucao.csv`) |

Ao fim: `outputs/origem-dos-numeros.md` atualizado e tag `final`. Depois, o meu
`docs/relatorio.md`.

---

## 6. Fora

- A segunda estratégia de reconstrução.
- Bola degradada (D2).
- Recalibrar o simulador.
- Eventos fora do escopo.
- Suavização da bola.
- Qualquer regra nova depois de ver a rodada final; se surgir, entra como
  exploratório.

---

## 7. Relatório do codificador (8a)

1. Arquivos tocados e número de testes (antes: 515).
2. Saída do `--piloto`, com o `EP5` por alvo e variante e a decisão de R8.
3. Tempo por unidade nas duas condições e o orçamento estimado.
4. Toda **[LACUNA]** nova, com a razão. Metodologia nova, só me consultando.
5. Desvios do plano.

---

## 8. Emenda de 2026-11-05: R6 e R7, ANTES de qualquer F1 degradado fora de `R0`

A emenda vem da revisão independente da 8a. Ela vale como **pré-registro**: até
aqui os níveis degradados só foram medidos em `R0` (piloto e T2), e nenhuma
comparação entre valores de `R_pz` degradados foi vista. Fica declarada como
emenda, não escondida.

**R6, nova redação** (substitui a conclusão e a fração recuperada da §2 R6).
O procedimento de escolha do `R*_g` continua o mesmo, com duas correções.

1. **Candidato:** `R` com `F1_t(R) − F1_t(R0) > 0` em **cada** jogo de treino
   **e** `F1_T(R) > F1_T(R0)` no treino somado. A segunda condição é a guarda
   contra Simpson: ganhar nos dois jogos não garante ganhar na soma das
   contagens.
2. **F1 sempre como `2·tp / (n_det + n_gab)`**, uma única divisão de inteiros.
   Assim, F1 iguais em fração saem iguais em ponto flutuante e não há "ganho"
   falso nem empate quebrado por arredondamento. Com denominador 0, o F1 é NaN.
   Um F1 NaN no treino nunca é candidato.
3. **Limiar de relevância:** `λ` = `experimento.ep_max_f1` = 0,01, o mesmo da
   R8: é o ruído de semente aceito. Um ganho menor que `λ` não conta como ganho
   em nenhuma conclusão.
4. **Duas conclusões distintas** por `(condição, variante, nível ≥ 2, alvo)`:
   - **"`R_pz` maior ajuda no nível":** `Δ_g > 0` em ≥ 2 dos 3 jogos de teste
     **e** `Δ_agregado > λ`.
   - **"`R_pz` maior compensa a degradação":** "ajuda" **e**
     `Δ_agregado(nível) − Δ_agregado(nível 1) > λ`. É preciso ganhar mais sob
     degradação do que com tracking perfeito: senão é afinação de `R_pz`, não
     compensação.
5. **Fração recuperada** = `Δ_agregado(nível) / (F1_LOGO(nível 1) − F1_nível(R0))`.
   `F1_LOGO(nível 1)` é o F1 do teto somado nos 3 jogos de teste, cada jogo no
   seu `R*_g`. Isso evita que afinar `R_pz` apareça como recuperação de mais de
   100 %. Só é reportada com denominador > `λ`.
6. **Consolidação: o que responde à pergunta do projeto.**
   - Respondem: os **dois alvos primários**, na condição **`reconstruido`**,
     variante **B**, nos níveis **B5 ("Camera 1") e B8 ("PGM")**. São os únicos
     dois níveis ancorados em alvos publicados (Fatia 6).
   - A resposta é dada **por alvo e por nível**, sem combiná-los: por exemplo,
     "em B8, compensa para bola parada e não para passe".
   - Tudo o mais é **descritivo, secundário**: os níveis intermediários, a
     variante A, `bruto`, os tipos isolados (baixa confiança) e `fixo_1m`.
     Continua limpo, porque está pré-especificado, mas não sustenta a resposta
     principal.
   - Se a conclusão diferir entre B5 e B8, reporta-se as duas, sem escolher.

**R7:** a grade de `ε_c` é a que **já existe** em
`bola_parada.grade_eps_c_m` = [1, 2, 3, 4, 5, 6, 8] (D9b, Fatia 4). A chave
duplicada `experimento.grade_eps_c_m` sai, para não haver duas constantes para
a mesma coisa.

**R8:** o `EP5` é `s/√5` **por definição**, com o 5 numa chave própria
(`experimento.n_ref_ep` = 5). Não depende de `simulador.n_sementes`, que é a
saída da regra.

**Leitura obrigatória no relatório:** em A8, o passe é igual ao teto
(2187 / 2262 / 2650, piloto). A janela centrada na bola nunca tira o passador.

**Esclarecimento de 2026-11-05 (re-revisão da 8a), sem mudança de regra.** O
item 3 ("ganho menor que `λ` não conta") vale para os ganhos **agregados**:
`Δ_agregado > λ` e `Δ_agregado(nível) − Δ_agregado(nível 1) > λ`. A contagem
por jogo de teste segue a letra do item 4, `Δ_g > 0`. O ruído de semente é medido
nos 3 jogos somados (R8), não por jogo, logo aplicar `λ` a cada `Δ_g` usaria o
limiar fora da escala em que ele foi definido. É o que o código e o teste já
fazem.

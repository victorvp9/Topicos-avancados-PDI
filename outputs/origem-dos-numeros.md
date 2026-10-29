# Origem de cada número

Todo número que aparece em `docs/` ou num relatório tem uma linha aqui.
Formato: **número → onde foi conferido**. Sem linha aqui, o número não pode ser
reportado; nesse caso escreva "não conferi".

Rótulo: **[lit]** da literatura; **[dado]** medido nos dados reais; **[prev]**
previsão derivada, ainda não medida por execução do nosso código; **[nosso]**
produzido pelo nosso código.

Nada aqui foi produzido pelo nosso código ainda: o repositório não tem código.
Aberto em 2026-10-29 (G1).

---

## Literatura — Vidal-Codina et al. 2022 (`refs/Automatic event detection in football using tracking data_compressed.pdf`)

| número | onde |
|---|---|
| Savitzky-Golay, 2ª ordem, janela 7 quadros | [lit] §2.3.1, p. 5 |
| 3 min de parede por partida de 90 min, 1 CPU, 4 GB | [lit] §3, p. 9 |
| `R_pz` = 50 cm (A), 100 cm (B e C); `R_dz` = 1 m | [lit] §3, p. 9, e supl. S4.1, p. 6 |
| grade varrida {50, 75, 100, 125, 150} cm | [lit] supl. S4.1, p. 6 |
| faixa 50–150 cm "after discussions with experts at FIFA" | [lit] supl. S4.1, p. 6 |
| provedor A = Track160 (9 jogos), B = Tracab (19), C = Hawk-Eye (3) | [lit] §2.1, p. 3, e supl. S3, p. 5 |
| estado da bola: booleano (Tracab) **ou ausência de dado da bola** (Track160, Hawk-Eye) | [lit] §2.1, p. 3, e §2.3.4, p. 6 |
| gatilhos (só jogadores) e leis IFAB 8, 14, 15, 16, 17 | [lit] §2.3.4, p. 6 |
| padrão = jogador na zona + bola na `R_pz` dele no 1º quadro vivo; mais próximo é o executor | [lit] §2.4.1, p. 7 |
| gatilho completo = ativo de `d1` até `dc` | [lit] §2.4.1, p. 7 |
| hierarquia K → P → C → T → G → F | [lit] Fig. 5, p. 7, e supl. Fig. S1, p. 2 |
| "trigger and pattern zones coincide for corners, throw-ins and goal kicks" | [lit] legenda da Fig. 4, p. 6 |
| erro de digitação `eps_c`/`eps_g` na pequena área | [lit] §2.3.4 p. 6 (texto) vs. Fig. 4 p. 6 (legenda) e supl. S4.2 p. 8 |
| passe = toda perda de posse que não é finalização nem cruzamento | [lit] §2.4.3, p. 9 |
| 4 erros assumidos pelo algoritmo em bola parada | [lit] §2.4.1, p. 8 |
| "supra 90 %" de precisão e revocação em passes; escanteio, lateral, tiro de meta acima de 90 % | [lit] §3.1, p. 9 |
| finalização: precisão 78 vs. revocação 53; 70 % das 254 confusões são finalização bloqueada | [lit] §3.1, p. 9 |
| gabarito tem eventos não anotados, timestamps e jogadores errados | [lit] §3.1, p. 9 |
| critério oficial: jogador anotado **e** ±10 s | [lit] supl. S2, p. 3 |
| reclassificações para passe/finalização (fair play, nutmeg, …) | [lit] supl. S2, p. 3 |
| defasagem média da anotação STS = **1,5 s**; 16 % com \|τ\| > 5 s, 8 % > 7,5 s | [lit] supl. S3, p. 5 |
| distância mínima passador-bola: A 99 % exatamente 0; B 80 % < 50 cm e 99 % < 1 m; C 67 % < 50 cm e 99 % < 1 m | [lit] supl. S3, pp. 5–6 |
| eventos com distância mínima > 1,5 m: 1,8 % / 1,1 % / 2,2 % | [lit] supl. S3, p. 5 |
| `eps_k1` ∈ 3–5 m, `eps_k2` ≥ 2 m; F1 de pontapé inicial cai a 9 %, 82 %, 95 % com `eps_k1` = 0, 0,5, 1 m | [lit] supl. S4.2, p. 7 |
| `eps_c` = 3 m, `eps_t` = `eps_g` = 0,5 m, `eps_f` = 1 m; F1 ponderado 93,4 % | [lit] supl. S4.2, p. 8 |
| `eps_p1` = 2 m, `eps_p2` = 2 m, `eps_p3` = 4 m; 13 pênaltis | [lit] supl. S4.2, p. 8 |
| `eps_theta` = cos 10° (todos); `eps_v` = 5 m/s e `eps_s` = 10 cm (B, C); 1 m/s e 5 cm (A) | [lit] supl. S4.2, p. 8 |
| `eps_f` = deslocamento do jogador antes de passar, no fluxo de erro | [lit] supl. S1, p. 1 |
| hierarquia de reserva: F1 médio de bola parada **85 % → 95 %** | [lit] supl. S1, p. 2 |
| "higher detection rate when favoring complete throw-in over incomplete corner" | [lit] supl. S1, p. 2 |
| `eps_g` acomoda "a goal kick pass from beyond the goal area" | [lit] supl. S4.2, p. 7 |

## Literatura — Mills et al. 2026 (`refs/Automatic event detection in association football using broadcast-derived tracking data_compressed.pdf`)

| número | onde |
|---|---|
| 3 entradas: x,y,z da bola + x,y dos jogadores + estado vivo/morto quadro a quadro | [lit] §2.2, p. 4 |
| Provedor 1 usou o próprio estado; 2 e 3 usaram o do multicâmera | [lit] §2.2, p. 4 |
| escanteio: jogador e bola na mesma PZ e ambos a **≤ 3 m** de um canto | [lit] §2.2, p. 4 |
| PZ específica de bola parada, com outro conjunto de hiperparâmetros | [lit] §2.2, p. 4 |
| critério: mesmo tipo dentro de **3 s** | [lit] §2.2, p. 4 |
| contagens DCU: 4 pontapés iniciais, 18 tiros de meta, 28 tiros livres, 5 escanteios, 31 laterais, 984 passes/cruzamentos, 27 finalizações, 2 gols, 3 defesas | [lit] §2.2, p. 4 |
| multicâmera ~0,15 m de posição e ~0,15 m/s de velocidade | [lit] Introdução, p. 1 (citando FIFA 2024) |
| TRACAB Gen 5: RMSE 0,08 m (posição), MAE 0,07 m (bola) | [lit] §2.1, p. 3 |
| RMSE geral da bola 3,5 a 16,2 m | [lit] Tabela 1, p. 5, e Discussão, p. 7 |
| escanteio 1,00; pontapé inicial 1,00; tiro de meta 0,94 → 0,97; tiro livre 0,93 → 0,85+; lateral 0,97 → 0,87; passe 0,93 → ≥ 0,90; finalização 0,48 → 0,24; defesa 0,67 → 0,00 | [lit] Resultados, pp. 6–7 |
| PGM: tiro de meta 0,62, tiro livre 0,57, lateral 0,60 | [lit] Resultados, p. 7 |
| média de passes/cruzamentos: 0,81 (Camera 1), 0,78 (PGM), 0,69 (Tactical); máximos 0,93 / 0,91 / 0,90 | [lit] Resultados, p. 7 |
| "best-case … within 0.05 F1-score" vale "for most events" | [lit] Resumo, p. 1, e Discussão, p. 8 |
| pontapé inicial confundido com tiro livre por erro de posição da bola; lateral vs. tiro livre perto da lateral | [lit] §4.2, p. 8 |

## Literatura — Crang et al. 2026 (`refs/Concurrent validity ..._compressed.pdf`)

| número | onde |
|---|---|
| detecção: tático 89–96 %, Camera 1 56–64 %, PGM 36–42 % | [lit] Tabela 1, p. 5 |
| RMSE de posição geral 1,68 a 16,39 m | [lit] Resumo p. 1, Tabela 2 p. 6 |
| RMSE de posição: detectado 0,44–16,24 m; não detectado 4,58–19,38 m | [lit] Tabela 2, p. 6 |
| RMSE de velocidade 0,34 a 2,38 m/s | [lit] Resumo p. 1, Tabela 3 p. 9 |
| viés de distância total −1745 m (−21,8 %) a +1945 m (+24,3 %) | [lit] Resumo p. 1, Tabela 4 p. 10 |
| erro < 1 m: PGM 24,1–69,3 %; Camera 1 60,5–63,7 %; tático 82,6–93,7 % | [lit] Discussão, p. 10 |
| melhor imputador: Provedor 1 com 4,6 m no PGM, contra 10,0–11,6 m | [lit] Discussão, pp. 10–11 |
| TRACAB Gen 5 vs. captura 3D: 0,08 m e 0,08 m/s | [lit] Métodos, p. 3 |
| goleiros excluídos; 27 jogadores; tempos de 48 e 50 min | [lit] Métodos, p. 3 |

## Literatura — Bassek et al. 2025 (`refs/Broadcast analytics.pdf`)

| número | onde |
|---|---|
| TV: 0 jogadores visíveis em **38 %** dos frames | [lit] Resultados, p. 6 |
| TV: 0 jogadores visíveis em **41 %** — **divergência interna do artigo** | [lit] Discussão, p. 8 |
| TV: moda ~7 jogadores (9 %); ≥ 9 por time só 20 % do tempo; 11 juntos 3 % | [lit] pp. 6 e 8 |
| SF: 9 (7 %), 10 (58 %), 11 (32 %) → ≥ 9 em 97 % do tempo | [lit] Resultados, p. 6 |
| 56 % do tempo ativo, 44 % parado | [lit] Resultados, p. 6 |
| TV com 0 visíveis: 21 % ativo, 79 % parado | [lit] Resultados, p. 6 |
| **981 cortes por partida, 10,9 por minuto** | [lit] Discussão, p. 8 |
| distância visível em TV: GK 14 %, DEF 40 %, MID 52 %, OFF 46 % | [lit] Tabela 1 e Resultados, p. 6 |
| distância visível em SF: GK 25 %, linha ~80 % | [lit] Resultados, p. 6 |
| alta intensidade visível em TV: GK 31 %, DEF 49 %, MID 48 %, OFF 52 % | [lit] Resultados, p. 6 |
| formação, top-1/3/5: GT 31,3/60,9/75,2; SF 31,3/60,6/74,0; TV 26,4/52,0/66,7 | [lit] Tabela 2, p. 7 |
| jogadores de linha igualmente ativos dentro e fora do quadro | [lit] Discussão, p. 8 |
| crítica à janela de 40×40 m de Mortensen e Bornn | [lit] Introdução, p. 3 |
| suplementar = "preprocessed intermediate data", **não** séries de visibilidade | [lit] Data and code availability, p. 10 |
| 4 partidas, uma liga, TRACAB Gen4; Butterworth 3ª ordem 1 Hz; Savitzky-Golay janela 31, 3ª ordem na homografia; buracos ≤ 25 quadros interpolados | [lit] Métodos, pp. 3–4 |

## Literatura — FOOTPASS 2026 (`refs/FOOTPASS_..._compressed.pdf`)

| número | onde |
|---|---|
| **46,8 % dos laterais caem em segmento de replay** | [lit] §3.2, p. 6 |
| cobertura de caixa do jogador ativo: média 81,5 %; **lateral 43,8 %**, tackle 62,1 %, cabeceio 66,7 %, cruzamento 70,7 %, bloqueio 78,4 %, passe 81,5 %, finalização 81,6 %, condução 85,7 % | [lit] §3.2, p. 6 |
| ao vivo: cabeceio 95,4 %, bloqueio 95 %, finalização 99,5 % | [lit] §3.2, p. 6 |
| tolerância de casamento ±12 quadros (0,48 s), mesmo jogador e classe | [lit] §4.1, p. 6 |
| 54 partidas, 102 992 eventos, 8 classes | [lit] Tabela 1, p. 3, e §4.1, p. 6 |
| 17 % dos EPTS certificados pela FIFA são de broadcast | [lit] §1.2, p. 2 (citando FIFA 2026) |
| dataset alternativo: Bassek et al. 2025, 7 partidas da Bundesliga com GT multicâmera + eventos — **licença e disponibilidade não conferidas** | [lit] §2.1, p. 4 |

## Dados — Metrica (`docs/inspecao-metrica.md`)

Todos medidos em 2026-10-29 sobre o commit
`e706dd506b360d69d9d123d5b8026e7294b13996`. Os sha256 de cada arquivo estão em
`docs/inspecao-metrica.md` §1.

| número | onde |
|---|---|
| 25 Hz exatos; `max │Time − Frame/25│ = 0`; sem buraco de quadro | [dado] §2 |
| sem z da bola, sem booleano vivo/morto | [dado] §2 |
| 22 jogadores com dado em todos os quadros nos 3 jogos | [dado] §2.1 e §4 |
| coordenadas fora de [0,1]; jogadores recortados em ±0,05 | [dado] §2.2 |
| bola fora de [0,1] em 1,671 % / 0,390 % dos quadros | [dado] §2.2 |
| sentido de ataque por jogo e por período (x médio do goleiro) | [dado] §2.3 |
| bola NaN em 39,14 % / 41,01 % / 32,22 % | [dado] §2.4 e §4 |
| 155 / 169 sequências de NaN; mediana 7,84 / 5,08 s; máx. 131,68 / 129,80 s | [dado] §2.4 |
| contagens por `Type` dos 3 jogos | [dado] §3.1 |
| `SET PIECE` por subtipo; **26 escanteios nos 3 jogos** | [dado] §3.2 |
| `GOAL KICK` em 3 `Type`; total 22 / 16 / 11 | [dado] §3.3 |
| `SET PIECE` sempre seguido do mesmo jogador, Δquadro mediano 0 (157 de 157) | [dado] §3.4 |
| `Start X`/`Start Y` NaN em 0 de 77 e 0 de 80 `SET PIECE` | [dado] §3 |
| `THEFT` = 21 / 38; união `PASS`∪`BALL LOST`∪`BALL OUT` = 1107 / 1246 | [dado] §3.5 |
| 0 de 799 e 0 de 964 `PASS` em quadro com bola NaN | [dado] §5.2 |
| 32 de 1935 eventos do jogo 2 dentro de NaN, todos de bola morta | [dado] §5.2 |
| fração de NaN nos 2 s antes de bola parada: 0,93 a 1,00 | [dado] §5.2 |
| **escanteio: 10/18 = 56 % com `eps_c` = 3 m; 83 % a 5 m; 94 % a 8 m** | [dado] §6.2 |
| lateral: 55/60 = 92 % com `eps_t` = 0,5 m; 98 % a 1 m | [dado] §6.2 |
| tiro de meta: 34/38 = 89 % com `eps_g` = 0,5 m | [dado] §6.2 |
| pontapé inicial: 12/13 = 92 %; o do quadro 1 do jogo 1 é indetectável | [dado] §6.2 |
| padrão (bola na PZ do executor): `d` = 0,00 m, satisfeito em 88–100 % | [dado] §6.2 |
| distância jogador anotado-bola no passe: < 0,5 m em 96,7 % e 97,4 %, mediana 0,08–0,09 m | [dado] §6.4 |
| jogo 3 legível sem `kloppy`: 11 `DataFormatSpecification`, 44 `PlayerChannelRef` | [dado] §4 |

## Previsões ainda não medidas por execução

| número | base |
|---|---|
| teto de revocação de passe ~97 % com `R_pz` = 0,50 m e ~98 % com 1,00 m | [prev] distribuição de `docs/inspecao-metrica.md` §6.4; **não** vem de rodar o detector |
| teto de revocação de bola parada: lateral 92 %, pontapé inicial 92 %, tiro de meta 89 %, escanteio 56 % | [prev] geometria dos gatilhos, §6.2; não inclui posse, hierarquia nem hierarquia de reserva |
| ~96 h de CPU para a grade de exemplo (1920 execuções × 3 min) | [prev] 3 min/partida do artigo (§3, p. 9) extrapolado; **medir uma execução real antes do G4** |

# Origem de cada número

Todo número que aparece em `docs/` ou num relatório tem uma linha aqui.
Formato: **número → onde foi conferido**. Sem linha aqui, o número não pode ser
reportado; nesse caso escreva "não conferi".

Rótulo: **[lit]** da literatura; **[dado]** medido nos dados reais; **[prev]**
previsão derivada, ainda não medida por execução do nosso código; **[nosso]**
produzido pelo nosso código.

Aberto em 2026-10-29 (G1). Os primeiros números **[nosso]** entraram na Fatia 1 e
estão marcados como tal; tudo que vier do nosso código só é promovido depois de
revisão independente.

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
| distância visível em TV: GK 14 %, DEF 40 %, MID 52 %, OFF 46 % | [lit] ~~Tabela 1 e Resultados, p. 6~~ **texto de Resultados, p. 6** (a Tabela 1 fica na p. 7 e a razão das médias dela dá 13,9 / 36,6 / 46,2 / 42,1 %; mesma correção de `docs/02-dados.md`) [corrigido 2026-11-04, auditoria pós-Fatia 6] |
| distância visível em SF: GK 25 %, linha ~80 % | [lit] Resultados, p. 6 |
| alta intensidade visível em TV: GK 31 %, DEF 49 %, MID 48 %, OFF 52 % | [lit] Resultados, p. 6 |
| formação, top-1/3/5: GT 31,3/60,9/75,2; SF 31,3/60,6/74,0; TV 26,4/52,0/66,7 | [lit] Tabela 2, ~~p. 7~~ **p. 8** (página do PDF; no Bassek a impressa é a do PDF − 1) [corrigido 2026-11-04, auditoria pós-Fatia 6] |
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
| tolerância de casamento ±12 quadros (0,48 s), mesmo jogador e classe | [lit] §4.1, ~~p. 6~~ **p. 7** [corrigido 2026-11-04, auditoria pós-Fatia 6] |
| 54 partidas, 102 992 eventos, 8 classes | [lit] Tabela 1, p. 3, e §4.1, p. 6 |
| 17 % dos EPTS certificados pela FIFA são de broadcast | [lit] §1.2, p. 2 (citando FIFA 2026) |
| dataset alternativo: Bassek et al. 2025, 7 partidas da Bundesliga com GT multicâmera + eventos — **licença e disponibilidade não conferidas** | [lit] §2.1, p. 4 |

## Dados — Metrica (`docs/inspecao-metrica.md`)

Todos medidos em 2026-10-29 sobre o commit
`e706dd506b360d69d9d123d5b8026e7294b13996`. Os sha256 de cada arquivo estão em
`docs/inspecao-metrica.md` §1.

| número | onde |
|---|---|
| 25 Hz exatos; `max │Time − Frame/25│ = 0`; sem buraco de quadro | [dado] §2 — **consistência de unidade apenas. Não usar como evidência de acurácia do instante anotado** (ver §6.5) |
| sem z da bola, sem booleano vivo/morto | [dado] §2 |
| 22 jogadores com dado em todos os quadros nos 3 jogos | [dado] §2.1 e §4 |
| coordenadas fora de [0,1]; jogadores recortados em ±0,05 | [dado] §2.2 |
| bola fora de [0,1] em 1,671 % / 0,390 % dos quadros | [dado] §2.2 |
| sentido de ataque por jogo e por período (x médio do goleiro) | [dado] §2.3 |
| bola NaN em 39,14 % / 41,01 % / 32,22 % | [dado] §2.4 e §4 |
| 155 / 169 sequências de NaN; mediana 7,84 / 5,08 s; máx. 131,68 / 129,80 s | [dado] §2.4 |
| contagens por `Type` dos 3 jogos | [dado] §3.1 |
| `SET PIECE` por subtipo nos 3 jogos: lateral 110, tiro livre 92, **escanteio 26**, pontapé inicial 18, pênalti 1 | [dado] §3.2 |
| jogo 3: 90 bolas paradas = 50 laterais, 28 tiros livres, **8 escanteios**, 4 pontapés iniciais | [dado] §3.2 |
| os 8 escanteios do jogo 3 são de **3 cobradores**, 6 de um só time | [dado] §3.2 |
| `GOAL KICK` em 3 `Type`; total 22 / 16 / 11 | [dado] §3.3 |
| `SET PIECE` sempre seguido do mesmo jogador, Δquadro mediano 0 (157 de 157) | [dado] §3.4 |
| `Start X`/`Start Y` NaN em ~~0 de 77 e 0 de 80~~ **77 de 77 e 80 de 80** linhas `SET PIECE` (zero não nulos) [corrigido 2026-11-04, auditoria pós-Fatia 6] | [dado] §3 |
| `THEFT` = 21 / 38; união `PASS`∪`BALL LOST`∪`BALL OUT` = 1107 / 1246 | [dado] §3.5 |
| 0 de 799 e 0 de 964 `PASS` em quadro com bola NaN | [dado] §5.2 |
| 32 de 1935 eventos do jogo 2 dentro de NaN, todos de bola morta | [dado] §5.2 |
| fração de NaN nos 2 s antes de bola parada: 0,93 a 1,00 **sem tiro de meta**; `PASS/GOAL KICK` 0,62 a 0,92 [corrigido 2026-11-04, auditoria pós-Fatia 6] | [dado] §5.2 |
| **escanteio: 10/18 = 56 % com `eps_c` = 3 m; 83 % a 5 m; 94 % a 8 m** | [dado] §6.2 |
| lateral: 55/60 = 92 % com `eps_t` = 0,5 m; 98 % a 1 m | [dado] §6.2 |
| tiro de meta: ~~34/38 = 89 %~~ **33/38 = 86,8 %** com `eps_g` = 0,5 m (nota "ERRO MEU, corrigido em 2026-11-01", split autoritativo) [corrigido 2026-11-04, auditoria pós-Fatia 6] | [dado] §6.2 |
| pontapé inicial: 12/13 = 92 %; o do quadro 1 do jogo 1 é indetectável; ~~n = 13~~ **n = 14 contando `KICK OFF-RETAKEN` (8 no jogo 2); a fração com n = 14 não foi remedida** [corrigido 2026-11-04, auditoria pós-Fatia 6] | [dado] §6.2 |
| padrão (bola na PZ do executor): `d` = 0,00 m, satisfeito em 88–100 % | [dado] §6.2 |
| distância jogador anotado-bola no passe: < 0,5 m em 96,7 % e 97,4 %, mediana 0,08–0,09 m | [dado] §6.4 |
| jogo 3 legível sem `kloppy`: 11 `DataFormatSpecification`, 44 `PlayerChannelRef` | [dado] §4 |

## Previsões ainda não medidas por execução

| número | base |
|---|---|
| ~~teto de revocação de passe ~97 % com `R_pz` = 0,50 m e ~98 % com 1,00 m~~ | **OBSOLETO** (plano 05 §2.2; `decisoes.md` 2026-11-04): substituído por `tp_diag` estrito ≤ 2353 (R ≤ 0,888), seção Fatia 3 |
| teto de revocação de bola parada: lateral 92 %, pontapé inicial 92 % (**n = 14 com `KICK OFF-RETAKEN`, fração não remedida**), tiro de meta ~~89 %~~ **86,8 % (33/38)**, escanteio 56 % [corrigido 2026-11-04, auditoria pós-Fatia 6] | [prev] geometria dos gatilhos, §6.2; não inclui posse, hierarquia nem hierarquia de reserva |
| ~96 h de CPU para a grade de exemplo (1920 execuções × 3 min) | [prev] 3 min/partida do artigo (§3, p. 9) extrapolado; **medir uma execução real antes do G4** |

## Dados — medidos na Fatia 1 (2026-10-29)

Medidos por script efêmero independente do código do projeto, sobre o dado cru.

| número | onde |
|---|---|
| ancoragem: **12 de 296** bolas paradas saltam > 10 s para trás | [dado] G3, `docs/decisoes.md` |
| por tipo: tiro de meta **9 de 49 (18,4 %)**, tiro livre 3 de 92, escanteio/lateral/pontapé inicial **0** | [dado] G3 |
| maior salto: 4242 quadros = 169,7 s (tiro livre, jogo 1, 42476 → 38234) | [dado] G3 |
| colisões de âncora: j1 125558 e 125622 → 124787; j2 56958 → 54472 (quadro de um pontapé inicial) | [dado] G3 |
| 3 s e 10 s de guarda dão o **mesmo** conjunto de 12 eventos; 1 s cortaria o caso bom 77582 | [dado] G3 |
| j1 quadro 77582: bola a **49,55 m** da linha de fundo própria; executor a **5,45 m** no quadro anotado e **4,52 m** no 1º quadro vivo (77510, shift −72) | [dado] `docs/inspecao-metrica.md` §6.3, **corrigido** |
| j1 quadro 125622: executor a **11,29 m** da linha de fundo própria no quadro anotado; bola em x = +15,65 m | [dado] §6.3 |
| jogo 3 tem `position_type = Goalkeeper` no XML (2 ocorrências) | [dado] `Sample_Game_3_metadata.xml` |
| margem mínima do `attack_dir` pela média do time: **2,24 m** (j3, P2, home) contra ~40 m pelo goleiro | [dado] relatório da Fatia 1 |
| jogo 3 **não** tem recorte em ±0,05: `max\|y\|` = **39,2952 m** (vs 37,4000 nos jogos 1 e 2) | [dado] relatório da Fatia 1 |
| `pass_secundario` **cru** (descritivo): 1086 / 1208 / 1447 (= 1107 − 21 e 1246 − 38); com `GOAL KICK` excluído daria 1064 / 1192 | [dado] §3.5 + Fatia 1 |
| `pass_secundario` na tabela `events` (**denominador normativo de avaliação**): 1009 / 1131 / 1358 | [dado] revisão da Fatia 1 |
| tetos de gatilho são **idênticos** nas duas âncoras: tiro de meta ~~33/38 (`eps_g`=0) e 34/38 (0,5)~~ **32/38 e 33/38** (números antigos são do bug do `abs()`; split correto em `docs/inspecao-metrica.md` §6.2) [corrigido 2026-11-04, auditoria pós-Fatia 6]; lateral 27 e 28; escanteio 6 e 4 | [dado] revisão da Fatia 1 |
| `refs/events-definitions.pdf` == `data/.../documentation/`: sha256 `5afb1ee3…` | [dado] revisão da Fatia 1 |
| margem do `attack_dir`: goleiro ~~39,1 a 42,6 m~~ **39,06 a 46,36 m** com o jogo 3 (a faixa antiga só cobria os jogos 1 e 2; `\|gk_mean_x\|` de `carregar_jogo`) [corrigido 2026-11-04, auditoria pós-Fatia 6]; média do time 2,24 a 11,11 m | [dado] revisão da Fatia 1 |
| fusão `SET PIECE` + execução: **247 de 247** nos 3 jogos | [dado] Fatia 1 |
| ancorar pelo quadro do rótulo daria `anchor_shift` positivo em 12 de 77 e 9 de 80 | [dado] Fatia 1 |

**[nosso]** — primeiros números produzidos pelo código do projeto. Pendentes de
revisão independente; serão recalculados após a guarda de 10 s.

| número | onde |
|---|---|
| sha256 de `ball_live`: j1 `437927c2…`, j2 `98263d3f…`, j3 `2b43ba7f…` | [nosso] `docs/decisoes.md` |
| linhas de `tracking`: 3190138 / 3105436 / 3162742 | [nosso] `src.run --inspect` |
| eventos no gabarito: 1668 / 1855 / 3530 (linhas cruas 1745 / 1935 / 3620) | [nosso] `src.run --inspect` |


## Dados — medidos na Fatia 2 (2026-10-30)

Produzidos por `src/tau.py` e `src/evaluate.py`, e **todos reproduzidos
independentemente pelo revisor** com script próprio.

| número | onde |
|---|---|
| passes medidos: 722 / 889 / 1039 = **2650** | [nosso] `src.run --tau` |
| `|τ| > 1 s` = **45,36 %** (1202/2650); por jogo 46,95 / 46,57 / 43,21 % | [nosso] `--tau`, confirmado pelo revisor (45,3585 %) |
| média de `τ` = **+0,699 s**; mediana **+0,120 s** | [nosso] confirmado (+0,698943) |
| `|τ| > 3 s` 22,11 % · `> 5 s` **13,02 %** · `> 7,5 s` 6,26 % | [nosso] confirmado |
| `d_min < 0,5 m` 97,92 % · `< 1 m` 98,49 % · `< 1,5 m` 98,68 % | [nosso] `--tau` |
| **gatilho de G3 disparou**: 45,36 % contra limiar de 5 % | [nosso] decisão em `docs/decisoes.md` |
| sanidade §6.4, linhas cruas `PASS`: j1 n=799 **96,75 %** med 0,0840 m; j2 n=964 **97,41 %** med 0,0884 m | [nosso] confirmado (96,7459 / 97,4066) |
| passes do **gabarito**: j1 96,40 % · j2 97,19 % · j3 89,61 % | [nosso] confirmado |
| **jogo 3, linhas cruas `PASS`: n=1121, `d < 0,5 m` em 90,01 %, mediana 0,0648 m** — anotação mais frouxa, não estava na inspeção | [nosso] confirmado pelo revisor (90,0089 %) |
| filtrar os 13 `no_dead_ball_before`: **+2,2530 pontos no F1 micro** de bola parada (0,977470 → 1,0) e **+2,371 em média ponderada** | [nosso] confirmado; as duas agregações nomeadas |
| filtrar os 13: **revocação de `goal_kick` 0,816327 → 1,0 = +18,367 pontos** | [nosso] confirmado |
| os 13 são 9 `goal_kick` + 3 `free_kick` + 1 `kickoff` | [nosso] confirmado |
| sensibilidade da âncora: única célula diferente é `goal_kick` no estrito, **49 contra 48** | [nosso] confirmado; só 4 eventos têm `anchor_shift` ≠ 0, só 1 passa de 1 s |
| casamento ótimo: 0 divergências contra força bruta em 300 casos aleatórios | [nosso] medido pelo revisor |
| decomposição de `τ` (jogos 1+2, linhas cruas `PASS`): dos ~43 % com `|τ| > 1 s`, a maior parte persiste **dentro** de um único episódio de contato | [dado] orquestrador 30,26/12,31 pp (n=1738); revisor 26,32/16,00 pp (n=1763), operacionalizações diferentes, **mesma conclusão** |
| quadro anotado fora de qualquer contato `d < 0,5 m`: 2,93 % (orquestrador) / 0,85 % (revisor) | [dado] operacionalizações diferentes |

**Números que NÃO devem ser reportados como resultado:** as frações de `|τ|` são
válidas como réplica do S3 (mesmo estimador), mas **não** como porteiro da janela
de ±1 s — a grandeza é inválida para isso neste dataset. Ver `docs/decisoes.md`.

## Fatia 3 — Passo 1 e `τ_posse` (2026-10-30 a 2026-11-04)

Todos `R_pz` = 0,50 m, `R_dz` = 1,00 m, política `acompanha_r_pz`, salvo
indicação. "Bloco" = cabeçalho de `docs/decisoes.md`. Conferido em 2026-11-04
rodando o comando indicado com o código atual; onde o registro e o comando
divergem, a linha diz e a divergência vai para a lista no fim da seção.

| número | onde | comando |
|---|---|---|
| perdas 1017 / 1120 / 1322 | [nosso] "Fatia 3 fechada", 2026-10-31 (era 1011/1110/1311 antes da correção da sequência) | `--posse` |
| ganhos 1127 / 1278 / 1635 (0,50 m); 1200 / 1354 / 1583 (3,00 m) | [nosso] "Revisão da Fatia 3" e "Correção 3", 2026-10-31 | `--posse` |
| jogo 1, 3,00 m: perdas 729 (`acompanha`) contra 791 (`fixo_1m`) | [nosso] "Fatia 3 fechada", 2026-10-31 | `--posse` |
| empates exatos de distância: 112 / 110 / 32 quadros | [nosso] "Fatia 3 — achados", 2026-10-30 | `--posse` |
| passes 2650; **220 sem perda (8,30 %)**, por jogo 44 / 73 / 103 | [nosso] "Fatia 3 fechada", 2026-10-31, e "Fatia 5 — plano", 2026-11-04 | `--tau-posse` |
| **2430 com perda** (678 / 816 / 936); **3,17 %** acima de 1,0 s | [nosso] idem; `docs/01-definicoes.md` corrigido em 2026-11-04 | `--tau-posse` |
| **2353** com perda a `\|τ_posse\|` ≤ 1,0 s (662 / 799 / 892) | [nosso] "Fatia 5 — plano", 2026-11-04 | `--tau-posse` (= com perda × (1 − fração > 1 s), por jogo) |
| mediana de `τ_posse` −0,040 s (um quadro); p95 de `\|τ_posse\|` 0,16 s | [nosso] "DECISAO DO PORTAO", 2026-10-30, mantida em "Fatia 3 fechada" | `--tau-posse` |
| escada {1,0; 1,5; 2,0; 3,0} s → janela **1,0 s** | [nosso] "DECISAO DO PORTAO", 2026-10-30 | `--tau-posse` |
| `R_pz` 1,00 m: 6,87 % sem perda, 2,71 % > 1 s | [nosso] "AMEACA A VALIDADE", 2026-10-31 | `--tau-posse` (sensibilidade) |
| `R_pz` 2,50 m: 25,13 % sem perda, 9,93 % > 1 s, 7,61 % > 3 s (escada esgotada) | [nosso] idem | `--tau-posse` |
| `R_pz` 3,00 m: 32,87 % sem perda, 12,65 % > 1 s, 10,23 % > 3 s (escada esgotada) | [nosso] idem | `--tau-posse` |
| deriva: mediana de `τ_posse` −0,040 s (0,50 m) → −0,280 s (3,00 m) | [nosso] "Correção 2", 2026-10-31, medido pelo revisor | **nenhum comando imprime a de 3,00 m** |
| cauda > 1 s com `τ < 0`: 53 % → 48 % | [nosso] "Correção 2", 2026-10-31, revisor | **sem comando no repositório** |
| bloqueios pela condição 2: 224 → 25; quadros com condição 1: 3553 → 2162 (−39 %) | [nosso] "Correção 1", 2026-10-31, revisor | **sem comando no repositório** |
| lacuna 5 a 3,00 m: 263 perdas; `free_kick` 46 % dos 130 a 0,50 m (21/41, 24/54, 15/35), 33 % dos 263 a 3,00 m | [nosso] "Fatia 3 — itens menores", 2026-10-31 | `--posse` (bloco "PESO DA LACUNA 5") |
| trocas de dono por duelo a 3,00 m: 62 a 65 % dos duelos com 2+ donos | [nosso] "Revisão da Fatia 3", itens menores, 2026-10-31 | `--bola-parada` bloco 7 (61,6 / 63,2 / 65,1 %) |
| parede: `calcular` 0,31–0,38 s; célula 0,85–1,15 s; I/O 64,2 %; grade 30,8 min sem cache e 11,0 com | [nosso] "Revisão da Fatia 3", 2026-10-31 | `--posse` (tempo varia com a máquina; hoje 0,37–0,49 e 0,98–1,28 s) |
| ganhos com quebra de sequência (leitura errada): +23,0 / +28,2 / +31,7 % a 3,00 m | [nosso] "Correção 3", 2026-10-31 | **sem comando** (o código não tem mais a leitura errada) |
| leitura A do duelo: 1754 / 1981 / 2254 ganhos a 3 m, 90 a 115 quadros com ganho duplo | [nosso] "Fatia 3 fechada", 2026-10-31 | **sem comando** (contrafactual descartado) |
| 319 testes | [nosso] "Fatia 3 ACEITA", 2026-10-31 | `uv run pytest` no commit da Fatia 3 |

**Divergências da Fatia 3** (registro × comando atual, ou dois registros):

1. `τ_posse`: **237 sem perda (8,94 %), 2413 com perda, 3,27 % > 1 s** ("DECISAO
   DO PORTAO", 2026-10-30; "Fatia 3: tau_posse confirmada", 2026-10-31) contra
   **220 (8,30 %), 2430, 3,17 %** ("Fatia 3 fechada", 2026-10-31; "Fatia 5 —
   plano", 2026-11-04). Vale o segundo; o comando dá o segundo.
2. `R_pz` 1,00 m: 3,06 % > 1 s (2026-10-30) contra 2,71 % (2026-10-31). Vale 2,71 %.
3. Decomposição dos sem perda: registrada **125 PZ + 112 regra = 237** (19/33/73 e
   29/45/38, "DECISAO DE DESENHO", 2026-10-31), **anterior** à correção da
   sequência. O comando atual dá **112 + 108 = 220** (17/29/66 e 27/44/37).
   **Nenhum registro em `decisoes.md` com os números pós-correção.**
4. `perdas_termina_corrida` registrado 151 / 156 / 153 (2026-10-30); o comando
   dá **152 / 159 / 154**. Sem registro posterior.
5. `so_por_lacuna_5` registrado 41 / 52 / 38 (2026-10-30); o comando dá **41 /
   54 / 35** — que é o que o bloco "itens menores" de 2026-10-31 já usa
   (21/41, 24/54, 15/35). Dois valores em `decisoes.md`.
6. Lacuna 5 a 3,00 m: **80 / 104 / 87** ("Revisão da Fatia 3", 2026-10-31) contra
   **263** = 80 / 100 / 83 ("itens menores", mesmo dia; e o comando). Vale 263.
7. Corridas vivas sem posse: registrado 4 / 12 / 6 (2026-10-30); o comando dá
   **3 / 9 / 5**. Sem registro posterior.
8. Quadros falso-positivos do §2.3.3: registrado 647 / 676 / 721 (2026-10-30); o
   comando dá **527 / 433 / 597**. Sem registro posterior.
9. Trocas de dono por duelo a 0,50 m: registrado 0,27 a 0,46 por duelo e 21 a
   28 % com 2+ donos (2026-10-31); `--bola-parada` bloco 7 dá **0,25 a 0,44** e
   **20,9 a 28,2 %**. Sem registro posterior.

Itens 4, 5 (primeira parte), 7, 8 e 9 parecem ser números de antes da correção
da sequência (2026-10-31) que nunca foram reescritos — mesma classe do 3,27 %.

## Fatia 4 — bolas paradas (2026-11-01 a 2026-11-04)

Padrão `goal_kick_no_problema_3: depois_de_cto` (desde 2026-11-02), critério
estrito, âncora `frame`, 3 jogos, micro sem pênalti, salvo indicação.

| número | onde | comando |
|---|---|---|
| 481 detecções (154 / 168 / 159) contra 296 reinícios (99 / 96 / 101) | [dado] "Fatia 4 — plano", 2026-11-01 | `--bola-parada` bloco 1 |
| ~~teto de precisão 61,5 % (64,3 / 57,1 / 63,5 %)~~ **SUPERADO** | [dado] "Fatia 4 — plano", 2026-11-01; ver divergência 9 | — |
| **teto de precisão 58,8 % = 283 / 481** (89/154 = 57,8 %, 93/168 = 55,4 %, 101/159 = 63,5 %): detecções na âncora `frame` de um reinício anotado | [nosso] revisão da Fatia 5, 2026-11-04 | `--bola-parada` bloco 1 |
| detecções sem reinício na âncora: **198 = 185 + 13** (185 = 481 − 296; 13 = os `no_dead_ball_before`, sem transição morta→viva) | [nosso] revisão da Fatia 5, 2026-11-04 | `--bola-parada` bloco 1 (481 − 283); `--passes` bloco 8 |
| mínimo de 1 s: 312 transições; ~~teto 94,9 % (296/312)~~ **SUPERADO** → **90,4 % = 282 / 312** | [dado] "Fatia 4 — plano", 2026-11-01; corrigido na revisão da Fatia 5, 2026-11-04 | `--bola-parada` bloco 4 |
| p10 da duração da bola morta = 0,04 s | [dado] idem | **sem comando no repositório** |
| **micro P 0,482 / R 0,786 / F1 0,598 (0,5979); `tp_diag` 232; `n_gabarito` 295** | [nosso] "Fatia 4 ACEITA", 2026-11-04 | `--bola-parada` bloco 2 |
| F1 por tipo: `kickoff` 0,971, `throw_in` 0,912, `corner_kick` 0,762, `goal_kick` **0,396**, `free_kick` 0,500 | [nosso] `docs/estado.md` (2026-11-04); `goal_kick` em "Fatia 4 ACEITA" | `--bola-parada` bloco 2 |
| `goal_kick` nas três leituras: 0,649 (`nao`) / **0,396** (`depois_de_cto`) / 0,383 (`antes_de_cto`); revocação 0,735 nas três | [nosso] "Revisão da Fatia 4", 2026-11-02, e "Fatia 4 ACEITA" | `--bola-parada` bloco 8 |
| `antes_de_cto`: micro 0,590; `nao` e `depois_de_cto`: micro idêntico | [nosso] "A ambiguidade da Fig. S1", 2026-11-01, e 2026-11-02 | `--bola-parada` bloco 8 |
| 71 detecções mudam entre `nao` e `depois_de_cto`, todas `free_kick?` ↔ `goal_kick` | [nosso] "Fatia 4 — a ambiguidade fechada", 2026-11-02 | `--bola-parada` bloco 8 |
| escanteios perdidos (vidal_codina): 6 → `free_kick`, 3 → `throw_in`, 1 sem casamento | [nosso] "Três números meus errados", 2026-11-02 | `--bola-parada`, matriz `vidal_codina` |
| teto de gatilho, jogos 1+2: corner 10/18, throw_in 55/60, goal_kick 33/38, kickoff 13/14 | [nosso] "Fatia 4 ACEITA", 2026-11-04 | `--bola-parada` bloco 1, "REVOCACAO DE GATILHO" |
| curva `eps_c`: 3 m → F1 escanteio 0,762; 5 m → 0,902 (baixa confiança) | [nosso] "O que a Fatia 4 já mostrou", 2026-11-01 | `--bola-parada` bloco 5 |
| `eps_f` roteia 31 a 36 % das transições ao problema 3; deslocamento ≤ 1 m em ~~64 / 64 / 72 %~~ **63,6 / 63,7 / 69,2 %** (`confirmado` = 98/154, 107/168, 110/159); **36,4 / 36,3 / 30,8 %** vão ao problema 3 (`anda_mais_que_eps_f` + `sem_passe_do_executor` = 56, 61, 49); o 72 % do jogo 3 não reproduz [corrigido 2026-11-04, auditoria pós-Fatia 6] | [nosso] "a bifurcação do S1", 2026-11-01; remedido na auditoria | crosstab de `game` × `motivo_reserva1` em `outputs/deteccoes.csv` (gravado por `--bola-parada`) |
| 481 de 481 transições com a bola a ≤ 0,5 m de alguém no 1º quadro vivo | [nosso] idem | **sem comando no repositório** |
| bracketing de `eps_f`: 0,4484 (0) → 0,5979 (1 m) → 0,6134 (∞) | [nosso] "Três números meus errados", 2026-11-02, revisor | **sem comando no repositório** |
| leitura alternativa do `else` do S1: micro 0,6495, `tp_diag` 252 | [nosso] "Achado de desenho", 2026-11-02, revisor (cópia fora do repositório) | **sem comando** |
| lacuna "sem passe do executor": vale 14 acertos; micro 0,634 e `tp_diag` 246 se tratada como "não se deslocou" | [nosso] idem, revisor | **sem comando** (o bloco 2 mostra só a contagem por motivo) |
| pênalti: cobrador a \|y\| = 1,478 m, falha por 0,478 m | [nosso] "o pênalti", 2026-11-01 | **sem comando no repositório** |
| M12 (`abs` na profundidade): `tp_diag` 233, micro 0,6005 | [nosso] "Dois mutantes", 2026-11-02 | mutante, fora do repositório |
| 378 testes | [nosso] "Fatia 4 ACEITA", 2026-11-04 | `uv run pytest` no commit `db7c080` |

**Divergências da Fatia 4:**

1. Micro F1: **0,599** ("O que a Fatia 4 já mostrou", 2026-11-01, antes da caixa
   quadrada do pênalti) contra **0,5979** ("o pênalti", 2026-11-01, e "Fatia 4
   ACEITA"). Vale 0,5979.
2. `free_kick` F1: **0,492** (2026-11-01) contra **0,500** (`docs/estado.md`,
   2026-11-04, e o comando).
3. `goal_kick` F1: 0,649 (2026-11-01, leitura `nao`) contra 0,396 (padrão desde
   2026-11-02). Não é erro: mudou o padrão. Vale 0,396.
4. `free_kick?`: **117** (2026-11-01) → **122** (2026-11-02, leitura `nao`) → o
   comando atual dá **51** no padrão `depois_de_cto` (122 − 71). O "47 dos 122
   `free_kick?` vêm de sem passe" (2026-11-02) é da leitura `nao`; no padrão
   atual o comando dá 19 `free_kick?` com `sem_passe_do_executor`. **Nenhum
   registro de 51 em `decisoes.md`.**
5. Escanteios perdidos: 7 + 3 (2026-11-01; e ainda em `docs/estado.md`) contra 6 +
   3 + 1 (2026-11-02, e o comando). Vale 6 + 3 + 1. ~~**`docs/estado.md` está
   desatualizado neste ponto.**~~ **Resolvida: `docs/estado.md` já diz 6 + 3 + 1.** [corrigido 2026-11-04, auditoria pós-Fatia 6]
6. Sensibilidade de âncora: micro 0,599 → **0,596** (2026-11-01) contra o comando
   atual 0,598 → **0,595** (`tp_diag` 231). O registro é de antes da correção do
   pênalti; sem registro posterior.
7. `so_por_lacuna_5`: **8** de 481 rótulos mudam (2026-11-01, leitura `nao`)
   contra **7** no comando atual (`depois_de_cto`). Micro idêntico nos dois.
8. Topo do bracketing de `eps_f`: 0,643 (2026-11-01) contra 0,6134 (2026-11-02).
   Vale 0,6134; o 0,643 era outra medida (a leitura alternativa, 0,6495).
9. **Teto de precisão: 61,5 % (296/481) e 94,9 % (296/312) estão SUPERADOS por
   58,8 % (283/481) e 90,4 % (282/312)** (revisão da Fatia 5, 2026-11-04). O
   numerador antigo eram os 296 reinícios anotados, mas 13 deles (os
   `no_dead_ball_before`) não têm transição morta → viva, logo nenhuma detecção
   pode casar com eles; o numerador certo são as detecções que caem na âncora
   `frame` de um reinício. Os "185 FP estruturais" (481 − 296) passam a **198**
   (481 − 283 = 185 + 13). Com mínimo de 1 s uma das 283 sai (282): o intervalo
   morto dela dura menos de 1 s.

## Fatia 5 — passes (2026-11-04)

Produzidos por `src/events/passes.py`, `src/evaluate.py:gabarito_secundario` e
`python -m src.run --passes`. ~~**Ainda sem revisão independente.**~~ **Revistos (revisão independente aceita em 2026-11-04;** `docs/decisoes.md`, "Revisao da Fatia 5"). [corrigido 2026-11-04, auditoria pós-Fatia 6] Critério
principal = passes `completo` × `PASS`; secundário = todos × `pass_secundario`
sem o grupo `bola_parada`; âncora `frame` (para passe as duas coincidem, com
teste).

| número | onde | comando |
|---|---|---|
| denominador principal 722 / 889 / 1039 = 2650 | [nosso] contrato do `docs/fatias/05-plano.md` §2.1 | `--passes` blocos 3 e 5 |
| denominador secundário 987 / 1115 / 1347 = 3449 (= 1009/1131/1358 − 22/16/11 tiros de meta) | [nosso] plano 05 §2.1; "Fatia 5 — plano", 2026-11-04 | `--passes` bloco 4 |
| perdas 3459 = 1017 / 1120 / 1322; suprimidas como bola parada 464 = 151 / 159 / 154; passes 2995 = 866 / 961 / 1168 | [nosso] | `--passes` bloco 1 |
| suprimidas de jogador ≠ executor: 137 (44 / 51 / 42), dos quais 48 são `free_kick?` (sem executor) | [nosso] | `--passes` bloco 1 |
| desfecho: completo 2262, interceptado 366, bola_morta 365, próprio 2, fim_de_periodo 0; recepção em duelo 76 | [nosso] | `--passes` bloco 2 |
| **principal estrito: P 0,967 / R 0,825 / F1 0,890; `tp_diag` 2187, `n_det` 2262** | [nosso] | `--passes` bloco 3 |
| principal por jogo, F1 estrito: 0,912 / 0,904 / 0,864 | [nosso] | `--passes` bloco 3 |
| principal vidal_codina F1 0,898 (`tp` 2205); mills 0,914 (`tp` 2244) | [nosso] | `--passes` bloco 3 |
| secundário estrito: P 0,922 / R 0,801 / F1 0,857; `tp_diag` 2761, `n_det` 2995 | [nosso] | `--passes` bloco 4 |
| diagnóstico (todos × `PASS`) estrito `tp_diag` 2209 (≤ teto 2353); vidal_codina 2246 (≤ 2430) | [nosso] | `--passes` bloco 5 |
| decomposição dos 463 FN do principal estrito: a 297, b 144, c 22, d 0 (por jogo 111 / 148 / 204, = `fn`) | [nosso] | `--passes` bloco 6 |
| (a) = 297 = 2650 − 2353, exatamente o complemento do teto da Fatia 3 | [nosso] | `--passes` bloco 6 e `--tau-posse` |
| sem lacuna 5: 2884 passes (111 a menos); F1 principal estrito 0,890, secundário 0,859 | [nosso] | `--passes` bloco 7 |
| detecções "espúrias" (quadro não é âncora de reinício anotado): 198 de 481 = 185 + 13 (ver divergência 9 da Fatia 4) | [nosso] | `--passes` bloco 8 |
| supressões a ≤ 1 s de um `PASS` do mesmo jogador: 144 de 464; 114 delas por detecção espúria | [nosso] | `--passes` bloco 8 |
| decomposição por jogo: a 60 / 90 / 147, b 45 / 51 / 48, c 6 / 7 / 9, d 0 (travada em teste) | [nosso] revisão da Fatia 5, 2026-11-04 | `--passes` bloco 6 |
| **EXPLORATÓRIO** (bloco 9, supressão só se a perda for do executor): 3132 passes; principal estrito P 0,967 / R 0,861 / F1 0,911 (`tp_diag` 2282); secundário estrito P 0,921 / R 0,837 / F1 0,877 (`tp_diag` 2886) | [nosso] revisão da Fatia 5, 2026-11-04 — decidido depois de ver o resultado; o principal não muda | `--passes` bloco 9 |
| 418 testes (até a Fatia 5) | [nosso] | `uv run pytest` |

## Fatia 6 — simulador de broadcast (2026-11-04, com a emenda §10)

Produzidos por `src/broadcast.py` e `python -m src.run --simulador` (74 s de
parede). Rótulos do bloco 1 e do bloco 5 revistos na revisão independente
(2026-11-04, I1–I4); os números calibrados não mudaram. ~~**Ainda sem revisão independente.**~~ **Revistos (revisão independente aceita em 2026-11-04;** `docs/decisoes.md`, "Revisao da Fatia 6"). [corrigido 2026-11-04, auditoria pós-Fatia 6] Tudo em valor esperado, sem sorteio,
exceto as taxas "amostradas" do bloco 4. **Nenhum P/R/F1 nem contagem de detecção
sobre tracking degradado** (plano 06 §6). Parâmetros e os 16 níveis em
`config.yaml:simulador.calibrado`, travados pelo T8. **Todos os números abaixo
são da rodada DEPOIS da emenda §10** (trocas por minuto como restrição do ajuste);
os da rodada anterior (`b` = 0,3245, 332,5 trocas/min) estão superados.

| número | onde | comando |
|---|---|---|
| alvos dos cortes 0,1425 (vivo) / 0,6823 (morto) / 0,468 (âncora de 110 laterais) | [lit] Bassek p. 6 e FOOTPASS §3.2 p. 6, derivados no código | `--simulador` bloco 1 |
| restrição: trocas on↔off esperadas em B8 ≤ 10,9/min | [lit] Bassek, Discussão, p. 8; emenda §10 | `--simulador` blocos 1 e 5 |
| `a_vivo` ≈ 0 (9,7e-19, no limite inferior), `a_morto` 0,0059498, `b` 0,0030118 | [nosso] | `--simulador` bloco 1 |
| obtido 0,1648 / 0,5695 / 0,5639; resíduos +0,0223 / **−0,1128 / +0,0959** (os dois últimos > 5 pontos: limitação registrada, §4.5) | [nosso] | `--simulador` blocos 1 e 5 |
| trocas/min em B8 2,8704; folga 8,0296; **restrição INATIVA no ótimo, mas seletora de bacia** | [nosso] | `--simulador` bloco 1 |
| ótimo SEM a restrição (teto = ∞, mesmos 4 pontos iniciais): `a_vivo` 0,052890, `a_morto` 0,675492, `b` 0,324508, custo 3,816e-5, 332,53 trocas/min (3 dos 4 pontos; o 4º cai na bacia interior, `b` 0,003012) | [nosso] diagnóstico | `--simulador` bloco 1 |
| episódios `off` esperados em B8 (entradas on → off): 1,4414 por minuto; 142,9 / 145,8 / 124,4 por jogo — **não** é a taxa de cortes do Bassek | [nosso] | `--simulador` bloco 1 |
| duração esperada dos episódios (taxa de saída constante): `off` 13,28 s nos dois estados; `on` 6,72 s em bola morta, ∞ em bola viva (`a_vivo` ≈ 0, abaixo de `tol_confere_abs` = 1e-9: "limite inferior ativo") | [nosso] | `--simulador` bloco 1 |
| 4 pontos iniciais do SLSQP, mesma solução: custo 0,0112062359 em todos, dispersão relativa 2,6e-5 (`a_morto`) e 1,8e-5 (`b`) | [nosso] | `--simulador` bloco 1 |
| papéis por (jogo, time) e o `x` médio de cada jogador | [nosso] | `--simulador` bloco 2 |
| `θ*` = 24,5598° (`d_cam` 30 m, `c` = 1) | [nosso] | `--simulador` bloco 3 |
| distância visível GK / DEF / MID / OFF = 0,1913 / 0,4038 / 0,4927 / 0,4622 (alvo texto 0,14 / 0,40 / 0,52 / 0,46; GK com resíduo +0,0513, limitação registrada) | [nosso] contra [lit] Bassek p. 6 | `--simulador` blocos 3 e 5 |
| resíduos contra a Tabela 1 (0,139 / 0,366 / 0,462 / 0,421): +0,0523 / +0,0378 / +0,0307 / +0,0412 | [nosso] | `--simulador` bloco 3 |
| tempo visível GK / DEF / MID / OFF = 0,1166 / 0,3394 / 0,4181 / 0,3781 | [nosso] | `--simulador` bloco 3 |
| 152 segmentos de presença, 0 curtos | [nosso] | `--simulador` bloco 3 |
| níveis B: `θ` = ∞ / 65,083 / 45,461 / 33,442 / 24,560 (×4), `c` = 0 ×5, 1/3, 2/3, 1; taxa esperada 1,0000 / 0,8752 / 0,7503 / 0,6255 / 0,5006 / 0,4184 / 0,3745 / 0,3471 | [nosso] | `--simulador` bloco 4 |
| níveis A: `L` = ∞ / 83,493 / 65,074 / 53,365 / 43,418 / 37,265 / 34,027 / 32,019 m, mesmas taxas (\|Δ\| < 1e-4) | [nosso] | `--simulador` bloco 4 |
| taxas sem GK e só em bola viva, esperadas e amostradas por jogo (mín.–máx. em 5 sementes) | [nosso] | `--simulador` bloco 4 |
| sementes efetivas `[20261104, jogo, 0..4]` | [nosso] plano 06 §5 | `--simulador` bloco 4 |
| B5 sem GK 0,5321 vs Crang Camera 1 0,56–0,64: **abaixo** do limite inferior | [nosso] contra [lit] Crang Tabela 1 p. 5 | `--simulador` bloco 5 |
| B8 sem GK 0,3701 vs Crang PGM 0,36–0,42: dentro | [nosso] contra [lit] | `--simulador` bloco 5 |
| B8 visíveis por time: P(0) 0,331; moda (k ≥ 1) 7 (0,114); P(≥ 9) 0,0728 (alvo ~0,20, abaixo); P(11) 0,0066 (alvo ~0,03, abaixo) | [nosso] contra [lit] Bassek pp. 6 e 8 | `--simulador` bloco 5 |
| B8 P(0 visíveis) marginal 0,3310 vs 38 %; P(off) marginal previsto pelos ALVOS 0,3446 e pelos cortes AJUSTADOS 0,3163 (f_viva 0,6256) | [nosso] | `--simulador` bloco 5 |
| critério de parada: GK é o papel menos visível em B8 → segue | [nosso] plano 06 §4.5 | `--simulador` bloco 5; travado no T8 |
| sensibilidade: `d_cam` 15 m → `θ*` 31,822°, resíduo GK +0,0721; 60 m → 16,756°, GK +0,0317 | [nosso] diagnóstico | `--simulador` bloco 6 |
| precursor: visibilidade esperada do executor anotado e da própria pequena área na corrida morta, por nível e tipo (em A1/B1 as áreas medem **presença** na zona, não visibilidade) | [nosso] só visibilidade | `--simulador` bloco 7 |
| tiro de meta em B5: executor visível 0,980 na âncora; área do time 0,844, GK 0,803 (B1: 0,847 / 0,807); em B8: 0,448 / 0,374 / 0,353 | [nosso] | `--simulador` bloco 7 |
| 483 testes (65 da Fatia 6: `test_broadcast.py` 21, `test_simulador_real.py` 44) | [nosso] | `uv run pytest` |

## Números pendentes de medição, com gatilho de portão

| número | quando | gatilho |
|---|---|---|
| ~~distribuição de `τ` pelo argmin de distância~~ | ~~Fatia 2~~ | **FEITO: disparou com 45,36 %, mas a grandeza é inválida; decisão adiada** |
| ~~`\|τ_posse\|` = \|quadro anotado − quadro de perda de posse\|~~ | ~~Fatia 3~~ | **FEITO: 3,17 % > 1,0 s, janela 1,0 s; seção Fatia 3** |
| curva F1(`eps_c`) no jogo 3 | Fatia 8 | sem gatilho, mas **baixa confiança obrigatória**: n = 8 escanteios, 3 cobradores |
| tempo de parede de uma execução real | antes da Fatia 8 | **G4 se o orçamento passar de 2 h de CPU** |

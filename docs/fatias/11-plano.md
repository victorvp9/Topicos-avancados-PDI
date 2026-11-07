# Fatia 11 — Replicação no IDSSE (7 jogos, Bundesliga): teste LIMPO

Data: 2026-11-07. Aprovada pelo Victor (frente "Replicar no IDSSE"). G2 é meu, por
delegação. G4 e G5 ficam com o Victor.

## 0. Por que isto é limpo

Ninguém viu um único resultado do detector no IDSSE. O método fica congelado
**antes** de qualquer F1 de lá:
- o detector, a avaliação, o simulador e a reconstrução da tag `final`;
- as hipóteses H1–H3 de `docs/fatias/10-hipoteses.md`;
- as regras abaixo.

Uma única rodada final, com tag. O que for decidido depois de ver um F1 do IDSSE
leva o rótulo **exploratório**.

## 1. O dado (inspeção do orquestrador, `decisoes.md` 2026-11-06 e 2026-11-07)

- **Arquivos:** `data/idsse/` traz 7 jogos, com 3 arquivos XML por jogo (ficha,
  eventos, posições), sha256 em `SHA256SUMS.txt` e licença CC-BY 4.0.
- **Artigo:** Bassek, Rein, Weber e Memmert, *Scientific Data* 2025, DOI
  10.1038/s41597-025-04505-y. Não está em `refs/`, logo é citação web e cada
  número tem de ser conferido na página do artigo.
- **Posições:** TRACAB Gen5, 25 Hz (Métodos), o mesmo provedor B do Vidal-Codina
  (§2.1, p. 3). Uma `FrameSet` por pessoa e por tempo, com `N` (quadro absoluto),
  `T` (UTC), `X` e `Y` em metros, origem no centro e campo de 105 × 68.
- **Bola:** tem `BallStatus` (0 inativo, 1 ativo) e `BallPossession`.
- **Eventos:** codificados **ao vivo** e controlados depois do jogo. O `EventTime`
  vem em hora local com fuso (+02:00).
  - Bolas paradas: `KickOff`, `ThrowIn`, `CornerKick`, `GoalKick`, `FreeKick`,
    `Penalty`. Cada uma envolve um `Play` com `Player`, o executor.
  - Passe: `Play/Pass` e `Play/Cross`.
  - `Delete`: "evento apagado no pós-processamento, sem informação".
  - As coordenadas dos eventos têm a origem no canto. Não são usadas.
- **Defasagem evento × posição relatada no artigo:** −0,37 ± 1,82 s, máximo de
  27,34 s, só para passes e finalizações. **Isso ameaça o critério estrito de
  ±1 s**, daí o portão τ (§3).

## 2. Mapeamento DFL → interno (decidido agora, antes de medir)

Segue o mapeamento da Metrica (`mapeamento-eventos.yaml`, `src/gabarito.py`) nos
campos equivalentes:

| DFL | interno | nota |
|---|---|---|
| `KickOff` | `kickoff` | |
| `ThrowIn` | `throw_in` | |
| `CornerKick` | `corner_kick` | |
| `GoalKick` | `goal_kick` | |
| `FreeKick` | `free_kick` | |
| `Penalty` | `penalty` | |
| `Play` com `Pass` ou `Cross`, fora de bola parada | `pass` | na Metrica, `PASS` inclui o cruzamento |
| `Delete` | descartado | sem informação, segundo o artigo |
| o resto | `fora_do_escopo` | |

- **O executor da bola parada** é o `Player` do `Play` filho. O `Play` filho não
  conta como passe: é a fusão bola parada + execução da Metrica
  (`fundir_set_piece_com_execucao`).
- **Ancoragem da bola parada:** a mesma regra da Metrica. O quadro anotado vai
  para o primeiro quadro vivo da corrida morta mais recente, com a guarda de
  10 s.
- **Estado da bola (D1 no IDSSE):** `ball_live = BallStatus == 1`. É o booleano
  do provedor, como o provedor B do artigo (§2.1, p. 3). **Não** é derivado de
  NaN. O mínimo de 1 s não se aplica (`10-hipoteses.md`, "Fora").
- **Qualquer `Play` ou tipo DFL que não caiba na tabela:** o loader estoura, e a
  decisão vai ao G3 (orquestrador).

## 3. Portão τ (regra escrita antes de medir)

É a mesma medida da Fatia 2 (`tau:` no config): τ = t_anotado − t_D, onde t_D é o
quadro de menor distância passador–bola em ±10 s. A janela do critério principal
no IDSSE é o **menor valor da escada {1,0; 1,5; 2,0; 3,0} s**
(`tau_posse.escada_janela_s`, pré-registrada no `03-plano`) com no máximo 5 % dos
passes com |τ| maior que ela. Se nenhum valor passar, usa-se 3,0 s, e isso é
declarado. Sem interpolação e sem valor fora da escada. A janela escolhida vale
para os três critérios? **Não**: só substitui a do `estrito`; `vidal_codina`
(10 s) e `mills` (3 s) ficam como estão.

## 4. O que se mede

### 4a. Teto no IDSSE (11b)
O ponto da AB1, nos 7 jogos, com P/R/F1 por tipo e o mínimo e máximo por jogo.
- **H1:** precisão micro de bola parada ≥ 0,75.
- **H2:** a regra D (`supressao_exige_executor`) dá Δ F1 de passe principal > 0
  agregado e em ≥ 5 dos 7 jogos. É a única chave exploratória que vira
  pré-registrada aqui; B e C não entram.
- **H3:** a precisão pela via `padrao` é maior que a das reservas 1 e 3.
- Mais as decomposições R9 e a curva de `ε_c` (R7).

### 4b. Experimento de degradação (11c), a pergunta do projeto, replicada
- **As regras R1–R10 do `08-plano.md` e a emenda §8 valem sem mudança**, com
  três adaptações a 7 jogos, decididas agora:
  1. **Candidato no LOGO:** ganho em pelo menos 4 dos 6 jogos de treino
     (⌈2/3 · 6⌉), em vez de "nos 2 de 2", e F1_T(R) > F1_T(R0). Com k = n = 6,
     a regra ficaria mais severa só por haver mais jogos.
  2. **"Ajuda":** Δ_g > 0 em ≥ 5 dos 7 jogos (⌈2/3 · 7⌉) e Δ_agregado > λ.
  3. **Sementes:** `[20261107, jogo, rep]`, `rep` 0–4 (5 sementes, R8).
- **Simulador:** os parâmetros calibrados da Metrica (`simulador.calibrado`),
  congelados. **Não recalibrar no IDSSE**: seria afinar no dado de teste. Os
  níveis A e B e as taxas são os mesmos; a taxa amostrada é medida de novo.
- **Condições:** `reconstruido` (principal); `bruto` só se o orçamento couber
  (G4).
- **A resposta:** `reconstruido`, B5 e B8, alvos primários, como na Fatia 8.

## 5. Implementação (codificador), em três partes

- **11a. Loader e inspeção.**
  - `src/io/idsse.py`: leitura com `xml.etree.ElementTree.iterparse` da
    biblioteca padrão, **sem dependência nova**, devolvendo o esquema interno de
    `docs/02-dados.md`.
  - Quadros remapeados para 1..N contíguos com `period`. Eventos convertidos de
    `EventTime` para quadro pelo `T` UTC das posições. `home`/`away` pela ficha.
    IDs de jogador `gI_<home|away>_<PersonId>`.
  - A conversão é cacheada em `outputs/cache/`, por sha256 do arquivo de entrada.
  - Modo `--inspect-idsse`: contagens por tipo e por jogo; `Delete`; transições
    morto → vivo por tempo contra o número de bolas paradas; NaN de jogadores e
    da bola; o portão τ da §3.
  - Saída `outputs/idsse/inspecao.csv` e um resumo impresso. **Nenhum detector
    roda na 11a.**
- **11b. Teto e hipóteses** (depois que eu aplicar a regra do portão τ): modo
  `--teto-idsse`, saídas em `outputs/idsse/teto/`.
- **11c. Experimento:** a máquina da Fatia 8 parametrizada por conjunto de dados
  (`--experimento --dados idsse`), saídas em `outputs/idsse/experimento/`. G4
  com o tempo medido, G5 e uma rodada, com a tag `final-idsse`.

O caminho da Metrica tem de ficar **bit a bit igual**: teste que reproduz AB1 e
uma unidade B8 da rodada final.

### Testes obrigatórios (11a)
1. Um XML sintético mínimo com 2 jogadores, bola e 2 tempos dá o esquema interno
   esperado: coordenadas, `period`, quadros contíguos e `ball_live`.
2. O mapeamento estoura com um tipo DFL desconhecido. `Delete` é descartado e
   contado.
3. O executor da bola parada vem do `Play` filho, e esse `Play` não vira passe.
4. A conversão de `EventTime` (+02:00) para quadro bate com o `T` (UTC) num caso
   sintético. O fuso trocado faz o teste falhar.
5. O cache invalida quando o sha256 do XML muda.
6. Com `--dados metrica` (padrão), nada muda: AB1 e uma unidade B8 iguais aos de
   `outputs/experimento/pontos.csv`.

## 6. Fora
- Recalibrar o simulador no IDSSE.
- Escolher limiar olhando F1 do IDSSE.
- Usar DataBallPy ou outra sincronização evento × posição, porque seria uma
  dependência e uma decisão nova. Se o portão τ mostrar que é preciso, vai ao
  G3.
- Vídeo, que não existe no dataset.

## 7. Emenda de 2026-11-07 (depois do teto da 11b; decisão do Victor)

A 11c roda **duas configurações**, com a máquina, a grade, as regras R1–R10 e a
emenda §8 do `08-plano.md`, mais as adaptações a 7 jogos da §4b:

| config | `R0` | `eps_s` / `eps_v` | rótulo |
|---|---|---|---|
| **A** (pré-registrada) | 0,50 m | 0,05 m / 1,0 m/s | **limpa** |
| **B** (provedor B, supl. S4.1 p. 6 e S4.2 p. 8) | 1,00 m | 0,10 m / 5,0 m/s | **EXPLORATÓRIA**: escolhida depois de ver o teto da 11b |

- **Fixos para A e B:**
  - condição `reconstruido` apenas;
  - 5 sementes `[20261107, jogo, rep]`;
  - simulador congelado com a calibração da Metrica;
  - critério principal `vidal_codina`;
  - níveis 1, B2–B8 e A2–A8;
  - grade de `R_pz` igual à da Fatia 8. Em B, o `R0` é 1,00 m e a grade continua a mesma; o LOGO compara cada `R` com esse `R0`.
- **Fora:** a curva de `ε_c`, que já está na 11b.
- **Resposta:** como na Fatia 8 (B5 e B8, alvos primários), dada separadamente para A e para B.
- **G4:** o tempo de uma unidade completa é medido antes de rodar. Se a estimativa passar de 1,5× ~6 h de CPU, volta ao Victor.
- **G5:** config congelada e tag `pre-rodada-final-idsse`; uma rodada por config.

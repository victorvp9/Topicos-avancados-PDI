# Estado do projeto

Atualizado: 2026-11-06 (REABERTO pelo Victor: Fatia 10 auditoria em curso; depois 11 IDSSE e 12 StatsBomb 360. O resultado limpo continua na tag `final`)

## Onde estamos

- **G1 fechado.** Docs 00 a 03 corrigidos com V1–V16, `decisoes.md` escrito com
  D1–D10 congeladas, plano congelado na tag **`plano-congelado`**.
- Dados baixados e inspecionados: `data/metrica-sample-data`, commit
  `e706dd506b360d69d9d123d5b8026e7294b13996`, sem ponteiro de LFS, sha256 de cada
  arquivo em `docs/inspecao-metrica.md` §1.
- Os 7 PDFs de `refs/` foram lidos por inteiro (Vidal-Codina e suplementar,
  Mills, Bassek, Crang, FOOTPASS, definições da Metrica). A lista "AINDA NÃO
  CONFERIDO" do briefing está encerrada.
- Prazo: sem prazo fixo (Victor, 28/10). As semanas do `03-plano` valem só como
  ordem.

## O que a inspeção mudou no plano

1. **Estado da bola resolvido sem circularidade** (D1): `NaN(bola)`, que é o
   mecanismo dos provedores Track160 e Hawk-Eye no artigo original.
2. **Jogo 3 entra no escopo sem dependência nova** (D6): sem `kloppy`, sem
   `floodlight`.
3. **O `docs/01` estava errado sobre gatilho e padrão.** Gatilho olha só os
   jogadores, durante a bola morta. Reescrito.
4. **Passe estava errado** (V16): é toda perda de posse que não é finalização nem
   cruzamento.
5. **O critério de acerto virou estrito** (D8), porque no instante anotado o
   passador já está a 8 cm da bola (mediana), ao contrário da STS.
6. **`eps_c` = 3 m dá só 56 % de teto em escanteio** (D9b). É o achado central da
   inspeção e vira um 2º parâmetro livre, com o jogo 3 reservado.

## Ajustes do Victor pós-G1 (2026-10-29, sem reabrir regra)

1. **Justificativa do D8 corrigida.** Eu havia justificado a janela de ±1 s por
   `max |Start Time − Frame/25| = 0`, que só prova consistência de unidade e nada
   diz sobre a acurácia do instante anotado. A justificativa agora é a medida do
   D9c (passador a menos de 0,5 m da bola no quadro anotado em 96,7 % e 97,4 %,
   mediana 0,08–0,09 m). **A regra não mudou, logo não é mudança declarada.**
2. **Nova medição obrigatória na Fatia 2, com gatilho de G3:** distribuição de
   `τ = t_anotado − t_D` nos passes dos 3 jogos. Se mais de 5 % tiverem
   |τ| > 1 s, parar antes de rodar qualquer detector.
3. **Jogo 3 contado:** 90 bolas paradas = 50 laterais, 28 tiros livres,
   **8 escanteios**, 4 pontapés iniciais. Os 8 escanteios são de 3 cobradores,
   6 de um só time → **ajuste de `eps_c` declarado de baixa confiança**, e o
   rótulo acompanha o número onde ele aparecer.

## Fatia 1 — ACEITA (2026-10-29)

Plano em `docs/fatias/01-plano.md`, aprovado no G2. Implementada, revisada em duas
rodadas, aceita. **144 testes passam.** Os 12 testes novos da segunda rodada
passaram por teste de mutação do revisor.

Entregue: `pyproject.toml`, `config.yaml`, `mapeamento-eventos.yaml`, `src/` (9
arquivos, ~1120 linhas), `tests/` (6 arquivos, ~1320 linhas). Dependências:
`pandas>=3.0`, `numpy`, `pyyaml`, `pytest`. Sem `kloppy`, sem `floodlight`.

Tabelas produzidas: `frames`, `tracking`, `periods`, `events`, para os 3 jogos.
`python -m src.run --inspect` confere contra `docs/inspecao-metrica.md`.

Uma mudança declarada em regra congelada saiu daqui: a **guarda de 10 s** na
ancoragem (G3). Ver `docs/decisoes.md`.

## Fatia 2 — ACEITA (2026-10-30)

Plano em `docs/fatias/02-plano.md`, aprovado no G2. Implementada, revisada em
**duas rodadas completas mais uma re-revisão focada**, com teste de mutação em
cada uma. **227 testes passam.**

Entregue: `src/evaluate.py` (casador um-para-um ótimo via `scipy`, métricas,
matriz de confusão por grupo), `src/tau.py`, 4 arquivos de teste, `--tau` no CLI.

Três correções de fundo saíram daqui, e **duas eram erros meus de plano**:

1. O critério do Vidal-Codina **não casa por tipo** — a comparação de tipo é a
   matriz de confusão (supl. S2, p. 3).
2. `precisao`/`revocacao`/`f1` saem da **diagonal** da matriz (`tp_diag`). Com o
   numerador anterior, um detector que erra todos os tipos reportaria F1 = 1,00.
3. `penalty` virou classe própria do gabarito, senão a detecção da Fatia 4 seria
   falso positivo sem par possível.

**O gatilho de G3 da defasagem disparou (45,36 % contra 5 %) e eu concluí que o
meu próprio teste era inválido.** Decisão: adiada para a Fatia 3, com a regra de
escolha da janela **escrita antes de medir**. O ±1 s está rotulado **provisório**.

> O código da Fatia 2 entrou nos commits `7e3686f` e `99af5ca`, rotulados
> `docs:` por descuido meu (`git add -A` com subagente em voo, duas vezes).
> Regra nova: commit por caminho explícito.

## Fatia 3 — ACEITA (2026-10-31)

Passo 1 completo (PZ/DZ, control frames, Savitzky-Golay por corrida, perda e
ganho), as duas políticas de `R_dz`, e a medição que **confirmou a janela do D8
em ±1 s** (3,17 % dos 2430 passes com perda acima de 1 s, limiar pré-registrado
de 5 %, primeiro degrau da escada). **319 testes.** Duas revisões completas mais
uma re-revisão focada; o revisor reimplementou o Passo 1 do zero **duas vezes**.

Três afirmações minhas foram desmentidas por medição nesta fatia, e a lição virou
regra: **nenhuma afirmação numérica sobre a grade entra em documento sem a linha
dos três jogos ao lado** — os três erros tiveram a mesma causa, eu escrever a
partir do jogo 1.

## Fatia 4 — ACEITA (2026-11-04)

Plano em `docs/fatias/04-plano.md`. **378 testes passam** (após a re-revisão). Cinco rodadas com o
codificador; é a fatia com mais lacunas de especificação preenchidas do projeto
(oito dele, três minhas), e por isso a revisão independente é a mais importante
até agora.

**A primeira tabela de F1 real do projeto** (critério estrito, âncora `frame`,
3 jogos, micro sem pênalti): **P 0,482 / R 0,786 / F1 0,598**. Por tipo: pontapé
inicial 0,971, lateral 0,912, escanteio 0,762, tiro de meta **0,396** (era 0,649 antes de a Fig. S1 ser lida; ver `decisoes.md`), tiro livre
0,500. A precisão baixa é o teto de precisão previsto (~~61,5 %~~ **58,8 %**, erro meu nº 8, Fatia 5); a revocação alta mostra que
o algoritmo **acha** os reinícios e erra o **tipo**.

**Três achados de fundo:**

1. **As tolerâncias publicadas não transferem para a Metrica**, com três
   instâncias medidas: `ε_c` = 3 m pega 10 de 18 escanteios (gatilho, jogos 1+2), `ε_f` = 1 m roteia
   31–36 % das transições para o problema 3 do S1 (remedido na auditoria: 36,4 / 36,3 / 30,8 %), e `ε_p2` = 2 m perde o único
   pênalti por 48 cm. É o que explica o teto abaixo dos ~90 % do artigo **sem que
   o algoritmo esteja errado**.
2. **A matriz do critério Vidal-Codina mostrou o erro previsto desde o G1**: dos
   10 escanteios perdidos nos **3 jogos** (26 − 16 casados como escanteio), 6 viram tiro livre, 3 viram lateral e 1 fica sem
   casamento (corrigido em 2026-11-04; o "7 + 3" era meu, ver `decisoes.md`
   2026-11-02).
3. **O goleiro mora na pequena área**, logo o gatilho de tiro de meta fica quase
   sempre completo — e daí saiu a previsão pré-registrada para a Fatia 6.

## Fatia 5 — ACEITA (2026-11-04), tag `teto`

Plano em `docs/fatias/05-plano.md`. **418 testes.** Duas rodadas do revisor, com
reprodução independente e mutação.

**Teto do projeto** (critério estrito, `R_pz` = 0,50 m, 3 jogos):

| | P | R | F1 |
|---|---|---|---|
| passe principal (`completo` × `PASS`, n = 2650) | 0,967 | 0,825 | **0,890** |
| passe secundário (todos × união sem tiro de meta, n = 3449) | 0,922 | 0,801 | 0,857 |
| bola parada, micro sem pênalti | 0,482 | 0,786 | 0,598 |

FN de passe: 297 sem perda a ≤ 1 s (= 2650 − 2353, fecha com a Fatia 3), 144
suprimidos como bola parada, 22 com desfecho errado. **Erro meu nº 8:** o teto de
precisão de bola parada é 58,8 %, não 61,5 %. Exploratório: suprimir só a perda
do executor daria F1 de passe 0,911 (89 + 48 casos; ver `decisoes.md`).

## Fatia 6 — ACEITA (2026-11-04)

Plano em `docs/fatias/06-plano.md`, com a emenda §10 (mudança declarada) e o
resultado em §10.1. **483 testes.** Revisão independente, que reproduziu tudo com
Δ = 0, testou 16 mutantes e matou 13, mais uma re-revisão focada, que matou os 9
mutantes pedidos.

Os níveis, sempre medidos como a taxa = linhas visíveis / presentes, nos 3 jogos e
em valor esperado:

- **Variante B (cunha que segue a bola, mais cortes):** B1 = 1,000; B5 ("Camera 1",
  `θ*` = 24,56°, sem cortes) = 0,501; B8 ("PGM", com cortes) = 0,347.
- **Variante A (janela fixa):** pareada em taxa com a B, nível a nível.

Como cada número se comportou:

- **Calibrados contra alvos publicados:** distância visível por papel (DEF, MID,
  OFF a menos de 3 pontos do Bassek) e cortes.
- **Validações pré-registradas reprovadas, só registradas:** B5 sem GK = 0,532,
  abaixo do limite inferior de 0,56 do Crang; P(≥ 9 visíveis por time) = 0,07
  contra 0,20.
- **Validação dentro do alvo:** B8 sem GK = 0,370, dentro da faixa do Crang PGM.

Três achados:

1. **O ajuste livre dos cortes dava pisca-pisca** (332 trocas/min). A restrição de
   ≤ 10,9 trocas/min (Bassek) escolhe a bacia dos cortes longos (~13 s, 2,9
   trocas/min); está declarada como mudança. Os resíduos de −11 e +9,6 pontos são
   **estruturais** à cadeia sem memória.
2. **Nenhum corte começa com a bola viva** (`a_vivo` ≈ 0): o apagão em jogo é
   corte herdado da paralisação e se concentra logo depois dos reinícios.
3. **Contra a minha previsão do tiro de meta**, só em visibilidade: a cunha mostra
   o goleiro na bola parada antes do tiro de meta (0,80 em B5). Toda a queda vem
   dos cortes, e em B8 o executor do tiro de meta é **mais** visível (0,45) que o
   do escanteio (0,34) e o da lateral (0,43). O F1 da Fatia 8 decide.

## Fatia 8a — ACEITA (2026-11-05), tag `baseline`

Plano em `docs/fatias/08-plano.md`. As regras de decisão (§2) e a emenda §8
foram escritas **antes** de qualquer F1 degradado fora de `R0`. **560 testes.**
Houve uma revisão e duas re-revisões, com reprodução Δ = 0, determinismo entre
workers e cache vazio confirmados, e mais de 40 mutantes mortos.

- **Piloto** (desenvolvimento, não resultado): em B8, `R0`, `reconstruido`, 10
  sementes, o EP5 é 0,0047 no passe e 0,0073 na bola parada, ambos ≤ 0,01, logo
  **5 sementes**.
- **Orçamento do `--all`, com 3 workers:** 0,83–0,91 h de parede e 2,27–2,52 h de
  CPU com `bruto`; 0,52–0,56 h e 1,34–1,47 h sem `bruto`.

## Fatia 7 — ACEITA (2026-11-04)

Plano em `docs/fatias/07-plano.md`. **515 testes.** A revisão independente
reproduziu tudo com Δ = 0. Dos 19 mutantes, 3 sobreviveram e foram corrigidos; a
re-revisão focada aceitou. `python -m src.run --reconstrucao` leva cerca de
3,5 min e grava `outputs/reconstrucao.csv`.

Interpolação linear por jogador e período. `visible=False` nas linhas imputadas.
Usa a presença do teto, nunca a posição.

- **Erro no não detectado, sem GK, rep 0** (Crang, Tabela 2, p. 6):
  - B5 = **9,14 m**, dentro da faixa Cam 1 (9,08–10,27), numa taxa abaixo da do Crang;
  - B8 = **11,76 m**, acima da faixa PGM (4,58–11,56); de 11,46 a 12,15 m nas 5 sementes;
  - previsão registrada (acima de 4,6 m) confirmada.
- **O erro cresce com o buraco:** 0,14 m até 1 s, 18 m acima de 60 s (B8).
- **Viés de velocidade (B8):** a interpolação recupera 54 % da distância e 25 % da
  distância em alta velocidade.
- **Validação livre reprovada (5(a)):** no simulador, quem corre está mais
  visível (+0,18 a +0,32 contra −0,04 a +0,09 no Bassek). A queda de F1 da Fatia
  8 tende a ser **otimista**, e a pergunta Bassek × Mortensen e Bornn fica sem
  resposta sobre o mundo.
- **Executor imputado no quadro anotado (B8):** passe 16 %, bolas paradas de 50 % a 77 %.

## Auditoria pós-Fatia 6 (2026-11-04, pedida pelo Victor)

Dois revisores refizeram os resultados das Fatias 1 a 6 pelo CLI e por código
próprio. **Tudo reproduz; nenhum achado bloqueante; nenhum resultado mudou.** Os
achados eram de documento (números superados sem marca, páginas trocadas, rótulos
velhos) e foram corrigidos com a marca `[corrigido 2026-11-04, auditoria
pós-Fatia 6]`. Detalhe em `decisoes.md`, seção "Auditoria pós-Fatia 6".

## Próximo passo

Projeto concluído pelo plano: rodada final única (commit `48224e0`, 60 min),
revisada duas vezes, tag `final`. Resposta em `docs/relatorio.md` §1: aumentar
`R_pz` não compensa em B5; em B8 compensa só para bola parada, por margem pequena
(recupera ~9 % do F1 perdido), e não para passe. Depois, a pedido do Victor, análise de alternativas
(`docs/analise-alternativas.md`) e Fatia 9 exploratória (`docs/fatias/09-plano.md`,
revisada; apêndice no relatório). Achado: sob cortes, a perda é a fração de
eventos que cai num apagão total; nenhuma alternativa legítima a recupera com
estes dados. A regra D (supressão exige executor) corrige o detector também no
teto, a confirmar em dado novo (Bassek 2025, licença não conferida). Encerrado
por decisão do Victor.

## Portões

**2026-10-30: o Victor delegou todos os portões ao orquestrador até o fim do
projeto.** Eles viram auto-portões **com registro escrito** — a disciplina não
muda: regra antes de medir, decisão registrada com a alternativa descartada,
mudança declarada como mudança, rótulos limpo/exploratório honestos.

**Controle compensatório:** como eu passo a ser proponente e aprovador, e como
**três decisões minhas de plano já estavam erradas** e foram pegas por outros (o
`docs/01-definicoes.md` trocava gatilho por padrão; o teste de `τ` da Fatia 2 era
inválido por desenho; o F1 do `vidal_codina` esconderia um detector que erra todos
os tipos), o mandato do revisor passa a incluir **criticar o plano**, não só o
código.

| portão | situação |
|---|---|
| G1 correção consolidada e plano congelado | fechado 2026-10-29 |
| G2 plano de fatia | Fatias 1 e 2 fechadas; Fatia 3 decidida por mim |
| G3 mudança em regra congelada | 2 usados: guarda de 10 s; janela do D8 (adiada) |
| G4 aviso de execução longa | **continua indo ao Victor**: a máquina é dele e ele precisa pausar Windows Update e suspensão |
| G5 rodada final limpa | **continua indo ao Victor**, mesmo motivo |

## Dívidas registradas

- ~~Conferir se o `events-definitions.pdf` de `refs/` e o de
  `data/metrica-sample-data/documentation/` são o mesmo arquivo.~~ **Fechada:**
  são, sha256 `5afb1ee34931447223ef8b9dc6a30b827fd0ba57ac9b6e2d7125ee87b083a866`.
- ~~Não medi a defasagem `τ` da anotação.~~ **Fechada** na Fatia 3 (janela de ±1 s confirmada).
- Não medi os gatilhos de bola parada no jogo 3 antes da Fatia 4 — de propósito, para ele
  seguir sendo conjunto não visto para `eps_c`. (A distância passador–bola do jogo 3 foi medida
  na Fatia 2: 90,01 % a < 0,5 m.)
- ~~Não medi a distribuição de `eps_s`, `eps_v`, `eps_theta` na Metrica.~~ **Fechada** na Fatia 3.
- Não baixei a SkillCorner nem o suplementar do Bassek. A calibração usa os alvos
  publicados (tabela em `docs/02-dados.md`).
- Dataset alternativo não avaliado: Bassek et al. 2025, 7 partidas da Bundesliga
  com verdade de terreno multicâmera e eventos (FOOTPASS §2.1, p. 4). Licença e
  disponibilidade não conferidas. Decidir depois da Fatia 5 (G3).

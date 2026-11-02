# Estado do projeto

Atualizado: 2026-10-30 (portoes delegados ao orquestrador)

## Onde estamos

- **G1 fechado.** Docs 00 a 03 corrigidos com V1–V16, `decisoes.md` escrito com
  D1–D10 congeladas, plano congelado na tag **`plano-congelado`**.
- Dados baixados e inspecionados: `data/metrica-sample-data`, commit
  `e706dd506b360d69d9d123d5b8026e7294b13996`, sem ponteiro de LFS, sha256 de cada
  arquivo em `docs/inspecao-metrica.md` §1.
- Os 7 PDFs de `refs/` foram lidos por inteiro (Vidal-Codina e suplementar,
  Mills, Bassek, Crang, FOOTPASS, definições da Metrica). A lista "AINDA NÃO
  CONFERIDO" do briefing está encerrada.
- **Ainda não existe código.** `src/`, `tests/`, `config.yaml` e `pyproject.toml`
  não foram criados.
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

## Fatia 4 — implementada, em revisão (2026-11-02)

Plano em `docs/fatias/04-plano.md`. **375 testes passam.** Cinco rodadas com o
codificador; é a fatia com mais lacunas de especificação preenchidas do projeto
(oito dele, três minhas), e por isso a revisão independente é a mais importante
até agora.

**A primeira tabela de F1 real do projeto** (critério estrito, âncora `frame`,
3 jogos, micro sem pênalti): **P 0,482 / R 0,786 / F1 0,598**. Por tipo: pontapé
inicial 0,971, lateral 0,912, escanteio 0,762, tiro de meta 0,649, tiro livre
0,500. A precisão baixa é o teto de 61,5 % previsto; a revocação alta mostra que
o algoritmo **acha** os reinícios e erra o **tipo**.

**Três achados de fundo:**

1. **As tolerâncias publicadas não transferem para a Metrica**, com três
   instâncias medidas: `ε_c` = 3 m pega 10 de 18 escanteios, `ε_f` = 1 m roteia
   31–36 % das transições para o problema 3 do S1, e `ε_p2` = 2 m perde o único
   pênalti por 48 cm. É o que explica o teto abaixo dos ~90 % do artigo **sem que
   o algoritmo esteja errado**.
2. **A matriz do critério Vidal-Codina mostrou o erro previsto desde o G1**: dos
   10 escanteios perdidos, 7 viram tiro livre e 3 viram lateral.
3. **O goleiro mora na pequena área**, logo o gatilho de tiro de meta fica quase
   sempre completo — e daí saiu a previsão pré-registrada para a Fatia 6.

## Próximo passo

**Revisar a Fatia 4**, com o mandato de criticar as onze lacunas e as minhas
decisões antes do código. Depois, **Fatia 5 — passes**, que fecha o marco `teto`.

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
- Não medi a defasagem `τ` da anotação. É entregável da Fatia 2 e pode derrubar a
  janela de ±1 s do D8 (G3).
- Não medi distância jogador-bola nem gatilhos no jogo 3 — de propósito, para ele
  seguir sendo conjunto não visto para `eps_c`. As contagens já foram feitas.
- Não medi a distribuição de `eps_s`, `eps_v`, `eps_theta` na Metrica — é a
  Fatia 3.
- Não baixei a SkillCorner nem o suplementar do Bassek. A calibração usa os alvos
  publicados (tabela em `docs/02-dados.md`).
- Dataset alternativo não avaliado: Bassek et al. 2025, 7 partidas da Bundesliga
  com verdade de terreno multicâmera e eventos (FOOTPASS §2.1, p. 4). Licença e
  disponibilidade não conferidas. Decidir depois da Fatia 5 (G3).

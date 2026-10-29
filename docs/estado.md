# Estado do projeto

Atualizado: 2026-10-29

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
5. **O critério de acerto virou estrito** (D8), porque o gabarito da Metrica é
   frame-sincronizado e a defasagem de 1,5 s da STS não existe aqui.
6. **`eps_c` = 3 m dá só 56 % de teto em escanteio** (D9b). É o achado central da
   inspeção e vira um 2º parâmetro livre, com o jogo 3 reservado.

## Próximo passo

**Fatia 1 — loaders e gabarito.** Escrever `docs/fatias/01-plano.md` e levar ao
G2. Escopo em `docs/03-plano.md`, Fatia 1; esquemas em `docs/02-dados.md`;
constantes em `docs/01-definicoes.md`.

## Portões

| portão | situação |
|---|---|
| G1 correção consolidada e plano congelado | **fechado** 2026-10-29 |
| G2 plano de cada fatia | aberto, começa na Fatia 1 |
| G3 decisão só do Victor / mudança em regra congelada | — |
| G4 orçamento antes de execução > 2 h de CPU | antes da Fatia 8 |
| G5 rodada final limpa | antes da Fatia 8 |

## Dívidas registradas

- Não conferi se o `events-definitions.pdf` de `refs/` e o de
  `data/metrica-sample-data/documentation/` são o mesmo arquivo.
- Não medi distância jogador-bola nem gatilhos no jogo 3 (reservado para `eps_c`).
- Não medi a distribuição de `eps_s`, `eps_v`, `eps_theta` na Metrica — é a
  Fatia 3.
- Não baixei a SkillCorner nem o suplementar do Bassek. A calibração usa os alvos
  publicados (tabela em `docs/02-dados.md`).
- Dataset alternativo não avaliado: Bassek et al. 2025, 7 partidas da Bundesliga
  com verdade de terreno multicâmera e eventos (FOOTPASS §2.1, p. 4). Licença e
  disponibilidade não conferidas. Decidir depois da Fatia 5 (G3).

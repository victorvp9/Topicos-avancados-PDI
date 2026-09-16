# 02 — Dados

Nada em `data/` entra no Git. Baixe os datasets manualmente e coloque nos
caminhos abaixo.

---

## Metrica Sports — fonte principal

Repositório: `github.com/metrica-sports/sample-data`

Três partidas. Tracking e event data **sincronizados**. Dados anonimizados (sem
nomes de jogadores, times ou competições). A pasta `documentation/` traz um PDF
com a definição de todos os tipos e subtipos de evento — leia antes de mapear as
classes.

- **Jogos 1 e 2**: formato CSV padrão da Metrica.
- **Jogo 3**: formato novo — EPTS FIFA para o tracking, JSON para os eventos.
  Recomendam ler com `kloppy`.

**Coordenadas.** Normalizadas de 0 a 1 em cada eixo. `(0,0)` é o canto superior
esquerdo, `(1,1)` o inferior direito, `(0.5,0.5)` o ponto central. Campo de
**105 × 68 m** nos dois primeiros jogos.

**Conversão obrigatória para o sistema interno** (origem no centro, metros):

```
x_m = (x_norm - 0.5) * 105
y_m = (y_norm - 0.5) * 68   # conferir o sinal: y cresce para baixo na origem
```

O sinal de `y` é armadilha clássica. Escreva um teste que projeta as quatro
bandeirinhas de escanteio e confere que caem em `(±52.5, ±34)`.

**Atenção:** o sistema de coordenadas da Metrica mudou entre as primeiras lições
do Friends of Tracking e as posteriores. Não copie fórmula de tutorial sem
validar contra o dado que você baixou.

**Sentido de ataque.** Inverte no segundo tempo. Normalize para que o time da
casa ataque sempre no mesmo sentido, e registre isso em `docs/decisoes.md`.

---

## SkillCorner — calibração do simulador

Repositório atual: `github.com/skillcorner/opendata`

**O repositório mudou de conteúdo.** Hoje traz 10 partidas da A-League
australiana 2024/25, com tracking extrapolado em JSONL, eventos dinâmicos e
fases de jogo em CSV, mais agregados físicos de temporada. Tem módulos Python em
`src/` para carregar e visualizar.

O conjunto **antigo** — 9 partidas das cinco grandes ligas europeias em 2019/20 —
é o mais próximo do que este projeto precisa e continua acessível em forks e via
a biblioteca `floodlight` (`floodlight.io.skillcorner.read_position_data_json`).
Formato antigo, por partida:
- `match_data.json` — escalações, árbitro, dimensões do campo
- `structured_data.json` — lista de frames

Cada frame: `period` (1 ou 2), `frame` (**10 fps**), `timestamp` (precisão de
1/10 s), `data` (lista com jogadores, árbitro principal e bola).

**Coordenadas:** metros, origem no centro do campo. Já é o sistema interno — não
converta.

**O que interessa aqui:** o dado é real de broadcast, então jogadores faltam em
muitos frames. A distribuição de "quantos jogadores visíveis por frame" é o alvo
de calibração do simulador. Não é gabarito de evento — é referência de
visibilidade.

---

## Esquema interno

Todo loader converte para estes dois DataFrames.

### `tracking`
| coluna | tipo | unidade |
|---|---|---|
| `frame` | int | — |
| `t` | float | s desde o início do período |
| `period` | int | 1 ou 2 |
| `player_id` | str | `ball` para a bola |
| `team` | str | `home` / `away` / `ball` / `referee` |
| `x`, `y` | float | m, origem no centro |
| `visible` | bool | False quando imputado |

### `events` (gabarito)
| coluna | tipo | unidade |
|---|---|---|
| `t` | float | s |
| `period` | int | — |
| `type` | str | vocabulário de `docs/01-definicoes.md` |
| `team` | str | — |
| `player_id` | str | — |

O mapeamento das classes da Metrica para o vocabulário interno vai num YAML
explícito, não espalhado em `if`s.

---

## Armadilhas registradas

- Unidades: normalizado (Metrica) vs. metros (SkillCorner).
- Frequência: Metrica a 25 fps, SkillCorner a 10 fps. Reamostrar, não assumir.
- Sinal de `y` invertido entre convenções.
- Inversão de sentido de ataque no segundo tempo.
- Jogo 3 da Metrica em formato diferente dos jogos 1 e 2 — trate como loader
  separado ou deixe fora do escopo inicial.

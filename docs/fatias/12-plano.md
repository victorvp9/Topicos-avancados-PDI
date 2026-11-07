# Fatia 12 — StatsBomb 360: o simulador contra a visibilidade real de broadcast

Data: 2026-11-07. Frente aprovada pelo Victor. G2 é meu, por delegação.

**Rótulo: validação externa, descritiva.** Não há parâmetro livre, não se
recalibra o simulador e não há F1. Mede-se se o simulador acerta a visibilidade
**no instante dos eventos**, que é onde ele foi reprovado (R10, item 4: a
validação 5(a)) e onde a degradação se concentra (R10, item 2).

## 1. O dado (inspeção do orquestrador, 2026-11-07)

- **Fonte:** `github.com/statsbomb/open-data`. Termos: citar a StatsBomb como
  fonte e usar o logo (README, "Terms & Conditions").
- **Competição, fixada agora:** FIFA World Cup 2022 (`competition_id` 43,
  `season_id` 106). Tem 360 nos dados abertos.
- **Formato:**
  - `three-sixty/<match>.json`: uma entrada por evento com 360, contendo
    `event_uuid`, `visible_area` (polígono, em jardas, campo de 120 × 80) e
    `freeze_frame` (jogadores **visíveis** no quadro, com `teammate`, `actor`,
    `keeper` e `location`).
  - `events/<match>.json`: os eventos. Bolas paradas são `Pass` com
    `pass.type` ∈ {Throw-in, Free Kick, Goal Kick, Corner, Kick Off}.
  - Exemplo, jogo 3857276: 3388 eventos e 2873 entradas 360.
- **Evento sem entrada 360:** tratado como "sem imagem utilizável" (replay, close,
  corte). É **hipótese**: o README não diz por que um evento fica sem 360. Por
  isso é reportado como proxy de apagão, nunca como apagão medido.

## 2. Medidas (definidas antes de olhar)

### 2.1 Por tipo
Os tipos são: passe em jogo corrido (`pass.type` ausente ou Recovery /
Interception), lateral, tiro livre, tiro de meta, escanteio e pontapé inicial.
Medem-se, nos 64 jogos:
1. a fração de eventos **sem entrada 360**;
2. com entrada 360:
   - a distribuição do número de jogadores visíveis (percentis 5/25/50/75/95);
   - a fração com 0 visíveis;
   - a fração em que o `actor` aparece no `freeze_frame`;
   - a área de `visible_area` como fração do campo.

### 2.2 O mesmo no simulador
Nos eventos da Metrica: passe no quadro anotado, bola parada no primeiro quadro
vivo (âncora `frame`). Níveis B5–B8 e A5–A8, `rep` 0–4, os 3 jogos, com as
sementes da rodada final. Medem-se:
- a fração em apagão total;
- a distribuição do número de visíveis;
- a fração com o executor visível.

Nenhum simulador novo: usa-se `broadcast` como está, congelado na tag `final`.

### 2.3 A comparação
Tabelas lado a lado por tipo. A leitura é escrita **antes** de medir:
- **Validação externa do item 2 da R10:** se no broadcast real a fração "sem 360"
  ou com poucos visíveis for maior nas bolas paradas que nos passes, a
  concentração dos apagões nos reinícios é um traço real, e não só do simulador.
- **Teste do item 4:** se o executor no 360 aparecer menos do que no simulador
  com taxa parecida, confirma-se que o simulador mostra demais a ação, e que a
  perda medida no projeto é otimista.
- **Qual nível do simulador** se parece com a Copa de 2022 no instante dos
  eventos, só como descrição.

## 3. Implementação (codificador)
- **Dados:** download para `data/statsbomb/wc2022/`, com o ok do Victor, nos
  moldes do IDSSE. O orquestrador baixa, com sha256.
- **Código:** `src/io/statsbomb.py` (leitura) e o modo `--statsbomb360`, com as
  saídas em `outputs/statsbomb360/`. A parte do simulador fica em
  `--visibilidade-eventos`, que reusa `broadcast`, `reconstruct` e o gabarito.
- **Testes obrigatórios:**
  1. Um JSON sintético dá as contagens certas, inclusive um evento sem 360.
  2. A área do polígono está certa num caso conhecido.
  3. O tipo de bola parada vem de `pass.type`, e o passe em jogo corrido exclui
     os 5 tipos.
  4. A parte do simulador reproduz, em B8 `rep` 0, a fração em apagão de
     `outputs/exploratorio/apagao.csv`, onde ela existir.

## 4. Fora
Recalibrar o simulador com o 360. Usar o 360 como gabarito de evento.

## 5. Detalhes fixados antes do código (2026-11-07, orquestrador)

Estes detalhes completam as §2 e §3 e foram decididos sem ver nenhum número do 360.

- **Eventos StatsBomb no escopo:** só os de `type.name` = `Pass`.
  - O tipo vem de `pass.type.name`. `Throw-in`, `Free Kick`, `Goal Kick`,
    `Corner` e `Kick Off` viram lateral, tiro livre, tiro de meta, escanteio e
    pontapé inicial.
  - Quando `pass.type` falta ou é `Recovery` ou `Interception`, o evento é passe
    em jogo corrido.
  - Qualquer outro `pass.type` faz o código estourar.
  - O pênalti é um `Shot` e fica fora, dos dois lados.
- **Visíveis:** é o número de entradas do `freeze_frame`, contando todos os
  jogadores: companheiros, adversários, o `actor` e os goleiros. No simulador
  vale o mesmo: o número de jogadores com `visible` = True no quadro, goleiros
  incluídos.
- **"Executor no quadro":** há uma entrada com `actor` = true. No simulador, o
  jogador anotado do evento, que é o executor da bola parada, tem
  `visible` = True no quadro.
- **Área visível:** o polígono `visible_area` (pares x, y em jardas) é recortado
  ao campo [0, 120] × [0, 80] por Sutherland–Hodgman, e a área sai pela fórmula
  do cadarço. A fração é a área dividida por 9600. Tudo com a biblioteca padrão
  ou numpy, sem dependência nova.
- **Simulador:**
  - níveis B5–B8 com `rep` 0–4, e A5–A8 só com `rep` 0, porque a variante A é
    determinística (`decisoes.md`, 2026-11-07);
  - sementes `[20261104, jogo, rep]`, as da rodada final da Metrica;
  - eventos: passe principal no quadro anotado e bola parada no primeiro quadro
    vivo (âncora `frame`), nos 6 tipos acima;
  - **"apagão total":** nenhum jogador visível no quadro, a mesma definição da
    Fatia 9;
  - **o detector não roda**.
- **Saídas em `outputs/statsbomb360/`:**
  - `copa2022_por_tipo.csv`: uma linha por tipo, nos 64 jogos;
  - `copa2022_por_jogo.csv`: tipo × jogo;
  - `simulador_por_tipo.csv`: nível × tipo, somado nos 3 jogos e nas
    sementes;
  - `comparacao.csv`;
  - `manifesto.json`, com o commit, `working_tree_sujo`, o sha256 dos JSON
    lidos (pode ser um único hash agregado de `SHA256SUMS.txt` mais a conferência
    dele) e as sementes.
- **Teste 4:** para B6, B7 e B8, com os 5 `rep`, a fração em apagão total do
  passe principal e da bola parada micro tem de bater exatamente com
  `frac_eventos` de `outputs/exploratorio/apagao.csv`. A linha usada é a de
  `frente` = base, `condicao` = reconstruido e `estrato` = apagão. Se o arquivo
  não existir, o teste é pulado com uma mensagem. Os valores esperados
  (`origem-dos-numeros.md`, Fatia 9) são: passe 0,088 / 0,131 / 0,158 e bola
  parada 0,335 / 0,498 / 0,598.
- **Orçamento:** medir o tempo de uma unidade antes de rodar tudo. Se passar de
  2 h de CPU, a decisão vai ao Victor (G4).

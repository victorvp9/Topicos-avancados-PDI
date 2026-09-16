# 03 — Plano de implementação

Oito fatias verticais. Cada uma entrega algo executável e testável. A ordem não é
negociável: **a avaliação vem antes da detecção**, para que exista um número
desde o primeiro dia.

---

### Fatia 1 — Carregar e normalizar (semana 1)
Loader da Metrica → os dois DataFrames de `docs/02-dados.md`.

- Conversão de coordenadas, normalização do sentido de ataque, reamostragem.
- **Teste:** as quatro bandeirinhas de escanteio projetam em `(±52.5, ±34)`;
  a bola no pontapé inicial fica a menos de 1 m do centro.
- **Saída:** `python -m src.run --inspect` imprime um resumo da partida.

### Fatia 2 — Avaliação (semana 1)
Casador de eventos e métricas, **antes de detectar qualquer coisa**.

- Casamento por tipo + janela de 3 s, um-para-um.
- Precisão, revocação, F1 por tipo, com contagem absoluta do gabarito.
- **Teste:** com o gabarito comparado contra ele mesmo, F1 = 1,0 em tudo. Com o
  gabarito deslocado 10 s, F1 = 0. Com metade dos eventos removidos, revocação
  = 0,5.

### Fatia 3 — Posse e estado da bola (semana 2)
Implementa o Passo 1 da especificação.

- Derivação de `viva/morta`. Documente a decisão.
- **Teste:** a soma dos frames com posse + sem posse = total; nenhum frame tem
  dois donos.
- **Saída:** série temporal de posse, visualizável.

### Fatia 4 — Bolas paradas (semana 3)
Pontapé inicial, escanteio, lateral, tiro de meta, e o tiro livre residual.

- Checagem **ordenada** dos padrões; tiro livre é o `else`.
- **Teste:** uma bola posicionada em cada vértice dispara escanteio; no centro,
  pontapé inicial.
- **Marco:** primeira tabela de F1 real. Compare com os números do artigo.

### Fatia 5 — Passes (semana 4)
O evento de maior volume e o que mais vale acertar.

- **Teste:** sequência sintética A → B → C gera exatamente dois passes.
- **Marco:** o "teto" está estabelecido. Fim da primeira metade do projeto.

### Fatia 6 — Simulador de broadcast (semana 5)
O coração da contribuição.

- Frustum 2D que segue a bola, com abertura parametrizável e suavização do
  movimento da câmera (a câmera real não teleporta).
- Marca `visible=False` para quem cai fora; um parâmetro varre a taxa de detecção
  resultante de ~100% a ~35%.
- **Teste:** com abertura infinita, a taxa é 100% e o F1 é idêntico ao da Fatia 5.
- **Calibração:** compare a distribuição de jogadores visíveis por frame com a do
  dataset da SkillCorner.

### Fatia 7 — Reconstrução (semana 6)
Preenche os buracos, como fazem os sistemas reais.

- Interpolação linear como base. Se sobrar tempo, uma segunda estratégia para
  comparar.
- Nunca sobrescreva `visible` — a distinção entre medido e imputado precisa
  sobreviver até o relatório.
- **Teste:** buraco artificial de N frames numa trajetória conhecida; o erro de
  reconstrução cresce com N.

### Fatia 8 — Experimento e relatório (semanas 7-8)
- Varredura em duas dimensões: taxa de detecção x R_pz, por tipo de evento.
- Ajuste do R_pz ótimo numa partida; medição nas outras duas.
- Superfície F1, tabela final, relatório em markdown.
- **Saída:** `python -m src.run --all` reproduz tudo do zero.

---

## Estrutura

```
.
├── CLAUDE.md
├── config.yaml              # todas as constantes, cada uma com origem citada
├── docs/
│   ├── 00-problema.md
│   ├── 01-definicoes.md
│   ├── 02-dados.md
│   ├── 03-plano.md
│   └── decisoes.md          # log; uma linha por decisão
├── data/                    # gitignored
├── src/
│   ├── io/                  # loaders
│   ├── possession.py
│   ├── events/              # um módulo por família de evento
│   ├── broadcast.py         # simulador de visibilidade
│   ├── reconstruct.py
│   ├── evaluate.py
│   └── run.py
├── tests/
└── outputs/                 # tabelas e figuras geradas
```

## Folga

Seis semanas de trabalho num prazo de oito. A folga não é para adicionar escopo —
é para o Jogo 3 da Metrica estar num formato diferente, para o sinal de `y` estar
invertido, e para a derivação do estado da bola dar mais trabalho do que parece.

## Se atrasar, corte nesta ordem

1. A segunda estratégia de reconstrução (Fatia 7).
   (A varredura de R_pz nunca se corta — é a pergunta do projeto.)
2. A calibração contra a SkillCorner (Fatia 6) — vira trabalho futuro.
3. Passes (Fatia 5). Doloroso, mas bolas paradas sozinhas já respondem a
   pergunta do projeto.

Nunca corte a Fatia 2. Sem avaliação, não há projeto.

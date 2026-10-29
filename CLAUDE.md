# CLAUDE.md

## O que é este projeto

Mede quanto da detecção automática de eventos de futebol sobrevive à degradação
típica do vídeo de broadcast. Implementa o algoritmo determinístico de
Vidal-Codina et al. (2022), roda sobre tracking completo (Metrica), depois sobre
o mesmo tracking degradado por um simulador de visibilidade de câmera, e compara
o F1 por tipo de evento em função da taxa de detecção.

Entregável: sistema funcionando, rodável com um comando, que produz uma tabela de
resultados e as figuras.

## Leia antes de qualquer coisa

- `docs/00-problema.md` — o quê e o porquê
- `docs/01-definicoes.md` — **especificação normativa** dos eventos
- `docs/02-dados.md` — esquemas, unidades, sistemas de coordenadas
- `docs/03-plano.md` — fatias de implementação, em ordem

## Regra de ouro

**Nenhuma definição de evento pode ser inventada.** Toda regra de detecção vem de
`docs/01-definicoes.md`, que por sua vez vem do artigo. Se uma situação não estiver
coberta, PARE e pergunte — não improvise uma heurística. Na literatura desta área,
erro de definição é a principal fonte de erro, não erro de algoritmo.

Se você precisar de uma constante nova (um raio, um limiar, uma janela), ela vai
para `config.yaml` com um comentário citando a origem. Nunca hardcode.

## Stack

- Python 3.11+, `uv` para dependências
- pandas, numpy, scipy, matplotlib, pytest
- Sem frameworks de ML. Se você achar que precisa de um, está resolvendo o
  problema errado.
- CLI com argparse ou typer. Um ponto de entrada: `python -m src.run`

## Convenções

- Unidades internas sempre em **metros** e **segundos**. Conversão acontece só na
  camada de I/O, nunca no meio do pipeline.
- Sistema de coordenadas interno: origem no centro do campo, x no sentido do
  comprimento, y no sentido da largura. Cada loader converte para isso.
- Toda função que transforma dados recebe e devolve DataFrame com esquema
  documentado no docstring.
- Nomes de variáveis em inglês, comentários e docs em português.

## O que NÃO fazer

- Não criar camadas de abstração antes de ter dois casos de uso reais.
- Não escrever wrapper de biblioteca padrão.
- Não adicionar dependência sem justificar em `docs/decisoes.md`.
- Não mexer em `data/` — é somente leitura, e está no `.gitignore`.
- Não "consertar" um resultado ruim ajustando o gabarito. Se o F1 está baixo,
  investigue e reporte; número ruim é resultado, não bug.

## Fluxo de trabalho

1. Antes de codar uma fatia, escreva o plano e espere aprovação.
2. Uma fatia por vez, cada uma com teste.
3. `pytest` tem que passar antes de seguir.
4. Registre decisões não óbvias em `docs/decisoes.md` (uma linha, com a razão).
5. Quando tomar um atalho consciente, marque com `# TODO(divida):` e a razão.

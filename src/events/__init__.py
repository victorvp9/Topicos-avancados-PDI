"""Passo 2 da especificacao: deteccao de bolas paradas.

Divisao dos modulos, na ordem em que o algoritmo decide:

  `gatilhos`    configuracao espacial DOS JOGADORES no intervalo de bola morta;
  `padroes`     o primeiro quadro em jogo, com a bola;
  `hierarquia`  a ordem principal (Fig. 5, p. 7) e a reserva do suplementar S1;
  `bola_parada` orquestra os tres e emite a tabela de deteccoes.

Regra normativa: `docs/01-definicoes.md`, Passo 2 inteiro. Nenhuma constante
aqui: tudo vem de `config.yaml:bola_parada`, `config.yaml:campo` e
`config.yaml:posse` (o `R_pz` do padrao).
"""

# Adendo ao briefing do orquestrador (29/10/2026)

Prevalece sobre docs/briefing-orquestrador.md onde divergir.

## Modo de trabalho
Substitui "Como trabalhamos" e "Primeiros passos" do briefing.
O orquestrador roda dentro do Claude Code como sessão principal (agente `orquestrador`). Ele delega a implementação ao subagente `codificador` e a verificação ao subagente `revisor`. Não há mais blocos "Resposta para colar". O Victor responde nos portões definidos no agente. Os PDFs estão em refs/.

## Respostas do Victor (28/10)
- Prazo: não importa. O 03-plano vale como ordem, não como calendário.
- O repositório tinha só os documentos. Dados não baixados.
- Os docs do projeto no claude.ai são a versão atual dos que estão no repositório.

## Conferido em 28/10
- Savitzky-Golay de 2ª ordem, janela de 7 quadros: Vidal-Codina, seção 2.3.1, p. 5.
- 3 min por partida, 1 CPU, 4 GB: Vidal-Codina, seção 3, p. 9.
- Significado dos ε (seções 2.3.2 a 2.3.4, pp. 5–6):
  - ε_s: deslocamento da bola de f para f+1.
  - Ganho de posse se d0_f0 · d1_fn < ε_θ. Usar vetores unitários e declarar.
  - ε_k1: tolerância de "cada um no seu campo".
  - ε_k2: distância de pelo menos um jogador ao ponto central.
  - ε_c: distância à marca de escanteio.
  - ε_t: define a linha lateral auxiliar.

## Novos achados (V12–V16) e D10
V12. ε_f (= 1 m, suplementar S4.2, p. 8) não é tolerância de tiro livre. É o deslocamento máximo do jogador que ativa o padrão de tiro livre antes de passar a bola, no fluxo de erros de tracking (S1, p. 1, Fig. S1). Corrige V11.

V13. PZ de bola parada.
- O Mills, seção 2.2 (p. 4), fala em PZ específica de bola parada com outro conjunto de hiperparâmetros. É dali que vem o texto do docs/01, inclusive o escanteio "até 3 m" e a descrição do pontapé inicial.
- O Vidal-Codina, seção 2.4.1 (p. 7), só exige a bola dentro de R_pz do executor no primeiro quadro em jogo (o mais próximo, se houver vários) e não dá outro raio.
- Decisão do Victor (28/10): seguir o Vidal-Codina e registrar a divergência em decisoes.md. O plano deve dizer que varrer R_pz também afeta as bolas paradas.

V14. Gatilho de tiro de meta: a seção 2.3.4 (p. 6) escreve ε_c para a tolerância da pequena área, mas a legenda da Fig. 4 (p. 6) e o S4.2 usam ε_g. Tratar como erro de digitação, usar ε_g = 0,5 m e declarar.

V15. Estado da bola.
- A seção 2.3.4 (p. 6) define o gatilho de bola morta por booleano ou pela ausência de dado da bola.
- A seção 2.1 (p. 3) diz que o Tracab traz o booleano; Track160 e Hawk-Eye sinalizam o jogo parado indiretamente, pela falta de dado da bola.
- Se a bola da Metrica for NaN exatamente nas bolas mortas, D1 usa o mesmo mecanismo dos provedores A e C. Conferir nos dados antes de decidir.

V16. Passe.
- O algoritmo rotula como passe toda perda de posse que não é finalização nem cruzamento, inclusive interceptada ou que sai (seção 2.4.3, p. 9). O docs/01 ("ganho de B, mesmo time") está errado.
- Na Metrica (PDF de definições, lista de tipos), PASS é só passe completo; passe errado vira BALL LOST ou BALL OUT.
- Tiro de meta no gabarito = Attempt GOAL KICK em PASS, BALL LOST ou BALL OUT (aprovado pelo Victor).
- O "[OK]" do escanteio de 3 m no docs/01 vem do S4.2 (p. 8) e do Mills, não do texto principal do Vidal-Codina.

D10. Critério de passe, a fechar e congelar no G1.
- Principal: "passe completo", isto é, o passe detectado cujo próximo ganho é de companheiro contra o PASS da Metrica.
- Secundário: "todo evento de passe", PASS ∪ BALL LOST ∪ BALL OUT, sem finalização.
- Excluir THEFT do secundário é proposta, a decidir com as contagens reais.

## Leituras pendentes antes do G1
Mills (além da 2.2), Bassek, Crang e FOOTPASS, por inteiro. A lista "AINDA NÃO CONFERIDO" do briefing continua valendo, exceto Savitzky-Golay e o texto principal do Vidal-Codina, que já foram lidos.

## Próximo passo: baixar e inspecionar a Metrica (sem implementar)
- Download e integridade:
  - git clone --depth 1 https://github.com/metrica-sports/sample-data data/metrica-sample-data
  - Registrar o hash do commit e o sha256 de cada arquivo.
  - Parar se algum arquivo for ponteiro de Git LFS.
- Python só em ambiente efêmero: uv run --no-project --with pandas, com script por stdin ou em pasta temporária fora do repositório.
- Jogos 1 e 2, tracking:
  - cabeçalhos crus e colunas;
  - frequência real e buracos na numeração de quadros;
  - faixas de x e y;
  - existe coluna de z da bola ou de estado vivo/morto?
- Jogos 1 e 2, bola e jogadores:
  - NaN da bola: fração, sequências e durações;
  - fração de quadros com bola fora de [0,1];
  - NaN por jogador e número de jogadores visíveis por quadro.
- Jogos 1 e 2, eventos:
  - tabela Type × Subtype completa, com as strings cruas;
  - evento seguinte a cada SET PIECE (tipo, mesmo jogador, Δquadro);
  - GOAL KICK por Type;
  - BALL LOST e BALL OUT por subtipo;
  - sincronia entre Start Frame e os quadros do tracking.
- Diagnóstico NaN da bola × eventos (só para decidir D1; nunca vira regra do algoritmo):
  - tipo do evento antes e depois de cada sequência de NaN ≥ 1 s;
  - para cada SET PIECE e GOAL KICK, se houve NaN nos 2 s anteriores;
  - sequências de NaN ≥ 1 s sem BALL OUT, FAULT RECEIVED ou SHOT antes.
- Jogo 3:
  - arquivos;
  - metadados (frequência, dimensões do campo);
  - estrutura do JSON de eventos com contagem de tipos (json da biblioteca padrão);
  - formato do tracking;
  - é legível sem kloppy?
- Resultado em docs/inspecao-metrica.md.

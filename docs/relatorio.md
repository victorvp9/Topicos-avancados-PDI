# Relatório — Quanto da detecção de eventos sobrevive ao broadcast?

Data: 2026-11-05. Rodada final única no commit `48224e0` (código e config da tag
`pre-rodada-final`), 60 min de parede, revisada de forma independente. Todo número
abaixo vem de `outputs/` e tem linha em `outputs/origem-dos-numeros.md` (seção
"Fatia 8b"); números da literatura vêm das seções "Literatura" do mesmo arquivo.

**Rótulos.** *Limpo* = produzido pela rodada final conforme as regras
pré-registradas em `docs/fatias/08-plano.md` (§2 e emenda §8, escritas antes de
qualquer F1 degradado). *Exploratório* = qualquer coisa decidida depois de ver o
resultado. Tudo neste relatório é limpo, salvo onde está escrito
**EXPLORATÓRIO**. As frases marcadas como *leitura* são interpretação minha dos
números limpos, não regra.

---

## 1. A pergunta e a resposta

> Aumentar o raio da zona de posse (`R_pz`) compensa a perda de taxa de detecção?
> Até que ponto, e para quais tipos de evento? (`docs/00-problema.md`)

A resposta pré-registrada vem só da condição `reconstruido` (tracking degradado
pelo simulador e reconstruído por interpolação linear), variante B (frustum com
cortes editoriais), níveis B5 e B8, alvos primários (bola parada micro e passe
principal), critério estrito, âncora `frame`. `R_pz` escolhido por
leave-one-game-out (LOGO) com a regra da §8; λ = 0,01.

| nível (taxa amostrada sem GK) | alvo | F1 em `R0` = 0,5 m | `R*` por jogo de teste (1/2/3) | Δ agregado | Δ no nível 1 | ajuda | **compensa** | fração recuperada |
|---|---|---|---|---|---|---|---|---|
| B5 (0,532) | bola parada | 0,595 | 0,5 / 1,0 / 2,0 | 0,000 | 0,000 | não | **não** | — |
| B5 (0,532) | passe | 0,891 | 1,0 / 1,0 / 1,0 | 0,0096 | 0,0096 | não (Δ < λ) | **não** | — |
| B8 (0,368) | bola parada | 0,386 | 2,0 / 3,0 / 2,5 | 0,020 | 0,000 | sim | **sim** (margem pequena) | 0,092 |
| B8 (0,368) | passe | 0,799 | 1,0 / 1,0 / 1,0 | 0,0141 | 0,0096 | sim | **não** | 0,140 |

Fontes: `outputs/experimento/tabelas/tabela1.csv` (F1 e taxa) e `tabela2.csv` /
`selecao_logo.csv` (LOGO). Δ = F1 de teste em `R*` menos F1 de teste em `R0`,
somando contagens dos 3 jogos e 5 sementes antes de dividir.

**Controle da deriva do rótulo de tempo (descritivo, não é regra):** com o
critério `vidal_codina` (jogador anotado, ±10 s), o passe em B8 vai de 0,805 em
`R0` para 0,820 em 1,0 m (+0,015), e no nível 1 de 0,898 para 0,908 (+0,010). O
excesso, 0,005, também fica abaixo de λ: o "não compensa" do passe não é
artefato da janela de ±1 s (`pontos.csv`, critério `vidal_codina`, passe
principal, somado sobre jogos e sementes).

**Resposta, em uma frase:** aumentar `R_pz` **não compensa** em B5 (onde quase
nada se perde) e, em B8, **compensa só para bola parada, e pouco**: recupera
cerca de 9 % do F1 perdido (0,386 → 0,406, contra 0,598 sem degradação). Para
passe, o ganho em B8 (+0,014) é quase todo o mesmo ganho que `R_pz` = 1 m já dá
sem degradação (+0,010); o excesso fica abaixo de λ, logo não é compensação da
degradação.

**Cautelas obrigatórias sobre o "sim":**
- A margem é pequena: o excesso sobre o nível 1 é 0,0196 contra λ = 0,01, e o
  erro-padrão de 5 sementes medido no piloto para esse alvo foi 0,0073
  (`outputs/experimento/piloto.csv`). O "sim" vale pela regra, não por folga.
- **A composição das detecções muda com `R_pz`** (confundimento registrado em
  2026-11-02): em B8, bola parada, as detecções com motivo "sem passe do
  executor" sobem de 243 em `R0` para 392 em `R_pz` = 2,0 m e 538 em 3,0 m,
  enquanto as "sem padrão de tiro livre" caem de 975 para 705 e 565
  (`tabela3.csv`, `reconstruido` B8). Parte do ganho vem do acoplamento com a
  revocação de perda do Passo 1, não só da geometria do gatilho.
- Leitura: a hipótese do Vidal-Codina et al. (aumentar `R_pz` em tracking de
  qualidade inferior) recebe, aqui, apoio fraco e restrito a bola parada; a
  maior parte da perda não é recuperável por esse parâmetro.

## 2. Quanto se perde

Tabela 1 (`tabela1.csv`; `reconstruido`, estrito, `R0` = 0,5 m; contagens
somadas sobre jogos e sementes; mín.–máx. por jogo entre parênteses):

| alvo | sem degradação | B5 | B8 | A8 |
|---|---|---|---|---|
| passe principal | 0,891 (0,864–0,912) | 0,891 | 0,799 (0,776–0,822) | 0,891 |
| bola parada micro | 0,598 (0,593–0,608) | 0,595 | 0,386 (0,367–0,405) | 0,564 |
| lateral (n = 110) | 0,912 | 0,916 | 0,652 | 0,916 |
| escanteio (n = 26) | 0,762 | 0,762 | 0,633 | 0,762 |
| pontapé inicial (n = 18) | 0,971 | 0,941 | 0,560 | 0,364 |
| tiro de meta (n = 49) | 0,396 | 0,350 | 0,241 | 0,346 |
| tiro livre (n = 92) | 0,500 | 0,500 | 0,275 | 0,476 |

- **Passe:** em B8 a precisão quase não muda (0,967 → 0,970) e a revocação cai
  (0,825 → 0,680). O detector perde passes, não inventa.
- **Bola parada:** caem as duas (precisão 0,482 → 0,311, revocação 0,786 →
  0,508); o tiro de meta passa de 133 detecções por 49 reinícios no teto para
  1064 por 245 (5 sementes) em B8.
- **Leitura — nos alvos primários, a perda só aparece quando entram os
  cortes.** Em B2 a B5 (só o
  frustum estreita, `c` = 0) o F1 dos dois alvos primários fica igual ao do
  teto, ou a 0,003 dele; a queda começa em B6, o primeiro nível com cortes
  editoriais (bola parada 0,479, passe 0,841), e segue em B7 e B8. A variante A
  (janela fixa, sem cortes) fica no passe a no máximo 0,0002 do teto até A8 e
  perde pouco em bola parada (0,598 → 0,564). Para os dois alvos primários,
  neste simulador, o que derruba a detecção é o apagão do quadro, não o campo
  de visão estreito. **Não vale para todo tipo:** sem cortes, o pontapé inicial
  cai para 0,364 e o tiro de meta para 0,346 em A8.
- **A reconstrução nem sempre ajuda.** Contra o tracking degradado sem
  reconstrução (`bruto`, secundário), `reconstruido` melhora B8 em bola parada
  (0,386 contra 0,327) e quase nada em passe (0,799 contra 0,795), mas **piora**
  A8 em bola parada (219 acertos contra 232; `bruto` A8 = teto) e B5 marginalmente
  (1155 contra 1160) (`tabela5.csv`, condição `bruto`). Leitura, **não
  verificada**: a interpolação pode pôr jogadores imputados dentro de zonas de
  padrão onde eles não estavam. Não investiguei caso a caso.
- **Pontapé inicial em A8 cai para 0,364** (4 de 18), enquanto o passe em A8
  fica igual ao teto. n = 18; leitura não verificada: a janela de 32 m centrada
  na bola corta parte do meio-campo exigido pelo padrão.

Comparação com a literatura, só como ordem de grandeza (dados, feeds e gabaritos
diferentes; no Mills a bola também é degradada, aqui não): o Mills et al. 2026
reporta média de 0,78 em passes e cruzamentos no PGM e 0,57–0,62 em tiro livre,
lateral e tiro de meta (Resultados, p. 7). Nosso B8 (taxa sem GK 0,37, dentro da
faixa do PGM no Crang, 0,36–0,42) dá 0,80 em passe.

## 3. Resultados secundários

- **Tiro livre no nível 1:** `R_pz` maior já "ajuda" sem degradação (Δ agregado
  +0,134, `tabela2.csv`). É a maior sensibilidade a `R_pz` de todas as linhas,
  mas é alvo secundário, e não entra na resposta.
- **`bruto` em B8:** passe Δ 0,0092 (Δ_g > 0 nos 3 jogos, mas abaixo de λ:
  não ajuda pela regra), bola parada Δ −0,0005 (não ajuda).
- **Raio do escanteio `ε_c` (R7, baixa confiança, sem ótimo escolhido):** em
  `ε_c` = 3 m (valor do artigo) a curva reproduz o teto; o escanteio estrito,
  3 jogos, vai de 4 acertos em 1 m a 25 em 8 m, em 26 escanteios
  (`tabela4.csv`). **Jogo 3, à parte (o único não visto no desenvolvimento): 8
  escanteios de 3 cobradores**; acertos 0 / 4 / 4 / 5 / 7 / 8 / 8 para
  `ε_c` = 1 / 2 / 3 / 4 / 5 / 6 / 8 m, com 0 / 4 / 4 / 5 / 8 / 10 / 11
  detecções. O limpo continua sendo `ε_c` = 3 m.
- **Decomposições (R9):** em cada ponto, motivos das detecções, via de detecção
  (padrão ou reserva), causa de cada FN e estado do executor (visível, imputado,
  ausente) no quadro anotado (`tabela3.csv`). Em `reconstruido` não há executor
  ausente; em `bruto` há. Diagnóstico (h): nenhuma distância jogador–bola
  reconstruída cai exatamente num valor da grade de `R_pz`, em nenhuma unidade
  (coluna `n_dist_igual_grade` = 0).
- Critérios `vidal_codina` e `mills`, `R_dz` fixo em 1 m, sem lacuna 5, âncora
  anotada: `tabela5.csv`. P/R/F1 vêm sempre da diagonal da matriz de confusão
  (`tp_diag`); a coluna `tp` dos outros critérios é diagnóstica.

## 4. Declarações obrigatórias (R10)

1. **Bola perfeita e estado da bola oráculo** (D2, D1b). Só os jogadores são
   degradados; a bola e o vivo/morto vêm do tracking completo. No broadcast real
   a bola também some e erra (Mills: RMSE da bola 3,5 a 16,2 m). Os números
   degradados são, por isso, um limite **superior**.
2. **A degradação é correlacionada com os eventos.** Os episódios fora do ar
   duram em média 13,3 s e, como os cortes vêm da bola morta, concentram-se logo
   depois dos reinícios: onde estão as bolas paradas e os primeiros passes
   (`origem-dos-numeros.md`, Fatia 6).
3. **A calibração dos cortes usou as âncoras de lateral dos 3 jogos,** inclusive
   as dos jogos de teste do LOGO: 3 escalares, sem detector. Vazamento pequeno,
   declarado.
4. **A validação 5(a) foi reprovada.** No simulador, quem corre fica visível mais
   do que no Bassek (em B8, a fração visível da distância em alta velocidade
   excede a da distância total em +0,18 a +0,32 nos jogadores de linha, contra
   −0,04 a +0,09 no Bassek). O simulador mostra demais o jogador perto da ação,
   logo **a queda de F1 medida tende a ser otimista**.
5. **Desvios conhecidos do simulador:** B5 sem GK 0,532, abaixo da faixa da
   Camera 1 no Crang (0,56–0,64); ≥ 9 jogadores por time visíveis em 7 % do tempo
   em B8 contra ~20 % no Bassek; resíduos estruturais de −11 e +9,6 pontos nos
   alvos de corte em bola morta e na âncora de lateral.
6. **A interpolação recupera só 54 % da distância percorrida** pelos jogadores
   imputados em B8 (25 % em alta velocidade).
7. **A pergunta Bassek × Mortensen e Bornn fica sem resposta sobre o mundo.**
   Este simulador não a decide (item 4).
8. **Em A8 o passe é igual ao teto** (2187/2262/2650): a janela centrada na bola
   nunca tira o passador. A bola parada em A8 `reconstruido` **não** é igual ao
   teto (219 contra 232), por causa da reconstrução (§2).
9. **Duas convenções de F1.** Na Fatia 8, F1 = 2tp/(n_det + n_gab), que vale 0
   quando não há detecção e há gabarito; as tabelas das Fatias 2 a 5 dão NaN
   nesse caso. Só difere em casos de borda (`free_kick?` com n_gab = 0). O
   pênalti (n = 1) tem F1 NaN e fica na tabela.

## 5. O que não foi feito

Segunda estratégia de reconstrução; bola degradada; recalibrar o simulador;
eventos fora do escopo (finalização, defesa); suavização da bola. Nenhuma regra
foi mudada depois da rodada final.

## 6. Como reproduzir

`uv run python -m src.run --all` (≈ 1 h com 2 workers nesta máquina; 16 GB de
RAM). Sementes efetivas `[20261104, jogo, rep]` e commit no
`outputs/experimento/manifesto.json`. `uv run pytest` (560 testes).
Figuras: `outputs/experimento/figuras/figura1.png` (F1 × taxa amostrada, um
ponto por semente) e `figura2.png` (F1 por taxa × `R_pz`, mapa de calor). **O
eixo de taxa das figuras usa a taxa com todos os jogadores, GK incluído**
(B8 0,34), enquanto o texto usa a taxa sem GK (B8 0,368); o nível é o mesmo.

---

## Apêndice — EXPLORATÓRIO: onde a detecção se perde, e duas correções

Tudo aqui foi decidido **depois** de ver a rodada final, nos mesmos 3 jogos
(`docs/analise-alternativas.md`, plano `docs/fatias/09-plano.md`). Nada substitui
os números das §1 a §4. Pontos medidos: `R0` = 0,5 m, estrito, `frame`, lacuna 5
com, condição `reconstruido`, 5 sementes em B. Fonte: `outputs/exploratorio/`
(`pontos.csv`, coluna `frente`; `apagao.csv`). A linha base reproduz
`outputs/experimento/pontos.csv` linha a linha.

**A. Dentro e fora do apagão total** (nenhum jogador visível no quadro de
referência). Revocação pelo estrato do evento; precisão pelo estrato do quadro da
detecção. Nenhum evento é excluído.

| B8 | estrato | fração dos eventos | revocação | precisão |
|---|---|---|---|---|
| passe principal | apagão | 0,158 | 0,004 (8/2094) | 0,889 (8/9) |
| passe principal | fora | 0,842 | 0,807 (9000/11156) | 0,970 |
| bola parada micro | apagão | 0,598 | 0,367 (324/882) | 0,295 |
| bola parada micro | fora | 0,402 | 0,717 (425/593) | 0,325 |

Fração de eventos em apagão: passe 0,088 / 0,131 / 0,158 e bola parada 0,335 /
0,498 / 0,598, em B6 / B7 / B8. Em B5, A8 e no teto, zero.

**Leitura:** na variante B, a perda de passe é quase exatamente a fração de passes
que cai num apagão: ali o detector fica cego. A bola parada sofre mais porque os
apagões se concentram depois dos reinícios (R10, item 2). Fora do apagão, a
revocação do passe (0,807) fica perto da do teto (0,825). Mas as populações
diferem: os eventos fora do apagão não são uma amostra aleatória, e não medi o
teto restrito aos mesmos eventos.

**B. Controle "a bola some no corte"** (bola NaN no apagão, `ball_live` oráculo).
Em B8, o passe vai de 0,799 a 0,795 e a bola parada de 0,386 a 0,378. A perda é
pequena **porque o detector já quase não acerta nada no apagão**. Isto não valida
o D2: a bola fora do apagão continua perfeita, e o `ball_live`, oráculo.

**C. Problema 2 do S1 por visibilidade.** Bola parada em B8 de 0,386 a 0,390 (+8
acertos); idêntico no teto e no `bruto`. Imaterial (abaixo de λ = 0,01).

**D. A supressão de bola parada exige a perda do executor.** Passe no teto de
0,891 a 0,901 (2187 → 2236 acertos; **muda o teto**), em B5 de 0,891 a 0,905, em
B8 de 0,799 a 0,825. O excesso sobre o ganho do teto, em B8, é 0,015. Por estrato,
em B8, os acertos sobem de 9000 para 9470 fora do apagão e de 8 para 43 dentro.
**Leitura:** D corrige um erro da regra de supressão decidida em 2026-11-01
([LACUNA] do plano 05), que já custava cerca de 1 ponto no teto e custa mais sob
degradação, porque o passe real do reinício some e a regra "come" o passe
seguinte. **D não recupera o apagão.** A regra foi escolhida depois de ver os FN;
por isso fica no apêndice, não no resultado limpo.

**Conclusão do apêndice:** com os dados deste projeto, nenhuma alternativa
legítima recupera o que se perde nos apagões. O limite da detecção, sob broadcast
com cortes, é a fração de eventos que cai num corte. A regra D vale como correção
do detector em qualquer condição, a confirmar em dado novo.

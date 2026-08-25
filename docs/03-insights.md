# 03 — Catálogo de insights (Camada 2)

Regra de ouro do projeto: **o insight é produzido por algoritmo de grafo (determinístico);
o LLM apenas verbaliza e recupera.** Cada padrão gravado carrega `algoritmo_origem`.

Todos os exemplos abaixo são **saídas reais** das partidas ingeridas (Copa 2022:
final 3869685, semifinal 3869519, quartas 3869354), copiados da execução de
`scripts/run_analysis.py`. Total gerado: 73 padrões (24 + 22 + 27).

---

### 7.1 O pivô invisível
- **Pergunta que responde:** qual jogador é o gargalo estrutural da progressão do time,
  mesmo sem aparecer nas estatísticas?
- **Por que não é visível nos dados brutos:** a tabela mostra passes por jogador; volume
  e betweenness não são correlacionados. Um zagueiro pode ter 90 passes estéreis e um meia
  com 30 concentrar a passagem obrigatória da rede.
- **Estrutura de grafo usada:** rede de passes do time, direcionada, agregada por par,
  custo `1/(1+xT)` (projeção `pass_network`).
- **Algoritmo:** `gds.betweenness.stream` (+ `gds.pageRank.stream` como contraste no texto
  do padrão, para mostrar que medem coisas diferentes).
- **Cypher:**
  ```cypher
  CALL gds.betweenness.stream('passnet', {relationshipWeightProperty: 'cost'})
  YIELD nodeId, score
  RETURN gds.util.asNode(nodeId).nome AS nome, score ORDER BY score DESC
  ```
- **Saída (PadraoTatico):** `tipo="pivo_estrutural"`, `nome_metrica="betweenness_centrality"`,
  `algoritmo_origem="gds.betweenness.stream"`.
- **Exemplo real observado na final:** *"Nicolás Otamendi é o gargalo estrutural da
  progressão de Argentina: betweenness 50.0 (2º colocado: 25.0), com 143 ações e pageRank
  1.622"* — betweenness 2x o segundo colocado; pelo pageRank (volume/prestígio) ele não se
  destaca na mesma proporção, que é exatamente a diferença que o insight captura. Para a
  França: Jules Koundé (40.0 contra 25.0).

---

### 7.2 Padrão do terceiro homem
- **Pergunta que responde:** quais combinações de três jogadores se repetem para quebrar linhas?
- **Por que não é visível:** no parquet são linhas separadas sem coluna que as ligue; o
  padrão só existe navegando A→B→C dentro da mesma fase de posse com progressão de faixa.
- **Estrutura:** caminhos de 2 arestas `PASSOU_PARA` com `fase_posse_id` igual, quase
  consecutivas (`Δaction_id ≤ 3`, tolerando uma condução no meio), com
  `faixa(zona_destino_2) > faixa(zona_origem_1)`.
- **Algoritmo:** Cypher puro (padrão de caminho + contagem de recorrência); sem GDS.
- **Cypher:**
  ```cypher
  MATCH (a:Jogador)-[p1:PASSOU_PARA {match_id: $m}]->(b)-[p2:PASSOU_PARA {match_id: $m}]->(c)
  WHERE p1.fase_posse_id = p2.fase_posse_id
    AND p2.action_id > p1.action_id AND p2.action_id - p1.action_id <= 3
    AND a <> b AND b <> c AND a <> c
    AND (p2.zona_destino / 8) / 4 > (p1.zona_origem / 8) / 4
  RETURN a.nome, b.nome, c.nome, count(*) AS n ORDER BY n DESC
  ```
- **Saída:** `tipo="terceiro_homem"`, `valor_metrica=n_ocorrencias`.
- **Exemplo real (final):** *"Trio recorrente de quebra de linha de Argentina: Rodrigo De
  Paul -> Lionel Messi -> Ángel Di María (2x, xT acumulado 0.021)"*.

---

### 7.3 Gatilho de pressão
- **Pergunta que responde:** o que exatamente dispara a pressão do adversário?
- **Por que não é visível:** pressões são centenas de linhas com timestamp; a regra só
  aparece cruzando a ação imediatamente anterior a cada pressão numa janela temporal.
- **Estrutura:** para cada `PRESSIONOU`, o `PASSOU_PARA` mais recente para o time
  pressionado no mesmo período em até 8 s; agregação por (faixa, corredor) da zona de
  destino do passe; taxa = pressões disparadas / passes para a região.
- **Algoritmo:** Cypher com janela temporal + agregação.
- **Cypher (núcleo):**
  ```cypher
  MATCH (presser:Jogador)-[pr:PRESSIONOU {match_id: $m}]->(alvo)
  MATCH (:Jogador)-[p:PASSOU_PARA {match_id: $m}]->(recebedor)
  WHERE recebedor.time = alvo.time AND p.periodo = pr.periodo
    AND p.minuto <= pr.minuto AND pr.minuto - p.minuto <= $janela
  WITH pr, p ORDER BY p.minuto DESC
  WITH pr, head(collect(p.zona_destino)) AS zona_gatilho
  RETURN zona_gatilho, count(*) AS disparos
  ```
- **Saída:** `tipo="gatilho_pressao"`, `nome_metrica="taxa_disparo_pressao"`.
- **Exemplo real (final):** *"Argentina dispara pressão quando a bola chega ao corredor
  centro na faixa de meio do campo adversário: 13 pressões em até 8s após o passe (81%
  dos passes para a região)"*.

---

### 7.4 Ligação estrutural frágil
- **Pergunta que responde:** qual conexão única, se cortada, desconecta a defesa do
  ataque — onde o adversário deveria ter pressionado?
- **Por que não é visível:** é propriedade da topologia; nenhuma métrica por jogador
  captura "esta aresta é a única ponte entre dois blocos".
- **Estrutura:** rede de passes não-direcionada. Primeiro `gds.bridges.stream` (ponte
  clássica). Redes de elite são densas e raramente têm ponte literal — nesse caso o
  fallback mede a concentração do fluxo entre as duas comunidades Louvain num único par
  de jogadores (share do fluxo inter-blocos).
- **Algoritmo:** `gds.bridges.stream`; fallback `gds.louvain.stream` + Cypher de share de fluxo.
- **Saída:** `tipo="ligacao_fragil"`, `nome_metrica="ponte_estrutural"` ou
  `"share_fluxo_entre_comunidades"`.
- **Exemplo real (final):** *"47% de todo o fluxo de passes entre dois blocos de Argentina
  passa por um único par: Tagliafico <-> Otamendi (51 passes entre os blocos)"*. Nas três
  partidas nenhuma rede teve ponte literal (resultado honesto: redes de seleções de elite
  são 2-aresta-conexas); o fallback documentado produziu o padrão nas seis redes.

---

### 7.5 Papel real versus posição nominal
- **Pergunta que responde:** algum jogador funciona taticamente numa função diferente da escalação?
- **Por que não é visível:** a escalação diz "lateral"; só a vizinhança no grafo revela
  que ele se agrupa com os meias/atacantes.
- **Estrutura:** comunidades Louvain na rede de passes não-direcionada; comunidade de cada
  jogador comparada com a comunidade modal da sua linha nominal (defesa/meio/ataque, da
  escalação StatsBomb). Divergência exige ≥15 ações e que a comunidade real seja a modal
  de OUTRA linha (fragmentação do Louvain não vira padrão).
- **Algoritmo:** `gds.louvain.stream` + comparação com `posicao_nominal`.
- **Saída:** `tipo="papel_divergente"`.
- **Exemplo real (final):** *"Theo Hernández (Left Back) escalado na linha de defesa, mas
  a comunidade de passes o agrupa com a linha de ataque (92 ações)"* — o lateral que jogou
  de ala/ponta de fato. Também: Koundé (Right Back → ataque) nas quartas, Borna Sosa
  (Left Back → meio) na semifinal.

---

### 7.6 Assimetria entre construção e finalização
- **Pergunta que responde:** o time constrói por um lado e finaliza pelo outro? Onde a bola atravessa?
- **Por que não é visível:** "percentual de ataque por lado" mostra volume, não mostra que
  o volume de um corredor VIRA chegada por outro.
- **Estrutura:** agregação sobre `PROGREDIU_PARA`: share de cada corredor na construção
  (progressões com origem em defesa/meio) vs. na chegada (fluxo de xT com destino no
  ataque). Padrão quando algum corredor diverge ≥20 p.p. entre os dois papéis.
- **Algoritmo:** Cypher de agregação de fluxo (`cypher.flow_aggregation(PROGREDIU_PARA)`).
- **Saída:** `tipo="assimetria_construcao"`, `valor_metrica=delta_share`.
- **Exemplo real (final):** *"O xT de chegada de France ao ataque concentra no corredor
  esquerda (68%) de forma desproporcional à construção, que passa por lá só 41% das vezes"*
  (o lado de Mbappé/Theo). Nas quartas, o espelho: *"England constrói pelo corredor
  esquerda (50%) mas quase não chega ao ataque por ele (27% do xT de chegada)"*.

---

### 7.7 Estado tático que mudou no meio do jogo (bitemporal)
- **Pergunta que responde:** o time mudou de comportamento? Quando e o quê?
- **Por que não é visível:** o PPDA da partida inteira é uma média que não descreve nenhum
  dos dois regimes.
- **Estrutura:** série de PPDA/field tilt em janelas móveis (10 min, passo 5 — calculada
  na camada 0); ponto de quebra = maior |média(3 janelas seguintes) − média(3 anteriores)|
  acima do limiar (PPDA: 6.0; tilt: 18 p.p.). Cada regime vira um fato com intervalo de
  validade explícito: **o estado antigo é invalidado (`invalid_at`), não apagado.**
- **Algoritmo:** `pipeline.windowed_metrics + cypher.changepoint(diff_medias)`.
- **Saída:** dois `PadraoTatico(tipo="mudanca_estado")` por métrica com quebra: o estado
  invalidado e o vigente.
- **Exemplo real (final):** *"Argentina em bloco baixo até o minuto 50 (PPDA médio 15.4) —
  estado invalidado aos 50"* seguido de *"Argentina muda para pressão alta a partir do
  minuto 50 (PPDA médio 5.2 contra 15.4 antes)"*. E a França: pressão alta (PPDA 7.9) até
  o minuto 105, bloco baixo (PPDA 30.0) na prorrogação — a média da partida inteira
  (9.6/9.9 por tempo) não descreve nenhum dos regimes.
- **Nota:** é o insight que justifica o modelo bitemporal (Graphiti) em vez de Neo4j puro:
  na indexação da camada 3 os dois fatos coexistem, um com `invalid_at` preenchido.

---

### 7.8 O alvo real da pressão adversária
- **Pergunta que responde:** o adversário está caçando um jogador específico?
- **Por que não é visível:** as pressões estão espalhadas; só a concentração do grau de
  entrada sobre um nó, **normalizada por toques**, revela a intenção (sem normalizar, o
  jogador que mais toca sempre "vence").
- **Estrutura:** rede de pressão agregada; grau de entrada ponderado por par.
- **Algoritmo:** `gds.degree.stream` (orientation REVERSE, peso `n_pressoes`) + normalização
  por toques (`ATUOU_EM`). Padrão só se o líder tem ≥1.5x a taxa média dos companheiros.
- **Saída:** `tipo="alvo_de_pressao"`, `nome_metrica="pressoes_por_toque"`.
- **Exemplo real (quartas):** *"England concentra pressão em Kylian Mbappé: 22 pressões em
  77 toques (0.29 por toque, 1.6x a média dos companheiros)"*. Na semifinal: *"Argentina
  concentra pressão em Nikola Vlašić: 14 pressões em 39 toques (0.36 por toque, 2.1x a
  média)"*. **Na final, nenhum dos times concentrou pressão acima do limiar — registrado
  como resultado honesto (não há caça direcionada), não como falha.**

---

## Distribuição real dos padrões gerados

| Insight | final | semi | quartas |
|---|---|---|---|
| pivo_estrutural | 2 | 2 | 2 |
| terceiro_homem | 6 | 4 | 4 |
| gatilho_pressao | 2 | 2 | 2 |
| ligacao_fragil | 2 | 2 | 2 |
| papel_divergente | 3 | 1 | 2 |
| assimetria_construcao | 1 | 2 | 2 |
| alvo_de_pressao | 0 | 1 | 1 |
| mudanca_estado | 8 | 8 | 8 |
| **total** | **24** | **22** | **23** |

## Avaliação: grafo vs baseline vetorial (o resultado central)

Golden dataset de 16 perguntas (`evaluation/golden_dataset.py`, cobrindo os 8 insights
nas 3 partidas) rodado ao vivo nos dois sistemas com `claude-haiku-4-5` como gerador e
juiz, embeddings Gemini no baseline (`scripts/run_evaluation.py`; saída completa em
`data/processed/eval_results.json`). Scores 1–5 dos juízes; fidelidade determinística
só se aplica ao sistema de grafo:

| Categoria (n) | Grafo: retrieval | Grafo: insight | Grafo: fidelidade | Baseline: retrieval | Baseline: insight |
|---|---|---|---|---|---|
| **estrutural** (15) | **5.0** | **5.0** | **100%** | 1.0 | 1.13 |
| **agregada** (1) | 5.0 | 5.0 | 100% | 2.0 | 1.0 |

A tese da seção 0.2 do plano se confirmou pelo mecanismo previsto: nas perguntas
estruturais o baseline respondeu literalmente *"não é possível responder a essa pergunta
com os dados disponíveis"* — a informação (betweenness, comunidades, trios, pontes)
**não existe** no resumo agregado que ele indexa; não é um problema de recuperação, é
limite arquitetural. Exemplo (q01, pivô da Argentina): grafo responde Otamendi com
betweenness 50.0 citando o padrão; baseline lista os jogadores com mais passes e declara
que isso não identifica gargalo estrutural.

**Nuance honesta na pergunta agregada:** esperava-se empate, e o baseline de fato chegou
perto pela direção certa (comparou PPDA do 2º tempo entre os times), mas errou por não
conseguir identificar qual partida era "a final" — os chunks dele carregam `match_id`
numérico, sem rótulo da fase. É um artefato do desenho do baseline (fiel aos RAGs
descritivos existentes), registrado aqui em vez de inflar a diferença: com rótulos de
fase nos chunks, essa pergunta específica provavelmente empataria.

**Nota de execução:** a rodada com o dataset expandido (16 perguntas) já usa o formato
de resposta em dois registros (tatiquês + `em_bom_portugues`); o score de insight do
grafo subiu de 4.33 para 5.0 em relação à rodada anterior de 10 perguntas — consistente
com a rubrica do juiz, que pune resposta que "só repete o número" sem explicar o
mecanismo. Histórico das duas rodadas em `07-validacao.md`.

**Categoria `factual` (modo autônomo, ADR-8):** o golden dataset foi expandido para
**24 perguntas** — 8 factuais novas (gols, assistências, dupla com mais passes, top
passador, cartões, dribles, desarmes, defesas de goleiro), todas com referência
conferida à mão contra o parquet. As 8 já foram validadas ao vivo individualmente
(acerto 8/8, re-execução de consultas 100% — tabelas em `07-validacao.md`); a rodada
formal do `run_evaluation.py` com as 24 fica pendente de chave de LLM ativa (a chave
Anthropic foi rotacionada durante a validação; ver `07-validacao.md`).

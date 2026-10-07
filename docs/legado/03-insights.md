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
- **Em campo:** é o jogador por quem a bola PRECISA passar para o time sair jogando.
  Não é quem toca mais na bola — é por quem passam os caminhos. Se o adversário
  colar um marcador nele, o time perde a ligação entre defesa e ataque.
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
- **A diferença entre tocar muito e ser o gargalo:**

  ```mermaid
  graph LR
      Z1["Zagueiro A"] --- Z2["Zagueiro B"]
      Z1 --- P["Pivô"]
      Z2 --- P
      P --- M1["Meia"]
      P --- M2["Ala"]
      M1 --- AT["Atacante"]
      M2 --- AT

      style P fill:#fdf0e3,stroke:#a86420,stroke-width:3px
  ```

  Os dois zagueiros podem trocar 40 passes entre si e liderar o volume. Mas
  **todo caminho** da defesa até o atacante passa pelo pivô: é ele que tem
  betweenness alto. Anular os zagueiros custa pouco ao adversário; anular o
  pivô parte o time em dois.

- **Exemplo real observado na final:** *"Nicolás Otamendi é o gargalo estrutural da
  progressão de Argentina: betweenness 50.0 (2º colocado: 25.0), com 143 ações e pageRank
  1.622"* — betweenness 2x o segundo colocado; pelo pageRank (volume/prestígio) ele não se
  destaca na mesma proporção, que é exatamente a diferença que o insight captura. Para a
  França: Jules Koundé (40.0 contra 25.0).

---

### 7.2 Padrão do terceiro homem
- **Pergunta que responde:** quais combinações de três jogadores se repetem para quebrar linhas?
- **Em campo:** o "tabelinha e vai" ensaiado. A quebra de linha raramente é um passe
  só: é A toca em B, B devolve ou desvia para C, e C já está do outro lado da
  marcação. O padrão procura esses trios que se repetem.
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
- **Em campo:** o time não pressiona o tempo todo — ele espera um gatilho. Passe
  para trás? Bola no lateral? Bola no meio? Saber qual região dispara a pressão é
  saber por onde NÃO sair jogando.
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
- **Em campo:** é a dupla que sustenta a saída de bola sozinha. Se a ligação entre
  elas for cortada, o time fica partido em dois blocos que não se falam — a defesa
  não acha o meio e o meio não acha o ataque.
- **Pergunta que responde:** qual conexão única, se cortada, desconecta a defesa do
  ataque — onde o adversário deveria ter pressionado?
- **Por que não é visível:** é propriedade da topologia; nenhuma métrica por jogador
  captura "esta aresta é a única ponte entre dois blocos".
- **O que é uma ponte, em desenho:**

  ```mermaid
  graph LR
      D1["Zagueiro"] --- D2["Zagueiro"]
      D2 --- D3["Lateral"]
      O1["Meia"] --- O2["Ala"]
      O2 --- AT["Atacante"]
      D3 --- O1

      style D3 fill:#fdf0e3,stroke:#a86420,stroke-width:3px
      style O1 fill:#fdf0e3,stroke:#a86420,stroke-width:3px
      linkStyle 4 stroke:#a86420,stroke-width:4px
  ```

  Enquanto a ligação destacada existir, o time sai jogando. Cortada ela, os dois
  blocos ficam sem comunicação: a defesa toca entre si e não acha o ataque. Numa
  rede densa a ponte clássica pode não existir — aí o padrão cai para o par que
  concentra a maior fatia do fluxo entre os dois blocos, que é o caso da final
  (Tagliafico ↔ Otamendi, com 47% de todo o fluxo entre os blocos da Argentina).

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
- **Em campo:** a escalação diz "lateral esquerdo", mas com quem ele troca passes o
  jogo inteiro? Se ele troca com os atacantes e não com os zagueiros, ele é ala, não
  lateral — independentemente do que está no papel.
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
- **Em campo:** o time sai jogando pela direita mas o perigo aparece pela esquerda.
  Alguém está invertendo o jogo — e saber onde essa inversão acontece é saber onde
  fechar.
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
- **Em campo:** o time que começou esperando e depois do intervalo subiu a marcação.
  A média da partida inteira esconde isso: dá um número morno que não descreve nem
  o primeiro tempo nem o segundo.
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
- **Em campo:** marcação combinada em cima de um jogador só. Precisa ser medida por
  toque, senão quem toca mais na bola "ganha" sempre — sofrer 20 pressões em 100
  toques é normal; sofrer 20 em 40 é perseguição.
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

**A tabela citável é a da 4ª rodada, completa, em três braços** (2026-08-31,
`z-ai/glm-5.3-flash` via OpenRouter, busca híbrida ligada,
`data/processed/eval_results.json`, gerada por `scripts/run_evaluation.py
--hibrida` e formatada por `scripts/consolidar_resultados.py`). O desenho de
três braços (ADR-10) resolve a dúvida "a súmula pré-agregada não quebra o que
a pesquisa quer validar?": mede em vez de assumir.

| Categoria | n | Grafo: prévia / insight | Baseline: prévia / insight | Diferença (prévia) |
|---|---:|---|---|---:|
| **estrutural** | 15 | **5,0 / 2,53** | 1,2 / 2,0 | **+3,8** |
| factual | 8 | 2,5 / 3,38 | 3,75 / 4,25 | −1,25 |
| **agregada** | 4 | **4,75 / 4,75** | 2,0 / 2,5 | **+2,75** |
| **composta** | 3 | **5,0 / 3,33** | 2,67 / 3,33 | **+2,33** |

`prévia` é `retrieval_previo` (braço `grafo_com_sumula`) — a métrica simétrica
com o baseline, porque julga só o que a recuperação entregou ANTES do agente
rodar, sem o acréscimo das consultas que só o grafo tem ferramenta para fazer.
Fidelidade determinística desta rodada: 86,3% (sem súmula) / 93,3% (com
súmula) — abaixo do ~100% de rodadas anteriores com modelo mais forte, e a
razão é o achado mais importante desta seção (ver "O preço do modelo barato",
abaixo). A checagem de isolamento da ADR-10 passou: os dois braços do grafo
ficam a 0,27 pontos um do outro em `estrutural`, onde deveriam ser
indistinguíveis — a súmula não contamina o que é estrutural.

**estrutural, agregada e composta confirmam a tese com folga; factual
inverteu** (−1,25, baseline ganhando) — analisado abaixo em "A categoria
factual perdeu, e por quê".

### Números anteriores, preservados como referência histórica

A 3ª rodada (2026-08-25, `claude-sonnet-5`, 24 perguntas, sem os três braços
nem a ficha do jogo) está em `data/processed/eval_results_r3_sonnet.json`:

| Categoria (n) | Grafo: retrieval | Grafo: insight | Grafo: fidelidade | Baseline: retrieval | Baseline: insight |
|---|---|---|---|---|---|
| **estrutural** (15) | **4.93** | **4.73** | **100%** | 1.13 | 1.13 |
| **factual** (8) | 2.62 | 3.38 | 100% | 1.25 | 1.12 |
| **agregada** (1) | 5.0 | 5.0 | 100% | 2.0 | 2.0 |

Comparar as duas tabelas diretamente mede o MODELO, não o sistema (ADR-9): a
3ª rodada usou Claude, a 4ª usou um modelo gratuito/barato via agregador. A
comparação que continua válida entre rodadas é a estrutural, que sobreviveu
com folga aos dois modelos.

Ressalvas que precisam ser lidas junto com a tabela histórica acima:

1. **"Fidelidade 100%" não quer dizer "respostas corretas".** A métrica verifica
   que as citações apontam para padrões existentes e que as consultas
   re-executam. `q23_desarmes_final` tirou fidelidade 1.0 respondendo errado —
   contou tentativas de desarme como desarmes. Detalhe em `07-validacao.md`.
2. **A nota 2.62 em recuperação factual é artefato de medição.** O juiz pontua o
   CONTEXTO recuperado, e na época o contexto factual era o dump bruto do
   Cypher; perguntas com resposta final correta tiravam 1/5 em recuperação e
   4/5 em insight. Desde então a súmula entrou na recuperação
   (`api/retrieval.py`), o que deve corrigir isso — **sem medição ainda**.
3. **O baseline desta rodada não tinha paridade de fatos.** O resumo dele não
   continha gols, cartões, desarmes nem dribles, então a coluna factual compara
   um sistema com dado contra um sem dado. Corrigido em
   `evaluation/baseline_rag.py`; também sem medição nova.

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

**Categoria `composta` (a que melhor separa os dois sistemas):** 3 perguntas que só
se respondem CRUZANDO as camadas — um padrão estrutural com um número da súmula.
Exemplo (`q25`): *"o jogador por quem passavam os caminhos de progressão da Argentina
foi também o que mais errou passe?"* A resposta é não, e prová-lo exige o betweenness
(camada 2, 50.0 para Otamendi) **e** a contagem de passes errados (camada 1b: Otamendi
6, contra 17 de Molina). Nenhuma das duas fontes responde sozinha, e o baseline não
alcança nem com paridade de fatos: metade da resposta é topologia de rede, que não cabe
em resumo textual.

**Categoria `agregada` (onde o empate é o resultado desejado):** subiu de 1 para 4
perguntas — PPDA no fim do jogo, posse de bola, volume de finalizações e
aproveitamento de passe. São métricas clássicas, que um sistema descritivo já
sabe entregar, e agora o baseline tem os números para respondê-las. Se empatar,
é o resultado previsto e ele reforça a leitura das outras linhas: a vantagem do
grafo não é geral, é concentrada onde a resposta depende da topologia. Uma
categoria com n=1, como estava antes, não sustentava nem essa afirmação.

### O preço do modelo barato: alucinação, não bug

A fidelidade da 4ª rodada (86–93%) ficou abaixo do ~100% histórico. Investigado
sem gastar nada — `run_evaluation.py` passou a persistir citações e consultas
brutas por pergunta —, a causa não é falha da métrica nem do pipeline: em
14 das 82 citações da rodada (17%), o modelo **inventou dados inteiros** em
vez de admitir que não sabia ou de consultar o grafo.

Não é imprecisão de arredondamento — é fabricação com aparência de dado real:
`q06_papel_theo` citou consultas Cypher para `match_id: 'FB-MCI-LIV-2023-11-25'`
— sintaticamente válidas, referenciando Manchester City × Liverpool (uma
partida real, mas de 2023, que não existe neste projeto); `q15_papel_kounde`
citou o jogador "Alessandro Florenzi" em `match_id: 3918315`. Nenhum dos dois
existe no grafo (só há três partidas: 3869685, 3869519, 3869354). O modelo
completou a lacuna com o que parecia plausível vindo do próprio treino, em vez
de dizer "não sei" ou usar `consultar_grafo`.

A fidelidade determinística fez exatamente o que deveria: sinalizou as 14
citações como `padrao_inexistente` em vez de aceitá-las. **A métrica não
falhou — ela mostrou que o modelo falhou.** É a diferença prática entre um
modelo de laboratório forte (Claude, rodadas anteriores, ~100%) e um modelo
gratuito/barato via agregador (`z-ai/glm-5.3-flash`, esta rodada): a mesma
arquitetura de citação obrigatória (ADR-8) que garante rastreabilidade com um
modelo capaz não impede um modelo mais fraco de inventar — só torna a invenção
detectável. Confirma ao vivo a ressalva 2 da ADR-9: um modelo barato não é
base para o número oficial sem uma rodada em modelo estável para citação.

### A categoria factual perdeu, e por quê

Diferente da 3ª rodada, aqui o baseline ganhou a comparação simétrica em
`factual` (3,75 contra 2,5). A ficha do jogo da ADR-11 resolveu o caso que a
motivou (`q17`, "quem fez os gols" — ver `07-validacao.md`), mas a categoria
inteira tem 8 perguntas, e várias pedem números que não são gols, assistências
nem cartões (a ficha só cobre esses três) — nesses casos a recuperação
estruturada volta a depender de o agente consultar corretamente, e a rodada
mostrou consultas com erro de sintaxe (`q10`, `q15`, `q20` — ver mismatches em
`07-validacao.md`) que o baseline, por não ter Cypher para errar, não sofre.
Achado honesto, não escondido: a ficha do jogo resolve uma fatia da categoria
factual, não a categoria inteira.

**Verificação sem LLM:** `scripts/check_golden_queries.py` roda a consulta de referência
das **30 perguntas** contra o grafo e imprime o esperado ao lado do obtido — 30/30
respondidas, sem gastar API. Separa a qualidade do MODELO DE DADOS da qualidade do
modelo de linguagem, que a avaliação com juiz mistura.

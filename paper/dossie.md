# Dossiê do artigo: LLMs para consultar dados de futebol

Oct 10, 2026 · @João Bussolotto

## Resumo executivo

Com o sexto braço (`text_to_cypher`), o artigo ganhou uma tese mais forte do que "grafo vence": quanto mais da lógica de consulta já está pronta para o modelo, mais ele acerta, até o ponto em que a lógica fica rígida demais. Nas 47 perguntas com resposta: ferramentas prontas 87%, Cypher escrito pelo modelo 70%, partida inteira no prompt 45%, estatísticas fixas 0%.

**Estado do repositório.** A branch `refactor/benchmark-final` consolida 52 perguntas × 6 braços × 1 repetição (312 execuções, US$ 1,04, Claude Haiku 5.5) em `data/benchmark/final_results.jsonl`. O sexto braço recebe o schema do grafo e uma única ferramenta que executa Cypher só de leitura, sem a biblioteca de algoritmos (GDS) e sem os nós de padrões prontos.

**A escada de abstração** (do modelo que calcula tudo ao modelo que só escolhe):

| Degrau | Braço | Quem faz a lógica | Acerto (IC 95%) |
| --- | --- | --- | --- |
| Dados brutos no contexto | `events_in_prompt` | o modelo, de cabeça | 45% (31 a 59) |
| Linguagem de consulta livre | `text_to_cypher` | o modelo, escrevendo consultas | 70% (56 a 81) |
| Primitivas prontas | `graph_tools` | as ferramentas; o modelo escolhe e combina | 87% (75 a 94) |
| Agregados fixos | `stats_in_prompt` | ninguém; tudo pré-calculado e imutável | 0% |

O último degrau mostra o limite: pré-calcular tudo tira a flexibilidade que as perguntas com recorte exigem. A curva é um U invertido, e esse é o desenho central do artigo.

**O que é sólido e o que é frágil:**

- **Sólido:** sair do contexto e ir para consulta estruturada ajuda. `text_to_cypher` contra `events_in_prompt`: 17 perguntas só o primeiro acertou, 5 só o segundo, McNemar p = 0,017. E o `text_to_cypher` é medição de primeiro contato, sem nenhum ajuste guiado por erro.
- **Frágil:** a vantagem das ferramentas prontas sobre o Cypher livre (11 contra 3 perguntas, p = 0,057) não é significativa com 1 repetição, e o `graph_tools` foi ajustado olhando erros enquanto o `text_to_cypher` não. Leia os 17 pontos como teto do ganho da engenharia de ferramentas.
- **Onde as ferramentas fazem diferença:** jogadas e sequências (80% contra 40%) e rede de passes (95% contra 75%), as perguntas em que a ferramenta esconde lógica difícil (agrupar ações em jogadas, rede sem um jogador, intermediação). Em contagem e em antes e depois de um momento, os dois empatam.

**Medições de primeiro contato** (contam a história do ajuste): v2.2 em perguntas inéditas, `graph_tools` 67% contra 75% do `events_in_prompt`; v3 nas perguntas de grafo inéditas, 50% contra 10%. O `graph_tools` chegou a 87% depois de sete congelamentos de ferramentas (v2 a v3.1) e da correção da rodada 12.

## Requisitos da entrega

Artigo (AV2, 60% da nota) e apresentação (AV3, 20%) vencem em 18/10/2026, com 1 ponto de desconto por dia de atraso. A apresentação acontece entre 19 e 23/10.

| Item | Exigência | Como o projeto atende |
| --- | --- | --- |
| Tamanho | 6 a 12 páginas no template do Overleaf | alvo de 9 a 10 páginas (orçamento na seção de estrutura) |
| Idioma | português ou inglês | português, salvo decisão contrária |
| Referências | mínimo de 10, artigos com DOI | 24 com DOI verificado nesta pesquisa |
| Processo | todo o ciclo de ciência de dados (ex.: CRISP-DM); só análise exploratória não basta | metodologia escrita fase a fase do CRISP-DM |
| IA generativa | declaração obrigatória | rascunho no fim deste dossiê |
| Repositório | recomendável | link do GitHub no artigo, com commit da rodada |
| Submissão | opcional, recomendada | candidatos: eventos da SBC (ex.: SBBD, BRACIS) |
| Apresentação | 20 min + 20 min de perguntas, até 15 slides, todos apresentam | derivar dos mesmos gráficos do artigo |

Estrutura de artigo pedida pela disciplina: Introdução, Contribuições, Trabalhos Relacionados, Metodologia, Experimentos e Resultados, Conclusão, Referências.

**Template:** o link do Overleaf só abre com login, então não consegui ver a classe LaTeX. Pergunta aberta: é o template da SBC (comum em disciplinas brasileiras e compatível com 6 a 12 páginas) ou outro? O orçamento de páginas abaixo assume uma coluna no estilo SBC; se for duas colunas (IEEE), cabe cerca de 40% mais texto por página.

**Atualização:** o rascunho do colega usa o template IEEE de conferência, e você indicou que esse não é o da disciplina. Antes de portar qualquer texto, abra o projeto do link da disciplina pelo MCP do Overleaf e confirme a classe LaTeX e o estilo de citação. Com BibTeX, o formato das referências passa a vir do template, e o problema do rascunho (ABNT dentro de IEEE) desaparece.

## Problema, perguntas de pesquisa e contribuições

O artigo responde: para que um LLM responda perguntas táticas sobre uma partida, quanto da lógica de consulta deve estar pronta antes de ele começar?

**Problema.** Uma partida no StatsBomb tem cerca de 4.400 eventos. Boa parte da tática é relacional, feita de interações entre jogadores, e a ciência de redes formaliza essa leitura com jogadores como vértices e passes como arestas (Duch et al., 2010; Buldú et al., 2018). Perguntas relacionais exigem calcular, e não só recuperar. LLMs prometem consulta em linguagem natural, mas há várias formas de ligá-los aos dados, e elas se diferenciam justamente por quem faz o cálculo: o modelo, uma consulta que o modelo escreve, ou uma ferramenta pronta.

**Perguntas de pesquisa**

1. **QP1:** entre seis formas de acesso (sem dados, recuperação vetorial, partida inteira no prompt, estatísticas agregadas, Cypher escrito pelo modelo, ferramentas prontas sobre o grafo), qual acerta mais?
2. **QP2:** como o acerto varia por tipo de pergunta (busca e contagem, relações na rede de passes, jogadas, antes e depois de um momento)?
3. **QP3:** qual o custo (tokens, latência) e o perfil de erro (alucinação contra abstenção) de cada forma?
4. **QP4 (metodológica):** quais perguntas táticas têm resposta verificável, isto é, estável sob as leituras razoáveis da pergunta?

**Hipóteses.** H1 a H4 foram registradas antes das rodadas da v2 (estão no histórico desta conversa e podem ir para um apêndice). O sexto braço entrou depois e não tem hipótese pré-registrada; o texto deve dizer isso.

- **H1:** a recuperação vetorial falha em contagem, porque só vê os k eventos mais parecidos. Confirmada (11%).
- **H2:** a partida inteira no prompt acerta fatos, mas erra contagens e custa mais tokens. Confirmada (82% em busca e contagem, 30% em jogadas, 115 mil tokens por pergunta).
- **H3:** só o agente com ferramentas acerta perguntas que exigem algoritmo de grafo. Parcialmente: na s01 (intermediação) o `text_to_cypher` errou porque não escreveu o algoritmo, embora ele exista em Cypher puro.
- **H4:** sem dados, o modelo se abstém quando instruído. Confirmada (0% de alucinação no `no_context`).

**Contribuições**

1. Um benchmark verificável de 52 perguntas sobre a final da Copa de 2022, com gabarito calculado sem o sistema avaliado (pandas e networkx) e teste de robustez a leituras.
2. Uma comparação controlada de seis formas de acesso (mesmo modelo, prompt, saída estruturada e conferência por código), organizada como uma escada de abstração da lógica de consulta.
3. Evidência de que consulta estruturada supera o contexto longo em perguntas relacionais, e de que primitivas prontas ajudam sobretudo onde escondem lógica difícil (jogadas, rede sem um jogador, intermediação).
4. Dois achados metodológicos: conceitos clássicos de rede de passes, como o jogador mais central, mudam de resposta conforme peso e direção da rede; e o acerto do agente com ferramentas depende de um ciclo de ajuste que precisa ser reportado.

**Fora do escopo** (lista de exclusões do rascunho do colega, que é útil e não depende de referência): várias partidas; dados de rastreamento e fisiológicos; inferência sobre lesão, fadiga ou saúde; valor de mercado e recomendação de contratação; escalação; predição de resultado; qualidade da explicação tática; comparação entre modelos; agente que escreve Python.

## Trabalhos relacionados

Nenhum trabalho encontrado compara, com gabarito exato, formas diferentes de ligar um LLM a dados de eventos de futebol, e menos ainda organizadas pelo quanto da lógica de consulta está pronta; essa é a lacuna do artigo. Os trabalhos se agrupam em seis eixos, e o artigo fica na interseção deles. O eixo 3 ganhou peso com o sexto braço: texto para consulta (SQL ou Cypher) é agora uma das formas comparadas, não só uma alternativa descartada.

### Posicionamento

| Trabalho | Domínio esportivo | Dados estruturados | Compara formas de acesso | Gabarito exato | Quem faz a lógica |
| --- | --- | --- | --- | --- | --- |
| SportQA (Xia et al., 2024) | sim | não (múltipla escolha) | não | sim | o modelo, de memória |
| SoccerRAG (Strand et al., 2024) | sim | sim (SQLite) | não | não | o modelo, escrevendo SQL |
| SPORTSQL (Martinez et al., 2025) | sim | sim (SQL) | não | sim | o modelo, escrevendo SQL |
| SoccerAgent (Rao et al., 2025) | sim | parcial | não | sim (múltipla escolha) | ferramentas |
| Text2Cypher (Ozsoy et al., 2025) | não | sim (grafo) | não | sim (consulta de referência) | o modelo, escrevendo Cypher |
| RAG ou contexto longo (Li et al., 2024) | não | não (texto) | sim, 2 formas | parcial | o modelo, de cabeça |
| RAG vs. GraphRAG (Han et al., 2025) | não | não (texto) | sim, 2 formas | parcial | o modelo, sobre grafo extraído |
| NLGraph (Wang et al., 2023) | não | grafos sintéticos | não | sim | o modelo, de cabeça |
| **Este artigo** | **sim** | **sim (eventos)** | **sim, 6 formas** | **sim, por código** | **varia: é a variável estudada** |

### Eixo 1: LLMs no esporte

**SportQA** ([Xia et al., NAACL 2024](https://doi.org/10.18653/v1/2024.naacl-long.283)). Benchmark com mais de 70 mil perguntas de múltipla escolha em três níveis, de fatos históricos a raciocínio sobre cenários. Avaliaram LLMs com few-shot e chain-of-thought. Resultado: bons em conhecimento básico, fracos em raciocínio de cenário. Diferença para o nosso: mede o que o modelo sabe de memória, sem dados de uma partida. Nosso braço `no_context` é o equivalente, e por isso ele zera.

**SoccerRAG** ([Strand et al., 2024](https://doi.org/10.48550/arXiv.2406.01273)). Converte os JSON do SoccerNet (anotações de eventos, comentários transcritos, jogadores) num SQLite. Um LLM extrai entidades da pergunta, valida contra o banco e um agente SQL consulta. Avaliação qualitativa, e os autores admitem erros com matemática complexa e listas longas. É o trabalho mais próximo em arquitetura (agente com acesso a banco), mas sem comparação controlada nem gabarito.

**SPORTSQL** ([Martinez et al., IJCNLP-AACL 2025](https://doi.org/10.18653/v1/2025.ijcnlp-demo.11)). Texto para SQL sobre dados da Premier League, com o benchmark DSQABench: mais de 1.700 perguntas com SQL e resposta de ouro. Mostra que a avaliação por resposta exata é viável no esporte. Não compara com contexto longo nem usa grafo.

**SoccerAgent** ([Rao et al., 2025](https://doi.org/10.48550/arXiv.2505.03735)). Sistema multiagente com caixa de ferramentas para perguntas sobre futebol, sobre uma base de conhecimento (SoccerWiki) e cerca de 10 mil perguntas de múltipla escolha. Confirma a tendência de agentes com ferramentas no domínio. Foco em conhecimento enciclopédico, não em eventos de uma partida.

**TacticAI** ([Wang et al., Nature Communications 2024](https://doi.org/10.1038/s41467-024-45965-x)). Aprendizado profundo geométrico sobre dados de rastreamento para escanteios, avaliado com especialistas do Liverpool, que preferiram as sugestões em 90% dos casos. Serve para mostrar que grafos são a representação natural de tática coletiva, embora com outro tipo de dado e sem LLM.

### Eixo 2: RAG, contexto longo e GraphRAG

**RAG** ([Lewis et al., 2020](https://doi.org/10.48550/arXiv.2005.11401)). Origem da recuperação densa acoplada à geração. É o que o braço `vector` implementa.

**Lost in the Middle** ([Liu et al., TACL 2024](https://doi.org/10.1162/tacl_a_00638)). O desempenho cai quando a informação relevante está no meio de um contexto longo, numa curva em U. Explica por que o `events_in_prompt` acerta fatos isolados e erra contagens: contar exige usar o contexto inteiro.

**RAG ou contexto longo** ([Li et al., EMNLP 2024](https://doi.org/10.18653/v1/2024.emnlp-industry.66)). Com recursos suficientes, contexto longo supera RAG em média, mas RAG custa muito menos; propõem roteamento (Self-Route). Nosso resultado replica a ordem (`events_in_prompt` 45% contra `vector` 11%) em dados estruturados, e acrescenta um terceiro caminho, ferramentas, que supera os dois.

**GraphRAG** ([Edge et al., 2024](https://doi.org/10.48550/arXiv.2404.16130)). Um LLM extrai um grafo de entidades do texto e resume comunidades; vence RAG ingênuo em perguntas globais, avaliado por LLM-juiz. Diferença importante: no nosso caso o grafo não é extraído por LLM, ele já está nos dados (quem passou para quem).

**RAG vs. GraphRAG** ([Han et al., 2025](https://doi.org/10.48550/arXiv.2502.11371)). Comparação controlada: RAG vence em perguntas de um salto e detalhes; GraphRAG vence em perguntas de vários saltos. Mesma conclusão de complementaridade que nossos tipos de pergunta mostram.

**Unifying LLMs and KGs** ([Pan et al., IEEE TKDE 2024](https://doi.org/10.1109/TKDE.2024.3352100)). Roteiro que classifica integrações entre LLM e grafo de conhecimento. Nosso braço `graph_tools` cai na categoria de LLM que raciocina sobre o grafo por ferramentas.

### Eixo 3: LLMs sobre dados estruturados e ferramentas

**Table Meets LLM** ([Sui et al., WSDM 2024](https://doi.org/10.1145/3616855.3635752)). Benchmark de compreensão estrutural de tabelas: o desempenho de GPT-4 varia com formato, ordem e marcadores, e falha até em tarefas triviais como contar linhas. Explica os erros de leitura do `stats_in_prompt` e do `events_in_prompt` em tabelas largas.

**StructGPT** ([Jiang et al., EMNLP 2023](https://doi.org/10.18653/v1/2023.emnlp-main.574)). Interfaces especializadas leem os dados estruturados e o LLM só raciocina sobre o que foi lido, em ciclos. Melhora muito o zero-shot em tabelas, grafos de conhecimento e bancos. É o antecessor conceitual do nosso `graph_tools`.

**ReAct** ([Yao et al., ICLR 2023](https://doi.org/10.48550/arXiv.2210.03629)). Alternar raciocínio e ações (chamadas de ferramenta) reduz alucinação e propagação de erro. É o padrão de agente que o PydanticAI implementa no `graph_tools`.

**Text2Cypher** ([Ozsoy et al., 2025](https://doi.org/10.48550/arXiv.2412.10064)). Conjunto de perguntas com consultas Cypher de referência; LLMs erram nuances ao gerar Cypher livre, e fine-tuning ajuda. É a referência direta do braço `text_to_cypher`. O resultado aqui concorda: as 47 respostas existem em Cypher, mas o modelo errou 14, por quatro motivos (consulta única sem conferência, estouro das 12 chamadas, medida aproximada no lugar da pedida, significado errado de um campo).

### Eixo 4: LLMs e raciocínio sobre grafos

**NLGraph** ([Wang et al., NeurIPS 2023](https://doi.org/10.48550/arXiv.2305.10037)). 29.370 problemas de grafo descritos em texto. LLMs têm raciocínio preliminar, mas o ganho de prompting avançado some nos problemas complexos, e os modelos são frágeis a correlações espúrias. É a base teórica de por que o `events_in_prompt` falha em centralidade: o modelo teria de calcular caminhos mínimos de cabeça.

### Eixo 5: Análise de redes de passes e dados de eventos

**Duch, Waitzman e Amaral** ([PLoS ONE 2010](https://doi.org/10.1371/journal.pone.0010937)). Rede de passes da Euro 2008, com centralidade de fluxo até a finalização; o ranking bate com a seleção da UEFA. Trabalho fundador de redes de passes.

**Buldú et al.** ([Frontiers in Psychology 2018](https://doi.org/10.3389/fpsyg.2018.01900)). Redes de passes são dirigidas, ponderadas, espaciais e mudam no tempo. Sustenta o achado de robustez: o "jogador mais central" depende de direção, peso e recorte de tempo.

**Brandes** ([J. Math. Sociology 2001](https://doi.org/10.1080/0022250X.2001.9990249)). Algoritmo de intermediação em O(nm) usado por networkx e pelo GDS. Referência técnica do gabarito.

**SPADL e VAEP** ([Decroos et al., KDD 2019](https://doi.org/10.1145/3292500.3330758)). Linguagem padronizada de ações e valoração de cada ação. É a camada 0 do pipeline.

**Pappalardo et al.** ([Scientific Data 2019](https://doi.org/10.1038/s41597-019-0247-7)). Maior coleção pública de eventos (Wyscout). Contextualiza dados de eventos e sua disponibilidade aberta, como o StatsBomb Open Data usado aqui.

### Eixo 6 (metodologia): avaliação e processo

**Contaminação** ([Sainz et al., 2023](https://doi.org/10.48550/arXiv.2310.18018)). Exposição prévia a um benchmark superestima o desempenho. Justifica o braço `no_context` e a retirada do nome da partida do prompt.

**Alucinação** ([Ji et al., ACM Computing Surveys 2023](https://doi.org/10.1145/3571730)). Taxonomia de alucinação intrínseca e extrínseca. Base para separar alucinação de abstenção nas métricas.

**CRISP-DM** ([Schröer et al., 2021](https://doi.org/10.1016/j.procs.2021.01.199); [Martínez-Plumed et al., IEEE TKDE 2021](https://doi.org/10.1109/TKDE.2019.2962680); [Shimaoka et al., SBC Reviews 2024](https://doi.org/10.5753/reviews.2024.3757)). Revisão do uso do modelo, sua evolução para ciência de dados e uma revisão brasileira de adaptações. Sustentam a estrutura da metodologia exigida pela disciplina.

## Referências com DOI

27 referências, 24 com DOI confirmado em página da editora, do arXiv ou do Crossref durante esta pesquisa; 3 seguem o padrão de DOI do arXiv e precisam de uma conferência rápida antes de entrar no BibTeX. O mínimo exigido é 10. Onde houver versão publicada em conferência ou revista, prefira o DOI dela ao do arXiv.

| # | Referência | Veículo | DOI | Status | Seção do artigo |
| --- | --- | --- | --- | --- | --- |
| 1 | Xia et al., SportQA | NAACL 2024 | 10.18653/v1/2024.naacl-long.283 | confirmado | Relacionados |
| 2 | Strand et al., SoccerRAG | arXiv 2024 | 10.48550/arXiv.2406.01273 | confirmado | Relacionados |
| 3 | Martinez et al., SPORTSQL | IJCNLP-AACL 2025 (demo) | 10.18653/v1/2025.ijcnlp-demo.11 | confirmado | Relacionados |
| 4 | Rao et al., SoccerAgent / SoccerWiki | arXiv 2025 | 10.48550/arXiv.2505.03735 | conferir | Relacionados |
| 5 | Wang et al., TacticAI | Nature Communications 2024 | 10.1038/s41467-024-45965-x | confirmado | Introdução, Relacionados |
| 6 | Lewis et al., RAG | arXiv 2020 (NeurIPS) | 10.48550/arXiv.2005.11401 | conferir | Relacionados, Metodologia |
| 7 | Liu et al., Lost in the Middle | TACL 2024 | 10.1162/tacl\_a\_00638 | confirmado | Relacionados, Discussão |
| 8 | Li et al., RAG ou contexto longo | EMNLP 2024 Industry | 10.18653/v1/2024.emnlp-industry.66 | confirmado | Relacionados, Discussão |
| 9 | Edge et al., GraphRAG | arXiv 2024 | 10.48550/arXiv.2404.16130 | confirmado | Introdução, Relacionados |
| 10 | Han et al., RAG vs. GraphRAG | arXiv 2025 | 10.48550/arXiv.2502.11371 | confirmado | Relacionados, Discussão |
| 11 | Xiang et al., When to use Graphs in RAG | arXiv 2025 | 10.48550/arXiv.2506.05690 | conferir | Discussão |
| 12 | Pan et al., Unifying LLMs and KGs | IEEE TKDE 2024 | 10.1109/TKDE.2024.3352100 | confirmado | Relacionados |
| 13 | Sui et al., Table Meets LLM | WSDM 2024 | 10.1145/3616855.3635752 | confirmado | Relacionados, Discussão |
| 14 | Jiang et al., StructGPT | EMNLP 2023 | 10.18653/v1/2023.emnlp-main.574 | confirmado | Relacionados, Metodologia |
| 15 | Yao et al., ReAct | arXiv 2022 (ICLR 2023) | 10.48550/arXiv.2210.03629 | confirmado | Metodologia |
| 16 | Ozsoy et al., Text2Cypher | arXiv 2024 (GenAIK 2025) | 10.48550/arXiv.2412.10064 | confirmado | Relacionados, Metodologia |
| 17 | Wang et al., NLGraph | arXiv 2023 (NeurIPS) | 10.48550/arXiv.2305.10037 | confirmado | Relacionados, Discussão |
| 18 | Duch, Waitzman e Amaral | PLoS ONE 2010 | 10.1371/journal.pone.0010937 | confirmado | Relacionados |
| 19 | Buldú et al. | Frontiers in Psychology 2018 | 10.3389/fpsyg.2018.01900 | confirmado | Relacionados, Discussão |
| 20 | Brandes | J. Mathematical Sociology 2001 | 10.1080/0022250X.2001.9990249 | confirmado | Metodologia |
| 21 | Decroos et al., SPADL e VAEP | KDD 2019 | 10.1145/3292500.3330758 | confirmado | Metodologia |
| 22 | Pappalardo et al. | Scientific Data 2019 | 10.1038/s41597-019-0247-7 | confirmado | Introdução |
| 23 | Sainz et al., contaminação | arXiv 2023 (Findings EMNLP) | 10.48550/arXiv.2310.18018 | confirmado | Metodologia, Ameaças |
| 24 | Ji et al., alucinação | ACM Computing Surveys 2023 | 10.1145/3571730 | confirmado | Metodologia |
| 25 | Schröer, Kruse e Gómez, CRISP-DM | Procedia Computer Science 2021 | 10.1016/j.procs.2021.01.199 | confirmado | Metodologia |
| 26 | Martínez-Plumed et al., CRISP-DM 20 anos | IEEE TKDE 2021 | 10.1109/TKDE.2019.2962680 | confirmado | Metodologia |
| 27 | Shimaoka, Ferreira e Goldman, CRISP-DM | SBC Reviews 2024 | 10.5753/reviews.2024.3757 | confirmado | Metodologia |

Prioridade se faltar espaço: as 13 primeiras citadas no texto são 1, 2, 3, 5, 7, 8, 9, 10, 13, 16, 17, 19 e 25 (a 16, Text2Cypher, subiu de importância com o sexto braço); as demais reforçam pontos específicos.

**Sem DOI, citar como fonte de dados ou software:** StatsBomb Open Data (GitHub), Neo4j Graph Data Science, networkx, PydanticAI, Langfuse e a ferramenta socceraction. TacticalGPT (Caron e Müller, StatsBomb Conference 2023) é relevante, mas não tem DOI; use só se sobrar espaço.

## Metodologia em CRISP-DM

O projeto já percorre as seis fases do CRISP-DM; a seção de metodologia do artigo só precisa nomeá-las. Isso atende à exigência de que o trabalho cubra o processo inteiro, e não só análise exploratória.

| Fase | O que foi feito | Artefato no repositório |
| --- | --- | --- |
| 1. Entendimento do negócio | Problema do analista que quer consultar eventos em linguagem natural; questões de pesquisa e hipóteses | `docs/01-visao-geral.md` |
| 2. Entendimento dos dados | StatsBomb Open Data, final da Copa de 2022: 4.407 eventos no JSON bruto, 1.263 passes, escalações; o que os dados não têm (rastreamento, velocidade) vira a categoria de controle | `docs/02-dos-dados-ao-grafo.md` |
| 3. Preparação dos dados | Camada 0: normalização SPADL (2.585 ações), xT e VAEP treinados em 16 partidas, zonas, fases de posse, vocabulário em português; correção da direção de ataque; camadas 1 e 1b no Neo4j | `docs/09-transformacoes-dos-dados.md`, `ingestion/`, `graph/` |
| 4. Modelagem | Seis braços com o mesmo modelo e a mesma saída estruturada, ordenados pelo quanto da lógica de consulta está pronta; ferramentas primitivas congeladas antes das perguntas | `benchmark/arms.py`, `benchmark/tools.py` |
| 5. Avaliação | 52 perguntas, gabarito independente (pandas e networkx), teste de robustez, conferência por código, métricas de acerto, alucinação, abstenção e custo | `benchmark/ground_truth.py`, `scoring.py`, `data/benchmark/` |
| 6. Implantação | `ask.py` interativo, Langfuse com trace por execução, página gerada por rodada, Docker | `scripts/ask.py`, `docs/execucoes/` |

### Detalhes que o texto precisa trazer

**Dados.** Uma partida para que o braço `events_in_prompt` caiba no contexto: a tabela de eventos tem cerca de 115 mil tokens, enquanto o JSON bruto tem cerca de 670 mil.

**Os seis braços,** na ordem da escada de abstração:

1. `no_context`: só a pergunta (controle de conhecimento prévio).
2. `vector`: embeddings das linhas de eventos, top-30 por similaridade de cosseno.
3. `events_in_prompt`: tabela compacta com todas as ações da partida; o modelo calcula tudo de cabeça.
4. `text_to_cypher`: schema do grafo lido do Neo4j (cerca de 11 mil caracteres) e uma ferramenta `run_cypher`, só leitura, até 12 chamadas; procedimentos `gds.*`, `apoc.*` e `db.*` bloqueados, nós de padrões prontos fora do schema. O modelo escreve toda a lógica.
5. `graph_tools`: agente ReAct (PydanticAI) com ferramentas parametrizadas sobre o Neo4j e o GDS, até 12 chamadas. A lógica difícil (jogadas, rede sem um jogador, intermediação) está pronta; o modelo escolhe e combina.
6. `stats_in_prompt`: estatísticas agregadas por jogador e time, lidas do Neo4j. Toda a lógica está pronta e fixa.

O `text_to_cypher` e o `graph_tools` usam o mesmo grafo e o mesmo limite de chamadas; a única diferença é quem escreve a lógica. Isso faz deles o par controlado do artigo, no lugar do `tools_no_graph` que tinha sido discutido.

Todos usam o mesmo modelo (Claude Haiku 5.5 via OpenRouter, temperatura 0), o mesmo prompt de sistema (sem nomear a partida) e a mesma saída estruturada (`players`, `value`, `no_data`, `rationale`).

**Perguntas.** 52 ativas em cinco grupos: busca e contagem (11), relações na rede de passes (20), jogadas e sequências (10), antes e depois de um momento (6), controle sem resposta (5). Perguntas em linguagem de futebol, fechadas (quem, quantos, quais), sem definição operacional no texto.

**Gabarito e robustez.** Calculado sem o Neo4j: pandas sobre o JSON bruto ou o Parquet, networkx para redes. Cada pergunta é resolvida em todas as leituras razoáveis (peso nenhum, por passes ou por xT; rede dirigida ou não; mesma posse ou não). Só ficam as perguntas cuja resposta não muda entre leituras; empate conta como instável, a menos que todas as leituras concordem no empate.

**Conferência.** Por tipo de resposta: jogador, valor, conjunto, jogador e valor, ou sem dados. Nomes normalizados com apelidos das escalações; sobrenome sozinho só vale quando é único na partida.

**Métricas.** Acerto por grupo e braço; alucinação (resposta errada dada como resposta), abstenção e erro de formato; tokens de entrada e saída, chamadas de ferramenta e latência.

**Testes estatísticos a acrescentar** (baratos, rodam sobre o `results.jsonl` que já existe):

- intervalo de confiança de Wilson a 95% para cada proporção de acerto;
- teste exato de McNemar entre pares de braços, porque todos respondem as mesmas perguntas (amostras pareadas).

## Resultados e como reportá-los

A escada de abstração se sustenta nos testes pareados, com uma ressalva no degrau mais alto. Teste exato de McNemar sobre as 47 perguntas com resposta (perguntas que só o primeiro braço acertou contra só o segundo):

| Par | Só o primeiro | Só o segundo | p |
| --- | --- | --- | --- |
| `text_to_cypher` contra `events_in_prompt` | 17 | 5 | 0,017 |
| `graph_tools` contra `text_to_cypher` | 11 | 3 | 0,057 |
| `graph_tools` contra `events_in_prompt` | 23 | 3 | menor que 0,001 |

&#91;embedded content: data/benchmark/final\_results.jsonl, execução 14 (10/10/2026), branch refactor/benchmark-final; no\_context e stats\_in\_prompt: 0% em todos os grupos\]

O gráfico mostra onde a lógica pronta faz diferença: em jogadas (80% contra 40% do Cypher livre) e na rede de passes (95% contra 75%). Em antes e depois de um momento, Cypher e ferramentas empatam em 100%; em busca e contagem, as três formas ficam entre 73% e 82%.

### Por que cada degrau erra

- **`events_in_prompt`:** acerta fatos isolados e erra contagens longas; 33% de abstenção. Coerente com "Lost in the Middle" e com "Table Meets LLM".
- **`text_to_cypher` (14 erros):** consulta única sem conferir o resultado (sequência de três que repete jogador, finalização sem exigir o passe imediatamente antes); estouro das 12 chamadas montando a lógica de jogadas; medida aproximada no lugar da pedida (respondeu "mais passes" em vez de intermediação na s01); significado errado de campo (zona de destino no lugar de corredor). As 47 respostas existem em Cypher puro, o gargalo é escrever a consulta.
- **`graph_tools` (6 erros):** leitura ou contagem (3), lista com mais itens do que o pedido (p01, n12), "sem dados" após 12 chamadas (q03), aproximação proibida em pergunta sem resposta (u03).
- **Onde o Cypher vence as ferramentas (4 perguntas):** n12, u03, q03, p01. Útil para o texto: mostra que a vantagem das ferramentas não é uniforme.

### Custo e perfil de erro

| Braço | Alucinação | Abstenção | Tokens de entrada por pergunta | Chamadas | Latência |
| --- | --- | --- | --- | --- | --- |
| `graph_tools` | 12% | 2% | 76.118 | 3,3 | 7,8 s |
| `text_to_cypher` | 23% | 6% | 50.983 | 4,8 | 10,1 s |
| `events_in_prompt` | 17% | 33% | 115.735 | 0 | 3,9 s |
| `vector` | 19% | 62% | 2.623 | 0 | 2,3 s |
| `stats_in_prompt` | 0% | 90% | 4.968 | 0 | 1,7 s |
| `no_context` | 0% | 90% | 880 | 0 | 1,8 s |

O `text_to_cypher` custou US$ 0,12 nas 52 perguntas porque o schema se repete e entra em cache; o `graph_tools` sem cache sai por cerca de US$ 0,40. O Cypher livre troca abstenção por alucinação: responde quase sempre, e erra com mais confiança.

### Como reportar sem inflar

1. **A assimetria de ajuste vai no texto principal, não no rodapé.** O `text_to_cypher` é primeiro contato; o `graph_tools` passou por sete congelamentos de ferramentas e por uma correção com reexecução de 6 perguntas (39 de 52 antes, 45 depois). Os 17 pontos entre eles são o teto do ganho de engenharia.
2. **A trajetória de versões vira resultado:** o `graph_tools` foi de 50% (primeiro contato nas perguntas de grafo) a 95% no mesmo grupo. É o custo de construir as primitivas, comparado ao Cypher, que chega a 70% sem ajuste nenhum.
3. **`stats_in_prompt` zera por construção** e agora tem um papel: é o degrau em que a lógica está toda pronta e por isso não serve a perguntas com recorte.
4. **O controle não discrimina:** todos acertam as 5 sem resposta, exceto `graph_tools` e `text_to_cypher` na u03 e u01, que aproximaram uma medida inexistente.

### Achado metodológico para a discussão

O "principal elo da circulação de bola" da partida inteira (n01, n02) saiu no teste de robustez: dá Otamendi na maioria das leituras e Enzo Fernández com a rede pesada por número de passes e sem direção. O conceito mais citado em redes de passes é justamente o que a linguagem natural não fixa. Das 81 perguntas escritas, 22 foram removidas por instabilidade ou ambiguidade.

## Ameaças à validade

A ameaça mais séria continua interna, agora com uma forma mais precisa: o `graph_tools` foi ajustado olhando erros e o `text_to_cypher` não, então a comparação entre os dois degraus mais altos favorece o primeiro. A ameaça de construção que mais preocupava (ferramenta contra grafo) ficou menor, porque os dois braços usam o mesmo grafo.

| Tipo | Ameaça | Mitigação existente | Mitigação barata até 18/10 |
| --- | --- | --- | --- |
| Interna | Ajuste assimétrico: `graph_tools` corrigido após ver erros, `text_to_cypher` em primeiro contato | Histórico de congelamentos no git; página de cada rodada | Declarar os 17 pontos como teto; reportar a trajetória do `graph_tools` (50% a 95% no grupo de rede) |
| Interna | Perguntas removidas depois de ver erros (triângulos, p09, b01, b04) | Motivo registrado em `config/questions.yaml` | Tabela de removidas e motivo no repositório |
| Interna | Reexecução de 6 perguntas só no `graph_tools` | Documentada na execução 12 | Reportar 39/52 antes e 45/52 depois |
| Construção | O ganho vem do grafo ou de qualquer consulta estruturada? `text_to_cypher` e `graph_tools` usam o mesmo grafo, mas nenhum braço consulta uma tabela relacional | Par controlado isola quem escreve a lógica | Declarar como trabalho futuro um braço texto-para-SQL sobre a mesma tabela de eventos |
| Construção | `text_to_cypher` sem a biblioteca GDS: intermediação precisa ser escrita em Cypher | Escolha deliberada, documentada; a resposta existe em Cypher puro | Declarar |
| Construção | Perguntas fechadas medem correção, não qualidade da explicação | Escolha declarada | Comentário qualitativo de 2 ou 3 `rationale` |
| Construção | Descrições de ferramentas e do schema escritas por quem escreveu as perguntas | Ferramentas congeladas antes de cada lote | Declarar |
| Construção | Controle sem resposta não discrimina; `stats_in_prompt` zera por construção | Contas com e sem o controle; o zero passa a ser o degrau rígido da escada | Declarar |
| Externa | Uma partida, um modelo (Claude Haiku 5.5) | Modelo registrado em cada linha de resultado | Amostra com um segundo modelo, se sobrar orçamento |
| Externa | Final famosa: risco de resposta de memória | `no_context` com 0% e prompt sem o nome da partida | Citar o 0% como evidência |
| Conclusão | 1 repetição; `graph_tools` contra `text_to_cypher` com p = 0,057 | McNemar pareado e intervalos de Wilson | 3 repetições em `events_in_prompt`, `text_to_cypher` e `graph_tools` (cerca de US$ 1,50) |

## Estrutura do artigo

Alvo de 10 páginas mais referências, na ordem pedida pela disciplina; sobra uma margem de 2 páginas até o limite de 12.

| Seção | Páginas | Conteúdo | Figuras e tabelas | Referências principais |
| --- | --- | --- | --- | --- |
| Título e resumo | 0,5 | Pergunta da escada de abstração, 6 formas, 52 perguntas, 87% / 70% / 45% / 0%, achado de robustez |  |  |
| 1. Introdução | 1 | Dados de eventos são ricos e relacionais; LLMs prometem consulta em linguagem natural; a escolha de quem faz o cálculo (modelo, consulta escrita pelo modelo, ferramenta pronta); questões de pesquisa |  | 5, 9, 18, 22 |
| 2. Contribuições | 0,5 | As quatro contribuições |  |  |
| 3. Trabalhos relacionados | 1,5 | LLMs no esporte; RAG, contexto longo e GraphRAG; texto para consulta e ferramentas; LLMs e grafos; redes de passes | Tabela de posicionamento (coluna "quem faz a lógica") | 1 a 19 |
| 4. Metodologia (CRISP-DM) | 2,5 | Dados e pipeline; os seis braços como escada; o par controlado `text_to_cypher` e `graph_tools`; perguntas, gabarito, robustez, conferência, métricas | Diagrama da arquitetura; diagrama da escada; exemplo de pergunta com suas leituras | 15, 16, 20, 21, 23 a 27 |
| 5. Experimentos e resultados | 2,5 | Configuração; acerto total com IC; acerto por grupo; McNemar entre degraus; custo e perfil de erro; trajetória de ajuste do `graph_tools` | Gráfico por grupo; tabela de pares; tabela de custo; trajetória | 7, 8, 10, 13, 16 |
| 6. Discussão | 1 | O U invertido; por que cada degrau erra; custo de engenharia contra ganho; robustez dos conceitos de rede; ameaças | Tabela de ameaças compacta | 7, 13, 16, 17, 19, 23 |
| 7. Conclusão | 0,5 | Respostas às QPs; trabalhos futuros (texto para SQL, agente com Python, várias partidas, outros modelos, repetições) |  |  |
| Declaração de IA generativa | 0,25 | Exigência da disciplina |  |  |
| Referências | 1 a 1,5 | 27 |  |  |

Os números da coluna de referências seguem a tabela de referências acima.

**Escolha de idioma.** Português facilita a banca; inglês facilita uma submissão futura. Como os nomes de braços e o código já estão em inglês, os dois funcionam.

**Título de trabalho:** "Quem faz o cálculo? Seis formas de dar a um LLM acesso a dados de eventos de futebol". Alternativa mais descritiva: "Do contexto longo às ferramentas: um benchmark verificável de consultas em linguagem natural sobre uma partida de futebol".

**Do rascunho do colega, o que vira texto:** a lista de exclusões de escopo (Metodologia), o parágrafo de LGPD (Metodologia, 3 a 4 linhas) e o formato de hipóteses que admitem resultado negativo (Introdução). O resto não se aproveita: título, pergunta de pesquisa, H0/H1, a seção de experimentos e a conclusão descrevem a v1 (juízes LLM, fidelidade de citação, painel), e a anedota de abertura cita Pollard (2002) para uma afirmação que a fonte contradiz. Nenhuma referência dele entra.

## Figuras e tabelas planejadas

Nove exibições cabem em 10 páginas; só os dois diagramas (arquitetura e escada) precisam ser feitos do zero, as outras já têm os dados prontos no repositório e só precisam virar PDF ou LaTeX.

| # | Exibição | O que mostra | Fonte dos dados | Como produzir | Estado |
| --- | --- | --- | --- | --- | --- |
| F1 | Arquitetura | JSON bruto, camada 0, Neo4j, os seis braços, gabarito independente e conferência | `docs/09-transformacoes-dos-dados.md` | TikZ ou draw.io em PDF | a fazer |
| F2 | A escada | Os seis braços ordenados por quanto da lógica está pronta, com o acerto e o IC de Wilson de cada um: o U invertido | `final_results.jsonl` | `scripts/figures.py` | dados prontos |
| F3 | Acerto por grupo | O gráfico da seção de resultados deste dossiê (quatro braços, quatro grupos) | `final_results.jsonl` | `scripts/figures.py` | dados prontos |
| F4 | Trajetória de ajuste | Acerto do `graph_tools` em cada versão, com o `text_to_cypher` como linha de referência de primeiro contato | páginas de `docs/execucoes/` | `scripts/figures.py` | montar a série |
| F5 | Exemplo de robustez | n01 (removida) e s01 (mantida) com a resposta em cada leitura | `robustness.md` | tabela LaTeX | dados prontos |
| T1 | Posicionamento | Tabela de trabalhos relacionados, com a coluna "quem faz a lógica" | este dossiê | LaTeX | pronta |
| T2 | Os seis braços | O que cada um recebe, tokens, ferramentas, limite de chamadas | `docs/04-os-cinco-bracos.md` | LaTeX | dados prontos |
| T3 | Pares de McNemar | Os três pares entre degraus vizinhos | `final_results.jsonl` | `scripts/figures.py` | dados prontos |
| T4 | Custo e erros | Alucinação, abstenção, tokens, chamadas, latência | `final_results.jsonl` | `scripts/figures.py` | dados prontos |

Se faltar espaço, F5 vira um parágrafo e T3 entra como frase no texto. F2 é a figura que carrega o artigo; F3 diz onde a lógica pronta importa; F4 diz quanto ela custou.

Para a apresentação (até 15 slides, 20 minutos), F1 a F4 viram slides diretos, e uma demonstração ao vivo do `ask.py` com uma pergunta de rede ocupa 2 minutos.

## Plano de implementação

O código fecha neste fim de semana (10 e 11/10) e daqui em diante não muda; os seis dias seguintes são só de escrita, para entregar em 18/10.

&#91;embedded content: cronograma de 10 a 23/10/2026 · entrega em 18/10\]

A única mudança de código depois de 11/10 seria corrigir um número errado encontrado ao escrever, nunca ajustar ferramenta ou pergunta.

### Código (10 e 11/10)

- [ ] Fazer merge da `refactor/benchmark-final` e criar a tag `paper-final`; a partir dela nenhuma ferramenta, pergunta ou schema muda
- [ ] Rodar 3 repetições de `events_in_prompt`, `text_to_cypher` e `graph_tools` nas 52 perguntas, sem nenhuma correção no meio (cerca de US$ 1,50); decide se a diferença entre os dois degraus mais altos é significativa
- [ ] Criar `scripts/figures.py`: escada (F2), grupos (F3), trajetória (F4), tabelas de McNemar e de custo (T3, T4), tudo a partir dos arquivos versionados
- [ ] Criar `paper/` no repositório: `main.tex` com uma seção por arquivo, `refs.bib` gerado pelos DOIs, `generated/numbers.tex` com cada número do texto como macro, e um `CLAUDE.md` com o guia de estilo
- [ ] Confirmar o template da disciplina pelo MCP do Overleaf antes de portar texto

### Texto (12 a 17/10)

- [ ] Confirmar a classe LaTeX do template e montar o esqueleto com as seções da tabela de estrutura
- [ ] BibTeX das 27 referências, conferindo os 3 DOIs pendentes (4, 6 e 11)
- [ ] Metodologia a partir da seção CRISP-DM deste dossiê e de `docs/09`
  - [ ] Incluir na Metodologia o parágrafo de LGPD e as exclusões de escopo do rascunho do colega, reescritos
- [ ] Trabalhos relacionados a partir dos seis eixos e da tabela de posicionamento
- [ ] Resultados com F2, F3, T3; Discussão com o achado de robustez e as ameaças
- [ ] Introdução, Contribuições, Conclusão, Resumo e declaração de IA por último, quando os números estiverem fixos
- [ ] Conferir cada número do texto contra os arquivos de resultado versionados
- [ ] Slides: até 15, todos do grupo apresentam, 20 minutos; F1 a F4 viram slides diretos

### Riscos e o que fazer

| Risco | Sinal | Resposta |
| --- | --- | --- |
| As repetições aproximam `graph_tools` e `text_to_cypher` | diferença média abaixo de 10 pontos ou McNemar acima de 0,05 | A tese vira "consulta estruturada vence contexto longo; ferramentas prontas ajudam só em jogadas", que é igualmente defensável |
| As repetições separam os dois | p abaixo de 0,05 | A escada completa se sustenta; reportar com a ressalva do ajuste assimétrico |
| Template com limite mais apertado | mais de 12 páginas no rascunho | Cortar F5 e T3 primeiro, depois condensar Trabalhos Relacionados |
| Provedor fora do ar na rodada | erros de rede no log | O runner retoma com `--resume`; rodar cedo |
| Número divergente entre texto e resultados | valor digitado no `.tex` | Todo número vem de `numbers.tex`; um teste falha se houver dígito solto em frase de resultado |

### Fluxo de escrita com Claude Code e Overleaf

O repositório é a fonte da verdade e o Overleaf só compila: o Claude Code escreve em `paper/` e empurra pelo MCP, e ninguém edita o mesmo arquivo nos dois lados ao mesmo tempo.

| Peça | O que faz | Por que acelera |
| --- | --- | --- |
| `paper/CLAUDE.md` | Guia de estilo: voz impessoal, passado para o que foi feito, presente para o que os resultados mostram, sem travessão, sem adjetivo de propaganda, glossário fixo (braço, degrau, primeiro contato) | Cada sessão escreve no mesmo tom sem repetir instruções |
| Skill `paper-numbers` | Regenera `numbers.tex`, figuras e tabelas a partir de `final_results.jsonl` e das repetições | As 3 repetições atualizam o artigo inteiro sem retoque manual |
| Skill `cite-check` | Para cada `\cite`, busca título, autores e resumo pelo DOI e registra em `paper/claims.md` se a frase é sustentada | Pega erros como o Pollard do rascunho e números de artigo trocados |
| Skill `latex-figures` | Largura de coluna do template, fonte do tamanho do texto, cinza com um destaque, PDF vetorial | Figuras saem prontas para o template na primeira vez |
| Skill `banca-review` | Revisão adversária por seção com as objeções prováveis: ajuste assimétrico, 1 repetição, um modelo, U invertido sustentado por um braço que zera por construção | Antecipa as perguntas dos 20 minutos de banca |

**Ordem que paraleliza:** Metodologia e Trabalhos Relacionados não dependem dos números e podem ser escritos por subagentes enquanto as repetições rodam. Resultados e Discussão depois delas. Introdução, Contribuições e Resumo por último.

**Divisão com o grupo:** tarefas com saída conferida por script, como os slides gerados das figuras e a revisão ortográfica, que não exigem confiar no conteúdo.

## Declaração de uso de IA generativa (rascunho)

A declaração precisa separar o LLM como objeto de estudo do LLM como ferramenta de trabalho; o rascunho abaixo faz isso e deve ser ajustado ao que de fato aconteceu.

> **Declaração de uso de IA generativa.** Este trabalho usa modelos de linguagem em dois papéis distintos. Como objeto de estudo, o modelo Claude Haiku 5.5 (Anthropic), acessado via OpenRouter, é o sistema avaliado nos cinco braços do benchmark; todas as suas respostas foram conferidas por código contra um gabarito calculado sem uso de IA. Como ferramenta de apoio, os autores usaram o Claude (Anthropic), pela interface claude.ai, para revisar o desenho experimental, levantar e resumir trabalhos relacionados e revisar o texto, e o Claude Code para implementar e refatorar parte do código do repositório, sob especificação e revisão dos autores. Todas as referências foram conferidas nas fontes originais, e todos os números reportados vêm dos arquivos de resultado versionados no repositório. Os autores assumem integral responsabilidade pelo conteúdo.

Os commits do repositório já trazem a coautoria do Claude e o link da sessão, o que torna a declaração verificável.

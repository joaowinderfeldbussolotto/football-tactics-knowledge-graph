# 8. Glossário

Termos usados na documentação e no código, em ordem alfabética, explicados
sem pressupor conhecimento prévio.

---

**Abstenção.** Quando o modelo responde "não tenho dados para isso"
(`no_data`) numa pergunta que tinha resposta. Conta como erro, mas é
registrada separadamente da alucinação, porque é um erro honesto (capítulo 5).

**Agente.** Um modelo de linguagem que pode usar ferramentas: ele decide qual
chamar, lê o resultado e decide o próximo passo. No benchmark, só o braço
`graph_tools` é um agente.

**Alucinação.** Quando o modelo dá uma resposta errada como se estivesse
certa. Nas perguntas sem resposta nos dados, qualquer resposta diferente de
"sem dados" é alucinação.

**Aresta.** Num grafo, uma ligação entre dois nós. Exemplo: `PASSOU_PARA`
liga o jogador que passou ao que recebeu.

**Benchmark.** Um teste padronizado para comparar alternativas sob as mesmas
condições. Aqui, comparar cinco formas de entregar dados a um modelo.

**Betweenness centrality (centralidade de intermediação).** Para cada par de
jogadores do time, encontra-se o caminho de passes mais curto entre eles e
conta-se quem está no meio desse caminho. Quanto mais caminhos passam por um
jogador, maior a betweenness dele. É uma medida de "quem liga o time". Não é
o mesmo que dar mais passes (capítulo 3, com exemplo).

**Braço.** Cada uma das cinco formas de entregar dados ao modelo
(`no_context`, `vector`, `events_in_prompt`, `stats_in_prompt`,
`graph_tools`). O nome vem dos experimentos científicos, em que cada braço é
um grupo com um tratamento diferente.

**Camada.** Cada etapa do processamento dos dados: 0 (tabela de ações), 1
(grafo factual), 1b (súmula), 2 (padrões de rede). Capítulo 2.

**Comunidade (Louvain).** Um grupo de jogadores que trocam passes
principalmente entre si. O algoritmo Louvain encontra esses grupos, mas com
um componente aleatório: os grupos podem mudar de uma execução para outra.

**Condução.** Andar com a bola dominada. No formato SPADL se chama `dribble`,
o que confunde; na camada 0 vira `conducao`.

**Contexto (janela de contexto).** O tamanho máximo de texto, em tokens, que
um modelo consegue ler de uma vez. O braço `events_in_prompt` precisa de
cerca de 70 mil tokens.

**Cypher.** A linguagem de consulta do Neo4j. Descreve caminhos no grafo:
`(a:Jogador)-[:PASSOU_PARA]->(b:Jogador)`.

**Desarme certo / tentado.** Tentado: o jogador tentou tirar a bola do
adversário. Certo: conseguiu. Enzo Fernandez tentou 9 e acertou 5 na final.

**Determinístico.** Que dá sempre o mesmo resultado para a mesma entrada.
As camadas 0 a 2 e a correção das respostas são determinísticas; um LLM não é
garantidamente.

**Drible.** Tentativa de passar pelo marcador com a bola. No SPADL se chama
`take_on`.

**Embedding.** Uma lista de números (um vetor) que representa o sentido de um
texto. Textos parecidos têm vetores parecidos. É a base do braço `vector`.

**Fase de posse.** Uma sequência de ações seguidas do mesmo time com a bola,
até perdê-la ou a jogada parar. A final teve 537.

**Field tilt.** A fatia de um time nos passes feitos no terço de ataque,
somando os dois times. Mede domínio territorial: 54% (Argentina na final)
quer dizer que, de todos os passes dados no terço final do adversário pelos
dois times, 54% foram da Argentina. 50% é equilíbrio.

**Gabarito.** A resposta certa de cada pergunta, calculada por código a partir
dos dados brutos (capítulo 3). Fica em `data/benchmark/ground_truth.json`.

**GDS (Graph Data Science).** Uma biblioteca do Neo4j com algoritmos de grafo
prontos (betweenness, Louvain, pontes...).

**Grafo.** Um jeito de guardar dados como nós (coisas) e arestas (ligações).
Bom para perguntas sobre relações.

**JSON / JSON Lines.** JSON é um formato de texto para dados estruturados. O
JSON Lines (`.jsonl`) tem um objeto JSON por linha; é o formato de
`results.jsonl`, que permite gravar uma execução por vez.

**Langfuse.** Um serviço que mostra, passo a passo, cada conversa com o
modelo. Opcional; serve para investigar erros, não para medir.

**LLM (Large Language Model).** Modelo de linguagem grande, como ChatGPT,
Claude ou Gemini. Lê e escreve texto.

**Neo4j.** O banco de dados em grafo usado no projeto.

**networkx.** Uma biblioteca Python de grafos, usada para recalcular a rede de
passes de forma independente do Neo4j, no gabarito.

**Nó.** Num grafo, uma "coisa": um jogador, um time, uma zona do campo.

**Parquet.** Um formato de arquivo de tabela, compacto e rápido. A camada 0
grava a tabela de ações em Parquet.

**Ponte.** Uma ligação da rede de passes que, se removida, separa o time em
dois grupos sem conexão. A final não teve nenhuma.

**Posse de bola (por tempo).** A porcentagem do tempo em que cada time teve a
bola, somando a duração das fases de posse. Não é a proporção de toques, que
favoreceria quem toca muito.

**PPDA (Passes Per Defensive Action).** Quantos passes o adversário troca, em
média, antes de o time fazer uma ação defensiva (desarme, interceptação,
falta). **Quanto menor, mais o time pressiona.**

**Prompt.** O texto enviado ao modelo: instrução de sistema, dados (quando o
braço os envia) e pergunta.

**PydanticAI.** A biblioteca Python que o projeto usa para conversar com os
modelos, definir ferramentas e exigir o formato de resposta.

**RAG (Retrieval-Augmented Generation).** Buscar trechos relevantes de um
acervo e entregá-los ao modelo junto com a pergunta. O braço `vector` é um RAG
vetorial.

**Saída estruturada.** Obrigar o modelo a responder preenchendo campos fixos
(aqui: `rationale`, `players`, `value`, `no_data`), em vez de texto livre.

**Similaridade de cosseno.** Uma medida, de -1 a 1, de quanto dois vetores
apontam na mesma direção. Usada para achar as linhas de evento mais parecidas
com a pergunta.

**SPADL.** Formato padronizado de ações de futebol: uma linha por ação com
bola, com os mesmos campos para todo tipo de ação, e o campo virado para que
todo time ataque da esquerda para a direita.

**StatsBomb Open Data.** Dados gratuitos de partidas publicados pela empresa
StatsBomb, incluindo a Copa do Mundo de 2022.

**Súmula (camada 1b).** As estatísticas pré-calculadas de cada jogador e de
cada time (passes, desarmes, gols...), guardadas no Neo4j.

**Temperatura.** Um ajuste do modelo que controla o quanto ele "sorteia" as
palavras. Com 0, escolhe sempre a mais provável.

**Terço do campo.** O campo dividido em três faixas no comprimento: defesa,
meio e ataque.

**Token.** O pedaço de texto que o modelo lê e escreve, em geral uma palavra
curta ou parte de uma palavra. Os provedores cobram por token.

**Tool calling (chamada de ferramenta).** A capacidade do modelo de pedir
que o programa execute uma função (uma "ferramenta") e de usar o resultado.

**VAEP (Valuing Actions by Estimating Probabilities).** Mede o valor de cada
ação pela mudança na chance de marcar **e** de sofrer gol logo depois. É
calculado por um modelo treinado com jogos da Copa.

**xT (expected threat, ameaça esperada).** Cada zona do campo tem um valor que
indica a chance de aquela posse virar gol. Levar a bola de uma zona fraca
para uma forte gera xT positivo. O passe de Mac Allister para Di María, no
gol de 36', gerou 0,070.

**Zona.** Uma das 96 células da grade de 12 × 8 em que o campo é dividido. A
coluna 0 fica junto ao próprio gol; a 11, junto ao gol adversário.

# football-tactics-knowledge-graph

Um benchmark que responde uma pergunta:

> Dado o registro de eventos de uma partida de futebol, qual a melhor forma de
> permitir perguntas em linguagem natural: vetorizar, colocar tudo no prompt,
> colocar dados processados no prompt, ou deixar o modelo consultar um grafo
> por ferramentas?

Os dados são a final da Copa do Mundo de 2022, Argentina x França (StatsBomb
Open Data). São 52 perguntas fechadas (as 25 do benchmark original mais 27 de grafo e de
leitura tática), cada uma com resposta certa calculada por código, testada
em todas as leituras razoáveis da pergunta, e corrigida por código; nenhum
LLM dá nota. Há cinco braços principais e um sexto, opcional
(`text_to_cypher`).

## Comece por aqui

A documentação foi escrita para ser lida em ordem, sem conhecimento prévio:

| Capítulo | O que você aprende |
|---|---|
| [1. Visão geral](docs/01-visao-geral.md) | a pergunta do benchmark, os 5 braços e os 5 tipos de pergunta, com analogias |
| [2. Dos dados ao grafo](docs/02-dos-dados-ao-grafo.md) | o caminho do JSON bruto ao banco em grafo, acompanhando o gol de Di María |
| [3. Perguntas e gabarito](docs/03-perguntas-e-gabarito.md) | o arquivo de perguntas, como a resposta certa é calculada e conferida |
| [4. Os cinco braços](docs/04-os-cinco-bracos.md) | exatamente o que cada braço envia ao modelo, com trechos reais |
| [5. Conferência e métricas](docs/05-conferencia-e-metricas.md) | como cada resposta é corrigida e como ler o relatório |
| [6. Como rodar](docs/06-como-rodar.md) | passo a passo do zero, local ou Docker, e solução de problemas |
| [7. Decisões e limitações](docs/07-decisoes-e-limitacoes.md) | por que cada escolha, problemas achados nos dados, o que o benchmark não diz |
| [8. Glossário](docs/08-glossario.md) | todos os termos técnicos em linguagem simples |
| [9. Transformações dos dados](docs/09-transformacoes-dos-dados.md) | tudo o que acontece com os dados, do JSON bruto ao que cada braço vê, e como o gabarito é calculado |
| [Registro das execuções](docs/execucoes/README.md) | cada execução do benchmark: configuração, custo real, resultado, achados e links para os traces |

## Em uma tabela

| Braço | O modelo recebe |
|---|---|
| `no_context` | só a pergunta (mede a memória do modelo) |
| `vector` | as 30 linhas de evento mais parecidas com a pergunta |
| `events_in_prompt` | todos os 2.585 lances da partida (~111 mil tokens) |
| `stats_in_prompt` | a súmula por jogador e por time |
| `graph_tools` | 7 ferramentas primitivas que consultam o grafo no Neo4j |

| Tipo de pergunta (5 de cada) | Exemplo |
|---|---|
| `fact` | "Quem cometeu a falta que deu origem ao primeiro pênalti da final?" |
| `filtered_aggregation` | "Depois do gol que deixou o placar em 2 a 2 no tempo normal, quantas finalizações a Argentina fez até o fim da prorrogação?" |
| `network` | "Qual dupla da França mais trocou passes entre si na final?" |
| `network_slice` | "Na prorrogação, quem foi o principal elo da circulação de bola da França?" |
| `unanswerable` | "Quantos minutos Messi passou no campo de ataque durante a final?" |

As perguntas ficam em [`config/questions.yaml`](config/questions.yaml).

## Rodar em 5 comandos

Com Docker e Python 3.11 (detalhes e caminho só com Docker no
[capítulo 6](docs/06-como-rodar.md)):

```bash
cp .env.example .env                       # preencha as chaves de LLM e de embeddings
scripts/local_setup.sh                     # ambiente, Neo4j e camadas de dados, sem custo de API
source .venv/bin/activate
python scripts/check_ground_truth.py       # gabarito x grafo: tem de dar 52/52
python scripts/run_benchmark.py --sample   # 1 pergunta por tipo, centavos
```

Depois, a execução completa (`python scripts/run_benchmark.py --fresh`).

## Fazer perguntas livres

Qualquer pergunta sobre a final, fora as do benchmark. Não há gabarito:
a resposta é mostrada, não corrigida.

```bash
python scripts/ask.py --arm graph_tools                   # modo interativo: uma pergunta por linha, "sair" encerra
python scripts/ask.py "Quem tocou mais na bola?"          # uma pergunta, nos 5 braços
python scripts/ask.py "Quem tocou mais na bola?" --arm stats_in_prompt
python scripts/ask.py --question s03                      # uma pergunta do benchmark, com gabarito
```

Cada braço mostra a resposta, as ferramentas chamadas (no `graph_tools`) e o
link do trace no Langfuse. Escolher um braço com `--arm` é mais barato e mais
rápido do que consultar os cinco.

## Resultados

Rodada consolidada: 52 perguntas × 6 braços × 1 repetição, Claude Haiku 5.5,
custo de US$ 1,04 (arquivo [`data/benchmark/final_results.jsonl`](data/benchmark/final_results.jsonl),
página [`docs/execucoes/2026-10-10_14_final.md`](docs/execucoes/2026-10-10_14_final.md)).

| Braço | Acertos | Sem as 5 perguntas sem resposta |
|---|---|---|
| `graph_tools` | 45/52 (87%) | 41/47 (87%) |
| `text_to_cypher` | 37/52 (71%) | 33/47 (70%) |
| `events_in_prompt` | 26/52 (50%) | 21/47 (45%) |
| `vector` | 10/52 (19%) | 5/47 (11%) |
| `no_context` | 5/52 (10%) | 0/47 |
| `stats_in_prompt` | 5/52 (10%) | 0/47 |

Com 1 repetição por pergunta, são números de uma amostra: a rodada do
artigo repete 3 vezes. Cada execução, com configuração, custo, resultado e
links para os traces, fica registrada em
[`docs/execucoes/`](docs/execucoes/README.md).

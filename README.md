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
LLM dá nota. São seis braços (cinco principais e o `text_to_cypher`), rodados
em quatro modelos: dois fechados e dois de pesos abertos, um barato e um caro
de cada.

## Comece por aqui

A documentação foi escrita para ser lida em ordem, sem conhecimento prévio:

| Capítulo | O que você aprende |
|---|---|
| [1. Visão geral](docs/01-visao-geral.md) | a pergunta do benchmark, os 6 braços, os 5 grupos de pergunta e os 4 modelos, com analogias |
| [2. Dos dados ao grafo](docs/02-dos-dados-ao-grafo.md) | o caminho do JSON bruto ao banco em grafo, acompanhando o gol de Di María |
| [3. Perguntas e gabarito](docs/03-perguntas-e-gabarito.md) | o arquivo de perguntas, como a resposta certa é calculada e conferida |
| [4. Os seis braços](docs/04-os-cinco-bracos.md) | exatamente o que cada braço envia ao modelo, com trechos reais |
| [5. Conferência e métricas](docs/05-conferencia-e-metricas.md) | como cada resposta é corrigida e como ler o relatório |
| [6. Como rodar](docs/06-como-rodar.md) | passo a passo do zero, local ou Docker, e solução de problemas |
| [7. Decisões e limitações](docs/07-decisoes-e-limitacoes.md) | por que cada escolha, os quatro modelos e suas condições, problemas achados nos dados, o que o benchmark não diz |
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
python scripts/ask.py "Quem tocou mais na bola?"          # uma pergunta, nos braços de config/benchmark.yaml
python scripts/ask.py "Quem tocou mais na bola?" --arm stats_in_prompt
python scripts/ask.py --question s03                      # uma pergunta do benchmark, com gabarito
```

Cada braço mostra a resposta, as ferramentas chamadas (no `graph_tools`) e o
link do trace no Langfuse. Escolher um braço com `--arm` é mais barato e mais
rápido do que consultar todos.

## Resultados

Acerto nas 47 perguntas com resposta (as outras 5 são de controle), uma
repetição por pergunta, em quatro modelos pareados por preço:

| Braço | Claude Haiku 5.5 | Qwen3.8-flash | Claude Sonnet 4.6 | Kimi K3 |
|---|---|---|---|---|
| `graph_tools` | 41/47 (87%) | 39/47 (83%) | 42/47 (89%) | 42/47 (89%) |
| `text_to_cypher` | 33/47 (70%) | 27/47 (57%) | 42/47 (89%) | 44/47 (94%) |
| `events_in_prompt` | 21/47 (45%) | 19/47 (40%) | 34/47 (72%) | 40/47 (85%) |
| `vector` | 5/47 (11%) | 4/47 (9%) | 7/47 (15%) | 8/47 (17%) |
| `stats_in_prompt` | 0/47 | 2/47 (4%) | 4/47 (9%) | 3/47 (6%) |
| `no_context` | 0/47 | 0/47 | 0/47 | 0/47 |
| **Tipo** | fechado, barato | pesos abertos, barato | fechado, caro | pesos abertos, caro |
| **Custo da rodada** | US$ 1,04 | ~US$ 0,49 | ~US$ 28 (com refações) | US$ 33,40 |

As ferramentas prontas (`graph_tools`) acertam entre 83% e 89% em todos os
modelos. Nos modelos baratos, elas são claramente a melhor forma; nos caros,
o modelo que escreve as próprias consultas (`text_to_cypher`) chega ao mesmo
lugar, e o que lê a tabela inteira (`events_in_prompt`) chega perto, a um
custo bem maior de tempo e de tokens. Nos dois caros, o tamanho do modelo e
o raciocínio vêm juntos; o Sonnet 4.6 usa esforço de raciocínio diferente no
`events_in_prompt`. Condições de cada rodada e limites dessa leitura:
[capítulo 7](docs/07-decisoes-e-limitacoes.md).

| Modelo | Arquivo de resultados | Página da execução |
|---|---|---|
| Claude Haiku 5.5 | [`final_results.jsonl`](data/benchmark/final_results.jsonl) | [`2026-10-10_14_final.md`](docs/execucoes/2026-10-10_14_final.md) |
| Qwen3.8-flash | [`qwen_results.jsonl`](data/benchmark/qwen_results.jsonl) | [`2026-10-12_15_qwen.md`](docs/execucoes/2026-10-12_15_qwen.md) |
| Claude Sonnet 4.6 | [`sonnet46_combined_results.jsonl`](data/benchmark/sonnet46_combined_results.jsonl) | [`2026-10-13_17_sonnet46.md`](docs/execucoes/2026-10-13_17_sonnet46.md) (rodada `medium`) |
| Kimi K3 | [`kimi_k3_results.jsonl`](data/benchmark/kimi_k3_results.jsonl) | [`2026-10-12_16_kimi-k3.md`](docs/execucoes/2026-10-12_16_kimi-k3.md) |

Com uma repetição por pergunta, são números de uma amostra, com intervalos
de confiança largos (cerca de ±12 pontos). Cada execução, com configuração,
custo, resultado e links para os traces, fica registrada em
[`docs/execucoes/`](docs/execucoes/README.md).

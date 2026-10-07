# football-tactics-knowledge-graph

Um benchmark que responde uma pergunta:

> Dado o registro de eventos de uma partida de futebol, qual a melhor forma de
> permitir perguntas em linguagem natural: vetorizar, colocar tudo no prompt,
> colocar dados processados no prompt, ou deixar o modelo consultar um grafo
> por ferramentas?

Os dados são a final da Copa do Mundo de 2022, Argentina x França (StatsBomb
Open Data). São 30 perguntas fechadas, cada uma com resposta certa calculada
por código e corrigida por código; nenhum LLM dá nota.

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
| [Registro das execuções](docs/execucoes/README.md) | cada execução do benchmark: configuração, custo real, resultado, achados e links para os traces |

## Em uma tabela

| Braço | O modelo recebe |
|---|---|
| `no_context` | só a pergunta (mede a memória do modelo) |
| `vector` | as 30 linhas de evento mais parecidas com a pergunta |
| `events_in_prompt` | todos os 2.585 lances da partida (~68 mil tokens) |
| `stats_in_prompt` | a súmula por jogador e por time |
| `graph_tools` | 8 ferramentas que consultam o grafo no Neo4j |

| Tipo de pergunta (6 de cada) | Exemplo |
|---|---|
| `factual` | "Quem deu a assistência para o segundo gol da França na final?" |
| `aggregation` | "Quem fez mais desarmes certos na final? Liste os 3 primeiros." |
| `structural` | "Quem foi o jogador da Argentina por quem passava o maior número de rotas de passe entre os companheiros?" |
| `composite` | "Quantos passes errou esse jogador?" |
| `unanswerable` | "Qual foi a velocidade máxima atingida por Mbappé na final?" |

As perguntas ficam em [`config/questions.yaml`](config/questions.yaml).

## Rodar em 5 comandos

Com Docker e Python 3.11 (detalhes e caminho só com Docker no
[capítulo 6](docs/06-como-rodar.md)):

```bash
cp .env.example .env                       # preencha as chaves de LLM e de embeddings
scripts/local_setup.sh                     # ambiente, Neo4j e camadas de dados, sem custo de API
source .venv/bin/activate
python scripts/check_ground_truth.py       # gabarito x grafo: tem de dar 30/30
python scripts/run_benchmark.py --sample   # 1 pergunta por tipo, centavos
```

Depois, a execução completa (`python scripts/run_benchmark.py --fresh`) e
perguntas isoladas (`python scripts/ask.py --question s03`).

## Resultados

Primeira execução: **Claude Haiku 5.5** (via OpenRouter), **1 repetição** (150
execuções), com cache de prompt. Custo real ~US$ 0,25. Relatório completo em
[`data/benchmark/summary.md`](data/benchmark/summary.md); cada resposta em
[`data/benchmark/results.jsonl`](data/benchmark/results.jsonl); análise e links para os
traces em [`docs/execucoes/`](docs/execucoes/README.md).

| Tipo | `no_context` | `vector` | `events_in_prompt` | `stats_in_prompt` | `graph_tools` |
|---|---|---|---|---|---|
| factual | 0% | 33% | **100%** | 33% | **100%** |
| aggregation | 0% | 17% | 33% | 50% | **100%** |
| structural | 0% | 0% | 17% | 0% | **100%** |
| composite | 0% | 0% | 0% | 17% | **83%** |
| unanswerable | 100% | 100% | 100% | 100% | 100% |
| **total** | 20% | 30% | 50% | 40% | **97%** |

| Braço | Alucinação | Abstenção |
|---|---|---|
| `no_context` | 0% | 80% |
| `vector` | **47%** | 23% |
| `events_in_prompt` | 37% | 13% |
| `stats_in_prompt` | 17% | 43% |
| `graph_tools` | 3% | 0% |

Como ler, com cuidado:

- **Uma repetição só, 6 perguntas por tipo**: cada célula de tipo é de 0 a 6
  acertos. As tendências são claras, mas os números ainda não medem
  consistência (a tabela de repetições fica vazia com 1 execução).
- **Um modelo, sem raciocínio estendido.** Na amostra com o DeepSeek V4 Pro,
  que raciocina, o `events_in_prompt` acertou contagens que o Haiku errou.
- **Dois defeitos conhecidos do benchmark**, achados nesta execução:
  - **c05**: nenhuma ferramenta conta passes entre dois jogadores específicos,
    então o `graph_tools` não tinha como responder (é o seu único erro);
  - **c06** confere só o número: o `stats_in_prompt` acertou com o jogador
    errado, por coincidência (Tchouaméni e Koundé fizeram 2 faltas cada).

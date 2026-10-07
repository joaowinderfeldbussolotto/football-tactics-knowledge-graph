# football-tactics-knowledge-graph

Um benchmark que responde uma pergunta só:

> Dado um JSON de eventos de futebol, qual a melhor forma de permitir perguntas
> em linguagem natural: vetorizar, colocar tudo no prompt, colocar dados
> processados no prompt, ou deixar o LLM percorrer um grafo via tools?

Dados: a final da Copa do Mundo de 2022, Argentina x França (StatsBomb Open
Data, partida 3869685). Detalhes, decisões e limitações estão em
**[docs/benchmark.md](docs/benchmark.md)**.

## Os 5 braços

Todos usam o mesmo modelo, o mesmo prompt de sistema, `temperature=0` e a
mesma saída estruturada. Só muda o que o LLM recebe.

| Braço | O LLM recebe |
|---|---|
| `no_context` | só a pergunta (mede o que o modelo sabe de memória) |
| `vector` | os 30 eventos mais parecidos com a pergunta (embeddings) |
| `events_in_prompt` | a tabela de todos os eventos da partida (~63 mil tokens) |
| `stats_in_prompt` | estatísticas agregadas por jogador e por time, lidas do Neo4j |
| `graph_tools` | 8 tools com Cypher fixo sobre o Neo4j, incluindo algoritmos do GDS |

## Os 5 tipos de pergunta (6 de cada)

| Tipo | Exige | Exemplo |
|---|---|---|
| `factual` | achar um fato | "Quem deu a assistência para o segundo gol da França?" |
| `aggregation` | contar e ordenar | "Quem fez mais desarmes certos? Top 3." |
| `structural` | algoritmo de grafo | "Quem foi o jogador da Argentina por quem passavam mais rotas de passe entre os companheiros?" |
| `composite` | estrutural + agregação | "Quantos passes errou esse jogador?" |
| `unanswerable` | perceber que o dado não existe | "Qual a velocidade máxima do Mbappé?" |

O gabarito é calculado **sem o Neo4j**: do JSON bruto do StatsBomb, e com
networkx sobre o Parquet para as estruturais. Ele é conferido contra o grafo
(30/30). Nenhum LLM dá nota; a conferência é feita por código.

## Como rodar do zero

Pré-requisitos: Docker e Python 3.11 (o `socceraction` não instala em 3.13).

```bash
cp .env.example .env            # preencha LLM_* e EMBEDDER_* (Langfuse é opcional)
scripts/local_setup.sh          # venv + Neo4j (GDS/APOC) + camadas 0, 1/1b e 2, sem custo de API
source .venv/bin/activate
```

O `local_setup.sh` roda os passos abaixo. Para fazê-los à mão:

```bash
docker compose up -d neo4j
python scripts/download_statsbomb.py      # JSON bruto (eventos + escalações)
python scripts/run_pipeline.py            # camada 0: SPADL, xT, VAEP -> Parquet
python scripts/build_graph.py             # camadas 1 e 1b: grafo factual + súmula
python scripts/run_analysis.py            # camada 2: padrões do GDS (usados só na checagem cruzada)
```

Depois, o benchmark:

```bash
python scripts/check_ground_truth.py      # gabarito x grafo, 30/30, sem LLM
python scripts/smoke_llm.py               # o modelo faz tool calling e saída estruturada?
python scripts/run_benchmark.py --sample  # 1 pergunta por tipo, 1 repetição (centavos)
python scripts/run_benchmark.py           # 30 perguntas x 5 braços x 3 repetições
python scripts/summarize.py               # refaz o summary.md a partir do results.jsonl, sem LLM
```

O `run_benchmark.py` grava cada execução em `data/benchmark/results.jsonl` logo
depois da chamada. Se cair, `--resume` continua de onde parou. Também aceita
`--repeats N`, `--arms a,b` e `--questions f01,s02`. Com chaves do Langfuse no
`.env`, cada execução vira um span `{pergunta}/{braço}/r{n}`.

## Rodando tudo no Docker

Alternativa ao venv local: os scripts rodam dentro do container `app`, ao
lado do Neo4j. Só precisa de Docker, sem Python na máquina.

```bash
cp .env.example .env                  # preencha LLM_* e EMBEDDER_* (Langfuse é opcional)
docker compose up -d --build          # sobe neo4j (GDS/APOC) + app; o app espera o Neo4j ficar saudável
```

Depois, os mesmos comandos, prefixados com `docker compose exec app`:

```bash
docker compose exec app python scripts/download_statsbomb.py
docker compose exec app python scripts/run_pipeline.py
docker compose exec app python scripts/build_graph.py
docker compose exec app python scripts/run_analysis.py
docker compose exec app python scripts/check_ground_truth.py
docker compose exec app python scripts/smoke_llm.py
docker compose exec app python scripts/run_benchmark.py --sample
docker compose exec app python scripts/run_benchmark.py
docker compose exec app python scripts/ask.py --question s01 --arm graph_tools
```

O que é bom saber:

- **Código e dados são montados do host** (`./src`, `./scripts`, `./data`).
  Editar o código não exige rebuild, e o `results.jsonl` e o `summary.md`
  aparecem direto em `data/benchmark/` na sua máquina. Só mudanças no
  `pyproject.toml` pedem `docker compose up -d --build`.
- **O `NEO4J_URI` é ajustado pelo compose.** Dentro do container, o Neo4j é
  `bolt://neo4j:7687`, e o compose sobrescreve o valor do `.env`. O mesmo
  `.env` serve para os dois jeitos de rodar.
- **Erro `Temporary failure in name resolution`** no download (comum em
  Codespaces) significa que o container não resolve nomes. Rode
  `docker compose down && docker compose up -d` e tente de novo. Se
  persistir, baixe os dados pelo host: o download nunca refaz um arquivo que
  já existe em `data/raw/`, então o container os encontra pelo volume. Outra
  saída é usar o `scripts/local_setup.sh`.
- Para parar: `docker compose down`. O grafo fica no volume `neo4j_data`;
  `docker compose down -v` o apaga.

## Uma pergunta isolada

Não grava nada em `results.jsonl`:

```bash
python scripts/ask.py --question s01                      # pergunta do benchmark, todos os braços
python scripts/ask.py --question s01 --arm graph_tools    # um braço só
python scripts/ask.py "Quem tocou mais na bola?"          # pergunta livre, todos os braços
python scripts/ask.py "Quem tocou mais na bola?" --arm stats_in_prompt
python scripts/ask.py --question s01 --show-prompt        # mostra também o prompt enviado
```

A saída mostra, por braço, a resposta completa, os tokens, as tools chamadas
(com os argumentos) e a latência. Numa pergunta do benchmark, mostra também o
gabarito e se a resposta acertou.

## Resultados

**Ainda não executado.** O `results.jsonl` e o `summary.md` da execução
completa vão para `data/benchmark/`. A tabela principal (acerto por tipo ×
braço) entra aqui quando a execução for feita.

## Testes

```bash
pytest     # os testes que dependem do Neo4j ou dos dados são pulados sem eles
```

## Histórico

Este repositório começou como uma PoC de GraphRAG (API, Graphiti, juízes LLM).
A documentação daquele sistema está em [docs/legado/](docs/legado/).

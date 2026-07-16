# football-tactics-knowledge-graph

PoC de um GraphRAG tático para futebol: ingestão de eventos do StatsBomb
Open Data, cálculo de métricas táticas (xT, VAEP, PPDA, rede de passes),
carga incremental num grafo de conhecimento temporal (Graphiti + Neo4j),
relatórios táticos pós-jogo e replay "ao vivo" simulado via fila Redis.

Ver o plano completo da PoC para o contexto de design e as decisões já
tomadas (stack, escopo, critérios de validação).

## Stack

Neo4j 5.26 (grafo), Redis (fila do replay), FastAPI (API), Graphiti
(`graphiti-core`, grafo de conhecimento temporal), PydanticAI (geração
estruturada, agnóstica de provedor de LLM), Langfuse (observabilidade OTel),
StatsBomb Open Data + `kloppy` + `socceraction` (ingestão/SPADL/xT/VAEP).

## Quickstart

```bash
cp .env.example .env
# preencha LLM_API_KEY, EMBEDDER_API_KEY, STATSBOMB_MATCH_IDS

docker compose up --build
```

Isso sobe `neo4j`, `redis`, `api` (porta 8000) e `replay-worker`. O Neo4j
Browser fica em http://localhost:7474 (usuário/senha do `.env`).

A API não baixa/processa partidas sozinha no startup — isso é uma etapa
offline, rodada uma vez por partida:

```bash
# dentro do container api, ou localmente com as mesmas env vars:
python scripts/download_statsbomb.py 3869151      # cacheia o JSON bruto em data/raw/
python scripts/run_ingestion.py 3869151           # gera data/processed/3869151.parquet
```

`GET /report/{match_id}` sempre gera a mesma síntese completa da partida.
Pra perguntas específicas ("quem pressionou mais no 2º tempo?", "qual foi o
corredor mais usado pelo Barcelona?"), use `GET /ask/{match_id}?q=...`: ele
roda a mesma busca híbrida sem LLM, mas com a sua pergunta em vez de uma
query fixa, e o agente responde só com base nos fatos recuperados — se o
grafo não tiver o fato, ele diz isso em vez de inventar.

Depois disso:

```bash
curl -X POST "http://localhost:8000/ingest/3869151?mode=batch"   # carrega no grafo
curl "http://localhost:8000/report/3869151"                      # relatório pós-jogo

curl -X POST "http://localhost:8000/replay/3869151/start"        # simula ingestão ao vivo
curl "http://localhost:8000/live/3869151/insights"                # consulta incremental

curl -G "http://localhost:8000/ask/3869151" --data-urlencode "q=quem pressionou mais?"

curl http://localhost:8000/health
```

Para resetar o grafo do zero: `docker compose down -v` (apaga o volume
nomeado do Neo4j).

## Desenvolvimento local sem Docker

```bash
pip install -e ".[dev]"
pytest tests/                              # 21 testes, offline, sem Neo4j/Redis/LLM
python scripts/download_statsbomb.py 15946
python scripts/run_ingestion.py 15946
uvicorn football_graphrag.api.main:app --reload
```

## Avaliação

```bash
python scripts/run_evaluation.py 3869151   # precisa da API rodando e da partida já ingerida
```

Roda o golden dataset (seção 8 do plano) contra `GET /report/{match_id}`:
checagem determinística de fidelidade (`cited_metrics` batendo com o grafo,
sem LLM) + dois scorers LLM-as-judge (`retrieval_accuracy`,
`tactical_insight`). Resultado salvo em `data/processed/eval_results.json`.

## Decisões e limitações conhecidas desta PoC

- **`kloppy` pinado em `3.15.0`**: `socceraction==1.5.3` depende de uma API
  interna do `kloppy` (`CoordinateSystem`) que foi removida em versões
  `3.16+`. Confirmado via teste manual contra o StatsBomb Open Data.
- **Grid de xT com fallback offline**: o modelo de xT usa a grid pública de
  Karun Singh (`karun.in/blog/data/open_xt_12x8_v1.json`). Se o host não
  estiver acessível (proxy/firewall), `spadl_transform.get_xt_model()` cai
  para uma grid uniforme — os valores de xT ficam 0 (uma grid uniforme não
  gera diferença de valor entre células, então nenhuma ação "progride"
  threat). Isso é logado como warning; documentar no relatório se acontecer.
- **VAEP treinado com poucos dados**: `fit_vaep_model` treina um único
  modelo combinando as ações de todas as partidas baixadas na mesma
  execução. Com 2-3 partidas isso é uma amostra pequena demais para um
  modelo com poder preditivo real — é uma limitação de uma PoC com poucos
  dados, não do método; em produção o modelo seria treinado numa base maior.
- **Cross-encoder do Graphiti substituído por um passthrough**: por padrão,
  `Graphiti()` constrói um `OpenAIRerankerClient()` mesmo se `LLM_PROVIDER`
  for outro — o que quebra sem `OPENAI_API_KEY`. Como o retrieval desta PoC
  usa `graphiti.search()` (RRF puro, sem LLM, pelo critério de latência
  <1s), passamos um `CrossEncoderClient` no-op só para satisfazer o
  construtor; nunca é exercitado no caminho quente. Ver
  `llm/provider.py::_PassthroughCrossEncoder`.
- **Fila do replay em Redis, não `asyncio.Queue`**: usada porque o
  `replay-worker` roda como container separado (produtor e consumidor são
  processos de fato distintos, como no desenho de produção). Se isso virar
  um obstáculo, a alternativa mais simples é uma `asyncio.Queue` em memória
  num único processo — ver seção 6.5 do plano.
- **PPDA/field tilt são injetados como um episode extra, só em modo batch**:
  essas métricas são agregados por time/partida, não por ação, então nunca
  apareceriam no texto de nenhum episode de fase de posse.
  `graph/client.py::ingest_match_summary_facts` injeta um episode adicional
  com esses números depois de todas as fases, só no modo batch (injetar o
  total da partida no meio de um replay "ao vivo" vazaria informação do
  futuro pro grafo incremental).
- **Índices do Neo4j: não chamamos `build_indices_and_constraints()`
  explicitamente**: o `Neo4jDriver` do graphiti-core já agenda essa criação
  sozinho como task em background assim que é construído. Como `api` e
  `replay-worker` constroem cada um seu próprio driver, é normal ver um
  `EquivalentSchemaRuleAlreadyExists` nos logs na subida — o graphiti-core
  já trata essa corrida como benigna internamente
  (`Neo4jDriver._execute_index_query`); é só ruído de log, não um erro real.

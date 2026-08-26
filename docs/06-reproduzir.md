# 06 — Reproduzir do zero

## Pré-requisitos

- Docker + Docker Compose
- (opcional, para rodar fora do container) Python 3.11 e [uv](https://docs.astral.sh/uv/)

## 1. Clonar e configurar

```bash
git clone <repo>
cd football-tactics-knowledge-graph
cp .env.example .env
# editar .env: NEO4J_PASSWORD e, para /report, /ask e avaliação,
# LLM_PROVIDER + LLM_API_KEY + LLM_MODEL + EMBEDDER_*
```

Sem chaves de LLM tudo funciona **exceto** `/report`, `/ask`, indexação Graphiti e a
avaliação com juízes — as camadas 0, 1 e 2 são 100% determinísticas e não usam LLM.

## 2. Subir o stack

```bash
docker compose up -d
```

Saída esperada: serviço `neo4j` fica `healthy` (healthcheck `RETURN 1`), depois `api`
sobe em `http://localhost:8000` (docs em `/docs`).

Validar o GDS na primeira subida (Neo4j Browser em `http://localhost:7474`, usuário
`neo4j`, senha do `.env`):

```cypher
RETURN gds.version();   // esperado: "2.13.2"
RETURN apoc.version();  // esperado: "5.26.0"
```

**Pegadinha clássica dos plugins:** `NEO4J_PLUGINS` só baixa os plugins **antes da
primeira inicialização do volume**. Se o volume `neo4j_data` já existe de uma subida
anterior sem plugin, faça `docker compose down -v` e suba de novo.

**Ambiente sem acesso ao GitHub/graphdatascience.ninja** (ver ADR-6): resolva os jars do
Maven Central com um pom contendo `org.neo4j.gds:proc`, `org.neo4j.gds:opengds-extension`,
`org.neo4j.gds:open-model-catalog` e `org.neo4j.gds:open-write-services` (versão 2.13.2) +
`org.neo4j.procedure:apoc-core:5.26.0` (classifier `core`), suba `commons-lang3` para
3.18.0, e monte tudo em `/plugins` do container.

## 3. Baixar dados e rodar a pipeline (camada 0)

```bash
# dentro do container da api (ou no venv local):
docker compose exec api python scripts/run_pipeline.py
```

Saída esperada (primeira execução baixa as 16 partidas de treino e treina xT/VAEP, ~1 min;
as seguintes usam cache e levam ~1,5 s por partida):

```
[3869685] 4527 eventos kloppy -> 2585 ações SPADL (537 fases de posse) em 2.3s
[3869519] 3891 eventos kloppy -> 2274 ações SPADL (346 fases de posse) em 1.9s
[3869354] 3351 eventos kloppy -> 1895 ações SPADL (326 fases de posse) em 1.7s
```

(2585 e não 2584 na final: o passo 0.4h recupera do JSON bruto um cartão que o
SPADL descarta — ver `01-pipeline.md`.)

Artefatos em `data/processed/` (parquet + `_phases` + `_windows` + `_pressures` +
`_meta.json` + `_schema.json` por partida).

## 4. Construir o grafo factual (camada 1)

```bash
docker compose exec api python scripts/build_graph.py
```

Saída esperada (final): `8004 escritas em ~3s` e stats com
`PASSOU_PARA: 989, PRESSIONOU: 301, FaseDePosse: 537, EstatisticaJogador: 26...`.
Rodar duas vezes não muda as contagens (idempotente).

## 5. Rodar a análise (camada 2)

```bash
docker compose exec api python scripts/run_analysis.py
```

Saída esperada:

```
[3869685] 24 padrões táticos: {'pivo_estrutural': 2, 'terceiro_homem': 6, ...}
[3869519] 22 padrões táticos: ...
[3869354] 27 padrões táticos: ...
```

## 5b. Conferir o modelo de dados (sem LLM, sem custo)

```bash
docker compose exec api python scripts/check_golden_queries.py
```

Roda a consulta de referência das 30 perguntas do golden dataset contra o grafo
e imprime, lado a lado, a resposta esperada e o que o grafo devolve. **Não usa
LLM e não consome API.** Saída esperada na última linha:

```
RESUMO: 30/30 perguntas com resposta no grafo
```

Se alguma pergunta ficar sem linhas, o defeito é do modelo de dados — e o
diagnóstico sai daqui em segundos, em vez de depender da avaliação completa.
Aceita filtro por id: `check_golden_queries.py q23 q17`.

## 6. Relatório e Q&A (camada 3 — exige chaves de LLM)

```bash
curl -X POST localhost:8000/analyze/3869685        # (re)gera padrões + indexa no Graphiti
curl localhost:8000/report/3869685                  # relatório estruturado com citações
curl -X POST localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"match_id": 3869685, "pergunta": "Qual jogador foi o gargalo estrutural da progressão da Argentina?"}'
```

Endpoints auxiliares sem LLM: `GET /health`, `GET /graph/3869685/stats`,
`POST /ingest/{match_id}` (camadas 0+1 de uma partida nova).

## 7. Avaliação

```bash
# confere o pipeline antes de comprometer as 30: uma pergunta de cada categoria
docker compose exec api python scripts/run_evaluation.py --amostra --saida eval_amostra.json

# a rodada de verdade
docker compose exec api python scripts/run_evaluation.py
```

Roda o golden dataset (30 perguntas: 15 estruturais, 8 factuais, 4 agregadas e
3 compostas) em **três braços** — grafo sem súmula, grafo com súmula e baseline
vetorial plano —, com fidelidade determinística + juízes LLM, e salva
`data/processed/eval_results.json`. O porquê dos três braços está na ADR-10
(`docs/05-decisoes.md`) e na seção de ablação de `docs/07-validacao.md`.

Flags: `--amostra` (uma pergunta por categoria), `--ids q01,q17` (seleção
explícita), `--saida NOME.json` (não encostar no arquivo citado na
documentação). Com `--amostra`/`--ids`, o índice do baseline é construído só
com as partidas das perguntas escolhidas, para não gastar cota de embeddings.

Formato da saída:

```json
{
  "modelo": "openrouter:stealth/ox-alpha",
  "n_perguntas": 30,
  "faithfulness_media": {"grafo_sem_sumula": 1.0, "grafo_com_sumula": 1.0},
  "por_categoria": {
    "estrutural": {
      "n": 15,
      "grafo_sem_sumula": {"retrieval_previo": 0.0, "retrieval_final": 0.0,
                            "insight": 0.0, "consultas_media": 0.0},
      "grafo_com_sumula": {"retrieval_previo": 0.0, "retrieval_final": 0.0,
                            "insight": 0.0, "consultas_media": 0.0},
      "baseline":         {"retrieval_previo": 0.0, "insight": 0.0}
    }
  }
}
```

(Zeros são o formato, não medições — os números da 3ª rodada, em outro
desenho de avaliação, estão em `docs/03-insights.md`, seção "Avaliação".)

**`retrieval_previo` é a nota comparável com o baseline**; `retrieval_final`
inclui o resultado das consultas que o agente fez durante a geração, e o
baseline não tem ferramenta que produza equivalente. Não misturar as duas.

## 8. Testes

```bash
docker compose exec api pytest tests/ -q
```

Esperado: `62 passed`. Testes que exigem Neo4j/parquet se auto-pulam quando o recurso não
está disponível (rodam completos com o stack de pé e a pipeline executada).

## Troca de provedor de LLM

Editar apenas o `.env` (nenhum código):

```bash
LLM_PROVIDER=anthropic   # ou mistral, gemini, openrouter
LLM_API_KEY=...
LLM_MODEL=claude-sonnet-5
LLM_SMALL_MODEL=claude-haiku-4-5
EMBEDDER_PROVIDER=mistral        # anthropic e openrouter não têm API de embeddings
EMBEDDER_API_KEY=...
EMBEDDER_MODEL=mistral-embed
```

Com `LLM_PROVIDER=openrouter` (ver ADR-9 em `05-decisoes.md` — inclui a ressalva
de modelo stealth): `LLM_MODEL` precisa do formato `vendor/modelo`
(ex. `stealth/ox-alpha`, `anthropic/claude-sonnet-5`) — é o próprio SDK do
PydanticAI que exige, não uma regra do projeto. Antes de rodar a avaliação
completa, `python scripts/smoke_llm.py` testa ferramenta + saída estruturada
com uma pergunta só, em segundos:

```bash
$ python scripts/smoke_llm.py
provedor=openrouter  modelo=stealth/ox-alpha
pergunta: Quantos desarmes certos o Enzo Fernandez fez na final?

saída validou no schema RespostaTatica: sim
...
re-execução das consultas: 100% (1/1)
```

e reiniciar a api: `docker compose restart api`.

Nota sobre **rate limits / chaves free-tier** (ADR-7): `LLM_MAX_RETRIES` é repassado ao
retry nativo de todos os SDKs (LLM, embedder e reranker), que respeitam o
`Retry-After`/`retryDelay` do servidor — 429 esporádico se resolve sozinho. A indexação
do Graphiti (`/analyze`) é adicionalmente ritmada por `GRAPHITI_PACE_SECONDS` (default
2.0, ~3 min por partida, dimensionado para a cota gratuita do Gemini de 100
embed-requests/min); com chave paga use `GRAPHITI_PACE_SECONDS=0`.

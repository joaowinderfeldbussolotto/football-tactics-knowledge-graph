# football-tactics-knowledge-graph

PoC de **grafo tático de futebol com insights não triviais**: dados de evento
(StatsBomb Open Data) passam por uma pipeline determinística, viram um grafo em Neo4j, e
algoritmos de grafo (GDS) produzem insights que **não existem em nenhuma linha da tabela**
— o LLM (Graphiti + PydanticAI) apenas verbaliza e recupera, nunca calcula.

## Arquitetura

```
┌──────────────────────────────────────────────────────────────────┐
│ CAMADA 0: PIPELINE DE DADOS             (determinística, sem LLM) │
│ StatsBomb JSON → kloppy → SPADL → xT/VAEP → métricas → Parquet    │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ CAMADA 1: GRAFO FACTUAL                 (determinística, sem LLM) │
│ Jogador, Time, Zona, FaseDePosse + PASSOU_PARA, PRESSIONOU,       │
│ PROGREDIU_PARA... com valores EXATOS do parquet                   │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ CAMADA 2: ANÁLISE ESTRUTURAL            (Neo4j GDS, sem LLM)      │
│ AQUI NASCEM OS INSIGHTS: betweenness, comunidades, caminhos       │
│ multi-hop, co-ocorrência temporal → nós PadraoTatico              │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ CAMADA 3: INTERPRETAÇÃO E RECUPERAÇÃO   (Graphiti + PydanticAI)   │
│ Relatório e Q&A com citação obrigatória; busca híbrida sem LLM    │
└──────────────────────────────────────────────────────────────────┘
```

## Quickstart

```bash
cp .env.example .env                                  # 1. configurar (chaves de LLM opcionais)
docker compose up -d                                  # 2. Neo4j (GDS+APOC) + API
docker compose exec api python scripts/run_pipeline.py   # 3. camada 0
docker compose exec api python scripts/build_graph.py    # 4. camada 1
docker compose exec api python scripts/run_analysis.py   # 5. camada 2 (insights)
# camada 3: GET /report/{match_id} e POST /ask em localhost:8000 (exige LLM_API_KEY)
```

## Documentação

| Doc | Conteúdo |
|---|---|
| [docs/01-pipeline.md](docs/01-pipeline.md) | linhagem completa StatsBomb → grafo, com contagens reais |
| [docs/02-modelo-grafo.md](docs/02-modelo-grafo.md) | schema do grafo, projeções do GDS, volumes medidos |
| [docs/03-insights.md](docs/03-insights.md) | catálogo dos 8 insights, com exemplos reais das partidas |
| [docs/04-consumo.md](docs/04-consumo.md) | relatório, Q&A, prompts na íntegra, recuperação estruturada |
| [docs/05-decisoes.md](docs/05-decisoes.md) | ADRs (por que a camada 1 não usa LLM, etc.) |
| [docs/06-reproduzir.md](docs/06-reproduzir.md) | passo a passo do zero, com saídas esperadas |
| [docs/07-validacao.md](docs/07-validacao.md) | relatório da execução de validação: todos os números medidos, separados da doc |
| [docs/08-autonomia.md](docs/08-autonomia.md) | o processo do modo autônomo: text-to-Cypher read-only no relatório e no Q&A, bugs reais e regras |

Dados: [StatsBomb Open Data](https://github.com/statsbomb/open-data) (CC BY-NC 4.0, uso
acadêmico com atribuição). Partidas da PoC: Copa do Mundo 2022 — final, semifinal e quartas.

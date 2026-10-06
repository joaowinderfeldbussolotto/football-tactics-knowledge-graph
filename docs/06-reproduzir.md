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
curl -X POST localhost:8000/analyze/3869685        # (re)gera os padrões (camada 2); não toca no Graphiti
curl localhost:8000/report/3869685                  # relatório estruturado com citações
curl -X POST localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"match_id": 3869685, "pergunta": "Qual jogador foi o gargalo estrutural da progressão da Argentina?"}'
```

Endpoints auxiliares sem LLM: `GET /health`, `GET /graph/3869685/stats`,
`POST /ingest/{match_id}` (camadas 0+1 de uma partida nova).

## 6b. Índice do Graphiti (busca híbrida)

```bash
docker compose exec api python scripts/index_graphiti.py
```

Indexa os `PadraoTatico` como fatos temporais e constrói as comunidades. Até a
4ª rodada isso só acontecia dentro da rota `POST /analyze/{match_id}`: quem
reproduzia pelos scripts nunca criava o índice, e a busca híbrida ficava
dormente sem avisar (ADR-11). Desde a ADR-13 a rota **não indexa mais**: este
script é o único caminho. Custo: ~3-4 chamadas de embedding por padrão,
espaçadas por `GRAPHITI_PACE_SECONDS`.

**É o único passo caro, e é retomável** (ADR-13). Rodar de novo depois de uma
queda **não** apaga nem repaga o que já foi indexado: padrões existentes são
pulados, e as comunidades só são construídas nas partidas que ainda não as têm.

```bash
python scripts/index_graphiti.py                          # retoma de onde parou
python scripts/index_graphiti.py --so-comunidades         # refaz só as comunidades
python scripts/index_graphiti.py --do-zero                # apaga e refaz TUDO (repaga)
python scripts/index_graphiti.py --partidas 3869685       # só uma partida
```

Se a construção de comunidades falhar numa partida (aconteceu: o provedor
devolveu resposta vazia 4 vezes seguidas), o script **não aborta**: segue para
as demais, lista as pendentes no fim e sai com código 2. Os triplets dessa
partida já estão gravados; `--so-comunidades` refaz só o que faltou. Para o Q&A
isso não é fatal — a busca híbrida funciona sobre os fatos, e as comunidades
só acrescentam resumos.

Atenção a quem atualizar de uma versão anterior: o `index_graphiti.py` antigo
**apagava o grupo no início de cada execução**. Atualize o código antes de
rodar de novo, ou ele destrói o que você já pagou para indexar.

## 6c. Rodar fora do container (Codespaces / container sem DNS)

**Sintoma:** `docker compose exec api python scripts/run_pipeline.py` falha com
`socket.gaierror: [Errno -3] Temporary failure in name resolution`, enquanto
`curl` no host funciona. No Codespace, o `/etc/resolv.conf` do container mostra
`ExtServers: [168.63.129.16]` (o resolvedor interno da Azure): o host alcança, o
container não. Fixar `dns: [1.1.1.1, 8.8.8.8]` no serviço `api` mudou o
`resolv.conf` e **não resolveu** — o DNS embutido da rede do compose continuou
sem sair, enquanto `docker run --dns 1.1.1.1` na bridge padrão funcionava.

**Solução:** manter só o Neo4j no Docker e rodar os scripts no host:

```bash
scripts/local_setup.sh              # ambiente + Neo4j + camadas 0/1/2 + restaura o backup
scripts/local_setup.sh --sem-camadas --sem-restore   # só ambiente e Neo4j
source .venv/bin/activate           # em CADA terminal novo
```

O script cuida de três armadilhas que aparecem justamente nesse cenário:

1. **Python 3.11, não o do sistema.** `socceraction>=1.5` só instala em
   Python `<3.13` (`pip` responde `No matching distribution found`). O script
   cria o `.venv` com 3.11 via `uv`, como o `Dockerfile` faz.
2. **`NEO4J_URI`.** Dentro do compose o Neo4j é `bolt://neo4j:7687`; no host é
   `bolt://localhost:7687`. O script ajusta e guarda o original em `.env.bak-local`.
3. **O plugin GDS não chega.** O container do Neo4j baixa o GDS sozinho na
   primeira subida; sem DNS, o download falha e o Neo4j sobe **sem o plugin, em
   silêncio** — só a camada 2 reclama, depois de as camadas 0 e 1 já terem
   rodado. O script detecta, baixa o jar pelo host (que resolve), copia para
   `/plugins` e reinicia o Neo4j. Testado: Neo4j 5.26.31 → GDS 2.13.13.

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
documentação), `--rodada RÓTULO` (nome da rodada no Langfuse), `--hibrida`
(liga a busca híbrida do Graphiti; falha se o índice não existir). Com
`--amostra`/`--ids`, o índice do baseline é construído só com as partidas das
perguntas escolhidas, para não gastar cota de embeddings.

Com `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` no `.env`, cada par
(pergunta, braço) vira um trace nomeado no Langfuse, com as gerações do
PydanticAI embaixo e metadados de rodada, categoria, braço e modelo. Sem as
chaves, no-op silencioso.

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

Esperado: `108 passed`. Testes que exigem Neo4j/parquet se auto-pulam quando o recurso não
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

### Quando `/ask` ou `/report` devolvem 502 por limite de tokens

Sintoma, no log da API:

```
UnexpectedModelBehavior: Model token limit (16000) exceeded before any response was generated.
```

O cliente recebe **502** com a instrução de o que ajustar (antes era um 500 com
traceback). Significa que a chamada terminou com `finish_reason: length` **sem
texto**. Em modelo de raciocínio (ex. `z-ai/glm-5.3-flash`), o raciocínio oculto
conta contra o teto de saída, e pode consumi-lo inteiro. Dois botões no `.env`
(ADR-14), nesta ordem:

```bash
LLM_MAX_TOKENS=32000          # 1º: só dá mais espaço; não muda a qualidade da resposta
LLM_REASONING_EFFORT=low      # 2º, se persistir: limita o raciocínio (só openrouter)
```

Reinicie a API depois (`docker compose restart api`): os agentes leem o `.env`
uma vez, no primeiro uso. **Nenhum dos dois foi testado ao vivo** — ver a ADR-14
para o que se sabe e o que não se sabe. Para distinguir "raciocínio longo" de
"resposta vazia", o trace dessa chamada no Langfuse (se as chaves estiverem
no `.env`) deve mostrar os tokens de saída gastos.

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
do Graphiti (`scripts/index_graphiti.py`) é adicionalmente ritmada por `GRAPHITI_PACE_SECONDS` (default
2.0, ~3 min por partida, dimensionado para a cota gratuita do Gemini de 100
embed-requests/min); com chave paga use `GRAPHITI_PACE_SECONDS=0`.

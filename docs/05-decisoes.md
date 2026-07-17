# 05 — Registro de decisões arquiteturais (ADR)

Formato: contexto → alternativas → decisão → consequências. Data em todas.

---

## ADR-1 — Camada 1 determinística: sem `add_episode`, e escrita via driver Neo4j (2026-07-17)

**Contexto.** O `add_episode()` do Graphiti dispara extração de entidades/relações via LLM
mesmo para JSON estruturado. A camada 1 escreve ~5.000 nós/arestas por partida a partir de
um dataset validado — já sabemos, com certeza, que A passou para B no minuto X com xT Y.

**Alternativas.**
1. `add_episode` por evento — descartada: chamada de LLM por evento (~2.600 ações/partida),
   custo/latência inviáveis e risco de erro de extração sobre fatos que já são exatos.
2. `graphiti.add_triplet` por fato — prevista no plano como caminho preferencial da camada 1.
3. Driver Neo4j direto, Cypher `UNWIND ... MERGE` em lotes.

**Decisão.** Opção 3 (Cypher direto). Ao inspecionar o `add_triplet` do graphiti-core
0.29.2, verificou-se que ele **gera embedding do fato a cada chamada** (além de resolução
de duplicatas): para a camada factual seriam ~5.000 chamadas de embedding por partida —
exatamente o acoplamento a serviço externo que a camada determinística não pode ter, e
inviável de rodar offline. A validação ao vivo confirmou a ordem de grandeza dos dois
lados (Cypher: segundos por partida; `add_triplet`: segundos por fato) — medições em
`07-validacao.md`.

**Consequências.** O Graphiti fica onde agrega: camada 3 — `add_triplet` para indexar as
**dezenas** de `PadraoTatico` (volume compatível com embeddings), `build_communities()` e
busca híbrida. A idempotência é garantida por `uid = uuid5(chave natural)` + `MERGE` por
chave de aresta, coberta por teste (`test_build_is_idempotent`).

---

## ADR-2 — Louvain, com Leiden disponível (2026-07-17)

**Contexto.** O plano usa detecção de comunidade nos insights 7.4/7.5/7.6 e pede
verificação da disponibilidade do Leiden na edição Community.

**Verificação real.** No build openGDS 2.13.2 instalado, `gds.leiden.*` **está disponível**
(confirmado via `gds.list()`), junto com `gds.louvain.*` e `gds.bridges.*`.

**Decisão.** Manter **Louvain** (`gds.louvain.stream`), como especificado no catálogo de
insights. As redes projetadas têm 11–17 nós; a vantagem do Leiden (comunidades
mal-conectadas em grafos grandes) é irrelevante nessa escala, e Louvain é o algoritmo
citado na literatura de passing networks usada como referência.

**Consequências.** Nenhuma perda prática; trocar para Leiden é mudar uma string de
procedure nas projeções, se o trabalho evoluir para redes maiores (temporada inteira).

---

## ADR-3 — Modelos de valoração: xT ajustado localmente e VAEP treinado uma vez (2026-07-17)

**Contexto.** O plano diz "usar os modelos prontos do socceraction; não treinar nada".
Na implementação verificou-se que: (a) o socceraction **não distribui** modelo VAEP
pré-treinado — a classe `VAEP` exige `fit`; (b) a grade pública de xT de Karun Singh
(`karun.in/blog/data/open_xt_12x8_v1.json`) não era alcançável no ambiente de build.

**Alternativas.** Deixar `vaep=NaN` (empobrece a aresta `PASSOU_PARA`); treinar em 2–3
partidas (frágil); treinar num conjunto maior da mesma competição, uma vez, com cache e
seed fixa.

**Decisão.** Treino único e cacheado sobre **16 partidas do mata-mata da Copa 2022**
(`DEFAULT_TRAINING_MATCH_IDS` em `ingestion/pipeline.py`): xT via
`ExpectedThreat(l=12, w=8).fit` (iteração de ponto fixo, sem aleatoriedade) e VAEP via
xgboost com `random_state=42`. O código **prefere automaticamente** a grade canônica de
Karun Singh se o arquivo `data/models/open_xt_12x8_v1.json` existir.

**Consequências.** Pipeline reprodutível e auto-contida; os valores absolutos de xT/VAEP
são ilustrativos (modelo de 16 partidas, não de uma temporada) — limitação registrada
para o TCC. Nenhum insight da seção 7 depende do valor absoluto: usam ranking/agregados.

---

## ADR-4 — Pin do kloppy em 3.16 (2026-07-17)

**Contexto.** `socceraction 1.5.3` (`spadl.kloppy.convert_to_actions`) quebra com kloppy
3.19 (`_SoccerActionCoordinateSystem() takes no arguments` — mudança de API dos
CoordinateSystems do kloppy).

**Decisão.** Pin `kloppy==3.16.0` no ambiente (compatível com o conversor). Registrado
para revisão quando o socceraction publicar suporte a kloppy ≥3.17.

**Consequências.** Nenhuma funcional; a disputa de pênaltis (período 5) é filtrada antes
da conversão (sem tática de jogo corrido a modelar — ver `01-pipeline.md`).

---

## ADR-5 — Provedores de LLM: implementação e validação ao vivo (2026-07-17)

**Contexto.** Troca de provedor deve ser só `.env` (mistral | anthropic | gemini).

**Implementação.** `llm/provider.py`: PydanticAI via `Model` construído com `Provider`
explícito; Graphiti via classe (`OpenAIGenericClient` com `base_url` da Mistral,
`AnthropicClient`, `GeminiClient`). Coberto por `tests/test_provider.py` (sem rede).

**Validação ao vivo (Anthropic `claude-haiku-4-5` + embeddings Gemini
`gemini-embedding-001`).** Achados reais, cada um corrigido no código:

1. **A forma-string do PydanticAI ignora `LLM_API_KEY`.** `Agent("anthropic:<m>")` lê a
   env var nativa do provedor (`ANTHROPIC_API_KEY`). Correção: `pydantic_ai_model()`
   constrói `AnthropicModel/MistralModel/GoogleModel` com o `Provider` explícito e a
   chave do `.env`.
2. **Saída estruturada longa precisa de knobs nativos.** Com o default do SDK
   (`max_tokens=4096`, 1 retry de validação), o Haiku truncou o `RelatorioTatico`
   (faltou `secoes`). Correção: `retries=2` + `model_settings={"max_tokens": 16000}`
   nos agentes — knobs do PydanticAI, não camada nossa.
3. **`cross_encoder=None` no Graphiti NÃO significa "sem reranker".** O construtor cai
   no `OpenAIRerankerClient` default e exige `OPENAI_API_KEY`. Correção: reranker
   Gemini sempre que houver chave Gemini; `OpenAIRerankerClient` apontado para o
   endpoint da Mistral no caso mistral.
4. **`text-embedding-004` foi descontinuado na API do Gemini** (404). Modelo atual:
   `gemini-embedding-001`.
5. **Cotas free-tier limitam a indexação do Graphiti** (100 embed-requests/min no
   Gemini gratuito). `index_match_patterns` limpa o grupo antes de reindexar (os uuids
   do `add_triplet` mudam a cada execução) e espaça os triplets (`pace_seconds=2`).

**Consequências.** Structured output do Anthropic funcionou sem ajuste de
`structured_output_mode`. Mistral segue não validado ao vivo (o ambiente da sessão
bloqueia `api.mistral.ai`); Gemini foi validado como embedder/reranker, não como LLM
principal. **Todas as medições da validação (latências, fidelidade, Graphiti) estão em
`07-validacao.md`** — este ADR registra as decisões e correções, não os números.

---

## ADR-6 — GDS instalado a partir do Maven Central (nota de infraestrutura) (2026-07-17)

**Contexto.** No ambiente de build desta PoC, os hosts padrão de download de plugins do
Neo4j (GitHub Releases e graphdatascience.ninja) eram inacessíveis; o
`NEO4J_PLUGINS=["apoc","graph-data-science"]` do compose não conseguiria baixá-los.

**Decisão.** Para o desenvolvimento, os jars do openGDS 2.13.2 foram resolvidos do Maven
Central (`org.neo4j.gds:proc` + `org.neo4j.gds:opengds-extension` + `open-model-catalog` +
`open-write-services`, com dependências transitivas; `commons-lang3` elevado a 3.18.0 para
compatibilidade com o APOC `apoc-core-5.26.0-core.jar`, também do Maven Central) e
montados em `/plugins`. Verificação: `RETURN gds.version()` → `2.13.2`;
`apoc.version()` → `5.26.0`.

**Consequências.** Em ambientes com rede normal, o `docker-compose.yml` como está
(plugin download automático) é o caminho padrão e nada disso é necessário. O procedimento
Maven fica documentado em `06-reproduzir.md` como alternativa para ambientes restritos.

---

## ADR-7 — Rate limits (free-tier): retry nativo em todos os clientes, pacing só onde é previsível (2026-07-17)

**Contexto.** A validação ao vivo usou chaves free-tier. O Gemini gratuito limita
embeddings a 100 requests/min e devolve 429 com `retryDelay` de até ~50 s; o retry
default dos SDKs (poucas tentativas, backoff curto) esgotava antes da janela virar e a
indexação do Graphiti quebrava no meio. O plano do projeto (seção 4) proíbe empilhar
tenacity/token bucket por cima dos SDKs.

**Alternativas.** (a) camada própria de retry (tenacity) — vetada pelo plano; (b) token
bucket/limiter próprio — vetado pelo plano; (c) configurar o retry NATIVO de cada SDK
pelos knobs de construtor e manter um pacing proativo apenas onde o volume de chamadas é
conhecido de antemão.

**Decisão.** Opção (c), implementada inteira em `llm/provider.py` (fábricas de cliente
SDK) e aplicada tanto ao LLM quanto ao embedder/reranker:

| SDK | Knob nativo | Comportamento |
|---|---|---|
| Anthropic (`AsyncAnthropic`) | `max_retries=LLM_MAX_RETRIES` | respeita `Retry-After` do servidor |
| OpenAI-compat (`AsyncOpenAI`, usado p/ Mistral no Graphiti) | `max_retries=LLM_MAX_RETRIES` | idem |
| google-genai (`genai.Client`) | `HttpOptions(retry_options=HttpRetryOptions(attempts=LLM_MAX_RETRIES+2, initial_delay=2, max_delay=65, exp_base=2, jitter=0.5, http_status_codes=[429,5xx]))` | backoff exponencial dimensionado para cruzar a janela de 1 min das cotas por minuto |
| mistralai (`Mistral`) | `RetryConfig(strategy="backoff", BackoffStrategy(2 s → 65 s, exp 2))` | idem |

Os clientes configurados são injetados em TODOS os consumidores: modelos do PydanticAI
(`AnthropicModel/MistralModel/GoogleModel` com provider explícito), clientes de LLM do
Graphiti, embedders (`GeminiEmbedder`/`OpenAIEmbedder`) e rerankers — todos aceitam
`client=` no construtor, então não há wrapper nenhum.

**Pacing proativo** existe num único lugar: `index_match_patterns`
(`GRAPHITI_PACE_SECONDS`, default 2.0), porque ali o número de chamadas é previsível
(~3-4 embeddings por triplet) e evitar o 429 é mais barato e mais rápido que absorvê-lo
por retry. Com chave paga, `GRAPHITI_PACE_SECONDS=0`.

**Consequências.** 429 esporádico em qualquer camada é absorvido pelo próprio SDK
respeitando o que o servidor pedir; nenhum código do projeto contém laço de retry.
Coberto por testes de introspecção sem rede (`tests/test_provider.py`, seção "Rate
limits") e por teste de estresse ao vivo com a cota estourada de propósito (medições em
`07-validacao.md`). `SEMAPHORE_LIMIT` permanece como único controle de concorrência.

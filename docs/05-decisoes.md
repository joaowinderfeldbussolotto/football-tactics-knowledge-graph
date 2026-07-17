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
inviável de rodar offline. **Números medidos da opção 3:** final = 5.351 escritas em
6,9 s (primeira execução) e 1,1 s (re-execução idempotente); semifinal = 4.565 em 1,1 s;
quartas = 4.035 em 0,7 s.

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

## ADR-5 — Provedores de LLM: implementação e estado de validação (2026-07-17)

**Contexto.** Troca de provedor deve ser só `.env` (mistral | anthropic | gemini).

**Implementação.** `llm/provider.py`: PydanticAI via string (`mistral:*`, `anthropic:*`,
`google-gla:*`); Graphiti via classe (`OpenAIGenericClient` com
`base_url=https://api.mistral.ai/v1`, `AnthropicClient`, `GeminiClient`; reranker dedicado
só para Gemini, RRF puro nos demais). Coberto por `tests/test_provider.py` (sem rede).

**Estado de validação.** O ambiente de desenvolvimento desta PoC **não tinha chaves de
API**, então o comportamento de structured output de cada provedor (inclusive o risco
documentado do `json_schema` em endpoints compatíveis com OpenAI, caso do Mistral) **ainda
não foi validado ao vivo**. Fica como passo 10 do plano: rodar `/report` e `/ask` com cada
provedor, e registrar aqui o resultado (inclusive eventual troca de
`structured_output_mode` para `json_object` no Graphiti).

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

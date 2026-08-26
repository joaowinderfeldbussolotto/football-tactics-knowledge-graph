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

---

## ADR-8 — Modo autônomo: text-to-Cypher read-only no Q&A e no relatório (2026-07-17, ampliado 2026-07-18)

**Contexto.** A arquitetura original restringia o Q&A ao que existisse como
`PadraoTatico`: perguntas factuais legítimas ("quem fez os gols?", "qual dupla mais
trocou passes?") recebiam "não tenho no contexto", embora o dado existisse no grafo
factual. Requisito do usuário: o sistema deve responder TUDO sobre o jogo — fatos e
tática — com o LLM tendo autonomia para navegar o grafo.

**Alternativas.** (a) Pré-computar mais padrões (não escala para a cauda longa de
perguntas factuais); (b) `graphiti.search` (já usado como busca híbrida, mas só enxerga
o que foi indexado — padrões —, não os ~5.000 fatos por partida, que o ADR-1
deliberadamente não indexa); (c) tool use com consultas Cypher geradas pelo LLM.

**Decisão.** Opção (c), com três invariantes que preservam a tese da seção 0.2 do plano
("o LLM não calcula"):
1. **Quem calcula é o Neo4j.** O LLM decide *o que* consultar; contagens/somas/rankings
   são agregação determinística do banco. A regra "nada é computado na hora" vale para
   MÉTRICAS (que continuam nascendo nas camadas 0/2); recuperação factual é leitura.
2. **Somente leitura, imposto em duas camadas** (`graph/db.py::run_readonly`): transação
   READ do Neo4j (o servidor rejeita escrita) + guarda sintática que recusa cláusulas de
   escrita e `CALL` (bloqueia procedures dbms/apoc/gds), com limite de 50 linhas e
   timeout de 15 s.
3. **Auditabilidade.** Toda consulta usada volta na resposta (`consultas_executadas`) e
   `faithfulness.check_queries` a re-executa. A fidelidade dos padrões continua exata
   (valor contra nó); a das consultas é "re-executa e retorna dados".

Para isso o grafo factual ganhou o que faltava: arestas `FINALIZOU` (com `gol`
booleano) e `DEU_ASSISTENCIA` (seleções diretas do parquet, dentro das regras da
camada 1).

**Ampliação (2026-07-18) — cobertura total e relatório autônomo.**
1. Aresta `REALIZOU`: o log COMPLETO de ações SPADL (uma aresta por ação, cópia direta
   do parquet). Antes, perguntas sobre dribles, desarmes, interceptações, faltas,
   cartões amarelos, defesas de goleiro e passes errados não tinham dado no grafo;
   agora qualquer ação do jogo é consultável. O schema no prompt anota as armadilhas de
   vocabulário de futebol lido do banco (`acao`, `sucesso`, `minuto`) e não precisa
   mais avisar sobre nomenclatura SPADL nem proibir somar contagens
   de `REALIZOU` com as das arestas dedicadas.
2. A MESMA ferramenta `consultar_grafo` foi dada ao agente de **relatório**: o
   `RelatorioTatico` abre com uma seção factual ("O jogo em fatos" — gols e
   assistências vindos de consulta, máx. 3) e ganha `consultas_executadas`. A regra
   antiga "não mencione placar/gols" (que existia para evitar alucinação de memória)
   foi substituída pela regra certa: fatos do jogo SÓ se sustentados por consulta
   registrada. O processo completo está documentado em `08-autonomia.md`.

**Risco aceito e mitigado.** Text-to-Cypher pode gerar a *consulta errada que roda
certo* — observado ao vivo na primeira validação: join `DEU_ASSISTENCIA×FINALIZOU`
multiplicou 1 assistência de Thuram pelos 3 gols de Mbappé; e o modelo completou
"3-3, pênaltis" de memória. Mitigações aplicadas: schema gerado do banco (com o
anti-padrão explícito), regra de `COUNT(DISTINCT)`/contagem direta de arestas, proibição
de completar com conhecimento externo, e máximo de 4 consultas. A re-execução NÃO detecta
erro semântico — limitação documentada; o golden dataset ganhou categoria `factual`
para medir exatamente isso.

**Consequências.** O sistema responde fatos (gols, assistências, passes, dribles,
desarmes, cartões, duplas, zonas...) e tática nos DOIS caminhos de consumo (`/ask` e
`/report`), sempre com auditoria por consulta. A comparação com o baseline segue
válida: as perguntas estruturais continuam decididas pelos algoritmos da camada 2 —
o text-to-Cypher recupera fatos, não substitui os insights.

## ADR-9 — OpenRouter como provedor opcional de LLM (2026-08-25)

**Contexto.** A conta Anthropic ficou sem crédito com a 4ª rodada de avaliação
pendente. O OpenRouter (agregador compatível com OpenAI) tem `stealth/ox-alpha`
com preço zero na sua própria API pública (`prompt: 0`, `completion: 0`,
consultado em `https://openrouter.ai/api/v1/models`), 1.048.576 tokens de
contexto, e declara `supported_parameters` incluindo `tools` e
`response_format` — os dois mecanismos que a camada 3 usa (`consultar_grafo` e
saída estruturada via PydanticAI).

**Decisão.** Adicionar `openrouter` como quarto valor de `LLM_PROVIDER`,
reaproveitando o caminho "compatível com OpenAI" que já existia para a Mistral
(`OpenAIGenericClient` no Graphiti, `_openai_compat_sdk_client` com
`LLM_MAX_RETRIES`). A única generalização de código foi extrair
`_openai_compat_base_url()` para os três lugares que faziam
`if provider == "mistral"` (`graphiti_llm_client`, `graphiti_cross_encoder`,
`graphiti_embedder` continua fora — OpenRouter não serve embeddings). No lado
do PydanticAI, `OpenAIChatModel` + `OpenRouterProvider` (nativo do SDK desde a
versão instalada, 2.34.0).

**Achado do próprio SDK durante a integração.** `OpenRouterProvider` valida em
tempo de construção que o nome do modelo tenha o formato `vendor/modelo`
(`stealth/ox-alpha` já serve; um nome sem `/` levanta `UserError` antes de
qualquer chamada de rede). Não é uma regra do projeto — é o SDK protegendo
contra o erro comum de usar nome de modelo de outro provedor.

**Duas ressalvas que pesam para o uso em pesquisa, não só em produção:**

1. **"Stealth" significa que os prompts alimentam o laboratório por trás do
   modelo.** É o preço de ser grátis. Os dados aqui são StatsBomb Open Data
   (público) mais perguntas táticas — sem informação sensível —, mas a troca é
   real e deve ser dita explicitamente a quem for revisar o trabalho.
2. **Um modelo stealth pode ser retirado ou renomeado sem aviso.** Isso o torna
   inadequado como base do número OFICIAL da pesquisa sem duas salvaguardas: registrar
   a data exata da rodada (modelos stealth mudam de versão silenciosamente) e manter
   pelo menos uma rodada em modelo estável e versionado para o resultado citável.
   Comparar duas rodadas feitas em modelos diferentes (ex.: esta rodada em
   `ox-alpha` contra a 3ª rodada em `claude-sonnet-5`) mede o modelo, não o
   sistema — a comparação que continua válida é grafo-vs-baseline DENTRO da
   mesma rodada, porque os dois lados usam o mesmo modelo.

**Consequências.** `LLM_MAX_RETRIES`, o semáforo de aplicação e o mecanismo de
faithfulness são agnósticos de provedor por construção (ADR-5/ADR-7) — nenhum
deles precisou mudar. `LLM_STRUCTURED_OUTPUT_MODE` (novo, default
`json_schema`) é o botão exposto no `.env` para o caso de um modelo agregado
não suportar o modo estrito do Graphiti; não foi necessário até agora, porque
ninguém rodou contra a API ainda (integração feita e revisada antes de haver
chave configurada). `scripts/smoke_llm.py` existe para checar ferramenta + saída
estruturada com uma pergunta só, antes de comprometer a rodada de 30 perguntas.

## ADR-10 — A súmula no contexto é condição experimental, não decisão fechada (2026-08-26)

**Contexto.** Depois que a camada 1b passou a entrar no contexto do Q&A
(`api/retrieval.py`), levantou-se a dúvida certa: entregar a súmula pronta não
quebra parte do que o trabalho quer validar? O diagnóstico separa três
afirmações que estavam sendo tratadas como uma só:

| Afirmação | A súmula afeta? |
|---|---|
| Insights estruturais não existem em linha de tabela nenhuma | **Não.** Nenhum campo de `EstatisticaJogador` contém betweenness, comunidade, ponte ou janela temporal. As 15 perguntas `estrutural` são indiferentes a ela. |
| O agente alcança fatos sozinho escrevendo Cypher (ADR-8) | **Sim, e muito.** `PROMPT_QA` manda usar a súmula e NÃO consultar quando o número já está lá. Na 3ª rodada as 8 perguntas factuais rodaram 1–2 consultas cada; com a súmula isso tende a zero, e o mecanismo deixa de ser exercido justamente onde era. |
| Grafo consultável supera texto embeddado | **Muda de sentido** em `factual`/`agregada`. Com a paridade de fatos (`evaluation/match_facts.py`), os dois lados têm os mesmos números da mesma fonte; a variável isolada vira serialização + mecanismo de recuperação, e o resultado ESPERADO ali é empate, não vitória. |

Agrava a dúvida que a justificativa registrada na docstring de
`api/retrieval.py` citava, entre os motivos, o `judge_retrieval` dar nota
baixa. A sequência "métrica baixa → mudei o sistema → métrica alta" precisa de
outro apoio, mesmo quando a mudança é defensável em arquitetura — e é: resolver
entidade e puxar atributos para o contexto é o *local search* do GraphRAG
canônico, não uma invenção deste projeto.

**Decisão.** Não escolher entre ter e não ter súmula: medir. `retrieve_context`
ganhou `incluir_sumula: bool = True`, e a avaliação passou a rodar **três
braços** sobre as mesmas perguntas, no mesmo modelo e na mesma rodada:

1. `grafo_sem_sumula` — controle; mede a autonomia do ADR-8.
2. `grafo_com_sumula` — o comportamento da API.
3. `baseline` — RAG vetorial plano com paridade de fatos.

A diferença 1→2 é o custo-benefício da pré-agregação medido, em vez de
assumido. `n_consultas` por braço é o indicador direto da dúvida original: se
o braço 2 zera as consultas, a súmula calou a ferramenta.

**Decisão acoplada: duas notas de recuperação.** `run_evaluation.py`
concatenava `consultas_executadas` no contexto entregue ao `judge_retrieval`.
A nota de *recuperação* do grafo incluía o que o agente foi buscar **durante a
geração** — que não é recuperação —, e o baseline, sem ferramenta, nunca
recebia acréscimo equivalente. A assimetria favorecia o grafo numa métrica que
leva o nome do que não estava medindo. Agora são duas:

- `retrieval_previo` — só o que a recuperação entregou antes de o agente rodar.
  **É a comparável com o baseline**, por ser a simétrica.
- `retrieval_final` — aquilo mais o resultado das consultas. Mede o sistema
  inteiro; não tem contrapartida no baseline.

Quando o agente não consulta nada, os dois contextos são o mesmo texto e a nota
é reaproveitada, para não transformar ruído de amostragem de um juiz estocástico
em diferença aparente entre as métricas.

**Consequências.** Os números da 3ª rodada foram medidos com uma nota só, e
essa nota é a `retrieval_final` — comparada, na época, contra a `previo` do
baseline. Ao confrontar rodadas, é `retrieval_final` que continua no lugar
dela; `retrieval_previo` não tem equivalente anterior. O arquivo da 3ª rodada
foi preservado em `data/processed/eval_results_r3_sonnet.json` porque o formato
de `eval_results.json` mudou e a documentação cita números dele.

**Braços considerados e descartados**, que ficam como trabalho futuro:
"súmula sem ferramenta" (isolaria quanto a ferramenta ainda contribui depois de
a súmula chegar) e "só ferramenta, sem camada 2" (separaria *ter grafo
consultável* de *ter GDS pré-calculado* — hoje a vitória em `estrutural`
confunde as duas). Ambos são desejáveis; nenhum dos dois cabia numa rodada só.

### Adendo à ADR-9 — a ressalva 2 se cumpriu em um dia (2026-08-26)

`stealth/ox-alpha` foi **retirado no meio de uma execução**. A API passou a
devolver 404 com a mensagem de que o modelo era o GLM-5.3 Flash da ZAI e que o
período de teste acabara. Entre o smoke test que validou a integração (25/08) e
a primeira tentativa de rodar a avaliação (26/08) houve menos de 24 horas.

Não é anedota: é a razão de a ressalva existir. Um número de dissertação
apoiado nesse modelo teria virado irreproduzível de um dia para o outro, sem
aviso e sem como voltar atrás — o modelo não existe mais sob aquele nome.

**Achado adicional, ao procurar substituto gratuito.** As vias `:free` do
OpenRouter não servem à camada 3. `z-ai/glm-5.2:free` recusou a chamada com
`grammar_not_supported`: a lane gratuita (provedor Decart) roda **sem backend
de gramática**, então não aceita `response_format: json_schema` nem
`tool_choice` forçado — que são exatamente os dois mecanismos de que a camada
3 depende (saída estruturada do PydanticAI e a ferramenta `consultar_grafo`).
O catálogo em `/api/v1/models` declara `tools` e `response_format` para esse
modelo, mas isso descreve a via paga; **o catálogo não distingue as lanes**.
Sondando os 9 gratuitos que declaravam os dois parâmetros, só 2 honraram o
schema de fato e 4 devolveram 429 na primeira tentativa. Um deles,
`openrouter/free`, é um roteador que escolhe outro modelo a cada chamada —
inutilizável para pesquisa, por construção.

**Decisão.** A rodada de avaliação passa a usar `z-ai/glm-5.3-flash`, pago e
versionado (US$ 0,075/M entrada, US$ 0,25/M saída). Medido na chave depois de
5 perguntas reais: **US$ 0,012 por pergunta** somando os três braços da
ADR-10, o que põe a rodada completa das 30 em torno de **US$ 0,37**. (Uma
estimativa a priori de US$ 0,09 errou por ~4x, por não contar que o fallback
injeta os ~24 padrões da partida inteira no contexto e que o modelo cobra
tokens de raciocínio como saída — anotado aqui porque estimar custo de LLM
por contagem de prompt subestima sistematicamente.) Trinta e sete centavos são
um preço baixo pela propriedade que o modelo grátis não tinha: existir amanhã,
com o mesmo nome e a mesma versão.

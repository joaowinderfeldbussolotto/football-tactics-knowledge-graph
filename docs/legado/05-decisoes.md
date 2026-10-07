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

## ADR-11 — Ficha do jogo, roteador de intenção e busca híbrida ligada (2026-08-26)

**Contexto.** A amostra da ADR-10 mostrou o grafo perdendo a categoria factual
para o baseline na comparação simétrica — 5,0 contra 1,0 de `retrieval_previo`.
O rastreamento da pergunta "Quem fez os gols da final?" achou a causa:

```
entidades resolvidas: []                        ← nenhum nome próprio na pergunta
súmula entregue: [(Argentina, 3), (France, 3)]  ← o TOTAL de gols, não quem fez
os gols no grafo:  Messi 23' · Di María 36' · Mbappé 80' · 81' · Messi 108' · Mbappé 118'
```

Os gols estavam a **um hop** (`FINALIZOU {gol: true}`) e a recuperação não ia
buscar. `resolve_entities` só enxerga nome próprio: sem jogador ou time citado,
resolvia zero entidades, caía no fallback e despejava os ~24 padrões táticos da
partida — ruído puro para uma pergunta sobre gols.

**A paridade tinha quebrado para o outro lado.** `evaluation/match_facts.py`
foi escrito para dar ao baseline a súmula que o grafo ganhou na camada 1b. Mas
ele dá ao baseline também uma **ficha do jogo** — linhas prontas de gols,
assistências e cartões — que a recuperação do grafo nunca entregou. Corrigimos
a assimetria numa direção e criamos outra, no sentido oposto. A ADR-10 exige
que a variável isolada seja a REPRESENTAÇÃO; enquanto um lado tem o fato e o
outro não, não é isso que está sendo medido.

**Decisão 1 — ficha do jogo na recuperação.** `ficha_do_jogo()` em
`api/retrieval.py` devolve gols, assistências e cartões em frases do mesmo
formato que o baseline recebe. As consultas percorrem as MESMAS arestas que uma
consulta ad-hoc percorreria — nada pré-calculado, ao contrário da súmula da
camada 1b.

**Decisão 2 — roteador de intenção determinístico.** `detectar_intencoes()`
casa o vocabulário da pergunta (gol/marcou/placar, assistência, cartão/amarelo)
contra gatilhos fixos, sem LLM na recuperação. É o que decide quais partes da
ficha entram. Sem nome próprio E sem intenção, a pergunta é genérica sobre a
partida e o fallback continua valendo.

**Decisão 3 — fallback com pontaria.** `padroes_relevantes()` ordena os padrões
por casamento lexical com a pergunta e corta em 8. Quando não há casamento
nenhum, devolve tudo como antes — não se remove informação sem motivo. Isso
ataca de uma vez a diluição de contexto e o custo: o despejo dos 24 padrões era
o que fazia a estimativa a priori de custo errar por 4x.

**Decisão 4 — a busca híbrida deixa de ser dormente.** `index_match_patterns`
só era chamado dentro da rota `POST /analyze/{match_id}`. Quem reproduz o
projeto pelos scripts nunca criava o índice do Graphiti, e `retrieve_context`
recebia `graphiti=None` seguindo só com a recuperação estruturada — sem avisar.
**Todos os números medidos até a 4ª rodada são de recuperação estruturada pura,
não híbrida.** `scripts/index_graphiti.py` cria o índice e
`run_evaluation.py --hibrida` liga a busca, recusando-se a rodar se o índice
estiver vazio: ligar sem índice devolveria zero fatos em silêncio, o que é pior
que não ligar, porque o rótulo da estratégia diria "híbrida" sem ser.

**Consequência para a comparação.** A ficha é o mesmo tipo de movimento que a
súmula: dado pronto no contexto. A diferença é que agora existe a máquina da
ADR-10 para medir o efeito, e a justificativa é simetria com o baseline — que
já tinha esses fatos — e não a nota de um juiz.

## ADR-12 — A 4ª rodada completa: quatro quedas, três bugs reais, um achado de modelo (2026-08-26 a 2026-08-31)

**Contexto.** Rodar as 30 perguntas × 3 braços (ADR-10) com busca híbrida
(ADR-11) foi pedido três vezes ao longo de 5 dias corridos, com o processo
caindo repetidamente. Vale o registro da causa de cada queda — todas
diagnosticadas ao vivo, nenhuma escondida — porque juntas formam um retrato
mais honesto de "rodar avaliação de LLM contra API de terceiros" do que uma
tabela de números sozinha.

**Queda 1 e 2 — indexação do Graphiti.** Um defeito do cliente do Graphiti
(`response.choices[0]` sem checar) derrubava a indexação inteira num triplet
que devolvesse resposta vazia do OpenRouter; e a cota diária de embeddings do
Gemini free tier (1000/dia) esgotou no meio de tentativas repetidas. Corrigido
com um cliente que repete a chamada e tolera falha por triplet
(`c1dc411`) — a indexação final rodou 73/73 padrões nas três partidas.

**Queda 3 — resposta inválida do OpenRouter.** `finish_reason: "error"` dentro
de um HTTP 200, fora do enum que o PydanticAI aceita — `UnexpectedModelBehavior`
sem tratamento. Corrigido com `_retentar()` (`b4ae74c`), depois ampliado para
cobrir também `google.genai.errors.APIError` quando a mesma falha apareceu do
lado do embedder (`de3e0d5`).

**Queda 4 — cota diária do Gemini de novo**, agora consumida pela própria
avaliação (busca híbrida + baseline vetorial, mesmo free tier). Sem chave
alternativa de embedder configurada, e trocar de provedor no meio teria
misturado vetores de espaços diferentes no cache do baseline — a mesma
armadilha que `restore_graphiti.py` já guarda contra na restauração do índice.
Sem solução de código: esperada a virada do dia (a cota reseta à meia-noite
Pacífico). O checkpoint (`--retomar`, seção do plano original) foi o que
tornou essa espera barata — 18 das 30 perguntas continuaram seguras.

**O achado que não é bug: alucinação sob citação obrigatória.** Entre as
quedas 3 e 4 apareceu um problema de qualidade, não de infraestrutura: o
modelo às vezes ecoava o TEXTO da `description` de um campo Pydantic como se
fosse o valor (`padrao_tatico_id` virou a string `"uid"`) — corrigido com
validadores que rejeitam esse eco especificamente, forçando o retry nativo do
Agent a corrigir sozinho (`d9d4eec`). Depois desse conserto, a rodada limpa
ainda fechou com fidelidade de 86–93%, não ~100%. Investigado sem gastar mais
nada (os dados brutos passaram a ser persistidos por pergunta), a causa
restante foi mais séria: em 14 de 82 citações (17%), o modelo **inventou
dados inteiros** — consultas Cypher sintaticamente válidas para uma partida
(`match_id: 'FB-MCI-LIV-2023-11-25'`, Manchester City × Liverpool) e um
jogador (`Alessandro Florenzi`, `match_id: 3918315`) que não existem neste
projeto. A fidelidade determinística (ADR-8) capturou as 14 corretamente como
`padrao_inexistente` — a métrica funcionou; o modelo que falhou.

**Decisão.** Manter a citação obrigatória como está: ela não impede um modelo
fraco de alucinar, mas torna a alucinação detectável e mensurável, que é
exatamente o que se espera de um mecanismo de verificação — e a ressalva já
registrada em `evaluation/faithfulness.py` ("100% não é correção") ganha aqui
seu par simétrico: **fidelidade abaixo de 100% pode ser a métrica funcionando
contra um modelo fraco, não um defeito do pipeline.** Não implementar detecção
automática de alucinação nesta rodada — seria um projeto à parte, e o
mecanismo determinístico já cobre o caso que importa (a resposta cita algo que
não existe, e isso é sinalizado).

**Consequência para leitura dos números.** A 4ª rodada é a fonte legítima da
tabela de três braços (a ablação da súmula e a checagem de isolamento não
dependem da força do modelo — mediram exatamente o que deviam, ver
`03-insights.md`). Ela NÃO deve ser lida como "o sistema piorou" frente à 3ª
rodada: o que mudou foi o modelo, de Claude para um agregador gratuito/barato,
confirmando ao vivo a ressalva 2 da ADR-9. Para uma citação que dependa de
fidelidade ~100%, a 3ª rodada (estrutural, Claude) continua sendo a referência
— preservada em `eval_results_r3_sonnet.json` exatamente para isso.

## ADR-13 — Indexação retomável e não destrutiva (2026-10-05)

**Contexto.** Rodando `index_graphiti.py` na máquina do próprio autor (Codespace,
`graphiti-core 0.30.2`, OpenRouter + `z-ai/glm-5.3-flash`), a indexação caiu na
construção de comunidades depois de já ter gasto dinheiro com os triplets:

```
Error in generating LLM response: LLM returned an empty response
Retrying _generate_response_with_retry after 2 attempts...   (3, 4)
Error in generating LLM response: Unterminated string starting at: line 1 column 14
graphiti_core.llm_client.errors.EmptyResponseError: LLM returned an empty response
```

Três defeitos, todos de desenho nosso e não do provedor:

1. **Rodar de novo apagava o que já fora pago.** `index_match_patterns` limpava o
   grupo inteiro no início de cada execução. Reexecutar depois de uma queda
   repagava tudo — inclusive o que tinha dado certo.
2. **A falha de uma etapa opcional derrubava o processo.** Comunidades só
   acrescentam resumos (a busca híbrida funciona sobre os fatos), mas uma
   exceção em `build_communities` matava o script e deixava as partidas
   seguintes sem indexar. E o `build_communities` do Graphiti é tudo-ou-nada:
   resume os clusters em paralelo e só grava no fim, então uma chamada
   falhando perde todas as já pagas daquela partida.
3. **O cliente resiliente não cobria a falha real.** O que escrevi em 28/08
   tratava só `TypeError` por `choices` ausente — mas o `graphiti-core` 0.30
   levanta `EmptyResponseError`, que passava direto. Pior: esse ramo usava
   `logger`, que `provider.py` nunca definiu; teria virado `NameError` na
   primeira vez que rodasse, e nenhum teste o exercitava. Confirmado
   revertendo o arquivo: `NameError: name 'logger' is not defined`.

**Decisão.**

- **Retomável por padrão.** Padrões cujo nó já existe no grupo são pulados (a
  chave é o nome `tipo:uid[:8]`); um triplet que falhou não deixa nó, então é
  tentado de novo. Comunidades só são construídas onde ainda não existem.
  `--do-zero` restaura o comportamento antigo, explícito, para quando os
  `PadraoTatico` mudaram. (A rota `POST /analyze` deixou de indexar — ver o
  adendo ao fim desta ADR.)
- **Comunidades isoladas por partida.** `build_pattern_communities` repete a
  etapa inteira (3 vezes, espera crescente, limpando as comunidades da
  tentativa anterior para não duplicar). Se ainda assim falhar, o script marca
  a partida como pendente, segue, e sai com código 2 e o comando exato para
  refazer só aquilo (`--so-comunidades`).
- **Cliente cobre as três assinaturas.** `EmptyResponseError`,
  `json.JSONDecodeError` e `TypeError` de `choices`, 3 tentativas rápidas
  *dentro* de cada uma das 4 do Graphiti (até 12 no total, sem multiplicar as
  esperas longas), e `logger` definido.

**O que NÃO foi estabelecido.** A causa de o GLM devolver corpo vazio ou JSON
cortado não foi confirmada. Duas hipóteses: orçamento de `max_tokens` consumido
por raciocínio oculto (o JSON cortado no caractere 13 combina com isso), ou o
`finish_reason: "error"` intermitente que este provedor já mostrou antes
(ADR-12). Uma pista descartou uma terceira: o Graphiti usa `temperature=1` por
padrão, então repetir não reexecuta a mesma amostra — o retry tem chance real,
e a minha suposição inicial de que seria determinístico estava errada. Sem
distinguir as hipóteses, o conserto não depende delas: protege o dinheiro já
gasto qualquer que seja a causa. Distinguir exigiria chamadas pagas de
diagnóstico (ex.: ler `finish_reason` e o uso de tokens de raciocínio nas
respostas vazias) e não foi feito.

**Consequências.** Uma queda no meio da indexação custa, no pior caso, a etapa
em curso — não a rodada inteira. O preço do desenho: comunidades repetidas
gastam de novo as chamadas de resumo (poucas por partida, mas não zero), e a
retomada por nome assume que um padrão já indexado não mudou; se mudou, use
`--do-zero`. Os testes (`tests/test_resiliencia_indexacao.py`, 17 dos 20 — os 3 últimos são da ADR-14 —, sem rede)
cobrem cada decisão acima, e foram verificados contra o código antigo: os de
resposta vazia e de `choices` falham nele.

**Adendo (2026-10-06) — o Graphiti sai da rota `POST /analyze`.** Uma hora
depois de escrever a ADR acima, a mesma falha apareceu num log da API
(`EmptyResponseError`, vindo de `build_communities`), e ela mostrou que eu tinha
consertado o script e deixado a rota com o defeito: a camada 2 já estava gravada
quando o Graphiti entrava, e qualquer falha dele virava HTTP 500, com o cliente
achando que a análise falhara. O primeiro conserto (commit `0491c26`) isolou a
falha e devolveu 200 com um campo `graphiti`. Foi **desfeito** no passo
seguinte, por decisão do autor, e o motivo vale registrar: isolar a falha
resolvia o 500 mas não o problema de fundo.

A rota apagava o índice da partida a cada chamada (`limpar=True`) e repagava
todas as chamadas de LLM. Quem chamava `/analyze` só para refazer a camada 2 —
determinística, de graça — gastava dinheiro sem saber, e perdia um índice
restaurado do backup. Um 200 com `erro` dentro da resposta deixa isso mais
tolerável, não menos caro. O que o script tem e a rota não pode ter: mostra o
estado antes de agir, retoma em vez de recomeçar, e exige `--do-zero` por
escrito para destruir.

**Decisão.** `/analyze` faz só a camada 2: sem LLM, sem custo, sem tocar no
Graphiti. O índice é construído exclusivamente por `scripts/index_graphiti.py`.
O `/ask` continua usando o Graphiti na busca híbrida, só leitura — `app.state.graphiti`
segue criado no lifespan. O campo `graphiti` que a rota ganhara foi removido da
resposta (seria sempre `None`); como o PR ainda não foi mergeado, não há cliente
dependendo dele.

**Consequência, que é uma mudança de comportamento.** Quem dependia de
`/analyze` para manter o índice atualizado depois de refazer a análise agora
precisa rodar `index_graphiti.py` (`--do-zero` se os padrões mudaram). Isso
é mais um passo manual — e foi o preço aceito em troca de a rota nunca mais
gastar dinheiro por baixo dos panos. O índice pode ficar desatualizado em
relação aos padrões sem nada avisar; o script mostra o estado, a rota não
verificaria. `tests/test_resiliencia_indexacao.py` guarda a regra: qualquer
chamada ao Graphiti durante `/analyze` falha o teste, e ele foi verificado
contra a rota antiga, onde falha.

## ADR-14 — Teto de tokens e esforço de raciocínio configuráveis; erro do modelo vira 502 (2026-10-06)

**Contexto.** Numa requisição à API (`/ask` ou `/report`), o log do autor:

```
pydantic_ai.exceptions.UnexpectedModelBehavior: Model token limit (16000) exceeded
before any response was generated. Increase the `max_tokens` model setting, ...
```

O cliente recebeu um 500 com traceback.

**O que está estabelecido** (lido no código instalado, não suposto):

- O PydanticAI levanta isso só quando `finish_reason == 'length'` **e** a
  resposta chega vazia, com texto em branco, ou só com raciocínio
  (`_agent_graph.py`). O próprio comentário dele diz *"possibly during
  thinking"*, e de propósito **não repete** a chamada nesse caso.
- O 16000 é um teto **nosso** (`_MODEL_SETTINGS`, hardcoded até aqui). O
  OpenRouter anuncia `max_completion_tokens` de 943.717 para
  `z-ai/glm-5.3-flash`.
- O mesmo modelo anuncia `reasoning`, `reasoning_effort` e `include_reasoning`
  entre os parâmetros suportados — é um modelo capaz de raciocínio oculto.
- `provider.py` usa `OpenAIChatModel` + `OpenRouterProvider`. A tradução
  `openrouter_reasoning` → `extra_body["reasoning"]` pertence à classe
  `OpenRouterModel`, que não é a usada; o caminho que o `OpenAIChatModel`
  envia é o `extra_body` direto.

**O que NÃO está estabelecido.**

- **Que a causa é o raciocínio.** A condição acima também cobre resposta
  genuinamente vazia. Este erro é do mesmo tipo do `EmptyResponseError` da
  ADR-13 (mesmo modelo, mesmo sintoma de saída vazia/cortada), o que dá peso à
  hipótese "raciocínio consumindo o orçamento" — mas por caminhos diferentes
  (PydanticAI aqui, Graphiti lá), então é indício, não prova de que são a mesma
  causa.
- **Que `effort: low` reduz o raciocínio deste modelo**, ou que não piora o uso
  de ferramenta e a saída estruturada. Nada foi rodado ao vivo: o ambiente em
  que isto foi escrito não tem a chave do provedor, e nenhuma chamada paga foi
  feita.
- **Que 32000 basta.** Se o raciocínio for um laço descontrolado em vez de
  longo-mas-finito, dobrar o teto só dobra o gasto da chamada que falha.

**Decisão.**

- Dois botões no `.env`, com defaults que **preservam o comportamento atual**:
  `LLM_MAX_TOKENS=16000` (o valor que sempre foi usado) e `LLM_REASONING_EFFORT=`
  (vazio: não envia nada). Não mudei o default de tokens porque não sei se
  dobrá-lo resolve; mudar às cegas gastaria mais sem garantia.
- `LLM_REASONING_EFFORT` só é traduzido para o `openrouter`
  (`extra_body["reasoning"]["effort"]`). Em outro provedor é **ignorado com
  aviso no log**: ignorar em silêncio faria o botão parecer funcionar. Os dois
  valores vão para `pydantic_ai_model_settings()` em `llm/provider.py` — a
  camada que já isola o que muda de provedor — e não ficam espalhados em
  `agents.py`.
- `/ask` e `/report` devolvem **502** com a instrução (qual variável ajustar)
  quando o erro é de limite de tokens, e 502 genérico para outro
  `UnexpectedModelBehavior`, sem a dica de tokens — não se manda ajustar um teto
  por um erro que não é de teto. 502, não 500: quem falhou foi o modelo, não a
  aplicação.
- **Sem repetição automática na API.** O PydanticAI se recusa a repetir de
  propósito, e repetir com o mesmo teto tende a repetir o resultado, cada
  tentativa podendo gastar o teto inteiro. (O runner de avaliação repete, via
  `_retentar`, mas ali o custo de uma pergunta perdida é de uma rodada inteira;
  numa requisição de API, quem chamou pode simplesmente tentar de novo.)

**Consequências.** A ordem sugerida é `LLM_MAX_TOKENS=32000` primeiro — só dá
espaço, não pode piorar a resposta — e `LLM_REASONING_EFFORT=low` depois, se
persistir. Só a medição ao vivo diz qual resolve, e se a qualidade das respostas
(fidelidade, insight) se mantém: a avaliação (`run_evaluation.py`) é o
instrumento, e o `effort` merece uma rodada própria antes de virar default. Fora
do escopo e não tocado: os juízes e o baseline não definem teto
(`judges.py`, `baseline_rag.py`), então usam o do provedor — o mesmo risco de
raciocínio longo existe ali, sem a proteção do teto.

# 07 — Relatório de validação da execução

Este arquivo separa **dado de execução** (números medidos numa rodada concreta, num
ambiente concreto) de **documentação e decisão** (docs 01–06). Os docs descrevem o que o
sistema É e por quê; este arquivo registra o que foi MEDIDO ao validá-lo. Os ADRs em
`05-decisoes.md` apontam para cá em vez de carregar tabelas de medição.

## Ambiente da execução de validação

| Item | Valor |
|---|---|
| Data | 2026-07-17 e 2026-07-18 |
| Ambiente | sessão Claude Code remota (sandbox Linux com proxy TLS de saída) |
| Neo4j | 5.26.0 Community em container, openGDS 2.13.2 + APOC 5.26.0 (via Maven, ADR-6) |
| LLM | Anthropic `claude-haiku-4-5` (o Claude mais barato: $1/$5 por MTok) |
| Embeddings/reranker | Gemini `gemini-embedding-001` + reranker Gemini, **chave free-tier** |
| Particularidades da sandbox | `api.mistral.ai`, Docker Hub e hosts de plugin do Neo4j bloqueados pelo proxy; PyPI/Maven liberados |

O que é **específico deste ambiente** (não se reproduz fora dele): o workaround do GDS
via Maven (ADR-6), o bloqueio da Mistral, e os tempos absolutos (hardware/entorno). O que
é **reproduzível em qualquer ambiente**: contagens da pipeline, contagens do grafo,
padrões gerados, fidelidade e o comparativo com o baseline (dados e seeds fixos).

## Camada 0 — pipeline (medições)

| Partida | Eventos kloppy | Ações SPADL | Linhas no parquet* | Fases | Passes c/ recebedor | Pressões (c/ alvo) |
|---|---|---|---|---|---|---|
| 3869685 (final) | 4.527 | 2.584 | 2.585 | 537 | 989 | 361 (301) |
| 3869519 (semi) | 3.891 | 2.272 | 2.274 | 346 | 916 | 290 (266) |
| 3869354 (quartas) | 3.351 | 1.895 | 1.895 | 326 | 791 | 230 (210) |

\* a diferença entre ações SPADL e linhas do parquet são os cartões que o SPADL
descarta e o passo 0.4h recupera do JSON bruto (1 na final, 2 na semi, 0 nas
quartas). Ver `01-pipeline.md`, passo 0.4h.

\* primeira execução inclui download das 16 partidas de treino + treino de xT/VAEP;
as demais usam cache.

## Camada 1 — grafo factual (medições)

| Partida | Escritas | Tempo |
|---|---|---|
| final | 8.004 | 3,2 s |
| semi | 6.895 | 1,5 s |
| quartas | 5.984 | 1,3 s |

O salto em relação à medição anterior (5.351 na final) vem da camada 1b: os
nós `EstatisticaJogador`/`EstatisticaTime` e a propagação do vocabulário de
futebol para todas as arestas.

Idempotência confirmada por teste (contagens idênticas após reconstrução).

## Camada 2 — insights (medições)

73 padrões táticos no total (24 + 22 + 27); distribuição por tipo e exemplos reais em
`03-insights.md`. `alvo_de_pressao` não disparou na final (sem concentração ≥1.5x a
média) — resultado honesto, registrado no catálogo.

## Camada 3 — validação ao vivo (medições)

| Operação | Medição |
|---|---|
| `GET /report/3869685` | 43 s; 5 seções, 25 citações; **fidelidade determinística 100% (25/25)**; sem menção a placar |
| `/ask` — recuperação estruturada | 0,02–0,43 s |
| `/ask` — geração (Haiku) | 5–7 s |
| Graphiti `add_triplet` | 24 padrões em 196 s com pacing de 2 s (free-tier); ~3 s/padrão sem cota |
| Graphiti `build_communities` | 2 comunidades (uma por seleção), resumos coerentes, 15 s |
| Graphiti busca híbrida | 0,29 s, 10 fatos relevantes |

**Teste de estresse de rate limit (ADR-7):** indexação da semifinal com pacing
desligado de propósito — a cota free-tier do Gemini (100 embeddings/min) foi estourada e
todos os 429 foram absorvidos pelo retry nativo do google-genai; 22 padrões em 163,5 s,
zero falhas.

**Bugs reais encontrados pela validação** (cada um corrigido; detalhes no ADR-5):
forma-string do PydanticAI ignora `LLM_API_KEY`; saída estruturada truncada nos defaults
do SDK; `cross_encoder=None` exige chave OpenAI no Graphiti; `text-embedding-004`
descontinuado; cota free-tier quebrava a indexação.

## Avaliação comparativa (grafo vs baseline vetorial)

Resultado central da tese — tabela e análise em `03-insights.md` (seção "Avaliação");
JSON completo por pergunta em `data/processed/eval_results_r3_sonnet.json` (gerado por
`scripts/run_evaluation.py`, não versionado). Duas rodadas executadas:

| Rodada | Golden | Formato de resposta | Estrutural: grafo (retr/insight) | Estrutural: baseline | Fidelidade |
|---|---|---|---|---|---|
| 1ª | 10 perguntas | registro único | 5.0 / 4.33 (n=9) | 1.0 / 1.0 | 100% |
| 2ª | 16 perguntas | duplo registro (tatiquês + em_bom_portugues) | 5.0 / 5.0 (n=15) | 1.0 / 1.13 | 100% |

Na agregada (n=1), a 2ª rodada deu grafo 5.0/5.0 vs baseline 2.0/1.0. Custo total das
duas rodadas + validações avulsas com `claude-haiku-4-5`: da ordem de centavos de dólar.

**3ª rodada (executada em 2026-08-25, `claude-sonnet-5` + embeddings Gemini):**
golden de 24 perguntas, 24/24 sem erro de autenticação.

| Categoria | n | Grafo (recuperação / insight) | Baseline vetorial | Fidelidade |
|---|---|---|---|---|
| estrutural | 15 | 4,93 / 4,73 | 1,13 / 1,13 | 100% |
| factual | 8 | 2,62 / 3,38 | 1,25 / 1,12 | 100% |
| agregada | 1 | 5,0 / 5,0 | 2,0 / 2,0 | 100% |

Reexecução de consultas 100% em 23 das 24 perguntas (0,75 em `q12_papel_sosa`).

> **O que "fidelidade 100%" significa — e o que não significa.** A métrica
> verifica duas coisas: que toda métrica citada aponta para um `PadraoTatico`
> existente com o mesmo valor, e que toda consulta registrada roda e devolve
> linhas. Ela **não** verifica que a resposta está certa. A prova está na
> própria tabela: `q23_desarmes_final` pontuou fidelidade 1.0 dando a resposta
> errada — o número saiu mesmo da consulta, mas a consulta perguntava outra
> coisa (tentativas de desarme em vez de desarmes certos). Erro semântico de
> consulta é invisível para qualquer verificação que não conheça a resposta de
> antemão; a defesa contra ele é o dado não ser ambíguo, mais
> `scripts/check_golden_queries.py`.

**Duas ressalvas importantes sobre essa tabela**, ambas descobertas na análise
posterior:

1. **A nota "recuperação" da categoria factual (2,62) mede outra coisa.** O juiz
   `judge_retrieval` pontua o CONTEXTO recuperado, e para pergunta factual o
   contexto é o dump bruto do Cypher, não a resposta. Perguntas cuja resposta
   final estava correta e bem citada tiraram 1/5 em recuperação e 4/5 em
   insight. Não é falha do sistema; é a métrica sendo lida fora do lugar.

2. **`q23_desarmes_final` estava genuinamente errada.** O sistema respondeu
   "Enzo Fernández 9 desarmes, Tagliafico 7, Kolo Muani 6"; a resposta é "Enzo
   5, Camavinga 4, Tagliafico 4". O modelo contou TENTATIVAS de desarme como
   desarmes. O ranking inteiro muda. Na mesma execução ele acertou os dribles
   (onde filtrou por sucesso) — ou seja, o comportamento era **inconsistente**,
   porque a semântica de "desarme" vivia no prompt e não no dado.

O achado 2 motivou a refatoração descrita em `00-entenda-o-projeto.md` (seção
2.6) e `01-pipeline.md` (passo 0.4h): o vocabulário de futebol passou para o
dado e as contagens viraram campos nomeados (`desarmes_certos` vs
`desarmes_tentados`).

**4ª rodada (não executada):** a refatoração deveria ser medida com uma nova
rodada de `run_evaluation.py`, mas a conta Anthropic ficou sem crédito. **Os
números da 3ª rodada acima são, portanto, do sistema ANTES da refatoração** —
não há medição pós-refatoração com juiz de LLM, e este documento não afirma
melhora que não foi medida.

O que foi possível verificar sem API está na seção seguinte.

## Verificação do modelo de dados (sem LLM, sem custo)

`scripts/check_golden_queries.py` roda a consulta de referência de cada uma
das 30 perguntas (`evaluation/reference_queries.py`) contra o grafo e imprime
a resposta esperada ao lado do que o grafo devolve. Separa o que a avaliação
completa mistura: **a qualidade do modelo de dados** e a qualidade do modelo
de linguagem.

Resultado em 2026-08-25: **30/30 perguntas com resposta no grafo.** As oito
factuais são consulta de um hop sobre `EstatisticaJogador`, sem agregação
escrita na hora — inclusive `q23`, que agora devolve Enzo 5 / Camavinga 4 /
Tagliafico 4 por construção. As três compostas (`q25`-`q27`) casam um
`PadraoTatico` com a súmula do jogador que ele aponta, numa consulta só.

Isto **não** substitui a avaliação com juiz: não mede se o LLM escolhe a
consulta certa, nem a qualidade do texto. Mede que o dado está lá, correto e
alcançável — que era a causa raiz do erro da 3ª rodada.

## Defeitos de dado encontrados e corrigidos em 2026-08-25

Três problemas achados ao auditar o grafo contra o StatsBomb bruto e a súmula
oficial. Nenhum deles era detectável pela avaliação com juiz, porque em dois
casos o golden dataset tinha sido conferido contra o próprio dado defeituoso.

| Defeito | Sintoma | Correção |
|---|---|---|
| SPADL descarta cartões de `bad_behaviour` | a final tem **7 amarelos em campo** e o grafo registrava 6 (faltava o do Giroud aos 95', por reclamação). O golden dizia 6 | resgate do JSON bruto no passo 0.4h; golden corrigido |
| `minuto` era contado dentro do período | o gol do Mbappé aos 80' estava gravado como "minuto 34.4" | `minuto` passa a ser o minuto de transmissão; os 6 gols batem com a súmula da FIFA (23, 36, 80, 81, 108, 118) |
| Janela temporal do insight 7.3 comparava escalas diferentes | `PASSOU_PARA.minuto` era minuto-do-período (float) e `PRESSIONOU.minuto` era minuto-absoluto (int). No 1º tempo coincidem por acaso; do 2º em diante diferem em 45 a 105 minutos e a janela de 8 s nunca fechava | campo `segundo` (contínuo desde o apito) em ambas as arestas; consulta do insight passa a usá-lo |

O terceiro é o mais sério em termos de método: o padrão `gatilho_pressao` vinha
de um join quebrado, e as respostas de referência de `q04` e `q16` no golden
dataset foram conferidas contra esse resultado — **estavam erradas as duas**.
Ambas foram recalculadas. Este é o argumento prático a favor de
`check_golden_queries.py`: um golden dataset conferido contra o sistema, e não
contra a realidade, valida o sistema contra si mesmo.

Cobertura de teste ao fim desta primeira leva: **47 testes**, incluindo uma trava que
falha se jargão SPADL (`take_on`, `tackle`, `tipo_spadl`) reaparecer no schema
exposto ao agente, e uma que verifica que a súmula pré-agregada bate com a
contagem ad-hoc sobre as mesmas arestas.

## Correções de integridade da comparação (2026-08-25, 2ª leva)

Uma auditoria do que ficou de fora da refatoração encontrou um desequilíbrio
que afeta a leitura de H₁, e ele foi corrigido.

**O baseline não tinha os mesmos fatos que o grafo.** A camada 1b deu ao lado
do grafo um `EstatisticaJogador` com ~30 contagens por jogador; o resumo do
baseline tinha passes, PPDA, field tilt, xT/VAEP e os 5 maiores passadores, e
mais nada — sem gols, cartões, desarmes, dribles ou defesas. Nas perguntas
factuais o baseline perdia por **ausência de dado**, não por ser vetorial, o
que não é evidência sobre grafos e é exatamente o tipo de assimetria que uma
banca aponta.

Correção em `evaluation/baseline_rag.py`: o resumo passa a incluir a ficha do
jogo (gols, assistências, cartões), a súmula individual dos jogadores com
volume e leaderboards por estatística — que é o que um RAG descritivo bem
construído precomputaria. Os números vêm de `evaluation/match_facts.py`, em
pandas, espelhando `graph/statistics.py`.

A duplicação de definição entre Cypher e pandas é deliberada (o baseline não
pode depender do grafo, senão deixa de ser independente) e é mantida honesta
por `tests/test_baseline_parity.py`, que compara jogador a jogador e falha em
qualquer divergência. Outros dois testes garantem que o baseline **não**
recebeu resultado da camada 2 — se betweenness ou comunidade vazassem para o
resumo, a comparação perderia o sentido pelo outro lado.

**Efeito esperado, ainda não medido:** as factuais devem empatar; as
estruturais o grafo continua ganhando. Isso FORTALECE a tese, porque isola a
vantagem no que é estrutural em vez de em volume de dado. Sem crédito de API,
a medição fica pendente — e nenhuma melhora é afirmada aqui sem ela.

**A recuperação passou a entregar as súmulas.** `api/retrieval.py` só buscava
`PadraoTatico`; agora, quando a pergunta cita jogador ou time, traz também o
`EstatisticaJogador`/`EstatisticaTime` correspondente (e as duas súmulas de
time quando nenhuma entidade é citada). Duas consequências: a maioria das
perguntas factuais deixa de precisar de uma ida e volta de ferramenta, e o
`judge_retrieval` — que pontua o CONTEXTO — passa a ver um contexto que
contém a resposta, o que corrige a nota de 2,62 sem maquiar nada.

**Categoria `composta`.** O projeto de pesquisa descrevia 4 categorias e o
código tinha 3. Foram acrescentadas `q25`-`q27`, que exigem cruzar um padrão
da camada 2 com um número da camada 1b — a categoria que melhor separa os
dois sistemas, porque metade da resposta é topologia de rede.

**Inconsistências menores corrigidas:** `segundo` faltava no `SCHEMA_DOC` (o
dicionário de dados gerado saía incompleto — agora coberto por teste);
`MOVE_TYPES` tinha `"carry"`, tipo que não existe no SPADL; `nominal_line`
dependia de precedência de `and`/`or` sem parênteses e tinha um ramo morto
(comportamento conferido idêntico antes e depois).

**Categoria agregada de n=1 para n=4.** A linha "agregada" da tabela de
resultados tinha uma pergunta só, o que não sustenta afirmação nenhuma — ainda
mais sendo a categoria em que a tese PREVÊ empate, e cujo empate é justamente o
que mostra que o grafo não perde no que um sistema descritivo já faz bem. Foram
acrescentadas posse de bola, volume de finalizações e aproveitamento de passe
(`q28`-`q30`), todas respondidas por `EstatisticaTime` e todas ao alcance do
baseline agora que ele tem paridade de fatos.

**Explicação.** `00-entenda-o-projeto.md` ganhou a seção 3, que segue uma
PERGUNTA de ponta a ponta com saída real da 3ª rodada — o caminho curto (q01,
respondida direto do padrão pré-calculado, zero Cypher) e o caminho longo (q17,
com os dois defeitos que a refatoração corrigiu). O documento cobria só o
caminho do DADO entrando. O projeto passou de 4 para 11 diagramas, e os oito
insights de `03-insights.md` ganharam uma linha de intuição em linguagem de
campo, mais desenho para betweenness e para ponte.

Cobertura após esta leva: **62 testes**, 30/30 no `check_golden_queries.py`.

## Modo autônomo (ADR-8) — validação ao vivo

O processo completo (5 bugs reais encontrados, cada um virando regra) está narrado em
`08-autonomia.md`; aqui ficam as medições.

**Q&A, rodada 1** (antes do endurecimento do prompt) expôs os dois riscos previstos:

| Achado | Sintoma observado | Correção |
|---|---|---|
| Vazamento de memória externa | resposta dos gols completou "3-3, pênaltis" sem consulta que sustentasse | regra 1 do prompt ampliada (proíbe completar com conhecimento externo, explícito sobre placar/pênaltis) |
| Join que multiplica linhas | `DEU_ASSISTENCIA×FINALIZOU` virou "Thuram: 3 assistências" (1 assistência × 3 gols do Mbappé) | schema anotado com o anti-padrão + regra de COUNT(DISTINCT)/contagem direta |

**Q&A, rodada 2** (prompt endurecido): gols 6/6 corretos por consulta única, assistências
2/2 corretas, dupla Otamendi-Romero 18 passes com citação combinada de padrão tático
(betweenness) — todas as consultas re-executam (check_queries 100%). A guarda read-only
recusa `CREATE`/`SET`/`CALL` na sintaxe e a transação READ do Neo4j bloqueia escrita no
servidor (coberto por teste).

**Q&A sobre o log completo `REALIZOU`** (2026-07-18, 5 perguntas novas, Haiku): todas
corretas contra o parquet, 1 consulta por pergunta, re-execução 100%:

| Pergunta | Resposta do sistema | Confere? |
|---|---|---|
| cartões amarelos | 6 (Paredes, Montiel, Enzo, Acuña; Rabiot, Thuram) | ⚠️ ver abaixo |
| dribles certos | Mbappé 6, Di María 5, Coman 4 | ✅ |
| desarmes | Enzo Fernández 5; Tagliafico e Camavinga 4 | ✅ |
| defesas de goleiro | Lloris 8, Martínez 2 | ✅ |
| passes errados | Molina 16; Tchouaméni e Enzo 13 | ✅ |

⚠️ **Correção retroativa (2026-08-25):** a linha dos cartões foi marcada como
correta em 2026-07-18 porque batia com o grafo — mas o grafo estava errado. A
final teve 7 amarelos em campo; o do Giroud (95', por reclamação) era
descartado pelo SPADL. O sistema respondeu certo *sobre um dado incompleto*.
É o padrão de falha que motivou a auditoria contra a fonte bruta descrita mais
adiante: conferir a resposta contra o grafo só valida o grafo contra si mesmo.

⚠️ Note também que os desarmes aparecem corretos aqui (validação manual, uma
pergunta por vez) e ERRADOS na 3ª rodada de avaliação (9 em vez de 5). A
diferença é a inconsistência do modelo diante de um dado ambíguo — motivo pelo
qual a semântica saiu do prompt.

**Relatório autônomo** (2026-07-18, Haiku): rodada 1 do relatório reproduziu DOIS bugs
novos (o join das assistências reapareceu no outro agente + atribuição de time de
memória — bugs 3 e 4 do `08-autonomia.md`); rodada 2, após endurecimento: 72–77 s,
7→5 seções, seção "O jogo em fatos" com gols 6/6 (nome+time+minuto+período do grafo) e
assistências 2/2 por listagem direta de arestas, 28/28 citações de padrão válidas,
re-execução de consultas 100%. Ficou um vazamento residual no `resumo_executivo`
("decidida nos pênaltis, 3 a 3") — bug 5, regra aplicada; a revalidação dessa correção
rodou com **Gemini como LLM principal** (a chave Anthropic foi rotacionada no meio da
validação), o que de quebra validou ao vivo a troca de provedor só por `.env`.

## O que NÃO foi validado ao vivo

- Provedor **Mistral** como LLM (bloqueio de rede da sandbox; caminho de código coberto
  por testes de introspecção sem rede).
- ~~Gemini como LLM principal~~ — validado em 2026-07-18: o relatório autônomo rodou
  com `LLM_PROVIDER=gemini`/`gemini-2.5-flash` (free tier) trocando apenas variáveis de
  ambiente, com seção factual correta e re-execução de consultas 100% (23/24 citações de
  padrão válidas nessa rodada).
- ~~A rodada formal de avaliação com o golden de 24 perguntas~~ — executada em
  2026-08-25 (ver seção de avaliação).
- **O sistema depois da refatoração do vocabulário de futebol.** A conta
  Anthropic ficou sem crédito antes da 4ª rodada. Há verificação determinística
  do modelo de dados (30/30 em `check_golden_queries.py`) e 62 testes, mas
  nenhuma medição com juiz de LLM após a mudança. Qualquer afirmação de melhora
  de nota seria não medida — e por isso não é feita aqui.

## Desenho da 4ª rodada: ablação da súmula (2026-08-26)

A 4ª rodada não roda mais dois sistemas, e sim **três braços** sobre as mesmas
30 perguntas, no mesmo modelo e na mesma execução (`scripts/run_evaluation.py`):

| Braço | Contexto do agente | O que mede |
|---|---|---|
| `grafo_sem_sumula` | padrões da camada 2 + ferramenta `consultar_grafo` | a autonomia do ADR-8: o número factual só chega se o agente escrever Cypher |
| `grafo_com_sumula` | o anterior + súmula da camada 1b | o comportamento da API |
| `baseline` | chunks do resumo textual, com paridade de fatos | representação em texto embeddado |

O motivo está na ADR-10: a súmula pronta economiza uma ida e volta de
ferramenta e cala o text-to-Cypher no mesmo gesto, e não dá para decidir isso
no olho. A diferença entre os dois primeiros braços é essa troca medida.
`n_consultas` por braço é o indicador direto — se o braço com súmula zera as
consultas, ela calou a ferramenta.

**Sinal que valida o desenho, antes de qualquer conclusão:** na categoria
`estrutural` os dois braços do grafo devem ficar praticamente iguais, porque
nenhum campo da súmula contém betweenness, comunidade ou ponte. Se divergirem
muito, o braço está mal isolado e o resto da rodada não vale.

### Duas notas de recuperação, e por que a comparação com o baseline usa a primeira

Até a 3ª rodada, `judge_retrieval` recebia os padrões **mais o resultado das
consultas que o agente executou durante a geração**. Isso não é recuperação: é
o sistema inteiro. E o baseline, que não tem ferramenta, nunca recebia
acréscimo equivalente — a assimetria empurrava a métrica a favor do grafo.

| Métrica | Contexto julgado | Compara com o baseline? |
|---|---|---|
| `retrieval_previo` | padrões (+ súmula, no braço que a tem) | **sim** — é a simétrica |
| `retrieval_final` | o anterior + `consultas_executadas` | não — o baseline não tem equivalente |

Consequência para ler a tabela da 3ª rodada: a nota única de lá é a
`retrieval_final`. Os 4,93 de `estrutural`, por exemplo, incluem perguntas que
rodaram até 4 consultas. `retrieval_previo` é métrica nova e não tem
equivalente anterior para confrontar.

### Conferência do pipeline: amostra de 4 perguntas (2026-08-26)

`run_evaluation.py --amostra`, uma pergunta de cada categoria, em
`openrouter:z-ai/glm-5.3-flash`. Fidelidade 100% nos dois braços do grafo.
**n=1 por categoria: isto confere o mecanismo, não mede o sistema.** Nenhuma
conclusão sobre o efeito da súmula sai daqui.

| Categoria | Braço | Prévio | Final | Insight | Consultas |
|---|---|---:|---:|---:|---:|
| estrutural | grafo sem súmula | 5,0 | 5,0 | 5,0 | 0 |
| estrutural | grafo com súmula | 5,0 | 5,0 | 5,0 | 0 |
| estrutural | baseline | 1,0 | — | 2,0 | — |
| factual | grafo sem súmula | 1,0 | 1,0 | 3,0 | 2 |
| factual | grafo com súmula | 1,0 | 5,0 | 5,0 | 2 |
| factual | baseline | **5,0** | — | 3,0 | — |
| agregada | grafo sem súmula | 5,0 | 5,0 | 5,0 | 0 |
| agregada | grafo com súmula | 5,0 | 5,0 | 5,0 | 0 |
| agregada | baseline | 3,0 | — | 3,0 | — |
| composta | grafo sem súmula | 2,0 | 2,0 | 5,0 | 3 |
| composta | grafo com súmula | 5,0 | 5,0 | 5,0 | 1 |
| composta | baseline | 1,0 | — | 1,0 | — |

**O desenho passou no teste que o valida.** Em `estrutural`, os dois braços do
grafo saíram idênticos e sem nenhuma consulta — que é o previsto, já que
nenhum campo da súmula contém betweenness. Se tivessem divergido, o braço
estaria mal isolado e o resto não valeria.

Três coisas que a métrica antiga escondia, visíveis já com n=1:

1. **Na factual, o baseline ganha a comparação simétrica** (5,0 contra 1,0 de
   prévio). A pergunta era "quem fez os gols da final": não cita jogador nem
   time, então `resolve_entities` não resolve nada e a súmula que chega é só a
   dos dois times — que tem o TOTAL de gols, não quem fez. O resumo textual do
   baseline tem a linha dos gols pronta. A recuperação do grafo é pior aqui, e
   a nota única antiga registrava 5,0 porque o agente ia buscar depois.
2. **A súmula não ajudou onde se esperava e ajudou onde não se esperava.** Na
   factual não mudou o prévio (1,0 nos dois braços); na `composta` levou o
   prévio de 2,0 a 5,0 e cortou as consultas de 3 para 1.
3. **Prévio e final divergem exatamente onde há consulta** — factual e
   composta. Onde o agente não consulta, são o mesmo número por construção.

### Custo medido

US$ 0,061 na chave para as 5 perguntas executadas (1 avulsa + as 4 da
amostra), ou **US$ 0,012 por pergunta** somando os três braços. A rodada
completa de 30 perguntas fica em torno de **US$ 0,37**. Uma estimativa
anterior de US$ 0,09 subestimou em ~4x, por não contar que
`fallback_todos_padroes` injeta os ~24 padrões da partida inteira no contexto
e que o modelo cobra tokens de raciocínio como saída.

### O que ainda NÃO foi medido

A rodada completa das 30 perguntas nos três braços. Até ela existir, a tabela
de avaliação citável continua sendo a da 3ª rodada, com a ressalva de que a
nota de recuperação de lá é a `retrieval_final`.

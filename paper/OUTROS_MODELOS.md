# Outros modelos: o que foi rodado além do Haiku 5.5

Nota de passagem para a escrita do artigo (12/10/2026). Os resultados principais continuam sendo os de
`data/benchmark/final_results.jsonl` (Haiku 5.5). Este arquivo diz o que foi rodado com outros modelos, onde estão os
arquivos e o que o texto pode e não pode afirmar com eles. Qwen e Kimi K3 estão em `paper/data/models.yaml`, então
`scripts/paper_numbers.py` já gera as macros com prefixo (`\accQwenGraphTools`, `\accKimiGraphTools`...).

## Por que outros modelos

Com um modelo só, a objeção previsível é "isso vale só para o Haiku?". O Haiku 5.5 e o Qwen3.8-flash são da faixa
pequena e barata dos seus laboratórios; a pergunta de escala (a vantagem das ferramentas encolhe com um modelo mais
capaz?) pede um modelo grande. Por isso: Qwen3.8-flash (outro laboratório, pesos abertos, pequeno) e Kimi K3 (pesos
abertos, grande). As macros e tabelas de Qwen e Kimi K3 já saem de `paper/data/models.yaml`.

## Qwen3.8-flash: rodada completa

- Arquivo: `data/benchmark/qwen_results.jsonl` (312 execuções: 52 perguntas x 6 braços x 1 repetição);
  página `docs/execucoes/2026-10-12_15_qwen.md`; resumo `data/benchmark/qwen_summary.md`.
- Via OpenRouter, provedor fixo Alibaba (`LLM_PROVIDER_ORDER=alibaba`, sem fallback), raciocínio desligado
  (`LLM_REASONING_EFFORT=none`): o Alibaba recusa o `tool_choice` forçado (que o PydanticAI usa para a resposta
  final) em modo de raciocínio. O artigo precisa dizer isso no método.
- Custo calculado pelos tokens: US$ 0,49.

Acerto nas 47 perguntas com resposta (Wilson, pergunta como unidade), ao lado do Haiku:

| Braço | Qwen3.8-flash | IC 95% | Haiku 5.5 |
|---|---|---|---|
| graph_tools | 39/47 = 83% | 70 a 91 | 41/47 = 87% |
| text_to_cypher | 27/47 = 57% | 43 a 70 | 33/47 = 70% |
| events_in_prompt | 19/47 = 40% | 28 a 55 | 21/47 = 45% |
| vector | 4/47 = 9% | 3 a 20 | 5/47 = 11% |
| stats_in_prompt | 2/47 = 4% | 1 a 14 | 0/47 |
| no_context | 0/47 | 0 a 8 | 0/47 |

McNemar exato no Qwen (só o primeiro / só o segundo, p, p de Holm para os três testes):
graph_tools x events_in_prompt 23/3, p < 0,001; graph_tools x text_to_cypher 15/3, p = 0,008 (Holm 0,016);
text_to_cypher x events_in_prompt 12/4, p = 0,077 (Holm 0,077). Diferença em relação ao Haiku: lá
text_to_cypher x events_in_prompt foi significativo (Holm 0,034); aqui não é.

Por grupo (events_in_prompt / text_to_cypher / graph_tools): busca e contagem 7/8/8 de 11; relações 9/12/17 de 20;
jogadas 2/3/8 de 10; antes e depois 1/4/6 de 6.

Leitura: a ordem dos braços se repete num segundo laboratório. A vantagem do graph_tools sobre os outros dois se
mantém; a do text_to_cypher sobre o events_in_prompt não se sustenta neste modelo.

## Kimi K3: rodada completa (modelo grande, pesos abertos)

- Arquivo: `data/benchmark/kimi_k3_results.jsonl` (312 execuções); página `docs/execucoes/2026-10-12_16_kimi-k3.md`;
  já está em `paper/data/models.yaml` (macros com prefixo `Kimi`, colunas nas tabelas `*_models.tex`).
- Via OpenRouter com a chave do autor no Amazon Bedrock (BYOK), provedor fixo `amazon-bedrock/us-east-2`, sem
  fallback e sem a capacidade compartilhada do OpenRouter. Raciocínio no padrão do modelo (ligado).
- Custo real: US$ 33,40 na AWS (uso BYOK da chave); créditos do OpenRouter: zero. 16 execuções falharam com erro
  502 do Bedrock e foram refeitas com `--resume`.

| Braço | Kimi K3 | IC 95% | Qwen3.8-flash | Haiku 5.5 |
|---|---|---|---|---|
| text_to_cypher | 44/47 = 94% | 83 a 98 | 57% | 70% |
| graph_tools | 42/47 = 89% | 77 a 95 | 83% | 87% |
| events_in_prompt | 40/47 = 85% | 72 a 93 | 40% | 45% |
| vector | 8/47 = 17% | 9 a 30 | 9% | 11% |
| stats_in_prompt | 3/47 = 6% | 2 a 17 | 4% | 0% |
| no_context | 0/47 | 0 a 8 | 0% | 0% |

McNemar exato no Kimi K3 (só o primeiro / só o segundo, p, Holm): text_to_cypher x events_in_prompt 6/2, p = 0,29
(Holm 0,87); graph_tools x text_to_cypher 2/4, p = 0,69 (Holm 1); graph_tools x events_in_prompt 6/4, p = 0,75
(Holm 1). Nenhuma diferença significativa.

Por grupo (events_in_prompt / text_to_cypher / graph_tools): busca e contagem 11/11/10 de 11; relações 17/19/18
de 20; jogadas 7/9/10 de 10; antes e depois 5/5/4 de 6.

Latência média por pergunta: events_in_prompt 71 s, text_to_cypher 38 s, graph_tools 81 s (Haiku: 4, 10 e 8 s).

**Isto muda a conclusão do artigo.** Com o modelo grande, os três braços com acesso aos dados ficam todos entre 85% e
94%, sem diferença estatística. O events_in_prompt sobe de 40 a 45% para 85%, e o text_to_cypher fica numericamente
à frente do graph_tools. A escada só aparece nos modelos pequenos. A leitura que os dados sustentam: as ferramentas
prontas compensam a falta de capacidade de modelos pequenos; com um modelo grande, ler a tabela inteira ou escrever
a consulta chega ao mesmo lugar, a um custo e latência maiores. O texto genérico dos Resultados (que fala da ordem
dos braços) precisa ser revisto à luz disso.

## Correção feita depois da rodada do Haiku (declarar no método)

Commit `e45cba2` (`_unquote` em `src/football_graphrag/benchmark/arms.py`): um argumento de ferramenta enviado como
texto JSON (`"{\"yellow_card\": true}"`) passa a ser lido como objeto, e o objeto ainda passa pela validação do
argumento. Qwen e MiMo mandavam `filters` assim e o graph_tools falhava 4 de 4 na triagem; com a correção, 4 de 4
certas. O esquema mostrado ao modelo não mudou. O Haiku nunca mandou argumento nesse formato, então a correção não
deveria alterar os resultados dele; isso não foi reexecutado para provar. Também na mesma linha: `LLM_PROVIDER_ORDER`
(commit `b0d758d`) fixa o provedor no OpenRouter.

## Triagens (2 a 5 perguntas; não são resultado, servem só como observação)

| Modelo | Via | O que aconteceu |
|---|---|---|
| DeepSeek V4 Pro | OpenRouter, Baidu fp8 | 2 de 10 certas (`second_models_pro_sample_results.jsonl`); omite `players` na resposta final, ou raciocina até estourar 16 mil tokens |
| MiMo v2.6 Pro | OpenRouter, Xiaomi fp8 | events_in_prompt 2/2; graph_tools 0/2 antes da correção de argumentos, 2/2 depois |
| GLM-5 | Bedrock (BYOK) | respostas vazias intermitentes (só raciocínio) no graph_tools |
| Kimi K2.5 | Bedrock (BYOK) | 3 de 4; uma excedeu o limite de chamadas |
| gpt-oss-20b | Bedrock (BYOK) | o Bedrock recusou o nome de ferramenta `list_actions<\|channel\|>commentary` |
| gpt-6-luna (fechado) | Bedrock (BYOK) | 3 de 4, sem erro de formato; o cache do events_in_prompt escreveu e nunca leu |
| Kimi K3 | Bedrock (BYOK) | 4 de 4 |

O que o texto pode dizer com isso: a vantagem das ferramentas depende de o modelo usá-las de forma confiável, e
vários modelos tropeçaram no formato das chamadas ou da resposta final. Como limitação observada, não como
resultado medido.

## Afirmações que o artigo pode fazer

- Com Haiku e Qwen: a ordem graph_tools > text_to_cypher > events_in_prompt > demais se repete em dois laboratórios,
  em modelos pequenos.
- Com o Kimi K3: num modelo grande de pesos abertos, essa ordem desaparece; os três braços com acesso aos dados
  empatam (85 a 94%). A vantagem das ferramentas depende do tamanho do modelo.
- O custo muda de lado: o graph_tools no Haiku custou centavos; o events_in_prompt no Kimi K3 lê ~82 mil tokens por
  pergunta e leva mais de um minuto. Ferramentas tornam um modelo pequeno e barato competitivo com um grande.
- Em todos os casos: uma repetição por pergunta; os intervalos são largos (n = 47); três modelos não são uma curva de
  escala.

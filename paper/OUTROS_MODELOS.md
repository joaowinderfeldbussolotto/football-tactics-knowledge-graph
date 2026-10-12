# Outros modelos: o que foi rodado além do Haiku 5.5

Nota de passagem para a escrita do artigo (12/10/2026). Os resultados principais continuam sendo os de
`data/benchmark/final_results.jsonl` (Haiku 5.5). Este arquivo diz o que foi rodado com outros modelos, onde estão os
arquivos e o que o texto pode e não pode afirmar com eles. Nenhum desses números ainda tem macro em
`generated/numbers.tex`: `scripts/paper_numbers.py` lê só `final_results.jsonl`, e precisa ser estendido (com
`--results` por modelo ou um prefixo de macro por modelo) antes de o texto citar qualquer um deles.

## Por que outros modelos

Com um modelo só, a objeção previsível é "isso vale só para o Haiku?". O Haiku 5.5 e o Qwen3.8-flash são da faixa
pequena e barata dos seus laboratórios; a pergunta de escala (a vantagem das ferramentas encolhe com um modelo mais
capaz?) pede um modelo grande. Por isso: Qwen3.8-flash (outro laboratório, pesos abertos, pequeno) e Kimi K3 (pesos
abertos, grande).

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

## Kimi K3: rodada completa em andamento

- Arquivo (quando terminar): `data/benchmark/kimi_k3_results.jsonl`, página em `docs/execucoes/`. Será acrescentado
  a esta branch.
- Via OpenRouter com a chave do autor no Amazon Bedrock (BYOK), provedor fixo `amazon-bedrock/us-east-2`, sem
  fallback e sem a capacidade compartilhada do OpenRouter. Raciocínio no padrão do modelo.
- Custo esperado: US$ 30 a 35 de crédito AWS (o cache do events_in_prompt lê só em parte das chamadas).

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
- Com o Kimi K3 (depois da rodada): se a ordem se mantém num modelo grande de pesos abertos.
- Em todos os casos: uma repetição por pergunta; os intervalos são largos (n = 47).

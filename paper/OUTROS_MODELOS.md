# Outros modelos: o que foi rodado além do Haiku 5.5

Nota de passagem para a escrita do artigo (12/10/2026). Os resultados principais continuam sendo os de
`data/benchmark/final_results.jsonl` (Haiku 5.5). Este arquivo diz o que foi rodado com outros modelos, onde estão os
arquivos e o que o texto pode e não pode afirmar com eles. Qwen, Kimi K3 e Sonnet 4.6 estão em `paper/data/models.yaml`, então
`scripts/paper_numbers.py` já gera as macros com prefixo (`\accQwenGraphTools`, `\accKimiGraphTools`...).

## Desenho: dois fechados, dois de pesos abertos, pareados por preço

| | Faixa barata | Faixa cara |
|---|---|---|
| Fechado | Claude Haiku 5.5 (US$ 0,10 / 0,50 por M) | Claude Sonnet 4.6 (US$ 3 / 15) |
| Pesos abertos | Qwen3.8-flash (US$ 0,15 / 0,47) | Kimi K3 (US$ 3 / 15) |

Preços de entrada / saída por milhão de tokens nos provedores usados. O critério é o custo de uso: o par barato e o
par caro custam o mesmo dentro de cada faixa (Sonnet 4.6 e Kimi K3 têm preço idêntico no Bedrock). Não é
"mesmo tamanho": a Anthropic não divulga parâmetros, e o Sonnet é a faixa intermediária dela, abaixo do Opus.
A escolha do fechado caro veio da disponibilidade na conta AWS do autor: Opus, Haiku 5.5, os GPT e os Nova
aparecem como indisponíveis ou bloqueados pela política da organização; o Sonnet 4.6 é o mais recente liberado
(só na região us-east-2). O texto deve dizer isso.

Por quê: com um modelo só, a objeção previsível é "isso vale só para o Haiku?". Os dois baratos respondem à
generalização entre laboratórios; os dois caros, à pergunta de escala (a vantagem das ferramentas encolhe com um
modelo mais capaz?).

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

## Claude Sonnet 4.6: rodada completa (fechado, faixa cara)

- Arquivos: `data/benchmark/sonnet46_results.jsonl` (rodada com raciocínio "medium", 312 execuções; página
  `docs/execucoes/2026-10-13_17_sonnet46.md`), `sonnet46_events_low_results.jsonl` (events_in_prompt refeito com
  raciocínio "low", 52 perguntas) e `sonnet46_combined_results.jsonl` (o que o artigo usa: a rodada "medium" com
  as linhas do events_in_prompt trocadas pelas "low", e as 6 que ainda estouraram com "low" trocadas pela nova
  tentativa com teto de 32 mil em `sonnet46_events_low32k_results.jsonl`, por `scripts/merge_results.py`).
- Chamada direta ao Amazon Bedrock (provedor `bedrock` do código, API Converse), perfil de inferência
  `us.anthropic.claude-sonnet-4-6`, região us-east-2. Raciocínio estendido ligado (`LLM_REASONING_EFFORT`, que no
  Bedrock vira o ajuste `thinking` do PydanticAI) e, por exigência da Anthropic, temperatura 1.
- **Esforço diferente por braço (declarar):** com "medium", em 19 das 52 perguntas do events_in_prompt o modelo
  gastou os 16 mil tokens de saída raciocinando e não respondeu. Nas 28 que responderam, acertou 25. Com "low" e o
  mesmo teto, o events_in_prompt passou a 68% (32/47), com 6 estouros. Essas 6 foram refeitas com "low" e teto de
  32 mil: s04 e p02 certas, s12 e b06 erradas (responderam com 6 a 8,5 mil tokens; com o teto de 16 mil tinham
  estourado, então parte dos estouros é aleatória, a temperatura é 1), a05 e n09 estouraram de novo (também
  estouram com "medium"). Com elas, 72% (34/47). Os outros braços ficam com "medium": neles não houve estouro.
  Assim, o events_in_prompt do Sonnet tem duas condições (teto de 16 mil e, em 6 perguntas, 32 mil).
- Amostra de sensibilidade em 5 das perguntas que estouraram (`sonnet46_events_32k_results.jsonl` e as 5 primeiras
  linhas do arquivo "low"): "medium" com 16 mil, 0/5; "medium" com 32 mil, 3/5 (raciocínios de 10 a 32 mil tokens,
  até 4,5 min por pergunta, uma estourou de novo); "low" com 16 mil, 4/5. Raciocinar mais não ajudou nessa tarefa.
- Custo calculado pelos tokens (chamada direta, sem consumo de chave para ler): US$ 17,76 a rodada "medium",
  US$ 6,05 o events_in_prompt "low", US$ 1,99 a nova tentativa "low" com 32 mil, US$ 2,21 a amostra "medium" de
  32 mil; total US$ 28,01. Créditos do OpenRouter: zero.

| Braço | Sonnet 4.6 | IC 95% |
|---|---|---|
| graph_tools | 42/47 = 89% | 77 a 95 |
| text_to_cypher | 42/47 = 89% | 77 a 95 |
| events_in_prompt ("low"; 6 com teto de 32 mil) | 34/47 = 72% | 58 a 83 |
| vector | 7/47 = 15% | 7 a 28 |
| stats_in_prompt | 4/47 = 9% | 3 a 20 |
| no_context | 0/47 | 0 a 8 |

McNemar exato (arquivo combinado): text_to_cypher x events_in_prompt 8/0, p = 0,008 (Holm 0,023); graph_tools x
text_to_cypher 5/5, p = 1; graph_tools x events_in_prompt 12/4, p = 0,077 (Holm 0,154, não significativo).

Por grupo (events_in_prompt / text_to_cypher / graph_tools): busca e contagem 9/11/11 de 11; relações 14/17/18 de
20; jogadas 8/8/9 de 10; antes e depois 3/6/4 de 6. Latência média: events_in_prompt 51 s ("low"), text_to_cypher
16 s, graph_tools 19 s.

## Raciocínio e temperatura dos modelos caros (declarar no método)

- Kimi K3 é um modelo de raciocínio (2,8 trilhões de parâmetros, pesos abertos) e rodou com o raciocínio no padrão
  dele (ligado): saída mediana de 12 mil tokens no events_in_prompt, contra 464 no Haiku. O endpoint do Bedrock
  para o K3 não aceita `temperature`: o valor 0 do código foi descartado e ele rodou na temperatura padrão.
- Sonnet 4.6 rodou com raciocínio ligado e temperatura 1 (ver acima).
- Haiku 5.5 e Qwen3.8-flash rodaram sem raciocínio (o Qwen com `LLM_REASONING_EFFORT=none`) e com temperatura 0.
- Ou seja: no desenho, a faixa cara também é a faixa com raciocínio. Tamanho e raciocínio estão confundidos;
  o texto não deve atribuir o efeito a um só dos dois.

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

| Braço | Haiku 5.5 | Qwen3.8-flash | Sonnet 4.6 | Kimi K3 |
|---|---|---|---|---|
| graph_tools | 87% | 83% | 89% | 89% |
| text_to_cypher | 70% | 57% | 89% | 94% |
| events_in_prompt | 45% | 40% | 72% | 85% |

- O graph_tools é estável: 83 a 89% nos quatro modelos, baratos e caros, abertos e fechados.
- O text_to_cypher cresce com o modelo: 57 a 70% nos baratos, 89 a 94% nos caros, onde empata com o graph_tools
  (Sonnet 5/5; Kimi 2/4, sem diferença).
- O events_in_prompt depende do modelo e do raciocínio: 40 a 45% nos baratos, 72 a 85% nos caros. No Sonnet fica
  abaixo do text_to_cypher (significativo) e do graph_tools (não significativo depois de Holm). Ler a tabela inteira custa caro: 51 a 71 s por
  pergunta e milhares de tokens de raciocínio nos modelos caros.
- Leitura geral: ferramentas prontas tornam um modelo barato competitivo com os caros; com um modelo caro, escrever
  a consulta (text_to_cypher) chega ao mesmo lugar. Tamanho e raciocínio vêm juntos nos caros (ver acima).
- Em todos os casos: uma repetição por pergunta; os intervalos são largos (n = 47); quatro modelos não são uma curva
  de escala.

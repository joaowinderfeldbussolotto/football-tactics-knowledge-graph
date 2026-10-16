# 7. Decisões, problemas encontrados e limitações

Este capítulo reúne o "porquê" do projeto: as escolhas que moldaram o
benchmark, os problemas conhecidos nos dados (e como são tratados) e o que o
benchmark **não** consegue dizer. Leia antes de tirar conclusões dos
resultados.

---

## 7.1 Decisões de projeto

### Simplicidade acima de completude

O projeto começou como um sistema maior: uma API web, uma camada de busca
híbrida (Graphiti) e outros LLMs atuando como juízes das respostas. Tudo isso
foi removido. Cada peça extra era mais uma coisa que podia falhar e mais uma
variável que confundia a pergunta central. O que sobrou é o mínimo para
comparar seis formas de entregar dados a um modelo, de forma verificável.

### Uma partida só

Só a final da Copa 2022. Isso mantém o gabarito pequeno o bastante para ser
conferido à mão e a tabela de eventos pequena o bastante para caber no
contexto de um modelo (o braço `events_in_prompt` precisa disso). O preço
está em 7.3.

### O gabarito nunca vem do banco avaliado

Explicado no capítulo 3: se o gabarito fosse lido do Neo4j, um erro no banco
apareceria dos dois lados e contaria como acerto. O gabarito sai do JSON
bruto e da camada 0, e é **comparado** com o Neo4j, nunca copiado dele.

### Nenhum LLM dá nota

Juízes LLM erram, variam de uma execução para outra e custam dinheiro. Com
perguntas fechadas e respostas num formato fixo, a correção é um `if`.

### Mesma configuração em todos os braços

Dentro de uma rodada: mesmo modelo, mesma instrução, temperatura 0, mesmo
formato de resposta com o mesmo número de novas tentativas. (Exceções de
temperatura e esforço de raciocínio nos modelos caros: 7.1, "Quatro
modelos".) O formato é entregue sempre pelo mesmo
mecanismo do PydanticAI (a resposta vem como uma "ferramenta de saída"),
porque ele funciona junto com as ferramentas do `graph_tools`. Usar um
mecanismo diferente em algum braço seria mais uma diferença além dos dados.

A instrução de sistema diz que as perguntas são sobre **uma partida**, sem
dizer qual. Dizer "a final da Copa de 2022" ajudaria o modelo a responder de
memória em vez de usar os dados.

### Quatro modelos, pareados por preço

A primeira rodada usou um modelo só, o Claude Haiku 5.5. Para saber se a
ordem dos braços vale além dele, foram rodados mais três, escolhidos num
desenho 2 × 2: fechado ou de pesos abertos, barato ou caro.

| | Faixa barata | Faixa cara |
|---|---|---|
| **Fechado** | Claude Haiku 5.5 (US$ 0,10 / 0,50 por milhão de tokens) | Claude Sonnet 4.6 (US$ 3 / 15) |
| **Pesos abertos** | Qwen3.8-flash (US$ 0,15 / 0,47) | Kimi K3 (US$ 3 / 15) |

O critério é o **preço**, não o tamanho (que nenhum dos laboratórios fechados
divulga): dentro de cada faixa, os dois modelos custam o mesmo, e a pergunta
vira "pelo mesmo preço, qual forma de acesso aos dados rende mais?". O
Sonnet não é o topo de linha da Anthropic (o Opus é); foi o fechado caro
disponível na conta usada.

Acerto nas 47 perguntas com resposta:

| Braço | Haiku 5.5 | Qwen3.8-flash | Sonnet 4.6 | Kimi K3 |
|---|---|---|---|---|
| `graph_tools` | 87% | 83% | 89% | 89% |
| `text_to_cypher` | 70% | 57% | 89% | 94% |
| `events_in_prompt` | 45% | 40% | 72% | 85% |
| `vector` | 11% | 9% | 15% | 17% |
| `stats_in_prompt` | 0% | 4% | 9% | 6% |
| `no_context` | 0% | 0% | 0% | 0% |

O que se lê: o `graph_tools` fica entre 83% e 89% em todos. Nos baratos, ele
é claramente o melhor; nos caros, escrever a consulta (`text_to_cypher`)
chega ao mesmo lugar, e ler a tabela inteira (`events_in_prompt`) chega perto,
a um custo de tempo e de tokens de raciocínio bem maior. Ferramentas prontas
tornam um modelo barato competitivo com os caros.

Condições de cada rodada, que o texto do artigo tem de declarar:

- **Haiku 5.5:** OpenRouter, temperatura 0, sem raciocínio.
- **Qwen3.8-flash:** OpenRouter com o provedor fixo no Alibaba, raciocínio
  desligado (`none`), porque o Alibaba recusa a resposta estruturada com
  raciocínio; temperatura 0.
- **Kimi K3:** OpenRouter com a chave do autor no Bedrock (`us-east-2`), sem
  fallback. É um modelo de raciocínio e rodou com ele ligado (padrão). O
  Bedrock não aceita `temperature` para ele: rodou na temperatura padrão.
- **Sonnet 4.6:** Bedrock direto (`us-east-2`), raciocínio estendido `medium`
  e temperatura 1 (exigência da Anthropic com raciocínio). No
  `events_in_prompt`, com `medium`, o raciocínio esgotou o teto de 16 mil
  tokens em 19 das 52 perguntas, sem resposta; o braço foi refeito com
  `low`, e as 6 que ainda estouraram, com teto de 32 mil. O resultado usado é
  o arquivo combinado (`sonnet46_combined_results.jsonl`); as rodadas de
  origem ficam guardadas. Numa amostra de 5 perguntas, `medium` com 32 mil
  acertou 3 e `low` com 16 mil acertou 4: raciocinar mais não ajudou nessa
  tarefa.

Antes de cada rodada, uma triagem de 2 perguntas mostrou se o modelo
funcionava. Ficaram de fora: DeepSeek V4 Pro (deixava de preencher a resposta
final ou raciocinava até estourar o teto), GLM-5 (respostas vazias
intermitentes), gpt-oss-20b (o nome da ferramenta saía com um marcador interno
e o Bedrock recusava) e os modelos fechados que a conta não liberava. Que
metade dos modelos testados tropece no formato das chamadas é, por si, um
achado: a vantagem das ferramentas depende de o modelo usá-las de forma
confiável.

Os arquivos, as páginas de cada execução e a nota para o artigo estão em
`data/benchmark/` (`final_results`, `qwen_results`, `kimi_k3_results`,
`sonnet46_combined_results`), `docs/execucoes/` e
`paper/OUTROS_MODELOS.md` (na branch do artigo).

### Perguntas sem definição, testadas em todas as leituras

As perguntas descrevem os conceitos como um comentarista ("o principal elo
da circulação de bola", "a dupla que mais trocou passes"), sem dizer como
calcular. Um teste impede vocabulário de ferramenta ou de algoritmo. O preço
é que a mesma pergunta pode ser lida de mais de um jeito. Em vez de
acrescentar definição ao texto, o gabarito calcula a resposta em todas as
leituras razoáveis e a pergunta só fica se todas concordam (capítulo 3,
seção 3.5).

### Ferramentas primitivas, fixadas antes das perguntas

As oito ferramentas do `graph_tools` são operações sem conceito tático
pronto: filtrar e contar ações, listar ações, montar uma rede de passes,
calcular uma métrica, listar ligações, contar sequências. O modelo tem de
combiná-las. Elas foram escritas e fixadas antes das perguntas que as
testam, e um teste guarda um hash das definições.

O modelo nunca escreve Cypher: cada ferramenta executa uma consulta fixa,
com parâmetros. Escrever consultas misturaria duas habilidades (saber
consultar um banco e saber usar os dados), e a primeira não é o que se quer
medir. Nenhuma ferramenta lê os padrões prontos da camada 2.

### Descrições de ferramenta com a leitura no futebol

Cada descrição tem duas partes: o que a ferramenta calcula e o que isso
costuma significar no futebol ("betweenness... marks a player who connects
teammates in ball circulation"). Um produto real faria o mesmo. Isso
facilita ao modelo traduzir a pergunta para a ferramenta, e é uma escolha
deliberada. As descrições não trazem regras feitas para uma pergunta, nem
sugestões de filtros ou pesos para um caso concreto.

### A súmula do `stats_in_prompt` vem do Neo4j

Não de um cálculo à parte. Assim o `stats_in_prompt` e o `graph_tools` partem
do mesmo banco: a súmula é contada pelo Neo4j sobre as mesmas arestas que as
ferramentas consultam.

### A mesma informação de eventos nos três braços que veem eventos

`events_in_prompt`, `vector` e o `list_actions` do `graph_tools` mostram os
mesmos fatos de cada ação: período, minuto, time, jogador, ação, sucesso,
recebedor, zonas, posse, desfecho e placar. O placar aparece de dois jeitos:
**antes** da ação, em toda linha, e **depois**, na linha de um gol. O primeiro
serve para recortes ("enquanto vencia por 2 a 0"); o segundo, para achar um
gol pelo placar que ele fez ("o gol do 2 a 2"). Nenhum dos três recebe
contagens prontas.

### O braço `vector` indexa as mesmas linhas

Cada linha da tabela de eventos é um documento. Assim o `vector` e o
`events_in_prompt` veem **o mesmo material**, e a diferença entre eles é só
"30 linhas escolhidas" contra "todas as linhas". Os embeddings são calculados
em lotes de 100 (cerca de 26 pedidos) e guardados em cache.

### Cache de prompt nos braços com dados fixos

O `events_in_prompt` envia a mesma tabela de ~100 mil tokens em todas as
perguntas, e o `stats_in_prompt` a mesma súmula. Com cache de prompt, o
provedor guarda esse trecho na primeira pergunta e cobra as seguintes por uma
fração do preço (no Claude Haiku 5.5, leitura a 10% do preço de entrada). Na
amostra sem cache, o `events_in_prompt` sozinho custou ~95% do total.

Para funcionar, a mensagem desses dois braços vai em **dois blocos de texto**:
os dados, com a marcação de cache, e a pergunta. O cache só reaproveita um
começo idêntico, e a pergunta muda a cada vez. **O modelo lê exatamente o
mesmo texto**; muda só a cobrança. Por isso o projeto usa a classe
`OpenRouterModel` do PydanticAI, a única que repassa essa marcação a modelos
Anthropic pelo OpenRouter. Modelos sem esse tipo de cache simplesmente a
ignoram. O `results.jsonl` registra os tokens lidos e gravados no cache
(`cache_read_tokens`, `cache_write_tokens`).

Verificado com o Claude Haiku 5.5: a segunda pergunta do `stats_in_prompt`
leu 4.921 de 4.966 tokens do cache e custou metade.

### Erros do provedor não viram resultado

Se o provedor do modelo falhar (servidor fora, limite de uso), depois das
novas tentativas do próprio SDK, a execução é avisada e **não é gravada**, e o
`--resume` a refaz. Uma falha de infraestrutura não é uma resposta errada do
braço. Já uma resposta fora do formato, mesmo após 2 novas tentativas, é
gravada como erro de formato, porque é um comportamento do modelo.

### O script não apaga resultados pagos sem pedir

Se o arquivo de resultados já tem execuções, `run_benchmark.py` se recusa a
começar e pede `--resume` (continuar) ou `--fresh` (recomeçar). Resultados
custam dinheiro; apagá-los deve ser uma decisão explícita.

---

## 7.2 Problemas encontrados nos dados

Montar o gabarito por um caminho independente serve para encontrar
divergências entre as fontes. Os casos abaixo são conhecidos e contornados
nas perguntas ou na apresentação dos dados.

### Defesas do goleiro: 7 ou 8?

O JSON bruto tem 7 defesas de Hugo Lloris (eventos "Shot Saved"). A camada 0
tem 8 ações de defesa. A oitava, no minuto 107, é na verdade uma saída do
goleiro para afastar a bola ("Keeper Sweeper Clear"), que a conversão para
SPADL classificou como defesa. A súmula do grafo herda o 8.

**O que foi feito:** nenhuma pergunta usa defesas do goleiro. **O que deveria
ser feito numa próxima etapa:** corrigir a classificação na camada 0.

### Passes tentados

A conversão para SPADL descarta alguns passes do JSON: Enzo Fernandez tem 94
passes tentados no JSON e 92 na camada 0; Koundé, 67 e 66. Passes **certos**
batem nas duas fontes.

**Como é tratado:** nenhuma pergunta depende de passes tentados ou errados;
as perguntas sobre passes usam passes certos.

### O cartão recuperado no fim da tabela

O amarelo de Giroud (95', por reclamação) não é uma ação com bola, então o
SPADL o descarta. A camada 0 o recupera do JSON bruto, mas o acrescenta **no
fim da tabela**, com o último número de ação. Quem lesse a tabela pela ordem
das ações veria o cartão depois do último lance da prorrogação.

**Como é tratado:** a tabela de eventos dos braços e o `list_actions` ordenam
por período e tempo de jogo, não pelo número da ação. Um teste garante isso.

### O banco pode ter outras partidas

Se o Neo4j já foi usado com outras partidas (versões anteriores do projeto
carregavam três), os nós delas continuam lá. Toda consulta do benchmark
filtra pela partida (`match_id`), então isso não afeta os resultados. Para
um banco limpo: `docker compose down -v` e rodar as camadas de novo.

---

## 7.3 Limitações: o que o benchmark não diz

**Uma partida, 52 perguntas.** São 47 com resposta e 5 de controle. Uma
pergunta vale ~2 pontos percentuais no total, mas de 5 a 17 pontos dentro de
um grupo (o menor tem 6 perguntas). Os intervalos de confiança são largos
(cerca de ±12 pontos), e diferenças de poucas perguntas entre braços podem ser
acaso das perguntas escolhidas.

**Variação entre execuções.** Com temperatura 0, a mesma pergunta ainda pode
ter respostas diferentes em execuções diferentes. Com uma repetição, a
tabela de consistência fica vazia e essa variação não é medida.

**Mede correção, não qualidade.** O benchmark diz se o braço acertou o nome
ou o número. Não diz se ele explicaria bem uma jogada, nem se o raciocínio
(`rationale`) faz sentido.

**Ferramentas e perguntas da mesma autoria.** As ferramentas foram fixadas
antes das perguntas, mas foram desenhadas por quem escreveu as perguntas.
Ajustes posteriores de apresentação (placar nos eventos, resultados das
ferramentas de rede que repetem os filtros, contagem de jogadores nas
sequências) foram feitos depois de ver erros do modelo em parte das
perguntas. Num uso real, ninguém garante que a ferramenta certa exista.

**Descrições que ajudam.** As descrições das ferramentas trazem a leitura
tática de cada métrica (7.1). Isso aproxima a pergunta da ferramenta.

**Perguntas que saíram.** 22 de 81 perguntas escritas saíram porque a
resposta mudava com a leitura. Entre elas está o "principal elo da circulação de
bola" na partida inteira, um conceito comum em análise de futebol que, nesta
final, não tem resposta única.

**O `graph_tools` mistura dois efeitos:** ter ferramentas que calculam e ter
algoritmos de grafo. Separá-los exige um braço com só as ferramentas de
ações (`list_players`, `query_actions`, `list_actions`), sem as de rede.
Esse braço é uma linha de configuração (`TOOL_ARMS` em `arms.py`) e fica como
trabalho futuro.

**O `events_in_prompt` depende de uma partida caber no contexto.** A tabela
tem de ~78 mil a ~115 mil tokens, conforme o modelo (240 mil no DeepSeek). Uma rodada de Copa ou um campeonato não cabe, e o braço
deixaria de existir; as ferramentas continuariam funcionando.

**Quatro modelos, não uma curva de escala.** Com dois modelos baratos e dois
caros, o benchmark mostra que a ordem dos braços muda com o modelo (7.1), mas
não diz em que ponto ela muda. Nos dois caros, tamanho e raciocínio vêm
juntos, e não há como separar um do outro com esses dados. A escolha dos
modelos dependeu do que a conta do autor podia usar (Opus e GPT não estavam
liberados). O modelo usado fica registrado em cada linha do arquivo de
resultados.

**Condições diferentes no `events_in_prompt` do Sonnet 4.6.** Esse braço usa
esforço de raciocínio `low` e, em 6 perguntas, teto de 32 mil tokens; os
outros braços do mesmo modelo usam `medium` e 16 mil (7.1). A comparação
entre braços do Sonnet carrega essa diferença.

**Uma correção de ferramenta posterior à rodada do Haiku.** A leitura de
argumentos enviados como texto JSON (capítulo 4) entrou depois da rodada do
Haiku. O Haiku nunca enviou argumento assim, então a correção não deveria
mudar os números dele, mas a rodada não foi refeita para provar.

**Conferência por conjunto.** Nas sequências de três jogadores, a ordem não é
conferida. Na pergunta que compara o 1º e o 2º tempo, só a dupla do 2º tempo
é conferida.

**O gabarito de rede depende da camada 0.** Redes e xT vêm da camada 0, cujo
modelo de xT foi treinado com jogos que incluem a final. O gabarito e o grafo
partem do mesmo Parquet, então a conferência cruzada valida as camadas 1 e
2 e as ferramentas, **não a 0**. Por isso a camada 0 tem testes próprios
contra o JSON bruto.

**Escolhas fixas do `vector`.** 30 linhas e um modelo de embedding. Outro
número de linhas ou outro modelo daria outro resultado; não foram testadas
variações.

**Instruções em inglês, perguntas em português.** É comum na prática e vale
para todos os braços igualmente, mas é uma variável que não foi isolada.

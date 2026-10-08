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
comparar cinco formas de entregar dados a um modelo, de forma verificável.

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

Mesmo modelo, mesma instrução, temperatura 0, mesmo formato de resposta com o
mesmo número de novas tentativas. O formato é entregue sempre pelo mesmo
mecanismo do PydanticAI (a resposta vem como uma "ferramenta de saída"),
porque ele funciona junto com as ferramentas do `graph_tools`. Usar um
mecanismo diferente em algum braço seria mais uma diferença além dos dados.

A instrução de sistema diz que as perguntas são sobre **uma partida**, sem
dizer qual. Dizer "a final da Copa de 2022" ajudaria o modelo a responder de
memória em vez de usar os dados.

### Perguntas sem definição, testadas em todas as leituras

As perguntas descrevem os conceitos como um comentarista ("o principal elo
da circulação de bola", "a dupla que mais trocou passes"), sem dizer como
calcular. Um teste impede vocabulário de ferramenta ou de algoritmo. O preço
é que a mesma pergunta pode ser lida de mais de um jeito. Em vez de
acrescentar definição ao texto, o gabarito calcula a resposta em todas as
leituras razoáveis e a pergunta só fica se todas concordam (capítulo 3,
seção 3.5).

### Ferramentas primitivas, fixadas antes das perguntas

As sete ferramentas do `graph_tools` são operações sem conceito tático
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

**Uma partida, 25 perguntas.** Cada tipo tem 5 perguntas, então uma pergunta
vale 20 pontos percentuais dentro do tipo. Diferenças de uma ou duas
perguntas entre braços podem ser acaso das perguntas escolhidas.

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

**Perguntas que saíram.** 9 de 40 perguntas escritas saíram porque a resposta
mudava com a leitura. Entre elas está o "principal elo da circulação de
bola" na partida inteira, um conceito comum em análise de futebol que, nesta
final, não tem resposta única.

**O `graph_tools` mistura dois efeitos:** ter ferramentas que calculam e ter
algoritmos de grafo. Separá-los exige um braço com só as ferramentas de
ações (`list_players`, `query_actions`, `list_actions`), sem as de rede.
Esse braço é uma linha de configuração (`TOOL_ARMS` em `arms.py`) e fica como
trabalho futuro.

**O `events_in_prompt` depende de uma partida caber no contexto.** A tabela
tem ~111 mil tokens. Uma rodada de Copa ou um campeonato não cabe, e o braço
deixaria de existir; as ferramentas continuariam funcionando.

**Um único modelo.** O resultado vale para o modelo do `.env` no dia da
execução. Outro modelo pode inverter a ordem dos braços. O modelo usado fica
registrado em cada linha do arquivo de resultados.

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

# 7. Decisões, problemas encontrados e limitações

Este capítulo reúne o "porquê" do projeto: as escolhas que moldaram o
benchmark, os problemas encontrados nos dados (e o que foi feito com eles) e
o que o benchmark **não** consegue dizer. Leia antes de tirar conclusões dos
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

### As perguntas falam futebol

Uma versão anterior das perguntas usava o vocabulário das ferramentas
("betweenness centrality... ponderada pelo xT"), o que dava ao `graph_tools`
um atalho: a pergunta apontava a ferramenta. Agora elas descrevem os
conceitos em linguagem de futebol, e um teste impede o jargão de voltar. Para
isso não criar ambiguidade, mediu-se antes se a resposta muda conforme a
leitura do conceito, e o que mudava saiu (capítulo 3, seção 3.5).

### `ligacao_fragil` fora das perguntas

A camada 2 tem um padrão chamado `ligacao_fragil`: a ligação da rede de passes
que, cortada, separaria o time em dois blocos. Na final, **nenhuma das duas
redes tem uma ponte** (uma ligação cuja remoção desconecta a rede), então o
padrão usa um plano B: agrupa os jogadores em comunidades com o algoritmo
**Louvain** e procura o par que concentra o fluxo entre os grupos. O
problema é que o Louvain tem um componente aleatório: rodando com sementes
diferentes (0 a 4), as comunidades mudaram de uma vez para outra. Um gabarito
que depende de sorte não é gabarito. As perguntas estruturais usam só os
dois padrões estáveis: o elo de ligação (betweenness) e as combinações de
três jogadores. A ferramenta `pass_network_bridges` continua à disposição do
modelo.

### A súmula do `stats_in_prompt` vem do Neo4j

Não de um cálculo à parte. Assim o `stats_in_prompt` e o `graph_tools` partem
dos mesmos números, e a comparação entre os dois isola uma única coisa: ter
ou não ter ferramentas. Pelo mesmo motivo, o glossário dos campos é o mesmo
nos dois braços.

### A tabela de eventos tem três colunas a mais que o plano original

`period`, `possession` e `outcome` (capítulo 4, seção 4.3). Sem elas, o braço
não teria fatos que as perguntas exigem (quem fez gol, quem levou cartão, se
dois passes foram na mesma posse) ou leria o minuto de forma ambígua. A
tabela continua sem nenhum valor agregado.

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

### Ferramentas com consultas fixas

O modelo escolhe ferramentas, mas não escreve consultas ao banco. Deixar o
modelo escrever Cypher misturaria duas habilidades (saber consultar um banco
e saber usar os dados), e a primeira não é o que se quer medir. As
ferramentas são genéricas e nenhuma lê os padrões prontos da camada 2.

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

Montar o gabarito por um caminho independente serviu para o que foi pensado:
encontrar divergências. A regra do projeto nesta etapa é **não alterar as
camadas 0 a 2**, então os problemas abaixo foram registrados e contornados,
não corrigidos nas camadas.

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

**O que foi feito:** as perguntas usam passes certos. "Passes errados" aparece
uma vez (c01, Otamendi), num jogador em que as duas fontes concordam (6).

### O cartão recuperado no fim da tabela

O amarelo de Giroud (95', por reclamação) não é uma ação com bola, então o
SPADL o descarta. A camada 0 o recupera do JSON bruto, mas o acrescenta **no
fim da tabela**, com o último número de ação. Quem lesse a tabela pela ordem
das ações veria o cartão depois do último lance da prorrogação.

**O que foi feito:** a tabela de eventos dos braços é ordenada por período e
tempo de jogo, não pelo número da ação. Um teste garante isso.

### O banco pode ter outras partidas

Se o Neo4j já foi usado com outras partidas (versões anteriores do projeto
carregavam três), os nós delas continuam lá. Toda consulta do benchmark
filtra pela partida (`match_id`), então isso não afeta os resultados. Para
um banco limpo: `docker compose down -v` e rodar as camadas de novo.

---

## 7.3 Limitações: o que o benchmark não diz

**Uma partida, 30 perguntas.** Cada tipo tem 6 perguntas. Dentro de um tipo,
uma pergunta a mais ou a menos muda o acerto em ~17 pontos percentuais.
Diferenças pequenas entre braços podem ser acaso das perguntas escolhidas,
não superioridade real.

**Mede correção, não qualidade.** O benchmark diz se o braço acertou o nome
ou o número. Não diz se ele explicaria bem uma jogada, nem se o raciocínio
(`rationale`) faz sentido.

**O gabarito estrutural depende da camada 0.** A rede de passes usa o xT, que
vem de um modelo treinado pela própria pipeline, com jogos que incluem a
final. O gabarito e o grafo partem do mesmo Parquet, então a conferência
cruzada valida as camadas 1 e 2, **não a 0**. Um erro na camada 0 passaria
igual pelos dois lados (como o das defesas do goleiro, que só foi achado
porque essa pergunta usaria o JSON bruto).

**As ferramentas foram desenhadas por quem escreveu as perguntas.** Elas são
genéricas, mas `pass_network_centrality` e `three_player_sequences` existem
porque há perguntas estruturais. Num uso real, ninguém garante que a
ferramenta certa exista. O resultado do `graph_tools` é, portanto, um teto
otimista para "LLM com ferramentas de grafo".

**As perguntas explicam os conceitos.** Mesmo em linguagem de futebol, as
perguntas estruturais dizem o que querem ("por quem passavam mais rotas de
passe"). Uma pergunta espontânea seria mais vaga. A regra das combinações de
três jogadores coincide, por necessidade, com a descrição da ferramenta,
porque "combinação de três" não tem definição única no futebol.

**Um único modelo.** O resultado vale para o modelo do `.env` no dia da
execução. Outro modelo pode inverter a ordem dos braços. O modelo usado fica
registrado em cada linha do `results.jsonl`.

**Temperatura 0 não garante repetição.** Provedores podem dar respostas
diferentes para o mesmo pedido. A tabela de consistência mede isso, mas não
corrige.

**Escolhas fixas do `vector`.** 30 linhas e um modelo de embedding: outro
número de linhas ou outro modelo daria outro resultado. Não foram testadas
variações.

**Instruções em inglês, perguntas em português.** É comum na prática e vale
para todos os braços igualmente, mas é uma variável que não foi isolada.

**Tokens aproximados na documentação.** Os tamanhos citados nos capítulos usam
um tokenizador genérico. Os números do `summary.md` vêm do provedor e são os
que valem.

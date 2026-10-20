# Roteiro de fala, slides 1 a 15

Tempo estimado: cerca de 19 minutos (Daniel nos slides 1 a 7, cerca de 9 min; João Victor nos slides 8 a 15,
cerca de 10 min). `[pausa]` marca uma respiração de 1 a 2 segundos.

---

## Slide 1 · Capa (≈ 0:20)

Boa noite a todos. Eu sou o Daniel, e esse é o João Victor. A gente vai apresentar o nosso trabalho, que compara seis
formas de entregar os dados de uma partida de futebol pra um modelo de linguagem responder perguntas sobre ela.

---

## Slide 2 · Pergunta de pesquisa (≈ 1:30)

Hoje, um modelo de linguagem consegue responder perguntas em linguagem natural, mas pra falar de uma partida
específica ele precisa receber os dados dela. E pergunta de análise de futebol quase nunca tem a resposta num lance
só. Por exemplo, qual dupla da França mais trocou passes, ou, depois que o Dembélé saiu, quem mais passou a bola pro
Mbappé. Pra responder isso, você precisa ligar vários eventos entre si.

[pausa] Então a nossa pergunta foi qual é a melhor forma de levar esses dados até o modelo. A gente quis saber qual
abordagem acerta mais, se isso muda de um modelo pra outro e quanto cada uma custa em tokens e em tempo.

E o trabalho entrega três coisas. Uma transformação dos eventos da partida numa tabela de ações e num grafo, um
conjunto de 52 perguntas com gabarito, e a comparação de seis abordagens em quatro modelos, todas com as mesmas
perguntas, o mesmo prompt e o mesmo formato de resposta.

---

## Slide 3 · Trabalhos relacionados (≈ 1:10)

Antes de entrar nos dados, rapidinho sobre os trabalhos relacionados. Essa tabela resume o que a gente encontrou. No
esporte, tem conjuntos que só testam o que o modelo já sabe, com múltipla escolha, como o SportQA. E tem sistemas que
ligam o modelo a dados de partidas, como o SoccerRAG e o SPORTSQL, que escrevem SQL, e o trabalho do Tzikas, que usa
busca vetorial sobre eventos. Só que cada um testa uma forma de recuperação por vez.

Fora do esporte, trabalhos como o LOFT e o do Li comparam contexto longo com recuperação, mas sem dados de futebol.

[pausa] Então a lacuna que a gente viu é essa última linha. Comparar várias formas de recuperação, com as mesmas
perguntas, em eventos de futebol, e com a correção feita por código, sem um LLM dando nota.

---

## Slide 4 · Os dados em JSON (≈ 1:20)

Os dados são da StatsBomb, que publica de graça os eventos de várias partidas. A gente usou a final da Copa de 2022,
Argentina e França. São dois arquivos, a lista de eventos em ordem e as escalações.

O JSON bruto tem mais de 4.400 eventos, e cada evento tem o tipo, o tempo, o time, o jogador e a posição no campo.
Esse exemplo aqui é o passe do Mac Allister e o gol do Di María, logo em seguida.

E esse formato tem algumas armadilhas. Cada tipo de evento tem campos próprios, então o passe traz o recebedor e o
chute traz o resultado. A mesma informação pode estar em lugares diferentes, como o cartão amarelo, que às vezes vem
dentro da falta e às vezes num evento separado. E o nome é o de registro, não o apelido, e o minuto conta o tempo
decorrido. Então esse gol, que aparece no minuto 35 do JSON, na transmissão foi aos 36.

---

## Slide 5 · Do JSON à tabela de ações (≈ 1:30)

Por isso, o primeiro passo foi transformar esses eventos numa tabela. A gente usou a biblioteca socceraction, que
converte os eventos pro formato SPADL. Esse formato guarda só as ações com bola, num vocabulário fechado, e todas com
os mesmos campos. Os eventos viraram 2.585 ações.

Em cima disso, a gente acrescentou colunas de contexto. Todas as ações passam a atacar da esquerda pra direita, pros
dois times. Cada ação ganha a zona do campo onde começou e onde terminou. O passe ganha o recebedor, que é o jogador
do mesmo time que age em seguida. As ações são agrupadas em fases de posse, que é como a gente identifica as jogadas.
E cada linha tem o placar e o minuto da transmissão. Além disso, a gente recuperou do JSON o que o SPADL perde, como o
desfecho do chute e o cartão sem falta.

[pausa] Esse campo do lado mostra a grade de zonas, e o passe do Mac Allister pro Di María sai de uma zona e termina
na outra, já perto do gol. E é essa tabela, inteira, que a abordagem de contexto longo entrega pro modelo.

---

## Slide 6 · Da tabela ao grafo (≈ 1:20)

Depois, essa tabela foi carregada num grafo, no Neo4j. Cada ação vira uma ligação do jogador pra partida, com as
colunas da tabela, e cada passe certo com recebedor vira uma ligação de um jogador pro outro. Os outros nós são os
times, as fases de posse e as zonas do campo.

Essas ligações não acrescentam informação, elas só reorganizam a tabela. A única coisa calculada é a súmula, que o
próprio banco conta, com os totais de cada jogador e de cada time, separando o que foi tentado e o que deu certo.

[pausa] E por que um grafo? Porque a análise de futebol já trata os passes de um time como uma rede, com os
jogadores ligados pelos passes. Então perguntas como qual dupla mais trocou passes, ou por qual jogador a bola mais
circula, viram caminhos e métricas nesse grafo.

---

## Slide 7 · Perguntas e gabarito (≈ 1:20)

Com os dados prontos, a gente escreveu as perguntas. São 52, divididas em cinco grupos. Busca e contagem são as mais
diretas, como quem recebeu o primeiro cartão amarelo. Relações na rede de passes, jogadas e sequências, e antes e
depois de uma substituição são as encadeadas, em que você precisa ligar um evento ao outro.

E tem o grupo de controle, com perguntas que não têm resposta nesses dados, como a distância que o De Paul percorreu.
Aí a resposta certa é o modelo dizer que não tem a informação.

[pausa] O gabarito de cada pergunta foi calculado por código, a partir do JSON e da tabela de ações, e as perguntas
que davam margem pra mais de uma leitura saíram do conjunto. A correção também é por código, então a mesma resposta
sempre recebe a mesma nota.

Agora o João Victor vai mostrar as seis abordagens que a gente comparou e os resultados.

---

## Slide 8 · Seis abordagens (≈ 1:30)

Valeu, Daniel. Boa noite, pessoal, eu vou continuar a partir daqui.

Então, com os dados e as perguntas prontas, a gente comparou seis jeitos de entregar esses dados pro modelo. Ou seja, a
gente está usando aprendizado em contexto, alimentando o modelo com os dados na hora da pergunta, sem treinar ele de
novo.

A primeira é sem dados, então só a pergunta vai pro modelo. É a nossa linha de base.

A segunda é o contexto longo, em que a tabela inteira de ações vai direto no prompt.

A terceira são as estatísticas resumidas, em que vai só a súmula, com os totais por jogador e por time.

A quarta é a busca vetorial, o RAG tradicional. As linhas da tabela e a pergunta viram embeddings, que são vetores que
representam o texto, e uma busca por similaridade manda pro prompt só as linhas mais parecidas com a pergunta.

E as duas em azul são agentes que consultam o grafo. Isso quer dizer que o modelo não responde de uma vez. Ele chama
uma ferramenta, vê o resultado e decide se chama de novo ou se já responde. Na consulta escrita pelo modelo, ele
escreve a consulta sozinho, em Cypher. Nas ferramentas sobre o grafo, ele só escolhe uma ferramenta pronta e passa os
argumentos.

Em cada modelo, as seis abordagens usam o mesmo prompt e o mesmo formato de resposta, então a única coisa que muda é a forma
como os dados chegam até a janela de contexto do LLM.

---

## Slide 9 · Mesmo grafo, duas formas de consultar (≈ 1:00)

Aqui tem um exemplo real desses dois agentes. A pergunta é quem deu mais passes certos no terço final pela Argentina.

Nos dois casos o modelo chama uma ferramenta, mas o que ele passa pra ela é bem diferente. Na esquerda, o parâmetro
da ferramenta é a própria consulta em Cypher, escrita pelo modelo, com todos os filtros dentro, time, passe certo e
terço de ataque. Na direita, o modelo não escreve consulta nenhuma. Ele passa só os argumentos, como o time, o tipo de
ação e o terço do campo, e esses argumentos preenchem uma consulta parametrizada que já está implementada dentro da
ferramenta. No fim, os dois chegaram no Messi.

Essa ferramenta da direita, que conta ações, é uma das 8 ferramentas, e as outras seguem a mesma ideia, contando ou listando ações e trabalhando com a rede
de passes.

[pausa] Então os dois agentes usam o mesmo grafo, e o que muda é quem escreve a consulta, se é o próprio modelo ou a
implementação dentro da ferramenta.

---

## Slide 10 · Resultado principal (≈ 1:55)

Agora os resultados. A gente testou em quatro modelos, em dois grupos. Os menores são o Claude Haiku 5.5 e o
Qwen3.8-flash, e os maiores, o Claude Sonnet 4.6 e o Kimi K3. Em cada grupo tem um modelo proprietário e um de pesos
abertos, então o Haiku e o Sonnet, da Anthropic, representando os fechados, e o Qwen e o Kimi, os de pesos abertos. Os maiores
rodaram com o raciocínio estendido ligado.

O que está em azul é a abordagem com ferramentas, e ela ficou entre 83 e 89% em todos os modelos, então o tamanho do
modelo quase não fez diferença nessa abordagem.

A consulta escrita pelo modelo fica bem abaixo nos menores e sobe até empatar com as ferramentas nos maiores. O
contexto longo faz o mesmo caminho, só que sempre um degrau abaixo. E isso já aparece na literatura, porque trabalhar
com um contexto muito longo exige um modelo maior, e escrever código também, seja uma consulta em Cypher, em SQL ou até, sei lá, em Python.

As outras três acertaram pouco em todos, e eu já explico por quê.

[pausa] Só um cuidado. Esses risquinhos são o intervalo de confiança, e como foi uma repetição só, eles são largos.
Então nos modelos maiores a gente não consegue separar a consulta das ferramentas, e por isso a gente lê essas
diferenças como indício, e não como prova.

---

## Slide 11 · Perguntas encadeadas (≈ 1:25)

Esse gráfico não está no artigo, a gente trouxe só pra ilustrar. São só as perguntas encadeadas, em que você precisa
ligar um evento ao outro, tipo quem passou pra quem ou o que mudou depois de uma substituição.

É aqui que a diferença aparece, tá. Nos modelos menores, o contexto longo e a consulta caem bastante, e a abordagem com
ferramentas segura. Nos maiores, as três ficam bem mais próximas.

E dá pra entender o porquê olhando o que cada uma exige do modelo. Nas ferramentas, quem faz o trabalho pesado é a
implementação dentro da ferramenta, que conta os passes ou percorre a jogada, e o modelo só escolhe a ferramenta certa, com os parâmetros certos.

Já na consulta, o modelo menor erra ao escrever o Cypher e precisa de várias tentativas até chegar numa consulta que
funciona. E no contexto longo, ele tem que achar e juntar eventos espalhados pela tabela inteira, que é justamente o
que um modelo menor faz pior.

[pausa] Mas isso tem uma contrapartida, porque a abordagem com ferramentas acaba sendo mais restritiva. O que eu quero dizer com isso é
que, no contexto longo, a gente tá dando ao modelo todos os dados que ele precisa pra responder. Na consulta, a gente
dá a liberdade pro modelo navegar pelos dados usando a linguagem Cypher. Já nas ferramentas, o modelo só vai recuperar, e consequentemente só vai responder, aquilo que as ferramentas permitem que ele recupere.

---

## Slide 12 · As três que acertaram pouco (≈ 1:15)

Voltando nas três que foram mal.

A busca vetorial traz as 30 linhas mais parecidas com a pergunta, mas parecer não é o mesmo que ser útil pra responder. Pra contar ou
ligar eventos, você vai acabar precisando de mais do que isso. Numa pergunta sobre a Argentina sem o Enzo Fernández, por exemplo,
ela trouxe justamente as ações do Enzo.

E muitas vezes essas linhas pareciam suficientes, então o modelo respondia errado em vez de dizer que não tinha os
dados. E dizer que não tem os dados, ou seja, a abstenção, já conta como um erro, né, porque a gente está avaliando num conjunto em que sabe que toda pergunta tem
resposta. Mas responder errado com cara de certo pode ser pior.

A abordagem com estatísticas só tem o total do jogo, sem tempo, sem lugar do campo e sem quem passou pra quem, então o modelo dizia que não tinha os dados. É um resultado esperado.

E o sem dados zerou porque o prompt proíbe responder de memória. Ou seja, os LLMs que a gente avaliou obedeceram a
instrução, o que já é comum nos modelos atuais.

---

## Slide 13 · Custo (≈ 1:00)

No custo, vamos olhar aqui só as abordagens que mais acertaram. O que pesa é o contexto longo nos modelos maiores, que gera
milhares de tokens de raciocínio. No Kimi, ele levou 81 segundos por pergunta, e esse valor é a mediana, contra 15 da abordagem com
ferramentas. Então ele chega perto no acerto, mas paga bem mais caro em tempo e em tokens.

Mas cada uma tem vantagens e desvantagens. O contexto longo acaba sendo mais barato em termos de implementação, porque não precisa de banco de grafos nem de um agente chamando ferramenta, mas ele tem o custo do modelo.

---

## Slide 14 · Conclusão e limitações (≈ 1:20)

Pra concluir, a abordagem com ferramentas sobre o grafo foi a única com acerto alto em todos os modelos, entre 83 e
89%. A consulta e o contexto longo dependem da capacidade do modelo, e o contexto longo ainda custa mais.

E as limitações. É uma partida só, com uma repetição, então os intervalos são largos. Nos modelos maiores, tamanho e
raciocínio vieram juntos. As ferramentas e as perguntas foram feitas por nós, então o resultado vale pro que as
ferramentas cobrem.

E a gente não separou o efeito do grafo do efeito de agentes com ferramentas. A nossa hipótese é
que, num banco relacional com as mesmas ferramentas, as perguntas de contagem iriam bem, e a diferença ia aparecer nas
perguntas de relação entre jogadores, que são mais complicadas de modelar num banco relacional. Seguir uma cadeia de
passes ali exigiria um JOIN pra cada passe, então provavelmente não é a ferramenta ideal pra isso.

---

## Slide 15 · Próximos passos e perguntas (≈ 1:25)

Como próximos passos, a gente quer ter mais evidência, com mais repetições e mais partidas. Quer separar os efeitos,
testando modelos grandes sem raciocínio e as mesmas ferramentas num banco SQL, sem grafo. E quer levar isso pra outros
domínios, como processos industriais. Numa linha de produção, por exemplo, cada parada de máquina, cada alerta e cada
movimentação de peça é um evento, com quem fez, quando e onde, e muitas vezes um evento puxa o outro, do mesmo jeito que, sei lá, um passe puxa uma finalização. Dá pra testar as mesmas abordagens nesses dados, montando a tabela, o grafo e as
ferramentas pras perguntas daquele contexto.

[pausa] Então, resumindo, não existe uma abordagem que seja a melhor pra tudo. A escolha depende do orçamento, da latência
e do acerto que se precisa. Com modelo pequeno, a abordagem com ferramentas segura o acerto. Com modelo grande, a
consulta escrita pelo modelo chega no mesmo nível e é mais flexível. E o contexto longo funciona, é mais fácil de
implementar e de manter, mas custa caro.

[pausa] Era isso. O código está nesse repositório. Muito obrigado, e a gente fica aberto pras perguntas.

---

## Cola para as perguntas (não é fala)

| O quê | Valor |
|---|---|
| Ferramentas sobre o grafo | 83% a 89% (87, 83, 89, 89) |
| Consulta escrita pelo modelo | 57% a 70% nos menores; 89% a 94% nos maiores |
| Contexto longo | 40% a 45% nos menores; 72% a 85% nos maiores |
| Busca vetorial | 9% a 17% de acerto; resposta errada em 19% a 42% das execuções |
| Estatísticas resumidas | 0% a 9% |
| Sem dados | 0 de 47 (se abstém) |
| Latência do Contexto longo | 37 s no Sonnet, 81 s no Kimi |
| Latência das Ferramentas | 10 s no Sonnet, 15 s no Kimi |
| Tokens de saída do Contexto longo | 4,4 mil no Sonnet, 12,2 mil no Kimi |
| Ressalva do custo | Ferramentas sem cache de prompt; Contexto longo com a maior parte da entrada em cache |
| Modelos | Haiku 5.5 e Sonnet 4.6 (fechados); Qwen3.8-flash e Kimi K3 (pesos abertos) |
| Perguntas | 52 (47 com resposta, 5 de controle); 36 encadeadas |

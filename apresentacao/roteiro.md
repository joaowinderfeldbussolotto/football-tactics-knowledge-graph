# Roteiro de fala, slides 8 a 15

Tempo estimado: cerca de 10 minutos. `[pausa]` marca uma respiração de 1 a 2 segundos.

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

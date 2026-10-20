# Perguntas prováveis da banca (20 min de perguntas)

A **Parte 1** traz respostas para falar, por slide: curtas, simples, com uma explicação e um exemplo. A **Parte 2**
é a reserva técnica, com os números e as fontes, para quando a banca apertar. Ordem dos modelos nas listas de quatro
números: Haiku 5.5, Qwen3.8-flash, Sonnet 4.6, Kimi K3. Código, perguntas, gabarito e resultados por modelo estão no
repositório novo, `match-events-qa-benchmark`.

---

# Parte 1 · Respostas para falar, por slide

## Slide 2 · Problema e perguntas de pesquisa

**"Por que aprendizado em contexto, e não treinar o modelo com os dados?"**

> Porque cada partida é um conjunto novo de dados. Treinar ou ajustar o modelo pra cada jogo seria caro e não faria
> sentido, já que a ideia é perguntar sobre a partida na hora. No aprendizado em contexto o modelo continua o mesmo, e
> a gente só entrega os dados junto com a pergunta. É como entregar a súmula pra um analista na hora, em vez de pedir
> pra ele decorar o jogo.

**"Por que só uma partida?"**

> Por dois motivos. Primeiro, a tabela inteira de uma partida cabe no contexto do modelo, o que era necessário pra
> testar o contexto longo. Segundo, com uma partida dava pra conferir o gabarito de cada pergunta com cuidado. Usar
> mais partidas é um dos próximos passos.

## Slide 3 · Trabalhos relacionados

**"O que vocês fazem que os outros não fazem?"**

> Os trabalhos de futebol que a gente encontrou testam uma forma de recuperação por vez. O SoccerRAG e o SPORTSQL,
> por exemplo, só testam o modelo escrevendo SQL, e o Tzikas só testa busca vetorial. A gente pegou as mesmas
> perguntas e comparou seis formas lado a lado, em quatro modelos, com a correção feita por código, sem um LLM dando
> nota.

**"O Tzikas teve acerto bem maior com busca vetorial. Por quê?"**

> Porque o desenho é outro. Lá, cada trecho já traz os eventos seguintes, tipo o passe junto com o chute que veio
> depois, a busca traz até cem trechos e reordena, e quem corrige é um LLM. Aqui, cada linha é uma ação isolada, e vão
> trinta linhas. Testar a busca com os eventos vizinhos está nos próximos passos.

## Slide 4 · Os dados em JSON

**"A final é famosa. O modelo não responde de memória?"**

> Esse foi um cuidado que a gente teve. O prompt não diz qual é a partida e proíbe responder de memória, e a
> abordagem sem dados mostra que os modelos obedeceram, porque ela zerou nas perguntas com resposta. Isso não prova que
> o modelo não conhece a final, mas mostra que ele seguiu a instrução. E muitas respostas dependem de definições nossas,
> como quem é o recebedor de um passe ou em que zona do campo a ação aconteceu, que não existem fora desses dados.

**"Por que dados da StatsBomb?"**

> Porque são dados abertos e cada evento já vem com jogador, momento e posição no campo. Qualquer pessoa consegue
> baixar e reproduzir o trabalho.

## Slide 5 · Do JSON à tabela de ações

**"O que é o SPADL e por que converter?"**

> O SPADL é um formato padrão pra ações de futebol. No JSON bruto, cada tipo de evento tem campos diferentes, e às
> vezes a mesma informação aparece em dois lugares, como o cartão amarelo, que pode vir dentro da falta ou num evento
> separado. O SPADL deixa todas as ações com os mesmos campos, quem fez, quando, onde começou, onde terminou e se deu
> certo. Aí fica muito mais fácil contar e comparar.

**"Como vocês sabem quem recebeu o passe?"**

> A gente define o recebedor como o jogador do mesmo time que faz a ação seguinte. Então, se o Mac Allister passa e a
> próxima ação é do Di María, o Di María é o recebedor. Se a próxima ação é do adversário, o passe fica sem recebedor.

**"O que é uma fase de posse?"**

> É uma sequência de ações seguidas do mesmo time. Ela termina quando a bola muda de time, quando muda o período ou
> quando acontece algo que encerra a jogada, como uma falta, uma finalização ou uma defesa do goleiro. É assim que a
> gente identifica as jogadas.

## Slide 6 · Da tabela ao grafo

**"Por que um grafo?"**

> Porque no futebol os passes já são analisados como uma rede, com os jogadores ligados pelos passes. Então perguntas
> como qual dupla mais trocou passes ou por quem a bola mais circula viram operações diretas no grafo, como seguir um
> caminho ou calcular uma métrica de rede. Mas a gente não testou o mesmo com SQL, então isso fica como hipótese.

**"O que é a betweenness?"**

> A betweenness, ou intermediação, mede por quantos caminhos da bola um jogador fica no meio. Imagina uma jogada em
> que a bola só pode andar assim, do goleiro pro zagueiro, do zagueiro pro volante e do volante pro atacante. Pra bola
> sair do goleiro e chegar no atacante, ela obrigatoriamente passa pelo zagueiro e pelo volante. Então esses dois têm
> betweenness alta, porque estão no meio do caminho, e o goleiro e o atacante têm zero.
>
> No futebol, isso mostra quem é a ponte da circulação, o jogador por onde a bola precisa passar pra ir de um setor pro
> outro. E isso é diferente de quem mais tocou na bola. Um jogador pode dar muito passe sempre pros mesmos dois
> companheiros e não ligar ninguém, enquanto outro toca menos, mas é ele que conecta todo mundo.
>
> E foi exatamente isso que aconteceu na nossa pergunta. Na prorrogação, o Camavinga foi quem mais trocou passes na
> França, mas quem estava no meio dos caminhos da bola era o Koundé. Os modelos que escreveram a consulta contaram passes
> e responderam Camavinga. Já a abordagem com ferramentas tem essa métrica pronta, calculou a betweenness e acertou o
> Koundé nos quatro modelos.

**"Mas dá pra calcular betweenness em Cypher, não dá?"**

> Dá, sim, e o nosso repositório até tem um script que faz isso só com Cypher. O problema foi o modelo. Na pergunta
> sobre o principal elo da França, nenhum dos quatro modelos tentou calcular essa métrica. Todos contaram passes e
> responderam o Camavinga, que é quem mais tocou na bola, e não o Koundé, que é por onde a bola mais passa. Na
> abordagem com ferramentas, essa métrica já vem pronta, e o modelo só precisa escolher.

**"O que é a súmula?"**

> É uma tabela de totais por jogador e por time, como passes certos, desarmes e finalizações. Ela é calculada pelo
> próprio banco, contando as ações de cada jogador no grafo. É o que a abordagem de estatísticas resumidas recebe.

## Slide 7 · Perguntas e gabarito

**"Como vocês garantem que o gabarito está certo?"**

> O gabarito foi calculado por código, a partir do JSON bruto e da tabela de ações, sem usar o banco de grafos. E pra
> cada pergunta a gente testou as leituras possíveis. Por exemplo, o principal elo pode ser calculado com ou sem peso
> nos passes. Se a resposta mudava dependendo da leitura, a pergunta saía do conjunto. Por isso, das 81 perguntas que a
> gente escreveu, ficaram 52.

**"Como a resposta é corrigida?"**

> Por código também, sem LLM dando nota. A resposta vem num formato fixo, com uma lista de jogadores e um valor. Se a
> pergunta pede um jogador, vale o primeiro da lista, e se tem empate no gabarito, qualquer um dos empatados vale. Então
> a mesma resposta sempre recebe a mesma nota.

**"Pra que servem as perguntas de controle?"**

> Pra ver se o modelo sabe admitir quando não tem o dado. São perguntas como a distância que o De Paul percorreu, que
> não existe nesses dados. A resposta certa é dizer que não tem a informação, e se o modelo inventa um número, ele
> erra.

## Slide 8 · Seis abordagens

**"O que é um agente aqui?"**

> É o modelo trabalhando em passos. Em vez de responder de uma vez, ele chama uma ferramenta, olha o resultado e
> decide se chama outra ou se já responde. A gente limitou em 12 chamadas por pergunta.

**"Por que 30 linhas na busca vetorial?"**

> Foi uma escolha fixa do projeto, e a gente não testou outros valores. Mas o problema não é só o número. Pra contar,
> por exemplo, quantos desarmes alguém fez, você precisa de todas as linhas de desarme, e a busca por similaridade não
> garante isso, seja com trinta ou com cem linhas.

**"Por que temperaturas diferentes entre os modelos?"**

> Os menores rodaram com temperatura zero. Nos maiores, com o raciocínio estendido ligado, isso não é possível. O
> Sonnet exige temperatura 1 nesse modo, e o endpoint do Kimi não aceita mudar a temperatura, então os dois rodaram no
> padrão.

## Slide 9 · Mesmo grafo, duas formas de consultar

**"As ferramentas não foram feitas sob medida pras perguntas?"**

> Em parte, sim, e isso é uma limitação. As ferramentas e as perguntas foram feitas por nós, e as ferramentas foram
> ajustadas ao longo do projeto olhando os erros. Mas nas doze perguntas que não serviram pra esse ajuste, as
> ferramentas continuaram acertando quase todas, de dez a doze, dependendo do modelo. E elas são genéricas, tipo contar
> ações com filtros, e não uma ferramenta por pergunta.

**"Por que oito ferramentas, e não uma só que consulta tudo?"**

> Porque cada uma corresponde a um tipo de pergunta de futebol, como contar ações, montar a rede de passes ou achar
> sequências de passes. Assim o modelo escolhe pelo significado, e não precisa montar a consulta. Tem trabalho que faz
> o contrário, com uma ferramenta genérica de filtros e agregações, e comparar os dois jeitos seria interessante.

## Slide 10 · Resultado principal

**"Com uma repetição só, dá pra confiar?"**

> Dá pra ler como indício, não como prova. Com uma repetição e 47 perguntas, os intervalos de confiança ficam largos. O
> que se sustenta é a subida da consulta e do contexto longo dos modelos menores pros maiores, porque ali os intervalos
> não se cruzam. Entre ferramentas e consulta nos maiores, a gente não consegue dizer qual é melhor. Rodar mais
> repetições é o primeiro próximo passo.

**"Por que esses quatro modelos?"**

> A gente queria dois tamanhos e, em cada um, um modelo fechado e um aberto. Como nem todo fabricante divulga o número
> de parâmetros, a gente separou pelo preço por token. Assim dá pra ver se o resultado depende do tamanho e se vale
> também pra modelo aberto.

**"No Kimi, a consulta passou das ferramentas. Isso não contradiz?"**

> Não, porque a diferença está dentro do intervalo de confiança. Nos maiores, consulta e ferramentas ficaram empatadas
> na prática. O ponto é que as ferramentas mantêm esse nível também nos modelos menores, e a consulta não.

## Slide 11 · Perguntas encadeadas

**"Esse gráfico não está no artigo. De onde vêm os números?"**

> Dos mesmos resultados, separados por grupo de pergunta, e eles estão no repositório. No artigo, essa conclusão
> aparece no texto, quando a gente diz que nos modelos menores a diferença se concentrou nas perguntas de jogadas e de
> relações na rede de passes.

**"O que é uma pergunta encadeada?"**

> É uma pergunta em que a resposta depende de ligar eventos entre si. Por exemplo, depois que o Dembélé saiu, quem
> mais passou pro Mbappé? Não dá pra responder com uma linha só da tabela. Você precisa achar a substituição, pegar só
> os passes depois dela e contar por recebedor.

## Slide 12 · As três que acertaram pouco

**"A busca vetorial não foi mal configurada?"**

> Pode ser que outra configuração vá melhor, e a gente não testou variações. Mas o problema principal é o tipo de
> pergunta. A busca por similaridade traz o que se parece com a pergunta, e contar ou ligar eventos exige linhas que não
> se parecem com ela. O Tzikas, por exemplo, foi melhor porque cada trecho já trazia os eventos seguintes.

**"O que vocês chamam de alucinação?"**

> É quando o modelo dá uma resposta e ela está errada. A classificação é feita por código, então não tem julgamento de
> intenção. Se a pergunta tinha resposta e o modelo respondeu outra coisa, conta como alucinação. Se ele disse que não
> tinha os dados, conta como abstenção.

**"As estatísticas zeraram. Não é uma abordagem feita pra perder?"**

> Ela representa uma solução que muita gente usaria, que é mandar um resumo pronto pro modelo. E o resultado mostra
> justamente o limite disso. Os totais da partida inteira não respondem perguntas com recorte de tempo, de campo ou de
> quem passou pra quem.

## Slide 13 · Custo

**"Por que não colocar o custo em dólar?"**

> Porque preço muda o tempo todo e varia entre provedores. Tokens e tempo são medidas que continuam valendo, e dá pra
> converter pra dólar com o preço do dia.

**"A comparação de tempo é justa?"**

> Tem um detalhe que a gente declara. As ferramentas não usaram cache de prompt, e o contexto longo usou, porque a
> tabela era sempre a mesma. Isso favorece o contexto longo, e mesmo assim ele foi o mais lento. Então a conclusão é
> conservadora.

## Slide 14 · Conclusão e limitações

**"Por que não testaram o banco relacional?"**

> Por escopo. Montar as mesmas ferramentas sobre SQL é um trabalho grande, e a gente preferiu fechar bem a comparação
> das seis abordagens. Mas é o teste mais direto pra separar o efeito do grafo do efeito das ferramentas, e está nos
> próximos passos.

**"O ganho é do tamanho do modelo ou do raciocínio?"**

> Não dá pra separar, porque nos maiores os dois vieram juntos. Pra separar, teria que rodar os modelos maiores sem
> raciocínio estendido, que também está nos próximos passos.

## Slide 15 · Próximos passos

**"Como isso vira algo na indústria?"**

> Pensa numa linha de produção. Cada parada de máquina, cada alerta e cada movimentação de peça é um evento, com quem
> fez, quando e onde, igual um lance de futebol. Uma pergunta como qual máquina mais aparece antes das paradas é
> parecida com quem mais passou pro Mbappé. O caminho seria o mesmo, montar a tabela de eventos, o grafo e as
> ferramentas pras perguntas daquele contexto, e comparar as abordagens de novo.

**"Qual abordagem vocês recomendariam?"**

> Depende do cenário. Se precisa de um modelo pequeno e barato, e as perguntas são conhecidas, a abordagem com
> ferramentas. Se tem orçamento pra um modelo maior e as perguntas variam muito, a consulta escrita pelo modelo, que é
> mais flexível. E o contexto longo é o mais fácil de montar, mas fica caro e lento com modelo grande.

---

# Parte 2 · Reserva técnica (números e fontes)

Fontes: `paper/review/threats.md`, `paper/review/revisao-2026-10-15.md`, `paper/ALERTAS.md` e
`paper/generated/numbers.tex`. Nenhum número aqui foi recalculado à mão: todos vêm dessas fontes.

## 1. Comparação das abordagens

**1. As ferramentas foram feitas e ajustadas para estas perguntas. A comparação é justa?**
Não é simétrica, e o artigo declara isso: as Ferramentas foram ajustadas olhando erros (sete congelamentos); a Consulta
escrita pelo modelo é primeiro contato. Por isso a diferença entre as duas é o teto do ganho de engenharia, não uma
medida de justiça. Sinais a favor: nas 12 perguntas que não serviram ao ajuste, as Ferramentas acertaram 12, 10, 12 e
11, e a Consulta, 10, 9, 11 e 12. As Ferramentas acertam dentro da cobertura delas (limitação do slide 14).

**2. O ganho vem das ferramentas, do grafo ou dos algoritmos de grafo (GDS)?**
Não está separado. O par Consulta × Ferramentas usa o mesmo grafo e o mesmo limite de chamadas e isola quem escreve a
consulta. Só 5 perguntas dependem do GDS. Sem elas, as Ferramentas acertaram 36, 34, 37 e 37 de 42, e a Consulta, 30,
26, 39 e 40. A Discussão traz uma hipótese não testada: um banco relacional (SQL) com as mesmas ferramentas iria bem
nas perguntas de busca e contagem, que são filtros e agregações, e a diferença apareceria nas de relações, que dependem
de caminhos e métricas de rede. Testar isso é trabalho futuro (Conclusão).

**2b. Por que um grafo, e não um banco relacional?**
A análise de futebol trata os passes de um time como uma rede, com os jogadores como nós e os passes como arestas
(Buldú et al.; Duch et al.). Perguntas sobre essa rede, como qual dupla mais trocou passes ou por qual jogador mais passa
a circulação da bola, viram caminhos e métricas sobre o grafo. Uma tabela relacional também guarda a informação, mas,
conforme a organização, seguir uma cadeia de passes pode exigir uma junção a cada passe, e métricas como a
intermediação dependeriam de implementação própria. A comparação direta com SQL não foi feita (pergunta 2).

**2c. O acerto das Ferramentas não é só cobertura?**
Em parte, e o artigo diz isso: as Ferramentas só respondem a perguntas para as quais existe uma ferramenta. No Contexto
longo e na Consulta escrita pelo modelo, o limite é a capacidade do modelo, não um conjunto fixo de operações. A
liberdade de escrever a consulta só virou acerto nos modelos maiores; nos menores, as consultas parametrizadas
supriram essa limitação.

**3. O ajuste das Ferramentas melhorou de fato o acerto?**
Seis perguntas refeitas levaram o Haiku de 39 para 45 de 52 (`all52_before_fixes_results.jsonl`, que está só no repositório antigo, `football-tactics-knowledge-graph`). A trajetória do ajuste
com as mesmas perguntas em cada versão oscila (10 a 25 pontos em n pequeno) e os intervalos se sobrepõem; por isso o
artigo não afirma que o ajuste levou as Ferramentas "de 50% a 95%" (`paper/ALERTAS.md`, item 1, no repositório antigo).

**4. Por que a Busca vetorial acerta tão pouco? Não é só um RAG mal feito?**
Cada linha recuperada é uma ação isolada; contar exige todas as linhas de um tipo e ligar eventos exige as vizinhas.
Tzikas et al. obtiveram acerto maior com outro desenho (trechos com os eventos seguintes, até cem trechos, reordenação,
conferência por LLM). Busca vetorial com eventos vizinhos é trabalho futuro.

**5. O 0% de Estatísticas resumidas não é um resultado forçado?**
É o degrau rígido: a súmula só tem totais da partida inteira, sem recorte de tempo ou de campo. O texto atribui o baixo
acerto ao desenho da abordagem, não a uma curva de comparação.

## 2. Estatística e desenho

**6. Uma repetição por pergunta e 47 perguntas com resposta: o que é sinal?**
Indício, não demonstração. O que se sustenta: a subida de Consulta e de Contexto longo dos menores para os maiores
(os intervalos de Wilson não se cruzam). Ferramentas e Consulta não se distinguem nos maiores (empate no Sonnet e
Consulta à frente no Kimi). Três repetições são o próximo passo.

**7. Havia três testes de McNemar sem correção.**
O texto não traz testes. Com ajuste de Holm, Consulta contra Contexto longo no Haiku fica em p=0,034; Ferramentas contra
Consulta no Haiku fica em p=0,057 (valores de `numbers.tex`).

**8. Os intervalos de confiança e o n.**
Wilson de 95%, que fica sempre entre 0 e 100. Com 47 perguntas e uma repetição, os intervalos são largos; o gráfico do
slide 10 mostra o acerto, e a figura do artigo traz os intervalos.

**9. Temperatura zero não é determinismo.**
As rodadas 10 e 11 mudaram três perguntas sem mudança de ferramenta. Só as repetições medem essa variação. Os modelos
maiores rodaram na temperatura padrão do provedor, com raciocínio estendido.

## 3. Perguntas, gabarito e dados

**10. As perguntas foram escritas e removidas por quem fez as ferramentas.**
Foram 81 escritas e 52 ativas; 22 removidas pelo teste de robustez ou por ambiguidade (7 candidatas nunca rodaram). A
lista com o motivo está em `config/questions.yaml` (`stage: removed`). Nenhuma ferramenta mudou por causa de uma pergunta.

**11. O gabarito é do mesmo autor e a regra de empate mudou no meio.**
O gabarito é calculado por código (pandas e networkx), a partir do JSON bruto e da tabela de ações. A
recorreção de 312 execuções mudou 0 veredito. Em empate, todos os empatados valem.

**12. A final de 2022 é famosa. Não é memorização?**
O prompt não nomeia a partida e proíbe responder de memória; o 0 de 47 de Sem dados mede obediência ao prompt.
Defesa adicional: as definições do projeto (recebedor inferido, fases de posse, leituras) e uma pergunta (s11) cuja
resposta famosa está errada. Uma só partida é limitação declarada.

**13. O controle não discrimina?**
São 5 perguntas; cada abordagem que lê os dados erra no máximo uma delas (`accControl*` em `numbers.tex`). A Consulta errou a u01 nos 4 modelos
(resposta dada em vez de ausência de dados). O artigo reporta com e sem o controle.

## 4. Custo, modelos e alcance

**14. A comparação de custo é justa? Ferramentas não usa cache.**
Por isso o artigo só mostra tokens e latência, sem preço em dólar. Ferramentas não usa cache de prompt e Consulta usa.
No Contexto longo, a maior parte da entrada vem do cache, o que o favorece: a conclusão de que ele é o mais lento é
conservadora.

**15. Tamanho ou raciocínio estendido explica o salto nos modelos maiores?**
Não dá para separar: vieram juntos. Avaliar modelos maiores sem raciocínio estendido é trabalho futuro. O Sonnet usou um
nível de raciocínio menor no Contexto longo (o ajuste favoreceu o Contexto longo, que ficou abaixo mesmo assim).

**16. "Alucinação" inclui erro honesto de leitura?**
A classificação é por código: resposta errada dada como resposta, não por intenção (`docs/05-conferencia-e-metricas.md`).

## 5. Próximos passos e dados industriais (fecho)

**17. Por que isso vale para indústria?**
Parte dos dados industriais tem a mesma forma: registros de eventos com agente, momento e local, ligados entre si (paradas,
alertas, movimentações). O resultado do futebol indica que a forma de levar os dados ao contexto pesa tanto quanto o
modelo. O slide 15 trata isso como um dos próximos passos, ao lado de mais repetições, várias partidas e a separação dos efeitos; não é um resultado.

**18. O que muda para aplicar em outro domínio?**
A preparação dos dados, o grafo e as ferramentas dependem das perguntas que se quer responder: exige implementação
própria para o domínio. As Ferramentas só valem para perguntas dentro da cobertura delas.

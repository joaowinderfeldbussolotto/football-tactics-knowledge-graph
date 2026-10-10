# 4. Os cinco braços, por dentro

Este capítulo mostra **exatamente** o que cada braço envia ao modelo, com
trechos reais. O código está em `src/football_graphrag/benchmark/arms.py`
(braços) e `benchmark/tools.py` (ferramentas do `graph_tools`). A lista
completa de transformações, coluna por coluna, está no
[capítulo 9](09-transformacoes-dos-dados.md).

---

## 4.1 O que todos os braços têm em comum

Para a comparação ser justa, só pode mudar uma coisa: **os dados que o modelo
recebe**. Todo o resto é igual:

| Item | Valor | Por quê |
|---|---|---|
| Modelo | o do `.env` (`LLM_PROVIDER` + `LLM_MODEL`) | o mesmo "cérebro" em todos os braços |
| Temperatura | 0 | o modelo escolhe sempre a resposta mais provável, sem sortear; reduz a variação entre repetições |
| Instrução de sistema | a mesma para todos (abaixo) | as mesmas regras do jogo |
| Formato da resposta | o modelo `Answer` (capítulo 5); resposta vazia é recusada | a mesma correção para todos |
| Tentativas de formato | até 2 novas tentativas se a resposta vier fora do formato | a mesma tolerância para todos |

A **instrução de sistema** (o texto que o modelo recebe antes de qualquer
pergunta) é esta, em inglês como todo o código:

```text
You answer questions about one football match, using the data provided in
this conversation. Questions are in Portuguese.

Answer only with the data provided in this conversation (in the message or
returned by your tools). Do not use outside knowledge, even if you think you
know the answer. If the provided data does not contain exactly what the
question asks for, set no_data to true: do not answer with a different or
approximate measure in its place.

Write player names exactly as they appear in the data.
```

A instrução não diz **qual** é a partida: diz só que as perguntas são sobre
uma partida, a dos dados. Assim o prompt não ajuda o modelo a responder de
memória. (As perguntas e os dados ainda permitem reconhecer o jogo; a regra
abaixo é o que impede o uso da memória.)

Em português: "Responda **só com os dados fornecidos**, mesmo que ache que
sabe a resposta. Se os dados não têm **exatamente** o que a pergunta pede,
marque `no_data`; não responda com outra medida no lugar." A última parte
existe porque, sem ela, o modelo tende a trocar o que foi pedido por algo
parecido que os dados têm, como contar conduções quando a pergunta é sobre
piques em velocidade.

Essa instrução tem uma consequência no braço `no_context`: como ele não
recebe dado nenhum, **o comportamento correto é responder `no_data` a quase
tudo**. Se ele acerta "quem marcou o primeiro gol", é porque usou a memória e
desobedeceu à instrução.

### Tamanho de cada braço

Tokens de entrada por pergunta (média de uma execução completa com o Claude
Haiku 5.5; a unidade que os provedores cobram):

| Braço | Tokens | O que pesa |
|---|---|---|
| `no_context` | ~900 | instrução + formato da resposta + pergunta |
| `vector` | ~2.600 | + 30 linhas de evento com a legenda |
| `stats_in_prompt` | ~5.000 | + súmula completa com glossário |
| `graph_tools` | ~37.000 | descrição das 7 ferramentas, repetida a cada chamada, mais os resultados |
| `events_in_prompt` | ~111.000 | + todos os 2.585 lances; com cache de prompt, só a primeira pergunta paga o preço cheio |

O `events_in_prompt` exige um modelo com janela de contexto de pelo menos 128
mil tokens.

---

## 4.2 `no_context`: só a pergunta

O modelo recebe a instrução de sistema e a pergunta, mais nada.

**O que se espera:** responder "sem dados". Serve de linha de base: mede o
quanto o modelo responde de memória.

---

## 4.3 `events_in_prompt`: o jogo inteiro, lance por lance

O modelo recebe uma tabela com **uma linha por ação**, os 2.585 lances, em
ordem de jogo, precedida de uma legenda:

```text
Match events:
One row per on-ball action (SPADL), in match order; penalty shootout excluded.
period: 1 and 2 regular time, 3 and 4 extra time. minute: broadcast minute (stoppage
time continues the count, so the 1st half goes past 45). team, player: who acted. action: action type
(Portuguese labels, e.g. passe, conducao, drible, desarme, interceptacao,
falta_cometida, finalizacao, penalti, cartao_por_reclamacao). success: 1/0.
receiver: who received a completed pass. zone_from/zone_to: cell of a 12x8 grid,
zone = column*8 + row, column 0-11 from the acting team's own goal to the
opponent's goal; third = zone // 32 (0 defensive, 1 middle, 2 attacking).
possession: id of the possession phase. outcome: goal with the score it made,
e.g. goal(3-2), yellow_card, and the shot result (defendida, bloqueada,
para_fora) when there is one. score: the score Argentina-France when the
action starts, before it (2-1: Argentina 2, France 1).

period,minute,team,player,action,success,receiver,zone_from,zone_to,possession,outcome,score
1,1,France,Antoine Griezmann,passe,1,Aurélien Djani Tchouaméni,51,35,1,,0-0
1,1,France,Aurélien Djani Tchouaméni,conducao,1,,35,35,1,,0-0
...
4,124,Argentina,Paulo Bruno Exequiel Dybala,corte,1,,10,10,537,,3-3

Question: <a pergunta>
```

O fim do lance do gol de Di María (capítulo 2) aparece assim:

```text
1,36,Argentina,Alexis Mac Allister,passe,1,Ángel Fabián Di María Hernández,74,92,132,,1-0
1,36,Argentina,Ángel Fabián Di María Hernández,finalizacao,1,,92,91,132,goal(2-0),1-0
```

Cada coluna é um dado da camada 0, sem nenhuma contagem pronta. Algumas
existem para que o braço tenha os fatos que as perguntas usam:

- **`period`:** o minuto da transmissão se repete entre os tempos (o 1º tempo
  da final foi até 53', e o 2º recomeça no 46'). Sem o período, "52'" é
  ambíguo.
- **`possession`:** permite saber se dois passes foram na mesma jogada.
- **`outcome`:** marca gol, com o placar que ele fez, cartão amarelo e o
  desfecho das finalizações.
- **`score`:** o placar quando a ação começa. Permite localizar recortes
  como "enquanto vencia por 2 a 0" sem reconstruir o placar de cabeça.

**O que se espera:** todos os fatos estão lá, mas o modelo precisa **contar e
cruzar sozinho**, lendo 111 mil tokens. Fatos isolados costumam ir bem.
Contagens longas e cálculos de rede são onde costuma errar ou desistir.

---

## 4.4 `vector`: as 30 linhas mais parecidas

Este é o "RAG vetorial", o jeito mais comum de ligar um LLM a documentos.

**Como funciona, passo a passo:**

1. **Preparação (uma vez).** Cada uma das 2.585 linhas da tabela de eventos
   é enviada a um modelo de *embedding*, que devolve um vetor: uma lista de
   centenas de números que representa o "sentido" do texto. Textos parecidos
   ganham vetores parecidos. Os vetores ficam guardados em
   `data/benchmark/cache/` e não são pagos de novo enquanto a tabela não
   mudar.
2. **A cada pergunta**, a pergunta também vira vetor.
3. Calcula-se a **similaridade de cosseno** entre o vetor da pergunta e o de
   cada linha. É um número de -1 a 1 que mede o quanto dois vetores apontam
   para a mesma direção.
4. As **30 linhas mais parecidas** vão para o modelo, reordenadas na ordem do
   jogo, com a mesma legenda do `events_in_prompt`.

Não há banco vetorial: os vetores ficam numa matriz em memória (numpy) e a
busca é uma multiplicação de matrizes.

**O que se espera:** bom quando a resposta está em **uma ou poucas linhas**
com palavras parecidas com as da pergunta. Ruim para contagens ("quantos
passes?" exige todas as linhas de passe, não 30) e para perguntas de rede. A
similaridade é de **texto**, não de significado futebolístico.

---

## 4.5 `stats_in_prompt`: a súmula pronta

O modelo recebe a súmula da camada 1b (capítulo 2), **lida do Neo4j**:
primeiro um glossário de cada coluna, depois uma linha por time e uma por
jogador.

```text
Match stats:
What each column means:
- acoes: on-ball actions of any type (team)
- acoes_no_terco_final: actions in the attacking third (team)
- assistencias: passes that set up a goal
- desarmes_certos: tackles won
...

Team stats:
nome,acoes,acoes_no_terco_final,cartoes_amarelos,desarmes_certos,...,posse_pct,...

Player stats (one row per player who acted):
nome,time,posicao,assistencias,cartoes_amarelos,conducoes,cortes,...

Question: <a pergunta>
```

**O que se espera:** bom quando a pergunta é sobre a partida inteira e a
conta já está feita. A súmula não tem recortes de tempo (um tempo, a
prorrogação, "depois do 2 a 2"), nem quem passou para quem, nem a ordem dos
lances. Nesses casos, o certo é responder "sem dados".

---

## 4.6 `graph_tools`: o modelo investiga com ferramentas

Aqui o modelo **não recebe dados**. Recebe a pergunta e uma lista de
ferramentas (*tools*), cada uma com nome, descrição e argumentos. O modelo
decide qual chamar; o programa executa a ferramenta (uma consulta ao Neo4j) e
devolve o resultado; o modelo lê e decide se chama outra ou se já responde.
Isso se chama *tool calling*.

### As sete ferramentas

São **primitivas**: nenhuma traz um conceito tático pronto. O modelo tem de
combiná-las.

| Ferramenta | O que faz |
|---|---|
| `list_players` | lista os jogadores, com time e posição |
| `query_actions` | conta ações (ou soma o xT delas) com filtros, agrupando por jogador, recebedor, time, ação, período, terço ou corredor |
| `list_actions` | lista ações em ordem, com o segundo do jogo, o placar antes da ação e, num gol, o placar depois |
| `pass_network` | monta a rede de passes de um time, com filtros; devolve um identificador |
| `network_metric` | calcula uma métrica sobre a rede: betweenness, grau, PageRank, pontes, pontos de articulação ou comunidades |
| `network_edges` | lista as ligações da rede (quem passou para quem, quantas vezes) |
| `pass_paths` | conta as sequências de jogadores mais repetidas em passes encadeados (A → B → C) |

Os filtros são os mesmos em todas: time, jogador, tipo de ação, certo ou
errado, período, janela de tempo em segundos, terço, corredor, gol, cartão,
assistência. As regras de cada filtro e de cada métrica estão no
[capítulo 9](09-transformacoes-dos-dados.md#as-ferramentas-graph_tools).

### Um exemplo do ciclo

Pergunta: "Na prorrogação, quem foi o principal elo da circulação de bola da
França?" (trace real, resumido):

1. `pass_network(team="France", filters={"period": [3, 4]})` devolve
   `{"network_id": "net1", "team": "France", "filters": {"period": [3, 4]}, "players": ..., "passes": ...}`.
2. `network_metric(network_id="net1", metric="betweenness", weight="passes", direction="undirected")`
   devolve Koundé em primeiro, bem à frente de Tchouaméni e Varane.
3. O modelo responde `players: ["Jules Koundé"]`.

### Como as ferramentas foram desenhadas

- **Consultas fixas.** Cada ferramenta executa uma consulta Cypher escrita à
  mão, com parâmetros. O modelo **nunca escreve Cypher**.
- **Descrição em duas partes.** Cada descrição diz o que a ferramenta
  calcula (mecânica) e o que isso costuma significar no futebol, sem regras
  feitas para uma pergunta. Exemplo, da betweenness: "for every pair of
  other players, counts how many shortest passing routes go through each
  player... In football terms, betweenness marks a player who connects
  teammates in ball circulation, a link or hub of the build-up".
- **Nenhuma lê a camada 2.** Os padrões já calculados (`PadraoTatico`)
  seriam a resposta pronta. As métricas de rede são calculadas **na hora**.
- **Resultados que se explicam.** Toda ferramenta de rede repete o time e
  os filtros com que a rede foi montada, para o modelo não confundir duas
  redes.
- **Erros viram mensagens.** Um time que não existe, um nome ambíguo
  ("Martínez" é Lautaro ou Emiliano?) ou uma rede que ainda não foi criada
  geram uma mensagem explicando o problema, e o modelo pode tentar de novo.
- **Uma chamada por vez, até 12 por pergunta.** Da 13ª em diante, a
  ferramenta responde "limite atingido, responda com o que você tem". Se o
  modelo ainda insistir, a execução para depois de 16 pedidos ao provedor e
  conta como erro de formato.
- **Congeladas antes das perguntas.** As ferramentas e suas descrições são
  fixadas antes de se escreverem as perguntas que as testam.
  `tests/test_tools_frozen.py` guarda um hash das definições.

**O que se espera:** é o único braço capaz de calcular redes e recortes sem
ler tudo, então deve ir melhor em agregações e perguntas de rede. O risco
está em escolher a ferramenta errada, ler mal o resultado ou localizar mal o
momento do jogo.

---

## 4.7 Rodando um braço isolado

Para ver tudo isso acontecendo, sem gravar resultados:

```bash
python scripts/ask.py --question s01 --arm graph_tools
python scripts/ask.py --question a01 --arm stats_in_prompt --show-prompt
```

O `--show-prompt` imprime o prompt completo enviado. Para o `graph_tools`, a
saída lista cada ferramenta chamada, com os argumentos. Detalhes no
[capítulo 6](06-como-rodar.md).

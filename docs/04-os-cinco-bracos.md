# 4. Os cinco braços, por dentro

Este capítulo mostra **exatamente** o que cada braço envia ao modelo, com
trechos reais. O código está em `src/football_graphrag/benchmark/arms.py`
(braços) e `benchmark/tools.py` (ferramentas do `graph_tools`).

---

## 4.1 O que todos os braços têm em comum

Para a comparação ser justa, só pode mudar uma coisa: **os dados que o modelo
recebe**. Todo o resto é igual:

| Item | Valor | Por quê |
|---|---|---|
| Modelo | o do `.env` (`LLM_PROVIDER` + `LLM_MODEL`) | o mesmo "cérebro" em todos os braços |
| Temperatura | 0 | o modelo escolhe sempre a resposta mais provável, sem sortear; reduz a variação entre repetições |
| Instrução de sistema | a mesma para todos (abaixo) | as mesmas regras do jogo |
| Formato da resposta | o modelo `Answer` (capítulo 5) | a mesma correção para todos |
| Tentativas de formato | até 2 novas tentativas se a resposta vier fora do formato | a mesma tolerância para todos |

A **instrução de sistema** (o texto que o modelo recebe antes de qualquer
pergunta) é esta, em inglês como todo o código:

```text
You answer questions about one football match: the 2022 FIFA World Cup final,
Argentina vs France. Questions are in Portuguese.

Answer only with the data provided in this conversation (in the message or
returned by your tools). Do not use outside knowledge, even if you think you
know the answer. If the provided data does not contain what is needed to
answer, set no_data to true.

Write player names exactly as they appear in the data.
```

Em português: "Você responde perguntas sobre uma partida, a final da Copa de
2022. Responda **só com os dados fornecidos**, mesmo que ache que sabe a
resposta. Se os dados não bastarem, marque `no_data`."

Essa instrução tem uma consequência no braço `no_context`: como ele não
recebe dado nenhum, **o comportamento correto seria responder `no_data` a
quase tudo**. Se ele acerta "quem marcou o primeiro gol", é porque usou a
memória e desobedeceu à instrução. Isso é exatamente o que se quer medir.

### Tamanho de cada braço

Quantos **tokens** (pedaços de palavra; a unidade que os provedores cobram)
cada braço envia no primeiro pedido, para a pergunta c01:

| Braço | Tokens | O que pesa |
|---|---|---|
| `no_context` | ~340 | instrução + formato da resposta + pergunta |
| `vector` | ~1.450 | + 30 linhas de evento com a legenda |
| `graph_tools` | ~2.350 | + descrição das 8 ferramentas (~2.000); **cada consulta soma um novo pedido** |
| `stats_in_prompt` | ~3.700 | + súmula completa com glossário |
| `events_in_prompt` | ~68.400 | + todos os 2.585 lances |

A contagem usa um tokenizador genérico (`o200k`); o do seu modelo pode
diferir em 10 a 20%. Os números reais de cada execução ficam no
`results.jsonl`, informados pelo provedor. O `events_in_prompt` exige um
modelo com janela de contexto de pelo menos 128 mil tokens.

---

## 4.2 `no_context`: só a pergunta

O modelo recebe a instrução de sistema e a pergunta, mais nada.

```text
Na final, quantos passes errou o jogador da Argentina por quem passava o maior
número de rotas de passe entre os companheiros (o principal elo de ligação na
circulação de bola do time)?
```

**O que se espera:** acertar só o que é famoso (f01, f02), e talvez inventar
respostas no resto. Serve de linha de base: um braço com dados que acerta
menos que o `no_context` está atrapalhando o modelo.

---

## 4.3 `events_in_prompt`: o jogo inteiro, lance por lance

O modelo recebe uma tabela com **uma linha por ação**, os 2.585 lances, em
ordem de jogo. Começo e fim reais da tabela:

```text
Match events:
One row per on-ball action (SPADL), in match order; penalty shootout excluded.
period: 1 and 2 regular time, 3 and 4 extra time. minute: broadcast minute (stoppage
time continues the count, so the 1st half goes past 45). team, player: who acted.
action: action type (Portuguese labels, e.g. passe, conducao, drible, desarme, ...).
success: 1/0. receiver: who received a completed pass. zone_from/zone_to: cell of a
12x8 grid, ... third = zone // 32 (0 defensive, 1 middle, 2 attacking).
possession: id of the possession phase. outcome: goal, yellow_card, and the
shot result (defendida, bloqueada, para_fora) when there is one.

period,minute,team,player,action,success,receiver,zone_from,zone_to,possession,outcome
1,1,France,Antoine Griezmann,passe,1,Aurélien Djani Tchouaméni,44,60,1,
1,1,France,Aurélien Djani Tchouaméni,conducao,1,,60,60,1,
1,1,France,Aurélien Djani Tchouaméni,passe,0,,60,16,1,
...
4,124,Argentina,Paulo Bruno Exequiel Dybala,corte,1,,85,85,537,

Question: Quem deu a assistência para o segundo gol da França na final?
```

O lance do gol de Di María (capítulo 2) aparece assim:

```text
1,36,Argentina,Alexis Mac Allister,passe,1,Ángel Fabián Di María Hernández,74,92,132,
1,36,Argentina,Ángel Fabián Di María Hernández,finalizacao,1,,92,91,132,goal
```

As colunas são as da camada 0, sem nada agregado. Três delas foram
acrescentadas ao que o plano original previa, porque sem elas faltariam
fatos que as perguntas usam:

- `period`: o minuto da transmissão se repete entre os tempos (o 1º tempo da
  final foi até 53', ou seja, 45+8, e o 2º recomeça no 46'). Sem o período,
  "52'" é ambíguo.
- `possession`: a regra da combinação de três jogadores exige "na mesma
  posse".
- `outcome`: gol e cartão amarelo são marcas da ação. Sem esta coluna, o
  braço não saberia quem fez gol nem quem levou cartão.

**O que se espera:** todos os fatos estão lá, mas o modelo precisa **contar e
cruzar sozinho**, lendo 68 mil tokens. Perguntas factuais devem ir bem.
Contagens longas e cálculos de rede são onde costuma errar.

---

## 4.4 `vector`: as 30 linhas mais parecidas

Este é o "RAG vetorial", o jeito mais comum de ligar um LLM a documentos.

**Como funciona, passo a passo:**

1. **Preparação (uma vez).** Cada uma das 2.585 linhas da tabela de eventos
   é enviada a um modelo de *embedding*, que devolve um vetor: uma lista de
   centenas de números que representa o "sentido" do texto. Textos parecidos
   ganham vetores parecidos. Os vetores ficam guardados em
   `data/benchmark/cache/` e não são pagos de novo.
2. **A cada pergunta**, a pergunta também vira vetor.
3. Calcula-se a **similaridade de cosseno** entre o vetor da pergunta e o de
   cada linha. É um número de -1 a 1 que mede o quanto dois vetores apontam
   para a mesma direção.
4. As **30 linhas mais parecidas** vão para o modelo, reordenadas na ordem do
   jogo, com a mesma legenda do `events_in_prompt`.

```text
The 30 match events most similar to the question:
One row per on-ball action (SPADL), in match order; ...
period,minute,team,player,action,success,receiver,zone_from,zone_to,possession,outcome
... (30 linhas escolhidas pela similaridade) ...

Question: Quem deu a assistência para o segundo gol da França na final?
```

Não há banco vetorial: os vetores ficam numa matriz em memória (numpy) e a
busca é uma multiplicação de matrizes. Com 2.585 linhas, isso leva
milissegundos.

**O que se espera:** bom quando a resposta está em **uma ou poucas linhas**
com palavras parecidas com as da pergunta. Ruim para contagens ("quantos
passes?" exige todas as linhas de passe, não 30) e para perguntas de rede.
Há também um limite que vale entender: a similaridade é de **texto**, não de
significado futebolístico. "Segundo gol da França" não se parece
textualmente com a linha `finalizacao,...,goal` de Mbappé aos 81'.

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
- desarmes_tentados: tackles attempted
...

Team stats:
nome,acoes,acoes_no_terco_final,cartoes_amarelos,desarmes_certos,...,posse_pct,...
Argentina,1391,327,4,15,...,54.4,...

Player stats (one row per player who acted):
nome,time,posicao,assistencias,cartoes_amarelos,conducoes,cortes,...,desarmes_certos,desarmes_tentados,...
Enzo Fernandez,Argentina,Center Defensive Midfield,0,1,80,4,...,5,9,...

Question: Quem fez mais desarmes certos na final? Liste os 3 primeiros.
```

Duas escolhas de projeto:

- **A fonte é o Neo4j**, não um cálculo à parte. Assim este braço e o
  `graph_tools` partem **exatamente dos mesmos números**, e a única
  diferença entre eles é ter ou não ter as ferramentas.
- **O glossário é o mesmo** que vai na descrição das ferramentas do
  `graph_tools`. Se só um dos dois braços recebesse a explicação dos campos,
  a comparação ficaria torta.

**Não inclui nada da camada 2** (nenhum padrão de rede). **O que se espera:**
muito bom em factual simples e em agregações, porque a conta já está feita.
Não tem como responder perguntas de rede, nem fatos que não viraram
contagem (quem deu a assistência do 2º gol, em que ordem vieram os cartões).

---

## 4.6 `graph_tools`: o modelo investiga com ferramentas

Aqui o modelo **não recebe dados**. Recebe a pergunta e uma lista de
ferramentas (*tools*), cada uma com nome, descrição e argumentos. O modelo
decide quais chamar. O programa executa a ferramenta (uma consulta ao Neo4j)
e devolve o resultado. O modelo lê o resultado e decide se chama outra
ferramenta ou se já responde. Isso se chama *tool calling*.

### Um exemplo do ciclo

Pergunta s03: "Na final, quem foi o segundo jogador da Argentina por quem
passavam mais rotas de passe entre os companheiros?"

1. O modelo lê a descrição das ferramentas e conclui que
   `pass_network_centrality` mede "who held a team's passing together".
2. Chama `pass_network_centrality(team="Argentina", top=3)`.
3. O programa roda o algoritmo no Neo4j e devolve (resultado real):
   ```json
   [{"player": "Nicolás Hernán Otamendi", "betweenness": 50.0},
    {"player": "Enzo Fernandez", "betweenness": 25.0},
    {"player": "Lionel Andrés Messi Cuccittini", "betweenness": 21.0}]
   ```
4. O modelo responde `players: ["Enzo Fernandez"]`.

Numa pergunta composta, o ciclo tem mais voltas: primeiro descobrir quem é o
elo (ferramenta de rede), depois buscar os números dele (`player_stats`).

### As 8 ferramentas

| Ferramenta | O que faz | Exemplo de uso |
|---|---|---|
| `list_players(team)` | lista os jogadores do time com posição e número de ações | descobrir o nome exato antes de outra consulta |
| `player_stats(name)` | a súmula completa de um jogador | "quantos desarmes Enzo fez?" |
| `team_stats(team)` | a súmula de um time | "quantas finalizações a França fez?" |
| `stat_ranking(stat, team, top)` | ranking por uma estatística | "quem fez mais faltas?" |
| `events(event_type, team)` | lista de eventos de um tipo, em ordem: gols, assistências, cartões, finalizações, faltas, desarmes... | "quem levou o primeiro amarelo?" |
| `pass_network_centrality(team, top)` | ranking de quem mais liga a rede de passes do time (betweenness, calculada na hora) | perguntas de "elo de ligação" |
| `three_player_sequences(team, top)` | combinações A→B→C mais repetidas | perguntas de combinação de três |
| `pass_network_bridges(team)` | pontes e grupos (comunidades) da rede de passes | nenhuma pergunta usa; está lá porque um usuário real poderia perguntar |

### Como as ferramentas foram desenhadas

- **Consultas fixas.** Cada ferramenta executa uma consulta Cypher escrita à
  mão, com parâmetros. O modelo **nunca escreve Cypher**. Isso elimina uma
  fonte de erro (Cypher inválido ou que conta errado) e torna o braço
  reproduzível.
- **Genéricas, não uma por pergunta.** Não existe `quem_deu_assistencia_do_2o_gol`.
  As ferramentas devolvem **dados e rankings**, e o modelo tem de interpretar.
- **Nenhuma lê a camada 2.** Os padrões já calculados (`PadraoTatico`)
  seriam a resposta pronta. As ferramentas de rede rodam o algoritmo **na
  hora**, sobre a mesma rede de passes que a camada 2 usa.
- **Descrições escritas para o modelo.** Cada descrição explica o que a
  ferramenta calcula, quando usar e como ler o resultado, em termos de
  futebol. A de `pass_network_centrality`, por exemplo, diz que um valor alto
  significa que a circulação de bola dependia daquele jogador para ligar os
  outros, e que isso **não** é o mesmo que dar mais passes. Os argumentos
  também têm descrição (que times valem, que estatísticas existem, limites).
- **Erros viram mensagens.** Se o modelo pede um time que não existe, um nome
  ambíguo ("Martínez" é Lautaro ou Emiliano?) ou uma estatística
  desconhecida, a ferramenta devolve uma mensagem explicando o problema, e
  o modelo pode corrigir e tentar de novo. Nada quebra.
- **Limite de 8 chamadas por pergunta.** Da 9ª em diante, a ferramenta
  responde "limite atingido, responda com o que você tem". Se o modelo ainda
  insistir, a execução é interrompida após 12 pedidos ao provedor e conta
  como erro de formato.

**O que se espera:** é o único braço capaz de calcular a rede de passes, então
deve ir melhor em `structural` e `composite`. O risco está em escolher a
ferramenta errada, entender mal o resultado ou gastar as chamadas. Também é
o braço mais caro em número de pedidos.

---

## 4.7 Rodando um braço isolado

Para ver tudo isso acontecendo, sem gravar resultados:

```bash
python scripts/ask.py --question s03 --arm graph_tools
python scripts/ask.py --question a01 --arm stats_in_prompt --show-prompt
```

O `--show-prompt` imprime o prompt completo enviado. Para o `graph_tools`, a
saída lista cada ferramenta chamada, com os argumentos. Detalhes no
[capítulo 6](06-como-rodar.md).

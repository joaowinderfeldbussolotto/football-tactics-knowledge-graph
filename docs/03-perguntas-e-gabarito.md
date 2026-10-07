# 3. Perguntas e gabarito

Um benchmark só vale o que valem as respostas certas dele. Este capítulo
explica como as 30 perguntas foram escritas, onde elas ficam, como a
resposta certa de cada uma é calculada e como se confere que esse cálculo
está certo.

---

## 3.1 Onde ficam as perguntas: `config/questions.yaml`

As perguntas ficam num arquivo de configuração, separado do código:
[`config/questions.yaml`](../config/questions.yaml). Uma entrada tem esta
cara:

```yaml
  - id: a01
    type: aggregation
    check: set
    text: >-
      Quem fez mais desarmes certos na final? Liste os 3 primeiros.
    note: >-
      Ranking sem empate na 3ª posição (Enzo 5, Tagliafico 4, Camavinga 4; o 4º tem 3).
      A ordem não é conferida.
```

O que cada campo quer dizer:

| Campo | Para que serve |
|---|---|
| `id` | identificador curto. A letra diz o tipo: **f**actual, **a**ggregation, **s**tructural, **c**omposite, **u**nanswerable |
| `type` | o tipo da pergunta (capítulo 1) |
| `check` | **como** a resposta é conferida (tabela abaixo) |
| `tolerance` | opcional. Margem aceita para números contínuos. Contagens são exatas e não usam |
| `text` | a pergunta, **exatamente** como vai para o modelo |
| `note` | um comentário para quem lê o arquivo. **Nunca vai para o modelo** |

Os tipos de conferência (`check`):

| `check` | A resposta está certa quando... | Exemplo |
|---|---|---|
| `player` | o **primeiro** jogador da resposta é o esperado | "Quem marcou o primeiro gol?" |
| `value` | o número é o esperado | "Quantos gols foram marcados?" |
| `set` | o **conjunto** de jogadores é o esperado, em qualquer ordem | "Quais jogadores da França receberam amarelo?" |
| `player_and_value` | jogador **e** número estão certos | "Qual jogador deu mais passes certos, e quantos foram?" |
| `no_data` | o modelo disse que os dados não respondem | "Qual a velocidade máxima de Mbappé?" |

O arquivo é **validado ao carregar** (`benchmark/questions.py`). O programa se
recusa a rodar se houver id repetido, `check` desconhecido, um tipo com
quantidade diferente de 6, ou um `id` cuja letra não bate com o tipo.

---

## 3.2 As regras para escrever uma pergunta

Cada regra existe para evitar um jeito específico de o benchmark medir a
coisa errada.

**1. Toda pergunta é fechada** ("quem", "quantos", "quais"), nunca "explique"
ou "por quê". Uma pergunta aberta precisaria de alguém (ou de outro LLM)
julgando a resposta, e o julgamento vira ruído. Com pergunta fechada, a
correção é feita por código e é inequívoca.

**2. Resposta única, sem empate.** Se dois jogadores empatam em primeiro,
"quem fez mais?" tem duas respostas certas. O código que calcula o gabarito
**se recusa a continuar** quando há empate na posição perguntada (3.4).

**3. Linguagem de futebol, não de ferramenta.** Esta é a regra mais sutil. O
braço `graph_tools` tem uma ferramenta chamada `pass_network_centrality`, que
calcula a *betweenness centrality*. Se a pergunta dissesse "quem tem a maior
betweenness centrality?", ela estaria **apontando a ferramenta para o
modelo**: bastaria casar as palavras. Por isso a pergunta descreve o
conceito como um comentarista descreveria:

> Na final, quem foi o jogador da Argentina por quem passava o maior número
> de rotas de passe entre os companheiros (o principal elo de ligação na
> circulação de bola do time)?

Cabe ao modelo perceber que "elo de ligação na circulação de bola" é o que a
ferramenta calcula, e essa é justamente a habilidade que se quer medir. O
teste `tests/test_questions.py` falha se alguma pergunta usar nome de
ferramenta ou de algoritmo ("betweenness", "xT", "grafo", "Louvain" etc.).

**4. Só duas perguntas com resposta famosa.** f01 (primeiro gol) e f02 (número
de gols) qualquer fã sabe. As demais foram escolhidas para que a memória do
modelo não ajude, e é isso que o braço `no_context` vai confirmar.

**5. Nada que dependa de onde os dados discordam.** "Passes tentados" e
"defesas do goleiro" têm números diferentes no JSON bruto e na camada 0
(capítulo 2), então não são perguntados.

**6. Seis por tipo.** O mesmo número em cada tipo permite comparar os tipos
entre si.

### As 30 perguntas e as respostas certas

| id | Pergunta (resumida) | Resposta certa | Fonte do gabarito |
|---|---|---|---|
| f01 | Quem marcou o primeiro gol? | Messi | JSON bruto |
| f02 | Quantos gols (sem disputa de pênaltis)? | 6 | JSON bruto |
| f03 | Assistência do 2º gol da França? | Marcus Thuram | JSON bruto |
| f04 | Primeiro jogador a levar amarelo? | Enzo Fernandez | JSON bruto |
| f05 | Quem levou amarelo sem cometer falta? | Olivier Giroud | JSON bruto |
| f06 | Quantas finalizações de Lautaro Martínez? | 4 | JSON bruto |
| a01 | Top 3 em desarmes certos | Enzo, Tagliafico, Camavinga | Parquet |
| a02 | Mais passes certos, e quantos? | Enzo Fernandez, 79 | JSON bruto |
| a03 | Mais dribles completos, e quantos? | Mbappé, 6 | JSON bruto |
| a04 | Finalizações da França | 10 | JSON bruto |
| a05 | Mais faltas cometidas, e quantas? | Julián Álvarez, 8 | JSON bruto |
| a06 | Jogadores da França com amarelo | Rabiot, Thuram, Giroud | JSON bruto |
| s01 | Principal elo de ligação da Argentina | Otamendi | Parquet + networkx |
| s02 | Principal elo de ligação da França | Koundé | Parquet + networkx |
| s03 | Segundo elo de ligação da Argentina | Enzo Fernandez | Parquet + networkx |
| s04 | Jogador do meio da combinação de três mais repetida da França | Varane | Parquet |
| s05 | Os três jogadores dessa combinação | Koundé, Varane, Upamecano | Parquet |
| s06 | Combinações de três repetidas ≥ 2 vezes pela Argentina | 6 | Parquet |
| c01 | Passes errados do principal elo da Argentina | 6 | Parquet + JSON |
| c02 | Passes certos do principal elo da França | 52 | Parquet + JSON |
| c03 | Desarmes certos do 2º elo da Argentina | 5 | Parquet |
| c04 | Na combinação mais repetida da França, quem deu mais passes certos? | Varane | Parquet + JSON |
| c05 | Passes certos do 1º para o 2º elo da Argentina | 14 | Parquet + JSON |
| c06 | Faltas do principal elo da França | 2 | Parquet + JSON |
| u01–u06 | velocidade, distância, melhor jogador, temperatura, público, frequência cardíaca | `no_data` | – |

O texto completo de cada uma está no YAML. As respostas calculadas ficam em
`data/benchmark/ground_truth.json`.

---

## 3.3 A regra de ouro do gabarito: nunca ler o banco avaliado

O braço `graph_tools` consulta o Neo4j, e o `stats_in_prompt` recebe números
que vêm do Neo4j. Se o gabarito também viesse do Neo4j, um erro no banco
apareceria **dos dois lados**: o braço erraria, o gabarito erraria igual, e o
erro contaria como acerto.

Por isso o gabarito (`benchmark/ground_truth.py`) é calculado por **outro
caminho**, a partir de duas fontes:

1. **O JSON bruto da StatsBomb**, sempre que a definição é simples:
   - gol = evento `Shot` com resultado `Goal`;
   - cartão amarelo = cartão dentro de `foul_committed` **ou** de
     `bad_behaviour` (o de Giroud, por reclamação, está no segundo);
   - assistência = passe marcado com `goal_assist`;
   - passe certo = evento `Pass` **sem** campo `outcome` (a StatsBomb só
     marca o resultado dos passes que falharam);
   - drible completo = evento `Dribble` com resultado `Complete`;
   - falta = evento `Foul Committed`; finalização = evento `Shot`.

   A disputa de pênaltis (período 5) é sempre excluída.

2. **A tabela da camada 0 (Parquet)**, quando a definição é da própria camada
   0, como "desarme certo" (`acao == 'desarme'` e `sucesso`), e para tudo o
   que envolve a rede de passes.

Conferência com a súmula oficial da FIFA: 6 gols (aos 23', 36', 80', 81',
108' e 118' da transmissão) e 7 cartões amarelos com a bola rolando. O 8º
amarelo, de Emiliano Martínez, foi na disputa de pênaltis e fica fora.

---

## 3.4 Como as perguntas estruturais são calculadas

### A rede de passes

Para cada time, monta-se uma **rede de passes**:

- cada jogador é um **nó**;
- se A deu pelo menos um passe certo para B, existe uma **seta A → B**;
- cada seta guarda quantos passes houve e quanto xT eles geraram somados.

A seta Mac Allister → Di María, por exemplo, inclui o passe do gol, que gerou
0,070 de xT.

### "Por quem passam as rotas": a betweenness, sem fórmula

Imagine quatro jogadores em linha, onde a bola só anda assim:

```
Goleiro → Zagueiro → Volante → Atacante
```

Para ir do Goleiro ao Atacante, a bola **tem** de passar pelo Zagueiro e pelo
Volante. Para ir do Zagueiro ao Atacante, tem de passar pelo Volante. Se
contarmos, para cada par de jogadores, quem fica no meio do caminho mais
curto, o Zagueiro e o Volante aparecem várias vezes e o Goleiro e o Atacante
nenhuma. Essa contagem é a **betweenness centrality**: quanto mais rotas
passam por um jogador, mais a circulação do time depende dele para ligar os
outros.

No jogo de verdade há muitos caminhos possíveis. O algoritmo pega, para cada
par de companheiros, o caminho **mais curto** e conta quem está no meio. O
"comprimento" de cada seta é `1 / (1 + xT dos passes)`: setas por onde a bola
avançou para áreas perigosas ficam mais curtas, então as rotas que criam
ameaça pesam mais.

Na final, o resultado foi:

| Argentina | | França | |
|---|---|---|---|
| Otamendi | 50 | Koundé | 40 |
| Enzo Fernandez | 25 | Rabiot | 25 |
| Messi | 21 | Kolo Muani | 17 |

Note que **ter o maior número de rotas não é o mesmo que dar mais passes**.
Quem deu mais passes certos na final foi Enzo (79), mas o principal elo da
Argentina foi Otamendi.

### Mesmo cálculo, dois programas diferentes

O Neo4j calcula a betweenness com a biblioteca GDS. O gabarito recalcula a
mesma coisa com **networkx** (uma biblioteca Python de grafos), a partir do
Parquet, replicando a montagem da rede de `graph/projections.py`. Um detalhe
técnico importa: o GDS devolve o valor **bruto**, e o networkx por padrão
devolve um valor **normalizado** (dividido por um fator). O gabarito usa
`normalized=False` para os dois falarem a mesma língua. Os números batem
exatamente: 50/25 e 40/25.

### As combinações de três jogadores

A regra, que vai por extenso na pergunta, é:

> A passa para B e B passa para C, três jogadores diferentes, na mesma posse
> de bola e sem outro passe no meio, terminando num terço do campo mais
> avançado do que aquele onde a jogada começou.

O gabarito procura todos os pares de passes certos que encaixam nessa regra
e conta quantas vezes cada combinação (A, B, C) aparece. É a mesma busca que
a camada 2 faz em Cypher, refeita em pandas. Nas 119 ocorrências da final,
entre o passe de A e o de B **só houve uma condução de B ou nada**, o que
confirma que "sem outro passe no meio" descreve fielmente a busca.

A combinação mais repetida da França foi **Koundé → Varane → Upamecano**, 3
vezes. A Argentina teve **6** combinações diferentes repetidas pelo menos
duas vezes.

### Recusa de empates

Antes de gravar cada resposta, o código verifica se há empate na posição
perguntada. Se houver, ele **para com erro** em vez de escolher um vencedor.
Por exemplo: em desarmes certos, o 2º e o 3º empatam (Tagliafico e Camavinga,
4 cada), mas a pergunta pede o **conjunto** dos 3 primeiros, e o 4º colocado
tem 3, então não há ambiguidade.

---

## 3.5 Tirar o jargão sem criar ambiguidade

A regra 3 (linguagem de futebol) tem um risco. Sem a definição técnica, cada
braço pode **entender o conceito de um jeito diferente**. Se a resposta muda
conforme a leitura, a pergunta fica injusta.

Por isso, antes de reescrever as perguntas, mediu-se a resposta sob quatro
leituras razoáveis de "por quem passavam mais rotas de passe":

| Pergunta | Pesado por xT (gabarito) | Sem peso | Rede sem direção | Peso = nº de passes |
|---|---|---|---|---|
| Principal elo, Argentina | Otamendi | Otamendi | Otamendi | Otamendi |
| Principal elo, França | Koundé | Koundé | Koundé | Varane (83,5 × 83,0) |
| 2º elo, Argentina | Enzo | Enzo | Enzo | Enzo |
| 2º elo, França | Rabiot | Tchouaméni | Rabiot | Koundé |

- As três primeiras linhas quase não mudam: a pergunta pode ser feita em
  linguagem de futebol sem medo.
- O **2º elo da França muda conforme a leitura** e saiu do benchmark, junto
  com a pergunta composta que dependia dele.
- As **combinações de três** mudam muito: sem a exigência de "terminar num
  terço mais avançado", a Argentina passa de 6 combinações repetidas para
  **58**. Por isso essas perguntas trazem a regra por extenso, em palavras de
  futebol.

---

## 3.6 Conferindo o gabarito contra o grafo

O gabarito foi calculado sem o Neo4j. Agora ele é comparado com o que o
Neo4j responde, por consultas Cypher fixas (camadas 1, 1b e 2):

```bash
python scripts/check_ground_truth.py
```

Saída (trecho):

```
[OK ] s03 structural   (parquet)
       truth: Enzo Fernandez   betweenness 25.0
       graph: Enzo Fernandez   GDS live: [('Nicolás Hernán Otamendi', 50.0), ('Enzo Fernandez', 25.0), ...]
[OK ] c05 composite    (parquet+raw_json)
       truth:  = 14   Nicolás Hernán Otamendi -> Enzo Fernandez
       graph:  = 14   Nicolás Hernán Otamendi -> Enzo Fernandez
...
30/30 agree
```

Como ler: `truth` é o gabarito e `graph` é o que o banco diz. `OK` quer dizer
que batem. Como foram calculados por caminhos independentes, **a
concordância valida os dois ao mesmo tempo**: é muito improvável que dois
programas diferentes errem do mesmo jeito.

Se aparecer `DIFF`, não se escolhe automaticamente quem está certo. Olha-se o
dado bruto do lance em questão e descobre-se qual dos dois caminhos tem o
defeito. Foi assim que se encontraram os problemas de "passes tentados" e
"defesas do goleiro" (capítulo 7).

Para conferir uma pergunta só: `python scripts/check_ground_truth.py --question s03`.

---

## 3.7 Como mudar ou acrescentar uma pergunta

1. Edite `config/questions.yaml`. Respeite as regras de 3.2 e mantenha 6 por
   tipo (troque uma pergunta por outra, em vez de só acrescentar).
2. Se a pergunta é nova, acrescente o cálculo da resposta em
   `benchmark/ground_truth.py` (função `compute`) e a consulta equivalente em
   `scripts/check_ground_truth.py` (função `graph_answer`).
3. Recalcule e confira:
   ```bash
   python -m football_graphrag.benchmark.ground_truth   # grava data/benchmark/ground_truth.json
   python scripts/check_ground_truth.py                 # tem de dar 30/30
   pytest tests/test_questions.py tests/test_scoring.py
   ```
4. As linhas antigas dessa pergunta em `data/benchmark/results.jsonl` ficam
   inválidas. Apague-as do arquivo (uma linha por execução, com o campo
   `"question_id"`) e rode `python scripts/run_benchmark.py --resume`: ele refaz
   só o que falta.

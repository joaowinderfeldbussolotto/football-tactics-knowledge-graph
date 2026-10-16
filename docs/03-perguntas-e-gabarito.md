# 3. Perguntas e gabarito

Um benchmark só vale o que valem as respostas certas dele. Este capítulo
explica como as perguntas foram escritas, onde elas ficam, como a resposta
certa de cada uma é calculada, como se testa se ela não depende da leitura da
pergunta e como se confere o cálculo.

---

## 3.1 Onde ficam as perguntas: `config/questions.yaml`

As perguntas ficam num arquivo de configuração, separado do código:
[`config/questions.yaml`](../config/questions.yaml). Uma entrada tem esta
cara:

```yaml
  - id: s01
    type: network_slice
    stage: pilot
    check: player
    text: >-
      Na prorrogação, quem foi o principal elo da circulação de bola da França?
```

O que cada campo quer dizer:

| Campo | Para que serve |
|---|---|
| `id` | identificador curto. A letra diz o tipo: **f** (fact), **a** (filtered_aggregation), **n** (network), **s** (network_slice), **t** (structure), **c** (counterfactual), **q** (sequence), **p** (play), **b** (substitution), **u** (unanswerable) |
| `type` | o tipo da pergunta (tabela abaixo) |
| `stage` | se a pergunta entra na execução (`pilot`, `full`, `graph`), fica de reserva (`candidate`) ou saiu no teste de robustez (`removed`) |
| `check` | **como** a resposta é conferida (tabela abaixo) |
| `tolerance` | opcional. Margem aceita para números contínuos. Contagens são exatas e não usam |
| `text` | a pergunta, **exatamente** como vai para o modelo |
| `note` | um comentário para quem lê o arquivo; numa pergunta removida, o motivo. **Nunca vai para o modelo** |

No topo do arquivo, `active_stages` diz quais estágios entram na execução.
Hoje são `[pilot, full, graph]`: **52 perguntas ativas**. O arquivo tem 81
perguntas escritas: as 52 ativas, 22 removidas no teste de robustez e 7
reservas (`candidate`). As 25 primeiras (`pilot` e `full`, 5 de cada um dos
cinco primeiros tipos) foram as das rodadas iniciais; as 27 de `graph` vieram
depois, com os tipos que exploram jogadas, substituições e a estrutura da
rede.

Os tipos:

| `type` | O que a pergunta exige |
|---|---|
| `fact` | achar um evento: quem cometeu a falta do pênalti, quem deu o passe do gol |
| `filtered_aggregation` | filtrar, contar e ordenar, com recorte: "na prorrogação", "depois do 2 a 2", "enquanto vencia por 2 a 0" |
| `network` | um conceito de rede de passes na partida inteira: dupla, elo, sequência de três |
| `network_slice` | um conceito de rede num recorte, ou comparando recortes |
| `structure` | a estrutura da rede de passes: quem, se saísse, deixaria companheiros isolados |
| `counterfactual` | "se fulano não estivesse em campo": a rede recalculada sem um jogador |
| `sequence` | o que acontece imediatamente antes de uma ação: o penúltimo passe, o passe antes do chute |
| `play` | jogadas inteiras (posses de bola): onde começam, aonde chegam, como terminam, quem participa |
| `substitution` | antes e depois de uma substituição: como a circulação de bola mudou |
| `unanswerable` | parece respondível com eventos, mas os dados não têm o que é pedido |

Para os resultados, os tipos são reunidos em **cinco grupos**, mais fáceis de
explicar:

| Grupo | Tipos | Perguntas |
|---|---|---|
| Busca e contagem | `fact`, `filtered_aggregation` | 11 |
| Relações na rede de passes | `network`, `network_slice`, `structure`, `counterfactual` | 20 |
| Jogadas e sequências | `sequence`, `play` | 10 |
| Antes e depois de um momento do jogo | `substitution` | 6 |
| Controle: sem resposta | `unanswerable` | 5 |

Os grupos ficam em `benchmark/questions.py` (`GROUPS`).

Os tipos de conferência (`check`):

| `check` | A resposta está certa quando... | Exemplo |
|---|---|---|
| `player` | o **primeiro** jogador da resposta é o esperado | "Quem cometeu mais faltas no segundo tempo?" |
| `value` | o número é o esperado | "Quantas finalizações a Argentina fez depois do 2 a 2?" |
| `set` | o **conjunto** de jogadores é o esperado, em qualquer ordem | "Qual dupla da França mais trocou passes?" |
| `player_and_value` | jogador **e** número estão certos | "Qual jogador acertou mais passes durante o 2 a 0, e quantos?" |
| `no_data` | o modelo disse que os dados não respondem | "Quantos minutos Messi passou no campo de ataque?" |

O arquivo é **validado ao carregar** (`benchmark/questions.py`). O programa se
recusa a rodar se:
- houver id repetido;
- houver tipo, `check` ou `stage` desconhecido;
- a letra do `id` não bater com o tipo;
- uma pergunta removida não disser o motivo;
- algum tipo não somar `per_type` perguntas ativas.

---

## 3.2 As regras para escrever uma pergunta

Cada regra existe para evitar um jeito específico de o benchmark medir a
coisa errada.

**1. Fechada e com resposta única.** "Quem", "quantos", "quais", nunca
"explique". Uma pergunta aberta precisaria de alguém, ou de outro LLM,
julgando a resposta. Com pergunta fechada, a correção é um `if`.

**2. Linguagem de futebol, sem definição operacional.** A pergunta fala como
um comentarista: "o principal elo da circulação de bola", "a dupla que mais
trocou passes", "a sequência de três jogadores que mais se repetiu". Ela não
diz como calcular ("A passa para B na mesma posse, sem outro passe no meio").
O teste `tests/test_questions.py` falha se alguma pergunta usar nome de
ferramenta ou de algoritmo ("betweenness", "pagerank", "rede", "grafo",
"xT", "pass_paths" etc.).

**3. Sem copiar a descrição de uma ferramenta.** As ferramentas do
`graph_tools` têm descrições em inglês com a leitura de cada métrica no
futebol (capítulo 4). Uma pergunta que traduzisse esse texto ao pé da letra
apontaria a ferramenta para o modelo. A checagem é manual.

**4. Ferramentas antes das perguntas.** As ferramentas são escritas e
fixadas antes de se escreverem as perguntas que as testam. Nenhuma
ferramenta é criada para uma pergunta. Um teste
(`tests/test_tools_frozen.py`) guarda um hash das definições.

**5. Estável em todas as leituras.** Sem definição no texto, a mesma
pergunta pode ser lida de mais de um jeito. A resposta é calculada em todas
as leituras razoáveis (3.4). Se ela muda, a pergunta sai; não se conserta
acrescentando definição ao texto.

**6. Nada que dependa de onde as fontes discordam.** "Passes tentados" e
"defesas do goleiro" têm números diferentes no JSON bruto e na camada 0
(capítulo 9), então não são perguntados.

**7. Sem dados quer dizer sem dados em nenhuma fonte.** As perguntas
`unanswerable` pedem algo que nem os dados 360 da StatsBomb têm: tempo em
cada parte do campo, distância percorrida, velocidade, impedimento passivo.

**8. Empate não desclassifica.** Se, numa leitura, dois jogadores empatam,
a resposta certa aceita qualquer um deles, ou os dois juntos. A pergunta só
sai se a resposta **muda** de uma leitura para outra; um empate dentro de uma
leitura não muda a resposta, só a deixa com mais de uma forma certa (campo
`accepted` do gabarito, capítulo 5).

---

## 3.3 As 52 perguntas e as respostas certas

Nomes encurtados aqui; o gabarito usa o nome completo de registro. "ou"
separa respostas igualmente certas (empate dentro de uma leitura).

### Busca e contagem (11)

| id | Pergunta | Resposta certa |
|---|---|---|
| f01 | Quem recebeu o primeiro cartão amarelo da final? | Enzo Fernández |
| f02 | Quem cometeu a falta que deu origem ao primeiro pênalti da final? | Dembélé |
| f03 | No lance do gol de Messi na prorrogação, o goleiro francês tinha feito uma defesa instantes antes. Quem deu o chute que ele defendeu? | Lautaro Martínez |
| f04 | Quem deu o passe para o gol que deixou o placar em 2 a 2 no tempo normal? | Marcus Thuram |
| f05 | Quem fez a última finalização da França na final, antes da disputa de pênaltis? | Kolo Muani |
| a01 | Quem deu mais passes certos no terço final do campo pela Argentina? | Messi |
| a02 | Quem deu mais passes certos no terço final do campo pela França? | Rabiot |
| a03 | Depois do gol que deixou o placar em 2 a 2 no tempo normal, quantas finalizações a Argentina fez até o fim da prorrogação? | 10 |
| a05 | Enquanto a Argentina vencia por 2 a 0, qual jogador argentino acertou mais passes, e quantos? | Enzo Fernández, 26 |
| a06 | Na prorrogação, quem fez mais desarmes certos pela Argentina? | Enzo Fernández |
| a07 | No segundo tempo, quem cometeu mais faltas? | Julián Álvarez |

### Relações na rede de passes (20)

| id | Pergunta | Resposta certa |
|---|---|---|
| n03 | Na troca de passes da Argentina, qual jogador, se não estivesse em campo, deixaria algum companheiro sem trocar passes com ninguém do time? | Otamendi |
| n04 | Qual dupla da França mais trocou passes entre si na final? | Upamecano e Varane |
| n05 | Qual dupla da Argentina mais trocou passes entre si na final? | Romero e Otamendi |
| n06 | Qual jogador da Argentina trocou passes com o maior número de companheiros diferentes na final? | Enzo Fernández |
| n09 | Qual sequência de três jogadores da França, com a bola passando de um para o outro, mais se repetiu na final? | Upamecano, Koundé e Varane |
| n11 | Para cortar a bola que chega a Messi, preciso saber: qual companheiro mais passou a bola para ele na final? | De Paul |
| n12 | Para marcar Mbappé, preciso saber: qual companheiro mais passou a bola para ele na final? | Theo Hernández |
| s01 | Na prorrogação, quem foi o principal elo da circulação de bola da França? | Koundé |
| s03 | Depois do gol que deixou o placar em 2 a 2 no tempo normal, qual dupla da França mais trocou passes entre si? | Koundé e Varane |
| s04 | A dupla da Argentina que mais trocou passes entre si no primeiro tempo continuou sendo a principal no segundo tempo? Qual foi a dupla que mais trocou passes no segundo tempo? | Enzo Fernández e De Paul |
| s06 | No segundo tempo, qual companheiro mais recebeu passes de Enzo Fernández? | De Paul |
| s07 | Na prorrogação, qual sequência de três jogadores da Argentina, com a bola passando de um para o outro, mais se repetiu? | Romero, Enzo Fernández e Otamendi |
| s09 | Na prorrogação, qual jogador da Argentina trocou passes com o maior número de companheiros diferentes? | Enzo Fernández |
| s10 | No campo de ataque, pelo lado direito, quais dois jogadores da Argentina mais trocaram passes entre si? | Messi e De Paul |
| s11 | No campo de ataque, pelo lado esquerdo, quem foi o jogador da Argentina mais procurado pelos companheiros? | Mac Allister |
| s12 | Enquanto a França perdia por 2 a 0, quem foi o jogador francês mais procurado pelos companheiros? | Upamecano |
| s13 | Depois do gol que deixou o placar em 2 a 2 no tempo normal, quem passou a ser o jogador da França mais procurado pelos companheiros? | Koundé |
| t06 | Na prorrogação, qual jogador da França, se não estivesse em campo, deixaria algum companheiro sem trocar passes com ninguém do time? | Koundé |
| c01 | Se Enzo Fernández não estivesse em campo, quem passaria a ser o principal elo da circulação de bola da Argentina? | Otamendi |
| c02 | Sem Otamendi em campo, algum companheiro da Argentina ficaria sem trocar passes com ninguém do time? Quem? | Pezzella |

### Jogadas e sequências (10)

| id | Pergunta | Resposta certa |
|---|---|---|
| q01 | Qual jogador argentino mais vezes finalizou logo depois de receber um passe de um companheiro? | Lautaro Martínez |
| q03 | Quem deu mais vezes o penúltimo passe nas jogadas da Argentina que terminaram em finalização? | Julián Álvarez |
| p01 | Quais dois jogadores argentinos mais vezes participaram juntos das mesmas jogadas que chegaram ao terço final? | Enzo Fernández e Messi |
| p02 | Qual jogador participou de mais jogadas da Argentina que começaram no próprio campo de defesa e terminaram em finalização? | Messi |
| p03 | Qual jogador participou de mais jogadas da Argentina que terminaram em finalização? | Messi |
| p04 | Qual jogador participou de mais jogadas da França que terminaram em finalização? | Mbappé |
| p05 | Nas jogadas da Argentina que terminaram em finalização e em que Messi tocou na bola, qual companheiro mais participou junto com ele? | Enzo Fernández |
| p06 | Nas jogadas da França que terminaram em finalização e em que Mbappé tocou na bola, qual companheiro mais participou junto com ele? | Rabiot |
| p07 | Quais dois jogadores franceses mais vezes participaram juntos das mesmas jogadas que chegaram ao terço final? | Rabiot e Tchouaméni ou Rabiot e Mbappé |
| p08 | Quem participou de mais jogadas da França que levaram a bola da defesa até o terço final no segundo tempo? | Kolo Muani |

### Antes e depois de um momento do jogo (6)

| id | Pergunta | Resposta certa |
|---|---|---|
| b02 | Depois que Di María foi substituído, qual companheiro mais passou a bola para Messi? | Enzo Fernández |
| b03 | Depois que Dembélé foi substituído no primeiro tempo, qual companheiro mais passou a bola para Mbappé? | Rabiot |
| b05 | Depois que Dembélé foi substituído no primeiro tempo, para qual companheiro Mbappé mais passou a bola? | Kolo Muani |
| b06 | Depois que Dembélé foi substituído no primeiro tempo, qual dupla francesa mais trocou passes entre si? | Koundé e Varane |
| b07 | Depois que Di María foi substituído, qual companheiro mais recebeu passes de Messi? | Enzo Fernández |
| b09 | Depois que Di María foi substituído, quem passou a ser o jogador da Argentina mais procurado pelos companheiros? | Enzo Fernández |

### Controle: sem resposta (5)

| id | Pergunta | Resposta certa |
|---|---|---|
| u01 | Quantos minutos Messi passou no campo de ataque durante a final? | sem dados |
| u02 | Qual foi a distância total percorrida por Rodrigo De Paul na final? | sem dados |
| u03 | Quantos piques em alta velocidade Mbappé deu na prorrogação? | sem dados |
| u04 | A que velocidade saiu o chute de Mbappé no gol que deixou o placar em 2 a 2? | sem dados |
| u05 | Em quantos lances Mbappé ficou em posição de impedimento sem participar da jogada? | sem dados |

Nas sequências de três jogadores, a conferência é por conjunto: a ordem não
é conferida. Na s04, só a dupla do segundo tempo é conferida. Além do
`check_ground_truth.py`, `scripts/check_cypher.py` responde as 47 perguntas
com resposta com uma consulta Cypher escrita à mão para cada uma, e as 47
batem com o gabarito. O arquivo de
perguntas tem também as reservas estáveis e as removidas, cada uma com o
motivo. As respostas calculadas ficam em `data/benchmark/ground_truth.json`.

---

## 3.4 A regra de ouro do gabarito: nunca ler o banco avaliado

O braço `graph_tools` consulta o Neo4j, e o `stats_in_prompt` recebe números
que vêm do Neo4j. Se o gabarito também viesse do Neo4j, um erro no banco
apareceria **dos dois lados**: o braço erraria, o gabarito erraria igual, e o
erro contaria como acerto.

Por isso o gabarito (`benchmark/ground_truth.py`) é calculado por **outro
caminho**:

1. **O JSON bruto da StatsBomb**, sempre que a definição é simples:
   - gol = evento `Shot` com resultado `Goal`;
   - cartão amarelo = cartão dentro de `foul_committed` **ou** de
     `bad_behaviour` (o de Giroud, por reclamação, está no segundo);
   - pênalti = falta marcada como pênalti em `foul_committed`;
   - assistência = passe marcado com `goal_assist`;
   - drible completo = evento `Dribble` com resultado `Complete`;
   - falta = evento `Foul Committed`; finalização = evento `Shot`.

   A disputa de pênaltis (período 5) é sempre excluída.

2. **A tabela da camada 0 (Parquet)**, quando a definição é da própria
   camada 0 (desarme certo, passe com recebedor) e para tudo o que envolve
   redes e sequências de passes. As redes são calculadas com **networkx**,
   uma biblioteca Python de grafos; as sequências, com pandas.

Conferência com a súmula oficial da FIFA: 6 gols (aos 23', 36', 80', 81',
108' e 118' da transmissão) e 7 cartões amarelos com a bola rolando. O 8º
amarelo, de Emiliano Martínez, foi na disputa de pênaltis e fica fora.

---

## 3.5 O teste de robustez: a mesma resposta em todas as leituras

Uma pergunta em linguagem de futebol pode ser lida de mais de um jeito.
"Passes" inclui laterais e bolas paradas? "Depois do gol" inclui o próprio
gol? Para cada pergunta, o gabarito calcula a resposta em **todas as
leituras razoáveis**:

| Eixo | Leituras | Onde se aplica |
|---|---|---|
| Conjunto de passes | todos os passes certos · só passes de bola rolando | tudo o que conta passes |
| Peso da ligação | nenhum · número de passes · xT | "principal elo" |
| Direção | passador → recebedor · as duas direções somadas | duplas, elos, companheiros |
| Companheiros | nas duas direções · só para quem passou · só de quem recebeu | "companheiros diferentes" |
| Recorte no tempo | com o evento que define o corte · sem ele | "depois de", "enquanto" |
| Terço | onde o passe começa · onde termina | "no terço final" |
| Sequências | mesma posse ou não · passes consecutivos ou não | "sequência de três" |
| Fonte | JSON bruto · camada 0 | quando as duas servem |

A pergunta fica só se **alguma resposta está certa em todas as leituras**,
naquilo que a conferência olha: o jogador, o conjunto ou o número. Empate
dentro de uma leitura não desclassifica: todos os empatados no topo valem
naquela leitura. A resposta aceita é a que está no topo em todas. Exemplo:
"quem mais passou a bola para Mbappé" dá Theo 8 × Rabiot 7 contando todos
os passes e 7 × 7 só com bola rolando; Theo está no topo nas duas leituras e
é a resposta aceita, Rabiot não. Mais de uma resposta aceita só acontece
quando elas empatam em todas as leituras (p07). O que tira a pergunta é
leituras que discordam sem ninguém no topo de todas.

Um exemplo que saiu e um que ficou, ambos sobre o "principal elo da
circulação de bola":

| Pergunta | Leituras | Respostas |
|---|---|---|
| Quem era o principal elo da circulação de bola da Argentina? | 12 | Otamendi em 9, Enzo Fernández em 3: **saiu** |
| Na prorrogação, quem foi o principal elo da circulação de bola da França? | 12 | Koundé em todas: **ficou** |

Das 40 perguntas escritas, 9 saíram por esse teste. Todas as leituras de
todas as perguntas estão em
[`data/benchmark/robustness.md`](../data/benchmark/robustness.md), gerado por
`scripts/robustness_report.py`.

---

## 3.6 Os conceitos de rede, sem fórmula

Para cada time, monta-se uma **rede de passes**:
- cada jogador é um **nó**;
- se A deu pelo menos um passe certo para B, existe uma **ligação A → B**;
- cada ligação guarda quantos passes houve e quanto xT eles geraram somados.

A ligação Mac Allister → Di María, por exemplo, inclui o passe do gol, que
gerou 0,184 de xT.

Sobre essa rede, as perguntas usam quatro ideias:

**Dupla que mais trocou passes.** A ligação mais forte, somando ou não as
duas direções do par.

**Companheiros diferentes.** Com quantos colegas um jogador trocou pelo
menos um passe: é o grau do jogador na rede.

**Principal elo da circulação: a betweenness.** Imagine quatro jogadores em
linha, onde a bola só anda assim:

```
Goleiro → Zagueiro → Volante → Atacante
```

Para ir do Goleiro ao Atacante, a bola **tem** de passar pelo Zagueiro e pelo
Volante. Se contarmos, para cada par de jogadores, quem fica no meio do
caminho mais curto, o Zagueiro e o Volante aparecem várias vezes e o Goleiro
e o Atacante nenhuma. Essa contagem é a **betweenness**. Ter muitas rotas
passando por você não é o mesmo que dar muitos passes.

**Jogador sem o qual alguém fica isolado.** Um jogador cuja saída deixaria
algum companheiro sem trocar passes com ninguém é um **ponto de
articulação** da rede. Na final, é Otamendi: Pezzella, que entrou no fim, só
trocou passes com ele.

**Sequência de três jogadores.** A passa para B, e B, no passe seguinte que
tenta, acha C. As leituras variam a exigência de mesma posse e de nenhum
outro passe entre os dois.

O GDS do Neo4j e o networkx calculam a betweenness com a mesma convenção
(valores brutos, não normalizados), e os testes confirmam que os dois batem
nas seis combinações de peso e direção.

---

## 3.7 Conferindo o gabarito contra o grafo

O gabarito foi calculado sem o Neo4j. Para conferi-lo, cada pergunta é
respondida de novo **pelas ferramentas do `graph_tools`**, com uma sequência
fixa de chamadas, sem LLM:

```bash
python scripts/check_ground_truth.py           # as 52 perguntas ativas
python scripts/check_ground_truth.py --all     # também as reservas
```

Saída (trecho):

```
OK  s01  ground truth: ['Jules Koundé']  |  graph (tools): ['Jules Koundé']
OK  n09  ground truth: ['Dayotchanculle Upamecano', 'Jules Koundé', 'Raphaël Varane']  |  graph (tools): [...]
OK  u01  no data expected; the tools expose only on-ball events
...
52/52 agree
```

Como os dois lados foram calculados por caminhos independentes, **a
concordância valida os dois ao mesmo tempo**. Ela mostra também que as
ferramentas bastam para responder cada pergunta: cada sequência de chamadas
do script é uma solução possível.

---

## 3.8 Como mudar ou acrescentar uma pergunta

1. Escreva a pergunta em `config/questions.yaml`, seguindo as regras de 3.2.
2. Acrescente a função da resposta em `benchmark/ground_truth.py`, com
   todas as leituras razoáveis, e a sequência de chamadas equivalente em
   `scripts/check_ground_truth.py`.
3. Recalcule e confira:
   ```bash
   python -m football_graphrag.benchmark.ground_truth   # grava ground_truth.json
   python scripts/robustness_report.py                  # tabela de leituras
   python scripts/check_ground_truth.py                 # tem de concordar em todas
   pytest tests/test_questions.py
   ```
4. Se a resposta mudar com a leitura, marque `stage: removed` e escreva o
   motivo em `note`. O teste falha se uma pergunta ativa for instável.

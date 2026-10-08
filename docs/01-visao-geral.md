# 1. Visão geral: o que este projeto mede e por quê

## A pergunta

Imagine que você tem o registro completo de uma partida de futebol: cada
passe, cada chute, cada falta, quem fez, onde e quando. Na final da Copa do
Mundo de 2022 (Argentina x França), isso dá cerca de **4.400 eventos** num
arquivo JSON fornecido gratuitamente pela StatsBomb.

Agora alguém quer fazer perguntas sobre o jogo em português comum:

- "Quem deu a assistência para o segundo gol da França?"
- "Quem fez mais desarmes certos?"
- "Por qual jogador da Argentina passava a maior parte das rotas de passe?"

Um modelo de linguagem (LLM, como o ChatGPT ou o Claude) entende a pergunta,
mas não viu o jogo. Ele precisa receber os dados de algum jeito. A pergunta
deste projeto é:

> **Qual é a melhor forma de entregar esses dados ao modelo para que ele
> responda certo?**

Existem quatro jeitos comuns de fazer isso, e o benchmark compara os quatro,
mais um controle sem dado nenhum. Cada jeito é chamado de **braço** (como os
braços de um experimento científico: grupos que recebem tratamentos
diferentes e são comparados entre si).

## Os cinco braços, explicados com uma analogia

Pense num jornalista que precisa responder perguntas sobre o jogo. Os braços
são cinco jornalistas que recebem materiais diferentes:

| Braço | O jornalista recebe... | Na prática, o modelo recebe... |
|---|---|---|
| `no_context` | nada; responde de cabeça | só a pergunta |
| `vector` | as 30 fichas do arquivo que mais se parecem com a pergunta | as 30 linhas da tabela de eventos com texto mais parecido com a pergunta |
| `events_in_prompt` | o arquivo inteiro do jogo, lance por lance | uma tabela com todos os 2.585 lances da partida (~63 mil tokens) |
| `stats_in_prompt` | a súmula estatística pronta | uma tabela com as estatísticas de cada jogador e de cada time |
| `graph_tools` | um analista com um banco de dados, a quem pode fazer até 8 consultas | ferramentas (*tools*) que consultam um banco de dados em grafo |

Alguns detalhes que importam:

- **`no_context` é o controle.** Ele mostra o que o modelo "sabe de memória".
  Como a final de 2022 é famosa, o modelo provavelmente sabe que Messi fez o
  primeiro gol. Esse braço separa o que vem dos dados do que vem da memória.
- **`vector` é o jeito mais comum hoje** (chamado de RAG vetorial). Cada linha
  da tabela vira um vetor de números que representa o "sentido" do texto, e
  a pergunta também. As linhas cujos vetores mais se parecem com o da
  pergunta vão para o modelo. É rápido e barato, mas só traz pedaços.
- **`events_in_prompt` é a força bruta.** Tudo vai para o modelo, que precisa
  contar e cruzar sozinho, lendo milhares de linhas.
- **`stats_in_prompt` entrega o trabalho já feito**: contagens prontas por
  jogador e por time. Responde bem o que foi pré-calculado e não responde o
  que não foi.
- **`graph_tools` deixa o modelo investigar.** Ele recebe ferramentas como
  "ranking de uma estatística" ou "quem conecta a rede de passes do time" e
  decide quais chamar, com quais argumentos, até ter a resposta.

**A única diferença entre os braços é o que o modelo recebe.** O modelo é o
mesmo, as instruções são as mesmas, a temperatura é zero (o modelo escolhe
sempre a resposta mais provável, sem sortear) e o formato da resposta é o
mesmo. Se um braço acerta mais, é por causa dos dados que recebeu.

## Os cinco tipos de pergunta

São 25 perguntas, 5 de cada tipo. Os tipos existem porque cada braço deve ir
bem em algumas e mal em outras, e o interessante é ver onde cada um quebra.

| Tipo | O que exige | Exemplo real do benchmark | Resposta |
|---|---|---|---|
| `fact` | achar um evento | "Quem cometeu a falta que deu origem ao primeiro pênalti da final?" | Dembélé |
| `filtered_aggregation` | filtrar, contar e ordenar, com recorte | "Enquanto a Argentina vencia por 2 a 0, qual jogador argentino acertou mais passes, e quantos?" | Enzo Fernández, 26 |
| `network` | um conceito de rede de passes na partida inteira | "Qual dupla da França mais trocou passes entre si na final?" | Upamecano e Varane |
| `network_slice` | um conceito de rede num recorte do jogo | "Na prorrogação, quem foi o principal elo da circulação de bola da França?" | Koundé |
| `unanswerable` | perceber que o dado não existe | "Quantos minutos Messi passou no campo de ataque durante a final?" | `no_data` |

Por que cada tipo é difícil:

- **fact**: basta achar a linha certa, mas é preciso achá-la, muitas vezes
  em relação a outro momento ("a falta que deu origem ao pênalti"). O
  `vector` pode trazer as linhas erradas.
- **filtered_aggregation**: exige localizar um recorte do jogo ("enquanto
  vencia por 2 a 0") e contar dezenas de eventos dentro dele sem errar.
- **network**: a resposta não está em nenhuma linha nem em nenhuma contagem
  simples. Ela vem de olhar a rede de passes inteira (quem passa para quem).
- **network_slice**: o mesmo, num pedaço do jogo, ou comparando dois
  pedaços. Dois jeitos de errar: o recorte e a rede.
- **unanswerable**: o certo é dizer "não tenho esse dado". As perguntas
  parecem respondíveis com eventos, mas pedem algo que só um rastreamento
  contínuo dos jogadores teria (tempo em cada parte do campo, velocidade,
  distância). O erro típico é aproximar com outra medida, como contar
  conduções no lugar de piques.

As perguntas falam como um comentarista e não dizem como calcular. Para isso
não criar ambiguidade, cada resposta certa é calculada em todas as leituras
razoáveis da pergunta, e só ficam as perguntas em que todas concordam
(capítulo 3).

## Como se sabe se a resposta está certa

Cada pergunta tem um **gabarito** (a resposta certa), calculado por código a
partir dos dados brutos, **sem usar o banco de dados que os braços
consultam**. Assim o gabarito não herda um possível erro do sistema avaliado.
O gabarito também é conferido contra o banco, pelas ferramentas do
`graph_tools`: as 25 respostas batem.

Cada resposta do modelo é conferida **por código, não por outro modelo**. O
modelo responde num formato fixo (lista de jogadores, um número, ou "sem
dados") e um programa compara com o gabarito. Não existe "meio certo" nem
opinião: está certo ou errado. Detalhes no
[capítulo 5](05-conferencia-e-metricas.md).

## O que sai no fim

Depois de rodar as 25 perguntas nos 5 braços (com 1 ou mais repetições), o
projeto gera um resumo (`summary.md`) com:

1. **acerto por tipo de pergunta e por braço**, a tabela principal, com o
   total com e sem as perguntas sem resposta;
2. **tipos de erro por braço**: alucinação (respondeu errado com
   confiança), abstenção (disse "sem dados" quando havia) e erro de formato;
3. **consistência**: se o mesmo braço dá a mesma resposta nas repetições;
4. **custo**: tokens e tempo médios por pergunta.

## Mapa da documentação

| Capítulo | O que explica |
|---|---|
| 1. Visão geral | este texto |
| [2. Dos dados ao grafo](02-dos-dados-ao-grafo.md) | o caminho do JSON bruto até o banco de dados, acompanhando o gol de Di María |
| [3. Perguntas e gabarito](03-perguntas-e-gabarito.md) | como as perguntas são escritas (o arquivo YAML) e como a resposta certa é calculada e conferida |
| [4. Os cinco braços](04-os-cinco-bracos.md) | exatamente o que cada braço envia ao modelo, com trechos reais |
| [5. Conferência e métricas](05-conferencia-e-metricas.md) | como cada resposta é corrigida e como ler o `summary.md` |
| [6. Como rodar](06-como-rodar.md) | passo a passo do zero, no computador ou no Docker, com saídas esperadas e solução de problemas |
| [7. Decisões e limitações](07-decisoes-e-limitacoes.md) | as escolhas feitas, os problemas encontrados nos dados e o que o benchmark não mede |
| [8. Glossário](08-glossario.md) | todos os termos técnicos, em linguagem simples |

Se é sua primeira vez aqui, leia na ordem. Se só quer rodar, vá direto ao
[capítulo 6](06-como-rodar.md).

# 9. Todas as transformações dos dados

Este capítulo lista, em ordem, tudo o que acontece com os dados desde o JSON
bruto da StatsBomb até o texto que cada braço entrega ao modelo. Cada item diz
**o que** a transformação faz, **onde** está no código e, quando não é óbvio,
**por quê**. Os capítulos 2 e 4 contam a mesma história com exemplos; este é a
referência completa.

O caminho tem quatro trechos:

```text
JSON bruto ──► camada 0 (tabela de ações) ──► camadas 1 e 1b (Neo4j) ──► o que cada braço vê
                    │                                                        ▲
                    └──────────────── tabela de eventos ─────────────────────┘
```

O gabarito faz um caminho próprio a partir do JSON bruto e da camada 0
(seção 9.6).

---

## 9.1 A origem: o JSON bruto

| Arquivo | Conteúdo |
|---|---|
| `data/raw/statsbomb/events/3869685.json` | ~4.400 eventos da final, cada um com tipo, tempo, time, jogador e local |
| `data/raw/statsbomb/lineups/3869685.json` | escalações, com nome e apelido de cada jogador |

Nos eventos da StatsBomb, o local de cada evento é dado **do ponto de vista
de quem age**: o time que executa a ação sempre ataca no sentido de x
crescente, num campo de 120 × 80.

A **disputa de pênaltis (período 5) é descartada** em todo o projeto: ela não
é jogo corrido e não entra em nenhuma contagem.

---

## 9.2 Camada 0: de eventos para uma tabela de ações

Código: `src/football_graphrag/ingestion/` (orquestrado por `pipeline.py`).
Saída: `data/processed/3869685.parquet` (uma linha por ação) e arquivos
auxiliares (`_phases`, `_windows`, `_pressures`, `_meta`).

### 1. Leitura (`statsbomb_loader.py`)

A biblioteca `kloppy` lê os eventos e as escalações num modelo comum a vários
fornecedores. Todos os tipos de evento são lidos; o período 5 sai aqui.

### 2. Conversão para SPADL (`spadl_transform.py`)

A biblioteca `socceraction` converte os eventos em **ações SPADL**:

- só ficam ações com bola, num vocabulário fechado de ~23 tipos; eventos
  auxiliares (recepção, início de tempo, pressão, bloqueio...) saem;
- cada ação ganha os mesmos campos: tempo no período, time, jogador,
  coordenadas de início e fim, tipo, resultado (certo ou errado) e parte do
  corpo;
- as coordenadas passam para metros, num campo de 105 × 68;
- a própria biblioteca ajusta cortes e insere **conduções** entre duas ações
  do mesmo jogador quando a bola se moveu com ele.

Os ~4.400 eventos viram 2.585 ações.

### 3. Toda ação atacando da esquerda para a direita (`spadl_transform.py::_play_left_to_right`)

A conversão a partir da `kloppy` entrega o mandante (Argentina) atacando para
a direita nos períodos ímpares, e os lados trocam a cada período. A camada 0
espelha (x → 105 − x, y → 68 − y, no início e no fim) as ações do mandante
nos períodos pares e as do visitante nos ímpares. Depois disso, em toda ação,
x alto significa "perto do gol adversário" e "esquerda" é a esquerda de quem
ataca.

Dois testes garantem isso: cada ação está no mesmo lugar que no JSON bruto (a
menos do arredondamento da escala), e toda finalização está no terço de
ataque.

### 4. Nomes

O nome do jogador e do time vêm do carregador local do `socceraction`, pelo
id.

### 5. xT, ameaça esperada (`spadl_transform.py::add_xt`)

O campo é dividido numa grade de 12 × 8 células, e cada célula tem um valor:
a chance de uma posse que passa por ali terminar em gol. O xT de uma ação é
`valor(célula final) − valor(célula inicial)`. Ele só é calculado para
**passes, cruzamentos e conduções certos**; as demais ações recebem 0.

A grade é ajustada uma vez nos 16 jogos do mata-mata da Copa 2022, com as
ações desses jogos também postas da esquerda para a direita, e guardada em
`data/models/xt_fitted_12x8.json`.

### 6. VAEP (`spadl_transform.py::add_vaep`)

Outro valor por ação: quanto ela mudou a chance de o time marcar
(componente ofensivo) e de sofrer gol (defensivo) nas ações seguintes. Vem de
um modelo de aprendizado de máquina treinado uma vez nos mesmos 16 jogos.
Esse modelo espera o formato original do SPADL (mandante para a direita,
visitante para a esquerda) e vira as ações por conta própria. Por isso as
ações do visitante são espelhadas de volta só para essa conta.

### 7. Zonas (`tactical_metrics.py::add_zones`)

Cada ação ganha `zone_start` e `zone_end`, a célula de início e de fim na
grade de 12 colunas × 8 linhas: `zona = coluna × 8 + linha`. A coluna 0 fica
junto ao próprio gol e a 11 junto ao gol adversário.

### 8. Fases de posse (`tactical_metrics.py::add_possession_phases`)

`possession_id` numera sequências de ações seguidas do mesmo time. Uma fase
nova começa quando muda o time, quando muda o período, ou depois de uma
ação que encerra a jogada: falta, finalização, defesa do goleiro, corte ou
erro de domínio. A final tem 537 fases.

### 9. Passe progressivo (`tactical_metrics.py::add_progressive_flag`)

Um passe ou condução certo é **progressivo** se aproximou a bola do centro
do gol adversário em pelo menos 30 m (começando e terminando no próprio
campo), 15 m (cruzando o meio-campo) ou 10 m (todo no campo adversário).
Definição da Wyscout.

### 10. Recebedor do passe (`tactical_metrics.py::add_pass_receivers`)

O recebedor de um passe certo é o jogador **do mesmo time** que executa a
ação seguinte. Se a ação seguinte é do adversário, o passe fica sem
recebedor.

### 11. Métricas de time e tabelas auxiliares (`tactical_metrics.py`, `pressure_events.py`)

| Métrica | Como é calculada |
|---|---|
| Resumo por fase de posse | por fase: time, período, início e fim, zona inicial e final, xT somado, número de ações |
| Janelas móveis | PPDA e field tilt em janelas de 10 minutos, de 5 em 5 |
| Pressões | lidas direto do JSON bruto (eventos "Pressure"): quem pressionou quem, onde e quando |
| PPDA | passes do adversário nos primeiros 60% do campo dele (x ≤ 63 m) ÷ ações defensivas do time nesse mesmo espaço (x ≥ 42 m, do ponto de vista dele). Quanto menor, mais pressão. Calculado no 1º e no 2º tempo |
| Field tilt | passes do time no terço final (x ≥ 70 m) ÷ passes dos dois times no terço final de cada um |

### 12. Vocabulário de futebol (`football_semantics.py::add_football_semantics`)

| Coluna | Regra |
|---|---|
| `acao` | o tipo SPADL traduzido: `pass` → `passe`, `dribble` → `conducao`, `take_on` → `drible`, `tackle` → `desarme`, `keeper_save` → `defesa_do_goleiro`, etc. (23 valores) |
| `grupo_acao` | agrupamento: `passe` (passe, cruzamento, lateral, tiro de meta), `bola_parada` (escanteios e faltas cobradas), `finalizacao`, `conducao`, `drible`, `defensiva`, `infracao`, `erro`, `goleiro` |
| `sucesso` | resultado SPADL "success" |
| `minuto` | minuto da transmissão: começo do período (0, 45, 90, 105) + minutos completos no período + 1. Os acréscimos continuam a contagem (o 1º tempo vai até 53') |
| `segundo` | relógio de jogo em segundos: começo do período (0, 2700, 5400, 6300) + segundos no período |
| `periodo_nome` | "1º tempo", "2º tempo", "1ª prorrogação", "2ª prorrogação" |
| `gol` | finalização (chute, pênalti, falta direta) certa |
| `cartao_amarelo` | resultado SPADL "yellow_card" |
| `corpo` | parte do corpo, em português |
| `terco` | pela zona inicial: colunas 0–3 `defesa`, 4–7 `meio`, 8–11 `ataque` |
| `corredor` | pela zona inicial, olhando para o gol adversário: linhas 0–2 `direita`, 3–4 `centro`, 5–7 `esquerda` |

### 13. O que o SPADL perde, recuperado do JSON bruto (`football_semantics.py::enrich_from_statsbomb`)

A junção é pelo id do evento original, que a conversão preserva.

- **Desfecho da finalização** (`desfecho`, `no_gol`): `gol`, `defendida`,
  `para_fora`, `na_trave` ou `bloqueada`. No gol = gol ou defendida.
- **Cartão por reclamação**: o SPADL só vê cartão que veio com uma falta. O
  amarelo de Giroud por reclamação vira uma linha própria, com a ação
  `cartao_por_reclamacao`.

### Diferenças conhecidas entre o JSON e a camada 0

- Alguns passes do JSON não viram ação SPADL. Os passes certos batem; os
  tentados ficam 1 ou 2 abaixo em alguns jogadores.
- Uma saída do goleiro para afastar a bola é classificada como defesa: Lloris
  tem 8 defesas na camada 0 e 7 no JSON.

---

## 9.3 Camadas 1 e 1b: o grafo no Neo4j

Código: `src/football_graphrag/graph/build.py` e `statistics.py`. Nada é
calculado de novo: cada linha da camada 0 vira nó ou aresta.

| No grafo | Vem de |
|---|---|
| `Jogador`, `Time`, `Partida`, `Zona` (96), `FaseDePosse` (537) | camada 0 e escalações |
| `REALIZOU` (jogador → partida) | uma por ação, com as colunas de futebol da camada 0 (ação, sucesso, minuto, segundo, período, gol, cartão, desfecho, terço, corredor, zona, xT, VAEP, fase) |
| `PASSOU_PARA` (jogador → jogador) | uma por passe **certo e com recebedor**, dos tipos de passe (passe, cruzamento, lateral, tiro de meta, escanteios e faltas cobradas); guarda xT, zonas e fase |
| `DEU_ASSISTENCIA` | para cada gol, o último passe ao autor do gol na mesma fase de posse |
| `FINALIZOU`, `PRESSIONOU`, `ATUOU_EM`, `PARTICIPOU_DE`, `PROGREDIU_PARA` | finalizações, pressões, ações por zona, jogadores por fase, progressões entre zonas |
| `EstatisticaJogador`, `EstatisticaTime` (camada 1b) | a súmula, contada pelo próprio Neo4j sobre as arestas acima (toques, passes, desarmes, faltas, finalizações, xT, PPDA, field tilt...) |

A camada 2 (`PadraoTatico`) existe no banco, mas **nenhum braço a lê**.

---

## 9.4 O que cada braço recebe

### `no_context`

Nada além da pergunta.

### A tabela de eventos (`events_in_prompt` e `vector`)

Código: `benchmark/arms.py::event_lines`. Uma linha CSV por ação da camada 0,
2.585 linhas:

1. **Ordem:** período, tempo no período, número da ação. O cartão
   recuperado do JSON entra no lugar certo do jogo, não no fim.
2. **Colunas:** `period, minute, team, player, action, success, receiver,
   zone_from, zone_to, possession, outcome, score`.
3. **`receiver`:** o nome do recebedor do passe (passo 10), vazio nas demais
   ações.
4. **`outcome`:** junta, separados por `+`:
   - `goal(A-F)`, com o placar **depois** do gol (Argentina-França);
   - `yellow_card`;
   - o desfecho da finalização, quando não é gol (`defendida`, `bloqueada`,
     `para_fora`).
5. **`score`:** o placar **antes** da ação, Argentina-França. Na linha de um
   gol, `score` mostra o placar antes dele e `outcome` o placar que ele fez:
   ```text
   1,36,Argentina,Ángel Fabián Di María Hernández,finalizacao,1,,92,91,132,goal(2-0),1-0
   ```
6. Antes da tabela vai uma legenda em inglês que explica cada coluna.

O `events_in_prompt` recebe a tabela inteira (~110 mil tokens). O `vector`
recebe **30 linhas**:
- cada linha é transformada uma vez num vetor (embedding), guardado em cache;
- a pergunta também vira um vetor;
- vão para o modelo as 30 linhas de maior similaridade de cosseno com a
  pergunta, reordenadas na ordem do jogo e com a mesma legenda.

### A súmula (`stats_in_prompt`)

Código: `benchmark/arms.py::stats_table`. Lida do Neo4j (camada 1b): uma linha
por time e uma por jogador, com todos os campos, menos os de identificação
interna. Antes das tabelas vai um glossário de cada campo
(`tools.STAT_GLOSSARY`).

### As ferramentas (`graph_tools`)

Código: `benchmark/tools.py` (consultas) e `benchmark/arms.py` (descrições que
o modelo lê). O modelo não recebe dados: chama ferramentas, que consultam o
Neo4j e devolvem dados.

**Filtros comuns** (`query_actions`, `list_actions`, `pass_network`,
`pass_paths`), aplicados sobre `REALIZOU`:

| Filtro | Regra |
|---|---|
| `team`, `player` | time e jogador de quem agiu. Nome completo, apelido ou sobrenome único; um nome ambíguo devolve os candidatos |
| `action` | um ou mais valores do vocabulário da camada 0 |
| `success` | ação certa ou errada |
| `period` | um ou mais períodos (1 a 4) |
| `second_from`, `second_to` | janela de **tempo contínuo**, em segundos desde o apito inicial, sem intervalos. Cada período começa onde a última ação do anterior terminou. Comparado com 3 casas decimais, a mesma precisão que o `list_actions` mostra |
| `third`, `corridor` | terço e corredor de início da ação (passo 12), em inglês |
| `goal`, `yellow_card` | marcas da ação |
| `assist` | o passe que deu a assistência: o último passe recebido pelo autor do gol na mesma fase de posse |

**As sete ferramentas:**

| Ferramenta | O que calcula |
|---|---|
| `list_players` | jogadores com pelo menos uma ação, com time e posição |
| `query_actions` | conta as ações filtradas (ou soma o xT delas), agrupadas por jogador, recebedor, time, ação, período, terço ou corredor; da maior para a menor |
| `list_actions` | as ações filtradas, em ordem: período, minuto, segundo contínuo, time, jogador, ação, sucesso, recebedor, terço, corredor, `score` (placar antes da ação, "Argentina 2-1 France") e `outcome` (num gol, com o placar depois: "goal (score after: Argentina 2-2 France)"). Até 100 linhas, mais o total encontrado |
| `pass_network` | a rede de passes de um time: os passes certos entre companheiros que passam nos filtros, somados por par passador → recebedor (número de passes e xT). Devolve um identificador, o time e os filtros usados |
| `network_metric` | uma métrica sobre a rede, calculada pelo Neo4j GDS |
| `network_edges` | as ligações da rede (passador, recebedor, passes, xT), da mais forte para a mais fraca; com um jogador, só as dele |
| `pass_paths` | sequências de passes em que cada passe sai de quem recebeu o anterior. O elo é o próximo passe que o recebedor tenta, e a sequência para se esse passe errar. Conta as sequências de jogadores mais repetidas |

**Detalhes do `network_metric`:**

- **Projeção sob demanda:** a cada chamada, a rede é projetada no GDS,
  calculada e descartada.
- **Direção:**
  - `directed`: mantém passador → recebedor;
  - `undirected`: soma as duas direções de cada par numa ligação só.
- **Peso na betweenness:** vira comprimento de caminho:
  - `none`: toda ligação mede 1;
  - `passes`: 1/passes;
  - `xt`: 1/(1+xT).
- **Peso no grau, PageRank e comunidades:** vira força: o número de passes,
  ou o xT com totais negativos contados como zero.
- **Pontes e pontos de articulação:** sempre sem peso e sem direção.
- **Comunidades:** algoritmo Louvain, sem direção; os grupos podem variar
  entre chamadas.
- **Grau na rede direcionada:** devolve saídas e entradas separadas.

**Detalhes do `pass_paths`:**

- `players` é o número de jogadores na sequência, de 3 a 5 (3 = A → B → C).
- `same_possession` exige que toda a sequência esteja na mesma fase de
  posse.
- `consecutive` exige que não haja nenhum outro passe, de ninguém, entre
  dois passes ligados.
- Os filtros escolhem só o primeiro passe da sequência.
- Um jogador pode se repetir (A → B → A).

**Execução:**

- O modelo chama uma ferramenta por vez, até 8 por pergunta; da 9ª em
  diante, recebe "limite atingido".
- Argumento inválido volta como mensagem de erro, para o modelo corrigir.

### O que vale para todos os braços

- **Mesmo modelo,** com temperatura 0.
- **Mesmo formato de resposta:** raciocínio, jogadores, número e "sem
  dados". O formato recusa resposta vazia.
- **Mesma instrução de sistema.** Ela diz que as perguntas são sobre uma
  partida, sem dizer qual. Manda responder só com os dados
  fornecidos e marcar "sem dados" quando eles não têm **exatamente** o que a
  pergunta pede, sem trocar por outra medida aproximada.

---

## 9.5 Nomes de jogadores

Os dados usam o nome completo da StatsBomb ("Lionel Andrés Messi
Cuccittini"). Para conferir respostas e resolver nomes nas ferramentas,
`scoring.py` monta apelidos a partir das escalações:

- valem o nome completo e o apelido;
- vale também o sobrenome, mas **só quando é único** na partida.
  "Martínez" é ambíguo (Lautaro e Emiliano) e não resolve sozinho.

A comparação ignora acentos e maiúsculas.

---

## 9.6 O gabarito: um caminho à parte

Código: `benchmark/ground_truth.py`. O gabarito **nunca lê o Neo4j**:

- fatos e contagens simples vêm do JSON bruto;
- contagens que dependem de definições da camada 0 (desarme certo, passe
  com recebedor) vêm do Parquet;
- redes e sequências são calculadas com `networkx` e pandas, sobre o Parquet.

Cada pergunta é respondida em **todas as leituras razoáveis**, combinando:

| Eixo | Leituras |
|---|---|
| Conjunto de passes | todos os passes certos · só passes de bola rolando (`passe`) |
| Peso da ligação | nenhum · número de passes · xT |
| Direção | passador → recebedor · as duas direções somadas |
| Recorte no tempo | com o evento que define o corte · sem ele |
| Terço | onde o passe começa · onde termina |
| Sequências | mesma posse ou não · passes consecutivos ou não |
| Fonte | JSON bruto · camada 0 |

Uma pergunta só fica no benchmark se alguma resposta está certa em todas as
leituras, naquilo que a conferência olha. Num empate dentro de uma leitura,
todos os empatados no topo valem naquela leitura; as respostas aceitas
(campo `accepted` do gabarito) são as que estão no topo em todas. As
leituras de cada pergunta estão em `data/benchmark/robustness.md`.

A conferência cruzada (`scripts/check_ground_truth.py`) responde cada
pergunta de novo pelas ferramentas do `graph_tools`, com uma sequência fixa
de chamadas, e compara com o gabarito.

# O benchmark por dentro

> Dado um JSON de eventos de futebol, qual a melhor forma de permitir
> perguntas em linguagem natural: vetorizar, colocar tudo no prompt, colocar
> dados processados no prompt, ou deixar o LLM percorrer um grafo via tools?

Este documento explica como as respostas certas são calculadas, como cada
resposta do modelo é conferida, quanto custa cada braço, as decisões tomadas
no caminho e as limitações. Comandos para rodar estão no [README](../README.md).

## 1. Os cinco braços

Todos usam o mesmo modelo (do `.env`), o mesmo prompt de sistema,
`temperature=0` e a mesma saída estruturada (`Answer`, via tool de saída do
PydanticAI). A única diferença é o que o modelo recebe.

| Braço | O modelo recebe | Fonte |
|---|---|---|
| `no_context` | só a pergunta | – |
| `vector` | as 30 linhas de evento mais parecidas com a pergunta (cosseno, numpy) | Parquet da camada 0 |
| `events_in_prompt` | a tabela de todos os 2.585 eventos da final | Parquet da camada 0 |
| `stats_in_prompt` | as estatísticas por jogador e por time | Neo4j, camada 1b |
| `graph_tools` | 8 tools com Cypher fixo, no máximo 8 chamadas por pergunta | Neo4j, camadas 1 e 1b + GDS ao vivo |

O prompt de sistema (em inglês, como todo o código; as perguntas são em
português) manda responder **só com os dados fornecidos** e marcar
`no_data` quando eles não bastarem. No braço `no_context` isso significa que
o certo seria responder `no_data` a quase tudo. Ele mede quanto o modelo
desobedece e responde de memória.

**Tamanho do primeiro pedido** (pergunta c01; tokens contados com `o200k`, o
tokenizador do modelo real pode diferir uns 10–20%):

| Braço | Tokens |
|---|---|
| `no_context` | ~340 |
| `graph_tools` | ~1.200 (inclui as definições das 8 tools; cada chamada de tool soma um novo pedido) |
| `vector` | ~1.300 |
| `stats_in_prompt` | ~3.200 |
| `events_in_prompt` | ~63.000 |

O `events_in_prompt` cabe em modelos com contexto de 128k. Para trocar para
um modelo de 32k, esse braço precisa sair (`--arms`).

### As tools do `graph_tools`

Genéricas, não uma por pergunta, e devolvem dados e rankings, não a resposta
pronta. Nenhuma lê os nós `PadraoTatico` da camada 2: as estruturais calculam
na hora, com as mesmas projeções do GDS que a camada 2 usa.

| Tool | O que devolve |
|---|---|
| `list_players(team)` | jogadores, posição e toques |
| `player_stats(name)` | a súmula de um jogador (aceita apelido e sobrenome único) |
| `team_stats(team)` | a súmula de um time |
| `stat_ranking(stat, team=None, top=5)` | ranking por uma estatística |
| `events(event_type, team=None)` | gols, assistências, cartões, finalizações, faltas, desarmes etc., em ordem |
| `pass_network_centrality(team, top=5)` | betweenness da rede de passes (GDS, custo 1/(1+xT)) |
| `three_player_sequences(team, top=5)` | trios A→B→C progressivos mais frequentes |
| `pass_network_bridges(team)` | pontes e comunidades Louvain da rede não direcionada |

Argumento ruim (time inexistente, nome ambíguo como "Martínez", estatística
desconhecida) volta como mensagem de erro para o modelo corrigir, não como
exceção. Da 9ª chamada em diante, a tool responde "limite atingido, responda
com o que tem". Se o modelo insistir, o limite de 12 pedidos encerra a
execução e ela conta como erro de formato.

## 2. As 30 perguntas

São 6 por tipo, todas fechadas ("quem", "quantos", "quais"). A lista completa
está em `src/football_graphrag/benchmark/questions.py`; as respostas, em
`data/benchmark/ground_truth.json`.

| Tipo | Exige | Exemplo |
|---|---|---|
| `factual` | achar um fato | f03: "Quem deu a assistência para o segundo gol da França?" → Marcus Thuram |
| `aggregation` | contar e ordenar | a01: "Quem fez mais desarmes certos? Top 3" → Enzo, Tagliafico, Camavinga |
| `structural` | algoritmo de grafo | s03: "Quem tinha a 2ª maior betweenness da Argentina?" → Enzo Fernandez |
| `composite` | estrutural + agregação | c05: "Quantos passes certos o pivô da Argentina deu ao 2º de betweenness?" → 14 |
| `unanswerable` | perceber que o dado não existe | u03: "Quem foi eleito o melhor jogador da final?" → `no_data` |

Só f01 (primeiro gol) e f02 (número de gols) têm resposta amplamente
conhecida. As perguntas estruturais e compostas trazem a definição do
conceito no próprio texto ("o jogador com maior betweenness centrality na
rede de passes certos do time, ponderada pelo xT"), para que todos os braços
recebam a mesma pergunta autoexplicativa.

## 3. Como o gabarito é calculado

**Regra central: o gabarito nunca é lido do Neo4j.** Ele vem de um caminho
independente do sistema avaliado (`benchmark/ground_truth.py`):

- **JSON bruto do StatsBomb** (`source: raw_json`): gols, cartões,
  assistências (`pass.goal_assist`), finalizações, faltas, dribles completos e
  passes certos (passe sem `outcome`). A disputa de pênaltis (período 5) fica
  de fora.
- **Parquet da camada 0** (`source: parquet`): o que depende de uma definição
  da camada 0. O único caso é "desarme certo" (`acao == 'desarme'` e
  `sucesso`, de `ingestion/football_semantics.py`).
- **networkx sobre o Parquet** (estruturais): réplica exata da projeção do
  GDS (`graph/projections.py::pass_network`). A rede é direcionada, por time,
  com uma aresta por par (a,b) e `cost = 1/(1+xt_total)`. A betweenness usa
  `normalized=False`, porque o GDS devolve o valor bruto. Os trios replicam o
  Cypher de `terceiro_homem` linha a linha. As compostas misturam as duas
  fontes (`source: parquet+raw_json`).

O código **recusa empates**: se a pergunta pede "o primeiro" e há empate
nessa posição, o cálculo levanta erro em vez de escolher um.

Conferência com a súmula oficial da FIFA: 6 gols (minutos 23, 36, 80, 81,
108 e 118 de transmissão) e 7 amarelos com a bola rolando. O 8º amarelo, de
Emiliano Martínez, foi na disputa de pênaltis. O campo `minute` do StatsBomb é
minuto decorrido (22, 35, 79…); a coluna `minuto` da camada 0 soma 1.

### Checagem cruzada

`python scripts/check_ground_truth.py` põe lado a lado o gabarito e o que o
grafo responde por consultas Cypher fixas (camadas 1, 1b e 2, e o GDS rodado
na hora para o 2º colocado em betweenness, que a camada 2 não guarda).
Resultado: **30/30 batem**. Como os dois caminhos são independentes, a
concordância valida o gabarito e o grafo ao mesmo tempo. É só para isso que a
camada 2 (`run_analysis.py`) continua no fluxo.

## 4. Conferência das respostas

Todo braço responde no mesmo modelo:

```python
class Answer(BaseModel):
    rationale: str        # escrito primeiro, de propósito; nunca é conferido
    players: list[str]    # nomes completos; rankings em ordem
    value: float | None   # um número, sem unidade
    no_data: bool         # só quando os dados não respondem
```

| `check` | Certo quando |
|---|---|
| `player` | o primeiro de `players` é o jogador esperado |
| `value` | `abs(value - esperado) <= tolerance` (contagens: exato) |
| `set` | o conjunto de `players` é igual ao esperado, em qualquer ordem |
| `player_and_value` | as duas condições acima |
| `no_data` | `no_data == True` |

- **Abstenção**: responder `no_data` numa pergunta que tem resposta. Conta
  como erro, mas aparece separada da alucinação.
- **Alucinação**: resposta errada que não é abstenção nem erro de formato.
  Numa pergunta sem resposta, qualquer coisa diferente de `no_data` é
  alucinação.
- **Erro de formato**: sem `Answer` válido depois de 2 retries de saída (ou
  com o limite de pedidos estourado). Aparece em linha própria no
  `summary.md`.
- **Nomes**: o dicionário de apelidos vem das escalações do StatsBomb
  (`player_name` e `player_nickname`), mais o sobrenome sozinho **só quando
  ele é único na partida**. "Messi", "Di María", "Kolo Muani" e "Enzo
  Fernández" valem. "Martínez" (Lautaro ou Emiliano) e "Hernández" (Theo ou
  Di María) não valem. A comparação ignora acentos e maiúsculas.

Nenhum LLM dá nota. A conferência é código (`benchmark/scoring.py`), coberta
por `tests/test_scoring.py`, que também confere que o gabarito acerta 30/30
contra si mesmo.

## 5. Decisões tomadas no caminho

1. **`ligacao_fragil` ficou fora das perguntas.** A final não tem nenhuma
   ponte nas redes de passes, então o padrão cai no fallback de comunidades
   Louvain. Rodando o Louvain do networkx com sementes de 0 a 4, as
   comunidades mudam de uma semente para outra, e o GDS também não é
   determinístico. Um gabarito que depende de semente não é gabarito. As
   6 estruturais usam só betweenness (`pivo_estrutural`) e o padrão de
   caminho (`terceiro_homem`). A tool `pass_network_bridges` continua
   disponível para o modelo.
2. **Achado na camada 0, não corrigido: defesas do goleiro.** O JSON bruto
   tem 7 eventos "Shot Saved" de Lloris; o Parquet tem 8 `keeper_save`.
   A conversão SPADL classificou um "Keeper Sweeper Clear" (minuto 107) como
   defesa. A súmula do grafo herda o 8, e o golden antigo dizia 8. Pela regra
   do plano (camadas 0 a 2 não mudam), a pergunta foi evitada e o achado fica
   registrado aqui.
3. **"Passes tentados" também foi evitado.** O SPADL descarta alguns passes do
   JSON bruto: Enzo tem 94 no bruto e 92 no Parquet, Koundé 67 e 66. "Passes
   certos" bate nas duas fontes e foi o usado. "Passes errados" só aparece
   para Otamendi (c01), onde as duas fontes dão 6.
4. **A tabela de eventos tem duas colunas além das listadas no plano**:
   `possession`, porque o trio progressivo é definido "na mesma posse", e
   `outcome` (gol, cartão amarelo, resultado da finalização), porque gols e
   cartões são flags da ação e sem elas o braço não teria esses fatos. A
   tabela continua sem nada agregado. As zonas vêm com uma legenda de uma
   linha (`terço = zona // 32`).
5. **O braço `vector` indexa as mesmas linhas da tabela de eventos**, uma
   linha por documento. Os embeddings são calculados em lotes de 100 (cerca
   de 26 pedidos) e ficam em cache em `data/benchmark/cache/`, que não é
   versionado.
6. **Erro do provedor não vira linha.** Depois dos retries do próprio SDK, um
   erro de rede ou de API é avisado e não entra no `results.jsonl`, e
   `--resume` o refaz. Já uma resposta que nunca valida no schema entra, como
   erro de formato.
7. **`run_benchmark.py` não sobrescreve resultados pagos.** Se o arquivo já
   tem linhas, ele exige `--resume` ou `--fresh`.

## 6. Limitações

- **Uma partida só, 30 perguntas.** Seis por tipo é pouco para separar
  braços com diferença pequena: cada pergunta vale 17 pontos percentuais
  dentro do tipo.
- **Mede correção da resposta, não qualidade da explicação tática.** O
  `rationale` não é avaliado.
- **O gabarito estrutural usa o Parquet da camada 0.** O xT, que pesa a rede
  de passes, vem do modelo treinado na pipeline. Por isso a checagem valida as
  camadas 1 e 2, não a 0. Um erro na camada 0 (como o das defesas do goleiro)
  passaria igual pelo gabarito e pelo grafo.
- **As tools do `graph_tools` foram desenhadas por quem escreveu as
  perguntas.** Elas são genéricas, mas `pass_network_centrality` e
  `three_player_sequences` existem porque há perguntas estruturais. Um
  usuário real não teria tools sob medida.
- **As perguntas estruturais e compostas explicam o conceito** (betweenness,
  trio progressivo). Isso ajuda todos os braços igualmente, mas é uma ajuda
  que uma pergunta espontânea não teria.
- **Um único modelo de LLM.** O resultado vale para o modelo do `.env` no
  dia da execução (registrado em cada linha do `results.jsonl`).
- **Tokens aproximados.** Os tamanhos da seção 1 usam um tokenizador
  genérico. Os números de custo do `summary.md` vêm do uso que o provedor
  reporta.

## 7. Histórico

O sistema anterior (API FastAPI, Graphiti, juízes LLM, avaliação com três
braços) está documentado em [`docs/legado/`](legado/). A refatoração para
benchmark tirou tudo o que não respondia a pergunta acima.

# 10 — Roteiro de testes manuais

Um passeio guiado pelo app. São **28 casos**: você roda, compara com o resultado
esperado, e ao fim de cada um entende uma peça do sistema. Não precisa saber
Cypher nem algoritmo de grafo — cada caso traz o comando pronto.

> **Sobre os números.** Todo valor marcado como *esperado* nos casos
> **[grátis]** foi conferido contra o grafo real (Copa 2022: final, semifinal e
> quartas) na hora de escrever este documento. Nos casos **[LLM]**, o que está
> escrito é *o que uma resposta correta precisa conter* — essa parte também vem
> do grafo, mas a **redação** do modelo muda a cada chamada, então confira os
> **fatos**, nunca o texto. Esses casos eu **não** rodei ao vivo (sem a chave do
> provedor, sem gastar API).

## O app em um minuto

Você faz uma pergunta sobre uma partida. O app:

1. **Acha o que importa**: reconhece nomes de jogadores/times na pergunta e
   busca no grafo os *padrões táticos* e as *estatísticas* deles. Perguntas
   como "quem fez os gols?" disparam uma *ficha do jogo*.
2. **Entrega isso ao modelo de linguagem**, que escreve a resposta. O modelo
   também pode consultar o grafo diretamente (a ferramenta `consultar_grafo`).
3. **Exige citação**: toda métrica que a resposta usa aponta para um padrão que
   existe no grafo, e toda consulta que o modelo fez fica registrada.
4. **Confere sozinho**: a *fidelidade* verifica se as citações existem e se as
   consultas reexecutam.

Quatro palavras que aparecem o tempo todo:

| Termo | O que é |
|---|---|
| **Padrão tático** (`PadraoTatico`) | Um achado calculado por algoritmo de grafo, sem IA — ex.: "Otamendi é o gargalo da rede de passes". |
| **Súmula** (`EstatisticaJogador/Time`) | Contagens prontas por jogador e por time (passes, desarmes, posse…). |
| **Betweenness** | Quão "obrigatório" um jogador é como ponte entre os outros na rede de passes. Alto = a bola passa por ele. |
| **Fidelidade** | Teste automático: as citações existem no grafo? As consultas reexecutam? **Não** diz que a resposta está *certa*. |

## Mapa dos casos

| # | O que você vê | Custo |
|---|---|---|
| 1–9 | O grafo por dentro (Neo4j Browser) | grátis |
| 10–14 | A API sem modelo de linguagem | grátis |
| 15–21 | Perguntar ao app e conferir | LLM |
| 22–25 | Tentar fazer o app errar | LLM |
| 26–28 | Conferir o conferidor | grátis |

**Custo dos casos [LLM]:** centavos. Medi ~US$ 0,012 por pergunta da avaliação
(3 braços + juízes), o que dá ~US$ 0,37 para as 30 — uma **estimativa**, não um
custo medido de uma rodada inteira. Um `/ask` avulso é uma fração disso (não
medi um isolado).

---

## Antes de começar

**1. Neo4j de pé.**

```bash
docker compose up -d neo4j
docker compose ps          # neo4j deve aparecer "healthy"
```

**2. Neo4j Browser.** Abra `http://localhost:7474` (no Codespace: aba *Ports* →
porta 7474). Conexão `bolt://localhost:7687`, usuário `neo4j`, senha
`changeme` (ou o `NEO4J_PASSWORD` do seu `.env`). Os casos 1–9 e 27 se colam
lá (o 26 é um script).

**3. As camadas montadas.** Se o grafo estiver vazio, `scripts/local_setup.sh`
monta tudo de graça (ver `06-reproduzir.md`, seção 6c).

**4. A API**, para os casos 10 em diante:

```bash
# no container:
docker compose up -d
# ou direto no host (útil se o container não resolve nomes):
source .venv/bin/activate
uvicorn football_graphrag.api.main:app --port 8000
```

Painel interativo em `http://localhost:8000/docs`. Os exemplos abaixo usam
`curl`; o `| python -m json.tool` só deixa a saída legível.

**5. Para os casos [LLM]**, o `.env` precisa de `LLM_PROVIDER`, `LLM_API_KEY` e
`LLM_MODEL`. As chaves de embeddings (`EMBEDDER_*`) só servem à busca híbrida;
sem índice do Graphiti o app funciona igual, apenas sem ela.

A partida que usamos quase sempre é a **final: `match_id = 3869685`**
(Argentina × França). As outras duas: `3869519` (semifinal, Argentina ×
Croácia) e `3869354` (quartas, França × Inglaterra).

---

# Parte 1 — O grafo por dentro  `[grátis]`

Cole cada consulta no Neo4j Browser. Aqui não há IA: é o dado puro.

### Caso 1 — O que existe no grafo da final?

**Entenda:** o grafo tem camadas; cada tipo de nó tem um papel.

```cypher
MATCH (n) WHERE n.match_id = 3869685
RETURN labels(n)[0] AS tipo, count(*) AS quantidade ORDER BY quantidade DESC
```

**Esperado:** `FaseDePosse` 537 · `EstatisticaJogador` 34 · `PadraoTatico` 24 ·
`EstatisticaTime` 2 · `Partida` 1.

**Repare:** `Jogador`, `Time` e `Zona` não aparecem — são compartilhados entre
as três partidas e por isso não têm `match_id`.

### Caso 2 — Quem fez os gols?

**Entenda:** o fato bruto, a um passo, sem agregação.

```cypher
MATCH (j:Jogador)-[f:FINALIZOU {match_id: 3869685}]->(:Partida)
WHERE f.gol
RETURN j.nome AS jogador, j.time AS time, f.minuto AS minuto, f.acao AS acao
ORDER BY f.periodo, f.minuto
```

**Esperado — 6 linhas:** Messi 23' (pênalti) · Di María 36' · Mbappé 80'
(pênalti) · Mbappé 81' · Messi 108' · Mbappé 118' (pênalti).

**Repare:** o `minuto` é o da transmissão — o 2º tempo começa em 45. A disputa
de pênaltis **não** está no grafo; só os quatro períodos em campo.

### Caso 3 — Cartões amarelos

```cypher
MATCH (j:Jogador)-[r:REALIZOU {match_id: 3869685}]->(:Partida)
WHERE r.cartao_amarelo
RETURN j.nome AS jogador, j.time AS time, r.minuto AS minuto
ORDER BY r.periodo, r.minuto
```

**Esperado — 7 linhas:** Enzo Fernández 52' · Rabiot 55' · Thuram 87' ·
Giroud 95' · Acuña 98' · Paredes 114' · Montiel 116'.

**Repare:** o 8º amarelo da partida (do goleiro Martínez) foi na disputa de
pênaltis — fora do grafo. Um app honesto responde **7**, não 8.

### Caso 4 — A súmula bate com a conta feita à mão?

**Entenda:** a súmula é uma conveniência. Ela só vale se for idêntica à
contagem direta nas arestas.

```cypher
// (a) o número pronto
MATCH (e:EstatisticaJogador {match_id: 3869685}) WHERE e.nome CONTAINS 'Enzo'
RETURN e.desarmes_certos AS certos, e.desarmes_tentados AS tentados
```

```cypher
// (b) contado na unha, nas arestas
MATCH (j:Jogador)-[r:REALIZOU {match_id: 3869685, acao: 'desarme'}]->(:Partida)
WHERE j.nome CONTAINS 'Enzo'
RETURN count(r) AS tentados, sum(CASE WHEN r.sucesso THEN 1 ELSE 0 END) AS certos
```

**Esperado:** as duas dão **5 certos de 9 tentados**.

**Repare:** "desarme certo" e "desarme tentado" são campos separados de
propósito. Contar tentativas como acertos já gerou uma resposta errada neste
projeto ("Enzo fez 9") — ver caso 24.

### Caso 5 — Ver a rede de passes

**Entenda:** a base de todos os padrões estruturais. Aqui você *enxerga* a rede.

```cypher
MATCH (a:Jogador)-[p:PASSOU_PARA {match_id: 3869685}]->(b:Jogador)
WHERE a.time = 'Argentina' AND b.time = 'Argentina'
RETURN a, b, count(p) AS passes
```

No Browser, clique em **Graph** (e não em Table) para ver o desenho.

**Esperado:** 17 jogadores, 129 pares ligados. A ligação mais forte é
**Otamendi → Romero: 18 passes**.

### Caso 6 — Os padrões que o algoritmo achou

**Entenda:** a camada 2. Cada linha é um achado calculado, sem IA.

```cypher
MATCH (p:PadraoTatico {match_id: 3869685})
RETURN p.tipo AS tipo, count(*) AS quantidade ORDER BY quantidade DESC
```

**Esperado — 24 no total:** `mudanca_estado` 8 · `terceiro_homem` 6 ·
`papel_divergente` 3 · `pivo_estrutural` 2 · `gatilho_pressao` 2 ·
`ligacao_fragil` 2 · `assimetria_construcao` 1.

### Caso 7 — O gargalo de cada time

```cypher
MATCH (p:PadraoTatico {match_id: 3869685, tipo: 'pivo_estrutural'})
RETURN p.time AS time, p.descricao_curta AS achado,
       p.valor_metrica AS valor, p.algoritmo_origem AS algoritmo, p.uid AS uid
```

**Esperado:**

| Time | Quem | Betweenness | 2º colocado | uid começa com |
|---|---|---|---|---|
| Argentina | Otamendi | **50.0** | 25.0 | `148ff0f8` |
| França | Koundé | **40.0** | 25.0 | `531ccd7a` |

**Repare:** gargalo é uma medida de **posição na rede** (quem liga os outros),
não de volume. Koundé tem 133 ações — empatado no topo com Tchouaméni, também
133 —, mas muita ação não faz ninguém ser ponte; o que o algoritmo mede é onde o
jogador está no desenho. Esse tipo de achado não existe em nenhuma linha de
tabela; só aparece rodando o algoritmo na rede. O `uid` é o que as respostas do
app citam (casos 15–16 e 27).

### Caso 8 — O tempo muda o padrão (e nada é apagado)

```cypher
MATCH (p:PadraoTatico {match_id: 3869685, tipo: 'mudanca_estado'}) WHERE p.time = 'Argentina'
RETURN p.descricao_curta AS achado, p.valid_at AS valido_de, p.invalid_at AS invalido_em
ORDER BY p.valid_at
```

**Esperado — 4 linhas.** Bloco baixo até o minuto 50 (PPDA 15.4), que
**vira** pressão alta a partir do 50 (PPDA 5.2). Também: campo cedido até o
minuto 20 (field tilt 42%) e domínio territorial a partir daí (68%).

**Repare:** o estado antigo tem `invalido_em = 50.0`, **não foi deletado**. É o
modelo bitemporal: o app sabe o que era verdade *antes* da mudança.

### Caso 9 — Quando a escalação mente

```cypher
MATCH (p:PadraoTatico {match_id: 3869685, tipo: 'papel_divergente'})
RETURN p.descricao_curta AS achado
```

**Esperado — 3 linhas.** Entre elas: **Theo Hernández** (escalado Left Back)
agrupado pela rede de passes com a linha de ataque (92 ações); **Molina**
(Right Back) idem (88 ações); **Dembélé** (Right Wing) com a defesa (27).

**Repare:** a posição "oficial" diz uma coisa; o que o jogador *fez* diz outra.
É um achado que só a topologia da rede revela.

---

# Parte 2 — A API sem modelo de linguagem  `[grátis]`

Aqui você testa o encanamento: nada chama LLM, nada custa.

### Caso 10 — A API está viva?

```bash
curl -s localhost:8000/health
```

**Esperado:** `{"status":"ok","llm":"<provedor>:<modelo>"}` — o `llm` mostra o
que está no seu `.env`. `503` aqui significa Neo4j fora do ar.

### Caso 11 — Contagens da final pela API

```bash
curl -s localhost:8000/graph/3869685/stats | python -m json.tool
```

**Esperado:** `FaseDePosse` 537 · `EstatisticaJogador` 34 · `PadraoTatico` 24 ·
`REALIZOU` 2585 · `PASSOU_PARA` 989 · `PRESSIONOU` 301 · `FINALIZOU` 30 ·
`DEU_ASSISTENCIA` 2.

**Repare:** `Jogador` aparece como **68** e `Time` como **4** — não é a final,
são os nós compartilhados entre as três partidas (a final tem 34 jogadores; veja
`EstatisticaJogador`). É uma pegadinha de leitura, não um erro.

### Caso 12 — Refazer a camada 2

```bash
curl -s -X POST localhost:8000/analyze/3869685 | python -m json.tool
```

**Esperado:** em ~5 s, `200` e `{"match_id": 3869685, "padroes_por_tipo": {...}}`
com os 24 padrões do caso 6. **Sem custo e sem LLM.**

**Repare:** esta rota **só** recalcula os padrões. Ela não toca no índice do
Graphiti — já tocou, apagava o índice e repagava tudo, e foi retirado de lá
(ADR-13).

### Caso 13 — Sem chave de LLM

Com o `LLM_API_KEY`/`LLM_MODEL` vazios no `.env`:

```bash
curl -s localhost:8000/report/3869685
curl -s -X POST localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"match_id": 3869685, "pergunta": "teste"}'
```

**Esperado — `503` nas duas:** `LLM_API_KEY/LLM_MODEL ausentes no .env: este
endpoint usa o agente de verbalização (camada 3)`.

**Repare:** as camadas 0, 1 e 2 funcionam sem nenhuma chave. Só a camada 3 usa LLM.

### Caso 14 — Partida que não existe

Com as chaves de LLM configuradas (qualquer valor serve — não chama o modelo):

```bash
curl -s localhost:8000/report/999
```

**Esperado — `404`:** `sem padrões para 999; rode /analyze antes`.

---

# Parte 3 — Perguntar ao app  `[LLM]`

```bash
curl -s -X POST localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"match_id": 3869685, "pergunta": "SUA PERGUNTA"}' | python -m json.tool
```

**Como ler a resposta:**

| Campo | O que é |
|---|---|
| `resposta` | A resposta em linguagem técnica de tática. |
| `em_bom_portugues` | A mesma coisa, sem jargão. |
| `metricas_citadas` | Os padrões em que a resposta se apoia (`padrao_tatico_id` = o `uid` do caso 7). |
| `consultas_executadas` | As consultas que o modelo fez no grafo — cada uma pode ser reexecutada (caso 27). |
| `confianca` | `alta`, `media` ou `baixa`. |

Em todos os casos abaixo: **confira os fatos, não o texto**.

### Caso 15 — Pergunta estrutural: o gargalo da Argentina

**Pergunte:** `Qual jogador foi o gargalo estrutural da progressão da Argentina na final?`

**Resposta correta contém:** **Otamendi**, betweenness **50.0**, o dobro do 2º
colocado (25.0). Em `metricas_citadas`, um `padrao_tatico_id` que começa com
`148ff0f8`.

**Valide:** compare com o caso 7.

**Sinal de alerta:** outro jogador, ou número diferente de 50.0.

### Caso 16 — O mesmo, para a França

**Pergunte:** `Por qual jogador da França passavam os caminhos de progressão do time?`

**Resposta correta contém:** **Koundé**, betweenness **40.0** (2º: 25.0), `uid`
começando com `531ccd7a`.

**Cuidado com uma armadilha na referência do projeto:** a resposta de referência
desta pergunta diz que ele "não é o jogador de mais toques do time". Hoje isso
**não é verdade**: Koundé e Tchouaméni empatam com 133 ações. Uma resposta do app
que diga que ele está entre os que mais tocam **não está errada** — está
corrigindo a referência.

### Caso 17 — Pergunta factual: desarmes do Enzo

**Pergunte:** `Quantos desarmes certos o Enzo Fernandez fez na final?`

**Resposta correta contém:** **5** (de 9 tentados).

**Valide:** caso 4.

**Sinal de alerta:** responder **9**. É a confusão entre desarme *certo* e
*tentado* — o erro real que o projeto já cometeu.

### Caso 18 — Quem fez os gols (a ficha do jogo)

**Pergunte:** `Quem fez os gols da final (tempo normal e prorrogação)?`

**Resposta correta contém:** **6 gols** — Messi 23' (pênalti) e 108'; Di María
36'; Mbappé 80' (pênalti), 81' e 118' (pênalti). Placar 3 × 3.

**Valide:** caso 2.

**Repare:** a pergunta não cita nenhum nome. O app reconhece a *intenção*
("gols") e monta a ficha sozinho. Antes dessa correção, o app só trazia o
**total** de gols por time e perdia para um sistema de busca simples.

**Sinal de alerta:** dizer que alguém fez "hat-trick" pela Argentina. Quem fez
três gols foi o Mbappé.

### Caso 19 — Pergunta agregada: posse de bola

**Pergunte:** `Qual time teve mais posse de bola na final?`

**Resposta correta contém:** **Argentina, 54,4%** contra 45,6% da França.

**Valide:**

```cypher
MATCH (e:EstatisticaTime {match_id: 3869685})
RETURN e.nome AS time, e.posse_pct AS posse
```

**Repare:** posse aqui é medida por **tempo** de posse, não por número de
toques.

### Caso 20 — Pergunta composta: cruza duas camadas

**Pergunte:** `O jogador por quem passavam os caminhos de progressão da Argentina na final foi também o que mais errou passe?`

**Resposta correta contém:** **Não.** O gargalo é Otamendi (betweenness 50.0),
mas ele foi dos mais seguros: **69 certos em 75** (92,0%), só **6 errados**. O
que mais errou foi **Molina (17)**, depois Enzo (13).

**Valide:**

```cypher
MATCH (e:EstatisticaJogador {match_id: 3869685}) WHERE e.time = 'Argentina'
RETURN e.nome AS nome, e.passes_tentados - e.passes_certos AS errados
ORDER BY errados DESC LIMIT 4
```

**Repare:** a resposta exige **duas fontes**: o padrão estrutural (camada 2) e
a contagem de passes (súmula). Nenhuma sozinha basta — é onde o grafo mais se
separa de um sistema de busca em texto.

**Cuidado com um empate:** a validação mostra **Tagliafico e o goleiro Martínez
empatados em 12 errados** na 3ª posição. A resposta de referência do projeto
cita só o Tagliafico. Uma resposta que diga "Tagliafico (12)" não está errada,
só incompleta; uma que ignore o empate de propósito merece desconfiança.

### Caso 21 — A mesma resposta, dois idiomas

Em qualquer pergunta acima, compare `resposta` com `em_bom_portugues`.

**Esperado:** a primeira usa o vocabulário técnico (betweenness, bloco, linha de
passe); a segunda diz **a mesma conclusão** como se fosse para alguém no bar —
sem jargão e **sem números novos**.

**Sinal de alerta:** o segundo texto trazer um fato ou número que não está no
primeiro.

---

# Parte 4 — Tentar fazer o app errar  `[LLM]`

Estes casos importam mais que os anteriores. Um sistema que acerta o fácil mas
inventa no difícil não serve — e este projeto já foi pego inventando.

### Caso 22 — O que está fora do grafo: os pênaltis

**Pergunte:** `Quem converteu os pênaltis da disputa na final?`

**Esperado:** o app diz que a **disputa de pênaltis não está no grafo** (só os
quatro períodos em campo), ou que não tem o dado — idealmente com
`confianca: baixa`.

**Sinal de alerta:** uma lista de batedores. Eles não estão no dado; seria
conhecimento externo do modelo, vindo de fora — exatamente o que o app não pode
fazer.

### Caso 23 — Um jogador que não existe

**Pergunte:** `Quantos passes o Cristiano Ronaldo fez na final?`

**Valide antes** que ele realmente não existe no grafo:

```cypher
MATCH (j:Jogador)
WHERE toLower(j.nome) CONTAINS 'ronaldo' OR toLower(j.nome) CONTAINS 'cristiano'
RETURN j.nome
```

**Esperado:** a consulta devolve **vazio**, e o app diz que o grafo não tem esse
jogador.

**Sinal de alerta:** qualquer número de passes. Seria invenção.

### Caso 24 — Desarme certo ou tentado?

**Pergunte:** `Quem fez mais desarmes na final?`

**Resposta correta contém:** **Enzo Fernández, 5 certos** (de 9 tentados);
Camavinga e Tagliafico 4 cada.

**Sinal de alerta:** o ranking por **tentativas** — Enzo 9, Tagliafico 7, Kolo
Muani 6 — apresentado como "desarmes". É o erro que, numa rodada anterior,
passou com 100% de fidelidade: as citações existiam e as consultas rodavam, mas a
consulta perguntava a coisa errada.

### Caso 25 — Os casos que já alucinaram

Na 4ª rodada de avaliação, estas duas perguntas fizeram o modelo **inventar
citações inteiras**. Se o seu modelo for o mesmo (ou parecido), repita:

**Pergunte (partida `3869685`):** `Theo Hernández jogou mesmo como lateral esquerdo na final?`

**Pergunte (partida `3869354`):** `Jules Koundé jogou como lateral direito de verdade nas quartas contra a Inglaterra?`

**Respostas corretas:**

- **Theo:** *não funcionalmente* — escalado como lateral esquerdo, a rede de
  passes o agrupa com a linha de ataque (**92 ações**). É o caso 9.
- **Koundé (quartas):** *não funcionalmente* — escalado como lateral direito, a
  rede o agrupa com a linha de ataque (**79 ações**).

**Valide, sempre, as citações** (caso 27). Na rodada em que alucinou, o modelo
citou uma partida `FB-MCI-LIV-2023-11-25` (Manchester City × Liverpool — não é
deste projeto) e um jogador, Alessandro Florenzi, em `match_id 3918315`. Nenhum
dos dois existe aqui.

**Sinal de alerta:** `padrao_tatico_id` que não aparece no `MATCH` do caso 27,
ou `consultas_executadas` com um `match_id` que não seja um dos três listados em
"Antes de começar" (`3869685`, `3869519`, `3869354`).

---

# Parte 5 — Conferir o conferidor  `[grátis]`

O app promete que cada resposta é auditável. Aqui você audita.

### Caso 26 — As 30 perguntas contra o grafo, sem modelo

```bash
source .venv/bin/activate
python scripts/check_golden_queries.py
```

**Esperado:** a última linha diz `RESUMO: 30/30 perguntas com resposta no grafo`.
Para uma só: `python scripts/check_golden_queries.py q23`.

**Repare:** isso separa **a qualidade do dado** da qualidade do modelo. Se 30/30
passa e o app erra uma resposta, o defeito está no modelo, não no grafo.

### Caso 27 — Reexecutar o que o app diz ter feito

Pegue uma resposta do caso 17 ou 20. Copie um `cypher` de
`consultas_executadas`, cole no Neo4j Browser.

**Esperado:** o resultado bate com o `resultado_resumido` que veio na resposta.

E para uma citação, pegue um `padrao_tatico_id` de `metricas_citadas`:

```cypher
MATCH (p:PadraoTatico {uid: 'COLE-O-UID-AQUI'})
RETURN p.nome_metrica AS metrica, p.valor_metrica AS valor, p.algoritmo_origem AS algoritmo, p.descricao_curta
```

**Esperado:** uma linha, com a mesma métrica, valor e algoritmo que a resposta
declarou. **Vazio = citação inventada.**

### Caso 28 — O que a fidelidade NÃO garante

**Entenda por quê:** o conferidor só diz *"as citações existem e as consultas
rodam"*. Ele **não** diz *"a resposta está certa"*.

**Exercício:** no caso 24, se o app responder "Enzo fez 9 desarmes" com uma
consulta que de fato retorna 9 (tentativas), a fidelidade dá 100% — e a resposta
está errada. Por isso este roteiro tem **os dois**: o conferidor automático
(casos 26–27) e a **sua** conferência dos fatos contra o grafo (todos os casos).
Um sem o outro não basta.

---

## Pontas soltas conhecidas

Comportamentos que você vai encontrar, ainda não corrigidos. Não são sinal de
que você fez algo errado.

| O que acontece | Por que importa |
|---|---|
| `POST /analyze/999` (partida inexistente) devolve **500** `Internal Server Error`. | Deveria ser um `404` claro, como o do `/report/999`. |
| `GET /graph/999/stats` (partida inexistente) devolve **200** com `Jogador: 68, Time: 4, Zona: 96`. | São os nós compartilhados entre partidas; a resposta engana, parece que a partida existe. Deveria ser `404`. |
| O índice do Graphiti (busca híbrida) pode ficar **desatualizado** em relação aos padrões depois de um `/analyze`. | A rota não reindexa mais (ADR-13). Para atualizar: `python scripts/index_graphiti.py --do-zero`. |
| Um `502` com *"O modelo esgotou o limite de tokens"* aparece de vez em quando num modelo de raciocínio. | Aumente `LLM_MAX_TOKENS` ou defina `LLM_REASONING_EFFORT=low` (ADR-14). **Não verificado ao vivo.** |

## Onde aprofundar

| Se você quer entender… | Leia |
|---|---|
| o projeto do zero, com uma jogada real | `00-entenda-o-projeto.md` |
| os 8 insights, com a intuição de cada um | `03-insights.md` |
| como a avaliação mede e por que existem três braços | `09-a-avaliacao-por-dentro.md` |
| por que o app foi desenhado assim | `05-decisoes.md` |

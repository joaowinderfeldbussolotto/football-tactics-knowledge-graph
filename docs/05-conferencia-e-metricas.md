# 5. Conferência e métricas: como cada resposta é corrigida

**Nenhum LLM dá nota neste benchmark.** Toda correção é feita por código,
comparando a resposta do modelo com o gabarito. Este capítulo explica o
formato da resposta, as regras de correção, os tipos de erro e como ler o
relatório final. O código está em `src/football_graphrag/benchmark/scoring.py`.

---

## 5.1 O formato da resposta: o modelo `Answer`

Se cada modelo respondesse em texto livre ("Acho que foi o Enzo, com uns 5
desarmes..."), seria preciso interpretar o texto, e a interpretação erra.
Por isso todos os braços respondem num **formato fixo**, chamado de saída
estruturada: o modelo é obrigado a preencher quatro campos.

```python
class Answer(BaseModel):
    rationale: str        # o raciocínio, escrito ANTES da resposta
    players: list[str]    # nomes dos jogadores; rankings em ordem
    value: float | None   # um número, sem unidade
    no_data: bool         # True só se os dados não respondem
```

| Campo | O que o modelo põe | Exemplo (pergunta a02) |
|---|---|---|
| `rationale` | um raciocínio curto, baseado nos dados | "No ranking de passes_certos, Enzo Fernandez lidera com 79." |
| `players` | nomes completos; em rankings, do melhor para o pior | `["Enzo Fernandez"]` |
| `value` | um número só, sem "passes" ou "%" | `79` |
| `no_data` | `true` apenas se os dados não permitem responder | `false` |

**Por que `rationale` vem primeiro?** Um modelo de linguagem escreve um
pedaço de cada vez, na ordem dos campos. Pondo o raciocínio antes da
resposta, ele "pensa" antes de responder, e isso costuma melhorar o acerto.
O `rationale` **nunca é corrigido**: ele existe para investigar erros
(entender *por que* um braço errou).

Cada campo tem uma descrição curta, em inglês, que o modelo lê. Ela é parte
do contrato: diz como escrever nomes ("full player names as they appear in
the data") e números ("a single number, no units").

**E se o modelo não respeitar o formato?** O PydanticAI (a biblioteca que
conversa com o modelo) detecta, devolve o erro ao modelo e pede de novo, até
**2 vezes**. Se ainda assim não vier no formato, a execução é registrada como
**erro de formato** e o benchmark segue para a próxima.

---

## 5.2 As regras de correção

Cada pergunta diz no YAML como deve ser conferida (o campo `check`, capítulo
3). As regras, com exemplos reais:

### `player`: o primeiro nome tem de ser o esperado

Pergunta f03, "Quem deu a assistência para o segundo gol da França?".
Gabarito: Marcus Thuram.

| Resposta do modelo | Resultado | Por quê |
|---|---|---|
| `players: ["Marcus Thuram"]` | ✅ certo | |
| `players: ["Thuram"]` | ✅ certo | sobrenome único na partida (5.3) |
| `players: ["Kylian Mbappé", "Marcus Thuram"]` | ❌ errado | só o **primeiro** conta, e o primeiro é o autor do gol |
| `players: []` | ❌ errado | |

### `value`: o número tem de bater

Pergunta f02, "Quantos gols...?". Gabarito: 6.

| Resposta | Resultado |
|---|---|
| `value: 6` ou `value: 6.0` | ✅ certo |
| `value: 7` | ❌ errado |
| `value: null` | ❌ errado |

Contagens são **exatas**. O YAML permite uma margem (`tolerance`) para
números contínuos, como porcentagens, mas nenhuma pergunta atual usa.

### `set`: o conjunto de jogadores, em qualquer ordem

Pergunta a06, "Quais jogadores da França receberam cartão amarelo?".
Gabarito: Rabiot, Thuram, Giroud.

| Resposta | Resultado | Por quê |
|---|---|---|
| `["Giroud", "Rabiot", "Thuram"]` | ✅ certo | a ordem não importa |
| `["Rabiot", "Thuram"]` | ❌ errado | faltou um |
| `["Rabiot", "Thuram", "Giroud", "Mbappé"]` | ❌ errado | sobrou um |

### `player_and_value`: as duas coisas

Pergunta a02, "Qual jogador deu mais passes certos, e quantos foram?".
Gabarito: Enzo Fernandez, 79.

| Resposta | Resultado |
|---|---|
| `["Enzo Fernández"], 79` | ✅ certo (o acento não importa) |
| `["Enzo Fernández"], 92` | ❌ errado (92 são os tentados) |
| `["Otamendi"], 79` | ❌ errado |

### `no_data`: dizer que não há dado

Pergunta u03, "Quem foi eleito o melhor jogador da final?". Gabarito:
`no_data`.

| Resposta | Resultado |
|---|---|
| `no_data: true` | ✅ certo |
| `players: ["Lionel Messi"]` | ❌ errado, e conta como **alucinação** (o dado não existe; a resposta veio da memória) |

---

## 5.3 Nomes: como "Messi" vira "Lionel Andrés Messi Cuccittini"

Os dados usam o nome completo de registro. O modelo pode escrever "Messi",
"Lionel Messi" ou "messi". Para não penalizar isso, a correção usa um
**dicionário de apelidos** montado automaticamente a partir das escalações
da StatsBomb:

1. o **nome completo** (`player_name`): "Lionel Andrés Messi Cuccittini";
2. o **apelido oficial** (`player_nickname`): "Lionel Messi";
3. o **sobrenome sozinho, só quando é único na partida**: "Messi".

E toda comparação **ignora acentos, maiúsculas e comentários entre
parênteses**: "Enzo Fernández", "ENZO FERNANDEZ" e "Enzo Fernandez (ARG)"
são o mesmo nome.

A regra 3 tem uma exceção importante. Dois jogadores da final se chamam
Martínez (Lautaro e Emiliano, o goleiro), e dois se chamam Hernández (Theo e
Ángel Di María Hernández). Nesses casos o sobrenome sozinho é **ambíguo** e
**não vale**: responder só "Martínez" conta como erro. Sobrenomes compostos
funcionam: "Di María", "De Paul", "Mac Allister", "Kolo Muani".

---

## 5.4 Os quatro desfechos de uma resposta

Toda execução termina em exatamente um destes:

| Desfecho | Quando acontece | Conta como |
|---|---|---|
| **Acerto** | a resposta bate com o gabarito | certo |
| **Alucinação** | respondeu, com cara de certeza, e errou | erro |
| **Abstenção** | disse `no_data` numa pergunta que **tem** resposta | erro, mas registrado à parte |
| **Erro de formato** | não produziu um `Answer` válido, mesmo depois das 2 novas tentativas (ou estourou o limite de chamadas) | erro, registrado à parte |

Por que separar os erros? Porque eles têm **custos diferentes** para quem usa
o sistema:

- uma **abstenção** é um erro honesto: o usuário sabe que não tem resposta;
- uma **alucinação** é perigosa: o usuário recebe uma resposta errada com
  confiança e não tem como saber;
- um **erro de formato** é um problema de engenharia (o modelo ou o provedor
  não lidou bem com o formato), não de conhecimento.

Um braço com 70% de acerto e 30% de abstenção é muito mais confiável que um
com 70% de acerto e 30% de alucinação.

Nas perguntas `unanswerable`, qualquer resposta diferente de `no_data` é
alucinação.

---

## 5.5 O que fica registrado: `results.jsonl`

Cada execução (uma pergunta × um braço × uma repetição) vira **uma linha** em
`data/benchmark/results.jsonl`, gravada logo depois da chamada. O formato é
JSON Lines: um objeto JSON por linha. Os campos:

| Campo | Exemplo | Significado |
|---|---|---|
| `question_id`, `type`, `arm`, `repeat` | `"a02"`, `"aggregation"`, `"graph_tools"`, `1` | o que foi executado |
| `answer` | `{"rationale": "...", "players": [...], "value": 79, "no_data": false}` | a resposta completa (`null` se houve erro de formato) |
| `expected` | `{"players": ["Enzo Fernandez"], "value": 79, "no_data": false}` | o gabarito |
| `correct`, `abstention`, `format_error` | `true`, `false`, `false` | o desfecho (5.4) |
| `error` | `null` | o motivo, quando não houve resposta válida |
| `input_tokens`, `output_tokens` | `2817`, `95` | tokens consumidos, informados pelo provedor |
| `n_tool_calls`, `tool_calls` | `1`, `[{"tool": "stat_ranking", "args": {...}}]` | ferramentas chamadas (só no `graph_tools`) |
| `latency_s` | `3.2` | tempo da execução, em segundos |
| `model`, `timestamp` | `"openrouter:..."`, `"2026-10-07T14:43:00+00:00"` | modelo usado e quando |

Esse arquivo é a **fonte única dos números**. Tudo no relatório sai dele.

---

## 5.6 Como ler o relatório: `summary.md`

Ao fim da execução, `scripts/run_benchmark.py` gera
`data/benchmark/summary.md`. Para regenerá-lo sem chamar nenhum modelo:
`python scripts/summarize.py`. As seções:

### 1. Acerto por tipo e braço (a tabela principal)

Linhas são os tipos de pergunta, colunas são os braços, e cada célula é a %
de execuções certas (as 3 repetições contam). A última linha é o total.

Como ler: compare **colunas** para saber qual braço vai melhor em cada tipo.
Compare **linhas** para saber que tipo de pergunta é difícil para todos.
Cada tipo tem 6 perguntas × 3 repetições = 18 execuções, então **uma pergunta
vale cerca de 17 pontos percentuais** dentro do tipo. Diferenças pequenas
entre braços (menos de 15 pontos) podem ser uma ou duas perguntas e não
devem ser lidas como superioridade.

### 2. Erros por braço

Para cada braço, a % de alucinação, de abstenção e de erro de formato, sobre
todas as execuções do braço. É aqui que se vê se um braço erra "com
honestidade" (abstém) ou "com confiança" (alucina).

### 3. Consistência entre repetições

A % de perguntas em que as 3 repetições deram **exatamente a mesma resposta**
(mesmos jogadores, mesmo número, mesmo `no_data`). Mesmo com temperatura 0,
modelos servidos por provedores nem sempre são determinísticos. Um braço
inconsistente é menos confiável, mesmo que acerte na média.

### 4. Custo por pergunta

Tokens de entrada e de saída, número de chamadas de ferramenta e tempo,
todos em média por execução. O custo em dinheiro é tokens × preço do seu
modelo. O `events_in_prompt` deve aparecer com dezenas de milhares de tokens
de entrada; o `graph_tools`, com várias chamadas.

### 5. Acertos por pergunta

Para cada pergunta e braço, quantas das repetições acertaram (por exemplo,
`2/3`). É a tabela para investigar: ache a célula `0/3` e vá ao
`results.jsonl` (ou ao Langfuse) ver o `rationale` e as ferramentas chamadas.

---

## 5.7 Langfuse: para investigar, não para medir

Se as chaves do Langfuse estiverem no `.env`, cada execução aparece no
Langfuse como um bloco nomeado `{pergunta}/{braço}/r{n}` (por exemplo,
`s03/graph_tools/r2`). Dentro dele está a conversa inteira: o prompt
enviado, cada chamada de ferramenta com o resultado e a resposta final.
Isso é muito útil para entender um erro.

Mas **os números do benchmark saem do `results.jsonl`, nunca do Langfuse.**
O Langfuse é um serviço externo e pode perder ou atrasar registros. O arquivo
local é gravado execução por execução e é versionado no repositório. Sem as
chaves, tudo funciona igual, só sem essa visualização.

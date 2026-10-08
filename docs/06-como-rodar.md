# 6. Como rodar, do zero

Este capítulo leva você de um computador sem nada até o relatório do
benchmark. Há dois caminhos que chegam ao mesmo lugar:

- **Caminho A, Python local**: o Neo4j roda no Docker e os scripts rodam no
  seu Python. É o mais rápido para mexer no código.
- **Caminho B, tudo no Docker**: os scripts também rodam dentro de um
  container. Não precisa de Python instalado.

As etapas são as mesmas nos dois; muda só o prefixo dos comandos.

---

## 6.1 Pré-requisitos

| O quê | Para quê | Caminho |
|---|---|---|
| Docker (com `docker compose`) | rodar o Neo4j | A e B |
| Python **3.11** | rodar os scripts | só A |
| Uma chave de API de LLM | os braços do benchmark | A e B |
| Uma chave de API de embeddings | só o braço `vector` | A e B |
| ~3 GB livres | imagem do Neo4j, dados, modelos | A e B |

Por que Python 3.11 e não o mais novo? A biblioteca `socceraction`, que faz a
conversão para SPADL, não instala em Python 3.13 ou superior.

---

## 6.2 Configurar o `.env`

Todas as configurações ficam num arquivo `.env` na raiz do projeto, que
**não vai para o Git** (contém chaves secretas). Comece copiando o modelo:

```bash
cp .env.example .env
```

E preencha:

| Variável | O que é | Exemplo |
|---|---|---|
| `LLM_PROVIDER` | quem fornece o modelo | `openrouter`, `anthropic`, `gemini` ou `mistral` |
| `LLM_API_KEY` | a chave desse provedor | `sk-or-...` |
| `LLM_MODEL` | o nome do modelo no provedor. No OpenRouter, sempre `laboratório/modelo` | `z-ai/glm-5.3-flash` |
| `LLM_MAX_RETRIES` | quantas vezes o próprio SDK tenta de novo após erro temporário (limite de uso, servidor fora) | `5` (use 6 a 8 em chaves gratuitas) |
| `LLM_MAX_TOKENS` | teto de tokens que o modelo pode **escrever** por resposta | `16000` |
| `LLM_REASONING_EFFORT` | só OpenRouter: quanto o modelo "pensa" antes de responder. Vazio = padrão do modelo | vazio |
| `EMBEDDER_PROVIDER` | quem gera os embeddings do braço `vector`. O OpenRouter não oferece embeddings, então é preciso outro | `gemini` ou `mistral` |
| `EMBEDDER_API_KEY`, `EMBEDDER_MODEL` | chave e modelo de embeddings | `gemini-embedding-001` |
| `NEO4J_URI` | endereço do Neo4j | `bolt://localhost:7687` no caminho A; no B o compose ajusta sozinho |
| `NEO4J_USER`, `NEO4J_PASSWORD` | usuário e senha do Neo4j | `neo4j` / `changeme` |
| `LANGFUSE_*` | opcional; visualização das execuções (capítulo 5) | vazio desliga |
| `STATSBOMB_MATCH_IDS` | a partida | `3869685` (a final) |

**Por que o `NEO4J_URI` muda?** Dentro do Docker, o Neo4j é encontrado pelo
nome do serviço (`neo4j`). Fora dele, pelo seu computador (`localhost`). O
`local_setup.sh` (caminho A) troca isso automaticamente e guarda uma cópia do
original em `.env.bak-local`.

---

## 6.3 Caminho A: Python local

### Tudo de uma vez

```bash
scripts/local_setup.sh
source .venv/bin/activate
```

O script faz, nesta ordem, e pode ser rodado de novo sem estragar nada:

1. confere o Docker e instala o `uv` (um instalador rápido de Python) se
   faltar;
2. cria o ambiente `.venv` com Python 3.11 e instala o projeto;
3. cria ou ajusta o `.env` (`NEO4J_URI` para `localhost`);
4. sobe **só o Neo4j** no Docker, espera ficar pronto e confere se o plugin
   GDS carregou. Se o container não conseguiu baixar o plugin (acontece em
   redes com DNS quebrado), o script baixa pelo seu computador e instala;
5. roda as camadas 0, 1/1b e 2.

**Nada disso gasta API.** Na primeira vez, o passo 5 é o mais demorado:
baixa os 16 jogos do mata-mata da Copa e treina com eles os modelos de xT e
VAEP. Das outras vezes, usa os modelos guardados em `data/models/` e a camada
0 da final leva poucos segundos.

Opções: `--sem-camadas` (só ambiente e Neo4j) e `--testes` (roda o `pytest`
no fim).

### Passo a passo, à mão

Se preferir ver cada etapa:

```bash
docker compose up -d neo4j                 # sobe o Neo4j (GDS e APOC incluídos)
python scripts/download_statsbomb.py       # baixa o JSON bruto da final
python scripts/run_pipeline.py             # camada 0
python scripts/build_graph.py              # camadas 1 e 1b
python scripts/run_analysis.py             # camada 2
```

O que esperar de cada um (saídas reais, resumidas):

```text
# run_pipeline.py
[3869685] 4527 eventos kloppy -> 2585 ações SPADL (537 fases de posse) em 2.01s

# build_graph.py
estatísticas de jogador 3869685: 34 nós
estatísticas de time 3869685: 2 nós
[3869685] 8004 escritas em 0.88s

# run_analysis.py
[3869685] 24 padrões táticos: {'pivo_estrutural': 2, 'terceiro_homem': 6, ...}
```

(O `run_pipeline.py` conta 4.527 eventos, e não os 4.407 do JSON, porque a
biblioteca de leitura, a `kloppy`, cria eventos derivados: por exemplo, 80
eventos de "bola fora" e os cartões como eventos separados.)

---

## 6.4 Caminho B: tudo no Docker

```bash
cp .env.example .env                       # preencha as chaves
docker compose up -d --build               # sobe neo4j + app
```

O serviço `app` é um container com o projeto instalado, que fica parado
esperando comandos. Ele só existe no branch `refactor/benchmark` em diante.
Confira com `docker compose config --services`: deve listar `neo4j` e `app`.

Depois, todo comando do caminho A ganha o prefixo `docker compose exec app`:

```bash
docker compose exec app python scripts/download_statsbomb.py
docker compose exec app python scripts/run_pipeline.py
docker compose exec app python scripts/build_graph.py
docker compose exec app python scripts/run_analysis.py
docker compose exec app python scripts/check_ground_truth.py
docker compose exec app python scripts/smoke_llm.py
docker compose exec app python scripts/run_benchmark.py --sample
```

Bom saber:

- `src/`, `scripts/`, `config/` e `data/` são **montados do seu computador**
  dentro do container. Editar código ou perguntas não exige reconstruir a
  imagem, e os resultados aparecem direto em `data/benchmark/`. Só mudanças
  no `pyproject.toml` (dependências) pedem `docker compose up -d --build`.
- O `pytest` não está instalado na imagem; rode os testes pelo caminho A.
- Para parar: `docker compose down`. O banco fica guardado num volume;
  `docker compose down -v` apaga o banco também.

---

## 6.5 Conferir antes de gastar: gabarito e modelo

Duas verificações baratas antes do benchmark:

```bash
python scripts/check_ground_truth.py
```

Compara o gabarito com o grafo, sem LLM (capítulo 3). Tem de terminar com
`25/25 agree`. Se não terminar, há algo diferente nos dados e o benchmark não
deve ser rodado até entender a diferença.

```bash
python scripts/smoke_llm.py
```

Faz **uma** chamada ao seu modelo para conferir as duas capacidades de que o
benchmark depende: chamar ferramentas e responder no formato `Answer`. O
formato da saída (os números variam):

```text
provider=openrouter  model=z-ai/glm-5.3-flash
tool calling:      ok
structured output: ok
tokens in/out: <entrada>/<saída>  latency: <segundos>s
```

Se aparecer `FAILED`, o modelo escolhido não serve para o benchmark (ou não
chamou a ferramenta, ou não respeitou o formato). Troque o `LLM_MODEL`.

---

## 6.6 Rodar o benchmark

### Primeiro, a amostra

```bash
python scripts/run_benchmark.py --sample
```

Roda **a primeira pergunta de cada tipo** (f01, a01, s01, c01, u01), nos 5
braços, uma vez: 25 execuções. Custa centavos e mostra se tudo funciona de
ponta a ponta. Cada execução imprime uma linha neste formato:

```text
[7/25] a01 events_in_prompt r1: ok (<tokens de entrada>/<tokens de saída> tok, <segundos>s)
```

O desfecho pode ser `ok`, `wrong`, `abstention` ou `format_error`
(capítulo 5).

### Quais braços rodar

O arquivo [`config/benchmark.yaml`](../config/benchmark.yaml) diz quais braços
o `run_benchmark.py` e o `ask.py` usam quando a linha de comando não diz
outra coisa:

```yaml
arms: [events_in_prompt, graph_tools]
```

Para a rodada que consolida os resultados, liste os cinco. Na linha de
comando, `--arms` (no `run_benchmark.py`) ou `--arm` (no `ask.py`) sobrepõe o
arquivo.

### Depois, o benchmark completo

```bash
python scripts/run_benchmark.py --fresh
```

São 25 perguntas × 5 braços × 3 repetições = **375 execuções**, uma de cada
vez (`--repeats 1` faz 125). O `--fresh` esvazia o arquivo de resultados antes (sem ele, o script se
recusa a começar se já houver resultados, para não misturar a amostra com a
execução completa nem apagar dados pagos sem querer).

**Quanto custa?** Os dois braços mais pesados são o `events_in_prompt` (~111
mil tokens de entrada por pergunta, quase todos lidos do cache a partir da
segunda) e o `graph_tools` (~37 mil por pergunta, sem cache). Com o Claude
Haiku 5.5 pelo OpenRouter, uma repetição das 25 perguntas nos 5 braços custou
cerca de US$ 0,30. O custo real aparece no `summary.md` (tokens médios) e no
painel do provedor.

**Quanto demora?** Depende do provedor. Conte alguns segundos por execução,
mais nas do `events_in_prompt` e do `graph_tools`: algo entre 30 minutos e
algumas horas para as 375.

### Se cair no meio

Cada execução é gravada **logo depois** de terminar. Se a internet cair ou o
provedor falhar, nada se perde além da execução em andamento:

```bash
python scripts/run_benchmark.py --resume
```

continua de onde parou. Erros do provedor (servidor fora, limite de uso
estourado mesmo depois das novas tentativas do SDK) **não são gravados**, e o
`--resume` os refaz. O script avisa no fim quantos foram.

### Outras opções

| Opção | O que faz | Exemplo |
|---|---|---|
| `--repeats N` | número de repetições (padrão 3) | `--repeats 1` |
| `--arms a,b` | só alguns braços | `--arms stats_in_prompt,graph_tools` |
| `--questions x,y` | só algumas perguntas | `--questions f01,s02` |
| `--output arquivo` | grava em outro arquivo (o relatório sai ao lado, com o mesmo nome + `_summary.md`) | `--output data/benchmark/teste.jsonl` |

### O resultado

- `data/benchmark/results.jsonl`: uma linha por execução (capítulo 5);
- `data/benchmark/summary.md`: o relatório.

Para refazer o relatório sem chamar modelo nenhum:

```bash
python scripts/summarize.py
```

Os dois arquivos são versionados no Git: o resultado do benchmark faz parte
do projeto.

Para registrar a execução, siga o roteiro de
[`docs/execucoes/`](execucoes/README.md). Ele inclui uma tabela de links
para os traces, gerada por `python scripts/trace_links.py --results <arquivo>`.

---

## 6.7 Fazer perguntas livres (ou uma pergunta isolada)

Para explorar, investigar um erro ou ver como cada braço se comporta, sem
gravar nada em `results.jsonl`. Há três jeitos:

**Modo interativo**, para várias perguntas livres seguidas:

```bash
python scripts/ask.py --arm graph_tools
```

```text
model: openrouter:anthropic/claude-haiku-5.5 | arms: graph_tools
Free questions about the 2022 World Cup final, one per line. Empty line or 'sair' to quit.

pergunta> Quem tocou mais na bola?
=== graph_tools  (<segundos>s, tokens in/out <entrada>/<saída>)
  tool: query_actions(filters=None, group_by=['player'], metric='count', top=5)
  answer:  <o raciocínio do modelo, em texto>
  players: <jogadores> | value: <número> | no_data: no
  trace:   https://us.cloud.langfuse.com/project/.../traces/...

pergunta> sair
```

Sem `--arm`, cada pergunta vai aos cinco braços. Isso é útil para comparar,
mas é mais caro: o `events_in_prompt` envia ~100 mil tokens por pergunta. Com
cache de prompt, a primeira pergunta paga a gravação e as seguintes, feitas em
até 5 minutos, saem bem mais baratas.

**Uma pergunta livre**, num comando só:

```bash
python scripts/ask.py "Quem tocou mais na bola?"                  # nos 5 braços
python scripts/ask.py "Quem tocou mais na bola?" --arm stats_in_prompt
```

**Uma pergunta do benchmark**, com gabarito e veredito:

```bash
python scripts/ask.py --question s03                      # nos 5 braços
python scripts/ask.py --question s03 --arm graph_tools    # um braço só
python scripts/ask.py --question s03 --show-prompt        # mostra também o prompt enviado
```

Pergunta livre **não tem gabarito**: a resposta é mostrada, não corrigida.
Todo braço responde no mesmo formato do benchmark (`rationale`, `players`,
`value`, `no_data`), então a explicação fica no campo `answer` (o
`rationale`). Perguntas abertas ("como a Argentina construía o jogo?")
funcionam, mas o formato foi pensado para perguntas fechadas, e a resposta
vem resumida nesse campo.

Em pergunta do benchmark, a saída mostra também o gabarito e o veredito:
`CORRECT`, `WRONG`, `ABSTENTION` ou `FORMAT ERROR`.

## 6.8 Testes

```bash
pytest
```

Os testes conferem a correção das respostas, o gabarito, as ferramentas, a
montagem dos prompts e as camadas 0 a 2, sem chamar nenhum LLM (usam modelos
falsos da própria biblioteca). Os que precisam do Neo4j ou dos dados baixados
são **pulados** quando eles não estão disponíveis. Isso não é falha: suba o
Neo4j e rode as camadas para que rodem todos.

---

## 6.9 Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `cannot run: LLM_API_KEY and LLM_MODEL must be set in .env` | `.env` sem chave ou sem modelo | preencha (6.2). Para o braço `vector`, também `EMBEDDER_*` |
| `Temporary failure in name resolution` ao baixar os dados | o container não resolve nomes de domínio (comum em Codespaces) | `docker compose down && docker compose up -d` e tente de novo. Se persistir, use o caminho A: o download feito no seu computador fica em `data/raw/` e é reaproveitado |
| `Couldn't connect to localhost:7687` | o Neo4j não está de pé, ou o `NEO4J_URI` aponta para o lugar errado | `docker compose ps`; no caminho A, `NEO4J_URI=bolt://localhost:7687` |
| `run_analysis.py` falha com `gds...` | o plugin GDS não carregou no Neo4j | rode `scripts/local_setup.sh`, que instala pelo seu computador |
| `already has N runs. Use --resume to continue or --fresh to start over.` | já há resultados no arquivo | `--resume` para continuar; `--fresh` para começar do zero (apaga os anteriores) |
| muitos `format_error` num braço | o modelo não lida bem com saída estruturada | rode `smoke_llm.py`; considere outro modelo |
| erro de contexto/tamanho no `events_in_prompt` | o modelo aceita menos de ~70 mil tokens | use um modelo com janela maior, ou rode sem esse braço (`--arms`) |
| `PROVIDER ERROR` em várias execuções | limite de uso do provedor | espere e rode `--resume`; em chave gratuita, suba `LLM_MAX_RETRIES` |
| `Model token limit (N) exceeded before any response was generated` | o modelo gastou todo o teto pensando (modelos de raciocínio) | suba `LLM_MAX_TOKENS` ou reduza `LLM_REASONING_EFFORT` |

# 09 — A avaliação por dentro

Este documento explica, sem pressupor que você acompanhou a construção, **o
que a avaliação mede, por que ela é do jeito que é, e como rodá-la**. Se você
quer só os números, eles estão em `03-insights.md` (seção "Avaliação") e
`07-validacao.md`. Aqui está o raciocínio por trás deles.

## 1. O que está sendo provado (e o que não está)

A tese do projeto é: **um grafo de conhecimento responde perguntas táticas que
um RAG vetorial comum não responde** — não porque tenha mais dados, mas porque
a informação estrutural (quem é o gargalo da rede de passes, que trio forma uma
comunidade, onde estão as pontes) **não existe em linha nenhuma de tabela**.
Ela é propriedade da topologia, e só aparece quando você roda um algoritmo de
grafo.

Repare no que essa frase **não** diz. Ela não diz que o grafo responde melhor
"quantos desarmes o Enzo fez". Esse número está numa tabela, e qualquer
sistema com acesso à tabela acerta. Se o grafo ganhasse essa também, seria
sinal de que a comparação está enviesada — não de que grafos são melhores.

Daí a regra que organiza tudo: **os dois sistemas recebem os mesmos fatos.**
O que muda entre eles é só a *representação* — grafo consultável de um lado,
texto embeddado do outro. Isso é o que `evaluation/match_facts.py` garante:
ele reconstrói, em pandas, exatamente as mesmas contagens que o grafo tem em
Cypher, e as entrega ao baseline. Sem isso, vencer as perguntas factuais não
significaria nada: seria um sistema **com** o dado contra um **sem** o dado.

## 2. Por que existem três braços

Em algum momento o grafo ganhou uma "súmula pré-agregada" (camada 1b): nós
`EstatisticaJogador` com ~30 contagens prontas por jogador. E a recuperação
passou a **entregar essa súmula direto no prompt** do modelo.

Aí veio a pergunta certa: *isso não quebra o que eu quero validar?*

Quebra parte, e vale separar quais:

| O que o trabalho afirma | A súmula atrapalha? |
|---|---|
| Insight estrutural não existe em tabela | **Não.** Nenhum campo da súmula tem betweenness, comunidade ou ponte. |
| O agente busca fatos sozinho, escrevendo Cypher | **Sim, muito.** O prompt manda *não* consultar quando o número já está no contexto. A capacidade some justamente onde era exercida. |
| Grafo consultável > texto embeddado | **Muda de sentido.** Com os mesmos fatos dos dois lados, o esperado ali é EMPATE. |

Em vez de escolher entre ter ou não ter a súmula, a avaliação **mede as duas
opções**, na mesma execução e com o mesmo modelo:

1. **`grafo_sem_sumula`** — só os padrões táticos no contexto. Para saber um
   número factual, o modelo *precisa* escrever Cypher. É o braço que mede a
   autonomia.
2. **`grafo_com_sumula`** — o anterior mais a súmula pronta. É o que a API faz.
3. **`baseline`** — o RAG vetorial plano, com os mesmos fatos.

A diferença entre 1 e 2 é o custo-benefício da pré-agregação, medido em vez de
assumido. E há uma checagem que valida o desenho: **na categoria estrutural os
dois braços do grafo têm de dar praticamente igual**, porque a súmula é
irrelevante lá. Se divergirem muito, o experimento está mal isolado e o resto
não vale.

## 3. As métricas, uma por uma

### `retrieval_previo` e `retrieval_final` — por que são duas

Um juiz (outro LLM) lê a pergunta, a resposta de referência e **o contexto que
foi recuperado**, e dá nota de 1 a 5 para: *o necessário para responder estava
ali?*

O problema é definir "ali". O agente do grafo tem uma ferramenta: ele pode
consultar o grafo durante a geração. Se o resultado dessas consultas entra no
contexto julgado, a nota deixa de medir recuperação e passa a medir o sistema
inteiro — e o baseline, que não tem ferramenta, nunca recebe esse acréscimo.
A métrica ficaria com o nome de uma coisa medindo outra, e favorecendo um lado.

Então são duas:

- **`retrieval_previo`** — só o que a recuperação entregou **antes** de o
  modelo rodar. É a **comparável com o baseline**, porque é simétrica.
- **`retrieval_final`** — aquilo **mais** o resultado das consultas. Mede o
  sistema completo.

Um caso real mostra por que a separação importa. Na pergunta *"Quem fez os gols
da final?"*, os dois braços do grafo tiraram **prévio 1,0 e final 5,0**. A
recuperação não trouxe nada útil; quem salvou a resposta foi o modelo indo
buscar. A métrica antiga registrava só o 5,0.

### `tactical_insight`

Outro juiz, outra pergunta: *a resposta **explica** o padrão — o mecanismo, por
que importa, o que revela sobre o time — ou só repete o número?* Nota 5 é
explicar corretamente; 3 é estar certo mas raso; 1 é errado ou vazio.

### `faithfulness` — e por que 100% não quer dizer "correto"

Esta é determinística, sem LLM: pega cada número que a resposta citou e
verifica se ele existe mesmo no grafo, e reexecuta cada consulta que o modelo
disse ter feito, conferindo se o resultado bate.

**Ela não verifica se a resposta está certa.** Verifica se a resposta é
*rastreável*. A diferença apareceu ao vivo: numa rodada, a resposta afirmou
*"hat-tricks de ambos os lados"* — falso, o Messi fez 2 gols, não 3. A
fidelidade marcou 100% assim mesmo, porque as citações existiam e as consultas
reexecutavam. Sempre que você vir 100% aqui, leia como "nada foi inventado do
nada", nunca como "está tudo certo".

## 4. O piso de ruído: por que n=1 não conclui nada

Os juízes são LLMs, e LLM não é determinístico. Dá para medir esse ruído de
graça, e nós medimos por acidente: entre duas execuções da amostra, o
**baseline não teve uma linha de código alterada** — e o `tactical_insight`
dele mudou em 3 das 4 perguntas (3→4, 3→4, 1→2).

Ou seja: **±1 ponto é ruído.** Diferença de um ponto entre dois braços, com uma
pergunta só, não é interpretável. É por isso que a rodada oficial usa as 30
perguntas: com 15 estruturais, 8 factuais, 4 agregadas e 3 compostas, a média
de cada categoria fica bem mais estável que qualquer pergunta isolada.

## 5. Como rodar

```bash
# 1. ambiente
docker compose up -d neo4j

# 2. camadas 0, 1, 1b e 2 (de graça, minutos)
python scripts/run_pipeline.py
python scripts/build_graph.py
python scripts/run_analysis.py

# 3. índice do Graphiti (PAGO — ver seção 6 para reaproveitar o backup).
#    É retomável: se cair, rode de novo e ele só paga o que faltou (ADR-13).
python scripts/index_graphiti.py

# 4. conferir o pipeline antes de gastar: 4 perguntas
python scripts/run_evaluation.py --amostra --hibrida --saida eval_amostra.json

# 5. a rodada de verdade
python scripts/run_evaluation.py --hibrida --rodada 4a-rodada
```

**Flags que importam:**

| Flag | Para quê |
|---|---|
| `--amostra` | uma pergunta de cada categoria, para testar o pipeline barato |
| `--ids q01_pivo_argentina,q17_gols_final` | perguntas específicas |
| `--saida NOME.json` | não sobrescrever o resultado citado na documentação |
| `--rodada RÓTULO` | nome da execução no Langfuse |
| `--hibrida` | liga a busca semântica do Graphiti (exige o índice) |
| `--retomar` | continua de onde parou, se a execução caiu |

**Custo e tempo, medidos:** ~US$ 0,012 por pergunta (somando os três braços),
o que põe a rodada de 30 em torno de **US$ 0,37**, em cerca de **2 horas**.
A indexação do Graphiti custa à parte, ~US$ 0,06 por partida.

**Se cair no meio:** a execução grava `{saida}.parcial.json` depois de *cada*
pergunta. Rode de novo com `--retomar` e ela pula as já respondidas. Duas horas
pagas não se perdem por um contêiner que morreu.

**Observabilidade:** com as chaves do Langfuse no `.env`, cada par
(pergunta, braço) vira um trace nomeado, com as chamadas do modelo penduradas
embaixo e metadados de rodada, categoria, braço e modelo. Sem as chaves, nada
acontece e o código roda igual.

## 6. O backup do índice — como não pagar duas vezes

As camadas 0, 1, 1b e 2 se reconstroem **de graça**, em minutos, a partir dos
parquets em `data/processed/`. O índice do Graphiti, não: cada padrão indexado
gasta chamadas de LLM e de embedding.

Por isso o backup guarda **só o índice**:

```bash
# gerar (depois de indexar)
python scripts/backup_graphiti.py --saida backup_graphiti.json.gz

# restaurar num ambiente novo, no lugar de rodar index_graphiti.py
python scripts/restore_graphiti.py backup_graphiti.json.gz
```

O arquivo tem os nós `Entity`/`Community`, as arestas `RELATES_TO`/`HAS_MEMBER`
e os vetores de embedding, mais um cabeçalho com data, modelo de embedding e
contagens. Comprimido, fica na casa de centenas de KB.

**Uma trava proposital:** a restauração se recusa a rodar se o modelo de
embedding do arquivo não for o mesmo do `.env`. Misturar vetores de modelos
diferentes não levanta erro nenhum — só piora a busca, em silêncio. Num
trabalho que compara sistemas de recuperação, é o defeito mais caro que existe,
porque não aparece. Use `--forcar` só se souber por quê.

**Ordem de restauração num ambiente do zero:**

```bash
docker compose up -d neo4j
python scripts/run_pipeline.py      # parquets (se não tiver)
python scripts/build_graph.py       # camadas 1 e 1b
python scripts/run_analysis.py      # camada 2
python scripts/restore_graphiti.py backup_graphiti.json.gz   # em vez de index_graphiti.py
```

## 7. Como ler a tabela de resultados

Para cada categoria, você verá os três braços. Leia nesta ordem:

1. **Estrutural, grafo contra baseline.** É a tese. É aqui que a diferença
   precisa ser grande, e é aqui que ela não pode depender da súmula.
2. **Estrutural, um braço do grafo contra o outro.** Precisam ser parecidos.
   Se não forem, pare: o experimento não isolou o que devia.
3. **Factual e agregada.** Empate é o resultado **correto**, não uma derrota.
   Os dois lados têm os mesmos fatos; se um ganhasse muito, seria sinal de
   assimetria escondida.
4. **Composta.** Precisa cruzar camada 2 com camada 1b, e é onde a
   recuperação estruturada tende a mostrar vantagem real.
5. **`consultas_media`.** Quantas vezes o modelo precisou escrever Cypher. É o
   número que responde "a súmula calou a ferramenta?".
6. **Qualquer diferença de 1 ponto**: ignore, a menos que seja consistente na
   categoria inteira. Ver seção 4.

## 8. As decisões, com os porquês

Os registros completos estão em `05-decisoes.md`:

- **ADR-8** — o modo autônomo (text-to-Cypher read-only) e as regras dele.
- **ADR-9** — troca de provedor de LLM, e por que um modelo "stealth" grátis
  não serve de base para o número oficial (o que estávamos usando foi retirado
  do ar em menos de 24 horas, no meio de uma execução).
- **ADR-10** — a súmula como condição experimental; os três braços; as duas
  notas de recuperação.
- **ADR-11** — a ficha do jogo, o roteador de intenção e a busca híbrida que
  estava dormente sem ninguém notar.

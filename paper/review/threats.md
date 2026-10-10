# Objeções permanentes da banca

Lista viva usada pela skill `banca-review`. `status`: **respondida** (o texto já responde, com o local),
**parcial** ou **aberta**. A evidência aponta para o repositório; o número vem de uma macro de `numbers.tex`.

| # | Objeção | Por que a banca levanta | Evidência no repositório | Resposta curta | status |
|---|---|---|---|---|---|
| 1 | O `graph_tools` foi ajustado olhando erros; o `text_to_cypher` não | a comparação entre os dois degraus mais altos favorece o primeiro | histórico de congelamentos (`tests/fixtures/tools_frozen.json`, git), execuções 04 a 12, `paper/data/trajectory.yaml` | declarar a assimetria no texto principal; a diferença é o teto do ganho de engenharia; mostrar a trajetória com as mesmas perguntas | parcial |
| 2 | Uma repetição, 47 perguntas com resposta, intervalos largos | pouca potência; `graph_tools` contra `text_to_cypher` com p=0,057 | `final_results.jsonl`; intervalos de Wilson | três repetições; reportar Holm; dizer "indica" | aberta até as repetições |
| 3 | Um modelo só (Claude Haiku 5.5) | o resultado pode ser do modelo, não da forma de acesso | modelo gravado em cada linha de resultado | declarar; amostra com um segundo modelo se sobrar orçamento | aberta |
| 4 | O `graph_tools` mistura ferramentas e grafo | o ganho vem das primitivas, do grafo ou do algoritmo (GDS)? | `text_to_cypher` usa o mesmo grafo sem GDS; não há braço de ferramentas sobre tabela ou SQL | o par controlado isola quem escreve a lógica; separar primitivas e grafo fica como trabalho futuro (texto para SQL) | parcial |
| 5 | O U invertido se apoia num braço que zera por construção | o último degrau só mostra que agregado fixo não serve a recortes | `stats_in_prompt` 0% | dizer que é o degrau rígido, não um resultado de comparação; reportar com e sem ele | parcial |
| 6 | As perguntas foram escritas e removidas por quem fez as ferramentas | seleção de perguntas depois de ver erros | `config/questions.yaml` (motivos), `robustness.md`, 22 removidas de 81 | tabela de removidas e motivo no repositório; nenhuma ferramenta mudou por causa de uma pergunta | parcial |
| 7 | O gabarito é do mesmo autor e a regra de empate mudou no meio | viés de correção | gabarito sem Neo4j (pandas e networkx); recorreção de 312 execuções mudou 0 veredito | declarar a regra e a recorreção | respondida (metodologia) |
| 8 | Uma partida, famosa | memorização e pouca generalidade | `no_context` 0%; nome da partida fora do prompt | citar o 0%; declarar o limite | respondida |
| 9 | Hipóteses "registradas antes" não verificáveis | pré-registro sem prova | `paper/ALERTAS.md`, item 2 | não afirmar o registro sem prova | aberta |
| 10 | Custo comparado entre braços com e sem cache | comparação injusta | `graph_tools` sem cache; `text_to_cypher` com cache | comparar tokens, não só dólares; ou ligar o cache | aberta |
| 11 | Três testes de McNemar sem correção; perguntas correlacionadas | falso positivo | `scripts/paper_numbers.py` calcula Holm | reportar o ajustado; as perguntas do mesmo grupo não são independentes | parcial |
| 12 | O controle não discrimina | quase todos acertam as perguntas sem resposta | 5 perguntas; dois braços erram a u01 ou a u03 | reportar com e sem o controle | respondida |
| 13 | Temperatura 0 não é determinismo; o provedor muda | resultados diferentes em dias diferentes | rodadas 10 e 11 mudaram três perguntas sem mudança de ferramenta; custo por provedor (execução 01) | as repetições medem isso; registrar o provedor | parcial |
| 14 | "Alucinação" inclui erro de leitura honesto | a classificação é por código, não por intenção | definição em `docs/05-conferencia-e-metricas.md` | definir como resposta errada dada como resposta | respondida |

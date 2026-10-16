# Perguntas prováveis da banca (20 min de perguntas)

Respostas curtas, para falar. Fontes: `paper/review/threats.md`, `paper/review/revisao-2026-10-15.md`,
`paper/ALERTAS.md` e `paper/generated/numbers.tex`. Ordem dos modelos nas listas de quatro números: Haiku 5.5,
Qwen3.8-flash, Sonnet 4.6, Kimi K3. Nenhum número aqui foi recalculado à mão: todos vêm dessas fontes.

## 1. Comparação das abordagens

**1. As ferramentas foram feitas e ajustadas para estas perguntas. A comparação é justa?**
Não é simétrica, e o artigo declara isso: as Ferramentas foram ajustadas olhando erros (sete congelamentos); a Consulta
escrita pelo modelo é primeiro contato. Por isso a diferença entre as duas é o teto do ganho de engenharia, não uma
medida de justiça. Sinais a favor: nas 12 perguntas que não serviram ao ajuste, as Ferramentas acertaram 12, 10, 12 e
11, e a Consulta, 10, 9, 11 e 12. As Ferramentas acertam dentro da cobertura delas (limitação do slide 13).

**2. O ganho vem das ferramentas, do grafo ou dos algoritmos de grafo (GDS)?**
Não está separado. O par Consulta × Ferramentas usa o mesmo grafo e o mesmo limite de chamadas e isola quem escreve a
consulta. Só 5 perguntas dependem do GDS. Sem elas, as Ferramentas acertaram 36, 34, 37 e 37 de 42, e a Consulta, 30,
26, 39 e 40. Aplicar as mesmas ferramentas a uma tabela, sem o grafo, é trabalho futuro (Conclusão).

**3. O ajuste das Ferramentas melhorou de fato o acerto?**
Seis perguntas refeitas levaram o Haiku de 39 para 45 de 52 (`all52_before_fixes_results.jsonl`). A trajetória do ajuste
com as mesmas perguntas em cada versão oscila (10 a 25 pontos em n pequeno) e os intervalos se sobrepõem; por isso o
artigo não afirma que o ajuste levou as Ferramentas "de 50% a 95%" (`paper/ALERTAS.md`, item 1).

**4. Por que a Busca vetorial acerta tão pouco? Não é só um RAG mal feito?**
Cada linha recuperada é uma ação isolada; contar exige todas as linhas de um tipo e ligar eventos exige as vizinhas.
Tzikas et al. obtiveram acerto maior com outro desenho (trechos com os eventos seguintes, até cem trechos, reordenação,
conferência por LLM). Busca vetorial com eventos vizinhos é trabalho futuro.

**5. O 0% de Estatísticas resumidas não é um resultado forçado?**
É o degrau rígido: a súmula só tem totais da partida inteira, sem recorte de tempo ou de campo. O texto atribui o baixo
acerto ao desenho da abordagem, não a uma curva de comparação.

## 2. Estatística e desenho

**6. Uma repetição por pergunta e 47 perguntas com resposta: o que é sinal?**
Indício, não demonstração. O que se sustenta: a subida de Consulta e de Contexto longo dos menores para os maiores
(os intervalos de Wilson não se cruzam). Ferramentas e Consulta não se distinguem nos maiores (empate no Sonnet e
Consulta à frente no Kimi). Três repetições são o próximo passo.

**7. Havia três testes de McNemar sem correção.**
O texto não traz testes. Com ajuste de Holm, Consulta contra Contexto longo no Haiku fica em p=0,034; Ferramentas contra
Consulta no Haiku fica em p=0,057 (valores de `numbers.tex`).

**8. Os intervalos de confiança e o n.**
Wilson de 95%, que fica sempre entre 0 e 100. Com 47 perguntas e uma repetição, os intervalos são largos; o gráfico do
slide 9 mostra o acerto, e a figura do artigo traz os intervalos.

**9. Temperatura zero não é determinismo.**
As rodadas 10 e 11 mudaram três perguntas sem mudança de ferramenta. Só as repetições medem essa variação. Os modelos
maiores rodaram na temperatura padrão do provedor, com raciocínio estendido.

## 3. Perguntas, gabarito e dados

**10. As perguntas foram escritas e removidas por quem fez as ferramentas.**
Foram 81 escritas e 52 ativas; 22 removidas pelo teste de robustez ou por ambiguidade (7 candidatas nunca rodaram). A
lista com o motivo está em `config/questions.yaml` (`stage: removed`). Nenhuma ferramenta mudou por causa de uma pergunta.

**11. O gabarito é do mesmo autor e a regra de empate mudou no meio.**
O gabarito é calculado por código, fora do grafo (pandas e networkx), a partir do JSON bruto e da tabela de ações. A
recorreção de 312 execuções mudou 0 veredito. Em empate, todos os empatados valem.

**12. A final de 2022 é famosa. Não é memorização?**
O prompt não nomeia a partida e proíbe responder de memória; o 0 de 47 de Sem dados mede obediência ao prompt.
Defesa adicional: as definições do projeto (recebedor inferido, fases de posse, leituras) e uma pergunta (s11) cuja
resposta famosa está errada. Uma só partida é limitação declarada.

**13. O controle não discrimina?**
São 5 perguntas; cada abordagem que lê os dados erra no máximo uma delas (`accControl*` em `numbers.tex`). A Consulta errou a u01 nos 4 modelos
(resposta dada em vez de ausência de dados). O artigo reporta com e sem o controle.

## 4. Custo, modelos e alcance

**14. A comparação de custo é justa? Ferramentas não usa cache.**
Por isso o artigo só mostra tokens e latência, sem preço em dólar. Ferramentas não usa cache de prompt e Consulta usa.
No Contexto longo, a maior parte da entrada vem do cache, o que o favorece: a conclusão de que ele é o mais lento é
conservadora.

**15. Tamanho ou raciocínio estendido explica o salto nos modelos maiores?**
Não dá para separar: vieram juntos. Avaliar modelos maiores sem raciocínio estendido é trabalho futuro. O Sonnet usou um
nível de raciocínio menor no Contexto longo (o ajuste favoreceu o Contexto longo, que ficou abaixo mesmo assim).

**16. "Alucinação" inclui erro honesto de leitura?**
A classificação é por código: resposta errada dada como resposta, não por intenção (`docs/05-conferencia-e-metricas.md`).

## 5. Dados industriais (fecho)

**17. Por que isso vale para indústria?**
Parte dos dados industriais tem a mesma forma: registros de eventos com agente, momento e local, ligados entre si (paradas,
alertas, movimentações). O resultado do futebol indica que a forma de levar os dados ao contexto pesa tanto quanto o
modelo. A tabela de correspondência do slide 14 é uma proposta de analogia, não um resultado.

**18. O que muda para aplicar em outro domínio?**
A preparação dos dados, o grafo e as ferramentas dependem das perguntas que se quer responder: exige implementação
própria para o domínio. As Ferramentas só valem para perguntas dentro da cobertura delas.

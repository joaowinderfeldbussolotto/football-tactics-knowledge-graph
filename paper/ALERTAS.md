# Alertas: o que o dossiê diz e o repositório não sustenta como está escrito

Conferido em 10/10/2026 contra `data/benchmark/final_results.jsonl` e o git. **Bate com o repositório:**
os acertos e intervalos de Wilson (45%, 70%, 87%), os três McNemar (17/5 p=0,017; 11/3 p=0,057; 23/3
p<0,001), as 81 perguntas escritas e as 22 removidas, 4.407 eventos brutos, 1.263 passes, 2.585 ações,
27 DOIs que resolvem para os artigos certos (inclusive os três que o dossiê marcava "conferir": 4, 6 e 11).

**Não bate, ou não pode ser dito como está:**

1. **A trajetória "50% a 95%" (F4).** Compara conjuntos de perguntas diferentes: os 50% são as 20 perguntas de
   grafo da execução 10 (com os cinco triângulos retirados depois) e os 95% são o grupo de rede da rodada final.
   Com as MESMAS perguntas em cada versão (`paper/data/trajectory.yaml`, `scripts/figures.py`), o acerto do
   `graph_tools` fica assim:

   | Série (mesmas perguntas) | Pontos |
   |---|---|
   | perguntas do piloto ($n$=8) | v2 4/8, v2.1 5/8, v2.2 7/8, v2.4 7/8, **final 5/8** |
   | 25 originais ($n$=20 com resposta) | v2.2 15/20, v2.4 19/20, **final 17/20** |
   | perguntas de grafo ($n$=13) | v3 9/13, v3.1 10/13, final 12/13 |

   Só a série de grafo sobe sem queda, e todos os intervalos se sobrepõem. Nas outras duas, a rodada final fica
   abaixo da v2.4 sem que nenhuma ferramenta daquelas perguntas tenha piorado: a oscilação entre rodadas
   (10 a 25 pontos em $n$ pequeno) é do tamanho do efeito que se quer medir. O texto deve dizer isso, e é o
   argumento mais forte a favor das três repetições. Não escrever que o ajuste "levou o `graph_tools` de 50% a 95%".

2. **Hipóteses H1 a H4 "registradas antes das rodadas".** Não estão em nenhum arquivo do repositório (nem em
   `docs/`, nem no histórico do git); o dossiê diz que estão na conversa. Um leitor não consegue verificar.
   Dizer "formuladas durante o planejamento" ou fornecer o registro; o apêndice com o texto está em
   `paper/dossie.md`. O sexto braço, como o dossiê já diz, não tem hipótese prévia.

3. **Declaração de IA.** O rascunho diz "cinco braços": são seis. Também deve citar o Claude Code, o MCP do
   Overleaf e as skills de escrita como ferramentas de apoio.

4. **Tamanho da tabela de eventos.** `docs/01-visao-geral.md` dizia "~63 mil tokens" (valor da v1); o medido
   é 115.735 tokens de entrada por pergunta (já corrigido nesta branch). O dossiê cita "JSON bruto com cerca de
   670 mil tokens": não há contagem de tokens do JSON no repositório (são 3,75 milhões de caracteres). Medir com
   o tokenizador ou tirar o número.

5. **Denominador dos erros.** "14 erros do `text_to_cypher` e 6 do `graph_tools`" valem nas 47 perguntas com
   resposta. Nas 52 são 15 e 7 (a u01 e a u03, do controle, entram). Dizer o denominador.

6. **81 perguntas.** São 52 ativas + 22 removidas + 7 candidatas que nunca rodaram. "22 removidas de 81" é
   verdade, mas as 7 candidatas não são nem uma coisa nem outra.

7. **Custo.** O US$ 0,12 do `text_to_cypher` é medido (consumo da chave); o US$ 0,40 do `graph_tools` é uma
   estimativa por tokens, e o `graph_tools` não usa cache de prompt enquanto o `text_to_cypher` usa. Não
   apresentar os dois como comparação direta; ou ligar o cache no `graph_tools` e medir de novo.

8. **Três testes sem correção.** Com ajuste de Holm (`scripts/paper_numbers.py` já calcula), o
   `text_to_cypher` contra o `events_in_prompt` fica em p=0,034 (significativo); com Bonferroni seria 0,051.
   O `graph_tools` contra o `text_to_cypher` segue em 0,057. Reportar o ajustado.

9. **O `graph_tools` de 87% já inclui a reexecução.** Seis perguntas rodaram duas vezes e a segunda substituiu
   a primeira (39/52 antes, 45/52 depois; o arquivo antes está em
   `data/benchmark/all52_before_fixes_results.jsonl`). As três repetições limpas resolvem isso.

10. **Escolha estatística a confirmar.** Com repetições, o intervalo de Wilson usa a pergunta como unidade
    (n = perguntas, proporção = média da taxa de acerto de cada pergunta) e o McNemar usa o resultado por maioria.
    Está descrito no cabeçalho de `src/football_graphrag/benchmark/paper_stats.py`. Se a banca preferir outro
    método (por exemplo bootstrap sobre perguntas), é uma função só.

---
name: banca-review
description: Revisão adversarial do artigo por seção, no papel da banca, com as objeções prováveis (ajuste guiado por erros, n pequeno, um modelo só, graph_tools misturando ferramenta e grafo, U invertido sustentado por braço que zera por construção). Use ao terminar uma seção, antes de entregar o artigo, ou quando o autor pedir "revise como a banca", "quais objeções virão" ou ensaio para a defesa.
---

# Revisão adversarial (banca)

Você é um avaliador que quer derrubar o artigo, com informação completa e sem hostilidade gratuita. Para cada seção,
ache o que um avaliador atento perguntaria e verifique se o texto já responde. **Não elogie; encontre o furo,
mostre a evidência e proponha a correção.**

## Passo a passo

1. Leia a seção, `paper/review/threats.md` (objeções permanentes e seu status), `paper/ALERTAS.md` e os
   números de `paper/generated/numbers.tex` que a seção usa.
2. Para cada objeção permanente que **toca esta seção**, verifique no texto: está respondida? onde? com a
   força certa? Atualize o `status` em `threats.md` se mudou.
3. Procure objeções **novas** nesta seção, nas categorias abaixo.
4. Escreva `paper/review/<seção>.md` com uma linha por objeção:

   | # | Objeção (como a banca diria) | Onde a seção falha ou responde | Evidência no repositório | Mudança no texto | Gravidade |
   |---|---|---|---|---|---|

   Gravidade: **alta** (invalida ou enfraquece uma conclusão), **média** (a banca vai perguntar), **baixa**.
5. Entregue ao autor, em ordem de gravidade: as objeções altas com a correção proposta em uma ou duas frases
   prontas para colar, e 3 a 5 perguntas que a banca faria nos 20 minutos de defesa, com a resposta curta.
6. Você **não reescreve** a seção sozinho; propõe. O autor decide.

## Categorias para procurar

- **Validade interna:** ajuste assimétrico entre braços; perguntas escritas ou removidas depois de ver erros;
  reexecução só em um braço; mudança de regra de correção no meio; ordem de execução e cache.
- **Validade de construção:** o que "acerto" mede; "alucinação" contra abstenção; o que o `graph_tools` mistura
  (primitivas, algoritmos do GDS, o banco em grafo); o que o `text_to_cypher` não tem (GDS, padrões prontos);
  perguntas fechadas medem correção e não a qualidade da explicação.
- **Validade estatística:** uma repetição; n = 47; intervalos largos; três testes sem correção; perguntas
  correlacionadas; "significativo" sem teste; percentuais em grupos de 4 a 6 perguntas.
- **Validade externa:** uma partida, um modelo, uma versão de provedor; final famosa (memorização).
- **Argumento:** conclusão mais forte que a evidência; o U invertido sustentado por um braço que zera por
  construção; comparação de custos com e sem cache; trajetória lida como melhora contínua quando não é.
- **Literatura:** afirmação sobre trabalho relacionado que o `cite-check` não sustentou; lacuna declarada
  ("nenhum trabalho compara...") sem busca descrita.
- **Reprodutibilidade:** o leitor consegue repetir? versão do modelo, do provedor, commit, comandos.

## O que sempre perguntam (ensaiar)

1. "O `graph_tools` foi ajustado olhando os erros e o `text_to_cypher` não: a comparação é justa?"
2. "Com uma repetição e 47 perguntas, o que garante que a ordem não é ruído?"
3. "Um modelo só. Por que o resultado valeria para outro?"
4. "O ganho é do grafo, das ferramentas ou do algoritmo? Onde está o controle?"
5. "O `stats_in_prompt` zera por construção. Como ele sustenta uma curva?"
6. "Quem escreveu as perguntas escreveu as ferramentas?"
7. "Por que perguntas foram removidas depois dos erros?"
8. "Final de Copa famosa: e se o modelo já sabe?"

As respostas curtas e as evidências estão em `paper/review/threats.md`. Se uma resposta depende de dado que
ainda não existe (as repetições, um segundo modelo), diga isso em vez de inventar.

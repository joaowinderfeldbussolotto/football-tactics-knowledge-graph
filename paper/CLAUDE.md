# Escrita do artigo (paper/)

Artigo da disciplina, em português, sobre "Quem faz o cálculo? Seis formas de dar a um LLM acesso a dados de
eventos de futebol". Prazo de entrega: 18/10/2026. **Leia `paper/dossie.md` (a pesquisa) e `paper/ALERTAS.md`
(onde o dossiê não se sustenta) antes de escrever qualquer seção.**

## Regras que valem sempre

1. **O código e os resultados não mudam.** Nenhuma ferramenta, pergunta, schema ou gabarito é alterado para o
   artigo. A única exceção é corrigir um número que o texto mostre estar errado. Rodar o benchmark gasta
   crédito: só com pedido explícito do autor.
2. **Nenhum número digitado no texto.** Todo número vem de uma macro de `generated/numbers.tex`
   (`\accGraphTools`, `\nQuestions`, `\mcTextToCypherEventsInPromptP`...). Antes de escrever, liste as macros
   (`grep newcommand paper/generated/numbers.tex`). Falta uma? Acrescente em `scripts/paper_numbers.py`, com teste.
   Skill: `paper-numbers`.
3. **Toda afirmação tem uma citação ou uma macro de número.** Citação só de uma chave de `refs.bib`, e só depois
   do `cite-check` ter sustentado a frase (`paper/claims.md`). Nunca inventar referência, DOI, página ou número.
4. **Estilo:** skill `paper-style-pt` (voz impessoal; passado para o que foi feito, presente para o que os
   resultados mostram; sem adjetivo de propaganda; sem travessão; glossário fixo em `paper/glossary.tsv`).
   `python paper/scripts/lint_paper.py` tem de dar limpo antes de qualquer commit de texto.
5. **Figuras:** skill `latex-figures`; geradas por `scripts/figures.py`, nunca à mão.
6. **Antes de dar uma seção por pronta,** skill `banca-review` (objeções em `paper/review/threats.md`).
7. **Uma repetição por pergunta enquanto as repetições não rodarem:** escrever "indica", não "demonstra"; não
   chamar de significativa uma diferença sem o teste (`\mc...PHolm`).

## Onde está cada coisa

| O quê | Onde |
|---|---|
| Texto, uma seção por arquivo | `paper/sections/*.tex` (roteiro em comentários; orçamento de páginas) |
| Preâmbulo e ordem das seções | `paper/main.tex` (preâmbulo do template, confirmado em 10/10/2026) |
| Referências | `paper/refs/references.tsv` → `paper/refs.bib` (`paper/scripts/fetch_bibtex.py`) |
| Números, tabelas, figuras | `paper/generated/` (gerado; não editar) |
| Afirmação contra fonte | `paper/claims.md` (gerado por `paper/scripts/cite_check.py`) |
| Objeções da banca | `paper/review/` |
| Configuração do template | `paper/template.json` (`confirmed: false` até conferir) |
| Resultados | `data/benchmark/final_results.jsonl` (uma repetição); `repeats_final_results.jsonl` depois das repetições |
| Páginas de cada rodada | `docs/execucoes/` |

## O ciclo

```bash
python scripts/paper_numbers.py && python scripts/figures.py   # depois de qualquer mudança nos resultados
python paper/scripts/cite_check.py                             # depois de qualquer \cite novo
python paper/scripts/lint_paper.py                             # antes de commitar
python -m pytest tests/test_paper.py -q
```

## Overleaf

O repositório é a fonte da verdade e o Overleaf só compila. Sincronize pelo MCP `claudeleaf` (ferramentas
`overleaf_*`: listar projetos, ler e editar documentos, compilar) e nunca edite o mesmo arquivo nos dois lados ao
mesmo tempo. Suba `sections/`, `generated/`, `refs.bib` e `main.tex`. O Overleaf mostra o histórico: toda
edição do agente fica atribuída à conta dele. Configuração da sessão na web, plano B pela CLI e o que está
verificado: `paper/OVERLEAF.md`. **Primeira coisa a fazer:** abrir o projeto da disciplina, descobrir a classe
LaTeX e o estilo de citação, preencher `paper/template.json` e trocar o preâmbulo de `main.tex` pelo do template.

**Skills.** Há a `academic-writing` (de terceiros, genérica). Quando ela conflitar com `paper-style-pt`
(primeira pessoa do plural, travessão, estrutura IMRaD no lugar da estrutura da disciplina), vale a
`paper-style-pt`.

## Fatos que o texto não deve errar

- Modelo: Claude Haiku 5.5 via OpenRouter, temperatura 0, mesmo prompt de sistema e mesma saída estruturada em
  todos os braços. O prompt não nomeia a partida.
- `text_to_cypher` e `graph_tools`: mesmo grafo, mesmo limite de 12 chamadas; muda quem escreve a lógica. O
  `text_to_cypher` não tem a biblioteca de algoritmos (GDS) nem os nós de padrões prontos (`PadraoTatico`).
- O `graph_tools` foi ajustado olhando erros (sete congelamentos, v2 a v3.1, e uma reexecução de seis
  perguntas); o `text_to_cypher` é primeiro contato. Isso vai no texto principal.
- Controle: as cinco perguntas sem resposta nos dados. Reportar sempre com e sem elas.
- Perguntas: 52 ativas de 81 escritas; 22 removidas pelo teste de robustez ou por ambiguidade.

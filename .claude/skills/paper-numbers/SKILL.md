---
name: paper-numbers
description: Regenera paper/generated/numbers.tex, as tabelas e as figuras a partir dos resultados versionados e falha se o texto tiver número solto. Use ao citar qualquer número no artigo, quando os resultados mudarem (por exemplo depois das repetições) ou quando o autor pedir "atualize os números" ou "confira os números".
---

# Números, tabelas e figuras do artigo

Nenhum número do artigo é digitado. Cada um é uma macro de `paper/generated/numbers.tex`, gerada de
`data/benchmark/final_results.jsonl` (ou do arquivo mesclado das repetições). Mudou o resultado, o artigo inteiro
acompanha.

## Comandos

```bash
python scripts/paper_numbers.py            # numbers.tex e generated/tables/*.tex
python scripts/paper_numbers.py --check    # falha se paper/generated/ está desatualizado
python scripts/figures.py                  # generated/figures/*.pdf
python paper/scripts/lint_paper.py         # falha se o texto tem número solto
```

Depois das três repetições (ver `paper/README.md`), aponte os dois primeiros para o arquivo mesclado:
`--results data/benchmark/repeats_final_results.jsonl`.

## Como usar no texto

1. Liste o vocabulário: `grep newcommand paper/generated/numbers.tex`. Os nomes têm só letras:
   prefixo + grupo + braço. Exemplos: `\accGraphTools` (acerto nas perguntas com resposta), `\kGraphTools`
   (quantas), `\ciLowGraphTools` e `\ciHighGraphTools` (intervalo de Wilson), `\accAllGraphTools` (com o
   controle), `\accPlaysTextToCypher` (grupo × braço), `\mcTextToCypherEventsInPromptFirst`, `...Second`, `...P`,
   `...PHolm` (McNemar), `\hallGraphTools`, `\abstGraphTools`, `\tokInGraphTools`, `\callsGraphTools`,
   `\latGraphTools`, `\nQuestions`, `\nAnswerable`, `\nRuns`, `\costFinal`, `\preFixKGraphTools`.
2. Escreva `\accGraphTools{}` com chaves vazias quando a macro vier antes de uma palavra, para o espaço não sumir.
   Percentuais já trazem `\%`; decimais usam vírgula (`0,017`); milhares usam ponto (`76.118`).
3. Tabelas: `\input{generated/tables/ladder}` (acerto com IC), `groups`, `mcnemar`, `cost`. Estão sem o ambiente
   `table`: ponha a legenda e o rótulo no texto, em volta.
4. Precisa de um número que não existe? Acrescente-o em `build()` de `scripts/paper_numbers.py` (ou em
   `src/football_graphrag/benchmark/paper_stats.py` se for estatística), gere de novo e acrescente uma
   asserção em `tests/test_paper.py`. Nunca escreva o número à mão "só por enquanto".
5. Custo em dólares não está nos resultados: vem de `paper/data/costs.yaml`, que o autor preenche.

## Regras de leitura dos números

- **Unidade é a pergunta.** Com repetições, o acerto de um braço numa pergunta é a fração de repetições certas;
  o intervalo é o de Wilson com n = perguntas; o McNemar usa o resultado por maioria. Está no cabeçalho de
  `paper_stats.py` e vai para a Metodologia.
- Reporte sempre **com e sem as perguntas sem resposta**. O controle é acertado por quem responde "sem dados".
- Diga o **denominador** de cada erro (47 com resposta, 52 no total).
- Os braços `no_context`, `vector` e `stats_in_prompt` têm uma repetição mesmo depois da rodada de repetições
  (`\repNoContext`, `\repVector`...): a Metodologia diz isso.
- Antes de afirmar uma diferença, olhe `\mc...PHolm` (três testes, ajuste de Holm), não só `\mc...P`.
- Não compare custos de braços com e sem cache de prompt sem dizer (`paper/ALERTAS.md`, item 7).

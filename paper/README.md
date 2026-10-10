# Artigo: preparação e ciclo de escrita

Branch `paper/writing`, a partir de `refactor/benchmark-final`. Aqui está tudo o que o artigo usa: o dossiê, as
referências, o esqueleto do texto, os números e figuras gerados dos resultados, e as skills do Claude Code. O
texto em si ainda não foi escrito.

## Antes de tudo, na sua máquina

```bash
git fetch && git checkout paper/writing
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,paper]"                    # não precisa de Neo4j, Docker nem chave de API
python -m pytest tests/test_paper.py -q             # deve passar
```

Abra o Claude Code na raiz do repositório. Ele lê `CLAUDE.md` (raiz) e `paper/CLAUDE.md` e carrega as cinco
skills de `.claude/skills/` (`paper-style-pt`, `cite-check`, `paper-numbers`, `latex-figures`, `banca-review`).
O MCP do Overleaf (`.mcp.json`) e a skill de escrita acadêmica (`.claude/skills/academic-writing`) também estão no
repositório, para funcionar na web e na sua máquina; nada aqui depende deles, exceto a sincronização com o Overleaf.
O passo a passo, o que foi verificado e o que falta (a sessão do Overleaf) estão em `paper/OVERLEAF.md`.

**Leia `paper/ALERTAS.md` primeiro:** são dez pontos em que o dossiê não se sustenta como está escrito, e o
mais importante é a trajetória de ajuste (item 1).

## O que está pronto

| Peça | Estado |
|---|---|
| `paper/dossie.md` | o dossiê, sem alteração |
| `paper/refs/references.tsv`, `paper/refs.bib` | as 27 referências com DOI, geradas do resolvedor de DOI (os três DOIs "conferir" do dossiê resolvem para os artigos certos); mais seis fontes de software e dados |
| `paper/sections/*.tex`, `paper/main.tex` | esqueleto com o roteiro e o orçamento de páginas de cada seção, sem prosa; preâmbulo do template (duas colunas, `plain`, babel brasileiro) |
| `paper/generated/numbers.tex`, `tables/`, `figures/` | números, tabelas (escada, grupos, McNemar com Holm, custo) e figuras F2, F3, F4 geradas de `final_results.jsonl` |
| `paper/scripts/lint_paper.py` | números soltos, travessão, voz, adjetivo de propaganda, glossário |
| `paper/scripts/cite_check.py` | par frase e chave com o resumo da fonte, em `paper/claims.md` |
| `paper/review/threats.md` | 14 objeções permanentes da banca, com evidência e status |
| `.claude/skills/` | as cinco skills |

## O que falta, na ordem

1. ~~Confirmar o template~~ Feito em 10/10/2026 (`paper/template.json`, `confirmed: true`): `article` A4 12pt, duas colunas, `plain`. Figuras regeradas para a coluna de 3,47 pol; a F4 (largura de texto) não cabe numa coluna de `multicols*` e precisa de decisão.
2. **Rodar as três repetições** (gasta crédito; o saldo da chave estava em US$ 2,31 em 10/10). A repetição 1 do
   `graph_tools` em `final_results.jsonl` não é limpa: 46 das 52 perguntas rodaram antes das três correções (aspas
   soltas, 12 chamadas) e seis foram reexecutadas depois. O `events_in_prompt` e o `text_to_cypher` não sofreram
   mudança, então a repetição 1 deles serve. Plano que economiza o que dá, cerca de US$ 1,7 a 1,9 (o dossiê estimava
   1,5; a conta aqui é pelos tokens medidos):

   ```bash
   # semear com a repetição 1 de events_in_prompt e text_to_cypher
   python - <<'PY'
   import json
   rows = [json.loads(l) for l in open("data/benchmark/final_results.jsonl")]
   keep = [r for r in rows if r["arm"] in ("events_in_prompt", "text_to_cypher")]
   open("data/benchmark/repeats_results.jsonl", "w").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep))
   PY
   LLM_MODEL=anthropic/claude-haiku-5.5 python scripts/run_benchmark.py \
     --arms events_in_prompt,text_to_cypher,graph_tools --repeats 3 --resume \
     --output data/benchmark/repeats_results.jsonl --title "52 perguntas, 3 braços, 3 repetições"
   python scripts/merge_results.py data/benchmark/final_results.jsonl data/benchmark/repeats_results.jsonl \
     --output data/benchmark/repeats_final_results.jsonl
   ```

   O `graph_tools` (o braço caro, cerca de US$ 1,2 nas três repetições, sem cache) deve rodar primeiro; use
   `--arms graph_tools` na primeira chamada se o saldo for curto, e `--resume` continua de onde parou. Depois:
   preencher `paper/data/costs.yaml`, e `python scripts/paper_numbers.py --results data/benchmark/repeats_final_results.jsonl`
   (idem `scripts/figures.py`). `vector`, `no_context` e `stats_in_prompt` ficam com uma repetição; a Metodologia diz.
3. **Escrever, nesta ordem** (Metodologia e Trabalhos relacionados não dependem dos números): Metodologia,
   Trabalhos relacionados, Resultados, Discussão, depois Introdução, Contribuições, Conclusão, Resumo e a
   declaração de IA. A cada seção: `lint_paper.py`, `cite_check.py` (e a skill `cite-check` para os vereditos),
   `banca-review`.
4. **Figura F1** (arquitetura) e **F5** (exemplo de robustez, n01 contra s01 em `data/benchmark/robustness.md`):
   ainda não existem.
5. **Declaração de IA e hipóteses:** ajustar conforme `paper/ALERTAS.md` (itens 2 e 3).

## Decisões que são suas

- Português ou inglês (o dossiê assume português; o `lint_paper.py` tem a exceção `% lang: en` para o resumo).
- Como contar as repetições (escolha descrita no cabeçalho de `src/football_graphrag/benchmark/paper_stats.py`).
- Se vale gastar o orçamento restante num segundo modelo em vez de mais repetições.
- O que fazer com a trajetória F4, que não sobe de forma contínua (`ALERTAS.md`, item 1).

## Reproduzir os números sem rodar nada

```bash
python scripts/paper_numbers.py --check      # paper/generated/ bate com os resultados versionados?
python scripts/check_ground_truth.py         # (precisa de Neo4j) 52/52
python scripts/merge_results.py ...          # junta arquivos de resultado
```

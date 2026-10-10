# Registro das execuções

Uma página por execução do benchmark: configuração exata, custo real, o que
saiu e o que se aprendeu, com links para os traces no Langfuse. Os números
vêm sempre do arquivo de resultados da execução, nunca do Langfuse.

| # | Data | Execução | Modelo | Execuções | Acerto `graph_tools` | Custo real |
|---|---|---|---|---|---|---|
| [01](2026-10-07_01_amostra_deepseek-v4-pro.md) | 2026-10-07 | amostra (parcial) | DeepSeek V4 Pro (Cloudflare) | 17 | 3/3 | ~US$ 0,32 |
| [02](2026-10-07_02_amostra_claude-haiku-5.5.md) | 2026-10-07 | amostra | Claude Haiku 5.5 | 25 | 5/5 | ~US$ 0,27 |
| [03](2026-10-07_03_completa_claude-haiku-5.5_r1.md) | 2026-10-07 | completa, 1 repetição | Claude Haiku 5.5 + cache | 150 | 29/30 | ~US$ 0,23 |
| [04](2026-10-07_04_piloto-v2_claude-haiku-5.5.md) | 2026-10-07 | **v2**, piloto, 1 repetição | Claude Haiku 5.5 + cache | 50 | 5/10 | US$ 0,10 |
| [05](2026-10-07_05_piloto-v2.1_claude-haiku-5.5.md) | 2026-10-07 | **v2.1**, piloto, 1 repetição + 2 nas perguntas-alvo | Claude Haiku 5.5 + cache | 56 | 6/10 | US$ 0,24 |
| [06](2026-10-07_06_placar-list-actions_v2.2.md) | 2026-10-07 | **v2.2**, só `graph_tools` em a03, a05, f03 | Claude Haiku 5.5 | 3 | 2/3 | ~US$ 0,04 |
| [07](2026-10-07_07_completa-v2.2_claude-haiku-5.5_r1.md) | 2026-10-07 | **v2.2**, completa, 1 repetição | Claude Haiku 5.5 + cache | 125 | 20/25 | US$ 0,30 |
| [08](2026-10-07_08_placar-depois-do-gol_v2.3.md) | 2026-10-07 | **v2.3**, só `graph_tools` em f04, s03, a03 | Claude Haiku 5.5 | 3 | 3/3 | ~US$ 0,04 |
| [09](2026-10-08_09_completa-atual_claude-haiku-5.5_r1.md) | 2026-10-08 | completa, versão atual, 1 repetição | Claude Haiku 5.5 + cache | 125 | 24/25 | US$ 0,36 |
| [10](2026-10-08_10_perguntas-de-grafo-v3.md) | 2026-10-08 | **v3**, 20 perguntas de grafo, 2 braços | Claude Haiku 5.5 + cache | 40 | 10/20 | US$ 0,28 |
| [11](2026-10-08_11_perguntas-de-grafo-v3.1.md) | 2026-10-08 | **v3.1**, 17 perguntas de grafo, 2 braços | Claude Haiku 5.5 + cache | 34 | 11/17 | ~US$ 0,23 |
| [12](2026-10-10_12_all52.md) | 2026-10-10 | 52 perguntas, 5 braços, 1 repetição | claude-haiku-5.5 | 260 | 45/52 | US$ 0.92 |
| [13](2026-10-10_13_cypher.md) | 2026-10-10 | 52 perguntas, text_to_cypher, 1 repetição | claude-haiku-5.5 | 52 | – | US$ 0.12 |

> **As execuções 01 a 03 usaram dados com um erro na camada 0**, corrigido
> depois: em 44% das ações o lado do ataque estava invertido, o que deixava
> errados terço, corredor, xT e VAEP dessas ações (capítulo 7, seção 7.2).
> Contagens simples, gols, cartões e assistências não mudam. As respostas
> estruturais da v1 mudam (o 2º elo da Argentina passa a ser Messi; o trio
> mais repetido da França vira empate). Servem como registro, não como
> resultado.

## Sobre os links dos traces

Cada símbolo nas tabelas (✅ certo, ❌ alucinação, 🟡 abstenção, ⚠️ erro de
formato) abre o trace daquela execução no Langfuse: o prompt enviado, cada
ferramenta chamada com o resultado, e a resposta. **É preciso estar logado no
projeto do Langfuse** para abrir.

Desde o commit que acrescentou o campo, cada linha do `results.jsonl` já
grava o próprio `trace_url`, e o `ask.py` imprime o link. Para execuções
antigas, `scripts/trace_links.py --write` encontra os traces pelo nome e pelo
horário e preenche o campo.

## Como registrar uma nova execução

O `scripts/run_benchmark.py` escreve a página sozinho ao terminar: cria
`AAAA-MM-DD_NN_<arquivo>.md` nesta pasta (configuração, commit, comando,
custo real, resultado por grupo e braço, erros, leitura automática, cada erro
com a resposta esperada e os traces) e acrescenta a linha no índice acima.

1. Rode com um arquivo de saída próprio quando não for a execução principal:
   `python scripts/run_benchmark.py --repeats 1 --output data/benchmark/<nome>_results.jsonl --title "<título>"`.
   `--no-report` pula a página.
2. O custo real sai do consumo da chave no OpenRouter antes e depois
   (`https://openrouter.ai/api/v1/key`, campo `usage`); com outro provedor fica
   "não medido". Se parecer fora do esperado, consulte chamada por chamada em
   `https://openrouter.ai/api/v1/generation?id=<id>` (campo `provider_name`).
3. Para refazer a página de um arquivo que já existe:
   `python scripts/report_run.py --results <arquivo>.jsonl [--title ...] [--cost ...]`.
4. Faça commit do arquivo de resultados, do resumo e da página juntos. A
   leitura automática só descreve os números; o que eles querem dizer vai à mão
   numa seção a mais, se for preciso.

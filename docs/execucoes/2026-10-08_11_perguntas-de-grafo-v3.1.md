# Execução 11: perguntas de grafo (v3.1), 2 braços, 1 repetição

| | |
|---|---|
| Data | 2026-10-08 |
| Tipo | 17 perguntas de grafo (estágio `graph`) × 2 braços (`events_in_prompt`, `graph_tools`) × 1 repetição = 34 execuções |
| Modelo | `anthropic/claude-haiku-5.5` via OpenRouter, temperatura 0 |
| Tools | v3.1: filtro `receiver` nas ações; `pass_network` devolve `left_without_connection` |
| Perguntas | as 15 da execução 10 que ficaram (sem os triângulos t01–t05) + p09 e b09 |
| Código | branch `refactor/benchmark-v3-graph`, commit `7b10890` |
| Comando | `LLM_MODEL=anthropic/claude-haiku-5.5 python scripts/run_benchmark.py --repeats 1 --output data/benchmark/graph_v31_results.jsonl` (braços de `config/benchmark.yaml`) |
| Custo real | ~US$ 0,23 (estimado pelos tokens, na proporção da execução 10; o consumo da chave não foi anotado logo antes) |
| Arquivos | [`graph_v31_results.jsonl`](../../data/benchmark/graph_v31_results.jsonl), [`graph_v31_summary.md`](../../data/benchmark/graph_v31_summary.md) |

## Resultado

| Tipo | Perguntas | `events_in_prompt` | `graph_tools` |
|---|---|---|---|
| structure (jogador que isolaria um companheiro) | 1 | 0 | 1 |
| counterfactual (rede sem um jogador) | 2 | 1 | **2** |
| sequence (passe e finalização) | 1 | 0 | 1 |
| play (jogadas inteiras) | 7 | 0 | 4 |
| substitution (antes e depois de uma substituição) | 6 | 1 | 3 |
| **total** | 17 | 2 (12%) | **11 (65%)** |

| Braço | Alucinação | Abstenção | Erro de formato | Tokens de entrada por pergunta | Chamadas de tool | Latência |
|---|---|---|---|---|---|---|
| `events_in_prompt` | 24% | 65% | 0% | 111.430 | – | 4,6 s |
| `graph_tools` | 18% | 12% | 6% | 97.029 | 4,2 | 8,4 s |

## Leitura

- **O que as correções da v3.1 resolveram:** c02 (Pezzella isolado sem
  Otamendi) e b03 (quem mais passou para Mbappé) passaram a acertar, cada uma
  pelo motivo previsto (`left_without_connection` e o filtro `receiver`).
  t06 e q01 também acertaram.
- **Variação de uma execução para outra:** p01, p05 e b02 estavam certas na
  execução 10 e erraram aqui, sem mudança de ferramenta que as afete. Com 1
  repetição, uma pergunta a mais ou a menos é ruído.
- **p01:** achou a dupla certa (Enzo e Messi, 23 jogadas), mas listou também
  as duplas seguintes na resposta.
- **p05:** o modelo mandou `group_by` com aspas a mais (`"\"pair\""`) três
  vezes seguidas e esgotou as tentativas. Erro do modelo, fica como resultado.
- **p09:** pediu só jogadas terminadas em `finalizacao` e deixou de fora o
  pênalti de Mbappé aos 118', que é a segunda jogada. **A pergunta tem uma
  leitura que o teste de robustez não cobriu** (pênalti conta como jogada
  terminada em finalização?): sem o pênalti a resposta é 1, não 2.
- **b01:** chamou `pass_paths` com 3 jogadores e leu "os três passando a bola
  uns para os outros" como sequência, o mesmo problema dos triângulos
  retirados.
- **b02 e b04:** gastaram 6 a 8 das 8 chamadas procurando o momento da
  substituição com `list_actions` e responderam "sem dados" ao bater no
  limite. Nenhuma ferramenta informa quando um jogador entrou ou saiu.
- **`events_in_prompt`:** respondeu "sem dados" em 11 das 17 e acertou c02 e
  b09.

## Traces

| pergunta | `events_in_prompt` | `graph_tools` |
|---|---|---|
| t06 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9865a0039522f56b12287d3ea2e40aad) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e570cbc16f61d974c0214c2d906ace9d) |
| c01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/831140e539ab0a710c346484f23a772c) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9c700a6348a83bf937256fd47e06edae) |
| c02 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/14d9eb151deb9906e33939a240148782) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e0fe4ed85a577f5841f40b31dc7a9ee8) |
| q01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/01c182dca891f73b933e7a37ccf60369) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/df08c8a9037e94b040615264c08aee48) |
| p01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/99917351c759e08e043d41586a2f215b) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/bda6c39e0d47e51ccb8fc34c85fb7bc4) |
| p02 | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/0273b34b8a8fb0b6ce3fb010c5ee2eea) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/fa73983c638302d527cb5b8e71d6d2c7) |
| p03 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/a6496476aa9287ac37b29c2a435bdf8d) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/f12ec82c4a95086f287d190145e74248) |
| p04 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/f88ca53f26d3c382bd150580394dd5f2) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/8da94fa18a64ebfb036c27ec80b30c6f) |
| p05 | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/10bbc68e998c7ab25cb8d95b65175dbb) | [⚠️](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e866f6fe2aa233197c1acc169ba6cdf9) |
| p06 | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/492b2b166af2540f05e0f2c0d34ce47e) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c7d5b362e68c2a6d9eb5a7d773685a17) |
| p09 | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/f21ad43e239ea16ded149458482d3967) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/7fb22fc8354138c69efe053f84aecae2) |
| b01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e6a90ffc1eebc2c29d5ea232f3116948) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/b5a40e2f47fdfe9d85c3bf98f6a3d9ee) |
| b02 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/8b4a56b22ddc87250a7b54a88e9db648) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/7759bc7fa4cbaeac05144aaeff613ae5) |
| b03 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/317107b4b5e624ffd3aa0b97a4962697) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/64b5d84cf6b83c1b2ca7bc16a973efbd) |
| b04 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/04e7544fac2ca55107039f8126788fc6) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/354f46e3ecc838eba5769eaa2ea53bff) |
| b05 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e880c4b37fc3d296dbe6ac70671e3c52) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/5479ef86869a61d1eed281108e01cd3a) |
| b09 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/2ec9992474b31c222e88c55732c178eb) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/059af8b86f58824ec5792f46d14fe710) |

✅ certo · ❌ alucinação · 🟡 abstenção · ⚠️ erro de formato. Cada símbolo abre o trace no Langfuse.

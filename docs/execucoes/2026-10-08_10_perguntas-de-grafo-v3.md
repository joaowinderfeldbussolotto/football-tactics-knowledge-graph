# Execução 10: perguntas de grafo (v3), 2 braços, 1 repetição

| | |
|---|---|
| Data | 2026-10-08 |
| Tipo | 20 perguntas de grafo (estágio `graph`) × 2 braços (`events_in_prompt`, `graph_tools`) × 1 repetição = 40 execuções |
| Modelo | `anthropic/claude-haiku-5.5` via OpenRouter, temperatura 0 |
| Tools | v3: `pass_network` sem jogadores, triângulos, `pass_paths` com a ação final, `query_possessions` |
| Código | branch `refactor/benchmark-v3-graph`, commit `52bfb03` |
| Comando | `LLM_MODEL=anthropic/claude-haiku-5.5 python scripts/run_benchmark.py --repeats 1 --output data/benchmark/graph_results.jsonl` (braços de `config/benchmark.yaml`) |
| Custo real | US$ 0,28 |
| Arquivos | [`graph_results.jsonl`](../../data/benchmark/graph_results.jsonl), [`graph_summary.md`](../../data/benchmark/graph_summary.md) |

## Resultado

| Tipo | Perguntas | `events_in_prompt` | `graph_tools` |
|---|---|---|---|
| structure (triângulos, jogador que isolaria um companheiro) | 6 | 0 | 1 |
| counterfactual (rede sem um jogador) | 2 | 0 | 1 |
| sequence (passe e finalização) | 1 | 0 | 0 |
| play (jogadas inteiras) | 6 | 2 | **6** |
| substitution (antes e depois de uma substituição) | 5 | 0 | 2 |
| **total** | 20 | 2 (10%) | **10 (50%)** |

| Braço | Alucinação | Abstenção | Tokens de entrada por pergunta | Chamadas de tool | Latência |
|---|---|---|---|---|---|
| `events_in_prompt` | 20% | 70% | 122.693 | – | 4,7 s |
| `graph_tools` | 40% | 10% | 97.845 | 3,6 | 8,2 s |

## Leitura

- **Jogadas inteiras:** o `graph_tools` acertou as 6, cada uma com uma
  chamada a `query_possessions`. O `events_in_prompt` respondeu "sem dados"
  em 4.
- **Triângulos:** nos 5, os dois braços leram "o trio que mais trocou passes
  entre si, com os três passando a bola uns para os outros" como **sequência**
  A → B → C, não como os três trocando passes em todas as duplas. O
  `graph_tools` chamou `pass_paths` em vez da métrica de triângulos, e os
  dois braços chegaram ao mesmo trio errado na t01. O teste de robustez não
  incluía essa leitura.
- **Rede sem um jogador (c02):** sem Otamendi, Pezzella não troca passe com
  ninguém e some da rede. O modelo olhou só os jogadores que restaram e
  concluiu que ninguém ficava isolado.
- **Substituições:** o modelo errou o momento da saída (b01) ou contou os
  passes recebidos por todos em vez dos passes para Mbappé (b03): os filtros
  de ação não têm "recebedor". Na b04, contou passes à mão e bateu no limite
  de chamadas.
- **q01:** leu a sequência [passador, recebedor] ao contrário e contou o
  passador como quem finalizou.

## Traces

| pergunta | `events_in_prompt` | `graph_tools` |
|---|---|---|
| t01 | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/5491d93a9eaf8eaf7f2cc20c1fdd41af) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/a0f26c18a0d7bd1020e472c04a8c8aaf) |
| t02 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/cac597973775e18c0dbddb9383fc11f8) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e94222a4c2eb6e85e48d55399cd87cf1) |
| t03 | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/7fe47575038c9334b7328b94db2b9ea3) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/7ccbb310d6cb7bd762838be53be922b1) |
| t04 | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/bf415babb64ed10770b6900578e71181) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/12f7fc2c7fc7a1a40e8864b5e9904d7b) |
| t05 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/fc9f32a902bc0bd21afb10ef816713cc) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/dc406e51d94a77516111a1c5c8f86149) |
| t06 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/239e043c5a278ae1df3b91494cc0ac2c) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/46add8bce2feff2cec5526afe6c1ea47) |
| c01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/be082bc199c2fa0b93da23f0662c1876) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/250fc0a2667ca7d794ed81ea17445e43) |
| c02 | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e40d197b09970e0047a5296aa7d81210) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c36af63d391ee1e5b9c618ad7cc0ae0b) |
| q01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/d7041c25158edefb7766141f00e07173) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/578a627d0dce96f78692082e42498376) |
| p01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/db4654b19bf85cc3415c2de397c416db) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/47ad755df22230702d75d20389b9464b) |
| p02 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/8b46511d1f60f56fdc8f0ef707f1b5de) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/5ad00062e5574af6672bc6b412971929) |
| p03 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/545ca927ebf2c96f8dcc02f4c437449e) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e77003d82fa6eeb2b469732825431cb2) |
| p04 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/40f4c65c53b9cbaedbaf8d95276e5ebb) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/d915baf574e803a15171f5b752a3ab58) |
| p05 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c9755012509bbe8c7d9a3b1f6457bb5b) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/f838fa77eb281043720583c357cfd0be) |
| p06 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/65a0efd90a04acfa310514dc030435be) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/3d042a6622720f1d8cf530acd74a355f) |
| b01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/00e81cea002ea2eb31b485303cc32575) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/71d8fe683c419f18f66629d598121396) |
| b02 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9b225ddec5fd8c4e4aec5a8b9742b48a) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/6111a734bea4ee83ec71861708f57e6b) |
| b03 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/6ddb9595ae9fffc65de686c91ca638ea) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/a033d46953cb0465d7831345ab24b671) |
| b04 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/0e72a3f3377dd0992ccb11da61c747ab) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c87d25cff5d4ba35a88f2905ac2c7802) |
| b05 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/872a2e1c9a3a0f5a5c32af3c4cd53ada) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/dde455cc01186048d98b2ba7f77c052d) |

✅ certo · ❌ alucinação · 🟡 abstenção · ⚠️ erro de formato. Cada símbolo abre o trace no Langfuse.


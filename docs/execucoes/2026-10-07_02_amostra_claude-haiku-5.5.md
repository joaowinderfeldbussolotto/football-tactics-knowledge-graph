# Execução 02: amostra com Claude Haiku 5.5

| | |
|---|---|
| Data | 2026-10-07, 20:03 a 20:04 UTC |
| Tipo | amostra (`--sample`): 5 perguntas (f01, a01, s01, c01, u01) × 5 braços, 1 repetição |
| Modelo | `anthropic/claude-haiku-5.5` via OpenRouter (Claude Platform on AWS) |
| Configuração | temperatura 0, `LLM_MAX_TOKENS=16000`, sem raciocínio estendido, **sem cache de prompt** |
| Código | commit `f37d369` (sem cache de prompt) |
| Custo real | ~US$ 0,27, sendo ~US$ 0,26 só do `events_in_prompt` |
| Arquivos | [`sample_claude-haiku-5.5.jsonl`](../../data/benchmark/sample_claude-haiku-5.5.jsonl), [resumo](../../data/benchmark/sample_claude-haiku-5.5_summary.md) |

## Para que serviu

Comparar com o DeepSeek em custo, tempo e comportamento, antes de escolher o
modelo da execução completa.

## Resultado

| Braço | Acerto | Tempo médio |
|---|---|---|
| `graph_tools` | **5/5** | 3,5 s |
| `events_in_prompt` | 2/5 | 3,6 s |
| `stats_in_prompt` | 1/5 | 2,0 s |
| `vector` | 1/5 | 2,3 s |
| `no_context` | 1/5 | 1,7 s |

## Achados

1. **~50 vezes mais rápido que o DeepSeek**: o Haiku não raciocina antes de
   responder, então cada chamada leva segundos.
2. **Acima de ~100 mil tokens, o preço sobe 5 vezes**, e o catálogo não
   mostra isso. As chamadas pequenas saíram a US$ 0,10 / 0,50 por milhão; as
   do `events_in_prompt` (~101 mil tokens) a ~US$ 0,50 / 2,50, ~US$ 0,05
   cada. Isso motivou o cache de prompt da execução 03.
3. **O `graph_tools` escolheu bem as ferramentas**, com 1,2 chamadas por
   pergunta em média. Na c01, encadeou a centralidade da rede e a súmula do
   Otamendi ([trace](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/1ea72e6bc36d19522dcc8e281e49fbd4)).
4. **O `stats_in_prompt` se confunde com a tabela larga** (30 colunas) na a01
   ([trace](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/ad05f739b29f66f389efbf7ffb7c5ec7)). Nas perguntas de rede, ele
   reconheceu que a súmula não tinha o dado e se absteve.

## Traces

| pergunta | `no_context` | `vector` | `events_in_prompt` | `stats_in_prompt` | `graph_tools` |
|---|---|---|---|---|---|
| f01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/3ac5a01ebcce674f45f6fd157a9d0b75) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/ef3736da2b41871015c6fe61d08f12f1) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/4b20240cda9bf8a526da7bec23a78f4f) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/ab4ecd0b6bb251dbe94ad166f031a707) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/2a41f69655342c967c41d418e9534ea5) |
| a01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/ef004b87a6e260e1d1c4f939d9c49867) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/431ec77b73acc36f4dea2548415ccd2a) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c6ace5e4fb981da5881bb103a094b99f) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/ad05f739b29f66f389efbf7ffb7c5ec7) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/38da5238b24024db0f8c3e36cbe39c6a) |
| s01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9f157bf2fe6be84bac990569089fb03b) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/bf6b2f5c1f704e122403226c26c0fe34) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/ea3ac6292b2c9d4058da3ae83470d445) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/963f177da3766ffcd066926726ab8b45) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/1b22a58ee793e45404a3a02c403d818e) |
| c01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/0cec86a3a2080c57bd1067830b7f14c7) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/13b1d356f15c12e33acd08eec80c9e48) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/babcbd8e7333d78317cf71e37bbf7972) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/67ef2fc36db5d80e54136f84558934ac) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/1ea72e6bc36d19522dcc8e281e49fbd4) |
| u01 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/55eefb2778bb937627f176cc67a20afa) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/fef08820e3f50055e936153653ad5ee4) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/865f9e92c2db899f9c0294ac1606efb9) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/055c04c81656950ec20d74b72e8b08b5) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c3f701546a0bfa0c48a23a915f0f9d49) |

✅ certo · ❌ alucinação · 🟡 abstenção · ⚠️ erro de formato. Cada símbolo abre o trace no Langfuse.

# Execução 01: amostra com DeepSeek V4 Pro (parcial)

| | |
|---|---|
| Data | 2026-10-07, 19:26 a 19:47 UTC |
| Tipo | amostra (`--sample`): 1 pergunta por tipo, 1 repetição. **Parada de propósito** após 17 de 25 execuções |
| Modelo | `deepseek/deepseek-v4-pro` via OpenRouter, atendido pela **Cloudflare** |
| Configuração | temperatura 0, `LLM_MAX_TOKENS=16000`, raciocínio no padrão do modelo, sem cache de prompt |
| Código | commit `f37d369` (antes do cache de prompt) |
| Custo real | ~US$ 0,32 (consulta de cada chamada em `openrouter.ai/api/v1/generation`) |
| Arquivos | [`sample_deepseek-v4-pro_cloudflare.jsonl`](../../data/benchmark/sample_deepseek-v4-pro_cloudflare.jsonl), [resumo](../../data/benchmark/sample_deepseek-v4-pro_cloudflare_summary.md) |

## Para que serviu

Medir os tokens reais de cada braço para estimar o custo da execução completa.

## Resultado (17 execuções; não é conclusivo)

| Braço | Acerto | Observação |
|---|---|---|
| `graph_tools` | 3/3 | |
| `events_in_prompt` | 2/3 | na pergunta estrutural, gastou os 16 mil tokens só raciocinando ([trace](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/037fe7166a4a137be6e27d0185c2361c)) |
| `stats_in_prompt` | 1/3 | |
| `vector` | 0/4 | todas alucinações |
| `no_context` | 0/4 | todas abstenções (obedeceu à instrução) |

## Achados

1. **O OpenRouter mandou as chamadas para um provedor caro.** O catálogo mostra
   US$ 0,209 / 0,418 por milhão de tokens, mas todas as chamadas foram atendidas
   pela Cloudflare, que cobrou o equivalente a **US$ 1,15 / 2,55**: ~5,5 vezes
   mais. Lição: conferir o custo real por chamada, não só o preço do catálogo.
2. **O modelo raciocina muito, e isso define tempo e custo.** A velocidade foi
   constante (~35 tokens/s); o que varia é quanto ele escreve antes de
   responder. Na a01, o `vector` escreveu 8,7 mil tokens (233 s) para chegar a
   uma resposta errada ([trace](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/3fdbe1b3c6de83fa54b566e84a9c77c7)). Com o
   raciocínio, o `events_in_prompt` acertou a contagem de desarmes
   ([trace](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/a9ab664f0750ebf59eb31db6a9f9336f)), que o Haiku errou depois.
3. **A base vetorial não é reindexada**: o índice foi criado uma vez, na
   primeira pergunta, e reaproveitado.

## Traces

| pergunta | `no_context` | `vector` | `events_in_prompt` | `stats_in_prompt` | `graph_tools` |
|---|---|---|---|---|---|
| f01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/b6b646d2f9519d234fe177672977c280) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/fb0ade4a24e054df2f729a5872ce458a) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/5f1ea8991ca886b8adab2a59cba1130c) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/41198c2d60bc3c2d568db1b94ce9357f) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/dd76e7afca43cb6f81512771585c090f) |
| a01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/1b02e007daf66ac5fa6f5077d964541f) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/3fdbe1b3c6de83fa54b566e84a9c77c7) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/a9ab664f0750ebf59eb31db6a9f9336f) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c85ac3bfe5f12b7e9b35d9fac288b004) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/494dcbf1453422567ca65dc1dde6912a) |
| s01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e4fa1958d6136d2fd85a67ad285c1cb5) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/09ded09c2e2f37aabb573fcd6e49ca7a) | [⚠️](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/037fe7166a4a137be6e27d0185c2361c) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c91d4489e843146cd58e1d4d865afb54) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/7afcb4ecda13147de1c7cb1636521c98) |
| c01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/681d0fcf6657ffd08d744b83518d8b24) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/87aed7d42efcf1d939a48696551f0f7d) | – | – | – |

✅ certo · ❌ alucinação · 🟡 abstenção · ⚠️ erro de formato. Cada símbolo abre o trace no Langfuse.

# Execução 04: piloto da v2 com Claude Haiku 5.5

| | |
|---|---|
| Data | 2026-10-07, 21:55 a 21:59 UTC (~4 minutos) |
| Tipo | piloto da v2, 1 repetição: 10 perguntas (2 por tipo) × 5 braços = 50 execuções |
| Modelo | `anthropic/claude-haiku-5.5` via OpenRouter |
| Configuração | temperatura 0, `LLM_MAX_TOKENS=16000`, sem raciocínio estendido, cache de prompt em `events_in_prompt` e `stats_in_prompt` |
| Dados | camada 0 corrigida (lado do ataque, capítulo 7, seção 7.2) |
| Tools | as sete primitivas, congeladas em `v2-tools-frozen`, mais a correção aprovada do segundo em `list_actions` |
| Código | commit `41ddda5` |
| Comando | `LLM_MODEL=anthropic/claude-haiku-5.5 python scripts/run_benchmark.py --repeats 1` |
| Custo real | US$ 0,104 (consumo da chave antes e depois); 0,95 milhão de tokens lidos do cache |
| Arquivos | [`pilot_results.jsonl`](../../data/benchmark/pilot_results.jsonl), [`pilot_summary.md`](../../data/benchmark/pilot_summary.md) |

## Resultado

| Tipo | `no_context` | `vector` | `events_in_prompt` | `stats_in_prompt` | `graph_tools` |
|---|---|---|---|---|---|
| fact | 0% | 0% | 50% | 0% | 50% |
| filtered_aggregation | 0% | 0% | 50% | 0% | 50% |
| network | 0% | 0% | 50% | 0% | **100%** |
| network_slice | 0% | 0% | 0% | 0% | 0% |
| unanswerable | 100% | 50% | 100% | 100% | 50% |
| **total** | 20% | 10% | **50%** | 20% | **50%** |
| **sem as unanswerable** | 0% | 0% | 38% | 0% | **50%** |

| Braço | Alucinação | Abstenção | Erro de formato |
|---|---|---|---|
| `no_context` | 0% | 80% | 0% |
| `vector` | **60%** | 30% | 0% |
| `events_in_prompt` | 40% | 10% | 0% |
| `stats_in_prompt` | 0% | 80% | 0% |
| `graph_tools` | 50% | 0% | 0% |

Com 2 perguntas por tipo e 1 repetição, cada célula é 0, 1 ou 2 acertos. É
um piloto para validar a ideia, não um resultado.

## Leitura

- **O `graph_tools` caiu de 97% (v1) para 50%.** Com tools primitivas e
  perguntas sem a definição no texto, o modelo precisa montar o caminho, e
  erra: nunca por erro de tool, sempre por escolha ou leitura.
- **`stats_in_prompt` se absteve em 8 de 10.** A súmula não tem recortes de
  tempo nem relações entre jogadores, e o braço reconhece isso em vez de
  inventar.
- **`events_in_prompt` empata com o `graph_tools` no total**, com outro
  perfil: acerta fatos e contagens simples, erra quando precisa contar pares
  ou montar uma rede de cabeça.
- **Nenhum braço acertou `network_slice`.**

## Os 5 erros do `graph_tools`

| Pergunta | O que o modelo fez | Natureza |
|---|---|---|
| f03 (chute defendido antes do gol de Messi) | Procurou numa janela que terminava 60 s antes do gol e achou outra defesa de Lloris, num chute do próprio Messi | busca na janela errada |
| a05 (mais passes durante o 2 a 0) | Leu "enquanto vencia por 2 a 0" como "até o segundo gol" e contou o período antes do 2 a 0 (Otamendi, 26) | interpretação do recorte |
| s01 (elo da França na prorrogação) | Montou uma rede para o período 3 e outra para o 4, e respondeu com a do 3 (Tchouaméni). Não usou a janela de tempo para juntar os dois | limitação de uso: `period` aceita um só valor |
| s04 (dupla do 2º tempo) | Trocou as redes do 1º e do 2º tempo e bateu no limite de 8 chamadas | confusão entre redes: o resumo de `pass_network` não repete o filtro usado |
| u03 (piques de Mbappé) | Contou conduções como "piques" e respondeu 2 | alucinação por aproximação |

## Traces

| pergunta | `no_context` | `vector` | `events_in_prompt` | `stats_in_prompt` | `graph_tools` |
|---|---|---|---|---|---|
| f02 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/35558780762afbf3c1c413d6332ab7a9) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/4224e677e347d024520c50d2d43cc08e) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/56f1a84da32a0d43bd60a7167a3d0632) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/6c0ab19118cc636a4c32f4dc8d557088) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/3b5807ea43731cfad615ae1c0eacff3f) |
| f03 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9bee97b32ec21b39bb4e5a4fdec38ac9) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/720b9f99944f48eaf9d0563f19d7c056) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e0d4f3139fd5b6736a864eb1e24971a2) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/ed1f605b9c86c10b3ea6a873f4fc8122) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/b3d627d25c972517da374eb78be415c8) |
| a03 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/ccd5af60f43d2cc7e603877e7560c677) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/6681ed426a3f99a90449eb8ee4f4260f) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/1b5b3e79bea530b3ffaaae7746276ba0) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/d125ed1f879b8a25f726d5c8eb44cdc8) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/07237d26e5af72d7c46b712d666c4588) |
| a05 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/8abfcddba3b1d8dc68d9c098e743ce30) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/509824d143e72faf466b35e2358af42a) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/4a6b4e2c65fe558520d5b3ba73bcfb7b) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/1d10137d9c6e218852e49961adc075c9) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/145efd709cbef482135a281e90db4e9e) |
| n03 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/4f8c0062baac3fcf3d4f0f472014e712) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/5dd7661a868cf159ef629fcf5fc119d7) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c0546aa7aec5ea1cb599cef0088a557c) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/00f3f28d79fc40821c41bf791a080e9c) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/d90f933c48a972fb67721ddca2bf938b) |
| n04 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c78322ce34c2ef44654d9f5fcfea57d8) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/deb16eee40bea698544d7fdf684d39eb) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/d485a3372704abe18c79b19763fa5947) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/5f74ba15d547ed9f9c2769b4add1141d) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/d377bc4f1faeb081b4f40daf1b3c3957) |
| s01 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/272427f3ddec1cabc2b2ecf38bcbf6a2) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/35294aca0b3960eda8939e77cad63d31) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/4d3422186884da5ba5e4a849ad4b7383) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/f7feca3f06fb81cffd63696306fea00f) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/6ae0f1d5935d52b701fedb29608496c3) |
| s04 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e197ad6aeb654764f082572cdcc3084a) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/108ec0b1fc4bfc3a8aa6b346b52f2862) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/55f536b28cdbe01e307910fcaeb3f053) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/3af5f4a4200021fef6bdf5fc74884641) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/2c99bead1eb6b740f53ba10c6b04d1a3) |
| u01 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/57bf96b082ed133d0ad4005a7fd19b55) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/16b6bdde04284736752a255fb96d3188) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/52ad99c442b42ed334733ce816ba8832) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/49ce764edf013deaf593d88a362f78be) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/0156a10b18373c3e95d673bf88591e0b) |
| u03 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/a02510a6c6b4a23a0ad3b5a2089bb404) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/a3a7e696a5b3e2098fbc008bd61950e3) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/6c4258e9c198878112b7c7e6b80657e1) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/547ed7220950fbbd543e030844f50b39) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9d155a18c5335d4c2fdcbf135af19904) |

✅ certo · ❌ alucinação · 🟡 abstenção · ⚠️ erro de formato. Cada símbolo abre o trace no Langfuse.


# Execução 06: placar no `list_actions` (v2.2), teste rápido

| | |
|---|---|
| Data | 2026-10-07 |
| Tipo | só o `graph_tools`, 1 tentativa, nas 3 perguntas que ele errou na execução 05 por localizar mal um momento do jogo: a03, a05 e f03 |
| Mudança desde a 05 | v2.2: cada ação listada pelo `list_actions` traz o placar no instante em que começa (ex.: "Argentina 2-1 France"). Sem filtro por placar. `events_in_prompt` e `vector` não mudaram |
| Código | commit da tag local `v2.2-tools-frozen` |
| Comando | `LLM_MODEL=anthropic/claude-haiku-5.5 python scripts/run_benchmark.py --questions a03,a05,f03 --arms graph_tools --repeats 1 --output data/benchmark/pilot_v22_score_graph_tools.jsonl` |
| Arquivo | [`pilot_v22_score_graph_tools.jsonl`](../../data/benchmark/pilot_v22_score_graph_tools.jsonl) |

| Pergunta | Antes (todas as tentativas) | v2.2 | O que o modelo fez |
|---|---|---|---|
| a03 (finalizações da Argentina depois do 2 a 2) | ✅ ❌ | ✅ 10 | Listou as finalizações e contou a partir do 2 a 2 |
| a05 (mais passes durante o 2 a 0) | ❌ ❌ ❌ ❌ | ❌ Enzo, 51 | Acertou o fim do recorte (o gol de Mbappé aos 80'), mas começou a contar no apito inicial, não no 2 a 0. Jogador certo, número errado |
| f03 (chute defendido antes do gol de Messi) | ❌ ❌ ❌ ❌ | ✅ Lautaro | Viu as duas defesas de Lloris e escolheu a mais próxima do gol |

Uma tentativa por pergunta não separa o efeito do placar da variação do
modelo: a a03 já tinha acertado uma vez antes, e o raciocínio da f03 nem cita
o placar. O que dá para dizer: na a05, o modelo passou a achar o fim do
"enquanto vencia por 2 a 0", mas ainda não o começo.

## Traces

| pergunta | `graph_tools` |
|---|---|
| f03 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/eebfe26dc1c24371a71a13a187925c20) |
| a03 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/3de59d247a1a2272bc116ccad5c3dcd5) |
| a05 | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/83d416c09608773f63c127751f21793d) |

✅ certo · ❌ alucinação · 🟡 abstenção · ⚠️ erro de formato. Cada símbolo abre o trace no Langfuse.


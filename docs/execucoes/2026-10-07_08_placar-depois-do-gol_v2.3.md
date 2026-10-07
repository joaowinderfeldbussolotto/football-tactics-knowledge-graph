# Execução 08: placar depois do gol no `list_actions` (v2.3), teste rápido

| | |
|---|---|
| Data | 2026-10-07 |
| Tipo | só o `graph_tools`, 1 tentativa, nas 3 perguntas em que achar "o gol do 2 a 2" é o primeiro passo: f04, s03, a03 |
| Mudança desde a 07 | v2.3: no `list_actions`, a linha de um gol diz o placar que ele produziu: `goal (score after: Argentina 3-2 France)`. A coluna `score` continua sendo o placar antes da ação. `events_in_prompt` e `vector` ainda não mudaram |
| Comando | `LLM_MODEL=anthropic/claude-haiku-5.5 python scripts/run_benchmark.py --questions f04,s03,a03 --arms graph_tools --repeats 1 --output data/benchmark/v23_score_after_graph_tools.jsonl` |
| Arquivo | [`v23_score_after_graph_tools.jsonl`](../../data/benchmark/v23_score_after_graph_tools.jsonl) |

| Pergunta | Execução 07 (v2.2) | v2.3 | O gol que o modelo tomou como o do 2 a 2 |
|---|---|---|---|
| f04 (passe para o gol do 2 a 2) | ❌ Enzo Fernández | ✅ Thuram | antes: Messi aos 108'; agora: Mbappé aos 81' |
| s03 (dupla da França depois do 2 a 2) | ❌ Fofana e Koundé | ✅ Koundé e Varane | antes: Messi aos 108'; agora: Mbappé aos 81' |
| a03 (finalizações da Argentina depois do 2 a 2) | ✅ 10 | ✅ 10 | Mbappé aos 81' nas duas |

Nas 3, o modelo identificou o gol certo logo na primeira chamada. As três
perguntas agora são "vistas" para essa correção: a melhora nelas mostra que
ela funciona, não que generaliza.

## Traces

| pergunta | `graph_tools` |
|---|---|
| f04 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/41cc73f41447e5fbea0e4e7d7fb72f16) |
| a03 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/3d2789505b5334f0987cbf3309646e60) |
| s03 | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/b5dbb9efadea2b1c9d5e239fc3f55fc9) |

✅ certo · ❌ alucinação · 🟡 abstenção · ⚠️ erro de formato. Cada símbolo abre o trace no Langfuse.


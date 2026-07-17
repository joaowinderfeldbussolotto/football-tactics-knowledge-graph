# 07 — Relatório de validação da execução

Este arquivo separa **dado de execução** (números medidos numa rodada concreta, num
ambiente concreto) de **documentação e decisão** (docs 01–06). Os docs descrevem o que o
sistema É e por quê; este arquivo registra o que foi MEDIDO ao validá-lo. Os ADRs em
`05-decisoes.md` apontam para cá em vez de carregar tabelas de medição.

## Ambiente da execução de validação

| Item | Valor |
|---|---|
| Data | 2026-07-17 |
| Ambiente | sessão Claude Code remota (sandbox Linux com proxy TLS de saída) |
| Neo4j | 5.26.0 Community em container, openGDS 2.13.2 + APOC 5.26.0 (via Maven, ADR-6) |
| LLM | Anthropic `claude-haiku-4-5` (o Claude mais barato: $1/$5 por MTok) |
| Embeddings/reranker | Gemini `gemini-embedding-001` + reranker Gemini, **chave free-tier** |
| Particularidades da sandbox | `api.mistral.ai`, Docker Hub e hosts de plugin do Neo4j bloqueados pelo proxy; PyPI/Maven liberados |

O que é **específico deste ambiente** (não se reproduz fora dele): o workaround do GDS
via Maven (ADR-6), o bloqueio da Mistral, e os tempos absolutos (hardware/entorno). O que
é **reproduzível em qualquer ambiente**: contagens da pipeline, contagens do grafo,
padrões gerados, fidelidade e o comparativo com o baseline (dados e seeds fixos).

## Camada 0 — pipeline (medições)

| Partida | Eventos kloppy | Ações SPADL | Fases | Passes c/ recebedor | Pressões (c/ alvo) | Tempo* |
|---|---|---|---|---|---|---|
| 3869685 (final) | 4.527 | 2.584 | 537 | 989 | 361 (301) | 53 s / 1,5 s |
| 3869519 (semi) | 3.891 | 2.272 | 346 | 916 | 290 (266) | 1,5 s |
| 3869354 (quartas) | 3.351 | 1.895 | 326 | 791 | 230 (210) | 1,2 s |

\* primeira execução inclui download das 16 partidas de treino + treino de xT/VAEP;
as demais usam cache.

## Camada 1 — grafo factual (medições)

| Partida | Escritas | Tempo (1ª / re-execução) |
|---|---|---|
| final | 5.351 | 6,9 s / 1,1 s |
| semi | 4.565 | 1,1 s |
| quartas | 4.035 | 0,7 s |

Idempotência confirmada por teste (contagens idênticas após reconstrução).

## Camada 2 — insights (medições)

69 padrões táticos no total (24 + 22 + 23); distribuição por tipo e exemplos reais em
`03-insights.md`. `alvo_de_pressao` não disparou na final (sem concentração ≥1.5x a
média) — resultado honesto, registrado no catálogo.

## Camada 3 — validação ao vivo (medições)

| Operação | Medição |
|---|---|
| `GET /report/3869685` | 43 s; 5 seções, 25 citações; **fidelidade determinística 100% (25/25)**; sem menção a placar |
| `/ask` — recuperação estruturada | 0,02–0,43 s |
| `/ask` — geração (Haiku) | 5–7 s |
| Graphiti `add_triplet` | 24 padrões em 196 s com pacing de 2 s (free-tier); ~3 s/padrão sem cota |
| Graphiti `build_communities` | 2 comunidades (uma por seleção), resumos coerentes, 15 s |
| Graphiti busca híbrida | 0,29 s, 10 fatos relevantes |

**Teste de estresse de rate limit (ADR-7):** indexação da semifinal com pacing
desligado de propósito — a cota free-tier do Gemini (100 embeddings/min) foi estourada e
todos os 429 foram absorvidos pelo retry nativo do google-genai; 22 padrões em 163,5 s,
zero falhas.

**Bugs reais encontrados pela validação** (cada um corrigido; detalhes no ADR-5):
forma-string do PydanticAI ignora `LLM_API_KEY`; saída estruturada truncada nos defaults
do SDK; `cross_encoder=None` exige chave OpenAI no Graphiti; `text-embedding-004`
descontinuado; cota free-tier quebrava a indexação.

## Avaliação comparativa (grafo vs baseline vetorial)

Resultado central da tese — tabela e análise em `03-insights.md` (seção "Avaliação");
JSON completo por pergunta em `data/processed/eval_results.json` (gerado por
`scripts/run_evaluation.py`, não versionado). Duas rodadas executadas:

| Rodada | Golden | Formato de resposta | Estrutural: grafo (retr/insight) | Estrutural: baseline | Fidelidade |
|---|---|---|---|---|---|
| 1ª | 10 perguntas | registro único | 5.0 / 4.33 (n=9) | 1.0 / 1.0 | 100% |
| 2ª | 16 perguntas | duplo registro (tatiquês + em_bom_portugues) | 5.0 / 5.0 (n=15) | 1.0 / 1.13 | 100% |

Na agregada (n=1), a 2ª rodada deu grafo 5.0/5.0 vs baseline 2.0/1.0. Custo total das
duas rodadas + validações avulsas com `claude-haiku-4-5`: da ordem de centavos de dólar.

## Modo autônomo (ADR-8) — validação ao vivo

Primeira rodada (antes do endurecimento do prompt) expôs os dois riscos previstos, ambos
reproduzidos de verdade e corrigidos:

| Achado | Sintoma observado | Correção |
|---|---|---|
| Vazamento de memória externa | resposta dos gols completou "3-3, pênaltis" sem consulta que sustentasse | regra 1 do prompt ampliada (proíbe completar com conhecimento externo, explícito sobre placar/pênaltis) |
| Join que multiplica linhas | `DEU_ASSISTENCIA×FINALIZOU` virou "Thuram: 3 assistências" (1 assistência × 3 gols do Mbappé) | schema anotado com o anti-padrão + regra de COUNT(DISTINCT)/contagem direta |

Segunda rodada (prompt endurecido): gols 6/6 corretos por consulta única, assistências
2/2 corretas, dupla Otamendi-Romero 18 passes com citação combinada de padrão tático
(betweenness) — todas as consultas re-executam (check_queries 100%). A guarda read-only
recusa `CREATE`/`SET`/`CALL` na sintaxe e a transação READ do Neo4j bloqueia escrita no
servidor (coberto por teste).

## O que NÃO foi validado ao vivo

- Provedor **Mistral** como LLM (bloqueio de rede da sandbox; caminho de código coberto
  por testes de introspecção sem rede).
- Gemini como LLM principal (validado como embedder e reranker).

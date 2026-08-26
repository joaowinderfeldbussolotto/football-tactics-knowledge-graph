#!/usr/bin/env python
"""Teste de fumaça de um provedor de LLM contra o grafo real.

Serve para QUALQUER provedor, não só um novo: roda UMA pergunta real
(escolhida de propósito para exercitar os dois mecanismos que quebram
primeiro num modelo desconhecido — chamada de ferramenta e saída
estruturada) e reporta se funcionou, sem o custo de rodar as 30 perguntas
do golden dataset.

Uso:
    python scripts/smoke_llm.py                    # pergunta padrão
    python scripts/smoke_llm.py "sua pergunta aqui"

Não roda nada se LLM_API_KEY estiver ausente — sai com mensagem clara em
vez de deixar o traceback de autenticação explicar o problema por você.
"""

import asyncio
import sys
import time

from football_graphrag.api import agents, retrieval
from football_graphrag.config import get_settings
from football_graphrag.evaluation import faithfulness
from football_graphrag.graph import db
from football_graphrag.observability import logging_setup

logging_setup.setup()

# Pede um fato que não está em nenhum PadraoTatico (força o agente a usar
# consultar_grafo) e cita um jogador (a súmula entra no contexto — ver
# api/retrieval.py) — cobre ferramenta, súmula e saída estruturada num só tiro.
PERGUNTA_PADRAO = "Quantos desarmes certos o Enzo Fernandez fez na final?"
MATCH_ID = 3869685


async def main(pergunta: str) -> int:
    settings = get_settings()
    if not settings.llm_api_key:
        print("LLM_API_KEY ausente no .env — nada para testar. Configure e rode de novo.")
        return 1

    print(f"provedor={settings.llm_provider}  modelo={settings.llm_model}")
    print(f"pergunta: {pergunta}\n")

    driver = db.make_driver(settings)
    try:
        t0 = time.perf_counter()
        patterns, stats, extra_facts, timings = await retrieval.retrieve_context(driver, MATCH_ID, pergunta)
        try:
            resposta = await agents.answer_question(pergunta, patterns, stats, extra_facts, driver, MATCH_ID)
        except Exception as exc:
            print(f"FALHOU ao gerar a resposta estruturada: {type(exc).__name__}: {exc}")
            return 1
        elapsed = round(time.perf_counter() - t0, 2)

        print("saída validou no schema RespostaTatica: sim")
        print(f"resposta: {resposta.resposta}")
        print(f"em_bom_portugues: {resposta.em_bom_portugues}")
        print(f"confiança declarada: {resposta.confianca}")
        print(f"consultas executadas: {len(resposta.consultas_executadas)}")
        for c in resposta.consultas_executadas:
            print(f"  - {c.cypher}\n    => {c.resultado_resumido}")

        if resposta.consultas_executadas:
            qfid = faithfulness.check_queries(driver, resposta.consultas_executadas)
            print(f"re-execução das consultas: {qfid.score:.0%} ({qfid.matched}/{qfid.total})")
            for m in qfid.mismatches:
                print(f"  MISMATCH: {m}")
        if resposta.metricas_citadas:
            cfid = faithfulness.check_citations(driver, resposta.metricas_citadas)
            print(f"citações válidas: {cfid.score:.0%} ({cfid.matched}/{cfid.total})")

        print(f"\ntempo total: {elapsed}s (recuperação {timings['retrieval_seconds']}s)")
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    pergunta = " ".join(sys.argv[1:]) or PERGUNTA_PADRAO
    sys.exit(asyncio.run(main(pergunta)))

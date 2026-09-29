#!/usr/bin/env python
"""Confere se o GRAFO responde as 24 perguntas do golden dataset.

Não usa LLM e não gasta um centavo de API: para cada pergunta roda a consulta
de referência (evaluation/reference_queries.py) e imprime o que o grafo
devolve, lado a lado com a resposta esperada.

É a verificação do MODELO DE DADOS, separada da avaliação do sistema
(scripts/run_evaluation.py, que mede o LLM e custa chamadas). Uma pergunta
sem linhas aqui é defeito de modelagem, não de prompt.

Uso:
    python scripts/check_golden_queries.py           # todas
    python scripts/check_golden_queries.py q23 q17   # só as que casarem
"""

import sys

from football_graphrag.config import get_settings
from football_graphrag.evaluation.golden_dataset import GOLDEN_QUESTIONS
from football_graphrag.evaluation.reference_queries import REFERENCE_QUERIES
from football_graphrag.graph import db
from football_graphrag.observability import logging_setup

logging_setup.setup()

LARGURA = 100


def _formata(linhas: list[dict], limite: int = 6) -> str:
    if not linhas:
        return "    (nenhuma linha — o grafo NÃO responde esta pergunta)"
    saida = []
    for linha in linhas[:limite]:
        campos = ", ".join(f"{k}={v}" for k, v in linha.items() if v is not None)
        saida.append(f"    · {campos}")
    if len(linhas) > limite:
        saida.append(f"    · ... (+{len(linhas) - limite} linhas)")
    return "\n".join(saida)


def main(filtros: list[str]) -> int:
    settings = get_settings()
    driver = db.make_driver(settings)
    sem_resposta, sem_consulta = [], []
    try:
        for q in GOLDEN_QUESTIONS:
            if filtros and not any(f in q.id for f in filtros):
                continue
            cypher = REFERENCE_QUERIES.get(q.id)
            print("=" * LARGURA)
            print(f"[{q.id}]  ({q.categoria})  partida {q.match_id}")
            print(f"  PERGUNTA:  {q.pergunta}")
            print(f"  ESPERADO:  {q.resposta_referencia}")
            if cypher is None:
                print("  !! sem consulta de referência cadastrada")
                sem_consulta.append(q.id)
                continue
            try:
                linhas = db.run_readonly(driver, cypher.replace("$m", str(q.match_id)))
            except Exception as exc:
                print(f"  !! ERRO NA CONSULTA: {exc}")
                sem_resposta.append(q.id)
                continue
            print("  GRAFO:")
            print(_formata(linhas))
            if not linhas:
                sem_resposta.append(q.id)
    finally:
        driver.close()

    print("=" * LARGURA)
    total = len([q for q in GOLDEN_QUESTIONS if not filtros or any(f in q.id for f in filtros)])
    respondidas = total - len(sem_resposta) - len(sem_consulta)
    print(f"RESUMO: {respondidas}/{total} perguntas com resposta no grafo")
    if sem_consulta:
        print(f"  sem consulta de referência: {', '.join(sem_consulta)}")
    if sem_resposta:
        print(f"  sem resposta no grafo:      {', '.join(sem_resposta)}")
    return 1 if (sem_resposta or sem_consulta) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

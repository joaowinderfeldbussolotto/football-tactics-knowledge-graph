#!/usr/bin/env python
"""Tabelas em Markdown a partir do JSON de uma rodada de avaliação.

Existe para que as tabelas da documentação não sejam digitadas à mão a partir
do JSON — que foi como a 3ª rodada entrou nos documentos, e é como um número
erra de casa sem ninguém perceber.

Uso:
    python scripts/consolidar_resultados.py data/processed/eval_results.json
"""

import argparse
import json
from pathlib import Path

BRACOS = [("grafo_sem_sumula", "grafo sem súmula"), ("grafo_com_sumula", "grafo com súmula")]
CATEGORIAS = ("estrutural", "factual", "agregada", "composta")


def tabela_por_categoria(summary: dict) -> str:
    linhas = [
        "| Categoria | n | Braço | Recuperação prévia | Recuperação final | Insight | Consultas |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for cat in CATEGORIAS:
        v = summary["por_categoria"].get(cat)
        if not v:
            continue
        for chave, rotulo in BRACOS:
            b = v[chave]
            linhas.append(
                f"| {cat} | {v['n']} | {rotulo} | {b['retrieval_previo']} | "
                f"{b['retrieval_final']} | {b['insight']} | {b['consultas_media']} |"
            )
        bl = v["baseline"]
        linhas.append(
            f"| {cat} | {v['n']} | baseline vetorial | {bl['retrieval_previo']} | — | {bl['insight']} | — |"
        )
    return "\n".join(linhas)


def tabela_tese(summary: dict) -> str:
    """A comparação citável: grafo (com súmula) contra baseline, na métrica simétrica."""
    linhas = [
        "| Categoria | n | Grafo: prévia / insight | Baseline: prévia / insight | Diferença (prévia) |",
        "|---|---:|---|---|---:|",
    ]
    for cat in CATEGORIAS:
        v = summary["por_categoria"].get(cat)
        if not v:
            continue
        g, b = v["grafo_com_sumula"], v["baseline"]
        dif = round(g["retrieval_previo"] - b["retrieval_previo"], 2)
        linhas.append(
            f"| {cat} | {v['n']} | {g['retrieval_previo']} / {g['insight']} | "
            f"{b['retrieval_previo']} / {b['insight']} | {dif:+} |"
        )
    return "\n".join(linhas)


def checagem_de_isolamento(summary: dict) -> str:
    """Os dois braços do grafo têm de empatar em 'estrutural' (ADR-10)."""
    v = summary["por_categoria"].get("estrutural")
    if not v:
        return "sem perguntas estruturais nesta rodada."
    a = v["grafo_sem_sumula"]["retrieval_previo"]
    b = v["grafo_com_sumula"]["retrieval_previo"]
    dif = abs(a - b)
    veredito = "OK" if dif <= 0.5 else "ATENÇÃO: braço mal isolado"
    return (f"estrutural, prévia: sem súmula {a} vs com súmula {b} (|Δ| = {round(dif, 2)}) — {veredito}. "
            "A súmula não contém betweenness; divergência grande aqui invalida a rodada.")


def main(caminho: Path) -> None:
    d = json.loads(caminho.read_text())
    s = d["summary"]
    print(f"# Rodada `{s.get('rodada', '?')}`\n")
    print(f"- modelo: `{s['modelo']}`")
    print(f"- perguntas: {s['n_perguntas']}")
    print(f"- fidelidade determinística: {s['faithfulness_media']}\n")
    print("## Comparação citável (métrica simétrica)\n")
    print(tabela_tese(s), "\n")
    print("## Três braços, todas as métricas\n")
    print(tabela_por_categoria(s), "\n")
    print("## Checagem de isolamento\n")
    print(checagem_de_isolamento(s))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("arquivo", type=Path)
    main(p.parse_args().arquivo)

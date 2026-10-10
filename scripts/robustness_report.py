#!/usr/bin/env python
"""Robustness report: every question written, its answer in every reading, kept or not.

Reads ``data/benchmark/ground_truth.json`` (run
``python -m football_graphrag.benchmark.ground_truth`` first) and writes
``data/benchmark/robustness.md``.

Usage:
    python scripts/robustness_report.py
"""

from football_graphrag.benchmark import ground_truth
from football_graphrag.benchmark.questions import ALL_QUESTIONS, PREFIXES
from football_graphrag.config import get_settings


def cell(a: dict) -> str:
    if "tie" in a:
        return "**empate:** " + "; ".join(" e ".join(x) if isinstance(x, list) else x for x in a["tie"])
    players = " e ".join(a["players"])
    value = "" if a.get("value") is None else str(round(a["value"], 2))
    return " · ".join(x for x in (players, value) if x)


def main() -> None:
    gt = ground_truth.load()
    out = [
        "# Teste de robustez do gabarito",
        "",
        "Gerado por `scripts/robustness_report.py` a partir de `ground_truth.json`. Cada pergunta "
        "escrita aparece com a resposta em cada leitura razoável. Fica no benchmark só a pergunta em "
        "que alguma resposta (o jogador, o conjunto ou o número) está certa em todas as leituras. "
        "Empate dentro de uma leitura não desclassifica: todos os empatados no topo valem naquela "
        "leitura, e a resposta aceita é a que está no topo em todas.",
        "",
        "Nos rankings, o número ao lado do nome é a pontuação naquela leitura (passes, contagem ou "
        "intermediação); ele muda entre leituras sem tornar a pergunta instável quando a conferência "
        "olha só o jogador.",
        "",
        "| pergunta | tipo | estágio | estável | leituras |",
        "|---|---|---|---|---|",
    ]
    for q in ALL_QUESTIONS:
        r = gt[q.id]
        out.append(f"| [{q.id}](#{q.id}) | {q.type} | {q.stage} | {'sim' if r['stable'] else '**não**'} "
                   f"| {len(r['readings']) or '–'} |")
    for t in PREFIXES:
        out += ["", f"## {t}"]
        for q in (q for q in ALL_QUESTIONS if q.type == t):
            r = gt[q.id]
            out += ["", f"### {q.id}", "", f"> {q.text}", "",
                    f"Estágio: **{q.stage}** · conferência: `{q.check}` · estável: **{'sim' if r['stable'] else 'não'}**"]
            if len(r.get("accepted") or []) > 1:
                out += ["", "Respostas aceitas (empatadas em todas as leituras): "
                        + "; ".join(" e ".join(a) for a in r["accepted"])]
            if q.note:
                out += ["", f"Nota: {q.note}"]
            if q.type == "unanswerable":
                out += ["", "Sem leituras: a resposta esperada é \"sem dados\"."]
                continue
            out += ["", "| leitura | resposta |", "|---|---|"]
            out += [f"| {label} | {cell(a)} |" for label, a in r["readings"].items()]
            if "context_readings" in r:
                out += ["", "Premissa que a pergunta afirma (também tem de ser estável):", "",
                        "| leitura | resposta |", "|---|---|"]
                out += [f"| {label} | {cell(a)} |" for label, a in r["context_readings"].items()]
    path = get_settings().data_dir / "benchmark" / "robustness.md"
    path.write_text("\n".join(out) + "\n")
    print(f"written {path}")


if __name__ == "__main__":
    main()

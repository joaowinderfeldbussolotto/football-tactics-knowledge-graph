"""The paper's pipeline without any paid call: statistics, generated numbers, text lint, citations, skeleton."""

import importlib.util
import json
import re
from pathlib import Path

import pytest

from football_graphrag.benchmark import paper_stats as ps

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"


def script(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lint = script("paper/scripts/lint_paper.py")
cite = script("paper/scripts/cite_check.py")
numbers = script("scripts/paper_numbers.py")


# --------------------------------------------------------------------------- statistics

def test_wilson_matches_the_dossier_intervals():
    assert [round(100 * x) for x in ps.wilson(21, 47)] == [31, 59]
    assert [round(100 * x) for x in ps.wilson(33, 47)] == [56, 81]
    assert [round(100 * x) for x in ps.wilson(41, 47)] == [75, 94]
    assert ps.wilson(0, 47)[0] == 0.0 and ps.wilson(0, 0) == (0.0, 0.0)


def test_exact_mcnemar():
    assert round(ps.mcnemar_exact(17, 5), 3) == 0.017
    assert round(ps.mcnemar_exact(11, 3), 3) == 0.057
    assert ps.mcnemar_exact(23, 3) < 0.001
    assert ps.mcnemar_exact(0, 0) == 1.0 and ps.mcnemar_exact(5, 5) == 1.0


def test_holm_is_a_step_down_adjustment():
    adjusted = ps.holm([0.0169, 0.0574, 0.0000880])
    assert [round(x, 3) for x in adjusted] == [0.034, 0.057, 0.0]
    assert ps.holm([0.04]) == [0.04]


def test_the_question_is_the_unit_when_there_are_repeats():
    rows = [{"arm": "a", "question_id": "q1", "correct": c} for c in (True, True, False)]
    rows += [{"arm": "a", "question_id": "q2", "correct": False}] * 3
    res = ps.by_question(rows, "a")
    assert res["q1"].share == pytest.approx(2 / 3) and res["q1"].majority and not res["q2"].majority
    acc = ps.accuracy(res)
    assert acc.n == 2 and acc.correct == pytest.approx(2 / 3)  # two questions, not six runs


# --------------------------------------------------------------------------- generated numbers

def test_generated_files_match_the_versioned_results():
    built = numbers.files(ROOT / "data" / "benchmark" / "final_results.jsonl")
    stale = [str(p.relative_to(ROOT)) for p, text in built.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
    assert not stale, f"run python scripts/paper_numbers.py: {stale}"


def test_the_numbers_the_dossier_states():
    macros, tables = numbers.build(ROOT / "data" / "benchmark" / "final_results.jsonl")
    assert (macros["accGraphTools"], macros["ciLowGraphTools"], macros["ciHighGraphTools"]) == ("87\\%", "75", "94")
    assert (macros["accTextToCypher"], macros["accEventsInPrompt"], macros["accStatsInPrompt"]) == ("70\\%", "45\\%", "0\\%")
    assert (macros["mcTextToCypherEventsInPromptFirst"], macros["mcTextToCypherEventsInPromptSecond"]) == ("17", "5")
    assert macros["mcTextToCypherEventsInPromptP"] == "0,017" and macros["mcTextToCypherEventsInPromptPHolm"] == "0,034"
    assert macros["mcGraphToolsEventsInPromptP"] == "menor que 0,001"
    assert (macros["nQuestions"], macros["nAnswerable"], macros["nRuns"]) == ("52", "47", "312")
    assert not {"nWritten", "nRemoved", "nCandidates"} & set(macros)  # the paper talks about the 52 only
    assert macros["armGraphTools"] == "Ferramentas sobre o grafo" and macros["armShortTextToCypher"] == "Consulta"
    assert (macros["nMaxCalls"], macros["nTopK"], macros["nTools"], macros["nMaxRows"], macros["nTimeoutS"]) == \
        ("12", "30", "8", "50", "15")
    assert (macros["nEvents"], macros["nActions"], macros["ciLevel"]) == ("4.407", "2.585", "95\\%")
    assert all(f"arm{k}" in macros and f"armShort{k}" in macros for k in ps.ARM_KEYS.values())
    assert (macros["preFixKGraphTools"], macros["preFixNGraphTools"]) == ("39", "52")
    assert macros["accPlaysGraphTools"] == "80\\%" and macros["accPlaysTextToCypher"] == "40\\%"
    assert macros["tokInGraphTools"] == "76.118" and macros["costFinal"] == "1,04"
    assert set(tables) == {"groups.tex", "mcnemar.tex", "cost.tex", "ladder.tex"}
    assert all(re.fullmatch(r"[A-Za-z]+", name) for name in macros)  # LaTeX control sequences: letters only


def test_pt_br_number_format():
    assert numbers.num(76118) == "76.118" and numbers.num(0.017, 3) == "0,017" and numbers.num(4.8, 1) == "4,8"
    assert numbers.pct(0.872) == "87\\%" and numbers.p_value(0.00009) == "menor que 0,001"


def test_trajectory_series_use_the_same_questions_in_every_version():
    import yaml

    bench = ROOT / "data" / "benchmark"
    cfg = yaml.safe_load((PAPER / "data" / "trajectory.yaml").read_text(encoding="utf-8"))["series"]
    final = ps.load(bench / "final_results.jsonl")
    for series in cfg:
        points = ps.trajectory(series, bench, final)
        assert len({p["n"] for p in points}) == 1 and points[0]["n"] >= 8
    graph = next(ps.trajectory(s, bench, final) for s in cfg if s["key"] == "graph")
    assert [round(p["correct"]) for p in graph[:3]] == [9, 10, 12] and graph[0]["n"] == 13


# --------------------------------------------------------------------------- lint

NO_TERMS: list = []


def kinds(text: str, **kw) -> list[str]:
    return [f.rule for f in lint.scan(text, "t.tex", allowed=kw.get("allowed", set()), terms=kw.get("terms", NO_TERMS))]


def test_lint_flags_typed_numbers_but_not_macros_citations_or_ids():
    assert kinds("O braço acertou 87\\% das perguntas.") == ["number"]
    assert kinds("Foram \\nQuestions{} perguntas, acerto \\accGraphTools{}.") == []
    assert kinds("Como em~\\cite{xia2024sportqa,li2024ragorlongcontext}, ver \\ref{fig:f2} e \\label{sec:a1}.") == []
    assert kinds("A pergunta s01 e a n12 (\\texttt{p05}) aparecem.") == []
    assert kinds("As hipóteses H1 e H2 e a QP3.") == []
    assert kinds("Na Copa de 2022.") == ["number"] and kinds("Na Copa de 2022.", allowed={"2022"}) == []
    assert kinds("% 87 num comentário\nTexto limpo.") == []
    assert kinds("Valor 87 \\% % lint: ignore") == []


def test_lint_style_rules():
    assert kinds("Isso — e aquilo.") == ["dash"] and kinds("de um – dois") == ["dash"] and kinds("a - b") == ["dash"]
    assert kinds("Fica-se com o meio-campo e a rede de passes.") == []  # a hyphen inside a word is not a dash
    assert kinds("Nós avaliamos o nosso método.") == ["voice", "voice", "voice"]
    assert kinds("Um resultado notável e inovador.") == ["promotional", "promotional"]
    assert kinds("% lang: en\nA result — in English, we show 3 things.") == ["number"]  # English: only numbers are checked


def test_lint_glossary_and_the_shipped_glossary():
    terms = lint.glossary()
    assert any(p.search("a accuracy") for p, _ in terms) and any(p.search("each arm") for p, _ in terms)
    assert [f.rule for f in lint.scan("O arm acertou.", "t", allowed=set(), terms=terms)] == ["glossary"]
    assert lint.scan("O braço acertou.", "t", allowed=set(), terms=terms) == []


def test_the_shipped_section_files_are_lint_clean():
    found = lint.scan((PAPER / "main.tex").read_text(encoding="utf-8"), "main.tex")
    for f in sorted((PAPER / "sections").glob("*.tex")):
        found += lint.scan(f.read_text(encoding="utf-8"), f.name)
    assert not found, "\n".join(map(str, found))


# --------------------------------------------------------------------------- citations

def test_cite_check_finds_sentences_and_keeps_verdicts(tmp_path, monkeypatch):
    text = ("Primeira frase sem fonte. O trabalho de Xia mediu o conhecimento~\\cite{a,b}.\n"
            "Outra\nfrase~\\citep{c}.\n\n% \\cite{z}\nÚltima~\\cite{d}.\n")
    found = cite.sentences(text)
    assert [s for _, s in found] == ["O trabalho de Xia mediu o conhecimento~\\cite{a,b}.", "Outra frase~\\citep{c}.",
                                     "Última~\\cite{d}."]
    assert [l for l, _ in found] == [1, 2, 6]  # the line where each sentence starts (a comment line stays, empty)
    claims = tmp_path / "claims.md"
    claims.write_text("| " + " | ".join(cite.HEADER) + " |\n|---|---|---|---|---|---|---|\n"
                      "| s.tex:1 | A frase | a | ref | resumo | SUSTENTA EM PARTE | só o núcleo |\n"
                      "| s.tex:2 | Outra | b | ref | resumo | PENDENTE |  |\n", encoding="utf-8")
    kept = cite.previous_verdicts(claims)
    assert kept[("A frase", "a")] == ("SUSTENTA EM PARTE", "só o núcleo") and kept[("Outra", "b")][0] == "PENDENTE"


# --------------------------------------------------------------------------- references and skeleton

def test_every_reference_in_the_table_is_in_refs_bib_and_balanced():
    import csv

    bib = (PAPER / "refs.bib").read_text(encoding="utf-8")
    keys = set(cite.parse_bib(bib))
    rows = list(csv.DictReader((PAPER / "refs" / "references.tsv").open(encoding="utf-8"), delimiter="\t"))
    assert len(rows) == 27 and all(r["key"] in keys for r in rows)
    assert {"statsbomb_opendata", "neo4j_gds", "networkx", "pydanticai", "langfuse", "socceraction"} <= keys
    assert all(r["status"] == "confirmado" for r in rows)
    for entry in re.split(r"\n\n(?=@)", bib):
        assert entry.count("{") == entry.count("}"), entry[:60]


def test_every_cited_key_exists_and_every_input_file_exists():
    keys = set(cite.parse_bib((PAPER / "refs.bib").read_text(encoding="utf-8")))
    main = (PAPER / "main.tex").read_text(encoding="utf-8")
    for tex in [PAPER / "main.tex", *sorted((PAPER / "sections").glob("*.tex"))]:
        text = re.sub(r"(?<!\\)%.*$", "", tex.read_text(encoding="utf-8"), flags=re.M)
        for group in cite.CITE.findall(text):
            assert {k.strip() for k in group.split(",")} <= keys, tex.name
        assert text.count("{") == text.count("}"), f"unbalanced braces in {tex.name}"
    for name in re.findall(r"\\input\{([^}]+)\}", main):
        assert (PAPER / f"{name}.tex").exists(), name
    assert len(re.findall(r"\\input\{sections/", main)) == len(list((PAPER / "sections").glob("*.tex")))


def test_outline_keys_in_the_section_comments_exist():
    keys = set(cite.parse_bib((PAPER / "refs.bib").read_text(encoding="utf-8")))
    for tex in (PAPER / "sections").glob("*.tex"):
        m = re.search(r"% Referências previstas \(chaves de refs\.bib\): (.+)", tex.read_text(encoding="utf-8"))
        if m:
            assert {k.strip() for k in m.group(1).split(",")} <= keys, tex.name


# --------------------------------------------------------------------------- skills and template

@pytest.mark.parametrize("name", ["paper-style-pt", "cite-check", "paper-numbers", "latex-figures", "banca-review"])
def test_each_skill_has_frontmatter_matching_its_folder(name):
    text = (ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"---\nname: (.+)\ndescription: (.+)\n---\n", text)
    assert m and m.group(1) == name and len(m.group(2)) > 80


def test_template_is_confirmed_from_the_overleaf_project():
    template = json.loads((PAPER / "template.json").read_text(encoding="utf-8"))
    assert template["confirmed"] is True and template["columns"] == 2
    assert template["column_width_in"] > 0 and template["text_font_pt"] == 12


def test_figures_are_vector_pdf_with_embedded_fonts(tmp_path):
    pytest.importorskip("matplotlib")
    pymupdf = pytest.importorskip("pymupdf")
    figures = script("scripts/figures.py")
    template = json.loads((PAPER / "template.json").read_text(encoding="utf-8"))
    rows = ps.load(ROOT / "data" / "benchmark" / "final_results.jsonl")
    plt = figures.style(template)
    figures.OUT = tmp_path
    made = [figures.ladder(plt, rows, ps.question_types(rows), template), figures.by_group(plt, rows, ps.question_types(rows), template),
            figures.trajectory(plt, rows, template)]
    for path in made:
        doc = pymupdf.open(path)
        assert doc[0].get_images() == []  # no raster
        assert all(f[3] for f in doc[0].get_fonts()) or doc[0].get_fonts()
        assert doc[0].rect.width / 72 <= template.get("text_width_in", 2 * template["column_width_in"]) + 0.5

#!/usr/bin/env python
"""Check the paper's text: loose numbers, style rules and the fixed glossary.

Reads paper/sections/*.tex (and main.tex). Exit code 1 if anything is found.

Rules:
- numbers: no typed number in the text. Every number is a macro from generated/numbers.tex
  (\\accGraphTools, \\nQuestions...). Digits are allowed only inside citations, references,
  labels, URLs, file names, question identifiers (s01, n12), hypothesis and research-question
  labels (H1, QP2) and the literals of paper/lint_allowlist.txt. A number written in words
  ("duas perguntas") is not checked: say it with a macro when it comes from the results.
- style: no em dash or en dash, no hyphen used as a dash, no first person plural (the voice is
  impersonal), no promotional adjective.
- glossary: the terms in paper/glossary.tsv marked "avoid" are not used.

A file with the line ``% lang: en`` (the English abstract) skips the Portuguese-only style
and glossary rules. A line ending in ``% lint: ignore`` is skipped.

Usage:
    python paper/scripts/lint_paper.py
    python paper/scripts/lint_paper.py paper/sections/05-resultados.tex
"""

import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]

# Commands whose arguments are not prose: a digit there is not a number in the text.
OPAQUE = re.compile(
    r"\\(?:cite\w*|ref|autoref|cref|Cref|eqref|label|url|href|input|include|includegraphics|bibliography|"
    r"bibliographystyle|usepackage|documentclass|pagestyle|setlength|vspace|hspace|resizebox|"
    r"begin|end|newcommand|renewcommand|providecommand)\*?(?:\[[^\]]*\])*(?:\{[^{}]*\})*")
QUESTION_ID = re.compile(r"\b[a-z]\d{2}\b")
LABELS = re.compile(r"\b(?:H|QP|RQ)\d\b")
NUMBER = re.compile(r"(?<![\w\\])\d+(?:[.,]\d+)*(?![\w])")
DASHES = re.compile(r"[\u2014\u2013]| - |--(?!-)")
FIRST_PERSON = re.compile(
    r"\b(?:nós|nosso|nossa|nossos|nossas|vamos|iremos|propomos|apresentamos|mostramos|avaliamos|observamos|"
    r"concluímos|verificamos|acreditamos|usamos|utilizamos|medimos|comparamos|constatamos|defendemos)\b", re.I)
PROMOTIONAL = re.compile(
    r"\b(?:revolucionári\w+|inovador\w*|poderos\w+|extraordinári\w+|impressionante\w*|notável|notáveis|"
    r"excepciona\w+|incrível|incríveis|surpreendente\w*|fantástic\w+|excelente\w*|de ponta|estado da arte)\b", re.I)


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    rule: str
    text: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: [{self.rule}] {self.text}"


def allowlist(path: Path = PAPER / "lint_allowlist.txt") -> set[str]:
    if not path.exists():
        return set()
    return {ln.split("#")[0].strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.split("#")[0].strip()}


def glossary(path: Path = PAPER / "glossary.tsv") -> list[tuple[re.Pattern, str]]:
    """(pattern, preferred term) for each avoided term."""
    if not path.exists():
        return []
    out = []
    for row in csv.DictReader(path.open(encoding="utf-8"), delimiter="\t"):
        for term in filter(None, (t.strip() for t in row["avoid"].split("|"))):
            out.append((re.compile(rf"\b{re.escape(term)}\b", re.I), row["use"]))
    return out


def prose(line: str) -> str:
    """The line without comments and without the arguments that are not prose."""
    line = re.sub(r"(?<!\\)%.*$", "", line)
    line = OPAQUE.sub(" ", line)
    line = re.sub(r"\\(?:texttt|verb|lstinline)\{[^{}]*\}", " ", line)
    return QUESTION_ID.sub(" ", LABELS.sub(" ", line))


def scan(text: str, name: str = "text", allowed: set[str] | None = None,
         terms: list[tuple[re.Pattern, str]] | None = None) -> list[Finding]:
    allowed = allowlist() if allowed is None else allowed
    terms = glossary() if terms is None else terms
    english = any(re.match(r"\s*%\s*lang:\s*en\b", ln) for ln in text.splitlines())
    found = []
    for i, raw in enumerate(text.splitlines(), 1):
        if raw.rstrip().endswith("% lint: ignore"):
            continue
        line = prose(raw)
        for m in NUMBER.finditer(line):
            if m.group(0) not in allowed:
                found.append(Finding(name, i, "number", f"'{m.group(0)}' typed in the text: use a macro from numbers.tex"))
        if english:
            continue
        for m in DASHES.finditer(line):
            found.append(Finding(name, i, "dash", f"'{m.group(0).strip() or '-'}' used as a dash: rewrite the sentence"))
        for m in FIRST_PERSON.finditer(line):
            found.append(Finding(name, i, "voice", f"'{m.group(0)}': the voice is impersonal"))
        for m in PROMOTIONAL.finditer(line):
            found.append(Finding(name, i, "promotional", f"'{m.group(0)}': no promotional adjective"))
        for pattern, use in terms:
            for m in pattern.finditer(line):
                found.append(Finding(name, i, "glossary", f"'{m.group(0)}': the glossary says '{use}'"))
    return found


def files(args: list[str]) -> list[Path]:
    if args:
        return [Path(a) for a in args]
    return sorted((PAPER / "sections").glob("*.tex")) + [p for p in [PAPER / "main.tex"] if p.exists()]


def main(argv: list[str]) -> int:
    paths = files(argv)
    found = []
    for p in paths:
        found += scan(p.read_text(encoding="utf-8"), str(p.relative_to(PAPER.parent)) if p.is_absolute() else str(p))
    for f in found:
        print(f)
    print(f"{len(found)} findings in {len(paths)} files" if found else f"clean: {len(paths)} files")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python
"""Prepare the citation check: for every \\cite in the text, the sentence and the cited paper's abstract.

The script does the mechanical part and leaves the judgement to the reader (the skill
``cite-check`` has Claude do it): it finds each (sentence, key) pair, fetches title, authors,
year and abstract of the cited paper by DOI, and writes paper/claims.md with one row per pair.
The ``veredito`` and ``nota`` columns are the reader's and survive a new run.

Sources, in order: Crossref (metadata and, when deposited, the abstract), arXiv (the abstract of
10.48550/arXiv.* DOIs), ACL Anthology (10.18653/v1/* DOIs), Semantic Scholar (abstract). Responses are cached in paper/.cache/refs/.

Also reports: keys cited but missing from refs.bib (an error) and entries never cited (a warning).

Usage:
    python paper/scripts/cite_check.py
    python paper/scripts/cite_check.py --offline      # cache only
"""

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
CACHE = PAPER / ".cache" / "refs"
CLAIMS = PAPER / "claims.md"
CITE = re.compile(r"\\cite\w*\*?(?:\[[^\]]*\])*\{([^}]*)\}")
VERDICTS = ("PENDENTE", "SUSTENTA", "SUSTENTA EM PARTE", "NAO SUSTENTA", "SEM RESUMO")
HEADER = ["arquivo:linha", "frase", "chave", "referência", "resumo da fonte", "veredito", "nota"]


def parse_bib(text: str) -> dict[str, dict]:
    """key -> {doi, title, year, authors}. A light parser: the file is generated, one field per line."""
    entries = {}
    for m in re.finditer(r"@\w+\{([^,\s]+),(.*?)\n\}", text, re.S):
        body = m.group(2)
        def field(name: str) -> str:
            f = re.search(rf"^\s*{name}\s*=\s*[{{\"](.*?)[}}\"],?\s*$", body, re.I | re.M)
            return f.group(1) if f else ""
        entries[m.group(1)] = {"doi": field("doi"), "title": field("title"), "year": field("year"), "authors": field("author")}
    return entries


def sentences(text: str) -> list[tuple[int, str]]:
    """(line of the first character, sentence) for each sentence that has a \\cite."""
    clean = re.sub(r"(?<!\\)%.*$", "", text, flags=re.M)
    out, pos = [], 0
    for m in re.finditer(r"[^.!?]*?(?:\\cite\w*\*?(?:\[[^\]]*\])*\{[^}]*\}[^.!?]*?)+(?:[.!?](?=\s|$)|$)", clean, re.S):
        sentence = " ".join(m.group(0).split())
        if CITE.search(sentence):
            first = m.start() + len(m.group(0)) - len(m.group(0).lstrip())  # skip the whitespace before the sentence
            out.append((clean.count("\n", 0, first) + 1, sentence))
    return out


def get(url: str, headers: dict | None = None, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "paper-cite-check/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def fetch(doi: str, offline: bool) -> dict:
    cache = CACHE / (hashlib.sha1(doi.encode()).hexdigest()[:16] + ".json")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    if offline or not doi:
        return {}
    info: dict = {"doi": doi}
    try:
        msg = json.loads(get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}", {"Accept": "application/json"}))["message"]
        info["title"] = (msg.get("title") or [""])[0]
        info["year"] = str((msg.get("issued", {}).get("date-parts") or [[""]])[0][0])
        info["abstract"] = re.sub(r"<[^>]+>", " ", msg.get("abstract", ""))
    except Exception as exc:
        info["crossref_error"] = type(exc).__name__
    arxiv = re.match(r"10\.48550/arxiv\.(.+)$", doi, re.I)
    if arxiv and not info.get("abstract"):
        try:
            root = ET.fromstring(get(f"https://export.arxiv.org/api/query?id_list={arxiv.group(1)}"))
            entry = root.find("{http://www.w3.org/2005/Atom}entry")
            if entry is not None:
                info["abstract"] = entry.findtext("{http://www.w3.org/2005/Atom}summary", "")
        except Exception as exc:
            info["arxiv_error"] = type(exc).__name__
    acl = re.match(r"10\.18653/v1/(.+)$", doi)
    if acl and not info.get("abstract"):  # the ACL Anthology page carries the abstract (its .bib does not)
        try:
            page = get(f"https://aclanthology.org/{acl.group(1)}/")
            m = re.search(r'acl-abstract"><h5 class=card-title>Abstract</h5><span>(.*?)</span>', page, re.S)
            info["abstract"] = re.sub(r"<[^>]+>", " ", m.group(1)) if m else ""
        except Exception as exc:
            info["acl_error"] = type(exc).__name__
    if not info.get("abstract"):
        try:
            sem = json.loads(get(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi)}?fields=title,abstract"))
            info["abstract"] = sem.get("abstract") or ""
        except Exception as exc:
            info["semanticscholar_error"] = type(exc).__name__
    info["abstract"] = " ".join(html.unescape(info.get("abstract", "")).split())
    CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    time.sleep(0.5)
    return info


def previous_verdicts(path: Path = CLAIMS) -> dict[tuple[str, str], tuple[str, str]]:
    """(sentence, key) -> (veredito, nota) from an earlier claims.md, so a new run keeps the review."""
    if not path.exists():
        return {}
    kept = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if len(cells) == len(HEADER) and cells[5] in VERDICTS:
            kept[(cells[1], cells[2])] = (cells[5], cells[6])
    return kept


def cell(text: str, limit: int | None = None) -> str:
    text = text.replace("|", "\\|").replace("\n", " ")
    return text if limit is None or len(text) <= limit else text[: limit - 1] + "…"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    bib = parse_bib((PAPER / "refs.bib").read_text(encoding="utf-8"))
    kept = previous_verdicts()
    rows, cited, missing = [], set(), set()
    for tex in sorted((PAPER / "sections").glob("*.tex")):
        for line, sentence in sentences(tex.read_text(encoding="utf-8")):
            for keys in CITE.findall(sentence):
                for key in (k.strip() for k in keys.split(",")):
                    cited.add(key)
                    if key not in bib:
                        missing.add(key)
                        continue
                    info = fetch(bib[key]["doi"], args.offline)
                    title = info.get("title") or bib[key]["title"]
                    abstract = info.get("abstract", "")
                    verdict, note = kept.get((cell(sentence), key), ("PENDENTE" if abstract else "SEM RESUMO", ""))
                    rows.append([f"{tex.name}:{line}", cell(sentence), key, cell(f"{title} ({info.get('year') or bib[key]['year']}), doi:{bib[key]['doi']}"),
                                 cell(abstract, 600) or "—", verdict, cell(note)])
    out = ["# Afirmações e fontes", "",
           "Gerado por `paper/scripts/cite_check.py`. Cada linha é uma frase com `\\cite` e o resumo da fonte citada. "
           "As colunas `veredito` e `nota` são da revisão (skill `cite-check`) e sobrevivem a uma nova execução. "
           f"Veredito: {', '.join(VERDICTS)}.", "",
           "| " + " | ".join(HEADER) + " |", "|" + "|".join("---" for _ in HEADER) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    CLAIMS.write_text("\n".join(out) + "\n", encoding="utf-8")
    unused = sorted(set(bib) - cited)
    pending = sum(r[5] in ("PENDENTE", "SEM RESUMO") for r in rows)
    print(f"{len(rows)} pairs sentence/key written to {CLAIMS.relative_to(PAPER.parent)}; {pending} to review")
    if unused:
        print(f"warning: {len(unused)} entries of refs.bib are never cited: {', '.join(unused)}")
    if missing:
        print(f"ERROR: cited but not in refs.bib: {', '.join(sorted(missing))}", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
"""Build paper/refs.bib from the DOIs in paper/refs/references.tsv.

Each entry comes from the DOI resolver (content negotiation, Crossref or DataCite
metadata), so authors, venue and year are the publisher's, not typed by hand. The cite key
is the one in the table. The title returned is printed next to the short name from the
table: read that list once, because a DOI that resolves to the wrong paper is not an
error to the resolver.

Software and data sources without a DOI are in paper/refs/software.bib and are appended. Entries in
paper/refs/overrides.bib replace the resolver's entry with the same key (published version without a DOI of
its own, or wrong metadata from the resolver).

Usage:
    python paper/scripts/fetch_bibtex.py            # all
    python paper/scripts/fetch_bibtex.py --check    # list the titles only, write nothing
"""

import argparse
import csv
import re
import sys
import time
import urllib.request
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
TABLE = PAPER / "refs" / "references.tsv"
SOFTWARE = PAPER / "refs" / "software.bib"
OVERRIDES = PAPER / "refs" / "overrides.bib"
OUT = PAPER / "refs.bib"


def fetch(doi: str, retries: int = 3) -> str:
    req = urllib.request.Request(f"https://doi.org/{doi}", headers={"Accept": "application/x-bibtex"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8").strip()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def rekey(entry: str, key: str) -> str:
    return re.sub(r"^(@\w+)\s*\{[^,]+,", rf"\1{{{key},", entry.strip(), count=1)


def field(entry: str, name: str) -> str:
    m = re.search(rf"\b{name}\s*=\s*[{{\"](.*?)[}}\"]\s*,?\s*(?:\w+\s*=|}})", " ".join(entry.split()), re.I)
    return m.group(1) if m else ""


DROP = {"keywords", "copyright", "month", "issn", "collection"}  # noise, or (month) a bare macro bibtex warns about


def clean(parts: list[str]) -> list[str]:
    """Fix what the `plain` style renders wrong: lowercased titles, "page 1–2", arXiv entries without the id."""
    out, arxiv = [], ""
    for p in parts:
        name, _, value = p.partition("=")
        name, value = name.strip(), value.strip()
        if name.lower() in DROP:
            continue
        if name.lower() == "title" and not value.startswith("{{"):
            value = "{" + value + "}"  # keep the publisher's capitalization (SportQA, LLMs, CRISP-DM)
        if name.lower() == "pages":
            value = value.replace("–", "--")
        if name.lower() == "doi":
            m = re.search(r"arxiv\.(\d{4}\.\d{4,5})", value, re.I)
            arxiv = m.group(1) if m else ""
        out.append(f"{name} = {value}" if _ else p)
    if arxiv and not any(p.lower().startswith("howpublished") for p in out):
        out.append(f"howpublished = {{arXiv:{arxiv}}}")
    return out


def pretty(entry: str) -> str:
    """One field per line: easier to read in the Overleaf editor and in diffs."""
    entry = " ".join(entry.split()).replace("&amp;", r"\&")  # the DOI resolver leaves HTML entities; a bare & breaks LaTeX
    head, body = entry.split(",", 1)
    body = body.strip()
    body = body[:-1].strip() if body.endswith("}") else body  # the entry's own closing brace
    parts = clean([p.strip() for p in re.split(r",\s*(?=\w+\s*=)", body)])
    return head + ",\n  " + ",\n  ".join(parts) + "\n}"


MAX_AUTHORS = 6  # longer lists are cut to the first six plus "and others", which the plain style prints as "et al."


def shorten_authors(entry: str, limit: int = MAX_AUTHORS) -> str:
    """Keep the first `limit` authors of a long list and end it with `and others` (a page-budget choice)."""
    m = re.search(r"(author\s*=\s*\{)(.*?)(\},?\s*\n)", entry, re.S)
    if not m:
        return entry
    names = re.split(r"\s+and\s+", " ".join(m.group(2).split()))
    if len(names) <= limit or names[-1] == "others":
        return entry
    cut = " and ".join(names[:limit]) + " and others"
    return entry[: m.start(2)] + cut + entry[m.end(2):]


def overrides() -> dict[str, str]:
    if not OVERRIDES.exists():
        return {}
    text = OVERRIDES.read_text(encoding="utf-8")
    return {m.group(1): m.group(0).strip() for m in re.finditer(r"^@\w+\{([^,]+),.*?^\}", text, re.S | re.M)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = list(csv.DictReader(TABLE.open(encoding="utf-8"), delimiter="\t"))
    entries, failed, manual = [], [], overrides()
    for row in rows:
        if row["key"] in manual:
            entries.append(manual[row["key"]])
            print(f"{row['status']:10s} {row['key']:28s} {row['short'][:26]:26s} -> (overrides.bib)")
            continue
        try:
            raw = fetch(row["doi"])
        except Exception as exc:  # network or unknown DOI
            failed.append(row["key"])
            print(f"FAIL  {row['key']:28s} {row['doi']}  ({type(exc).__name__})")
            continue
        entry = pretty(rekey(raw, row["key"]))
        if entry.count("{") != entry.count("}"):
            failed.append(row["key"])
            print(f"FAIL  {row['key']:28s} unbalanced braces in the BibTeX returned")
            continue
        entries.append(entry)
        print(f"{row['status']:10s} {row['key']:28s} {row['short'][:26]:26s} -> {field(raw, 'title')[:90]}")
    if failed:
        print(f"\n{len(failed)} DOIs did not resolve: {', '.join(failed)}", file=sys.stderr)
    if args.check:
        return 1 if failed else 0
    software = SOFTWARE.read_text(encoding="utf-8").strip() if SOFTWARE.exists() else ""
    header = ("% Generated by paper/scripts/fetch_bibtex.py from paper/refs/references.tsv "
              "(DOI resolver). Do not edit by hand: change the table and run again.\n\n")
    entries = [shorten_authors(e) for e in entries]
    OUT.write_text(header + "\n\n".join(entries) + ("\n\n" + software if software else "") + "\n", encoding="utf-8")
    print(f"\nwritten {OUT.relative_to(PAPER.parent)}: {len(entries)} entries with DOI"
          f"{' + software' if software else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

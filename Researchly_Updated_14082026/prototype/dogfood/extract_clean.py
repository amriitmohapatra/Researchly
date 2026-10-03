"""Extract and clean thesis text from pdftotext output for dogfooding.

Goals: recover readable prose paragraphs + standalone heading lines (so
Researchly's plain-text section detection can work), and drop the noise a
PDF adds that a real .tex/.qmd source would never contain (page numbers,
TOC dot leaders, references, equation glyph soup).
"""

import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Paths are resolved from this file so the corpus can be re-extracted on any
# machine. They were hardcoded to a cloud sandbox, which meant the noise-floor
# guard — the project's primary precision regression check — could not be run
# locally at all.
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC = Path(os.environ.get("RESEARCHLY_CORPUS",
                          REPO / "Sample_thesis_drafts"))
OUT = Path(os.environ.get("RESEARCHLY_CORPUS_TEXT", HERE / "text"))
OUT.mkdir(parents=True, exist_ok=True)

HEADING_RX = re.compile(
    r"^(?:chapter\s+\d+[.:]?\s*|(?:\d+\.)+\d*\s+|\d+\s+)?"
    r"([A-Z][A-Za-z ,&\-]{2,70})$")
REF_START = re.compile(r"^(references|bibliography)\s*$", re.I)
CHAPTER_START = re.compile(r"^(chapter\s+\d+|appendix\b)", re.I)
DOT_LEADER = re.compile(r"\.{4,}")
PAGE_NUM = re.compile(r"^\s*(page\s+)?[divxlc0-9]{1,4}\s*$", re.I)


def alpha_ratio(s: str) -> float:
    if not s:
        return 0.0
    ok = sum(1 for c in s if c.isalpha() or c in " ,.;:()'\"-%")
    return ok / len(s)


def extract(pdf: Path) -> str:
    return subprocess.run(
        ["pdftotext", "-q", str(pdf), "-"],
        capture_output=True, text=True, timeout=600).stdout


def clean(raw: str) -> str:
    lines = [ln.rstrip() for ln in raw.replace("\f", "\n").split("\n")]

    # Identify running headers/footers: short lines repeated many times
    freq = Counter(ln.strip() for ln in lines
                   if 0 < len(ln.strip()) < 70)
    running = {ln for ln, n in freq.items()
               if n >= 8 and not REF_START.match(ln)}

    out_lines: list[str] = []
    in_refs = False
    for ln in lines:
        s = ln.strip()
        if REF_START.match(s):
            in_refs = True
            continue
        if in_refs:
            if CHAPTER_START.match(s):
                in_refs = False
            else:
                continue
        if not s:
            out_lines.append("")
            continue
        if s in running or PAGE_NUM.match(s) or DOT_LEADER.search(s):
            continue
        out_lines.append(s)

    # Rebuild: headings stand alone; wrapped lines join into paragraphs.
    paras: list[str] = []
    buf: list[str] = []

    def flush():
        if buf:
            p = " ".join(buf)
            p = re.sub(r"(\w)-\s+(\w)", r"\1\2", p)      # de-hyphenate
            p = re.sub(r"\s+", " ", p).strip()
            if len(p) >= 40 and alpha_ratio(p) >= 0.72:  # drop glyph soup
                paras.append(p)
            buf.clear()

    for ln in out_lines:
        s = ln.strip()
        if not s:
            flush()
            continue
        m = HEADING_RX.match(s)
        if m and len(s) < 72 and not s.endswith((".", ",", ";", ":")):
            title = m.group(1).strip()
            # keep only useful headings (section words or short title case)
            flush()
            paras.append("")
            paras.append(title)
            paras.append("")
            continue
        buf.append(s)
    flush()

    text = "\n\n".join(p for p in paras)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def main():
    for pdf in sorted(SRC.glob("*.pdf")):
        name = re.sub(r"[^\w]+", "_", pdf.stem).strip("_")[:40]
        dest = OUT / f"{name}.txt"
        raw = extract(pdf)
        cleaned = clean(raw)
        dest.write_text(cleaned, encoding="utf-8")
        print(f"{pdf.name:55s} raw={len(raw):>9,}  clean={len(cleaned):>9,}"
              f"  -> {dest.name}")


if __name__ == "__main__":
    sys.exit(main())

"""Extract and clean thesis text from pdftotext output for dogfooding.

Goals: recover readable prose paragraphs + standalone heading lines (so
Researchly's plain-text section detection can work), and drop the noise a
PDF adds that a real .tex/.qmd source would never contain (page numbers,
running headers and footers, TOC dot leaders, references, equation glyph
soup).

Repair pass (2026-10-15, PLAN Q3): about 90% of the S001 flags on the old
corpus were the extractor's, not the theses'. Two artefacts, both repaired
deterministically here and pinned by `test_extract_clean.py` on synthetic
pages:

- **Line-break hyphens.** pdftotext's layout mode joins a word hyphenated at
  a line end and drops the hyphen, so a compound broken at its hyphen
  ("laboratory-" / "confirmed") came out as one non-word. Its raw mode keeps
  every line-end hyphen but loses paragraph breaks. So the corpus keeps the
  layout text and restores the hyphen in the words raw mode shows were
  broken at a line end, wherever a hyphen belongs (`keep_hyphen`).
- **Page breaks.** A paragraph that runs over a page break was cut in two
  by the page's furniture (running header, footer, page number), and a word
  hyphenated across the break stayed in two pieces ("coun-" … "tion"). Page
  furniture is now stripped page by page, and a page that ends mid-sentence
  is joined to the next when the next carries on in lower case.

The structure (which lines exist, where paragraphs break) is otherwise the
layout mode's, as before; only words and page joins change.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

# Paths are resolved from this file so the corpus can be re-extracted on any
# machine. They were hardcoded to a cloud sandbox, which meant the noise-floor
# guard — the project's primary precision regression check — could not be run
# locally at all.
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC = Path(os.environ.get("RESEARCHLY_CORPUS",
                          REPO / "Sample_thesis_drafts"))
OUT = Path(os.environ.get("RESEARCHLY_CORPUS_TEXT", HERE / "text"))
CORE_DATA = REPO / "packages" / "core" / "researchly" / "data"

HEADING_RX = re.compile(
    r"^(?:chapter\s+\d+[.:]?\s*|(?:\d+\.)+\d*\s+|\d+\s+)?"
    r"([A-Z][A-Za-z ,&\-]{2,70})$")
REF_START = re.compile(r"^(references|bibliography)\s*$", re.I)
REF_SINGULAR = re.compile(r"^reference\s*$", re.I)
NUMBERED_ENTRY = re.compile(r"^(?:1\.\s|\[1\])")
CHAPTER_START = re.compile(r"^(chapter\s+\d+|appendix\b)", re.I)
DOT_LEADER = re.compile(r"\.{4,}")
PAGE_NUM = re.compile(r"^\s*(page\s+)?[divxlc0-9]{1,4}\s*$", re.I)

# A word broken at a line end: letters, a hyphen, then the next line.
LINE_END_HYPHEN = re.compile(r"([A-Za-z]+)-$")
LINE_START_WORD = re.compile(r"\s*([A-Za-z]+)")
# A suspended hyphen ("pre- and post-test") is not a broken word.
SUSPENDED = frozenset({"and", "or", "to", "nor", "versus", "vs"})
WORD_RX = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*")
# How many lines at the top and bottom of a page may be furniture, and how
# many pages a header or footer must recur on to count as one.
FURNITURE_LINES = 3
FURNITURE_MIN_PAGES = 5
SENTENCE_END = re.compile(r"[.?!:]['\")\]]*$")


def alpha_ratio(s: str) -> float:
    if not s:
        return 0.0
    ok = sum(1 for c in s if c.isalpha() or c in " ,.;:()'\"-%")
    return ok / len(s)


def extract(pdf: Path, raw: bool = False) -> str:
    """pdftotext's layout-order text, or (raw=True) its content-stream text,
    which keeps every line-end hyphen but has no paragraph breaks."""
    args = ["pdftotext", "-q"] + (["-raw"] if raw else []) + [str(pdf), "-"]
    return subprocess.run(args, capture_output=True, text=True,
                          timeout=600).stdout


# --- words ---------------------------------------------------------------------

def load_known_words() -> frozenset:
    """Lower-case words a general or scientific dictionary knows: the
    symspellpy frequency list plus the engine's scientific and specialist
    lexicons. Used only to decide whether a word broken at a line end is
    one word ("transmis-" / "sion") or a hyphenated compound."""
    words: set = set()
    try:
        from importlib import resources
        ref = resources.files("symspellpy") / "frequency_dictionary_en_82_765.txt"
        for line in ref.read_text(encoding="utf-8").splitlines():
            if line:
                words.add(line.split(" ", 1)[0].lower())
    except Exception:  # noqa: BLE001 - extraction still runs on evidence alone
        pass
    for name in ("scientific_terms.txt", "specialist_words.txt"):
        p = CORE_DATA / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                w = line.strip().lower()
                if w and not w.startswith("#"):
                    words.add(w)
    return frozenset(words)


class Evidence:
    """How the document itself spells words when no line break interferes:
    counts of single words and of hyphenated pairs ("laboratory-confirmed"
    counts the pair and each part)."""

    def __init__(self, text: str):
        # A hyphen at a line end is the thing being decided, never evidence.
        text = re.sub(r"(?<=[A-Za-z])-[ \t]*\n[\s\f]*(?=[A-Za-z])", " \x00 ",
                      text)
        self.words: Counter = Counter()
        self.pairs: Counter = Counter()
        for tok in WORD_RX.findall(text):
            parts = tok.lower().split("-")
            self.words.update(parts)
            for a, b in zip(parts, parts[1:]):
                self.pairs[a + "-" + b] += 1

    def joined(self, head: str, tail: str) -> int:
        return self.words[(head + tail).lower()]

    def hyphenated(self, head: str, tail: str) -> int:
        return self.pairs[(head + "-" + tail).lower()]


def keep_hyphen(head: str, tail: str, evidence: Optional[Evidence],
                known: Iterable[str]) -> bool:
    """Was "head-" at a line end followed by "tail" a hyphenated compound
    (keep the hyphen) rather than one word broken across lines (join)?

    In order: a capital or digit after the break keeps it ("COVID-19",
    "non-Asian"); then the document's own unbroken spellings decide; then a
    dictionary: a known joined word joins, two known halves stay hyphenated
    ("well-known"), and anything else is a word broken at a syllable."""
    if not tail[:1].islower() or not head[-1:].isalpha():
        return True
    if evidence is not None:
        j, h = evidence.joined(head, tail), evidence.hyphenated(head, tail)
        if j != h:
            return h > j
    joined = (head + tail).lower()
    if joined in known:
        return False
    return head.lower() in known and tail.lower() in known


def join_broken(head: str, tail: str, evidence: Optional[Evidence],
                known: Iterable[str]) -> str:
    return head + ("-" if keep_hyphen(head, tail, evidence, known) else "") + tail


def line_break_pairs(raw_text: str) -> Counter:
    """(head, tail) for every word raw-mode text shows hyphenated at a line
    end, with how often."""
    pairs: Counter = Counter()
    lines = raw_text.split("\n")
    for a, b in zip(lines, lines[1:]):
        m = LINE_END_HYPHEN.search(a.rstrip())
        n = LINE_START_WORD.match(b)
        if m and n and n.group(1).lower() not in SUSPENDED:
            pairs[(m.group(1), n.group(1))] += 1
    return pairs


def restore_hyphens(layout_text: str, raw_text: str,
                    known: Iterable[str],
                    evidence: Optional[Evidence] = None) -> str:
    """Put back the hyphen pdftotext's layout mode drops from a compound
    broken at a line end.

    Layout mode prints "laboratory-" / "confirmed" as "laboratoryconfirmed";
    raw mode prints the line break. For every such pair whose hyphen belongs
    (`keep_hyphen`), the joined form becomes hyphenated, but only when the
    document never spells it joined elsewhere: then every joined occurrence
    in the layout text is one of those line breaks."""
    evidence = evidence or Evidence(raw_text)
    out = layout_text
    for (head, tail), _ in sorted(line_break_pairs(raw_text).items()):
        if not keep_hyphen(head, tail, evidence, known):
            continue
        if evidence.joined(head, tail):
            continue
        out = re.sub(r"(?<![A-Za-z])" + re.escape(head + tail) + r"(?![A-Za-z])",
                     head + "-" + tail, out)
    return out


# --- pages ---------------------------------------------------------------------

def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", line.strip().lower()))


def _ends(lines: list) -> list:
    """Indexes of the first and last few non-empty lines of a page."""
    idx = [i for i, ln in enumerate(lines) if ln.strip()]
    return idx[:FURNITURE_LINES] + idx[-FURNITURE_LINES:]


def strip_page_furniture(pages: list) -> tuple:
    """Remove page numbers and running headers/footers from the top and
    bottom of each page.

    A header or footer is a line (digits ignored, so "Chapter 3 · 41" and
    "Chapter 3 · 42" agree) found among the first or last few lines of
    pages that follow one another, at least FURNITURE_MIN_PAGES times. Runs
    of pages are what tell furniture from a heading that recurs: "Chapter 4"
    opens one page per chapter, a running header sits on every page. A
    "References" line is never furniture: it starts a reference list the
    cleaner skips.

    Returns the pages and, for each, the headers or footers taken off it
    (digits ignored, page numbers left out): a change of running header is
    how `skip_references` sees a new chapter begin."""
    keys = [{_norm(lines[i]) for i in _ends(lines)} for lines in pages]
    runs: Counter = Counter()
    for a, b in zip(keys, keys[1:]):
        runs.update(a & b)
    furniture = {k for k, n in runs.items()
                 if n >= FURNITURE_MIN_PAGES and len(k) < 100
                 and not REF_START.match(k)}

    def is_furniture(line: str) -> bool:
        return bool(PAGE_NUM.match(line)) or _norm(line) in furniture

    out, headers = [], []
    for lines in pages:
        lines = list(lines)
        taken = set()
        for end in (0, -1):                       # the top, then the bottom
            for _ in range(FURNITURE_LINES):
                idx = [i for i, ln in enumerate(lines) if ln.strip()]
                if not idx or not is_furniture(lines[idx[end]]):
                    break
                key = _norm(lines[idx[end]])
                if key in taken:     # a heading right under its own header
                    break
                if re.search(r"[a-z]", key) and not PAGE_NUM.match(key):
                    taken.add(key)
                del lines[idx[end]]
        out.append(lines)
        headers.append(frozenset(taken))
    return out, headers


def _numbered_next(lines: list, i: int) -> bool:
    """Whether the next line with text opens a numbered reference ("1. "
    or "[1]")."""
    nxt = next((ln.strip() for ln in lines[i + 1:] if ln.strip()), "")
    return bool(NUMBERED_ENTRY.match(nxt))


def skip_references(pages: list, headers: list) -> list:
    """Drop reference lists: from a "References"/"Bibliography" line to the
    next chapter, which is a "Chapter N"/"Appendix" line or, when the
    document has running headers, the first page whose header differs from
    the list's own (the next chapter's header, or none on its opening
    page). A singular "Reference" heading counts only above a numbered
    first entry: the word is also a table's column heading. Before page
    furniture was stripped, the next page's running
    header ended a list after one page, and the rest of it was checked as
    prose."""
    out = []
    in_refs, refs_header = False, frozenset()
    for lines, header in zip(pages, headers):
        if in_refs and header != refs_header:
            in_refs = False
        kept = []
        for i, ln in enumerate(lines):
            s = ln.strip()
            if REF_START.match(s) or (REF_SINGULAR.match(s)
                                      and _numbered_next(lines, i)):
                in_refs, refs_header = True, header
                continue
            if in_refs:
                if CHAPTER_START.match(s):
                    in_refs = False
                else:
                    continue
            kept.append(ln)
        out.append(kept)
    return out


def _header_like(line: str) -> bool:
    """A short line that can sit between a page's last words and their
    continuation: a page number, or a running header ("4.2 Data",
    "Chapter 3. Methods") that recurs too seldom to be found as furniture
    (a short section's header)."""
    s = line.strip()
    return bool(PAGE_NUM.match(s)) or (
        len(s) < 70 and not SENTENCE_END.search(s) and not s[:1].islower())


def join_pages(pages: list, evidence: Optional[Evidence],
               known: Iterable[str]) -> list:
    """One list of lines. A page that ends mid-sentence runs on into the
    next when the next carries on in lower case: "coun-" / "tion" becomes
    one word (`join_broken`) and a sentence cut by the break becomes one
    paragraph. Up to FURNITURE_LINES short header-like lines before the
    continuation are furniture and dropped: nothing a reader sees can stand
    between the halves of a word or a sentence. Otherwise the pages are
    separated by a blank line, as the form feed used to be."""
    out: list = []
    for lines in pages:
        body = [ln.rstrip() for ln in lines]
        while body and not body[0].strip():
            body.pop(0)
        last = next((i for i in range(len(out) - 1, -1, -1)
                     if out[i].strip()), None)
        run_on = False
        if body and last is not None:
            prev = out[last].rstrip()
            m = LINE_END_HYPHEN.search(prev)
            open_end = bool(m) or not SENTENCE_END.search(prev)
            text = [i for i, ln in enumerate(body) if ln.strip()]
            k = next((j for j, i in enumerate(text[:FURNITURE_LINES + 1])
                      if body[i].strip()[:1].islower()), None)
            if open_end and k is not None and all(
                    _header_like(body[i]) for i in text[:k]):
                first = body[text[k]].strip()
                n = LINE_START_WORD.match(first)
                body = body[text[k]:]
                if m and n:
                    joined = join_broken(m.group(1), n.group(1), evidence,
                                         known)
                    out[last] = prev[:m.start()] + joined + first[n.end():]
                    body = body[1:]
                del out[last + 1:]           # same paragraph: no blank line
                run_on = True
        if out and not run_on:
            out.append("")
        out.extend(body)
    return out


GLUED_NUMBER = re.compile(r"([A-Za-z]{2,})(\d{1,4})$")


def unglue_page_numbers(pages: list, raw_mode: str) -> list:
    """Layout mode joins a page's last word, hyphenated at the line end,
    to the page number printed below it ("defin-" / "103" comes out as
    "defin103"). Raw mode shows the hyphen and the number on its own line;
    where it does, the number goes and the hyphen comes back, so
    `join_pages` can rejoin the word on the next page."""
    out = []
    for lines in pages:
        lines = list(lines)
        idx = [i for i, ln in enumerate(lines) if ln.strip()]
        if idx:
            i = idx[-1]
            m = GLUED_NUMBER.search(lines[i].rstrip())
            if m and re.search(r"(?<![A-Za-z])" + re.escape(m.group(1))
                               + r"-[ \t]*\n\s*" + m.group(2) + r"\s*(?:\n|\f|$)",
                               raw_mode):
                lines[i] = lines[i].rstrip()[:m.start(2)] + "-"
        out.append(lines)
    return out


# --- clean ---------------------------------------------------------------------

def clean(raw: str, raw_mode: Optional[str] = None,
          known: Optional[Iterable[str]] = None) -> str:
    """Prose paragraphs and headings from pdftotext's layout text `raw`.
    `raw_mode` is the same PDF's `-raw` text; with it, compounds broken at
    a line end get their hyphen back."""
    known = load_known_words() if known is None else known
    evidence = Evidence(raw_mode if raw_mode is not None else raw)
    if raw_mode is not None:
        raw = restore_hyphens(raw, raw_mode, known, evidence)

    pages = [p.split("\n") for p in raw.split("\f")]
    if raw_mode is not None:
        pages = unglue_page_numbers(pages, raw_mode)
    pages, headers = strip_page_furniture(pages)
    lines = join_pages(skip_references(pages, headers), evidence, known)
    lines = [ln.rstrip() for ln in lines]

    # Identify running headers/footers: short lines repeated many times
    freq = Counter(ln.strip() for ln in lines
                   if 0 < len(ln.strip()) < 70)
    running = {ln for ln, n in freq.items()
               if n >= 8 and not REF_START.match(ln)}

    out_lines: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            out_lines.append("")
            continue
        if s in running or PAGE_NUM.match(s) or DOT_LEADER.search(s):
            continue
        out_lines.append(s)

    # Rebuild: headings stand alone; wrapped lines join into paragraphs.
    paras: list[str] = []
    buf: list[str] = []

    def dehyphenate(m: re.Match) -> str:
        head, tail = m.group(1), m.group(2)
        if tail.lower() in SUSPENDED:        # "pre- and post-test"
            return m.group(0)
        return join_broken(head, tail, evidence, known)

    def flush():
        if buf:
            p = " ".join(buf)
            p = re.sub(r"([A-Za-z]+)-\s+([A-Za-z0-9]+)", dehyphenate, p)
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
    OUT.mkdir(parents=True, exist_ok=True)
    known = load_known_words()
    for pdf in sorted(SRC.glob("*.pdf")):
        name = re.sub(r"[^\w]+", "_", pdf.stem).strip("_")[:40]
        dest = OUT / f"{name}.txt"
        raw = extract(pdf)
        cleaned = clean(raw, extract(pdf, raw=True), known)
        dest.write_text(cleaned, encoding="utf-8")
        print(f"{pdf.name:55s} raw={len(raw):>9,}  clean={len(cleaned):>9,}"
              f"  -> {dest.name}")


if __name__ == "__main__":
    sys.exit(main())

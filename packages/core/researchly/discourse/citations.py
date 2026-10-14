"""Where each cited source first appears: the review's links to the
Discussion (S4; owner request 2026-10-14).

A source that carries the Discussion but was never cited before it is a
"stranger". It means one of two things: the review left it out, or the
Discussion has moved on to another question. Researchly shows such
sources on the narrative map and in the reviewer's brief. It never flags
them as an error: a
Discussion may legitimately bring in new work, and only the writer knows
which case this is.

Deterministic and conservative. Citations are read from the original text
in the form the document uses:

- LaTeX: the keys of `\\cite`-family commands in prose (not `\\nocite`);
- Markdown and Quarto: `[@key]` and `@key`;
- plain text and Word, and LaTeX or Markdown written without citation
  commands: author-year, "(Lim et al., 2021; Okafor 2019)" and
  "Lim et al. (2021)", or numbered, "[12]" and "[3-5]".

Only the document's main style is used, so a stray "[1]" in a document
cited author-year is not read as a source. Nothing is reported when the
citations cannot be read reliably: no section before the Discussion that
reviews the literature, or fewer than `MIN_REVIEW_CITATIONS` citations in
it. A source counts as a stranger only when it is cited in two or more
sentences of the Discussion (it carries the argument, it is not a passing
comparison) and nowhere in the document before the Discussion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..document import Document, classify_heading

# Below this many citations in the review there is too little to judge
# whether the citation style was read at all.
MIN_REVIEW_CITATIONS = 3
# A source carries the Discussion when it is cited in this many sentences.
MIN_DISCUSSION_SENTENCES = 2
# Shown by name in the message; the rest are counted.
SHOW = 5

# A heading that opens a review of the literature, whatever the IMRaD
# classifier calls it ("Literature review" is "other" to it).
_REVIEW_HEADING = re.compile(
    r"\b(?:literature|related (?:work|studies|research)|previous "
    r"(?:work|studies|research)|prior (?:work|studies|research)|state of "
    r"the art|background|review of)\b", re.IGNORECASE)

_SURNAME = r"(?:(?:van|von|de|der|den|du|da|di|le|la|del|dos|ter)\s+)*" \
           r"[A-Z][^\W\d_]*(?:[-'\u2019][A-Z]?[^\W\d_]+)*"
_YEAR = r"(?:1[89]\d{2}|20\d{2})[a-z]?"
# Months, float labels and other capitalised words that precede a year in
# brackets without being an author: "(March 2020)", "(Table 2, 2021)".
_NOT_AUTHOR = frozenset("""
    january february march april may june july august september october
    november december jan feb mar apr jun jul aug sep sept oct nov dec
    spring summer autumn fall winter table figure fig supplementary appendix
    section chapter eq equation since from until before after during in on
    by between week weeks year years season n see e i cf and or the
    """.split())
# One reference inside brackets: "e.g., Lim et al., 2021", "Okafor and
# Mensah 2019a, 2020", "WHO, 2020: 14".
_PAREN_REF = re.compile(
    rf"^(?:(?:e\.g\.|i\.e\.|see(?: also)?|cf\.|for example|for a review,? see)"
    rf"[,]?\s+)?(?P<author>{_SURNAME})(?P<etal>\s+et\s+al\.?|\s+(?:and|&)\s+"
    rf"{_SURNAME})?,?\s+(?P<years>{_YEAR}(?:\s*,\s*{_YEAR})*)"
    rf"(?:\s*[,:]\s*(?:pp?\.\s*)?\d+(?:[-\u2013]\d+)?)?$")
_PAREN = re.compile(rf"\(([^()\n]{{4,400}}?\b{_YEAR}\b[^()\n]{{0,80}}?)\)")
_NARRATIVE = re.compile(
    rf"(?P<author>{_SURNAME})(?P<etal>\s+et\s+al\.?|\s+(?:and|&)\s+"
    rf"{_SURNAME})?\s+\((?P<years>{_YEAR}(?:\s*[,;]\s*{_YEAR})*)\)")
_NUMBERED = re.compile(
    r"\[(\d{1,3}(?:\s*[-\u2013]\s*\d{1,3})?(?:\s*,\s*\d{1,3}"
    r"(?:\s*[-\u2013]\s*\d{1,3})?)*)\]")
_LATEX_CITE = re.compile(
    r"\\(?P<cmd>[a-zA-Z]*cites?[a-zA-Z]*)\*?(?:\[[^\]]*\])*\{(?P<keys>[^{}]*)\}")
_MD_CITE = re.compile(r"(?<![\w.])@(?P<key>[A-Za-z0-9_][\w:.\-]*[A-Za-z0-9_])")


@dataclass(frozen=True)
class Citation:
    key: str        # identity used to compare sources ("lim 2021", "[12]")
    label: str      # what the writer recognises ("Lim et al. 2021")
    start: int      # offsets into the original text
    end: int
    style: str      # "key" | "author-year" | "numbered"


def _years(text: str) -> list:
    return re.findall(_YEAR, text)


def _author_year(author: str, etal: Optional[str], year: str,
                 start: int, end: int) -> Optional[Citation]:
    first = author.split()[-1] if author.split()[0].islower() else author
    if author.lower() in _NOT_AUTHOR or first.lower() in _NOT_AUTHOR:
        return None
    if len(first) < 2:
        return None
    tail = ""
    if etal:
        tail = " et al." if "et" in etal else " and " + etal.split()[-1]
    return Citation(key=f"{first.lower()} {year.lower()}",
                    label=f"{author}{tail} {year}", start=start, end=end,
                    style="author-year")


def read_citations(document: Document) -> list:
    """Every citation in the prose, in document order."""
    text = document.original
    out: list = []
    if document.kind == "latex":
        for m in _LATEX_CITE.finditer(text):
            if m.group("cmd").lower() == "nocite":
                continue
            if not document.masked_content(m.start(), m.start() + 1):
                continue            # in a comment or outside the prose
            for key in m.group("keys").split(","):
                key = key.strip()
                if key and key != "*":
                    out.append(Citation(key, key, m.start(), m.end(), "key"))
    elif document.kind == "markdown":
        for m in _MD_CITE.finditer(text):
            if document.masked_content(m.start(), m.end()):
                out.append(Citation(m.group("key"), "@" + m.group("key"),
                                    m.start(), m.end(), "key"))
    if out:
        return out
    # Citations typed as text: plain text and Word always, and LaTeX or
    # Markdown written without citation commands. Only prose counts: a
    # comment or a code block is masked.
    out = [c for c in _typed_citations(text)
           if document.masked[c.start] == text[c.start]]
    # The document's main style only: a stray "[1]" in an author-year
    # document is a list marker or a footnote, not a source.
    by_style: dict = {}
    for c in out:
        by_style[c.style] = by_style.get(c.style, 0) + 1
    if not by_style:
        return []
    main = max(by_style, key=by_style.get)
    return [c for c in out if c.style == main]


def _typed_citations(text: str) -> list:
    out: list = []
    for m in _PAREN.finditer(text):
        for part in re.split(r"\s*;\s*", m.group(1)):
            r = _PAREN_REF.match(part.strip())
            if not r:
                continue
            for year in _years(r.group("years")):
                c = _author_year(r.group("author"), r.group("etal"), year,
                                 m.start(), m.end())
                if c:
                    out.append(c)
    for m in _NARRATIVE.finditer(text):
        for year in _years(m.group("years")):
            c = _author_year(m.group("author"), m.group("etal"), year,
                             m.start(), m.end())
            if c:
                out.append(c)
    for m in _NUMBERED.finditer(text):
        for part in m.group(1).split(","):
            bounds = [int(x) for x in re.split(r"\s*[-\u2013]\s*", part.strip())]
            lo, hi = bounds[0], bounds[-1]
            if hi < lo or hi - lo > 30:
                continue
            for n in range(lo, hi + 1):
                out.append(Citation(f"[{n}]", f"[{n}]", m.start(), m.end(),
                                    "numbered"))
    out.sort(key=lambda c: c.start)
    return out


def review_spans(document: Document) -> list:
    """(start, end) of the text that reviews the literature: the
    Introduction and Background sections, and any section headed as a
    literature review, with its subsections."""
    heads = sorted(document.headings, key=lambda h: h.start)
    spans = []
    for i, h in enumerate(heads):
        own = h.keyword or classify_heading(h.text)
        if not (h.section == "introduction" or own == "introduction"
                or _REVIEW_HEADING.search(h.text)):
            continue
        end = len(document.original)
        for g in heads[i + 1:]:
            if h.level is not None and g.level is not None:
                if g.level <= h.level:
                    end = g.start
                    break
            elif g.section not in ("other", "introduction"):
                end = g.start
                break
        spans.append((h.start, end))
    return spans


def _sentence_spans(document: Document, spacy_doc=None) -> list:
    if spacy_doc is not None:
        return [(s.start_char, s.end_char) for s in spacy_doc.sents]
    spans, pos = [], 0
    for m in re.finditer(r"(?<=[.!?])\s+|\n\s*\n", document.masked):
        spans.append((pos, m.start()))
        pos = m.end()
    spans.append((pos, len(document.masked)))
    return spans


def _sentence_of(offset: int, spans: list) -> tuple:
    for a, b in spans:
        if a <= offset < b:
            return a, b
    return offset, offset + 1


def strangers(document: Document, spacy_doc=None) -> dict:
    """The sources that carry the Discussion but were never cited before
    it.

    {"assessed": bool, "reason": str, "items": [{"label", "sentences",
     "evidence": (start, end)}], "discussion_sources": int}

    `assessed` is False, with the reason in plain words, when the check
    cannot be made reliably; `items` is then empty.
    """
    out = {"assessed": False, "reason": "", "items": [],
           "discussion_sources": 0}
    if not any(document.section_at(h.start) == "discussion"
               for h in document.headings):
        out["reason"] = "there is no Discussion section"
        return out
    reviews = review_spans(document)
    if not reviews:
        out["reason"] = ("there is no introduction or literature review "
                         "before the Discussion")
        return out
    cites = read_citations(document)
    in_review = [c for c in cites
                 if any(a <= c.start < b for a, b in reviews)
                 and document.section_at(c.start) != "discussion"]
    if len(in_review) < MIN_REVIEW_CITATIONS:
        out["reason"] = ("too few citations could be read in the "
                         "introduction or review")
        return out
    out["assessed"] = True
    sents = _sentence_spans(document, spacy_doc)
    seen_before: set = set()
    found: dict = {}            # key -> {"label", "sentences": set, "first"}
    for c in cites:
        section = document.section_at(c.start)
        if section in ("references", "appendix"):
            continue
        if section != "discussion":
            seen_before.add(c.key)
            continue
        if c.key in seen_before:
            continue
        entry = found.setdefault(c.key, {"label": c.label,
                                         "sentences": set(),
                                         "first": None})
        span = _sentence_of(c.start, sents)
        entry["sentences"].add(span)
        if entry["first"] is None:
            entry["first"] = span
    disc_keys = {c.key for c in cites
                 if document.section_at(c.start) == "discussion"}
    out["discussion_sources"] = len(disc_keys)
    items = [{"label": e["label"], "sentences": len(e["sentences"]),
              "evidence": e["first"]}
             for k, e in found.items()
             if k not in seen_before
             and len(e["sentences"]) >= MIN_DISCUSSION_SENTENCES]
    items.sort(key=lambda e: (-e["sentences"], e["evidence"][0]))
    out["items"] = items
    return out


def message(result: dict) -> str:
    """One line for the map and the brief."""
    items = result["items"]
    n = len(items)
    names = ", ".join(f"{e['label']} ({e['sentences']} sentences)"
                      for e in items[:SHOW])
    more = f", and {n - SHOW} more" if n > SHOW else ""
    return (f"{n} source{'s carry' if n != 1 else ' carries'} the Discussion "
            f"but {'were' if n != 1 else 'was'} never cited before it: "
            f"{names}{more}. Either the review should introduce "
            f"{'them' if n != 1 else 'it'}, or the Discussion has moved on "
            "to a different question.")

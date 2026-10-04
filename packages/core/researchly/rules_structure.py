"""Structural checks: figures, tables, equations and the text citing them
(S2b; owner decision P4).

They read `researchly.structure`, which only LaTeX and Word documents have:
pasted plain text gets none of these checks rather than a guess. Messages
ask a question; the author knows whether the figure is meant to be cited.
"""

from __future__ import annotations

import re

from .document import Document
from .engine import Category, Suggestion, rule
from .structure import Structure, analyse

# "Figure 3 of Smith et al." / "Table 2 in [12]": another paper's float.
_ELSEWHERE = re.compile(
    r"\s*(?:of|in|from)\s+(?:ref\b|refs?\.|\[|\(|[A-Z][A-Za-z'-]+\s+et\s+al)")


def structure_of(document: Document) -> Structure:
    """Analysed once per document and shared by every structural rule."""
    st = getattr(document, "_structure", None)
    if st is None:
        st = analyse(document)
        document._structure = st
    return st


def _anchor(document: Document, start: int, end: int,
            limit: int = 80) -> tuple[int, int]:
    """A short span to highlight: the opening words of a caption."""
    stop = min(end, start + limit)
    text = document.original
    dot = text.find(". ", start, stop)
    return start, (dot + 1 if dot > start + 8 else stop)


def _word_near(document: Document, start: int, end: int) -> tuple[int, int]:
    """A \\ref is masked markup and is never highlighted: point at the word
    before it ("Figure~\\ref{x}" -> "Figure"), else the word after."""
    m = document.masked
    if m[start:end].strip():
        return start, end
    before = re.search(r"([A-Za-z][\w.-]*)[^\w\n]*\n?[^\w\n]*$",
                       m[max(0, start - 40):start])
    if before:
        a = max(0, start - 40) + before.start(1)
        return a, a + len(before.group(1))
    after = re.match(r"\W*?([A-Za-z][\w-]*)", m[end:end + 40])
    if after:
        return end + after.start(1), end + after.end(1)
    return start, end


def _text_mentions(st: Structure):
    """Mentions in running text (not captions), resolved to their float."""
    for m in st.mentions:
        if m.in_caption or m.supplementary:
            continue
        if m.label is not None:
            f = st.float_for(m)
            if f is not None:
                yield m, [f]
            continue
        found = [f for f in st.floats
                 if f.kind == m.kind and f.number in m.numbers]
        if found:
            yield m, found


# --- X101–X104: are figures and tables cited, in order, and do the
# --- citations point at something? ------------------------------------------

@rule("X101", "float-not-cited", Category.CONVENTION,
      "A figure or table the text never cites.",
      "Every figure and table should be cited in the text, so the reader "
      "knows when to look at it and what to see there. One that is never "
      "cited is either missing its sentence in the Results or not needed. "
      "(ICMJE Recommendations: number figures and tables in the order the "
      "text first cites them.)",
      source="ICMJE")
def x101_float_not_cited(doc, document: Document):
    st = structure_of(document)
    cited = {id(f) for _, fs in _text_mentions(st) for f in fs}
    # Cited from another float's caption ("as in Table 2") still sends the
    # reader to it; only a float's own caption does not count.
    for m in st.mentions:
        if m.in_caption and not m.supplementary:
            for f in ([st.float_for(m)] if m.label is not None else
                      [f for f in st.floats
                       if f.kind == m.kind and f.number in m.numbers]):
                if f is not None and f.caption is not None and not (
                        f.caption.start <= m.start < f.caption.end):
                    cited.add(id(f))
    for f in st.floats:
        if f.number is None or f.caption is None or id(f) in cited:
            continue
        a, b = _anchor(document, f.caption.start, f.caption.end)
        yield Suggestion(
            message=f"{f.name} is never cited in the text — where should "
                    "the reader look at it?",
            start=a, end=b)


@rule("X102", "float-cited-out-of-order", Category.CONVENTION,
      "Figures or tables first cited out of numerical order.",
      "Figures and tables are numbered in the order the text first cites "
      "them, so a reader meets Figure 2 before Figure 3. When the text "
      "cites Figure 3 first, either the numbering or the order of the "
      "argument needs changing. (ICMJE Recommendations.)",
      source="ICMJE")
def x102_cited_out_of_order(doc, document: Document):
    st = structure_of(document)
    seen: set = set()
    highest: dict = {}                      # (kind, chapter) -> number
    for m, fs in _text_mentions(st):
        new = [f for f in fs if id(f) not in seen and not f.appendix]
        for f in sorted(new, key=lambda f: f.number):
            seen.add(id(f))
            group = (f.kind, f.number[:-1])      # per chapter in a thesis
            top = highest.get(group)
            if top is not None and f.number < top[0]:
                a, b = _word_near(document, m.start, m.end)
                yield Suggestion(
                    message=f"{f.name} is first cited after {top[1]} — "
                            "renumber, or cite them in order?",
                    start=a, end=b)
            elif top is None or f.number > top[0]:
                highest[group] = (f.number, f.name)


@rule("X103", "broken-cross-reference", Category.CORRECTION,
      "A cross-reference to a figure, table or label that does not exist.",
      "A \\ref to a label that is never defined prints as '??' in the PDF; "
      "a 'Figure 5' in a document with four figures sends the reader "
      "nowhere. Usually a typo in the label or a figure that was removed. "
      "(ICMJE Recommendations.)",
      source="ICMJE")
def x103_broken_reference(doc, document: Document):
    st = structure_of(document)
    numbered = {k: {f.number for f in st.floats
                    if f.kind == k and f.number is not None}
                for k in ("figure", "table")}
    for m in st.mentions:
        if m.supplementary:
            continue
        if m.label is not None:
            if st.resolve(m.label) is None:
                a, b = _word_near(document, m.start, m.end)
                yield Suggestion(
                    message=f"'{m.label}' is not defined anywhere — a typo "
                            "in the label, or a removed figure? It prints "
                            "as '??'.",
                    start=a, end=b)
            continue
        have = numbered.get(m.kind) or set()
        if not have or m.in_caption:
            continue                    # the document has none to check
        if _ELSEWHERE.match(document.masked, m.end):
            continue
        # A thesis chapter cites figures of other chapters: only judge
        # numbers whose chapter is in this document.
        chapters = {n[:-1] for n in have}
        missing = [n for n in m.numbers
                   if n not in have and n[:-1] in chapters]
        if missing:
            name = ".".join(str(x) for x in missing[0])
            yield Suggestion(
                message=f"There is no {m.kind.capitalize()} {name} in this "
                        "document — renumbered, or removed?",
                start=m.start, end=m.end)


@rule("X104", "float-before-first-citation", Category.CONVENTION,
      "A figure or table placed before the text first cites it.",
      "A reader should meet the sentence that cites a figure before the "
      "figure itself; placed earlier, it interrupts the paragraph before "
      "it with something not yet introduced. (ICMJE Recommendations.) "
      "Word documents only: LaTeX places floats itself.",
      source="ICMJE")
def x104_before_first_citation(doc, document: Document):
    if document.kind != "word":
        return
    st = structure_of(document)
    first: dict = {}
    for m, fs in _text_mentions(st):
        for f in fs:
            first.setdefault(id(f), m)
    for f in st.floats:
        m = first.get(id(f))
        if (m is not None and f.caption is not None and not f.appendix
                and m.start > f.end):
            a, b = _anchor(document, f.caption.start, f.caption.end)
            yield Suggestion(
                message=f"{f.name} comes before the text first cites it — "
                        "move it after that paragraph?",
                start=a, end=b)

"""Evidence spans: where in the text a document-level statement rests
(Codex review #3, 2026-10-15).

The reviewer's brief and the narrative map say things about the whole
document ("a causal claim", "a gap statement was detected"). Each such
statement that rests on a sentence carries that sentence's place, so every
surface can jump to it: the website outlines it in the text, Word selects
it. A statement that rests on nothing that can be placed carries no span:
it abstains rather than point somewhere plausible.

Offsets are code points into `Document.original` (as suggestion spans
are); `shapes.evidence_span` adds UTF-16 offsets and, for Word, the
paragraph location at the edge. A multi-file project (an Overleaf .zip) is
one expanded text, so its spans are offsets into that text; the surfaces
name the file and line from the document's segments, as they do for
suggestions.
"""

from __future__ import annotations

from bisect import bisect_right
from typing import Optional

# The longest quote a surface shows beside a span.
QUOTE_CHARS = 180


def quote(text: str) -> str:
    """A sentence as a surface quotes it: one line, at most QUOTE_CHARS."""
    text = " ".join(text.split())
    return text if len(text) <= QUOTE_CHARS else text[:QUOTE_CHARS - 1] + "…"


def trimmed(document, start: int, end: int) -> Optional[tuple]:
    """(start, end) without the blanks either side, judged on the masked
    text (a masked heading or markup at the edge is not the sentence);
    None when nothing readable is left."""
    m = document.masked
    start, end = max(0, start), min(len(m), end)
    while start < end and m[start].isspace():
        start += 1
    while end > start and m[end - 1].isspace():
        end -= 1
    return (start, end) if end > start else None


def span(document, start: int, end: int) -> Optional[dict]:
    """The span the surfaces receive: offsets, the quoted text and the
    line and column of its start (like a suggestion's), or None."""
    t = trimmed(document, start, end)
    if t is None:
        return None
    a, b = t
    text = quote(document.original[a:b])
    if not text:
        return None
    line, col = document.line_col(a) if document._line_starts else (0, 0)
    out = {"start": a, "end": b, "text": text, "line": line, "col": col}
    segments = getattr(document, "segments", None) or []
    if len({s.path for s in segments}) > 1:
        # A project of several files: name the file and the line in it.
        from .ingest import source_position
        path, file_line, _ = source_position(segments, document.original, a)
        out["file"], out["file_line"] = path, file_line
    return out


class Sentences:
    """The prose sentences of a document in order, as (start, end) over the
    shared parse (or a punctuation split without one), with a lookup from
    an offset to the sentence that holds it."""

    def __init__(self, document, spacy_doc=None, roles=None):
        self.document = document
        if roles is not None:
            pairs = [(r.start, r.end) for r in roles]
        elif spacy_doc is not None:
            pairs = [(s.start_char, s.end_char) for s in spacy_doc.sents
                     if s.text.strip()]
        else:
            from .discourse.argument import label_sentences
            pairs = [(r.start, r.end)
                     for r in label_sentences(document)]
        self.spans = []
        for a, b in pairs:
            t = trimmed(document, a, b)
            if t is not None:
                self.spans.append(t)
        self.starts = [a for a, _ in self.spans]

    def index_at(self, offset: int) -> Optional[int]:
        i = bisect_right(self.starts, offset) - 1
        if i < 0:
            return None
        a, b = self.spans[i]
        return i if a <= offset < max(b, a + 1) else None

    def around(self, start: int, end: Optional[int] = None) -> Optional[dict]:
        """The span of the sentence holding `start` (falling back to
        [start, end) itself when no sentence holds it)."""
        i = self.index_at(start)
        if i is not None:
            return span(self.document, *self.spans[i])
        if end is None or end <= start:
            return None
        return span(self.document, start, end)

    def first_matching(self, patterns) -> Optional[dict]:
        """The first sentence whose (masked) wording matches one of the
        regular expressions, as a span; None when none does."""
        import re
        for a, b in self.spans:
            text = self.document.masked[a:b]
            if any(re.search(rx, text, re.IGNORECASE) for rx in patterns):
                return span(self.document, a, b)
        return None

    def find(self, text: Optional[str], after: int = 0) -> Optional[dict]:
        """The sentence holding the first occurrence of `text` (a quote
        taken from the masked text) at or after `after`; None when the
        quote cannot be found again (abstain, never guess)."""
        if not text or not text.strip():
            return None
        needle = text.strip()
        at = self.document.masked.find(needle, after)
        if at < 0:
            return None
        return self.around(at, at + len(needle))

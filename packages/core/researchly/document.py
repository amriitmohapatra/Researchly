"""Markup-aware document handling.

Core idea (borrowed from LTeX+'s "annotated text" pattern, simplified):
instead of *removing* markup, we *mask* it with spaces. The masked text has
exactly the same length and character positions as the original, so any
character offset found by a rule maps 1:1 back to the source file — no offset
arithmetic, no drift.

Supported kinds: markdown / quarto (.md, .qmd, .rmd), latex (.tex), plain text.

Also performs lightweight IMRaD section detection from headings, so rules can
be section-conditioned (the defining Researchly behaviour: the same sentence
gets different advice in Methods vs Discussion).
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Section classification
# ---------------------------------------------------------------------------

_SECTION_PATTERNS: list[tuple[str, str]] = [
    (r"abstract|summary\b", "abstract"),
    (r"introduction|background", "introduction"),
    (r"method|material|model|data\b|analys[ie]s|estimation|inference|"
     r"statistic|design|setting|participants", "methods"),
    (r"result|finding", "results"),
    (r"limitation", "limitations"),
    (r"discussion", "discussion"),
    (r"conclusion", "conclusion"),
    (r"appendix|supplement", "appendix"),
]


def classify_heading(text: str) -> str:
    low = text.lower()
    for pat, name in _SECTION_PATTERNS:
        if re.search(pat, low):
            return name
    return "other"


@dataclass
class Heading:
    start: int
    text: str
    section: str
    # Where the heading's own text ends. None means "end of its line", which
    # is right for Markdown and Word; a LaTeX `\paragraph{Title.} Text...`
    # shares its line with prose that must not be masked with it.
    end: int | None = None


@dataclass
class Segment:
    """`Document.original[start:end]` came from `path` at `source_start`
    (docs/s2-design.md §4). A single-file document has one segment."""
    path: str
    start: int
    end: int
    source_start: int = 0


@dataclass
class StructureItem:
    """A figure, table, equation, caption or citation (kept for S2b)."""
    kind: str            # figure | table | equation | caption | citation
    start: int
    end: int
    label: str | None = None


@dataclass
class Document:
    original: str
    masked: str
    kind: str
    headings: list[Heading] = field(default_factory=list)
    path: str = "<text>"
    # For documents built from Word paragraphs: char offset where each
    # paragraph starts in `original`, so suggestions can be mapped back to
    # (paragraph index, in-paragraph position) for Office JS.
    para_offsets: list[int] = field(default_factory=list)
    # (start, end) spans that are table cells, not prose. Metrics exclude
    # them: a table of parameter values is not a set of long sentences.
    table_spans: list[tuple[int, int]] = field(default_factory=list)
    # Set by the file adapters (researchly.ingest); empty for pasted text.
    segments: list[Segment] = field(default_factory=list)
    structure: list[StructureItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    _line_starts: list[int] = field(default_factory=list, repr=False)

    # -- construction -------------------------------------------------------

    @classmethod
    def from_path(cls, path: str | Path) -> "Document":
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix in {".docx", ".zip"}:
            # Binary containers go through the file adapters, so the CLI
            # reads them exactly as the hosted engine does.
            from .ingest import load_bytes
            doc = load_bytes(path.name, path.read_bytes())
            doc.path = str(path)
            return doc
        text = path.read_text(encoding="utf-8")
        if suffix in {".md", ".qmd", ".rmd", ".markdown"}:
            kind = "markdown"
        elif suffix in {".tex", ".ltx"}:
            kind = "latex"
        else:
            kind = "plain"
        doc = cls.from_text(text, kind)
        doc.path = str(path)
        return doc

    @classmethod
    def from_text(cls, text: str, kind: str = "plain", *,
                  locate=None) -> "Document":
        """`locate(offset) -> str` words a position in a warning; the
        Overleaf adapter passes one that names the source file."""
        structure: list[StructureItem] = []
        warnings: list[str] = []
        if kind == "markdown":
            masked, headings = _mask_markdown(text)
        elif kind == "latex":
            # Parsed with pylatexenc; falls back to `_mask_latex` (with a
            # warning) when the source cannot be parsed. Imported here
            # because the ingest package imports this module.
            from .ingest.latex import mask_latex
            res = mask_latex(text, locate)
            masked, headings = res.masked, res.headings
            structure, warnings = res.structure, res.warnings
        else:
            masked, headings = text, _detect_plain_headings(text)
        # Mask heading TEXT as well (after recording it): headings are not
        # sentences, and without terminal punctuation the parser merges them
        # into the following paragraph's first sentence, corrupting
        # subject/verb analysis ("Results Selected variables are shown...").
        chars = list(masked)
        for h in headings:
            end = h.end if h.end is not None else masked.find("\n", h.start)
            end = end if end != -1 else len(masked)
            _mask_spans(chars, [(h.start, end)])
        masked = "".join(chars)
        doc = cls(original=text, masked=masked, kind=kind, headings=headings,
                  structure=structure, warnings=warnings)
        doc._line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
        return doc

    @classmethod
    def from_word(cls, paragraphs: list[dict]) -> "Document":
        """Build a Document from Office JS Word paragraphs.

        Each item: {"text": str, "style": str, "kind": str} — style is the
        Word paragraph style (e.g. "Heading1", "Heading 2", "Title",
        "Normal"). Word headings are detected from STYLE (far more reliable
        than keywords), classified into IMRaD sections, and masked like all
        other headings. Falls back to plain-text keyword heading detection
        for authors who type headings without applying a style.

        `kind` is "body" (default) or "table". Table cells arrive through
        the same paragraph collection as prose; counted as prose they skewed
        sentence-length and passive-voice metrics, and a cell reading
        "Methods" could re-section the rest of the document. They are
        recorded in `table_spans` so metrics can exclude them.
        """
        texts = [p.get("text") or "" for p in paragraphs]
        combined = "\n\n".join(texts)
        doc = cls.from_text(combined, kind="plain")

        offsets: list[int] = []
        pos = 0
        for t in texts:
            offsets.append(pos)
            pos += len(t) + 2
        doc.para_offsets = offsets

        chars = list(doc.masked)
        style_headings: list[Heading] = []
        table_spans: list[tuple[int, int]] = []
        for i, p in enumerate(paragraphs):
            style = (p.get("style") or "").lower().replace(" ", "")
            title = texts[i].strip()
            if p.get("kind") == "table" and title:
                table_spans.append((offsets[i], offsets[i] + len(texts[i])))
                continue          # never a heading, never prose
            if not title:
                continue
            if "heading" in style or style == "title":
                style_headings.append(
                    Heading(offsets[i], title, classify_heading(title)))
                _mask_spans(chars, [(offsets[i], offsets[i] + len(texts[i]))])
        doc.table_spans = table_spans
        if table_spans:
            # from_text() already ran keyword heading detection over the
            # combined string, before table cells were known. A cell reading
            # "Methods" would otherwise re-section everything after it.
            doc.headings = [h for h in doc.headings
                            if not doc.in_table(h.start)]

        if style_headings:
            merged = {h.start: h for h in doc.headings}
            merged.update({h.start: h for h in style_headings})
            doc.headings = sorted(merged.values(), key=lambda h: h.start)
            doc.masked = "".join(chars)
        doc.kind = "word"
        return doc

    def in_table(self, offset: int) -> bool:
        """Is this offset inside a Word table cell?"""
        return any(a <= offset < b for a, b in self.table_spans)

    def locate(self, offset: int) -> tuple[int, int]:
        """(paragraph index, in-paragraph offset) for a char offset."""
        if not self.para_offsets:
            return 0, offset
        idx = bisect_right(self.para_offsets, offset) - 1
        return idx, offset - self.para_offsets[idx]

    # -- position helpers ---------------------------------------------------

    def line_col(self, offset: int) -> tuple[int, int]:
        """1-based (line, col) for a character offset in the original text."""
        line_idx = bisect_right(self._line_starts, offset) - 1
        return line_idx + 1, offset - self._line_starts[line_idx] + 1

    def masked_content(self, start: int, end: int) -> bool:
        """True if [start, end) covers masked material inside the running
        text: something that was in the source (maths, a citation, code) and
        is now blanked. Headings are masked too, but they are not part of a
        sentence, so they never count."""
        o, m = self.original, self.masked
        for i in range(max(0, start), min(end, len(m))):
            if m[i] == " " and not o[i].isspace() and not self._in_heading(i):
                return True
        return False

    def _in_heading(self, i: int) -> bool:
        for h in self.headings:
            if h.start <= i:
                end = h.end if h.end is not None else self.original.find("\n", h.start)
                if end == -1 or i < end:
                    return True
        return False

    def touches_masked(self, start: int, end: int) -> bool:
        """True if masked material lies inside [start, end) or in the spaces
        either side of it (across a wrapped line, not a paragraph break).

        Masking blanks inline maths, citations and code to spaces, so the
        words around them look adjacent: "and $C(0)$ and" reads as a doubled
        "and and", "An $\\exp(1)$ prior" as "An prior". A finding whose
        evidence crosses a blank is about the masking, not the writing.
        """
        m = self.masked
        a = self._blank_run(start, -1)
        b = self._blank_run(end, +1)
        return self.masked_content(a, b)

    def _blank_run(self, i: int, step: int) -> int:
        """Walk from i over blanks in the masked text, crossing at most one
        line break (a sentence wrapped in the source) but never a blank line
        (a paragraph break)."""
        m, newlines = self.masked, 0
        while True:
            j = i if step > 0 else i - 1
            if j < 0 or j >= len(m) or m[j] not in " \t\n":
                return i
            if m[j] == "\n":
                newlines += 1
                if newlines > 1:
                    return i
            i += step

    def section_at(self, offset: int) -> str:
        """IMRaD section governing this offset ('unknown' if no headings)."""
        if not self.headings:
            return "unknown"
        current = "front"
        for h in self.headings:
            if h.start > offset:
                break
            current = h.section
        return current


# ---------------------------------------------------------------------------
# Masking machinery
# ---------------------------------------------------------------------------

def _mask_spans(chars: list[str], spans: list[tuple[int, int]]) -> None:
    """Overwrite [start, end) spans with spaces, preserving newlines."""
    for start, end in spans:
        for i in range(start, min(end, len(chars))):
            if chars[i] != "\n":
                chars[i] = " "


def _find_all(pattern: str, text: str, flags: int = 0) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(pattern, text, flags)]


# -- Markdown / Quarto ------------------------------------------------------

def _mask_markdown(text: str) -> tuple[str, list[Heading]]:
    chars = list(text)
    spans: list[tuple[int, int]] = []

    # YAML front matter at very top
    m = re.match(r"\A---\n.*?\n(---|\.\.\.)\s*\n", text, re.DOTALL)
    if m:
        spans.append((0, m.end()))

    # Fenced code blocks (``` or ~~~), including Quarto chunks
    spans += _find_all(r"^(```|~~~).*?^\1[^\n]*$", text, re.DOTALL | re.MULTILINE)
    # Inline code
    spans += _find_all(r"`[^`\n]+`", text)
    # Display + inline math
    spans += _find_all(r"\$\$.*?\$\$", text, re.DOTALL)
    spans += _find_all(r"(?<![\\$])\$[^$\n]+\$", text)
    # Bracketed citation groups [ ... @key ... ] and bare @citekeys
    spans += _find_all(r"\[[^\]\n]*@[^\]\n]*\]", text)
    spans += _find_all(r"(?<![\w.])@[\w:.\-]+", text)
    # Images entirely; links keep their text
    spans += _find_all(r"!\[[^\]]*\]\([^)]*\)", text)
    for m2 in re.finditer(r"\[([^\]\n]+)\]\(([^)]*)\)", text):
        spans.append((m2.start(), m2.start(1)))          # '['
        spans.append((m2.end(1), m2.end()))              # '](url)'
    # HTML tags and comments
    spans += _find_all(r"<!--.*?-->", text, re.DOTALL)
    spans += _find_all(r"</?[a-zA-Z][^>\n]*>", text)
    # Cross-reference / div fences (Quarto ::: blocks) — markers only
    spans += _find_all(r"^:{3,}.*$", text, re.MULTILINE)
    # Emphasis markers (keep the emphasised words)
    spans += _find_all(r"\*{1,3}", text)
    spans += _find_all(r"(?<![\w])_{1,3}(?=\w)|(?<=\w)_{1,3}(?![\w])", text)

    _mask_spans(chars, spans)

    # Headings: record, then mask the leading hashes (keep the text so spaCy
    # still sees it, but rules can skip heading lines via section metadata).
    headings: list[Heading] = []
    masked_so_far = "".join(chars)
    for m3 in re.finditer(r"^(#{1,6})[ \t]+([^\n{]+)", masked_so_far, re.MULTILINE):
        title = m3.group(2).strip()
        if title:
            headings.append(Heading(m3.start(), title, classify_heading(title)))
        _mask_spans(chars, [(m3.start(1), m3.end(1))])

    return "".join(chars), headings


# -- LaTeX ------------------------------------------------------------------

_TEX_MASK_ENVS = (
    "equation", "align", "alignat", "gather", "eqnarray", "multline",
    "displaymath", "math", "verbatim", "lstlisting", "minted", "tikzpicture",
    "tabular", "array",
)
_TEX_KEEP_CONTENT = (
    "emph", "textbf", "textit", "texttt", "textsc", "underline", "mbox",
    "caption", "title", "textnormal", "textrm",
)
_TEX_MASK_WHOLE = (
    "cite", "citep", "citet", "citealt", "citealp", "parencite", "textcite",
    "ref", "eqref", "autoref", "cref", "Cref", "vref", "label", "url",
    "includegraphics", "input", "include", "bibliography", "bibliographystyle",
    "usepackage", "documentclass", "footnote", "footnotemark", "href",
)


def _mask_latex(text: str) -> tuple[str, list[Heading]]:
    chars = list(text)
    spans: list[tuple[int, int]] = []

    # Comments (unescaped % to end of line)
    spans += _find_all(r"(?<!\\)%[^\n]*", text)
    # Whole environments that are not prose
    env_alt = "|".join(_TEX_MASK_ENVS)
    spans += _find_all(
        rf"\\begin\{{({env_alt})\*?\}}.*?\\end\{{\1\*?\}}", text, re.DOTALL)
    # Math
    spans += _find_all(r"\$\$.*?\$\$", text, re.DOTALL)
    spans += _find_all(r"(?<!\\)\$[^$]+\$", text, re.DOTALL)
    spans += _find_all(r"\\\[.*?\\\]", text, re.DOTALL)
    spans += _find_all(r"\\\(.*?\\\)", text, re.DOTALL)
    # Commands whose whole call should vanish (incl. optional args)
    whole_alt = "|".join(_TEX_MASK_WHOLE)
    spans += _find_all(
        rf"\\({whole_alt})\*?(\[[^\]]*\])*(\{{[^{{}}]*\}})+", text)

    # Sectioning: record heading, keep title text, mask the command wrapper
    headings: list[Heading] = []
    for m in re.finditer(
            r"\\(section|subsection|subsubsection|chapter|paragraph)\*?"
            r"\{([^{}]+)\}", text):
        title = m.group(2).strip()
        headings.append(Heading(m.start(), title, classify_heading(title)))
        spans.append((m.start(), m.start(2)))
        spans.append((m.end(2), m.end()))

    # Commands that keep their content: mask "\cmd{" and the matching "}"
    keep_alt = "|".join(_TEX_KEEP_CONTENT)
    for m in re.finditer(rf"\\({keep_alt})\*?\{{([^{{}}]*)\}}", text):
        spans.append((m.start(), m.start(2)))
        spans.append((m.end(2), m.end()))

    # \begin{...} / \end{...} of prose environments (abstract, document, ...)
    spans += _find_all(r"\\(begin|end)\{[^{}]*\}(\[[^\]]*\])?", text)
    # Any remaining bare command (\item, \noindent, \alpha, \\ ...)
    spans += _find_all(r"\\[a-zA-Z@]+\*?", text)
    spans += _find_all(r"\\[\\,;:!]", text)
    # Leftover braces and tex-special characters
    spans += _find_all(r"[{}~^]", text)

    _mask_spans(chars, spans)

    # LaTeX abstract environment counts as a section
    m_abs = re.search(r"\\begin\{abstract\}", text)
    if m_abs:
        headings.append(Heading(m_abs.start(), "Abstract", "abstract"))
        headings.sort(key=lambda h: h.start)

    return "".join(chars), headings


# -- Plain text -------------------------------------------------------------

def _detect_plain_headings(text: str) -> list[Heading]:
    """Short lines that look like section titles (no trailing period)."""
    headings = []
    for m in re.finditer(r"^([A-Z][A-Za-z &\-]{2,60})\s*$", text, re.MULTILINE):
        title = m.group(1).strip()
        section = classify_heading(title)
        if section != "other":
            headings.append(Heading(m.start(), title, section))
    return headings

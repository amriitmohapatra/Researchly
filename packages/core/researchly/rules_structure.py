"""Structural checks: figures, tables, equations and the text citing them
(S2b; owner decision P4).

They read `researchly.structure`, which only LaTeX and Word documents have:
pasted plain text gets none of these checks rather than a guess. Messages
ask a question; the author knows whether the figure is meant to be cited.
"""

from __future__ import annotations

import re

from . import tables
from .document import _RELATION, Document
from .engine import Category, Suggestion, rule
from .structure import Structure, analyse, number_text

# "Figure 3 of Smith et al." / "Table 2 in [12]": another paper's float.
_ELSEWHERE = re.compile(
    r"\s*(?:of|in|from)\s+(?:ref\b|refs?\.|\[|\(|[A-Z][A-Za-z'-]+\s+et\s+al)")


_CAPTION_WORD = {"figure": r"Fig(?:ure)?\.?", "table": "Table"}


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
      'Every figure and table should be cited in the text, so the reader '
      'knows when to look at it and what to see there. One that is never '
      'cited is either missing its sentence in the Results or not needed.',
      plain=('The text never mentions this figure or table. Readers need a '
             'sentence that tells them when to look at it and what to see. If no '
             'sentence needs it, it may not be needed.'),
      source="ICMJE",
      scope="document")
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
      'Figures and tables are numbered in the order the text first cites '
      'them, so a reader meets Figure 2 before Figure 3. When the text '
      'cites Figure 3 first, either the numbering or the order of the '
      'argument needs changing.',
      plain=('Figures and tables should be numbered in the order you first '
             'mention them. Here a later one is mentioned before an earlier one. '
             'Renumber them, or change the order of the text.'),
      source="ICMJE",
      scope="document")
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
      'nowhere. Usually a typo in the label or a figure that was removed.',
      plain=('The text refers to a figure, table or label that does not exist. '
             "In LaTeX this prints as '??'. It is usually a typo in the label, "
             'or a figure that was removed.'),
      source="ICMJE",
      scope="document")
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
        # A caption a converter ran into a paragraph ("... linear. Figure
        # C.2: Scatterplot of ...") was not found as a float, but the
        # figure is there (P33).
        missing = [n for n in missing if not re.search(
            rf"\b{_CAPTION_WORD[m.kind]}\s+{re.escape(number_text(n))}"
            r"\s*:\s*\S", document.original)]
        if missing:
            name = number_text(missing[0])
            yield Suggestion(
                message=f"There is no {m.kind.capitalize()} {name} in this "
                        "document — renumbered, or removed?",
                start=m.start, end=m.end)


@rule("X104", "float-before-first-citation", Category.CONVENTION,
      "A figure or table placed before the text first cites it.",
      'A reader should meet the sentence that cites a figure before the '
      'figure itself; placed earlier, it interrupts the paragraph before '
      'it with something not yet introduced. Word documents only: LaTeX '
      'places floats itself.',
      plain=('This figure or table appears before the sentence that first '
             'mentions it. Move it after that paragraph, so readers meet the '
             'explanation before the picture.'),
      source="ICMJE",
      scope="document")
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
        # Only a caption made with Word's caption style: a typed one is a
        # guess, and in a supplement every table precedes its sentence
        # (33 such flags on PMC supplements, P33).
        if (m is not None and f.caption is not None and not f.appendix
                and f.caption.label != "typed" and m.start > f.end):
            a, b = _anchor(document, f.caption.start, f.caption.end)
            yield Suggestion(
                message=f"{f.name} comes before the text first cites it — "
                        "move it after that paragraph?",
                start=a, end=b)


# --- X202: can the caption be read on its own? -----------------------------------------

def _caption_body(document: Document, cap) -> tuple[int, str]:
    """Where a caption's own words start, and the words: without
    `\\caption{` (masked) or a Word caption's "Figure 2." prefix."""
    m = document.masked
    a = cap.start
    while a < cap.end and m[a].isspace():
        a += 1
    prefix = _WORD_PREFIX.match(m, a, cap.end)
    if prefix:
        a = prefix.end()
    return a, m[a:cap.end]


_WORD_PREFIX = re.compile(
    r"(?:Fig(?:ure)?\.?|Table)\s*[SA]?\d+(?:\.\d+)?[a-z]?\s*[.:|\-–—]?\s*",
    re.IGNORECASE)
_WORDS = re.compile(r"[A-Za-z][A-Za-z'-]*")


@rule("X202", "caption-too-short", Category.IMPROVEMENT,
      "A figure caption too short to be read on its own.",
      'Readers look at figures and tables before they read the text, and '
      "many read nothing else. A caption should state the figure's point "
      'and define what it shows, so the figure can be read unaided; a '
      'label of two or three words cannot.',
      plain=('This figure caption is only a few words. Many readers look at the '
             'figures first, so the caption should say what the figure shows and '
             'what each part means, without needing the main text.'),
      source="§9.7",
      scope="document")
def x202_caption_too_short(doc, document: Document):
    st = structure_of(document)
    for f in st.floats:
        # A table takes a short title (ICMJE: "a short or an abbreviated
        # heading"); only a figure's caption must stand on its own. On 140
        # published articles nearly every X202 was a table title (P33).
        if f.caption is None or f.number is None or f.kind != "figure":
            continue
        a, body = _caption_body(document, f.caption)
        n = len(_WORDS.findall(body))
        if 0 < n < 5:
            yield Suggestion(
                message=f"The caption of {f.name} has {n} word"
                        f"{'s' if n != 1 else ''} — what should the reader "
                        "see in it, and what does each element show?",
                start=a, end=a + len(body.rstrip()))


# --- X301: is every numbered equation referred to? ----------------------------------

_NUMBERED_ENV = re.compile(
    r"\\begin\{(equation|align|alignat|gather|multline|eqnarray|flalign|"
    r"dmath)\}")


@rule("X301", "equation-not-referenced", Category.PREFERENCE,
      "A numbered equation the text never refers to.",
      'Introduce an equation, display it, then interpret it. A numbered '
      'equation the text never refers back to is often one that floats in '
      'unannounced or is never interpreted; if so, remove the number '
      '(equation*).',
      plain=('This equation has a number but the text never refers to it. '
             'Numbers are for equations you refer back to. Either mention it in '
             'the text, or remove the number.'),
      source="§9.2",
      scope="document")
def x301_equation_not_referenced(doc, document: Document):
    if document.kind != "latex":
        return
    st = structure_of(document)
    src = document.original
    referred = {st.resolve(m.label) for m in st.mentions if m.label}
    written = _written_equation_numbers(document.masked)
    chapters = sorted(h.start for h in document.headings if h.level == 0)
    counter: dict = {}
    for it in document.structure:
        if it.kind != "equation":
            continue
        env = _NUMBERED_ENV.match(src, it.start)
        if not env:
            continue
        body = src[it.start:it.end]
        # The numbers LaTeX gives it, to match "Eq. (3)" typed by hand (P33).
        chapter = sum(1 for c in chapters if c < it.start)
        first = counter.get(chapter, 0) + 1
        counter[chapter] = first - 1 + _numbers_in(env.group(1), body)
        mine = {str(k) for k in range(first, counter[chapter] + 1)}
        if chapters:
            mine = {f"{chapter}.{k}" for k in mine} | mine
        if mine & written:
            continue
        labels = {k.strip() for k in re.findall(r"\\label\s*\{([^{}]+)\}",
                                                body)}
        if labels & referred:
            continue
        if not labels and re.search(r"\\(?:nonumber|notag)\b", body):
            continue
        a, b = _word_near(document, it.start, it.start)
        yield Suggestion(
            message="This equation is numbered but the text never refers "
                    "to it — is it introduced and interpreted? If so, it "
                    "can go unnumbered.",
            start=a, end=b)


_EQ_WRITTEN = re.compile(
    r"\b(?:Eqs?\.?|Eqns?\.?|Equations?)\s*~?((?:\(?\s*\d+(?:\.\d+)?[a-z]?\s*\)?"
    r"(?:\s*(?:,|and|&|to|[-\u2013\u2014])\s*)?)+)", re.IGNORECASE)


def _written_equation_numbers(text: str) -> set[str]:
    """Numbers typed after "Eq."/"Equation(s)": "Eqs. (2)-(4)" -> 2, 3, 4."""
    out: set[str] = set()
    for m in _EQ_WRITTEN.finditer(text):
        listing = m.group(1)
        nums = re.findall(r"\d+(?:\.\d+)?", listing)
        out.update(nums)
        for a, b in re.findall(r"(\d+)\)?\s*(?:to|[-\u2013\u2014])\s*\(?(\d+)\b",
                               listing):
            if 0 < int(b) - int(a) < 50:
                out.update(str(k) for k in range(int(a), int(b) + 1))
    return out


def _numbers_in(env: str, body: str) -> int:
    """How many numbers a numbered environment prints (rows of an align,
    less any \\nonumber / \\notag)."""
    if env in ("equation", "multline", "dmath"):
        return 1
    rows = len(re.findall(r"\\\\(?!\s*\\end)", body)) + 1
    return max(0, rows - len(re.findall(r"\\(?:nonumber|notag)\b", body)))


# --- X302: is the equation part of a sentence? -----------------------------------------

# "e.g.", "i.e.", "Eq.", "Fig.", an initial: a full stop that is not the end
# of a sentence.
_ABBREV_STOP = re.compile(
    r"(?:\b(?:e\.g|i\.e|cf|vs|etc|et al|Eq|Eqs|Fig|Figs|Ref|Refs|No|resp|"
    r"approx|ca|viz)\.|\b[A-Z]\.)$")


@rule("X302", "equation-not-in-sentence", Category.CONVENTION,
      "A displayed equation that is not part of a sentence.",
      "An equation is a clause of the sentence around it: the words before "
      "it lead in ('the force of infection is') and the words after it "
      "interpret it ('where beta is'). When the sentence before ends with a "
      "full stop, the equation floats in on its own, unannounced, and the "
      "reader has to guess what it is for. Introduce it, display it, then "
      "interpret it.",
      plain=("The sentence before this equation ends with a full stop, so "
             "the equation stands alone. Make it part of a sentence: lead "
             "in with words like 'is given by' or 'as', and follow it with "
             "what it means, such as 'where N is the population'."),
      source="§9.2")
def x302_equation_not_in_sentence(doc, document: Document):
    if document.kind == "latex":
        starts = [it.start for it in document.structure
                  if it.kind == "equation"]
    elif document.kind == "word":
        starts = list(_word_display_equations(document))
    else:
        return
    masked = document.masked
    for start in starts:
        before = masked[:start].rstrip()
        if not before:
            continue                       # nothing readable before it
        if before[-1] != "." or _ABBREV_STOP.search(before[-14:]):
            continue
        # "...} ." from a masked \cite or \ref is still the sentence's end.
        a, b = _word_near(document, start, start)
        yield Suggestion(
            message="This equation starts after a full stop — make it part "
                    "of a sentence (lead in, display, then interpret).",
            start=a, end=b)


# A displayed equation's paragraph in Word, once the equation object is
# masked: nothing, or its number ("\t(3)", "(3a)").
_EQ_NUMBER_ONLY = re.compile(r"^\s*(?:\(?\d{1,3}[a-z]?\)?)?\s*$")
# Function names that are maths, not words, in a typed equation.
_MATH_WORDS = frozenset(
    "log ln exp sin cos tan sinh cosh tanh max min arg lim sup inf det "
    "diag var cov dt dx dy ds du".split())


def _equation_paragraph(text: str) -> bool:
    """A Word paragraph that IS an equation written as text: a relation
    sign and no ordinary word. The add-in reads paragraph text only, so an
    equation object arrives in its linear form ("R0 = βS/N"); a PDF
    conversion flattens one the same way."""
    text = text.strip()
    if not text or len(text) > 240 or not _RELATION.search(text):
        return False
    return not any(w.lower() not in _MATH_WORDS
                   for w in re.findall(r"[A-Za-z]{2,}", text))


def _word_display_equations(document: Document):
    """Start offsets of the paragraphs that are a displayed equation: an
    equation object on its own (an uploaded .docx, where the reader masks
    it), or a paragraph of maths written as text (the add-in). An equation
    inside a sentence's paragraph is inline and never judged here."""
    offs = document.para_offsets
    objects = [it.start for it in document.structure if it.kind == "equation"]
    for i, off in enumerate(offs):
        end = offs[i + 1] - 2 if i + 1 < len(offs) else len(document.original)
        text = document.original[off:end]
        if not text.strip() or document.in_table(off):
            continue
        if any(off <= s < end for s in objects):
            if _EQ_NUMBER_ONLY.match(document.masked[off:end]):
                yield off
        elif _equation_paragraph(text):
            yield off


# --- X401: does the number quoted from a table appear in it? ------------------------
#
# Where the sentence names a row or a column of the table ("the incidence
# in the 18–29 age group was 4.1"), the number nearest that name must be
# in that row and column (Codex review #7). Everything else in the
# sentence, and every sentence whose row or column cannot be found with
# confidence, is looked for anywhere in the table, as before.

_VALUE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?![.\d])(\s*\\?%)?")


def _values(text: str) -> list[tuple[str, float, int]]:
    """(as written, value, decimals) for decimals and percentages."""
    out = []
    for m in _VALUE.finditer(text):
        whole, frac, pct = m.group(1), m.group(2) or "", m.group(3)
        if not frac and not pct:
            continue                 # counts, years, ids: too often derived
        v = float(whole.replace(",", "") + frac)
        out.append((m.group(0).strip(), v, len(frac) - 1 if frac else 0))
    return out


def _in_table(value: float, decimals: int, table_text: str) -> bool:
    for _, v, d in _values(table_text) + [
            (None, float(x), 0) for x in re.findall(r"(?<![\w.])\d+(?![\d.])",
                                                    table_text)]:
        if abs(v - value) < 1e-9:
            return True
        # The text may round what the table reports: 0.4321 -> 0.43.
        if d > decimals and abs(round(v, decimals) - value) < 1e-9:
            return True
    return False


def _table_model(document: Document, t) -> "tables.Table | None":
    """The table as rows and columns, read once per document; None when
    it has no grid this engine can read (the add-in's Word cells, a
    \\captionof table, two tabulars in one float)."""
    cache = document.__dict__.setdefault("_x401_tables", {})
    key = (t.start, t.end)
    if key not in cache:
        try:
            cache[key] = _read_table(document, t)
        except Exception:            # an unreadable table: whole-table check
            cache[key] = None
    return cache[key]


def _read_table(document: Document, t):
    if document.kind == "latex":
        grid = tables.latex_grid(document.original[t.start:t.end], t.start)
    elif document.kind == "word":
        cells = [c for c in document.table_cells if t.start <= c[0] < t.end]
        spans = [s for s in document.table_spans if t.start <= s[0] < t.end]
        # Every cell must know its place, or the grid has holes.
        if not cells or len(cells) != len(spans):
            return None
        grid = tables.word_grid([c + (document.original[c[0]:c[1]],)
                                 for c in cells])
    else:
        return None
    return tables.read(grid) if grid is not None else None


# "Table 2" names no row: blanked before the sentence is matched.
_FLOAT_NAME = re.compile(
    r"\b(?:Tables?|Tab\.|Fig(?:ure)?s?\.?)~?\s*(?:[A-Z]\.?)?\d+[a-z]?")
# A comparison, a derived number or a paired list: the number next to a
# row's name may belong to another row, so no cell is assumed.
_CONTRAST = re.compile(
    r"\b(?:than|unlike|compared|comparison|whereas|while|versus|vs|"
    r"relative|against|except|respectively|between|differ\w*|ratio|"
    r"times|fold|increase[sd]?|decrease[sd]?|reduction|reduced|change[sd]?|"
    r"rose|fell|risen|fallen|higher|lower)\b", re.IGNORECASE)
_BIND_DISTANCE = 60


def _nearest(found: list, spans: list, text: str):
    """The quoted number closest to where the sentence names the row (or
    column): only that one is held to the cell. None on a tie or when the
    closest is far away or across a semicolon."""
    best = []
    for item in found:
        m = item[0]
        d = min(m.start() - b if m.start() >= b else
                a - m.end() if m.end() <= a else 0 for a, b in spans)
        lo = min(m.start(), min(a for a, _ in spans))
        hi = max(m.end(), max(b for _, b in spans))
        if ";" in text[lo:hi] and d > 0:
            continue
        best.append((d, item))
    best.sort(key=lambda x: x[0])
    if not best or best[0][0] > _BIND_DISTANCE:
        return None
    if len(best) > 1 and best[1][0] == best[0][0]:
        return None
    return best[0][1]


_CLAUSE_BREAK = re.compile(
    r"[;:,()]|\b(?:and|but|or|where|which|while|whereas|with|who|whom)\b",
    re.IGNORECASE)


def _attached(text: str, spans: list, m) -> bool:
    """Does a column's name belong to this number: "the incidence was
    4.1", not "incidence was highest in the north, where 45.2% ..."? Only
    then does the number have to be in that column."""
    for a, b in spans:
        lo, hi = (b, m.start()) if b <= m.start() else (m.end(), a)
        if lo <= hi and not _CLAUSE_BREAK.search(text, lo, hi):
            return True
    return False


def _quote(s: str, limit: int = 40) -> str:
    s = " ".join(s.split())
    return "'" + (s if len(s) <= limit else s[:limit - 1].rstrip() + "…") + "'"


def _place(t, model, rows, cols) -> str:
    out = t.name
    if rows is not None:
        if len(rows.cover) == 1:
            label = model.row_name[next(iter(rows.cover))]
        else:
            label = " / ".join(lab.text for lab in rows.labels)
        out += f", row {_quote(label)}"
    if cols is not None:
        if len(cols.cover) == 1:
            label = model.col_name[next(iter(cols.cover))]
        else:
            label = " / ".join(lab.text for lab in cols.labels)
        out += f", column {_quote(label)}"
    return out


def _listing(nums: list) -> str:
    shown = []
    for n in nums:
        if n.written not in shown:
            shown.append(n.written)
    if len(shown) <= 3:
        return (shown[0] if len(shown) == 1 else
                ", ".join(shown[:-1]) + " and " + shown[-1])
    return ", ".join(shown[:3]) + f" and {len(shown) - 3} more"


def _decimal_places(d: int) -> str:
    return "a whole number" if d == 0 else (
        "1 decimal place" if d == 1 else f"{d} decimal places")


def _judge(t, model, rows, cols, written: str, text: str, end: int):
    """("pass" | "flag" | "abstain", evidence, compared) for the number the
    sentence gives for a named row or column. `compared` is (row, col,
    number) when the named row and column come down to one cell holding
    numbers, else None."""
    quoted = tables.numbers(written)[0]
    row_set = sorted(rows.cover) if rows else model.data_rows
    col_set = sorted(cols.cover) if cols else model.value_cols
    expected = model.values(row_set, col_set)
    # The named row or column must hold numbers of the kind quoted, or the
    # sentence did not mean it ("in most cases" is not the Cases column).
    if quoted.decimals > 0:
        if not any(n.decimals > 0 for _, _, n in expected):
            return "abstain", "", None
    elif not any(n.percent or "%" in model.unit_text(r, c)
                 for r, c, n in expected):
        return "abstain", "", None
    place = _place(t, model, rows, cols)
    main = []                     # each expected cell's first number
    seen = set()
    for r, c, n in expected:
        if (r, c) not in seen:
            seen.add((r, c))
            main.append((r, c, n))
    one = len(main) == 1
    hits = [(r, c, n) for r, c, n in expected if tables.rounds_to(n, quoted)]
    after = text[end:end + 48]
    m = re.match(r"\s*(?:[A-Za-z-]+\s+){0,3}?(?:per\b|/)\s*[\d ,]+", after)
    text_base = tables.per_base(m.group(0)) if m else None
    if hits:
        conflicts = []
        for r, c, n in hits:
            unit = model.unit_text(r, c)
            base = tables.per_base(unit)
            percent_cell = n.percent or "%" in unit
            if text_base and base and text_base != base:
                conflicts.append(
                    f"{place} holds {n.written} per {base:,}, but the text "
                    f"gives {written} per {text_base:,} — check the units.")
            elif quoted.percent and base and not percent_cell:
                conflicts.append(
                    f"{place} holds {n.written} per {base:,}, but the text "
                    f"gives {written} — a rate, not a percentage?")
            else:
                how = ("" if n.value == quoted.value else
                       ", which matches when rounded to "
                       + _decimal_places(quoted.decimals))
                return "pass", (f"{place}: {n.written} — the text says "
                                f"{written}{how}"), (r, c, n) if one else None
        r, c, n = hits[0]
        return "flag", conflicts[0], (r, c, n) if one else None
    # Not in the named cell. A proportion is not a percentage.
    for r, c, n in main:
        percent_cell = n.percent or "%" in model.unit_text(r, c)
        if quoted.percent and not percent_cell and tables.rounds_to(
                tables.Number(n.written, n.value * 100, max(0, n.decimals - 2),
                              True), quoted):
            return "flag", (f"{place} holds {n.written}, a proportion; the "
                            f"text gives {written}, a percentage — use one "
                            "form so they match."), (r, c, n) if one else None
        if not quoted.percent and percent_cell and tables.rounds_to(
                tables.Number(n.written, n.value / 100, n.decimals + 2,
                              False), quoted):
            return "flag", (f"{place} holds {n.written}, a percentage; the "
                            f"text gives {written}, a proportion — use one "
                            "form so they match."), (r, c, n) if one else None
    holds = _listing([n for _, _, n in main])
    if len(main) == 1 and main[0][2].decimals > quoted.decimals:
        holds += (f" ({tables.rounded(main[0][2], quoted.decimals)} when "
                  f"rounded to {_decimal_places(quoted.decimals)})")
    compared = main[0] if one else None
    elsewhere = [(r, c) for r, c, n in model.values(model.data_rows,
                                                     model.value_cols)
                 if tables.rounds_to(n, quoted)]
    if elsewhere:
        r, c = elsewhere[0]
        where, why = [], "cell"
        if r not in row_set:
            where.append(f"row {_quote(model.row_name[r])}")
            groups = {model.group_of.get(x, "") for x in row_set}
            why = ("group" if model.group_of.get(r, "") not in groups
                   else "row")
        if c not in col_set:
            where.append(f"column {_quote(model.col_name[c])}")
            why = "column" if r in row_set else "cell"
        return "flag", (f"{place} holds {holds}, not {written}; {written} "
                        f"is in {', '.join(where)} — a value from the wrong "
                        f"{why}?"), compared
    return "flag", (f"{place} holds {holds}, not {written} — a typo, an "
                    "older value, or a number from elsewhere?"), compared


_UNIT_TAIL = re.compile(r"\s*,\s*(?:%|n|no\.|n\s*\(%\)|mean|median)\s*$",
                        re.IGNORECASE)


def _header(text: str) -> str:
    """A row's or column's name without its unit: "Incidence (per 1,000)"
    -> "Incidence", "Vaccinated, %" -> "Vaccinated"."""
    text = re.sub(r"\s*(?:\([^()]*\)|\[[^\[\]]*\])", "", text)
    return " ".join(_UNIT_TAIL.sub("", text).split())


def _cell_evidence(document: Document, t, model, compared, written: str):
    """The compared cell as the service's TableEvidence: where it is, its
    headers, what it holds as the text would quote it, and the rounding
    the comparison allowed."""
    r, c, n = compared
    cell = model.grid.at(r, c)
    if cell is None or cell.start < 0 or cell.end < cell.start:
        return None
    quoted = tables.numbers(written)[0]
    expected = n.written
    if (not n.percent and "%" in model.unit_text(r, c)
            and len(tables.numbers(cell.text)) == 1):
        expected += "%"           # "12.5" under "Vaccinated (%)"
    return {
        "table": t.name,
        "row": cell.row,
        "column": c,
        "row_header": _header(model.row_name.get(r, "")),
        "column_header": _header(model.col_name.get(c, "")),
        "cell_start": cell.start,
        "cell_end": cell.end,
        "cell_text": document.original[cell.start:cell.end],
        "expected": expected,
        "quoted": written,
        "rounding": ("rounded to " + _decimal_places(quoted.decimals)
                     if n.decimals > quoted.decimals else ""),
    }


def table_evidence(doc, document: Document):
    """For each number a sentence quotes from one table: (start, end,
    verdict, evidence, cell). The verdict is "pass" or "flag" for the number
    held to a named row and column (its evidence names the cell and any
    rounding), "missing" for any other number that is nowhere in the
    table. `cell` is the compared cell as a dict (the service's
    TableEvidence) when the sentence's row and column come down to one
    cell, else None. X401 reports the flags and the missing."""
    st = structure_of(document)
    floats_cited: dict = {}
    for m, fs in _text_mentions(st):
        floats_cited.setdefault(m.start, []).extend(fs)
    if not floats_cited:
        return
    for sent in doc.sents:
        a, b = sent.start_char, sent.end_char
        cited = [f for pos, fs in floats_cited.items() if a <= pos < b
                 for f in fs]
        if not cited:
            continue
        kinds = {f.kind for f in cited}
        tabs = {id(f): f for f in cited if f.kind == "table"}
        # One table and nothing else: then the number must come from it.
        if kinds != {"table"} or len(tabs) != 1:
            continue
        (t,) = tabs.values()
        table_text = document.original[t.start:t.end]
        # A percentage quoted from a table of counts is derived, not
        # copied: only judge the kinds of number the table itself holds.
        has_pct = "%" in table_text
        has_dec = bool(re.search(r"\d\.\d", table_text))
        text = document.masked[a:b]
        if _AGGREGATE.search(text):
            continue                 # "altogether 99.9%": summed, not quoted
        found = []
        for m in _VALUE.finditer(text):
            vals = _values(m.group(0))
            if not vals:
                continue
            written, value, decimals = vals[0]
            if not (has_pct if "%" in written else has_dec):
                continue
            # A level, not a result: "95% CI", "p < 0.05", "alpha = 0.05".
            if (_LEVEL_AFTER.match(text, m.end())
                    or _LEVEL_BEFORE.search(text[max(0, m.start() - 12):
                                                 m.start()])):
                continue
            found.append((m, written.replace("\\%", "%"), value, decimals))
        if not found:
            continue
        bound, rows, cols = None, None, None
        model = _table_model(document, t)
        if model is not None and not _CONTRAST.search(text):
            probe = _FLOAT_NAME.sub(lambda x: " " * len(x.group(0)), text)
            rows, cols = tables.locate(model, probe)
            if rows is not None:
                # The number nearest the row's name is that row's.
                bound = _nearest(found, rows.spans, text)
            elif cols is not None:
                bound = _nearest(found, cols.spans, text)
            if (bound is not None and cols is not None
                    and not _attached(text, cols.spans, bound[0])):
                cols = None              # the column is named for another
                if rows is None:         # number, or in another clause
                    bound = None
        for item in found:
            m, written, value, decimals = item
            start, end = a + m.start(), a + m.start() + len(m.group(0).strip())
            if item is bound:
                verdict, evidence, compared = _judge(
                    t, model, rows, cols, written, text, m.end())
                if verdict != "abstain":
                    yield start, end, verdict, evidence, (
                        _cell_evidence(document, t, model, compared, written)
                        if compared is not None else None)
                    continue
            if not _in_table(value, decimals, table_text):
                yield start, end, "missing", (
                    f"{written} is not in {t.name} — a typo, an older "
                    "value, or a number from elsewhere?"), None


@rule("X401", "number-not-in-table", Category.CORRECTION,
      "A number quoted with 'Table N' that Table N does not contain, or "
      "that sits in another row or column than the one the sentence names.",
      'When a sentence cites a table and quotes a figure from it, the '
      'reader will look for that number in the table, in the row and '
      'column the sentence names. A mismatch is usually a typo, a value '
      'from an older run, a number from another row or group, or a number '
      'from another table. A rounded value matches; a proportion does not '
      'match a percentage. Derived numbers (differences, ratios) are worth '
      'a word saying so.',
      plain=('This sentence cites a table and quotes a number, but that number '
             'is not where the sentence says it is: not in the table, or not '
             'in the row or column the sentence names. It may be a typo, an '
             'old value, or a number from a different row or table. If you '
             'calculated it from the table, say so.'),
      source="§6",
      scope="document")
def x401_number_not_in_table(doc, document: Document):
    for start, end, verdict, evidence, cell in table_evidence(doc, document):
        if verdict != "pass":
            yield Suggestion(message=evidence, start=start, end=end,
                             table_evidence=cell)


_AGGREGATE = re.compile(
    r"\b(?:altogether|in total|overall|combined|together|cumulative|"
    r"sum of|of all)\b", re.IGNORECASE)
_LEVEL_AFTER = re.compile(
    r"\s*(?:\\?%)?\s*(?:CI|CrI|UI|PI|HDI|confidence|credible|uncertainty|"
    r"prediction|significance)\b", re.IGNORECASE)
_LEVEL_BEFORE = re.compile(r"(?:\bp|\bP|α|alpha|level of)\s*[<>=≤≥]?\s*$")


# --- X501: a heading style on body text -------------------------------------------

@rule("X501", "heading-style-on-body-text", Category.CORRECTION,
      "A paragraph of body text formatted with a heading style.",
      "Word builds the navigation pane, the table of contents and a "
      "journal's section structure from heading styles. A paragraph of "
      "body text in a heading style puts the whole paragraph into all "
      "three, and a heading run into its first paragraph (common after "
      "converting a PDF) hides where the section starts.",
      plain=('This paragraph of normal text has a heading style. Word uses '
             'heading styles to build the table of contents and the navigation '
             'pane, so this whole paragraph will appear there. Give it a body '
             'style.'),
      source="Word",
      scope="document")
def x501_heading_style_on_body(doc, document: Document):
    if document.kind != "word":
        return
    for item in document.structure:
        if item.kind != "styled_body":
            continue
        text = document.original[item.start:item.end]
        n = len(text.split())
        a, b = _anchor(document, item.start, item.end, limit=60)
        if item.label == "run-in":
            msg = ("The heading runs into its first paragraph: "
                   f"{n} words carry the heading style. Put the heading on "
                   "its own line and give the text a body style.")
        else:
            msg = (f"This paragraph has a heading style but holds {n} words "
                   "of body text — give it a body style (or make it a "
                   "table, if it is one).")
        yield Suggestion(message=msg, start=a, end=b)

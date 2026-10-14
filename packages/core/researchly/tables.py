"""Tables as grids: the cell a sentence names (Codex review #7).

X401 used to ask only whether a quoted number appears *anywhere* in the
cited table, so "treatment mortality was 12.5% (Table 1)" passed when 12.5%
was the control group's figure. When the source says where each cell sits
(an uploaded .docx file, or the Word add-in on WordApi 1.3: see
`Document.table_cells`), a table becomes a grid: the first row holds the
column headers, the first column the row headers. A sentence that names
exactly one row and one column names one cell, and the number it quotes is
compared with that cell.

Deliberately narrow (precision over recall, CLAUDE.md #5):

- Only plain rectangular tables: one header row, one header column, no
  merged cells. A cell spanning columns, a vertical merge, a nested table
  or a row that skips grid columns leaves the table unsupported (the
  readers then send no places, or a colspan this module refuses).
- A header is named only by its own words: case, spacing, punctuation, a
  trailing unit such as "(%)" and a leading "the" are ignored; there are
  no synonyms and no fuzzy matching.
- Numbers are compared by type: a percentage with a percentage, a plain
  number with a plain number. 0.125, 12.5% and 12.5 people are not the
  same value without a conversion rule, so a mismatch in type is no
  verdict. The rounding allowance is X401's: the text may round what the
  table reports.
- When the words fit more than one cell, or a header repeats, there is no
  cell. The caller falls back to the whole table; abstaining is never a
  confirmation that the number is right.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .document import Document


@dataclass
class Cell:
    row: int
    col: int
    start: int
    end: int
    text: str


@dataclass
class Grid:
    table: int
    start: int
    end: int
    cells: dict = field(default_factory=dict)      # (row, col) -> Cell
    # Why the grid cannot name cells ("" when it can).
    unsupported: str = ""


def grids(document: Document) -> list[Grid]:
    """The document's tables as grids, from its cell places (cached)."""
    out = getattr(document, "_grids", None)
    if out is None:
        out = _build(document)
        document._grids = out
    return out


def grid_within(document: Document, start: int, end: int) -> Grid | None:
    """The one table whose cells lie in [start, end), e.g. a float's span
    (caption and table); None when there is none, or more than one."""
    found = [g for g in grids(document) if start <= g.start and g.end <= end]
    return found[0] if len(found) == 1 else None


def _build(document: Document) -> list[Grid]:
    by_table: dict[int, Grid] = {}
    for a, b, t, row, col, span in sorted(document.table_cells):
        g = by_table.get(t)
        if g is None:
            g = by_table[t] = Grid(t, a, b)
        g.start, g.end = min(g.start, a), max(g.end, b)
        if span != 1:
            g.unsupported = "a merged cell"
        text = document.original[a:b].strip()
        cell = g.cells.get((row, col))
        if cell is None:
            g.cells[(row, col)] = Cell(row, col, a, b, text)
        else:                               # a cell of several paragraphs
            cell.end = b
            cell.text = f"{cell.text} {text}".strip()
    for g in by_table.values():
        if not g.unsupported:
            if not any(label(c.text)[0] for (r, k), c in g.cells.items()
                       if r == 0 and k >= 1):
                g.unsupported = "no header row"
            elif not any(label(c.text)[0] for (r, k), c in g.cells.items()
                         if k == 0 and r >= 1):
                g.unsupported = "no header column"
    return sorted(by_table.values(), key=lambda g: g.start)


# --- naming a cell ---------------------------------------------------------

# A trailing unit: "Mortality (%)", "Age [years]", "Vaccinated, %".
_UNIT = re.compile(r"\s*(?:\(([^()]*)\)|\[([^\[\]]*)\]|,\s*(%))\s*$")


def normalize(text: str) -> str:
    """Lower case, punctuation as spaces, single spaces, no leading "the"."""
    t = re.sub(r"[\W_]+", " ", text.lower()).strip()
    return re.sub(r"^the\s+", "", t)


def label(text: str) -> tuple[str, str]:
    """(header words, unit) for a header cell; words "" when the cell
    cannot name a row or column (empty, or no letters: "2020", "0-14")."""
    unit = ""
    m = _UNIT.search(text)
    if m and m.start() > 0:
        unit = next(g for g in m.groups() if g is not None)
        text = text[:m.start()]
    words = normalize(text)
    if len(words) < 2 or not re.search(r"[^\W\d_]", words):
        return "", unit
    return words, unit


def header_name(text: str) -> str:
    """A header as the table writes it, without its unit: "Mortality (%)"
    -> "Mortality"; "" when the cell cannot name a row or column."""
    if not label(text)[0]:
        return ""
    m = _UNIT.search(text)
    if m and m.start() > 0:
        text = text[:m.start()]
    return " ".join(text.split())


@dataclass
class Target:
    """The cell a sentence names, with the headers that name it."""
    cell: Cell
    row_header: Cell | None
    col_header: Cell | None
    percent: bool               # the cell, or a header over it, says "%"


def named_cell(grid: Grid | None, sentence: str) -> Target | None:
    """The one cell `sentence` names by its row and column headers, or None.

    A row (or column) may go unnamed only when the table has a single data
    row (or column). Two rows or two columns named, a header text that
    repeats, or one that is both a row and a column header: no cell.
    """
    if grid is None or grid.unsupported:
        return None
    rows: dict[str, set] = {}
    cols: dict[str, set] = {}
    for (r, c), cell in grid.cells.items():
        if r == 0 and c >= 1:
            words = label(cell.text)[0]
            if words:
                cols.setdefault(words, set()).add(c)
        elif c == 0 and r >= 1:
            words = label(cell.text)[0]
            if words:
                rows.setdefault(words, set()).add(r)
    ambiguous = ({w for w, s in rows.items() if len(s) > 1}
                 | {w for w, s in cols.items() if len(s) > 1}
                 | (rows.keys() & cols.keys()))
    text = normalize(sentence)
    hits = [(m.start(), m.end(), w) for w in rows.keys() | cols.keys()
            for m in re.finditer(r"(?<!\S)" + re.escape(w) + r"(?!\S)", text)]
    # "Mortality" inside a match for "Mortality at 30 days" is not a
    # second header named.
    hits = [h for h in hits
            if not any(o[0] <= h[0] and h[1] <= o[1]
                       and o[1] - o[0] > h[1] - h[0] for o in hits)]
    named = {w for _, _, w in hits}
    if not named or named & ambiguous:
        return None
    named_rows = [w for w in named if w in rows]
    named_cols = [w for w in named if w in cols]
    if len(named_rows) > 1 or len(named_cols) > 1:
        return None
    row = (next(iter(rows[named_rows[0]])) if named_rows
           else _only({r for r, c in grid.cells if r >= 1 and c >= 1}))
    col = (next(iter(cols[named_cols[0]])) if named_cols
           else _only({c for r, c in grid.cells if r >= 1 and c >= 1}))
    if row is None or col is None:
        return None
    cell = grid.cells.get((row, col))
    if cell is None or not numbers(cell.text):
        return None
    rh, ch = grid.cells.get((row, 0)), grid.cells.get((0, col))
    percent = "%" in cell.text or any(
        h is not None and "%" in h.text for h in (rh, ch))
    return Target(cell, rh, ch, percent)


def _only(values: set):
    return next(iter(values)) if len(values) == 1 else None


# --- comparing a number with the cell --------------------------------------

_NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?![.\d])(\s*\\?%)?")


@dataclass
class Number:
    written: str
    value: float
    decimals: int
    percent: bool


def numbers(text: str) -> list[Number]:
    out = []
    for m in _NUMBER.finditer(text):
        whole, frac = m.group(1), m.group(2) or ""
        out.append(Number(m.group(0).strip().replace("\\%", "%"),
                          float(whole.replace(",", "") + frac),
                          len(frac) - 1 if frac else 0, bool(m.group(3))))
    return out


@dataclass
class Comparison:
    matches: bool
    expected: Number            # the cell's number the text is set against
    rounding: str = ""          # "rounded to 1 decimal place", when it was


def compare(quoted: Number, target: Target) -> Comparison | None:
    """The quoted number against the target cell; None when they are not
    the same kind of number (a percentage against a plain number)."""
    if quoted.percent != target.percent:
        return None
    found = numbers(target.cell.text)
    if not found:
        return None
    for n in found:
        if abs(n.value - quoted.value) < 1e-9:
            return Comparison(True, n)
        # The text may round what the table reports: 0.4321 -> 0.43.
        if (n.decimals > quoted.decimals and abs(n.value - quoted.value)
                <= 0.5 * 10 ** -quoted.decimals + 1e-9):
            return Comparison(True, n, _rounded(quoted.decimals))
    expected = found[0]
    rounding = (_rounded(quoted.decimals)
                if expected.decimals > quoted.decimals else "")
    return Comparison(False, expected, rounding)


def _rounded(decimals: int) -> str:
    if decimals == 0:
        return "rounded to a whole number"
    return f"rounded to {decimals} decimal place{'s' if decimals > 1 else ''}"


def shown(n: Number, percent: bool, decimals: int | None = None) -> str:
    """A cell's number as the reader would quote it: "8.2%" when the cell
    or its header says "%"; rounded to `decimals` when given."""
    if decimals is None:
        text = n.written.rstrip("% ").strip()
    else:
        text = f"{_half_up(n.value, decimals):.{decimals}f}"
    return text + ("%" if percent else "")


def _half_up(value: float, decimals: int) -> float:
    from decimal import ROUND_HALF_UP, Decimal
    q = Decimal(1).scaleb(-decimals)
    return float(Decimal(repr(value)).quantize(q, rounding=ROUND_HALF_UP))

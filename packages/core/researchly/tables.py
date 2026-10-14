"""Tables as rows and columns, so X401 can find the cell a sentence quotes
(Codex review #7).

A table reaches the engine in one of two forms:

- LaTeX: the float's source, with one `tabular` (or `tabularx`,
  `longtable`, ...) inside it. Rows end at `\\\\`, cells at `&`;
  `\\multicolumn` spans columns and an empty cell under a `\\multirow`
  label repeats the label above it.
- Word: an uploaded .docx gives every table cell its row and column
  (`Document.table_cells`). The Word add-in sends cells without them, so
  its tables have no grid and X401 looks anywhere in the table, as before.

Plain text and Markdown have no tables here at all (`structure.analyse`
reads only LaTeX and Word).

`read(grid)` finds the header rows (the leading rows with no numbers), the
label columns (the leading columns with no numbers), and the labels a
sentence can name: each header cell names the columns under it, each row
label (and a label row standing over a group of rows) names its rows.
`locate(table, sentence)` returns the rows and columns the sentence names,
and only when it names them unambiguously: two different rows, or two
different columns, named at the same level are not resolved by guessing.
Anything this module cannot read with confidence gives None, and the rule
falls back to the whole table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

MAX_ROWS, MAX_COLS = 300, 40


# --- the grid ----------------------------------------------------------------

@dataclass
class Cell:
    row: int
    col: int
    span: int
    text: str


@dataclass
class Grid:
    rows: list[list[Cell]]
    ncols: int

    def at(self, r: int, c: int) -> Optional[Cell]:
        for cell in self.rows[r]:
            if cell.col <= c < cell.col + cell.span:
                return cell
        return None

    def text(self, r: int, c: int) -> str:
        cell = self.at(r, c)
        return cell.text if cell is not None else ""


def _grid(rows: list[list[tuple[int, int, str]]]) -> Optional[Grid]:
    """(col, span, text) per row -> a Grid, or None when it is too small
    or too large to be a table of results."""
    rows = [r for r in rows if any(t.strip() for _, _, t in r)]
    if len(rows) < 2 or len(rows) > MAX_ROWS:
        return None
    ncols = max(c + s for r in rows for c, s, _ in r)
    if ncols < 2 or ncols > MAX_COLS:
        return None
    out = []
    for i, r in enumerate(rows):
        out.append([Cell(i, c, s, " ".join(t.split())) for c, s, t in r])
    return Grid(out, ncols)


# --- LaTeX ------------------------------------------------------------------

_TABULAR = re.compile(
    r"\\begin\s*\{(tabular\*?|tabularx|tabulary|longtable\*?)\}")
# Any other table environment in the float (tabularray's tblr, a nested
# array): its cells are not read, so the float is not either.
_OTHER_TABLE = re.compile(r"\\begin\s*\{(?:tblr|longtblr|talltblr|array)\}")
_WIDTH_FIRST = {"tabular*", "tabularx", "tabulary"}
_COMMENT = re.compile(r"(?<!\\)%[^\n]*")
# Rules and spacing between rows: never a cell.
_RULE = re.compile(
    r"\s*\\(?:hline|toprule|midrule|bottomrule|morecmidrules|"
    r"endfirsthead|endhead|endfoot|endlastfoot|"
    r"cline|cmidrule|addlinespace|specialrule|noalign|rowcolor|hhline|"
    r"arrayrulecolor|rule)\b\*?")
_CELL_COLOUR = re.compile(r"\\cellcolor\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}")


def _group(s: str, i: int, open_: str = "{", close: str = "}"
           ) -> Optional[tuple[str, int]]:
    """The balanced group starting at s[i] (after spaces): (inside, end)."""
    while i < len(s) and s[i] in " \t\n":
        i += 1
    if i >= len(s) or s[i] != open_:
        return None
    depth = 0
    j = i
    while j < len(s):
        ch = s[j]
        if ch == "\\":
            j += 2
            continue
        if ch == open_:
            depth += 1
        elif ch == close:
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return None


def _skip_args(s: str, i: int, pattern: str) -> Optional[int]:
    """Skip a macro's arguments: '[' optional, '{' required, '(' optional."""
    for kind in pattern:
        if kind == "[":
            g = _group(s, i, "[", "]")
            if g is not None:
                i = g[1]
        elif kind == "(":
            g = _group(s, i, "(", ")")
            if g is not None:
                i = g[1]
        else:
            g = _group(s, i)
            if g is None:
                return None
            i = g[1]
    return i


_RULE_ARGS = {"cline": "{", "cmidrule": "[({", "addlinespace": "[",
              "specialrule": "{{{", "noalign": "{", "rowcolor": "[{",
              "hhline": "{", "arrayrulecolor": "[{", "toprule": "[",
              "midrule": "[", "bottomrule": "[", "rule": "[{{"}


def _strip_rules(row: str) -> str:
    """Rules and colours at the start of a row (`\\midrule \\cmidrule{2-3}`)."""
    while True:
        m = _RULE.match(row)
        if not m:
            return row
        name = m.group(0).strip().lstrip("\\").rstrip("*")
        end = _skip_args(row, m.end(), _RULE_ARGS.get(name, ""))
        if end is None:
            end = m.end()
        row = row[end:]


def _split(s: str, sep: str) -> list[str]:
    """Split at `sep` ('&' or '\\\\') outside braces, never at `\\&`."""
    out, depth, start, i = [], 0, 0, 0
    while i < len(s):
        ch = s[i]
        if ch == "\\":
            if sep == "\\\\" and depth == 0 and s.startswith("\\\\", i):
                out.append(s[start:i])
                i += 2
                if i < len(s) and s[i] == "*":
                    i += 1
                g = _group(s, i, "[", "]")     # \\[2pt]
                if g is not None:
                    i = g[1]
                start = i
                continue
            if (sep == "\\\\" and depth == 0
                    and s.startswith("\\tabularnewline", i)):
                out.append(s[start:i])
                i += len("\\tabularnewline")
                start = i
                continue
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif ch == "&" and sep == "&" and depth == 0:
            out.append(s[start:i])
            start = i + 1
        i += 1
    out.append(s[start:])
    return out


def _unwrap(cell: str, macro: str, pattern: str) -> Optional[tuple[str, str]]:
    """`\\multicolumn{3}{c}{Men}` -> ("3", "Men") for pattern '{{{' with
    the first and last arguments kept."""
    m = re.match(r"\s*\\" + macro + r"\b", cell)
    if not m:
        return None
    i = m.end()
    args = []
    for kind in pattern:
        if kind == "[":
            g = _group(cell, i, "[", "]")
            if g is not None:
                i = g[1]
            continue
        g = _group(cell, i)
        if g is None:
            return None
        args.append(g[0])
        i = g[1]
    return args[0], args[-1] + cell[i:]


_SYMBOLS = [
    (r"\%", "%"), (r"\&", "&"), (r"\_", "_"), (r"\#", "#"), (r"\$", "$"),
    ("{,}", ","), ("---", "—"), ("--", "–"), ("~", " "),
]
_MACRO_SYMBOLS = {"pm": "±", "times": "×", "textless": "<",
                  "textgreater": ">", "geq": "≥", "ge": "≥", "leq": "≤",
                  "le": "≤", "textpm": "±", "textendash": "–",
                  "textemdash": "—", "lt": "<", "gt": ">"}
# Footnote marks on a cell: "0.43^{a}", "Male\\textsuperscript{*}".
_SUPERSCRIPT = re.compile(
    r"\\textsuperscript\s*\{[^{}]*\}|\^\s*\{[^{}]*\}"
    r"|\^\s*(?:\\[A-Za-z]+|\w)")


def latex_text(cell: str) -> str:
    """A cell's LaTeX as the text a reader sees."""
    s = cell
    s = re.sub(r"\\\\(?:\[[^\]]*\])?", " ", s)       # \makecell line breaks
    s = _CELL_COLOUR.sub("", s)
    s = _SUPERSCRIPT.sub("", s)
    for a, b in _SYMBOLS:
        s = s.replace(a, b)
    s = re.sub(r"\\([,;:! ])", " ", s)
    s = re.sub(r"\\([A-Za-z]+)\*?\s*(?:\[[^\]]*\])?",
               lambda m: _MACRO_SYMBOLS.get(m.group(1), " "), s)
    s = s.replace("}{", "} {").replace("$", "")
    s = re.sub(r"[{}]", "", s)
    return " ".join(s.split())


def latex_grid(src: str) -> Optional[Grid]:
    """The grid of the one tabular in a LaTeX table float; None when there
    is none, more than one (sub-tables), or it cannot be read."""
    src = _COMMENT.sub("", src)
    found = list(_TABULAR.finditer(src))
    if len(found) != 1 or _OTHER_TABLE.search(src):
        return None
    # \multirow{-2}: the label sits on the group's last row, so filling it
    # down would give the rows above it the previous group's label.
    if re.search(r"\\multirow\s*(?:\[[^\]]*\])?\s*\{\s*-", src):
        return None
    m = found[0]
    env = m.group(1)
    i = m.end()
    g = _group(src, i, "[", "]")
    if g is not None:
        i = g[1]
    if env in _WIDTH_FIRST:
        g = _group(src, i)
        if g is None:
            return None
        i = g[1]
    g = _group(src, i)                                    # column spec
    if g is None:
        return None
    i = g[1]
    end = src.find("\\end{" + env + "}", i)
    if end == -1:
        return None
    body = src[i:end]
    # \caption{...} and \label{...} inside a longtable are not cells.
    for macro in ("caption", "label"):
        while True:
            c = re.search(r"\\" + macro + r"\*?\s*(?:\[[^\]]*\])?\s*(?=\{)",
                          body)
            if not c:
                break
            g = _group(body, c.end())
            body = body[:c.start()] + (body[g[1]:] if g else
                                       body[c.end():])
    # A longtable repeats its header on every page: keep the first one.
    if "\\endfirsthead" in body:
        head, rest = body.split("\\endfirsthead", 1)
        cut = max(rest.rfind(k) for k in ("\\endhead", "\\endfoot",
                                           "\\endlastfoot"))
        body = head + "\\\\" + (rest[cut:] if cut >= 0 else rest)
    elif "\\endhead" in body:
        head, rest = body.split("\\endhead", 1)
        cut = max(rest.rfind(k) for k in ("\\endfoot", "\\endlastfoot"))
        body = head + "\\\\" + (rest[cut:] if cut >= 0 else rest)
    rows = []
    for raw in _split(body, "\\\\"):
        raw = _strip_rules(raw)
        if not raw.strip():
            continue
        cells, col = [], 0
        for part in _split(raw, "&"):
            part = _strip_rules(part)
            span = 1
            mc = _unwrap(part, "multicolumn", "{{{")
            if mc is not None:
                try:
                    span = max(1, int(mc[0].strip()))
                except ValueError:
                    return None
                part = mc[1]
            mr = _unwrap(part, "multirow", "[{[{[{")
            if mr is not None:
                part = mr[1]
            mk = _unwrap(part, "makecell", "[{")
            if mk is not None:
                part = mk[1]
            cells.append((col, span, latex_text(part)))
            col += span
        rows.append(cells)
    return _grid(rows)


# --- Word -------------------------------------------------------------------

def word_grid(cells: list[tuple[int, int, int, int, int, int, str]]
              ) -> Optional[Grid]:
    """(start, end, table, row, col, span, text) for every non-empty cell
    paragraph of one table -> a Grid. Several paragraphs in one cell are
    one cell; cells of two tables (a nested table) are not one grid."""
    if not cells or len({c[2] for c in cells}) != 1:
        return None
    by_pos: dict[tuple[int, int], list] = {}
    for _, _, _, r, c, span, text in cells:
        key = (r, c)
        if key in by_pos:
            by_pos[key][1] = max(by_pos[key][1], span)
            by_pos[key][2] += " " + text
        else:
            by_pos[key] = [c, span, text]
    nrows = max(r for r, _ in by_pos) + 1
    rows: list[list[tuple[int, int, str]]] = [[] for _ in range(nrows)]
    for (r, _), (c, span, text) in sorted(by_pos.items()):
        rows[r].append((c, span, text))
    return _grid(rows)


# --- numbers ----------------------------------------------------------------

NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?![.\d])(\s*\\?%)?")


@dataclass(frozen=True)
class Number:
    written: str          # "4.13", "12.5%"
    value: Decimal
    decimals: int
    percent: bool


def numbers(text: str) -> list[Number]:
    """Every number in a cell, integers included."""
    out = []
    for m in NUMBER.finditer(text):
        whole, frac, pct = m.group(1), m.group(2) or "", m.group(3)
        try:
            v = Decimal(whole.replace(",", "") + frac)
        except InvalidOperation:
            continue
        out.append(Number(m.group(0).strip().replace("\\%", "%"), v,
                          len(frac) - 1 if frac else 0, bool(pct)))
    return out


def _data_cell(text: str) -> bool:
    """A cell holding a result: a decimal, or numbers and no words."""
    if not re.search(r"\d", text):
        return False
    return bool(re.search(r"\d\.\d", text)) or not re.search(
        r"[^\W\d_]", text)


# A label written in numbers: "18–29", "≥65", "65+", "<18".
_RANGE_LABEL = re.compile(
    r"^\s*(?:[<>≤≥]\s*\d+|\d+\s*(?:–|—|-{1,3}|−|to)\s*\d+|\d+\s*\+)\s*$")


def _value_cell(text: str) -> bool:
    """A decimal or a percentage: never a row's label."""
    return bool(re.search(r"\d\.\d|\d\s*%", text))


def rounds_to(cell: Number, text: Number) -> bool:
    """Is the text's number the cell's, or the cell's rounded to the
    text's decimal places? (Half up or half to even: both are in use.)"""
    if cell.value == text.value:
        return True
    if cell.decimals <= text.decimals:
        return False
    q = Decimal(1).scaleb(-text.decimals)
    return any(cell.value.quantize(q, rounding=r) == text.value
               for r in (ROUND_HALF_UP, ROUND_HALF_EVEN))


def rounded(cell: Number, decimals: int) -> str:
    q = Decimal(1).scaleb(-decimals)
    return str(cell.value.quantize(q, rounding=ROUND_HALF_UP))


# "per 1,000", "per 100 000", "/1000": a rate's base.
_PER = re.compile(
    r"(?:\bper\b|/)\s*(\d{1,3}(?:\s?[,\u00a0\u202f ]\s?\d{3})+|\d+)(?![\d.])",
    re.IGNORECASE)


def per_base(text: str) -> Optional[int]:
    """The one rate base a text names, if exactly one."""
    bases = {int(re.sub(r"\D", "", m.group(1))) for m in _PER.finditer(text)}
    return bases.pop() if len(bases) == 1 else None


# --- labels -----------------------------------------------------------------

_TOKEN = re.compile(
    r"[<>≤≥]?\d+(?:[.,]\d+)*"
    r"(?:\s*(?:–|—|-{1,3}|−|to)\s*\d+(?:[.,]\d+)*)?\+?"
    r"|[^\W\d_]+(?:['’][^\W\d_]+)?")
_RANGE_SEP = re.compile(r"\s*(?:–|—|-{1,3}|−|to)\s*")
# Words that name no particular row or column: a label made only of these
# ("Total", "Mean (SD)", "n (%)") is never matched.
GENERIC = frozenset("""
a an the of in on at by for to with and or vs versus per from than as is
was were be are this that these those its their it
n no number numbers total totals overall all mean means median medians
sd se iqr range ranges value values estimate estimates variable variables
characteristic characteristics parameter parameters group groups category
categories subgroup subgroups level levels year years yr yrs ci cri ui
interval intervals percent percentage percentages p other others
table tables column columns row rows unit units
after before during within yes none missing unknown any some most more less
high low
""".split())
_ALIASES = {"aged": "age"}


def norm(token: str) -> str:
    t = token.lower().replace("’", "'")
    if t[:1].isdigit() or t[:1] in "<>≤≥":
        return _RANGE_SEP.sub("-", t).replace(" ", "")
    t = _ALIASES.get(t, t)
    if t.endswith("'s"):
        t = t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        t = t[:-1]
    return t


def tokens(text: str) -> list[tuple[str, int, int]]:
    return [(norm(m.group(0)), m.start(), m.end())
            for m in _TOKEN.finditer(text)]


_PAREN = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
_MARKS = re.compile(r"[*†‡§¶]+")


def label_keys(text: str) -> frozenset[str]:
    """The words a sentence must use to name this label: without its
    bracketed unit or count, footnote marks and generic words."""
    text = _MARKS.sub(" ", _PAREN.sub(" ", text))
    text = re.split(r",\s*(?:n|%|mean|median|no\.)\b", text,
                    flags=re.IGNORECASE)[0]
    keys = frozenset(t for t, _, _ in tokens(text) if t not in GENERIC)
    return keys if _distinctive(keys) else frozenset()


def _distinctive(keys: frozenset[str]) -> bool:
    if not keys:
        return False
    for k in keys:
        if k[:1].isdigit() or k[:1] in "<>≤≥":
            digits = re.sub(r"\D", "", k)
            if "-" in k or "+" in k or k[:1] in "<>≤≥" or (
                    len(digits) >= 2 and "." not in k):
                return True
        elif len(k) >= 3:
            return True
    return False


@dataclass
class Label:
    text: str
    keys: frozenset
    level: int
    cover: set = field(default_factory=set)


def _labels(entries: list[tuple[int, str, int]]) -> list[Label]:
    """(level, text, index) -> one Label per distinct text and level, its
    cover the union of the indexes ("18–29" under Men and under Women)."""
    out: dict[tuple[int, frozenset], Label] = {}
    for level, text, index in entries:
        keys = label_keys(text)
        if not keys:
            continue
        lab = out.setdefault((level, keys), Label(text, keys, level))
        lab.cover.add(index)
    return list(out.values())


# --- reading a table --------------------------------------------------------

@dataclass
class Table:
    grid: Grid
    header_rows: list[int]
    label_cols: list[int]
    data_rows: list[int]
    value_cols: list[int]
    row_labels: list[Label]
    col_labels: list[Label]
    row_name: dict
    col_name: dict
    group_of: dict           # data row -> its group's text ("" if none)

    def values(self, rows, cols) -> list[tuple[int, int, Number]]:
        out = []
        seen = set()
        for r in rows:
            for c in cols:
                cell = self.grid.at(r, c)
                if cell is None or id(cell) in seen:
                    continue
                seen.add(id(cell))
                for n in numbers(cell.text):
                    out.append((r, c, n))
        return out

    def unit_text(self, r: int, c: int) -> str:
        """Where a cell's unit may be written: the cell, its column's
        headers and its row's labels."""
        parts = [self.grid.text(r, c)]
        parts += [self.grid.text(h, c) for h in self.header_rows]
        parts += [self.grid.text(r, j) for j in self.label_cols]
        return " ".join(parts)


def read(grid: Grid) -> Optional[Table]:
    rows = range(len(grid.rows))
    header = []
    for r in rows:
        if any(_data_cell(t) and not _RANGE_LABEL.match(t)
               for t in (grid.text(r, c) for c in range(1, grid.ncols))):
            break
        filled = [x for x in grid.rows[r] if x.text.strip()]
        if header and len(filled) == 1 and filled[0].col == 0:
            break                     # a label row heading a group of rows
        header.append(r)
    if len(header) > 3 or len(header) == len(grid.rows):
        return None
    body = [r for r in rows if r not in header]
    # The first column labels the rows unless it holds results; its labels
    # may be numbers ("18–29", "2019"). Further label columns hold words
    # or ranges ("Men" | "18–29"), never counts.
    label_cols = []
    for c in range(grid.ncols - 1):
        cells = [grid.text(r, c) for r in body]
        if any(_value_cell(t) for t in cells):
            break
        if c > 0 and any(_data_cell(t) and not _RANGE_LABEL.match(t)
                         for t in cells):
            break
        label_cols.append(c)
    value_cols = [c for c in range(grid.ncols) if c not in label_cols]
    if not label_cols or not value_cols:
        return None
    data_rows = [r for r in body
                 if any(_data_cell(grid.text(r, c)) for c in value_cols)]
    if not data_rows:
        return None

    # Rows: a label row with nothing else in it heads the rows below it;
    # an empty outer label repeats the one above it (a \multirow, or a
    # merged Word cell).
    entries: list[tuple[int, str, int]] = []
    group, group_of, row_name = "", {}, {}
    above = [""] * len(label_cols)
    for r in body:
        texts = [grid.text(r, c) for c in range(grid.ncols)]
        if r not in data_rows:
            filled = [x for x in grid.rows[r] if x.text.strip()]
            if len(filled) == 1 and filled[0].col == 0:
                group = filled[0].text.strip()
                above = [""] * len(label_cols)
            continue
        parts = []
        for k, c in enumerate(label_cols):
            t = texts[c].strip()
            if not t and k < len(label_cols) - 1:
                t = above[k]
            above[k] = t
            parts.append(t)
        # The row's group: its label row and outer labels ("Men" over
        # "18–29"), everything but its own label.
        group_of[r] = " / ".join(p for p in [group] + parts[:-1] if p)
        if group:
            entries.append((-1, group, r))
        for k, t in enumerate(parts):
            if t:
                entries.append((k, t, r))
        row_name[r] = " / ".join(p for p in ([group] + parts) if p)
    # Columns: every header cell over a value column.
    col_entries: list[tuple[int, str, int]] = []
    col_name = {}
    for c in value_cols:
        path = []
        for level, h in enumerate(header):
            t = grid.text(h, c).strip()
            if t:
                col_entries.append((level, t, c))
                if not path or path[-1] != t:
                    path.append(t)
        col_name[c] = " / ".join(path)
    return Table(grid, header, label_cols, data_rows, value_cols,
                 _labels(entries), _labels(col_entries), row_name, col_name,
                 group_of)


# --- what a sentence names --------------------------------------------------

@dataclass
class Named:
    cover: set
    spans: list               # where the sentence names it
    labels: list


def _match(label: Label, toks: dict) -> Optional[list[tuple[int, int]]]:
    """Where the sentence uses all of a label's words, close together."""
    spans = []
    for k in label.keys:
        if k not in toks:
            return None
        spans.append(toks[k])
    if max(b for _, b in spans) - min(a for a, _ in spans) > 60:
        return None
    return spans


def _axis(labels: list[Label], toks: dict, everything: set
          ) -> Optional[Named]:
    matched = [(lab, sp) for lab in labels
               if (sp := _match(lab, toks)) is not None]
    if not matched:
        return None
    by_level: dict[int, list] = {}
    for lab, sp in matched:
        by_level.setdefault(lab.level, []).append((lab, sp))
    chosen = []
    for level, items in by_level.items():
        # "Hospitalised, ICU" beats "Hospitalised" when both match.
        items = [(lab, sp) for lab, sp in items
                 if not any(lab.keys < other.keys for other, _ in items)]
        if len(items) != 1:
            return None              # two rows (or columns) named: abstain
        chosen.append(items[0])
    cover = set(everything)
    for lab, _ in chosen:
        cover &= lab.cover
    if not cover or cover == set(everything):
        return None
    return Named(cover, [s for _, sp in chosen for s in sp],
                 [lab for lab, _ in chosen])


def locate(table: Table, sentence: str
           ) -> tuple[Optional[Named], Optional[Named]]:
    """(rows, columns) the sentence names; each None when it names none,
    or names them ambiguously."""
    toks: dict[str, tuple[int, int]] = {}
    for t, a, b in tokens(sentence):
        toks.setdefault(t, (a, b))
    rows = _axis(table.row_labels, toks, set(table.data_rows))
    cols = _axis(table.col_labels, toks, set(table.value_cols))
    return rows, cols

"""LaTeX masking by parsing, not by regex (docs/s2-design.md §4).

`mask_latex(text)` walks pylatexenc's node tree and copies through only the
characters a reader sees as prose; everything else becomes a space (newlines
are kept). The masked text is therefore exactly as long as the source, and
every offset a rule reports is an offset into the .tex file.

Why a parser: the regex masker (`document._mask_latex`) cannot match nested
braces, so `\\footnote{see \\cite{x}}` or a caption containing `\\emph{}` was
masked by guesswork, and a `%` inside a URL or a `$` inside a listing broke
everything after it. pylatexenc knows argument structure and verbatim
environments. It never executes TeX: `\\newcommand` is recorded, not expanded.

What stays prose: running text, heading titles (recorded, then masked by
`Document.from_text` like every heading), the text arguments of formatting
macros (`\\emph`, `\\textbf`, `\\footnote`, ...), caption text (also inside
floats), and `\\href` link text. What is masked: comments, math, float bodies,
tabulars, verbatim/listings, citations, references, labels, URLs, graphics,
the preamble, and every macro name.

If pylatexenc is missing or cannot parse the file (an unbalanced brace,
an unclosed `$`), we fall back to the regex masker and say so in
`warnings`, so the user knows some markup may be read as prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..document import Heading, StructureItem, _mask_latex, classify_heading

HEADING_MACROS = frozenset({"part", "chapter", "section", "subsection",
                            "subsubsection", "paragraph", "subparagraph"})
CAPTION_MACROS = frozenset({"caption", "captionof", "subcaption"})
CITE_MACROS = frozenset({
    "cite", "citep", "citet", "citealt", "citealp", "citeauthor", "citeyear",
    "citeyearpar", "citenum", "nocite", "Cite", "Citep", "Citet", "Citealt",
    "Citealp", "Citeauthor", "parencite", "Parencite", "textcite",
    "Textcite", "autocite", "Autocite", "footcite", "smartcite", "Smartcite",
    "supercite", "fullcite", "cites", "parencites", "textcites",
    "autocites",
})
# Macros whose arguments are never prose. Anything not listed here keeps its
# mandatory `{}` arguments (that is how `\emph{x}` and `\footnote{x}` stay
# readable), so this list is what stops "1cm" or "red" reaching the checker.
MASK_WHOLE = frozenset({
    "label", "ref", "eqref", "autoref", "cref", "Cref", "vref", "pageref",
    "nameref", "url", "href", "includegraphics", "input", "include",
    "subfile", "includeonly", "bibliography", "bibliographystyle",
    "addbibresource", "printbibliography", "usepackage", "RequirePackage",
    "documentclass", "footnotemark", "author", "date", "affiliation",
    "affil", "address", "email", "institute", "hspace", "vspace",
    "setlength", "addtolength", "addlength", "setcounter", "addtocounter",
    "addcounter", "newcommand", "renewcommand", "providecommand",
    "newenvironment", "renewenvironment", "provideenvironment",
    "DeclareMathOperator", "def", "gdef", "edef", "xdef", "definecolor",
    "providecolor", "colorlet", "color", "pagecolor", "rowcolors",
    "selectlanguage", "hypersetup", "hphantom", "vphantom", "verb",
    "lstinline", "graphicspath", "newtheorem", "pagestyle", "thispagestyle",
    "pagenumbering",
    # `\iffalse ... \fi` is how LaTeX authors comment out a block.
    "iffalse",
})
# Code, file names and table-of-contents plumbing: never prose. A preamble
# `\newcommand{\code}[1]{\texttt{#1}}` adds `\code` to these per document
# (_Masker.code_macros), which is how most authors spell inline code.
CODE_MACROS = frozenset({"texttt", "code", "path", "file", "filename", "pkg",
                         "cmd", "command", "nolinkurl", "addcontentsline"})
_CODE_BODY = re.compile(r"\\(?:texttt|ttfamily|verb|lstinline|url|path|"
                        r"nolinkurl|code)\b")
_NEWCOMMAND = re.compile(
    r"\\(?:re)?newcommand\*?\s*\{?\\([A-Za-z]+)\}?\s*(?:\[\d\])?"
    r"\s*(?:\[[^\]]*\])?\s*\{")


def code_macros_in(preamble: str) -> set[str]:
    """Macros the preamble defines as wrappers around code formatting."""
    found = set()
    for m in _NEWCOMMAND.finditer(preamble):
        body = preamble[m.end():m.end() + 200].split("\n", 1)[0]
        if _CODE_BODY.search(body):
            found.add(m.group(1))
    return found


# Macros whose text is their LAST argument only (`\textcolor{red}{text}`).
LAST_ARG_ONLY = frozenset({"textcolor", "colorbox", "fcolorbox"})
# Escaped characters stay as written ("50\%", "R\&D"), as the regex masker
# left them: masking only the backslash would split "R\&D" into "R &D".
ESCAPED_CHARS = frozenset("%&$#_{}")

MATH_ENVS = frozenset({"equation", "align", "alignat", "gather", "multline",
                       "eqnarray", "flalign", "displaymath", "math",
                       "split", "dmath"})
VERBATIM_ENVS = ("verbatim", "verbatim*", "Verbatim", "lstlisting",
                 "minted", "comment")
NONPROSE_ENVS = frozenset({"tabular", "tabular*", "tabularx", "tabulary",
                           "array", "tikzpicture", "thebibliography"})
TABULAR_ENVS = frozenset({"tabular", "tabular*", "tabularx", "tabulary"})
FIGURE_ENVS = frozenset({"figure", "figure*", "wrapfigure", "sidewaysfigure",
                         "SCfigure"})
TABLE_ENVS = frozenset({"table", "table*", "wraptable", "sidewaystable",
                        "longtable", "longtable*"})
# Panels inside a float: their \label and \caption belong to the panel.
SUBFLOAT_ENVS = frozenset({"subfigure", "subtable", "minipage"})


@dataclass
class LatexMask:
    masked: str
    headings: list[Heading]
    structure: list[StructureItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def mask_latex(text: str,
               locate: Optional[Callable[[int], str]] = None) -> LatexMask:
    """Mask `text`; never raises. `locate(offset)` words a warning's
    position ("line 12", "line 12 of chapters/methods.tex")."""
    try:
        return _Masker(text).run()
    except ImportError:
        reason = ("The LaTeX parser (pylatexenc) is not installed, so "
                  "Researchly read this file with a simpler reader; some "
                  "markup may be checked as prose.")
    except Exception as exc:   # parse errors, recursion depth, parser bugs
        # A position at the end of the input only says "something was never
        # closed", not where it opened, so it is not worth quoting.
        pos = getattr(exc, "pos", None)
        where = ""
        if isinstance(pos, int) and 0 <= pos < len(text):
            where = " near " + (locate or _line_of(text))(pos)
        reason = (f"Researchly could not fully parse the LaTeX{where} (an "
                  "unbalanced brace, $ or environment?), so it read the file "
                  "with a simpler reader; some markup may be checked as "
                  "prose.")
    masked, headings = _mask_latex(text)
    return LatexMask(masked, headings, [], [reason])


def _line_of(text: str) -> Callable[[int], str]:
    return lambda pos: f"line {text.count(chr(10), 0, pos) + 1}"


# ---------------------------------------------------------------------------
# pylatexenc context: what each macro's arguments look like
# ---------------------------------------------------------------------------

_CONTEXT = None
_CONTROL_SEQ = re.compile(r"\\(?:[A-Za-z@]+|.)", re.S)
_FI = re.compile(r"\\fi(?![A-Za-z@])")
# The first `\begin{document}` that is not commented out.
_BEGIN_DOCUMENT = re.compile(r"^[^%\n]*?(\\begin\s*\{document\})", re.M)


def _context():
    """pylatexenc's default macro database plus what theses use and it lacks
    (biblatex citations, captions, listings, definitions read raw). Built
    once; the parsers keep no state, so threads may share it."""
    global _CONTEXT
    if _CONTEXT is not None:
        return _CONTEXT
    from pylatexenc import latexwalker
    from pylatexenc.macrospec import (EnvironmentSpec, MacroSpec,
                                      MacroStandardArgsParser,
                                      ParsedMacroArgs)

    def fail(s, pos, msg):
        return latexwalker.LatexWalkerParseError(msg=msg, s=s, pos=pos)

    def balanced(s, p, open_, close):
        """Index just past the `close` matching the `open_` at `p`."""
        depth, q = 0, p
        while q < len(s):
            c = s[q]
            if c == "\\":
                q += 2
                continue
            if c == open_:
                depth += 1
            elif c == close:
                depth -= 1
                if depth == 0:
                    return q + 1
            q += 1
        raise fail(s, p, "unclosed argument")

    def token(s, p):
        """Index past one TeX token: a control sequence or a character."""
        if s[p] != "\\":
            return p + 1
        m = _CONTROL_SEQ.match(s, p)
        return m.end() if m else p + 1

    class VerbatimEnv(MacroStandardArgsParser):
        """Body is raw text up to `\\end{name}`, as TeX reads it. Without
        this a `$` or `%` in a code listing derails the rest of the parse."""

        def __init__(self, name):
            super().__init__(argspec="")
            self.end = "\\end{" + name + "}"

        def parse_args(self, w, pos, parsing_state=None):
            stop = w.s.find(self.end, pos)
            if stop == -1:
                raise fail(w.s, pos, "unclosed verbatim environment")
            return ParsedMacroArgs(argnlist=[], argspec=""), pos, stop - pos

    class RawArgs(MacroStandardArgsParser):
        """Arguments read as raw text, as TeX reads them for these macros,
        never parsed as LaTeX: a `%` in a URL is not a comment, and
        `\\newenvironment{q}{\\begin{quote}}{\\end{quote}}` is not an
        unclosed environment. The macros using this are all masked whole.

        `raw` kinds: `*` optional star, `[` optional bracket group, `{` a
        braced group or one token, `c` a control sequence and its parameter
        text (`\\def\\x#1{`), `v` a `\\verb` argument (`[opts]`, then a
        delimiter or braces), `f` everything up to `\\fi` (`\\iffalse`).
        `rest` is parsed normally afterwards (`\\href`'s link text)."""

        def __init__(self, raw, rest=""):
            super().__init__(argspec="{" * len(raw) + rest)
            self.raw, self.rest = raw, rest

        def parse_args(self, w, pos, parsing_state=None):
            s, p, spans = w.s, pos, []
            for kind in self.raw:
                if kind != "v":
                    while p < len(s) and s[p] in " \t\n":
                        p += 1
                if p >= len(s):
                    raise fail(s, pos, "missing argument")
                start = p
                if kind == "*":
                    if s[p] == "*":
                        p += 1
                elif kind == "[":
                    if s[p] == "[":
                        p = balanced(s, p, "[", "]")
                elif kind == "{":
                    p = balanced(s, p, "{", "}") if s[p] == "{" \
                        else token(s, p)
                elif kind == "c":
                    p = s.find("{", token(s, p))
                    if p == -1:
                        raise fail(s, start, "definition without a body")
                elif kind == "f":
                    m = _FI.search(s, p)
                    if not m:
                        raise fail(s, start, "\\iffalse without \\fi")
                    p = m.end()
                else:                                   # "v"
                    if s[p] == "*":
                        p += 1
                    if p < len(s) and s[p] == "[":
                        p = balanced(s, p, "[", "]")
                    if p >= len(s):
                        raise fail(s, start, "missing argument")
                    if s[p] == "{":
                        p = balanced(s, p, "{", "}")
                    else:
                        close = s.find(s[p], p + 1)
                        if close == -1:
                            raise fail(s, start, "unclosed \\verb")
                        p = close + 1
                spans.append((start, p))
            argnlist = [w.make_node(latexwalker.LatexCharsNode,
                                    parsing_state=parsing_state,
                                    chars=s[a:b], pos=a, len=b - a)
                        if b > a else None for a, b in spans]
            if self.rest:
                more, mpos, mlen = MacroStandardArgsParser(
                    self.rest).parse_args(w, p, parsing_state)
                argnlist += more.argnlist
                p = mpos + mlen
            return (ParsedMacroArgs(argnlist=argnlist, argspec=self.argspec),
                    pos, p - pos)

    macros = [MacroSpec(name, "*[[{") for name in CITE_MACROS]
    macros += [MacroSpec(name, spec) for name, spec in (
        ("part", "*[{"), ("paragraph", "*[{"),   # default db lacks/misspells
        ("caption", "*[{"), ("subcaption", "*[{"), ("captionof", "*{[{"),
        ("subfile", "{"), ("includeonly", "{"), ("bibliographystyle", "{"),
        ("addbibresource", "[{"), ("printbibliography", "["),
        ("pageref", "*{"), ("nameref", "*{"), ("vref", "*{"),
        ("graphicspath", "{"), ("newtheorem", "*{[{["), ("pagestyle", "{"),
        ("thispagestyle", "{"), ("pagenumbering", "{"), ("footnotemark", "["),
        ("affiliation", "[{"), ("affil", "[{"), ("address", "{"),
        ("email", "{"), ("institute", "{"), ("addtolength", "{{"),
        ("addtocounter", "{{"),
        ("code", "{"), ("file", "{"), ("filename", "{"), ("pkg", "{"),
        ("cmd", "{"), ("command", "{"), ("addcontentsline", "{{{"),
    )]
    macros += [MacroSpec(name, args_parser=RawArgs(raw, rest))
               for names, raw, rest in (
                   (("url", "path", "nolinkurl"), "{", ""),
                   (("href",), "{", "{"),
                   (("verb", "lstinline"), "v", ""),
                   (("newcommand", "renewcommand", "providecommand"),
                    "*{[[{", ""),
                   (("newenvironment", "renewenvironment",
                     "provideenvironment"), "*{[[{{", ""),
                   (("DeclareMathOperator",), "*{{", ""),
                   (("def", "gdef", "edef", "xdef"), "c{", ""),
                   (("iffalse",), "f", ""))
               for name in names]
    envs = [EnvironmentSpec(name, args_parser=VerbatimEnv(name))
            for name in VERBATIM_ENVS]
    envs += [EnvironmentSpec(name, spec) for name, spec in (
        ("wrapfigure", "[{[{"), ("wraptable", "[{[{"), ("minipage", "[[[{"),
        ("subfigure", "[{"), ("subtable", "[{"), ("multicols", "{["),
        ("multicols*", "{["), ("tcolorbox", "["), ("adjustbox", "{"))]
    envs += [EnvironmentSpec(name, None, is_math_mode=True)
             for base in ("displaymath", "dmath")
             for name in (base, base + "*")]
    db = latexwalker.get_default_latex_context_db()
    db.add_context_category("researchly", macros=macros, environments=envs,
                            prepend=True)
    _CONTEXT = db
    return db


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------

class _Masker:
    def __init__(self, text: str):
        # pylatexenc fails on a macro whose optional argument would start
        # at end of input (a file ending in `\\`); a harmless `\relax`
        # after the source gives it a token to stop at. Nothing before it
        # moves, and the result is cut back to the source length.
        self.n = len(text)
        self.text = text + "\n\\relax"
        self.out = [c if c == "\n" else " " for c in self.text]
        self.headings: list[Heading] = []
        self.structure: list[StructureItem] = []
        # Each caption and the float or panel whose \label names it; the
        # label may come after the caption, so they are joined at the end.
        self.captions: list[tuple[StructureItem, StructureItem]] = []
        self.code_macros = set(CODE_MACROS)
        # Set after a code macro pylatexenc parsed without arguments (one
        # the preamble defined): its `{...}` follows as a sibling group.
        self.skip_group = False

    def run(self) -> LatexMask:
        from pylatexenc import latexwalker as lw
        self.lw = lw
        walker = lw.LatexWalker(self.text, latex_context=_context(),
                                tolerant_parsing=False)
        # With a \begin{document}, only its body is prose and only it is
        # parsed: the preamble is configuration (and full of definitions
        # pylatexenc need not understand), and nothing after \end{document}
        # is typeset.
        m = _BEGIN_DOCUMENT.search(self.text, 0, self.n)
        if m:
            self.code_macros |= code_macros_in(self.text[:m.start()])
        if m:
            node, _, _ = walker.get_latex_environment(m.start(1), "document")
            nodes = [node]
        else:
            nodes, _, _ = walker.get_latex_nodes()
        self.walk(nodes, prose=True, sink=None)
        for caption, owner in self.captions:
            if caption.label is None:
                caption.label = owner.label
        for item in self.structure:
            item.end = min(item.end, self.n)
        for h in self.headings:
            h.end = min(h.end, self.n) if h.end is not None else None
        self.structure.sort(key=lambda s: s.start)
        return LatexMask("".join(self.out[:self.n]), self.headings,
                         self.structure)

    # -- primitives ---------------------------------------------------------

    def keep(self, a: int, b: int) -> None:
        self.out[a:b] = self.text[a:b]

    def mask(self, a: int, b: int) -> None:
        self.out[a:b] = ["\n" if c == "\n" else " " for c in self.text[a:b]]

    def raw_arg(self, node) -> str:
        """Source text of an argument without its braces."""
        if node is None:
            return ""
        s = self.text[node.pos:node.pos + node.len]
        if s[:1] in "{[" and s[-1:] in "}]":
            s = s[1:-1]
        return " ".join(s.split())

    @staticmethod
    def args(node) -> tuple[list, str]:
        d = node.nodeargd
        if d is None or not d.argnlist:
            return [], ""
        return list(d.argnlist), d.argspec or ""

    # -- dispatch -----------------------------------------------------------

    def walk(self, nodes, prose: bool, sink: Optional[StructureItem]) -> None:
        """`prose` False means inside a float: only captions are kept.
        `sink` is the float or equation that a `\\label` names."""
        lw = self.lw
        for n in nodes:
            if n is None:
                continue
            if self.skip_group:
                if isinstance(n, lw.LatexGroupNode):
                    self.skip_group = False
                    continue                     # the code's argument
                if not (isinstance(n, lw.LatexCharsNode)
                        and not n.chars.strip()):
                    self.skip_group = False
            if isinstance(n, lw.LatexCharsNode):
                if prose:
                    self.keep(n.pos, n.pos + n.len)
            elif isinstance(n, lw.LatexSpecialsNode):
                # `--` and quote ligatures read as punctuation; `~` is a
                # tie (a space) and `&` a column separator.
                if prose and n.specials_chars not in ("~", "&"):
                    self.keep(n.pos, n.pos + n.len)
            elif isinstance(n, lw.LatexGroupNode):
                self.walk(n.nodelist, prose, sink)
            elif isinstance(n, lw.LatexMathNode):
                if n.displaytype == "display":
                    self.structure.append(StructureItem(
                        "equation", n.pos, n.pos + n.len,
                        self.find_label(n.nodelist)))
            elif isinstance(n, lw.LatexMacroNode):
                self.macro(n, prose, sink)
            elif isinstance(n, lw.LatexEnvironmentNode):
                self.environment(n, prose, sink)
            # comments stay masked

    def macro(self, n, prose: bool, sink: Optional[StructureItem]) -> None:
        name = n.macroname
        args, spec = self.args(n)
        end = n.pos + n.len
        if name in HEADING_MACROS:
            if prose and args and args[-1] is not None:
                self.heading(n, args[-1])
            return
        if name in CAPTION_MACROS:
            if args and args[-1] is not None:
                # Captions are prose even inside a float (a typo in one is
                # as visible as anywhere), and are recorded as structure.
                self.walk([args[-1]], True, sink)
                item = StructureItem("caption", n.pos, end)
                self.structure.append(item)
                if sink is not None:
                    self.captions.append((item, sink))
            return
        if name == "label":
            if sink is not None and sink.label is None and args:
                sink.label = self.raw_arg(args[-1]) or None
            return
        if name in CITE_MACROS:
            if prose:
                key = self.raw_arg(args[-1]) if args else ""
                self.structure.append(
                    StructureItem("citation", n.pos, end, key or None))
            return
        if name == "href":
            if len(args) > 1 and args[1] is not None:
                self.walk([args[1]], prose, sink)
            return
        if name in MASK_WHOLE:
            return
        if name in self.code_macros:
            self.skip_group = not args
            return
        if name in ESCAPED_CHARS:
            if prose:
                self.keep(n.pos, n.pos + 2)
            return
        if name in LAST_ARG_ONLY:
            text_args = args[-1:]
        else:
            # Optional `[...]` arguments are options (`\\\\[2pt]`,
            # `\\item[label]`), never checked.
            text_args = [a for a, kind in zip(args, spec) if kind == "{"]
        self.walk(text_args, prose, sink)

    def heading(self, n, title_node) -> None:
        # Keep the title to read it (so `\\section{\\emph{Methods}}` reads
        # "Methods"), then mask the whole command: headings are not sentences.
        self.walk([title_node], True, None)
        a, b = title_node.pos, title_node.pos + title_node.len
        title = " ".join("".join(self.out[a:b]).split())
        self.mask(n.pos, n.pos + n.len)
        if title:
            self.headings.append(Heading(n.pos, title, classify_heading(title),
                                         end=n.pos + n.len))

    def environment(self, n, prose: bool,
                    sink: Optional[StructureItem]) -> None:
        name = n.environmentname
        if name in VERBATIM_ENVS:
            return
        if name.rstrip("*") in MATH_ENVS:
            if name.rstrip("*") != "math":
                self.structure.append(StructureItem(
                    "equation", n.pos, n.pos + n.len,
                    self.find_label(n.nodelist)))
            return
        floating = name in FIGURE_ENVS or name in TABLE_ENVS
        if floating and prose:
            kind = "figure" if name in FIGURE_ENVS else "table"
            item = StructureItem(kind, n.pos, n.pos + n.len)
            self.structure.append(item)
            self.walk(n.nodelist, False, item)
            return
        if not prose and (floating or name in SUBFLOAT_ENVS):
            # A panel: its \label names its own caption, not the float.
            # The panel is not recorded as structure of its own.
            panel = StructureItem(name, n.pos, n.pos + n.len)
            self.walk(n.nodelist, False, panel)
            return
        if name in NONPROSE_ENVS:
            if prose and name in TABULAR_ENVS:
                self.structure.append(StructureItem(
                    "table", n.pos, n.pos + n.len,
                    self.find_label(n.nodelist)))
            return
        if name == "abstract" and prose:
            self.headings.append(Heading(n.pos, "Abstract", "abstract",
                                         end=n.pos))
        # `center` and friends are transparent: a \label inside one still
        # names the enclosing float.
        self.walk(n.nodelist, prose, sink)

    def find_label(self, nodes) -> Optional[str]:
        lw = self.lw
        for n in nodes or []:
            if n is None:
                continue
            if isinstance(n, lw.LatexMacroNode):
                if n.macroname == "label":
                    args, _ = self.args(n)
                    return self.raw_arg(args[-1]) if args else None
                found = self.find_label(self.args(n)[0])
            elif isinstance(n, (lw.LatexGroupNode, lw.LatexEnvironmentNode,
                                lw.LatexMathNode)):
                found = self.find_label(n.nodelist)
            else:
                found = None
            if found:
                return found
        return None


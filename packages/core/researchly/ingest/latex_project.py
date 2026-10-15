"""Overleaf project (.zip) -> one Document (docs/s2-design.md §4).

The main file (the one with `\\documentclass`) is read with every
`\\input`, `\\include` and `\\subfile` expanded in place, in reading order,
into ONE text: the parent up to and including the command, then the child,
then the rest of the parent. The command stays in the parent's segment and
is masked like any macro. `Document.segments` maps every span of the
combined text back to its file and offset, so a suggestion can be shown in
`chapters/methods.tex`, not "character 48,112 of a file that does not
exist".

When several files have a `\\documentclass` of their own (a cover letter
beside the paper), one is chosen (choose_main) and the Document lists them
all (`main_candidates`) with the one read (`main_file`); the writer can
name another (`load_zip(..., main_file=...)`).

Only `.tex` members are read; images, .bib files and nested zips are
ignored. A missing or non-UTF-8 input, a cycle or nesting deeper than
MAX_DEPTH is skipped with a warning rather than failing the whole project.
TeX is never executed and nothing is extracted to disk.

Known approximation: TeX ends every input file with an implicit end of
line; here the child's text is joined to the parent's directly (inserting a
character would break the segment map). It only matters when text follows
`\\input{x}` on the same line and x ends in a `%` comment with no final
newline: that text is then masked as part of the comment.
"""

from __future__ import annotations

import posixpath
import re

from ..document import Document, Segment
from . import MAX_TEXT_CHARS, IngestError, source_position
from ._zip import open_zip, read_member

MAX_DEPTH = 10

# `\input{x}`, `\include{x}`, `\subfile{x}`. Not `\includegraphics{` (a
# letter follows "include") and not the brace-less TeX primitive `\input x`,
# which Overleaf projects do not use for chapters.
_INPUT = re.compile(r"\\(input|include|subfile)\s*\{([^{}\n]*)\}")
_DOCCLASS = re.compile(
    r"^[^%\n]*\\documentclass\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}", re.M)
_COMMENT = re.compile(r"(?<!\\)%")


def load_zip(filename: str, data: bytes,
             main_file: str | None = None) -> Document:
    """`main_file` names the project's main .tex file when the writer chose
    one (the website's "Main file" choice, the CLI's --main); otherwise it
    is found (choose_main)."""
    zf, members = open_zip(data, ".zip")
    # A .tex that is not UTF-8 is None: an old template nobody \inputs must
    # not sink the project, so it only matters if it is actually read.
    files: dict[str, str | None] = {}
    for name, info in members.items():
        if name.lower().endswith(".tex"):
            try:
                files[name] = read_member(zf, info, ".zip").decode(
                    "utf-8-sig")
            except UnicodeDecodeError:
                files[name] = None
    candidates = main_candidates(files)
    if main_file:
        main = chosen_main(files, main_file)
    else:
        main, _ = choose_main(files)
    text, segments, warnings, skipped = expand(files, main)

    def locate(offset: int) -> str:
        path, line, _ = source_position(segments, text, offset)
        return f"line {line} of {path}"

    doc = Document.from_text(text, "latex", locate=locate)
    doc.path = filename
    doc.segments = segments
    doc.warnings = warnings + doc.warnings
    # Several files could be the main one: the response lists them and the
    # one read, so the writer can choose another (Codex review #5).
    doc.main_file = main
    doc.main_candidates = candidates
    if skipped:
        doc.not_checked = {**doc.not_checked, "skipped_files": skipped}
    return doc


def main_candidates(files: dict[str, str | None]) -> list[str]:
    """Every file that starts a document of its own (a real
    `\\documentclass`), sorted, when there is more than one; else []."""
    roots = sorted(n for n, t in files.items() if _is_root(t))
    return roots if len(roots) > 1 else []


def chosen_main(files: dict[str, str | None], wanted: str) -> str:
    """The .tex file the writer named as the main one."""
    name = posixpath.normpath(wanted.replace("\\", "/").strip())
    if name in files:
        if files[name] is None:
            raise _not_utf8()
        return name
    raise IngestError("unreadable_file",
                      f"This project has no .tex file called "
                      f"{_shown(wanted)}. Choose one of its .tex files as "
                      "the main file.")


def _is_root(text: str | None) -> bool:
    m = _DOCCLASS.search(text) if text is not None else None
    return bool(m) and m.group(1).strip() != "subfiles"


# Files that carry their own \documentclass but are not the paper: a cover
# letter or rebuttal kept beside the manuscript is common on Overleaf, and
# refusing such projects outright (P29 bench: 2 of 18 real projects) helped
# nobody.
_SIDE_DOCUMENT = re.compile(
    r"cover|letter|response|rebuttal|reply|reviewer|supp|appendix|"
    r"slides?|poster|highlights|graphical|abstract_only", re.IGNORECASE)
_INCLUDES = re.compile(r"\\(?:input|include|subfile)\s*\{")


def find_main(files: dict[str, str | None]) -> str:
    return choose_main(files)[0]


def choose_main(files: dict[str, str | None]) -> tuple[str, str | None]:
    """(main file, note for the user or None). See find_main_strict for the
    rules; when they leave several candidates, choose rather than refuse:
    drop side documents (cover letter, response to reviewers, slides),
    then prefer the file that \\inputs the most others, then the longest,
    and say which file was checked."""
    try:
        return find_main_strict(files), None
    except IngestError as e:
        roots = getattr(e, "candidates", None)
        if not roots:
            raise
    pool = [n for n in roots
            if not _SIDE_DOCUMENT.search(posixpath.basename(n))] or roots
    best = max(pool, key=lambda n: (len(_INCLUDES.findall(files[n] or "")),
                                    len(files[n] or ""), -n.count("/"), n))
    others = sorted(n for n in roots if n != best)
    note = (f"This project has several main .tex files; Researchly checked "
            f"{best} (not {', '.join(others[:3])}"
            f"{'…' if len(others) > 3 else ''}). To check another, name it "
            "main.tex or upload it on its own.")
    return best, note


def find_main_strict(files: dict[str, str | None]) -> str:
    """The file with a real `\\documentclass` (a `subfiles` chapter names
    the main file as its class, so it does not count). Several: prefer
    main.tex, then the only one at the top level. None: the only .tex."""
    if not files:
        raise IngestError("unreadable_file",
                          "This .zip has no .tex files. Download the project "
                          "from Overleaf (Menu, Download, Source) and upload "
                          "that .zip.")
    roots = [name for name, text in files.items() if _is_root(text)]
    if not roots and list(files.values()) == [None]:
        raise _not_utf8()
    if len(roots) == 1:
        return roots[0]
    if roots:
        shallow = min(name.count("/") for name in roots)
        top = [n for n in roots if n.count("/") == shallow]
        mains = [n for n in top if posixpath.basename(n).lower() == "main.tex"]
        if len(mains) == 1:
            return mains[0]
        if len(top) == 1:
            return top[0]
    elif len(files) == 1:
        return next(iter(files))
    err = IngestError("unreadable_file",
                      "Researchly could not tell which .tex file is the main "
                      "one. Name it main.tex, or upload that file on its own.")
    err.candidates = roots          # choose_main picks among these
    raise err


def _not_utf8() -> IngestError:
    return IngestError("unreadable_file",
                       "The main .tex file in the .zip is not UTF-8 text. "
                       "Save it as UTF-8 (Overleaf does by default) and "
                       "upload the project again.")


def expand(files: dict[str, str | None],
           main: str) -> tuple[str, list[Segment], list[str], int]:
    """(combined text, segments, warnings, inputs skipped unread). A cycle
    is warned about but not counted as skipped: its file is read once."""
    parts: list[str] = []
    segments: list[Segment] = []
    warnings: list[str] = []
    skipped: set[str] = set()
    total = 0
    root = posixpath.dirname(main)

    def emit(path: str, src: str, a: int, b: int) -> None:
        nonlocal total
        if b <= a:
            return
        # Checked as we go: a file included ten times, each including ten
        # more, would otherwise build gigabytes before any length check.
        if total + (b - a) > MAX_TEXT_CHARS:
            raise IngestError("payload_too_large",
                              f"This project has more than {MAX_TEXT_CHARS:,}"
                              " characters of text once its files are "
                              "combined. Check one chapter at a time.")
        parts.append(src[a:b])
        segments.append(Segment(path=path, start=total, end=total + b - a,
                                source_start=a))
        total += b - a

    def warn(message: str) -> None:
        if message not in warnings:
            warnings.append(message)

    def visit(path: str, stack: list[str]) -> None:
        src = files[path]
        pos = 0
        for m in _INPUT.finditer(src):
            line_start = src.rfind("\n", 0, m.start()) + 1
            if _COMMENT.search(src, line_start, m.start()):
                continue                   # `% \input{old-draft}`
            emit(path, src, pos, m.end())
            pos = m.end()
            cmd, target = m.group(1), _shown(m.group(2))
            child = resolve(files, m.group(2).strip(), path, root)
            if child is None:
                skipped.add("?" + m.group(2).strip())
                warn(f"\\{cmd}{{{target}}} was not found in the .zip (or is "
                     "not a .tex file); skipped.")
            elif files[child] is None:
                skipped.add(child)
                warn(f"\\{cmd}{{{target}}} is not UTF-8 text; skipped. Save "
                     "it as UTF-8 to have it checked.")
            elif child in stack:
                warn(f"\\{cmd}{{{target}}} would include a file that is "
                     "already being read (a cycle); skipped.")
            elif len(stack) > MAX_DEPTH:
                skipped.add(child)
                warn(f"\\{cmd}{{{target}}} is nested more than {MAX_DEPTH} "
                     "files deep; skipped.")
            else:
                visit(child, stack + [child])
        emit(path, src, pos, len(src))

    if files[main] is None:
        raise _not_utf8()
    visit(main, [main])
    return "".join(parts), segments, warnings, len(skipped)


def resolve(files: dict[str, str], target: str, including: str,
            root: str) -> str | None:
    """LaTeX resolves inputs against the main file's directory; Overleaf
    users also write them relative to the including file. Try both, with
    `.tex` added first as TeX does. Never outside the project."""
    name = target.replace("\\", "/")
    if not name or name.startswith("/") or re.match(r"[A-Za-z]:", name):
        return None
    names = [name] if name.lower().endswith(".tex") else [name + ".tex", name]
    for base in (root, posixpath.dirname(including)):
        for n in names:
            p = posixpath.normpath(posixpath.join(base, n))
            if p == ".." or p.startswith("../"):
                continue
            if p in files:
                return p
    return None


def _shown(target: str) -> str:
    """An input name as quoted in a warning: printable and short."""
    t = "".join(c for c in target.strip() if c.isprintable())
    return t if len(t) <= 80 else t[:77] + "..."

"""Genre-native units (Codex review #4, 2026-10-15): the parts a policy
brief and a response to reviewers are made of, which are not a research
paper's sections.

- A **policy brief** is read as Context, Evidence, Options and
  Recommendations (after Young & Quinn's parts of a policy paper; see
  sources.py). A unit is recognised from a heading, or in plain text from a
  line of its own that names it ("Policy options"). The units feed the
  narrative map only: the checks keep reading the brief's prose as argued
  text (profiles.py), so recognising a unit never changes a suggestion.
- A **response to reviewers** is read as reviewer-comment units: a comment
  ("Reviewer 1, Comment 2", "R1.2", "Comment 3" under a "Reviewer 2" line,
  or a quoted comment) and the reply after it ("Response:", or the
  paragraph after a quoted comment). The units are described, never judged
  (Codex review N5): the map lists each comment beside its reply and says
  nothing about whether the reply is good enough.

Everything here is deterministic and works on `Document.original` with
code-point offsets, so each unit can be shown in the text.
"""

from __future__ import annotations

import re
from typing import Optional

# --- policy brief ------------------------------------------------------------

POLICY_UNITS = ("context", "evidence", "options", "recommendations")
UNIT_LABELS = {"context": "Context", "evidence": "Evidence",
               "options": "Options", "recommendations": "Recommendations"}

# Checked in this order, so "Options and recommendations" is the
# recommendations unit and "Evidence on the options" the options unit.
_UNIT_WORDS = (
    ("recommendations", r"recommendations?|what (?:should|must|needs to) be "
                        r"done|calls? to action|next steps|actions? "
                        r"(?:needed|required|for)"),
    ("options", r"(?:policy )?options?|alternatives|choices|policy "
                r"responses?|approaches|scenarios"),
    ("evidence", r"evidence|findings|what we know|what the (?:data|research|"
                 r"evidence) (?:say|says|show|shows)|key facts|the data"),
    ("context", r"context|background|the problem|problem statement|"
                r"the issue|why (?:this|it) matters|the situation|"
                r"introduction|overview"),
)
_NUMBER = re.compile(r"^\s*(?:\d+(?:\.\d+)*|[ivxlc]+|[a-z])[.:)]?\s+",
                     re.IGNORECASE)
# A plain-text line that is only a unit's name ("Policy options", "3.
# Recommendations"): short, no closing full stop.
_LINE = re.compile(r"^[ \t]*([^\n]{3,60}?)[ \t]*$", re.MULTILINE)


def unit_of(heading: str) -> Optional[str]:
    """The policy-brief unit a heading names, or None."""
    text = _NUMBER.sub("", " ".join(heading.split())).strip(" :.-").lower()
    if not text or len(text.split()) > 8:
        return None
    for unit, words in _UNIT_WORDS:
        if re.search(r"\b(?:" + words + r")\b", text):
            return unit
    return None


def policy_units(document) -> list:
    """[(unit, start, end, heading)] in document order: each unit runs from
    its heading to the next heading or unit line. Plain text records only
    IMRaD headings, so there a line of its own naming a unit counts."""
    marks = []                          # (start, body_start, unit, text)
    for h in document.headings:
        end = h.end if h.end is not None else document.original.find(
            "\n", h.start)
        end = len(document.original) if end < 0 else end
        marks.append((h.start, end, unit_of(h.text), h.text.strip()))
    if document.kind == "plain":
        taken = {m[0] for m in marks}
        for m in _LINE.finditer(document.original):
            line = m.group(1)
            if m.start(1) in taken or line.rstrip().endswith((".", ",", ";")):
                continue
            unit = unit_of(line)
            if unit and _alone(document.original, m.start(), m.end()):
                marks.append((m.start(1), m.end(1), unit, line.strip()))
    marks.sort()
    out = []
    for i, (start, body, unit, text) in enumerate(marks):
        if unit is None:
            continue
        end = marks[i + 1][0] if i + 1 < len(marks) else len(
            document.original)
        out.append((unit, body, end, text))
    return out


def _alone(text: str, start: int, end: int) -> bool:
    """A heading line stands alone: the line before it is blank (or there
    is none), so a list item or a wrapped sentence is not a heading."""
    before = text[:start]
    if not before.strip():
        return True
    return before.rstrip(" \t").endswith("\n\n") or \
        re.search(r"\n[ \t]*\n[ \t]*$", before) is not None


# --- response to reviewers ---------------------------------------------------

_REVIEWER = r"(?:reviewer|referee)\s*#?\s*(\d+|[ivx]+|[a-c])\b"
_COMMENT = r"(?:comment|point|query|remark|issue|concern)\s*#?\s*(\d+(?:\.\d+)?)"
# "Reviewer 1, Comment 2: ..." / "Reviewer 1 - Point 2"
_BOTH = re.compile(r"^[ \t]*\**" + _REVIEWER + r"\s*[,.:;\-–]?\s*"
                   + _COMMENT + r"\b\**[ \t]*[.:)\-–]?[ \t]*",
                   re.IGNORECASE | re.MULTILINE)
# "R1.2", "R1C2", "R1-C2", "R2.1:"
_SHORT = re.compile(r"^[ \t]*\**R(\d+)[ \t]*[.\-]?[ \t]*C?(\d+)\b\**[ \t]*"
                    r"[.:)\-–]?[ \t]*", re.MULTILINE)
# "Reviewer 2" (or "Reviewer #2:", "Comments from Referee 2") on its own line
_HEADER = re.compile(r"^[ \t]*\**(?:comments? (?:from|of|by) )?" + _REVIEWER
                     + r"\**[ \t]*(?:comments?)?[ \t]*[:.]?[ \t]*$",
                     re.IGNORECASE | re.MULTILINE)
# "Comment 3:" with the reviewer from the last header
_ALONE = re.compile(r"^[ \t]*\**" + _COMMENT + r"\b\**[ \t]*[.:)\-–]?"
                    r"[ \t]*", re.IGNORECASE | re.MULTILINE)
# A quoted comment: "> ..." or a line opening with a quotation mark.
_QUOTED = re.compile(r"^[ \t]*(?:>|“|\")[ \t]*", re.MULTILINE)
# Where the reply starts: "Response:", "Reply:", "Our response:",
# "Author response:", "Authors’ reply -".
_REPLY = re.compile(r"^[ \t]*\**(?:our |the )?(?:authors?(?:’|')?s?"
                    r"(?:’|')? )?(?:response|reply|answer)\b\**[ \t]*"
                    r"[:.\-–][ \t]*", re.IGNORECASE | re.MULTILINE)


def _roman(token: str) -> str:
    roman = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
             "viii": 8, "ix": 9, "x": 10, "a": 1, "b": 2, "c": 3}
    return str(roman.get(token.lower(), token))


_BLOCK = re.compile(r"\S(?:.*\S)?(?:\n[ \t]*\S.*)*")


def _blocks(text: str) -> list:
    """(start, end) of each paragraph: lines between blank lines."""
    return [(m.start(), m.end()) for m in _BLOCK.finditer(text)]


def _comment_mark(text: str, pos: int):
    """(reviewer, comment, end of the marker) when a comment marker opens
    the line at `pos`, else None."""
    for rx, has_reviewer in ((_BOTH, True), (_SHORT, True), (_ALONE, False)):
        m = rx.match(text, pos)
        if m:
            if has_reviewer:
                who = _roman(m.group(1)) if rx is _BOTH else m.group(1)
                return who, m.group(2), m.end()
            return None, m.group(1), m.end()
    return None


def reviewer_units(document) -> list:
    """[{"reviewer", "comment", "label", "comment_span", "reply_span"}] in
    document order. Spans are (start, end) into `document.original`;
    `reply_span` is None when no reply text follows the comment.

    Read paragraph by paragraph: a "Reviewer 2" line sets the reviewer; a
    comment marker or a quoted paragraph opens a unit; "Response:" (on a
    line of its own or opening one) starts its reply, and so does the
    first unquoted paragraph after a quoted comment. Text before the first
    unit (thanks, a summary of changes) belongs to no unit."""
    text = document.original
    units: list = []
    reviewer = ""
    counts: dict = {}
    cur: Optional[dict] = None

    def close():
        nonlocal cur
        if cur is not None:
            c = _clip(text, cur["c0"], cur["c1"])
            r = _clip(text, cur["r0"], cur["r1"]) if cur["r0"] is not None \
                else None
            if c is not None:
                units.append({"reviewer": cur["reviewer"],
                              "comment": cur["comment"],
                              "label": _label(cur["reviewer"], cur["comment"]),
                              "comment_span": c, "reply_span": r})
        cur = None

    def open_unit(who, number, c0, c1, quoted):
        nonlocal cur
        close()
        who = who or reviewer
        key = who or "-"
        counts[key] = counts.get(key, 0) + 1
        cur = {"reviewer": who, "comment": number or str(counts[key]),
               "c0": c0, "c1": c1, "r0": None, "r1": None,
               "quoted": quoted}

    def reply_in(a: int, b: int):
        """A reply marker at the start of a line inside [a, b)."""
        for m in _REPLY.finditer(text, a, b):
            if m.start() == a or text[m.start() - 1] == "\n":
                return m
        return None

    for a, b in _blocks(text):
        head = _HEADER.match(text, a)
        if head and head.end() >= b - 1:
            close()
            reviewer = _roman(head.group(1))
            continue
        if head:                      # "Reviewer 2" then the comment below
            close()
            reviewer = _roman(head.group(1))
            a = text.find("\n", a, b) + 1 or b
            if a >= b:
                continue
        mark = _comment_mark(text, a)
        if mark is not None:
            who, number, body = mark
            open_unit(who, number, body, b, False)
            rep = reply_in(body, b)
            if rep is not None:
                cur["c1"], cur["r0"], cur["r1"] = rep.start(), rep.end(), b
            continue
        if _QUOTED.match(text, a):
            if cur is not None and cur["quoted"] and cur["r0"] is None:
                cur["c1"] = b         # the quotation goes on
            else:
                open_unit(None, None, _QUOTED.match(text, a).end(), b, True)
            continue
        rep = reply_in(a, b)
        if rep is not None and rep.start() == a:
            if cur is not None and cur["r0"] is None:
                cur["r0"], cur["r1"] = rep.end(), b
            elif cur is not None:
                cur["r1"] = b
            continue
        if cur is None:
            continue
        if cur["r0"] is not None:
            cur["r1"] = b             # the reply goes on
        elif cur["quoted"]:
            cur["r0"], cur["r1"] = a, b
        else:
            cur["c1"] = b             # a numbered comment goes on
    close()
    return units


def _clip(text: str, start: int, end: int) -> Optional[tuple]:
    while start < end and text[start] in " \t\n\"\u201c>*":
        start += 1
    while end > start and text[end - 1] in " \t\n*":
        end -= 1
    return (start, end) if end > start else None


def _label(reviewer: str, comment: str) -> str:
    if reviewer:
        return f"Reviewer {reviewer}, comment {comment}"
    return f"Comment {comment}"

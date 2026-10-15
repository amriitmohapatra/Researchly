"""UTF-16 offsets, converted once at the edge (S4d R3).

The engine counts in Unicode code points (Python `str` indices). Word,
browsers, macOS Accessibility and Windows UI Automation all count in UTF-16
code units, where a character outside the Basic Multilingual Plane (an
emoji, a mathematical letter such as U+1D445) takes two units. Combining
marks are code points of their own in both systems, so only astral
characters move an offset.

The contract's convention: `start`/`end` are code points, `begin`/`end` on a
live suggestion (and `begin`/`end` beside a `span`) are UTF-16 units.
"""

from __future__ import annotations

import hashlib
from bisect import bisect_left
from typing import List


def utf16_len(text: str) -> int:
    """Length of `text` in UTF-16 code units."""
    return len(text) + sum(1 for c in text if ord(c) > 0xFFFF)


class Utf16Index:
    """Code-point offset -> UTF-16 offset for one text, in O(log n) per
    lookup after one pass. Text without astral characters (the usual case)
    costs one scan and then nothing."""

    __slots__ = ("_astral", "_len")

    def __init__(self, text: str):
        self._astral: List[int] = [i for i, c in enumerate(text)
                                   if ord(c) > 0xFFFF]
        self._len = len(text)

    def __call__(self, offset: int) -> int:
        offset = max(0, min(offset, self._len))
        if not self._astral:
            return offset
        return offset + bisect_left(self._astral, offset)


def to_utf16(text: str, offset: int) -> int:
    """One code-point offset into `text` as a UTF-16 offset."""
    return Utf16Index(text)(offset)


def live_id(rule_id: str, paragraph_id: str, begin: int, end: int,
            flagged: str) -> str:
    """A live suggestion's id: opaque, short and stable.

    The same rule on the same range of the same words in the same
    paragraph gets the same id on every check, so a client can keep a
    writer's choice (dismissed, open card) across re-checks. It is a hash:
    the flagged words are never readable from it. Fields are joined with
    U+001F so ("A1", "2…") and ("A", "12…") cannot collide."""
    raw = "\x1f".join((rule_id, paragraph_id, str(begin), str(end), flagged))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

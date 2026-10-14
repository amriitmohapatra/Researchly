"""Context-aware ranking of spelling suggestions: a noisy-channel model.

The classic design (Kernighan, Church & Gale 1990; Brill & Moore 2000),
which keyboard autocorrect engines also use (research/05). For a typed word
w and a candidate c:

    score(c) = error(w | c) + log P(c | previous word) + log P(next word | c)

* **error(w | c)**: how likely the writer was to type w when meaning c. A
  table of character edits with one letter of context, learned from openly
  licensed misspelling pairs (``data/spell_errors.json``, built by
  ``ml/tools/build_spell_errors.py``); without it, a hand-set model of the
  commonest slips (transposed letters, a doubled or undoubled consonant, a
  vowel for a vowel) is used.
* **P(c | context)**: unigram and bigram counts from SymSpell's own English
  dictionaries (symspellpy, MIT): "infact" in "infact, the rate" is "in
  fact", not "infant".

Candidates come from SymSpell (edit distance ≤ 2), the correctly inflected
form of a misinflected word (spelling.reinflect: "happend" → "happened"),
and two-word splits of run-together words ("inspite" → "in spite") that the
bigram list confirms.

Nothing here rewrites text: it orders the suggestions a card offers, and the
writer decides (CLAUDE.md #1).
"""

from __future__ import annotations

import json
import math
import threading
from pathlib import Path

from . import spelling

_LOCK = threading.Lock()
_BIGRAMS: dict[tuple[str, str], int] | None = None
_ERRORS: dict | None = None

ERRORS_FILE = Path(__file__).parent / "data" / "spell_errors.json"

# Hand-set log-probabilities of one edit, used when no learned table is
# present. Ordered by how often each kind of slip appears in published
# misspelling studies (Damerau 1964; Kukich 1992): most misspellings are one
# edit, and transpositions and doubling slips are the cheapest.
DEFAULT_COSTS = {
    "transpose": -2.0,
    "double": -1.8,        # a letter typed twice, or a double typed once
    "vowel": -2.5,         # one vowel for another: "seperate"
    "delete": -3.5,
    "insert": -3.5,
    "substitute": -4.0,
    "space": -2.5,         # two words run together: "inspite"
}
_VOWELS = frozenset("aeiou")

# How much the error model counts against the language model. Set on the
# development split by ml/eval/spelling_bench.py; see the log entry.
ERROR_WEIGHT = 1.0
# The writer's ending says which form they meant: "happend" is "happened",
# not the more frequent "happen". log-odds credited to spelling.reinflect.
INFLECTION_BONUS = 2.0
BACKOFF = math.log(0.4)    # stupid backoff (Brants et al. 2007)


# --- language model ----------------------------------------------------------

def bigrams() -> dict[tuple[str, str], int]:
    """SymSpell's English bigram counts (243,342 pairs), loaded once."""
    global _BIGRAMS
    with _LOCK:
        if _BIGRAMS is None:
            import importlib.resources as ir
            table: dict[tuple[str, str], int] = {}
            ref = (ir.files("symspellpy")
                   / "frequency_bigramdictionary_en_243_342.txt")
            with ir.as_file(ref) as p:
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) == 3 and parts[2].isdigit():
                            table[(parts[0], parts[1])] = int(parts[2])
            _BIGRAMS = table
    return _BIGRAMS


def _total() -> float:
    return float(spelling.get_sym().N or 1)


def log_unigram(word: str) -> float:
    """log P(word); a phrase scores as its first word plus the bigram."""
    parts = word.split()
    if len(parts) == 2:
        return log_unigram(parts[0]) + log_next(parts[0], parts[1])
    count = spelling.get_sym().words.get(word, 0)
    return math.log((count + 1) / _total())


def log_next(prev: str, word: str) -> float:
    """log P(word | prev) with stupid backoff to the unigram."""
    first = word.split()[0]
    pair = bigrams().get((prev, first))
    prev_count = spelling.get_sym().words.get(prev, 0)
    if pair and prev_count:
        # The two count lists come from different corpora, so a pair can
        # outnumber its first word; a probability stays at most 1.
        return min(0.0, math.log(pair / prev_count))
    return BACKOFF + log_unigram(first)


def log_context(cand: str, prev: str | None, nxt: str | None) -> float:
    """log P(cand | prev) + log P(nxt | cand), or log P(cand) alone."""
    score = log_next(prev, cand) if prev else log_unigram(cand)
    if nxt:
        last = cand.split()[-1]
        score += log_next(last, nxt)
    return score


# --- error model -------------------------------------------------------------

def _learned() -> dict:
    global _ERRORS
    if _ERRORS is None:
        try:
            _ERRORS = json.loads(ERRORS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _ERRORS = {}
    return _ERRORS


def edits(typed: str, intended: str) -> list[tuple[str, str, str]]:
    """The character edits that turn the intended word into the typed one,
    from an optimal-string-alignment alignment. Each edit is (kind, from,
    to) with one letter of left context in "from" ("^" at the start), the
    form the learned table is keyed on."""
    a, b = "^" + intended, "^" + typed
    n, m = len(a), len(b)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] \
                    and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    out: list[tuple[str, str, str]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1] \
                and a[i - 1] != b[j - 1] and d[i][j] == d[i - 2][j - 2] + 1:
            out.append(("transpose", a[i - 2:i], b[j - 2:j]))
            i, j = i - 2, j - 2
        elif i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + \
                (0 if a[i - 1] == b[j - 1] else 1):
            if a[i - 1] != b[j - 1]:
                out.append(("substitute", a[i - 2:i], a[i - 2] + b[j - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            out.append(("delete", a[i - 2:i], a[i - 2]))
            i -= 1
        else:
            out.append(("insert", a[i - 1], a[i - 1] + b[j - 1]))
            j -= 1
    return out[::-1]


def _default_cost(kind: str, src: str, dst: str) -> float:
    if kind == "transpose":
        return DEFAULT_COSTS["transpose"]
    if kind == "insert" and dst[-1] == " ":
        return DEFAULT_COSTS["space"]
    if kind == "insert" and len(dst) == 2 and dst[0] == dst[1]:
        return DEFAULT_COSTS["double"]
    if kind == "delete" and len(src) == 2 and src[0] == src[1]:
        return DEFAULT_COSTS["double"]
    if kind == "substitute" and src[-1] in _VOWELS and dst[-1] in _VOWELS:
        return DEFAULT_COSTS["vowel"]
    return DEFAULT_COSTS[kind]


def log_error(typed: str, intended: str) -> float:
    """log P(typed | intended): the sum of its edits' log-probabilities."""
    table = _learned().get("edits", {})
    floor = _learned().get("floor")
    total = 0.0
    for kind, src, dst in edits(typed, intended):
        key = f"{kind}|{src}|{dst}"
        if key in table:
            total += table[key]
        elif floor is not None:
            # an edit the training pairs never showed: rarer than any seen
            total += min(floor, _default_cost(kind, src, dst))
        else:
            total += _default_cost(kind, src, dst)
    return total


# --- candidates and ranking ----------------------------------------------------

def split_candidates(word: str) -> list[str]:
    """Two known words run together, confirmed by the bigram list:
    "inspite" → "in spite", "eachother" → "each other". A split the bigram
    list has never seen ("modelfit" → "model fit") is not offered: the
    joined form is as likely to be a term."""
    out = []
    table = bigrams()
    for i in range(1, len(word)):
        left, right = word[:i], word[i:]
        if len(right) < 2 or (len(left) < 2 and left not in ("a", "i")):
            continue
        if (left, right) in table and spelling.is_known(left) \
                and spelling.is_known(right):
            out.append(f"{left} {right}")
    return out


def candidates(word: str) -> list[str]:
    out: list[str] = []
    fixed = spelling.reinflect(word)
    if fixed:
        out.append(fixed)
    for cand, _dist in spelling.suggest_with_distance(word, top_n=8):
        if cand not in out:
            out.append(cand)
    for phrase in split_candidates(word):
        if phrase not in out:
            out.append(phrase)
    return out


def rank(word: str, prev: str | None = None, nxt: str | None = None,
         top_n: int = 3) -> list[tuple[str, float]]:
    """Candidates for a misspelt (lower-case) word, best first, with their
    noisy-channel scores (natural log; higher is better)."""
    scored = []
    intended = spelling.reinflect(word)
    for cand in candidates(word):
        typed_form = word
        target = cand.replace(" ", "") if " " in cand else cand
        err = log_error(typed_form, target)
        if " " in cand:
            err += DEFAULT_COSTS["space"]
        bonus = INFLECTION_BONUS if cand == intended else 0.0
        scored.append((cand, ERROR_WEIGHT * err + bonus
                       + log_context(cand, prev, nxt)))
    scored.sort(key=lambda t: -t[1])
    return scored[:top_n]

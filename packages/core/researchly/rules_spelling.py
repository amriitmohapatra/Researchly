"""S001 — the basic spelling layer (SymSpell-backed), precision-guarded.

This is the 'commodity' tier deliberately deferred in Phase 1 and added
once a maintained open-source component could be integrated rather than
rebuilt (symspellpy, MIT). Grammar-proper (agreement, articles) is the
optional LanguageTool tier in rules_grammar.py.

Implementation note: words are scanned with a regex over the masked text
rather than spaCy tokens — the tokenizer SPLITS some typos ("thiss" →
"this"+"s"), which would hide them from a token-based scan.
"""

from __future__ import annotations

import re
from collections import Counter

from . import lexicons as lx
from . import spelling
from .document import Document
from .engine import Category, Suggestion, rule

MIN_LEN = 3
WORD_RX = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def _sentence_start(text: str, start: int) -> bool:
    """Is this word the first of a sentence (or of the text/line)?"""
    i = start - 1
    while i >= 0 and text[i] in " \t":
        i -= 1
    return i < 0 or text[i] in ".!?\n"


def _in_url_like(text: str, start: int, end: int) -> bool:
    prev = text[start - 1] if start > 0 else " "
    nxt = text[end] if end < len(text) else " "
    if prev in "@/_-" or nxt in "@/_":
        return True
    # "example.com" — a dot immediately followed by another letter
    if nxt == "." and end + 1 < len(text) and text[end + 1].isalpha():
        return True
    return False


@rule("S001", "spelling", Category.CORRECTION,
      "Possible misspelling (SymSpell dictionary + scientific lexicon).",
      "Basic spelling against a frequency dictionary plus a scientific "
      "lexicon (seroprevalence, covariates, nowcasting… are not errors "
      "here). Proper nouns, acronyms, UK/US variants, and terms you use "
      "repeatedly are skipped. False alarm on your terminology? "
      "`researchly dict add <word>` teaches it your word permanently "
      "(stored locally in ~/.researchly/dictionary.txt).",
      source="symspellpy",
      tier="spelling", fix_safety="review")
def s001_spelling(doc, document: Document):
    text = document.masked
    domain = spelling.domain_terms()
    cfg_words: list[str] = getattr(document, "extra_dictionary", []) or []
    user = spelling.user_dictionary(cfg_words)

    words = list(WORD_RX.finditer(text))
    # words the author uses 3+ times are their vocabulary, not typos
    counts = Counter(m.group(0).lower() for m in words)

    for m in words:
        w = m.group(0)
        if len(w) < MIN_LEN or "'" in w:
            continue
        if w.isupper():                       # acronyms → F601's business
            continue
        lower = w.lower()
        if lower in domain or lower in user:
            continue
        if w.upper() in lx.ACRONYM_ALLOWLIST:
            continue
        if counts[lower] >= 3:
            continue
        if _in_url_like(text, m.start(), m.end()):
            continue
        # "mis-ordered", "non-zero", "co-circulating": a prefix before a
        # hyphen is half of a compound, not a word on its own.
        if text[m.end():m.end() + 1] == "-" and \
                lower in spelling.DERIVATIONAL_PREFIXES:
            continue
        capitalized = w[0].isupper()
        if capitalized and not _sentence_start(text, m.start()):
            continue                          # likely a proper noun
        if spelling.known_with_fallbacks(lower):
            continue

        scored = spelling.suggest_with_distance(lower, top_n=3)
        # A capitalized unknown at a sentence start may be a NAME opening
        # the sentence ("Kieshha and colleagues…"). Only flag it when a
        # distance-1 correction exists ("Thiss"→"this") — anything farther
        # is more likely a name than a typo.
        if capitalized and (not scored or scored[0][1] > 1):
            continue
        candidates = [t for t, _ in scored]
        if candidates:
            top = spelling.match_case(candidates[0], w)
            rest = (f" (also: {', '.join(candidates[1:])})"
                    if len(candidates) > 1 else "")
            msg = f"Did you mean '{top}'?{rest}"
            repl = top
        else:
            msg = ("Not in any dictionary — if this is your term, "
                   "`researchly dict add` it.")
            repl = None
        yield Suggestion(
            message=msg,
            start=m.start(), end=m.end(),
            replacement=repl)

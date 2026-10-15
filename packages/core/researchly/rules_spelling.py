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
from . import spelling, spellrank
from .document import Document
from .engine import Category, Suggestion, rule

MIN_LEN = 3
WORD_RX = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

# The word either side within the same clause: punctuation that ends a
# clause, or a line break, cuts the context.
_PREV_WORD = re.compile(r"([A-Za-z']+)[ \t]*$")
_NEXT_WORD = re.compile(r"[ \t]*([A-Za-z']+)")


def _neighbours(text: str, start: int, end: int) -> tuple[str | None,
                                                          str | None]:
    before = _PREV_WORD.search(text, max(0, start - 40), start)
    after = _NEXT_WORD.match(text, end)
    return (before.group(1).lower() if before else None,
            after.group(1).lower() if after else None)


def _distance(typed: str, cand: str) -> int:
    """Edit distance, with a run-together pair ("inspite" → "in spite")
    counted as the one missing space it is."""
    if " " in cand and cand.replace(" ", "") == typed:
        return 1
    from symspellpy.editdistance import DistanceAlgorithm, EditDistance
    dist = EditDistance(DistanceAlgorithm.DAMERAU_OSA).compare(typed, cand, 3)
    return dist if dist >= 0 else 3


def _sentence_start(text: str, start: int) -> bool:
    """Is this word the first of a sentence (or of the text/line)?"""
    i = start - 1
    while i >= 0 and text[i] in " \t":
        i -= 1
    return i < 0 or text[i] in ".!?\n"


# The halves of a word broken at a line end by a PDF: "effec-" + "tive".
# At most a blank line between them: a masked line is a run of spaces.
_BROKEN_AFTER = re.compile(
    r"-[ \t]{0,3}\n(?:[ \t]{0,3}\n)?[ \t]{0,3}([a-z]+)\b")
_BROKEN_BEFORE = re.compile(
    r"[A-Za-z]-[ \t]{0,3}\n(?:[ \t]{0,3}\n)?[ \t]{0,3}\Z")


def _in_latin_phrase(text: str, m) -> bool:
    """"ad valorem", "per capita": the word and a neighbour form a phrase."""
    before = re.search(r"([A-Za-z]+)[\s-]+$", text[max(0, m.start() - 20):m.start()])
    after = re.match(r"[\s-]+([A-Za-z]+)", text[m.end():m.end() + 20])
    w = m.group(0).lower()
    return ((before is not None
             and f"{before.group(1).lower()} {w}" in lx.LATIN_PHRASES)
            or (after is not None
                and f"{w} {after.group(1).lower()}" in lx.LATIN_PHRASES))


def _in_url_like(text: str, start: int, end: int) -> bool:
    prev = text[start - 1] if start > 0 else " "
    nxt = text[end] if end < len(text) else " "
    if prev in "@/_-" or nxt in "@/_":
        return True
    if text.startswith("://", end):                   # "https://..."
        return True
    # "example.com" — a dot immediately followed by another letter
    if nxt == "." and end + 1 < len(text) and text[end + 1].isalpha():
        return True
    return False


# What follows a surname in a citation or reference entry: initials
# ("Lau H, Khosrawipour V", "Zhang, Y.") or "et al". A dictionary cannot
# judge a name, and at a sentence start (a numbered reference, "Ruan et
# al. found") the proper-noun guard in s001 does not apply (P31).
_AUTHOR_NAME = re.compile(
    r",?\s+(?:et\s+al\b|[A-Z]{1,3}(?:[,.;]|\s+[A-Z][a-z])|[A-Z]\.)")


# --- S001 / S003: unknown words, and words used again and again --------------
#
# Until Codex review #10 (2026-10-15) any word used three or more times was
# taken to be the author's vocabulary and never flagged, so a typo the writer
# repeated ("recieve" three times) went unseen. Now a repeated unknown word is
# judged: a known kind of slip near a common word stays an S001 card at every
# occurrence; anything else is asked about once (S003), never flagged.

# How often an unknown word must appear before it is judged as a group.
REPEAT_MIN = 3
# Set 2026-10-15 with ml/eval/spelling_repetition.py on the training split of
# Wikipedia's common misspellings and a sample of SPECIALIST Lexicon words
# hidden from the lexicon (standing in for field terms no dictionary knows),
# choosing the fewest terms read as typos (precision first, CLAUDE.md #5).
# The intended word must be common in SymSpell's English counts ("seasonality"
# is about 300,000; "until" 113 million) ...
TYPO_MIN_FREQ = 300_000
# ... and the slip a usual one: log P(typed | intended) from the learned
# error table (spellrank.log_error). A transposition, a doubled or dropped
# letter or a swapped vowel scores above -5.5; an edit the table never saw
# scores -8.
TYPO_MIN_ERROR = -5.5
# A long word one edit from a very frequent word, with no other candidate
# near it, is a slip even when the edit is one the table has not seen
# ("bewteen", "ppublisher").
LONE_MIN_LEN = 8
LONE_MIN_FREQ = 5_000_000
# A word this short is one edit from too many words to call ("clin", "sera",
# "buri" in the eight theses: abbreviations and place names), so a short
# repeated word is a typo only by its ending or a split around a little word.
TYPO_MIN_LEN = 6


class _Unknown:
    """One occurrence S001 would flag: where, and what to suggest."""
    __slots__ = ("start", "end", "word", "lower", "message", "replacement")

    def __init__(self, start, end, word, lower, message, replacement):
        self.start, self.end = start, end
        self.word, self.lower = word, lower
        self.message, self.replacement = message, replacement


def _term_shaped(lower: str) -> bool:
    """Endings of coined biomedical and chemical names ("-ase", "-mab",
    "-omics"): a word built like a term is asked about, never corrected."""
    return lower.endswith(lx.TERM_ENDINGS)


def _compound(cand: str) -> bool:
    """Is a two-word split a compound rather than a habit? The run-togethers
    writers repeat open with a little word ("in spite", "each other", "a
    lot", "as well"); a split after a content word is a field's compound
    ("line width", "herpes virus", "burn in") or a lost hyphen or space at a
    line end ("low- and middle-income" read as "lowand"), which a question
    covers better than a correction at every use."""
    left = cand.split(" ", 1)[0]
    return left not in spelling.FUNCTION_WORDS | {"a", "i", "each"}


def repeated_kind(lower: str) -> str:
    """"typo" or "term" for an unknown word the writer uses REPEAT_MIN or
    more times. Precision first: only a word the error model and the
    dictionary both call a slip is a typo; everything else is a term to ask
    about, as the old blanket exemption assumed."""
    if spelling.reinflect(lower) is not None:
        return "typo"                     # "occured", "happend"
    ranked = spellrank.rank(lower, None, None, top_n=3)
    if not ranked:
        return "term"                     # nothing near it: a coined word
    cand = ranked[0][0]
    if " " in cand:
        return "term" if _compound(cand) else "typo"
    if len(lower) < TYPO_MIN_LEN or _term_shaped(lower) \
            or _distance(lower, cand) != 1:
        return "term"
    freq = spelling.get_sym().words.get(cand, 0)
    if freq >= TYPO_MIN_FREQ \
            and spellrank.log_error(lower, cand) >= TYPO_MIN_ERROR:
        return "typo"
    lone = len(ranked) == 1 or all(" " in c for c, _ in ranked[1:])
    if lone and len(lower) >= LONE_MIN_LEN and freq >= LONE_MIN_FREQ:
        return "typo"
    return "term"


def _scan(document: Document) -> list[_Unknown]:
    """Every occurrence S001 would flag, with no regard to repetition.
    Shared by S001 and S003 and kept on the document, so the words are
    looked up once per check."""
    text = document.masked
    domain = spelling.domain_terms()
    cfg_words: list[str] = getattr(document, "extra_dictionary", []) or []
    user = spelling.user_dictionary(cfg_words)
    # Keyed on the dictionary too: a word added between two checks of one
    # document must not be served from the first.
    key = (text, frozenset(user))
    cached = getattr(document, "_unknown_words", None)
    if cached is not None and cached[0] == key:
        return cached[1]
    found: list[_Unknown] = []

    for m in WORD_RX.finditer(text):
        w = m.group(0)
        if "'" in w:
            continue
        # A word a PDF broke across a line ("effec-\ntive"): judge the whole
        # word, once, on its first half (P33).
        if _BROKEN_BEFORE.search(text, max(0, m.start() - 12), m.start()):
            continue
        broken = _BROKEN_AFTER.match(text, m.end())
        if broken:
            joined = w + broken.group(1)
            if spelling.known_with_fallbacks(joined.lower()):
                found.append(_Unknown(
                    m.start(), broken.end(1), w, "",
                    f"One word broken across a line — join it: "
                    f"'{joined}'.", joined))
                continue
        if len(w) < MIN_LEN:
            continue
        if w.isupper():                       # acronyms → F601's business
            continue
        # "mDh", "nIter", "logLik": a lower-case start with a capital inside
        # is a code name, not a word ("THe", a shift slip, is still checked)
        if w[0].islower() and any(c.isupper() for c in w[1:]):
            continue
        lower = w.lower()
        if lower in lx.APOSTROPHELESS_CONTRACTIONS:
            continue                          # "dont": W208 owns it
        if lower in domain or lower in user:
            continue
        if w.upper() in lx.ACRONYM_ALLOWLIST:
            continue
        if _in_url_like(text, m.start(), m.end()):
            continue
        if lower in lx._LATIN_WORDS and _in_latin_phrase(text, m):
            continue
        # "mis-ordered", "non-zero", "co-circulating": a prefix before a
        # hyphen is half of a compound, not a word on its own.
        if text[m.end():m.end() + 1] == "-" and \
                lower in spelling.DERIVATIONAL_PREFIXES:
            continue
        capitalized = w[0].isupper()
        if capitalized and not _sentence_start(text, m.start()):
            continue                          # likely a proper noun
        if capitalized and _AUTHOR_NAME.match(text, m.end()):
            continue                          # "Lau H, ...", "Ruan et al."
        if spelling.known_with_fallbacks(lower):
            continue

        # Ranked by the noisy-channel model with the words either side
        # ("infact, the" → "in fact"; "thier study" → "their").
        prev, nxt = _neighbours(text, m.start(), m.end())
        candidates = [c for c, _ in spellrank.rank(lower, prev, nxt)]
        # A capitalized unknown at a sentence start may be a NAME opening
        # the sentence ("Kieshha and colleagues…"). Only flag it when a
        # distance-1 correction exists ("Thiss"→"this") — anything farther
        # is more likely a name than a typo.
        if capitalized and (not candidates
                            or _distance(lower, candidates[0]) > 1):
            continue
        if candidates:
            top = spelling.match_case(candidates[0], w)
            rest = (f" (also: {', '.join(candidates[1:])})"
                    if len(candidates) > 1 else "")
            msg = f"Did you mean '{top}'?{rest}"
            repl = top
        else:
            msg = ("Not in any dictionary. If this is your term, add it "
                   "to your dictionary.")
            repl = None
        found.append(_Unknown(m.start(), m.end(), w, lower, msg, repl))

    document._unknown_words = (key, found)
    return found


def _usage(document: Document) -> Counter:
    """How often each word appears in the checked text, in any case."""
    return _counts(document)[0]


def _lower_usage(document: Document) -> Counter:
    """How often each word appears written all in lower case."""
    return _counts(document)[1]


def _counts(document: Document) -> tuple[Counter, Counter]:
    cached = getattr(document, "_word_usage", None)
    if cached is None or cached[0] != document.masked:
        anycase: Counter = Counter()
        lower: Counter = Counter()
        for m in WORD_RX.finditer(document.masked):
            w = m.group(0)
            anycase[w.lower()] += 1
            if w.islower():
                lower[w] += 1
        cached = (document.masked, anycase, lower)
        document._word_usage = cached
    return cached[1], cached[2]


def _repeated(document: Document) -> tuple[dict, set]:
    """Unknown words used REPEAT_MIN+ times that S001 leaves alone: the
    terms S003 asks about (each with the uses S001 would have flagged), and
    the names the writer spells as names. A word never written in lower
    case (a place name opening a table row, "Udon"), or written in capitals
    or as a proper noun at most of its uses ("MWS", "Chiang Mai") and in
    lower case at a few (a table cell, a label), is the writer's name for
    something; neither a correction nor a question helps."""
    scanned = _scan(document)
    cached = getattr(document, "_repeated_words", None)
    if cached is not None and cached[0] is scanned:
        return cached[1], cached[2]
    usage = _usage(document)
    groups: dict[str, list[_Unknown]] = {}
    for u in scanned:
        if u.lower and usage[u.lower] >= REPEAT_MIN:
            groups.setdefault(u.lower, []).append(u)
    lower = _lower_usage(document)
    names = {w for w, occ in groups.items()
             if 2 * len(occ) <= usage[w] or not lower[w]}
    terms = {w: occ for w, occ in groups.items()
             if w not in names and repeated_kind(w) == "term"}
    document._repeated_words = (scanned, terms, names)
    return terms, names


@rule("S001", "spelling", Category.CORRECTION,
      "Possible misspelling (SymSpell dictionary + scientific lexicon).",
      'Spelling against a frequency dictionary plus a scientific lexicon '
      '(seroprevalence, covariates, nowcasting are not errors here). '
      'Proper nouns, acronyms and UK/US variants are skipped. A word used '
      'three or more times is flagged at every use only when it is a known '
      'kind of slip next to a common word (a learned error model of real '
      'misspellings); any other repeated word is asked about once instead. '
      "A false alarm on your own terminology: 'Add to dictionary' on the "
      'card teaches it the word.',
      plain=('This word is not in the dictionary, so it may be a typo. '
             'Scientific terms, names and abbreviations are usually recognised. '
             'If it is a real word you use, add it to your dictionary from this '
             'card and it will not be flagged again.'),
      source="symspellpy",
      tier="spelling", fix_safety="review")
def s001_spelling(doc, document: Document):
    terms, names = _repeated(document)
    for u in _scan(document):
        if u.lower in terms or u.lower in names:
            continue                      # S003 asks about a term, once
        yield Suggestion(message=u.message, start=u.start, end=u.end,
                         replacement=u.replacement)


@rule("S003", "repeated-unknown-word", Category.CONVENTION,
      "A word used three or more times that no dictionary knows: one "
      "question for all its uses (add it, or check its spelling).",
      'A word the dictionaries do not know, used three or more times, and '
      'not a known kind of slip next to a common word (the learned error '
      'model S001 uses), is most likely a term of the field: a coined name, '
      'a gene, a software package. It is not marked at each use; one card '
      'asks whether it is a term, shows every place it appears, and adds it '
      'to your dictionary in one step. A repeated typo still gets a '
      'spelling card at every use.',
      plain=('You use this word several times and it is not in the '
             'dictionary. If it is a term from your field, add it to your '
             'dictionary and it will not be questioned again. If not, check '
             'its spelling in each place.'),
      source="symspellpy", tier="spelling", fix_safety="review",
      scope="document")
def s003_repeated_unknown(doc, document: Document):
    terms, _names = _repeated(document)
    for lower, occ in terms.items():
        first = occ[0]
        # Every use, in reading order (a capitalised one included), so
        # "Show where" visits each place the count speaks of.
        where = [{"start": m.start(), "end": m.end()}
                 for m in WORD_RX.finditer(document.masked)
                 if m.group(0).lower() == lower]
        yield Suggestion(
            message=(f"‘{first.word}’ appears {len(where)} times "
                     f"and isn’t in the dictionary. If it’s a term, "
                     f"add it to your dictionary; otherwise check its "
                     f"spelling."),
            start=first.start, end=first.end, replacement=None,
            occurrences=where)


# --- S002: real-word confusions --------------------------------------------

# How much likelier, in natural-log odds, the other word must be in this
# context before S002 speaks: 5.0 is about 150 times. Set on the eight
# theses and the 115 PMC articles so that published prose stays silent.
CONFUSION_MARGIN = 5.0

_CONFUSIONS: dict[str, str] = dict(lx.CONFUSIONS)


@rule("S002", "real-word-confusion", Category.CORRECTION,
      "A real word that the context says was probably meant as another "
      "(the affect of; the principle investigator; a casual relationship).",
      'Both spellings are words, so a dictionary passes them. A language '
      'model of English word pairs (SymSpell\'s bigram counts) compares the '
      'word with its usual confusion in the same place: only when the other '
      'word is about 150 times likelier, and attested on both sides, is it '
      'suggested. Pairs are chosen for scientific prose, where "casual" for '
      '"causal" or "trail" for "trial" changes the meaning.',
      plain=("This is a real word, but the words around it suggest you meant "
             "a similar one, for example 'effect' instead of 'affect', or "
             "'causal' instead of 'casual'. Check which one you meant."),
      source="Mays1991", tier="spelling", fix_safety="review")
def s002_confusion(doc, document: Document):
    text = document.masked
    pairs = spellrank.bigrams()
    for m in re.finditer(r"[A-Za-z]+", text):
        typed = m.group(0)
        lower = typed.lower()
        alt = _CONFUSIONS.get(lower)
        if alt is None or (typed.isupper() and len(typed) > 1):
            continue
        prev, nxt = _neighbours(text, m.start(), m.end())
        if not prev or not nxt:
            continue                      # judge only with both neighbours
        if (prev, alt) not in pairs or (alt, nxt) not in pairs:
            continue                      # the other word must be attested
        own = spellrank.log_next(prev, lower) + spellrank.log_next(lower, nxt)
        other = spellrank.log_next(prev, alt) + spellrank.log_next(alt, nxt)
        # Known limit: a literal use in a common frame ("the trail was
        # muddy") can still be questioned; demanding more evidence when the
        # typed word is normal on both sides lost "the affect of", the
        # slip that matters more in a paper (2026-10-14).
        if other - own < CONFUSION_MARGIN:
            continue
        fixed = spelling.match_case(alt, typed)
        yield Suggestion(
            message=f"Did you mean '{fixed}'? Here '{prev} {alt} {nxt}' is "
                    f"far more usual than '{prev} {lower} {nxt}'.",
            start=m.start(), end=m.end(), replacement=fixed)

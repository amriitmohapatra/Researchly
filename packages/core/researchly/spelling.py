"""Spelling backend: SymSpell (symspellpy, MIT) + scientific-vocabulary
guards.

Why guards matter (measured before building): a general English frequency
dictionary doesn't know 'seroprevalence', 'covariates', or 'nowcasting' —
flagging the researcher's own terminology is exactly the false-positive
fatigue that kills checkers. Layers of defence:

1. built-in frequency dictionary (~83k words)
2. shipped scientific lexicon (data/scientific_terms.txt — epi/stats/
   modelling vocabulary)
3. the user's personal dictionary (~/.researchly/dictionary.txt and
   [dictionary] words=[...] in .researchly.toml) — `researchly dict add X`
4. morphological fallback (covariates → covariate, behaviours → behaviour)
5. UK/US variant mapping (modelling/modeling, behaviour/behavior, -ise/-ize)
6. document-learned terms: a word used 3+ times is the author's vocabulary
"""

from __future__ import annotations

import re

import threading
from pathlib import Path

_LOCK = threading.Lock()
_SYM = None
_DOMAIN: set[str] | None = None

USER_DICT_FILE = Path.home() / ".researchly" / "dictionary.txt"

SUFFIXES = ("es", "s", "ed", "d", "ing", "ly", "er", "est")

# Closed-class words never take suffixes — "thiss" is a typo, not "this+s".
# Without this, the morphological fallback would excuse doubled-letter typos
# of function words.
FUNCTION_WORDS = frozenset("""
this that these those the and but or nor if is was are were be been being
has have had with from for not of to in on at by it its as we you they he
she him her them his our your their than then when which who whom whose
what why how would could should will shall may might must do does did done
am us me my mine no so too very can cannot into onto upon about above below
over under again further once here there all any both each few more most
other some such only own same
""".split())


def get_sym():
    """Lazy singleton SymSpell with the bundled English dictionary."""
    global _SYM
    with _LOCK:
        if _SYM is None:
            from symspellpy import SymSpell
            import importlib.resources as ir
            sym = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
            ref = (ir.files("symspellpy")
                   / "frequency_dictionary_en_82_765.txt")
            with ir.as_file(ref) as p:
                sym.load_dictionary(str(p), 0, 1)
            _SYM = sym
    return _SYM


def domain_terms() -> set[str]:
    global _DOMAIN
    if _DOMAIN is None:
        terms: set[str] = set()
        data = Path(__file__).parent / "data" / "scientific_terms.txt"
        if data.exists():
            for line in data.read_text(encoding="utf-8").splitlines():
                line = line.strip().lower()
                if line and not line.startswith("#"):
                    terms.add(line)
        _DOMAIN = terms
    return _DOMAIN


def user_dictionary(extra: list[str] | None = None) -> set[str]:
    words: set[str] = set(w.lower() for w in (extra or []))
    try:
        if USER_DICT_FILE.exists():
            for line in USER_DICT_FILE.read_text(
                    encoding="utf-8").splitlines():
                line = line.strip().lower()
                if line:
                    words.add(line)
    except Exception:
        pass
    return words


def add_to_user_dictionary(word: str) -> bool:
    try:
        USER_DICT_FILE.parent.mkdir(exist_ok=True)
        existing = user_dictionary()
        if word.lower() in existing:
            return True
        with open(USER_DICT_FILE, "a", encoding="utf-8") as f:
            f.write(word.lower() + "\n")
        return True
    except Exception:
        return False


def is_known(word: str) -> bool:
    """Exact dictionary membership (distance-0 lookup)."""
    from symspellpy import Verbosity
    hits = get_sym().lookup(word, Verbosity.TOP, max_edit_distance=0,
                            include_unknown=False)
    return bool(hits)


def _variants(word: str) -> list[str]:
    """UK↔US spelling transforms that are productive, so a list cannot hold
    every word: -ise/-ize and -yse/-yze ("dichotomise", "operationalize")
    and the medical -aemia/-oea forms ("viraemia", "diarrhoea"). Every
    other UK/US difference comes from VarCon (variant_words): the old
    letter swaps here also accepted "rigourous" (our → or), "controled"
    (lled → led) and "contre" (tre → ter)."""
    pairs = (("isation", "ization"), ("ise", "ize"), ("ised", "ized"),
             ("ising", "izing"), ("yse", "yze"), ("ysed", "yzed"),
             ("ysing", "yzing"), ("yser", "yzer"),
             ("aemia", "emia"), ("oea", "ea"))
    out = []
    for a, b in pairs:
        if a in word:
            out.append(word.replace(a, b))
        if b in word:
            v = word.replace(b, a)
            # "surprize" is no variant: surprise, advise, revise... are
            # spelt -ise in every English (lexicons.ISE_ONLY)
            if not (b.startswith("iz") and v.startswith(lx_ise_only())):
                out.append(v)
    return out


def lx_ise_only() -> tuple[str, ...]:
    from .lexicons import ISE_ONLY
    return ISE_ONLY


_VARIANT_WORDS: dict[str, tuple[str, str]] | None = None
_VARIANT_PAIRS: list[tuple[str, str]] | None = None
_PARTNERS: dict[str, list[str]] | None = None

# The spelling setting (config.SPELLINGS) as VarCon dialect codes.
DIALECT_CODES = {"us": "A", "uk": "B", "uk-oxford": "Z", "ca": "C",
                 "au": "D"}
DIALECT_NAMES = {"us": "American", "uk": "British",
                 "uk-oxford": "British (Oxford, -ize)", "ca": "Canadian",
                 "au": "Australian"}


def _load_variants() -> None:
    """data/variants.tsv, built from VarCon by ml/tools/build_variants.py:
    every spelling with the dialects it belongs to, and the pairs of
    spellings that W210 and W213 compare."""
    global _VARIANT_WORDS, _VARIANT_PAIRS, _PARTNERS
    words: dict[str, tuple[str, str]] = {}
    pairs: list[tuple[str, str]] = []
    partners: dict[str, list[str]] = {}
    path = Path(__file__).parent / "data" / "variants.tsv"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if parts[0] == "=" and len(parts) == 3:
                a, b = parts[1], parts[2]
                pairs.append((a, b))
                partners.setdefault(a, []).append(b)
                partners.setdefault(b, []).append(a)
            elif len(parts) == 3:
                words[parts[0]] = (parts[1], parts[2])
    _VARIANT_WORDS, _VARIANT_PAIRS, _PARTNERS = words, pairs, partners


_SPECIALIST: frozenset[str] | None = None


def specialist_words() -> frozenset[str]:
    """Biomedical and general English word forms from the NLM SPECIALIST
    Lexicon (data/specialist_words.txt, built and filtered by
    ml/tools/build_specialist_words.py; its notice is in the file's
    header): "spectrin", "biofilm", "rifampin", "epitopes"."""
    global _SPECIALIST
    if _SPECIALIST is None:
        path = Path(__file__).parent / "data" / "specialist_words.txt"
        words: set[str] = set()
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line and not line.startswith("#"):
                        words.add(line.strip())
        _SPECIALIST = frozenset(words)
    return _SPECIALIST


def variant_words() -> dict[str, tuple[str, str]]:
    """Spellings VarCon lists for American, British, Canadian or
    Australian English ("feces", "modeling", "colour"), each with its main
    and its accepted-variant dialect codes."""
    if _VARIANT_WORDS is None:
        _load_variants()
    return _VARIANT_WORDS or {}


def variant_pairs() -> list[tuple[str, str]]:
    """Two spellings of one word in different dialects, never both the
    main spelling of one dialect in any sense (W210)."""
    if _VARIANT_PAIRS is None:
        _load_variants()
    return _VARIANT_PAIRS or []


def dialect_spelling(word: str, spelling: str) -> str | None:
    """The spelling of `word` in the chosen dialect, when `word` is not
    written that way there: ("color", "uk") → "colour"; ("organise",
    "uk-oxford") → "organize"; ("meter", "uk") → None, because British
    English writes "meter" for the measuring device."""
    code = DIALECT_CODES.get(spelling)
    entry = variant_words().get(word)
    if code is None or entry is None or code in entry[0] + entry[1]:
        return None
    if _PARTNERS is None:
        _load_variants()
    for other in (_PARTNERS or {}).get(word, []):
        if code in variant_words().get(other, ("", ""))[0]:
            return other
    return None


def detect_dialect(words: list[str]) -> tuple[str | None, int, int]:
    """Which dialect a text's spellings point to: (setting, words that
    agree, words that tell the dialects apart). Only words with a partner
    count ("colour" tells; "data" does not). US against British, and
    -ise against -ize within British; None when the text says nothing."""
    tally = {k: 0 for k in DIALECT_CODES}
    telling = 0
    table = variant_words()
    if _PARTNERS is None:
        _load_variants()
    for w in words:
        if w not in (_PARTNERS or {}):
            continue
        main, _variant = table.get(w, ("", ""))
        telling += 1
        for name, code in DIALECT_CODES.items():
            if code in main:
                tally[name] += 1
    if not telling:
        return None, 0, 0
    best = max(("us", "uk", "uk-oxford"), key=lambda k: tally[k])
    return best, tally[best], telling


# Prefixes that make a real word from a real word: "unstratified",
# "uncited", "autoregression", "nonzero". A typo in the stem still fails,
# because the stem itself must be known.
DERIVATIONAL_PREFIXES = ("non", "un", "mis", "re", "pre", "post", "over",
                         "under", "sub", "co", "multi", "inter", "intra",
                         "semi", "pseudo", "quasi", "auto", "hyper", "hypo",
                         "anti", "counter", "cross", "self")


def _known_stem(word: str) -> bool:
    """A stem behind a prefix must be a dictionary word as written (or its
    UK/US twin). No suffix-stripping here: "mis" + "peled" would pass as
    "pele" + "d", and "mispeled" is the classic typo this tier exists for."""
    return is_known(word) or word in variant_words() \
        or word in specialist_words() \
        or any(is_known(v) for v in _variants(word))


_VOWELS = frozenset("aeiou")
_SIBILANT_ENDINGS = ("s", "x", "z", "ch", "sh")


def _doubles_final_consonant(stem: str) -> bool:
    """A consonant-vowel-consonant ending (occur, begin, commit, get):
    English doubles that consonant before -ed/-ing/-er/-est when the last
    syllable is stressed. Stress is not visible in the spelling, so the
    dictionary decides whether the doubled form is the one in use."""
    # "qu" is one consonant sound: acquit → acquitted, equip → equipped
    third = stem[-3] if len(stem) >= 3 else ""
    qu = third == "u" and len(stem) >= 4 and stem[-4] == "q"
    return (len(stem) >= 3 and stem[-1] not in "aeiouwxy"
            and stem[-2] in _VOWELS and (third not in _VOWELS or qu))


def _misinflected(base: str, suf: str) -> bool:
    """Does a known base take this ending in a different spelling?

    The suffix fallback used to accept any known base plus any ending, which
    excused the commonest misspellings in English: "occured" (occur + ed),
    "begining", "happend", "acess" (aces + s), "personaly". Each test below
    is a spelling rule of English inflection; where a rule depends on the
    word (doubling, a dropped e), the dictionary must know the correct form
    before the typed one is rejected."""
    if suf == "d":                                  # bake → baked, not happend
        return not base.endswith("e")
    if suf == "s":                                  # access, companies
        return base.endswith(_SIBILANT_ENDINGS) or (
            len(base) > 2 and base[-1] == "y" and base[-2] not in _VOWELS)
    if suf == "es":                                 # boxes, heroes; not detailes
        return not base.endswith(_SIBILANT_ENDINGS + ("o",))
    if suf == "ly":                                 # personally, basically, severely
        return any(is_known(base + x) for x in ("lly", "ally", "ely"))
    if suf == "est" and not is_known(base + "er"):  # "reqest" is not a superlative
        return True
    if suf in ("ed", "ing", "er", "est"):
        if base.endswith("e") and not base.endswith(("ee", "ye", "oe")):
            return is_known(base[:-1] + suf)        # useing → using
        if suf != "ing" and len(base) > 2 and base[-1] == "y" \
                and base[-2] not in _VOWELS:
            return is_known(base[:-1] + "i" + suf)  # tryed → tried
        # travel(l)ed, model(l)ing: the -l- / -ll- difference is a UK/US
        # variant, not an error, so -el and -al stems are left alone.
        if _doubles_final_consonant(base) and not base.endswith(("el", "al")) \
                and is_known(base + base[-1] + suf):
            return True                             # occured → occurred
    return False


def _word_count(word: str) -> int:
    return get_sym().words.get(word, 0)


def _accidental_prefix(word: str, stem: str) -> bool:
    """Is "prefix + known word" only a coincidence of letters?

    "untill" is "un" + "till" and "corect" is "co" + "rect", but the writer
    meant "until" and "correct": one edit away, and far more common than
    the stem the split produced. A genuine prefixed word ("preinfection",
    "unboiled") is rarer than its neighbour's stem would suggest, and a
    neighbour that is only another inflection of the same word
    ("reinfections" → "reinfection") is no evidence at all."""
    # Only a short stem is a likely accident ("till", "rect", "lase"); a
    # longer one is the word the writer built on ("uncited" is not a slip
    # for "united", however common that is).
    if len(stem) > 4:
        return False
    stem_count = _word_count(stem)
    for cand, dist in suggest_with_distance(word, top_n=3):
        if dist != 1:
            break
        if _same_word_inflected(word, cand):
            continue
        if _word_count(cand) > stem_count:
            return True
    return False


def _same_word_inflected(a: str, b: str) -> bool:
    """"reinfections" / "reinfection": one is the other plus an ending."""
    short, long_ = sorted((a, b), key=len)
    return any(long_ == short + suf for suf in SUFFIXES)


def _inflection_forms(base: str, suf: str) -> list[str]:
    """The spellings English uses for base + suf, most regular first."""
    if suf == "d":
        return [base + "ed"]
    if suf == "s":
        return ([base[:-1] + "ies"] if base.endswith("y") else []) \
            + [base + "es"]
    if suf == "es":
        return [base + "s"]
    if suf == "ly":
        return [base + "lly", base + "ally", base + "ely"]
    forms = []
    if base.endswith("e"):
        forms.append(base[:-1] + suf)
    if base.endswith("y"):
        forms.append(base[:-1] + "i" + suf)
    forms.append(base + base[-1:] + suf)
    return forms


def reinflect(word: str) -> str | None:
    """The correctly inflected word a misinflected one was meant to be:
    "happend" → "happened", "occured" → "occurred", "acess" → "access".
    Edit distance alone ranks "happen" first (it is more frequent); the
    writer's ending says which form they meant."""
    for suf in SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            base = word[: -len(suf)]
            if base in FUNCTION_WORDS or not is_known(base) \
                    or not _misinflected(base, suf):
                continue
            for form in _inflection_forms(base, suf):
                if form != word and is_known(form):
                    return form
    return None


def _lexicon_refuses(base: str, word: str) -> bool:
    """The SPECIALIST Lexicon lists every inflection of each word it holds,
    so when it holds the base and not this form, the form is not English:
    "spreaded" (spread), "adviced" (advice is a noun), "awared" (an
    adjective). Forms under 5 letters are outside the shipped list."""
    return len(word) >= 5 and base in specialist_words()


def known_with_fallbacks(word: str) -> bool:
    """Known directly, morphologically, as a UK/US variant, or as a known
    word behind a common prefix."""
    if is_known(word) or word in variant_words() \
            or word in specialist_words():
        return True
    # "crosssectional": a tripled letter is a lost hyphen or a slip, not a
    # prefixed word, however real the stem.
    tripled = re.search(r"(.)\1\1", word) is not None
    for p in () if tripled else DERIVATIONAL_PREFIXES:
        if word.startswith(p) and len(word) - len(p) >= 4 \
                and _known_stem(word[len(p):]) \
                and not _accidental_prefix(word, word[len(p):]):
            return True
    for suf in SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            base = word[: -len(suf)]
            if base not in FUNCTION_WORDS \
                    and (is_known(base) or base in variant_words()) \
                    and not _misinflected(base, suf) \
                    and not _lexicon_refuses(base, word):
                return True
            # A doubled final consonant before the ending (repel → repeller)
            # is right only where the undoubled form is not the word in use:
            # "editting", "openning", "developped" double wrongly, and
            # "edited", "opening", "developed" are known.
            stem = base[:-1]
            if suf in ("ed", "ing", "er", "est") and len(stem) >= 4 \
                    and base[-1] == base[-2] \
                    and _doubles_final_consonant(stem) \
                    and _word_count(stem) >= 100_000 \
                    and not is_known(stem + suf):
                return True
    for v in _variants(word):
        if is_known(v):
            return True
        for suf in SUFFIXES:
            if v.endswith(suf) and len(v) - len(suf) >= 3 \
                    and is_known(v[: -len(suf)]) \
                    and not _misinflected(v[: -len(suf)], suf):
                return True
    return False


def suggest(word: str, top_n: int = 3) -> list[str]:
    return [t for t, _ in suggest_with_distance(word, top_n)]


def suggest_with_distance(word: str, top_n: int = 3) -> list[tuple[str, int]]:
    from symspellpy import Verbosity
    hits = get_sym().lookup(word, Verbosity.CLOSEST, max_edit_distance=2,
                            include_unknown=False,
                            transfer_casing=False)
    out: list[tuple[str, int]] = []
    fixed = reinflect(word)
    if fixed is not None:
        from symspellpy.editdistance import DistanceAlgorithm, EditDistance
        dist = EditDistance(DistanceAlgorithm.DAMERAU_OSA).compare(
            word, fixed, 3)
        out.append((fixed, dist if dist >= 0 else 3))
    for h in hits:
        if h.term != word and all(h.term != t for t, _ in out):
            out.append((h.term, h.distance))
        if len(out) >= top_n:
            break
    return out


def match_case(suggestion: str, original: str) -> str:
    if original[:1].isupper():
        return suggestion[:1].upper() + suggestion[1:]
    return suggestion

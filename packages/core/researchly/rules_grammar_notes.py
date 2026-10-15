"""Researchly grammar notes (S4d R6; ARCHITECTURE.md ADR-11).

Grammar rules written for Researchly at build time, in its own words, from
general knowledge of English grammar and of how American, British,
Canadian, Australian and Indian English differ. The source document is
docs/grammar-notes.md (source code `rgn`, shown to writers as "Researchly
grammar notes"); each rule there says what it flags, why, and what it
deliberately leaves alone. Nothing here calls a model: every rule is a
pattern or a reading of spaCy's parse, with fire and don't-fire tests in
tests/test_grammar_notes.py.

Two families:

- GN1xx, regional conventions. They follow the writer's chosen English
  (`spelling` in the settings; Indian English follows British usage, as
  its spelling does). With the setting on "auto" they stay quiet, except
  where the document mixes two styles of its own (dates, full stops and
  quotation marks). They are Conventions: never errors.
- GN2xx, grammar that research prose gets wrong and LanguageTool (LT001)
  misses: agreement across an "of" phrase, a dangling opener before a
  passive, "a"/"an" before abbreviations. What LanguageTool reliably
  catches ("less cases", "between 5 to 10", "comprised of", "more
  better") is left to it.

None is a Correction: a rule is shown above Improvement only once its
precision on the real-document bench is measured at 0.9 or more
(docs/inline-review-design.md §7).
"""

from __future__ import annotations

import re

from . import lexicons as lx
from .document import Document
from .engine import Category, Suggestion, rule

SOURCE = "rgn"

ENGLISH = {"us": "American English", "uk": "British English",
           "uk-oxford": "British English", "ca": "Canadian English",
           "au": "Australian English", "in": "Indian English"}
# Indian English follows British usage in grammar as in spelling.
BRITISH_PATTERN = frozenset({"uk", "uk-oxford", "au", "in"})


def _choice(document: Document) -> str:
    cfg = getattr(document, "config", None)
    return getattr(cfg, "spelling", "auto") if cfg is not None else "auto"


def _prose(document: Document, start: int, end: int) -> bool:
    """A span of running prose: not beside masked maths, citations or code,
    and not in a table cell."""
    return (not document.touches_masked(start, end)
            and not document.in_table(start))


# A reference entry in running text (a list the headings did not mark as
# references): its dates and quoted titles follow the cited work's style.
_REFERENCE_ENTRY = re.compile(
    r"\bet al\.|\[Internet\]|\[cited\b|\bdoi\b|https?://|Available from|"
    r"\b(?:19|20)\d\d\s*(?:[A-Z][a-z]{2})?\s*;\s*\d+")


def _in_reference(text: str, start: int, end: int) -> bool:
    return bool(_REFERENCE_ENTRY.search(text, max(0, start - 150),
                                        min(len(text), end + 150)))


def _match_case(word: str, like: str) -> str:
    return word[:1].upper() + word[1:] if like[:1].isupper() else word


def _finite(verb):
    """The word that carries number in the clause `verb` heads: its first
    auxiliary ("were" in "were given", "have" in "have been fitted"), or
    the verb itself."""
    for c in verb.children:
        if c.dep_ in ("aux", "auxpass") and c.i < verb.i:
            return c
    return verb


def _plural_verb(tok) -> bool:
    return tok.lower_ in lx.PLURAL_TO_SINGULAR_VERB or tok.tag_ == "VBP"


def _plural_aux(tok) -> bool:
    """"are", "were", "have", "do": a plural form the tagger cannot
    mistake. A main verb tagged plural ("show") can be a mis-tagged
    adjective ("patients reactive to"), so agreement rules that suggest
    a fix use only these."""
    return tok.lower_ in lx.PLURAL_TO_SINGULAR_VERB


def _second_conjunct(doc, tok) -> bool:
    """`tok`'s phrase follows "and"/"or": "the date and the number of
    articles were" has a plural subject."""
    i = tok.left_edge.i - 1
    while i >= 0 and doc[i].is_space:
        i -= 1
    return i >= 0 and doc[i].lower_ in ("and", "or", "nor", "&")


def _singular_verb(tok) -> bool:
    return tok.lower_ in lx.SINGULAR_TO_PLURAL_VERB or tok.tag_ == "VBZ"


def _token_after(doc, offset: int):
    """The first word token that starts at or after `offset`, or None."""
    for tok in doc:
        if tok.idx >= offset and not tok.is_space:
            return tok
    return None


# =====================================================================
# GN1xx: regional conventions
# =====================================================================

@rule("GN101", "collective-noun-plural-verb-us", Category.CONVENTION,
      "A group noun with a plural verb ('the committee were') in American "
      "English.",
      'American English treats a noun for a group of people as one thing: '
      '"the committee was", "the cohort has". British, Australian and Indian '
      'English may also treat the group as the people in it ("the committee '
      'were divided"). With American English chosen in the settings, a '
      'plural verb after such a noun reads as British. A group noun followed '
      'by "of" and a plural ("a group of patients were") is left alone: '
      'there the verb follows the people.',
      plain=("You chose American English. In American English, a word for a "
             "group, such as 'team' or 'cohort', takes a singular verb: 'the "
             "team was', not 'the team were'."),
      source=SOURCE)
def gn101_collective_us(doc, document: Document):
    if _choice(document) != "us":
        return
    for tok in doc:
        if (tok.lower_ not in lx.COLLECTIVE_NOUNS or tok.tag_ != "NN"
                or tok.dep_ not in ("nsubj", "nsubjpass")
                or tok.head.pos_ not in ("VERB", "AUX")):
            continue
        if any(c.dep_ in ("prep", "conj", "cc") for c in tok.children):
            continue                  # "group of patients", "team and board"
        if not any(c.dep_ in ("det", "poss") for c in tok.children):
            continue                  # a label or a table row, not a phrase
        verb = _finite(tok.head)
        if verb.i < tok.i or not _plural_aux(verb) or \
                "," in doc[tok.i:verb.i].text:
            continue
        a, b = verb.idx, verb.idx + len(verb.text)
        if not _prose(document, tok.idx, b):
            continue
        fix = lx.PLURAL_TO_SINGULAR_VERB.get(verb.lower_)
        yield Suggestion(
            message=f"In American English, 'the {tok.lower_}' takes a "
                    f"singular verb" + (f": '{fix}'." if fix else "."),
            start=a, end=b,
            replacement=_match_case(fix, verb.text) if fix else None)


_DIFFERENT = re.compile(r"\b(different)\s+(than|to)\b", re.IGNORECASE)


@rule("GN102", "different-from-by-region", Category.CONVENTION,
      "'different than' in British-pattern English, 'different to' in "
      "American or Canadian English.",
      '"Different from" is standard in every English. British, Australian '
      'and Indian English also use "different to", and American English '
      '"different than", especially before a clause ("different than we '
      'expected"); each reads as foreign in the other. The chosen English '
      'in the settings decides which one is flagged; "different from" never '
      'is. A comparison ("more different than") and "different to" about '
      'how something looks to someone ("different to the reader") are left '
      'alone.',
      plain=("'Different from' is right everywhere. 'Different than' sounds "
             "American and 'different to' sounds British, so each one stands "
             "out in the other kind of English you chose."),
      source=SOURCE)
def gn102_different(doc, document: Document):
    choice = _choice(document)
    if choice == "auto":
        return
    text = document.masked
    for m in _DIFFERENT.finditer(text):
        word = m.group(2).lower()
        before = text[max(0, m.start() - 30):m.start()]
        if word == "than":
            if choice not in BRITISH_PATTERN:
                continue
            if re.search(r"\b(more|less|most|least)\s+$", before, re.I):
                continue              # a comparison: "more different than"
        else:
            if choice not in ("us", "ca"):
                continue
            if re.search(r"\bfrom\b[^.;]*$", before, re.I):
                continue              # "from different to similar"
            nxt = _token_after(doc, m.end())
            if nxt is None or nxt.tag_ == "VB" or nxt.pos_ == "PRON":
                continue              # "something different to do"
            if nxt.lower_ in ("the", "a", "an", "most", "many", "some"):
                j = nxt.i + 1
                while j < len(doc) and doc[j].pos_ in ("ADJ", "DET"):
                    j += 1
                if j < len(doc) and doc[j].lower_ in lx.PERCEIVERS:
                    continue          # "different to the reader"
            elif nxt.lower_ in lx.PERCEIVERS:
                continue
        if not _prose(document, m.start(), m.end()):
            continue
        fix = _match_case("different from", m.group(1))
        yield Suggestion(
            message=f"In {ENGLISH[choice]}, write '{fix}'"
                    + (" (before a clause, 'different from what …')."
                       if word == "than" else "."),
            start=m.start(), end=m.end(), replacement=fix)


@rule("GN103", "gotten-outside-north-america", Category.CONVENTION,
      "'gotten' in British, Australian or Indian English.",
      'American and Canadian English use "gotten" as a past participle of '
      '"get" ("the counts have gotten worse"). British, Australian and '
      'Indian English use "got", and keep "gotten" only in set phrases '
      '("ill-gotten"). In research prose a more exact verb usually reads '
      'better in any English: "obtained", "become", "received".',
      plain=("You chose British-style English, which says 'have got', not "
             "'have gotten'. A more exact word, such as 'obtained' or "
             "'become', is often better still."),
      source=SOURCE)
def gn103_gotten(doc, document: Document):
    choice = _choice(document)
    if choice not in BRITISH_PATTERN:
        return
    for m in re.finditer(r"(?<![\w-])gotten\b", document.masked, re.I):
        if not _prose(document, m.start(), m.end()):
            continue
        yield Suggestion(
            message=f"In {ENGLISH[choice]}, write 'got' (or a more exact "
                    "verb, such as 'obtained' or 'become').",
            start=m.start(), end=m.end(),
            replacement=_match_case("got", m.group(0)))


@rule("GN104", "whilst-in-american", Category.CONVENTION,
      "'whilst' in American English.",
      '"Whilst" is a British variant of "while"; American readers meet it '
      'mostly in older or British texts, so in American English it reads as '
      'old-fashioned or foreign. "While" means the same everywhere.',
      plain=("You chose American English, where 'whilst' sounds British or "
             "old-fashioned. 'While' means the same and is used everywhere."),
      source=SOURCE)
def gn104_whilst(doc, document: Document):
    if _choice(document) != "us":
        return
    for m in re.finditer(r"\bwhilst\b", document.masked, re.I):
        if not _prose(document, m.start(), m.end()):
            continue
        yield Suggestion(
            message="In American English, write 'while'.",
            start=m.start(), end=m.end(),
            replacement=_match_case("while", m.group(0)))


_FIT = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+"
    r"(?:(?:then|also|first|subsequently|each|all|not|initially)\s+)?"
    r"(fit)\s+([A-Za-z]+)\b", re.IGNORECASE)


@rule("GN105", "fit-as-past-participle", Category.CONVENTION,
      "'was fit' or 'were fit' for a fitted model in British-pattern "
      "English.",
      'For fitting a model to data, American English often uses "fit" as the '
      'past tense and participle ("the model was fit to weekly counts"). '
      'British, Australian and Indian English use "fitted" ("the model was '
      'fitted"). Only the passive with a following "to", "using", "with" and '
      'the like is flagged; "fit for purpose" and "fit to travel" are the '
      'adjective and are left alone.',
      plain=("You chose British-style English, where a model 'was fitted' to "
             "the data. 'Was fit' is the American way of saying it."),
      source=SOURCE)
def gn105_fit(doc, document: Document):
    choice = _choice(document)
    if choice not in BRITISH_PATTERN:
        return
    text = document.masked
    for m in _FIT.finditer(text):
        if m.group(2).lower() not in lx.FIT_FOLLOWERS:
            continue
        if m.group(2).lower() == "to":
            nxt = _token_after(doc, m.end(2))
            if nxt is None or nxt.tag_ == "VB":
                continue              # "fit to travel": the adjective
        a, b = m.start(1), m.end(1)
        if not _prose(document, m.start(), m.end()):
            continue
        yield Suggestion(
            message=f"In {ENGLISH[choice]}, a model 'was fitted': write "
                    "'fitted'.",
            start=a, end=b, replacement=_match_case("fitted", m.group(1)))


_OPEN = r"(?:“|\"|``)"
_CLOSE = r"(?:”|\"|'')"
_BODY = r"([^“”\"\n`']{1,80}?)"
# A full stop or comma inside the closing quotation mark, and outside it.
_INSIDE = re.compile(_OPEN + _BODY + r"([.,])" + _CLOSE)
_OUTSIDE = re.compile(_OPEN + _BODY + "(" + _CLOSE + r")([.,])")


def _a_term(body: str) -> bool:
    """Quoted words that are a term or a phrase, not a quoted sentence:
    where British placement would keep the full stop outside."""
    body = body.strip()
    return bool(body) and body[0].islower() and len(body.split()) <= 4


def _minority(a: list, b: list) -> tuple[list, str]:
    """The uses to flag when a document mixes two styles: the rarer one,
    or on a tie the one used second."""
    if len(a) != len(b):
        return (a, "b") if len(a) < len(b) else (b, "a")
    return (b, "a") if a[0][0] < b[0][0] else (a, "b")


@rule("GN106", "punctuation-with-quotation-marks", Category.CONVENTION,
      "A full stop or comma placed inside or outside closing quotation "
      "marks against the chosen English, or both ways in one document.",
      'American and Canadian style put a full stop or comma inside the '
      'closing quotation mark, always: the term "herd immunity." British, '
      'Australian and Indian style put it where the sense puts it, so after '
      'a quoted term it goes outside: the term "herd immunity". With an '
      'English chosen in the settings, the other placement is flagged (for '
      'British-pattern English only after a short lower-case term, since a '
      'quoted full sentence may keep its own full stop). With the setting on '
      '"auto", only a document that uses both placements is flagged. Some '
      'science journals use the British placement in American English; if '
      'yours does, mute this check.',
      plain=("American style puts a full stop or comma inside the closing "
             "quotation mark; British style puts it outside after a quoted "
             "word or phrase. Use the style of the English you write in, "
             "the same way throughout."),
      source=SOURCE, scope="document", aggregate=True)
def gn106_quote_punctuation(doc, document: Document):
    choice = _choice(document)
    text = document.masked
    inside = [(m.start(2), m.end(), m) for m in _INSIDE.finditer(text)
              if _prose(document, m.start(), m.end())
              and not _in_reference(text, m.start(), m.end())]
    outside = [(m.start(2), m.end(3), m)
               for m in _OUTSIDE.finditer(text)
               if _prose(document, m.start(), m.end())
               and not _in_reference(text, m.start(), m.end())]
    if choice in ("us", "ca"):
        flag, kind = outside, "a"
    elif choice in BRITISH_PATTERN:
        flag = [x for x in inside if _a_term(x[2].group(1))]
        kind = "b"
    else:
        terms = [x for x in inside if _a_term(x[2].group(1))]
        if not terms or not outside:
            return
        flag, keep = _minority(outside, terms)
        kind = "a" if keep == "b" else "b"   # "a": move the mark inside
    for a, b, m in flag:
        if kind == "a":               # outside -> inside
            quote, mark = m.group(2), m.group(3)
            fix = mark + quote
            msg = ("Put the " + ("full stop" if mark == "." else "comma")
                   + " inside the closing quotation mark")
        else:                         # inside -> outside
            mark = m.group(2)
            quote = text[m.end(2):m.end()]
            fix = quote + mark
            msg = ("Put the " + ("full stop" if mark == "." else "comma")
                   + " after the closing quotation mark")
        if choice == "auto":
            msg += ", as elsewhere in this document."
        else:
            msg += f", as {ENGLISH[choice]} does."
        yield Suggestion(message=msg, start=a, end=b, replacement=fix)


_MONTH = "(" + "|".join(lx.MONTHS) + ")"
_US_DATE = re.compile(_MONTH + r"\s+([0-3]?\d)(?:st|nd|rd|th)?,\s*(\d{4})\b")
_UK_DATE = re.compile(r"\b([0-3]?\d)(?:st|nd|rd|th)?\s+" + _MONTH
                      + r",?\s+(\d{4})\b")


def _dates(document: Document):
    text = document.masked

    def keep(m, day: str) -> bool:
        if not 1 <= int(day) <= 31:
            return False
        if re.search(r"[-\u2013\u2014]\s*$", text[max(0, m.start() - 2):
                                                     m.start()]) or \
                re.match(r"\s*[-\u2013\u2014]", text[m.end():m.end() + 2]):
            return False              # a range: "June 3-July 9, 2020"
        return (_prose(document, m.start(), m.end())
                and not _in_reference(text, m.start(), m.end()))

    us = [(m.start(), m.end(), m.group(2), m.group(1), m.group(3))
          for m in _US_DATE.finditer(text) if keep(m, m.group(2))]
    uk = [(m.start(), m.end(), m.group(1), m.group(2), m.group(3))
          for m in _UK_DATE.finditer(text) if keep(m, m.group(1))]
    return us, uk


@rule("GN107", "date-format", Category.CONVENTION,
      "A date written month-first ('October 15, 2026') in British-pattern "
      "English, or dates written both ways in one document.",
      'American English writes "October 15, 2026"; British, Australian and '
      'Indian English write "15 October 2026", and so do many scientific '
      'journals everywhere. Canadian English uses both. With British-pattern '
      'English chosen, a month-first date is flagged. In any English, a '
      'document that writes dates both ways is flagged, towards the form it '
      'uses more (towards the month-first form when American English is '
      'chosen). Dates written only with numbers are left alone.',
      plain=("Dates are written in two ways: '15 October 2026' and 'October "
             "15, 2026'. Use the one your English uses, and keep it the same "
             "throughout the document."),
      source=SOURCE, scope="document", aggregate=True)
def gn107_dates(doc, document: Document):
    choice = _choice(document)
    us, uk = _dates(document)
    if choice in BRITISH_PATTERN:
        flag, to = us, "uk"
    elif choice == "us":
        if not us:
            return                    # day-first alone is fine in US science
        flag, to = uk, "us"
    else:
        if not us or not uk:
            return
        flag, keep = _minority(us, uk)
        to = "uk" if keep == "b" else "us"
    for a, b, day, month, year in flag:
        day = str(int(day))
        fix = (f"{day} {month} {year}" if to == "uk"
               else f"{month} {day}, {year}")
        why = (f"as {ENGLISH[choice]} does" if choice in BRITISH_PATTERN
               or choice == "us" else "as elsewhere in this document")
        yield Suggestion(message=f"Write '{fix}', {why}.",
                         start=a, end=b, replacement=fix)


# =====================================================================
# GN2xx: grammar of research prose
# =====================================================================

def _plural_noun(tok) -> bool:
    return tok.tag_ in ("NNS", "NNPS")


@rule("GN201", "agreement-across-of", Category.IMPROVEMENT,
      "A plural verb after a singular head and an 'of' phrase ('the "
      "proportion of cases were').",
      'The verb agrees with the head of its subject, not with the nearest '
      'noun. In "the proportion of cases was higher", the subject is the '
      'proportion; "cases" only says what it is a proportion of. Long "of" '
      'phrases put a plural right before the verb and pull it into the '
      'plural. Heads that follow what they quantify in careful writing '
      '("the majority of patients were", "a proportion of patients were", '
      '"a number of studies have") are not flagged.',
      plain=("The verb should match the main word of the subject, not the "
             "nearest word. In 'the proportion of cases was higher', the "
             "main word is 'proportion', which is singular."),
      source=SOURCE)
def gn201_agreement_of(doc, document: Document):
    for tok in doc:
        if tok.dep_ not in ("nsubj", "nsubjpass"):
            continue
        low = tok.lower_
        if low in lx.AGREEMENT_HEADS:
            if tok.tag_ != "NN":
                continue
            dets = [c.lower_ for c in tok.children if c.dep_ in ("det",
                                                                 "poss")]
            if low in lx.AGREEMENT_HEADS_NEED_THE and not (
                    dets and dets[0] in ("the", "this", "that")):
                continue              # "a proportion of patients were"
        elif low not in lx.AGREEMENT_PRONOUN_HEADS:
            continue
        if tok.head.pos_ not in ("VERB", "AUX"):
            continue
        if any(c.dep_ in ("conj", "cc") for c in tok.children):
            continue                  # "the mean and the median were"
        of = [c for c in tok.children if c.dep_ == "prep" and c.lower_ == "of"]
        if not of:
            continue
        objs = [c for c in of[0].children if c.dep_ == "pobj"]
        if not objs or not _plural_noun(objs[0]):
            continue
        verb = _finite(tok.head)
        if verb.i < objs[0].i or not _plural_aux(verb):
            continue
        between = doc[tok.i:verb.i]
        if any(t.lower_ in ("and", "or", ",", "(", ";", ":", "-", "\u2013",
                            "\u2014") for t in between) or \
                _second_conjunct(doc, tok):
            continue                  # a coordinated or interrupted subject
        if not _prose(document, tok.idx, verb.idx + len(verb.text)):
            continue
        fix = lx.PLURAL_TO_SINGULAR_VERB.get(verb.lower_)
        yield Suggestion(
            message=f"The subject is '{tok.text}', not '{objs[0].text}': "
                    + (f"'{fix}'." if fix else "use the singular verb."),
            start=verb.idx, end=verb.idx + len(verb.text),
            replacement=_match_case(fix, verb.text) if fix else None)


@rule("GN202", "a-number-of-singular-verb", Category.IMPROVEMENT,
      "'A number of' with a singular verb ('a number of studies has').",
      '"A number of" means "several", so the verb is plural: "a number of '
      'studies have shown". "The number of" names one number and takes the '
      'singular: "the number of studies has grown".',
      plain=("'A number of studies' means 'several studies', so the verb is "
             "plural: 'have', not 'has'. 'The number of studies' is one "
             "number, so it takes 'has'."),
      source=SOURCE)
def gn202_a_number_of(doc, document: Document):
    for tok in doc:
        if (tok.lower_ != "number" or tok.dep_ not in ("nsubj", "nsubjpass")
                or tok.head.pos_ not in ("VERB", "AUX")):
            continue
        dets = [c.lower_ for c in tok.children if c.dep_ == "det"]
        if dets != ["a"]:
            continue
        of = [c for c in tok.children if c.dep_ == "prep" and c.lower_ == "of"]
        objs = [c for c in of[0].children if c.dep_ == "pobj"] if of else []
        if not objs or not _plural_noun(objs[0]):
            continue
        verb = _finite(tok.head)
        if verb.i < objs[0].i or not _singular_verb(verb):
            continue
        if not _prose(document, tok.idx, verb.idx + len(verb.text)):
            continue
        fix = lx.SINGULAR_TO_PLURAL_VERB.get(verb.lower_)
        yield Suggestion(
            message="'A number of' means several: use the plural verb"
                    + (f", '{fix}'." if fix else "."),
            start=verb.idx, end=verb.idx + len(verb.text),
            replacement=_match_case(fix, verb.text) if fix else None)


def _one_thing(span) -> bool:
    """A noun phrase naming one thing: a singular common noun, no plural
    noun, no pronoun, no comma."""
    words = [t for t in span if not t.is_space]
    return (any(t.tag_ == "NN" for t in words)
            and not any(t.tag_ in ("NNS", "NNPS", "PRP", "CD") or t.text == ","
                        or t.lower_ == "data" for t in words))


@rule("GN203", "neither-nor-plural-verb", Category.IMPROVEMENT,
      "'Neither … nor …' joining two singular nouns, with a plural verb.",
      '"Neither A nor B" says something about A and about B separately, '
      'one at a time, so with two singular nouns the verb is singular: '
      '"neither the model nor the method is suitable". When the noun nearer '
      'the verb is plural, the verb follows it ("neither the model nor the '
      'data are"), and that is not flagged.',
      plain=("'Neither the model nor the method' talks about one thing at a "
             "time, so the verb is singular: 'is', not 'are'."),
      source=SOURCE)
def gn203_neither_nor(doc, document: Document):
    for sent in doc.sents:
        toks = [t for t in sent if not t.is_space]
        if len(toks) < 5 or toks[0].lower_ != "neither":
            continue
        nor = next((t for t in toks if t.lower_ == "nor"), None)
        if nor is None:
            continue
        verb = next((t for t in toks if t.i > nor.i
                     and t.pos_ in ("AUX", "VERB")), None)
        if verb is None or not _plural_aux(verb):
            continue
        first, second = doc[toks[0].i + 1:nor.i], doc[nor.i + 1:verb.i]
        if not (_one_thing(first) and _one_thing(second)):
            continue
        if not _prose(document, toks[0].idx, verb.idx + len(verb.text)):
            continue
        fix = lx.PLURAL_TO_SINGULAR_VERB.get(verb.lower_)
        yield Suggestion(
            message="Two singular nouns joined by 'neither … nor' take a "
                    "singular verb" + (f": '{fix}'." if fix else "."),
            start=verb.idx, end=verb.idx + len(verb.text),
            replacement=_match_case(fix, verb.text) if fix else None)


_REASON_BECAUSE = re.compile(
    r"\breasons?\b[^.;:!?\n]{0,80}?\b(is|was|are|were)\s+(because)\b(\s+of)?",
    re.IGNORECASE)


@rule("GN204", "reason-is-because", Category.IMPROVEMENT,
      "'The reason … is because' says 'because' twice.",
      '"The reason" already means "why", so "the reason is because" says it '
      'twice. Write "the reason is that …", or drop "the reason": '
      '"The counts fell because …".',
      plain=("'The reason is because' says the same thing twice. Write 'the "
             "reason is that', or just say what happened 'because' of what."),
      source=SOURCE)
def gn204_reason_because(doc, document: Document):
    text = document.masked
    for m in _REASON_BECAUSE.finditer(text):
        before = text[max(0, m.start() - 20):m.start()]
        if re.search(r"\b(for|by|with)\s+(\w+\s+)?$", before, re.I):
            continue                  # "for this reason, ..." is not a subject
        a, b = m.start(1), m.end(2)
        if not _prose(document, m.start(), b):
            continue
        verb = m.group(1)
        fix = None if m.group(3) else f"{verb} that"
        yield Suggestion(
            message="'The reason … " + verb.lower() + " because' says it "
                    "twice: write '" + verb.lower() + " that'"
                    + (" or name the cause directly." if m.group(3) else "."),
            start=a, end=b, replacement=fix)


@rule("GN205", "dangling-opener", Category.IMPROVEMENT,
      "An opening '-ing' phrase with no doer in the main clause ('Using a "
      "Bayesian model, the parameters were estimated').",
      'An opening "-ing" phrase borrows its doer from the subject of the '
      'main clause. In "Using a Bayesian model, the parameters were '
      'estimated", the parameters seem to use the model. Methods sections '
      'write this often, because the passive hides the people doing the '
      'work. Name the doer ("Using a Bayesian model, we estimated the '
      'parameters") or drop the opener ("The parameters were estimated with '
      'a Bayesian model"). The passive itself is fine. Openers that work as '
      'prepositions ("assuming", "given", "including", "according to") are '
      'not flagged.',
      plain=("The opening words ('Using a Bayesian model') have no one doing "
             "them: the sentence reads as if the parameters used the model. "
             "Say who did it ('we estimated') or move the method after the "
             "verb."),
      source=SOURCE)
def gn205_dangling_opener(doc, document: Document):
    for sent in doc.sents:
        toks = [t for t in sent if not t.is_space]
        if len(toks) < 6:
            continue
        first = toks[0]
        if first.lower_ in lx.DANGLING_PREPOSITIONS and len(toks) > 1:
            ing = toks[1]
        else:
            ing = first
        if (ing.tag_ != "VBG" or not ing.text.lower().endswith("ing")
                or ing.lower_ in lx.DANGLING_OK):
            continue
        comma = next((t for t in toks if t.text == ","), None)
        if comma is None or comma.i - first.i < 2:
            continue
        words = [t for t in doc[first.i + 1:comma.i] if t.is_alpha]
        if sum(t.is_title for t in words) * 2 > len(words):
            continue                  # a title or heading run into the text
        root = sent.root
        if root.i < comma.i or root.tag_ != "VBN":
            continue
        if not any(c.dep_ == "nsubjpass" and c.i > comma.i
                   for c in root.children):
            continue
        if not any(c.dep_ == "auxpass" for c in root.children):
            continue
        # The opener must hang on this main verb, not on something inside it.
        if ing.head.i != root.i and ing.head.head.i != root.i:
            continue
        if any(t.lower_ in ("we", "i", "us", "our") for t in toks):
            continue
        if document.section_at(first.idx) == "references":
            continue
        if not _prose(document, first.idx, comma.idx):
            continue
        subj = next(c for c in root.children if c.dep_ == "nsubjpass")
        yield Suggestion(
            message=f"Who is '{ing.lower_}'? The main clause names "
                    f"'{subj.text}', not the doer — say who did it, or move "
                    "the method after the verb.",
            start=first.idx, end=comma.idx)


_ARTICLE = re.compile(r"(?<![\w$-])(a|an|A|An)\s+([A-Za-z][A-Za-z0-9]*)"
                      r"(?![A-Za-z0-9])")


@rule("GN206", "a-or-an-before-abbreviation", Category.IMPROVEMENT,
      "'a' or 'an' that does not match how an abbreviation is said ('a "
      "MCMC sampler', 'an UK cohort').",
      'The article follows the first sound, not the first letter. '
      'Abbreviations read letter by letter that start with F, H, L, M, N, R, '
      'S or X begin with a vowel sound ("an MCMC sampler", "an RCT", "an HIV '
      'test"); those read as words, or starting with a "you" sound, take '
      '"a" ("a NATO grant", "a SNP", "a UK cohort"). Only abbreviations '
      'with one settled pronunciation are checked; "SIR" and "SEIR" are '
      'said both ways, so either article is accepted.',
      plain=("Use 'an' before a vowel sound and 'a' before other sounds. "
             "Abbreviations are said aloud letter by letter, so 'MCMC' starts "
             "with 'em' and takes 'an', while 'UK' starts with 'you' and "
             "takes 'a'."),
      source=SOURCE)
def gn206_article_abbreviation(doc, document: Document):
    text = document.masked
    for m in _ARTICLE.finditer(text):
        typed, word = m.group(1), m.group(2)
        entry = lx.ABBREVIATION_ARTICLE.get(word)
        if entry is None or typed.lower() == entry[0]:
            continue
        if typed[0].isupper():
            # "Group A HIV ..." is a label; only a sentence's first word.
            lead = text[:m.start()].rstrip(" \t")
            if lead and lead[-1] not in ".!?\n:":
                continue
        if not _prose(document, m.start(), m.end()):
            continue
        fix = _match_case(entry[0], typed)
        yield Suggestion(
            message=f"'{word}' is said '{entry[1]}', so write '{fix} {word}'.",
            start=m.start(1), end=m.end(1), replacement=fix)


@rule("GN207", "data-singular-and-plural", Category.CONVENTION,
      "'data' treated as plural in one place and singular in another.",
      'Both "the data are" and "the data is" are accepted: the plural is '
      'the older scientific habit and many journals still ask for it; the '
      'singular, for data as one body of information, is now common '
      'everywhere. What reads as careless is a mixture in one document. '
      'The rarer form is flagged, towards the one the document uses more.',
      plain=("You treat 'data' as plural in some places ('the data are') "
             "and singular in others ('the data is'). Both are accepted; "
             "pick one and use it throughout."),
      source=SOURCE, scope="document")
def gn207_data_agreement(doc, document: Document):
    singular, plural = [], []
    for tok in doc:
        if tok.lower_ != "data":
            continue
        if any(c.dep_ in ("conj", "cc") for c in tok.children) \
                or tok.dep_ == "conj":
            continue                  # "data and code are": plural anyway
        says = []                     # (number, token showing it)
        for c in tok.children:
            if c.dep_ == "det" and c.i < tok.i:
                if c.lower_ in ("this", "that"):
                    says.append(("s", c))
                elif c.lower_ in ("these", "those"):
                    says.append(("p", c))
        if tok.dep_ in ("nsubj", "nsubjpass") and \
                tok.head.pos_ in ("VERB", "AUX"):
            verb = _finite(tok.head)
            if verb.i > tok.i and "," not in doc[tok.i:verb.i].text:
                if _singular_verb(verb):
                    says.append(("s", verb))
                elif _plural_verb(verb) and verb.lower_ != "am":
                    says.append(("p", verb))
        numbers = {n for n, _ in says}
        if len(numbers) != 1:
            continue                  # no sign, or a slip inside one phrase
        t = says[-1][1]
        rec = (t.idx, t.idx + len(t.text), t)
        (singular if numbers == {"s"} else plural).append(rec)
    singular = [x for x in singular if _prose(document, x[0], x[1])]
    plural = [x for x in plural if _prose(document, x[0], x[1])]
    if not singular or not plural:
        return
    if len(singular) == len(plural):
        flag, other, form = singular, plural, "singular"
    elif len(singular) < len(plural):
        flag, other, form = singular, plural, "singular"
    else:
        flag, other, form = plural, singular, "plural"
    # One card for the document: the mixture is the finding, not each use.
    a, b, _ = flag[0]
    n, more = len(other), len(flag) - 1
    yield Suggestion(
        message=f"'data' is {form} here"
                + (f" (and {more} more time{'s' if more > 1 else ''})"
                   if more else "")
                + f" but {'plural' if form == 'singular' else 'singular'} "
                f"{'once' if n == 1 else f'{n} times'} elsewhere — pick one.",
        start=a, end=b)


@rule("GN208", "which-for-defining-clause-us", Category.PREFERENCE,
      "'which' starting a clause that defines its noun, in American "
      "English ('the model which we fitted').",
      'American usage, as most US style manuals teach it, starts a clause '
      'that tells you which one is meant with "that" ("the model that we '
      'fitted"), and keeps "which" for a clause that adds a comment after a '
      'comma ("the model, which we fitted in 2024, ..."). British, '
      'Australian and Indian English use "which" for both, so this is '
      'checked only with American English chosen, and as a preference. '
      '"In which", "of which" and the like are never flagged.',
      plain=("In American English, 'that' starts a clause that says which "
             "one you mean ('the model that we fitted'), and 'which' "
             "follows a comma. British English uses 'which' for both."),
      source=SOURCE)
def gn208_which_that(doc, document: Document):
    if _choice(document) != "us":
        return
    for tok in doc:
        if tok.lower_ != "which" or tok.i == 0:
            continue
        if tok.dep_ not in ("nsubj", "nsubjpass", "dobj") or \
                tok.head.dep_ != "relcl":
            continue
        prev = doc[tok.i - 1]
        if prev.is_space or prev.pos_ not in ("NOUN", "PROPN"):
            continue                  # ", which", "in which", a masked cite
        if tok.head.head.i != prev.i and tok.head.head.i > prev.i:
            continue
        a, b = tok.idx, tok.idx + len(tok.text)
        if not _prose(document, prev.idx, b):
            continue
        yield Suggestion(
            message="In American usage, a clause that says which one you "
                    "mean starts with 'that'.",
            start=a, end=b, replacement=_match_case("that", tok.text))

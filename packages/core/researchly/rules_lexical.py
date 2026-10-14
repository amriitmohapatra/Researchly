"""Lexicon/regex rules (word- and phrase-level).

These run on the MASKED text, so anything inside code, math, citations, or
LaTeX commands can never match. All offsets map 1:1 to the source file.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from typing import Iterable

from . import lexicons as lx
from .document import Document
from .engine import Category, Suggestion, rule


def _finditer(pattern: str, text: str) -> Iterable[re.Match]:
    return re.finditer(pattern, text, re.IGNORECASE)


# ---------------------------------------------------------------------------
# W2xx — words and tone
# ---------------------------------------------------------------------------

@rule("W201", "grand-word", Category.IMPROVEMENT,
      "Prefer plain words to grand ones (utilize → use).",
      'Complexity should live in your ideas, never in your vocabulary. '
      'Grand words are camouflage, and experienced readers read them as '
      'camouflage.',
      plain=("A simpler word says the same thing: 'use' instead of 'utilize'. "
             'Big words do not make the science bigger, and experienced readers '
             'notice them.'),
      source="§6", fix_safety="safe")
def w201_grand_words(doc, document: Document):
    for word, plain in lx.GRAND_WORDS.items():
        for m in _finditer(rf"\b{word}\b", document.masked):
            if word in lx.GRAND_ONLY_AS_VERB and not _is_verb(doc, m.start()):
                continue
            yield Suggestion(
                message=f"Plainer: '{plain}'.",
                start=m.start(), end=m.end(), replacement=plain)


def _is_verb(doc, offset: int) -> bool:
    if doc is None:
        return True
    span = doc.char_span(offset, offset + 1, alignment_mode="expand")
    return bool(span) and span[0].pos_ in ("VERB", "AUX")


@rule("W202", "wordy-phrase", Category.IMPROVEMENT,
      "Compress wordy phrases (due to the fact that → because).",
      'Cut ruthlessly, but second: on a revision pass, try to remove ten '
      'per cent of the words without losing meaning. You almost always '
      'can, and the prose tightens every time.',
      plain=("This phrase can be shorter: 'because' instead of 'due to the fact "
             "that'. Shorter is easier to read, and the meaning stays the same."),
      source="§6", fix_safety="safe")
def w202_wordy_phrases(doc, document: Document):
    for phrase, tight in lx.WORDY_PHRASES.items():
        for m in _finditer(rf"\b{re.escape(phrase)}\b", document.masked):
            yield Suggestion(
                message=f"Tighter: '{tight}'.",
                start=m.start(), end=m.end(), replacement=tight)


@rule("W203", "hype", Category.CONVENTION,
      "Buzzwords (novel, cutting-edge) signal thin substance.",
      'Credibility comes from concreteness: facts, figures, mechanisms. '
      'Buzzwords and hype do the opposite; they signal that the substance '
      'may be thin. Let the numbers carry the weight. A convention, not '
      "an error: 'novel' survives review in some venues; you decide.",
      plain=("Words like 'novel' and 'cutting-edge' promise a lot but show "
             'nothing. Readers trust facts and numbers more than big claims. '
             'Some journals accept these words, so this is your call.'),
      source="§6")
def w203_hype(doc, document: Document):
    text = document.masked
    for word in lx.HYPE_WORDS:
        for m in _finditer(rf"\b{re.escape(word)}\b", text):
            follow = text[m.end():m.end() + 40].strip().lower()
            if any(follow.startswith(t) for t in lx.HYPE_TECHNICAL_FOLLOWERS):
                continue  # "novel coronavirus" is technical, not hype
            yield Suggestion(
                message="Hype word — let the result carry the weight, or "
                        "state concretely what is new.",
                start=m.start(), end=m.end())


@rule("W204", "intensifier", Category.PREFERENCE,
      "Intensifiers (very, extremely) rarely add information.",
      "In calibrated scientific prose, 'very important' is not more "
      "important than 'important'. If magnitude matters, quantify it.",
      plain=("'Very' or 'extremely' does not add information. 'Very important' "
             "is not more important than 'important'. If size matters, give the "
             'number.'),
      source="§6")
def w204_intensifiers(doc, document: Document):
    for word in lx.INTENSIFIERS:
        for m in _finditer(rf"\b{word}\b", document.masked):
            yield Suggestion(
                message="Consider deleting, or quantify instead.",
                start=m.start(), end=m.end())


@rule("W205", "filler", Category.IMPROVEMENT,
      "Throat-clearing ('It should be noted that…') delays the point.",
      "Every sentence either reduces or increases the reader's mental "
      "load. 'It is important to note that X' is usually just 'X': if it "
      'matters, the end of the sentence will say so better than an '
      'announcement.',
      plain=("'It should be noted that' delays the point. Remove it and say the "
             'point directly. If it matters, the reader will see that.'),
      source="§6", fix_safety="safe")
def w205_filler(doc, document: Document):
    for phrase in lx.FILLER_PHRASES:
        for m in _finditer(rf"\b{re.escape(phrase)}\b", document.masked):
            yield Suggestion(
                message="Cut the preamble; state the point directly.",
                start=m.start(), end=m.end(), replacement="")


@rule("W206", "redundant-pair", Category.IMPROVEMENT,
      "Redundant pairs (each and every, end result).",
      'Omit needless words: one of the pair is doing no work.',
      plain=("These two words say the same thing, like 'each and every' or 'end "
             "result'. Keep one."),
      source="§6", fix_safety="safe")
def w206_redundant_pairs(doc, document: Document):
    for pair, keep in lx.REDUNDANT_PAIRS.items():
        for m in _finditer(rf"\b{re.escape(pair)}\b", document.masked):
            yield Suggestion(
                message=f"'{keep}' says the same.",
                start=m.start(), end=m.end(), replacement=keep)


@rule("W207", "doubled-word", Category.CORRECTION,
      "Accidentally doubled word (the the).",
      'A mechanical slip the eye forgives and the reader stumbles on; the '
      'read-aloud test catches these.',
      plain=("A word is repeated by accident, like 'the the'. Delete one."),
      source="§8", fix_safety="safe")
def w207_doubled_word(doc, document: Document):
    masked = document.masked
    for m in re.finditer(r"\b([A-Za-z]+)[ \t]+\1\b", masked,
                         re.IGNORECASE):
        if m.group(1).lower() in {"had", "that"}:  # "had had" can be valid
            continue
        # Only a slip of the keyboard: one space apart, a real word, not a
        # run. "Yes   Yes" is a table row, "s S" and "P P" are maths, and
        # "Yes Yes Yes" a flattened row of a converted PDF (P33).
        gap = document.original[m.end(1):m.end() - len(m.group(1))]
        if len(gap) >= 3 and not gap.strip():     # aligned columns
            continue
        if len(m.group(1)) == 1 and m.group(1).lower() != "a":
            continue
        if re.match(rf"[ \t]+{m.group(1)}\b", masked[m.end():],
                    re.IGNORECASE) or re.search(
                rf"\b{m.group(1)}[ \t]+$", masked[max(0, m.start() - 40):
                                                     m.start()], re.IGNORECASE):
            continue
        # "and $C(0)$ and": the words were never adjacent in the source.
        if document.masked_content(m.start(), m.end()):
            continue
        yield Suggestion(
            message="Doubled word — delete one.",
            start=m.start(), end=m.end(), replacement=m.group(1))


@rule("W208", "contraction", Category.CONVENTION,
      "Contractions are unconventional in formal scientific prose.",
      'A register convention, not a grammar rule: journals and theses '
      'conventionally avoid contractions. Fine in talks, blogs, and '
      'emails.',
      plain=("Short forms like 'don't' or 'it's' are unusual in papers and "
             "theses. Write the full words: 'do not', 'it is'. Fine in talks and "
             'emails.'),
      source="§6")
def w208_contractions(doc, document: Document):
    text = document.masked
    for word in lx.CONTRACTIONS:
        for m in _finditer(rf"\b{re.escape(word)}\b", text):
            stem = m.group(0).split("'")[0]
            if len(stem) > 1 and stem.isupper():
                continue                  # "WHO's": an acronym's possessive
            full = lx.CONTRACTION_EXPANSIONS.get(word)
            # "it's been" is "it has been": leave the 's forms to the writer
            # when a participle follows.
            if full and word.endswith("'s") and re.match(
                    r"\s+(?:been|got)\b", text[m.end():m.end() + 8], re.I):
                full = None
            yield Suggestion(
                message=(f"Expand the contraction for formal register: "
                         f"'{_match_initial(full, m.group(0))}'."
                         if full else
                         "Expand the contraction for formal register."),
                start=m.start(), end=m.end(),
                replacement=_match_initial(full, m.group(0)) if full else None)
    # "dont", "doesnt": the apostrophe is missing too. A keyboard would put
    # it back; in a paper the full form is the fix. S001 leaves these words
    # to this rule, so the writer sees one card, not two.
    for m in re.finditer(r"\b[A-Za-z]+\b", text):
        full = lx.APOSTROPHELESS_CONTRACTIONS.get(m.group(0).lower())
        if full is None or (m.group(0).isupper() and len(m.group(0)) > 1):
            continue
        fixed = _match_initial(full, m.group(0))
        yield Suggestion(
            message=f"'{m.group(0)}' is a contraction without its "
                    f"apostrophe. In formal prose write '{fixed}'.",
            start=m.start(), end=m.end(), replacement=fixed)


def _match_initial(full: str | None, typed: str) -> str | None:
    """"Don't" → "Do not"; "don't" → "do not"; "I'm" stays "I am"."""
    if full is None:
        return None
    if typed[:1].isupper():
        return full[:1].upper() + full[1:]
    return full


@rule("W212", "uncountable-plural", Category.CORRECTION,
      "A noun that has no plural in standard English (softwares, "
      "informations).",
      'Mass nouns such as information, software, equipment and advice are '
      'uncountable in English: they take no -s, and a quantity is given '
      "with a counter ('three software packages', 'two pieces of "
      "advice'). Latin plurals such as criteria and phenomena are already "
      'plural and take no second -s.',
      plain=("This word has no plural in English. Write 'software', not "
             "'softwares'; to count, say 'three software packages' or 'two "
             "pieces of information'."),
      source="Swan", fix_safety="review")
def w212_uncountable_plural(doc, document: Document):
    for m in re.finditer(r"\b[A-Za-z]+\b", document.masked):
        typed = m.group(0)
        base = lx.UNCOUNTABLE_PLURALS.get(typed.lower())
        if base is None or (typed.isupper() and len(typed) > 1):
            continue
        fixed = _match_initial(base, typed)
        if base in lx.LATIN_PLURALS:
            msg = f"'{base}' is already plural: write '{fixed}'."
        else:
            msg = (f"'{typed}' has no plural: write '{fixed}'. To count "
                   f"it, name a unit ('two pieces of {base}').")
        yield Suggestion(message=msg, start=m.start(), end=m.end(),
                         replacement=fixed)


@rule("W209", "in-terms-of", Category.PREFERENCE,
      "'In terms of' is usually a vague connector.",
      'It typically hides the real relationship between ideas; naming the '
      "relationship ('as', 'for', 'measured by') is more precise.",
      plain=("'In terms of' is vague. Say what the relationship really is: 'as', "
             "'for', 'measured by'."),
      source="§6")
def w209_in_terms_of(doc, document: Document):
    for m in _finditer(r"\bin terms of\b", document.masked):
        yield Suggestion(
            message="Name the actual relationship instead.",
            start=m.start(), end=m.end())


# ---------------------------------------------------------------------------
# C3xx — calibration and claims
# ---------------------------------------------------------------------------

# In mathematics a proof is the evidence: "We prove that S(5) = 47,176,870"
# is calibrated, not an overclaim (P30 bench: 12 flags in one Busy Beaver
# paper). A sentence with maths in it, or the vocabulary of proofs, keeps
# its "prove".
_PROOF_WORDS = re.compile(
    r"\b(?:theorem|lemma|corollary|proposition|conjecture|axiom|"
    r"by induction|formally|formal proof|proof assistant|Coq|Lean|"
    r"Isabelle|Agda)\b", re.IGNORECASE)


def _is_mathematical(document: Document, a: int, b: int) -> bool:
    return (document.masked_content(a, b)
            or bool(_PROOF_WORDS.search(document.masked, a, b)))


@rule("C302", "overclaim", Category.CONVENTION,
      "Overclaiming (prove, conclusively) exceeds what empirical evidence supports.",
      'Reserve strong verbs for strong evidence. An unqualified claim '
      "reads as naive; 'prove' almost never belongs in empirical science. "
      'Models and data support, suggest, indicate, or are consistent '
      'with. Match the confidence of the language to the strength of the '
      'grounds.',
      plain=("Words like 'prove' and 'conclusively' claim more than most studies "
             "can show. Data and models usually 'suggest', 'indicate' or "
             "'support'. Match the strength of your words to the strength of "
             'your evidence.'),
      sections_only=("abstract", "results", "discussion", "conclusion",
                     "introduction", "limitations"),
      source="§4")
def c302_overclaim(doc, document: Document):
    sents = [(sent.start_char, sent.end_char) for sent in doc.sents]
    starts = [a for a, _ in sents]
    for pat in lx.OVERCLAIM_PATTERNS:
        for m in _finditer(pat, document.masked):
            if m.group(0).lower().startswith("prov"):
                i = max(0, bisect_right(starts, m.start()) - 1)
                a, b = sents[i] if sents else (0, len(document.masked))
                if _is_mathematical(document, a, b):
                    continue
            yield Suggestion(
                message="Calibrate: 'suggests', 'indicates', 'is consistent "
                        "with' — unless the evidence truly compels.",
                start=m.start(), end=m.end())


@rule("C305", "assertive-adverb", Category.CONVENTION,
      "Assertive adverbs (clearly, obviously) assert what structure should show.",
      'If it were clear, the word would be unnecessary; if it is not, the '
      'word will not make it so. Put the important idea in the stress '
      'position and let the evidence do the convincing.',
      plain=("Words like 'clearly' and 'obviously' tell the reader to agree "
             'instead of showing them why. If the point is clear, you do not '
             'need the word. If it is not, the word will not help. Let the '
             'evidence do the work.'),
      source="§4", aggregate=True)
def c305_assertive(doc, document: Document):
    for pat in lx.ASSERTIVE_PATTERNS:
        for m in _finditer(pat, document.masked):
            yield Suggestion(
                message="Delete, or show the evidence that makes it clear.",
                start=m.start(), end=m.end())


@rule("C304", "bare-significant", Category.CONVENTION,
      "Bare 'significant' is ambiguous (statistical vs substantive).",
      "In a results context, 'significant' invites the reader to hear "
      "'statistically significant'. If that is meant, say so, with the "
      'estimate and interval; if practical importance is meant, '
      "'substantial' or a quantified statement is clearer. Uncertainty is "
      'not a caveat; it is the finding.',
      plain=("'Significant' can mean two things: a statistical test passed, or "
             'the effect is large enough to matter. Say which one you mean. If '
             'it is the test, give the estimate and its interval too.'),
      sections_only=("abstract", "results", "discussion", "conclusion",
                     "limitations"),
      source="§9.3", aggregate=True)
def c304_significant(doc, document: Document):
    text = document.masked
    for m in _finditer(r"\bsignificant(?:ly)?\b", text):
        before = text[max(0, m.start() - 30):m.start()].lower()
        if re.search(r"(statistically|clinically|epidemiologically|"
                     r"biologically|practically)\s*$", before):
            continue
        yield Suggestion(
            message="Specify: 'statistically significant' (with estimate and "
                    "interval) or 'substantial' if you mean magnitude.",
            start=m.start(), end=m.end())


_ROMAN = re.compile(r"^(?=[IVX]{2,}$)X{0,3}(?:IX|IV|V?I{0,3})$")


_CAPS_RUN = re.compile(r"\b[A-Z][A-Z&'’-]+(?:\s+[A-Z][A-Z&'’-]+){2,}\b")


@rule("F601", "acronym-undefined", Category.CONVENTION,
      "Acronym used without definition at first use.",
      'Define a term the first time you use it, once, briefly, then use '
      'it consistently. Your reader is expert, but rarely in every '
      'discipline you are combining.',
      plain=('This abbreviation appears without its full name. Write the full '
             'name the first time, with the abbreviation in brackets, then use '
             'the abbreviation after that. Readers from other fields may not '
             'know it.'),
      source="§9.1",
      scope="document")
def f601_acronyms(doc, document: Document):
    text = document.masked
    # v0.2: an acronym defined in a List of Abbreviations counts as defined.
    # Detected as "ACR — full name" / "ACR: full name" / "ACR  full name"
    # lines anywhere in the ORIGINAL text (abbreviation lists are often in
    # front matter the masking may have touched).
    predefined = {
        m.group(1) for m in re.finditer(
            r"^\s*([A-Z]{2,6})s?\s*(?:[—–:\-]|\s{2,})\s*[A-Z(]",
            document.original, re.MULTILINE)
    }

    def in_caps_zone(start: int, end: int) -> bool:
        # Dogfooding tune: ALL-CAPS titles/headings ("SAW SWEE HOCK SCHOOL
        # OF PUBLIC HEALTH") are capitalized words, not acronyms. If the
        # surrounding window is mostly uppercase, this is display text.
        window = text[max(0, start - 45):min(len(text), end + 45)]
        alpha = [c for c in window if c.isalpha()]
        if not alpha:
            return True
        if sum(1 for c in alpha if c.isupper()) / len(alpha) > 0.55:
            return True
        # A run of three capitalised words is a title set in capitals
        # ("NATIONAL BUREAU OF ECONOMIC RESEARCH 1050 ...") even when an
        # address beside it dilutes the window (P33).
        line_a = text.rfind("\n", 0, start) + 1
        line_b = text.find("\n", end)
        line = text[line_a:line_b if line_b != -1 else len(text)]
        return any(a <= start - line_a < b for a, b in (
            (r.start(), r.end()) for r in _CAPS_RUN.finditer(line)))

    seen: set[str] = set()
    for m in re.finditer(r"\b([A-Z]{2,6})s?\b", text):
        acr = m.group(1)
        if acr in seen or acr in lx.ACRONYM_ALLOWLIST or acr in predefined:
            continue
        if _ROMAN.match(acr):                 # "Phase III", "Chapter II"
            continue
        if in_caps_zone(m.start(), m.end()):
            continue
        # Names with a number attached are labels, not abbreviations to
        # spell out: variant lineages (BA.1, XBB.1.5) and model orders
        # (AR(2), ARIMA(1,1,0)).
        if re.match(r"(?:\.\d|\(\d)", text[m.end():m.end() + 2]):
            continue
        # Author-initials guard ("Anderson KN," / "Chew LZX."): a short
        # caps token right after a capitalized surname, followed by
        # punctuation, is a name in a reference string, not an acronym.
        if len(acr) <= 3:
            before = text[max(0, m.start() - 20):m.start()]
            after = text[m.end():m.end() + 2]
            if (re.search(r"[A-Z][a-z]{2,}\s+$", before)
                    and re.match(r"\s*[,.;]", after or ",")):
                continue
        seen.add(acr)
        # Defined here? pattern "Full Name (ACR)" → first use is inside parens
        prev = text[max(0, m.start() - 2):m.start()]
        if prev.endswith("(") or prev.endswith("( "):
            continue
        # Defined anywhere earlier in the document?
        if re.search(rf"\({acr}s?\)", text[:m.start()]):
            continue
        yield Suggestion(
            message=f"First use of '{acr}' — spell it out once: "
                    f"'full name ({acr})'.",
            start=m.start(), end=m.end())


# ---------------------------------------------------------------------------
# G1xx regex members — stress position
# ---------------------------------------------------------------------------

@rule("G108", "weak-stress-position", Category.IMPROVEMENT,
      "Sentence trails off in attribution; the finding is buried mid-sentence.",
      'The end of a sentence is the stress position, the point of natural '
      "emphasis. 'Attack rates rose sharply, according to our "
      "simulations' spends the emphasis on the attribution; 'Our "
      "simulations show attack rates rising sharply' spends it on the "
      'result. Put what you most want remembered at the end.',
      plain=('The end of a sentence is where readers remember things, and this '
             "one ends on 'according to our simulations' rather than on the "
             "finding. Put the result at the end: 'Our simulations show attack "
             "rates rising sharply.'"),
      source="§5.2.2")
def g108_stress_position(doc, document: Document):
    for sent in doc.sents:
        stext = sent.text.rstrip()
        body = stext.rstrip(".!?").rstrip()
        for pat in lx.TRAILING_QUALIFIERS:
            m = re.search(pat, body, re.IGNORECASE)
            if m:
                start = sent.start_char + m.start()
                yield Suggestion(
                    message="Move the attribution earlier; end on the finding.",
                    start=start, end=start + len(m.group(0)))
                break


# ---------------------------------------------------------------------------
# E7xx — rules mined from the owner's lecture notes on scientific writing for
# infectious disease modelling (provenance: docs/knowledge-base.md §1)
# ---------------------------------------------------------------------------

@rule("E701", "empty-phrase", Category.CONVENTION,
      "Low-information phrase ('sheds light on', 'holistic understanding').",
      'Sentences that sound substantive but carry no information waste '
      "the reader's attention. A claim that a study offers 'a holistic "
      "understanding' of a system could describe any paper; a sentence "
      'naming the mechanism or estimate the study actually produced tells '
      'the reader what was learned. Say specifically what the work shows.',
      plain=("This phrase sounds important but says nothing specific. 'Sheds "
             "light on' or 'a holistic understanding' could describe any paper. "
             'Say exactly what your work shows or measures.'),
      source="lecture", aggregate=True)
def e701_empty_phrase(doc, document: Document):
    for phrase in lx.EMPTY_PHRASES:
        for m in _finditer(rf"\b{re.escape(phrase)}\b", document.masked):
            yield Suggestion(
                message="Replace with the concrete thing the work "
                        "shows/does/estimates.",
                start=m.start(), end=m.end())


@rule("E704", "uncited-consensus", Category.CONVENTION,
      "'Is known/considered to be…' — who says? Cite it or own it.",
      "Keep facts and opinions apart. A passive consensus formula ('X is "
      "considered/known to be') hides whose view it is: if the point is "
      'established, cite the evidence; if it is your judgement, own it '
      "('we consider').",
      plain=("'Is known to be' or 'is considered' does not say who knows or "
             'considers it. If it is established, add a citation. If it is your '
             "own view, say 'we consider'."),
      source="lecture", aggregate=True)
def e704_uncited_consensus(doc, document: Document):
    for sent in doc.sents:
        m = re.search(lx.CONSENSUS_RX, sent.text)
        if not m:
            continue
        # a citation in the same sentence satisfies the demand (numeric
        # [12] / (Author, 2020) / et al. survive masking in Word/plain text)
        if re.search(r"\[\d|\(\d{4}|\bet al\b|\(\w+ (?:and|&) \w+,? \d{4}",
                     sent.text):
            continue
        start = sent.start_char + m.start()
        yield Suggestion(
            message="Add the citation that establishes this, or attribute "
                    "the judgement explicitly.",
            start=start, end=start + len(m.group(0)))


@rule("E705", "absolute-novelty", Category.CONVENTION,
      "'Has not been studied' — risky absolute claim; soften and cite.",
      'Avoid claiming that something has never been done unless you are '
      'certain: the literature is large, and a reviewer who knows one '
      "counterexample will discount the claim. Soften with 'to our "
      "knowledge' and cite the closest existing attempts; 'few studies "
      "have' makes the same move safely.",
      plain=("Saying something 'has never been studied' is risky. The literature "
             'is large, and one counter-example from a reviewer will weaken your '
             "claim. Write 'to our knowledge' and cite the closest earlier work."),
      source="lecture", aggregate=True)
def e705_absolute_novelty(doc, document: Document):
    for sent in doc.sents:
        low = sent.text.lower()
        if any(s in low for s in lx.KNOWLEDGE_SOFTENERS):
            continue
        for rx in lx.NOVELTY_RX:
            m = re.search(rx, sent.text, re.IGNORECASE)
            if m:
                start = sent.start_char + m.start()
                yield Suggestion(
                    message="Soften: 'to our knowledge, X has not been…' — "
                            "and cite the nearest prior work.",
                    start=start, end=start + len(m.group(0)))
                break


@rule("E706", "missing-comparator", Category.CONVENTION,
      "'Relatively' — compared with what?",
      "Words such as 'additional', 'increase', 'relatively' and "
      "'proportion' are incomplete without a reference point: 'relatively "
      "high' leaves the reader asking 'relative to what?'. Name the "
      'comparator, or check that the context allows only one reading; '
      'otherwise drop the word.',
      plain=("'Relatively', 'higher' or 'additional' need a comparison: relative "
             'to what? Name the thing you are comparing with, or remove the word '
             'if the sentence works without it.'),
      source="lecture", aggregate=True)
def e706_missing_comparator(doc, document: Document):
    for m in _finditer(r"\brelatively\b", document.masked):
        yield Suggestion(
            message="Name the comparison ('relative to X'), or delete.",
            start=m.start(), end=m.end())


@rule("AB801", "vague-forward-reference", Category.CONVENTION,
      "'Results will be discussed' — say what the results are.",
      'An abstract that promises results without stating any gives a '
      'programme committee nothing to judge and readers no reason to '
      'attend. State at least one concrete finding instead of deferring '
      'it.',
      plain=('Your abstract says results will be discussed but does not say what '
             'they are. Readers decide from the abstract whether to read on. '
             'Give them at least one real finding.'),
      sections_only=("abstract",),
      source="course-U2", aggregate=True)
def ab801_vague_forward(doc, document: Document):
    for m in _finditer(lx.ABSTRACT_VAGUE_RX, document.masked):
        yield Suggestion(
            message="State the actual finding (with a number if you have "
                    "one) instead of promising it.",
            start=m.start(), end=m.end())


@rule("L901", "serial-summary-opener", Category.IMPROVEMENT,
      "'There are many studies on…' — catalogue opener, not an argument.",
      'A literature review should be a conversation that leads to your '
      "gap, not a catalogue: 'Many studies have looked at X. A reported, "
      "B reported' restates instead of synthesizing. Open with the "
      "synthesis point ('Evidence consistently links X to Y'), then use "
      'the sources as support, and let the review build toward a clear '
      'gap statement.',
      plain=("'There are many studies on' lists the literature instead of making "
             'a point. Start with what the studies show together, then use them '
             'as support, and lead to what is still missing.'),
      source="course-U1", aggregate=True)
def l901_serial_summary(doc, document: Document):
    for rx in lx.LITREVIEW_FILLER:
        for m in _finditer(rx, document.masked):
            yield Suggestion(
                message="Lead with your synthesis of what these studies "
                        "show, then cite them.",
                start=m.start(), end=m.end())


@rule("D902", "missing-niche-signal", Category.IMPROVEMENT,
      "Introduction has no detectable gap statement (CARS Move 2).",
      'The gap statement is the turn on which an Introduction pivots: it '
      'links what is already known to what this study sets out to do, and '
      'creates the need for your contribution. It is usually one short '
      'critical sentence, signalled by a contrastive turn (however, '
      'although, yet) plus a gap word (limited, few, little, remains '
      'unclear, has not been). No signal was detected here: either the '
      'niche is missing, or it is phrased so gently the reader may not '
      'notice it.',
      plain=('An introduction needs a sentence that says what is still unknown '
             'or unsolved. That sentence is why your study exists. We could not '
             "find one here. It usually starts with 'However' or 'Although' and "
             'names what is missing.'),
      source="Shehzad",
      scope="document")
def d902_missing_niche(doc, document: Document):
    intro = [h for h in document.headings if h.section == "introduction"]
    if not intro:
        return
    start = intro[0].start
    # The section runs to the next heading of another section; its own
    # subsections ("Background", "Aims") are part of it.
    ends = [h.start for h in document.headings
            if h.start > start and h.section != "introduction"]
    end = min(ends) if ends else len(document.masked)
    text = document.masked[start:end]
    if len(text) < 600:            # stub sections can't be judged
        return
    contrastive = re.search(
        r"\b(however|although|nevertheless|yet|whereas|despite|"
        r"in contrast|but)\b", text, re.IGNORECASE)
    gapword = re.search(
        r"\b(limited|few(er)? studies|little (is known|attention|work)|"
        r"remains? (unclear|unknown|unexplored|unquantified|"
        r"to be (seen|determined))|not (yet )?been|no (prior |previous )?"
        r"(study|studies|work|research)|gap|understudied|overlooked|"
        r"paucity|scarce)\b", text, re.IGNORECASE)
    if contrastive and gapword:
        return
    yield Suggestion(
        message="Where is the gap? Add the contrastive turn that names "
                "what remains unknown and that your study answers "
                "('However, … remains unquantified.').",
        start=start, end=start + len(intro[0].text))


# ---------------------------------------------------------------------------
# D903–D905 — the gap as an argument, carried to the end (2026-10-14).
# Section-gated on the headings themselves: a pasted paragraph with no
# heading cannot say whether "fills the gap" is an aim or a verdict.
# ---------------------------------------------------------------------------

def _sentences_in(doc, document: Document, sections) -> list:
    """(index, sentence) of every sentence in `sections`, plus the full
    sentence list, so a rule can look at the neighbours."""
    sents = list(doc.sents)
    return sents, [(i, s) for i, s in enumerate(sents)
                   if document.section_at(s.start_char) in sections]


def _muted(document: Document, rule_id: str) -> bool:
    cfg = getattr(document, "config", None)
    return rule_id in set(getattr(cfg, "disabled", ()) or ())


@rule("D903", "gap-without-stake", Category.IMPROVEMENT,
      "A gap stated as a bare absence, with nothing on what is at stake.",
      'Something missing from the literature is not yet a research gap: '
      'the gap is the case for why the missing answer matters. "No study '
      'has examined X" or "X remains underexplored" records only that '
      'something is missing, and much is missing for good reason. The '
      'case rests on the cost of not knowing: which model, policy or '
      'theory fails while the question stays open, and who will use the '
      'answer. Name the decision made without it, the estimate it biases, '
      'or the untested assumption a model rests on, in the gap sentence '
      'or the one after it.',
      plain=("This sentence says something has not been studied, but not "
             "why that matters. Many things are unstudied for good reason. "
             "Say what goes wrong, or who is left guessing, if the question "
             "stays open."),
      sections_only=("introduction",),
      source="workshop-S2+Sandberg2011+Alvesson2011", aggregate=True,
      scope="document")
def d903_gap_without_stake(doc, document: Document):
    sents, intro = _sentences_in(doc, document, ("introduction",))
    e705_live = not _muted(document, "E705")
    for i, sent in intro:
        text = sent.text
        m = None
        for rx in lx.ABSENCE_GAP_RX:
            m = re.search(rx, text, re.IGNORECASE)
            if m:
                break
        if not m:
            continue
        low = text.lower()
        # An unsoftened "has not been studied" is E705's card already: one
        # card per span, and its fix comes first.
        if e705_live and not any(s in low for s in lx.KNOWLEDGE_SOFTENERS) \
                and any(re.search(rx, text, re.IGNORECASE)
                        for rx in lx.NOVELTY_RX):
            continue
        window = [sents[j].text for j in range(max(0, i - 1),
                                               min(len(sents), i + 3))
                  if document.section_at(sents[j].start_char)
                  == "introduction"]
        if any(re.search(rx, w, re.IGNORECASE)
               for rx in lx.STAKE_RX for w in window):
            continue
        start = sent.start_char + m.start()
        yield Suggestion(
            message="What goes wrong if this stays unknown? Say who pays, "
                    "or what is decided without the answer.",
            start=start, end=start + len(m.group(0)))


@rule("D904", "fills-the-gap", Category.IMPROVEMENT,
      "'These findings fill the gap' — rule on the gap instead.",
      'A Discussion should return to the gap it opened with and give a '
      'verdict on it. "Fills the gap" claims the question is settled '
      'without saying to what extent, and few studies settle one. Give a '
      'verdict and its '
      'reason: closed (the question is answered), narrowed (answered for '
      'some settings or groups), reframed (the question turned out to be a '
      'different one) or reopened (the findings unsettle what was thought '
      'known).',
      plain=("'Fills the gap' says the question is settled but not how far. "
             "Say whether your findings closed it, narrowed it, changed the "
             "question, or opened it again, and why."),
      sections_only=("discussion", "conclusion"),
      source="workshop-S2", aggregate=True)
def d904_fills_the_gap(doc, document: Document):
    _, sents = _sentences_in(doc, document, ("discussion", "conclusion"))
    for _, sent in sents:
        text = sent.text
        for rx in lx.FILL_GAP_RX:
            m = re.search(rx, text, re.IGNORECASE)
            if not m:
                continue
            if re.search(lx.FILL_GAP_RULING_RX, text[:m.start()],
                         re.IGNORECASE):
                break
            start = sent.start_char + m.start()
            yield Suggestion(
                message="How far did the gap close? Say closed, narrowed, "
                        "reframed or reopened, and why.",
                start=start, end=start + len(m.group(0)))
            break


def _content_words(text: str) -> list:
    return [w for w in re.findall(r"[a-z]+", text.lower())
            if len(w) > 2 and w not in lx.GENERIC_FUTURE_WORDS]


@rule("D905", "generic-future-research", Category.IMPROVEMENT,
      "'Further research is needed' with nothing on what is still open.",
      'The end of a Discussion or a Conclusion hands the question on. '
      '"Further research is needed" or "future work could explore this" '
      'is true of every study and tells the next researcher nothing. Say '
      'what the field could say before this work, what it can say now, and '
      'what it still cannot say; then name the study, data or comparison '
      'that would settle what is left.',
      plain=("'Further research is needed' is true of every study, so it "
             "tells the reader nothing. Say what is still unknown after "
             "your work, and what kind of study would answer it."),
      sections_only=("discussion", "limitations", "conclusion"),
      source="workshop-S2+Bunton2005", aggregate=True)
def d905_generic_future(doc, document: Document):
    _, sents = _sentences_in(doc, document,
                             ("discussion", "limitations", "conclusion"))
    for _, sent in sents:
        text = sent.text
        for rx in lx.FUTURE_RESEARCH_RX:
            m = re.search(rx, text, re.IGNORECASE)
            if not m:
                continue
            rest = text[:m.start()] + " " + text[m.end():]
            if _content_words(rest):
                break               # it names what is open: specific
            start = sent.start_char + m.start()
            yield Suggestion(
                message="Name what is still unknown after this work, and "
                        "the study that would settle it.",
                start=start, end=start + len(m.group(0)))
            break


# ensure the abstract lens registers wherever the rule pack loads
from .discourse import abstract_lens  # noqa: E402,F401


@rule("W210", "variant-consistency", Category.CONVENTION,
      "Mixed UK/US spellings of the same word (modelling AND modeling).",
      'One term, one meaning, and one spelling. Readers assume a changed '
      'term signals a changed meaning. Pick the variant your venue '
      'prefers and use it throughout; co-authored drafts drift into '
      'mixtures without anyone noticing.',
      plain=('The same word is spelled in both British and American ways, such '
             "as 'modelling' and 'modeling'. Pick the one your journal uses and "
             'keep it the same throughout.'),
      source="§6+lecture")
def w210_variant_consistency(doc, document: Document):
    from . import spelling
    cfg = getattr(document, "config", None)
    if cfg is not None and getattr(cfg, "spelling", "auto") != "auto":
        return                  # a chosen spelling: W213 flags every one
    text = document.masked.lower()
    words = re.findall(r"[a-z]+", text)
    from collections import Counter
    counts = Counter(words)
    # The document's own dialect, from every word that tells the dialects
    # apart: a mixture is standardised on what the document mostly uses.
    dialect, agree, telling = spelling.detect_dialect(words)
    code = spelling.DIALECT_CODES.get(dialect or "", "")
    table = spelling.variant_words()
    varcon = set(spelling.variant_pairs())
    pairs = dict.fromkeys(spelling.variant_pairs())
    for a, b in lx.CONSISTENCY_PAIRS:
        pair = tuple(sorted((a, b)))
        # VarCon knows both words and does not pair them: one is right in
        # both dialects ("analyses" is also the US plural of "analysis").
        if a in table and b in table and pair not in varcon:
            continue
        pairs[pair] = None
    for a, b in pairs:
        na, nb = counts.get(a, 0), counts.get(b, 0)
        if na == 0 or nb == 0:
            continue
        rare, common = (a, b) if na <= nb else (b, a)
        reason = ""
        if code and telling >= 3 and agree / telling >= 0.7:
            in_a = code in table.get(a, ("", ""))[0]
            in_b = code in table.get(b, ("", ""))[0]
            if in_a != in_b:
                common, rare = (a, b) if in_a else (b, a)
                reason = (f" The document mostly uses "
                          f"{spelling.DIALECT_NAMES[dialect]} spelling "
                          f"({agree} of {telling} words that differ).")
        m = re.search(rf"\b{rare}\b", text)
        if not m:
            continue
        yield Suggestion(
            message=f"Both '{a}' ({na}x) and '{b}' ({nb}x) appear — "
                    f"standardise on '{common}'.{reason}",
            start=m.start(), end=m.end(),
            replacement=common if rare != common else None)


@rule("W213", "dialect-spelling", Category.CONVENTION,
      "A spelling from another English than the one chosen in the "
      "settings ('color' in a British paper).",
      'Journals and universities ask for one spelling throughout, British or '
      'American (some British publishers use -ize, the Oxford style). Once '
      'you choose one in the settings, every spelling of another dialect is '
      'flagged, even if it appears only once. The variant lists come from '
      'VarCon, which also knows where both dialects agree: British English '
      'writes "meter" for the measuring device and "program" for software.',
      plain=("This word is spelled the way another English spells it, not the "
             "one you chose in your settings. For example, British English "
             "writes 'colour', American English 'color'."),
      source="VarCon")
def w213_dialect_spelling(doc, document: Document):
    from . import spelling
    cfg = getattr(document, "config", None)
    choice = getattr(cfg, "spelling", "auto") if cfg is not None else "auto"
    if choice == "auto":
        return
    text = document.masked
    for m in re.finditer(r"[A-Za-z]+", text):
        typed = m.group(0)
        if typed.isupper() and len(typed) > 1:
            continue
        # a capital mid-sentence is a name: "Centers for Disease Control"
        if typed[0].isupper() and not re.search(
                r"(^|[.!?]\s+|\n\s*)$", text[max(0, m.start() - 4):m.start()]):
            continue
        meant = spelling.dialect_spelling(typed.lower(), choice)
        if meant is None:
            continue
        fixed = _match_initial(meant, typed)
        yield Suggestion(
            message=f"In {spelling.DIALECT_NAMES[choice]} spelling, write "
                    f"'{fixed}'.",
            start=m.start(), end=m.end(), replacement=fixed)


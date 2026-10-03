"""Lexicon/regex rules (word- and phrase-level).

These run on the MASKED text, so anything inside code, math, citations, or
LaTeX commands can never match. All offsets map 1:1 to the source file.
"""

from __future__ import annotations

import re
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
      "Complexity should live in your ideas, never in your vocabulary. "
      "Grand words are camouflage, and experienced readers read them as "
      "camouflage. (Guide §6.)",
      source="§6", fix_safety="safe")
def w201_grand_words(doc, document: Document):
    for word, plain in lx.GRAND_WORDS.items():
        for m in _finditer(rf"\b{word}\b", document.masked):
            yield Suggestion(
                message=f"Plainer: '{plain}'.",
                start=m.start(), end=m.end(), replacement=plain)


@rule("W202", "wordy-phrase", Category.IMPROVEMENT,
      "Compress wordy phrases (due to the fact that → because).",
      "Cut ruthlessly, but second: on a revision pass, try to remove 10% of "
      "the words without losing meaning — you almost always can, and the "
      "prose tightens every time. (Guide §6.)",
      source="§6", fix_safety="safe")
def w202_wordy_phrases(doc, document: Document):
    for phrase, tight in lx.WORDY_PHRASES.items():
        for m in _finditer(rf"\b{re.escape(phrase)}\b", document.masked):
            yield Suggestion(
                message=f"Tighter: '{tight}'.",
                start=m.start(), end=m.end(), replacement=tight)


@rule("W203", "hype", Category.CONVENTION,
      "Buzzwords (novel, cutting-edge) signal thin substance.",
      "Credibility comes from concreteness: facts, figures, mechanisms. "
      "Buzzwords and hype do the opposite — they signal that the substance "
      "may be thin. Let the numbers carry the weight. Convention, not error: "
      "'novel' survives review in some venues; you decide. (Guide §6.)",
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
      "In calibrated scientific prose, 'very important' is not more important "
      "than 'important'. If magnitude matters, quantify it. (Guide §6.)",
      source="§6")
def w204_intensifiers(doc, document: Document):
    for word in lx.INTENSIFIERS:
        for m in _finditer(rf"\b{word}\b", document.masked):
            yield Suggestion(
                message="Consider deleting, or quantify instead.",
                start=m.start(), end=m.end())


@rule("W205", "filler", Category.IMPROVEMENT,
      "Throat-clearing ('It should be noted that…') delays the point.",
      "Every sentence either reduces or increases the reader's mental load. "
      "'It is important to note that X' is usually just 'X' — if it matters, "
      "the stress position will say so better than an announcement. "
      "(Guide §0, §6.)",
      source="§6", fix_safety="safe")
def w205_filler(doc, document: Document):
    for phrase in lx.FILLER_PHRASES:
        for m in _finditer(rf"\b{re.escape(phrase)}\b", document.masked):
            yield Suggestion(
                message="Cut the preamble; state the point directly.",
                start=m.start(), end=m.end(), replacement="")


@rule("W206", "redundant-pair", Category.IMPROVEMENT,
      "Redundant pairs (each and every, end result).",
      "Omit needless words: one of the pair is doing no work. (Guide §6.)",
      source="§6", fix_safety="safe")
def w206_redundant_pairs(doc, document: Document):
    for pair, keep in lx.REDUNDANT_PAIRS.items():
        for m in _finditer(rf"\b{re.escape(pair)}\b", document.masked):
            yield Suggestion(
                message=f"'{keep}' says the same.",
                start=m.start(), end=m.end(), replacement=keep)


@rule("W207", "doubled-word", Category.CORRECTION,
      "Accidentally doubled word (the the).",
      "A mechanical slip the eye forgives and the reader stumbles on — the "
      "read-aloud test catches these. (Guide §8.)",
      source="§8", fix_safety="safe")
def w207_doubled_word(doc, document: Document):
    for m in re.finditer(r"\b([A-Za-z]+)[ \t]+\1\b", document.masked,
                         re.IGNORECASE):
        if m.group(1).lower() in {"had", "that"}:  # "had had" can be valid
            continue
        yield Suggestion(
            message="Doubled word — delete one.",
            start=m.start(), end=m.end(), replacement=m.group(1))


@rule("W208", "contraction", Category.CONVENTION,
      "Contractions are unconventional in formal scientific prose.",
      "A register convention, not a grammar rule: journals and theses "
      "conventionally avoid contractions. Fine in talks, blogs, and emails. "
      "(Guide §6, register.)",
      source="§6")
def w208_contractions(doc, document: Document):
    for word in lx.CONTRACTIONS:
        for m in _finditer(rf"\b{re.escape(word)}\b", document.masked):
            yield Suggestion(
                message="Expand the contraction for formal register.",
                start=m.start(), end=m.end())


@rule("W209", "in-terms-of", Category.PREFERENCE,
      "'In terms of' is usually a vague connector.",
      "It typically hides the real relationship between ideas; naming the "
      "relationship ('as', 'for', 'measured by') is more precise. (Guide §6.)",
      source="§6")
def w209_in_terms_of(doc, document: Document):
    for m in _finditer(r"\bin terms of\b", document.masked):
        yield Suggestion(
            message="Name the actual relationship instead.",
            start=m.start(), end=m.end())


# ---------------------------------------------------------------------------
# C3xx — calibration and claims
# ---------------------------------------------------------------------------

@rule("C302", "overclaim", Category.CONVENTION,
      "Overclaiming (prove, conclusively) exceeds what empirical evidence supports.",
      "Reserve strong verbs for strong evidence. An unqualified claim reads "
      "as naive; 'prove' almost never belongs in empirical science — "
      "models and data support, suggest, indicate, or are consistent with. "
      "Match the confidence of the language to the strength of the grounds. "
      "(Guide §4, Toulmin qualifiers.)",
      sections_only=("abstract", "results", "discussion", "conclusion",
                     "introduction", "limitations"),
      source="§4")
def c302_overclaim(doc, document: Document):
    for pat in lx.OVERCLAIM_PATTERNS:
        for m in _finditer(pat, document.masked):
            yield Suggestion(
                message="Calibrate: 'suggests', 'indicates', 'is consistent "
                        "with' — unless the evidence truly compels.",
                start=m.start(), end=m.end())


@rule("C305", "assertive-adverb", Category.CONVENTION,
      "Assertive adverbs (clearly, obviously) assert what structure should show.",
      "If it were clear, the word would be unnecessary; if it is not, the "
      "word will not make it so. Put the important idea in the stress "
      "position and let the evidence do the convincing. (Guide §4, §5.2.6.)",
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
      "'statistically significant' — if that is meant, say so (with the "
      "estimate and interval); if practical importance is meant, "
      "'substantial' or a quantified statement is clearer. Uncertainty is "
      "not a caveat — it is the finding. (Guide §9.3.)",
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


@rule("F601", "acronym-undefined", Category.CONVENTION,
      "Acronym used without definition at first use.",
      "Define a term the first time you use it, once, briefly, then use it "
      "consistently. Your reader is expert — but rarely in every discipline "
      "you are combining. (Guide §9.1.)",
      source="§9.1")
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
        return sum(1 for c in alpha if c.isupper()) / len(alpha) > 0.55

    seen: set[str] = set()
    for m in re.finditer(r"\b([A-Z]{2,6})s?\b", text):
        acr = m.group(1)
        if acr in seen or acr in lx.ACRONYM_ALLOWLIST or acr in predefined:
            continue
        if in_caps_zone(m.start(), m.end()):
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
      "The end of a sentence is the stress position — the point of natural "
      "emphasis. 'Attack rates rose sharply, according to our simulations' "
      "spends the emphasis on the attribution; 'Our simulations show attack "
      "rates rising sharply' spends it on the result. Put what you most "
      "want remembered at the end. (Guide §5.2.2.)",
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
# E7xx — rules mined from Dr Akira Endo's "Scientific writing for infectious
# disease modelling" lecture (Notes_on_writing/writing.pdf)
# ---------------------------------------------------------------------------

@rule("E701", "empty-phrase", Category.CONVENTION,
      "Low-information phrase ('sheds light on', 'holistic understanding').",
      "Information density: minimise 'empty' sentences sounding as if you're "
      "saying something but aren't. 'This study provides holistic "
      "understanding of the complex dynamics of dengue' adds no information; "
      "'This study explains multi-serotype dengue dynamics driven by "
      "cross-reacting immunity' does. Say specifically what the work shows. "
      "(Endo lecture, 'Information density'.)",
      source="Endo", aggregate=True)
def e701_empty_phrase(doc, document: Document):
    for phrase in lx.EMPTY_PHRASES:
        for m in _finditer(rf"\b{re.escape(phrase)}\b", document.masked):
            yield Suggestion(
                message="Replace with the concrete thing the work "
                        "shows/does/estimates.",
                start=m.start(), end=m.end())


@rule("E704", "uncited-consensus", Category.CONVENTION,
      "'Is known/considered to be…' — who says? Cite it or own it.",
      "Distinguish facts from opinions: 'XX is considered to be…', 'XX is "
      "known to be…' — who says that? If it's an established fact you should "
      "be able to cite it; if it's your judgement, own it ('we consider…'). "
      "(Endo lecture, 'Facts vs opinions'; also NG5001 Unit 1 on warranting "
      "every claim.)",
      source="Endo", aggregate=True)
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
      "Unless you are sure it has never been done, don't take the risk — "
      "you may simply have missed the literature (reviewers love finding "
      "the counterexample). Soften with 'to our knowledge' and cite the "
      "closest existing attempts. (Endo lecture, avoid-list; the CARS "
      "literature makes the same move safely: 'few studies have…'.)",
      source="Endo", aggregate=True)
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
      "Phrases like 'additional', 'increase', 'relatively', 'proportion' "
      "only make sense with a comparator or reference. 'Relatively high': "
      "relative to WHAT? Specify the reference, or make sure it is uniquely "
      "identifiable from context — otherwise drop the word. (Endo lecture, "
      "'Implicit comparator/reference'.)",
      source="Endo", aggregate=True)
def e706_missing_comparator(doc, document: Document):
    for m in _finditer(r"\brelatively\b", document.masked):
        yield Suggestion(
            message="Name the comparison ('relative to X'), or delete.",
            start=m.start(), end=m.end())


@rule("AB801", "vague-forward-reference", Category.CONVENTION,
      "'Results will be discussed' — say what the results are.",
      "Vague abstracts with little scientific substance are unattractive to "
      "committees and readers: they cannot risk a presentation devoid of "
      "content. Be specific about at least some results in the abstract "
      "rather than promising them. (Pallas 2022 ch.7 / Schultz, Eloquent "
      "Science, via NG5001 Unit 2.)",
      sections_only=("abstract",),
      source="NG5001-U2", aggregate=True)
def ab801_vague_forward(doc, document: Document):
    for m in _finditer(lx.ABSTRACT_VAGUE_RX, document.masked):
        yield Suggestion(
            message="State the actual finding (with a number if you have "
                    "one) instead of promising it.",
            start=m.start(), end=m.end())


@rule("L901", "serial-summary-opener", Category.IMPROVEMENT,
      "'There are many studies on…' — catalogue opener, not an argument.",
      "A literature review should be a conversation that leads to your gap, "
      "not a catalogue: 'There are many studies dealing with X. A claimed… "
      "B claimed…' restates instead of synthesizing. Open with the "
      "synthesis point ('Evidence consistently links X to Y'), then use the "
      "sources as support — and let the review build toward a clear gap "
      "statement. (NG5001 Unit 1, critical literature review; Week 2 key "
      "points.)",
      source="NG5001-U1", aggregate=True)
def l901_serial_summary(doc, document: Document):
    for rx in lx.LITREVIEW_FILLER:
        for m in _finditer(rx, document.masked):
            yield Suggestion(
                message="Lead with your synthesis of what these studies "
                        "show, then cite them.",
                start=m.start(), end=m.end())


@rule("D902", "missing-niche-signal", Category.IMPROVEMENT,
      "Introduction has no detectable gap statement (CARS Move 2).",
      "The gap is the hinge of an Introduction: it connects 'what has been "
      "done' to 'what this study is about' and builds demand for your "
      "contribution — a 'mini-critique', often one sentence, signalled by a "
      "contrastive turn (however, although, yet) plus a gap word (limited, "
      "few, little, remains unclear, has not been…). No signal detected "
      "here — either the niche is missing, or it's phrased so gently the "
      "reader may not notice it. (Shehzad 2008 on CARS Move 2; Swales & "
      "Feak; guide §3.)",
      source="Shehzad")
def d902_missing_niche(doc, document: Document):
    intro = [h for h in document.headings if h.section == "introduction"]
    if not intro:
        return
    start = intro[0].start
    ends = [h.start for h in document.headings if h.start > start]
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


# ensure the abstract lens registers wherever the rule pack loads
from . import abstract_lens  # noqa: E402,F401


@rule("W210", "variant-consistency", Category.CONVENTION,
      "Mixed UK/US spellings of the same word (modelling AND modeling).",
      "One term, one meaning — and one spelling. Rephrasing or re-spelling "
      "the same term reads as if you mean different things (Endo: 'by "
      "default, different terms = different things'; guide §6; the "
      "critical-reader checklist asks whether authors are consistent in "
      "their key terms). Pick the variant your venue prefers and use it "
      "throughout — co-authored drafts drift into mixtures without anyone "
      "noticing.",
      source="§6+Endo")
def w210_variant_consistency(doc, document: Document):
    text = document.masked.lower()
    words = re.findall(r"[a-z]+", text)
    from collections import Counter
    counts = Counter(words)
    for a, b in lx.CONSISTENCY_PAIRS:
        na, nb = counts.get(a, 0), counts.get(b, 0)
        if na == 0 or nb == 0:
            continue
        rare, common = (a, b) if na <= nb else (b, a)
        m = re.search(rf"\b{rare}\b", text)
        if not m:
            continue
        yield Suggestion(
            message=f"Both '{a}' ({na}x) and '{b}' ({nb}x) appear — "
                    f"standardise on '{common}'.",
            start=m.start(), end=m.end(),
            replacement=common if rare != common else None)

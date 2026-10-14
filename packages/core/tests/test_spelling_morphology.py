"""S001's morphological fallbacks must follow English spelling rules.

The suffix and prefix fallbacks exist so that a known word with an ending or
a prefix ("covariates", "reinfections", "preintervention") is not a typo. Until
2026-10-14 they accepted ANY known base plus ANY ending, which excused the
commonest misspellings in English: "occured" (occur + ed), "begining",
"happend", "acess" (aces + s), "personaly", "untill" (un + till). The words
below are invented test cases or well-known general-English misspellings;
none comes from a third-party list.
"""

import pytest
import spacy

from researchly import spelling
from researchly.document import Document
from researchly.engine import check

NLP = spacy.load("en_core_web_sm")


def s001(text):
    doc = Document.from_text(text, "plain")
    return {s.text: s.replacement
            for s in check(doc, NLP, disabled={"LT001"},
                           show_preferences=False)
            if s.rule_id == "S001"}


# --- fire: a known base with the wrong ending -------------------------------

@pytest.mark.parametrize("typo", [
    "occured", "occuring", "begining", "commited", "submited",
    "refered", "transfered", "geting", "runing",      # consonant not doubled
    "happend", "deliverd", "opend",                    # -d after no e
    "acess", "addresss", "researchs",                  # -s after s/ch
    "companys", "studys",                              # y → ies
    "detailes", "occures",                             # -es after no sibilant
    "useing", "completeing",                           # e kept before -ing
    "tryed", "copyed",                                 # y → ied
    "personaly", "basicly", "severly",                 # -ally / -ely
    "reqest",                                          # not a superlative
    "beter",                                           # comparative doubling
])
def test_misinflected_word_is_not_known(typo):
    assert not spelling.known_with_fallbacks(typo)


@pytest.mark.parametrize("typo", ["untill", "corect", "relase", "postions"])
def test_accidental_prefix_split_is_not_known(typo):
    # "un" + "till", "co" + "rect": a one-edit neighbour ("until",
    # "correct") is far more common than the stem the split produced.
    assert not spelling.known_with_fallbacks(typo)


def test_misinflected_words_are_flagged_with_the_right_fix():
    fixes = s001("The error occured when the model was submited and the "
                 "run happend twice before we were begining again.")
    assert fixes.get("occured") == "occurred"
    assert fixes.get("submited") == "submitted"
    assert fixes.get("happend") == "happened"
    assert fixes.get("begining") == "beginning"


# --- don't fire: real words the same fallbacks must keep accepting ----------

@pytest.mark.parametrize("word", [
    # regular inflections of known bases ("differenced" is in the
    # scientific lexicon: SPECIALIST lists "difference" as a noun only)
    "forecasted", "resampled", "confounders",
    "recalibrated", "stressors", "immunoassays", "subsamples",
    # prefixed words whose stem is the real word
    "reinfections", "preinfection", "preintervention", "postvaccination",
    "subnational", "interregional", "nonpharmaceutical", "underreported",
    "autocorrelated", "multicentric", "semiclosed", "unboiled",
    # -ly on adjectives the dictionary lacks
    "epidemiologically", "multiplicatively", "indicatively",
    # US -l- forms: a dialect variant, not a doubling error
    "modeling", "modeled", "traveling", "labeling",
])
def test_real_words_stay_known(word):
    assert spelling.known_with_fallbacks(word)


def test_real_inflected_words_are_not_flagged_in_prose():
    assert s001("The series was differenced, the samples were resampled, "
                "and reinfections were recalibrated against the "
                "postvaccination data.") == {}


# --- 2026-10-14 (P41): the lexicon knows the real inflections ----------------

@pytest.mark.parametrize("typo", [
    "adviced", "awared", "spreaded",       # the base takes no such ending
    "acquited",                            # "qu" is a consonant: acquitted
    "surprizingly",                        # surprise is -ise in every English
])
def test_forms_the_lexicon_and_spelling_rules_refuse(typo):
    assert not spelling.known_with_fallbacks(typo)


@pytest.mark.parametrize("word", [
    "acquitted", "equipped", "operationalise", "dichotomised",
    "hospitalised", "organized",
])
def test_real_forms_stay_known(word):
    assert spelling.known_with_fallbacks(word)


def test_letter_bag_reaches_a_misspelling_beyond_two_edits():
    # "sucesfull" is three edits from "successful": SymSpell finds nothing,
    # the letter-bag search does (2026-10-14, P41)
    from researchly import spellrank
    assert spelling.suggest_with_distance("sucesfull", 3) == []
    assert spellrank.rank("sucesfull")[0][0] == "successful"


def test_letter_bag_stays_out_of_one_edit_slips():
    from researchly import spellrank
    assert [c for c, _ in spellrank.rank("recieve")][:1] == ["receive"]

"""Academic conventions an everyday keyboard gets wrong (2026-10-14).

An email keyboard turns "dont" into "don't" and has no opinion on
"softwares". In a paper the full form is the convention (W208), and a mass
noun takes no plural (W212). Synthetic sentences only.
"""

import spacy

from researchly.document import Document
from researchly.engine import check

NLP = spacy.load("en_core_web_sm")


def cards(text, rule):
    doc = Document.from_text(text, "plain")
    return [s for s in check(doc, NLP, disabled={"LT001"},
                             show_preferences=False)
            if s.rule_id == rule]


def all_ids(text):
    doc = Document.from_text(text, "plain")
    return [s.rule_id for s in check(doc, NLP, disabled={"LT001"},
                                     show_preferences=False)]


# --- W208: contractions now carry their full form ----------------------------

def test_contraction_offers_full_form():
    hit = cards("The chain doesn't mix within the warm-up period.", "W208")
    assert [h.replacement for h in hit] == ["does not"]


def test_sentence_initial_contraction_keeps_its_capital():
    hit = cards("Don't fit the model before checking the priors.", "W208")
    assert [h.replacement for h in hit] == ["Do not"]


def test_its_been_is_not_expanded_to_it_is():
    # "it's been" means "it has been": flag, but offer no wrong fix.
    hit = cards("It's been difficult to estimate the delay.", "W208")
    assert len(hit) == 1 and hit[0].replacement is None


def test_apostropheless_contraction_is_one_card_not_two():
    ids = all_ids("The sampler dont converge when the step size is large.")
    assert ids.count("W208") == 1
    assert "S001" not in ids
    assert cards("The sampler dont converge when the step size is large.",
                 "W208")[0].replacement == "do not"


def test_real_words_that_look_like_contractions_are_left_alone():
    # cant, wont, lets, its, were, well, ill, shell: all real words.
    text = ("The model lets the rate vary; its prior is wide, as is the "
            "wont of hierarchical models, and the well-mixed chains were "
            "fine.")
    assert cards(text, "W208") == []


# --- W212: uncountable nouns -------------------------------------------------

def test_uncountable_plural_is_flagged_with_fix():
    hit = cards("We compared three softwares for fitting the model.", "W212")
    assert [h.replacement for h in hit] == ["software"]
    assert "pieces of" in hit[0].message


def test_latin_plural_with_second_plural():
    hit = cards("The inclusion criterias were set in advance.", "W212")
    assert [h.replacement for h in hit] == ["criteria"]
    assert "already plural" in hit[0].message


def test_correct_mass_nouns_and_verbs_are_not_flagged():
    text = ("The data were collected with the software and equipment "
            "described above; the infection progresses quickly, the study "
            "evidences a delay, and climate feedbacks were modelled. "
            "She researches transmission.")
    assert cards(text, "W212") == []

"""S002: real words used for their usual confusion (2026-10-14).

A dictionary passes "principle" in "the principle investigator"; word-pair
counts say "principal" was meant. Measured on 1.03 million words (eight
accepted theses + 115 CC BY PMC articles): 3 flags, all genuine slips.
Synthetic sentences only.
"""

import pytest

from researchly import rules_spelling as rs
from researchly.document import Document


def fixes(text):
    doc = Document.from_text(text, "plain")
    return [s.replacement for s in rs.s002_confusion(None, doc)]


@pytest.mark.parametrize("text, meant", [
    ("The principle investigator approved the protocol.", "principal"),
    ("We found a casual relationship between exposure and outcome.",
     "causal"),
    ("We estimated the affect of the intervention on incidence.", "effect"),
    ("The results were effected by the delay.", "affected"),
    ("A randomised clinical trail of the vaccine was run.", "trial"),
    ("The dependant variable was weekly incidence.", "dependent"),
    ("We used a discreet time model.", "discrete"),
    ("It is not clear weather the effect persists.", "whether"),
])
def test_confusion_is_flagged(text, meant):
    assert fixes(text) == [meant]


@pytest.mark.parametrize("text", [
    "The principle of parsimony guided model choice.",
    "The school principals were interviewed.",
    "Rainfall may affect the incidence of dengue.",
    "The effect of the intervention was small.",
    "Policies that affect the outcome were listed.",
    "We followed a casual conversation format.",
    "Ants followed the pheromone trail to the nest.",
    "Patients were interviewed in a quiet room.",
    # left to LanguageTool: word pairs misjudge these on published prose
    "We chose a simpler model rather than consider a time series model.",
    "The remaining samples form the posterior distribution.",
])
def test_correct_use_is_not_flagged(text):
    assert fixes(text) == []


def test_a_word_without_both_neighbours_is_not_judged():
    # no left neighbour at a sentence start: too little evidence
    assert fixes("Principle investigators signed the consent form.") == []


def test_acronym_is_left_alone():
    assert fixes("The LEAD trial enrolled adults.") == []

"""Tests for the Belcher/Pallas six-part abstract lens."""

import spacy

from researchly.abstract_lens import MOVES, analyze, missing_moves
from researchly.document import Document
from researchly.engine import check

NLP = spacy.load("en_core_web_sm")

# Pallas's own exemplar abstract (Doctoral Student Skills, ch. 7)
PALLAS = (
    "Existing scholarship shows that international donors reducing foreign "
    "aid to a country frequently seek to devolve responsibility for funding "
    "local NGOs to the national government. However, the outcomes of this "
    "transition vary widely between contexts; some funding transitions "
    "result in a successful government-NGO relationship while others result "
    "in an antagonistic relationship. Scholarship on aid reduction has yet "
    "to explain this variation. In this paper, we ask, what factors explain "
    "a government's willingness to fund local NGOs during aid reduction? "
    "To answer this question, we generate hypotheses using NGO-government "
    "relations theory and test them using case study data from the HIV/AIDS "
    "sectors in Thailand and Vietnam. We find that NGO-government relations "
    "theory provides a convincing explanation for the outcomes of the "
    "sector's transition. These findings suggest that donors need to pay "
    "attention to the underlying attitudes of NGOs and government when "
    "planning funding transitions."
)


def test_pallas_exemplar_has_all_six_moves():
    assert missing_moves(PALLAS) == []
    a = analyze(PALLAS)
    assert all(a[m]["present"] for m in MOVES)
    assert "Existing scholarship" in a["background"]["evidence"]
    assert "However" in a["gap"]["evidence"]


def test_methods_only_abstract_missing_five():
    t = ("We fitted an SEIR model to dengue case data from Singapore "
         "using Bayesian inference. Results will be discussed.")
    missing = missing_moves(t)
    assert "methods" not in missing
    assert {"background", "gap", "aim", "findings",
            "significance"} <= set(missing)


def test_cold_open_flags_missing_background():
    t = "We ask whether income shapes contact patterns. " + PALLAS
    a = analyze(t)
    assert not a["background"]["present"]     # first sentence is the aim


def test_epi_flavoured_signals():
    t = ("Dengue burden is rising across Southeast Asia. However, the role "
         "of income-related contact heterogeneity remains unquantified. "
         "We aimed to quantify its contribution to transmission. Using a "
         "compartmental model fitted to surveillance data, we estimated "
         "attack rates by income quintile. Attack rates were 40% higher in "
         "the lowest quintile (95% CrI: 25-58%). These findings suggest "
         "that equity-aware vaccination strategies could inform policy.")
    assert missing_moves(t) == []


def test_ab802_rule_fires_on_incomplete_abstract():
    t = ("Abstract\n\n"
         "We fitted an SEIR model to dengue case data from Singapore using "
         "Bayesian inference implemented in Stan with weakly informative "
         "priors. We used surveillance data from 2013 to 2020 covering all "
         "reporting clinics, and we conducted extensive sensitivity "
         "analyses across model structures and prior choices to confirm "
         "robustness of the fitting procedure across seasons and regions.")
    doc = Document.from_text(t, "plain")
    hits = [s for s in check(doc, NLP, disabled={"LT001"},
                             show_preferences=False)
            if s.rule_id == "AB802"]
    assert len(hits) == 1
    assert "findings" in hits[0].message
    assert "significance" in hits[0].message


def test_ab802_quiet_on_complete_abstract():
    doc = Document.from_text("Abstract\n\n" + PALLAS, "plain")
    hits = [s for s in check(doc, NLP, disabled={"LT001"},
                             show_preferences=False)
            if s.rule_id == "AB802"]
    assert hits == []


def test_ab802_quiet_without_abstract_section():
    doc = Document.from_text("Methods\n\nWe fitted a model to the data.",
                             "plain")
    hits = [s for s in check(doc, NLP, disabled={"LT001"},
                             show_preferences=False)
            if s.rule_id == "AB802"]
    assert hits == []

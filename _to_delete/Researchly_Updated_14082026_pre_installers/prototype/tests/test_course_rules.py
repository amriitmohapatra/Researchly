"""Fire / don't-fire tests for the rules mined from the Notes_on_writing
corpus (Endo lecture, NG5001 course, Shehzad 2008, Pallas 2022)."""

import spacy

from researchly.document import Document
from researchly.engine import check

NLP = spacy.load("en_core_web_sm")


def ids(text, kind="plain"):
    doc = Document.from_text(text, kind)
    return [s.rule_id for s in check(doc, NLP, show_preferences=True)]


# --- E701 empty phrases -----------------------------------------------------

def test_e701_fires_on_empty_value_phrase():
    assert "E701" in ids("This study sheds light on the transmission of "
                         "dengue in cities.")


def test_e701_quiet_on_concrete_statement():
    assert "E701" not in ids("This study explains multi-serotype dengue "
                             "dynamics driven by cross-reacting immunity.")


# --- E702 adversative runs --------------------------------------------------

def test_e702_fires_on_consecutive_howevers():
    t = ("All models are wrong. However, they can be useful when caveats "
         "are kept in mind. However, model outputs are sometimes oversold "
         "as solid predictions.")
    assert "E702" in ids(t)


def test_e702_quiet_on_single_however():
    t = ("All models are wrong. However, they can be useful when caveats "
         "are kept in mind. Guidelines are being developed to prevent "
         "miscommunication.")
    assert "E702" not in ids(t)


# --- E703 naked this --------------------------------------------------------

def test_e703_fires_on_naked_this():
    # long preceding sentence = multiple candidate referents (Endo's caveat)
    t = ("Mean contact rates among participants fell substantially after "
         "distancing was implemented and remained strongly correlated with "
         "the intensity of the intervention throughout the study period. "
         "This suggests that the reproduction number was lowered by the "
         "policy.")
    assert "E703" in ids(t)


def test_e703_quiet_when_this_has_a_noun():
    t = ("Contact rates fell after distancing began and remained low. "
         "This decline suggests that the reproduction number was lowered "
         "by the policy.")
    assert "E703" not in ids(t)


def test_e703_quiet_after_short_clear_sentence():
    # after a short simple sentence the referent is unambiguous — stay quiet
    t = "Contact rates fell sharply. This suggests the policy worked."
    assert "E703" not in ids(t)


# --- E704 uncited consensus -------------------------------------------------

def test_e704_fires_without_citation():
    assert "E704" in ids("Vaccine-derived immunity is considered to be "
                         "lifelong in most settings.")


def test_e704_quiet_with_citation():
    assert "E704" not in ids("Vaccine-derived immunity is considered to be "
                             "lifelong in most settings (Smith et al, 2019).")


# --- E705 absolute novelty --------------------------------------------------

def test_e705_fires_on_bare_novelty_claim():
    assert "E705" in ids("Income-related contact heterogeneity has not been "
                         "studied in Southeast Asia.")


def test_e705_quiet_with_softener():
    assert "E705" not in ids("To our knowledge, income-related contact "
                             "heterogeneity has not been studied in "
                             "Southeast Asia.")


# --- E706 relatively --------------------------------------------------------

def test_e706_fires():
    assert "E706" in ids("Attack rates were relatively high in the lowest "
                         "quintile.")


# --- E707 display-first openers ---------------------------------------------

def test_e707_fires_in_results():
    t = "Results\n\nFigure 1 shows the estimated Rt values in the city."
    assert "E707" in ids(t)


def test_e707_quiet_when_finding_leads():
    t = ("Results\n\nEstimated Rt showed a stable trend across the study "
         "period (Figure 1).")
    assert "E707" not in ids(t)


def test_e707_quiet_outside_results():
    t = "Methods\n\nFigure 1 shows the model structure."
    assert "E707" not in ids(t)


# --- AB801 vague abstract forward references --------------------------------

def test_ab801_fires_in_abstract():
    t = ("Abstract\n\nWe fitted an SEIR model to case data. Results will "
         "be discussed in the context of vaccination policy.")
    assert "AB801" in ids(t)


def test_ab801_quiet_when_results_stated():
    t = ("Abstract\n\nWe fitted an SEIR model to case data. Vaccination "
         "reduced hospitalisations by 34% in all scenarios.")
    assert "AB801" not in ids(t)


# --- L901 serial-summary openers --------------------------------------------

def test_l901_fires_on_catalogue_opener():
    assert "L901" in ids("There are many studies dealing with the effect "
                         "of knowledge management on performance.")


def test_l901_quiet_on_synthesis_opener():
    assert "L901" not in ids("Evidence consistently links poor sleep with "
                             "worse metabolic outcomes.")


# --- D902 missing niche signal ----------------------------------------------

_INTRO_NO_GAP = (
    "Introduction\n\n" + ("Dengue is a mosquito-borne viral disease with "
    "rising global incidence. Transmission is seasonal in many settings. "
    "Vector control has been the mainstay of prevention for decades. "
    "Vaccines have recently become available in several countries. ") * 4
    + "\n\nMethods\n\nWe fitted a model."
)

_INTRO_WITH_GAP = _INTRO_NO_GAP.replace(
    "Methods\n\nWe fitted a model.",
    "However, the contribution of income-related contact heterogeneity "
    "remains unquantified in Southeast Asian settings.\n\n"
    "Methods\n\nWe fitted a model.")


def test_d902_fires_when_intro_lacks_gap():
    assert "D902" in ids(_INTRO_NO_GAP)


def test_d902_quiet_when_gap_present():
    assert "D902" not in ids(_INTRO_WITH_GAP)


def test_d902_quiet_without_intro_section():
    assert "D902" not in ids("Results\n\nAttack rates rose sharply in the "
                             "lowest quintile of income.")


# --- W201 additions from Endo avoid-list ------------------------------------

def test_w201_leverage_and_elucidate():
    found = ids("We leveraged survey data to elucidate contact patterns.")
    assert found.count("W201") == 2

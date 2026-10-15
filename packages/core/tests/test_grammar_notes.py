"""Researchly grammar notes (S4d R6, ADR-11): fire and don't-fire tests for
every GN rule, and the gating by the writer's chosen English.

Every sentence here is synthetic, written for these tests (CLAUDE.md: no
third-party text). The rules and their reasons are in
docs/grammar-notes.md.
"""

from pathlib import Path

import pytest

from researchly import api, rules_grammar, sources
from researchly.document import Document
from researchly.engine import REGISTRY, Category, load_rules

NLP = api.get_nlp()
DIALECTS = ("auto", "us", "uk", "uk-oxford", "ca", "au", "in")
BRITISH = ("uk", "uk-oxford", "au", "in")


def gn(text, rule, spelling="auto", kind="plain", show_preferences=True):
    a = api.analyze(text, kind=kind, nlp=NLP, disabled={"LT001"},
                    show_preferences=show_preferences, with_metrics=False,
                    spelling=spelling)
    return [(s.text, s.replacement) for s in a.suggestions
            if s.rule_id == rule]


def res(body):
    return "Results\n\n" + body + "\n"


# --- the rule set ------------------------------------------------------------

GN_IDS = ("GN101", "GN102", "GN103", "GN104", "GN105", "GN106", "GN107",
          "GN201", "GN202", "GN203", "GN204", "GN205", "GN206", "GN207",
          "GN208")


def test_every_grammar_note_is_registered_and_sourced():
    load_rules()
    ids = tuple(sorted(r for r in REGISTRY if r.startswith("GN")))
    assert ids == GN_IDS
    for rid in ids:
        r = REGISTRY[rid]
        assert r.source == sources.cite("rgn")
        assert r.source.startswith("Researchly grammar notes")
        assert r.tier == "craft" and r.fix_safety == "review"
        # Shown above Improvement only after a measured precision of 0.9
        # on the real-document bench (docs/inline-review-design.md §7).
        assert r.category is not Category.CORRECTION


def test_regional_rules_are_conventions():
    load_rules()
    for rid in GN_IDS:
        if rid.startswith("GN1"):
            assert REGISTRY[rid].category is Category.CONVENTION


def test_the_source_document_covers_every_rule():
    doc = Path(__file__).resolve().parents[3] / "docs" / "grammar-notes.md"
    if not doc.exists():
        pytest.skip("docs/grammar-notes.md is not in this copy")
    text = doc.read_text("utf-8")
    for rid in GN_IDS:
        assert f"### {rid}" in text, rid
    assert "## Further reading" in text


# --- GN101: group nouns in American English -----------------------------------

def test_gn101_fires_in_american_english():
    assert gn(res("The committee were divided on the second dose."),
              "GN101", "us") == [("were", "was")]
    assert gn(res("The cohort have a median age of 40 years."),
              "GN101", "us") == [("have", "has")]


@pytest.mark.parametrize("spelling", [d for d in DIALECTS if d != "us"])
def test_gn101_quiet_outside_american_english(spelling):
    assert gn(res("The committee were divided on the second dose."),
              "GN101", spelling) == []


@pytest.mark.parametrize("text", [
    "A group of patients were admitted in June.",     # the people agree
    "The committee was divided on the second dose.",
    "The teams were small.",                          # a plural noun
    "The team and the board were consulted.",         # two subjects
])
def test_gn101_quiet(text):
    assert gn(res(text), "GN101", "us") == []


# --- GN102: different from / than / to ---------------------------------------

THAN = res("The second estimate is different than the first.")
TO = res("The second estimate is different to the first.")


@pytest.mark.parametrize("spelling", BRITISH)
def test_gn102_flags_different_than_in_british_pattern_english(spelling):
    assert gn(THAN, "GN102", spelling) == [("different than",
                                            "different from")]
    assert gn(TO, "GN102", spelling) == []


@pytest.mark.parametrize("spelling", ["us", "ca"])
def test_gn102_flags_different_to_in_north_american_english(spelling):
    assert gn(TO, "GN102", spelling) == [("different to", "different from")]
    assert gn(THAN, "GN102", spelling) == []


@pytest.mark.parametrize("text,spelling", [
    ("The second estimate is different from the first.", "us"),
    ("The second estimate is different from the first.", "uk"),
    ("This model is more different than we expected.", "uk"),  # comparison
    ("The two maps look different to the reader.", "us"),      # perception
    ("We wanted something different to do.", "us"),            # infinitive
    ("The second estimate is different than the first.", "auto"),
    ("The second estimate is different to the first.", "auto"),
])
def test_gn102_quiet(text, spelling):
    assert gn(res(text), "GN102", spelling) == []


# --- GN103: gotten --------------------------------------------------------------

@pytest.mark.parametrize("spelling", BRITISH)
def test_gn103_fires_in_british_pattern_english(spelling):
    assert gn(res("The estimates have gotten worse over time."), "GN103",
              spelling) == [("gotten", "got")]


@pytest.mark.parametrize("spelling", ["auto", "us", "ca"])
def test_gn103_quiet_in_north_american_english(spelling):
    assert gn(res("The estimates have gotten worse over time."), "GN103",
              spelling) == []


def test_gn103_quiet_on_other_words():
    assert gn(res("No ill-gotten data were used, and none was forgotten."),
              "GN103", "uk") == []


# --- GN104: whilst ----------------------------------------------------------------

def test_gn104_fires_in_american_english():
    assert gn(res("Whilst the model fits well, the tails are heavy."),
              "GN104", "us") == [("Whilst", "While")]


@pytest.mark.parametrize("spelling", [d for d in DIALECTS if d != "us"])
def test_gn104_quiet_elsewhere(spelling):
    assert gn(res("Whilst the model fits well, the tails are heavy."),
              "GN104", spelling) == []


# --- GN105: fit / fitted ---------------------------------------------------------

@pytest.mark.parametrize("text", [
    "The model was fit to weekly counts.",
    "Both models were then fit using a random-walk sampler.",
])
def test_gn105_fires_in_british_pattern_english(text):
    assert gn(res(text), "GN105", "uk") == [("fit", "fitted")]


@pytest.mark.parametrize("text,spelling", [
    ("The model was fit to weekly counts.", "us"),
    ("The model was fit to weekly counts.", "auto"),
    ("The model was fitted to weekly counts.", "uk"),
    ("The volunteers were fit to travel.", "uk"),     # the adjective
    ("The scheme is fit for purpose.", "uk"),
])
def test_gn105_quiet(text, spelling):
    assert gn(res(text), "GN105", spelling) == []


# --- GN106: full stops and commas with quotation marks ---------------------------

def test_gn106_american_placement():
    text = res('We call this "herd protection". It lasts.')
    assert gn(text, "GN106", "us") == [('".', '."')]
    assert gn(text, "GN106", "ca") == [('".', '."')]
    assert gn(res('We call this "herd protection." It lasts.'), "GN106",
              "us") == []


@pytest.mark.parametrize("spelling", BRITISH)
def test_gn106_british_placement(spelling):
    assert gn(res("We call this “herd protection.” It lasts."),
              "GN106", spelling) == [(".”", "”.")]
    assert gn(res('We call this "herd protection". It lasts.'), "GN106",
              spelling) == []


def test_gn106_british_leaves_a_quoted_sentence_alone():
    assert gn(res('The leaflet said "Stay at home today." Many did.'),
              "GN106", "uk") == []


def test_gn106_auto_flags_only_a_mixture():
    assert gn(res('We call it "drift". It is slow.'), "GN106") == []
    mixed = res('We call one "drift". We call the other "shift," as '
                'before.')
    # one of each: the style used first wins
    assert gn(mixed, "GN106") == [(',"', '",')]


# --- GN107: dates ------------------------------------------------------------------

@pytest.mark.parametrize("spelling", BRITISH)
def test_gn107_month_first_in_british_pattern_english(spelling):
    assert gn(res("The trial began on October 15, 2026."), "GN107",
              spelling) == [("October 15, 2026", "15 October 2026")]


def test_gn107_us_accepts_day_first_unless_mixed():
    assert gn(res("The trial began on 3 March 2026."), "GN107", "us") == []
    assert gn(res("The trial began on 3 March 2026 and ended on April 9, "
                  "2026."), "GN107", "us") == [("3 March 2026",
                                                "March 3, 2026")]


def test_gn107_auto_flags_the_rarer_form():
    text = res("Enrolment ran from 3 March 2026 to April 9, 2026. "
               "Follow-up ended on 2 May 2026.")
    assert gn(text, "GN107") == [("April 9, 2026", "9 April 2026")]


@pytest.mark.parametrize("text,spelling", [
    ("The trial began on 3 March 2026 and ended on 9 April 2026.", "auto"),
    ("The trial began on March 3, 2026 and ended on April 9, 2026.", "us"),
    ("Counts from June 3–July 9, 2020 and 12 August 2020 were used.",
     "auto"),                                       # a range is left alone
    ("The trial began on 03/04/2026.", "uk"),       # numbers only
])
def test_gn107_quiet(text, spelling):
    assert gn(res(text), "GN107", spelling) == []


# --- GN201: agreement across an "of" phrase ---------------------------------------

@pytest.mark.parametrize("text,fix", [
    ("The proportion of cases were higher in the north.", ("were", "was")),
    ("Each of the models have converged.", ("have", "has")),
    ("The mean of the posterior draws are close to one.", ("are", "is")),
    ("In June the number of admissions were low.", ("were", "was")),
])
def test_gn201_fires(text, fix):
    assert gn(res(text), "GN201") == [fix]


@pytest.mark.parametrize("text", [
    "A proportion of patients were admitted.",       # "a": the patients
    "The majority of patients were women.",
    "An average of 40 samples were taken each day.",
    "The proportion of cases was higher in the north.",
    "The mean and the median of the draws were close.",
    "The search date and the number of articles were recorded.",
    "The rates of infection in both districts were similar.",
])
def test_gn201_quiet(text):
    assert gn(res(text), "GN201") == []


# --- GN202: a number of ------------------------------------------------------------

def test_gn202_fires():
    assert gn(res("A number of studies has shown this effect."),
              "GN202") == [("has", "have")]


@pytest.mark.parametrize("text", [
    "A number of studies have shown this effect.",
    "The number of studies has grown.",
])
def test_gn202_quiet(text):
    assert gn(res(text), "GN202") == []


# --- GN203: neither ... nor ---------------------------------------------------------

def test_gn203_fires():
    assert gn(res("Neither the model nor the method are suitable here."),
              "GN203") == [("are", "is")]


@pytest.mark.parametrize("text", [
    "Neither the model nor the method is suitable here.",
    "Neither the model nor the data are suitable here.",   # nearer: plural
    "Neither the models nor the methods are suitable here.",
])
def test_gn203_quiet(text):
    assert gn(res(text), "GN203") == []


# --- GN204: the reason is because ---------------------------------------------------

def test_gn204_fires():
    assert gn(res("The reason is because the counts were delayed."),
              "GN204") == [("is because", "is that")]
    # "because of" has no one-word fix
    assert gn(res("The main reason for the drop was because of testing."),
              "GN204") == [("was because", None)]


@pytest.mark.parametrize("text", [
    "The reason is that the counts were delayed.",
    "The counts fell because testing stopped.",
    "For this reason, the step is skipped because it is slow.",
])
def test_gn204_quiet(text):
    assert gn(res(text), "GN204") == []


# --- GN205: dangling opener before a passive ---------------------------------------

@pytest.mark.parametrize("text,opener", [
    ("Using a Bayesian model, the parameters were estimated from weekly "
     "counts.", "Using a Bayesian model"),
    ("After fitting the model, the residuals were inspected for "
     "autocorrelation.", "After fitting the model"),
])
def test_gn205_fires_in_methods(text, opener):
    found = gn("Methods\n\n" + text + "\n", "GN205")
    assert found == [(opener, None)]


def test_gn205_is_not_about_the_passive():
    # In Methods the passive itself is never flagged (CLAUDE.md #4)
    text = ("Methods\n\nUsing a Bayesian model, the parameters were "
            "estimated from weekly counts.\n")
    assert gn(text, "G104") == []


@pytest.mark.parametrize("text", [
    "Using a Bayesian model, we estimated the parameters.",
    "Assuming a fixed interval, the rate was estimated from counts.",
    "Based on these counts, the rate was estimated weekly.",
    "Starting from April 2020, cases were counted weekly.",
    "Given these counts, the rate was estimated weekly.",
    "Using a Bayesian model gave stable estimates of the parameters.",
])
def test_gn205_quiet(text):
    assert gn("Methods\n\n" + text + "\n", "GN205") == []


# --- GN206: a / an before abbreviations ----------------------------------------------

@pytest.mark.parametrize("text,fix", [
    ("We used a MCMC sampler.", ("a", "an")),
    ("This was an UK cohort.", ("an", "a")),
    ("An SNP array was used.", ("An", "A")),
    ("We ran a RCT in two districts.", ("a", "an")),
])
def test_gn206_fires(text, fix):
    assert gn(res(text), "GN206") == [fix]


@pytest.mark.parametrize("text", [
    "We used an MCMC sampler.",
    "This was a UK cohort.",
    "We fitted a SEIR model.",      # said both ways: either article
    "We fitted an SEIR model.",
    "We fitted an SIR model.",
    "Group A HIV cases were rare.",  # a label, not an article
    "We ran an RCT and a SNP study.",
])
def test_gn206_quiet(text):
    assert gn(res(text), "GN206") == []


def test_gn206_quiet_inside_code():
    assert gn("Methods\n\nWe called `a MCMC` from R.\n", "GN206",
              kind="markdown") == []


def test_languagetool_leaves_known_abbreviations_to_gn206():
    doc = Document.from_text("We used a MCMC sampler and a SNP chip.",
                             "plain")
    a = doc.original.index("a MCMC")
    b = doc.original.index("a SNP")
    assert rules_grammar._covered_article("EN_A_VS_AN", doc, a + 1)
    assert rules_grammar._covered_article("EN_A_VS_AN", doc, b + 1)
    assert not rules_grammar._covered_article("SOME_OTHER_RULE", doc, a + 1)
    other = Document.from_text("We used a apple.", "plain")
    assert not rules_grammar._covered_article("EN_A_VS_AN", other, 6)


# --- GN207: data, singular and plural ------------------------------------------------

def test_gn207_flags_the_rarer_form_once():
    text = res("The data are sparse. These data were collected weekly. "
               "The data is noisy in winter. The data shows a peak.")
    found = gn(text, "GN207")
    assert len(found) == 1 and found[0][0] == "is"


@pytest.mark.parametrize("text", [
    "The data are sparse. These data were collected weekly.",
    "The data is sparse. This data was collected weekly.",
    "The data and code are public. The data is noisy in winter.",
])
def test_gn207_quiet(text):
    assert gn(res(text), "GN207") == []


# --- GN208: which / that in American English ------------------------------------------

def test_gn208_fires_in_american_english_as_a_preference():
    text = res("We report the model which we fitted to the counts.")
    assert gn(text, "GN208", "us") == [("which", "that")]
    # a Preference: hidden unless preferences are shown
    assert gn(text, "GN208", "us", show_preferences=False) == []


@pytest.mark.parametrize("text,spelling", [
    ("We report the model which we fitted to the counts.", "uk"),
    ("We report the model which we fitted to the counts.", "auto"),
    ("We report the model, which we fitted to the counts.", "us"),
    ("This is the extent to which the counts agree.", "us"),
    ("We report the model that we fitted to the counts.", "us"),
])
def test_gn208_quiet(text, spelling):
    assert gn(res(text), "GN208", spelling) == []

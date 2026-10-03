"""False positives found on the owner's first real .tex upload (P28).

Every sentence here is synthetic (CLAUDE.md: no third-party or private
text). Each fix has a don't-fire test (the false positive is gone) and a
fire test (the rule still catches the real error).
"""

import pytest

from researchly import api, rules_grammar
from researchly.document import Document
from researchly.ingest.latex import code_macros_in

PRE = "\\documentclass{article}\n"


def tex(body, preamble=""):
    return PRE + preamble + "\\begin{document}\n" + body + "\n\\end{document}\n"


def flags(text, kind="latex", rule=None):
    a = api.analyze(text, kind=kind, show_preferences=True, with_metrics=False)
    return [(s.rule_id, a.document.original[s.start:s.end]) for s in a.suggestions
            if rule is None or s.rule_id == rule]


# --- masked maths, citations and code make words look adjacent --------------

def test_touches_masked_sees_material_beside_a_span():
    d = Document.from_text(tex("An $\\exp(1)$ prior and a \\cite{k} model."), "latex")
    o = d.original
    an = o.index("An ")
    assert d.touches_masked(an, an + 2)               # maths follows "An"
    model = o.index("model")
    assert d.touches_masked(model, model + 5)         # citation precedes
    prior = o.index("prior")
    assert not d.touches_masked(prior + 6, prior + 9)  # "and": plain neighbours


def test_doubled_word_across_inline_maths_is_not_flagged():
    t = tex("Both models set $H(0)$ and $C(0)$ and then fit the counts.")
    assert flags(t, rule="W207") == []


def test_doubled_word_still_flagged_when_really_doubled():
    t = tex("Both models set the the initial counts.")
    assert flags(t, rule="W207") == [("W207", "the the")]


lt = pytest.mark.skipif(not rules_grammar.available(),
                        reason="LanguageTool not available here")


@lt
def test_grammar_across_maths_is_not_flagged():
    t = tex("An $\\exp(1)$ prior was used, with a $90\\%$ interval of the "
            "Student-$t$ shift.")
    assert flags(t, rule="LT001") == []


@lt
def test_grammar_still_flags_plain_prose():
    assert flags("Results\n\nWe used an prior for the rate.", kind="plain",
                 rule="LT001")


# --- abbreviations with a number attached are labels ------------------------

def test_lineage_and_model_order_names_are_not_undefined_acronyms():
    t = "Results\n\nWe fitted an AR(2) model to the BA.1 and XBB.1.5 counts."
    assert flags(t, kind="plain", rule="F601") == []


def test_undefined_acronym_still_flagged():
    t = "Results\n\nWe compared the ELPD of both fits."
    assert flags(t, kind="plain", rule="F601") == [("F601", "ELPD")]


# --- spelling: prefixes and vocabulary --------------------------------------

@pytest.mark.parametrize("sentence", [
    "The mis-ordered vector was repaired.",
    "The population remains unstratified by age.",
    "Two uncited vectors were averaged.",
    "A second-order autoregression was used.",
    "The decadal bands were merged.",
    "Counts were extracted programmatically.",
    "The severity simplices were relaxed.",
    "The rate was parameterised on the log scale.",
    "A softmax maps the values into the simplex.",
    "No treedepth saturation and enough walltime.",
    "The constants are hardcoded.",
])
def test_real_words_are_not_spelling_errors(sentence):
    assert flags("Results\n\n" + sentence, kind="plain", rule="S001") == []


@pytest.mark.parametrize("sentence,word", [
    ("The population remains unstratfied by age.", "unstratfied"),
    ("The constatns are fixed.", "constatns"),
])
def test_typos_behind_a_prefix_are_still_caught(sentence, word):
    assert ("S001", word) in flags("Results\n\n" + sentence, kind="plain",
                                   rule="S001")


# --- LaTeX code macros --------------------------------------------------------

def test_preamble_code_wrappers_are_recognised():
    pre = ("\\newcommand{\\code}[1]{\\texttt{\\small #1}}\n"
           "\\newcommand{\\fn}[1]{{\\ttfamily #1}}\n"
           "\\newcommand{\\term}[1]{\\emph{#1}}\n")
    assert code_macros_in(pre) == {"code", "fn"}


def test_code_and_toc_plumbing_are_masked_but_prose_wrappers_are_not():
    t = tex("The flag \\code{pacx1} and \\texttt{tou\\_prior} and \\fn{zqfile} "
            "and \\term{Keepword} and \\path{a/b}. "
            "\\addcontentsline{toc}{section}{Declaration}",
            preamble="\\newcommand{\\code}[1]{\\texttt{#1}}\n"
                     "\\newcommand{\\fn}[1]{\\texttt{#1}}\n"
                     "\\newcommand{\\term}[1]{\\emph{#1}}\n")
    masked = " ".join(Document.from_text(t, "latex").masked.split())
    for code in ("pacx1", "tou", "zqfile", "a/b", "toc", "Declaration"):
        assert code not in masked, code
    assert "Keepword" in masked


@lt
def test_grammar_across_maths_on_the_next_source_line():
    t = tex("This is precisely why\n        $\\psi$ must be read as a reduction.")
    assert flags(t, rule="LT001") == []


def test_a_heading_is_not_inline_material():
    t = tex("\\section{Results}\nThe the counts rose.")
    d = Document.from_text(t, "latex")
    the = d.original.index("The the")
    assert not d.touches_masked(the, the + 3)
    assert flags(t, rule="W207") == [("W207", "The the")]


def test_paragraph_break_stops_the_walk():
    t = tex("A sentence ends here with $x$.\n\nThe next paragraph starts.")
    d = Document.from_text(t, "latex")
    nxt = d.original.index("The next")
    assert not d.touches_masked(nxt, nxt + 3)


def test_a_typo_that_starts_like_a_prefix_is_still_a_typo():
    # Regression found while fixing P28: "mis" + "peled" passed as a prefix
    # on "pele" + "d" until stems had to be dictionary words as written.
    assert ("S001", "mispeled") in flags("Results\n\nThe word was mispeled.",
                                         kind="plain", rule="S001")


def test_a_lost_hyphen_with_a_tripled_letter_is_still_flagged():
    # Corpus review of the prefix rule (P28): "cross" + "sectional" is real,
    # "crosssectional" is not.
    assert ("S001", "crosssectional") in flags(
        "Results\n\nA crosssectional survey was run.", kind="plain", rule="S001")


# --- formatting is not inline material (bench finding 6, P29) ---------------
# The P28 guard first counted every masked character, so "\emph{" and "**"
# silenced real errors next to them. Only atoms (maths, citations, code,
# references, Word equations) count now.

def test_formatting_macros_are_not_atoms():
    d = Document.from_text(tex("We observed an \\emph{large} increase."), "latex")
    an = d.original.index("an ")
    assert not d.touches_masked(an, an + 2)


@lt
@pytest.mark.parametrize("text,kind", [
    (tex("We observed an \\emph{large} increase in cases."), "latex"),
    (tex("We observed an \\textbf{large} increase in cases."), "latex"),
    ("Results\n\nWe observed an **large** increase in cases.", "markdown"),
])
def test_grammar_next_to_formatting_is_still_flagged(text, kind):
    assert flags(text, kind=kind, rule="LT001"), "an + large must still be flagged"


def test_doubled_word_across_bold_is_still_flagged():
    t = tex("\\textbf{The} the outbreak spread.")
    assert [r for r, _ in flags(t, rule="W207")] == ["W207"]


def test_markdown_inline_code_and_maths_are_atoms():
    d = Document.from_text("Results\n\nWe set `x` and $y$ and then fit.", "markdown")
    assert len(d.atoms) == 2


def test_word_equations_are_atoms():
    from ingest_fixtures import docx_bytes, equation, para
    from researchly.ingest import load_bytes
    d = load_bytes("c.docx", docx_bytes(para("We set ", equation("x+1"), " and then fit.")))
    assert len(d.atoms) == 1

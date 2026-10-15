"""Genre-native and scope-aware profiles (Codex review #4, 2026-10-15):
the article type is separate from how much of the document was handed
over (whole, chapter, excerpt); topical headings are read from their
wording; a policy brief is mapped by its own units and a response to
reviewers by its comment-and-reply units, described and never judged.
Synthetic text only.
"""

import pytest

from researchly import api, profiles, shapes
from researchly.discourse import units
from researchly.document import Document
from tests.test_explanations import INTERNAL

NLP = api.get_nlp()


def run(text, **kw):
    return api.analyze(text, nlp=NLP, with_review=True, with_narrative=True,
                       **kw)


def points(a, qid="D"):
    return next(q for q in a.review["questions"] if q["id"] == qid)["points"]


def asks_for_sections(a):
    return [p for p in points(a) if "expects but the headings do not show"
            in p]


def asks_for_limitations(a):
    return [p for p in points(a) if "No limitations section" in p]


IMRAD = ("Introduction\n\nDengue remains a leading cause of admission. "
         "Little is known about the dry season.\n\n"
         "Methods\n\nWe fitted a renewal model to weekly counts.\n\n"
         "Results\n\nCases fell by 40% after spraying.\n\n"
         "Discussion\n\nSpraying may have reduced transmission.\n")
METHODS_ONLY = ("Methods\n\nWe fitted a renewal model to weekly counts from "
                "three districts. Priors were placed on the reproduction "
                "number.\n")
PARAGRAPH = ("Spraying may have reduced transmission in the north, although "
             "the rain that season was unusually light.\n")


# --- scope: inferred, chosen, and what it changes ----------------------------------

@pytest.mark.parametrize("text, kind, doc_type, scope", [
    (IMRAD, "plain", None, "whole"),
    (METHODS_ONLY, "plain", None, "excerpt"),
    (PARAGRAPH, "plain", None, "excerpt"),
    (METHODS_ONLY, "plain", "manuscript", "excerpt"),
    (IMRAD, "plain", "thesis-chapter", "chapter"),
    ("\\chapter{Measles in schools}\n\\section{Methods}\nWe fitted a "
     "model.\n\\section{Results}\nCases fell.\n", "latex", None, "chapter"),
    ("# Chapter 3: Measles\n\n## Methods\n\nWe fitted a model.\n", "markdown",
     None, "chapter"),
    # A commentary or brief without headings is a whole piece.
    (PARAGRAPH, "plain", "commentary", "whole"),
    (PARAGRAPH, "plain", "policy-brief", "whole"),
])
def test_scope_is_inferred_from_the_headings(text, kind, doc_type, scope):
    a = api.analyze(text, kind=kind, nlp=NLP, document_type=doc_type)
    assert a.scope.id == scope and a.scope.guessed
    note = a.scope.note
    assert note.startswith("Read as ") and not INTERNAL.search(note)
    assert "—" not in note and "'" not in note


def test_a_chosen_scope_wins_and_says_so():
    a = api.analyze(IMRAD, nlp=NLP, document_scope="excerpt")
    assert a.scope.id == "excerpt" and not a.scope.guessed
    assert "as you chose" in a.scope.note
    assert api.analyze(METHODS_ONLY, nlp=NLP,
                       document_scope="whole").scope.id == "whole"
    assert api.analyze(IMRAD, nlp=NLP, document_scope="auto").scope.guessed


def test_the_scope_reaches_the_wire():
    info = shapes.profile_info(api.analyze(METHODS_ONLY, nlp=NLP))
    assert info["scope"]["id"] == "excerpt"
    assert info["scope"]["label"] == "Excerpt"
    assert "only section is Methods" in info["scope"]["note"]


def test_an_excerpt_is_not_asked_for_missing_sections():
    # A Methods section pasted on its own, checked as a research article:
    # the whole article would be asked for its Introduction and its
    # limitations; the excerpt is not.
    a = run(METHODS_ONLY, document_type="manuscript")
    assert a.scope.id == "excerpt"
    assert asks_for_sections(a) == [] and asks_for_limitations(a) == []
    whole = run(METHODS_ONLY, document_type="manuscript",
                document_scope="whole")
    assert asks_for_sections(whole) and asks_for_limitations(whole)


def test_a_chapter_is_not_asked_for_an_abstract():
    whole = run(IMRAD, document_type="manuscript")
    assert any("abstract" in p for p in asks_for_sections(whole))
    chapter = run(IMRAD, document_type="manuscript", document_scope="chapter")
    assert not any("abstract" in p for p in asks_for_sections(chapter))


def test_the_policy_brief_and_commentary_do_not_ask_for_research_parts():
    brief = ("Context\n\nUptake fell to 81% this year.\n\nRecommendations\n\n"
             "The ministry should restore the mandate.\n")
    for kind in ("policy-brief", "commentary"):
        a = run(brief, document_type=kind)
        # Checks the type switches off are listed as not assessed; nothing
        # is asked for.
        text = " ".join(p for p in points(a)
                        if not p.startswith("Not assessed"))
        assert "abstract" not in text.lower()
        assert asks_for_limitations(a) == []
        assert "gap statement" not in text


# --- topical headings (PLAN: the owner's first real .tex upload) -------------------

REPORT = r"""\documentclass{article}
\begin{document}
\section{Introduction}
Measles remains a major cause of child deaths in Oldmere. Little is known
about its spread in schools.

\section{Experiment 1: the baseline SEIR}
The baseline SEIR model was introduced by Kermack and McKendrick. We fitted
the model to weekly case counts from the district registry. Priors were
placed on the transmission rate and the latent period. The likelihood was
negative binomial.
\subsection{Calibration}
The sampler was run for four chains. Convergence was assessed by Gelman and
Rubin.

\section{Why schools matter}
We argue that school closures must be planned now. Closing schools causes
large losses for families. This must not be ignored. The plan was
criticised by Smith.

\section{Conclusion}
Schools should be part of the plan.
\end{document}
"""


def g104(a):
    return [(s.section, a.document.original[s.start:s.end])
            for s in a.suggestions if s.rule_id == "G104"]


@pytest.mark.parametrize("doc_type", ["auto", "general", "manuscript",
                                      "thesis-chapter"])
def test_a_topical_methods_section_is_read_as_methods(doc_type):
    a = api.analyze(REPORT, kind="latex", nlp=NLP, document_type=doc_type)
    assert a.topical == [{"heading": "Experiment 1: the baseline SEIR",
                          "section": "methods"}]
    # Passive voice is the convention there, and in its subsection.
    hits = g104(a)
    assert not any("Kermack" in t or "Gelman" in t for _, t in hits)
    # The argued topical section is untouched: still flagged as before.
    assert ("other", "was\ncriticised by Smith") in hits or any(
        "Smith" in t for s, t in hits if s == "other")


def test_without_the_reading_the_passive_was_flagged():
    # The behaviour the owner's upload met: a type that reads topical
    # headings as argued prose (commentary) still flags the passive.
    a = api.analyze(REPORT, kind="latex", nlp=NLP,
                    document_type="commentary")
    assert a.topical == []
    assert any("Kermack" in t for _, t in g104(a))


def test_mixed_or_argued_topical_sections_stay_as_they_were():
    text = (r"\section{Introduction}" "\nLittle is known about schools.\n"
            r"\section{Measles in schools}" "\n"
            "We fitted the model to weekly counts. We argue that closures "
            "must be planned. This shows that schools drive spread. "
            "Closing schools causes losses.\n")
    a = api.analyze(text, kind="latex", nlp=NLP)
    assert a.topical == []
    assert any(h.section == "other" for h in a.document.headings)


def test_a_topical_results_section_is_read_as_results():
    text = (r"\section{Introduction}" "\nLittle is known about schools.\n"
            r"\section{What the fits showed}" "\n"
            "We found that cases rose in every school. The odds ratio was "
            "2.1 (95% CI 1.4 to 3.0). Attack rates were higher than in "
            "the community.\n")
    a = api.analyze(text, kind="latex", nlp=NLP)
    assert a.topical[0]["section"] == "results"


def test_plain_text_and_non_research_types_are_untouched():
    a = api.analyze(REPORT, kind="latex", nlp=NLP,
                    document_type="policy-brief")
    assert a.topical == []
    plain = api.analyze("Experiment 1\n\nWe fitted a model to counts. "
                        "Priors were placed on the rate.\n", nlp=NLP)
    assert plain.topical == []


def test_a_theory_chapter_is_not_asked_for_methods_and_results():
    text = (r"\chapter{Thresholds}" "\n" r"\section{Introduction}" "\n"
            "Little is known about thresholds.\n"
            r"\section{The threshold theorem}" "\n"
            "We argue that the threshold must hold. This shows that "
            "spread stops. Because the rate falls, the epidemic ends.\n"
            r"\section{Discussion}" "\nThe theorem may extend to networks.\n"
            r"\section{Conclusion}" "\nThresholds matter.\n")
    a = run(text, kind="latex", document_type="thesis-chapter")
    assert a.scope.id == "chapter"
    asked = " ".join(asks_for_sections(a))
    assert "methods" not in asked and "results" not in asked
    # A chapter with only named sections is still asked for its Methods.
    named = run("Introduction\n\nLittle is known.\n\nDiscussion\n\nIt may "
                "help.\n", document_type="thesis-chapter")
    assert "methods" in " ".join(asks_for_sections(named))


# --- policy brief units --------------------------------------------------------

BRIEF = ("Key messages\n\nRestoring the school mandate is the fastest way "
         "to stop measles.\n\n"
         "Context\n\nMeasles returned to three districts of Oldmere this "
         "year after uptake fell.\n\n"
         "Evidence\n\nUptake fell to 81% in 2025 (district survey, 2026). "
         "Studies from Marrowick show that mandates lift uptake.\n\n"
         "Policy options\n\nOption 1 is to restore the mandate. Option 2 is "
         "to fund outreach, which would cost more but avoid exclusions.\n\n"
         "Recommendations\n\nThe ministry should restore the mandate within "
         "six months.\n")


def unit_map(n):
    return {s["section"]: {m["id"]: m["status"] for m in s["moves"]}
            for s in n["sections"]}


def test_a_policy_brief_is_mapped_by_its_units():
    a = run(BRIEF, document_type="policy-brief")
    n = a.narrative
    assert [s["label"] for s in n["sections"]] == [
        "Context", "Evidence", "Options", "Recommendations"]
    m = unit_map(n)
    assert m["context"] == {"problem": "present"}
    assert m["evidence"] == {"brief_evidence": "present"}
    assert m["options"] == {"options_set_out": "present",
                            "tradeoffs": "present"}
    assert m["recommendations"] == {"recommendation": "present",
                                    "who_when": "present"}
    # Plain text records only named headings: "Key messages" is a line.
    assert n["unmapped"] == []
    assert n["note"].startswith("Read as a policy brief")
    assert "Not found" not in n["note"]
    # Every move teaches with the policy-brief card and a named source.
    for s in n["sections"]:
        for mv in s["moves"]:
            assert mv["learn_ref"] == "policy-brief"
            assert "Young" in mv["source"]
            assert not INTERNAL.search(mv["question"] + mv["plain"])


def test_other_headings_of_a_brief_are_named_as_unmapped():
    md = "\n".join(("## " + line) if line in (
        "Key messages", "Context", "Evidence", "Policy options",
        "Recommendations") else line for line in BRIEF.split("\n"))
    n = run(md, kind="markdown", document_type="policy-brief").narrative
    assert [s["section"] for s in n["sections"]] == list(units.POLICY_UNITS)
    assert n["unmapped"] == ["Key messages"]


def test_a_brief_without_options_says_so_when_whole():
    text = BRIEF.split("Policy options")[0] + BRIEF.split(
        "avoid exclusions.\n\n")[1]
    n = run(text, document_type="policy-brief").narrative
    assert "Not found among the headings: Options." in n["note"]
    # An excerpt of a brief is not asked for the parts it does not hold.
    n = run(text, document_type="policy-brief",
            document_scope="excerpt").narrative
    assert "Not found" not in n["note"]


def test_a_unit_whose_move_is_not_in_the_wording_says_not_detected():
    text = ("Context\n\nThe district is small and green.\n\n"
            "Recommendations\n\nThe ministry should act.\n")
    m = unit_map(run(text, document_type="policy-brief").narrative)
    assert m["context"] == {"problem": "not_detected"}
    assert m["recommendations"]["recommendation"] == "present"


def test_units_change_the_map_never_the_suggestions():
    a = api.analyze(BRIEF, nlp=NLP, document_type="policy-brief")
    b = run(BRIEF, document_type="policy-brief")
    assert [(s.rule_id, s.start) for s in a.suggestions] == \
        [(s.rule_id, s.start) for s in b.suggestions]


def test_a_policy_brief_without_units_maps_as_before():
    text = ("Introduction\n\nMeasles is back.\n\nDiscussion\n\nThe ministry "
            "should act now.\n")
    n = run(text, document_type="policy-brief").narrative
    assert [s["section"] for s in n["sections"]] == ["introduction",
                                                     "discussion"]


@pytest.mark.parametrize("heading, unit", [
    ("Context", "context"), ("2. Background and context", "context"),
    ("The problem", "context"), ("Evidence", "evidence"),
    ("What the evidence shows", "evidence"), ("Policy options", "options"),
    ("Options and recommendations", "recommendations"),
    ("Recommendations", "recommendations"), ("Next steps", "recommendations"),
    ("Key messages", None), ("Acknowledgements", None),
    ("A very long heading that names the context of the whole study here",
     None),
])
def test_unit_names(heading, unit):
    assert units.unit_of(heading) == unit


# --- response to reviewers --------------------------------------------------------

LETTER = ("We thank both reviewers for their careful reading.\n\n"
          "Reviewer 1\n\n"
          "Comment 1: The sample size is small and the intervals are wide.\n\n"
          "Response: We now report the intervals in Table 2.\n\n"
          "Comment 2: The model assumes homogeneous mixing.\n\n"
          "Response: We added an age-structured sensitivity analysis.\n\n"
          "Reviewer 2\n\n"
          "> The discussion overstates the findings.\n\n"
          "We have softened the claims in the Discussion.\n\n"
          "> Figure 2 is hard to read.\n\n"
          "We redrew Figure 2 with larger labels.\n\n"
          "R3.1: Please define R0 at first use.\n"
          "Reply: Done; it is defined in the Introduction.\n\n"
          "Reviewer 4, Comment 1: Cite the earlier survey.\n")


def test_reviewer_comments_and_replies_are_recognised():
    found = units.reviewer_units(Document.from_text(LETTER))
    got = [(u["label"],
            LETTER[slice(*u["comment_span"])],
            LETTER[slice(*u["reply_span"])] if u["reply_span"] else None)
           for u in found]
    assert got == [
        ("Reviewer 1, comment 1",
         "The sample size is small and the intervals are wide.",
         "We now report the intervals in Table 2."),
        ("Reviewer 1, comment 2", "The model assumes homogeneous mixing.",
         "We added an age-structured sensitivity analysis."),
        ("Reviewer 2, comment 1", "The discussion overstates the findings.",
         "We have softened the claims in the Discussion."),
        ("Reviewer 2, comment 2", "Figure 2 is hard to read.",
         "We redrew Figure 2 with larger labels."),
        ("Reviewer 3, comment 1", "Please define R0 at first use.",
         "Done; it is defined in the Introduction."),
        ("Reviewer 4, comment 1", "Cite the earlier survey.", None),
    ]


def test_a_response_letter_is_described_never_judged():
    a = run(LETTER, document_type="response-to-reviewers")
    n = shapes.extras(a)["narrative"]
    assert len(n["units"]) == 6
    assert n["units"][5]["reply"] is None
    assert n["note"].startswith("Found 6 reviewer comments; 5 of them have "
                                "a reply.")
    assert "described, not judged" in n["note"]
    assert not any(m["status"] == "not_detected"
                   for s in n["sections"] for m in s["moves"])
    for u in n["units"]:
        assert u["learn_ref"] == "response-letter"
        c = u["comment"]
        assert LETTER[c["start"]:c["end"]] == c["text"]


def test_auto_recognises_a_response_letter():
    a = api.analyze(LETTER, nlp=NLP)
    assert a.profile.id == "response-to-reviewers" and a.profile_guessed
    assert a.profile_evidence.startswith("Reviewer 1, comment 1")


def test_one_comment_line_in_a_paper_is_not_a_letter():
    text = IMRAD + "\nComment 1: see the appendix.\n"
    assert api.analyze(text, nlp=NLP).profile.id == "manuscript"
    one = ("Comment 1: The intervals are wide.\n\nResponse: We agree.\n")
    assert api.analyze(one, nlp=NLP).profile.id == "general"


def test_a_letter_with_no_recognised_units_says_so():
    n = run("We thank the editor for the chance to revise.\n",
            document_type="response-to-reviewers").narrative
    assert n["units"] == [] and "No reviewer comments were recognised" in \
        n["note"]

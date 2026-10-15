"""The gap as an argument, carried to the end (2026-10-14): D903 gap
without a stake, D904 "fills the gap", D905 generic future research, the
review's link to the Discussion (sources that carry it but were never
cited before it) and the thesis-only moves on the narrative map.

Fire and don't-fire for every rule. Synthetic text only: the districts
are the demo manuscript's fictional ones.
"""

import pytest

from researchly import api, learn, sources
from researchly.discourse import citations
from researchly.discourse import moves as moves_mod
from researchly.document import Document
from researchly.engine import REGISTRY, load_rules
from tests.test_explanations import INTERNAL

NLP = api.get_nlp()

_TERRITORY = ("Dengue is a growing cause of admission in the lowland "
              "districts. Rainfall and temperature shape the length of each "
              "season. ")


def ids(text, kind="plain", **kw):
    a = api.analyze(text, kind=kind, nlp=NLP, show_preferences=True, **kw)
    return [s.rule_id for s in a.suggestions]


def hits(text, rule_id, kind="plain", **kw):
    a = api.analyze(text, kind=kind, nlp=NLP, show_preferences=True, **kw)
    return [s for s in a.suggestions if s.rule_id == rule_id]


# --- the rules are registered and explained -------------------------------------------

@pytest.mark.parametrize("rid", ["D903", "D904", "D905", "D906"])
def test_rules_are_registered_explained_and_reviewed(rid):
    load_rules()
    r = REGISTRY[rid]
    assert r.category.value == "improvement"     # never an error
    assert r.fix_safety == "review"              # no replacement offered
    assert len(r.plain.split()) >= 8
    for field in (r.short, r.why, r.plain):
        assert not INTERNAL.search(field)
    assert learn.card_for_rule(rid) in learn.CARDS


def test_the_workshop_is_shown_as_the_owners_learnings():
    assert sources.cite("workshop-S2") == sources.LEARNINGS
    load_rules()
    assert REGISTRY["D904"].source == sources.LEARNINGS
    assert "Organization 18(1)" in REGISTRY["D903"].source
    assert "Journal of English for Academic Purposes" in REGISTRY["D905"].source
    for code in ("Alvesson2011", "Sandberg2011", "Bunton2005", "Kwan2006",
                 "Lim2006"):
        assert len(sources.cite(code)) > 40


# --- D903: a gap with no stake -----------------------------------------------------

def test_d903_fires_on_a_bare_absence_in_the_introduction():
    text = ("Introduction\n\n" + _TERRITORY + "The effect of school terms "
            "on transmission remains underexplored. We set out to estimate "
            "it.\n")
    (h,) = hits(text, "D903")
    assert h.text == "underexplored" and h.section == "introduction"
    assert h.learn_ref == "gap-stake"


@pytest.mark.parametrize("gap", [
    "Little is known about transmission in schools.",
    "Transmission in schools has largely been overlooked.",
    "To our knowledge, no study has examined transmission in schools.",
])
def test_d903_fires_on_other_bare_absences(gap):
    text = ("Introduction\n\n" + _TERRITORY + gap
            + " We set out to estimate it.\n")
    assert "D903" in ids(text)


@pytest.mark.parametrize("stake", [
    # the consequence, in the next sentence
    "The regional plan assumes schools add nothing, so the spraying "
    "budget may be set too low.",
    # who is left guessing
    "Without this estimate, the timing of school closures is guesswork.",
    # a conditional cost
    "If schools amplify spread, closing them early would shorten the "
    "season.",
])
def test_d903_is_quiet_when_the_stake_is_stated(stake):
    text = ("Introduction\n\n" + _TERRITORY + "The effect of school terms "
            "on transmission remains underexplored. " + stake + "\n")
    assert "D903" not in ids(text)


def test_d903_leaves_question_raising_gaps_alone():
    text = ("Introduction\n\n" + _TERRITORY + "It remains unclear whether "
            "school terms change transmission. We set out to estimate it.\n")
    assert "D903" not in ids(text)


def test_d903_gives_an_unsoftened_novelty_claim_to_e705():
    # One card per span: "has not been studied" without "to our knowledge"
    # is E705's, and its fix comes first.
    text = ("Introduction\n\n" + _TERRITORY + "School terms have not been "
            "studied in the lowland districts. We set out to estimate them.\n")
    found = ids(text)
    assert "E705" in found and "D903" not in found
    assert "D903" in ids(text, disabled=["E705"])


def test_d903_is_section_aware():
    body = ("The effect of school terms on transmission remains "
            "underexplored. We set out to estimate it.\n")
    assert "D903" not in ids("Discussion\n\n" + body)
    assert "D903" not in ids(body)               # no heading: cannot tell


def test_d903_is_off_where_no_gap_is_expected():
    text = ("Introduction\n\n" + _TERRITORY + "The effect of school terms "
            "on transmission remains underexplored. We set out to estimate "
            "it.\n")
    assert "D903" not in ids(text, document_type="commentary")


# --- D904: "fills the gap" ------------------------------------------------------------

@pytest.mark.parametrize("sentence", [
    "Our estimates fill the gap in the literature on school terms.",
    "Our study addresses this knowledge gap.",
    "This work fills this gap.",
    "The estimates bridge an important research gap.",
])
def test_d904_fires_in_the_discussion(sentence):
    (h,) = hits("Discussion\n\n" + sentence + "\n", "D904")
    assert h.learn_ref == "carry-the-gap"


def test_d904_fires_in_the_conclusion():
    assert "D904" in ids("Conclusion\n\nThis thesis fills the gap in the "
                         "literature on school terms.\n")


@pytest.mark.parametrize("sentence", [
    # a ruling, not a claim that the gap is filled
    "These findings partly fill the gap in the literature on schools.",
    "These findings do not fill the gap in the literature on schools.",
    "This closes the gap for the wet season only.",
    # an aim recalled, not a verdict
    "We set out to fill this gap with weekly counts.",
    # literal gaps
    "Mass vaccination could fill the immunity gap in older children.",
    "These dashboards bridge the gap between modelling and policy.",
    "Mobile clinics fill this gap in vaccination coverage.",
])
def test_d904_is_quiet_on_rulings_aims_and_literal_gaps(sentence):
    assert "D904" not in ids("Discussion\n\n" + sentence + "\n")


def test_d904_is_section_aware():
    # In the Introduction, "to fill this gap" is the aim: the right move.
    text = ("Introduction\n\nOur estimates fill the gap in the literature "
            "on school terms.\n")
    assert "D904" not in ids(text)


# --- D905: generic future research ----------------------------------------------------

@pytest.mark.parametrize("sentence", [
    "Further research is needed.",
    "Future research should explore this further.",
    "Further studies are needed to confirm these findings in other "
    "settings.",
    "This warrants further investigation.",
    "More studies are required in this area.",
])
def test_d905_fires_on_a_call_with_no_object(sentence):
    (h,) = hits("Conclusion\n\n" + sentence + "\n", "D905")
    assert h.learn_ref == "carry-the-gap"


@pytest.mark.parametrize("sentence", [
    "Future work should estimate the dry-season reproduction number from "
    "serology.",
    "Further research is needed to separate rainfall from school terms in "
    "Oldmere.",
    "The role of rainfall in the timing of outbreaks warrants further "
    "study.",
])
def test_d905_is_quiet_when_the_open_question_is_named(sentence):
    assert "D905" not in ids("Conclusion\n\n" + sentence + "\n")


def test_d905_is_section_aware():
    assert "D905" in ids("Discussion\n\nFurther research is needed.\n")
    assert "D905" in ids("Limitations\n\nFurther research is needed.\n")
    assert "D905" not in ids("Introduction\n\nFurther research is needed.\n")


def test_d905_aggregates_per_section():
    text = ("Conclusion\n\nFurther research is needed. Future work should "
            "explore this. More studies are needed.\n")
    (h,) = hits(text, "D905")
    assert "(3 similar in this section)" in h.message


# --- the review's link to the Discussion ----------------------------------------------

_AY = """Introduction

Dengue is a growing burden (Okafor et al., 2019). Seasons follow the rain (Lim and Mensah, 2020; Quintero 2018). Schools may amplify spread (Rahman, 2017).

Methods

We fitted a renewal model (Cori et al., 2013).

Discussion

Our estimate agrees with Okafor et al. (2019). It also matches Haldane et al. (2022), who used serology. Haldane et al. (2022) found a lag of two weeks. Cori et al. (2013) describe the same bias, and Cori et al. (2013) correct it. A single comparison with Brandt (2021) is enough here.
"""


def test_a_source_that_carries_the_discussion_but_was_never_cited_is_shown():
    found = citations.strangers(Document.from_text(_AY))
    assert found["assessed"]
    assert [e["label"] for e in found["items"]] == ["Haldane et al. 2022"]
    # Cori was introduced in the Methods; Brandt is a single comparison.
    assert found["items"][0]["sentences"] == 2


def test_strangers_reach_the_map_and_the_brief():
    a = api.analyze(_AY, nlp=NLP, with_narrative=True, with_review=True)
    (link,) = [x for x in a.narrative["missing_links"]
               if x["code"] == "stranger_sources"]
    assert link["section"] == "discussion"
    assert "Haldane et al. 2022" in link["message"]
    assert link["learn_ref"] == "carry-the-gap"
    assert link["source"].startswith(sources.LEARNINGS)
    assert "Kwan" in link["source"]
    assert link["evidence"] and "Haldane" in link["evidence"][0]
    assert not INTERNAL.search(link["message"])
    d = next(q for q in a.review["questions"] if q["id"] == "D")
    assert any(p.startswith("Sources: 1 source carries") for p in d["points"])
    # Shown, never flagged: no suggestion is made of it.
    assert all("Haldane" not in s.message for s in a.suggestions)


def test_numbered_citations_and_ranges():
    text = ("Introduction\n\nDengue is common [1]. Seasons follow the rain "
            "[2, 3]. Schools matter [4-6].\n\nDiscussion\n\nOur estimate "
            "agrees with [2]. Serology [9] gives a lag. A lag also appears "
            "in [9, 10]. Earlier reviews [5] agree.\n")
    found = citations.strangers(Document.from_text(text))
    assert [e["label"] for e in found["items"]] == ["[9]"]


def test_latex_keys_comments_and_nocite():
    text = r"""\section{Introduction}
Dengue is common \citep{okafor2019}. Seasons follow the rain \citep{lim2020,quintero2018}.
% \cite{haldane2022} was in an older draft
\nocite{brandt2021}
\section{Discussion}
Our estimate agrees with \citet{okafor2019}. Serology gives a lag \citep{haldane2022}.
The lag also appears in \citet{haldane2022}. Brandt \cite{brandt2021} agrees.
The same holds in \cite{brandt2021}.
"""
    found = citations.strangers(Document.from_text(text, "latex"))
    labels = [e["label"] for e in found["items"]]
    # Haldane appeared only in a comment before the Discussion; Brandt only
    # in \nocite, which puts nothing in the prose.
    assert labels == ["haldane2022", "brandt2021"]


def test_markdown_keys():
    text = ("# Introduction\n\nDengue is common [@okafor2019]. Seasons "
            "follow the rain [@lim2020; @quintero2018].\n\n# Discussion\n\n"
            "Serology gives a lag [@haldane2022]. As @haldane2022 notes, "
            "the lag is short.\n")
    found = citations.strangers(Document.from_text(text, "markdown"))
    assert [e["label"] for e in found["items"]] == ["@haldane2022"]


@pytest.mark.parametrize("text, reason", [
    ("Discussion\n\nIt agrees with Haldane et al. (2022). Haldane et al. "
     "(2022) found a lag.\n", "no introduction or literature review"),
    ("Introduction\n\nDengue is common (Okafor, 2019).\n\nDiscussion\n\nIt "
     "agrees with Haldane et al. (2022). Haldane et al. (2022) found a "
     "lag.\n", "too few citations"),
    ("Introduction\n\nDengue is common (Okafor, 2019).\n", "no Discussion"),
])
def test_abstains_when_it_cannot_judge(text, reason):
    found = citations.strangers(Document.from_text(text))
    assert not found["assessed"] and found["items"] == []
    assert reason in found["reason"]
    a = api.analyze(text, nlp=NLP, with_narrative=True, with_review=True)
    assert not [x for x in a.narrative["missing_links"]
                if x["code"] == "stranger_sources"]
    d = next(q for q in a.review["questions"] if q["id"] == "D")
    assert not any(p.startswith("Sources:") for p in d["points"])


def test_a_literature_review_heading_counts_as_the_review():
    # A thesis's "Literature review" chapter, with a topical subsection.
    text = ("# Literature review\n\n## Seasons and schools\n\nDengue is "
            "common (Okafor, 2019). Seasons follow the rain (Lim, 2020). "
            "Schools matter (Haldane et al., 2022).\n\n# Discussion\n\nIt "
            "agrees with Haldane et al. (2022). Haldane et al. (2022) found "
            "a lag.\n")
    found = citations.strangers(Document.from_text(text, "markdown"))
    assert found["assessed"] and found["items"] == []
    a = api.analyze(text, kind="markdown", nlp=NLP, with_review=True)
    d = next(q for q in a.review["questions"] if q["id"] == "D")
    assert "Sources: every source the Discussion leans on was cited before it." in d["points"]


def test_months_and_floats_are_not_authors():
    doc = Document.from_text("Introduction\n\nCases peaked (March 2020) and "
                             "fell (Table 2, 2021). See Figure 3 (2019).\n")
    assert citations.read_citations(doc) == []


# --- the thesis-only moves --------------------------------------------------------------

_THESIS = """Introduction

Dengue is a growing burden in the lowland districts. However, little is known about schools. We therefore set out to estimate their effect.

Methods

Weekly case counts were collected from the surveillance system. We fitted a renewal model by maximum likelihood. Weekly counts cannot separate school terms from rainfall in the same month.

Conclusion

This work adds an estimate of school effects to the field. Planners could use it to time closures. Whether the effect holds in the dry season is still unknown.
"""


def _moves(n, section):
    s = next(s for s in n["sections"] if s["section"] == section)
    return {m["id"]: m for m in s["moves"]}


def test_a_thesis_chapter_is_asked_for_the_limit_and_what_is_open():
    n = api.analyze(_THESIS, nlp=NLP, with_narrative=True,
                    document_type="thesis-chapter").narrative
    methods, conclusion = _moves(n, "methods"), _moves(n, "conclusion")
    assert methods["design_limit"]["status"] == "present"
    assert "cannot separate" in methods["design_limit"]["evidence"]
    assert conclusion["still_open"]["status"] == "present"
    assert methods["design_limit"]["learn_ref"] == "carry-the-gap"


def test_the_moves_are_missing_when_unsaid_and_absent_for_an_article():
    bare = _THESIS.replace(" Weekly counts cannot separate school terms "
                           "from rainfall in the same month.", "").replace(
        " Whether the effect holds in the dry season is still unknown.", "")
    n = api.analyze(bare, nlp=NLP, with_narrative=True,
                    document_type="thesis-chapter").narrative
    assert _moves(n, "methods")["design_limit"]["status"] == "not_detected"
    assert _moves(n, "conclusion")["still_open"]["status"] == "not_detected"
    article = api.analyze(_THESIS, nlp=NLP, with_narrative=True,
                          document_type="manuscript").narrative
    assert "design_limit" not in _moves(article, "methods")
    assert "still_open" not in _moves(article, "conclusion")


# --- D906: thread versus tape ----------------------------------------------------------
# The same gap or aim sentence pasted into several chapters. Synthetic
# chapters about the demo's fictional districts.

_GAP = ("However, little is known about how the length of the wet season "
        "changes dengue transmission in the lowland districts of Oldmere.")
_AIM = ("This thesis aims to estimate how the length of the wet season "
        "changes dengue transmission in the lowland districts of Oldmere.")
_FILLER = ("Weekly case counts were collected from every district clinic. "
           "Rainfall was recorded at four stations across the region. ")


def _thesis(ch1: str, ch2: str, ch3: str = "", kind: str = "markdown") -> str:
    if kind == "latex":
        body = "".join(f"\\chapter{{{t}}}\n{b}\n\n" for t, b in (
            ("Introduction", ch1), ("Seasonal forcing", ch2),
            ("Discussion", ch3)) if b)
        return ("\\documentclass{report}\n\\begin{document}\n"
                "\\chapter*{Abstract}\n" + _AIM + "\n\n" + body
                + "\\end{document}\n")
    parts = [("Chapter 1: Introduction", ch1), ("Chapter 2: Seasonal forcing",
             ch2), ("Chapter 3: General discussion", ch3)]
    return "".join(f"# {t}\n\n{b}\n\n" for t, b in parts if b)


def _md_hits(text):
    return hits(text, "D906", kind="markdown")


def _md_ids(text):
    return ids(text, kind="markdown")


def test_d906_fires_on_a_gap_sentence_pasted_into_a_later_chapter():
    text = _thesis(_FILLER + _GAP, _GAP + " " + _FILLER)
    (h,) = _md_hits(text)
    assert h.start > text.index("Chapter 2")
    assert text[h.start:h.end].startswith("However, little is known")
    assert "Chapter 1" in h.message
    assert h.category.value == "improvement"


def test_d906_fires_on_a_near_copy_and_names_the_first_chapter():
    # One word changed: still tape. Chapter 3 points back at Chapter 1.
    copy = _GAP.replace("lowland", "southern")
    text = _thesis(_FILLER + _GAP, _FILLER, copy + " " + _FILLER)
    (h,) = _md_hits(text)
    assert h.start > text.index("Chapter 3")
    assert "Chapter 1" in h.message


def test_d906_fires_in_latex_chapters_and_skips_the_abstract():
    text = _thesis(_FILLER + _AIM, _AIM + " " + _FILLER, kind="latex")
    found = hits(text, "D906", kind="latex")
    assert len(found) == 1
    assert found[0].start > text.index("\\chapter{Seasonal forcing}")
    # The starred Abstract is not a chapter: chapter 1 is "Introduction".
    assert "Chapter 1" in found[0].message


def test_d906_quiet_when_the_gap_is_carried_forward():
    # A thread: the same key words, but the later sentence knows more.
    thread = ("Chapter 1 showed that a longer wet season raises dengue "
              "transmission in the lowland districts, but not whether the "
              "effect holds in the dry uplands.")
    assert "D906" not in _md_ids(_thesis(_FILLER + _GAP, thread + " " + _FILLER))


def test_d906_quiet_on_repeated_sentences_that_are_not_gap_or_aim():
    # Methods boilerplate repeated across chapters (a thesis by
    # publication) is not the gap standing still.
    method = ("Weekly case counts from every district clinic were linked to "
              "rainfall records from four stations across the region.")
    assert "D906" not in _md_ids(_thesis(method + " " + _GAP, method))


def test_d906_quiet_within_one_chapter_and_without_chapters():
    # Repeated in the same chapter: not a chapter-to-chapter copy.
    assert "D906" not in _md_ids(_thesis(_GAP + " " + _FILLER + _GAP, _FILLER))
    # An article (no chapters): Introduction and Discussion may echo.
    article = ("# Introduction\n\n" + _GAP + "\n\n# Discussion\n\n" + _GAP
               + "\n")
    assert "D906" not in _md_ids(article)


def test_d906_quiet_on_short_sentences():
    short = "Little is known about rainfall effects."
    assert "D906" not in _md_ids(_thesis(short + " " + _FILLER, short))


def test_d906_reads_word_chapters():
    paras = [{"text": "Chapter 1 Introduction", "style": "Heading 1"},
             {"text": _FILLER + _GAP, "style": ""},
             {"text": "Chapter 2 Seasonal forcing", "style": "Heading 1"},
             {"text": _GAP + " " + _FILLER, "style": ""}]
    a = api.analyze(paras, nlp=NLP, show_preferences=True)
    assert [s.rule_id for s in a.suggestions].count("D906") == 1


def test_profile_moves_are_explained_and_reach_a_card():
    for profile, schemas in moves_mod.PROFILE_SCHEMAS.items():
        for section, schema in schemas.items():
            for mid in schema:
                m = moves_mod.MOVES[mid]
                assert m.question.endswith("?") and len(m.plain.split()) >= 10
                assert m.frame.startswith("“") and "[" in m.frame
                for field in (m.label, m.question, m.plain, m.frame):
                    assert not INTERNAL.search(field)
                assert learn.card_for_move(section, mid) in learn.CARDS

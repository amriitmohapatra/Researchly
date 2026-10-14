"""Discipline packs (S4, P3): reporting checklists, checked against the
text. Reporting only, never the science. Synthetic text only."""

import pytest

from researchly import api, packs
from tests.test_explanations import INTERNAL

NLP = api.get_nlp()

FORECAST = """Abstract

We forecast weekly dengue cases in three districts to inform the public health response.

Introduction

Dengue remains a major burden. We aimed to forecast weekly incidence four weeks ahead.

Methods

Weekly case counts were obtained from the national surveillance system. We corrected for reporting delays with a nowcast. We fitted a renewal model and assumed a gamma-distributed generation interval. Priors on the parameters were taken from earlier studies. Forecast accuracy was assessed with the weighted interval score against a naive baseline. Code is available on GitHub.

Results

Forecasts covered 92% of observations within their 95% prediction intervals.

Discussion

Our forecasts may not generalise to larger outbreaks. A limitation is that reporting changed during the season. This work was funded by a national research grant.
"""


def check(text, cid):
    return api.analyze(text, nlp=NLP, checklist=cid).checklist


def test_registry_items_are_explained_and_clean():
    for c in packs.checklists().values():
        assert len(c.items) >= 12 and c.citation
        ids = [i.id for i in c.items]
        assert len(ids) == len(set(ids))
        for it in c.items:
            assert it.question.endswith("?")
            for field in (it.question, it.plain, it.topic):
                assert not INTERNAL.search(field), (c.id, it.id, field)
            assert it.signals


def test_listing_names_every_checklist():
    assert [c["id"] for c in packs.listing()] == [
        "strobe", "consort", "prisma", "epiforge"]


@pytest.mark.parametrize("text,expected", [
    ("We conducted a retrospective cohort study of 4,000 adults.", "strobe"),
    ("In this randomised controlled trial, participants were randomly "
     "assigned to two arms.", "consort"),
    ("We conducted a systematic review and meta-analysis of trials.", "prisma"),
    ("We report forecasts of weekly cases for the next month.", "epiforge"),
    ("We fitted a model to the data.", None),
])
def test_the_text_suggests_its_checklist(text, expected):
    assert packs.suggest(text) == expected


def test_a_complete_forecast_paper_reports_most_items():
    c = check(FORECAST, "epiforge")
    st = {i["id"]: i["status"] for i in c["items"]}
    for item in ("design", "horizon", "data-issues",
                 "model", "assumptions", "parameters", "uncertainty",
                 "evaluation", "baseline", "code", "limitations", "funding"):
        assert st[item] == "found", item
    # compound questions: what the text gives, and what it does not
    by = {i["id"]: i for i in c["items"]}
    assert by["purpose"]["status"] == "partial"
    assert [p["found"] for p in by["purpose"]["parts"]] == [True, False]
    assert by["data"]["status"] == "partial"      # sources, not availability
    hor = next(i for i in c["items"] if i["id"] == "horizon")
    assert "four weeks ahead" in hor["evidence"]
    assert c["suggested"] is True and c["found"] <= c["total"]


def test_an_item_not_reported_is_a_prompt_with_its_question():
    text = FORECAST.replace("Code is available on GitHub.", "")
    c = check(text, "epiforge")
    code = next(i for i in c["items"] if i["id"] == "code")
    assert code["status"] == "needs_check" and code["evidence"] is None
    assert code["question"].endswith("?") and "supplement" in c["note"]


def test_items_are_looked_for_in_their_sections():
    # "assumed" in the Discussion does not report the Methods' assumptions
    text = ("Methods\n\nWe fitted a renewal model.\n\nDiscussion\n\n"
            "We assumed too much.\n")
    c = check(text, "epiforge")
    st = {i["id"]: i["status"] for i in c["items"]}
    assert st["assumptions"] == "needs_check"


def test_auto_uses_the_suggestion_and_nothing_when_there_is_none():
    assert check(FORECAST, "auto")["id"] == "epiforge"
    a = api.analyze("Methods\n\nWe fitted a model.\n", nlp=NLP, checklist="auto")
    assert a.checklist is None and a.suggested_checklist is None


def test_off_unless_asked_but_the_suggestion_is_always_there():
    a = api.analyze(FORECAST, nlp=NLP)
    assert a.checklist is None and a.suggested_checklist == "epiforge"


def test_unknown_checklist_is_nothing():
    assert check(FORECAST, "poem") is None


def test_an_unheaded_text_is_searched_whole():
    c = check("We report forecasts of weekly cases four weeks ahead, with "
              "95% prediction intervals.\n", "epiforge")
    st = {i["id"]: i["status"] for i in c["items"]}
    assert st["horizon"] == "found" and st["uncertainty"] == "found"


# --- Codex review N1 (2026-10-14): a keyword is not a report ------------------

def _st(text, cid):
    c = check(text, cid)
    return {i["id"]: i for i in c["items"]}, c


def test_a_sentence_saying_it_is_not_reported_does_not_count():
    by, c = _st("Methods\n\nThe sample size is not reported. Statistical "
                "analysis details are not provided. Handling of missing data "
                "is not described.\n", "strobe")
    for item in ("study-size", "statistics", "missing-data"):
        assert by[item]["status"] == "needs_check", item
        assert by[item]["not_counted"]["reason"] == "absent"
        assert by[item]["evidence"] is None
    assert c["found"] == 0


def test_databases_without_the_date_of_the_last_search_are_partial():
    by, c = _st("Methods\n\nWe searched PubMed.\n", "prisma")
    src = by["sources"]
    assert src["status"] == "partial" and c["partial"] == 1
    assert [(p["label"], p["found"]) for p in src["parts"]] == [
        ("the databases or sources", True),
        ("the date of the last search", False)]


def test_a_full_description_is_found():
    by, _ = _st("Methods\n\nWe searched PubMed, Embase and Scopus from "
                "inception to 3 March 2024.\n", "prisma")
    assert by["sources"]["status"] == "found"


def test_a_legitimate_negative_report_still_counts():
    by, _ = _st("Methods\n\nThere were no missing values for any variable.\n",
                "strobe")
    assert by["missing-data"]["status"] == "found"
    by, _ = _st("Methods\n\nNo formal sample size calculation was done; "
                "all eligible residents were included.\n", "strobe")
    assert by["study-size"]["status"] == "found"


@pytest.mark.parametrize("sentence,reason", [
    ("Previous studies imputed missing data with chained equations.",
     "prior"),
    ("Smith et al. (2019) handled missing data by multiple imputation.",
     "prior"),
    ("How missing data were handled will be reported elsewhere.", "future"),
    ("Missing data handling: TBD.", "absent"),
])
def test_prior_studies_and_promises_do_not_count(sentence, reason):
    by, _ = _st(f"Methods\n\n{sentence}\n", "strobe")
    md = by["missing-data"]
    assert md["status"] == "needs_check" and md["not_counted"]["reason"] == reason


def test_our_method_citing_a_source_still_counts():
    by, _ = _st("Methods\n\nWe handled missing data by multiple imputation, "
                "following Smith et al.\n", "strobe")
    assert by["missing-data"]["status"] == "found"


def test_a_pointer_to_a_table_is_possible_evidence():
    by, _ = _st("Results\n\nBaseline characteristics are shown in Table 1.\n",
                "strobe")
    assert by["descriptive"]["status"] == "found"


def test_an_absent_section_is_not_searched_elsewhere():
    # the Introduction describes other studies' methods; there is no Methods
    by, _ = _st("Introduction\n\nMost cohorts used regression adjusted for "
                "age.\n\nDiscussion\n\nOur estimates were robust.\n", "strobe")
    st = by["statistics"]
    assert st["status"] == "needs_check" and st["section_absent"] is True


def test_editions_and_item_numbers():
    for cid, edition in (("strobe", "STROBE (2007)"),
                         ("consort", "CONSORT 2010"),
                         ("prisma", "PRISMA 2020"),
                         ("epiforge", "EPIFORGE 2020")):
        c = check("Methods\n\nText.\n", cid)
        assert c["edition"] == edition
    by, _ = _st("Methods\n\nText.\n", "prisma")
    assert by["sources"]["refs"] == ["6"]
    by, _ = _st("Methods\n\nText.\n", "epiforge")
    assert by["funding"]["refs"] == []          # not an EPIFORGE item
    assert by["timing"]["refs"] == ["4"]
    assert "not a full compliance check" in check(
        "Methods\n\nText.\n", "strobe")["note"]

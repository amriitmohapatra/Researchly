"""Repeated unknown words (Codex review #10, 2026-10-15).

S001 used to skip any word used three or more times. Now a repeated typo is
flagged at every use (S001) and a repeated word that reads as a term gets
one grouped question (S003, a Convention) that lists every place it appears.
Synthetic sentences only.
"""

import pytest

from researchly import api, spelling
from researchly.config import Config
from researchly.engine import REGISTRY, Category
from researchly.rules_spelling import REPEAT_MIN, repeated_kind


@pytest.fixture(autouse=True)
def _no_personal_dictionary(tmp_path, monkeypatch):
    monkeypatch.setattr(spelling, "USER_DICT_FILE", tmp_path / "dict.txt")


def _cfg(**kw) -> Config:
    cfg = Config()
    cfg.disabled = {"LT001"}
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def _spelling(text, cfg=None, kind="plain"):
    a = api.analyze(text, kind=kind, cfg=cfg or _cfg(), with_metrics=False)
    return [s for s in a.suggestions if s.rule_id in ("S001", "S003")]


def _three(word):
    return (f"We measured {word} in every district. The {word} changed "
            f"little after adjustment. Estimates of {word} were stable "
            f"across analyses.")


# --- the rule's shape ----------------------------------------------------------

def test_s003_is_a_document_scope_convention_never_a_correction():
    r = REGISTRY["S003"]
    assert r.category is Category.CONVENTION
    assert r.scope == "document" and r.tier == "spelling"
    assert r.plain and "S00" not in r.plain
    assert "S003" not in api.live_rule_ids()


def test_the_websites_fallback_scope_list_knows_s003():
    # apps/web/lib/scope.ts stands in for the registry until it arrives;
    # without S003 there, the question would sit in a section's list.
    from pathlib import Path
    scope = (Path(__file__).resolve().parents[3] / "apps" / "web" / "lib"
             / "scope.ts").read_text(encoding="utf-8")
    assert '"S003"' in scope


# --- repeated typos stay visible ------------------------------------------------

@pytest.mark.parametrize("typo,fix", [
    ("recieve", "receive"), ("occured", "occurred"),
    ("seperate", "separate"), ("signficant", "significant"),
    ("paramter", "parameter"),
])
def test_a_repeated_typo_is_flagged_at_every_use(typo, fix):
    found = _spelling(_three(typo))
    flagged = [s for s in found if s.rule_id == "S001"]
    assert [s.text for s in flagged] == [typo] * 3
    assert all(s.replacement == fix for s in flagged)
    # same check, same message: the revision queue shows them as one issue
    assert len({s.message for s in flagged}) == 1
    assert not [s for s in found if s.rule_id == "S003"]


def test_a_typo_used_twice_is_flagged_twice_as_before():
    text = "We recieve data weekly. They recieve it late."
    assert [s.rule_id for s in _spelling(text)] == ["S001", "S001"]


def test_a_run_together_slip_is_a_typo():
    assert repeated_kind("inspite") == "typo"        # "in spite"


# --- repeated terms stay quiet --------------------------------------------------

@pytest.mark.parametrize("term", ["brms", "numpyro", "frobulation",
                                  "zanuvimab", "nextstrain", "seroreverters"])
def test_a_repeated_term_gets_one_question_and_no_flags(term):
    found = _spelling(_three(term))
    assert not [s for s in found if s.rule_id == "S001"]
    asked = [s for s in found if s.rule_id == "S003"]
    assert len(asked) == 1
    s = asked[0]
    assert s.category is Category.CONVENTION and s.replacement is None
    assert s.text == term                    # anchored on the first use
    assert s.message == (f"\u2018{term}\u2019 appears 3 times and isn\u2019t "
                         f"in the dictionary. If it\u2019s a term, add it to "
                         f"your dictionary; otherwise check its spelling.")


def test_a_two_word_compound_written_as_one_is_a_term():
    assert repeated_kind("linewidth") == "term"      # "line width"


def test_a_term_shaped_name_is_a_term_even_near_a_common_word():
    assert repeated_kind("dorlavir") == "term"


def test_a_run_together_after_a_content_word_is_a_term():
    # a lost hyphen at a line end ("low- and middle-income") or a field's
    # compound ("burn-in"): one question, not a correction at every use
    assert repeated_kind("lowand") == "term"
    assert repeated_kind("burnin") == "term"
    assert repeated_kind("eachother") == "typo"


def test_a_short_word_is_too_close_to_too_many_words_to_correct():
    assert repeated_kind("clin") == "term"
    # Known limit, chosen for precision: a short slip repeated ("teh") is
    # asked about rather than corrected, so it stays visible either way.
    assert repeated_kind("teh") == "term"


def test_a_name_never_written_in_lower_case_is_left_alone():
    # Opening each line, as in a table's first column: three capitalised
    # uses, each one edit from a common word ("Upon").
    text = "Udon rose in May.\nUdon fell in June.\nUdon held in July."
    assert _spelling(text) == []


def test_an_acronym_lower_cased_once_is_left_alone():
    text = ("The MWS rose. Then MWS fell. The MWS held. "
            "We plotted the mws label.")
    assert _spelling(text) == []


def test_a_term_used_twice_is_still_flagged_per_use():
    # Below REPEAT_MIN nothing is grouped: two uses are two S001 cards.
    assert REPEAT_MIN == 3
    text = "We fitted brms models. The brms fit converged."
    assert [s.rule_id for s in _spelling(text)] == ["S001", "S001"]


# --- grouping ------------------------------------------------------------------

def test_the_question_lists_every_use_in_reading_order_with_lines():
    text = ("Frobulation rose in the north.\n\nWe saw frobulation fall.\n\n"
            "The frobulation index was flat. Then frobulation rose.")
    asked = [s for s in _spelling(text) if s.rule_id == "S003"]
    assert len(asked) == 1
    occ = asked[0].occurrences
    assert [text[o["start"]:o["end"]].lower() for o in occ] == \
        ["frobulation"] * 4
    assert [o["start"] for o in occ] == sorted(o["start"] for o in occ)
    assert [o["line"] for o in occ] == [1, 3, 5, 5]
    assert asked[0].message.startswith("\u2018frobulation\u2019 appears 4 times")
    # a sentence-start capital counts but the card quotes a lower-case use
    assert asked[0].start == occ[1]["start"]


def test_two_terms_get_two_questions_and_a_typo_beside_them_is_flagged():
    text = (_three("numpyro") + " " + _three("kallisto") + " "
            + _three("recieve"))
    found = _spelling(text)
    asked = sorted(s.text for s in found if s.rule_id == "S003")
    assert asked == ["kallisto", "numpyro"]
    assert [s.text for s in found if s.rule_id == "S001"] == ["recieve"] * 3


def test_the_question_appears_in_the_to_dict_payload():
    s = [s for s in _spelling(_three("brms")) if s.rule_id == "S003"][0]
    d = s.to_dict()
    assert len(d["occurrences"]) == 3
    assert set(d["occurrences"][0]) == {"start", "end", "line", "col"}
    single = [x for x in _spelling("The recieve step.")][0].to_dict()
    assert single["occurrences"] is None


# --- the dictionary clears it everywhere ------------------------------------------

def test_adding_the_word_clears_every_use():
    text = _three("numpyro")
    assert _spelling(text)
    assert _spelling(text, _cfg(dictionary=["numpyro"])) == []
    assert spelling.add_to_user_dictionary("numpyro")
    assert _spelling(text) == []


def test_adding_a_repeated_typo_to_the_dictionary_clears_it_too():
    text = _three("recieve")
    assert _spelling(text, _cfg(dictionary=["recieve"])) == []


# --- muting, modes, masking -------------------------------------------------------

def test_muting_the_question_leaves_the_term_quiet_not_flagged():
    found = _spelling(_three("brms"), _cfg(disabled={"LT001", "S003"}))
    assert found == []


def test_muting_s001_keeps_the_question():
    found = _spelling(_three("brms"), _cfg(disabled={"LT001", "S001"}))
    assert [s.rule_id for s in found] == ["S003"]


def test_draft_mode_holds_the_question_back_and_never_flags_the_term():
    found = _spelling(_three("brms"), _cfg(mode="draft"))
    assert found == []


def test_masked_uses_are_neither_counted_nor_shown():
    # Two uses in maths and code are masked: one use in prose is left, a
    # single unknown word, so it is an ordinary S001 card.
    text = ("# Results\n\nThe $brms_{k}$ fit and `brms::brm` call. "
            "We report brms here.")
    found = _spelling(text, kind="markdown")
    assert [s.rule_id for s in found] == ["S001"]
    assert found[0].start == text.index("brms here")


def test_a_question_in_latex_points_only_at_prose():
    text = ("\\section{Methods}\nWe fitted numpyro models. The numpyro "
            "sampler ran. Then numpyro stopped. "
            "\\texttt{numpyro} and $numpyro$ are code.\n")
    asked = [s for s in _spelling(text, kind="latex") if s.rule_id == "S003"]
    assert len(asked) == 1
    for o in asked[0].occurrences:
        assert text[o["start"]:o["end"]] == "numpyro"
        assert "\\texttt{" not in text[o["start"] - 8:o["start"]]
    assert len(asked[0].occurrences) == 3


def test_the_live_check_never_groups():
    res = api.check_paragraphs(
        [{"id": "p", "text": _three("brms"), "heading": "Methods"}],
        cfg=_cfg())
    ids = [s.rule_id for s in res.paragraphs[0].suggestions]
    assert "S003" not in ids and "S001" not in ids


# --- the labelled harness ------------------------------------------------------------

def test_labelled_examples_meet_the_done_when():
    import importlib.util
    from pathlib import Path
    path = (Path(__file__).resolve().parents[3] / "ml" / "eval"
            / "spelling_repetition.py")
    spec = importlib.util.spec_from_file_location("spelling_repetition", path)
    sr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sr)
    res = sr.evaluate([w for w in sr.TYPOS if sr.unknown(w)],
                      [w for w in sr.TERMS if sr.unknown(w)])
    assert res["typo_recall"] >= 0.9           # was 0 under the exemption
    assert res["typos_silent"] == 0
    assert res["term_false_flag_rate"] <= 0.05
    assert res["terms_one_question"] >= res["terms"] - 1

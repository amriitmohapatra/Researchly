"""The corpus repair pass (extract_clean.py) on synthetic pages.

Every page here is written for this test; none comes from a thesis. The
noise-floor corpus is a measurement, so these pin what the extractor may
change: words broken at a line end or a page break, and page furniture.

Run: python3.10 -m pytest ml/dogfood/test_extract_clean.py -q
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("extract_clean",
                                               HERE / "extract_clean.py")
ec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ec)

KNOWN = frozenset("""laboratory confirmed transmission well known model
the cases were fitted to weekly counts of and we report a country each
season seroprevalence was high in every district estimated from data
community spread is slow population""".split())


# --- keep_hyphen ---------------------------------------------------------------

@pytest.mark.parametrize("head,tail,keep", [
    ("laboratory", "confirmed", True),   # two known halves: a compound
    ("well", "known", True),
    ("transmis", "sion", False),         # a word broken at a syllable
    ("coun", "try", False),
    ("sero", "prevalence", False),       # joined form is a known word
    ("COVID", "19", True),               # digit after the break
    ("non", "Asian", True),              # capital after the break
])
def test_keep_hyphen_by_dictionary(head, tail, keep):
    assert ec.keep_hyphen(head, tail, None, KNOWN) is keep


def test_the_documents_own_spelling_wins_over_the_dictionary():
    # Both halves are words, but the author writes it joined elsewhere.
    ev = ec.Evidence("We fitted a wellknown model. The wellknown form.")
    assert ec.keep_hyphen("well", "known", ev, KNOWN) is False
    # The joined form is a word, but the author hyphenates it elsewhere.
    ev = ec.Evidence("Sero-prevalence was high. Sero-prevalence rose.")
    assert ec.keep_hyphen("sero", "prevalence", ev, KNOWN) is True


def test_a_line_break_is_never_its_own_evidence():
    ev = ec.Evidence("cases were laboratory-\nconfirmed in May")
    assert ev.hyphenated("laboratory", "confirmed") == 0
    assert ev.joined("laboratory", "confirmed") == 0


# --- restore_hyphens -------------------------------------------------------------

LAYOUT = ("All cases were laboratoryconfirmed and the transmission was slow\n"
          "in every country.\n")
RAW = ("All cases were laboratory-\nconfirmed and the transmis-\n"
       "sion was slow in every coun-\ntry.\n")


def test_restore_hyphens_puts_back_a_compounds_hyphen_only():
    out = ec.restore_hyphens(LAYOUT, RAW, KNOWN)
    assert "laboratory-confirmed" in out
    assert "transmission" in out and "transmis-sion" not in out
    assert "country" in out


def test_restore_hyphens_leaves_a_word_the_document_writes_joined():
    layout = "The wellknown model. A wellknown result.\n"
    raw = "The well-\nknown model. A wellknown result.\n"
    assert ec.restore_hyphens(layout, raw, KNOWN) == layout


def test_restore_hyphens_ignores_a_suspended_hyphen():
    raw = "pre-\nand post-test counts\n"
    assert ec.line_break_pairs(raw) == {}


# --- page furniture and page joins ---------------------------------------------

def _pages(n: int, bodies: list) -> str:
    """n synthetic pages, each with a running header and a page number.
    Body lines are written longer than a heading can be (the cleaner reads
    a short capitalised line without punctuation as a heading)."""
    pages = []
    for i in range(n):
        body = bodies[i] if i < len(bodies) else ["A sentence of filler text."]
        pages.append("\n".join(["Chapter 2. Methods and data", ""] + body
                               + ["", str(i + 1)]))
    return "\f".join(pages)


def test_running_headers_and_page_numbers_are_removed():
    text = _pages(6, [])
    out = ec.clean(text, known=KNOWN)
    assert "Methods and data" not in out
    assert not any(line.strip().isdigit() for line in out.splitlines())


def test_a_header_with_a_changing_number_is_still_furniture():
    pages = ["\n".join([f"Running title page {i}", "",
                        "Weekly counts were fitted to the model again.", "",
                        str(i)]) for i in range(1, 8)]
    out = ec.clean("\f".join(pages), known=KNOWN)
    assert "Running title" not in out


def test_a_word_hyphenated_across_a_page_break_is_one_word():
    text = _pages(6, [
        ["The model was fitted to weekly counts of the cases, district by "
         "district, in each coun-"],
        ["try and we report the cases each season."],
    ])
    out = ec.clean(text, known=KNOWN)
    assert "each country and we report" in out
    assert "coun-" not in out and " try " not in out


def test_a_sentence_cut_by_a_page_break_stays_one_paragraph():
    text = _pages(6, [
        ["The model was fitted to weekly counts of the cases, season by "
         "season, in"],
        ["every district and we report the data each season."],
    ])
    paras = ec.clean(text, known=KNOWN).split("\n\n")
    assert any("season, in every district" in p for p in paras)


def test_a_page_that_ends_a_sentence_is_not_joined():
    text = _pages(6, [
        ["The model was fitted to weekly counts of the cases."],
        ["every district reported data each season to the team."],
    ])
    paras = ec.clean(text, known=KNOWN).split("\n\n")
    assert not any("cases. every" in p for p in paras)


def test_a_compound_split_across_a_page_keeps_its_hyphen():
    text = _pages(6, [
        ["The weekly counts of the cases were laboratory-"],
        ["confirmed in every district and we report the data."],
    ])
    out = ec.clean(text, known=KNOWN)
    assert "laboratory-confirmed in every district" in out


# --- the in-paragraph join keeps what the old one broke -------------------------

def test_in_paragraph_hyphens_follow_the_same_decision():
    text = ("The weekly cases were laboratory- confirmed and the transmis- "
            "sion was slow in every district, as seen in the COVID- 19 data, "
            "with pre- and post-season counts.")
    out = ec.clean(text, known=KNOWN)
    assert "laboratory-confirmed" in out
    assert "transmission" in out
    assert "COVID-19" in out
    assert "pre- and post-season" in out


def test_clean_without_raw_text_still_runs():
    assert ec.clean(_pages(6, []), known=KNOWN) == ""


def test_a_short_sections_header_between_the_halves_is_dropped():
    # "2.6 Conclusion" heads one page only, so it is not found as furniture;
    # it still cannot stand between "tran-" and "sition".
    text = _pages(6, [
        ["The weekly counts of the cases followed the epidemiological tran-"],
        ["2.6 Conclusion",
         "sition seen in every district and we report the data each season."],
    ])
    out = ec.clean(text, known=KNOWN | {"transition"})
    assert "epidemiological transition seen in every district" in out
    assert "Conclusion" not in out


def test_a_caption_between_the_halves_is_not_dropped():
    text = _pages(6, [
        ["The weekly counts of the cases were fitted to the model in"],
        ["Figure 2. Weekly counts by district.",
         "every district and we report the data each season to the team."],
    ])
    out = ec.clean(text, known=KNOWN)
    assert "Figure 2. Weekly counts by district." in out


def test_a_reference_list_runs_to_the_next_chapter_across_pages():
    # Each reference page carries the chapter's running header; the list
    # ends where the header changes (the next chapter), not after a page.
    ch2 = "Chapter 2. Weekly counts and the model"
    ch3 = "Chapter 3. Seasonal forcing in the model"
    entry = "Smith A, Jones B. A study of weekly counts in the wards, 2019."
    prose = ("The model was fitted to weekly counts of the cases in every "
             "district and we report the data each season to the team.")
    pages = [[ch2, "", prose], [ch2, "", "References", "", entry]]
    pages += [[ch2, "", entry] for _ in range(5)]
    pages += [["", prose], [ch3, "", prose], [ch3, "", prose]]
    pages += [[ch3, "", prose] for _ in range(3)]
    text = "\f".join("\n".join(p) for p in pages)
    out = ec.clean(text, known=KNOWN)
    assert "Smith" not in out
    assert out.count("The model was fitted") == 7


def test_a_singular_reference_heading_needs_a_numbered_list():
    entry = "1. Smith A. A study of weekly counts in the wards, 2019."
    prose = ("The model was fitted to weekly counts of the cases in every "
             "district and we report the data each season to the team.")
    listed = ec.clean("\n".join([prose, "", "Reference", entry]), known=KNOWN)
    assert "Smith" not in listed
    # "Reference" as a table's column heading starts nothing.
    cell = ec.clean("\n".join(["Reference", "", "(201)", "", prose]),
                    known=KNOWN)
    assert "The model was fitted" in cell


def test_a_page_number_glued_to_a_broken_word_is_removed():
    # Layout mode prints "defin-" / "103" as "defin103"; raw mode shows both.
    pages = [["The expected ratio is hard to define because of difficulties "
              "in defin103", ""],
             ["4.2 Data", "ing the ratio in every district for each season "
              "of the study period.", "", "104"]]
    raw_mode = ("The expected ratio is hard to define because of difficulties "
                "in defin-\n103\n\f4.2 Data\ning the ratio in every district\n")
    fixed = ec.unglue_page_numbers(pages, raw_mode)
    assert fixed[0][0].endswith("in defin-")
    # Without raw-mode evidence the number stays (it may be a real token).
    assert ec.unglue_page_numbers(pages, "")[0][0].endswith("defin103")
    lines = ec.join_pages(fixed, None, KNOWN | {"defining"})
    assert any("in defining the ratio in every district" in ln for ln in lines)

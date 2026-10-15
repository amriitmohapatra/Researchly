"""The repeated-word harness (Codex review #10, 2026-10-15).

Synthetic inputs only; nothing is fetched.
"""

import spelling_repetition as sr


def test_each_word_is_written_three_times_mid_sentence():
    text = sr.text_for("frobulation")
    assert text.count("frobulation") == len(sr.TEMPLATES) == 3
    assert " frobulation" in text and "Frobulation" not in text


def test_the_labelled_words_are_all_unknown_to_the_engine():
    # A labelled word the dictionaries know would measure nothing.
    assert all(sr.unknown(w) for w in sr.TYPOS)
    assert all(sr.unknown(w) for w in sr.TERMS)
    assert not set(sr.TYPOS) & set(sr.TERMS)


def test_a_repeated_typo_is_flagged_at_every_use():
    r = sr.judge("recieve")
    assert r["flags"] == 3 and r["questions"] == 0


def test_a_repeated_term_gets_one_question_covering_every_use():
    r = sr.judge("numpyro")
    assert r["flags"] == 0 and r["questions"] == 1
    assert r["question_places"] == 3


def test_the_report_counts_both_sides():
    res = sr.evaluate(["recieve", "seperate"], ["numpyro", "kallisto"])
    assert res["typo_recall"] == 1.0 and res["typos_silent"] == 0
    assert res["term_false_flag_rate"] == 0.0
    assert res["terms_one_question"] == 2
    assert res["missed_typos"] == [] and res["flagged_terms"] == []

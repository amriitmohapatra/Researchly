"""The precision report from labels (S4 exit check). Synthetic labels."""

import json

import pytest

import label_precision as lp


def labels(*rows):
    return [{"paragraph": p, "rule_id": r, "category": c,
             "section": "discussion", "verdict": v} for p, r, c, v in rows]


def test_wilson_interval_brackets_the_rate():
    lo, hi = lp.wilson(8, 10)
    assert lo < 0.8 < hi and 0 <= lo and hi <= 1
    assert lp.wilson(0, 0) == (0.0, 0.0)


def test_report_counts_and_leaves_unsure_out():
    ls = labels((1, "G106", "improvement", "useful"),
                (1, "G106", "improvement", "wrong"),
                (2, "S001", "correction", "useful"),
                (2, "S001", "correction", "useful"),
                (3, "S001", "correction", "unsure"))
    out = lp.report(ls, min_flags=2)
    assert "5 flags in 3 paragraphs" in out
    assert "| All flags | 3 | 1 | 1 | 75% |" in out
    assert "| S001 | 2 | 0 | 1 | 100% |" in out
    assert "Most false flags: G106 (1)." in out


def test_a_labels_file_with_text_is_refused(tmp_path):
    p = tmp_path / "l.json"
    p.write_text(json.dumps({"labels": [{"rule_id": "G106", "verdict":
                                         "useful", "text": "a sentence"}]}))
    with pytest.raises(ValueError):
        lp.load(p)


def test_the_web_pages_export_is_read():
    """ml/eval/fixtures/web-labels.json is what the website's Label page
    exports for a known session (apps/web/tests/unit/labels.test.ts checks
    the page produces exactly this file), so the two cannot drift apart."""
    from pathlib import Path
    ls = lp.load(Path(__file__).parent / "fixtures" / "web-labels.json")
    out = lp.report(ls, min_flags=2)
    assert "4 flags in 2 paragraphs" in out
    assert "| All flags | 2 | 1 | 1 | 67% |" in out
    assert "| C201 | 1 | 0 | 1 | 100% |" in out


def test_cli_round_trip(tmp_path, capsys):
    p = tmp_path / "l.json"
    p.write_text(json.dumps({"version": 1, "labels": labels(
        (1, "C303", "convention", "useful"))}))
    assert lp.main([str(p)]) == 0
    assert "| All flags | 1 | 0 | 0 | 100% |" in capsys.readouterr().out


# --- Codex review N3 (2026-10-14): one observation per flag -------------------

def _lab(paragraph, verdict, attempt=None, flag=None, rule="G106"):
    x = {"paragraph": paragraph, "rule_id": rule, "category": "improvement",
         "section": "results", "verdict": verdict}
    if attempt is not None:
        x["attempt"], x["flag"] = attempt, flag
    return x


def test_only_the_last_attempt_of_a_paragraph_counts():
    labels = [_lab(1, "wrong", "attemptaa1", 0),
              _lab(1, "useful", "attemptbb2", 0),      # rechecked: replaces
              _lab(2, "useful", "attemptcc3", 0)]
    kept, dropped = lp.dedupe(labels)
    assert dropped == 1 and [x["verdict"] for x in kept] == ["useful", "useful"]


def test_a_changed_verdict_counts_once_and_two_flags_count_twice():
    labels = [_lab(1, "wrong", "attemptaa1", 0),
              _lab(1, "useful", "attemptaa1", 0),
              _lab(1, "wrong", "attemptaa1", 1)]
    kept, dropped = lp.dedupe(labels)
    assert dropped == 1 and len(kept) == 2


def test_files_from_before_attempts_are_read_as_they_are():
    kept, dropped = lp.dedupe([_lab(1, "useful"), _lab(1, "useful")])
    assert dropped == 0 and len(kept) == 2


def test_a_text_attempt_id_is_refused(tmp_path):
    p = tmp_path / "l.json"
    p.write_text(json.dumps({"version": 1, "labels": [
        _lab(1, "useful", "We fitted a model", 0)]}))
    with pytest.raises(ValueError):
        lp.load(p)


def test_the_report_says_what_was_set_aside():
    out = lp.report([_lab(1, "wrong", "attemptaa1", 0),
                     _lab(1, "useful", "attemptbb2", 0)])
    assert "1 label from a replaced check or a changed verdict was set aside" in out
    assert "paragraph-clustered" in out

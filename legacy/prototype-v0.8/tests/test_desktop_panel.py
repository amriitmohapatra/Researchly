"""Tests for the desktop panel renderer (the platform-independent part of
the macOS app) driven by real engine output."""

import sys
from pathlib import Path

import spacy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop-mac"))

import panel_html  # noqa: E402
from researchly.document import Document  # noqa: E402
from researchly.engine import REGISTRY, check  # noqa: E402
from researchly import metrics as metrics_mod  # noqa: E402
from researchly.transform import polish  # noqa: E402

NLP = spacy.load("en_core_web_sm")


def _checked(text):
    doc = Document.from_text(text, "plain")
    suggestions = check(doc, NLP, show_preferences=False)
    out = []
    for s in suggestions:
        d = s.to_dict()
        d["why"] = REGISTRY[s.rule_id].why
        out.append(d)
    mets = metrics_mod.compute(NLP(doc.masked), doc)
    return out, mets


def test_render_check_contains_cards_and_whys():
    suggestions, mets = _checked(
        "We utilize household data. This proves that stratification "
        "matters for policy.")
    html = panel_html.render_check(suggestions, mets, hidden_prefs=1,
                                   source_app="Microsoft Word")
    assert "W201" in html and "grand-word" in html
    assert "utilize" in html
    assert "<details>" in html and "Why?" in html
    assert "Microsoft Word" in html
    assert "1 preference notes hidden" in html
    assert "read-out, not a score" in html


def test_render_check_empty_state():
    suggestions, mets = _checked("The model predicts higher attack rates.")
    html = panel_html.render_check(suggestions, mets)
    assert "Nothing to flag" in html


def test_render_check_escapes_html():
    fake = [{
        "rule_id": "W201", "rule_name": "grand-word",
        "category": "improvement", "message": "<script>alert(1)</script>",
        "text": "<b>utilize</b>", "section": "unknown", "replacement": None,
        "why": "x & y",
    }]
    html = panel_html.render_check(fake)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;utilize&lt;/b&gt;" in html


def test_render_polish_diff_and_ledger():
    r = polish("We utilize data in order to make an assessment of risk.",
               NLP)
    html = panel_html.render_polish(r, source_app="Overleaf")
    assert "<del>" in html and "<ins>" in html
    assert "G102" in html and "W201" in html and "W202" in html
    assert "Overleaf" in html
    assert "no AI generation" in html


def test_render_polish_unchanged_state():
    r = polish("We estimated the transmission rate for every scenario.",
               NLP)
    html = panel_html.render_polish(r)
    assert "Nothing to safely rewrite" in html


def test_render_message():
    html = panel_html.render_message("No selection", "Select some text.")
    assert "No selection" in html and "Select some text." in html

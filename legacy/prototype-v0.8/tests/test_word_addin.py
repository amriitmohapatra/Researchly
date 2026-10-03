"""Tests for the Word add-in path: from_word documents + server /check."""

import sys
from pathlib import Path

import spacy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "word-addin"))

from researchly.document import Document
from researchly.engine import check
import server as addin_server

NLP = spacy.load("en_core_web_sm")

PARAS = [
    {"text": "Methods", "style": "Heading1"},
    {"text": "Samples were incubated at 37 degrees before analysis.",
     "style": "Normal"},
    {"text": "Results", "style": "Heading 1"},
    {"text": "The pattern was first described by Anderson and May. "
             "We performed an estimation of the transmission rate.",
     "style": "Normal"},
]


def test_from_word_styles_define_sections():
    doc = Document.from_word(PARAS)
    assert [h.section for h in doc.headings] == ["methods", "results"]
    # heading text is masked
    assert "Methods" not in doc.masked and "Results" not in doc.masked
    # offsets: paragraph 3 starts after paragraphs 0-2 plus separators
    assert doc.para_offsets[1] == len("Methods") + 2
    assert doc.section_at(doc.para_offsets[1]) == "methods"
    assert doc.section_at(doc.para_offsets[3]) == "results"


def test_from_word_section_aware_rules():
    doc = Document.from_word(PARAS)
    found = [s.rule_id for s in check(doc, NLP, show_preferences=True)]
    assert "G104" in found      # agent-ful passive in Results fires
    assert "G102" in found      # buried action fires
    # the agentless passive in Methods stays quiet
    g104 = [s for s in check(doc, NLP, show_preferences=True)
            if s.rule_id == "G104"]
    assert all(s.section == "results" for s in g104)


def test_locate_maps_back_to_paragraph():
    doc = Document.from_word(PARAS)
    hits = [s for s in check(doc, NLP, show_preferences=True)
            if s.rule_id == "G102"]
    assert hits
    para, start_in = doc.locate(hits[0].start)
    assert para == 3
    para_text = PARAS[3]["text"]
    end_in = hits[0].end - doc.para_offsets[para]
    assert para_text[start_in:end_in] == "performed an estimation of"


def test_unstyled_typed_heading_still_detected():
    paras = [
        {"text": "Discussion", "style": "Normal"},   # typed, not styled
        {"text": "This proves that stratification matters.",
         "style": "Normal"},
    ]
    doc = Document.from_word(paras)
    found = [s.rule_id for s in check(doc, NLP, show_preferences=True)]
    assert "C302" in found       # overclaim fires because section=discussion


def test_server_run_check_payload():
    result = addin_server.run_check({
        "paragraphs": PARAS,
        "disabled": [],
        "show_preferences": False,
    })
    assert result["sections_detected"] == ["methods", "results"]
    g102 = [s for s in result["suggestions"] if s["rule_id"] == "G102"]
    assert g102
    s = g102[0]
    assert s["para"] == 3
    assert s["snippet"] == "performed an estimation of"
    assert s["occurrence"] == 0
    assert "why" in s and len(s["why"]) > 40
    assert "metrics" in result and result["metrics"]["sentences"] >= 2


def test_server_respects_disabled_and_occurrence():
    paras = [{"text": "We utilize diaries and we utilize surveys.",
              "style": "Normal"}]
    r1 = addin_server.run_check({"paragraphs": paras})
    w201 = [s for s in r1["suggestions"] if s["rule_id"] == "W201"]
    assert len(w201) == 2
    assert w201[0]["occurrence"] == 0 and w201[1]["occurrence"] == 1
    r2 = addin_server.run_check({"paragraphs": paras, "disabled": ["W201"]})
    assert not [s for s in r2["suggestions"] if s["rule_id"] == "W201"]

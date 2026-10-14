"""Guards for the 2026-10-14 performance pass. Each speed-up there was
chosen because it cannot change what the writer sees; these tests keep it
that way.

- The shared spaCy pipeline leaves out the entity recogniser (about 45% of
  a parse), which is only safe while nothing reads entities.
- LT001's LanguageTool request runs beside the spaCy parse, and the rule
  gives exactly what a synchronous request gives, failures included.
- The language and PDF-layout finders exit early only when the answer is
  already decided.

Synthetic sentences only (CLAUDE.md).
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

import pytest

from researchly import api, rules_grammar
from researchly.config import Config
from researchly.document import Document, layout_spans
from researchly.engine import check
from researchly.reading import paragraph_language

PKG = Path(api.__file__).resolve().parent
TEXT = ("Methods\n\nThe models was fitted to weekly counts of cases. "
        "We report the posterior median for each district.\n")


# --- the parser --------------------------------------------------------------

def test_the_entity_recogniser_is_left_out_and_nothing_reads_entities():
    assert "ner" in api.NOT_USED_PIPES
    assert "ner" not in api.get_nlp().pipe_names
    readers = re.compile(r"\.ents\b|\.ent_(?:type|iob|kb_id|id)_?\b")
    hits = [f"{p.relative_to(PKG)}:{i}"
            for p in PKG.rglob("*.py")
            for i, line in enumerate(p.read_text().splitlines(), 1)
            if readers.search(line.split("#")[0])]
    assert hits == [], ("these read named entities, which the shared "
                        "pipeline no longer produces; take 'ner' out of "
                        f"api.NOT_USED_PIPES: {hits}")


# --- the grammar tier beside the parse ---------------------------------------------

class _Match:
    def __init__(self, offset, length, message="Agreement.", rule="AGR"):
        self.offset, self.error_length = offset, length
        self.message, self.rule_id = message, rule
        self.rule_issue_type = "grammar"
        self.replacements = ["model was"]


class _FakeTool:
    def __init__(self, started=None, fail=False):
        self.started = started or threading.Event()
        self.fail = fail
        self.threads = []

    def check(self, text):
        self.threads.append(threading.current_thread().name)
        self.started.set()
        if self.fail:
            raise RuntimeError("server said: " + text[:40])
        i = text.index("models was")
        return [_Match(i, len("models was"))]


@pytest.fixture
def fake_lt(monkeypatch):
    saved = rules_grammar._STATE, rules_grammar._DETAIL
    tool = _FakeTool()
    monkeypatch.setattr(rules_grammar, "get_tool", lambda locale="en-US": tool)
    yield tool
    rules_grammar._STATE, rules_grammar._DETAIL = saved


class _ParserThatWaits:
    """The real parser, which first waits (up to 10 s) for the grammar
    request to have started: it can only start during the parse if it
    runs beside it."""

    def __init__(self, started):
        self.real, self.started, self.overlapped = api.get_nlp(), started, None

    def __call__(self, text):
        self.overlapped = self.started.wait(10)
        return self.real(text)

    def __getattr__(self, name):
        return getattr(self.real, name)


def _lt(suggestions):
    return [s.to_dict() for s in suggestions if s.rule_id == "LT001"]


def test_the_grammar_request_runs_while_spacy_parses(fake_lt):
    nlp = _ParserThatWaits(fake_lt.started)
    a = api.analyze(TEXT, nlp=nlp, cfg=Config())
    assert nlp.overlapped is True
    assert fake_lt.threads == ["researchly-lt001"]
    assert len(_lt(a.suggestions)) == 1
    assert a.document._lt_pending is None        # not kept past the rule


def test_overlapped_findings_equal_a_synchronous_check(fake_lt):
    a = api.analyze(TEXT, cfg=Config())
    doc = Document.from_text(TEXT)
    doc.config = Config()
    doc.default_section = a.profile.body_section
    plain = check(doc, api.get_nlp(), show_preferences=True)
    assert _lt(a.suggestions) == _lt(plain)
    assert fake_lt.threads[-1] == threading.current_thread().name


def test_a_failed_overlapped_request_is_reported_by_type_only(fake_lt):
    fake_lt.fail = True
    a = api.analyze(TEXT, cfg=Config())
    assert _lt(a.suggestions) == []
    assert rules_grammar.state() == ("error",
                                     "LanguageTool check failed (RuntimeError)")


def test_no_request_when_the_rule_is_off(fake_lt):
    api.analyze(TEXT, cfg=Config(disabled=["LT001"]))
    assert fake_lt.threads == []


def test_a_request_for_other_text_is_never_used(fake_lt):
    doc = Document.from_text(TEXT)
    doc.config = Config()
    doc._lt_pending = ("other text", doc.config, None)   # never .result()
    found = list(rules_grammar.lt001_grammar(None, doc))
    assert len(found) == 1
    assert fake_lt.threads == [threading.current_thread().name]


# --- early exits that cannot change an answer -----------------------------------

def test_layout_line_where_the_maths_catches_up_at_the_end():
    # Four words first, then just enough maths ("=" is maths) to tie: the
    # early exit must not have given up on this line before its end.
    tie = "alpha beta gamma delta = x y z\n"
    short = "alpha beta gamma delta = x y\n"
    assert layout_spans(tie) == [(0, len(tie) - 1)]
    assert layout_spans(short) == []


def test_english_heavy_paragraphs_are_english_without_scoring_others():
    english = ("the model of the data and the fit of the model was in the "
               "range that the study set for the region")
    assert paragraph_language(english) is None
    spanish = ("el modelo de los datos y la serie de casos que se usa para "
               "el ajuste de la tasa en los distritos de la región")
    assert paragraph_language(spanish) == "Spanish"
    greek = "Το μοντέλο προσαρμόστηκε στα εβδομαδιαία κρούσματα της περιοχής " * 2
    assert paragraph_language(greek) == "another script"

"""Large documents are parsed in pieces (2026-10-15, PLAN "Large .tex").

One spaCy call over a whole thesis held the network's working arrays for
every token at once: 2.49 GB at peak for a 120,000-word synthetic LaTeX
thesis, 1.02 GB in five pieces, with identical findings, metrics, brief and
map. These tests pin the contract:

- a document within `api.PARSE_PIECE_CHARS` is parsed in one call, exactly
  as before;
- a longer one is cut only where a paragraph starts a sentence anyway, the
  pieces tile the text, and the joined parse keeps every token, offset and
  sentence;
- the findings of a split check equal the unsplit check's, sentence- and
  document-scope alike (synthetic text, the limit lowered to force cuts).

Synthetic sentences only (CLAUDE.md).
"""

from __future__ import annotations

import random

import pytest

from researchly import api
from researchly.document import Document

NLP = api.get_nlp()

SENTENCES = [
    "The model was fitted to weekly counts of cases in every district.",
    "Transmission rose during the wet season and fell after it.",
    "We report the posterior median and a credible interval for each ward.",
    "However, little is known about how reporting delays bias the estimate.",
    "In order to account for the fact that testing changed, we adjusted it.",
    "It should be noted that the the data were incomplete in May.",
    "Vaccine coverage varied across the urban and rural districts.",
    "the serial interval was estimated from household pairs",
]
HEADINGS = ["Introduction", "Methods", "Results", "Discussion"]


def _thesis(chapters: int = 4, paras: int = 12, seed: int = 5) -> str:
    rng = random.Random(seed)
    out = ["\\documentclass{report}\n\\begin{document}\n"]
    for c in range(chapters):
        out.append(f"\\chapter{{Chapter title {c + 1}}}\n")
        for h in HEADINGS:
            out.append(f"\\section{{{h}}}\n")
            for _ in range(paras // len(HEADINGS) + 1):
                out.append(" ".join(rng.choice(SENTENCES)
                                    for _ in range(rng.randint(3, 7))))
                out.append("\n\n")
    out.append("\\end{document}\n")
    return "".join(out)


def _findings(a):
    return sorted((s.start, s.end, s.rule_id, s.message)
                  for s in a.suggestions)


@pytest.fixture
def small_pieces(monkeypatch):
    monkeypatch.setattr(api, "PARSE_PIECE_CHARS", 2_000)


# --- where the text is cut -------------------------------------------------------

def test_a_document_within_the_limit_is_one_piece():
    text = "Methods\n\nThe model was fitted.\n\nIt was checked.\n"
    assert api.parse_pieces(text) == [(0, len(text))]


def test_pieces_tile_the_text_and_start_sentences(small_pieces):
    masked = Document.from_text(_thesis(), "latex").masked
    pieces = api.parse_pieces(masked)
    assert len(pieces) > 3
    assert pieces[0][0] == 0 and pieces[-1][1] == len(masked)
    for (a, b), (c, _) in zip(pieces, pieces[1:]):
        assert b == c                                  # no gap, no overlap
        assert masked[c - 2:c].strip() == ""           # after a blank line
        assert masked[c - 2:c].count("\n") >= 1
        assert not masked[c].isspace() and not masked[c].islower()
    assert all(b - a <= 2_000 for a, b in pieces[:-1])


def test_a_lower_case_continuation_is_never_a_cut(monkeypatch):
    monkeypatch.setattr(api, "PARSE_PIECE_CHARS", 60)
    text = ("A first paragraph of some words here.\n\n"
            "continues in lower case after a page break.\n\n"
            "A new paragraph starts here with a capital.\n")
    cuts = [a for a, _ in api.parse_pieces(text)][1:]
    assert text.index("continues") not in cuts
    assert text.index("A new paragraph") in cuts


def test_a_paragraph_longer_than_the_limit_runs_on(monkeypatch):
    monkeypatch.setattr(api, "PARSE_PIECE_CHARS", 50)
    text = ("One very long paragraph " * 10 + "\n\nNext one.\n\n"
            + "Then another.\n")
    pieces = api.parse_pieces(text)
    assert pieces[0] == (0, text.index("Next one."))
    assert pieces[-1][1] == len(text)


# --- the joined parse ---------------------------------------------------------------

def test_within_the_limit_the_parse_is_the_one_call_parse():
    masked = Document.from_text(_thesis(chapters=1), "latex").masked
    assert len(masked) < api.PARSE_PIECE_CHARS
    one, ours = NLP(masked), api.parse(masked, NLP)
    assert [(t.idx, t.text, t.tag_, t.dep_, t.head.i, t.is_sent_start)
            for t in one] == \
        [(t.idx, t.text, t.tag_, t.dep_, t.head.i, t.is_sent_start)
         for t in ours]


def test_the_joined_parse_keeps_text_offsets_and_sentences(small_pieces):
    masked = Document.from_text(_thesis(), "latex").masked
    whole, joined = NLP(masked), api.parse(masked, NLP)
    assert joined.text == masked
    assert [(t.idx, t.text) for t in joined] == [(t.idx, t.text) for t in whole]
    assert [(s.start_char, s.end_char) for s in joined.sents] == \
        [(s.start_char, s.end_char) for s in whole.sents]


# --- the findings -------------------------------------------------------------------------

def test_a_split_check_finds_what_the_unsplit_check_finds(monkeypatch):
    text = _thesis(chapters=4, paras=16)
    kw = dict(kind="latex", nlp=NLP, show_preferences=True,
              with_review=True, with_narrative=True, grammar_tier=False)
    whole = api.analyze(text, **kw)
    monkeypatch.setattr(api, "PARSE_PIECE_CHARS", 2_000)
    assert len(api.parse_pieces(whole.document.masked)) > 3
    split = api.analyze(text, **kw)
    assert _findings(split) == _findings(whole)
    scopes = {s.rule_id for s in whole.suggestions}
    assert {"W207", "W202"} <= scopes          # sentence scope is exercised
    assert split.metrics.to_dict() == whole.metrics.to_dict()
    assert split.review == whole.review
    assert split.narrative == whole.narrative

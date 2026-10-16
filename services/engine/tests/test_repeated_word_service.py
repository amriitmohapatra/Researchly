"""A word used three or more times that no dictionary knows (Codex review
#10): one grouped question (S003) carrying every place it appears, on
/v1/analyze, /v1/analyze-word and the local Word server. A repeated typo is
flagged at every use. Synthetic text only."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from researchly import spelling
from researchly_service.schemas import AnalyzeResponse, AnalyzeWordResponse

ROOT = Path(__file__).resolve().parents[3]

# An astral character before the term, so UTF-16 and code points differ.
TEXT = ("\U0001D6FD We fitted numpyro models. The numpyro sampler ran "
        "quickly. Then numpyro stopped. We recieve data. They recieve "
        "more. You recieve some.")


@pytest.fixture(autouse=True)
def _no_personal_dictionary(tmp_path, monkeypatch):
    monkeypatch.setattr(spelling, "USER_DICT_FILE", tmp_path / "d.txt")


def _ours(body):
    return [s for s in body["suggestions"] if s["rule_id"] in ("S001", "S003")]


def test_analyze_groups_a_term_and_flags_a_repeated_typo(client):
    r = client.post("/v1/analyze", json={"content": TEXT, "format": "plain"})
    assert r.status_code == 200, r.text
    body = r.json()
    AnalyzeResponse.model_validate(body)
    found = _ours(body)
    (q,) = [s for s in found if s["rule_id"] == "S003"]
    assert q["category"] == "convention" and q["critical"] is False
    assert q["replacement"] is None
    assert q["message"].startswith("‘numpyro’ appears 3 times")
    occ = q["occurrences"]
    assert [TEXT[o["start"]:o["end"]] for o in occ] == ["numpyro"] * 3
    assert (q["span"]["start"], q["span"]["end"]) == \
        (occ[0]["start"], occ[0]["end"])
    # UTF-16 offsets count the astral character twice
    assert all(o["begin16"] == o["start"] + 1 for o in occ)
    assert all(o["end16"] == o["end"] + 1 for o in occ)
    assert [s["text"] for s in found if s["rule_id"] == "S001"] == \
        ["recieve"] * 3
    single = [s for s in found if s["rule_id"] == "S001"][0]
    assert single.get("occurrences") is None


def test_muting_s001_keeps_the_question_and_drops_the_typo_cards(client):
    r = client.post("/v1/analyze", json={
        "content": TEXT, "format": "plain",
        "options": {"disabled_rules": ["S001"]}})
    assert [s["rule_id"] for s in _ours(r.json())] == ["S003"]


PARAS = [{"text": "Methods", "style": "Heading 1"},
         {"text": "We fitted numpyro models. The numpyro sampler ran."},
         {"text": "Results", "style": "Heading 1"},
         {"text": "Then numpyro stopped early."}]


def _word_question(body):
    (q,) = [s for s in body["suggestions"] if s["rule_id"] == "S003"]
    return q


def test_analyze_word_gives_a_word_location_for_every_use(client):
    r = client.post("/v1/analyze-word", json={"paragraphs": PARAS})
    assert r.status_code == 200, r.text
    body = r.json()
    AnalyzeWordResponse.model_validate(body)
    q = _word_question(body)
    locs = q["occurrence_locations"]
    assert len(locs) == len(q["occurrences"]) == 3
    assert [(x["paragraph"], x["occurrence"]) for x in locs] == \
        [(1, 0), (1, 1), (3, 0)]
    assert all(x["snippet"] == "numpyro" and x["exact"] for x in locs)
    assert locs[0] == q["location"]


@pytest.fixture(scope="module")
def server():
    path = ROOT / "apps" / "word-addin" / "server.py"
    spec = importlib.util.spec_from_file_location("local_word_server_s003",
                                                  path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["local_word_server_s003"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_local_word_server_answers_the_same_shape(server):
    body = server.analyze_word({"paragraphs": PARAS})
    raw = json.loads(json.dumps(body))
    AnalyzeWordResponse.model_validate(raw)
    q = _word_question(raw)
    assert [(x["paragraph"], x["occurrence"])
            for x in q["occurrence_locations"]] == [(1, 0), (1, 1), (3, 0)]

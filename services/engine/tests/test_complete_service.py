"""POST /v1/complete: word prediction through the hosted engine
(2026-10-14). Synthetic text only."""

from __future__ import annotations

import pytest

from researchly import predict
from researchly_service.schemas import CompleteResponse

needs_model = pytest.mark.skipif(not predict.available(),
                                 reason="no shipped prediction model")


def post(client, **body):
    return client.post("/v1/complete", json=body)


@needs_model
def test_completes_a_word(client):
    text = "We report the 95% confidence int"
    r = post(client, text=text)
    assert r.status_code == 200
    body = CompleteResponse.model_validate(r.json())
    assert body.status == "ok" and body.candidates
    c = body.candidates[0]
    assert c.end == len(text) and text[c.start:c.end] == "int"
    assert c.text.lower().startswith("interval")


def test_masked_cursor_gets_nothing(client):
    r = post(client, text="As shown by \\cite{smi", format="latex")
    assert r.status_code == 200
    assert r.json() == {"candidates": [], "status": "masked"}


def test_cursor_inside_the_text(client):
    text = "the basic rep and more"
    r = post(client, text=text, cursor=13)
    assert r.status_code == 200
    for c in r.json()["candidates"]:
        assert c["end"] == 13


def test_the_limit_is_respected(client):
    r = post(client, text="we estimated the ", options={"limit": 1})
    assert r.status_code == 200
    assert len(r.json()["candidates"]) <= 1


def test_cursor_past_the_end_is_refused(client):
    assert post(client, text="abc", cursor=10).status_code == 422


def test_never_more_than_three_words(client):
    for text in ("the basic ", "in this ", "we used a "):
        for c in post(client, text=text).json()["candidates"]:
            assert len(c["text"].split()) <= 3


def test_prediction_has_its_own_rate_budget():
    from researchly_service.middleware import RateLimiter
    from researchly_service.settings import Settings
    assert Settings().complete_rate_limit_per_min > Settings().rate_limit_per_min
    lim = RateLimiter(2)
    assert lim.check("ip", 0.0) is None and lim.check("ip", 0.1) is None
    assert lim.check("ip", 0.2) is not None

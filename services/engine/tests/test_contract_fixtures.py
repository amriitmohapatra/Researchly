"""The live check's shared fixtures stay true (S4d R7/R8).

The macOS and Windows overlay clients decode
packages/contract/fixtures/check-paragraphs/*.json in their own tests. Here
every exchange is made again against the real service and compared, so a
change to the contract or to what the engine says shows up as a stale
fixture, never as a client that silently disagrees with the engine.
Regenerate with `python tests/contract_fixtures.py` from services/engine.
"""

from __future__ import annotations

import json

import pytest

from researchly_service.schemas import (CheckParagraphsRequest,
                                        CheckParagraphsResponse,
                                        ErrorResponse)

import contract_fixtures as cf

STALE = ("{} is stale: run `python tests/contract_fixtures.py` from "
         "services/engine and review the diff")


def load(name: str) -> dict:
    return json.loads(cf.path_for(name).read_text(encoding="utf-8"))


def test_the_fixture_folder_holds_exactly_the_scenarios():
    on_disk = sorted(p.stem for p in cf.FIXTURES.glob("*.json"))
    assert on_disk == sorted(cf.SCENARIOS)


@pytest.mark.parametrize("name", sorted(cf.SCENARIOS))
def test_each_fixture_is_what_the_service_answers(make_client, name):
    get = cf.cached(make_client)
    fresh = cf.exchange(name, get)
    on_disk = load(name)
    assert cf.comparable(on_disk) == cf.comparable(fresh), \
        STALE.format(cf.path_for(name).name)
    # Written as the generator writes it (no hand edits, no reformatting).
    assert cf.path_for(name).read_text(encoding="utf-8") == cf.dump(on_disk)


@pytest.mark.parametrize("name", sorted(cf.SCENARIOS))
def test_each_fixture_validates_against_the_contract(name):
    fx = load(name)
    assert set(fx) == {"about", "request", "status", "headers", "response"}
    if fx["status"] == 200:
        CheckParagraphsRequest.model_validate(fx["request"])
        body = CheckParagraphsResponse.model_validate(fx["response"])
        assert body.revision == fx["request"]["revision"]
        assert [p.id for p in body.paragraphs] == \
            [p["id"] for p in fx["request"]["paragraphs"]]
    else:
        ErrorResponse.model_validate(fx["response"])


def test_the_fixtures_cover_what_the_clients_must_handle():
    ok, clear, partial = load("ok"), load("clear"), load("partial")
    # Astral characters before a suggestion: UTF-16 offsets, and `text`
    # is exactly the flagged words at begin…end.
    p1 = ok["request"]["paragraphs"][0]["text"]
    assert any(ord(c) > 0xFFFF for c in p1)
    sugs = ok["response"]["paragraphs"][0]["suggestions"]
    assert sugs
    units = p1.encode("utf-16-le")
    for s in sugs:
        assert units[2 * s["begin"]:2 * s["end"]].decode("utf-16-le") == s["text"]
    # ...and they differ from Python's code-point offsets after the emoji.
    assert all(s["begin"] != p1.index(s["text"]) for s in sugs)
    # Section awareness: the same sentence, flagged in Discussion only.
    by_id = {p["id"]: p for p in ok["response"]["paragraphs"]}
    assert by_id["p2"]["section"] == "methods" and not by_id["p2"]["suggestions"]
    assert by_id["p3"]["section"] == "discussion" and by_id["p3"]["suggestions"]
    # A paragraph with nothing to suggest, and a reply with none at all.
    assert by_id["p4"]["suggestions"] == []
    assert clear["response"]["paragraphs"][0]["suggestions"] == []
    # A tier switched off (disabled) or without a model (missing) is not an
    # outage; a tier that failed is.
    tiers = {t["tier"]: t for t in ok["response"]["health"]}
    assert tiers["grammar"]["state"] == "disabled" and not tiers["grammar"]["ok"]
    assert ok["response"]["state"] == clear["response"]["state"] == "ok"
    down = [t for t in partial["response"]["health"] if t["tier"] == "grammar"]
    assert down[0]["ok"] is False and down[0]["state"] == "error"
    assert partial["response"]["state"] == "partial"
    assert partial["response"]["paragraphs"][0]["suggestions"]
    # Refusals a client must not retry blindly.
    assert load("invalid-422")["status"] == 422
    assert load("invalid-422")["response"]["error"]["code"] == "invalid_request"
    limited = load("rate-limited-429")
    assert limited["status"] == 429 and int(limited["headers"]["retry-after"]) >= 1
    assert limited["response"]["error"]["code"] == "rate_limited"

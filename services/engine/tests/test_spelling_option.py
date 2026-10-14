"""The `spelling` option (2026-10-14): British, American or auto.
Synthetic text only."""

from __future__ import annotations

from researchly.config import SPELLINGS
from researchly_service.schemas import AnalyzeResponse, Spelling

TEXT = ("We analysed the colour of the samples. The color scale and the "
        "behaviour data were checked.\n")


def post(client, **options):
    return client.post("/v1/analyze",
                       json={"format": "plain", "content": TEXT,
                             "options": options})


def test_the_contract_lists_every_engine_spelling():
    assert tuple(s.value for s in Spelling) == SPELLINGS


def test_a_chosen_spelling_reaches_the_engine(client):
    body = AnalyzeResponse.model_validate(post(client, spelling="us").json())
    got = {(s.rule_id, s.text) for s in body.suggestions
           if s.rule_id in ("W210", "W213")}
    assert ("W213", "colour") in got and ("W213", "behaviour") in got
    assert not any(r == "W210" for r, _ in got)


def test_auto_flags_only_the_mixture(client):
    body = AnalyzeResponse.model_validate(post(client).json())
    assert not any(s.rule_id == "W213" for s in body.suggestions)
    assert any(s.rule_id == "W210" for s in body.suggestions)


def test_an_unknown_spelling_is_refused(client):
    assert post(client, spelling="klingon").status_code == 422

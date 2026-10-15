"""POST /v1/check-paragraphs: the live check (S4d R3).

The contract: paragraphs with a revision and their nearest heading in;
per paragraph, sentence-level suggestions with UTF-16 offsets, opaque
stable ids and `critical` out; `state` ok or partial; its own rate limit;
native clients (no Origin header) accepted; account settings applied as
for /v1/analyze. Privacy is covered with the other routes in
test_privacy_canary.py.

Synthetic text only (CLAUDE.md).
"""

from __future__ import annotations

import re
import statistics
import time
from pathlib import Path

import pytest

from researchly import api, rules_grammar, shapes
from researchly_service import engine_adapter
from researchly_service.schemas import (MAX_LIVE_CHARS,
                                        MAX_LIVE_HEADING_CHARS,
                                        MAX_LIVE_PARAGRAPHS,
                                        PARAGRAPH_ID_PATTERN,
                                        CheckParagraphsResponse)

from conftest import PASSIVE

ROUTE = "/v1/check-paragraphs"
APP_ORIGIN = "https://researchly.example"
SLIPS = ("The data was recieved from each district, and in order to estimate "
         "the the reproduction number the models was fitted weekly.")


def live(client, paragraphs, revision=1, headers=None, **options):
    body = {"revision": revision, "paragraphs": paragraphs}
    if options:
        body["options"] = options
    return client.post(ROUTE, json=body, headers=headers or {})


def ids(resp, i=0):
    return {s["rule_id"] for s in resp.json()["paragraphs"][i]["suggestions"]}


# --- the happy path ------------------------------------------------------------

def test_shape_revision_and_order(client):
    r = live(client, [{"id": "b", "text": SLIPS, "heading": "Results"},
                      {"id": "a", "text": PASSIVE}], revision=42)
    assert r.status_code == 200, r.text
    body = r.json()
    CheckParagraphsResponse.model_validate(body)
    assert body["revision"] == 42
    assert [p["id"] for p in body["paragraphs"]] == ["b", "a"]
    assert body["paragraphs"][0]["section"] == "results"
    assert body["state"] in ("ok", "partial")
    assert body["health"] and body["elapsed_ms"] >= 0
    sug = body["paragraphs"][0]["suggestions"]
    assert sug
    keys = set(sug[0])
    assert {"id", "begin", "end", "category", "critical", "message", "plain",
            "why", "source", "replacements", "section", "fix_safety",
            "rule_id"} <= keys
    assert "span" not in keys and "start" not in keys


def test_section_awareness_from_the_heading(client):
    methods = live(client, [{"id": "p", "text": PASSIVE, "heading": "Methods"}])
    discussion = live(client, [{"id": "p", "text": PASSIVE,
                                "heading": "Discussion"}])
    assert "G104" not in ids(methods)        # never passive voice in Methods
    assert "G104" in ids(discussion)


def test_same_as_the_engine_and_the_core_shapes(client):
    paragraphs = [{"id": "x1", "text": SLIPS, "heading": "Methods",
                   "style": "Normal"}]
    r = live(client, paragraphs)
    cfg = engine_adapter.build_config(None)
    expected = shapes.live_paragraphs(api.check_paragraphs(paragraphs, cfg=cfg))
    assert r.json()["paragraphs"] == expected


def test_utf16_offsets_ids_and_critical(client):
    text = ("\U0001F600 \U0001D445 The data was recieved, and the the "
            "café results is clear.")
    r = live(client, [{"id": "emoji.1", "text": text}])
    units = text.encode("utf-16-le")
    sugs = r.json()["paragraphs"][0]["suggestions"]
    assert sugs
    for s in sugs:
        assert units[2 * s["begin"]:2 * s["end"]].decode("utf-16-le") == s["text"]
        assert s["critical"] is (s["category"] == "correction")
        assert len(s["id"]) == 16 and s["text"] not in s["id"]
    again = live(client, [{"id": "emoji.1", "text": text}], revision=2)
    assert [s["id"] for s in sugs] == \
        [s["id"] for s in again.json()["paragraphs"][0]["suggestions"]]


def test_options_apply(client):
    pref = "The effect was very large in every district."
    hidden = live(client, [{"id": "p", "text": pref, "heading": "Results"}])
    shown = live(client, [{"id": "p", "text": pref, "heading": "Results"}],
                 show_preferences=True)
    prefs = [s for s in shown.json()["paragraphs"][0]["suggestions"]
             if s["category"] == "preference"]
    assert prefs and hidden.json()["hidden_preferences"] == len(prefs)
    muted = live(client, [{"id": "p", "text": SLIPS}],
                 disabled_rules=["W207"])
    assert "W207" in ids(live(client, [{"id": "p", "text": SLIPS}]))
    assert "W207" not in ids(muted)


def test_document_rules_do_not_run(client):
    r = live(client, [{"id": "p", "text": "We fitted an SEIR model (Figure 2) "
                       "and an SEIR model (Figure 1).", "heading": "Results"}])
    live_rules = api.live_rule_ids()
    assert ids(r) <= live_rules
    assert set(r.json()["assessed_rules"]) <= live_rules


def test_state_partial_when_the_grammar_tier_fails(client, monkeypatch):
    class Failing:
        def check(self, text):
            raise RuntimeError("down")

        def close(self):
            pass

    monkeypatch.delenv(rules_grammar.REMOTE_ENV, raising=False)
    for k, v in (("_TOOL", Failing()), ("_LOCALE", "en-US"), ("_URL", None),
                 ("_FAILED", False), ("_STATE", "ready"), ("_DETAIL", "")):
        monkeypatch.setattr(rules_grammar, k, v)
    r = live(client, [{"id": "p", "text": SLIPS}])
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "partial"
    (grammar,) = [t for t in body["health"] if t["tier"] == "grammar"]
    assert grammar["ok"] is False


def test_state_ok_when_every_tier_runs(make_client):
    c = make_client(grammar_enabled=False)       # off by the operator: not degraded
    r = live(c, [{"id": "p", "text": SLIPS}])
    assert r.json()["state"] == "ok"


# --- validation -------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    {"revision": 1, "paragraphs": []},
    {"revision": -1, "paragraphs": [{"id": "a", "text": "x"}]},
    {"revision": "1", "paragraphs": [{"id": "a", "text": "x"}]},
    {"revision": 1.5, "paragraphs": [{"id": "a", "text": "x"}]},
    {"revision": 2 ** 53, "paragraphs": [{"id": "a", "text": "x"}]},
    {"paragraphs": [{"id": "a", "text": "x"}]},
    {"revision": 1, "paragraphs": [{"id": "", "text": "x"}]},
    {"revision": 1, "paragraphs": [{"id": "a b", "text": "x"}]},
    {"revision": 1, "paragraphs": [{"id": "a/b", "text": "x"}]},
    {"revision": 1, "paragraphs": [{"id": "x" * 65, "text": "x"}]},
    {"revision": 1, "paragraphs": [{"id": "a"}]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x", "kind": "table"}]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x"},
                                   {"id": "a", "text": "y"}]},
    {"revision": 1, "paragraphs": [{"id": f"p{i}", "text": "x"}
                                   for i in range(MAX_LIVE_PARAGRAPHS + 1)]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x" * (MAX_LIVE_CHARS + 1)}]},
    {"revision": 1, "paragraphs": [{"id": f"p{i}", "text": "x" * (MAX_LIVE_CHARS // 2)}
                                   for i in range(3)]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x", "heading": "h" * 301}]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x"}], "extra": 1},
])
def test_invalid_requests_are_422(client, body):
    r = client.post(ROUTE, json=body)
    assert r.status_code == 422, body
    assert r.json()["error"]["code"] == "invalid_request"


def test_the_limits_themselves_are_accepted(client):
    paras = [{"id": f"p.{i}:x-y_z", "text": "Fine." if i else ""}
             for i in range(MAX_LIVE_PARAGRAPHS)]
    assert live(client, paras, revision=2 ** 53 - 1).status_code == 200
    one = [{"id": "a" * 64, "text": "x " * (MAX_LIVE_CHARS // 2)}]
    assert live(client, one, revision=0).status_code == 200


# --- native clients, CORS and the rate limit -----------------------------------------

def test_native_clients_without_an_origin_are_accepted(make_client):
    c = make_client(allowed_origins=[APP_ORIGIN])
    r = live(c, [{"id": "p", "text": SLIPS}])
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_browsers_follow_cors_as_on_every_route(make_client):
    c = make_client(allowed_origins=[APP_ORIGIN])
    ok = live(c, [{"id": "p", "text": "Fine."}], headers={"origin": APP_ORIGIN})
    assert ok.headers["access-control-allow-origin"] == APP_ORIGIN
    pre = c.options(ROUTE, headers={
        "origin": APP_ORIGIN, "access-control-request-method": "POST",
        "access-control-request-headers": "content-type,authorization"})
    assert pre.status_code == 200
    evil = c.options(ROUTE, headers={
        "origin": "https://evil.example", "access-control-request-method": "POST",
        "access-control-request-headers": "content-type"})
    assert evil.status_code == 400
    assert "access-control-allow-origin" not in evil.headers
    r = live(c, [{"id": "p", "text": "Fine."}],
             headers={"origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_its_own_rate_limit(make_client):
    c = make_client(rate_limit_per_min=1, live_rate_limit_per_min=3)
    for _ in range(3):
        assert live(c, [{"id": "p", "text": "Fine."}]).status_code == 200
    r = live(c, [{"id": "p", "text": "Fine."}])
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    # Typing did not use up the full check's budget, nor the other way round.
    assert c.post("/v1/analyze", json={"content": "Fine."}).status_code == 200
    assert c.post("/v1/analyze", json={"content": "Fine."}).status_code == 429


def test_live_limit_from_the_environment(monkeypatch):
    from researchly_service import settings as settings_mod
    monkeypatch.delenv("RESEARCHLY_LIVE_RATE_LIMIT_PER_MIN", raising=False)
    assert settings_mod.load().live_rate_limit_per_min == 120
    monkeypatch.setenv("RESEARCHLY_LIVE_RATE_LIMIT_PER_MIN", "45")
    assert settings_mod.load().live_rate_limit_per_min == 45


# --- accounts -----------------------------------------------------------------------

def test_account_settings_apply(make_client):
    from test_accounts import (PUBLISHABLE, URL, FakeSupabase, InMemoryJWKS,
                               token)
    from researchly_service import accounts
    c = make_client(supabase_url=URL, supabase_publishable_key=PUBLISHABLE,
                    anon_max_words=10)
    fake = FakeSupabase({"disabled_rules": ["W207"], "show_preferences": True})
    c.app.state.accounts = accounts.Accounts(
        URL, PUBLISHABLE, jwks_client=InMemoryJWKS(), fetch=fake)
    auth = {"authorization": f"Bearer {token()}"}
    r = live(c, [{"id": "p", "text": SLIPS}], headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["signed_in"] is True and fake.calls
    assert "W207" not in ids(r)
    assert any(t["tier"] == "account" and t["ok"] for t in body["health"])
    # Anonymous callers meet the same word cap as a paste.
    anon = live(c, [{"id": "p", "text": "word " * 11}])
    assert anon.status_code == 401
    assert anon.json()["error"]["code"] == "sign_in_required"
    bad = live(c, [{"id": "p", "text": SLIPS}],
               headers={"authorization": "Bearer nonsense"})
    assert bad.status_code == 401


# --- the latency budget over HTTP ----------------------------------------------------

def test_latency_budget_over_http(client):
    """p50 < 300 ms, p95 < 800 ms for a ~200-word paragraph on a warm
    engine, through the whole service (validation, lock, shaping)."""
    para = " ".join([SLIPS, PASSIVE] * 6 + ["The effect was very large."] * 2)
    assert 180 <= len(para.split()) <= 230
    body = [{"id": "p", "text": para, "heading": "Discussion"}]
    for _ in range(3):
        assert live(client, body).status_code == 200
    times = []
    for i in range(25):
        t = time.perf_counter()
        assert live(client, body, revision=i).status_code == 200
        times.append((time.perf_counter() - t) * 1000)
    times.sort()
    p50, p95 = statistics.median(times), times[int(0.95 * (len(times) - 1))]
    if not rules_grammar.available():
        pytest.skip(f"grammar tier unavailable here; without it p50 "
                    f"{p50:.0f} ms, p95 {p95:.0f} ms")
    assert p50 < 300 and p95 < 800, (p50, p95)


# --- additive fields on the full check -----------------------------------------------

def test_analyze_suggestions_gain_utf16_offsets_and_critical(client):
    content = "Discussion\n\n\U0001F600 The data was recieved and the the result is clear."
    r = client.post("/v1/analyze", json={"content": content})
    units = content.encode("utf-16-le")
    sugs = r.json()["suggestions"]
    assert sugs
    for s in sugs:
        assert s["critical"] is (s["category"] == "correction")
        got = units[2 * s["begin16"]:2 * s["end16"]].decode("utf-16-le")
        assert got == s["text"] == content[s["span"]["start"]:s["span"]["end"]]


def test_analyze_word_locations_gain_utf16_offsets(client):
    paras = [{"text": "Discussion", "style": "Heading 1"},
             {"text": "\U0001D445\U0001F600 The data was recieved and the the "
                      "result is clear.", "style": "Normal"}]
    r = client.post("/v1/analyze-word", json={"paragraphs": paras})
    assert r.status_code == 200, r.text
    sugs = r.json()["suggestions"]
    assert sugs
    for s in sugs:
        loc = s["location"]
        units = paras[loc["paragraph"]]["text"].encode("utf-16-le")
        got = units[2 * loc["begin16"]:2 * loc["end16"]].decode("utf-16-le")
        assert got == s["text"]
        assert s["critical"] is (s["category"] == "correction")


def test_the_typescript_contract_mirrors_the_limits():
    index = (Path(__file__).resolve().parents[3] / "packages" / "contract"
             / "src" / "index.ts").read_text(encoding="utf-8")

    def const(name):
        m = re.search(rf"export const {name} = ([^;]+);", index)
        assert m, name
        return m.group(1).strip()

    assert int(const("MAX_LIVE_PARAGRAPHS").replace("_", "")) == MAX_LIVE_PARAGRAPHS
    assert int(const("MAX_LIVE_CHARS").replace("_", "")) == MAX_LIVE_CHARS
    assert int(const("MAX_LIVE_HEADING_CHARS").replace("_", "")) == \
        MAX_LIVE_HEADING_CHARS
    assert const("PARAGRAPH_ID_PATTERN") == \
        "/" + PARAGRAPH_ID_PATTERN.replace("]+$", "]{1,64}$") + "/"


def test_what_the_mac_client_sends_is_accepted(client):
    """No Origin, no token, options with only show_preferences and
    spelling, and option keys this engine does not know: accepted."""
    for options in ({}, {"show_preferences": False}, {"spelling": "uk"},
                    {"show_preferences": True, "spelling": "us",
                     "a_future_option": {"x": 1}, "tone": "formal"}):
        r = client.post(ROUTE, json={"revision": 1, "options": options,
                                     "paragraphs": [{"id": "f1", "text": SLIPS}]})
        assert r.status_code == 200, (options, r.text)
    r = client.post(ROUTE, json={"revision": 1, "paragraphs": [{"id": "f1", "text": SLIPS}]})
    assert r.status_code == 200
    # A known option with a bad value is still refused.
    bad = client.post(ROUTE, json={"revision": 1, "options": {"spelling": "klingon"},
                                   "paragraphs": [{"id": "f1", "text": SLIPS}]})
    assert bad.status_code == 422

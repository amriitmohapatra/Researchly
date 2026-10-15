"""The local engine ("This computer", apps/word-addin/server.py on
127.0.0.1:3517) answers the live check as the hosted engine does (S4d
R7/R8): POST /v1/check-paragraphs with the same limits, the same reply
(validated against the service's own model, which forbids unknown
fields), the same paragraphs for the same settings, CORS for the hosted
pages, and native clients without an Origin header from loopback only.

Synthetic text only (CLAUDE.md).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from researchly import config as config_mod
from researchly_service.schemas import (MAX_LIVE_CHARS,
                                        MAX_LIVE_HEADING_CHARS,
                                        MAX_LIVE_PARAGRAPHS, MAX_REVISION,
                                        PARAGRAPH_ID_PATTERN,
                                        CheckParagraphsResponse)

import contract_fixtures as cf

ROOT = Path(__file__).resolve().parents[3]
ROUTE = "/v1/check-paragraphs"
HOSTED = "https://researchly-chi.vercel.app"
SLIPS = cf.SLIPS


@pytest.fixture(scope="module")
def server():
    path = ROOT / "apps" / "word-addin" / "server.py"
    spec = importlib.util.spec_from_file_location("local_live_server", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["local_live_server"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def no_grammar(server, monkeypatch):
    """Default settings (as the hosted engine starts from) with the grammar
    tier off, so the answer depends neither on this machine's config file
    nor on whether Java is installed here."""
    def load(*a, **kw):
        cfg = config_mod.Config()
        cfg.grammar_tier = False
        return cfg
    monkeypatch.setattr(server.config_mod, "load", load)


def wire(obj):
    return json.loads(json.dumps(obj))          # exactly what a client reads


def live(server, paragraphs, revision=1, **options):
    body = {"revision": revision, "paragraphs": paragraphs}
    if options:
        body["options"] = options
    return wire(server.check_paragraphs_v1(body))


# --- the reply -------------------------------------------------------------------

def test_the_reply_is_the_contract(server):
    body = live(server, [{"id": "b", "text": SLIPS, "heading": "Results"},
                         {"id": "a", "text": cf.PASSIVE, "heading": "Methods"}],
                revision=42)
    resp = CheckParagraphsResponse.model_validate(body)       # extra=forbid
    assert resp.revision == 42
    assert [p.id for p in resp.paragraphs] == ["b", "a"]
    assert [p.section for p in resp.paragraphs] == ["results", "methods"]
    assert resp.paragraphs[0].suggestions and not resp.paragraphs[1].suggestions
    assert resp.state.value in ("ok", "partial") and resp.health
    assert resp.signed_in is False and resp.ruleset and resp.assessed_rules


@pytest.mark.parametrize("name", ["ok", "clear", "partial"])
def test_the_shared_fixtures_get_the_same_paragraphs_here(server, no_grammar,
                                                          name):
    """For the same text and settings, this computer underlines exactly
    what the hosted engine does (the shared fixtures were made by it)."""
    fx = json.loads(cf.path_for(name).read_text(encoding="utf-8"))
    body = wire(server.check_paragraphs_v1(fx["request"]))
    CheckParagraphsResponse.model_validate(body)
    assert body["revision"] == fx["response"]["revision"]
    assert body["paragraphs"] == fx["response"]["paragraphs"]
    assert body["hidden_preferences"] == fx["response"]["hidden_preferences"]


def test_utf16_offsets_and_the_flagged_words(server):
    text = cf.ASTRAL
    sugs = live(server, [{"id": "emoji.1", "text": text}])["paragraphs"][0][
        "suggestions"]
    units = text.encode("utf-16-le")
    assert sugs
    for s in sugs:
        assert units[2 * s["begin"]:2 * s["end"]].decode("utf-16-le") == s["text"]
        assert len(s["id"]) == 16 and s["critical"] is (s["category"] == "correction")


def test_state_partial_only_for_a_tier_that_should_run(server):
    tier = {"tier": "grammar", "label": "Grammar", "ok": False, "detail": "",
            "remedy": ""}
    assert server._degraded([dict(tier, state="error")])
    assert not server._degraded([dict(tier, state="disabled")])
    assert not server._degraded([dict(tier, tier="gec", state="missing")])
    assert server._degraded([dict(tier, tier="spelling", state="missing")])


def test_options_apply_and_unknown_keys_are_ignored(server):
    pref = "The effect was very large in every district."
    hidden = live(server, [{"id": "p", "text": pref, "heading": "Results"}])
    shown = live(server, [{"id": "p", "text": pref, "heading": "Results"}],
                 show_preferences=True, a_future_option={"x": 1})
    prefs = [s for s in shown["paragraphs"][0]["suggestions"]
             if s["category"] == "preference"]
    assert prefs and hidden["hidden_preferences"] == len(prefs)
    muted = live(server, [{"id": "p", "text": SLIPS}], disabled_rules=["W207"])
    assert "W207" in {s["rule_id"] for s in live(
        server, [{"id": "p", "text": SLIPS}])["paragraphs"][0]["suggestions"]}
    assert "W207" not in {s["rule_id"]
                          for s in muted["paragraphs"][0]["suggestions"]}


# --- the same limits as the hosted engine ------------------------------------------

INVALID = [
    {"revision": 1, "paragraphs": []},
    {"revision": -1, "paragraphs": [{"id": "a", "text": "x"}]},
    {"revision": "1", "paragraphs": [{"id": "a", "text": "x"}]},
    {"revision": 1.5, "paragraphs": [{"id": "a", "text": "x"}]},
    {"revision": True, "paragraphs": [{"id": "a", "text": "x"}]},
    {"revision": MAX_REVISION + 1, "paragraphs": [{"id": "a", "text": "x"}]},
    {"paragraphs": [{"id": "a", "text": "x"}]},
    {"revision": 1, "paragraphs": [{"id": "", "text": "x"}]},
    {"revision": 1, "paragraphs": [{"id": "a b", "text": "x"}]},
    {"revision": 1, "paragraphs": [{"id": "a/b", "text": "x"}]},
    {"revision": 1, "paragraphs": [{"id": "é", "text": "x"}]},
    {"revision": 1, "paragraphs": [{"id": "x" * 65, "text": "x"}]},
    {"revision": 1, "paragraphs": [{"id": "a"}]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": 3}]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x", "kind": "table"}]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x"},
                                   {"id": "a", "text": "y"}]},
    {"revision": 1, "paragraphs": [{"id": f"p{i}", "text": "x"}
                                   for i in range(MAX_LIVE_PARAGRAPHS + 1)]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x" * (MAX_LIVE_CHARS + 1)}]},
    {"revision": 1, "paragraphs": [{"id": f"p{i}", "text": "x" * (MAX_LIVE_CHARS // 2)}
                                   for i in range(3)]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x",
                                    "heading": "h" * (MAX_LIVE_HEADING_CHARS + 1)}]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x", "style": "s" * 201}]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x"}], "extra": 1},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x"}], "options": []},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x"}],
     "options": {"spelling": "klingon"}},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x"}],
     "options": {"disabled_rules": "W207"}},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x"}],
     "options": {"document_type": "poem"}},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x"}], "options": None},
    [],
]

VALID = [
    {"revision": MAX_REVISION, "paragraphs": [
        {"id": f"p.{i}:x-y_z", "text": "Fine." if i else ""}
        for i in range(MAX_LIVE_PARAGRAPHS)]},
    {"revision": 0, "paragraphs": [{"id": "a" * 64, "text": "x " * (MAX_LIVE_CHARS // 2)}]},
    {"revision": 1, "paragraphs": [{"id": "a", "text": "x", "style": "Normal",
                                    "heading": "h" * MAX_LIVE_HEADING_CHARS}]},
    {"revision": 1, "paragraphs": [{"id": "f1", "text": SLIPS}],
     "options": {"show_preferences": True, "spelling": "us",
                 "a_future_option": {"x": 1}, "tone": "formal"}},
    {"revision": 1, "paragraphs": [{"id": "f1", "text": SLIPS}], "options": {}},
]


@pytest.mark.parametrize("body", INVALID)
def test_refused_here_as_by_the_hosted_engine(server, client, body):
    assert client.post(ROUTE, json=body).status_code == 422, body
    with pytest.raises(server.ContractError) as e:
        server.check_paragraphs_v1(body)
    assert (e.value.status, e.value.code) == (422, "invalid_request")


@pytest.mark.parametrize("body", VALID)
def test_accepted_here_as_by_the_hosted_engine(server, client, body):
    assert client.post(ROUTE, json=body).status_code == 200
    CheckParagraphsResponse.model_validate(wire(server.check_paragraphs_v1(body)))


def test_the_limits_are_the_hosted_engines(server):
    assert server.MAX_LIVE_PARAGRAPHS == MAX_LIVE_PARAGRAPHS
    assert server.MAX_LIVE_CHARS == MAX_LIVE_CHARS
    assert server.MAX_LIVE_HEADING_CHARS == MAX_LIVE_HEADING_CHARS
    assert server.MAX_REVISION == MAX_REVISION
    assert "^" + server.PARAGRAPH_ID.pattern.replace("{1,64}", "+") + "$" == \
        PARAGRAPH_ID_PATTERN


# --- over HTTP: CORS, native clients and loopback ------------------------------------

@pytest.fixture(scope="module")
def http(server):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


# Straight to loopback, whatever proxy the environment names.
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(base, method="POST", body=None, headers=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base + ROUTE, data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          **(headers or {})})
    try:
        with DIRECT.open(req, timeout=60) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


BODY = {"revision": 9, "paragraphs": [{"id": "p1", "text": SLIPS}]}


def test_a_native_client_without_an_origin_is_served_over_loopback(http):
    status, headers, raw = call(http, body=BODY)
    assert status == 200
    assert "Access-Control-Allow-Origin" not in headers
    body = json.loads(raw)
    CheckParagraphsResponse.model_validate(body)
    assert body["revision"] == 9 and body["paragraphs"][0]["suggestions"]


def test_the_hosted_page_gets_cors_and_other_pages_are_refused(http):
    status, headers, _ = call(http, body=BODY, headers={"Origin": HOSTED})
    assert status == 200 and headers["Access-Control-Allow-Origin"] == HOSTED
    status, headers, raw = call(http, body=BODY,
                                headers={"Origin": "https://evil.example"})
    assert status == 403 and "Access-Control-Allow-Origin" not in headers
    assert json.loads(raw)["error"]["code"] == "origin_not_allowed"
    status, headers, _ = call(http, method="OPTIONS", headers={
        "Origin": HOSTED, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
        "Access-Control-Request-Private-Network": "true"})
    assert status == 204
    assert headers["Access-Control-Allow-Origin"] == HOSTED
    assert headers["Access-Control-Allow-Private-Network"] == "true"


def test_errors_over_http_are_the_contracts(http):
    status, _, raw = call(http, body={"revision": 1, "paragraphs": []})
    assert status == 422
    assert json.loads(raw)["error"]["code"] == "invalid_request"
    req = urllib.request.Request(http + ROUTE, data=b"{not json", method="POST",
                                 headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as e:
        DIRECT.open(req, timeout=30)
    assert e.value.code == 422


def test_native_clients_only_from_loopback(server):
    assert server.native_allowed(None, "127.0.0.1")
    assert server.native_allowed(None, "::1")
    assert not server.native_allowed(None, "192.168.1.20")
    assert not server.native_allowed(None, "10.0.0.5")
    # A browser request is judged by CORS, wherever it comes from.
    assert server.native_allowed(HOSTED, "127.0.0.1")

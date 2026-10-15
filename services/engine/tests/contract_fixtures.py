"""Shared fixtures of the live check, made by the real service (S4d R7/R8).

`packages/contract/fixtures/check-paragraphs/*.json` hold real exchanges of
`POST /v1/check-paragraphs`: the request a client sends, the status, the
headers a client acts on, and the body the service answered. The macOS
(XCTest) and Windows (xUnit) overlay clients decode the same files, so a
client can never drift from what the engine actually sends.

`test_contract_fixtures.py` makes every exchange again and compares; when a
rule's wording or the contract changes on purpose, regenerate from
services/engine:

    python tests/contract_fixtures.py

Synthetic text only (CLAUDE.md). Each file is a JSON object:

    {"about": str, "request": {...}, "status": int,
     "headers": {lower-case name: value}, "response": {...}}

Values that differ on every run are written as they came but not compared
(VOLATILE): the time a check took, the engine's rule fingerprint and rule
list, an error's request id and a rate limit's wait.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIXTURES = ROOT / "packages" / "contract" / "fixtures" / "check-paragraphs"
ROUTE = "/v1/check-paragraphs"

# Not compared: they change with the clock, a request id, or any new rule.
VOLATILE_RESPONSE = ("elapsed_ms", "ruleset", "assessed_rules")
VOLATILE_HEADERS = ("retry-after",)

# Synthetic prose. The first paragraph starts with an emoji and holds a
# mathematical italic capital R: both are outside the Basic Multilingual
# Plane, so UTF-16 offsets differ from code-point offsets after them.
ASTRAL = ("\U0001F600 The data was recieved from each district, and the the "
          "\U0001D445 estimate were stable.")
PASSIVE = "The model was calibrated by the authors using weekly data."
CLEAN = "We fitted a renewal model to weekly case counts."
SLIPS = ("The data was recieved from each district, and in order to estimate "
         "the the reproduction number the models was fitted weekly.")


def _ok_request() -> dict:
    return {"revision": 41, "options": {"show_preferences": False},
            "paragraphs": [
                {"id": "p1", "text": ASTRAL, "heading": "Results"},
                {"id": "p2", "text": PASSIVE, "heading": "Methods"},
                {"id": "p3", "text": PASSIVE, "heading": "Discussion"},
                {"id": "p4", "text": CLEAN},
            ]}


# name → (about, settings for make_client, grammar down?, requests to send)
SCENARIOS = {
    "ok": (
        "Four paragraphs under three headings. p1 has astral characters "
        "before its suggestions (UTF-16 offsets), p2 is passive in Methods "
        "(never flagged), p3 is the same sentence in Discussion (flagged), "
        "p4 has nothing to suggest. The grammar tier is switched off "
        "(state disabled) and the learned tier has no model (missing): "
        "neither is an outage, so state is ok.",
        {"grammar_enabled": False}, False, [_ok_request()]),
    "clear": (
        "One paragraph, nothing to suggest, no heading (section unknown); "
        "options with a key this engine does not know, which is ignored.",
        {"grammar_enabled": False}, False,
        [{"revision": 7, "paragraphs": [{"id": "only", "text": CLEAN}],
          "options": {"show_preferences": True, "a_future_option": True}}]),
    "partial": (
        "The grammar tier is down (ok false, state error): state partial. "
        "The suggestions of the tiers that ran are still sent.",
        {"grammar_enabled": True}, True,
        [{"revision": 3, "paragraphs": [{"id": "s.1", "text": SLIPS,
                                         "heading": "Results"}]}]),
    "invalid-422": (
        "Two paragraphs with the same id: refused with 422 invalid_request. "
        "Sending it again will not help: show it, and wait for an edit.",
        {"grammar_enabled": False}, False,
        [{"revision": 5, "paragraphs": [{"id": "p1", "text": CLEAN},
                                        {"id": "p1", "text": PASSIVE}]}]),
    "rate-limited-429": (
        "Over the live check's rate limit (here 1 a minute): 429 "
        "rate_limited with a Retry-After header in seconds. Wait at least "
        "that long before the next check.",
        {"grammar_enabled": False, "live_rate_limit_per_min": 1}, False,
        [{"revision": 1, "paragraphs": [{"id": "p1", "text": CLEAN}]},
         {"revision": 2, "paragraphs": [{"id": "p1", "text": CLEAN}]}]),
}


class _FailingGrammar:
    def check(self, text):
        raise RuntimeError("down")

    def close(self):
        pass


@contextmanager
def _grammar_down():
    """The grammar tier fails on every request (as in
    test_check_paragraphs.test_state_partial_when_the_grammar_tier_fails)."""
    import os
    from researchly import rules_grammar
    names = ("_TOOL", "_LOCALE", "_URL", "_FAILED", "_STATE", "_DETAIL")
    saved = {k: getattr(rules_grammar, k) for k in names}
    env = os.environ.pop(rules_grammar.REMOTE_ENV, None)
    for k, v in zip(names, (_FailingGrammar(), "en-US", None, False,
                            "ready", "")):
        setattr(rules_grammar, k, v)
    try:
        yield
    finally:
        for k, v in saved.items():
            setattr(rules_grammar, k, v)
        if env is not None:
            os.environ[rules_grammar.REMOTE_ENV] = env


def exchange(name: str, make_client) -> dict:
    """Runs one scenario against a fresh service; returns the fixture."""
    about, settings, grammar_down, requests = SCENARIOS[name]
    client = make_client(**settings)
    if grammar_down:
        with _grammar_down():
            resp = [client.post(ROUTE, json=r) for r in requests][-1]
    else:
        resp = [client.post(ROUTE, json=r) for r in requests][-1]
    headers = {}
    if "retry-after" in resp.headers:
        headers["retry-after"] = resp.headers["retry-after"]
    return {"about": about, "request": requests[-1],
            "status": resp.status_code, "headers": headers,
            "response": resp.json()}


def comparable(fixture: dict) -> dict:
    """The fixture without the values that change on every run."""
    out = json.loads(json.dumps(fixture))
    body = out["response"]
    for k in VOLATILE_RESPONSE:
        body.pop(k, None)
    if isinstance(body.get("error"), dict):
        body["error"].pop("request_id", None)
    for k in VOLATILE_HEADERS:
        out["headers"].pop(k, None)
    return out


def path_for(name: str) -> Path:
    return FIXTURES / f"{name}.json"


def dump(fixture: dict) -> str:
    return json.dumps(fixture, indent=2, ensure_ascii=False) + "\n"


def cached(make_client):
    """One service per distinct settings (the rate-limited one is the only
    one that needs its own), so the scenarios run in seconds."""
    clients: dict = {}

    def get(**kw):
        key = json.dumps(kw, sort_keys=True)
        if key not in clients:
            clients[key] = make_client(**kw)
        return clients[key]
    return get


def write_all(make_client) -> list:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    get = cached(make_client)
    written = []
    for name in SCENARIOS:
        path_for(name).write_text(dump(exchange(name, get)),
                                  encoding="utf-8")
        written.append(path_for(name))
    return written


def main() -> int:
    sys.path.insert(0, str(HERE.parent))
    sys.path.insert(0, str(HERE))
    from fastapi.testclient import TestClient
    from conftest import make_settings
    from researchly_service.main import create_app

    opened = []

    def make_client(**kw):
        c = TestClient(create_app(make_settings(**kw)),
                       raise_server_exceptions=False)
        c.__enter__()
        opened.append(c)
        return c

    try:
        for p in write_all(make_client):
            print(p.relative_to(ROOT))
    finally:
        for c in opened:
            c.__exit__(None, None, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

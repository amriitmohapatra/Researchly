"""The local Word server's word prediction route (2026-10-14).

apps/word-addin/server.py answers POST /v1/complete (and /complete) for the
taskpane's "Next words" panel when the writer chose "This computer". Its
JSON is validated against the hosted engine's CompleteResponse model,
which forbids unknown fields, and the route is exercised through the real
HTTP handler. The model is a tiny synthetic one, so these tests do not
depend on the shipped corpus. Synthetic sentences only."""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import urllib.error
import urllib.request
from collections import Counter
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from researchly import config, predict
from researchly_service.schemas import CompleteResponse

ROOT = Path(__file__).resolve().parents[3]
ORIGIN = "https://researchly-chi.vercel.app"

SENTENCES = [
    "we estimated the basic reproduction number from weekly case counts",
    "the basic reproduction number was estimated with a renewal model",
    "we report the median and the confidence interval for each estimate",
    "estimates are shown with a confidence interval in each table",
    "the confidence interval was wide because the sample was small",
    "we fitted a transmission model to the weekly case counts",
]


def _tables(sentences, copies=10):
    counts = {k: {} for k in range(predict.ORDER)}
    for _ in range(copies):
        for sent in sentences:
            seq = ["<s>"] + sent.split()
            for i in range(1, len(seq)):
                for k in range(predict.ORDER):
                    if i - k < 0:
                        break
                    ctx = tuple(seq[i - k:i])
                    counts[k].setdefault(ctx, Counter())[seq[i]] += 1
    return {k: {ctx: (sum(c.values()), c.most_common(40))
                for ctx, c in table.items()}
            for k, table in counts.items()}


@pytest.fixture(scope="module")
def server():
    path = ROOT / "apps" / "word-addin" / "server.py"
    spec = importlib.util.spec_from_file_location("local_word_server_complete", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["local_word_server_complete"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    path = tmp_path_factory.mktemp("predict") / "tiny.sqlite"
    predict.write_model(path, _tables(SENTENCES), {}, {"version": 1})
    return predict.Model(path)


@pytest.fixture
def model(monkeypatch, tiny):
    """The tiny model in place of the shipped one."""
    monkeypatch.setattr(predict, "_MODEL", tiny)
    monkeypatch.setattr(predict, "MODEL_FILE", tiny.path)
    return tiny


@pytest.fixture
def prediction_on(monkeypatch, server):
    """This computer's config, with prediction on, whatever ~/.researchly says."""
    monkeypatch.setattr(server.config_mod, "load",
                        lambda *a, **k: config.Config(prediction=True))


def answer(server, body: dict) -> CompleteResponse:
    raw = json.loads(json.dumps(server.complete_v1(body)))   # what the browser gets
    return CompleteResponse.model_validate(raw)                # extra=forbid


def test_completes_the_word_being_typed(server, model, prediction_on):
    text = "We estimated the basic rep"
    resp = answer(server, {"text": text, "format": "plain"})
    assert resp.status == "ok" and resp.candidates
    c = resp.candidates[0]
    assert (c.start, c.end) == (len(text) - 3, len(text))
    assert c.text.startswith("reproduction")
    assert all(len(x.text.split()) <= 3 for x in resp.candidates)


def test_the_cursor_counts_code_points(server, model, prediction_on):
    # An emoji is one Python index and two UTF-16 units: the browser converts.
    text = "\U0001F600 We estimated the basic rep and more"
    cursor = text.index(" and")
    resp = answer(server, {"text": text, "cursor": cursor, "options": {"limit": 2}})
    assert len(resp.candidates) <= 2
    for c in resp.candidates:
        assert c.end == cursor and text[c.start:c.end] == "rep"


def test_nothing_inside_a_citation(server, model, prediction_on):
    resp = answer(server, {"text": "As shown by \\cite{smi", "format": "latex"})
    assert resp.status == "masked" and resp.candidates == []


def test_nothing_when_this_computer_turned_it_off(server, model, monkeypatch):
    monkeypatch.setattr(server.config_mod, "load",
                        lambda *a, **k: config.Config(prediction=False))
    resp = answer(server, {"text": "We estimated the basic rep"})
    assert resp.status == "off" and resp.candidates == []


def test_without_a_model_it_says_unavailable(server, monkeypatch, prediction_on):
    monkeypatch.setattr(predict, "_MODEL", None)
    monkeypatch.setattr(predict, "MODEL_FILE", Path("/nonexistent/predict.sqlite"))
    resp = answer(server, {"text": "We estimated the basic rep"})
    assert resp.status == "unavailable" and resp.candidates == []


@pytest.mark.parametrize("bad", [
    {"text": "abc", "cursor": 10},
    {"text": "abc", "cursor": -1},
    {"text": "abc", "cursor": True},
    {"text": 42},
    {"text": "abc", "format": "docx"},
    {"text": "abc", "options": {"limit": 9}},
    {"text": "abc", "options": {"spelling": "klingon"}},
    {"text": "abc", "options": {"colour": "red"}},
    {"text": "abc", "colour": "red"},
    "not an object",
])
def test_bad_requests_are_refused(server, bad):
    with pytest.raises(server.ContractError) as e:
        server.parse_complete_request(bad)
    assert e.value.status == 422


def test_too_much_text_is_refused(server):
    with pytest.raises(server.ContractError) as e:
        server.parse_complete_request({"text": "a" * (server.MAX_COMPLETE_CHARS + 1)})
    assert e.value.status == 413


# --- through the real HTTP handler -----------------------------------------

@pytest.fixture
def http(server, model, prediction_on):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def post(base: str, path: str, body, origin: str | None = ORIGIN):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if origin:
        req.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers), json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read() or b"null")


@pytest.mark.parametrize("path", ["/v1/complete", "/complete"])
def test_the_route_answers_the_hosted_taskpane(http, path):
    status, headers, body = post(http, path, {"text": "We estimated the basic rep",
                                              "format": "plain"})
    assert status == 200
    assert headers.get("Access-Control-Allow-Origin") == ORIGIN
    resp = CompleteResponse.model_validate(body)
    assert resp.status == "ok" and resp.candidates


def test_the_route_refuses_other_sites_and_bad_bodies(http):
    status, _, body = post(http, "/v1/complete", {"text": "abc"},
                           origin="https://elsewhere.example")
    assert status == 403 and body["error"]["code"] == "origin_not_allowed"
    status, _, body = post(http, "/v1/complete", {"text": "abc", "cursor": 99})
    assert status == 422 and body["error"]["code"] == "invalid_request"
    assert "abc" not in json.dumps(body)        # errors never quote the text


def test_the_preflight_allows_the_hosted_taskpane(http):
    req = urllib.request.Request(http + "/v1/complete", method="OPTIONS")
    req.add_header("Origin", ORIGIN)
    req.add_header("Access-Control-Request-Method", "POST")
    req.add_header("Access-Control-Request-Private-Network", "true")
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 204
        assert r.headers.get("Access-Control-Allow-Origin") == ORIGIN
        assert r.headers.get("Access-Control-Allow-Private-Network") == "true"

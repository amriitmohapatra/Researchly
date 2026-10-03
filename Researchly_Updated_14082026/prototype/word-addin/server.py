"""Researchly local server for the Word add-in.

Serves the taskpane web app and a /check endpoint, all on localhost.
Everything runs on your machine — no document text ever leaves it.

Usage:
    python server.py            # http://localhost:3517
    python server.py --port N
    python server.py --https    # requires cert.pem/key.pem (see README)

Python stdlib only (plus the researchly package + spaCy already installed
for the CLI). Start this, then open the Researchly add-in in Word.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))          # make `researchly` importable

from researchly import api                             # noqa: E402
from researchly import config as config_mod            # noqa: E402
from researchly import telemetry                       # noqa: E402
from researchly import transform                       # noqa: E402

_NLP_LOCK = threading.Lock()


def get_nlp():
    """Shared with every other surface; api sets max_length identically."""
    with _NLP_LOCK:
        return api.get_nlp()


def run_check(payload: dict) -> dict:
    paragraphs = payload.get("paragraphs") or []

    analysis = api.analyze(
        paragraphs,
        nlp=get_nlp(),
        disabled=(set(payload["disabled"])
                  if payload.get("disabled") is not None else None),
        show_preferences=payload.get("show_preferences"),
    )
    doc = analysis.document

    out = []
    for s in analysis.suggestions:
        para, start_in = doc.locate(s.start)
        para_text = paragraphs[para].get("text") or ""
        end_in = min(s.end - doc.para_offsets[para], len(para_text))
        d = s.to_dict()
        d.update(_locator(para_text, start_in, end_in))
        d["para"] = para
        d["start_in_para"] = start_in
        d["end_in_para"] = end_in
        d["why"] = " ".join(s.why.split())
        out.append(d)

    result = analysis.to_dict()
    result["suggestions"] = out
    result["coverage"] = _coverage(paragraphs, doc)
    return result


def _coverage(paragraphs: list, doc) -> dict:
    """What was and was not read, stated plainly.

    Office JS `body.paragraphs` excludes footnotes, endnotes, headers,
    footers, text boxes and comments. Researchly never checked them and
    never said so, which reads as "nothing to flag" rather than "not looked
    at" — the same silence-is-ambiguous failure as the dead grammar tier.
    """
    return {
        "paragraphs": len(paragraphs),
        "table_paragraphs": len(getattr(doc, "table_spans", [])),
        "not_checked": ["footnotes", "endnotes", "headers and footers",
                        "text boxes", "comments"],
    }


def _locator(para_text: str, start_in: int, end_in: int) -> dict:
    """How the client should find this span again in Word.

    Word has no offset-addressable API, so the taskpane re-finds the text by
    searching. Two things make that safe: the snippet must be the FULL span
    (a truncated one can match somewhere else), and the occurrence index must
    be counted with the same string the client will search for.
    """
    span = para_text[start_in:end_in]
    # `search` chokes on its own wildcard characters and on very long
    # needles; when we cannot hand over an exact literal, say so rather than
    # let the client guess with a prefix.
    exact = bool(span) and len(span) <= 255 and "^" not in span
    snippet = span if exact else span[:180].replace("^", "")
    occurrence = para_text[:start_in].count(snippet) if snippet else 0
    return {"snippet": snippet, "occurrence": occurrence, "exact": exact,
            "expected": span}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE / "web"), **kwargs)

    def log_message(self, fmt, *args):  # quieter logs
        pass

    def _json(self, code: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/ping":
            # Rules register on import, which check() does lazily — so this
            # must trigger it or the taskpane reports "0 rules" until the
            # first check.
            return self._json(200, {"ok": True, "app": "researchly",
                                    "rules": api.ensure_rules_loaded()})
        if self.path.startswith("/status"):
            # Which tiers are actually running. The taskpane shows this so a
            # dead grammar engine can never again look like clean prose.
            cfg = config_mod.load()
            probe = "probe=1" in self.path
            statuses = api.status(cfg, probe=probe)
            from researchly.health import summary_line
            return self._json(200, {
                "health": [t.to_dict() for t in statuses],
                "summary": summary_line(statuses),
                "config": cfg.to_dict()})
        if self.path == "/rules":
            api.ensure_rules_loaded()          # registration is lazy
            from researchly.engine import REGISTRY
            return self._json(200, {"rules": [
                {"id": r.id, "name": r.name, "category": r.category.value,
                 "short": r.short, "why": " ".join(r.why.split()),
                 "source": r.source, "tier": r.tier,
                 "fix_safety": r.fix_safety}
                for r in REGISTRY.values()]})
        return super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            return self._json(400, {"error": f"bad payload: {e}"})
        if self.path == "/check":
            try:
                return self._json(200, run_check(payload))
            except Exception as e:  # prototype: surface the error in the pane
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})
        if self.path == "/polish":
            try:
                text = payload.get("text") or ""
                if not text.strip():
                    return self._json(400, {"error": "empty selection"})
                # Muted rules come from the SHARED config; a payload
                # override remains possible but the taskpane no longer
                # sends one (parity with every other surface).
                disabled = (set(payload["disabled"])
                            if payload.get("disabled") is not None
                            else config_mod.load().disabled)
                result = transform.polish(text, get_nlp(),
                                          disabled=disabled)
                return self._json(200, result.to_dict())
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})
        if self.path == "/review":
            # The critical-reader report (Wallace & Wray + the Toulmin
            # argument scan) over the whole document. Built from the same
            # Word paragraphs as /check so style-based headings survive.
            try:
                paragraphs = payload.get("paragraphs") or []
                if not paragraphs:
                    return self._json(400, {"error": "empty document"})
                from researchly import review as review_mod
                doc = api.build_document(paragraphs)
                r = review_mod.build_review(doc, get_nlp())
                return self._json(200, {
                    "report": review_mod.render_review(r), "data": r})
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})
        if self.path == "/dictionary":
            # "Add to dictionary" from an S001 card: persist the word
            # locally (~/.researchly/dictionary.txt) so it is never
            # flagged again on any surface.
            from researchly import spelling as _spelling
            word = str(payload.get("word") or "").strip()
            if not word or not word.replace("-", "").isalpha():
                return self._json(400, {"error": "not a valid word"})
            ok = _spelling.add_to_user_dictionary(word)
            return self._json(200 if ok else 500,
                              {"ok": ok, "word": word.lower()})
        if self.path == "/config":
            # The settings panel. Writes ~/.researchly/config.toml, which the
            # CLI, macOS app, Windows app and LSP all read — so a rule muted
            # in Word is muted everywhere, instead of living in this
            # taskpane's localStorage where nothing else could see it.
            try:
                cfg = config_mod.load()
                if payload.get("mute"):
                    config_mod.mute_rule(str(payload["mute"]))
                elif payload.get("unmute"):
                    config_mod.unmute_rule(str(payload["unmute"]))
                else:
                    cfg = cfg.with_overrides(**{
                        k: payload[k] for k in
                        ("show_preferences", "locale", "document_type",
                         "aggressiveness", "grammar_tier", "gec_tier",
                         "disabled")
                        if k in payload})
                    if not config_mod.save_user(cfg):
                        return self._json(500, {"error": "could not save"})
                return self._json(200, {"ok": True,
                                        "config": config_mod.load().to_dict()})
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})
        if self.path == "/telemetry":
            # local-only usage log (~/.researchly/telemetry.jsonl) — this is
            # the data `researchly stats` reports on. Never fails the UI.
            for ev in payload.get("events") or []:
                telemetry.log_event(
                    str(ev.get("event", "")), str(ev.get("rule", "")),
                    section=str(ev.get("section", "unknown")),
                    source="word", count=int(ev.get("n", 1)))
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "unknown endpoint"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=3517)
    ap.add_argument("--https", action="store_true",
                    help="serve over HTTPS using cert.pem/key.pem in this "
                         "folder (see README troubleshooting)")
    args = ap.parse_args()

    # Warm the model in the background so the first check is fast.
    threading.Thread(target=get_nlp, daemon=True).start()

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    scheme = "http"
    if args.https:
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(HERE / "cert.pem", HERE / "key.pem")
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        scheme = "https"
    print(f"Researchly server: {scheme}://localhost:{args.port}/taskpane.html")
    print("Keep this running while you write in Word. Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()

"""What a way of checking runs, and what it contacts (Codex review #11).

"Local mode" is a promise: the Word pane's "This computer", the desktop
overlays' "This computer" (both through apps/word-addin/server.py), the
editor extension (lsp.py) and the CLI check the text on this machine. The
promise is only as good as its description, so each route describes itself
from the same facts the checks run on: the tier health (health.py), the
settings (config.py) and what the route offers (the brief, the map, the
live check). Nothing here reads document text.

`describe()` answers two questions for one route:
- which checks run: writing rules, spelling, grammar, learned corrections,
  whole-document checks, the reviewer's brief and the map, each with on/off
  and, when off, why in plain words;
- what is contacted over the network: nothing, unless grammar uses a
  LanguageTool server (RESEARCHLY_LT_URL; the text goes there), or the first
  grammar check downloads LanguageTool (once; no text).

`/v1/health` on the local server and on the hosted engine carries it as
`capabilities`; `researchly doctor` and the language server print
`summary`. tests/test_capabilities.py checks each route's description
against what that route actually runs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .config import Config
from .health import TierStatus, bundled_languagetool, service_mode

# What each route offers beyond the per-check tiers. The local server
# answers both the Word pane (full check: brief and map included) and the
# desktop overlays (the live check: sentence-level rules only).
ROUTES = {
    "local_server": {
        "label": "This computer (Word and the desktop overlays)",
        "document": True, "brief": True},
    "overlay": {
        "label": "The desktop overlay, This computer",
        "document": False, "brief": False},
    "lsp": {"label": "Editor extension (VS Code, Positron)",
            "document": True, "brief": False},
    "cli": {"label": "Command line", "document": True, "brief": True},
    "service": {"label": "Researchly cloud", "document": True,
                "brief": True},
}

LABELS = {
    "rules": "writing rules",
    "spelling": "spelling",
    "grammar": "grammar",
    "gec": "learned corrections",
    "document": "whole-document checks",
    "brief": "the reviewer’s brief and the map",
}

_LOOPBACK = {"localhost", "127.0.0.1", "::1", "[::1]"}


def languagetool_downloaded() -> Optional[bool]:
    """Is LanguageTool already on this computer (so the first grammar check
    downloads nothing)? None when it cannot be told."""
    try:
        if os.environ.get("LTP_JAR_DIR_PATH") or bundled_languagetool():
            return True
        home = os.environ.get("LTP_PATH") or str(
            Path.home() / ".cache" / "language_tool_python")
        folder = Path(home)
        if not folder.is_dir():
            return False
        return any(p.is_dir() for p in folder.glob("LanguageTool*"))
    except Exception:
        return None


def _off_note(t: Optional[TierStatus]) -> str:
    if t is None:
        return "not available"
    if t.state == "disabled":
        return "turned off in settings"
    if t.state == "missing":
        return "not installed"
    if t.state == "error":
        return "not working"
    return ""


def _check(cid: str, on: bool, note: str = "") -> dict:
    return {"id": cid, "label": LABELS[cid], "on": bool(on),
            "note": "" if on else note}


def describe(cfg: Optional[Config], statuses: list,
             route: str = "cli") -> dict:
    """The checks `route` runs with these settings and this health, and
    what it contacts over the network. Never raises on missing tiers."""
    spec = ROUTES[route]
    by = {t.tier: t for t in statuses}

    def tier_on(name: str) -> bool:
        t = by.get(name)
        return t is not None and t.ok

    parser = tier_on("parser")
    draft = cfg is not None and cfg.mode == "draft"
    checks = [
        _check("rules", parser, _off_note(by.get("parser"))),
        _check("spelling", parser and tier_on("spelling"),
               _off_note(by.get("spelling") if parser
                         else by.get("parser"))),
        _check("grammar", tier_on("grammar"), _off_note(by.get("grammar"))),
    ]
    if tier_on("gec"):
        checks.append(_check("gec", True))
    if spec["document"]:
        checks.append(_check("document", parser and not draft,
                             "held back in Draft mode" if draft
                             else _off_note(by.get("parser"))))
    else:
        checks.append(_check("document", False,
                             "not part of the live check"))
    if spec["brief"]:
        checks.append(_check("brief", parser, _off_note(by.get("parser"))))
    else:
        checks.append(_check("brief", False, "not offered here"))

    contacts = network_contacts(by.get("grammar"))
    where = "service" if route == "service" or service_mode() \
        else "this_computer"
    return {
        "route": route,
        "label": spec["label"],
        "where": where,
        "checks": checks,
        "network": {
            "sends_text": any(c["sends_text"] and c["leaves_computer"]
                              for c in contacts),
            "contacts": contacts,
        },
        "summary": summary(where, checks, contacts),
    }


def network_contacts(grammar: Optional[TierStatus]) -> list[dict]:
    """What a check contacts besides this process. Only the grammar tier
    ever does: a LanguageTool server (the text goes there), or LanguageTool's
    download, once, before the first local grammar check (no text)."""
    from . import rules_grammar

    if grammar is None or grammar.state == "disabled":
        return []
    url = rules_grammar.remote_url()
    if url is not None:
        host = urlparse(url).hostname or url
        local = host in _LOOPBACK
        if service_mode():
            what = "the grammar checker beside the engine"
        elif local:
            what = f"a grammar server on this computer ({_netloc(url)})"
        else:
            what = f"the grammar server at {_netloc(url)}"
        return [{"what": what, "when": "every check", "sends_text": True,
                 "leaves_computer": not local or service_mode()}]
    if grammar.ok and languagetool_downloaded() is False:
        return [{"what": "LanguageTool’s download site",
                 "when": "once, before the first grammar check",
                 "sends_text": False, "leaves_computer": True}]
    return []


def _netloc(url: str) -> str:
    p = urlparse(url)
    return p.netloc or url


def _join(words: list[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def summary(where: str, checks: list[dict], contacts: list[dict]) -> str:
    """One plain line: "This computer: checks writing rules, spelling,
    grammar and whole-document checks; sends nothing over the network.\""""
    on = [c["label"] for c in checks if c["on"] and c["id"] != "brief"]
    brief = any(c["on"] for c in checks if c["id"] == "brief")
    off = [f"{c['label']} ({c['note']})" for c in checks
           if not c["on"] and c["id"] in ("rules", "spelling", "grammar")]
    head = "Researchly cloud" if where == "service" else "This computer"
    parts = [f"checks {_join(on)}" if on else "checks nothing"]
    if brief:
        parts[0] += ", and builds the reviewer’s brief and the map"
    line = f"{head}: {parts[0]}"
    if off:
        line += f"; off: {_join(off)}"
    sent = [c for c in contacts if c["sends_text"]]
    if where == "service":
        line += ("; your text is analysed in memory and never stored, "
                 "logged or used for training.")
        return line
    if any(c["leaves_computer"] for c in sent):
        line += "; sends your text to " + _join([c["what"] for c in sent])
    elif sent:
        line += "; sends your text only to " + _join(
            [c["what"] for c in sent]) + ", nothing over the network"
    else:
        line += "; sends nothing over the network"
    if any(not c["sends_text"] for c in contacts):
        line += (". The first grammar check downloads LanguageTool once "
                 "(no text is sent)")
    return line + "."

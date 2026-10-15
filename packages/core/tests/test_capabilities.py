"""Local-mode parity (Codex review #11): each local route says what it
checks and what it contacts, and the description matches what it runs.

Routes: the local server (Word's and the desktop overlays' "This computer",
apps/word-addin/server.py), the overlays' live check through it, the editor
extension (lsp.py) and the CLI. All text is synthetic.
"""

import json
import socket
import sys
from pathlib import Path

import pytest

from researchly import api, capabilities, cli, doctor, rules_grammar
from researchly import config as config_mod
from researchly.health import TierStatus

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "word-addin"))

import server as addin_server  # noqa: E402

TEXT = ("Methods\n\nWe fitted a renewal model to weekly counts. "
        "The priors was weak.\n\nDiscussion\n\nThe estimates were stable.\n")
PARAS = [{"text": "Methods", "style": "Heading 1", "kind": "body"},
         {"text": "We fitted a renewal model to weekly counts.",
          "style": "Normal", "kind": "body"}]


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """A user config of our own; never the real ~/.researchly."""
    user_dir = tmp_path / ".researchly"
    user_dir.mkdir()
    monkeypatch.setattr(config_mod, "USER_DIR", user_dir)
    monkeypatch.setattr(config_mod, "USER_CONFIG_FILE",
                        user_dir / "config.toml")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(rules_grammar.REMOTE_ENV, raising=False)
    return user_dir


def grammar_off(user_dir: Path) -> None:
    (user_dir / "config.toml").write_text("[tiers]\ngrammar = false\n")


def ready(tier: str, ok: bool = True, state: str = "ready") -> TierStatus:
    return TierStatus(tier, tier.title(), ok, state)


ALL_READY = [ready("parser"), ready("spelling"), ready("grammar"),
             ready("gec", False, "missing")]


def checks(desc: dict) -> dict:
    return {c["id"]: c["on"] for c in desc["checks"]}


# --- the description itself ---------------------------------------------------------

@pytest.mark.parametrize("route,document,brief", [
    ("local_server", True, True), ("overlay", False, False),
    ("lsp", True, False), ("cli", True, True)])
def test_each_route_says_what_it_offers(isolated, monkeypatch, route,
                                        document, brief):
    monkeypatch.setattr(capabilities, "languagetool_downloaded", lambda: True)
    d = capabilities.describe(config_mod.Config(), ALL_READY, route)
    on = checks(d)
    assert on["rules"] and on["spelling"] and on["grammar"]
    assert on["document"] is document and on["brief"] is brief
    assert "gec" not in on                 # an absent opt-in tier is not news
    assert d["where"] == "this_computer"
    assert d["network"] == {"sends_text": False, "contacts": []}
    assert d["summary"].startswith("This computer: checks writing rules, "
                                   "spelling" + (", grammar" if document
                                                 else " and grammar;"))
    assert d["summary"].endswith("sends nothing over the network.")


def test_grammar_off_is_said_with_its_reason(isolated):
    statuses = [ready("parser"), ready("spelling"),
                TierStatus("grammar", "Grammar", False, "missing",
                           "no Java", "brew install openjdk@17")]
    d = capabilities.describe(config_mod.Config(), statuses, "lsp")
    g = next(c for c in d["checks"] if c["id"] == "grammar")
    assert g == {"id": "grammar", "label": "grammar", "on": False,
                 "note": "not installed"}
    assert "off: grammar (not installed)" in d["summary"]


def test_draft_mode_holds_back_whole_document_checks(isolated):
    d = capabilities.describe(config_mod.Config(mode="draft"), ALL_READY,
                              "cli")
    doc = next(c for c in d["checks"] if c["id"] == "document")
    assert doc["on"] is False and doc["note"] == "held back in Draft mode"


def test_a_remote_grammar_server_is_where_the_text_goes(isolated,
                                                        monkeypatch):
    monkeypatch.setenv(rules_grammar.REMOTE_ENV, "http://lt.example.org:8010")
    d = capabilities.describe(config_mod.Config(), ALL_READY, "cli")
    assert d["network"]["sends_text"] is True
    assert d["network"]["contacts"][0]["what"] == \
        "the grammar server at lt.example.org:8010"
    assert "sends your text to the grammar server at lt.example.org:8010" \
        in d["summary"]


def test_a_grammar_server_on_this_computer_is_not_the_network(isolated,
                                                              monkeypatch):
    monkeypatch.setenv(rules_grammar.REMOTE_ENV, "localhost:8010")
    d = capabilities.describe(config_mod.Config(), ALL_READY, "cli")
    assert d["network"]["sends_text"] is False
    c = d["network"]["contacts"][0]
    assert c["sends_text"] and not c["leaves_computer"]
    assert "nothing over the network" in d["summary"]


def test_the_first_grammar_check_download_is_said(isolated, monkeypatch):
    monkeypatch.setattr(capabilities, "languagetool_downloaded",
                        lambda: False)
    d = capabilities.describe(config_mod.Config(), ALL_READY, "lsp")
    assert d["network"]["sends_text"] is False
    assert d["network"]["contacts"] == [{
        "what": "LanguageTool’s download site",
        "when": "once, before the first grammar check",
        "sends_text": False, "leaves_computer": True}]
    assert "downloads LanguageTool once (no text is sent)" in d["summary"]


def test_languagetool_download_is_found_where_the_library_keeps_it(
        tmp_path, monkeypatch):
    monkeypatch.delenv("LTP_JAR_DIR_PATH", raising=False)
    monkeypatch.setattr(capabilities, "bundled_languagetool", lambda: None)
    monkeypatch.setenv("LTP_PATH", str(tmp_path))
    assert capabilities.languagetool_downloaded() is False
    (tmp_path / "LanguageTool-6.6").mkdir()
    assert capabilities.languagetool_downloaded() is True


# --- each route's description matches what it runs ------------------------------------

def test_lsp_route_matches_its_checks(isolated):
    lsp = pytest.importorskip("researchly.lsp")
    grammar_off(isolated)
    report = lsp.capabilities_report()
    a = api.analyze(TEXT, cfg=config_mod.load())
    assert checks(report)["grammar"] is False
    assert "LT001" not in a.assessed_rules
    assert checks(report)["brief"] is False and a.review is None
    # on again: both agree again
    (isolated / "config.toml").write_text("")
    report = lsp.capabilities_report()
    assert checks(report)["document"] is True
    doc_rules = {r for r in api.assessed_rules(config_mod.load(), set(), [])
                 if api._scope(r) != "sentence"}
    assert doc_rules, "the full check runs whole-document rules"


def test_the_local_server_health_carries_its_capabilities(isolated):
    from test_word_addin_v1 import _schemas
    schemas = _schemas()
    grammar_off(isolated)
    h = addin_server.health_v1()
    schemas.HealthResponse.model_validate(json.loads(json.dumps(h)))
    caps = h["capabilities"]
    assert caps["route"] == "local_server" and caps["where"] == "this_computer"
    assert checks(caps)["grammar"] is False
    body = addin_server.analyze_word({"paragraphs": PARAS})
    assert "LT001" not in body["assessed_rules"]
    assert checks(caps)["brief"] is True
    with_brief = addin_server.analyze_word(
        {"paragraphs": PARAS, "options": {"review": True}})
    assert with_brief["review"] is not None


def test_the_local_server_health_without_the_service_installed(isolated):
    h = addin_server.health_v1()
    assert set(h) == {"status", "tiers", "engine", "capabilities"}
    assert h["capabilities"]["network"]["sends_text"] is False


def test_the_live_check_runs_no_whole_document_rule(isolated):
    d = capabilities.describe(config_mod.load(),
                              api.status(config_mod.load()), "overlay")
    res = api.check_paragraphs([{"id": "p1", "text": PARAS[1]["text"]}])
    assert checks(d)["document"] is False
    assert all(api._scope(r) == "sentence" for r in res.assessed_rules)


def test_a_local_check_connects_to_nothing_beyond_this_computer(isolated,
                                                                monkeypatch):
    """Where the text goes: the full local check (grammar included, when
    this machine has it) opens no connection that leaves the computer."""
    seen = []
    real_connect = socket.socket.connect

    def connect(self, address):
        seen.append(address)
        return real_connect(self, address)
    monkeypatch.setattr(socket.socket, "connect", connect)
    a = api.analyze(TEXT, cfg=config_mod.load(), with_review=True,
                    with_narrative=True)
    assert a.suggestions
    hosts = {addr[0] for addr in seen if isinstance(addr, tuple)}
    assert hosts <= {"127.0.0.1", "localhost", "::1"}, hosts


# --- researchly doctor ------------------------------------------------------------------

def test_doctor_lists_each_dependency_with_a_remedy(isolated, monkeypatch,
                                                    capsys):
    monkeypatch.setattr(doctor, "_server", lambda port: doctor.Item(
        "Local server (Word, desktop overlays)", None,
        f"not running on port {port}", "python3.10 apps/word-addin/server.py"))
    code = cli.main(["doctor"])
    out = capsys.readouterr().out
    for name in ("Python", "spaCy model", "Spelling (SymSpell)",
                 "File readers", "Local server"):
        assert name in out
    assert "to set up: python3.10 apps/word-addin/server.py" in out
    assert out.rstrip().splitlines()[-1].startswith("This computer: checks")
    assert code == 0


def test_doctor_fails_when_the_parser_cannot_run(isolated, monkeypatch):
    real = doctor._installed
    monkeypatch.setattr(doctor, "_installed",
                        lambda m: False if m == "en_core_web_sm" else real(m))
    items = doctor.run(config_mod.load(), port=1)
    model = next(i for i in items if i.name == "spaCy model")
    assert model.ok is False and "spacy download" in model.remedy
    assert doctor.exit_code(items) == 1


def test_doctor_says_grammar_is_off_when_turned_off(isolated):
    grammar_off(isolated)
    items = doctor.run(config_mod.load(), port=1)
    g = next(i for i in items if i.name.startswith("Grammar"))
    assert g.ok is None and "turned off" in g.detail
    caps = doctor.capability_summary(config_mod.load())
    assert checks(caps)["grammar"] is False


def test_doctor_finds_a_running_local_server(isolated):
    import threading
    from http.server import ThreadingHTTPServer
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), addin_server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        item = doctor._server(httpd.server_address[1])
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert item.ok is True and "running on port" in item.detail
    assert "older" not in item.detail


def test_doctor_json(isolated, capsys, monkeypatch):
    monkeypatch.setattr(doctor, "_server", lambda port: doctor.Item(
        "Local server", None, "not running"))
    cli.main(["doctor", "--json"])
    body = json.loads(capsys.readouterr().out)
    assert body["capabilities"]["route"] == "cli"
    assert {i["name"] for i in body["items"]} >= {"Python", "Settings"}

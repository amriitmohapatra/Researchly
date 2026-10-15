"""`researchly doctor`: the installation health check (Codex review #11).

One line per thing a local check depends on, each with what was found and,
when something is wrong, what to do about it: Python, spaCy and its model,
SymSpell and its dictionary, the file readers, Java and LanguageTool (or the
LanguageTool server), the editor extension's language server, the settings
file, and whether the local server (apps/word-addin/server.py) is running.
Then what checking on this computer runs and what it contacts, from
`capabilities.describe()`.

Probes capability, not presence (CLAUDE.md): Java is run, not found on
PATH; the dictionary is opened; the local server is asked for its health.
Nothing here reads or sends document text. The only connection it makes is
to the local server on 127.0.0.1, and to a LanguageTool server only when
RESEARCHLY_LT_URL names one (with a fixed synthetic sentence).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.request
from dataclasses import asdict, dataclass
from typing import Optional

LOCAL_PORT = 3517
MIN_PYTHON = (3, 10)


@dataclass
class Item:
    name: str
    ok: Optional[bool]       # True fine, False broken, None for information
    detail: str
    remedy: str = ""
    essential: bool = False  # broken means no check can run


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


def _python() -> Item:
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PYTHON
    return Item("Python", ok, f"{v.major}.{v.minor}.{v.micro} "
                f"({sys.executable})",
                "" if ok else "install Python 3.10 (brew install "
                "python@3.10) and run Researchly with it", essential=True)


def _spacy() -> list[Item]:
    from .health import SPACY_MODEL
    if not _installed("spacy"):
        return [Item("spaCy", False, "not installed", "pip install spacy",
                     essential=True)]
    import spacy
    out = [Item("spaCy", True, f"version {spacy.__version__}")]
    if _installed(SPACY_MODEL):
        out.append(Item("spaCy model", True, f"{SPACY_MODEL} installed"))
    else:
        out.append(Item("spaCy model", False, f"{SPACY_MODEL} is not "
                        "installed", f"python -m spacy download {SPACY_MODEL}",
                        essential=True))
    return out


def _symspell() -> Item:
    if not _installed("symspellpy"):
        return Item("Spelling (SymSpell)", False, "symspellpy is not "
                    "installed", "pip install symspellpy", essential=True)
    try:
        import importlib.resources as ir
        ref = ir.files("symspellpy") / "frequency_dictionary_en_82_765.txt"
        with ir.as_file(ref) as p:
            size = p.stat().st_size
        return Item("Spelling (SymSpell)", True,
                    f"dictionary present ({size // 1024:,} KB)")
    except Exception as e:
        return Item("Spelling (SymSpell)", False,
                    f"the English dictionary could not be opened "
                    f"({type(e).__name__})",
                    "pip install --force-reinstall symspellpy",
                    essential=True)


def _readers() -> Item:
    missing = [m for m in ("pylatexenc", "defusedxml") if not _installed(m)]
    if not missing:
        return Item("File readers", True, "LaTeX (pylatexenc) and .docx "
                    "(defusedxml)")
    return Item("File readers", False, " and ".join(missing) + " not "
                "installed", "pip install " + " ".join(missing))


def _grammar(cfg) -> list[Item]:
    from . import capabilities, health, rules_grammar
    if cfg is not None and cfg.grammar_tier is False:
        return [Item("Grammar (LanguageTool)", None,
                     "turned off in settings ([tiers] grammar = false)")]
    if not _installed("language_tool_python"):
        return [Item("Grammar (LanguageTool)", False,
                     "language-tool-python is not installed",
                     "pip install language-tool-python")]
    url = rules_grammar.remote_url()
    if url is not None:
        ok, why = health.probe_remote(url, use_cache=False)
        return [Item("Grammar (LanguageTool server)", ok,
                     f"{url} answers a check" if ok else why,
                     "" if ok else f"start the server at {url}, or unset "
                     f"{rules_grammar.REMOTE_ENV} to use LanguageTool on "
                     "this computer")]
    java = health.find_java()
    out = []
    if java:
        out.append(Item("Java", True, f"{java} runs (17 or newer)"))
    else:
        out.append(Item("Java", False, "no working Java 17+ found (PATH, "
                        "JAVA_HOME, Homebrew and /Library/Java searched)",
                        "brew install openjdk@17"))
    have = capabilities.languagetool_downloaded()
    if have:
        out.append(Item("LanguageTool", True, "downloaded; grammar is "
                        "checked on this computer"))
    elif have is False:
        out.append(Item("LanguageTool", None, "not downloaded yet: the "
                        "first grammar check downloads it once (about "
                        "200 MB; no text is sent)"))
    return out


def _lsp() -> Item:
    if not _installed("pygls"):
        return Item("Editor extension (language server)", None,
                    "pygls is not installed; needed only for VS Code or "
                    "Positron", "pip install 'pygls<2'")
    try:
        from importlib.metadata import version
        v = version("pygls")
    except Exception:
        v = "?"
    ok = v.split(".")[0] in ("0", "1")
    return Item("Editor extension (language server)", ok,
                f"pygls {v}", "" if ok else "pip install 'pygls<2'")


def _settings() -> Item:
    from . import config as config_mod
    path = config_mod.USER_CONFIG_FILE
    return Item("Settings", None, f"{path}" + ("" if path.exists()
                                                else " (not created yet: "
                                                "defaults apply)"))


def _server(port: int, timeout: float = 1.5) -> Item:
    """Is the local server (Word's and the overlays' "This computer")
    running? Asked over loopback only, for its health (no text)."""
    url = f"http://127.0.0.1:{port}/v1/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
        status = body.get("status", "?")
        caps = body.get("capabilities") or {}
        detail = f"running on port {port} ({status})"
        if not caps:
            detail += "; it is older than this check (restart it)"
        return Item("Local server (Word, desktop overlays)", True, detail)
    except Exception:
        return Item("Local server (Word, desktop overlays)", None,
                    f"not running on port {port}; needed only for Word's or "
                    "the desktop overlay's \"This computer\"",
                    "python3.10 apps/word-addin/server.py")


def run(cfg=None, port: int = LOCAL_PORT) -> list[Item]:
    """Every item, in the order they are printed. Never raises."""
    items: list[Item] = [_python()]
    for step in (_spacy, _symspell, _readers, lambda: _grammar(cfg), _lsp,
                 _settings, lambda: _server(port)):
        try:
            got = step()
        except Exception as e:                 # the doctor must not crash
            got = Item(getattr(step, "__name__", "check").strip("_"), False,
                       f"could not be checked ({type(e).__name__})")
        items.extend(got if isinstance(got, list) else [got])
    return items


def capability_summary(cfg) -> dict:
    from . import api, capabilities
    return capabilities.describe(cfg, api.status(cfg, probe=False), "cli")


def render(items: list[Item], caps: dict) -> str:
    mark = {True: "ok ", False: "!! ", None: "-- "}
    lines = ["Researchly installation check", ""]
    width = max(len(i.name) for i in items)
    for i in items:
        lines.append(f"  {mark[i.ok]}{i.name.ljust(width)}  {i.detail}")
        if i.remedy and i.ok is not True:
            how = "fix" if i.ok is False else "to set up"
            lines.append(f"     {' ' * width}  {how}: {i.remedy}")
    lines += ["", caps["summary"]]
    return "\n".join(lines)


def exit_code(items: list[Item]) -> int:
    """1 when something every check needs is broken, else 0."""
    return 1 if any(i.ok is False and i.essential for i in items) else 0


def to_json(items: list[Item], caps: dict) -> str:
    return json.dumps({"items": [asdict(i) for i in items],
                       "capabilities": caps}, indent=2)

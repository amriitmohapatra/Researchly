"""LT001 — optional grammar tier via LanguageTool (local server, open
source, explicitly non-AI — honors the no-LLM decision).

Requires `pip install language-tool-python` and Java 17+; the library
downloads and runs LanguageTool LOCALLY (no text leaves the machine).
When unavailable, this rule is silently inert — everything else works.

We keep only genuine grammar findings (agreement, verb forms, articles,
word confusion) and drop LanguageTool's spelling (S001's job) and style
(our rules' job) categories, so the tiers never double-flag.
"""

from __future__ import annotations

import threading

from .document import Document
from .engine import Category, Suggestion, rule

_LOCK = threading.Lock()
_TOOL = None
_FAILED = False
# Why the tier is down, for health.py to report. Before this, a missing
# package or JRE made LT001 silently inert forever and the writer had no
# way to tell grammar checking from a clean document.
_STATE = "unstarted"        # unstarted | ready | no_package | no_java | error
_DETAIL = ""
_LOCALE = None              # the locale the live tool was built for

# 'misspelling' is included because LanguageTool files rule-based word
# confusions (a/an, their/there) under it — dictionary spelling is still
# excluded via the MORFOLOGIK/HUNSPELL prefixes (that's S001's job).
KEEP_ISSUE_TYPES = {"grammar", "duplication", "inconsistency",
                    "typographical", "misspelling"}
SKIP_RULE_PREFIXES = ("MORFOLOGIK", "HUNSPELL", "SPELLER")
# Typographical rules that misfire on scientific prose. Measured on two
# independent corpora the first time this tier actually ran:
#
#   UPPERCASE_SENTENCE_START  39.7% of LT001 flags on the accepted-thesis
#     corpus, 26.4% on AESW's editor-approved published prose — the single
#     noisiest rule in both. Scientific sentences legitimately open with a
#     symbol, a variable, a gene name or a unit ("$R_0$ exceeds one",
#     "log-normal priors were used"), and PDF extraction manufactures more
#     by splitting sentences mid-clause.
#   EN_UNPAIRED_QUOTES / EN_UNPAIRED_BRACKETS  fire on the asymmetric
#     bracketing of numeric citations and interval notation.
#   DASH_RULE / GERMAN_QUOTES  fire on en-dashed year ranges (2003—2012)
#     and on quotation marks in reference lists.
SKIP_TYPO_RULES = {
    "WHITESPACE_RULE", "COMMA_PARENTHESIS_WHITESPACE",
    "UPPERCASE_SENTENCE_START", "EN_UNPAIRED_QUOTES",
    "EN_UNPAIRED_BRACKETS", "DASH_RULE", "GERMAN_QUOTES",
}


def get_tool(locale: str = "en-US"):
    """Lazy local LanguageTool; returns None if unavailable.

    Records WHY it is unavailable in module state so health.py can tell the
    writer whether grammar checking is off because the package is missing,
    because there is no JRE, or because they turned it off.
    """
    global _TOOL, _FAILED, _STATE, _DETAIL, _LOCALE
    with _LOCK:
        if _TOOL is not None and _LOCALE == locale:
            return _TOOL
        if _FAILED:
            return None
        try:
            import language_tool_python
        except Exception as e:
            _FAILED, _STATE = True, "no_package"
            _DETAIL = str(e)
            _TOOL = None
            return None
        # language_tool_python finds the JVM with shutil.which("java"), so a
        # keg-only Homebrew JDK is invisible to it however correctly it was
        # installed. Put the real one on PATH first.
        from .health import ensure_java_on_path
        if not ensure_java_on_path():
            _FAILED, _STATE = True, "no_java"
            _DETAIL = "no working Java 17+ runtime found"
            _TOOL = None
            return None
        try:
            if _TOOL is not None:               # locale changed: rebuild
                try:
                    _TOOL.close()
                except Exception:
                    pass
                _TOOL = None
            _TOOL = language_tool_python.LanguageTool(locale)
            _LOCALE, _STATE, _DETAIL = locale, "ready", ""
        except Exception as e:
            _FAILED = True
            _DETAIL = str(e)
            # A missing JRE is the common case and has a different remedy
            # from a failed download, so separate them. Note this must be a
            # real probe: macOS ships a `java` stub that exists on PATH but
            # runs nothing, which is how this tier stayed dead unnoticed.
            from .health import java_available
            _STATE = "error" if java_available() else "no_java"
            _TOOL = None
    return _TOOL


def available(locale: str = "en-US") -> bool:
    return get_tool(locale) is not None


def state() -> tuple[str, str]:
    """(state, detail) without forcing a load. See _STATE for the values."""
    return _STATE, _DETAIL


def reset() -> None:
    """Allow a retry after a failure.

    `_FAILED` is deliberately sticky so a broken tier costs one attempt, not
    one per check. But a user who installs a JDK while the Word server is
    running would otherwise be told "grammar is off" until they restarted
    the process, with no hint that a restart was the answer.
    """
    global _TOOL, _FAILED, _STATE, _DETAIL, _LOCALE
    with _LOCK:
        if _TOOL is not None:
            try:
                _TOOL.close()
            except Exception:
                pass
        _TOOL = None
        _FAILED = False
        _STATE, _DETAIL, _LOCALE = "unstarted", "", None
    from .health import reset_java_cache
    reset_java_cache()


@rule("LT001", "grammar", Category.CORRECTION,
      "Grammar (agreement, verb forms, articles) via local LanguageTool.",
      "The commodity grammar layer, delegated to LanguageTool — a mature "
      "open-source rule engine running locally on this machine (Java). "
      "Only genuine grammar categories are used; spelling belongs to S001 "
      "and style to Researchly's own rules, so nothing is flagged twice. "
      "If this rule never fires, LanguageTool isn't installed: "
      "`pip install language-tool-python` (plus Java 17+).",
      source="LanguageTool",
      tier="grammar", fix_safety="review")
def lt001_grammar(doc, document: Document):
    cfg = getattr(document, "config", None)
    if cfg is not None and cfg.grammar_tier is False:   # explicitly off
        return
    locale = getattr(cfg, "locale", None) or "en-US"
    tool = get_tool(locale)
    if tool is None:
        return
    try:
        matches = tool.check(document.masked)
    except Exception as e:
        global _STATE, _DETAIL
        _STATE, _DETAIL = "error", str(e)
        return
    for m in matches:
        # attribute names vary across language_tool_python versions
        issue = (getattr(m, "rule_issue_type", None)
                 or getattr(m, "ruleIssueType", "") or "").lower()
        rule_id = (getattr(m, "rule_id", None)
                   or getattr(m, "ruleId", "") or "")
        err_len = (getattr(m, "error_length", None)
                   or getattr(m, "errorLength", 0) or 0)
        if issue not in KEEP_ISSUE_TYPES:
            continue
        if rule_id.startswith(SKIP_RULE_PREFIXES) or rule_id in \
                SKIP_TYPO_RULES:
            continue
        start = m.offset
        end = m.offset + err_len
        # masked regions are spaces; never flag inside them
        if not document.masked[start:end].strip():
            continue
        repl = m.replacements[0] if m.replacements else None
        yield Suggestion(
            message=f"{m.message} [{rule_id}]",
            start=start, end=end,
            replacement=repl)

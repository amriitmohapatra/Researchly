"""The bridge from contract v1 to `researchly.api` — and nothing else.

The service never assembles its own pipeline (CLAUDE.md): every analysis is
one `api.analyze()` call. This module only

- builds a per-request `Config` from defaults + request options (never from
  files: hosted requests are multi-tenant, see _core.py);
- maps the engine's dataclasses onto the contract's pydantic models;
- serialises engine calls with one process-wide lock, because the spaCy
  pipeline and the LanguageTool client are shared singletons that are not
  documented as thread-safe, and FastAPI runs sync routes in a threadpool.
  Cloud Run's `containerConcurrency` is set to match (deploy/), so a request
  waits in Cloud Run's queue — or goes to another instance — rather than
  behind this lock;
- warms everything once at startup so no user request pays the cold start.
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import List, Optional

from . import _core  # noqa: F401  (import path + isolation first)
from . import __version__ as SERVICE_VERSION
from .schemas import (AnalyzeOptions, AnalyzeResponse, Category, EngineInfo,
                      FixSafety, Metrics, RuleInfo, Span, Suggestion,
                      TierHealth)

import researchly
from researchly import api
from researchly.config import Config
from researchly.engine import REGISTRY

ENGINE_LOCK = threading.Lock()

# Synthetic warm-up text (never user text): a Methods heading so section
# detection runs, a passive sentence, a hedge, and a grammar slip so the
# LanguageTool path is exercised end to end.
WARMUP_TEXT = (
    "Methods\n\n"
    "Weekly case counts were fitted with a renewal-equation model. "
    "This are a deliberate slip so the grammar tier is exercised.\n\n"
    "Discussion\n\n"
    "These results may suggest that transmission declined.\n"
)

_RULES_LOADED: Optional[int] = None


def rules_loaded() -> int:
    global _RULES_LOADED
    if _RULES_LOADED is None:
        _RULES_LOADED = api.ensure_rules_loaded()
    return _RULES_LOADED


def engine_info() -> EngineInfo:
    return EngineInfo(service_version=SERVICE_VERSION,
                      core_version=researchly.__version__,
                      rules_loaded=rules_loaded())


def build_config(options: Optional[AnalyzeOptions],
                 grammar_enabled: bool = True) -> Config:
    """Defaults + this request's options. Never reads a file."""
    cfg = Config()
    if not grammar_enabled:
        cfg.grammar_tier = False           # the deployment runs no grammar
    if options is not None:
        cfg.show_preferences = bool(options.show_preferences)
        cfg.disabled = set(options.disabled_rules)
    return cfg


def fingerprint(rule_id: str, start: int, end: int, text: str) -> str:
    """Stable id for a suggestion: sha1(rule_id, start, end, text).

    Fields are joined with U+001F (unit separator) so ("A1", "2…") and
    ("A", "12…") cannot collide.
    """
    raw = "\x1f".join((rule_id, str(start), str(end), text))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _category(value: str) -> Category:
    return Category(value)


def _fix_safety(value: str) -> FixSafety:
    return FixSafety.safe if value == "safe" else FixSafety.review


def to_suggestion(s) -> Suggestion:
    conf = float(s.confidence if s.confidence is not None else 1.0)
    return Suggestion(
        id=fingerprint(s.rule_id, s.start, s.end, s.text),
        rule_id=s.rule_id,
        rule_name=s.rule_name,
        category=_category(s.category.value),
        tier=s.tier,
        span=Span(start=max(0, s.start), end=max(0, s.end),
                  line=max(0, s.line), col=max(0, s.col)),
        text=s.text,
        section=s.section or "unknown",
        message=s.message,
        why=s.why,
        source=s.source,
        learn_ref=None,
        replacement=s.replacement,
        fix_safety=_fix_safety(s.fix_safety),
        confidence=min(1.0, max(0.0, conf)),
    )


def to_tier(t) -> TierHealth:
    return TierHealth(**t.to_dict())


def to_metrics(m) -> Optional[Metrics]:
    if m is None:
        return None
    return Metrics(**m.to_dict())


def run_analysis(content: str, fmt: str, options: Optional[AnalyzeOptions],
                 grammar_enabled: bool = True) -> AnalyzeResponse:
    """One analysis, serialised. Times the whole call including lock wait."""
    t0 = time.perf_counter()
    cfg = build_config(options, grammar_enabled)
    with ENGINE_LOCK:
        a = api.analyze(content, kind=fmt, cfg=cfg)
    out = AnalyzeResponse(
        suggestions=[to_suggestion(s) for s in a.suggestions],
        counts=dict(a.counts),
        hidden_preferences=a.hidden_preferences,
        metrics=to_metrics(a.metrics),
        sections_detected=list(a.sections_detected),
        health=[to_tier(t) for t in a.health],
        engine=engine_info(),
        elapsed_ms=0,
    )
    out.elapsed_ms = int(round((time.perf_counter() - t0) * 1000))
    return out


# Tiers that never make the service "degraded" by being off: gec is opt-in
# (no model ships), so missing/disabled is its normal state.
_OPTIONAL_STATES = {"gec": {"missing", "disabled"}}


def health_tiers(grammar_enabled: bool = True) -> List[TierHealth]:
    """Live tier status. Probes remote LanguageTool (cached a few seconds);
    loads nothing new — warm-up already did."""
    from researchly.health import engine_status
    cfg = build_config(None, grammar_enabled)
    nlp = api._NLP                       # loaded by warm-up, or None
    return [to_tier(t) for t in engine_status(cfg, nlp=nlp, probe=True)]


def is_degraded(tiers: List[TierHealth]) -> bool:
    """Degraded when a tier the service is configured to run is not ok."""
    for t in tiers:
        if t.ok:
            continue
        if t.state in _OPTIONAL_STATES.get(t.tier, set()):
            continue
        if t.state == "disabled":          # the operator turned it off
            continue
        return True
    return False


def rule_infos() -> List[RuleInfo]:
    rules_loaded()
    out = []
    for r in sorted(REGISTRY.values(), key=lambda r: r.id):
        out.append(RuleInfo(
            id=r.id, name=r.name, category=_category(r.category.value),
            short=r.short, why=r.why, source=r.source, tier=r.tier,
            fix_safety=_fix_safety(r.fix_safety),
            sections_only=sorted(r.sections_only) if r.sections_only else None,
            sections_excluded=(sorted(r.sections_excluded)
                               if r.sections_excluded else None),
        ))
    return out


def warm_up(grammar_enabled: bool = True) -> dict:
    """Load spaCy, register rules, start/reach LanguageTool, run one check.

    Never raises: a tier that fails to warm is reported by /v1/health, and
    the service still starts (degraded beats down).
    """
    t0 = time.perf_counter()
    info = {"rules_loaded": rules_loaded()}
    try:
        api.get_nlp()
        run_analysis(WARMUP_TEXT, "plain", AnalyzeOptions(), grammar_enabled)
    except Exception as e:                       # reported by type only
        info["error_type"] = type(e).__name__
    tiers = health_tiers(grammar_enabled)
    info["tiers"] = {t.tier: t.state for t in tiers}
    info["warmup_ms"] = int(round((time.perf_counter() - t0) * 1000))
    return info

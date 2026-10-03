"""Rule engine: typed suggestions, rule registry, and the check pipeline.

Design decisions (traceable to the landscape research):
- Every suggestion is TYPED (Correction / Improvement / Convention /
  Preference) — no incumbent tool makes this distinction (research/01).
- Every suggestion carries a one-line message AND a longer "why" — the
  explanation is the trust currency (research/04).
- Rules are section-conditioned — same sentence, different advice depending
  on IMRaD section (project brief §2).
- Preferences are hidden by default — precision over recall; false-positive
  fatigue is the tool-killer (research/04).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable, Optional

from .document import Document
from .sources import cite


class Category(str, Enum):
    CORRECTION = "correction"
    IMPROVEMENT = "improvement"
    CONVENTION = "convention"
    PREFERENCE = "preference"


# Which engine produced a suggestion. The commodity correction tiers can all
# fire on the same span, so they are ranked for overlap resolution; the craft
# and lens tiers say something different about text and are never deduped
# against each other.
TIER_SPELLING = "spelling"
TIER_GRAMMAR = "grammar"
TIER_GEC = "gec"
TIER_CRAFT = "craft"
TIER_LENS = "lens"

# Explainable-first: where two correction tiers cover the same span, keep the
# one that can say WHY in the writer's own terms. S001 carries the scientific
# lexicon and personal-dictionary guards; LanguageTool carries a named rule;
# the learned tagger is the fallback for what neither of those catches.
CORRECTION_TIER_PRIORITY = {TIER_SPELLING: 0, TIER_GRAMMAR: 1, TIER_GEC: 2}

# Fixes safe enough to apply in bulk without reading each one. Everything
# else is a judgement call and must be applied individually.
FIX_SAFE = "safe"
FIX_REVIEW = "review"


@dataclass
class Suggestion:
    """One typed, explainable, span-anchored suggestion."""
    message: str                      # one-line rationale (always shown)
    start: int                        # char offsets into the ORIGINAL text
    end: int
    replacement: Optional[str] = None  # concrete fix, when one exists
    # Set by a rule when it knows better than its own declared default —
    # the learned tier scores per edit, deterministic rules do not.
    confidence: float = 1.0
    # filled in by the engine from the rule registry:
    rule_id: str = ""
    rule_name: str = ""
    category: Category = Category.IMPROVEMENT
    why: str = ""                     # teachable explanation
    source: str = ""                  # provenance (guide section, paper)
    tier: str = TIER_CRAFT
    fix_safety: str = FIX_REVIEW
    # filled in by the engine:
    text: str = ""
    section: str = "unknown"
    line: int = 0
    col: int = 0

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "category": self.category.value,
            "message": self.message,
            "replacement": self.replacement,
            "why": self.why,
            "source": self.source,
            "tier": self.tier,
            "fix_safety": self.fix_safety,
            "confidence": self.confidence,
            "text": self.text,
            "section": self.section,
            "line": self.line,
            "col": self.col,
            "start": self.start,
            "end": self.end,
        }


@dataclass
class Rule:
    id: str
    name: str
    category: Category
    short: str                         # one-line description for `rules` list
    why: str                           # teachable explanation (guide-derived)
    func: Callable                     # (spacy_doc, document) -> Iterable[Suggestion]
    sections_only: Optional[frozenset[str]] = None
    sections_excluded: Optional[frozenset[str]] = None
    source: str = ""                   # provenance in the writing guide
    # Aggregate repeat fires: show the FIRST hit per section with a count
    # instead of every occurrence. Fatigue-control primitive from the
    # dogfooding round — a convention prompt made once with "(7 similar)"
    # teaches; made 7 times, it nags.
    aggregate: bool = False
    # Which engine this rule belongs to, and whether its fix is safe to apply
    # without reading. Declared per rule so both are auditable in `rules`.
    tier: str = TIER_CRAFT
    fix_safety: str = FIX_REVIEW


REGISTRY: dict[str, Rule] = {}


def rule(id: str, name: str, category: Category, short: str, why: str,
         sections_only: Iterable[str] | None = None,
         sections_excluded: Iterable[str] | None = None,
         source: str = "", aggregate: bool = False,
         tier: str = TIER_CRAFT, fix_safety: str = FIX_REVIEW):
    """Decorator registering a rule function."""
    def wrap(func):
        REGISTRY[id] = Rule(
            id=id, name=name, category=category, short=short, why=why,
            func=func,
            sections_only=frozenset(sections_only) if sections_only else None,
            sections_excluded=(frozenset(sections_excluded)
                               if sections_excluded else None),
            source=cite(source), aggregate=aggregate,
            tier=tier, fix_safety=fix_safety,
        )
        return func
    return wrap


def _section_allows(r: Rule, section: str) -> bool:
    # 'unknown' (no headings, e.g. a pasted paragraph) never suppresses a
    # rule: when we can't tell the section, we surface the suggestion and let
    # the section label say 'unknown'.
    if section == "unknown":
        return True
    if r.sections_only is not None and section not in r.sections_only:
        return False
    if r.sections_excluded is not None and section in r.sections_excluded:
        return False
    return True


def check(document: Document, nlp, *,
          disabled: set[str] | None = None,
          show_preferences: bool = False,
          spacy_doc=None) -> list[Suggestion]:
    """Run all enabled rules over a document; return enriched suggestions.

    `spacy_doc` lets a caller supply an already-parsed document so the parse
    can be shared with metrics instead of repeated — see api.analyze().
    """
    # Import here so registration happens on first use, avoiding cycles.
    from . import (rules_lexical, rules_syntax,  # noqa: F401
                   rules_spelling, rules_grammar, rules_gec)

    disabled = disabled or set()
    if spacy_doc is None:
        spacy_doc = nlp(document.masked)

    out: list[Suggestion] = []
    for r in REGISTRY.values():
        if r.id in disabled:
            continue
        if r.category is Category.PREFERENCE and not show_preferences:
            continue
        kept: list[Suggestion] = []
        for s in r.func(spacy_doc, document):
            s.rule_id, s.rule_name, s.category = r.id, r.name, r.category
            # Carry the explanation and provenance on the suggestion itself.
            # Every surface used to re-join these out of REGISTRY by hand.
            s.why, s.source = r.why, r.source
            s.tier, s.fix_safety = r.tier, r.fix_safety
            section = document.section_at(s.start)
            if not _section_allows(r, section):
                continue
            s.section = section
            s.text = document.original[s.start:s.end]
            s.line, s.col = document.line_col(s.start)
            kept.append(s)
        if r.aggregate:
            kept = _aggregate_by_section(kept)
        out.extend(kept)

    out = _resolve_overlaps(out)
    out.sort(key=lambda s: (s.start, s.rule_id))
    return out


def _overlaps(a: Suggestion, b: Suggestion) -> bool:
    return a.start < b.end and b.start < a.end


def _resolve_overlaps(suggestions: list[Suggestion]) -> list[Suggestion]:
    """Drop duplicate findings where two CORRECTION tiers cover one span.

    Scope is deliberately narrow. Spelling, grammar, and the learned tagger
    all propose edits to the same words, so without this they double-flag —
    and once three tiers are live the writer sees the same typo three times.
    Craft and lens suggestions are NOT deduped against anything: a note about
    a 60-word sentence and a spelling fix inside it are different observations
    that happen to share coordinates, and suppressing either loses real signal.
    """
    corrections = [s for s in suggestions
                   if s.tier in CORRECTION_TIER_PRIORITY]
    if len(corrections) < 2:
        return suggestions

    # Longest, then highest-priority tier, then highest confidence wins.
    ranked = sorted(
        corrections,
        key=lambda s: (-(s.end - s.start),
                       CORRECTION_TIER_PRIORITY[s.tier],
                       -s.confidence,
                       s.rule_id))
    dropped: set[int] = set()
    winners: list[Suggestion] = []
    for s in ranked:
        if any(_overlaps(s, w) for w in winners):
            dropped.add(id(s))
        else:
            winners.append(s)
    if not dropped:
        return suggestions
    return [s for s in suggestions if id(s) not in dropped]


def _aggregate_by_section(suggestions: list[Suggestion]) -> list[Suggestion]:
    """Keep the first suggestion per section, annotated with a count."""
    firsts: dict[str, Suggestion] = {}
    counts: dict[str, int] = {}
    for s in sorted(suggestions, key=lambda s: s.start):
        counts[s.section] = counts.get(s.section, 0) + 1
        firsts.setdefault(s.section, s)
    for sec, s in firsts.items():
        if counts[sec] > 1:
            s.message += f" ({counts[sec]} similar in this section)"
    return list(firsts.values())


# `hidden_preference_count` used to live here and re-ran the entire pipeline
# (a second spaCy parse plus a second LanguageTool round trip) just to count
# what the first pass had already seen. It had no callers. Use
# `api.analyze()`, which returns the count from the single pass it already
# does.

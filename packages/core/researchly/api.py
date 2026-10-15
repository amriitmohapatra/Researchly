"""The one entry point every surface calls.

Before this module each surface assembled its own pipeline, and they drifted:
the Word server parsed the document twice (once in `check`, once for
metrics), the macOS app parsed it three times (it ran the whole engine a
second time just to count hidden preferences), each surface re-joined `why`
and `source` out of REGISTRY by hand, and only the CLI and LSP read
`.researchly.toml` at all.

`analyze()` does the work once and returns everything a surface needs to
render: enriched suggestions, counts, the hidden-preference count, metrics,
detected sections, engine health, and the resolved config.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence, Union

from . import metrics as metrics_mod
from . import profiles as profiles_mod
from .config import Config
from . import config as config_mod
from .document import Document
from .engine import REGISTRY, Category, Suggestion, check
from .health import TierStatus, engine_status

# spaCy's default cap is 1,000,000 characters. Every surface but the CLI
# raised it, so `researchly check` was the only one that crashed rather than
# degraded on a long thesis. Set it in exactly one place now.
MAX_LENGTH = 1_200_000

_NLP = None
_NLP_LOCK = threading.Lock()
# Pipeline components nothing in the engine reads. A rule that needs one
# (doc.ents, token.ent_type_) must take it out of this list.
NOT_USED_PIPES = ("ner",)


def get_nlp(model: str = "en_core_web_sm"):
    """Process-wide spaCy singleton, configured identically everywhere."""
    global _NLP
    with _NLP_LOCK:
        if _NLP is None:
            import spacy
            from spacy.language import Language
            if not Language.has_factory("researchly_paragraphs"):
                Language.component("researchly_paragraphs",
                                   func=paragraph_breaks)
            # No rule, read-out or report reads named entities, and the
            # entity recogniser (its own tok2vec, run last) was about 45%
            # of the parse: 5 s of an 11 s parse on a 30,000-word document.
            # Leaving it out changes no tag, lemma, dependency or sentence
            # (2026-10-14 performance pass; tests/test_performance.py).
            nlp = spacy.load(model, exclude=NOT_USED_PIPES)
            nlp.add_pipe("researchly_paragraphs", before="parser")
            nlp.max_length = MAX_LENGTH
            _NLP = nlp
    return _NLP


# A long document is parsed in pieces of at most this many characters, cut
# at paragraph breaks, and the pieces joined into one parse. One call over
# a whole thesis held the network's working arrays for every token at once:
# 2.5 GB at peak for 120,000 words, whose finished parse needs about 0.1 GB
# (2026-10-15). A document up to this length is parsed in one call, exactly
# as before.
PARSE_PIECE_CHARS = 200_000
_LOWER_CONTINUES = ",;:)(-–—"


def parse_pieces(text: str, limit: Optional[int] = None) -> list:
    """Where a long text is cut for parsing: just before the first
    character of a paragraph that `paragraph_breaks` starts a sentence at
    anyway (after a blank line, not carrying on in lower case), as late as
    the limit allows. A piece with no such break in reach runs on to the
    next one. Returns the (start, end) of each piece; one piece when the
    text is within the limit."""
    limit = limit or PARSE_PIECE_CHARS
    if len(text) <= limit:
        return [(0, len(text))]
    cuts = [m.end() for m in re.finditer(r"\n[ \t]*\n\s*(?=\S)", text)
            if not (text[m.end()].islower()
                    or text[m.end()] in _LOWER_CONTINUES)]
    pieces, start, last = [], 0, None   # last: latest cut within reach
    for cut in cuts:
        if cut - start <= limit:
            last = cut
            continue
        if last is not None:             # cut at the latest break in reach
            pieces.append((start, last))
            start, last = last, None
            if cut - start <= limit:
                last = cut
                continue
        pieces.append((start, cut))      # no break in reach: run on to it
        start = cut
    if len(text) - start > limit and last is not None:
        pieces.append((start, last))
        start = last
    pieces.append((start, len(text)))
    return [p for p in pieces if p[1] > p[0]]


def parse(text: str, nlp=None):
    """THE parse of a masked document. Within PARSE_PIECE_CHARS: one call,
    as it always was. Longer: the pieces of `parse_pieces`, one at a time,
    joined with `Doc.from_docs` into one Doc over the same text (every
    offset, sentence and token as before; each piece starts a sentence, as
    the whole parse does there). Tags, dependencies and lemmas come from
    the same model; within a few tokens of a cut they may differ from a
    whole parse, which reads across the paragraph break
    (tests/test_large_documents.py)."""
    nlp = nlp or get_nlp()
    pieces = parse_pieces(text)
    if len(pieces) == 1:
        return nlp(text)
    from spacy.tokens import Doc
    return Doc.from_docs([nlp(text[a:b]) for a, b in pieces],
                         ensure_whitespace=False)


def paragraph_breaks(doc):
    """A blank line ends a sentence (P33). A Word paragraph, a TeX or
    Markdown paragraph and a masked heading, table or display equation all
    leave one; without this the parser ran title-page lines, table rows and
    the sentence after a heading together into 100-word "sentences".

    Unless the next line carries on in lower case: text from a PDF has a
    blank line at every page break ("about 70% of\n\nall cases"), and a
    sentence resumes after a displayed equation ("...\n\nwhere x is")."""
    for tok in doc[:-1]:
        if tok.is_space and tok.text.count("\n") >= 2:
            nxt = doc[tok.i + 1].text
            if not (nxt[0].islower() or nxt[0] in ",;:)(-\u2013\u2014"):
                doc[tok.i + 1].is_sent_start = True
    return doc


@dataclass
class Analysis:
    """Everything a surface needs from one pass over one document."""
    suggestions: list[Suggestion] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    hidden_preferences: int = 0
    # Document-level suggestions held back by Draft mode: counted, never
    # silently dropped (the hidden-preference pattern).
    hidden_by_mode: int = 0
    # The article-type profile the check ran under (S4) and whether it was
    # guessed from the headings ("auto") or chosen.
    profile: profiles_mod.Profile = profiles_mod.DEFAULT
    profile_guessed: bool = True
    # The headings an Auto guess rested on ("" when chosen or general).
    profile_evidence: str = ""
    # How much of the document this is (Codex review #4): whole, chapter or
    # excerpt, chosen or inferred, separate from the article type.
    scope: profiles_mod.Scope = field(
        default_factory=lambda: profiles_mod.Scope("whole", True))
    # Topical headings read as Methods or Results from their own wording:
    # [{"heading", "section"}] (profiles.infer_topical_sections).
    topical: list = field(default_factory=list)
    # The critical reader's brief (review.py), when asked for.
    review: Optional[dict] = None
    # The narrative map (discourse/narrative.py), when asked for.
    narrative: Optional[dict] = None
    # A reporting checklist (packs/), when asked for; and the one the
    # text's own words point to, always (a cheap pass over the text).
    checklist: Optional[dict] = None
    suggested_checklist: Optional[str] = None
    metrics: Optional[metrics_mod.Metrics] = None
    sections_detected: list = field(default_factory=list)
    health: list = field(default_factory=list)
    config: Config = field(default_factory=Config)
    document: Optional[Document] = None
    # The rules whose findings this check could show (Codex review N2):
    # not muted, not off for the article type, not held back by Draft, not
    # hidden preferences, not on a tier that is down. A rule outside this
    # list was not assessed, which is not the same as zero findings.
    assessed_rules: list = field(default_factory=list)
    # A fingerprint of the engine version and its rule set: two checks are
    # comparable only under the same one.
    ruleset: str = ""

    @property
    def grammar_ok(self) -> bool:
        return any(t.tier == "grammar" and t.ok for t in self.health)

    def to_dict(self) -> dict:
        return {
            "suggestions": [s.to_dict() for s in self.suggestions],
            "counts": self.counts,
            "hidden_preferences": self.hidden_preferences,
            "hidden_by_mode": self.hidden_by_mode,
            "profile": {"id": self.profile.id, "label": self.profile.label,
                        "guessed": self.profile_guessed,
                        "evidence": self.profile_evidence,
                        "note": self.profile.note,
                        "rules_off": sorted(self.profile.rules_off),
                        "scope": {"id": self.scope.id,
                                  "guessed": self.scope.guessed,
                                  "note": self.scope.note},
                        "topical": [dict(t) for t in self.topical]},
            "review": self.review,
            "narrative": self.narrative,
            "checklist": self.checklist,
            "suggested_checklist": self.suggested_checklist,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "sections_detected": list(self.sections_detected),
            "health": [t.to_dict() for t in self.health],
            "config": self.config.to_dict(),
            "assessed_rules": list(self.assessed_rules),
            "ruleset": self.ruleset,
        }


def _scope(rule_id: str) -> str:
    """A rule's scope; findings from outside the registry (none today) are
    treated as sentence-level, so Draft never hides them by accident."""
    r = REGISTRY.get(rule_id)
    return r.scope if r is not None else "sentence"


def ensure_rules_loaded() -> int:
    """Import the rule modules so REGISTRY is populated; return the count.

    Rules register as a side effect of import, and `check()` imports them
    lazily. Anything that reports on the registry BEFORE a first check —
    the Word add-in's /ping and /rules, `researchly rules` — therefore has
    to trigger registration itself, or it reports zero rules on a healthy
    engine.
    """
    from .engine import load_rules
    return load_rules()


def build_document(source: Union[str, Path, Sequence[dict]],
                   kind: str = "plain") -> Document:
    """Document from raw text, a file path, or Word paragraphs."""
    if isinstance(source, Document):
        return source
    if isinstance(source, Path):
        return Document.from_path(source)
    if isinstance(source, str):
        return Document.from_text(source, kind)
    return Document.from_word(list(source))


def analyze(source: Union[str, Path, Sequence[dict], Document],
            *,
            kind: str = "plain",
            nlp=None,
            cfg: Optional[Config] = None,
            near: Optional[Path] = None,
            with_metrics: bool = True,
            with_review: bool = False,
            with_narrative: bool = False,
            checklist: Optional[str] = None,
            document_scope: Optional[str] = None,
            **overrides: Any) -> Analysis:
    """Check one document and return everything the surfaces render.

    `cfg` is the resolved settings; when omitted they are loaded from the
    user config plus any `.researchly.toml` governing `near`. Keyword
    overrides (CLI flags, an HTTP payload) win over both.

    `document_scope` is how much of the document this is ("whole",
    "chapter", "excerpt"; None or "auto" infers it). It is a choice about
    this check, not a setting, so it is never stored.
    """
    if cfg is None:
        near = near if near is not None else (
            source if isinstance(source, Path) else None)
        cfg = config_mod.load(near, **overrides)
    elif overrides:
        cfg = cfg.with_overrides(**overrides)

    document = build_document(source, kind)
    # Rules read settings off the document — the pattern rules_spelling.py has
    # used for `extra_dictionary` since v0.5, which nothing ever populated.
    document.config = cfg
    document.extra_dictionary = list(cfg.dictionary)

    # The article-type profile (S4): checks that do not apply to this kind
    # of document are not run, and unheaded prose gets its section.
    profile, guessed = profiles_mod.resolve(cfg.document_type, document)
    evidence = (profiles_mod.guess_with_evidence(document)[1]
                if guessed else "")
    document.default_section = profile.body_section
    # A topical heading of a research document is read from its own wording
    # (Methods or Results), before any check reads the sections; then the
    # scope, which the headings inform (Codex review #4).
    topical = profiles_mod.infer_topical_sections(document, profile)
    scope = profiles_mod.resolve_scope(document_scope, document, profile)
    disabled = set(cfg.disabled) | set(profile.rules_off)

    # The grammar tier (LT001) reads the masked text, not the parse: start
    # its LanguageTool request now so it runs while spaCy parses. The rule
    # collects it in its usual turn, so nothing about the output changes.
    ensure_rules_loaded()
    if "LT001" in REGISTRY and "LT001" not in disabled:
        from .rules_grammar import start_check
        start_check(document)

    nlp = nlp or get_nlp()

    # THE single parse. Shared by the rules, the metrics and the review.
    spacy_doc = parse(document.masked, nlp)

    # Always check with preferences on so the hidden count is free; filter
    # afterwards. This is what made the second full run unnecessary.
    found = check(document, nlp, disabled=disabled,
                  show_preferences=True, spacy_doc=spacy_doc)
    everything = found
    prefs = sum(1 for s in found if s.category is Category.PREFERENCE)
    if not cfg.show_preferences:
        found = [s for s in found if s.category is not Category.PREFERENCE]
    by_mode = 0
    if cfg.mode == "draft":
        kept = [s for s in found if _scope(s.rule_id) == "sentence"]
        by_mode, found = len(found) - len(kept), kept

    counts: dict = {}
    for s in found:
        counts[s.category.value] = counts.get(s.category.value, 0) + 1

    mets = (metrics_mod.compute(spacy_doc, document)
            if with_metrics or with_review else None)
    review = None
    if with_review:
        from .review import build_review
        review = build_review(document, nlp, suggestions=everything,
                              spacy_doc=spacy_doc, metrics=mets,
                              profile=profile, disabled=cfg.disabled,
                              scope=scope)
    from . import packs
    suggested = packs.suggest(document.masked)
    checked = None
    if checklist:
        cid = suggested if checklist == "auto" else checklist
        if cid:
            checked = packs.check(document, cid, spacy_doc=spacy_doc,
                                  suggested=suggested)
    narrative = None
    if with_narrative:
        from .discourse.narrative import build_narrative
        narrative = build_narrative(document, spacy_doc=spacy_doc,
                                    profile=profile, scope=scope)

    health = engine_status(cfg, nlp=nlp)
    return Analysis(
        assessed_rules=assessed_rules(cfg, disabled, health),
        ruleset=ruleset_id(),
        suggestions=found,
        counts=counts,
        hidden_preferences=0 if cfg.show_preferences else prefs,
        hidden_by_mode=by_mode,
        profile=profile,
        profile_guessed=guessed,
        profile_evidence=evidence,
        scope=scope,
        topical=topical,
        review=review,
        narrative=narrative,
        checklist=checked,
        suggested_checklist=suggested,
        metrics=mets if with_metrics else None,
        sections_detected=sorted({h.section for h in document.headings}),
        health=health,
        config=cfg,
        document=document,
    )


# --- the live check (S4d R3) -------------------------------------------------

# The heading a live paragraph sits under is placed above it as a Word
# heading, so section detection is the full check's own (document.py).
LIVE_HEADING_STYLE = "Heading 1"


@dataclass
class ParagraphResult:
    """One paragraph of a live check. `suggestions` carry code-point
    offsets within the paragraph's own text (UTF-16 is the edge's job,
    researchly.utf16)."""
    id: str
    text: str
    section: str
    suggestions: list[Suggestion] = field(default_factory=list)


@dataclass
class ParagraphCheck:
    """The result of `check_paragraphs()`."""
    paragraphs: list[ParagraphResult] = field(default_factory=list)
    hidden_preferences: int = 0
    health: list = field(default_factory=list)
    config: Config = field(default_factory=Config)
    assessed_rules: list = field(default_factory=list)
    ruleset: str = ""


def live_rule_ids() -> frozenset:
    """The rules the live check runs: those judged from the sentence in
    front of the writer. Document-scope rules (figure order, abbreviations
    defined once, the abstract's moves) need the whole document and stay in
    the full check, with the brief, the map, checklists and read-outs."""
    ensure_rules_loaded()
    return frozenset(r.id for r in REGISTRY.values() if r.scope == "sentence")


def paragraph_document(text: str, style: str = "",
                       heading: str = "") -> tuple[Document, int]:
    """The document a live paragraph is checked as, and where the
    paragraph starts in it: the paragraph under its nearest heading,
    exactly as the full check would read those two Word paragraphs."""
    heading = " ".join((heading or "").split())
    items = []
    if heading:
        items.append({"text": heading, "style": LIVE_HEADING_STYLE})
    items.append({"text": text, "style": style or ""})
    offset = len(heading) + 2 if heading else 0
    return Document.from_word(items), offset


def check_paragraphs(paragraphs: Sequence[dict],
                     *,
                     nlp=None,
                     cfg: Optional[Config] = None,
                     near: Optional[Path] = None,
                     **overrides: Any) -> ParagraphCheck:
    """The live check: a few paragraphs, each in isolation (S4d R3).

    Each item is `{"id", "text", "style"?, "heading"?}`; `heading` is the
    text of the nearest heading above the paragraph, so advice stays
    section-aware without the whole document. A paragraph with no heading
    gets the article type's body section, as unheaded prose does in the
    full check.

    For every paragraph the findings are exactly those `analyze()` gives
    for a document made of the heading and the paragraph, restricted to
    sentence-scope rules and to the paragraph's own text
    (tests/test_live_check.py proves it per section). Masking is the full
    check's: maths, code, citations, URLs and headings are never flagged.

    Cheap for short inputs: every grammar request starts before the parse
    (one LanguageTool request per paragraph, run concurrently), and the
    paragraphs are parsed in one `nlp.pipe` call. Document-wide rules are
    not run at all.
    """
    if cfg is None:
        cfg = config_mod.load(near, **overrides)
    elif overrides:
        cfg = cfg.with_overrides(**overrides)

    live = live_rule_ids()
    not_live = {rid for rid in REGISTRY if rid not in live}
    grammar = "LT001" in live and "LT001" not in cfg.disabled

    prepared = []
    for p in paragraphs:
        text = p.get("text") or ""
        document, offset = paragraph_document(text, p.get("style") or "",
                                              p.get("heading") or "")
        document.config = cfg
        document.extra_dictionary = list(cfg.dictionary)
        profile, _ = profiles_mod.resolve(cfg.document_type, document)
        document.default_section = profile.body_section
        disabled = set(cfg.disabled) | set(profile.rules_off) | not_live
        blank = not text.strip()
        if grammar and not blank and "LT001" not in disabled:
            from .rules_grammar import start_check
            start_check(document)
        prepared.append((p, text, document, offset, disabled, blank))

    nlp = nlp or get_nlp()
    todo = [d for _, _, d, _, _, blank in prepared if not blank]
    parsed = iter(nlp.pipe([d.masked for d in todo]))

    out: list[ParagraphResult] = []
    prefs = 0
    for p, text, document, offset, disabled, blank in prepared:
        section = document.section_at(offset)
        result = ParagraphResult(id=str(p.get("id") or ""), text=text,
                                 section=section)
        out.append(result)
        if blank:
            continue
        found = check(document, nlp, disabled=disabled,
                      show_preferences=True, spacy_doc=next(parsed))
        kept = []
        for s in found:
            if s.start < offset:          # on the heading, not the paragraph
                continue
            if s.category is Category.PREFERENCE:
                prefs += 1
                if not cfg.show_preferences:
                    continue
            s.start -= offset
            s.end -= offset
            s.line, s.col = 0, 0          # a paragraph has no lines of its own
            kept.append(s)
        result.suggestions = kept

    health = engine_status(cfg, nlp=nlp)
    assessed = [rid for rid in assessed_rules(cfg, set(cfg.disabled), health)
                if rid in live]
    return ParagraphCheck(
        paragraphs=out,
        hidden_preferences=0 if cfg.show_preferences else prefs,
        health=health,
        config=cfg,
        assessed_rules=assessed,
        ruleset=ruleset_id(),
    )


def assessed_rules(cfg: Config, disabled: set, health: list) -> list:
    """The rules whose findings a check with these settings could show
    (Codex review N2): the progress view counts a rule outside this list as
    not assessed, never as zero."""
    down = {t.tier for t in health if not t.ok}
    out = []
    for r in REGISTRY.values():
        if r.id in disabled or r.tier in down:
            continue
        if r.category is Category.PREFERENCE and not cfg.show_preferences:
            continue
        if cfg.mode == "draft" and _scope(r.id) != "sentence":
            continue
        out.append(r.id)
    return sorted(out)


_RULESET: Optional[str] = None


def ruleset_id() -> str:
    """A short fingerprint of the engine version and its registered rules:
    checks are compared only under the same one."""
    global _RULESET
    if _RULESET is None:
        import hashlib
        from . import __version__
        ensure_rules_loaded()
        key = __version__ + "|" + ",".join(sorted(REGISTRY))
        _RULESET = __version__ + "+" + hashlib.sha256(
            key.encode()).hexdigest()[:8]
    return _RULESET


def status(cfg: Optional[Config] = None, probe: bool = False
           ) -> list[TierStatus]:
    """Engine health without checking anything — for a surface's status bar."""
    return engine_status(cfg or config_mod.load(), probe=probe)

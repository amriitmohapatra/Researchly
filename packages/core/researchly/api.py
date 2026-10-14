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
            nlp = spacy.load(model)
            nlp.add_pipe("researchly_paragraphs", before="parser")
            nlp.max_length = MAX_LENGTH
            _NLP = nlp
    return _NLP


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
                        "rules_off": sorted(self.profile.rules_off)},
            "review": self.review,
            "narrative": self.narrative,
            "checklist": self.checklist,
            "suggested_checklist": self.suggested_checklist,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "sections_detected": list(self.sections_detected),
            "health": [t.to_dict() for t in self.health],
            "config": self.config.to_dict(),
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
            **overrides: Any) -> Analysis:
    """Check one document and return everything the surfaces render.

    `cfg` is the resolved settings; when omitted they are loaded from the
    user config plus any `.researchly.toml` governing `near`. Keyword
    overrides (CLI flags, an HTTP payload) win over both.
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
    disabled = set(cfg.disabled) | set(profile.rules_off)

    nlp = nlp or get_nlp()

    # THE single parse. Shared by the rules, the metrics and the review.
    spacy_doc = nlp(document.masked)

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
                              profile=profile, disabled=cfg.disabled)
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
                                    profile=profile)

    return Analysis(
        suggestions=found,
        counts=counts,
        hidden_preferences=0 if cfg.show_preferences else prefs,
        hidden_by_mode=by_mode,
        profile=profile,
        profile_guessed=guessed,
        profile_evidence=evidence,
        review=review,
        narrative=narrative,
        checklist=checked,
        suggested_checklist=suggested,
        metrics=mets if with_metrics else None,
        sections_detected=sorted({h.section for h in document.headings}),
        health=engine_status(cfg, nlp=nlp),
        config=cfg,
        document=document,
    )


# --- word prediction (2026-10-14) ---------------------------------------------

# LaTeX commands whose argument is prose; any other command's argument
# (\cite{, \ref{, \label{, \begin{, \url{ ...) is not.
_PROSE_COMMANDS = frozenset({
    "emph", "textbf", "textit", "textsl", "textsc", "text", "underline",
    "footnote", "caption", "section", "subsection", "subsubsection",
    "paragraph", "subparagraph", "chapter", "part", "title", "item",
    "mbox", "textrm", "textsf", "enquote"})
_OPEN_ARG = re.compile(r"\\([A-Za-z@]+)\*?(?:\[[^\]]*\])?\{[^{}]*$")
_URLISH = re.compile(r"(?:://|www\.|@)\S*$")
COMPLETE_WINDOW = 50_000      # characters of a long document read around


@dataclass
class Completion:
    """What `complete()` returns. `status` says why there is nothing when
    there is nothing: "ok", "off" (the writer turned prediction off),
    "masked" (the cursor is in maths, code, a citation or a URL) or
    "unavailable" (no model; health.py says why)."""
    candidates: list = field(default_factory=list)
    status: str = "ok"

    def to_dict(self) -> dict:
        return {"candidates": [c.to_dict() for c in self.candidates],
                "status": self.status}


def _in_unfinished_markup(before: str, kind: str) -> bool:
    """The cursor is inside something still being typed that the masker
    cannot see yet: an unclosed $...$, a citation key, a code span."""
    para = before[before.rfind("\n\n") + 1:]
    if _URLISH.search(para):
        return True
    if kind in ("latex", "markdown"):
        dollars = len(re.findall(r"(?<!\\)\$", para))
        if dollars % 2:
            return True
    if kind == "latex":
        if re.search(r"\\[A-Za-z@]*$", para):
            return True             # a command name being typed
        m = _OPEN_ARG.search(para)
        if m and m.group(1) not in _PROSE_COMMANDS:
            return True
    if kind == "markdown":
        if before.count("```") % 2 or para.count("`") % 2:
            return True
        if re.search(r"\]\([^)]*$", para):
            return True             # a link target
    return False


def complete(text: str, cursor: Optional[int] = None, *,
             kind: str = "plain",
             cfg: Optional[Config] = None,
             near: Optional[Path] = None,
             limit: int = 3,
             **overrides: Any) -> Completion:
    """Word prediction at `cursor` (default: the end of `text`).

    Offers the end of the word being typed, or the next word or short
    fixed term, ranked by how often published scientific prose continues
    this way (researchly/predict.py). Never inserts anything: a surface
    shows the candidates and replaces `[start, end)` with one only when the
    writer accepts it. Nothing is offered inside masked material (maths,
    code, citations, URLs, headings) or when the writer has turned
    prediction off. The text is read in memory and kept nowhere.
    """
    from . import predict as predict_mod

    if cfg is None:
        cfg = config_mod.load(near, **overrides)
    elif overrides:
        cfg = cfg.with_overrides(**overrides)
    if not cfg.prediction:
        return Completion(status="off")
    cursor = len(text) if cursor is None else max(0, min(cursor, len(text)))

    # A long document is read around the cursor, from a paragraph break.
    lo = 0
    if cursor > COMPLETE_WINDOW:
        lo = text.rfind("\n\n", 0, cursor - COMPLETE_WINDOW)
        lo = 0 if lo < 0 else lo
    hi = text.find("\n\n", cursor)
    hi = len(text) if hi < 0 else hi
    window = text[lo:hi]
    at = cursor - lo
    before = window[:at]
    if _in_unfinished_markup(before, kind):
        return Completion(status="masked")
    document = Document.from_text(window, kind)
    word_start = at - len(re.search(r"[A-Za-z'\-]*$", before).group(0))
    check_from = word_start if word_start < at else max(0, at - 1)
    if at and document.masked[check_from:at] != window[check_from:at]:
        return Completion(status="masked")
    # Masked atoms (citations, inline maths) break the context: the words
    # either side of "[12]" are not a sequence.
    chars = list(before)
    for a, b in document.atoms:
        if a < at:
            for i in range(a, min(b, at)):
                chars[i] = "\n"
    context = "".join(chars)
    model = predict_mod.get_model()
    if model is None:
        return Completion(status="unavailable")
    found = predict_mod.complete(context, cursor,
                                 spelling_choice=cfg.spelling, limit=limit,
                                 model=model)
    return Completion(candidates=found)


def status(cfg: Optional[Config] = None, probe: bool = False
           ) -> list[TierStatus]:
    """Engine health without checking anything — for a surface's status bar."""
    return engine_status(cfg or config_mod.load(), probe=probe)

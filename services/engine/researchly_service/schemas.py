"""API contract v1 (ARCHITECTURE.md §7).

These models ARE the contract: FastAPI turns them into the OpenAPI document
(`packages/contract/openapi.json`), and the web app's and add-in's
TypeScript types are generated from that. Change a field here and CI's
contract-drift check fails until the generated files are regenerated, so a
surface can never silently disagree with the engine about a shape.

Python 3.10 compatible (the owner's interpreter): `Optional[...]`, not `X | None`
inside pydantic field annotations evaluated at runtime.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1"

# A 150k-word thesis is ~1M characters. The engine's spaCy cap is 1.2M
# (packages/core/researchly/api.py MAX_LENGTH); stay under it so the limit a
# user meets is ours, with our message, not spaCy's.
MAX_CONTENT_CHARS = 1_000_000


class Format(str, Enum):
    """Formats of pasted `content`. Files (.docx, .tex, Overleaf .zip, …) go
    to /v1/analyze-file instead; `word_paragraphs` arrives with the hosted
    add-in (S3)."""
    plain = "plain"
    markdown = "markdown"
    latex = "latex"


class Mode(str, Enum):
    """Draft / Revise (P1). Draft shows sentence-level checks only; Revise
    shows everything. A writing stage, not a quality dial."""
    draft = "draft"
    revise = "revise"


class DocumentType(str, Enum):
    """Article-type profile (S4). `auto` guesses from the headings and is
    otherwise `general`; the others switch off the checks that do not
    apply to that kind of document and say what section unheaded prose is
    in (a commentary is argued like a Discussion)."""
    auto = "auto"
    general = "general"
    manuscript = "manuscript"
    thesis_chapter = "thesis-chapter"
    abstract = "abstract"
    commentary = "commentary"
    policy_brief = "policy-brief"
    grant = "grant"
    response_to_reviewers = "response-to-reviewers"


class Scope(str, Enum):
    """What a rule needs to judge: the sentence, or the whole document
    (figure citations, abbreviations defined once). Draft hides `document`."""
    sentence = "sentence"
    document = "document"


class Category(str, Enum):
    """The four-type taxonomy (CLAUDE.md #3). Conventions are never errors;
    preferences are hidden unless asked for."""
    correction = "correction"
    improvement = "improvement"
    convention = "convention"
    preference = "preference"


class FixSafety(str, Enum):
    safe = "safe"        # may be bulk-applied unread (pinned to transform.POLISH_RULES)
    review = "review"    # a judgement call; apply one at a time


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- request ---------------------------------------------------------------

class AnalyzeOptions(_Strict):
    show_preferences: bool = Field(
        False, description="Include Preference-type suggestions (hidden by default).")
    disabled_rules: List[str] = Field(
        default_factory=list, max_length=200,
        description="Rule ids to mute for this request, e.g. [\"G101\"]. "
                    "For a signed-in caller these are added to the rules "
                    "muted in their account settings.")
    mode: Optional[Mode] = Field(
        None, description="Draft or Revise for this request. Omitted: the "
                          "caller's saved setting, else revise.")
    document_type: Optional[DocumentType] = Field(
        None, description="The article type to check as. Omitted: the "
                          "caller's saved setting, else auto.")
    review: bool = Field(
        False, description="Also build the critical reader's brief "
                           "(`review` in the response) from the same analysis.")


class AnalyzeRequest(_Strict):
    format: Format = Field(Format.plain, description="How to read `content`.")
    content: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS,
                         description="The document text. Held in memory for "
                                     "this request only; never stored or logged.")
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)


MAX_WORD_PARAGRAPHS = 50_000


class WordParagraph(_Strict):
    """One paragraph as Office JS reports it (`body.paragraphs`)."""
    text: str = Field("", max_length=MAX_CONTENT_CHARS)
    style: str = Field("", max_length=200, description="Word style name, "
                       "e.g. \"Heading 1\", \"Caption\", \"Normal\".")
    kind: Literal["body", "table"] = Field(
        "body", description="table: a table cell's paragraph (not prose).")


class AnalyzeWordRequest(_Strict):
    paragraphs: List[WordParagraph] = Field(
        ..., min_length=1, max_length=MAX_WORD_PARAGRAPHS,
        description="The document's paragraphs in order. Held in memory for "
                    "this request only; never stored or logged.")
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)

    @model_validator(mode="after")
    def _size(self) -> "AnalyzeWordRequest":
        total = sum(len(p.text) + 2 for p in self.paragraphs)
        if total > MAX_CONTENT_CHARS:
            raise ValueError(f"the document is longer than "
                             f"{MAX_CONTENT_CHARS:,} characters")
        return self


# --- response --------------------------------------------------------------

class Span(_Strict):
    start: int = Field(..., ge=0, description="Offset into `content` in Unicode code points "
                                              "(Python str indices, NOT UTF-16 units), inclusive.")
    end: int = Field(..., ge=0, description="Offset into `content` in Unicode code points, exclusive.")
    line: int = Field(..., ge=0, description="1-based line of `start`; 0 if unknown.")
    col: int = Field(..., ge=0, description="1-based column of `start`; 0 if unknown.")


class Suggestion(_Strict):
    id: str = Field(..., description="Stable fingerprint of (rule_id, start, end, text); "
                                     "used by /v1/feedback in S2.")
    rule_id: str
    rule_name: str
    category: Category
    tier: str = Field(..., description="spelling | grammar | gec | craft | lens — "
                                       "which engine produced it.")
    span: Span
    text: str = Field(..., description="The flagged source text, content[start:end].")
    section: str = Field(..., description="Detected section, e.g. methods, discussion, unknown.")
    message: str = Field(..., description="One-line rationale, always shown.")
    why: str = Field(..., description="The teachable explanation.")
    plain: str = Field("", description="The explanation in everyday words, "
                       "shown first; `why` is the fuller account.")
    source: str = Field(..., description="Named provenance of the advice (CLAUDE.md #6).")
    learn_ref: Optional[str] = Field(None, description="Lesson id; Learn cards arrive in S4.")
    replacement: Optional[str] = Field(
        None, description="A concrete fix, only from deterministic rules or a "
                          "≤40-char learned edit. Never generated prose.")
    fix_safety: FixSafety
    confidence: float = Field(..., ge=0.0, le=1.0)


class Metrics(_Strict):
    """Read-outs, never a score (metrics.py)."""
    sentences: int
    words: int
    mean_sentence_len: float
    long_sentences: int
    nominalizations_per_100w: float
    hedges_per_100w: float
    boosters_per_100w: float
    self_mention_per_100w: float
    hedge_booster_balance: Optional[str] = None
    passive_share_by_section: Dict[str, float] = Field(
        default_factory=dict,
        description="Share of clauses in the passive voice per section, as a fraction 0-1.")


class TierHealth(_Strict):
    tier: str = Field(..., description="parser | spelling | grammar | gec | files | account "
                                       "(files: the LaTeX/.docx readers, shown only "
                                       "when one is missing; account: whether a "
                                       "signed-in caller's settings could be loaded)")
    label: str
    ok: bool = Field(..., description="Is this tier contributing suggestions right now?")
    state: str = Field(..., description="ready | missing | disabled | error | unstarted")
    detail: str = ""
    remedy: str = ""


class EngineInfo(_Strict):
    service_version: str
    core_version: str
    rules_loaded: int


class ProfileInfo(_Strict):
    """The article-type profile a check ran under."""
    id: DocumentType
    label: str
    guessed: bool = Field(..., description="True when the type was `auto` "
                          "and guessed from the headings.")
    note: str = Field("", description="One line saying what the profile "
                      "switched off, empty when nothing.")
    rules_off: List[str] = Field(default_factory=list,
                                 description="Rules not run for this type.")


class ReviewQuestion(_Strict):
    id: str = Field(..., description="A to E.")
    question: str
    verdict: str = Field(..., description="One line answering the question "
                         "from the evidence.")
    points: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list,
                                description="Sentences of the document the "
                                "verdict rests on (never logged).")


class ReviewRuleCount(_Strict):
    id: str
    short: str
    count: int = Field(..., ge=0)


class ReviewReport(_Strict):
    """The critical reader's brief: five questions answered from the same
    deterministic analysis as the suggestions."""
    source: str
    sections: List[str]
    words: int = Field(..., ge=0)
    questions: List[ReviewQuestion]
    top_rules: List[ReviewRuleCount] = Field(default_factory=list)


class AnalyzeResponse(_Strict):
    schema_version: Literal["1"] = SCHEMA_VERSION
    mode: Mode = Field(Mode.revise, description="The mode this check ran in.")
    profile: ProfileInfo = Field(
        default_factory=lambda: ProfileInfo(id=DocumentType.general,
                                            label="General", guessed=True),
        description="The article-type profile this check ran under.")
    review: Optional[ReviewReport] = Field(
        None, description="Present when `options.review` was true.")
    hidden_by_mode: int = Field(0, ge=0, description="Document-level "
                                "suggestions Draft mode held back (0 in Revise).")
    signed_in: bool = Field(False, description="True when a valid account token "
                            "came with the request and its settings were looked up.")
    suggestions: List[Suggestion]
    counts: Dict[str, int] = Field(..., description="Shown suggestions per category.")
    hidden_preferences: int = Field(..., ge=0)
    metrics: Optional[Metrics] = None
    sections_detected: List[str]
    health: List[TierHealth] = Field(..., description="Every surface must show a "
                                     "degraded tier (CLAUDE.md: no silent tiers).")
    engine: EngineInfo
    elapsed_ms: int = Field(..., ge=0)
    warnings: List[str] = Field(
        default_factory=list,
        description="What was skipped or approximated while reading the text, "
                    "e.g. LaTeX that could not be parsed and was read with a "
                    "simpler method. May quote the caller's own text; never "
                    "logged.")


class WordLocation(_Strict):
    """How the add-in finds a suggestion in Word, which has no offsets:
    search `paragraph` for `snippet` and take match number `occurrence`."""
    paragraph: int = Field(..., ge=0, description="Index into the request's paragraphs.")
    start: int = Field(..., ge=0, description="Offset in that paragraph's text (code points).")
    end: int = Field(..., ge=0)
    snippet: str = Field(..., description="The text to search for.")
    occurrence: int = Field(..., ge=0, description="0-based match number within the paragraph.")
    exact: bool = Field(..., description="False when the span is too long or "
                        "unsafe to search for whole; `snippet` is then a prefix.")


class WordSuggestion(Suggestion):
    location: WordLocation


class Coverage(_Strict):
    """What was and was not read, stated plainly."""
    paragraphs: int = Field(..., ge=0)
    table_paragraphs: int = Field(..., ge=0)
    not_checked: List[str] = Field(..., description="Parts of a Word document "
                                   "Office JS does not hand over, e.g. footnotes.")


class AnalyzeWordResponse(AnalyzeResponse):
    suggestions: List[WordSuggestion]
    coverage: Coverage


class SourceFormat(str, Enum):
    """How an uploaded file was read."""
    latex = "latex"
    docx = "docx"
    markdown = "markdown"
    plain = "plain"


class Segment(_Strict):
    """A stretch of `document.text` that came from one source file.
    `text[start:end]` equals that file's `[source_start : source_start + (end - start)]`."""
    path: str = Field(..., description="Path inside the upload, e.g. sections/methods.tex.")
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)
    source_start: int = Field(..., ge=0, description="Offset in the source file, in code points.")


class StructureItem(_Strict):
    """A figure, table, equation, caption or citation found in the source.
    Kept as structure for the consistency and cross-reference checks (S2b)."""
    kind: Literal["figure", "table", "equation", "caption", "citation"]
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)
    label: Optional[str] = Field(None, description="\\label key or Word bookmark, if any.")


class SourceInfo(_Strict):
    filename: str = Field(..., description="Echoed back to the caller; never logged.")
    format: SourceFormat
    text: str = Field(..., description="The text suggestions' spans index into: the "
                                       "source itself for .tex/.md/.txt, the "
                                       "expanded project for a .zip, the "
                                       "extracted paragraphs for .docx.")
    segments: List[Segment]
    structure: List[StructureItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list,
                                description="Things skipped or approximated while "
                                            "reading the file; never document text.")


class AnalyzeFileResponse(AnalyzeResponse):
    document: SourceInfo


class HealthResponse(_Strict):
    status: Literal["ok", "degraded"] = Field(
        ..., description="degraded when any tier the service is configured to "
                         "run is not ok.")
    tiers: List[TierHealth]
    engine: EngineInfo


class RuleInfo(_Strict):
    id: str
    name: str
    category: Category
    short: str
    why: str
    plain: str = ""
    source: str
    tier: str
    fix_safety: FixSafety
    scope: Scope = Field(Scope.sentence, description="Draft mode shows "
                         "sentence-level rules only.")
    sections_only: Optional[List[str]] = None
    sections_excluded: Optional[List[str]] = None


class ProfileChoice(_Strict):
    id: DocumentType
    label: str
    summary: str


class RulesResponse(_Strict):
    rules: List[RuleInfo]
    profiles: List[ProfileChoice] = Field(
        default_factory=list, description="Article types a caller can "
        "check as, in display order (S4).")


class ErrorBody(_Strict):
    """Every non-2xx response. `code` is stable and machine-readable;
    `message` is for people and never contains document text."""
    code: str = Field(..., description="One of: invalid_request, malformed_json, "
                                       "malformed_request, payload_too_large, "
                                       "unsupported_media_type, "
                                       "unsupported_file, unreadable_file, "
                                       "unauthorized, sign_in_required, "
                                       "auth_unavailable, "
                                       "rate_limited, not_found, "
                                       "method_not_allowed, internal, or "
                                       "http_error for any other HTTP status")
    message: str
    request_id: str = Field(..., description="Quote this when reporting a problem.")


class ErrorResponse(_Strict):
    error: ErrorBody

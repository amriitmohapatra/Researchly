"""Article-type profiles (S4; owner request 2026-10-08).

The engine is section-aware: the same sentence gets different advice in
Methods and in Discussion. A profile says what KIND of document the
sections belong to, and so

- what the reader of the whole document expects to find (`expected`:
  the review lens asks for a limitations section in a research article,
  never in a commentary);
- which checks do not apply (`rules_off`, each with its reason: a
  commentary has no abstract to judge, and may argue assertively where a
  research paper must hedge);
- what "section" the prose is in when the document has no IMRaD headings
  (`body_section`: a commentary's body reads like a Discussion, so passive
  voice is flagged and the claim prompts run; a pasted abstract is an
  abstract).

The format is open: a new type is one more entry in PROFILES, and the
first two beyond the research article are the owner's own field, public
health (commentary, policy brief). "auto" guesses only from strong signals
(IMRaD headings, a chapter, a recommendations heading) and otherwise
checks as "general", which is the engine's long-standing behaviour.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Optional


@dataclass(frozen=True)
class Profile:
    id: str
    label: str
    summary: str
    # Sections a sceptical reader of this type expects (review lens).
    expected: tuple = ()
    # Section assigned to text that has no IMRaD heading over it
    # ("unknown", "front", "other"); None keeps the engine's default.
    body_section: Optional[str] = None
    # rule id -> why it does not apply to this type.
    rules_off: Mapping[str, str] = field(default_factory=dict)
    abstract_expected: bool = True
    limitations_expected: bool = True
    gap_expected: bool = True

    @property
    def note(self) -> str:
        """One line for the surfaces: what this profile changes."""
        if not self.rules_off:
            return ""
        reasons = sorted(set(self.rules_off.values()))
        return "Checked as " + _article(self.label) + ": " + "; ".join(reasons) + "."


def _article(label: str) -> str:
    return ("an " if label[0].lower() in "aeiou" else "a ") + label.lower()


# The reasons are user-visible (CLAUDE.md #6: plain words, no internals).
_NO_ABSTRACT = "there is no abstract to judge"
_NO_GAP = "no research gap is expected"
_ASSERTIVE = "it may argue assertively, so the hedging prompts are off"
_NO_FLOATS = "figures and tables belong to the manuscript it answers"

_RESEARCH = ("introduction", "methods", "results", "discussion")

PROFILES: dict = {p.id: p for p in (
    Profile("auto", "Auto", "Guess from the headings; otherwise general."),
    Profile("general", "General",
            "Any research prose: every check on, sections from the "
            "headings."),
    Profile("manuscript", "Research article",
            "A journal article with introduction, methods, results and "
            "discussion.",
            expected=("abstract",) + _RESEARCH),
    Profile("thesis-chapter", "Thesis chapter",
            "One chapter of a thesis; sections as the chapter has them.",
            expected=_RESEARCH, abstract_expected=False),
    Profile("abstract", "Abstract",
            "An abstract on its own: the six-move check runs on the whole "
            "text.",
            expected=("abstract",), body_section="abstract",
            limitations_expected=False),
    Profile("commentary", "Commentary",
            "An opinion or perspective piece: argued, not reported.",
            expected=("introduction", "discussion", "conclusion"),
            body_section="discussion",
            rules_off={"AB801": _NO_ABSTRACT, "AB802": _NO_ABSTRACT,
                       "D902": _NO_GAP, "D903": _NO_GAP, "C302": _ASSERTIVE,
                       "C303": _ASSERTIVE},
            abstract_expected=False, limitations_expected=False,
            gap_expected=False),
    Profile("policy-brief", "Policy brief",
            "Evidence for decision-makers: context, evidence, options, "
            "recommendations.",
            expected=("introduction", "discussion", "conclusion"),
            body_section="discussion",
            rules_off={"AB801": _NO_ABSTRACT, "AB802": _NO_ABSTRACT,
                       "D902": _NO_GAP, "D903": _NO_GAP, "C302": _ASSERTIVE,
                       "C303": _ASSERTIVE},
            abstract_expected=False, limitations_expected=False,
            gap_expected=False),
    Profile("grant", "Grant proposal",
            "Aims, background and approach for a funder.",
            expected=("introduction", "methods"),
            rules_off={"AB802": _NO_ABSTRACT},
            abstract_expected=False, limitations_expected=False),
    Profile("response-to-reviewers", "Response to reviewers",
            "Point-by-point replies; the manuscript's own checks do not "
            "apply.",
            expected=(),
            rules_off={"AB801": _NO_ABSTRACT, "AB802": _NO_ABSTRACT,
                       "D902": _NO_GAP, "D903": _NO_GAP, "X101": _NO_FLOATS,
                       "X102": _NO_FLOATS, "X103": _NO_FLOATS,
                       "X104": _NO_FLOATS},
            abstract_expected=False, limitations_expected=False,
            gap_expected=False),
)}

DOCUMENT_TYPES = tuple(PROFILES)
DEFAULT = PROFILES["general"]

_POLICY_HEADING = re.compile(
    r"\b(?:recommendations?|policy (?:options?|implications?|responses?)|"
    r"key messages?|calls? to action|options? for (?:policy|action))\b",
    re.IGNORECASE)
_POLICY_LINE = re.compile(
    r"^[ \t]*(?:\d+[.)]?[ \t]+)?(?:key messages?|recommendations?|policy "
    r"(?:options?|implications?|recommendations?))[ \t]*$",
    re.IGNORECASE | re.MULTILINE)


def guess_with_evidence(document) -> tuple:
    """(type, evidence): the type the headings make plain, and the headings
    that decided it; ("general", "") when nothing is plain.

    Never guesses "abstract" or "commentary": a pasted paragraph must not be
    judged as an abstract, and an opinion piece looks like any other prose.
    A research structure wins over a policy heading (Codex review R2): an
    article with Methods and Results and a closing "Recommendations"
    section is still a research article, and guessing a policy brief from
    one ancillary heading would switch off checks it needs. A guess may
    only weaken the checks when nothing points the other way.
    """
    heads = document.headings
    sections = {h.section for h in heads}
    research = {"methods", "results"} <= sections

    def named(*kinds):
        return ", ".join(h.text.strip() for h in heads
                         if h.section in kinds)[:120]

    if any(h.level == 0 for h in heads) and "methods" in sections:
        chapter = next(h.text.strip() for h in heads if h.level == 0)
        return "thesis-chapter", f"{chapter}; {named('methods')}"[:160]
    if research:
        return "manuscript", named("methods", "results")
    policy = [h.text.strip() for h in heads if _POLICY_HEADING.search(h.text)]
    if not policy and document.kind == "plain":
        # Plain text records only IMRaD headings; a "Recommendations" line
        # of its own is the signal here.
        policy = [m.group().strip()
                  for m in _POLICY_LINE.finditer(document.original)]
    if "methods" not in sections:
        # A response letter: two or more reviewer comments, at least one
        # with a reply under it (Codex review #4). Checked before the policy
        # headings: a letter may quote a "Recommendations" heading.
        from .discourse.units import reviewer_units
        found = reviewer_units(document)
        if len(found) >= 2 and any(u["reply_span"] for u in found):
            return ("response-to-reviewers",
                    ", ".join(u["label"] for u in found[:3])[:120])
    if policy and "methods" not in sections:
        return "policy-brief", ", ".join(policy)[:120]
    return "general", ""


def guess(document) -> str:
    return guess_with_evidence(document)[0]


def resolve(document_type: Optional[str], document=None) -> tuple:
    """(profile, guessed): the profile for a configured type, guessing from
    the document for "auto"; an unknown type is "general". The explicit
    choice is authoritative."""
    key = document_type or "auto"
    if key == "auto":
        return PROFILES[guess(document)] if document is not None else DEFAULT, True
    return PROFILES.get(key, DEFAULT), False


def listing() -> list:
    """For a selector: every type a user can pick, in display order."""
    return [{"id": p.id, "label": p.label, "summary": p.summary}
            for p in PROFILES.values()]


# --- scope: how much of the document this is (Codex review #4) ---------------
#
# The article type says what KIND of document the text belongs to; the
# scope says how much of it was handed over. A Methods section pasted on its
# own is a research article's excerpt, not a research article missing its
# Introduction; one chapter of a thesis has no abstract of its own. The two
# are separate choices: "auto" infers the scope from the headings, and the
# surfaces say what was assumed, with an override beside the brief and the
# map.

SCOPES = ("auto", "whole", "chapter", "excerpt")
SCOPE_LABELS = {"whole": "Whole document", "chapter": "Chapter",
                "excerpt": "Excerpt"}
# Types whose sections are a research paper's, so a lone section is an
# excerpt and a topical heading may be read from its wording.
RESEARCH_TYPES = frozenset({"general", "manuscript", "thesis-chapter",
                            "grant"})
_MAIN = ("abstract", "introduction", "methods", "results", "discussion",
         "limitations", "conclusion")
_NAMES = {"abstract": "Abstract", "introduction": "Introduction",
          "methods": "Methods", "results": "Results",
          "discussion": "Discussion", "limitations": "Limitations",
          "conclusion": "Conclusion"}
_CHAPTER = re.compile(r"^\s*chapter\s+(?:\d+|[ivxlc]+|one|two|three|four|"
                      r"five|six|seven|eight|nine|ten)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Scope:
    id: str              # whole | chapter | excerpt
    guessed: bool
    reason: str = ""     # plain words: what an inferred scope rests on

    @property
    def label(self) -> str:
        return SCOPE_LABELS[self.id]

    @property
    def note(self) -> str:
        """One line for the surfaces: what was assumed, and what it does."""
        how = (f" ({self.reason})" if self.guessed and self.reason
               else "" if self.guessed else ", as you chose")
        if self.id == "excerpt":
            return (f"Read as an excerpt{how}: sections that are not in it "
                    "are not asked for.")
        if self.id == "chapter":
            return (f"Read as a chapter{how}: no abstract is asked for, and "
                    "each section is read where it stands.")
        return (f"Read as a whole document{how}: the sections a reader of "
                "this kind of document expects are asked for.")


def _short(text: str, n: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def resolve_scope(choice: Optional[str], document, profile: Profile) -> Scope:
    """The scope a check runs under. An explicit choice wins; "auto" (or
    nothing) infers it:

    - a thesis chapter, or a document that opens a chapter (a LaTeX
      \\chapter, a "Chapter 3" heading), is a chapter;
    - research prose with no section headings, or with only one kind of
      section (a Methods section and its subsections), is an excerpt;
    - anything else is the whole document. A commentary or policy brief
      without headings is a whole piece, read as one.
    """
    if choice in ("whole", "chapter", "excerpt"):
        return Scope(choice, False)
    heads = list(getattr(document, "headings", []) or []) if document else []
    if profile.id == "thesis-chapter":
        return Scope("chapter", True, "checked as a thesis chapter")
    chapter = next((h for h in heads if h.level == 0
                    or _CHAPTER.match(h.text)), None)
    if chapter is not None:
        return Scope("chapter", True,
                     f"it opens a chapter, “{_short(chapter.text)}”")
    if profile.id in RESEARCH_TYPES and document is not None:
        kinds = []
        for h in sorted(heads, key=lambda h: h.start):
            if h.section in _MAIN and h.section not in kinds:
                kinds.append(h.section)
        if not heads:
            return Scope("excerpt", True, "it has no section headings")
        if len(kinds) == 1:
            return Scope("excerpt", True,
                         f"its only section is {_NAMES[kinds[0]]}")
        if len(kinds) > 1:
            return Scope("whole", True,
                         "its headings: " + ", ".join(_NAMES[k]
                                                      for k in kinds))
    return Scope("whole", True)


def topical_sections(document) -> list:
    """Headings that name no section and were not read as one: a topical
    title ("Transmission in Oldmere") at the top of its own subtree."""
    return [h for h in getattr(document, "headings", []) or []
            if h.section == "other" and h.level is not None and h.level > 0]


def expected_sections(profile: Profile, scope: Scope, document=None) -> tuple:
    """The sections a reader of this kind of document, at this scope,
    expects to find. An excerpt is asked for none; a chapter for no
    abstract. Where the document's own sections are topical ("Experiment
    1", "A model of measles"), its Methods and Results may stand under
    other names, so neither is asked for by name."""
    if scope.id == "excerpt":
        return ()
    expected = tuple(profile.expected)
    if scope.id == "chapter":
        expected = tuple(s for s in expected if s != "abstract")
    if document is not None and topical_sections(document):
        expected = tuple(s for s in expected if s not in ("methods",
                                                          "results"))
    return expected


def limitations_expected(profile: Profile, scope: Scope) -> bool:
    return profile.limitations_expected and scope.id != "excerpt"


# --- topical headings (PLAN: the owner's first real .tex upload) -------------
#
# "Experiment 1: the baseline SEIR" names no section, so its prose used to be
# "other" and got the advice meant for argued text (passive voice flagged as
# if in the Discussion). For a research type, a topical heading whose prose
# plainly reports (what was done, what was found) and plainly does not argue
# is read as Methods or Results. Only those two: reading a section as an
# Introduction or Discussion would switch on checks the writer did not ask
# for, so an argued or mixed section stays as it was (precision over
# recall). Nested headings inherit as they do under a named section.

_SPLIT = re.compile(r"(?<=[.!?])\s+")
_ARGUING = frozenset({"claim", "warrant", "implication", "limitation",
                      "rebuttal", "contribution"})


def _role_from_cues(text: str) -> Optional[str]:
    from .discourse import moves as moves_mod
    from .discourse.argument import label_sentence
    method_rx = moves_mod._DATA + moves_mod._ANALYSIS
    method = result = arguing = total = 0
    for sent in _SPLIT.split(text):
        sent = " ".join(sent.split())
        if len(sent.split()) < 4:
            continue
        total += 1
        roles = set(label_sentence(sent)[2])
        is_method = "method" in roles or any(
            re.search(rx, sent, re.IGNORECASE) for rx in method_rx)
        is_result = "result" in roles
        if roles & _ARGUING:
            arguing += 1
        elif is_method and not is_result:
            method += 1
        elif is_result:
            result += 1
    reporting = method + result
    if reporting < 2 or reporting < 2 * arguing or reporting * 5 < total * 2:
        return None
    return "methods" if method >= result else "results"


def infer_topical_sections(document, profile: Profile) -> list:
    """Read each topical heading of a research document from its own
    prose (see above); returns [{"heading", "section"}] for those read,
    after nested headings have inherited. Changes nothing for other types,
    for plain text (whose headings are only the named ones) or when the
    wording is mixed."""
    if profile.id not in RESEARCH_TYPES:
        return []
    heads = sorted(getattr(document, "headings", []) or [],
                   key=lambda h: h.start)
    changed = []
    for i, h in enumerate(heads):
        if h.section != "other" or h.level is None or h.level <= 0:
            continue
        end = next((g.start for g in heads[i + 1:]
                    if g.level is None or g.level <= h.level),
                   len(document.masked))
        role = _role_from_cues(document.masked[h.start:end])
        if role:
            h.inferred = role
            changed.append(h)
    if not changed:
        return []
    from .document import resolve_sections
    resolve_sections(document.headings)
    return [{"heading": _short(h.text, 80), "section": h.section}
            for h in changed]

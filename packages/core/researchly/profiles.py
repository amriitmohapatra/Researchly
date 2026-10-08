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
                       "D902": _NO_GAP, "C302": _ASSERTIVE,
                       "C303": _ASSERTIVE},
            abstract_expected=False, limitations_expected=False,
            gap_expected=False),
    Profile("policy-brief", "Policy brief",
            "Evidence for decision-makers: context, evidence, options, "
            "recommendations.",
            expected=("abstract", "introduction", "discussion",
                      "conclusion"),
            body_section="discussion",
            rules_off={"AB801": _NO_ABSTRACT, "AB802": _NO_ABSTRACT,
                       "D902": _NO_GAP, "C302": _ASSERTIVE,
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
                       "D902": _NO_GAP, "X101": _NO_FLOATS,
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


def guess(document) -> str:
    """The type the headings make plain, else "general". Never guesses
    "abstract" or "commentary": a pasted paragraph must not be judged as
    an abstract, and an opinion piece looks like any other prose."""
    heads = document.headings
    if any(_POLICY_HEADING.search(h.text) for h in heads):
        return "policy-brief"
    if document.kind == "plain" and _POLICY_LINE.search(document.original):
        # Plain text records only IMRaD headings; a "Recommendations" line
        # of its own is the signal here.
        return "policy-brief"
    sections = {h.section for h in heads}
    if any(h.level == 0 for h in heads) and "methods" in sections:
        return "thesis-chapter"
    if {"methods", "results"} <= sections:
        return "manuscript"
    return "general"


def resolve(document_type: Optional[str], document=None) -> tuple:
    """(profile, guessed): the profile for a configured type, guessing from
    the document for "auto"; an unknown type is "general"."""
    key = document_type or "auto"
    if key == "auto":
        return PROFILES[guess(document)] if document is not None else DEFAULT, True
    return PROFILES.get(key, DEFAULT), False


def listing() -> list:
    """For a selector: every type a user can pick, in display order."""
    return [{"id": p.id, "label": p.label, "summary": p.summary}
            for p in PROFILES.values()]

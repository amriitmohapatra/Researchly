"""Discipline packs (S4, product decision P3): the reporting checklists of
a field, checked against the text.

A pack checks *reporting*, never the science: for each item of a published
reporting guideline it asks whether the text says the thing a reader of
that kind of study needs (the eligibility criteria, the forecast horizon,
how missing data were handled), and points to the sentence where it does.
It cannot tell whether the design was right, only whether it was reported.

Format: a `Pack` holds `Checklist`s; a checklist holds `Item`s. Each item
is an authored question in Researchly's own words (the guidelines are
cited, never quoted), a plain reason, the sections where readers look for
it, and the signals (regular expressions over one sentence) that find it.
An item the signals do not find is "needs your check", never "missing":
it may sit in a table, a figure or the supplement, or not apply (the
surfaces let the writer mark it so for the session; Codex review #6).

What a match means (Codex review N1, 2026-10-14): a sentence the signals
match is *possible* evidence, so the status is "found" and the writer is
asked to confirm it, never "reported". A question that asks for two things
("the databases, with the date of the last search") is split into parts,
found separately; finding some is "partial". A matching sentence is not
counted when it says the thing is not reported ("Missing data handling is
not described"), promises it for later ("will be reported elsewhere"), or
describes earlier studies ("Previous studies imputed missing values"). A
legitimate negative report ("There were no missing values") still counts.
Each checklist names its edition, and each item the guideline items it
covers, so nothing implies full compliance with the guideline.

The first pack is epidemiology (`epidemiology.py`), the owner's field.
A new discipline is one more module listed in `PACKS`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .. import sources


@dataclass(frozen=True)
class Part:
    """One thing a compound question asks for, found on its own."""
    label: str                    # "the date of the last search"
    signals: tuple


@dataclass(frozen=True)
class Item:
    id: str
    topic: str
    question: str
    plain: str
    signals: tuple
    sections: tuple = ()          # where readers look; empty = anywhere
    parts: tuple = ()             # Part(...)s of a compound question
    refs: tuple = ()              # the guideline's item numbers; () = not
                                  # an item of the guideline (good practice)


@dataclass(frozen=True)
class Checklist:
    id: str
    label: str
    design: str                   # the kind of study it is for, in words
    source: str                   # a code for sources.cite
    cue: str                      # regex: the text looks like this design
    items: tuple
    edition: str = ""             # "STROBE (2007)": the version mapped

    @property
    def citation(self) -> str:
        return sources.cite(self.source)


@dataclass(frozen=True)
class Pack:
    id: str
    label: str
    checklists: tuple


def _packs() -> dict:
    from . import epidemiology
    return {p.id: p for p in (epidemiology.PACK,)}


def checklists() -> dict:
    """Every checklist of every pack, by id."""
    return {c.id: c for p in _packs().values() for c in p.checklists}


def listing() -> list:
    """For a selector: every checklist, with what it is for."""
    return [{"id": c.id, "label": c.label, "design": c.design,
             "pack": p.label}
            for p in _packs().values() for c in p.checklists]


def suggest(text: str) -> Optional[str]:
    """The checklist the text's own words point to, or None. The most
    specific design wins: a systematic review of trials is a review."""
    for cid in ("prisma", "consort", "epiforge", "strobe"):
        c = checklists().get(cid)
        if c is not None and re.search(c.cue, text, re.IGNORECASE):
            return cid
    return None


_QUOTE = 180


def _quote(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _QUOTE else text[:_QUOTE - 1].rstrip() + "…"


# A matching sentence that does not report the thing (Codex review N1).
# Only meta-reporting verbs: "the sample size was not calculated; all
# eligible patients were included" is a report, "the sample size is not
# reported" is not.
_ABSENT = re.compile(
    r"\b(is|are|was|were|has|have)\s+(not|never)\s+(yet\s+)?(been\s+)?"
    r"(reported|provided|described|given|stated|specified|presented|"
    r"documented|available|discussed|included in (this|the) (paper|"
    r"manuscript|draft))\b"
    r"|\bno (details?|information|description)\b[^.]{0,40}\b(is|are|was|"
    r"were) (given|provided|reported|available)\b"
    r"|\b(TBD|TODO|XXX)\b|\bto be (added|completed|confirmed|decided|"
    r"determined|written)\b", re.IGNORECASE)
_FUTURE = re.compile(
    r"\bwill be (reported|described|presented|provided|given|published|"
    r"added|detailed)\b"
    r"|\b(in|for) (a|an|the)? ?(future|forthcoming|subsequent|later|"
    r"separate) (work|paper|study|report|publication|manuscript)\b"
    r"|\b(reported|described|published) elsewhere\b", re.IGNORECASE)
_PRIOR = re.compile(
    r"^\W*(in )?(previous|prior|earlier|past|existing|several|many|most|"
    r"some|other|recent) (studies|study|work|research|trials|reviews|"
    r"analyses|authors|reports)\b"
    r"|^\W*[A-Z][\w'-]+ (et al\.?|and [A-Z][\w'-]+)\s*(\(\d{4}\)|\[\d+\])?"
    r"\s+(used|reported|found|handled|imputed|estimated|described|showed|"
    r"applied|searched|adjusted|recruited|included)\b"
    r"|^\W*in (a|an|the|their) (previous|prior|earlier|recent) (study|trial|"
    r"analysis|review|cohort)\b", re.IGNORECASE)

NOT_COUNTED = {
    "absent": "says this is not reported",
    "future": "promises it for later",
    "prior": "is about earlier studies",
}


def _why_not(sentence: str) -> Optional[str]:
    """Why a sentence the signals match does not count as reporting the
    item, or None when it may."""
    if _ABSENT.search(sentence):
        return "absent"
    if _FUTURE.search(sentence):
        return "future"
    if _PRIOR.search(sentence):
        return "prior"
    return None


def _first(signals, pool):
    """The first sentence that may report one of `signals`, and the first
    matching sentence set aside (with why), if any."""
    set_aside = None
    for t in pool:
        if not any(re.search(rx, t, re.IGNORECASE) for rx in signals):
            continue
        why = _why_not(t)
        if why is None:
            return t, set_aside
        if set_aside is None:
            set_aside = (why, t)
    return None, set_aside


def check(document, checklist_id: str, spacy_doc=None,
          suggested: Optional[str] = None) -> Optional[dict]:
    """Report each item of one checklist as found (possible evidence, for
    the writer to confirm), partly found, or needing a check. None for an
    unknown checklist."""
    c = checklists().get(checklist_id)
    if c is None:
        return None
    from ..discourse.narrative import _sentences
    sents = _sentences(document, spacy_doc)
    with_section = [(document.section_at(a), t) for a, _, t in sents]
    present = {s for s, _ in with_section}
    # A document with recognised sections: an item whose sections are all
    # absent is not searched elsewhere (a Methods item is not "found" in an
    # Introduction that describes other studies).
    sectioned = bool(present - {"unknown", "front", "other"})
    items = []
    for it in c.items:
        where = [s for s in it.sections if s in present]
        no_section = bool(it.sections) and not where and sectioned and \
            not set(it.sections) & {"unknown", "front", "other"}
        pool = [] if no_section else [
            t for s, t in with_section if not where or s in where]
        parts = []
        if it.parts:
            for part in it.parts:
                hit, aside = _first(part.signals, pool)
                parts.append({"label": part.label, "found": hit is not None,
                              "evidence": _quote(hit) if hit else None})
            found = [p for p in parts if p["found"]]
            hit = next((p["evidence"] for p in found), None)
            status = ("found" if len(found) == len(parts) else
                      "partial" if found else "needs_check")
            # the set-aside sentence, judged on the item's own signals
            _, aside = _first(it.signals + tuple(
                rx for p in it.parts for rx in p.signals), pool)
            if found:
                aside = None
        else:
            hit, aside = _first(it.signals, pool)
            status = "found" if hit else "needs_check"
            hit = _quote(hit) if hit else None
            if hit:
                aside = None
        items.append({
            "id": it.id, "topic": it.topic, "question": it.question,
            "plain": it.plain, "sections": list(it.sections),
            "refs": list(it.refs), "status": status,
            "evidence": hit,
            "parts": parts,
            "not_counted": ({"reason": aside[0],
                             "label": NOT_COUNTED[aside[0]],
                             "quote": _quote(aside[1])} if aside else None),
            "section_absent": no_section,
        })
    found = sum(1 for i in items if i["status"] == "found")
    partial = sum(1 for i in items if i["status"] == "partial")
    total = len(items)
    bits = [f"{found} of {total} items {'has' if found == 1 else 'have'} "
            "possible evidence in the text"]
    if partial:
        bits.append(f"{partial} more {'is' if partial == 1 else 'are'} "
                    "partly there")
    note = ("; ".join(bits) + ". Confirm each one: a matching sentence is "
            "not proof. The others need your check: they may be in a "
            "table, a figure or the supplement, or not apply to this "
            "study. These are selected themes of the guideline, not a full "
            "compliance check, and they check reporting only, never the "
            "science.")
    return {"id": c.id, "label": c.label, "edition": c.edition or c.label,
            "design": c.design, "source": c.citation,
            "suggested": suggested == c.id, "items": items,
            "found": found, "partial": partial, "total": total,
            "note": note}

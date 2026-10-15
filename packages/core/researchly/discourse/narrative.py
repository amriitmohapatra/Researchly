"""The narrative map (S4): per section, which moves are present, missing
or out of order; the argument's missing links; and the hedging trajectory.

Built from the same parse as the suggestions (`api.analyze(...,
with_narrative=True)`), so a document is analysed once. Everything here is
deterministic and traceable: a present move names the sentence it rests
on, a missing one carries the authored question, its lesson and a
fill-in frame, and nothing is a score.
"""

from __future__ import annotations

import re
from typing import Optional

from .. import evidence as evidence_mod
from .. import learn
from .. import lexicons as lx
from .. import sources
from ..document import Document
from . import argument as argument_mod
from . import citations as citations_mod
from . import units as units_mod
from .moves import (MOVES, ORDERED, SCHEMAS, SECTION_LABELS, UNIT_SCHEMAS,
                    label_moves, schema_for)

SOURCE = sources.cite("Swales+WW+§2")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][\w'-]*")
# Clean enough to quote back as evidence.
_EVIDENCE_CHARS = 180


def _sentences(document: Document, spacy_doc=None) -> list:
    """(start, end, text) of each prose sentence, in order, from the masked
    text (so offsets survive markup); table cells skipped."""
    out = []
    if spacy_doc is not None:
        for sent in spacy_doc.sents:
            text = sent.text.strip()
            if text and not document.in_table(sent.start_char):
                out.append((sent.start_char, sent.end_char, text))
        return out
    text = document.masked
    pos = 0
    for chunk in _SENT_SPLIT.split(text):
        stripped = chunk.strip()
        if not stripped:
            pos += len(chunk) + 1
            continue
        start = text.find(chunk, pos)
        start = pos if start == -1 else start
        pos = start + len(chunk)
        if not document.in_table(start):
            out.append((start, start + len(chunk), stripped))
    return out


def _quote(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _EVIDENCE_CHARS else text[:_EVIDENCE_CHARS - 1].rstrip() + "…"


def _move_entry(move_id: str, status: str, evidence: Optional[str] = None,
                note: str = "", section: str = "",
                span: Optional[dict] = None) -> dict:
    m = MOVES[move_id]
    return {
        "id": m.id, "label": m.label, "status": status,
        "question": m.question, "plain": m.plain, "frame": m.frame,
        "source": m.citation, "evidence": evidence, "note": note,
        "learn_ref": learn.card_for_move(section, m.id),
        # Where the sentence is, so the surfaces can show it in the text
        # (Codex review #3); None when it cannot be placed.
        "span": span,
    }


# Notes the map gives in plain words (Codex review N5, 2026-10-14).
_ASSUMED = ("Taken from the section's first sentence, which names no other "
            "move; nothing in its wording marks it as this one.")
_ORDER_FALLBACK = "Appears out of the usual order."


def expected_moves(section: str, profile=None) -> tuple:
    """The moves this kind of document is expected to make in a section:
    the same applicability the brief and the rules use (profiles.py), so a
    commentary is never told its research gap is missing."""
    schema = schema_for(section, getattr(profile, "id", profile))
    if profile is None or isinstance(profile, str):
        return schema
    if not getattr(profile, "gap_expected", True):
        schema = tuple(m for m in schema if m != "gap")
    if not getattr(profile, "limitations_expected", True):
        schema = tuple(m for m in schema if m != "limitations")
    return schema


def describes_only(profile) -> bool:
    """A kind of document with no research-paper structure to expect (a
    response to reviewers): the map lists what it finds and marks nothing
    as not detected."""
    return profile is not None and not isinstance(profile, str) and \
        getattr(profile, "id", "") == "response-to-reviewers"


def _section_map(section: str, sents: list, profile=None,
                 instance: int = 1, document=None, schema=None,
                 label: Optional[str] = None) -> dict:
    schema = expected_moves(section, profile) if schema is None else schema
    describe = describes_only(profile)
    first: dict = {}          # move -> index of its first sentence
    evidence: dict = {}
    spans: dict = {}
    assumed: set = set()
    for i, (_, _, text) in enumerate(sents):
        for mid in label_moves(text, section, first=(i == 0),
                               schema=schema):
            if mid not in first:
                first[mid] = i
                evidence[mid] = _quote(text)
                if document is not None:
                    spans[mid] = evidence_mod.span(document, sents[i][0],
                                                   sents[i][1])
                if MOVES[mid].opening and not MOVES[mid].matches(text):
                    assumed.add(mid)
    out = []
    misplaced = _misplaced(schema, first) if section in ORDERED else set()
    for j, mid in enumerate(schema):
        if mid not in first:
            if not describe:
                out.append(_move_entry(mid, "not_detected", section=section))
            continue
        if describe and mid in assumed:
            continue            # nothing expected: an assumption shows nothing
        status, note = "present", _ASSUMED if mid in assumed else ""
        if mid in misplaced:
            status = "out_of_order"
            after = [schema[i] for i in range(j + 1, len(schema))
                     if schema[i] in first and first[schema[i]] < first[mid]]
            before = [schema[i] for i in range(j) if schema[i] in first
                      and first[schema[i]] > first[mid]]
            if after:
                note = "Appears after " + MOVES[after[-1]].label.lower() + "."
            elif before:
                note = "Appears before " + MOVES[before[0]].label.lower() + "."
            else:
                note = _ORDER_FALLBACK      # every order warning explains itself
        out.append(_move_entry(mid, status, evidence[mid], note, section,
                               spans.get(mid)))
    present = sum(1 for e in out if e["status"] != "not_detected")
    label = label or SECTION_LABELS.get(section, section.capitalize())
    return {
        "section": section,
        "label": label if instance == 1 else f"{label} ({instance})",
        "sentences": len(sents),
        "words": sum(len(_WORD.findall(t)) for _, _, t in sents),
        "moves": out,
        "present": present,
        "expected": len(schema),
    }


def _misplaced(schema: tuple, first: dict) -> set:
    """The present moves that are out of place: those not on the longest
    run of moves that appear in the expected order, so one misplaced
    sentence is reported once, not as every move around it."""
    present = [m for m in schema if m in first]
    idx = [first[m] for m in present]
    n = len(idx)
    if n < 2:
        return set()
    best = [1] * n
    prev = [-1] * n
    for i in range(n):
        for j in range(i):
            # "<=": two moves in one sentence ("Although little is known
            # about X, we aimed to ...") are in order (Codex review N4).
            if idx[j] <= idx[i] and best[j] + 1 > best[i]:
                best[i], prev[i] = best[j] + 1, j
    end = max(range(n), key=lambda i: best[i])
    keep = set()
    while end != -1:
        keep.add(present[end])
        end = prev[end]
    return set(present) - keep


# Missing links worth a line on the map: where the argument is made. A
# Results section shows data without reading them by design.
_LINK_SECTIONS = frozenset({"abstract", "introduction", "discussion",
                            "limitations", "conclusion"})


def _hedging(by_section: dict, order: list) -> list:
    out = []
    for section in order:
        sents = by_section[section]
        words = hedges = boosters = 0
        for _, _, text in sents:
            for w in _WORD.findall(text):
                words += 1
                low = w.lower()
                if low in lx.HEDGE_TOKENS:
                    hedges += 1
                elif low in lx.BOOSTER_TOKENS:
                    boosters += 1
        if words == 0:
            continue
        h, b = hedges * 100.0 / words, boosters * 100.0 / words
        out.append({
            "section": section,
            "label": SECTION_LABELS.get(section, section.capitalize()),
            "words": words,
            "hedges_per_100w": round(h, 2),
            "boosters_per_100w": round(b, 2),
            "reading": _reading(h, b),
        })
    return out


def _reading(h: float, b: float) -> str:
    """A phrase, never a score: how the section's confidence reads."""
    if h == 0 and b == 0:
        return "flat"
    if b == 0:
        return "hedged"
    if h == 0:
        return "assertive"
    ratio = h / b
    if ratio >= 3:
        return "heavily hedged"
    if ratio <= 1 / 3:
        return "assertive"
    return "balanced"


def build_narrative(document: Document, spacy_doc=None,
                    profile=None, scope=None) -> dict:
    """The map every surface renders.

    {"sections": [...], "unmapped": [...], "missing_links": [...],
     "hedging": [...], "note": str, "source": str}
    """
    sents = _sentences(document, spacy_doc)
    by_section: dict = {}
    order: list = []
    # One map per section *instance* (Codex review N5): a section that comes
    # back after another one (a second chapter's Introduction) is mapped on
    # its own, so one chapter's moves never complete another's.
    runs: list = []           # (section, instance, sentences)
    seen: dict = {}
    for start, end, text in sents:
        section = document.section_at(start)
        if section not in by_section:
            by_section[section] = []
            order.append(section)
        by_section[section].append((start, end, text))
        if not runs or runs[-1][0] != section:
            seen[section] = seen.get(section, 0) + 1
            runs.append((section, seen[section], []))
        runs[-1][2].append((start, end, text))

    sections = [_section_map(s, run, profile, instance=k,
                             document=document)
                for s, k, run in runs if s in SCHEMAS]
    unmapped = [s for s in order if s not in SCHEMAS
                and s not in ("front", "references")]
    # A policy brief organised by its own units (Codex review #4) is mapped
    # by them: Context, Evidence, Options, Recommendations.
    pid = getattr(profile, "id", profile)
    policy = (_policy_sections(document, sents)
              if pid == "policy-brief" else None)
    missing_units: list = []
    if policy:
        sections, unmapped = policy
        found_units = {s["section"] for s in sections}
        if getattr(scope, "id", "whole") == "whole":
            missing_units = [units_mod.UNIT_LABELS[u]
                             for u in units_mod.POLICY_UNITS
                             if u not in found_units]
    # A response to reviewers is read as comment-and-reply units, listed
    # as found and never judged (Codex review N5).
    units = (_reviewer_units(document)
             if pid == "response-to-reviewers" else [])

    links = []
    for obj in argument_mod.build_argument(document, spacy_doc=spacy_doc):
        if obj.section not in _LINK_SECTIONS:
            continue
        for code, message in obj.missing_links:
            links.append({
                "section": obj.section,
                "label": SECTION_LABELS.get(obj.section, obj.section),
                "code": code,
                "message": message,
                "learn_ref": learn.card_for_link(code),
                "evidence": [_quote(document.original[a:b])
                             for a, b in obj.link_spans.get(code, [])[:3]],
                "spans": [sp for sp in (
                    evidence_mod.span(document, a, b)
                    for a, b in obj.link_spans.get(code, [])[:3])
                    if sp is not None],
                "source": sources.cite("WW+Toulmin+§4"),
            })
    links += _review_links(document, spacy_doc)

    if units:
        replied = sum(1 for u in units if u["reply"] is not None)
        n = len(units)
        found = f"Found {n} reviewer comment{'s' if n != 1 else ''}"
        found += (f"; {replied} of them {'has' if replied == 1 else 'have'} "
                  "a reply." if n > 1 else
                  ", with a reply under it." if replied else
                  "; no reply was recognised under it.")
        note = (found + " A response to reviewers is described, not "
                "judged: each comment is shown beside its reply.")
    elif describes_only(profile) and not sections:
        note = ("No reviewer comments were recognised (such as "
                "\u201cReviewer 1, Comment 2\u201d, \u201cR1.2\u201d or a "
                "quoted comment followed by its reply), so there is nothing "
                "to list. This kind of document is described, not judged.")
    elif not sections:
        if not document.headings:
            note = ("No section headings were found, so there is no map "
                    "to draw. Add headings (Introduction, Methods, "
                    "Results, Discussion) or check a longer part of the "
                    "document.")
        else:
            note = ("The headings found are not the usual sections "
                    "(Introduction, Methods, Results, Discussion), so "
                    "there is no map to draw for them.")
    elif describes_only(profile):
        note = ("This kind of document is not expected to follow a research "
                "paper's moves: what was found is listed, and nothing is "
                "marked as not detected.")
    else:
        missing = sum(1 for s in sections for m in s["moves"]
                      if m["status"] == "not_detected")
        note = ("Every expected move was found." if missing == 0 else
                f"{missing} expected move{'s were' if missing != 1 else ' was'}"
                " not detected in the wording; each one below has a question "
                "and a frame to fill in. The map reads wording, so check "
                "before adding anything.")
        if policy:
            note = ("Read as a policy brief, by its parts: context, "
                    "evidence, options and recommendations. " + note)
            if missing_units:
                note += (" Not found among the headings: "
                         + ", ".join(missing_units) + ".")
    return {
        "sections": sections,
        "unmapped": unmapped,
        "missing_links": links,
        "hedging": _hedging(by_section, [s for s in order
                                         if s not in ("front", "references")]),
        "note": note,
        "profile": getattr(profile, "id", None),
        "units": units,
        "source": SOURCE,
    }


def _policy_sections(document: Document, sents: list):
    """(sections, unmapped) for a policy brief organised by its units, or
    None when it names none of them (then its sections are mapped as
    before). Each unit instance gets its own strip; text under any other
    heading is left unmapped, by name."""
    found = units_mod.policy_units(document)
    # "Introduction" alone names the context; a brief is organised by its
    # units only when it names one of the others.
    if not any(u != "context" for u, _, _, _ in found):
        return None
    sections, seen = [], {}
    for unit, start, end, _ in found:
        run = [t for t in sents if start <= t[0] < end]
        if not run:
            continue
        seen[unit] = seen.get(unit, 0) + 1
        sections.append(_section_map(
            unit, run, None, instance=seen[unit], document=document,
            schema=UNIT_SCHEMAS[unit], label=units_mod.UNIT_LABELS[unit]))
    unmapped = []
    for h in document.headings:
        if units_mod.unit_of(h.text) is None:
            name = " ".join(h.text.split())[:60]
            if name and name not in unmapped and h.section not in (
                    "references",):
                unmapped.append(name)
    return sections, unmapped


def _reviewer_units(document: Document) -> list:
    """The comment-and-reply units of a response letter, in order: each
    comment and its reply as spans, quoted. Described, never judged."""
    out = []
    for u in units_mod.reviewer_units(document):
        c = u["comment_span"]
        r = u["reply_span"]
        comment = evidence_mod.span(document, *c)
        if comment is None:
            continue
        out.append({
            "kind": "reviewer_comment",
            "label": u["label"],
            "comment": comment,
            "reply": evidence_mod.span(document, *r) if r else None,
            "learn_ref": learn.card_for_unit("reviewer_comment"),
        })
    return out


def _review_links(document: Document, spacy_doc=None) -> list:
    """The review's link to the Discussion: sources that carry the
    Discussion but were never cited before it (`citations.strangers`).
    Nothing when the citations cannot be read reliably."""
    found = citations_mod.strangers(document, spacy_doc)
    if not found["items"]:
        return []
    return [{
        "section": "discussion",
        "label": SECTION_LABELS["discussion"],
        "code": "stranger_sources",
        "message": citations_mod.message(found),
        "learn_ref": learn.card_for_link("stranger_sources"),
        "evidence": [_quote(document.original[a:b])
                     for a, b in (e["evidence"] for e in found["items"][:3])],
        "source": sources.cite("workshop-S2+Kwan2006"),
    }]


def render_narrative(n: dict) -> str:
    """Plain-text map for the CLI."""
    marks = {"present": "present", "not_detected": "not detected",
             "out_of_order": "out of order"}
    L: list[str] = []
    add = L.append
    add("NARRATIVE MAP")
    add(n["note"])
    for s in n["sections"]:
        add("")
        add(f"{s['label']} ({s['words']} words): {s['present']} of "
            f"{s['expected']} moves")
        for m in s["moves"]:
            line = f"   {m['label']:<26} {marks[m['status']]}"
            if m["note"]:
                line += f" ({m['note'].rstrip('.')})"
            add(line)
            if m["status"] == "not_detected":
                add(f"      {m['question']}")
                add(f"      frame: {m['frame']}")
            elif m["evidence"]:
                add(f'      "{m["evidence"]}"')
    if n["missing_links"]:
        add("")
        add("Argument: missing links")
        for link in n["missing_links"]:
            add(f"   [{link['label']}] {link['message']}")
    if n["hedging"]:
        add("")
        add("Hedging across the document (per 100 words)")
        for h in n["hedging"]:
            add(f"   {h['label']:<14} hedges {h['hedges_per_100w']:>5}  "
                f"boosters {h['boosters_per_100w']:>5}  {h['reading']}")
    add("")
    add("Source: " + n["source"])
    return "\n".join(L)

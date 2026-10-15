"""The analysis, shaped for the wire (API contract v1).

The hosted service (services/engine) and the local Word server
(apps/word-addin/server.py) both answer the same contract. They used to
shape the response separately, and the local one fell behind the moment
the hosted one learned profiles and the brief (Codex review R1). Every
object beyond the suggestions is shaped here, once; the service validates
the result against its pydantic models, the local server sends it as is,
and a service test posts every contract option to the local server and
validates the answer.
"""

from __future__ import annotations

from typing import Optional


def profile_info(a) -> dict:
    p = a.profile
    return {"id": p.id, "label": p.label, "guessed": a.profile_guessed,
            "note": p.note, "rules_off": sorted(p.rules_off),
            "evidence": getattr(a, "profile_evidence", "") or ""}


def review_report(r: Optional[dict]) -> Optional[dict]:
    if r is None:
        return None
    return {
        "source": r["source"],
        "sections": list(r["sections"]),
        "words": int(r["metrics"]["words"]),
        "questions": [{"id": q["id"], "question": q["question"],
                       "status": q.get("status", "detected"),
                       "verdict": q["verdict"], "points": list(q["points"]),
                       "evidence": list(q["evidence"])}
                      for q in r["questions"]],
        "top_rules": [dict(t) for t in r["top_rules"]],
        "disclaimer": r.get("disclaimer", ""),
    }


def narrative_map(n: Optional[dict]) -> Optional[dict]:
    if n is None:
        return None
    return {
        "sections": [{
            "section": s["section"], "label": s["label"],
            "sentences": s["sentences"], "words": s["words"],
            "present": s["present"], "expected": s["expected"],
            "moves": [{k: m.get(k) for k in (
                "id", "label", "status", "question", "plain", "frame",
                "source", "evidence", "note", "learn_ref")}
                for m in s["moves"]],
        } for s in n["sections"]],
        "unmapped": list(n["unmapped"]),
        "missing_links": [{k: link.get(k) for k in (
            "section", "label", "code", "message", "source", "learn_ref")}
            | {"evidence": list(link.get("evidence") or [])}
            for link in n["missing_links"]],
        "hedging": [dict(h) for h in n["hedging"]],
        "note": n["note"],
        "profile": n.get("profile"),
        "source": n["source"],
    }


def checklist_report(c: Optional[dict]) -> Optional[dict]:
    if c is None:
        return None
    return {k: c[k] for k in ("id", "label", "edition", "design", "source",
                              "suggested", "found", "partial", "total",
                              "note")} | {
        "items": [{k: i[k] for k in ("id", "topic", "question", "plain",
                                     "sections", "refs", "status", "evidence",
                                     "parts", "not_counted",
                                     "section_absent")}
                  for i in c["items"]]}


_SET_ASIDE = (
    ("code", "lines of code"),
    ("maths_or_code", "bits of maths or code typed into the text"),
    ("layout", "lines laid out as a table or an equation"),
    ("marked_up", "bits of maths, citations or code in the markup"),
    ("other_language", "paragraphs not in English"),
)


def reading_summary(document) -> Optional[dict]:
    """What was read and what was set aside (Codex review #5): the words
    the checks saw, and each kind of material they skipped, in plain words.
    Counts only; no text."""
    if document is None:
        return None
    read = dict(getattr(document, "read", {}) or {})
    if document.kind in ("latex", "markdown") and document.atoms:
        read["marked_up"] = len(document.atoms)
    return {
        "words_checked": len(document.masked.split()),
        "set_aside": [{"kind": k, "count": int(read[k]), "label": label}
                      for k, label in _SET_ASIDE if read.get(k)],
    }


def extras(a) -> dict:
    """Everything an analysis response carries beyond the suggestions."""
    return {
        "assessed_rules": list(getattr(a, "assessed_rules", []) or []),
        "ruleset": getattr(a, "ruleset", "") or "",
        "reading": reading_summary(a.document),
        "profile": profile_info(a),
        "review": review_report(a.review),
        "narrative": narrative_map(a.narrative),
        "checklist": checklist_report(a.checklist),
        "suggested_checklist": a.suggested_checklist,
    }


# --- the live check (S4d R3) ---------------------------------------------------

def live_suggestion(s, paragraph_id: str, index) -> dict:
    """One live suggestion for the wire. `index` maps the paragraph's
    code-point offsets to UTF-16 (researchly.utf16.Utf16Index): `begin` and
    `end` are UTF-16 code units within the paragraph, because every client
    that draws underlines counts that way. `rule_id` is for actions and
    tests; surfaces never show it."""
    from .utf16 import live_id
    begin, end = index(s.start), index(s.end)
    return {
        "id": live_id(s.rule_id, paragraph_id, begin, end, s.text),
        "rule_id": s.rule_id,
        "rule_name": s.rule_name,
        "category": s.category.value,
        "critical": s.category.value == "correction",
        "tier": s.tier,
        "begin": begin,
        "end": end,
        "text": s.text,
        "section": s.section or "unknown",
        "message": s.message,
        "plain": s.plain,
        "why": s.why,
        "source": s.source,
        "learn_ref": s.learn_ref,
        "replacements": [s.replacement] if s.replacement else [],
        "fix_safety": "safe" if s.fix_safety == "safe" else "review",
    }


def live_paragraphs(result) -> list:
    """`api.check_paragraphs()`'s paragraphs, shaped for the wire."""
    from .utf16 import Utf16Index
    out = []
    for p in result.paragraphs:
        index = Utf16Index(p.text)
        out.append({"id": p.id, "section": p.section,
                    "suggestions": [live_suggestion(s, p.id, index)
                                    for s in p.suggestions]})
    return out

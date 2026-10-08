"""The critical reader's brief (Wallace & Wray's five critical-synopsis
questions, met in the owner's training; see sources.py).

An on-demand, document-level pass that plays the friendly-sceptical
reader. Every line is answered from deterministic evidence the engine
already computed: no model, every statement traceable to a rule or a
read-out.

    A. Why am I reading this?          (yours to answer)
    B. What are the authors trying to achieve?   -> aim signals
    C. What are they claiming?         -> claim inventory (causal, consensus)
    D. How convincing are the claims?  -> warranting evidence: gap statement,
                                          calibration balance, overclaims,
                                          novelty risks, limitations section,
                                          argument links
    E. What use can be made of this?   -> significance signals

Surfaces get it from `api.analyze(..., with_review=True)` as
`Analysis.review` (S4: the website and the Word add-in). The CLI's
`researchly review` and the old local add-in call `build_review` directly.
The wording below is user-visible: plain words, no internal references
(test_explanations.py applies the same ban as to rule text).
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from .discourse import abstract_lens
from .discourse import argument as argument_mod
from . import metrics as metrics_mod
from . import profiles as profiles_mod
from . import sources
from .document import Document
from .engine import REGISTRY, check

SOURCE = sources.cite("WW+NG5001-U1")

QUESTIONS = (
    ("A", "Why am I reading this?"),
    ("B", "What are the authors trying to achieve?"),
    ("C", "What are they claiming?"),
    ("D", "How convincing are the claims?"),
    ("E", "What use can be made of this?"),
)


def build_review(text, nlp, kind: str = "plain", *, suggestions=None,
                 spacy_doc=None, metrics=None,
                 profile: Optional[profiles_mod.Profile] = None) -> dict:
    """`text` may be a str or an already-built Document (the Word server
    passes a Document so style-based headings survive into the review).
    `api.analyze` passes its own suggestions, parse and metrics so the
    document is analysed once."""
    doc = text if isinstance(text, Document) else Document.from_text(text,
                                                                     kind)
    if profile is None:
        profile = profiles_mod.resolve(
            getattr(getattr(doc, "config", None), "document_type", None),
            doc)[0]
        doc.default_section = doc.default_section or profile.body_section
    if suggestions is None:
        suggestions = check(doc, nlp, disabled={"LT001"},
                            show_preferences=True, spacy_doc=spacy_doc)
    suggestions = [s for s in suggestions if s.rule_id != "LT001"]
    if metrics is None:
        metrics = metrics_mod.compute(spacy_doc or nlp(doc.masked), doc)
    mets = metrics
    by_rule = Counter(s.rule_id for s in suggestions)
    moves = abstract_lens.analyze(doc.masked)
    sections = sorted({h.section for h in doc.headings}) or ["(none)"]
    has_limitations = "limitations" in sections

    # The review reads the document's argument structure from the shared
    # argument objects, not only from rule hits.
    arg_objects = argument_mod.build_argument(doc)
    arg = argument_mod.summarize(arg_objects)

    def hits(rule_id):
        return [s for s in suggestions if s.rule_id == rule_id]

    causal = hits("C303")
    r = {
        "source": SOURCE,
        "profile": profile.id,
        "argument": arg,
        "sections": sections,
        "expected_missing": [s for s in profile.expected
                             if s not in sections],
        "metrics": mets.to_dict(),
        "aim": moves["aim"],
        "significance": moves["significance"],
        "gap_present": not hits("D902") and (
            moves["gap"]["present"] or "introduction" not in sections),
        "gap_evidence": moves["gap"]["evidence"],
        "gap_expected": profile.gap_expected,
        "causal_claims": [s.message for s in causal],
        "uncited_consensus": len(hits("E704")),
        "overclaims": len(hits("C302")),
        "novelty_risks": len(hits("E705")),
        "hedge_stacks": len(hits("C301")),
        "has_limitations": has_limitations,
        "limitations_expected": profile.limitations_expected,
        "abstract_missing": ([s.message for s in hits("AB802")] or None),
        "total_suggestions": len(suggestions),
        "by_rule": dict(by_rule.most_common(8)),
        "top_rules": [{"id": k, "short": _short(k), "count": v}
                      for k, v in by_rule.most_common(5)],
    }
    r["questions"] = brief(r)
    return r


def _short(rule_id: str) -> str:
    rule = REGISTRY.get(rule_id)
    return rule.short if rule is not None else rule_id


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def brief(r: dict) -> list:
    """The five questions, each with a one-line verdict, the points behind
    it and the sentences of the document they rest on. Plain words."""
    m = r["metrics"]
    out = []

    def add(key, verdict, points=(), evidence=()):
        question = dict(QUESTIONS)[key]
        out.append({"id": key, "question": question, "verdict": verdict,
                    "points": [p for p in points if p],
                    "evidence": [e for e in evidence if e]})

    # A
    add("A", "Yours to answer: what do you need from this document?",
        ["The brief below reads it as a sceptical reader would, from the "
         "evidence in the text alone."])

    # B
    if r["aim"]["present"]:
        add("B", "An aim is stated.", evidence=[r["aim"]["evidence"]])
    else:
        add("B", "No sentence says what this document sets out to answer.",
            ["Where does the reader learn what question this document "
             "answers? One sentence near the end of the introduction "
             "usually does it."])

    # C
    points, verdicts = [], []
    if r["causal_claims"]:
        verdicts.append(_count(len(r["causal_claims"]), "causal claim",
                               "causal claims") + " the design must carry")
        points += r["causal_claims"][:5]
    else:
        verdicts.append("no unhedged causal claims found")
    if r["uncited_consensus"]:
        verdicts.append(_count(r["uncited_consensus"],
                               "'is known' claim without a citation",
                               "'is known' claims without a citation"))
        points.append("A claim that something is known, accepted or "
                      "considered true needs a citation: who says?")
    add("C", "; ".join(verdicts).capitalize() + ".", points)

    # D
    points, evidence = [], []
    structured = r["sections"] != ["(none)"]
    if r["gap_expected"] and structured:
        if r["gap_present"]:
            points.append("A gap statement is present: the reader is told "
                          "what was missing before this work.")
            evidence.append(r["gap_evidence"])
        else:
            points.append("No gap statement found: the reader is not told "
                          "what was missing before this work, so the "
                          "demand for it is unstated.")
    points.append(f"Calibration: {m['hedge_booster_balance']} (hedges "
                  f"{m['hedges_per_100w']} per 100 words against boosters "
                  f"{m['boosters_per_100w']}).")
    if r["overclaims"]:
        points.append(_count(r["overclaims"], "overclaiming verb",
                             "overclaiming verbs")
                      + " such as 'prove' or 'conclusively': reserve strong "
                      "verbs for strong evidence.")
    if r["hedge_stacks"]:
        points.append(_count(r["hedge_stacks"], "stacked hedge",
                             "stacked hedges")
                      + ": one calibrated qualifier beats two weak ones.")
    if r["novelty_risks"]:
        points.append(_count(r["novelty_risks"], "absolute novelty claim",
                             "absolute novelty claims")
                      + ": soften with 'to our knowledge' and cite the "
                      "nearest work.")
    if r["limitations_expected"] and structured:
        points.append("A limitations section is present, so the rebuttal "
                      "is pre-empted." if r["has_limitations"] else
                      "No limitations section: the reviewer will supply "
                      "the rebuttal instead.")
    links = (r.get("argument") or {}).get("missing_links") or []
    for link in links[:6]:
        points.append(f"Argument, {link['section']}: {link['message']}")
    if r["abstract_missing"]:
        points.append("Abstract: " + r["abstract_missing"][0])
    if r["expected_missing"] and structured:
        points.append("Sections a reader of this kind of document expects "
                      "but the headings do not show: "
                      + ", ".join(r["expected_missing"]) + ".")
    worries = (r["overclaims"] + r["hedge_stacks"] + r["novelty_risks"]
               + len(links)
               + (1 if structured and r["gap_expected"]
                  and not r["gap_present"] else 0)
               + (1 if structured and r["limitations_expected"]
                  and not r["has_limitations"] else 0))
    add("D", "Nothing undermines the claims on the evidence here."
        if worries == 0 else
        _count(worries, "thing weakens", "things weaken")
        + " the claims; see the points.", points, evidence)

    # E
    if r["significance"]["present"]:
        add("E", "The significance is stated.",
            evidence=[r["significance"]["evidence"]])
    else:
        add("E", "No sentence says what a reader can do with this.",
            ["The ending never widens back out: say what should change in "
             "the field or in practice, and for whom."])
    return out


def render_review(r: dict) -> str:
    """Plain-text brief for the CLI and the old local add-in."""
    m = r["metrics"]
    L: list[str] = []
    add = L.append
    add("REVIEWER'S BRIEF — the critical reader's five questions")
    add(f"sections detected: {', '.join(r['sections'])} · "
        f"{m['words']} words · {r['total_suggestions']} suggestions total")
    for q in r["questions"]:
        add("")
        add(f"{q['id']}. {q['question']}")
        add(f"   {q['verdict']}")
        for p in q["points"]:
            add(f"     - {p}")
        for e in q["evidence"]:
            add(f'     "{e}"')
    if r["top_rules"]:
        add("")
        add("Most frequent checks: "
            + ", ".join(f"{t['short']} ({t['count']})"
                        for t in r["top_rules"]))
    add("Source: " + r["source"])
    return "\n".join(L)

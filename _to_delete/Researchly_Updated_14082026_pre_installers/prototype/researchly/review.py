"""The critical-reader review lens (Wallace & Wray, via NG5001 Unit 1).

An on-demand, document-level pass that plays the friendly-sceptical reader:
the five Critical Synopsis Questions, answered from deterministic evidence
already computed by the engine — no LLM, every line traceable.

    A. Why am I reading this?          (yours to answer)
    B. What are the authors trying to achieve?   → aim signals
    C. What are they claiming?         → claim inventory (causal, consensus)
    D. How convincing are the claims?  → warranting evidence: gap statement,
                                          calibration balance, overclaims,
                                          novelty risks, limitations section
    E. What use can be made of this?   → significance signals

Usage: `researchly review FILE` (or text/stdin).
"""

from __future__ import annotations

from collections import Counter

from . import abstract_lens
from . import argument as argument_mod
from . import metrics as metrics_mod
from .document import Document
from .engine import check


def build_review(text, nlp, kind: str = "plain") -> dict:
    """`text` may be a str or an already-built Document (the Word server
    passes a Document so style-based headings survive into the review)."""
    doc = text if isinstance(text, Document) else Document.from_text(text,
                                                                     kind)
    suggestions = check(doc, nlp, disabled={"LT001"},
                        show_preferences=True)
    by_rule = Counter(s.rule_id for s in suggestions)
    mets = metrics_mod.compute(nlp(doc.masked), doc)
    moves = abstract_lens.analyze(doc.masked)
    sections = sorted({h.section for h in doc.headings}) or ["(none)"]
    has_limitations = "limitations" in sections

    # W4: the review lens now reads the document's argument structure from
    # the shared argument objects rather than only rule hits — the first
    # consumer of the ArgumentObject layer (sprint items 9–10).
    arg_objects = argument_mod.build_argument(doc)
    arg = argument_mod.summarize(arg_objects)

    def hits(rule_id):
        return [s for s in suggestions if s.rule_id == rule_id]

    causal = hits("C303")
    return {
        "argument": arg,
        "sections": sections,
        "metrics": mets.to_dict(),
        "aim": moves["aim"],
        "significance": moves["significance"],
        "gap_present": not hits("D902") and (
            moves["gap"]["present"] or "introduction" not in sections),
        "gap_evidence": moves["gap"]["evidence"],
        "causal_claims": [s.message for s in causal],
        "uncited_consensus": len(hits("E704")),
        "overclaims": len(hits("C302")),
        "novelty_risks": len(hits("E705")),
        "hedge_stacks": len(hits("C301")),
        "has_limitations": has_limitations,
        "abstract_missing": ([s.message for s in hits("AB802")] or None),
        "total_suggestions": len(suggestions),
        "by_rule": dict(by_rule.most_common(8)),
    }


def render_review(r: dict) -> str:
    m = r["metrics"]
    L: list[str] = []
    add = L.append
    add("REVIEWER'S BRIEF — the friendly-sceptical reader "
        "(Wallace & Wray, deterministic evidence)")
    add(f"sections detected: {', '.join(r['sections'])} · "
        f"{m['words']} words · {r['total_suggestions']} suggestions total")
    add("")
    add("B. What are the authors trying to achieve?")
    if r["aim"]["present"]:
        add(f'   aim stated: "{r["aim"]["evidence"]}"')
    else:
        add("   NO explicit aim/question signal found — where does the "
            "reader learn what this document answers?")
    add("")
    add("C. What are they claiming?")
    if r["causal_claims"]:
        add(f"   {len(r['causal_claims'])} causal claim group(s) — each "
            "needs the design to carry it:")
        for msg in r["causal_claims"][:5]:
            add(f"     - {msg}")
    else:
        add("   no unhedged causal claims detected")
    if r["uncited_consensus"]:
        add(f"   {r['uncited_consensus']} 'is known/considered to be' "
            "claim(s) without citation — who says?")
    add("")
    add("D. How convincing? (warranting check)")
    add("   gap statement: " + ("present"
        + (f' — "{r["gap_evidence"]}"' if r["gap_evidence"] else "")
        if r["gap_present"] else
        "NOT detected — the demand for this work is unstated (CARS M2)"))
    add(f"   calibration: {m['hedge_booster_balance']} "
        f"(hedges {m['hedges_per_100w']}/100w vs boosters "
        f"{m['boosters_per_100w']}/100w)")
    if r["overclaims"]:
        add(f"   {r['overclaims']} overclaim(s) (prove/conclusively) — "
            "reserve strong verbs for strong evidence")
    if r["hedge_stacks"]:
        add(f"   {r['hedge_stacks']} stacked-hedge spot(s) — "
            "one calibrated qualifier beats two weak ones")
    if r["novelty_risks"]:
        add(f"   {r['novelty_risks']} absolute novelty claim(s) — soften "
            "with 'to our knowledge' and cite the nearest work")
    add("   limitations section: "
        + ("present — pre-empting the rebuttal (Toulmin)"
           if r["has_limitations"] else
           "NOT found — the rebuttal will come from the reviewer instead"))
    links = (r.get("argument") or {}).get("missing_links") or []
    if links:
        add(f"   argument structure ({len(links)} missing link"
            f"{'s' if len(links) != 1 else ''}, Toulmin scan):")
        for link in links[:6]:
            add(f"     - [{link['section']}] {link['message']}")
    if r["abstract_missing"]:
        add(f"   abstract: {r['abstract_missing'][0]}")
    add("")
    add("E. What use can a reader make of this?")
    if r["significance"]["present"]:
        add(f'   significance stated: "{r["significance"]["evidence"]}"')
    else:
        add("   no significance/implications signal — the hourglass never "
            "widens back out (OCAR Resolution)")
    add("")
    add("A is yours: why should THIS reader be reading it? "
        "Top rules firing: "
        + ", ".join(f"{k}({v})" for k, v in r["by_rule"].items()))
    return "\n".join(L)

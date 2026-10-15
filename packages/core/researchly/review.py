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

from bisect import bisect_right
from collections import Counter
from typing import Optional

from .discourse import abstract_lens
from .discourse import argument as argument_mod
from .discourse import citations as citations_mod
from . import evidence as evidence_mod
from . import metrics as metrics_mod
from . import profiles as profiles_mod
from . import sources
from .document import Document
from .engine import REGISTRY, check

SOURCE = sources.cite("WW+course-U1")

DISCLAIMER = ("This brief points to what a critical reader would ask, "
              "from signals in the wording. It does not establish whether "
              "the science is sound.")

QUESTIONS = (
    ("A", "Why am I reading this?"),
    ("B", "What are the authors trying to achieve?"),
    ("C", "What are they claiming?"),
    ("D", "How convincing are the claims?"),
    ("E", "What use can be made of this?"),
)


def build_review(text, nlp, kind: str = "plain", *, suggestions=None,
                 spacy_doc=None, metrics=None,
                 profile: Optional[profiles_mod.Profile] = None,
                 disabled=(), scope=None) -> dict:
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
    if scope is None:
        scope = profiles_mod.resolve_scope(None, doc, profile)
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
    roles = argument_mod.label_sentences(doc, spacy_doc)
    arg_objects = argument_mod.build_argument(doc, roles=roles,
                                              spacy_doc=spacy_doc)
    arg = argument_mod.summarize(arg_objects)
    # Checks muted by the writer or switched off by the article type were
    # not run: their silence is "not assessed", never "not found" (Codex
    # review R4).
    off = set(disabled) | set(profile.rules_off)
    claims_seen = any("claim" in r.all_roles
                      for o in arg_objects for r in o.supporting_spans)

    def sentence_of(s):
        text = doc.original
        a = max(text.rfind(". ", 0, s.start), text.rfind("\n", 0, s.start))
        b_dot = text.find(". ", s.end)
        b_nl = text.find("\n", s.end)
        ends = [x for x in (b_dot, b_nl) if x != -1]
        b = min(ends) + 1 if ends else len(text)
        return " ".join(text[a + 1:b].split())[:180]

    def hits(rule_id):
        return [s for s in suggestions if s.rule_id == rule_id]

    causal = hits("C303")
    # The review's link to the Discussion: sources that carry it but were
    # never cited before it (shown, never flagged; abstains when the
    # citations cannot be read reliably).
    found = citations_mod.strangers(doc, spacy_doc)
    strangers = {
        "assessed": found["assessed"],
        "count": len(found["items"]),
        "message": citations_mod.message(found) if found["items"] else "",
        "evidence": [" ".join(doc.original[a:b].split())[:180]
                     for a, b in (e["evidence"] for e in found["items"][:2])],
    }
    r = {
        "source": SOURCE,
        "profile": profile.id,
        "argument": arg,
        "sections": sections,
        "expected_missing": [s for s in profiles_mod.expected_sections(
                                 profile, scope, doc)
                             if s not in sections],
        "scope": scope.id,
        "metrics": mets.to_dict(),
        "aim": moves["aim"],
        "significance": moves["significance"],
        "has_introduction": "introduction" in sections,
        "gap_present": (not hits("D902") and moves["gap"]["present"]
                        and "introduction" in sections),
        "gap_evidence": moves["gap"]["evidence"],
        "gap_expected": profile.gap_expected,
        "gap_assessed": "D902" not in off,
        "gap_without_stake": [s.message for s in hits("D903")],
        "strangers": strangers,
        "causal_assessed": "C303" not in off,
        "consensus_assessed": "E704" not in off,
        "claims_seen": claims_seen or bool(causal) or bool(hits("C302")),
        "causal_claims": [s.message for s in causal],
        "causal_evidence": [sentence_of(s) for s in causal[:5]],
        "not_assessed": sorted(r_id for r_id in off
                               if r_id in ("C301", "C302", "C303", "E704",
                                           "E705", "D902", "AB802")),
        "disclaimer": DISCLAIMER,
        "uncited_consensus": len(hits("E704")),
        "overclaims": len(hits("C302")),
        "novelty_risks": len(hits("E705")),
        "hedge_stacks": len(hits("C301")),
        "has_limitations": has_limitations,
        "limitations_expected": profiles_mod.limitations_expected(profile,
                                                                  scope),
        "abstract_missing": ([s.message for s in hits("AB802")] or None),
        "total_suggestions": len(suggestions),
        "by_rule": dict(by_rule.most_common(8)),
        "top_rules": [{"id": k, "short": _short(k), "count": v}
                      for k, v in by_rule.most_common(5)],
    }
    r["links"] = _evidence_links(doc, roles, suggestions, moves, found,
                                 arg_objects)
    r["questions"] = brief(r)
    return r


# --- evidence links (Codex review #3) ------------------------------------------
#
# Each point of the brief that rests on a sentence carries that sentence's
# place (researchly/evidence.py), and a claim carries the evidence proposed
# beside it: the nearest sentence in the same section that reports a
# number, a citation or a finding (argument roles "evidence" and "result"),
# within two sentences, as the argument model links them (Codex review R5).
# Nothing is linked that cannot be placed: a quote the text no longer
# holds, or a point about the whole document, abstains.

_PER_KIND = 5

LINK_LABELS = {
    "aim": "The aim",
    "gap": "The gap",
    "gap_without_stake": "A gap without its stake",
    "causal_claim": "A causal claim",
    "consensus_claim": "A claim that something is known",
    "overclaim": "A strong verb",
    "hedge_stack": "Stacked hedges",
    "novelty": "A novelty claim",
    "stranger": "Leans on a source first cited here",
    "claim_without_warrant": "A claim with no reason nearby",
    "claim_without_grounds": "A claim with no evidence nearby",
    "evidence_without_interpretation": "A result not read for the reader",
    "limitation_not_reflected_in_claim_strength": "A claim at full strength",
    "significance": "Why it matters",
}

_GROUNDS = ("evidence", "result")
NEAREST = ("The nearest sentence with a number, a citation or a reported "
           "finding, within two sentences.")
SAME = ("The claim’s own sentence reports a number, a citation or a "
        "finding.")
NO_GROUNDS = ("No number, citation or reported finding was detected within "
              "two sentences of this claim.")
NO_WARRANT = ("No reason (‘because’, ‘this suggests "
              "that’) was detected in this sentence or the next.")
NO_CITATION = "No citation was detected in this sentence: who says so?"


def _evidence_links(doc, roles, suggestions, moves, strangers_found,
                    arg_objects) -> dict:
    """{kind: [link]}: every placeable sentence a point of the brief rests
    on. A link is {"kind", "label", "claim": span, "evidence": span|None,
    "evidence_status", "evidence_note"}; `evidence_status` is "detected"
    or "not_detected" for a claim weighed against its evidence, and
    "not_applicable" for a statement that needs none."""
    sents = evidence_mod.Sentences(doc, roles=roles)
    starts = [r.start for r in roles]
    heads = sorted(h.start for h in doc.headings)

    def role_index(offset):
        i = bisect_right(starts, offset) - 1
        return i if i >= 0 and offset < roles[i].end else None

    def instance(offset):
        return bisect_right(heads, offset)

    def grounds(offset):
        """(span, status, note) for the evidence proposed beside a claim."""
        i = role_index(offset)
        if i is None:
            return None, "not_detected", NO_GROUNDS
        if set(_GROUNDS) & set(roles[i].all_roles):
            return (sents.around(roles[i].start, roles[i].end), "detected",
                    SAME)
        home = instance(roles[i].start)
        for d in (-1, 1, -2, 2):
            j = i + d
            if 0 <= j < len(roles) and instance(roles[j].start) == home \
                    and set(_GROUNDS) & set(roles[j].all_roles):
                found = sents.around(roles[j].start, roles[j].end)
                if found is not None:
                    return found, "detected", NEAREST
        return None, "not_detected", NO_GROUNDS

    out: dict = {}
    seen: dict = {}

    def add(kind, claim, evidence=None, status="not_applicable", note=""):
        if claim is None:
            return              # nothing placeable: abstain
        bucket = out.setdefault(kind, [])
        key = (claim["start"], claim["end"])
        if key in seen.setdefault(kind, set()) or len(bucket) >= _PER_KIND:
            return
        seen[kind].add(key)
        bucket.append({"kind": kind, "label": LINK_LABELS[kind],
                       "claim": claim, "evidence": evidence,
                       "evidence_status": status, "evidence_note": note})

    # The aim, the gap and the significance: the first sentence the same
    # signals find, now over the shared sentences so it can be placed.
    for kind in ("aim", "gap", "significance"):
        if (moves.get(kind) or {}).get("present"):
            add(kind, sents.first_matching(abstract_lens.SIGNALS[kind]))

    def hits(rule_id):
        return [s for s in suggestions if s.rule_id == rule_id]

    for s in hits("C303"):
        add("causal_claim", sents.around(s.start, s.end), *grounds(s.start))
    for s in hits("C302"):
        add("overclaim", sents.around(s.start, s.end), *grounds(s.start))
    for s in hits("E704"):
        add("consensus_claim", sents.around(s.start, s.end), None,
            "not_detected", NO_CITATION)
    for s in hits("E705"):
        add("novelty", sents.around(s.start, s.end))
    for s in hits("C301"):
        add("hedge_stack", sents.around(s.start, s.end))
    for s in hits("D903"):
        add("gap_without_stake", sents.around(s.start, s.end))
    for item in strangers_found.get("items") or []:
        a, b = item["evidence"]
        add("stranger", sents.around(a, b))

    for obj in arg_objects:
        for code, _ in obj.missing_links:
            for a, b in obj.link_spans.get(code, []):
                span = sents.around(a, b)
                if code == "claim_without_warrant":
                    add(code, span, None, "not_detected", NO_WARRANT)
                elif code == "claim_without_grounds":
                    add(code, span, None, "not_detected", NO_GROUNDS)
                elif code in LINK_LABELS:
                    add(code, span)
    return out


def _short(rule_id: str) -> str:
    rule = REGISTRY.get(rule_id)
    return rule.short if rule is not None else rule_id


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def brief(r: dict) -> list:
    """The five questions, each with a status, a one-line verdict, the
    points behind it and the sentences it rests on. Plain words.

    status: "yours" (A), "detected", "not_detected" (the signals found
    nothing, which is not proof of absence), "not_assessed" (the check was
    off) or "not_applicable" (the part of the document is not there).
    Every positive assertion carries evidence (Codex review R4)."""
    m = r["metrics"]
    out = []
    structured = r["sections"] != ["(none)"]

    pool = r.get("links") or {}

    def take(*kinds):
        return [link for k in kinds for link in pool.get(k, [])]

    def add(key, status, verdict, points=(), evidence=(), links=()):
        question = dict(QUESTIONS)[key]
        out.append({"id": key, "question": question, "status": status,
                    "verdict": verdict,
                    "points": [p for p in points if p],
                    "evidence": [e for e in evidence if e],
                    # Where each point rests in the text (Codex review #3):
                    # only what could be placed; the rest abstains.
                    "links": list(links)})

    # A
    add("A", "yours", "Yours to answer: what do you need from this document?",
        ["The brief below reads the text as a sceptical reader would, from "
         "signals in the wording alone."])

    # B
    if r["aim"]["present"]:
        add("B", "detected", "An aim is stated.",
            evidence=[r["aim"]["evidence"]], links=take("aim"))
    else:
        add("B", "not_detected", "No explicit aim was detected.",
            ["Where does the reader learn what question this document "
             "answers? One sentence near the end of the introduction "
             "usually does it. If you have one, it may be worded in a way "
             "the signals do not recognise."])

    # C
    if not r["causal_assessed"]:
        add("C", "not_assessed",
            "Not assessed: the check for causal claims is off for this "
            "check (muted, or switched off by the article type).",
            ["Turn it back on to see the causal claims listed here."])
    else:
        points, verdicts = [], []
        if r["causal_claims"]:
            verdicts.append(_count(len(r["causal_claims"]), "causal claim",
                                   "causal claims")
                            + " detected; check that the design supports "
                            + ("it" if len(r["causal_claims"]) == 1 else "each"))
            points += r["causal_claims"][:5]
        else:
            verdicts.append("no unhedged causal claims were detected")
        if r["uncited_consensus"]:
            verdicts.append(_count(r["uncited_consensus"],
                                   "'is known' claim without a citation",
                                   "'is known' claims without a citation"))
            points.append("A claim that something is known, accepted or "
                          "considered true needs a citation: who says?")
        elif not r["consensus_assessed"]:
            points.append("Claims that something 'is known' were not "
                          "checked: that check is off.")
        status = "detected" if (r["causal_claims"] or r["uncited_consensus"]) \
            else "not_detected"
        text = "; ".join(verdicts)
        add("C", status, text[:1].upper() + text[1:] + ".", points,
            r.get("causal_evidence") or [],
            (take("causal_claim") if r["causal_claims"] else [])
            + (take("consensus_claim") if r["uncited_consensus"] else []))

    # D
    points, evidence, linked = [], [], []
    gap_point = False
    if r["gap_expected"] and structured and r.get("has_introduction"):
        if not r["gap_assessed"]:
            points.append("The gap statement was not assessed: that check "
                          "is off.")
        elif r["gap_present"] and r["gap_evidence"]:
            points.append("A gap statement was detected: the reader is told "
                          "what was missing before this work.")
            evidence.append(r["gap_evidence"])
            linked += take("gap")
            if r.get("gap_without_stake"):
                linked += take("gap_without_stake")
                gap_point = True
                points.append("The gap says what is missing but not what "
                              "goes wrong without the answer: say who pays, "
                              "or what is decided blind, if it stays open.")
        else:
            gap_point = True
            points.append("No gap statement was detected in the "
                          "introduction: the reader may not be told what was "
                          "missing before this work.")
    points.append(f"Calibration: {m['hedge_booster_balance']} (hedges "
                  f"{m['hedges_per_100w']} per 100 words against boosters "
                  f"{m['boosters_per_100w']}).")
    if r["overclaims"]:
        points.append(_count(r["overclaims"], "overclaiming verb",
                             "overclaiming verbs")
                      + " such as 'prove' or 'conclusively': reserve strong "
                      "verbs for strong evidence.")
        linked += take("overclaim")
    if r["hedge_stacks"]:
        points.append(_count(r["hedge_stacks"], "stacked hedge",
                             "stacked hedges")
                      + ": one calibrated qualifier beats two weak ones.")
        linked += take("hedge_stack")
    if r["novelty_risks"]:
        points.append(_count(r["novelty_risks"], "absolute novelty claim",
                             "absolute novelty claims")
                      + ": soften with 'to our knowledge' and cite the "
                      "nearest work.")
        linked += take("novelty")
    no_limits = False
    if r["limitations_expected"] and structured:
        if r["has_limitations"]:
            points.append("A limitations section is present, so the "
                          "rebuttal is pre-empted.")
        else:
            no_limits = True
            points.append("No limitations section was found: the reviewer "
                          "may supply the rebuttal instead.")
    st = r.get("strangers") or {}
    strangers = 0
    if st.get("count"):
        strangers = 1
        points.append("Sources: " + st["message"])
        evidence += st.get("evidence") or []
        linked += take("stranger")
    elif st.get("assessed"):
        points.append("Sources: every source the Discussion leans on was "
                      "cited before it.")
    links = (r.get("argument") or {}).get("missing_links") or []
    for link in links[:6]:
        points.append(f"Argument: {link['message']}")
        if link["code"] not in [x["kind"] for x in linked]:
            linked += take(link["code"])
    if r["abstract_missing"]:
        points.append("Abstract: " + r["abstract_missing"][0])
    if r["expected_missing"] and structured:
        points.append("Sections a reader of this kind of document expects "
                      "but the headings do not show: "
                      + ", ".join(r["expected_missing"]) + ".")
    if r["not_assessed"]:
        points.append("Not assessed (checks that are off): "
                      + ", ".join(_short(x) for x in r["not_assessed"]))
    worries = (r["overclaims"] + r["hedge_stacks"] + r["novelty_risks"]
               + len(links) + int(gap_point) + int(no_limits) + strangers)
    if not r.get("claims_seen") and worries == 0:
        add("D", "not_applicable",
            "No claims were detected to weigh in this text.", points,
            evidence, linked)
    elif worries == 0:
        add("D", "not_detected",
            "Nothing detected weakens the claims. That is not a judgement "
            "that they are sound.", points, evidence, linked)
    else:
        add("D", "detected",
            _count(worries, "thing was", "things were")
            + " detected that may weaken the claims; see the points.",
            points, evidence, linked)

    # E
    if r["significance"]["present"]:
        add("E", "detected", "The significance is stated.",
            evidence=[r["significance"]["evidence"]],
            links=take("significance"))
    else:
        add("E", "not_detected",
            "No explicit statement of what a reader can do with this was "
            "detected.",
            ["Does the ending widen back out? Say what should change in the "
             "field or in practice, and for whom."])
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
    add(r.get("disclaimer", DISCLAIMER))
    add("Source: " + r["source"])
    return "\n".join(L)

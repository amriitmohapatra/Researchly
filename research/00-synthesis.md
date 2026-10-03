# Researchly — Landscape Research Synthesis

*Compiled 2026-08-10. Synthesizes docs 01–04 in this folder plus the project's writing-craft notes (`The-Craft-of-Scientific-Writing.md`). This is the strategic read; the numbered docs hold the evidence and sources.*

---

## 1. The headline finding: the niche is real, and still open

Across ~120 sources, no shipping tool does what Researchly proposes:

- **Grammarly** is ubiquitous and has the best interaction loop ever built for writing feedback, but it is genre-blind: it over-flags passive voice in methods sections, pushes calibrated hedging toward "confident business English," and cannot tell a rule violation from a genre convention from a taste preference. Its parent company is actively diversifying *away* from writing depth (the 2025 "Superhuman" rebrand).
- **Writefull / Paperpal / Trinka / Curie** are academic but shallow in different ways: Writefull has the best idea in the field (corpus-as-evidence: "here is how published papers phrase this") but offers unexplained diffs; Paperpal and Trinka bolt useful submission checks onto ordinary grammar checking, gated behind reports and credits; none is section-aware at the suggestion level, and none touches statistical or causal wording.
- **LLM-era tools** (Jenni, SciSpace) are generation-first — the opposite posture from what journals allow and what researchers say they want (feedback and critique, not co-writing).
- The closest new competitor in *spirit* is **Springer Nature's Manuscript Adviser** (beta) — document-level feedback, no-training pledge — which validates the demand but operates at manuscript level, not in the writing loop.

Researchly's four-way suggestion taxonomy — **Correction / Improvement / Convention / Preference** — is not implemented by any incumbent, and it turns out to map cleanly onto both the available technology and the UI patterns users already understand.

## 2. The taxonomy maps onto an engineering stack

This was the most convergent finding across the four research streams:

| Type | What powers it | Precedent |
|---|---|---|
| **Correction** | Deterministic rules + edit-tagging GEC (GECToR-style, high precision, minimal edits) | LanguageTool rules; GECToR (Apache-2.0) |
| **Improvement** | LLM minimal-edit rewrite → diffed against source → **each edit typed via ERRANT** → shown as reviewable diff, never auto-applied | "Pillars of GEC" (BEA 2024) ensemble finding; InstaText diff UX |
| **Convention** | Corpus evidence + section/discipline-conditioned rules ("in discussion sections of epi journals, X phrasing occurs at Y frequency") | Writefull Language Search; Cotos's Research Writing Tutor; Vale-style rule packs |
| **Preference** | Off-by-default style rules, per-project config | Vale severity levels; Grammarly per-rule mutes |

Two components make the whole thing coherent:

1. **A markup→plain-text projection layer with offset mapping** (the LTeX+ "annotated text" pattern): parse LaTeX/Quarto/Markdown/docx, strip or dummy-out `\citep{}`, `@keys`, math, chunks — check the prose — map diagnostics back to source positions. This single component kills the #1 academic false-positive source and is what generic tools can't do.
2. **A section/context detector** (IMRaD is trivial; abstract sentence roles via PubMed-200k-RCT-class models; CARS move detection via few-shot LLM): every rule and every threshold conditions on it. "Same sentence, different advice depending on section" — the project's defining requirement — is technically feasible today.

## 3. The differentiator checks have surprisingly good public building blocks

The literature stream (doc 03) found that Researchly's most distinctive ambitions are *not* moonshots:

- **Hedging/certainty meter:** BioScope + CoNLL-2010 (hedge cues, near-solved) + Pei & Jurgens' `certainty-estimator` (pip-installable). Frame as calibration feedback per section — the Toulmin "qualifier" made visible.
- **Causal-language vs study-design mismatch:** Yu et al. 2019's 4-way claim-strength classifier + causal-verb word lists from the 2022 *Am J Epidemiol* audit + a trivial design detector. Near-term, high-value, and essentially uncompeted.
- **statcheck** (p-value consistency) is wrappable today; LLM extraction generalizes it beyond APA format.
- **Reporting-guideline coverage:** CONSORT-TM provides corpus + models as the template. **No STROBE corpus and no EPIFORGE automation exist at all** — an EPIFORGE checker would be first-of-kind, sits exactly in the builder's research field (infectious disease modelling), and is publishable as research, not just buildable as product.

The genuinely research-grade-hard problems: judging whether claim strength fits the *evidence in the paper* (spin detection is still prototype-level), discipline-conditioned convention models at scale, and personalization with demonstrated learning gains (no prior art in scientific writing — also publishable territory).

## 4. The writing-craft notes are directly operationalizable

`The-Craft-of-Scientific-Writing.md` is not just background — its content decomposes into implementable layers:

- **Sentence-level (deterministic or near-deterministic checks):** Gopen & Swan's principles — subject-verb separation distance, nominalization detection ("performed an estimation of" → "estimated"), stress-position analysis, topic-position consistency; "one term, one meaning" terminology-consistency checking; plain-word substitutions (utilize→use). These become the seed **Convention/Preference rule pack**, each rule carrying the guide's own *why* as its explanation text.
- **Paragraph-level:** topic-sentence-first and known–new contract checks — harder, LLM-assisted, revision-time.
- **Document-level (on-demand "review lens"):** CARS move detection in introductions ("I can't find your Move 2 — where is the gap?"), OCAR arc / opening-resolution symmetry, Toulmin decomposition of discussion paragraphs (claim/grounds/warrant/qualifier — "this claim has no qualifier and your grounds are observational").
- **Field-specific (from §9 of the guide):** symbol-defined-at-first-use, uncertainty-reported-with-drivers, "model implies X" vs "world will do X" separation, stratification-justification prompts — several of these align with EPIFORGE items.
- Crucially, the guide's *pedagogical framing* (correction vs improvement vs convention vs preference; explain why, don't just fix) matches what the AWE/tutoring literature says works, and what expert users on HN say they trust (auditable rules).

## 5. Interaction and architecture principles (evidence-backed consensus)

1. **Stage-aware by default:** quiet while drafting, thorough at revision. Repeatedly recommended in the HCI literature; almost no shipping tool does it. Directly matches the guide's "draft ugly, revise in passes" workflow — Researchly can be the first tool aligned with how writing teachers say writing should work.
2. **Precision over recall.** False-positive fatigue is the documented killer of linting tools. Show fewer, better suggestions; track dismissals per rule and attenuate.
3. **Every suggestion explainable** — one-line reason + expandable "learn more," rules auditable. This is the trust currency for expert users and the pedagogical requirement for a developing writer.
4. **Never silently edit.** Tracked changes in Word, diffs everywhere else, engagement-requiring acceptance for substantive rewrites (ownership research; journal authorship policies).
5. **Privacy as architecture, not policy:** local rule tier always; LLM tier opt-in per action. Elsevier/Wiley policies make this a compliance issue, not a preference, for the target user.
6. **Mute is first-class** and lives in a per-project config file that travels with the manuscript.

## 6. Recommended strategic shape (for discussion — not yet decided)

- **Architecture: the orchestrator pattern.** A lightweight core (markup projection + section detection + rule engine) that fans out to pluggable checkers: rules for Corrections/Conventions, optional local or cloud LLM for Improvements (diffed + ERRANT-typed), specialized checkers (hedging meter, causal-language, statcheck) as modules. Candidate foundations: build on **Harper** (Rust, Apache-2.0, LaTeX-aware, LSP+WASM, Weir rule DSL) vs. orchestrate **LanguageTool** behind an HTTP boundary vs. a Python-first prototype (fits the builder's stack) that trades performance for iteration speed. This is decision #1 for the next phase.
- **Delivery order: LSP first** (dogfoodable in the builder's own Quarto/VS Code workflow, no gatekeepers), then **Overleaf browser extension** (proven route, one editor to target), then **Word add-in with tracked changes**. Skip Google Docs, desktop overlays, mobile.
- **Vertical first: epidemiology / health sciences.** The differentiator checks (causal language, hedging, EPIFORGE/STROBE, statcheck) are all health-science-shaped; the builder has domain expertise, writing samples, and a use case (thesis + papers); and the equity-framing sensitivity in the guide's §9.6 has no competitor anywhere.
- **Positioning: assistant, not generator.** Feedback and minimal edits; rewrites behind explicit invocation. Safe under journal policies and matches researcher preferences.

## 7. Open questions for the next session

1. **Build-on decision:** Harper-core + custom rules vs orchestrator-from-scratch vs Python prototype first? (Trade-offs in doc 02 §Implications.)
2. **MVP scope:** which thin slice proves the concept? A candidate: markup-aware checking of a Quarto/LaTeX file with (a) 20–30 Gopen-&-Swan-derived rules, (b) section detection, (c) a hedging meter — delivered via CLI or LSP, tested on the builder's own thesis chapters.
3. **Licensing hygiene:** several attractive GEC checkpoints (CoEdIT) are non-commercial; AESW data terms need verification before any training use.
4. **Evaluation harness from day one:** ERRANT F0.5 for corrections; Liang-et-al-style human-overlap + helpfulness for document feedback; dismissal-rate telemetry as the product metric.
5. **Rule-mining pass on the writing guide:** convert `The-Craft-of-Scientific-Writing.md` into a structured rule inventory (rule, type, section-conditionality, explanation text, examples, testable pattern) — the natural next work item, and it requires no architecture decisions.

## Suggested next phase

Phase 2a: mine the writing guide into a rule inventory (no dependencies, immediately useful).
Phase 2b: concept & architecture document making the build-on and MVP-scope decisions, using docs 01–04 as evidence.
Phase 3: prototype spike — the thin slice above, in whatever stack Phase 2b picks.

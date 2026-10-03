# Researchly Dogfooding Report — v0.1 → v0.1.1

*2026-08-10 · Corpus: 8 accepted PhD theses in infectious disease modelling
(Sample_thesis_drafts/), ~285,000 words of checked prose after extraction
and cleaning.*

## What we did

Extracted text from the 8 thesis PDFs (`pdftotext` + cleaning: de-hyphenation,
paragraph reflow, page-number/header removal, references stripping, heading
preservation for section detection), ran the v0.1 checker over everything,
audited samples of every rule's flags by hand, tuned, and re-ran.

An important framing: these theses were **accepted**. Every flag is therefore
either (a) a stylistic observation an examiner tolerated — possibly still
worth making, but it must be *quiet and typed correctly*, or (b) a false
positive. There is no configuration in which the tool should shout at
accepted writing.

## Headline result

| | v0.1 | v0.1.1 (tuned) |
|---|---|---|
| Total suggestions | 6,010 | **2,868** (−52%) |
| Rate per 1,000 words | 21.0 (≈1 per 48 words) | **10.1** (≈1 per 99 words) |
| Per-thesis spread | 16.9–24.1 | 9.1–11.7 (tight cluster) |
| Tests passing | 37 | 52 (every fix has a regression test) |

v0.1's rate was squarely in the false-positive-fatigue zone the landscape
research warned about (research/04). The audit found the noise concentrated
in six specific, fixable failure patterns — none of which invalidated a
rule's premise; they were all *precision* failures in the implementation.

## What the audit found, rule by rule

**G101 subject–verb separation (1,571 → 779).** The worst offender. Two
failures: (1) headings without terminal punctuation merged into the next
sentence's parse ("Results Selected variables are shown…" → "Results"
became the subject); (2) plain long subject noun phrases ("The coefficient
for a classification of the upper risk decile is…") were flagged, but these
are ordinary academic register — Gopen & Swan's target is the
*interruption*, not subject length. **Fixes:** heading text is now masked
entirely (structural fix in the document layer, benefits every rule); G101
now requires an interrupting structure (comma-bounded clause, relative
clause, apposition, parenthesis) in a gap of ≥10.

**G106 overlong sentence (1,469 → 648).** Empirical calibration: across
three theses, mean sentence length was 28 words, p90 = 48, p95 = 57. A
40-word threshold flagged ~17% of all sentences in accepted writing — that
is not a useful signal. **Fixes:** threshold raised to 50 (targets the
~7% tail); sentences dense in digits/symbols (inline equations, statistics
runs) skipped.

**F601 undefined acronyms (762 → 501, and the outlier tamed).** Three FP
families: ALL-CAPS title pages ("SAW SWEE HOCK **SCHOOL**" — capitalized
words, not acronyms); author initials in reference strings ("Anderson
**KN**,"); currency codes ("**SGD**$10"). One thesis hit 283 flags almost
entirely from these. **Fixes:** caps-zone guard (skip when surrounding
text is mostly uppercase), author-initials pattern guard, currency codes
allowlisted. The outlier thesis dropped 283 → 74; the corpus-wide residue
is mostly real (WAIC, DCT, NPIs used without definition — legitimate
convention prompts).

**G107 noun strings (512 → 119).** The field's terminology *is* noun
compounds: "Markov chain Monte Carlo simulations," "World Health
Organization guideline," "Aedes aegypti." **Fix:** runs containing ≥2
proper nouns, short/non-alpha tokens, or "et al." are treated as
units/citations, not stacks. What survives ("school vacation effect
model," "income quintile contact matrix estimation procedure") is the
real target.

**C303 causal verbs (491 → 138).** The rule's premise held — but it fired
on purpose infinitives ("wash hands **to prevent** transmission" states an
aim, not a finding), on already-calibrated claims ("**might** lead to,"
"we **estimated that** closures averted…"), and on every occurrence
separately (40+ times per chapter = fatigue, not pedagogy). **Fixes:**
purpose-infinitive guard; modal and reporting-frame guards (a hedged or
explicitly modelled claim is already calibrated); aggregation — one
suggestion per verb per section with a count ("14 uses of 'reduce' in this
section").

**G104 passive-with-agent (192 → 63).** "Categorised **by decile**" — a
by-phrase naming a method, not a doer — is not an agent-ful passive. And
"**It** is transmitted by Aedes mosquitoes" is a passive the guide itself
endorses (topic continuity). **Fixes:** agent must contain a proper noun
or person-like word; pronoun subjects skipped.

**C301 hedge stacks (45 → 22).** "Suggests **that** X **may**…" is
conventional reporting-verb phrasing, not a stack; "could **not possibly**"
is a negation idiom. **Fixes:** clause-boundary and negation guards,
window tightened.

**G103 nominalization density (339 → 182).** "Prediction models" and
"notification data" are technical compounds, not buried actions. **Fix:**
nominals acting as compound modifiers no longer count.

**Quiet rules that behaved well:** G102 buried-action (34 flags, clean),
W202 wordy phrases ("prior to" → "before" all through Methods sections —
real and easy wins), W201, C304 bare-"significant" (63 flags, most
legitimate prompts), C302/C305/W205–W207 (low volume, high precision),
G108, G105 ("There are several limitations to…" — the classic Discussion
opener; kept, it's exactly the improvable-but-accepted case the
Improvement type exists for).

## What the residual 10.1/1000w looks like

Sampling the post-tune output: a mix of (1) legitimate craft observations
accepted writing tolerates but could improve on — long interrupted
subjects, "prior to," undefined niche acronyms, bare "significant,"
aggregated causal-verb prompts; and (2) residual PDF-extraction artifacts
(inline sub-headings the cleaner missed, merged paragraphs) that would not
exist in real `.tex`/`.qmd` sources. On source files, the true rate should
land meaningfully below 10/1000w.

## Lessons that go beyond the fixes

1. **Calibrate against accepted literature, not seeded errors.** The unit
   tests all passed while the tool was unusable on real text. The corpus
   run instantly exposed what no synthetic test could: thresholds must come
   from the register's actual distributions (p90 sentence length = 48), and
   "technical usage" exemption lists must come from the field's actual
   vocabulary. This is the Writefull corpus-as-ground-truth paradigm
   (research/01) validated from the false-positive direction — the corpus
   defines not just what to suggest, but what to *tolerate*.
2. **Aggregation is a fatigue-control primitive.** Convention prompts
   (C303) should fire once per pattern per context with a count, not per
   occurrence. This should probably become an engine-level capability
   (any rule can declare itself "aggregate"), not a per-rule hack.
3. **Structural fixes beat rule fixes.** Masking heading text in the
   document layer fixed a failure class across four rules at once. The
   markup/projection layer is where precision is won.
4. **PDFs are a hostile input.** Reference lists, all-caps front matter,
   equation soup, and merged paragraphs caused a large share of v0.1's
   noise. The tool's home is source files (`.qmd`/`.tex`/`.md`); PDF
   support, if ever, needs its own cleaning pipeline (the dogfood scripts
   are a start).
5. **Every fix is a regression test.** 15 new don't-fire tests now encode
   these precision promises permanently (52 total).

## Recommended next steps

1. **Dogfood on your own drafts in source form** (`.qmd`/`.tex`) — the
   corpus was the stress test; your drafts are the real workload and will
   generate the accept/dismiss signal that matters.
2. **Dismissal telemetry** — log accept/dismiss per rule (even just to a
   local file) to drive the next tuning round with data (the research/04
   "track dismissals and attenuate" principle).
3. **Engine-level aggregation** for convention rules (generalize the C303
   pattern).
4. **v0.2 candidates from the corpus experience:** per-chapter References
   detection (skip zones), a "list of abbreviations" awareness for F601
   (an acronym defined in a front-matter list is defined), and the hedging
   meter upgrade (the C301/C303 machinery is the natural base).

## Corpus numbers (v0.1.1)

| Thesis | Words | Flags | /1000w | Top rules |
|---|---|---|---|---|
| ChenY | 25,814 | 265 | 10.3 | G101, G106, C303 |
| Koh Wee Ming | 31,630 | 288 | 9.1 | G101, G106, F601 |
| LimJT | 51,236 | 496 | 9.7 | G101, G106, G103 |
| COVID-19 modelling | 32,547 | 310 | 9.5 | F601, G101, G106 |
| PremK | 32,731 | 351 | 10.7 | G101, G106, F601 |
| Sun Haoyang | 30,510 | 357 | 11.7 | G106, G101, W202 |
| ZHAOZX | 31,384 | 295 | 9.4 | G101, G106, F601 |
| Chao Fengqing | 48,691 | 506 | 10.4 | G101, G106, F601 |

Rule totals (v0.1 → v0.1.1): G101 1571→779 · G106 1469→648 · F601 762→501 ·
G107 512→119 · C303 491→138 · G103 339→182 · G104 192→63 · C301 45→22 ·
others unchanged (already precise).

# Researchly Rule Inventory — v0.2

*Phase 2a deliverable · Mined from `The-Craft-of-Scientific-Writing.md` · 2026-08-10.*
*v0.2 (same day): +10 rules mined from the `Notes_on_writing/` corpus — Dr
Akira Endo's scientific-writing lecture (E7xx), the NG5001 Academic
Communication course (L901, AB801), and Shehzad 2008 on CARS Move 2 (D902).
Full per-document provenance in `knowledge-base.md`. Layer 7 below.*

Every actionable heuristic in the writing guide, converted into a typed rule entry. This is the knowledge asset the prototype (and every later version) runs on. Each rule carries the guide's own reasoning as its explanation — the tool should teach, not just flag.

**Types** (from the project brief):

- **Correction** — objectively problematic (grammar, logic, statistics).
- **Improvement** — acceptable, but an alternative is clearer. Default: shown.
- **Convention** — common practice in scientific writing / a field. Default: shown, clearly labeled as convention, never as error.
- **Preference** — subjective. Default: off or muted-by-default; user opts in.

**Status codes:** `MVP` = in the v0.1 Python prototype (deterministic, spaCy/regex). `DET` = deterministic, feasible next. `LLM` = needs LLM assistance. `RES` = research-grade (see research/03).

**Plain explanations (P35, 2026-10-08):** every rule carries a `plain=` text beside its `why=`: the same advice in everyday words, for a writer who knows their science but not the grammar vocabulary (owner feedback from the first real use). The cards show the plain text first and the technical why behind it. Neither may mention this repository's internals: `tests/test_explanations.py` fails on a section number, a course code, a lecturer's name, a book citation or a command-line instruction in any user-visible text. Citations live on the Source line only.

**Scope and Draft mode (S3, 2026-10-04):** every rule declares a scope. *Sentence* rules judge the sentence in front of the writer; *document* rules need the whole document. Draft mode (P1) shows sentence-level rules only and says how many document-level suggestions it held back; Revise shows everything. Document-level today: X101–X104, X202, X301, X401, X501, F601, F612, F613, N101, W211, D902, AB802 (`GET /v1/rules` reports each rule's `scope`).

**Article-type profiles (S4, 2026-10-08; owner request):** `researchly/profiles.py`. A profile says what kind of document the sections belong to: which checks do not apply (each with a plain reason the cards show), what section unheaded prose is in, and what a reader of that kind expects (the review lens). Types: auto, general, manuscript, thesis-chapter, abstract, commentary, policy-brief, grant, response-to-reviewers. Commentary and policy brief (the owner's field first) switch off the abstract moves (AB801, AB802), the gap statement (D902) and the hedging prompts (C302, C303), and read their body as argued like a Discussion; "abstract" judges a pasted abstract whole; response-to-reviewers drops the float checks (X101–X104). "auto" guesses only from strong signals (IMRaD headings, a chapter, a recommendations heading) and is otherwise "general", the engine as before. `GET /v1/rules` lists the profiles; `options.document_type` chooses one per request and the account saves it.

**Section-conditioning:** rules may fire differently by IMRaD section (detected from headings in v0.1). This is the defining Researchly behavior — the same sentence gets different advice in Methods vs Discussion.

---

## Layer 1 — Sentence mechanics (Gopen & Swan; guide §5.2)

| ID | Rule | Type | Sections | Status |
|---|---|---|---|---|
| G101 | Subject–verb separation | Improvement | all | MVP |
| G102 | Buried action / light-verb nominalization | Improvement | all | MVP |
| G103 | Nominalization density | Improvement | all | MVP |
| G104 | Passive voice (section-aware) | Convention | not Methods | MVP |
| G105 | Expletive opener ("There is/are…", "It is … that") | Improvement | all | MVP |
| G106 | Overlong sentence | Improvement | all | MVP |
| G107 | Long noun string | Improvement | all | MVP |
| G108 | Weak stress position (trailing qualifier/attribution) | Improvement | all | MVP |
| G109 | Topic-position consistency across a passage | Improvement | all | LLM |
| G110 | Context-before-novelty ordering | Improvement | all | LLM |

**G101 — Subject–verb separation.** Readers hold their breath from subject to verb; long interruptions drain emphasis. Flag ≥10 tokens between a subject and its governing verb *when an interrupting structure (comma-bounded clause, relative clause, apposition, parenthesis) sits in the gap* — plain long subject noun phrases are ordinary academic register (v0.1.1 dogfooding tune). *P31 (Q3):* a comma that only separates list items, or brackets holding a citation or a 1–2-word abbreviation, is not an interruption; a restrictive relative clause, participle or bare apposition counts only at ≥15 tokens (it is part of the subject). *"The model, which incorporates income quintiles, seasonal forcing, and age structure, and was fitted using cmdstanR, predicts…"* → move the machinery after the verb. (Guide §5.2.1.)

**G102 — Buried action.** English readers look for the action in the verb. Light verb + nominalization ("we performed an estimation of R₀", "a comparison was made") goes limp; turn the noun back into the verb ("we estimated R₀", "we compared"). Trigger: {perform, conduct, make, carry out, undertake, provide, execute, achieve, do} + direct object ending in -tion/-sion/-ment/-ance/-ence/-sis/-al. (§5.2.4.)

**G103 — Nominalization density.** ≥3 derived nominals in one sentence reads as fog even when each is individually fine. Hunt the -tion/-ment/-ance words; prose "comes alive and shortens by a third." (§5.2.4.)

**G104 — Passive voice, section-aware.** Active and passive both have jobs: passive is *correct* when the doer is irrelevant ("Samples were incubated at 37 °C") — so this rule is **silent in Methods** and gentle elsewhere; flags only passives with an easily recoverable agent ("was shown by X"). Choose by what belongs in the topic position, "not by superstition." This inversion of Grammarly's most-hated behavior is deliberate. (§6; research/01 §4-AVOID.)

**G105 — Expletive openers.** "There are three factors that drive…" wastes the topic position; "Three factors drive…" doesn't. (§5.2.3/§6 cut-clutter.)

**G106 — Overlong sentence.** >50 words: not an error, but check whether it's one idea; suggest split points at coordinators. (Threshold set empirically: p90 sentence length in 8 accepted theses was 48 words — 40 flagged 17% of all sentences; v0.1.1 dogfooding tune.) (§5.1, §8 read-aloud test.)

**G107 — Long noun string.** ≥4 consecutive nouns ("income quintile contact matrix estimation procedure") forces the reader to unpack backwards; insert prepositions. (§6 plain-words principle applied to syntax.)

**G108 — Weak stress position.** The end of the sentence is where emphasis lives. Sentences trailing off in attribution/qualification ("…, according to our simulations", "…, as shown in Table 2") bury the finding mid-sentence. Move the key result to the end. (§5.2.2.)

## Layer 2 — Words and tone (guide §6)

| ID | Rule | Type | Sections | Status |
|---|---|---|---|---|
| W201 | Plain-word substitutions (utilize→use, prior to→before, …) | Improvement | all | MVP |
| W202 | Wordy phrases (due to the fact that→because, in order to→to, …) | Improvement | all | MVP |
| W203 | Hype/buzzwords (novel, cutting-edge, paradigm-shifting) | Convention | all | MVP |
| W204 | Intensifiers (very, extremely, really, quite) | Preference | all | MVP |
| W205 | Filler throat-clearing ("It should be noted that…") | Improvement | all | MVP |
| W206 | Redundant pairs ("each and every", "completely eliminate") | Improvement | all | MVP |
| W207 | Doubled word ("the the") | Correction | all | MVP |
| W208 | Contractions in formal prose | Convention | all | MVP |
| W209 | "In terms of" | Preference | all | MVP |
| W210 | One term, one meaning (elegant-variation detection) | Convention | all | LLM |
| W211 | 10% condensing pass | Improvement | all | LLM |

**W203 — Hype.** Buzzwords signal thin substance; "let the numbers carry the weight." Convention, not error — "novel" survives review in some venues; flag, explain, let the author decide. **W205 — Filler.** "It is important to note that X" = "Note that X" = usually just "X." **W208 — Contractions.** Convention of register, not grammar.

## Layer 3 — Calibration, claims, statistics (guide §4, §9.3, §9.4; Toulmin)

| ID | Rule | Type | Sections | Status |
|---|---|---|---|---|
| C301 | Hedge stacking ("may possibly suggest") | Improvement | all | MVP |
| C302 | Overclaiming verbs (prove, establish, demonstrate conclusively) | Convention | Results/Discussion | MVP |
| C303 | Causal verbs — design check prompt (increase, reduce, drive, cause) | Convention | Results/Discussion/Abstract | MVP |
| C304 | Bare "significant" (statistical vs substantive ambiguity) | Convention | Results/Discussion | MVP |
| C305 | Assertive adverbs (clearly, obviously, of course) | Convention | all | MVP |
| C306 | Uncertainty reported with its drivers (interval + source) | Convention | Results | LLM |
| C307 | "Model implies X" vs "world will do X" separation | Convention | Discussion | LLM |
| C308 | Warrant made explicit (Toulmin audit of Discussion paragraphs) | Improvement | Discussion | LLM |
| C309 | Qualifier calibrated to grounds (over/under-hedging vs evidence) | Improvement | Discussion | RES |
| C310 | Pre-empted rebuttal present in Limitations | Improvement | Limitations | LLM |
| C311 | statcheck-style p-value/statistic consistency | Correction | Results | DET |

**C301 — Hedge stacking.** "Qualifiers are strength, not weakness" — but stacked hedges ("it might possibly be tentatively suggested") are as much a calibration failure as overclaiming. One hedge per claim. (§4.2.)
**C302 — Overclaiming.** Reserve *demonstrates/establishes* for strong evidence; "prove" almost never belongs in empirical science. (§4.2.) *P31:* "prove" is left alone in a sentence with maths or proof vocabulary (theorem, lemma, conjecture, a proof assistant): in mathematics a proof is the evidence.
**C303 — Causal verbs.** *Reduce, increase, drive, prevent, affect* assert causation. Fires as a **prompt, not a verdict**: "this is a causal claim — does the study design support it?" (The design-aware version is the research/03 near-term differentiator; v0.1 just teaches the distinction.) (§9.4; AJE 2022 word lists.) *P31:* change verbs (*increase, decrease, reduce, lower, raise, improve, worsen*) fire only with an object or in the passive — "cases increased" describes a change, "X increased Y" claims a cause.
**C305 — Assertive adverbs.** "Clearly" asserts what structure should show; if it were clear, the word would be unnecessary. (§4/§6.)

## Layer 4 — Paragraph structure (guide §5.1)

| ID | Rule | Type | Status |
|---|---|---|---|
| P401 | One paragraph, one idea (can't summarize in one sentence → split) | Improvement | LLM |
| P402 | Topic sentence first (point stated up front, not as punchline) | Improvement | LLM |
| P403 | Known–new contract (old info opens each sentence, new closes it) | Improvement | LLM |
| P404 | Paragraph length outlier | Improvement | DET |

## Layer 5 — Document structure (guide §2, §3; OCAR, CARS)

| ID | Rule | Type | Status |
|---|---|---|---|
| D501 | CARS moves present in Introduction (M1 territory / M2 gap / M3 occupation) | Improvement | LLM |
| D502 | M2 niche sentence detectable (contrastive turn: "however/yet/remains unclear") | Improvement | DET+LLM |
| D503 | Lock-and-key: gap named in M2 = gap filled in M3 | Improvement | RES |
| D504 | Resolution returns to Opening (hourglass closes) | Improvement | LLM |
| D505 | O/R width match (overpromise/undersell audit) | Improvement | RES |
| D506 | Drafting-order coach (figures→results→…) — workflow feature, not a rule | — | future |

These become the on-demand **"review lens"** pass (research/04: coaching-style document feedback, distinct from inline checking) — not v0.1.

## Layer 6 — Field-specific (guide §9)

| ID | Rule | Type | Sections | Status |
|---|---|---|---|---|
| F601 | Acronym defined at first use | Convention | all | MVP |
| F602 | Cross-discipline term defined once (WAIFW, next-generation matrix…) | Convention | all | LLM |
| F603 | Every symbol defined with units at first use | Convention | Methods | LLM |
| F604 | Equation introduced → displayed → interpreted | Convention | Methods | LLM |
| F605 | Notation consistency across paper (β means one thing) | Correction | all | LLM |
| F606 | Reproducibility completeness (versions, priors, diagnostics, availability) | Convention | Methods | LLM |
| F607 | EPIFORGE checklist coverage | Convention | doc-level | RES (first-of-kind) |
| F608 | Stratification justified, not just mechanized (equity) | Improvement | Methods | LLM |
| F609 | Burden vs data-generating-assumption disparity language (equity) | Improvement | Results/Discussion | RES |
| F610 | Mechanism-not-attribute framing for group differences (equity) | Improvement | Discussion | LLM |
| F611 | Figure caption states the figure's point (topic sentence for figures) | Improvement | captions | LLM |

F607–F610 are the thesis-aligned, nobody-else-has-this rules. F601 is the one deterministic representative in v0.1. *P31:* F601 skips Roman numerals ("phase III"), journal names (BMJ, BMC, PLOS, JAMA, NEJM) and GDP/UV/ROC/AUC.

---

## Layer 7 — Course-corpus rules (v0.2; sources: Endo lecture, NG5001, Shehzad 2008, Pallas 2022)

| ID | Rule | Type | Sections | Status |
|---|---|---|---|---|
| E701 | Empty phrases ("sheds light on", "holistic understanding") | Convention | all | MVP |
| E702 | Adversative-opener runs (However… However…) | Improvement | all | MVP |
| E703 | Naked sentence-initial "This" + verb (after long sentences) | Improvement | all | MVP |
| E704 | "Is known/considered to be" without citation | Convention | all | MVP |
| E705 | Absolute novelty claim without "to our knowledge" | Convention | all | MVP |
| E706 | "Relatively" without comparator | Convention | all | MVP |
| E707 | "Figure 1 shows…" opener — lead with the finding | Improvement | Results | MVP |
| AB801 | "Results will be discussed" — vague abstract forward reference | Convention | Abstract | MVP |
| L901 | "There are many studies on…" — serial-summary lit-review opener | Improvement | all | MVP |
| D902 | Introduction lacks a detectable gap statement (Shehzad niche signals) | Improvement | doc-level | MVP |

All aggregate per section where repetition would nag (E701, E704–E707,
AB801, L901). E703 fires only when the preceding sentence is ≥18 words
(Endo's own scope: ambiguity needs candidates). E704 is silenced by an
in-sentence citation; E705 by a "to our knowledge" softener; D902 requires
an Introduction section of substance and searches for Shehzad's three
signal classes (contrastives; limited/few/little; none-of/not-been/no-study).

## Layer 8 — Structure and consistency (S2b, 2026-10-04; owner decisions P2, P4)

Structural checks read `researchly/structure.py`: floats (figures and tables with number, label, caption) and the text that cites them (`\ref`, preamble and style `\figref` macros, written "Figure 2", ranges). They run on LaTeX and Word only; pasted plain text has no reliable structure and gets none. Consistency checks compare a document with itself, never with a house style.

| ID | Rule | Type | Docs | Source | Status |
|---|---|---|---|---|---|
| X101 | Figure or table never cited in the text (a citation from another float's caption counts) | Convention | LaTeX, Word | ICMJE | S2b |
| X102 | Figures/tables first cited out of numerical order (per chapter; appendix floats exempt) | Convention | LaTeX, Word | ICMJE | S2b |
| X103 | Cross-reference to an undefined label ("??"), or "Figure 5" with four figures | Correction | LaTeX, Word | ICMJE | S2b |
| X104 | Figure/table placed before the text first cites it | Convention | Word | ICMJE | S2b |
| X202 | Caption under five words | Improvement | LaTeX, Word | §9.7 | S2b |
| X301 | Numbered equation never referred to | Preference | LaTeX | §9.2 | S2b |
| X302 | A displayed equation that is not part of a sentence: the text before it ends with a full stop (abbreviations such as "e.g." and "Eq." excepted). LaTeX: equation environments. Word: an equation object alone in its paragraph (an uploaded .docx; its number may follow), or a paragraph of maths written as text with no ordinary word (the add-in reads text only, so an equation object arrives in its linear form; a PDF conversion flattens one the same way). Equations inside a sentence's paragraph are inline and not judged. 5 of 102 equations on the 17 real LaTeX projects, all genuine; none on the 36 real Word files (their equations are led in or follow a colon) | Convention | LaTeX, Word | §9.2 (the owner's professor made the same correction) | P35 |
| X401 | Decimal or percentage quoted with "Table N" that Table N does not hold (rounding allowed; levels, versions and totals skipped) | Correction | LaTeX, Word | §6 | S2b |
| F612 | Abbreviation defined twice (abstract, a new chapter, captions and definitions 3,000+ words apart exempt) | Convention | all | §9.1 | S2b |
| F613 | Abbreviation defined but then used once or not at all | Preference | all | §9.1 | S2b |
| N101 | Number–unit spacing mixed ("5 %" and "5%"; °C, mg, km…) | Convention | all | SI Brochure | S2b |
| N102 | Sentence begins with a numeral (years and list items exempt) | Convention | all | AMA Manual of Style | S2b |
| W211 | Compound written closed and open/hyphenated ("dataset"/"data set") | Convention | all | §9.1 | S2b |
| X501 | Paragraph of body text in a heading style: a heading run into its paragraph ("1 Introduction How will…"), or a table row styled as a heading. The heading is split off when it is numbered; the rest is checked as prose | Correction | Word | Word heading styles | P33 |

Definitions ("full name (ACR)") are found with Schwartz & Hearst's (2003) algorithm, so notation such as "A(H1N1)" or panel letters "(D–F)" is not taken for a definition.

Tried and dropped: **X203** abbreviation in a caption not defined there (79 flags on 17 real LaTeX projects, nearly all product names, chemical formulae, coders' initials). Deferred: **X201** missing caption (a captionless float has no prose to anchor a suggestion to), equation symbols defined (F603), tense consistency per section (no named source yet).

## Layer 0 — Commodity spelling & grammar (v0.3; integrated open source)

| ID | Rule | Type | Backend | Status |
|---|---|---|---|---|
| S001 | Spelling (unknown words, top-3 suggestions) | Correction | symspellpy (MIT), always on | MVP |
| LT001 | Grammar: agreement, verb forms, a/an, confusions | Correction | LanguageTool via language_tool_python (local server, Java), optional | MVP |
| GEC001 | Learned corrections: minimal token-level edits (GECToR-style), opt-in `[tiers] gec = true`, abstains without a local model | Correction | local edit tagger scaffold (`gec.py` + `rules_gec.py`), tier="gec", never auto-applied, confidence-gated, masked-span-safe (test_gec.py) | 2026-08-14 scaffold |

Phase-1 deliberately deferred this tier ("integrate, don't rebuild");
added after desktop dogfooding exposed the gap. S001 precision guards:
shipped scientific lexicon (`researchly/data/scientific_terms.txt`),
personal dictionary (`researchly dict add`), UK/US variant mapping,
morphological fallback (closed-class words exempt — "thiss" ≠ "this+s"),
regex word scan (spaCy tokenizer splits some typos), 3+-use learned terms,
proper-noun skip (sentence-start capitalized words need a distance-1
correction to be flagged), author names followed by initials or "et al"
(P31). Reference-list sections ("References", "Bibliography") are masked
for every rule (P31). LT001 keeps grammar/duplication/confusion
categories only — LanguageTool's spelling (MORFOLOGIK) and style stay off
so the tiers never overlap with S001 or Researchly's own rules. P31 (Q3)
skips LanguageTool rules that misread scientific prose, each counted on the
thesis corpus and the owner's report (`rules_grammar.SKIP_MISREAD_RULES`):
the compound-spelling family (`EN_COMPOUNDS_*`, `MAKER_COMPOUNDS`),
`NON_STANDARD_WORD` (maths and code), `THE_SUPERLATIVE` ("least squares"),
`NUMBERS_IN_WORDS`, `POSSESSIVE_APOSTROPHE`, `I_LOWERCASE`, `THE_PUNCT`,
`EN_SPECIFIC_CASE`, `ADMIT_ENJOY_VB`.

## v0.1 MVP rule set (implemented in the prototype)

24 rules: G101–G108, W201–W209, C301–C305, F601, plus:

| ID | Rule | Type | Status |
|---|---|---|---|
| M901 | Sentence-length / nominalization / hedge-density document metrics (report, not flags) | — | MVP |

Selection logic: everything deterministic with spaCy POS/dependency + curated lexicons, tuned for **precision over recall** (research/04: false-positive fatigue is the tool-killer). Every rule ships with: one-line message, "why" paragraph traceable to the guide, bad→better example, section-conditioning, and a mute switch.

## Deliberate v0.1 exclusions

- **LLM-assisted layers (P4xx, D5xx, C306–C310, F6xx):** need the on-demand review-lens interaction (research/04) — next phase, after the inline loop feels right.
- **Terminology consistency (W210, F605):** high value but needs careful design to avoid false positives on legitimate variation; candidates for v0.2.
- **statcheck wrap (C311):** deterministic and proven, but epi papers rarely use APA format; do it when the LLM extractor generalizes it.
- **Grammar-proper (agreement, articles):** LanguageTool/Harper do this well; Researchly shouldn't rebuild commodity checks (research/02) — integrate later, differentiate now.

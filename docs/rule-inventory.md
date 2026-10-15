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

**Scope and Draft mode (S3, 2026-10-04):** every rule declares a scope. *Sentence* rules judge the sentence in front of the writer; *document* rules need the whole document. Draft mode (P1) shows sentence-level rules only and says how many document-level suggestions it held back; Revise shows everything. Document-level today: X101–X104, X202, X301, X401, X501, F601, F612, F613, N101, W211, D902, D903, AB802, GN106, GN107, GN207 (`GET /v1/rules` reports each rule's `scope`).

**Article-type profiles (S4, 2026-10-08; owner request):** `researchly/profiles.py`. A profile says what kind of document the sections belong to: which checks do not apply (each with a plain reason the cards show), what section unheaded prose is in, and what a reader of that kind expects (the review lens). Types: auto, general, manuscript, thesis-chapter, abstract, commentary, policy-brief, grant, response-to-reviewers. Commentary and policy brief (the owner's field first) switch off the abstract moves (AB801, AB802), the gap statement (D902, and D903 since 2026-10-14) and the hedging prompts (C302, C303), and read their body as argued like a Discussion; "abstract" judges a pasted abstract whole; response-to-reviewers drops the float checks (X101–X104). "auto" guesses only from strong signals (IMRaD headings, a chapter, a recommendations heading) and is otherwise "general", the engine as before. `GET /v1/rules` lists the profiles; `options.document_type` chooses one per request and the account saves it.

**Learn cards and reporting checklists (S4c, 2026-10-08):** every rule's suggestion carries a `learn_ref` to one of 26 Learn cards (`researchly/learn.py`; provenance in `knowledge-base.md` §12). The epidemiology pack (`researchly/packs/`) adds STROBE, CONSORT, PRISMA and EPIFORGE checklists, requested with `options.checklist` or suggested from the text. They are not rules: each item says "reported" with its sentence or "needs your check", never "missing", and none enters the flag counts or the noise floor.

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
| W208 | Contractions in formal prose; offers the full form ("do not"), and catches contractions typed without the apostrophe ("dont") | Convention | all | MVP; full forms 2026-10-14 |
| W209 | "In terms of" | Preference | all | MVP |
| W210 | One term, one meaning (elegant-variation detection) | Convention | all | LLM |
| W211 | 10% condensing pass | Improvement | all | LLM |
| W212 | Uncountable noun given a plural ("softwares", "informations"; "criterias") | Correction | all | 2026-10-14 (Swan, *Practical English Usage*) |
| W213 | A spelling of another English than the one chosen in the settings ("color" in a British paper); runs only when `spelling` is not `auto` | Convention | all | 2026-10-14 (VarCon) |

**W203 — Hype.** Buzzwords signal thin substance; "let the numbers carry the weight." Convention, not error — "novel" survives review in some venues; flag, explain, let the author decide. **W205 — Filler.** "It is important to note that X" = "Note that X" = usually just "X." **W208 — Contractions.** Convention of register, not grammar. An acronym's possessive ("WHO's") is never a contraction (found on the owner's own .tex, P41). Since 2026-10-14 the card offers the full form when it has one reading ("it's been" is "it has been", so the 's forms get no fix before "been"/"got"), and catches the apostrophe-less forms an everyday keyboard would "fix" to the contraction ("dont" → "do not"); words that are also real words (cant, wont, lets, its, were, well, ill, im) are left out, and S001 leaves these to W208 so the writer sees one card. **W213 — Chosen spelling.** With `spelling = "uk" | "uk-oxford" | "us" | "ca" | "au"` (TOML `[document] spelling`, request `options.spelling`), every spelling VarCon assigns only to other dialects is flagged, once per occurrence, with its spelling in the chosen one; names (a capital mid-sentence, "Centers for Disease Control") are left alone, and words both dialects use in some sense ("meter" the device, "program" software, "tire" to fatigue) never fire. W210 steps aside when a spelling is chosen. VarCon's Canadian and Australian codes are partial, so those choices are quiet rather than wrong. **W210, 2026-10-14:** pairs now come from VarCon (9,281, sense-aware) as well as the curated list, a curated pair VarCon contradicts is dropped (analyses/analyzes: "analyses" is also the US plural), and a mixture is resolved towards the dialect the whole document mostly uses ("The document mostly uses British spelling (5 of 7 words that differ)"). **S002 — Real-word confusions.** Both spellings are words, so S001 passes them; S002 compares log P(word | neighbours) for the typed word and its listed confusion and speaks only when the other is about 150 times likelier and attested on both sides. Pairs are one-way (principle → principal, never principals → principles). than/then and from/form were tried and left to LanguageTool: word pairs misjudged "rather than consider" and "samples form the posterior". On 1.03 M words (8 theses + 115 PMC articles): 3 flags, all genuine slips. Known limit: a literal "the trail was" can be questioned. **W212 — Uncountable plurals.** Mass nouns (information, software, hardware, equipment, advice) take no -s; Latin plurals (data, criteria, phenomena, bacteria, stimuli) take no second one. Words with a correct countable or verb reading stay out ("researches", "evidences", "progresses", "climate feedbacks", "knowledges"). In the eight theses it would flag "softwares" twice.

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

These became the on-demand **narrative map** (S4, 2026-10-08; `researchly/discourse/moves.py`, `narrative.py`): D501/D502 are the Introduction strip (territory, gap, aim, with Swales and Shehzad as sources); D504 is the Discussion strip's "what should change" and the Conclusion strip (guide §2, the hourglass); D503 and D505 remain research-grade. The map is not a rule: it is per-section moves present, missing or out of order, each missing one with an authored question, a lesson and a fill-in frame, plus the argument's missing links and the hedging trajectory. Requested with `options.narrative` on every analysis route; `researchly narrative` on the CLI. Provenance: `docs/knowledge-base.md` §11.

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

## Layer 7 — Course-corpus rules (v0.2; sources: Endo lecture, NG5001, Shehzad 2008, Pallas 2023)

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
| D903 | Gap stated as a bare absence ("remains underexplored", "has been overlooked", "little is known") with no stake in it, the sentence before or the two after (what fails, who pays, what is decided without the answer, an untested assumption) | Improvement | Introduction (doc-level) | 2026-10-14 |
| D904 | "Fills / addresses / bridges the gap" (a knowledge gap) with no ruling: say closed, narrowed, reframed or reopened | Improvement | Discussion, Conclusion | 2026-10-14 |
| D905 | Generic call for future research ("Further research is needed", "Future work should explore this") naming nothing that is still open | Improvement | Discussion, Limitations, Conclusion | 2026-10-14 |

All aggregate per section where repetition would nag (E701, E704–E707,
AB801, L901). E703 fires only when the preceding sentence is ≥18 words
(Endo's own scope: ambiguity needs candidates). E704 is silenced by an
in-sentence citation; E705 by a "to our knowledge" softener; D902 requires
an Introduction section of substance and searches for Shehzad's three
signal classes (contrastives; limited/few/little; none-of/not-been/no-study).

**The gap as an argument (2026-10-14; a thesis-writing workshop, shown to
users as the owner's learnings, with Alvesson & Sandberg 2011, Sandberg &
Alvesson 2011, Bunton 2005, Kwan 2006 and Lim 2006 by name; provenance in
`knowledge-base.md` §13).** D903–D905 aggregate per section and offer no
replacement (nothing is drafted for the writer). D903 runs on an
Introduction heading only, stays quiet when any stake signal is near the
gap (`lexicons.STAKE_RX`, deliberately broad), leaves question-raising
gaps ("it is unclear whether") alone, defers to E705 on an unsoftened "has
not been studied" (one card per span), and is off for commentary, policy
brief and response to reviewers. D904 skips a partial or negated claim
("partly fills", "does not fill"), an aim ("to fill this gap"), "closes the
gap" (a ruling) and literal gaps ("the immunity gap", "the gap between
modelling and policy", "this gap in coverage"). D905 fires only when every
word of the sentence other than the call itself is generic
(`lexicons.GENERIC_FUTURE_WORDS`). Not rules, and not counted in the noise
floor: **strangers**, sources cited in two or more sentences of the
Discussion and nowhere before it, shown as the narrative map's
`stranger_sources` link and in the brief's question D
(`discourse/citations.py`; abstains without a review section or with fewer
than three readable citations in it); and two thesis-chapter moves on the
map, Methods "what the design cannot show" and Conclusion "what is still
open".

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
| X401 | Decimal or percentage quoted with "Table N" that Table N does not hold (rounding allowed; levels, versions and totals skipped). **Row and column (Codex #7, 2026-10-14):** `researchly/tables.py` reads the table as a grid (LaTeX: the float's one `tabular`/`tabularx`/`longtable`, with `\multicolumn` spans, `\multirow` labels filled down, rules and footnote marks dropped; Word: an uploaded .docx gives each cell `[table, row, col, colspan]`). Header rows are the leading rows with no results; label columns the leading columns with no results; a label row with nothing else in it heads a group of rows. When the sentence names one row (or one group, or a group and a row) and/or one column (or a column group and a leaf header), the number nearest the row's name must be in that cell, or in that row or column when only one is named. The message names the cell and what it holds, the rounding ("holds 4.13 (4.1 when rounded to 1 decimal place), not 4.2"), and where the number is instead ("6.2 is in row '30–44' — a value from the wrong row / group / column?"). A proportion never matches a percentage (said as such), and a rate base that differs from the column's ("per 10,000" against "per 1,000"), or a percentage against a rate column, is flagged. **Abstains** (back to "anywhere in the table") when two rows or two columns are named at the same level, the sentence compares or derives (than, versus, respectively, ratio, fold, increase…), the column is named in another clause than the number, the named cells hold no number of the quoted kind ("in most cases" is not the Cases column), the float has no single readable grid (two tabulars, `\captionof`, nested Word tables, a cell in a content control), or the cells come from the Word add-in, which sends no row or column. Plain text and Markdown have no tables here. A flag compared with one cell (the row and column named, or a row or column that holds only one number) carries `table_evidence` (table, 0-based row and column, headers without units, the cell's offsets and text, its value as the text would quote it, the number quoted, the rounding allowed); a row or column with several numbers, or a number nowhere in the table, carries none. Tests: `tests/test_table_cells.py`, `services/engine/tests/test_table_cells_service.py` | Correction | LaTeX, Word | §6 | S2b; rows and columns 2026-10-14 The local Word add-in sends each table paragraph's cell place (P42), so in Word the cell rules apply too. |
| F612 | Abbreviation defined twice (abstract, a new chapter, captions and definitions 3,000+ words apart exempt) | Convention | all | §9.1 | S2b |
| F613 | Abbreviation defined but then used once or not at all | Preference | all | §9.1 | S2b |
| N101 | Number–unit spacing mixed ("5 %" and "5%"; °C, mg, km…) | Convention | all | SI Brochure | S2b |
| N102 | Sentence begins with a numeral (years and list items exempt) | Convention | all | AMA Manual of Style | S2b |
| W211 | Compound written closed and open/hyphenated ("dataset"/"data set") | Convention | all | §9.1 | S2b |
| X501 | Paragraph of body text in a heading style: a heading run into its paragraph ("1 Introduction How will…"), or a table row styled as a heading. The heading is split off when it is numbered; the rest is checked as prose | Correction | Word | Word heading styles | P33 |

Definitions ("full name (ACR)") are found with Schwartz & Hearst's (2003) algorithm, so notation such as "A(H1N1)" or panel letters "(D–F)" is not taken for a definition.

Tried and dropped: **X203** abbreviation in a caption not defined there (79 flags on 17 real LaTeX projects, nearly all product names, chemical formulae, coders' initials). Deferred: **X201** missing caption (a captionless float has no prose to anchor a suggestion to), equation symbols defined (F603), tense consistency per section (no named source yet).

## Layer 9 — Researchly grammar notes (S4d R6, 2026-10-15; ADR-11)

Rules written for Researchly at build time from general knowledge of English grammar and its regional usage; the source document is [`grammar-notes.md`](grammar-notes.md) (source code `rgn`, shown as "Researchly grammar notes"), in Researchly's own words with further reading at its end. Module `researchly/rules_grammar_notes.py`; tests `tests/test_grammar_notes.py` (fire, don't-fire and dialect gating for every rule). Regional notes follow the `spelling` setting: "British-pattern" means `uk`, `uk-oxford`, `au` and `in`; under `auto` they speak only about a document's own mixtures. None is a Correction until its precision on the real-document bench is measured at 0.9 or more. LanguageTool's a/an card (`EN_A_VS_AN`) steps aside for the abbreviations GN206 lists, so the writer sees one card with the pronunciation.

| ID | Rule | Type | English | Scope | Theses (auto) |
|---|---|---|---|---|---|
| GN101 | Group noun (team, committee, cohort…) with "are/were/have/do"; not before "of" + plural | Convention | US | sentence | 0 (1 under US, a true one) |
| GN102 | "different than" (British-pattern) / "different to" (US, CA) → "different from"; comparisons and "different to the reader" exempt | Convention | by choice | sentence | 0 |
| GN103 | "gotten" → "got" | Convention | British-pattern | sentence | 0 |
| GN104 | "whilst" → "while" | Convention | US | sentence | 0 (5 under US) |
| GN105 | "was/were fit to/using…" → "fitted"; "fit for purpose", "fit to travel" exempt | Convention | British-pattern | sentence | 0 (5 under UK) |
| GN106 | Full stop or comma inside/outside closing quotation marks against the chosen English; a mixture under auto | Convention | all | document | 0 |
| GN107 | Month-first date in British-pattern English; dates written both ways (ranges and reference entries exempt) | Convention | all | document | 0 |
| GN201 | Plural "are/were/have/do" after a singular head + "of" + plural ("the proportion of cases were"); "a proportion of", "the majority of", coordinated subjects exempt | Improvement | all | sentence | 23, all true |
| GN202 | "A number of" + plural noun with a singular verb | Improvement | all | sentence | 0 |
| GN203 | "Neither A nor B" (both singular nouns) + plural verb | Improvement | all | sentence | 0 |
| GN204 | "reason … is/was because" → "is that" | Improvement | all | sentence | 1, true |
| GN205 | "-ing" opener + comma + passive main clause with no doer ("Using a Bayesian model, the parameters were estimated"); prepositional openers (assuming, given, including…) exempt | Improvement | all | sentence | 10, all true |
| GN206 | "a"/"an" against how a listed abbreviation is said ("a MCMC", "an UK", "an SNP"); SIR/SEIR accepted either way | Improvement | all | sentence | 4, all true |
| GN207 | "data" plural in some places and singular in others; the rarer form flagged once | Convention | all | document | 6, all true |
| GN208 | "which" starting a defining clause (no comma) → "that" | Preference | US | sentence | 0 (258 under US) |

Noise floor with the notes: 11.74 → 11.89 flags/1000w (+44 flags, every one a true finding when read). Considered and dropped (reasons in the document): "less cases", "between 5 to 10", "comprised of", double comparatives (LanguageTool catches them); "compared to/with"; "in hospital"; "at/on the weekend"; "fill in/out"; all-number dates; "toward(s)".

## Layer 0 — Commodity spelling & grammar (v0.3; integrated open source)

| ID | Rule | Type | Backend | Status |
|---|---|---|---|---|
| S001 | Spelling (unknown words, top-3 suggestions ranked by a noisy-channel model with the neighbouring words) | Correction | symspellpy (MIT) + `spellrank.py`, always on | MVP; ranker 2026-10-14 |
| S002 | Real-word confusion: a real word the neighbouring words say was meant as its usual confusion ("principle component", "a casual relationship", "were effected by") | Correction | SymSpell bigram counts, one-way pairs in `lexicons.CONFUSIONS`, margin ≈150× | 2026-10-14 (Mays, Damerau & Mercer 1991) |
| LT001 | Grammar: agreement, verb forms, a/an, confusions | Correction | LanguageTool via language_tool_python (local server, Java), optional | MVP |
| GEC001 | Learned corrections: minimal token-level edits (GECToR-style), opt-in `[tiers] gec = true`, abstains without a local model | Correction | local edit tagger scaffold (`gec.py` + `rules_gec.py`), tier="gec", never auto-applied, confidence-gated, masked-span-safe (test_gec.py) | 2026-08-14 scaffold |

Phase-1 deliberately deferred this tier ("integrate, don't rebuild");
added after desktop dogfooding exposed the gap. **2026-10-14 (P41):** S001
also accepts the NLM SPECIALIST Lexicon's single-word forms (278k after
filtering; `data/specialist_words.txt`, notice in its header), which removed
more than half of its false flags on biomedical prose; and skips code names
(a lower-case start with a capital inside: "mDh", "logLik"). S001 precision guards:
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

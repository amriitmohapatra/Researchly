# Codex Review: Researchly Architecture, Knowledge Model, and Grammarly Gap

Date: 2026-08-10  
Scope: Read-only review of the current Researchly repository across the MS Word add-in, macOS app, and Windows scaffold, with the Python engine as the shared core.

## Executive verdict

Researchly has a coherent and unusually strong foundation for an academic writing assistant: one deterministic Python engine, offset-preserving document masking, IMRaD-aware rules, an explicit Correction/Improvement/Convention/Preference taxonomy, local-only execution, provenance-bearing explanations, and a practical Word/macOS/Windows multi-surface plan. That is the right architecture for a privacy-preserving academic tool and it is differentiated from Grammarly in ways that matter for scientific writing.

It is not yet close to Grammarly in grammar-checking depth, interaction maturity, ubiquity, personalization, or platform polish. Grammarly is not just a rule checker. Its public engineering work shows a learned grammatical-error-correction sequence tagging architecture, and its current product wraps this with real-time underlines, broad app/web/mobile coverage, Goals, tone features, style guides, brand tones, organization dictionaries, plagiarism/AI-detection features in some contexts, and generative rewrites. Researchly currently has a small deterministic rule engine, SymSpell spelling, optional local LanguageTool grammar, deterministic rewrite for a limited set of safe edits, and prototype-stage app shells.

The most important architectural decision is therefore not "add more rules" versus "do nothing." It is whether "no LLMs" means no cloud generative AI, or no learned language model of any kind. If it means no cloud/generative AI, Researchly can plausibly approach Grammarly-style correction quality by adding a local grammatical-error-correction tagger, deeper local grammar engines, and corpus-backed academic convention checks. If it means no neural language models at all, Researchly can remain excellent as an explainable academic writing coach, but it should not be expected to match Grammarly's broad grammar correction quality.

One clarification is important: Researchly should not be understood merely as "Grammarly for grammar, but academic." The stronger product idea is an argument-and-warranting assistant for scholarly writing. The course notes, books, and writing materials are not just a bag of style rules; they describe how a reader recognizes claims, grounds, warrants, limitations, gaps, and contributions. Researchly's distinctive goal should be to help the writer structure arguments so that a reader can see what is being claimed, why the claim is warranted, how strongly it can be stated, and how the English should carry that reasoning.

In that framing, grammar checking is necessary but secondary. Grammarly helps sentences become more correct and fluent. Researchly should help scientific arguments become more legible, warranted, calibrated, and defensible.

## Evidence reviewed

The review is grounded in the current repo files:

- Project context and decisions: `AGENTS.md`, `CLAUDE.md`, `docs/PROJECT_LOG.md`.
- Knowledge and rules: `docs/knowledge-base.md`, `docs/rule-inventory.md`, `docs/dogfooding-report.md`, `The-Craft-of-Scientific-Writing.md`.
- Strategy and competitor research: `research/00-synthesis.md`, `research/01-commercial-tools.md`, `docs/roadmap-rewrite-and-desktop.md`.
- Engine: `prototype/researchly/document.py`, `engine.py`, `rules_lexical.py`, `rules_syntax.py`, `rules_spelling.py`, `rules_grammar.py`, `spelling.py`, `transform.py`, `abstract_lens.py`, `review.py`, `metrics.py`.
- Surfaces: `prototype/word-addin/server.py`, `prototype/word-addin/web/taskpane.js`, `prototype/desktop-mac/researchly_app.py`, `prototype/desktop-mac/panel_html.py`, `prototype/desktop-win/researchly_win.py`.
- Tests: `prototype/tests/test_*.py`.

Current Grammarly references checked:

- Grammarly support: "How does Grammarly work?" https://support.grammarly.com/hc/en-us/articles/115000090871-How-does-Grammarly-work
- Grammarly product offerings: https://support.grammarly.com/hc/en-us/articles/115000090851-Grammarly-s-product-offerings
- Grammarly desktop guide: https://support.grammarly.com/hc/en-us/articles/4412816078349-Grammarly-for-Windows-and-Grammarly-for-Mac-user-guide
- Grammarly Goals: https://support.grammarly.com/hc/en-us/articles/360054679292-What-are-Goals
- Grammarly style guide: https://www.grammarly.com/business/styleguide
- Grammarly brand tones: https://support.grammarly.com/hc/en-us/articles/4403544890253-Set-brand-tones
- Grammarly tone suggestions: https://support.grammarly.com/hc/en-us/articles/10674801783309-How-do-Grammarly-s-tone-suggestions-work
- Grammarly GECToR implementation: https://github.com/grammarly/gector
- Grammarly features page: https://www.grammarly.com/features

## Current Researchly architecture

Researchly is currently an engine-first application. The real product asset is `prototype/researchly`, while Word, macOS, Windows, CLI, and LSP are surfaces over the same checking and polishing logic.

The core engine has several good architectural decisions:

- `Document` preserves original offsets by masking markup with spaces rather than deleting it. That is essential for Word, LSP, LaTeX, Markdown, and Quarto because suggestions can map back to source positions without offset drift.
- `Document.from_word()` builds the same abstraction from Office paragraphs and Word styles, including section detection from heading styles.
- `engine.py` has a simple typed `Suggestion` model and a `Rule` registry. Suggestions carry category, rule id, replacement, source span, line/column, section, and display text.
- The rule taxonomy is not decorative. It affects behavior: Preferences are hidden by default, section gates suppress inappropriate advice, and aggregate rules reduce repeated nagging.
- Rules are explainable. The `why` text is part of the rule metadata and is surfaced in the Word add-in and desktop panel.
- The grammar/spelling architecture is intentionally local: SymSpell for spelling and optional local LanguageTool for grammar.
- `transform.py` implements deterministic Polish as a constrained edit composer. It applies only safe, concrete replacement rules and leaves judgment calls as suggestions.
- Document-level features exist, but they are signal-based: `abstract_lens.py` checks six abstract moves, `review.py` produces a deterministic critical-reader brief, and `metrics.py` gives descriptive meters rather than a gamified score.

The Word add-in is the most mature surface. It runs a local HTTP server on `127.0.0.1`, extracts Word paragraphs and styles, checks through the engine, renders suggestions, supports applying replacements, gates tracked changes on WordApi 1.4, supports local dictionary additions, logs local telemetry, and supports deterministic Polish on a selection.

The macOS app is a useful D1/D2 prototype. It captures selected text through Accessibility or clipboard fallback, shows a floating WKWebView panel, can paste back a polished selection, has a menu bar item and hotkeys, and has a beta live watcher/badge. It does not yet provide true in-document underlines or per-suggestion application.

The Windows app is a scaffold, not a product. It mirrors the macOS selection-check-polish flow through `keyboard`, `pyperclip`, and `pywebview`, but the project log and file header are explicit that it has not been tested on Windows hardware.

## A. Limitations in Researchly that Grammarly does not have

### 1. Grammar correction quality is not in the same class

Researchly's always-on correction layer is currently spelling plus a small number of deterministic correctness rules. Grammar-proper depends on optional LanguageTool. If `language_tool_python` or Java is absent, `LT001` is silently inert. This is a reasonable prototype choice, but it means Researchly's baseline grammar checking is not comparable to Grammarly's.

Grammarly publicly describes broad checks for grammar, spelling, usage, wordiness, style, punctuation, tone, and plagiarism. Its published GECToR work is a learned grammatical-error-correction sequence tagger using transformer encoders and token-level edit operations. Even if Grammarly's current production architecture has moved beyond that exact implementation, the important point is that Grammarly-style correction quality is learned from large errorful/error-free corpora, not achieved by hand-written rules alone.

Researchly's limitation: it can teach and flag selected academic-writing patterns, but it does not yet have a robust learned correction layer for agreement, article use, prepositions, verb tense, punctuation, idiom, awkward syntax, run-ons, fragments, or subtle non-native English errors.

### 2. Grammarly has real-time inline interaction; Researchly mostly has side panels

Grammarly's desktop and browser products show inline underlines, widgets/tabs, hover cards, suggestion cards, and "review all" flows in many apps and websites. Researchly's Word add-in is a sidebar with Go to/Apply buttons. The macOS app is a selection-based floating panel with a beta badge. The Windows app is a selection-based scaffold.

This matters because Grammarly's most valuable feature is not just detection. It is the low-friction loop: type, see underline, click, accept/dismiss, continue. Researchly currently requires a more explicit workflow: select text or check document, inspect cards, and apply fixes through a side panel. The Word auto-check option helps, but it is still not true inline underlining.

### 3. Cross-app coverage is much narrower

Grammarly supports Windows, Mac, Microsoft Office, many desktop apps, web apps through browser support, Google Docs through browser extension, and mobile keyboards/editors on iOS and Android. Researchly currently has:

- Word add-in: working and most mature.
- macOS menu-bar app: working prototype, but not true overlay parity.
- Windows app: untested scaffold.
- LSP/VS Code: built, but not part of the user's requested app-surface review and not yet user-verified in the project log.
- No browser extension for Overleaf/Google Docs/Gmail.
- No mobile keyboard.
- No Google Docs-specific integration.

For a Grammarly-like product, browser and mobile support are not optional long-term. Researchers write in Word, Overleaf, Google Docs, email, manuscript systems, Slack/Teams, and web forms. Researchly currently covers Word and selected text reasonably, but not "wherever you type" with Grammarly-level reliability.

### 4. Researchly does not yet have a mature overlay system

The roadmap correctly describes why this is hard: OS accessibility APIs are inconsistent, browsers and Electron apps often do not expose enough text geometry, and true underlines require bounds for character ranges. Researchly has staged this sensibly:

- D1: selection hotkeys and floating panel.
- D2: live watcher and badge.
- D3: transparent underline overlay.

Current code is at D1/D2. Grammarly has already solved or worked around much of this with a maintained compatibility matrix, browser extension, desktop widget, and Word/Docs integrations.

### 5. Researchly has no learned personalization layer yet

Researchly has local telemetry and per-rule muting. The Word add-in logs shown/goto/applied/dismissed/muted events to a local file, and `researchly stats` can summarize rule usefulness. That is a good start.

Grammarly has much broader personalization primitives: personal dictionaries, language preferences, Goals, tone settings, brand tones, style guides, organizational dictionaries, block lists, and account-level settings. Researchly lacks:

- A user-facing preferences/settings UI across all surfaces.
- Rule aggressiveness profiles.
- Project/document type profiles beyond `.researchly.toml`.
- Audience and venue settings.
- Learned suppression from repeated dismissals.
- A manuscript/journal/discipline profile.
- Sync across devices, intentionally absent because the product is local-first.

Researchly's local-first position is a strength, but it means personalization needs to be designed as local project/user state rather than cloud account state.

### 6. Rewrite/paraphrase capacity is intentionally limited

Researchly Polish is deterministic and safe. It can apply plain-word substitutions, wordy phrase compression, filler deletion, redundant-pair cleanup, doubled-word fixes, buried-action fixes, and expletive-opener restructuring. It cannot paraphrase, change tone freely, rewrite paragraphs, or offer multiple alternative phrasings.

Grammarly now offers paragraph rewrites, tone suggestions, paraphrasing, AI-assisted proofreading, and generative features in multiple products. Those features are LLM-era product capabilities. Researchly's deterministic rewrite is safer for academic integrity, but it cannot match the fluency and breadth of Grammarly's rewrite functions without some learned editor.

### 7. The academic knowledge is deeper than Grammarly's, but less operationalized

Researchly's knowledge base is more academically relevant than Grammarly's generic goals. It encodes IMRaD awareness, passive voice exceptions in Methods, causal-claim prompts, novelty softening, gap statements, abstract moves, and critical-reader framing. This is a real differentiator.

However, much of the knowledge base is represented as lexical or structural signals. For example, a missing gap statement is detected by absence of contrastive/gap words in an Introduction. That is useful, but it is not the same as understanding whether the paper has actually established a niche. The critical-reader review can inventory signals, but it cannot evaluate whether claims are warranted by the actual evidence.

### 8. Researchly lacks plagiarism, citation, and reference-adjacent features

Grammarly offers plagiarism checking in some product contexts and increasingly integrates AI detection and broader writing assistance. Academic competitors also offer submission-readiness checks, citation tools, retracted-reference alerts, and journal compliance checks.

Researchly currently has no:

- Plagiarism checker.
- Citation integrity checker.
- Reference-list parser.
- Retracted-reference detection.
- Journal submission checklist.
- Ethics/COI/data-availability statement checker.
- Reporting-guideline checker.
- Statistical reporting consistency checker.

Some of these are in the roadmap or inventory as future/res items, but they are not implemented.

### 9. Researchly is English-only and academic-domain-narrow

Researchly is currently built around English scientific prose, especially epidemiology/modelling. Grammarly supports broader general English and has mobile settings indicating support for additional languages in some contexts. Researchly's narrowness is strategically good for differentiation, but it is a limitation if the goal is Grammarly-like coverage.

### 10. Deployment, installation, and maintenance are prototype-grade

The Word add-in requires a local Python server, spaCy model installation, and manual Word restart behavior. The macOS app is unsigned/unnotarized. The Windows app is untested. LanguageTool is optional and requires Java. Grammarly has consumer-grade installers, background services, account settings, support docs, and maintained compatibility.

Researchly can be a strong personal tool in this form. It is not yet a consumer-grade app.

## B. Are all aspects of the knowledge base appropriately modelled in Researchly?

No. The knowledge base is partially and thoughtfully modelled, but not fully modelled. The current implementation is strongest where the knowledge can be expressed as local, explainable, high-precision text patterns. It is weakest where the knowledge requires semantic interpretation, discourse understanding, evidence evaluation, or cross-document/citation reasoning.

This is the central gap relative to the original Researchly idea. The current code incorporates many notes as checkable surface signals, but it does not yet model the reader's argument task deeply enough. A reader needs to answer: What is the claim? What grounds support it? What warrant connects those grounds to the claim? What qualifier limits the claim? What rebuttal or limitation has been anticipated? What contribution does this make relative to the gap? Those are not ordinary grammar checks. They are discourse and argument-structure checks.

### Well modelled

The following knowledge-base aspects are appropriately represented for the current product stage:

- Suggestion taxonomy: Correction, Improvement, Convention, Preference are first-class engine categories.
- Explainability: each rule has a short description, a "why" explanation, and a source/provenance field.
- Section awareness: IMRaD heading detection influences rules, especially passive voice, causal claims, overclaiming, Results display openers, and abstract rules.
- Markup safety: Markdown, Quarto, R Markdown, LaTeX, and Word paragraph inputs are normalized through a shared offset-preserving `Document`.
- Precision-over-recall: aggregation, allowlists, scientific lexicons, proper-noun guards, and dogfooding-calibrated thresholds are built into rules.
- Sentence-level craft rules: subject-verb separation, nominalization density, buried actions, expletive openers, long sentences, noun strings, stress position, wordy phrases, hype, filler, contractions, doubled words.
- Scientific calibration prompts: causal verbs, overclaiming, bare "significant," hedge stacking, assertive adverbs.
- Some academic structure signals: abstract six-move completeness, missing Introduction niche signal, serial-summary literature-review opener, vague abstract forward reference.
- Some field vocabulary protection: scientific terms and personal dictionary support reduce false positives on epidemiology/modelling language.

This is a good model for explainable linting.

### Partially modelled

These areas exist, but the current representation is a proxy rather than a full model:

- Abstract quality: `abstract_lens.py` detects move signals. It does not judge whether each move is specific, balanced, accurate, or persuasive.
- Critical-reader review: `review.py` summarizes deterministic evidence. It does not actually infer claims, grounds, warrants, rebuttals, or whether the warrant supports the claim.
- Metadiscourse: `metrics.py` counts hedges, boosters, and self-mentions. It does not judge whether the calibration matches the study design or evidence.
- Terminology consistency: `W210` checks curated UK/US spelling pairs. It does not solve the broader "one term, one meaning" problem, synonym drift, notation drift, or concept-definition consistency.
- Causal language: `C303` detects causal verbs and calibrated frames. It does not classify study design, identify estimands, distinguish intervention effects from mechanistic model claims, or verify causal identification.
- Gap statements: `D902` detects a missing CARS Move 2 signal. It does not determine whether the stated gap logically follows from the reviewed literature or matches the study aim.
- Section detection: heading-keyword classification is useful, but unusual headings, nested sections, mixed document genres, and Word formatting edge cases remain brittle.
- Grammar: LanguageTool is integrated as an optional tier, but not tightly modelled into Researchly's taxonomy, confidence calibration, or academic register beyond category filtering.

These partial models are not failures. They are honest deterministic approximations. They should be labelled as signals/prompts, not verdicts.

### Not yet modelled

Several knowledge-base items are explicitly in the inventory or knowledge base but are not implemented as substantive checks:

- Paragraph-level known-new flow.
- Topic sentence quality.
- One paragraph, one idea.
- Full CARS move chain: territory, niche, occupation, and lock-and-key relation between gap and contribution.
- OCAR/hourglass document arc.
- Toulmin argument audit: claim, grounds, warrant, qualifier, rebuttal.
- Evidence-strength calibration.
- Reader-side warranting: whether the text gives sufficient grounds for accepting the claim.
- Argument repair suggestions: how to restructure a paragraph when the claim, warrant, or evidence is missing or in the wrong order.
- Warranting language: English patterns for connecting evidence to claims, such as "This suggests...", "This is consistent with...", "This supports...", "Taken together...", and when each is appropriate.
- Claim hierarchy: distinguishing main claims, subclaims, background claims, methodological claims, and speculative implications.
- Literature-review synthesis: turning serial summaries into a warranted argument about what is known, what remains unresolved, and why the current study is needed.
- Limitations/rebuttal completeness beyond detecting a Limitations section.
- "Model implies X" versus "the world will do X" separation as a semantic check.
- Symbol definition with units.
- Equation introduced/displayed/interpreted.
- Notation consistency.
- Reproducibility completeness: software versions, priors, diagnostics, data/code availability.
- Statistical consistency checks, including p-value/test-statistic consistency or estimate/interval completeness.
- Figure/table caption self-sufficiency.
- Figure-axis and visual-reporting checks.
- Reporting-guideline coverage such as STROBE, CONSORT, EPIFORGE.
- Equity-framing checks, including mechanism-not-attribute language and stratification justification.
- Audience/persona setting.
- Journal/style guide profiles.
- Corpus-backed convention evidence.

The short answer is therefore: Researchly has modelled the knowledge base as a first-generation rule inventory and deterministic signal system. It has not yet modelled the knowledge base as a semantic academic-writing intelligence system.

For the original vision, the next modelling unit should not be "another phrase rule." It should be an argument object: claim, evidence, warrant, qualifier, limitation, and suggested rhetorical repair. Rules can still detect signals, but the product should increasingly report at the level of "this paragraph makes a claim without showing the warrant" or "this evidence is present, but the sentence does not explain why it supports the conclusion."

## C. What should Researchly do if the goal is "nearly as good as Grammarly" without LLMs?

### First, clarify the no-LLM boundary

The current project rule says "No LLMs in the product." That is sensible if it means no ChatGPT-like cloud generation and no sending manuscript text to third-party APIs. But Grammarly's pre-ChatGPT quality did not come from regex rules alone. It came from statistical NLP and learned grammatical-error-correction models. GECToR, for example, is not a chat model and does not generate free-form prose, but it is still a transformer-based language model.

This creates three possible product policies:

1. Strict deterministic only: rules, dictionaries, LanguageTool-style grammars, no neural language models. This maximizes auditability but will not reach Grammarly-level grammar coverage.
2. Local non-generative ML allowed: local sequence taggers/classifiers for grammar, certainty, section roles, and claim type; no cloud and no free-form generation. This is the best fit if the goal is Grammarly-like quality without ChatGPT-like authorship risk.
3. Optional local neural editor: a local edit-only model for sentence correction/paraphrase, constrained by diffing, confidence thresholds, and user acceptance. This improves fluency but weakens the strict "no LLM" claim.

My recommendation is option 2: no cloud LLMs, no generative drafting, no silent rewriting, but allow local non-generative NLP models for correction and classification. That preserves the academic integrity promise while admitting the engineering reality that high-quality grammar correction is learned.

### Build a three-layer correction architecture

Researchly should separate its future engine into three layers:

1. Commodity correctness layer: spelling, grammar, punctuation, agreement, articles, prepositions, verb forms, confused words, typos.
2. Academic craft layer: the current Researchly rules for clarity, convention, claim calibration, section-aware scientific prose, and explainable suggestions.
3. Document intelligence layer: abstract, introduction, argument, reporting, reproducibility, causal language, statistical reporting, figure/caption, and equity checks.

Currently, layer 2 is the most developed. Grammarly's advantage is mostly layer 1 and UX. Researchly's unique opportunity is layer 3.

Layer 3 should be explicitly designed around reader-side argument comprehension. It should not only say "missing gap signal" or "causal verb detected." It should say, for example: "The paragraph gives a result but does not state what inference the reader should draw," "The claim is stronger than the warrant provided," or "The gap and aim do not yet lock together." That is the part of the course and book knowledge that ordinary grammar tools do not model.

### Make local grammar correction always available

Do not leave grammar-proper as an optional silent dependency. At minimum:

- Bundle or manage LanguageTool installation in the app packaging.
- Expose a visible grammar-tier status in each surface.
- Add a health check: "Grammar engine active/inactive."
- Expand retained LanguageTool categories after measuring false positives.
- Add tests for common academic ESL errors: articles, subject-verb agreement, prepositions, verb tense, plurality, punctuation, and word forms.
- Consider Harper as a second local grammar backend if its license and accuracy fit.

This is the fastest route to improving perceived quality.

### Add a local GEC sequence tagger

To approach Grammarly's correction quality, Researchly needs a learned edit tagger or equivalent local model. This should be framed as "local grammatical error correction," not "AI writing." It should:

- Run entirely on-device.
- Return minimal token-level edits, not generated paragraphs.
- Emit confidence scores.
- Be diffed against the source.
- Be mapped to Researchly categories and explanations where possible.
- Be disabled for citations, math, code, equations, and masked markup.
- Never auto-apply substantive changes.
- Be evaluated against both public GEC datasets and a local academic corpus.

GECToR is the obvious architectural reference because it is edit-based, fast, and aligned with Grammarly's own published pre-LLM direction. It may not be the exact model to use today, but the pattern is right: tag, do not freely rewrite.

### Build an academic evaluation corpus

More rules without evaluation will create false-positive fatigue. Researchly already learned this in the dogfooding report. The next corpus should include:

- Accepted PhD theses already used for false-positive calibration.
- User drafts with accepted/rejected Researchly suggestions.
- Synthetic but realistic grammar errors in academic sentences.
- ESL academic writing examples where permissions allow use.
- Before/after human-edited academic prose if available.
- A small gold set manually labelled as correction, improvement, convention, preference, or no issue.

Metrics should be separate:

- Correction layer: precision, recall, F0.5, exact edit match, false-positive rate.
- Academic craft layer: flags per 1000 words, keep rate, dismiss rate, mute rate.
- UX layer: time to accept, failed apply rate, stale range rate.
- Document lens: human usefulness rating, not automated "accuracy" alone.

### Preserve the explainable rule system

Do not replace the current Researchly rules with a black-box model. The rules are the product's academic identity. The better architecture is an orchestrator:

- Rule engine produces explainable academic signals.
- Local grammar engine produces correctness suggestions.
- Local GEC tagger proposes minimal edits.
- Document lenses produce review-style reports.
- The UI merges, deduplicates, ranks, and labels suggestions.

This preserves Researchly's differentiator: Grammarly may be broader, but Researchly can explain why a suggestion matters in Methods, Results, Discussion, or an abstract.

### Prioritize Word and macOS before Windows

For app architecture, the priority should be:

1. Word add-in reliability and polish.
2. macOS D2/D3 experience for native apps.
3. Browser/Overleaf extension.
4. Windows bring-up after a real Windows debugging session.

Windows should not be treated as equivalent to macOS yet. The current file is explicit that it is untested. A Windows product requires UI Automation testing, installer work, antivirus/code-signing considerations, clipboard reliability tuning, and WebView2 packaging checks.

### Improve the Word add-in first

The Word add-in is closest to real use. Recommended improvements:

- Add visible grammar-engine status.
- Add "Review all" grouping by category and section.
- Add persistent per-document settings.
- Add better stale-range handling after edits.
- Add bulk apply only for safe corrections.
- Add a local settings panel for disabled rules, dictionary, preferences, and grammar tier.
- Add document-type selection: thesis chapter, abstract, manuscript, grant, response to reviewers.
- Add explicit "academic convention" cards with source/provenance.

True inline underlines inside Word may be hard through Office JS, but the add-in can still become a strong Grammarly-like sidebar.

### Improve macOS in stages

The macOS app should continue the staged roadmap:

- D1: keep selection check/polish reliable.
- D2: improve live watcher, app denylist UI, and badge behavior.
- D3: implement underlines only for apps where AX range bounds are reliable.

Do not try to make one universal overlay work everywhere. Grammarly itself uses multiple integration strategies. Researchly should do the same: Word add-in for Word, browser extension for web editors, LSP for code/Quarto, macOS overlay for native text fields.

### Add corpus-backed conventions

Researchly's biggest academic opportunity is not generic grammar. It is being able to say: "In epidemiology Methods sections, this phrasing is conventional; in Discussion, this claim needs calibration." To make that credible:

- Build discipline packs.
- Add journal/document profiles.
- Use published-paper corpora where licensing permits.
- Store examples and frequencies locally.
- Use corpus evidence for Convention cards.
- Keep source/provenance visible.

This would give Researchly a stronger academic justification than Grammarly's generic Goals.

### Implement missing high-value academic checks

The next high-value checks should be:

- Claim-warrant paragraph lens: identify claim sentences, evidence sentences, warranting connectors, qualifiers, and missing links.
- Argument-structure suggestions: offer paragraph-level ordering patterns such as context -> claim -> evidence -> warrant -> implication, or gap -> aim -> method -> contribution.
- Warranting phrase support: suggest calibrated English connectors for different evidential relationships, without inventing content.
- Literature-review synthesis lens: flag serial summaries and suggest a synthesis-first structure leading toward the gap.
- Statistical reporting completeness: estimates with uncertainty intervals, not just p-values.
- Causal claim versus study-design language.
- Model-claim framing: "the model implies" versus "transmission will."
- Acronym/term/symbol/notation consistency.
- Abstract and Introduction structure with stronger move detection.
- Figure/table caption self-sufficiency.
- Reproducibility checklist for modelling papers: code, data, priors, diagnostics, software versions.
- Reporting-guideline packs for STROBE/CONSORT/EPIFORGE where applicable.

These should be document-lens checks, not noisy inline nags.

## Practical roadmap

### Phase 1: Make the current product dependable

- Bundle or clearly manage LanguageTool.
- Add grammar-tier status to Word and desktop surfaces.
- Run the full test suite regularly.
- Expand regression tests around Word mapping and grammar examples.
- Improve user-visible settings.
- Keep telemetry local and use it to tune rule noise.

### Phase 2: Reach credible grammar quality

- Add a local GEC tagger or equivalent edit model.
- Evaluate against public GEC benchmarks and academic samples.
- Merge GEC suggestions with Researchly categories.
- Use confidence thresholds to maintain precision.
- Keep all edits reviewable.

### Phase 3: Build Grammarly-like interaction loops

- Improve Word sidebar UX.
- Add D2/D3 macOS overlay where reliable.
- Build a browser extension for Overleaf/Google Docs/web editors.
- Keep LSP for Quarto/VS Code/Positron.
- Treat Windows as a separate bring-up project, not a copy-paste port.

### Phase 4: Deepen academic intelligence

- Add discipline and document-type profiles.
- Build corpus-backed convention evidence.
- Add reporting/reproducibility/statistical/causal checks.
- Expand the critical-reader lens with better structure detection.
- Keep semantic checks as prompts unless the evidence is strong enough for a correction.

## Final assessment

Researchly should not try to become a generic Grammarly clone. Its strongest path is "Grammarly's interaction quality plus Writefull-like academic convention evidence plus an epidemiology-aware reviewer lens, all local and explainable."

The current architecture can support that direction, but the current implementation is still early. The most consequential missing piece is a serious local correction layer. Deterministic rules are excellent for explainable academic advice; they are not enough for broad grammar correction. If the no-LLM rule allows local, non-generative sequence tagging, Researchly has a realistic path toward Grammarly-like correction quality while preserving privacy and authorship. If it does not, Researchly should position itself more narrowly and honestly as an academic writing coach that complements, rather than replaces, a mature grammar checker.

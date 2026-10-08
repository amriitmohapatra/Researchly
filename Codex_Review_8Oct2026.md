# Researchly: codebase and feature review

**Date:** 8 October 2026 (Singapore).  
**Reviewed baseline:** `main` at `5414cdce9b7290959cdb1731977410a564ca672b` (PR #10 merged).  
**Scope:** current core engine, hosted service, web revision studio, hosted and local Word add-ins, LSP/VS Code, account settings, ingestion, contracts, tests and evaluation. Desktop apps are maintenance-only; legacy experiments were considered context, not current product features.

This is a review and a proposed backlog. It does not implement the recommendations or change the owner's product decisions. No cloud LLM, generative drafting, silent rewriting, new document storage or third-party text is proposed.

## Overall assessment

Researchly has a useful foundation: one analysis entry point, section-aware advice, four distinct suggestion categories, explanations with sources, privacy-conscious transport, structural manuscript checks, and meaningful tests. The newly shipped profiles, reviewer's brief and printable report make it more useful as a revision studio.

The next investment should be **trustworthy interpretation and a manageable revision workflow**. Some conclusions currently exceed what their heuristic evidence establishes. Cross-surface contracts also need stronger integration coverage: the hosted app's new requests break the advertised local Word route even though the suites pass. Fix those before expanding the apparent intelligence of the narrative review.

Recommended order:

1. Restore the local Word workflow and tighten Word editing outcomes.
2. Make profile selection, stage and review coverage explicit and reliable.
3. Add evidence navigation, session-only dismissal and focused revision queues.
4. Build the narrative map and discipline checklists on validated evidence.
5. Introduce local learned components only through the existing S5 evaluation and licence gates.

## What already works well

| Capability | Code evidence | Preserve when extending it |
| --- | --- | --- |
| Shared analysis | [`api.analyze`](packages/core/researchly/api.py), [`engine_adapter`](services/engine/researchly_service/engine_adapter.py) | One spaCy parse; shared config and rule semantics across surfaces. |
| Context-sensitive advice | [`document`](packages/core/researchly/document.py), [`profiles`](packages/core/researchly/profiles.py), [`rules_syntax`](packages/core/researchly/rules_syntax.py) | Methods exemptions, heading inheritance and precision guards. |
| Explainable feedback | [`SuggestionCard`](apps/web/components/SuggestionCard.tsx), [`sources`](packages/core/researchly/sources.py) | Plain explanation first, source attribution and optional fuller reasoning; conventions remain optional norms. |
| Manuscript integrity | [`rules_structure`](packages/core/researchly/rules_structure.py), [`rules_consistency`](packages/core/researchly/rules_consistency.py) | References, captions, equations, abbreviation definitions and unit/compound consistency. |
| Writer control in Word | [`office`](apps/web/lib/word/office.ts), [`wordloc`](packages/core/researchly/wordloc.py) | Exact snippet verification, occurrence checks, explicit application and tracked changes where supported. |
| Document confidentiality | [`engine.ts`](apps/web/lib/engine.ts), [`check-boundary`](apps/web/scripts/check-boundary.mjs), service privacy-canary tests | Text goes from the browser to the engine; no server-side web document processing or automatic document persistence. |
| Account isolation | [`accounts`](services/engine/researchly_service/accounts.py), [`Supabase migrations`](supabase/migrations), two-user tests | Verified tokens, caller-scoped RLS and atomic rule-mute operations. |
| Export and accessibility | [`PrintReport`](apps/web/components/PrintReport.tsx), [`DocumentView`](apps/web/components/DocumentView.tsx), browser tests | Browser-made reports, numbered highlights, keyboard navigation and accessible error states. |

## Findings to address first

Priority meanings: **P1** = fix before relying on the affected workflow; **P2** = next product-quality iteration. “Reproduced” means a synthetic probe executed against this baseline, not a production incident or a real Word-host test. “Static” means the behavior follows from inspected code but was not exercised in its complete host environment.

### R1 — P1: the hosted taskpane cannot check through the local engine

**Reproduced.** [`analysisOptions`](apps/web/lib/engine.ts#L61) always sends `document_type` and `review`, including from [`Taskpane.runCheck`](apps/web/components/word/Taskpane.tsx#L224). The local server's [`parse_word_request`](apps/word-addin/server.py#L173) accepts only `show_preferences`, `disabled_rules` and `mode`. A current request therefore raises **422**, even with `document_type: "auto"` and `review: false`.

There is a second compatibility problem behind that rejection: [`_word_suggestion`](apps/word-addin/server.py#L226) omits `plain`, while [`WordCard`](apps/web/components/word/WordCard.tsx#L56) calls `s.plain.trim()`. The browser's response guard does not normalize that field. Passing the server response through a Python model supplies a default, but the browser receives the original JSON, not that normalized model.

**Improve:** bring the local request/response adapter up to the current shared contract, including profiles, plain explanations and the optional brief. If a feature cannot run locally, advertise that capability explicitly. Add a browser integration test that sends the actual taskpane request to the real local HTTP handler and renders its unmodified response. Keep bearer tokens out of local requests.

**Done when:** Draft and Revise, Auto and an explicit profile, suggestions and the brief work through “This computer”; contract changes fail CI if either adapter falls behind. Existing local-contract tests send the older option set and thus miss this break.

### R2 — P1: Auto can silently remove important checks from a research article

**Reproduced.** [`profiles.guess`](packages/core/researchly/profiles.py#L136) checks policy headings before research-article signals. An IMRaD document with causal/overclaim suggestions is guessed as `manuscript`. Appending a standalone **Recommendations** heading makes it `policy-brief`, disabling C302, C303 and other rules across the document. In the probe, the remaining suggestion list became empty.

**Improve:** resolve conflicting signals conservatively. A research article with recommendations should retain its research profile; do not let one ancillary heading switch off checks. Show the inferred type and the heading evidence, with an easy override. Preserve the explicit profile choice as authoritative.

**Done when:** manuscripts, thesis chapters and policy briefs with overlapping headings are tested in plain text, Markdown, LaTeX and Word; an ambiguous guess cannot quietly weaken the check. This concerns Auto's evidence, not reversing the owner's explicit profile behavior.

### R3 — P1: Word field-protection failures allow editing, and partial success can be reported as no change

**Reproduced at the Office adapter boundary with synthetic fakes; real Word behavior remains unverified.** [`overlapsField`](apps/web/lib/word/office.ts#L301) returns false if loading the range's fields throws. A fake field-probe failure still produced one insertion and `{ok: true, tracked: true}`. That makes “could not establish field safety” equivalent to “safe to edit.”

Separately, [`applyReplacement`](apps/web/lib/word/office.ts#L315) inserts text and then restores Track Changes in `finally`. If restoration fails after insertion, the outer catch returns “Nothing was changed; try again.” The probe recorded **one insertion followed by that failure response**. Similar uncertainty can arise when a batched host operation partly succeeds.

**Improve:** fail closed when field safety cannot be established; offer a manual edit. Distinguish not-applied, applied-but-restoration-failed, and unknown outcomes. After uncertain outcomes, refresh the document and invalidate affected suggestions; never encourage blindly repeating an operation that may already have edited text.

**Done when:** adapter tests cover failed field enumeration, insertion, selection and tracking restoration separately; a real Mac/Windows Word check confirms citation protection, change tracking restoration and honest recovery messages.

### R4 — P2: the reviewer's brief mistakes unchecked or unrecognized evidence for a substantive conclusion

**Reproduced.** [`review.build_review`](packages/core/researchly/review.py#L83) derives causal claims from C303 suggestions. Muting C303, or using a profile that disables it, changes the brief to **“No unhedged causal claims found”** on text that still contains the same claims. Policy/commentary profiles should change coaching policy, not make a claim inventory disappear.

Other reproduced examples:

- A Discussion-only excerpt with no gap statement receives **“A gap statement is present”** because `gap_present` is also true when no Introduction heading exists ([line 94](packages/core/researchly/review.py#L94)). Its evidence list is empty.
- “The specimens arrived on Tuesday.” receives **“Nothing undermines the claims on the evidence here”** ([line 215](packages/core/researchly/review.py#L215)), with no claim assessment or supporting evidence.
- The brief's aim/significance detectors are phrase lexicons. Failure to match becomes “No sentence says…” rather than “No explicit signal was detected.”

**Improve:** represent **detected / not detected / not assessed / not applicable** separately. Mark muted and profile-disabled checks as not assessed. Phrase heuristic output as prompts, not validation of scientific claims. Separate factual evidence extraction from which advice is displayed. Reuse the shared parse rather than adding another analysis pass.

**Done when:** muting or changing a profile cannot create false reassurance; excerpt-only checks abstain on absent sections; every positive “present” assertion has evidence. Give the brief an explicit statement that it does not establish scientific validity.

### R5 — P2: argument feedback needs links between passages, not section-wide keyword presence

**Static inspection plus synthetic probes.** [`argument`](packages/core/researchly/argument.py#L217) splits sentences with a punctuation regex, assigns one primary role, and pools passages by semantic section name. It does not use the already computed spaCy sentence boundaries. A sentence with both a claim and “because” is classified primarily as warrant; an unrelated warrant elsewhere in a section can suppress the missing-warrant prompt. Repeated Discussion sections also share one bucket.

**Improve:** retain multiple roles, use shared sentence spans, and associate a claim with nearby supporting passages in a particular section instance. Let the writer inspect or correct a role assignment in memory. Until relationships are validated, say **“I could not link this claim to supporting evidence”**, not that no evidence exists.

**Done when:** one unrelated “because” sentence cannot satisfy another claim; evidence and claims in different chapters are not joined accidentally; abbreviations, decimal numbers, equations and blank-line boundaries preserve sentence offsets. These are prerequisites for the planned narrative map.

### R6 — P2: web results can inherit Draft mode without showing the missing document checks

**Reproduced at the service/config boundary; UI confirmed by static inspection.** Web [`Checker`](apps/web/components/Checker.tsx#L211) requests a brief but does not send a mode. [`build_config`](services/engine/researchly_service/engine_adapter.py#L82) therefore inherits the account's saved Draft choice from Word. A synthetic account with `mode: "draft"` returned `hidden_by_mode: 1` and no visible suggestions for a duplicate abbreviation definition. [`Results`](apps/web/components/Results.tsx) has no equivalent of Word's held-back count or web stage control. The brief says Revise is needed, but the website has no immediate way to switch it.

**Improve:** either make the web revision studio explicitly request Revise, or add the shared Draft/Revise control. Show the held-back count next to results, with an action that runs the missing checks. A profile/stage change during an in-flight check should queue a fresh check or be disabled; label results with the options actually used.

**Done when:** choosing Draft in Word cannot silently reduce a later web check; the user can explain and change every active checking mode from the surface showing results.

### R7 — P2: LSP highlights and quick fixes are misplaced after non-BMP characters

**Reproduced.** [`to_position`](packages/core/researchly/lsp.py#L104) forwards Python character columns as LSP positions. With `😀 The the model was fitted.`, the second “the” starts at UTF-16 column **7**, but the adapter returns **6**. The VS Code client uses UTF-16 positions unless another encoding is negotiated. Quick fixes use the same faulty ranges.

**Improve:** translate per-line offsets to the negotiated position encoding, following the web app's existing code-point/UTF-16 distinction. Include document versions in diagnostics/actions and discard stale work. A canceled debounce timer does not cancel an analysis already running; `did_close` also does not cancel its pending timer.

**Done when:** emoji and mathematical characters have correct diagnostics and replacement ranges in a real editor, and edits/close/reopen cannot publish an older document's results. Offset mismatch is reproduced; the concurrency consequences still need host-level validation.

### R8 — P2: print/PDF reports omit context needed to interpret their findings

**Static.** [`PrintReport`](apps/web/components/PrintReport.tsx) includes the text, suggestions, profile and brief, but not tier health, read warnings or held-back counts. [`Results`](apps/web/components/Results.tsx#L213) can warn that the editor has changed; that stale status is not passed to the report. A PDF can therefore outlive the warning that grammar was unavailable, an input was skipped, or the result describes an earlier draft.

**Improve:** include analysis time separately from print time, actual mode/profile, disabled or unavailable capabilities, extraction warnings and a snapshot/stale label. For Overleaf projects, preserve file/line locations on printed suggestions. Offer full-document and selected-section reports without losing whole-document checks.

**Done when:** a reader of the PDF can tell what version and parts were assessed, and can locate the evidence without opening the app. Keep export in the browser; do not add a server document store.

## Feature improvements worth building

These extend existing behavior. Effort is relative: **S** = a bounded surface change; **M** = shared workflow/contract work; **L** = evaluation and multiple components. They are not delivery estimates.

| Proposal | Current limitation and evidence | Suggested behavior | Acceptance evidence | Effort / dependency |
| --- | --- | --- | --- | --- |
| **1. A focused revision queue** | [`Results`](apps/web/components/Results.tsx) filters by category/section but still lists every finding; frequency is not importance. | Offer “Correctness first,” “Clarity next,” and “Whole-document review”; group recurring issues with expandable locations and Next/Previous navigation. Preserve category meanings; do not create an overall score. | A chapter-scale usability test shows writers can finish a chosen pass without losing findings or context. | M; existing filters and rule scope. |
| **2. Dismiss once, mute deliberately, undo immediately** | [`SuggestionCard`](apps/web/components/SuggestionCard.tsx) offers persistent rule mute and dictionary addition, but no dismissal of one contextual suggestion. Mute/add actions trigger a full re-check, including a file re-upload. | Add session-only “Not an issue here,” a visible Undo action and “Why dismissed?” choices. Immediately filter successfully muted findings. Re-check dictionary changes when needed; keep the visible check marked as a snapshot. | Dismissing one false alarm does not disable a useful rule elsewhere; muted cards disappear promptly; no document text or dismissals are persisted without opt-in. | M; distinguish session state from account rules. |
| **3. Evidence-linked reviewer prompts** | The brief renders quotes as plain strings; causal points often contain only a rule message. The service's [`to_review`](services/engine/researchly_service/engine_adapter.py) drops the core's argument spans. | Give each prompt supporting spans, an evidence-status label and “Show in text.” Show the exact claim beside its proposed evidence/warrant; allow in-memory role correction. | Every supported assertion jumps to the correct text, including emoji and multi-file inputs; unsupported assertions abstain. | M–L; R4/R5 first, contract extension. |
| **4. Genre-native and scope-aware profiles** | [`profiles`](packages/core/researchly/profiles.py) largely uses rule exclusions and generic section names. Policy briefs have `abstract` in `expected` despite `abstract_expected=False`; a thesis chapter expects Methods and Results whether it is empirical or theoretical. | Separate article type from “whole manuscript / excerpt / chapter”; map Context/Evidence/Options/Recommendations and reviewer-comment/reply units to their own purposes. Add a methods-report/theory-chapter option only with tested behavior. | Profile tests cover topical headings and legitimate missing sections; no request for an abstract in a profile that declares one unnecessary. | M; R2/R4; extends the existing S4 profiles. |
| **5. A visible reading/coverage summary** | Word states body coverage through [`wordloc.coverage`](packages/core/researchly/wordloc.py). [`ingest/docx`](packages/core/researchly/ingest/docx.py) explicitly ignores notes, headers, comments and text boxes, without supplying an equivalent coverage report. ZIP main-file selection is heuristic. | Before interpreting results, say what was read, masked and skipped. Show the selected main TeX file and offer a choice when ambiguous. Treat lack of English support as a language/coverage issue, not hundreds of spelling corrections. | Synthetic documents with important footnotes/text boxes show omissions; ambiguous projects let the writer select the intended root; non-English samples receive an honest English-only notice. | M; existing ingest warnings; language detection is already in PLAN's Inbox. |
| **6. Reporting-guideline checklists** | STROBE, CONSORT, PRISMA and EPIFORGE are approved S4 work, not implemented checks. Structural rules cannot determine that a study is adequately reported. | Let the writer choose design/guideline; organize authored checklist items with evidence links and “reported / needs your check / not applicable.” Never infer methodological validity from keyword presence. | Each item cites its source, has authored positive/negative cases, and lets a writer record a session-only decision. | L; discipline-pack design and licence/provenance review. |
| **7. Better structural evidence, especially tables and Word objects** | [`X401`](packages/core/researchly/rules_structure.py#L490) checks whether a numeric value occurs anywhere in a cited table; it does not match a particular row, column or population. Live Word paragraphs do not retain all the objects available to `.docx` ingestion. | Display “value not found” as a bounded check. Add row/column identifiers before claiming contextual consistency; show compared cells and rounding assumptions. Expose unsupported Word-object checks through capabilities instead of implying upload/add-in parity. | Swapped rows, wrong groups, repeated values, units and rounded values are tested; unsupported inputs abstain rather than pass. | L; richer structure/Word metadata; do not equate number membership with scientific accuracy. |
| **8. Long-document progress and recovery** | [`engine.ts`](apps/web/lib/engine.ts#L40) waits up to 290 seconds; the UI mainly has a spinner. PLAN records long thesis checks and defers Q2 optimization by owner decision. | Start with elapsed time, a clear “still checking” message, preserved prior results and predictable cancel/retry. Later consider chapter-aware analysis with a separate whole-document pass. Browser cancellation should not be described as proof that server work stopped. | Large synthetic documents survive cancellation/retry without displaying an old response as current; chapter mode preserves cross-chapter consistency checks and offsets. | S for honest status; L for splitting. Respect the owner's deferred Q2 work. |
| **9. Teach the writer after a check** | Rules have source and explanations, but [`to_suggestion`](services/engine/researchly_service/engine_adapter.py#L128) always returns `learn_ref=None`. | Add short authored Learn cards linked to each recurring issue: principle, one synthetic good/bad example, and a question the writer can ask next time. Optional progress should use counts and explicit opt-in, not stored manuscripts. | A writer can apply a lesson to a new paragraph; examples are original/licence-clean; trends never become a grade. | M; S4 Learn cards already planned; postpone cross-document trends until privacy choices are explicit. |
| **10. A spelling policy that distinguishes repeated typos from terminology** | [`S001`](packages/core/researchly/rules_spelling.py#L120) skips any word used three or more times. A probe flags one `recieve` as `receive`, but suppresses all S001 flags when the typo appears three times. Grammar was disabled to isolate this tier; other tiers may independently notice it. | Keep scientific-term guards, but replace blanket repetition suppression with one grouped, cautious vocabulary/typo prompt. Ask the writer whether to add a term; do not auto-add it. | Repeated known typo pairs remain visible while repeated legitimate domain names stay quiet; measure both outcomes on labeled examples. | M; precision evaluation before changing the guard. |
| **11. Local-mode parity and a clear privacy choice** | The landing page advertises a local mode; the website has no engine selector, while the Word taskpane does. Account dictionary/locale choices are not all forwarded to local checks. | State which surfaces support local checking and what a signed-in local check still contacts for settings. Provide one capability summary and installation health check. Expand web-local checking only after testing browser transport/CSP and the full contract. | A writer can choose correctly without understanding deployment internals; each local route demonstrates its promised checks and text destination. | M; R1 first; preserve the no-cloud-LLM requirement. |
| **12. Account controls suitable for broader use** | Settings delete dictionary/settings rows but retain the sign-in identity; the engine rate limit is per IP and per instance; real Supabase/Word email flows are external dependencies. | Separate “Reset preferences” from “Delete account,” add secure self-service deletion before public beta, and use per-user limits with an anonymous IP fallback. Test institutional shared-network and email-delivery behavior. | Two users on one network do not unfairly exhaust each other's allowance; deletion has a verified lifecycle and no client-held privileged key. | M; existing S2/S6 open work, backend and owner configuration. |

## Product claims and evaluation

[`WhyResearchly`](apps/web/components/WhyResearchly.tsx) should distinguish **implemented capability**, **heuristic coverage**, and **future work**:

- “Measured false-flag rate” currently rests on flag density on accepted theses/published papers. [`noise_gate`](ml/dogfood/noise_gate.py) correctly calls this a proxy for fatigue. A flag on published prose can be valid advice, so **flags/1,000 words is not an annotated false-positive rate**. Publish that metric under its actual name, alongside precision from human-labeled samples and uncertainty. The logged 11.67/1,000-word figure is historical project evidence, not remeasured by this review.
- “No AI model reads your draft” is too broad for a system whose parser is spaCy's trained model. A more precise claim is that no cloud LLM or generative model sees it; explain where processing happens. This remains compatible with the approved future local, non-generative tier.
- “The same answer every time” needs a defined engine/dependency/config/profile version. Changes to settings, dictionaries and upstream grammar rules legitimately change outputs. Record those versions without storing text; include them in exports.
- “Exact checks” should describe the structural checks actually supported for each input, not imply every quoted table value or manuscript relationship is validated. The numeric membership check described above is narrower.
- The copy says Researchly “does neither” after describing grammar checking and text generation. It does offer grammar checking. State that it goes beyond grammar and leaves authorship to the writer.

**Evaluation improvements:** keep the existing invariant tests, privacy canaries, noise regression gate and per-rule fire/don't-fire cases. Add a small held-out, human-labeled set stratified by genre, discipline, format, English variety and draft stage. Track suggestion precision, missed known problems, severity, abstentions, coverage and rule/tier health separately. Split tuning and hold-out documents so a quieter engine cannot appear better just by suppressing useful checks. No private thesis passages should be copied into shipped fixtures.

For the new brief, label **each assertion** as supported, overstated, unsupported or not applicable, in addition to testing its JSON shape. For cross-surface features, test the same synthetic document through the actual browser, hosted service and local handler. Real Word timing, search semantics, fields and equations still need a host test matrix; fake Office.js cannot establish that compatibility.

## Suggested implementation batches

| Batch | Deliverables | Exit condition |
| --- | --- | --- |
| **A — Restore and protect existing workflows** | R1 local contract, R3 editing outcomes, R7 Unicode ranges. | Real adapters exercised; Word checks field safety; edits never falsely reported as untouched. |
| **B — Make current feedback trustworthy** | R2 Auto precedence, R4 brief evidence states, R6 explicit stage, R8 report caveats; bounded product claims. | No false reassurance from suppressed checks; every result explains its context and coverage. |
| **C — Improve daily revision** | Session dismissal/undo, grouped revision queue, evidence navigation, coverage/main-file choice, elapsed-time recovery. | Representative writers can act on chapter-length feedback without losing context or making blanket mutes. |
| **D — Expand document coaching** | R5 claim/evidence links, genre-native profiles, narrative map, reporting checklists, Learn cards. | Human-labeled evidence demonstrates useful precision per genre; links are inspectable; no science-validity verdicts. |
| **E — Validate learned additions and reach** | Existing S5 local-model bake-off; account lifecycle and live-host checks before broader beta. | Existing licence, precision and privacy gates hold; deploy/host evidence is recorded. |

These are proposed priorities, not changes to PLAN's completion flags. Several items already exist in S4/S5/S6 or the Inbox; the added value here is the concrete failure modes, dependencies and acceptance criteria.

## Validation and limits of this review

Executed against the reviewed baseline with Python 3.10.21, Java 21, Node 24 and the installed dependencies:

- Core: **820 passed, 2 skipped**. Skips: macOS Java-stub scenario; remote LanguageTool test requiring `RESEARCHLY_TEST_LT_URL`.
- Hosted service: **166 passed**; one upstream Starlette/httpx deprecation warning.
- Web: lint and confidentiality-boundary check passed; TypeScript check passed; **240 unit tests passed**.
- OpenAPI drift and generated TypeScript contract checks passed.
- Browser end-to-end suite: **105 passed, 7 skipped** (the optional screenshot cases). Both production builds succeeded. The existing suites mock the engine, Supabase and Office.js; they do not validate the real local Word server. Used four workers and installed `/usr/bin/chromium` through an external Playwright config, with the repository's test cases unchanged; this is not validation against CI's pinned browser binary.
- Synthetic probes reproduced R1, R2, the adapter-boundary cases in R3, R4, R6 and the offset mismatch in R7, plus the repeated-spelling policy. Grammar was disabled for selected probes to isolate the feature being assessed; those probes are not grammar-tier validation.

Passing tests do not negate the findings: their scenarios are not represented in the existing suite. Application source, tests, dependency manifests and lockfiles are unchanged by this review; only this document and the required project-log entry are proposed.

This review did not run production load tests, private-corpus evaluation, a new learned-model benchmark, live Supabase account deletion, real Word-host automation or native desktop packaging. It is a broad product/code review, not a comprehensive security audit or a claim that deployed production matches this commit.

## Minimal reproductions for follow-up work

Run these from the repository root in the prepared Python environment. Inputs are synthetic. Keep resulting evidence outside the checkout.

```python
import sys
sys.path[:0] = ["packages/core", "apps/word-addin"]
import server
from researchly import api
from researchly.config import Config
from researchly.document import Document
from researchly.lsp import to_position

# R1: options sent by every current taskpane check; raises ContractError(422).
server.parse_word_request({
    "paragraphs": [{"text": "Vaccination reduced transmission."}],
    "options": {"show_preferences": False, "disabled_rules": [],
                "mode": "revise", "document_type": "auto", "review": False},
})
```

Run the following independently of the intentional exception above:

```python
text = ("Introduction\n\nLittle is known about the burden.\n\n"
        "Methods\n\nWe fitted a model to weekly counts.\n\n"
        "Results\n\nVaccination reduced transmission.\n\n"
        "Discussion\n\nThe evidence proves that mandates reduce transmission.\n")
for source in (text, text + "\nRecommendations\n\nRestore the mandate.\n"):
    a = api.analyze(source, cfg=Config(grammar_tier=False), with_review=True)
    print(a.profile.id, sorted({s.rule_id for s in a.suggestions}),
          a.review["questions"][2]["verdict"])
# manuscript: C302/C303; policy-brief: neither; causal verdict becomes negative.

a = api.analyze("Discussion\n\nThe fit was stable across the districts.",
                cfg=Config(grammar_tier=False), with_review=True)
print(a.review["questions"][3])  # says a gap statement is present without evidence

source = "😀 The the model was fitted."
offset = source.index("the")
print(to_position(Document.from_text(source), offset).character,
      len(source[:offset].encode("utf-16-le")) // 2)
# Actual 6; expected UTF-16 column 7.
```

For R3, use an `OfficeApi` fake with one paragraph/range containing `the the` and `WordApi 1.4` support. First make `range.fields.load()` throw: `applyReplacement` still calls `insertText`. Then let insertion succeed but make `ctx.sync()` fail when restoring `changeTrackingMode`: one insertion has occurred, but the returned message says nothing changed. Add these as regression cases in a separate implementation PR.

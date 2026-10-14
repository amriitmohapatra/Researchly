# Researchly — Working Plan

The **shared, living checklist** for building production Researchly. The
*why* lives in [`ARCHITECTURE.md`](ARCHITECTURE.md); this file tracks *what's
done and what's next*. Both the owner and Claude edit it.

## How to use this file

- `[ ]` open · `[~]` in progress · `[x]` done · `[-]` dropped (say why inline)
- **Tick a box only when its "done when" evidence exists** — a passing test, a
  measured number, a working screen. Not when code merely exists.
- Owner tags: **(Amriit)** = needs the owner; **(Claude)** = lead engineer /
  sub-agents. Untagged = Claude.
- When a task finishes, append a one-line note: date, commit/PR, evidence.
  Example: `- [x] Wire CI — 2026-10-05, a1b2c3d, 275 tests green in Actions`
- New work goes into the right slice, or **Inbox** if unsure. Don't start a
  slice until the previous slice's exit check is ticked.
- Substantive work still gets a dated entry in `docs/PROJECT_LOG.md`.

**Current slice: S4 — Narrative map v1** (started 2026-10-08 after P35 merged as amriitmohapatra/Researchly#9 and the owner deployed it; the owner: "move to next steps"). S3's exit check (a week of real use) runs on in parallel with the owner; S1's and S2's real-document exit checks are still open with the owner; S2b's passed.

---

## Product decisions — see ARCHITECTURE.md §1.3–1.4

- [x] **P1** Coach alongside existing tools: web revision studio + Word/Overleaf add-ins; Draft / Revise mode — 2026-10-03
- [x] **P2** Consistency checks + reporting-guideline checklists in v1 — 2026-10-03
- [x] **P3** First discipline pack: epidemiology / ID modelling; expand later — 2026-10-03
- [x] **P4** Figures/tables/equations: structural checks; no image understanding — 2026-10-03
- [x] **P5** Responsive web (PWA) + desktop add-ins; phones for reading; no native apps in v1 — 2026-10-03
- [x] Positioning ("Why Researchly?") written down with its claims — ARCHITECTURE.md §1.3, 2026-10-03

## Owner decisions — see ARCHITECTURE.md §13

- [x] **D1** "Confidential by design" approved as drafted — 2026-10-03
- [x] **D2** Free / non-commercial for now — 2026-10-03. Vercel Hobby OK; NC data for evaluation only; shipped models stay licence-clean
- [x] **D3** Singapore — 2026-10-03
- [x] **D4** `Researchly_Updated_14082026` is the baseline — 2026-10-03
- [x] **D5** macOS app & Windows scaffold → maintenance-only — 2026-10-03
- [x] **D6** Sample theses: private evaluation only; thesis exemplars stripped from shipped data — 2026-10-03
- [x] **D7** `Notes_On_Writing/` = knowledge source (W5 re-mine); papers/theses added later via the dataset registry — 2026-10-03
- [x] **D8** Laya only via the S5 bake-off — 2026-10-03

---

## S-1 — Architecture (this session)

- [x] Read *The Art of Building Software* ch. 20–27 and adopt its method — 2026-10-03
- [x] Codebase audit, Laya identification, hosting research (3 sub-agents) — 2026-10-03
- [x] Write `ARCHITECTURE.md` draft v1 — 2026-10-03
- [x] Create `PLAN.md` — 2026-10-03
- [x] Owner reviews ARCHITECTURE.md and answers D1–D8 — 2026-10-03
- [x] Revise ARCHITECTURE.md to v1.1 with D2–D8 — 2026-10-03
- [x] Amend CLAUDE.md non-negotiable #2 — 2026-10-03, ARCHITECTURE.md v1.2

## S0 — Foundation (one repo, green CI; no user-visible change)

- [x] Create monorepo skeleton: `apps/ services/ packages/ ml/ docs/adr/ legacy/` — 2026-10-03; README in each folder
- [x] `git mv` baseline tree (D4) into `packages/core` + `apps/`; others into `legacy/` — 2026-10-03, d13255d; 260 passed / 1 skipped after the move (same as before)
- [x] Merge P19–P21 entries into root `docs/PROJECT_LOG.md` — 2026-10-03, 83421b5
- [x] Fix the Linux-only test failure (`test_jdk_found_with_a_finder_launch_environment`) — already fixed in the baseline tree (P19); passes on Linux
- [x] GitHub Actions: ruff + pytest + noise-floor gate + third-party scan + secret scan — 2026-10-03, all 5 green on PR #1 at c041cdd: 261 passed / 1 skipped on Python 3.10 + Java 21; noise floor 14.84 reproduced exactly on CI (delta 0.0); scan 0 hits; gitleaks clean
- [x] `ml/datasets.yaml` registry: 41 entries, licence + verified flag + permitted use + hash — 2026-10-03, 83421b5. Many licences unverifiable from the sandbox (proxy-blocked); marked unverified and narrowed
- [x] Thesis-derived exemplars are not in shippable code — they stayed in `legacy/experiment-p21/` (verified by the registry audit)
- [x] Remove third-party text found *inside* `packages/core` (Pallas exemplar abstract + frames, Endo lecture quotes in why-texts, ChenY thesis fragments, an NG5001 fixture) — 2026-10-03: paraphrased with attribution kept, original frames, synthetic fixtures. `check_third_party.py`: 19 hits → 0. Rule logic unchanged (string-blanked AST identical); tests 261 passed / 1 skipped. Several swapped fixtures now test their guard *more* strictly (C301, E703)
- [x] Quarantine `move_clf.joblib` — it stays in `legacy/experiment-p21/`, not loaded by the engine, until the S5 bake-off
- [x] Add S001 lexicon gaps: `estimand(s)`, `urbanicity`, `prespecified`, `lockdown(s)`, `serotypic`, `tradeoff(s)`, `exergy` — 2026-10-03, ee0057d; regression test fails without, passes with
- [x] Update CLAUDE.md / AGENTS.md / README repo map + commands to the new layout — 2026-10-03
- [x] Noise-floor gate: `ml/dogfood/noise_gate.py` + `baseline.json` — measured **14.84/1000w** all tiers (12.5 ex-S001; 12.8 ex-LT001). Fails on a rise > 0.3 *or* a busy rule going silent (dead tier)
- [x] **Exit check:** CI green on PR #1 ✅; `check_third_party.py` exits 0 ✅; owner merges PR #1 **(Amriit)** ✅ (merged 2026-10-03)

## S1 — Engine online (paste text at a private URL → suggestions)

- [x] API contract v1 first (Pydantic → OpenAPI → generated TS types), drift check in CI — 2026-10-03, 53862dd / 0f711e1; the check caught a real drift before regeneration
- [x] FastAPI `services/engine`: `/v1/analyze`, `/v1/health`, `/v1/rules`; per-request in-memory config (never reads ~/.researchly); one engine lock + Cloud Run concurrency 1 — aef87e6; 74 service tests
- [x] Q6 canary test (release-blocking): canary absent from all logs, stdout/stderr, error bodies, headers and /v1/health across success, every error path and forced crashes — aef87e6. **It found and fixed a real leak** (failed log write dumped a traceback with the document)
- [x] Logging: one JSON line per request, never text; exceptions as class + frames only — aef87e6 (Sentry not wired yet → S6)
- [x] Remote LanguageTool sidecar support (`RESEARCHLY_LT_URL`), probed by real check, backs off and recovers; failure detail is exception type only — aef87e6; probe cached for public /v1/health — 32a5135
- [x] Dockerfile (no Java, non-root, allow-list `.dockerignore`) + docker-compose + Cloud Run spec with sidecar, max 2 instances — aef87e6
- [x] Web page (Next.js 16): paste → highlights + cards + why + source; health banner; read-outs not a score; per-request nonce CSP; privacy boundary enforced in lint — 27ed1c2; redesigned with the owner's UI/UX skills, anti-ui-slop gate passed — d5448c9
- [x] Security review (security-review skill) of the engine service — no vulnerabilities at the reporting bar; one logic bug (uncached probe) fixed — 32a5135
- [x] Real end-to-end run (web → engine container → LanguageTool container, no mocks): section-awareness and emoji offsets correct, no CSP/console errors — 2026-10-03. It exposed two defects, both fixed in cb7375b: bare "§4" sources (now full citations via `sources.py`) and a duplicate "the the" flag (LanguageTool rule covered by W207 skipped; noise floor 14.84 → 14.75)
- [x] CI jobs for engine-service, contract, web (lint/typecheck/unit/e2e) and engine-image (privacy path check + boot) — b989081; all 9 checks green on PR #1 at b5c49c7 (web: 28 Playwright e2e passed on a production build, 0 retries)
- [x] Manual deploy workflow (WIF, deploy by digest, smoke test) + owner guide `docs/deploy.md` — 73a5755
- [x] Fixes from the live check — 4187ded: the reading key taught two categories the engine never gives (specimens now shared via `packages/contract/reading-key.json` and verified against `api.analyze` by `test_reading_key.py`); the "could not reach the engine" message names the host it tried; `bench.py` no longer crashes on `--n-chapter 0`
- [x] Cloud Run deploy in Singapore **(Amriit: docs/deploy.md steps 1–3, 5)** — 2026-10-03, `researchly-engine` in asia-southeast1 with the LanguageTool sidecar; health green on every tier
- [x] Vercel project for `apps/web` **(Amriit: docs/deploy.md steps 4, 6)** — 2026-10-03, production alias researchly-chi.vercel.app; live headless-Chromium check: HTTP 200, suggestions rendered, no console/CSP errors; owner confirmed in their own browser
- [x] Measure Q1/Q2 latency on the real deployment — 2026-10-03, `bench.py --url` against Cloud Run (warm; measured from Claude's cloud sandbox, so wall times include the network from there, about 1.4 s per request):
  - Q1 paragraph (311 words, n=20): **server p50 484 ms (meets 800 ms)**; wall p50 1.89 s / p95 2.02 s from the sandbox. Re-measure wall time from Singapore before calling Q1 met for users.
  - Q2 chapter (10,228 words, n=3): **server p50 6.89 s; wall p95 9.35 s — misses the 6 s target.** Follow-up below.
- [-] Bring Q2 under 6 s on Cloud Run — deferred by the owner (2026-10-03, "no need to speed up"); back in the Inbox
- [~] **Exit check:** owner pastes a real chapter on the deployed site and gets the same suggestions as the CLI — live vs local engine parity proven on a synthetic 10,316-word chapter (63/63 suggestions identical, 2026-10-03); waiting on the owner's real chapter **(Amriit)**

## S2 — Accounts, files, settings sync

- [x] Supabase project (region D3) **(Amriit: create project; docs/deploy.md step 8)** — 2026-10-03, owner signed in and out on the live site. Checked from outside: anonymous read/insert/update/delete and RPC calls refused (42501 permission denied), a forged unsigned token rejected (PGRST301), signing keys ES256
- [x] Schema: `user_settings`, `dictionary_words`, RLS per command, `my_config()` (s2-design §2) — afc3041. `profiles`, `usage_events`, `feedback_events` are **not** created until a feature reads them (collect only what's needed)
- [x] Engine verifies JWT; `user_id` from token only; remote config layer in `config.py` — 2026-10-03, 8e82b7a: JWKS verification with the algorithm pinned to the key, settings read via PostgREST with the caller's own token (no secret key in the engine; it refuses to start with one); 39 token/settings tests, 3 new canary scenarios
- [x] `/v1/analyze-file` (raw bytes, filename never logged, 25 MiB cap, sign-in required when accounts are on) — 8e82b7a, 16 tests
- [x] Two-user test (read/update/delete) automated in CI (Q7) — afc3041 + f5ac4b8: 90 tests on Postgres 16 with a Supabase shim, and all 19 deliberate weakenings of the migration caught (re-run independently by the lead). CI job `supabase-rls` green on GitHub at c975bec (amriitmohapatra/Researchly#2, merged 2026-10-03), after fixing a test that assumed the server's sort order
- [x] LaTeX adapter on pylatexenc; multi-file `.zip` (`\input`/`\include`/`\subfile`) — 8dd7b00, 6488b8a: 106 + 38 tests; parse failure falls back to the regex masker with a visible warning; hostile zips (bomb, traversal, symlink, encrypted, fan-out) refused
- [x] `.docx` OOXML adapter (styles incl. localised ids, headings, tables, tracked changes read as accepted; defusedxml; zip-bomb guard). Comments and footnotes ignored in S2 — 6488b8a: 37 tests incl. XXE and billion laughs; identical to the Word add-in path
- [x] Offset round-trip property test for every adapter — seeded random round trips: 40 LaTeX, 15 zip, 20 docx
- [~] Cross-surface parity test (mute in one surface → muted everywhere) — the engine applies account mutes for any caller with a token (test_accounts.py); the Word add-in joins in S3, when it moves to the hosted engine
- [x] Sign-in, upload, settings + dictionary UI in web app — 1bb2804…b193bf6, 4b56345: magic-link sign-in (PKCE in the browser), bearer on engine calls with one refresh-and-retry, upload by button or drop with a read-only file view and per-file locations, `/settings`, Mute / Add-to-dictionary on cards, atomic mute RPCs. With the Supabase variables unset the site is exactly S1 (own e2e project). 152 unit + 59 e2e (two builds), axe clean light and dark, anti-ui-slop gate passed
- [x] Adapters keep figures, tables, equations and captions as *structure* (not just masked text) — needed by S2b — `Document.structure`, returned as `document.structure`
- [x] Web layout responsive from the start (P5): checker, file view, settings, menus and dialogs at 375 and 1280 px with a no-horizontal-scroll check on every e2e run (Learn views arrive in S4)
- [ ] **Exit check:** owner uploads a real `.tex` and `.docx` thesis chapter; offsets correct; settings sync across two browsers

## S2b — Consistency & structure checks (P2, P4)

Built 2026-10-04 (P32): `researchly/structure.py`, `rules_structure.py`, `rules_consistency.py`; 12 rules, 76 tests (`test_structure_rules.py`, `test_consistency_rules.py`). Structural rules run on LaTeX and Word only.

- [x] Abbreviations: defined at first use (F601, existing), defined once (**F612**), used after definition (**F613**, Preference); definitions found with Schwartz & Hearst's algorithm
- [~] Terminology consistency: the same compound written closed and open (**W211**: "dataset"/"data set"). Concept drift ("infection rate" vs "incidence") needs meaning, not spelling: not deterministic, left to the review lens
- [ ] Tense consistency per section — deferred: no named source yet in the knowledge base (CLAUDE.md #6), and present tense is legitimate for model descriptions in Methods
- [x] Numbers and units: mixed number–unit spacing (**N101**), sentence opening with a numeral (**N102**)
- [x] Figures/tables: every one cited (**X101**), cited in order (**X102**), cited before it appears (**X104**, Word), labels and numbers exist (**X103**). Bench: 120 flags on the 17 real LaTeX projects at first, 14 after fixing what they showed; the ones read are genuine
- [~] Caption quality: too short (**X202**). Abbreviations defined in the caption (X203) tried and dropped: 79 false flags on 17 projects. Missing caption (X201) deferred: a captionless float has no prose to anchor to
- [~] Equations: numbered but never referred to (**X301**, Preference). Symbols defined near first use (F603) deferred: not deterministic enough
- [x] Text↔table numbers: a decimal or percentage quoted with "Table N" that Table N does not hold (**X401**; rounding allowed; levels, versions, totals skipped)
- [x] Each check: question-form message + named source (ICMJE, SI Brochure, AMA Manual of Style, guide §6/§9.1/§9.2/§9.7), fire and don't-fire tests, rule-inventory rows (Layer 8), knowledge-base §10
- [x] Converted manuscripts (P33, the owner's deliberately bad .docx: a working paper run through a PDF-to-Word converter): 604 → 409 flags. Headings run into their paragraphs are split and flagged (X501); typed captions, lettered appendix floats ("Table A.4") and "(continued)" tables are read, and a caption run into a paragraph ("… linear. Figure C.2: …") counts as present. 35 tests
- [x] Noise floor: 11.94 → 12.65 on purpose (+204 flags from the consistency rules), then 11.67 after P33
- [x] Structural rules on 140 published PMC articles (CI run 37190315670 at cfddd47, PASS, 547 files): three were noisy, each reproduced on synthetic JATS and fixed with a test that fails on the old code — X401 369 (Word rendering; 24 in TeX): a table caption took the previous table's cells when journals put every table at the end, and an image-only table took the next table's; X202 74/82: short *table* titles, which ICMJE asks for (X202 now judges figure captions only); X301 373 (TeX): the converter numbered every formula and the text cites them as typed "Eq. (3)" (X301 now counts typed references; the converter numbers only formulas the article labels). Rerun 37194170115 (710436f, PASS, 14.54/1000w overall): X401 369 → 24 (Word now equals TeX), X202 74/82 → 35/40 (figure captions of under five words, read as genuine), X301 373 → 249 (a hidden Preference; many articles number equations they never cite). New regression found and fixed: X104 0 → 33 on PMC supplement .docx files once typed captions counted — X104 now judges styled captions only; list-of-figures entries and repeated typed captions are no longer floats. Confirmed by run 37197496673 (73c7d5a, PASS; 138 articles, two bioRxiv fetches rate-limited): X104 on supplement .docx 33 → 0, X401 24/24, X202 35/40, X301 248. Still open on published articles: X101 16, X102 12, X103 12 per rendering and X104 11 (Word rendering) — about one per ten articles; needs the run's samples (artifact) or a local PMC cache to judge, since the sandbox cannot reach EBI
- [x] S2b + P33 merged to main — amriitmohapatra/Researchly#5, 2026-10-04; owner deployed the engine
- [x] **Exit check:** owner checks one real chapter and reports false flags **(Amriit)** — 2026-10-04, owner: "It's good"

## S3 — Word add-in, hosted

- [x] Engine contract for Word: `POST /v1/analyze-word` takes Office JS paragraphs and returns each suggestion's Word location (paragraph, offsets, search snippet, occurrence) and what was not read — 2026-10-04, 0e02387; locator shared with the local server (`researchly/wordloc.py`); 12 service tests incl. a privacy canary on the new route
- [x] Taskpane served over HTTPS from Vercel (`/word` in apps/web); calls hosted engine — opens in the owner's Mac Word 2026-10-04 (#6, #7, #8). Built 2026-10-04 (9551525): check, Draft/Revise, cards with why + source, click-to-select, Apply as tracked changes when WordApi 1.4 is supported (direct edit otherwise, and the card says so), mute / add-to-dictionary when signed in, coverage and health notes; its own CSP (office.js origin, Office web frame-ancestors, no X-Frame-Options on /word only). Tested against a fake Office.js: 192 unit + 88 e2e passing. **Not yet run in real Word**; live after merge + deploy
- [x] Sign-in by an emailed code inside the taskpane (Supabase OTP) — works in the owner's Mac Word, 2026-10-04. Changed from "Office dialog + Microsoft provider": no Azure app registration for the owner, and Office dialogs are unreliable on Mac Word; the Microsoft provider can be added later. Owner step: put `{{ .Token }}` in the Supabase Magic Link email template **(Amriit)**
- [x] XML manifest for Mac sideloading + unified JSON manifest — 180c2f4: `manifest.hosted.xml` (new Id, so it installs beside the local one; checked offline because Microsoft's validator service is unreachable from the sandbox) and `manifest.json` (passes `office-addin-manifest validate`); `install-mac.sh hosted` sideloads it
- [~] Optional local-engine mode retained: "This computer" engine choice in the hosted taskpane; `server.py` answers `/v1/analyze-word` and `/v1/health` with the same contract (20 tests validate it against the service's models), CORS for the Vercel origin only, no token accepted. The old localhost taskpane stays as the maintenance path. Unverified: whether Mac Word's web view lets an HTTPS page call `http://localhost`; if not, the old local add-in is the fallback
- [x] Draft / Revise mode (P1) in `config.py`, so it is shared by every surface; Draft shows sentence-level checks only — 2026-10-04, 0e02387: rules declare `scope`; Draft holds back document-level checks and says how many (`hidden_by_mode`); TOML, account (`user_settings.mode`, migration `20261004120000_s3_mode.sql`), CLI `--mode`, request `options.mode`; 9 core tests, Supabase two-user suite extended
- [x] Apply migration `supabase/migrations/20261004120000_s3_mode.sql` in the Supabase SQL Editor **(Amriit)** — 2026-10-04, owner ran it; `my_config()` returns `mode`
- [x] Support contact (9551525): "Report a problem" in the add-in and the web app footer. Every surface tells users to report problems by email to **amrit.mohapatra97@gmail.com** (owner's request, 2026-10-04) — a "Report a problem" link in the add-in and the web app, with a note not to paste confidential document text into the email; README and docs say the same
- [x] Custom SMTP (Gmail) set up and the sign-in code added to the Magic Link email — 2026-10-04, owner received an email with the code **(Amriit)**. (First try failed with a misleading "could not reach" message: supabase-js reports Supabase's 500 "could not send email" as a retryable fetch error; message fixed in the web app.)
- [x] Sign-in code added to the Confirm signup email too — 2026-10-04 **(Amriit)**. (The website itself never shows a code box: it signs in by the link; only the Word add-in asks for the code.)
- [x] Owner steps before trying it (all done 2026-10-04): run the S3 migration; set up custom SMTP (Gmail app password; Supabase now allows template edits only with custom SMTP, and its built-in sender reaches only the Supabase team, so this was needed before any beta user could sign in anyway); add `{{ .Token }}` to the Magic Link and Confirm signup email templates (guide in `apps/word-addin/README.md`, "Hosted add-in (S3)"); merge, deploy the engine and the web app; sideload `manifest.hosted.xml` and fully quit Word (Cmd-Q) **(Amriit)**
- [x] S3 merged and deployed — amriitmohapatra/Researchly#6 and the start-up fix #7 (office.js defines `Word` late; the taskpane looked for it too early), 2026-10-04; `/word` in a browser shows "Open Researchly from Word" as intended
- [x] First run in real Word (Mac) — 2026-10-04: after the manifest fix (resource ids over Microsoft's 32-character limit made Word drop it silently), the add-in appears, opens, and signs in with the emailed code **(Amriit)**
- [~] **Exit check:** owner uses it on Mac Word for a week; issues logged below. First report 2026-10-08 (an assignment's `.tex` on the website; `Researchly_Improvements_8Oct2026.docx`):
  - [x] "ad valorem" read as the lone word "valorem" and corrected to "galore" — Latin phrases of academic English are now known to the spelling tier (P35)
  - [x] "suggests transition support could" flagged as a hedge stack — a hedge inside the clause a reporting verb introduces (the "that" left out) is one hedge, judged from the parse (P35)
  - [x] "Why?" texts too technical and full of internal references ("Guide §4.2", "Run `researchly abstract`", "via NG5001 Unit 2") — every rule now has a plain explanation shown first; internal references stripped and forbidden by test (P35)
  - [x] Sources: the lecture and the NUS course are shown to users as "Amriit's learnings from scientific-writing training"; the published works and the owner's guide are cited by name (owner decision 2026-10-08; knowledge-base §9b)
  - [x] New rule from the owner's professor: an equation must be part of a sentence — **X302** (LaTeX and Word; 5 genuine flags on the 17 real LaTeX projects, none on the 36 real Word files) (P35; Word the same day, after the owner asked)
  - [ ] **Owner: X302 in real Word** — after the next deploy, put a display equation right after a sentence that ends with a full stop and run a check. The add-in reads paragraph text only, so the rule depends on what Word's add-in library returns for an equation paragraph: its linear text ("λ = βI/N", the card appears) or nothing (no card; only an uploaded .docx would be checked). Not verifiable from the sandbox. If no card appears, the fix is to read equations from the document's OOXML in the add-in **(Amriit)**
  - [x] Cards: "Rule" and "Checked by" gone; plain explanation first, the technical why behind "The full reasoning"; source as a reference line (web + add-in) — 6d8daea, 2026-10-08
  - [x] Section view: the whole document is analysed, the chosen section shown; document-wide checks grouped under "Whole document"; Word "Check this section" from the cursor (whole document still sent). Mode help: "Draft: check what you've written so far. Revise: check the finished manuscript." — 6d8daea; 205 unit + 94 e2e. **Owner: click "Check this section" once in real Word** (the fake Office.js covers it; real Word has not)

## S4 — Narrative map v1

- [~] **Article-type profiles** (owner request 2026-10-08): `document_type` is stored but unused. Each type gets a profile: expected sections, rules that do not apply, what "section" means without IMRaD headings; "auto" guesses from headings. Start with **commentary** and **policy brief** (the owner's field, public health); keep the format open so other disciplines' types can be added. A commentary has no abstract moves and no Methods exemption, and may be assertive where a research paper must hedge
  - [x] Engine and service — 2026-10-08 (P36), 63be8ea: `researchly/profiles.py` (nine types; each switched-off check carries a plain reason; unheaded prose gets the profile's section; "auto" guesses only from IMRaD headings, a chapter or a recommendations heading, else "general" = the engine as before); `options.document_type`, the response's `profile`, `GET /v1/rules` lists the profiles; the account saves the type (migration `20261008120000_s4_document_type.sql`, two-user suite 92 green on Postgres 16). 24 core + 8 service tests
  - [x] "Check as" selector on the website and in the Word add-in, saved locally and to the account like the mode; the profile line under the results — 2026-10-08, d4ab5f3 (sub-agent in its own worktree, re-run by the lead): labels from `GET /v1/rules`, the chosen type's summary under the control, a changed type re-checks; web 229 unit + 103 e2e
  - [x] **Owner: run the S4 migration** in the Supabase SQL Editor (same steps as S3's), then deploy the engine and the web app **(Amriit)** — S4a merged as amriitmohapatra/Researchly#10 and deployed 2026-10-08
- [x] **Selling point on the landing page, README and demo** — 2026-10-08 (P38): the demo paper loads on the website ("Try the demo paper", from `public/demo/`); the claims bounded per the Codex review; the deck and the video made (Inbox). Was: [~] **Selling point on the landing page, README and demo** (owner request 2026-10-08; landing page and README done 2026-10-08, f0f677d; the demo manuscript now exists, so the demo itself — a walkthrough on the site, or the deck and the video in the Inbox — is what remains): the problem (feedback on scientific writing arrives late and inconsistently; existing tools check grammar or write for you), what an LLM cannot do (same answer every time; a named source per suggestion; never sees the text in local mode; never writes for you; a measured false-flag rate; exact whole-document cross-checks), and the value for early-career and non-native writers (teaches the conventions while you write). The app encourages writing; it never delegates it
- [x] **Printable report / PDF of a check** (owner request 2026-10-08): a "Print or save as PDF" view of the results on the website: the document with its highlights numbered, the matching suggestions beside them (two columns on paper), and the reviewer's brief after them. Made in the browser with a print stylesheet and the browser's own Save-as-PDF, so no document text leaves the page (ADR-02); nothing is generated server-side. Works from a pasted check and from an uploaded file; A4 and Letter; light ink only — 2026-10-08 (P36): `components/PrintReport.tsx`, mounted only while printing (the button, or the browser's own print command); the lead rendered the A4 and Letter PDFs in headless Chromium and read all four pages; 11 unit + 2 e2e tests
- [x] Port `argument.py`, `guide.py`, `abstract_lens` into `tiers/discourse/` — 2026-10-08 (P37), 9c7deb7: `researchly/discourse/` (argument, abstract_lens, moves, narrative); the old import paths re-export. The prototype's `guide.py` was not ported as code: its expected-moves table became `moves.SCHEMAS`, and its classifier and exemplar index stay out (S5 bake-off; thesis exemplars never ship, D6)
- [x] Each discourse check = authored question + named source in `knowledge/` — 2026-10-08, `discourse/moves.py`: 16 moves over six section kinds, each a question, a source code (Swales, Shehzad, Wallace & Wray, Toulmin, the guide's §2–§4, §7.3, §9.7–§9.8, the course unit shown as the owner's learnings), a lesson in everyday words and a fill-in frame in our own wording; the user-visible text is checked for internal references. Provenance in `docs/knowledge-base.md` §11
- [~] `/v1/narrative` endpoint; narrative map UI (moves present/missing/out of order)
  - [x] Engine and service — 2026-10-08, 9c7deb7: the map is built from the same parse as the suggestions and requested with `options.narrative` on every analysis route (as the brief is), not a separate endpoint that would run the analysis twice; `narrative` in the response (`NarrativeMap`); `researchly narrative` on the CLI. One misplaced sentence is reported once (the moves off the longest in-order run); the argument's missing links come from the argued sections; core 24 + service 4 tests
  - [x] Narrative map view on the website, in the Word add-in and in the printable report — 2026-10-08 (P37), cf03573 (sub-agent in its own worktree, re-run by the lead): a third tab beside the suggestions and the brief; one strip per section with the moves marked by shape and word (never colour alone), each missing or out-of-order move opened to its question, lesson and frame, each present move's sentence behind "Show the sentence"; the argument's missing links; the hedging trajectory as a table of labelled values (no bars: the design contract bans meters); the Word pane shows the strip as a list; the printable report gains a map page. Web 258 unit + 109 e2e
  - [ ] **Owner: open the Narrative map once in real Word and on the site with the demo manuscript** (the site now has "Try the demo paper") **(Amriit)**
- [~] **Critical-reader review on the hosted surfaces** (the prototype's Review: `review.py`, Wallace & Wray's five critical-synopsis questions via NG5001 Unit 1). Works today in the CLI (`researchly review`) and the old local Word add-in only; bring it to the website and the hosted add-in (`/v1/review`, a Review tab), sharing the narrative map's evidence. Owner asked 2026-10-04; it had no PLAN item of its own
  - [x] Engine and service — 2026-10-08 (P36), 63be8ea: the brief is built from the same analysis as the suggestions (`api.analyze(with_review=True)`, no second pass): five questions, each a verdict, its points and the sentences it rests on, in plain words; it respects the profile (no limitations section asked of a commentary; a pasted paragraph is not asked for sections). `options.review` on every analysis route, `review` in the response; the canary test proves the quoted sentences reach only the response
  - [x] "Reviewer's brief" view on the website and in the Word add-in — 2026-10-08, d4ab5f3: a tab beside the suggestions (web) and in the taskpane (Word); the five questions, verdict, points, the quoted sentences, the most frequent checks and the source; asked for in Revise mode, with a one-line "needs Revise" otherwise
  - [ ] **Owner: try the brief and "Check as" in real Word** after the deploy **(Amriit)**
- [x] Learn cards for every `learn_ref` — 2026-10-08 (P38), 03d98d4 + f8bb433 + f891213: 26 authored cards in six groups (`researchly/learn.py`, shipped as `packages/contract/learn.json`); every rule, narrative move and argument link resolves to one (a test fails otherwise); `GET /v1/learn`; "The lesson" disclosure on every web card and on the map; `/learn` and `/learn/[id]` pages (server-rendered, no client script); "Lessons" in the header
- [x] Hedging trajectory read-out (never a score) — 2026-10-08, part of the map: hedges and boosters per 100 words per section with a reading word (flat, hedged, assertive, balanced, heavily hedged)
- [x] Discipline-pack format + the epidemiology pack (P3): reporting checklists STROBE, CONSORT, PRISMA, EPIFORGE — checks *reporting*, never the science — 2026-10-08 (P38): `researchly/packs/` (16, 18, 15 and 15 paraphrased items, each "reported" with its sentence or "needs your check", never "missing"); `options.checklist` (an id or "auto"), `suggested_checklist`, the checklists in `GET /v1/rules`; a "Reporting checklist" select and a Checklist tab on the website (session-only "Not applicable") and in Word (Revise only); printed with the report
- [x] Personal progress view: per-rule trends across a user's documents (from `usage_events` counts — no text) — 2026-10-08 (P38), 082794d + f891213: opt-in "Keep my progress" (off by default) and the `progress_events` table (migration `20261008140000_s4_progress.sql`: the database refuses a row unless the user opted in, accepts only rule-id → count maps, keeps the newest 1,000 per user, RLS select/insert/delete own rows; two-user suite 101 green on Postgres); recorded after signed-in checks on the website and in Word, never for local checks; `/progress` with one sparkline per rule, the first and latest values in words, never a score; "Delete my progress"
- [~] Labelling guide + small annotation tool **(Claude)**; owner labels 50 paragraphs **(Amriit)**
  - [x] Guide and tool — 2026-10-08 (P38): `docs/labelling-guide.md`; `/label` (paste a paragraph, pick the section, mark each flag Useful / Wrong / Unsure, export `researchly-labels.json` with rule ids and verdicts only, kept in this browser); `ml/eval/label_precision.py` reports precision per rule with Wilson intervals and refuses a file that carries text; one shared fixture pins the web export to the Python reader
  - [ ] **Owner: label 50 paragraphs** of your own drafts across the sections at `/label`, export, and run `python3.10 ml/eval/label_precision.py researchly-labels.json` **(Amriit)**
- [ ] **Owner: run the S4c migration** `supabase/migrations/20261008140000_s4_progress.sql` in the Supabase SQL Editor (same steps as before), then deploy the engine and the web app **(Amriit)**
- [ ] **Exit check:** flag precision on the 50 labelled paragraphs reported here

### Codex review, 2026-10-08 (`Codex_Review_8Oct2026.md`; the owner: "implement as you deem fit")

Findings R1–R8 were fixed in S4c. Feature proposals 2, 6 and 9 were built. The rest are recorded here with the review's acceptance evidence, so a later slice can pick them up.

- [x] **R1** The local engine accepts every option the hosted taskpane sends — 03d98d4: `apps/word-addin/server.py` shares `researchly/shapes.py` with the service; `services/engine/tests/test_local_word_contract.py` posts every `AnalyzeOptions` field to the real local handler and validates the reply against the contract
- [x] **R2** "Auto" no longer drops research checks from a manuscript with a policy-style heading — 03d98d4: research structure (Methods, Results, a chapter) wins over policy headings; the guessed type carries the headings it rests on (`profile.evidence`), shown under the results
- [x] **R3** Word edits fail closed: a protected field or a partial change is reported as such, never as "no change" — f891213: four outcomes (applied, applied without restoring Track Changes, not applied, unknown); "not applied" only after a fresh re-read finds the paragraph unchanged; the paragraph's other cards go out of date after an edit; the fake Office fails on demand for every reproduction. **Owner: apply one fix in real Word on Mac** to confirm **(Amriit)**
- [x] **R4** The reviewer's brief says what it checked: each question is yours / detected / not detected / not assessed / not applicable, abstains when it saw no claims, honours muted rules, and carries a one-line disclaimer — 03d98d4
- [x] **R5** Argument links are local: a warrant counts within one sentence of the claim and grounds within two, per section instance, from the shared parse; missing links quote the sentence they concern — 03d98d4
- [x] **R6** The website sends the mode explicitly ("revise") and shows what Draft held back — f8bb433
- [x] **R7** LSP ranges are UTF-16 columns; stale results are dropped and closing a document cancels its check — 03d98d4, `tests/test_lsp.py`
- [x] **R8** The printable report states the mode, the document type, the checklist, every tier that was off and the time of the check; multi-file uploads print each suggestion's file and line — f8bb433
- [x] **Product claims** bounded on the landing page: "no cloud or generative AI reads your draft", the noise read-out named as such with labelled precision "being added", "with the same settings, the same text gets the same feedback" — f8bb433
- [x] **#2** Dismiss once ("Not an issue here") with Undo, session-only; a muted rule's cards disappear at once — f8bb433
- [x] **#6** Reporting checklists with "reported / needs your check", session-only "not applicable" — see the S4 item above
- [x] **#9** Learn cards linked from every suggestion — see the S4 item above
- [ ] **#1 Revision queue**: "Correctness first", "Clarity next", "Whole-document review"; recurring issues grouped with Next/Previous; no score. *Done when* a chapter-scale usability test shows writers finish a chosen pass without losing findings or context
- [ ] **#3 Evidence-linked brief, the rest**: "Show in text" from each prompt; the claim beside its proposed evidence. *Done when* every supported assertion jumps to the right text (emoji and multi-file inputs included) and unsupported ones abstain
- [ ] **#4 Genre-native profiles, the rest**: separate article type from whole manuscript / excerpt / chapter; map Context/Evidence/Options/Recommendations and reviewer-comment units. *Done when* profile tests cover topical headings and legitimately missing sections (the policy brief no longer expects an abstract: done in 03d98d4)
- [ ] **#5 Coverage summary**: say what was read, masked and skipped (notes, text boxes, headers); the chosen main `.tex` file with a choice when ambiguous; an English-only notice. *Done when* synthetic documents with footnotes and text boxes show the omissions and an ambiguous project lets the writer pick the root
- [x] **#7 Table evidence**: X401 matches a row and column, not "anywhere in the table"; shows the compared cells and rounding. *Done when* swapped rows, wrong groups, repeated values, units and rounding are tested and unsupported inputs abstain — 2026-10-14 (P42): `researchly/tables.py` reads Word tables as grids from cell places (`Document.table_cells`, set by the `.docx` reader and by the local add-in's new `cell` field); a sentence naming one row header and one column header is compared with that cell, typed (a percentage only with a percentage), with the old rounding allowance; the suggestion says "Table 1 reports 8.2% in the Mortality row, Treatment column; this sentence says 12.5%." and carries `table_evidence` in the contract. Swapped groups, wrong rows, repeated values, rounding, header units, incompatible units, ambiguous headers, merged cells, derived numbers, no places and LaTeX are tested (`tests/test_table_cells.py`, 39; `services/engine/tests/test_table_cells_service.py`, 14; `tests/test_word_addin_cells.py`, 8); every abstention falls back to the whole-table check, never to a confirmation
  - [ ] **Owner: check one table in real Word on Mac** (the local add-in): restart `server.py`, quit Word fully (Cmd-Q), reopen, and quote a number from the wrong row of a simple table. The cell places come from WordApi 1.3, untested in a real host **(Amriit)**
  - [ ] The hosted taskpane (`apps/web/lib/word/office.ts`) sends `cell` too; the engine already accepts it
  - [ ] LaTeX `tabular` grids, merged header rows (a group spanning columns) and row groups; until then those tables keep the whole-table check
- [ ] **#8 Long documents**: elapsed time, "still checking", previous results kept, predictable cancel and retry; later, chapter-aware analysis. *Done when* a large synthetic document survives cancel and retry without showing an old response as current. Respects the owner's deferral of Q2
- [ ] **#10 Spelling repetition**: replace "skip any word used three times" with one grouped prompt that asks before adding a term. *Done when* repeated known typos stay visible and repeated domain terms stay quiet, measured on labelled examples
- [ ] **#11 Local-mode parity**: one capability summary per surface (what a local check still contacts), an installation health check. *Done when* each local route demonstrates its promised checks and where the text goes
- [ ] **#12 Account controls**: "Reset preferences" separate from "Delete account" (self-service, verified lifecycle); per-user rate limits with an IP fallback. Before the public beta (S6) **(Claude, owner configures Supabase)**

## S5 — Critic bake-off (Laya vs ModernBERT)

### Real-document test bench (P29, owner request 2026-10-03; seeds S5a)

- [x] Manifest of 208 openly licensed documents, every licence verified per item — `ml/realdocs/manifest.yaml`, `SOURCES.md`, six `datasets.yaml` entries: 115 PMC OA articles (9 disciplines, 34 epidemiology), 20 PMC articles with native `.docx` supplements, 14 medRxiv/bioRxiv preprints, 18 LaTeX manuscripts on GitHub (CC BY/CC0), 41 Word robustness files
- [x] Bench: fetch at run time (never committed), three renderings per JATS article (plain/docx/tex), invariants (lengths, segment round-trip, span bounds/text, spans never on masked markup, no I/O while reading, no crash/hang), format parity, report with no text — `ml/realdocs/`, `.github/workflows/realdocs.yml` (dispatch, weekly, engine changes); 26 tests in CI
- [x] Local run on the 59 GitHub-hosted documents: **PASS** after the P29 fixes (was FAIL: 1 crash, 21 span violations, 2 projects refused); LaTeX 19.4 → 16.2 flags/1000w
- [x] First full run in GitHub Actions — 2026-10-03, run 37136223549 on 020bd32: **PASS** (1 h 47 min). All 115 PMC articles in three renderings (2.25M words), 74 native Word supplements from 20 articles, 17 LaTeX projects, 41 Word robustness files: no crash, every invariant held. Format parity: docx vs plain −0.44, tex vs plain −0.34 flags/1000w (mean of 118 articles). Published articles run at ~16 flags/1000w (PMC plain 16.46), like the theses (14.51)
- [x] P28 + P29 fixes and the bench merged to main — amriitmohapatra/Researchly#3, 2026-10-04 (91e1c19). Live after the owner runs **Deploy engine** **(Amriit)**
- [x] P30 + P31 (nested-heading sections, Q3 tune 14.51 → 11.94, PMC preprints) merged to main — amriitmohapatra/Researchly#4, 2026-10-04, all 12 checks green incl. the full real-document run. Live after the owner runs **Deploy engine** **(Amriit)**
- [x] Preprints — 2026-10-04 (P30/P31): added 11 CC BY/CC0 preprints that PMC mirrors (NIH Preprint Pilot; ids `pmcpreprint-*`, registry `realdocs-pmc-preprints`). CI run 37183107815: all 11 fetched through Europe PMC and passed every invariant, but only 4 are full papers (6.4k–13k words); 7 returned 170–400 words (Europe PMC holds the abstract only). The original 14 stay as a weekly check on the servers
  - [ ] Replace the 7 abstract-only preprints with ones whose Europe PMC record has a body (check `fullTextXML` length before adding), or fetch them from NCBI's PMC OA service
- [ ] Add the published-article rate to the Q3 work: tune precision against PMC articles as well as the 8 theses (they are licence-clean, so examples can be inspected in the CI artifact)
- [ ] Gate on flags/1000w per discipline once a baseline exists (reported, not gated, today)

### S5a — Open-access training corpus (owner request, 2026-10-03)

Build a broad, high-quality, **licence-clean** corpus so the critics learn
patterns of good research writing across disciplines, not just epidemiology.

- [ ] Write a corpus spec: target disciplines (life sciences, medicine, public health, physical sciences, engineering, social sciences, humanities), journals (Nature family, Lancet family, PLOS, eLife, BMJ, Science Advances, PNAS OA…), article types, size target, de-duplication
- [ ] Harvest with the connectors — **PubMed** (search + `get_copyright_status` per article), **bioRxiv/medRxiv**, **Scholar Gateway**, **Consensus** — plus web search for publisher OA pages
- [ ] **Licence filter at intake:** keep CC BY / CC0 only (shippable); CC BY-NC(-ND) goes to evaluation only (D2); anything unclear is dropped. Every article gets a `ml/datasets.yaml` item with its licence evidence
- [ ] Extract structure for free labels: section headings → section roles; structured abstracts → sentence roles (Background/Methods/Results/Conclusions); figure/limitation/contribution sentences
- [ ] Store outside the repo (object storage or the owner's machine) with a manifest + hashes in `ml/`; never commit full texts
- [ ] Hold out a test split per discipline; report results per discipline, not just overall
- [ ] *Done when* ≥ N licence-verified articles across ≥ 6 disciplines are registered and the S5 training scripts read them (N set in the spec)

### S5b — Bake-off

- [ ] `Critic` interface in `packages/core/critics/`
- [ ] Laya zero-shot spike with `laya-evals` on ~50 labelled paragraphs (expect near-chance; learn the harness)
- [ ] Task A — flag re-ranker (accept/dismiss data): Laya vs ModernBERT-large. Owner also named **Jev** (TypeSafe AI; a non-generative choice/score/yes-no model, 2026-10-08): a candidate only if its weights run inside our own engine container — as a hosted API it is a cloud model (CLAUDE.md #1) and would see document text (#2). Check licence and local availability when S5 starts
- [ ] Task B — sentence rhetorical role (baseline 82.6%): Laya vs ModernBERT-large
- [ ] Verify licences of PubMed-RCT / CSAbstruct / CaRS-50 before training anything shippable
- [ ] ONNX INT8 export, SHA-pinned; model cards; `health.py` entries
- [ ] Promotion gate: precision ≥ 0.85, noise floor ≤ 11/1000w, fire + don't-fire tests
- [ ] **Exit check:** a model ships, or this file records "not shipped, because …"

## S6 — Reach

- [ ] Overleaf browser extension (CodeMirror 6)
- [ ] Installable PWA (P5)
- [ ] **Comparison study** (ARCHITECTURE §1.3): Researchly vs Grammarly vs a generic LLM prompt on the same public CC-BY chapters — false-flag rate, run-to-run consistency, sourced-feedback share; publish as measured. ⚠ Running Grammarly/an LLM on *public* text for evaluation is not product use, but confirm with owner before running **(Amriit)**
- [ ] Privacy policy, sub-processor list, DPAs (Vercel Pro, Supabase, GCP) **(Amriit)**
- [ ] AppSource submission (if D2 = paid/public)
- [ ] Public beta cohort
- [ ] **Exit check:** beta feedback summarised; legal checklist complete

---

## Inbox (unsorted ideas & issues)

- [x] **Demo manuscript** — 2026-10-08 (P37), `demo/`: a made-up SEIR paper on one dengue season in three fictional districts (about 1,540 words of prose), one source of truth rendered to `demo/dist/researchly-demo.docx` (real heading and caption styles, a Word table, two figures, equations as Office Math), an Overleaf project `researchly-demo-overleaf.zip` (`\input` sections, `.bib`, labelled floats and equations) and a Markdown copy for the text box; 17 planted errors (uncited table, figures out of order, a broken reference, a number not in its table, an abbreviation defined twice, a short caption, an equation after a full stop, passive with agent in the Discussion, an overclaim, a stacked hedge, a/an, two spellings, a doubled word, "Figure 1 shows", an uncited "is known", an abstract without its significance move), each firing exactly once in every format where its rule applies and nothing else firing: 0 unplanted flags in all three. `demo/tests/test_demo.py` (25 tests, in CI) keeps it that way. **Owner: open the .docx once in Word with the add-in and read the paper** (sub-agent, re-run by the lead). Was: a sample manuscript to demo Researchly in the web app and the Word add-in, as `.docx` and Overleaf `.zip`. Need not be original research: a short paper on a topic of interest (e.g. an SEIR fit to a dengue season), published online under an open licence or made up, with equations, tables and figures and **deliberate errors** the app should flag: an uncited or out-of-order figure, a broken `\ref`, a number in the text that is not in its table, an abbreviation defined twice, a short caption, passive voice in Discussion, overclaiming, a/an and spelling slips. Must stay synthetic or licence-clean (CLAUDE.md: no third-party text in `packages/`, `apps/`, `services/`) **(Claude, with owner review)**
- [x] **Presentation deck for an external audience** — 2026-10-08: a seven-slide, two-minute deck (Slides artifact, private until shared from its Share menu): the opening image and problem, the gap, a card, the demo result, the brief and map, the surfaces, the close. Was: **Presentation deck for an external audience** (owner request, 2026-10-08; later): a well-designed slide deck that introduces Researchly to people outside the project (what problem it solves, what it does and does not do, the four suggestion types, section awareness, the sources, confidentiality, the surfaces, a demo). Built from the selling point (S4) and the demo manuscript once it exists; Slides artifact or `.pptx`. **Claude is to remind the owner of this item** when the demo manuscript is done or when S4 closes, whichever comes first **(Claude, with owner review)**
- [x] **"Brag" launch video** — 2026-10-08: a 50 s cut with music and a 65 s cut with an offline voiceover (Kokoro-82M, Apache-2.0), problem then solution; claims bounded as on the site. **Owner: listen to the voice before sharing** **(Amriit)**. Was: **"Brag" launch video** (owner request, 2026-10-04; later): a short video showing what Researchly does, made once the demo manuscript exists (the `brag` skill) **(Claude)**
- [~] **A shareable public repository** (owner decision 2026-10-08: a separate public repository with a fresh history, generated from this one; this one stays private)
  - [x] Export tool and gate — 2026-10-08 (P39): `tools/public-export/` (allow-list, deny-list, overlay with the public README, CONTRIBUTING, SECURITY and CI); the gate refuses third-party text in any exported file, private names (`private-terms.txt`), secrets (own patterns and gitleaks), non-placeholder emails, PDFs, pickles and stray archives; a `public-export` CI job runs it on every change. The engine's source codes no longer name the lecturer or the course. The export (375 files) passes every suite on its own: core 918, service 183, database 101, demo, eval and bench 56, contract, ruff, web lint, typecheck and 345 unit
  - [x] **Owner: create an empty repository `researchly-public` on GitHub** (Private, no README, no licence) and give the Claude GitHub App access to it; then Claude pushes the single-commit history and checks its CI **(Amriit)** — 2026-10-08: created by the owner; Claude pushed 953a0a1 (one commit, 375 files, exported from 1b7e670 through a clean gate, gitleaks clean) to `amriitmohapatra/researchly-public` `main`
  - [ ] **Owner: review the private `researchly-public`, then switch it to Public** (Settings → General → Danger zone → Change visibility) **(Amriit)**
  - [ ] Decide whether to publish the founding guide (`The-Craft-of-Scientific-Writing.md`); it is cited on every card but kept private for now **(Amriit)**
- [ ] Browser "Private mode" (Pyodide core + ONNX parser) — revisit after S4
- [ ] Harper (WASM grammar) as an alternative to LanguageTool for the private mode
- [ ] W5 knowledge re-mine of `Notes_On_Writing/` → authored questions, rules, Learn cards (paraphrased + cited, never reproduced) — now the primary knowledge source (D7); schedule alongside S4
- [~] Wire `document_type` / `aggressiveness` config into behaviour — `document_type` done in S4a (profiles); `aggressiveness` still stored but unused
- [ ] LaTeX parsing (pylatexenc) costs ~5.7 s per 1M characters vs 0.23 s for the regex masker (~0.3 s per chapter); the LSP re-checks a large `.tex` on every change — measure in VS Code before S3
- [ ] **Known gaps from S2 (2026-10-03), not yet fixed:**
  - [ ] LaTeX footnote text is now checked and is spliced into the sentence it interrupts; watch for false positives (e.g. a lower-case "sentence start" after the footnote) once real chapters are uploaded
  - [ ] Overleaf `.zip`: a child file is joined without TeX's implicit end of line, which only matters when text follows `\input{x}` on the same line and `x` ends in a `%` comment with no final newline
  - [ ] `.docx`: Strict OOXML, and a main part not named `word/document.xml`, are untested; comments, footnotes, headers and text boxes are ignored (by design in S2)
  - [ ] Account deletion: "Delete my data" removes settings and dictionary rows; deleting the sign-in itself needs the owner (Supabase dashboard → Authentication → Users). Add a self-service route before public beta (PDPA/GDPR)
  - [ ] Per-user rate limits (ARCHITECTURE.md §9): the engine still limits per IP only
  - [ ] A token naming an unknown key id makes the engine re-fetch Supabase's public keys; bounded by the per-IP rate limit today, add a re-fetch cooldown with the per-user limits
  - [ ] Verify on the real Supabase project after step 8: run a quick two-user check through the REST API (the CI test uses a Postgres stand-in for Supabase's roles), and confirm `service_role` grants are as expected
  - [ ] Real users need a custom email sender (Supabase's built-in one only reaches the project team, ~2 emails/hour) — S6
  - [ ] Fold the S2 decisions from `docs/s2-design.md` into ARCHITECTURE.md when S2 closes
- [x] Verify the real Supabase project as an outsider — done 2026-10-03 after the owner allow-listed the domain (see the S2 Supabase item). The live engine side is verified (2026-10-03): anonymous upload and >1,500-word paste get `sign_in_required`, a forged token gets `unauthorized`, every tier healthy
- [ ] Large `.tex` (measured locally, synthetic LaTeX, grammar on): 25k words 21 s / 0.6 GB; 65k words 44 s / 1.3 GB; 120k words 74 s / 2.1 GB (×~1.5 on Cloud Run). Fixed: the browser gave up at 120 s while the engine may run 300 s; now 290 s, pinned by a test. Still open: no progress beyond a spinner, and a whole thesis waits ~2 min
- [ ] **From the owner's first real `.tex` upload (P28, 2026-10-03), not yet fixed:**
  - [x] Section inheritance — 2026-10-04: headings carry their level and nested ones inherit (`document.resolve_sections`); 23 tests in `test_section_nesting.py`, 9 of them fail on the old code. A subsection with no section keyword ("Priors", "Solver") resets the section to "other" instead of inheriting its parent's ("Methods"). Headings need a level (LaTeX/Markdown/Word all know it) and resolution should inherit; a keyword in a nested heading ("Model fit" under Results) must not override its parent
  - [ ] Topical top-level sections ("Experiment 1: the baseline SEIR") stay "other", so a methods report gets passive-voice flags meant for Discussion. Wire `document_type` (e.g. "methods report") into section defaults
  - [x] LanguageTool's own misreads on technical prose — 2026-10-04 (P31): counted on the theses and the owner's report (all 11 of its LT001 flags were misreads); rules that misfired repeatedly are skipped (`SKIP_MISREAD_RULES`). One-off misreads ("who meets whom" → "meet", "No fit is…" → "now") stay until they repeat
- [ ] **From the real-document bench (P29), not yet fixed:**
  - [ ] No language detection: a Portuguese document gets hundreds of spelling flags. Detect the language and say "Researchly checks English" instead of checking
  - [ ] A 1.8 MB LaTeX book chapter exceeds the 1M-character cap; consider per-chapter checking of large projects
  - [ ] One project (custom `\Set` macro in maths) still needs the regex reader; the parser's `$` tracking is thrown off. Collect more cases before special-casing
  - [~] JATS format parity on 11 eLife articles: G104 fires ~2× more and C303 ~3.5× less in docx/tex than plain — the nested-heading section bug, fixed 2026-10-04; re-measure in the next CI run
  - [x] C302 — 2026-10-04 (P31): "prove" is left alone in a sentence with maths or proof vocabulary; bench C302 28 → 6. Was: C302 flags "we prove" in mathematics and computer-science papers (bbchallenge: 12 more once its Introduction's `\paragraph` subsections stopped resetting the section). In a proof, "prove" is the right word: skip it near maths, theorems or proof assistants (Q3 work)
  - [ ] S001 counts Word table cells towards its "used 3+ times = vocabulary" exemption (benign; noted so it is not chased)
- [ ] Muting a rule while viewing an uploaded file re-sends the whole file to re-check; filtering the shown results in the browser would be instant (web, S2 follow-up)
- [ ] Upload is hidden when accounts are not configured, so local development without Supabase has no upload; consider a dev-only switch
- [ ] Q2: run spaCy and LanguageTool in parallel inside `api.analyze()` (chapter 6.9 s engine time on Cloud Run vs 6 s target); deferred by the owner 2026-10-03
- [ ] Lower or split very large documents server-side: a 1M-character request takes ~74 s and 2.8 GiB (backend measurement, S1)
- [~] Reach Q3: bring the noise floor to ≤ 11/1000w. 2026-10-04 (P31): 14.51 → **11.94** (LT001 566→295, G101 779→559, S001 611→415, C303 138→114, F601 243→220; reference lists masked), 37 fire/don't-fire tests; real-document bench 17.02 → 14.99. Remaining:
  - [ ] ~90% of the remaining S001 flags are PDF-extraction artefacts: `pdftotext` drops every line-break hyphen ("laboratoryconfirmed") and page-break hyphenation leaves fragments ("coun", "tion"). A trial re-extraction (`-raw`, keep a hyphen unless the joined word is a word) gives 11.3 with this code (13.7 with the old), S001 415 → 313, but also 16k more words (300,955 vs 284,537) whose origin must be read before the gate's corpus changes; re-baseline both sides when it does
  - [ ] Pasted code and maths in plain text and Word (R listings, `log=T`): detect code-like paragraphs and mask them like LaTeX code
  - [ ] G106 (648) and G101 (559) are now mostly real advice on long sentences; reaching 11 must not come from hiding it
  - [x] 2026-10-04 (P33, from the owner's PDF-converted manuscript): **12.65 → 11.67**, all removals of wrong flags. A blank line ends a sentence unless the next line continues in lower case (G106 648 → 529, G101 559 → 482: "sentences" run across headings, table cells, lists and equations; every flag diffed before/after); aligned-column and flattened-equation lines masked; G107 says a repeated stack once; title capitals, URLs, the noun "leverage" left alone. Bench 14.65 → 13.69
- [ ] Clean the 20 cosmetic ruff findings (17 unused imports, 3 placeholder-less f-strings) in a dedicated change, then widen `ruff.toml`
- [ ] `language_tool_python` client is GPL-3.0-only: fine server-side; check before bundling it into any distributed desktop installer
- [ ] Correct `docs/eval-corpora.md`: JFLEG and CWEB *do* declare CC BY-NC-SA 4.0 (registry audit, 2026-10-03)
- [ ] PubMed-RCT declares no licence — decide before training anything shippable on it (S5)
- [ ] `_to_delete/` holds tarballs that include thesis text; owner to confirm deletion **(Amriit)**
- [ ] Pallas citation year: the book says © 2023; the repo says 2022 throughout — fix in one pass (code + docs)
- [ ] Four course PDFs are scans with no text layer (`…ng5001_getting_started_on_critical_reading.pdf`, `Week 2 Reading.pdf`, `Writing conference abstract.pdf` and its `_compressed` copy), so the third-party scan can't see them; OCR them (or confirm nothing derives from them)
- [ ] `docs/rule-inventory.md` may still quote old why-texts / Pallas frames — re-sync with the paraphrased versions

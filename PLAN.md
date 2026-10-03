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

**Current slice: S2 — Accounts, files, settings sync** (design: `docs/s2-design.md`). S1 is live at researchly-chi.vercel.app; on 2026-10-03 the owner chose to defer the Q2 speed-up and move on, with S1's real-chapter exit check still to do.

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
- [~] **Exit check:** CI green on PR #1 ✅; `check_third_party.py` exits 0 ✅; owner merges PR #1 **(Amriit)**

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

- [ ] Supabase project (region D3) **(Amriit: create project; docs/deploy.md step 8)**
- [x] Schema: `user_settings`, `dictionary_words`, RLS per command, `my_config()` (s2-design §2) — afc3041. `profiles`, `usage_events`, `feedback_events` are **not** created until a feature reads them (collect only what's needed)
- [x] Engine verifies JWT; `user_id` from token only; remote config layer in `config.py` — 2026-10-03, 8e82b7a: JWKS verification with the algorithm pinned to the key, settings read via PostgREST with the caller's own token (no secret key in the engine; it refuses to start with one); 32 token/settings tests, 2 new canary scenarios
- [x] `/v1/analyze-file` (raw bytes, filename never logged, 25 MiB cap, sign-in required when accounts are on) — 8e82b7a, 16 tests
- [~] Two-user test (read/update/delete) automated in CI (Q7) — afc3041 + f5ac4b8: 85 tests on Postgres 16 with a Supabase shim, and all 19 deliberate weakenings of the migration caught (re-run independently by the lead). CI job `supabase-rls` added; tick when it has run green on GitHub
- [x] LaTeX adapter on pylatexenc; multi-file `.zip` (`\input`/`\include`/`\subfile`) — 8dd7b00, 6488b8a: 106 + 38 tests; parse failure falls back to the regex masker with a visible warning; hostile zips (bomb, traversal, symlink, encrypted, fan-out) refused
- [x] `.docx` OOXML adapter (styles incl. localised ids, headings, tables, tracked changes read as accepted; defusedxml; zip-bomb guard). Comments and footnotes ignored in S2 — 6488b8a: 37 tests incl. XXE and billion laughs; identical to the Word add-in path
- [x] Offset round-trip property test for every adapter — seeded random round trips: 40 LaTeX, 15 zip, 20 docx
- [~] Cross-surface parity test (mute in one surface → muted everywhere) — the engine applies account mutes for any caller with a token (test_accounts.py); the Word add-in joins in S3, when it moves to the hosted engine
- [x] Sign-in, upload, settings + dictionary UI in web app — 1bb2804…b193bf6, 4b56345: magic-link sign-in (PKCE in the browser), bearer on engine calls with one refresh-and-retry, upload by button or drop with a read-only file view and per-file locations, `/settings`, Mute / Add-to-dictionary on cards, atomic mute RPCs. With the Supabase variables unset the site is exactly S1 (own e2e project). 152 unit + 59 e2e (two builds), axe clean light and dark, anti-ui-slop gate passed
- [x] Adapters keep figures, tables, equations and captions as *structure* (not just masked text) — needed by S2b — `Document.structure`, returned as `document.structure`
- [x] Web layout responsive from the start (P5): checker, file view, settings, menus and dialogs at 375 and 1280 px with a no-horizontal-scroll check on every e2e run (Learn views arrive in S4)
- [ ] **Exit check:** owner uploads a real `.tex` and `.docx` thesis chapter; offsets correct; settings sync across two browsers

## S2b — Consistency & structure checks (P2, P4)

- [ ] Abbreviations: defined at first use, defined once, used after definition
- [ ] Terminology consistency (same concept → same term; e.g. "infection rate" vs "incidence" drift)
- [ ] Tense consistency per section (Methods past, etc. — section-aware)
- [ ] Numbers and units formatting consistency
- [ ] Figures/tables: every one cited in text, cited in order, cited before it appears; labels exist
- [ ] Caption quality: present, self-contained, defines abbreviations, states what/where/when/n
- [ ] Equations: symbols defined near first use; numbered equations referenced
- [ ] Text↔table numbers: a number quoted with "Table N" appears in Table N
- [ ] Each check: authored question + named source, fire and don't-fire tests, rule-inventory row
- [ ] **Exit check:** noise-floor gate holds; owner checks one real chapter and reports false flags

## S3 — Word add-in, hosted

- [ ] Taskpane served over HTTPS from Vercel; calls hosted engine
- [ ] Sign-in via Office dialog + Supabase (Microsoft provider)
- [ ] Unified JSON manifest (+ XML for Mac via `alternateIcons`)
- [ ] Optional local-engine mode retained (localhost)
- [ ] Draft / Revise mode (P1) in `config.py`, so it is shared by every surface; Draft shows sentence-level checks only
- [ ] **Exit check:** owner uses it on Mac Word for a week; issues logged below

## S4 — Narrative map v1

- [ ] Port `argument.py`, `guide.py`, `abstract_lens` into `tiers/discourse/`
- [ ] Each discourse check = authored question + named source in `knowledge/`
- [ ] `/v1/narrative` endpoint; narrative map UI (moves present/missing/out of order)
- [ ] Learn cards for every `learn_ref`
- [ ] Hedging trajectory read-out (never a score)
- [ ] Discipline-pack format + the epidemiology pack (P3): reporting checklists STROBE, CONSORT, PRISMA, EPIFORGE — checks *reporting*, never the science
- [ ] Personal progress view: per-rule trends across a user's documents (from `usage_events` counts — no text)
- [ ] Labelling guide + small annotation tool **(Claude)**; owner labels 50 paragraphs **(Amriit)**
- [ ] **Exit check:** flag precision on the 50 labelled paragraphs reported here

## S5 — Critic bake-off (Laya vs ModernBERT)

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
- [ ] Task A — flag re-ranker (accept/dismiss data): Laya vs ModernBERT-large
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

- [ ] Browser "Private mode" (Pyodide core + ONNX parser) — revisit after S4
- [ ] Harper (WASM grammar) as an alternative to LanguageTool for the private mode
- [ ] W5 knowledge re-mine of `Notes_On_Writing/` → authored questions, rules, Learn cards (paraphrased + cited, never reproduced) — now the primary knowledge source (D7); schedule alongside S4
- [ ] Wire `document_type` / `aggressiveness` config into behaviour (stored but unused today)
- [ ] LaTeX parsing (pylatexenc) costs ~5.7 s per 1M characters vs 0.23 s for the regex masker (~0.3 s per chapter); the LSP re-checks a large `.tex` on every change — measure in VS Code before S3
- [ ] Muting a rule while viewing an uploaded file re-sends the whole file to re-check; filtering the shown results in the browser would be instant (web, S2 follow-up)
- [ ] Upload is hidden when accounts are not configured, so local development without Supabase has no upload; consider a dev-only switch
- [ ] Q2: run spaCy and LanguageTool in parallel inside `api.analyze()` (chapter 6.9 s engine time on Cloud Run vs 6 s target); deferred by the owner 2026-10-03
- [ ] Lower or split very large documents server-side: a 1M-character request takes ~74 s and 2.8 GiB (backend measurement, S1)
- [ ] Reach Q3: bring the noise floor from 14.75 to ≤ 11/1000w (top contributors: G101 779, S001 676, G106 648, LT001 566 flags)
- [ ] Clean the 20 cosmetic ruff findings (17 unused imports, 3 placeholder-less f-strings) in a dedicated change, then widen `ruff.toml`
- [ ] `language_tool_python` client is GPL-3.0-only: fine server-side; check before bundling it into any distributed desktop installer
- [ ] Correct `docs/eval-corpora.md`: JFLEG and CWEB *do* declare CC BY-NC-SA 4.0 (registry audit, 2026-10-03)
- [ ] PubMed-RCT declares no licence — decide before training anything shippable on it (S5)
- [ ] `_to_delete/` holds tarballs that include thesis text; owner to confirm deletion **(Amriit)**
- [ ] Pallas citation year: the book says © 2023; the repo says 2022 throughout — fix in one pass (code + docs)
- [ ] `ng5001_getting_started_on_critical_reading.pdf` and `Writing conference abstract_compressed.pdf` are scans with no text layer, so the third-party scan can't see them; OCR them (or confirm nothing derives from them)
- [ ] `docs/rule-inventory.md` may still quote old why-texts / Pallas frames — re-sync with the paraphrased versions

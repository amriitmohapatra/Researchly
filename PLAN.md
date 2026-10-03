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

**Current slice: S0 — Foundation** (started 2026-10-03, in PR amriitmohapatra/Researchly#1).

---

## Product direction questions (asked 2026-10-03) — awaiting answers

- [ ] **P1** Researchly is a coach alongside existing tools (web "revision studio" + Word/Overleaf add-ins), not a place to write? **(Amriit)**
- [ ] **P2** Add consistency checks (abbreviations, terminology, tense, numbers/units, figure/table citation) and reporting-guideline checklists (CONSORT/STROBE/PRISMA/EPIFORGE) to v1? **(Amriit)**
- [ ] **P3** First discipline pack: epidemiology / infectious-disease modelling, then biomedical? **(Amriit)**
- [ ] **P4** Figures/tables/equations: structural checks now (cross-refs, captions, symbol definitions, text↔table numbers); image understanding out of scope under rule #1? **(Amriit)**
- [ ] **P5** Platforms: responsive web (installable PWA) + desktop add-ins; phones for reading reports; no native apps in v1? **(Amriit)**

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

- [ ] FastAPI `services/engine` wrapping `api.analyze()`; `/v1/analyze`, `/v1/health`, `/v1/rules`
- [ ] OpenAPI → `packages/contract` generated TS types; drift check in CI
- [ ] Dockerfile (engine) + LanguageTool sidecar; image excludes thesis/course data (CI grep for canaries)
- [ ] Cloud Run staging deploy in region D3 **(Amriit: create GCP project + billing)**
- [ ] Minimal Next.js page on Vercel: paste → highlights + suggestion list **(Amriit: Vercel account/team)**
- [ ] Logging config: request bodies never logged; Sentry payload scrubbing
- [ ] Q6 canary test: no document text in logs/DB/errors after an analysis
- [ ] Measure Q1/Q2 latency on staging; record numbers here
- [ ] **Exit check:** owner pastes a real chapter on staging and gets the same suggestions as the CLI

## S2 — Accounts, files, settings sync

- [ ] Supabase project (region D3): auth, `profiles`, `settings`, `dictionary_words`, `usage_events`, `feedback_events`, RLS on all **(Amriit: create project)**
- [ ] Engine verifies JWT; `user_id` from token only; remote config layer in `config.py`
- [ ] Two-user test (read/update/delete) automated in CI (Q7)
- [ ] LaTeX adapter on pylatexenc; multi-file `.zip` (`\input`/`\include`)
- [ ] `.docx` OOXML adapter (styles, headings, comments; defusedxml; zip-bomb guard)
- [ ] Offset round-trip property test for every adapter
- [ ] Cross-surface parity test (mute in one surface → muted everywhere)
- [ ] Settings + dictionary UI in web app
- [ ] **Exit check:** owner uploads a real `.tex` and `.docx` thesis chapter; offsets correct; settings sync across two browsers

## S3 — Word add-in, hosted

- [ ] Taskpane served over HTTPS from Vercel; calls hosted engine
- [ ] Sign-in via Office dialog + Supabase (Microsoft provider)
- [ ] Unified JSON manifest (+ XML for Mac via `alternateIcons`)
- [ ] Optional local-engine mode retained (localhost)
- [ ] **Exit check:** owner uses it on Mac Word for a week; issues logged below

## S4 — Narrative map v1

- [ ] Port `argument.py`, `guide.py`, `abstract_lens` into `tiers/discourse/`
- [ ] Each discourse check = authored question + named source in `knowledge/`
- [ ] `/v1/narrative` endpoint; narrative map UI (moves present/missing/out of order)
- [ ] Learn cards for every `learn_ref`
- [ ] Hedging trajectory read-out (never a score)
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
- [ ] Reach Q3: bring the noise floor from 14.84 to ≤ 11/1000w (top contributors: G101 779, S001 676, G106 648, LT001 592 flags)
- [ ] Clean the 20 cosmetic ruff findings (17 unused imports, 3 placeholder-less f-strings) in a dedicated change, then widen `ruff.toml`
- [ ] `language_tool_python` client is GPL-3.0-only: fine server-side; check before bundling it into any distributed desktop installer
- [ ] Correct `docs/eval-corpora.md`: JFLEG and CWEB *do* declare CC BY-NC-SA 4.0 (registry audit, 2026-10-03)
- [ ] PubMed-RCT declares no licence — decide before training anything shippable on it (S5)
- [ ] `_to_delete/` holds tarballs that include thesis text; owner to confirm deletion **(Amriit)**
- [ ] Pallas citation year: the book says © 2023; the repo says 2022 throughout — fix in one pass (code + docs)
- [ ] `ng5001_getting_started_on_critical_reading.pdf` and `Writing conference abstract_compressed.pdf` are scans with no text layer, so the third-party scan can't see them; OCR them (or confirm nothing derives from them)
- [ ] `docs/rule-inventory.md` may still quote old why-texts / Pallas frames — re-sync with the paraphrased versions

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

**Current slice: S0 — Foundation** (blocked on owner decisions D1–D8 below)

---

## Owner decisions (block S0) — see ARCHITECTURE.md §13

- [ ] **D1** Approve/edit the new non-negotiable #2 wording ("Confidential by design", ADR-02) **(Amriit)**
- [ ] **D2** Free or paid — now or later? **(Amriit)**
- [ ] **D3** Hosting region — Singapore recommended **(Amriit)**
- [ ] **D4** Baseline tree — `Researchly_Updated_14082026` recommended **(Amriit)**
- [ ] **D5** macOS app & Windows scaffold → maintenance-only? **(Amriit)**
- [ ] **D6** Sample theses: private evaluation only; strip thesis exemplars from shipped data? **(Amriit)**
- [ ] **D7** What training data / annotation time can you provide? **(Amriit)**
- [ ] **D8** Laya: adopt only via the S5 bake-off? **(Amriit)**

---

## S-1 — Architecture (this session)

- [x] Read *The Art of Building Software* ch. 20–27 and adopt its method — 2026-10-03
- [x] Codebase audit, Laya identification, hosting research (3 sub-agents) — 2026-10-03
- [x] Write `ARCHITECTURE.md` draft v1 — 2026-10-03
- [x] Create `PLAN.md` — 2026-10-03
- [ ] Owner reviews ARCHITECTURE.md and answers D1–D8 **(Amriit)**
- [ ] Revise ARCHITECTURE.md to v1.1 with the answers; amend CLAUDE.md non-negotiable #2

## S0 — Foundation (one repo, green CI; no user-visible change)

- [ ] Create monorepo skeleton: `apps/ services/ packages/ ml/ docs/adr/ legacy/` — *done when* layout exists and README explains it
- [ ] `git mv` baseline tree (D4) into `packages/core` + `apps/word-addin`; others into `legacy/` — *done when* history preserved (`git log --follow`)
- [ ] Merge P19–P21 entries into root `docs/PROJECT_LOG.md`
- [ ] Fix the Linux-only test failure (`test_jdk_found_with_a_finder_launch_environment`)
- [ ] GitHub Actions: ruff + pytest + noise-floor gate + secret scan — *done when* all baseline tests green in CI on a PR
- [ ] `ml/datasets.yaml` registry: every corpus with source, licence, permitted use, hash
- [ ] Remove thesis-derived exemplars from shippable data (per D6); re-source from CC-BY PMC-OA with per-sentence licence
- [ ] Replace `move_clf.joblib` loading with a non-pickle format (or quarantine it to `ml/` until S5)
- [ ] Add S001 lexicon gaps: `estimand(s)`, `urbanicity`, `prespecified`, `lockdowns`, `serotypic`, `tradeoff`, `exergy`
- [ ] Update CLAUDE.md repo map + test counts to the new layout
- [ ] **Exit check:** CI green on `main`; no third-party text in `packages/` or `services/`

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
- [ ] W5 knowledge re-mine of `Notes_On_Writing/` → new authored questions
- [ ] Wire `document_type` / `aggressiveness` config into behaviour (stored but unused today)

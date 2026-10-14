# Researchly: progress summary (as of 2026-10-14)

A short status report on everything done so far, drawn from
`docs/PROJECT_LOG.md` (P1–P39) and `PLAN.md`. Those two files are still the
full record. This one is a summary. It was written on the branch
`claude/vigilant-hawking-hnexgd`, and `main` is unchanged.

- **Snapshot:** `main` at `87fbec6` (merge of amriitmohapatra/Researchly#12, 2026-10-08).
  There are no commits after 2026-10-08.
- **Current slice:** S4, the narrative map. Engineering is complete. The
  owner's steps and the exit check are still open.
- **Live:** engine on Cloud Run (Singapore) with a LanguageTool sidecar; web
  app and Word taskpane on Vercel (`researchly-chi.vercel.app`); accounts on
  Supabase; a public mirror at `amriitmohapatra/researchly-public`.

---

## 1. Timeline at a glance

| Date | Phase | What happened |
|---|---|---|
| 2026-08-10 | P1–P13, prototype | Research, rule mining, v0.1–v0.7 engine, CLI, Word add-in, LSP/VS Code, Polish rewriter, knowledge mining, macOS menu-bar app (.dmg), spelling (SymSpell) and grammar (LanguageTool) tiers, abstract lens, review lens, Windows scaffold |
| 2026-08-10/11 | P14–P18 | Tester packages, Codex review, shared surface layer (`api.analyze`), reliability fixes, JDK discovery so the grammar tier really runs, packaging fixes |
| 2026-08-14 | P19–P21 | W2 sprint (actionable surfaces, GEC scaffold, ArgumentObject), standalone installers, drafting-guide experiment fork |
| 2026-10-03 | P22 | Production plan: `ARCHITECTURE.md` + `PLAN.md`; owner decisions D1–D8 and P1–P5 |
| 2026-10-03 | P23, **S0** | One monorepo, CI (ruff, tests, noise gate, third-party scan, gitleaks), dataset licence registry, third-party text removed from the engine — PR #1 |
| 2026-10-03 | P24–P25, **S1** | FastAPI engine service, API contract, privacy canary test, Next.js web app; deployed and measured |
| 2026-10-03 | P26–P27, **S2** | Accounts (Supabase, RLS), file uploads (.tex, Overleaf .zip, .docx), settings sync — PR #2 |
| 2026-10-03/04 | P28–P31 | Fixes from the owner's real `.tex`; real-document test bench (208 openly licensed docs); nested headings; noise floor 14.51 → 11.94 — PRs #3, #4 |
| 2026-10-04 | P32–P33, **S2b** | 12 structure and consistency rules; PDF-converted manuscript fixes; noise floor 11.67 — PR #5 |
| 2026-10-04/05 | P34, **S3** | Word add-in hosted on Vercel, calling the hosted engine; Draft / Revise mode; sign-in by emailed code — PRs #6, #7, #8 |
| 2026-10-08 | P35 | Owner's first real use: a plain-language explanation for every rule; Latin-phrase and hedge fixes; new rule X302 — PR #9 |
| 2026-10-08 | P36, **S4a** | Article-type profiles, the reviewer's brief on every surface, printable report, "Why Researchly" selling point — PR #10 |
| 2026-10-08 | Codex review | `Codex_Review_8Oct2026.md`: 8 findings and 12 feature proposals — PR #11 |
| 2026-10-08 | P37, **S4b** | Discourse package and narrative map; demo manuscript (17 planted errors) |
| 2026-10-08 | P38, **S4c** | Learn cards, epidemiology reporting checklists, opt-in progress, labelling tool; Codex findings R1–R8 fixed |
| 2026-10-08 | P39 | Public-export tool and gate; `researchly-public` created and pushed, with the launch video — PR #12 |

---

## 2. What was built, by area

### Engine (`packages/core/researchly`)
- One entry point, `api.analyze()`, used by every surface. It parses once and
  returns suggestions, counts, metrics, sections, health, and, on request,
  the brief and the narrative map.
- Tiers: lexical, syntax, spelling (S001), grammar (LT001, local
  LanguageTool), structure and consistency (S2b), discourse (S4), and a GEC
  scaffold that is off and abstains.
- Four suggestion types (Correction, Improvement, Convention, Preference),
  section-aware (passive voice is never flagged in Methods). Every rule has a
  `plain=` explanation, a named source and a Learn card.
- **Profiles:** nine article types; "auto" guesses only from strong signals.
- **Reviewer's brief:** Wallace & Wray's five questions, built from the same
  analysis, with statuses (detected / not detected / not assessed / not
  applicable).
- **Narrative map:** 16 authored moves over six section kinds, the
  argument's missing links and a hedging trajectory. None of it is a score.
- **Epidemiology pack:** STROBE, CONSORT, PRISMA and EPIFORGE as paraphrased
  checklists. An item reads "reported" or "needs your check", never
  "missing".
- **Learn cards:** 26 lessons in six groups, shipped as
  `packages/contract/learn.json`.

### Service, contract and data
- `services/engine` (FastAPI):
  - routes: `/v1/analyze`, `/v1/analyze-file`, `/v1/analyze-word`,
    `/v1/rules`, `/v1/learn`, `/v1/health`;
  - JWT verification against Supabase's keys;
  - a release-blocking privacy canary test.
- The contract is written as Pydantic models, exported to OpenAPI, and the
  TypeScript types are generated from that. CI fails on drift.
- Supabase migrations: S2 settings and dictionary, S3 mode, S4 document
  type, S4c opt-in progress (rule-id counts only). They come with a two-user
  RLS suite: 101 tests on Postgres 16.

### Surfaces
- **Web app** (`apps/web`, Next.js 16):
  - paste or upload;
  - cards that lead with the plain explanation;
  - Mute and Add to dictionary;
  - dismiss with Undo;
  - tabs for the reviewer's brief, the narrative map and the checklist;
  - the printable report;
  - "Try the demo paper";
  - pages for `/learn`, `/progress` and `/label`.
- **Word add-in (hosted):**
  - served from Vercel, calling the hosted engine;
  - sign-in by emailed code;
  - Apply as a tracked change, which fails closed (four honest outcomes);
  - "Check this section";
  - the same tabs as the web app.
- **CLI and LSP:** the CLI's `check`, `polish`, `review` and `abstract`
  commands come from the prototype; `narrative` was added in S4. The LSP now
  uses UTF-16 ranges and drops stale results.
- **macOS app and Windows scaffold:** maintenance-only (decision D5).

### Quality and measurement
- **Noise floor**, flags per 1000 words on 8 accepted theses:
  14.84 → 14.51 → 11.94 → 12.65 (new rules, on purpose) → **11.67**.
  The target is ≤ 11 (Q3).
- **Real-document bench:** 208 openly licensed documents, each in three
  renderings, with invariants checked in CI. Latest result: PASS, 13.69
  flags per 1000 words.
- **Test counts at P38/P39:**
  - core: 918 passed, 2 skipped;
  - service: 183;
  - database: 101;
  - demo, eval and bench: 56;
  - web: 345 unit and 152 e2e.
- **Latency on Cloud Run:**
  - a 311-word paragraph takes 484 ms server p50, which meets Q1;
  - a 10k-word chapter takes 6.89 s, which misses Q2. The owner deferred
    that speed-up.

### Governance
- `ml/datasets.yaml` is the licence registry. `check_third_party.py` keeps
  third-party text out of `packages/`, `apps/` and `services/`.
- **Public sharing** goes through `tools/public-export/`: an allow-list
  export plus a gate that blocks third-party text, private names, secrets,
  emails and certain file types. The result is the separate fresh-history
  repository `researchly-public`, and this one stays private.

---

## 3. Most recent changes (2026-10-08, PRs #9–#12)

1. **P35:**
   - a `plain=` explanation on every rule;
   - internal references (section numbers, course codes, CLI commands) are
     banned from user-visible text by test;
   - sources for the lecture and the course are shown as "Amriit's
     learnings";
   - new rule **X302** (an equation must be part of a sentence), for LaTeX
     and Word.
2. **P36:**
   - article-type profiles;
   - the "Check as" selector;
   - the reviewer's brief on the web and in Word;
   - the printable report, kept in the browser (nothing generated
     server-side);
   - the selling point on the landing page and in the README.
3. **Codex review:** 8 prioritised findings and 12 feature proposals.
4. **P37:**
   - the `discourse/` package and the narrative map on every surface;
   - the demo manuscript as `.docx`, an Overleaf `.zip` and Markdown. Its
     17 planted errors each fire exactly once, and nothing unplanted fires.
5. **P38:**
   - Learn cards;
   - the epidemiology checklists;
   - opt-in progress tracking;
   - the `/label` tool and `label_precision.py`;
   - Codex findings R1–R8 fixed;
   - proposals #2, #6 and #9 built;
   - a 7-slide deck and the launch video, kept outside the repo.
6. **P39:**
   - the public-export tool and its gate;
   - neutral source codes (`lecture`, `course-U1`, `course-U2`);
   - `researchly-public` pushed with all eight CI jobs green;
   - the voiced launch video (65 s, Kokoro-82M) in `media/`.

---

## 4. Open items

### Owner actions (Amriit)
- [ ] Run the S4c migration `supabase/migrations/20261008140000_s4_progress.sql`,
      then deploy the engine and the web app.
- [ ] **S4 exit check:** label 50 paragraphs at `/label`, then run
      `ml/eval/label_precision.py`.
- [ ] Checks in real Word:
  - X302 on an equation;
  - "Check this section";
  - one Apply (R3);
  - the brief, the map and the checklist.
- [ ] Open the narrative map with the demo paper, on the site and in Word.
- [ ] S1 exit check: paste a real chapter on the live site.
- [ ] S2 exit check: real `.tex` and `.docx` uploads; settings sync across
      two browsers.
- [ ] S3 exit check: a week of real use in Mac Word.
- [ ] Review `researchly-public` and switch it to Public. Decide whether to
      publish the founding guide.
- [ ] Confirm deleting `_to_delete/`.

### Engineering backlog (highlights)
- **Q3:** the noise floor is 11.67 against a target of ≤ 11. About 90% of
  the remaining S001 flags are PDF-extraction artefacts in the corpus.
- **Codex proposals not built yet:**
  - #1 revision queue;
  - #3 evidence-linked brief;
  - #4 genre-native profiles;
  - #5 coverage summary;
  - #7 X401 row/column matching;
  - #8 long-document UX;
  - #10 spelling repetition;
  - #11 local-mode parity;
  - #12 account controls and per-user rate limits (before beta).
- **S5:**
  - an open-access training corpus;
  - a critic bake-off (Laya vs ModernBERT; Jev only if it can run locally);
  - ONNX export and a promotion gate.
- **S6:**
  - an Overleaf extension;
  - a PWA;
  - a comparison study;
  - a privacy policy and DPAs;
  - a public beta.
- **Smaller items:**
  - language detection;
  - Q2 latency (deferred);
  - 20 cosmetic ruff findings;
  - the Pallas citation year;
  - re-syncing `rule-inventory.md`.

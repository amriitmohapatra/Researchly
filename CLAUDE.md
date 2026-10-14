# CLAUDE.md — Researchly

Guidance for any AI assistant working in this repository. Read this fully
before proposing or making changes. The complete build history lives in
`docs/PROJECT_LOG.md` — read it before asking the user anything.

## What this project is

**Researchly** is a research-focused writing assistant ("Grammarly for
scientific writing") built by and for Amriit — a PhD student in infectious
disease modelling (R/Stan/Python; writes in Word, Overleaf/LaTeX,
Quarto/VS Code). One engine, five surfaces: CLI, MS Word add-in, LSP
(VS Code/Positron), macOS menu-bar app (built to .dmg), Windows scaffold
(untested).

## Production build (from 2026-10-03)

Researchly is moving from prototype to a hosted product. Read
**`ARCHITECTURE.md`** (components, decisions, evidence) and **`PLAN.md`**
(the shared checklist — tick a box only when its evidence exists) before
starting any production work. Slice S0 (2026-10-03) consolidated the three
prototype trees into the monorepo layout below.

## Non-negotiable decisions (user-made; do not revisit without asking)

1. **No cloud LLMs, no generative drafting — local non-generative ML is
   permitted.** *(Amended 2026-08-11. The original rule read "NO LLMs
   anywhere"; the user drew the precise line after the Codex review showed
   the phrase was ambiguous and was blocking the grammar tier.)*
   - **Forbidden**: any cloud/API model; anything that generates free-form
     prose; silent rewriting; drafting sentences for the author.
   - **Permitted**: on-device, non-generative models — sequence taggers,
     classifiers, GECToR-style *token-level edit* tagging. These propose
     minimal edits against the source, carry confidence scores, are gated
     off inside masked spans, and are never auto-applied.
   - Rewriting stays deterministic and rule-composed (`transform.py`);
     grammar is delegated to open-source engines (SymSpell, local
     LanguageTool). The learned tier is labelled `tier="gec"` so its
     provenance is never passed off as a hand-written rule.
   - Rationale: Grammarly's pre-ChatGPT quality came from learned GEC, not
     regex. The compliance promise is *local-first*, which a bundled
     on-device tagger does not violate.
   - **Word prediction is permitted** *(amended 2026-10-14, owner: "I want
     to have it as a core feature of the app")*, within these limits, which
     `researchly/predict.py` and its tests hold:
     - it offers the end of the word being typed, or the next word, or a
       fixed term of at most three words ("confidence interval"), and never
       a clause or a sentence;
     - it is never inserted by itself: the writer accepts it with Tab or a
       click;
     - it comes from counts of word sequences (n-grams), not a neural
       language model, and it runs locally or in the pinned engine, never
       through a cloud model;
     - it is trained only on licence-clean text (CC BY / CC0 articles, each
       licence read from the article and attributed in
       `data/predict_sources.tsv`), never on theses or the owner's
       documents. A sequence is kept only if it occurs in at least three
       articles, so no one author's sentence can be reproduced;
     - it offers nothing inside masked spans (maths, code, citations,
       URLs, headings), and the writer can turn it off
       (`[features] prediction`).
2. **Confidential by design.** Document text is processed in memory in a
   pinned region and is never stored, logged, shared, or used for training
   unless the user explicitly opts in, per feature. No cloud LLM ever sees
   it. A local mode that sends nothing anywhere remains available.
   *(Amended 2026-10-03. The original rule read "Local-first, always. No
   document text ever leaves the machine." The user lifted local-only so
   Researchly can be hosted, and approved this wording — ADR-02 in
   `ARCHITECTURE.md`.)* Still a compliance matter (publisher AI policies),
   not a preference: anything that would persist, log or train on text needs
   an explicit per-feature opt-in, and the canary test (ARCHITECTURE.md Q6)
   must stay green.
3. **The four-type suggestion taxonomy** — Correction / Improvement /
   Convention / Preference — is the product's core idea. Conventions are
   never presented as errors; Preferences are hidden by default.
4. **Section-aware**: the same sentence gets different advice in Methods
   vs Discussion (e.g., passive voice is NEVER flagged in Methods).
5. **Precision over recall.** False-positive fatigue kills checkers
   (measured in `docs/dogfooding-report.md`). New rules need fire AND
   don't-fire tests, and ideally a corpus volume check.
6. **Every suggestion is explainable** — one-line message + a "why"
   traceable to a named source (the writing guide, Endo's lecture, the
   NG5001 course, a paper). Provenance map: `docs/knowledge-base.md`.
   Since P35 every rule also carries a `plain=` explanation in everyday
   words, shown first; no user-visible text may name the guide's section
   numbers, the course, the lecturer or a CLI command (the lecture and the
   course appear to users as "Amriit's learnings"; `test_explanations.py`
   enforces this).

## Repository map

```
Researchly/
├── CLAUDE.md, AGENTS.md          ← you are here
├── ARCHITECTURE.md, PLAN.md      ← production design + the shared checklist
├── The-Craft-of-Scientific-Writing.md   ← the founding writing guide (owner's)
├── Notes_On_Writing/             ← course PDFs: the knowledge source (D7) — third-party, private
├── Sample_thesis_drafts/         ← 8 accepted theses (noise-floor corpus) — third-party, private
├── research/                     ← Phase-1 landscape research (00-synthesis.md first)
├── docs/
│   ├── PROJECT_LOG.md            ← THE chronicle: read to understand everything
│   ├── rule-inventory.md         ← all rules, all layers, sources, status
│   ├── knowledge-base.md         ← source-document → rule provenance map
│   ├── dogfooding-report.md      ← how precision tuning was done (methodology)
│   ├── adr/                      ← decision records (index; ADRs live in ARCHITECTURE.md §10)
│   └── roadmap-rewrite-and-desktop.md   ← superseded by ARCHITECTURE.md
├── packages/core/                ← THE ENGINE (`researchly` package; every surface uses it)
│   ├── researchly/
│   │   ├── api.py                ← analyze(): THE entry point every surface calls
│   │   ├── config.py             ← layered settings, shared by every surface
│   │   ├── health.py             ← per-tier status; no tier may fail silently
│   │   ├── document.py           ← offset-preserving markup masking + IMRaD sections
│   │   ├── engine.py             ← Rule/Suggestion types, registry, check(), aggregation
│   │   ├── rules_*.py            ← rule modules (lexical, syntax, spelling, grammar, gec)
│   │   ├── gec.py                ← learned-edit tier scaffold (no model yet; abstains)
│   │   ├── discourse/            ← S4: moves.py (authored questions per section),
│   │   │                            narrative.py (the map), argument.py (Toulmin),
│   │   │                            abstract_lens.py (AB802); old paths re-export
│   │   ├── review.py             ← Wallace & Wray critical-reader report
│   │   ├── transform.py          ← deterministic Polish rewriter
│   │   ├── spelling.py           ← SymSpell wrapper + guards + user dictionary + VarCon dialects
│   │   ├── spellrank.py          ← noisy-channel ranking of spelling suggestions (P40)
│   │   ├── predict.py            ← word prediction (n-grams; data/predict.sqlite; P42)
│   │   ├── reading.py            ← pasted code, inline maths, other languages → masked (P42)
│   │   ├── tables.py             ← tables as rows × columns for X401 (P42)
│   │   ├── lexicons.py           ← ALL word lists (auditable; extend here)
│   │   ├── metrics.py            ← read-outs incl. hedge/booster meter (never a score)
│   │   ├── telemetry.py          ← local usage log → `researchly stats`
│   │   ├── lsp.py                ← language server (pygls <2)
│   │   └── cli.py                ← check/polish/review/abstract/rules/explain/stats/dict
│   └── tests/                    ← ~260 tests; run before ANY delivery
├── apps/
│   ├── word-addin/               ← Office JS taskpane + localhost:3517 server
│   ├── vscode-extension/         ← pre-bundled (esbuild); no npm needed on user's Mac
│   ├── desktop-mac/              ← MAINTENANCE-ONLY (D5): pyobjc menu-bar app + .dmg build
│   └── desktop-win/              ← MAINTENANCE-ONLY (D5): untested scaffold
├── services/                     ← hosted engine service (arrives in S1)
├── tools/public-export/          ← generates the public repository (never exported itself)
├── ml/
│   ├── datasets.yaml             ← licence registry: nothing ships unless permitted here
│   ├── dogfood/                  ← noise-floor corpus run + gate (baseline.json)
│   ├── eval/                     ← AESW precision/recall harness; spelling benchmarks (P40)
│   ├── private_eval/             ← PRIVATE, temporary: keyboard-bundle comparison (P41; never exported; delete when done)
│   └── tools/                    ← check_third_party.py (CI)
└── legacy/                       ← read-only: prototype-v0.8, updated-p20, experiment-p21
```

## How to work here

- **Run tests**: `cd packages/core && python3.10 -m pytest tests/ -q` (the
  user's interpreter is `python3.10`; bare `python3` is a 3.14 with no
  deps). All green before delivering. Every bug fix gets a regression test.
  CI (`.github/workflows/`) runs the same suite on Python 3.10 with Java,
  plus lint, the noise-floor gate, a third-party-text scan and a secret scan.
- **Never put third-party text in `packages/`, `apps/` or `services/`** —
  not thesis sentences, not course-PDF passages, not book exemplars, not
  even as test fixtures. Paraphrase and cite (D7); write synthetic test
  sentences. `ml/tools/check_third_party.py` enforces it in CI.
- **Nothing trained or derived ships unless `ml/datasets.yaml` permits it**
  (`ship_model` / `ship_text`). Add the registry entry before using a source.
- **Never assemble your own pipeline in a surface.** Call
  `api.analyze(...)`. It resolves config, parses **once**, and returns
  suggestions (already carrying `why`/`source`/`tier`/`fix_safety`), counts,
  the hidden-preference count, metrics, sections, and health. Surfaces that
  built their own path is exactly how they drifted apart — the macOS app was
  parsing the same text three times per keystroke batch.
- **Never store settings in a surface.** Use `researchly/config.py`; it
  layers `~/.researchly/config.toml` under `.researchly.toml`. A rule muted
  anywhere must be muted everywhere — `tests/test_surface_parity.py` proves
  it, so a new per-surface settings store will fail the suite.
- **Never let a tier fail silently.** If a dependency can be missing, it
  belongs in `researchly/health.py` with a *reason* and a *remedy*, and the
  surface must show it. Probe capability, don't test for presence: macOS
  ships a `java` stub that satisfies `shutil.which` and runs nothing, which
  is how the grammar tier stayed dead for a whole release.
- **Add a rule**: `@rule(...)` decorator in the right `rules_*.py`
  (word lists → `lexicons.py`), a `plain=` explanation in everyday words,
  fire + don't-fire tests, entry in `docs/rule-inventory.md` with its
  source. The rule's `source=` is a short
  code (`"§4"`, `"Endo"`) that `researchly/sources.py` expands into a full
  citation at registration; an unknown code fails at import, so add the
  citation there in the same change. Users never see a bare code. Declare `tier=` and
  `fix_safety=` — `fix_safety="safe"` means a bulk-apply button may touch it
  unread, and is pinned to `transform.POLISH_RULES` by a test. Registration
  happens via the imports in `engine.load_rules()`; a new *module* must be
  added there, the one list (a test fails if a `rules_*.py` is missing).
- **Surfaces pick up engine changes automatically** — they all call
  `api.analyze()`. UI changes are per-surface.
- **User's environment**: macOS (Apple Silicon), Homebrew Python 3.10 —
  so no 3.11+ syntax (no tomllib without fallback; no multiline f-string
  expressions; no backslashes inside f-string braces).
- **pyobjc rules** (learned the hard way): every non-selector method on an
  NSObject subclass needs `@objc.python_method`; ObjC-visible method names
  need one trailing underscore per argument.
- **Word add-in**: after changing its files, the user must restart
  server.py AND fully quit Word (Cmd-Q) — Word caches the taskpane.
  Never set `changeTrackingMode` without checking
  `isSetSupported("WordApi","1.4")` (silent batch-killer otherwise).
- **py2app**: only list installed packages (setup.py filters via
  `installed()`); runtime "No module named X" in the built app → add X to
  the candidates list.
- **Update the chronicle**: after any substantive work, append a dated
  entry to `docs/PROJECT_LOG.md` (what/why/files/lessons). This is a
  standing user requirement.

## Current state (details in PLAN.md and PROJECT_LOG.md)

Prototype surfaces working and user-verified: CLI, Word add-in (incl. Apply
fix, Add to dictionary), macOS app + .dmg, spelling tier. Untested by user:
LSP/VS Code extension, D2 live watching.

Production work follows `PLAN.md` slices S0–S6; the current slice is named
at the top of that file.

Things a future agent will otherwise get wrong:

- **The noise floor is just above target.** With every tier on, accepted
  theses get **11.74 flags/1000w** (P41 baseline, after the SPECIALIST
  lexicon cut S001; 11.86 at P40, when W210 learned 9k VarCon pairs; 11.67 at P33, 12.65 after S2b
  added its consistency rules, 14.51 before the Q3 tune). Q3's target is ≤ 11.
  Measure with `api.get_nlp()`, never a bare `spacy.load()`: the shared
  pipeline ends a sentence at a blank line (unless the next line carries
  on in lower case), and a runner without it measures a different engine. About 90% of the remaining S001 flags are PDF
  extraction artefacts (words joined or split at line breaks), so part of
  the gap is the measurement: see PLAN's Q3 item before re-extracting the
  corpus. Don't hide good advice (G106 long sentences, W202 wordiness) to
  reach the number — remove wrong flags. The
  corpus is plain text, so it cannot see LaTeX masking bugs; the owner's
  real `.tex` upload (P28) found those. The gate
  (`ml/dogfood/noise_gate.py`) blocks regressions *and* a busy rule going
  silent (a dead tier); it does not yet enforce the target.
  Run: `cd ml/dogfood && RESEARCHLY_CORPUS_OUT=/tmp/nf python3.10 run_dogfood.py
  && python3.10 noise_gate.py /tmp/nf/corpus_stats.json`. Never write run
  output into `ml/dogfood/results/` casually — `samples.json` holds thesis
  excerpts. `RESEARCHLY_DISABLE=S001` isolates a tier.
- **The only trained model** (TF-IDF move classifier) lives in
  `legacy/experiment-p21/` and is a pickle trained on PubMed-RCT, whose
  licence is undeclared. It is not in the engine; it re-enters only via the
  S5 bake-off and promotion gate (ADR-06).

## Before this repository is ever made public (user reminder, 2026-10-03)

The GitHub repo is **private** and must stay private while it contains
third-party material: `Sample_thesis_drafts/` (eight other people's theses),
the text extracted from them in `ml/dogfood/text/` (and older copies under
`legacy/`), and the course
PDFs in `Notes_On_Writing/`. The MIT `LICENSE` does not cover any of it.

If the user says they want to make the repo public, remind them of this
first. Deleting the files in a new commit is **not enough** — they remain in
git history. Either publish from a fresh repository that never contained
them, or rewrite history (e.g. `git filter-repo`) and confirm with the user
before doing so.

**Decision (owner, 2026-10-08): share through a separate public repository,
never by making this one public.** `tools/public-export/` generates it from
committed files through an allow-list, adds a public README and CI, and
gates every export (third-party text, the private names in
`private-terms.txt`, secrets, emails, file types); CI runs the gate on every
change. The public repository is `amriitmohapatra/researchly-public`, with
its own fresh history. To publish something new, add it to
`tools/public-export/include.txt`; read `tools/public-export/README.md` first.
Never name the lecturer or the course in the engine's code: use the neutral
source codes (`lecture`, `course-U1`, `course-U2`).

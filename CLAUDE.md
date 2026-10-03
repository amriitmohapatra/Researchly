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
starting any production work. The repository map below describes the
prototype and will change in PLAN.md slice S0.

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
2. **Local-first, always.** No document text ever leaves the machine.
   This is a compliance matter (publisher AI policies), not a preference.
   *(Under revision 2026-10-03: the user is lifting local-only so Researchly
   can be hosted. Proposed replacement — "Confidential by design": transient
   in-memory processing, never stored/logged/trained on without opt-in, local
   mode retained — is ADR-02 in `ARCHITECTURE.md`, awaiting the user's
   wording sign-off (PLAN.md D1). Until signed off, do not build anything
   that persists or logs document text.)*
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

## Repository map

```
Researchly/
├── CLAUDE.md, AGENTS.md          ← you are here
├── The-Craft-of-Scientific-Writing.md   ← the founding writing guide
├── Notes_On_Writing/             ← course PDFs — BEING RE-MINED (W5, see below)
├── Sample_thesis_drafts/         ← 8 accepted theses (dogfooding corpus)
├── research/                     ← Phase-1 landscape research (00-synthesis.md first)
├── docs/
│   ├── PROJECT_LOG.md            ← THE chronicle: read to understand everything
│   ├── rule-inventory.md         ← all rules, all layers, sources, status
│   ├── knowledge-base.md         ← source-document → rule provenance map
│   ├── dogfooding-report.md      ← how precision tuning was done (methodology)
│   └── roadmap-rewrite-and-desktop.md
└── prototype/
    ├── researchly/               ← THE ENGINE (one package, all surfaces use it)
    │   ├── api.py                ← analyze(): THE entry point every surface calls
    │   ├── config.py             ← layered settings, shared by every surface
    │   ├── health.py             ← per-tier status; no tier may fail silently
    │   ├── document.py           ← offset-preserving markup masking + IMRaD sections
    │   ├── engine.py             ← Rule/Suggestion types, registry, check(), aggregation
    │   ├── rules_*.py            ← rule modules (lexical, syntax, spelling, grammar)
    │   ├── abstract_lens.py      ← Belcher six-part abstract check (AB802)
    │   ├── review.py             ← Wallace & Wray critical-reader report
    │   ├── transform.py          ← deterministic Polish rewriter
    │   ├── spelling.py           ← SymSpell wrapper + guards + user dictionary
    │   ├── lexicons.py           ← ALL word lists (auditable; extend here)
    │   ├── metrics.py            ← read-outs incl. hedge/booster meter (never a score)
    │   ├── telemetry.py          ← local usage log → `researchly stats`
    │   ├── lsp.py                ← language server (pygls <2)
    │   └── cli.py                ← check/polish/review/abstract/rules/explain/stats/dict
    ├── word-addin/               ← Office JS taskpane + localhost:3517 server
    ├── vscode-extension/         ← pre-bundled (esbuild); no npm needed on user's Mac
    ├── desktop-mac/              ← pyobjc menu-bar app + py2app/.dmg build
    ├── desktop-win/              ← UNTESTED scaffold
    └── tests/                    ← ~130 tests; run before ANY delivery
```

## How to work here

- **Run tests**: `cd prototype && python3.10 -m pytest tests/ -q` (the
  user's interpreter is `python3.10`; bare `python3` is a 3.14 with no
  deps). All green before delivering. Every bug fix gets a regression test.
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
  (word lists → `lexicons.py`), fire + don't-fire tests, entry in
  `docs/rule-inventory.md` with its source. Declare `tier=` and
  `fix_safety=` — `fix_safety="safe"` means a bulk-apply button may touch it
  unread, and is pinned to `transform.POLISH_RULES` by a test. Registration
  happens via the imports in `engine.check()`; a new *module* must be added
  there (the surfaces no longer import rule modules individually).
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

## Current state & near-term backlog (details in PROJECT_LOG.md)

Working and user-verified: CLI, Word add-in (incl. Apply fix, Add to
dictionary), macOS app + .dmg, spelling tier. Untested by user: LSP/VS
Code extension, D2 live watching.

**v0.8 is in progress against a five-workstream plan** (W0 shared layer ✅ ·
W1 reliability · W2 parity + settings · W3 grammar depth · W4 document
intelligence · W5 knowledge re-mine). Read the PROJECT_LOG P15 entry first.

Two things a future agent will otherwise get wrong:

- **The grammar tier has never run on this machine.** Not a code bug — there
  is no JRE, only the macOS `java` stub. `researchly check` now says so.
- **The spelling tier has never been dogfooded** (S001 shipped after the last
  corpus run). It adds 2.4 flags/1000w on *accepted* theses; most are PDF
  artifacts, but `estimand(s)`, `urbanicity`, `prespecified`, `lockdowns`,
  `serotypic`, `tradeoff` are real gaps in `data/scientific_terms.txt`.

The noise-floor guard is runnable again:
`python3.10 dogfood/extract_clean.py && python3.10 dogfood/run_dogfood.py`
(`RESEARCHLY_DISABLE=S001` isolates a tier). Baseline **10.4/1000w** ex-S001;
past ~11 means re-tune, not ship.

## Before this repository is ever made public (user reminder, 2026-10-03)

The GitHub repo is **private** and must stay private while it contains
third-party material: `Sample_thesis_drafts/` (eight other people's theses),
the text extracted from them in `*/prototype/dogfood/text/`, and the course
PDFs in `Notes_On_Writing/`. The MIT `LICENSE` does not cover any of it.

If the user says they want to make the repo public, remind them of this
first. Deleting the files in a new commit is **not enough** — they remain in
git history. Either publish from a fresh repository that never contained
them, or rewrite history (e.g. `git filter-repo`) and confirm with the user
before doing so.

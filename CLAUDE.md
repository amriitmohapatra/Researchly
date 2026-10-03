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
├── Experiment_Researchly/        ← EXPERIMENT FORK (P21-EXP drafting guide); not the
│                                    mainline — see PROJECT_LOG P21 before touching it
├── docs/
│   ├── PROJECT_LOG.md            ← THE chronicle: read to understand everything
│   ├── rule-inventory.md         ← all rules, all layers, sources, status
│   ├── knowledge-base.md         ← source-document → rule provenance map
│   ├── dogfooding-report.md      ← how precision tuning was done (methodology)
│   ├── windows-smoke-checklist.md ← ordered real-hardware Windows bring-up protocol
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
    │   ├── argument.py           ← ArgumentObject: Toulmin roles per section (feeds review)
    │   ├── gec.py                ← learned-GEC scaffold (opt-in, abstains; tier="gec")
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
    └── tests/                    ← ~260 tests; run before ANY delivery
```

## How to work here

- **Run tests**: `cd prototype && python3.10 -m pytest tests/ -q` (the
  user's interpreter is `python3.10`; on their Mac bare `python3` is a 3.14
  with no deps). All green before delivering — currently **260 passed,
  1 skipped** off macOS (P21). Every bug fix gets a regression test.
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
  expressions; no backslashes inside f-string braces). Pin dependencies to
  versions that still ship 3.10 wheels, including the version any model
  artifact is pickled with (P21: a scikit-learn 1.8 pickle cannot load on
  3.10). Some sessions run on a cloud Ubuntu VM instead: `python3.10` and a
  real JDK exist there, `desktop-mac/` and pyobjc cannot be exercised, and
  the macOS java-stub test skips by design.
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

The repo holds **one mainline tree** at the root (consolidated in P21) plus
the `Experiment_Researchly/` fork (P21-EXP drafting guide — not merged; its
move classifier cannot load on Python 3.10 until retrained, see P21).

Working and user-verified: CLI, Word add-in (incl. Apply fix, Add to
dictionary), macOS app + .dmg, spelling tier, and the grammar tier on the
user's Mac (P17). Built but not yet user-tested: LSP/VS Code extension, D2
live watching, the P19 Word Settings/Review/Health tabs, the macOS panel
action buttons and Settings window, both P20 standalone installers, and
everything in `desktop-win/` (follow `docs/windows-smoke-checklist.md`).

**v0.8 is in progress against a five-workstream plan.** Status from the log:
W0 shared layer ✅ (P15) · W1 reliability ✅ (P16) · W2 parity + settings
— shipped in P19, awaiting on-device testing · W3 grammar depth — started:
LanguageTool live and tuned (P17–P18), learned-GEC scaffold present but
abstaining (P19) · W4 document intelligence — only the P19 ArgumentObject so
far · W5 knowledge re-mine — no entry yet. Read PROJECT_LOG P15 (the plan)
and P21 (the latest state) first.

Things a future agent will otherwise get wrong:

- **The grammar tier runs.** Homebrew's openjdk is keg-only, so the JDK is
  invisible to `which java`; `health.find_java()` searches for it and puts
  it on PATH for the process (P17), and the P20 installers bundle a JRE. Do
  not "fix" this with a `sudo` symlink, and do not reintroduce a presence
  check — macOS's `/usr/bin/java` stub passes `shutil.which`.
- **Spelling lexicon gaps are still open.** S001 adds 2.4 flags/1000w on
  *accepted* theses (P15); most are PDF artifacts, but `estimand(s)`,
  `urbanicity`, `prespecified`, `lockdowns`, `serotypic`, `tradeoff` are
  real gaps in `data/scientific_terms.txt`.
- **The recall bar is 15.3%** AESW edit-site recall with every tier live
  (P18). A learned GEC model has to beat it to justify itself.

The noise-floor guard: `python3.10 dogfood/run_dogfood.py` from
`prototype/` (re-extract first with `dogfood/extract_clean.py` only if the
PDFs change). Set `RESEARCHLY_CORPUS_OUT` to a scratch directory unless you
mean to update the tracked `dogfood/results/`. Compare like with like:

| Run | Baseline (flags/1000w) |
|---|---|
| `RESEARCHLY_DISABLE=S001,LT001` (craft layers only) | **10.4** — past ~11 means re-tune, not ship |
| `RESEARCHLY_DISABLE=S001` with grammar live | **12.5** (P18, after tuning LT001) |
| all tiers | 14.9 |

All three were reproduced exactly in P21. Grammar-live numbers are only
valid where a JDK is found; a machine without one silently gives the
craft-only figure, so check `researchly check`'s tier banner first.

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

# AGENTS.md — Researchly

Operational guide for AI coding agents. Fuller context in `CLAUDE.md`;
production design in `ARCHITECTURE.md`; the shared checklist in `PLAN.md`;
complete history in `docs/PROJECT_LOG.md`. **Read those two files before
asking the user what to change** — the answer to "what is this and where
are we" is written down.

## Project

Researchly: an explainable writing coach for research students — advice on
correctness, craft and narrative, never drafting. One Python engine
(`packages/core`), several surfaces (CLI, Word add-in, LSP/VS Code; macOS and
Windows apps in maintenance-only), moving to a hosted web app (PLAN.md).

## Setup

```bash
cd packages/core
pip install -r requirements.txt          # spacy, symspellpy, pygls, pytest, language-tool-python
python -m spacy download en_core_web_sm
# grammar tier needs a real Java 17+ runtime (not the macOS stub)
```

## Commands

```bash
python3.10 -m pytest tests/ -q           # ~260 tests (from packages/core); must be green
python3.10 -m researchly check FILE      # the checker
python -m researchly polish "text"       # deterministic rewrite
python -m researchly review --file F     # critical-reader report
python -m researchly abstract --file F   # six-part abstract lens
python -m researchly rules|explain|stats|dict
python ../../apps/word-addin/server.py   # Word add-in backend (:3517)
python -m researchly.lsp                 # language server (stdio)
python ../../apps/desktop-mac/researchly_app.py   # macOS app (maintenance-only)
```

## Hard constraints (user decisions — never violate silently)

- **No cloud LLMs, no generative drafting. Local non-generative ML is
  allowed.** *(Amended 2026-08-11 — the old rule said "no LLMs", which was
  ambiguous and blocked the grammar tier.)* Forbidden: cloud/API models,
  free-form prose generation, silent rewriting. Permitted: on-device
  taggers/classifiers proposing **minimal token-level edits**, confidence-
  scored, gated off inside masked spans, never auto-applied, labelled
  `tier="gec"`. Rewriting itself stays deterministic (`transform.py`).
- **Confidential by design** *(amended 2026-10-03; was "no text leaves the
  machine")*. Document text is processed in memory, never stored, logged,
  shared or trained on without a per-feature opt-in; no cloud LLM sees it;
  a local mode stays available. Still a compliance requirement.
- **No third-party text in `packages/`, `apps/`, `services/`** (theses,
  course PDFs, book passages — fixtures included). Paraphrase and cite;
  `ml/tools/check_third_party.py` runs in CI. Nothing trained on a source
  ships unless `ml/datasets.yaml` permits it.
- **Python 3.10 compatible** (user's Homebrew Python): no bare `tomllib`,
  no multiline/backslashed f-string expressions. Run tests with
  `python3.10` — bare `python3` is a 3.14 with no dependencies installed.
- Taxonomy (Correction/Improvement/Convention/Preference), section
  awareness, and precision-over-recall are architectural, not stylistic.

## The shared layer — use it, don't route around it

- `api.analyze(...)` is **the** entry point for every surface. One config
  resolution, one spaCy parse, one result object (suggestions already carry
  `why`/`source`/`tier`/`fix_safety`). Do not hand-assemble
  `Document`+`check`+`metrics` in a surface; that divergence is what W0
  existed to undo.
- `config.py` is **the** settings store (`~/.researchly/config.toml` layered
  under `.researchly.toml`). No per-surface preference files, no
  localStorage. `tests/test_surface_parity.py` fails if you add one.
- `health.py` is **the** capability report. Any optional dependency gets a
  status with a reason and a remedy, shown by every surface. Probe
  capability rather than presence — macOS's `java` stub passes
  `shutil.which` and runs nothing.

## Conventions

- New rule = `@rule` in a `rules_*.py` + lexicon in `lexicons.py` + fire
  AND don't-fire tests + row in `docs/rule-inventory.md` with source.
  Declare `tier=` and `fix_safety=`; `fix_safety="safe"` is pinned to
  `transform.POLISH_RULES` by a test. New rule *modules* are imported in
  `engine.check()` only.
- Rules operate on `document.masked` (markup already space-masked;
  offsets = source offsets). Never flag inside masked regions. If you build
  a replacement string, build it from the **original** text, not the mask —
  splicing mask-derived text back into the source deletes whatever was
  masked (this is how Polish once ate inline math).
- Convention-type rules that can fire often should set `aggregate=True`.
- Every bug fix ships with a regression test; run the full suite before
  handing anything back. Precision changes also get a corpus run:
  `ml/dogfood/run_dogfood.py` then `noise_gate.py` — S1 baseline 14.75/1000w
  all tiers (target ≤ 11). CI blocks regressions and silent tiers.
- Append a dated entry to `docs/PROJECT_LOG.md` after substantive work
  (standing user requirement).

## Platform gotchas (all previously hit; see PROJECT_LOG debug log)

- pyobjc: `@objc.python_method` on every helper in NSObject subclasses.
- Word add-in: user must Cmd-Q Word after file changes (taskpane cache);
  gate `changeTrackingMode` behind `isSetSupported("WordApi","1.4")`.
- py2app: bundle list is auto-filtered by `installed()`; runtime
  missing-module errors → add to the candidates list in setup.py.
- spaCy tokenizer splits some typos ("thiss"→"this"+"s") — spelling scans
  raw text by regex, not tokens. Don't "simplify" that back.
- macOS AX layer cannot be tested off-device: write defensively, expect a
  traceback-driven session with the user. (Windows hardware IS now
  available, but the desktop apps are maintenance-only since D5.)
- Word has no offset-addressable API: the taskpane re-finds each span by
  searching. Hand it the **full** span and make it verify what it matched
  before replacing — a truncated needle or a bare `items[0]` fallback
  silently rewrites the wrong copy of a repeated phrase.

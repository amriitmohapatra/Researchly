# PROJECT_LOG.md — The Researchly Chronicle

*The zero-memory file: a new AI agent (or future us) reads this and knows
the full sequence of work, why every decision was made, and where things
stand. **Standing convention: every working session appends a dated entry
here.** Companion files: `CLAUDE.md` / `AGENTS.md` (how to work here),
`rule-inventory.md` (all rules), `knowledge-base.md` (source provenance),
`dogfooding-report.md` (tuning methodology).*

---

## The idea

Researchly = "Grammarly for scientific writing": a research-focused,
context-aware writing assistant for academics — built by Amriit (PhD
student, infectious disease modelling, NUS; writes in Word,
Overleaf/LaTeX, Quarto/VS Code; R/Stan/Python). Core concept: suggestions
typed as **Correction / Improvement / Convention / Preference**,
**section-aware** (same sentence, different advice in Methods vs
Discussion), **explainable** (every flag cites its source), and
**local-first** (nothing leaves the machine — publisher AI policies make
this compliance, not preference).

## Foundational user decisions (chronological)

1. Research before building; markdown docs accumulate in the repo.
2. Python prototype first; Gopen & Swan rule pack as the MVP.
3. NC-licensed components acceptable (personal, non-commercial use).
4. **NO LLMs** — "explore options where LLMs are not needed" (rewriting
   is deterministic; grammar delegated to open-source engines).
5. Desktop goal = full Grammarly-style overlay, reached in stages
   (D1 menu-bar → D2 watcher/badge → D3 underlines).
6. Check open source before building anything commodity.
7. CLAUDE.md/AGENTS.md/this log must let any future AI work unassisted.

## Build sequence (all 2026-08-10, one long day)

**P1 — Landscape research** → `research/` (5 docs; read `00-synthesis.md`).
Verdict: the niche is open; taxonomy maps to an engineering stack;
LTeX-style offset-preserving markup masking + section detection are the
keystone components; precision (FP fatigue) is the known killer.

**P2 — Rule mining** → `rule-inventory.md`. The founding guide
(`The-Craft-of-Scientific-Writing.md`: Gopen & Swan, Schimel OCAR, Swales
CARS, Toulmin) decomposed into 60+ typed rules across 7 layers.

**P3 — v0.1 engine + CLI** → `prototype/researchly/`. spaCy
(en_core_web_sm) + regex; ~24 rules; masking for .md/.qmd/.tex with
offsets preserved 1:1 (mask with spaces, never delete); heading-based
IMRaD detection; `.researchly.toml` muting. User's Python is 3.10 →
tomllib fallback shipped.

**P4 — Dogfooding** → `dogfooding-report.md`. Ran on 8 *accepted* PhD
theses (`Sample_thesis_drafts/`, extracted via `prototype/dogfood/`).
v0.1 fired 21 flags/1000w (fatigue zone) → 6 failure patterns fixed →
10.1/1000w. Lessons: calibrate against accepted literature, not seeded
errors; aggregation is a fatigue-control primitive; structural fixes
(masking layer) beat rule fixes.

**P5 — Word add-in** → `word-addin/`. Office JS taskpane ↔ stdlib
localhost:3517 server. Word heading *styles* → sections. Suggestions map
back via (paragraph, offset, occurrence)+search. User-tested: works.

**P6 — v0.2** — local telemetry (`~/.researchly/telemetry.jsonl`,
`researchly stats` keep-rates); engine-level `aggregate=True`; F601
abbreviation-list awareness; **LSP server** (`researchly/lsp.py`, pygls
pinned <2) + pre-bundled VS Code extension (`vscode-extension/`, esbuild,
no npm needed on user machine).

**P7 — v0.3 Polish** → `transform.py`. Deterministic rule-composed
rewriting with word-level diff + per-edit ledger; cascades to fixpoint
("It is important to note that there are three factors that drive X." →
"Three factors drive X."). G102 conjugation fix ("performed an estimation
of the rate"→"estimated the rate"). Roadmap doc for desktop written
(`roadmap-rewrite-and-desktop.md`), incl. honest no-LLM ceiling.

**P8 — v0.4 Knowledge mining** → `knowledge-base.md`. All 12 documents in
`Notes_on_writing/` read individually (Endo lecture = richest; NG5001
Units; Wallace & Wray ch.4; Shehzad 2008; Pallas 2022). +10 rules (E70x,
AB801, L901, D902 first doc-level check). Noise floor held (10.2/1000w).

**P9 — D1 macOS app** → `desktop-mac/`. pyobjc menu-bar app: ⌘⇧R/⌘⇧P
hotkeys anywhere, AX selection capture + clipboard fallback (restore),
non-activating floating panel (WKWebView render + native buttons),
paste-back. User-tested after one fix (see debug log).

**P10 — v0.5 Commodity layer** (user caught the gap: "I amm duing dis
workk at thiss shity" unflagged — deliberate P1 deferral). **S001**
spelling: symspellpy + heavy guards (shipped scientific lexicon
`researchly/data/scientific_terms.txt`; personal dictionary `researchly
dict add`; UK/US variants; morphology with FUNCTION_WORDS exemption;
3+-use learned terms; proper-noun distance-1 gate; regex scan because the
tokenizer splits typos). **LT001** grammar: language_tool_python = LOCAL
LanguageTool server (non-AI, Java 17+, optional, silently inert if
absent); keeps grammar/confusion categories, drops spelling/style.

**P11 — Word add-in round 2** (user: Apply fix didn't work). Root cause:
setting changeTrackingMode without WordApi 1.4 fails at ctx.sync(),
killing every apply → now capability-gated. Added: body-search fallback,
Delete-phrase fixes, **Add to dictionary** button → /dictionary endpoint.

**P12 — v0.6** — **Abstract lens** (`abstract_lens.py`): Belcher/Pallas
six moves by signal lexicons; AB802 rule + `researchly abstract` CLI with
fill-in frames; validated on Pallas's own exemplar (6/6). **D2 live
watcher** in the macOS app: 2.5s AX poll of focused field, floating
"R n" badge (off by default; per-app deny list; browsers opaque → hidden).
**.dmg prep**; user built it after one fix (see debug log) — **.dmg and
Word add-in both confirmed working**.

**P13 — v0.7 Architecture completion (this entry).** Metadiscourse meter
(Hyland boosters + self-mention + hedge/booster calibration balance in
metrics across all surfaces); **W210** variant-consistency (curated UK/US
pairs — algorithmic pairing creates false pairs like four/for);
**`researchly review`** (`review.py`): Wallace & Wray five-question
reviewer's brief from deterministic evidence; **Windows scaffold**
(`desktop-win/`, UNTESTED: keyboard+pyperclip+pywebview+PyInstaller bat);
CLAUDE.md, AGENTS.md, and this chronicle created.

## Debug log (hard-won; don't re-learn these)

| Issue | Cause | Fix |
|---|---|---|
| pyobjc BadPrototypeError '_run' | NSObject methods treated as ObjC selectors | `@objc.python_method` on all helpers |
| Word Apply fix dead | changeTrackingMode fails at sync() pre-WordApi 1.4 | capability-gate with isSetSupported |
| py2app ImportError langcodes | crashes on any uninstalled listed package | setup.py `installed()` filter |
| "thiss" not flagged | spaCy tokenizer splits it "this"+"s" | S001 scans raw text by regex |
| "duing" excused | spaCy lemma guessed "due" | no lemma fallback in spelling |
| "thiss" excused as this+s | morphology too generous | FUNCTION_WORDS exemption |
| "Kieshha" flagged | sentence-start caps | flag only with distance-1 correction |
| LT AttributeError ruleIssueType | lib moved to snake_case | getattr fallbacks both spellings |
| tomllib missing | user Python is 3.10 | tomli fallback + graceful skip |
| f-string SyntaxError risk | 3.10: no multiline/backslash in braces | hoist to variables |
| Word shows stale add-in | taskpane cached | restart server + Cmd-Q Word |
| test polluted by real ~/.researchly | live test wrote user dictionary | tests monkeypatch USER_DICT_FILE |

## Current state (end of 2026-08-10)

- **User-verified working**: CLI, Word add-in (check/polish/apply/
  dictionary), macOS menu-bar app via built .dmg, spelling tier.
- **Built, not yet user-tested**: LSP + VS Code extension; D2 live
  watching toggle; LT001 on the user's machine (needs
  `pip install language-tool-python` + Java); `researchly review`,
  `researchly abstract`, metadiscourse meter, W210 (this session's work).
- **Untested scaffold**: `desktop-win/` (no Windows machine yet).
- ~37 rules · ~135 tests · all local · no LLM anywhere.

## Backlog (rough priority)

1. **Grammar depth** — user feels checking "needs improvement" but wants
   evidence first: accumulate telemetry, collect missed-error examples,
   then review `researchly stats` + consider LT category widening or
   more LT rules kept, more confusable pairs, agreement rules.
2. User testing of this session's features + LSP/VS Code.
3. D3 underline overlay (AXBoundsForRange; Word/native apps only).
4. Windows bring-up (traceback-driven session on a real machine).
5. Discipline/journal packs; audience/persona setting; figure-caption
   and equation-context checks (F60x layer); EPIFORGE checker (research-
   grade, publishable).

---

## 2026-08-10 (later) — P14: Shippable tester packages (v0.7)

User asked for compact, dependency-complete zips to share with testers.

- **`Researchly-WordAddin-v0.7.zip`** (84 KB, built + smoke-tested in the
  cloud sandbox: unzipped fresh → server ran → 37 rules fired). Contents:
  engine package (with data/), word-addin/, requirements.txt,
  `install-mac.sh` (deps + model + manifest sideload in one command),
  `start-server.sh`, `README-TESTERS.md` (privacy pitch, install, use,
  feedback protocol), `OPTIONAL-grammar-tier.md` (LanguageTool + Java),
  Windows sideload note. Testers need Python 3.9+; model download ~40 MB
  happens in the installer.
- **macOS app package**: the .dmg only exists on Amriit's Mac, so shipped
  `desktop-mac/ship_zip.sh` — run after build_app.sh/make_dmg.sh, bundles
  Researchly.dmg + `README-TESTERS-macOS.md` (right-click-open for the
  unsigned app, `xattr -cr` if "damaged", Accessibility grant, hotkeys,
  feedback protocol) into `Researchly-macOS-v0.7.zip`.
- Distribution caveat recorded: apps are unsigned/un-notarized — fine for
  personal sharing; wider distribution would need an Apple Developer ID
  (signing + notarization) later.

Files: shipping zip delivered to repo root; desktop-mac/ship_zip.sh,
desktop-mac/README-TESTERS-macOS.md.

---

## 2026-08-10 (later) — Codex review received

`Codex_Review.md` (repo root) — a read-only architecture/knowledge/Grammarly-gap
audit across the Word add-in, macOS app, and Windows scaffold. Logged here
retrospectively; it arrived after P14 and sat untriaged.

Headline findings: (§A) ten limitations vs Grammarly, led by "grammar
correction quality is not in the same class" and the observation that LT001
is an **optional silent dependency**; (§B) the knowledge base is modelled as
a first-generation rule inventory, not as "a semantic academic-writing
intelligence system" — 24 items listed as not yet modelled, and the argument
that the next modelling unit should be an **argument object** (claim,
grounds, warrant, qualifier, rebuttal), not another phrase rule; (§C) the
pivotal question — does "no LLMs" mean no cloud generation, or no learned
model at all? Codex recommends allowing local non-generative ML.

---

## 2026-08-11 — P15: W0 shared surface layer (v0.8 begins)

Plan: `~/.claude/plans/read-the-files-in-greedy-patterson.md` (5 workstreams,
user-approved). Four user decisions taken up front, which **amend the
non-negotiables in CLAUDE.md**:

1. **"No LLMs" now means no cloud, no generative drafting. Local
   non-generative ML is permitted** (GEC edit taggers, classifiers). CLAUDE.md
   non-negotiable #1 must be reworded or a future agent will revert the work.
2. Windows hardware is now available → real bring-up, not blind hardening.
3. All four limitation areas in scope, plus a fifth: **re-mine
   `Notes_On_Writing/` in full** — overriding CLAUDE.md's "already fully
   mined — don't re-read".
4. Audience = user + a few testers → low install friction, no code-signing.

### The structural problem W0 fixes

Every surface re-implemented config loading, `why`/`source` joining,
preference counting, and the metrics parse — which is why they had drifted.
`load_config` lived inside `cli.py`, so `.researchly.toml` reached only the
CLI and LSP; Word mutes lived in browser localStorage; macOS had its own
`desktop.json`; Windows had nothing.

### Shipped

- **`researchly/config.py`** — layered settings (defaults → `~/.researchly/
  config.toml` → `.researchly.toml` → call overrides). Legacy `[rules]` shape
  still read. Adds `locale`, `document_type`, `aggressiveness`, tier
  switches. Hand-rolled TOML writer (the Word server is stdlib-only).
  `mute_rule()` writes the USER config so a mute follows the writer.
- **`researchly/health.py`** — `engine_status()` per tier with a *reason* and
  a *remedy*. Never raises, never downloads unless probed.
- **`researchly/api.py`** — `analyze()`: one entry point, **one spaCy parse**,
  returning suggestions + counts + hidden-preference count + metrics +
  sections + health + config. `get_nlp()` now sets `max_length` identically
  for every surface.
- **`engine.py`** — `Suggestion` gains `why`, `source`, `tier`, `fix_safety`,
  `confidence`; `Rule` gains `tier`/`fix_safety`; `check()` accepts a
  pre-parsed doc; added `_resolve_overlaps()` (correction tiers only — craft
  and lens suggestions are never deduped against anything). Removed the dead
  `hidden_preference_count()`, which re-ran the whole pipeline.
- **All five surfaces rewired** onto `api.analyze`. Word gains `/status`,
  `/rules`, `/config` endpoints. macOS/Windows panels gain a tier-status
  banner via `panel_html.render_tiers()`. LSP mute now goes through
  `config.mute_rule` instead of hand-patching TOML with `str.replace`.

### Measured

- **Latency**: 34k-char document — macOS 3.92s → 1.30s (3.0×; it had been
  parsing three times), Word 2.52s → 1.30s (1.9×).
- **Noise floor**: 10.4/1000w with S001 disabled, against the documented
  10.1–10.2 baseline — the W0 refactor is output-neutral; the delta is W210
  and other rules added after the last corpus run.
- Tests 128 → **177 passed**, 4 skipped.

### Findings worth keeping

| Finding | Detail |
|---|---|
| **LT001 has never run on this machine** | macOS ships a `java` *stub* at `/usr/bin/java` that exists on PATH but exits non-zero. `shutil.which("java")` finds it, so the tier looked installed while never once starting. Health checks must **run** `java -version`, not test for presence. |
| **The spelling tier has never been dogfooded** | S001 was added in P10, after the last corpus run. It contributes 691 flags (2.4/1000w) on *accepted* theses. Families: PDF-extraction fragments (`sero`, `Princ`, `Diagn`), proper nouns (`Zhang`, `Acta`), code identifiers (`logP`, `ejk`), and **real lexicon gaps** — `estimand(s)`, `urbanicity`, `prespecified`, `lockdowns`, `serotypic`, `tradeoff`. One genuine catch: `subsceptible`. → W3. |
| **`[dictionary] words` never worked** | Documented in `spelling.py` since v0.5; `rules_spelling.py` read `document.extra_dictionary` and nothing ever set it. Now wired through `api.analyze`. |
| **The dogfood scripts could not run locally** | Both carried hardcoded cloud-sandbox paths (`/home/claude/...`, `/mnt/user-data/...`), so the project's primary precision guard was unrunnable on the user's machine. Now resolved relative to the file, with `RESEARCHLY_DISABLE` to isolate a tier's contribution. |
| **`test_lsp.py` failed opaquely** | `pygls` is not installed on the user's 3.10; the subprocess died instantly on ImportError but stderr was `DEVNULL`, so it surfaced as "no diagnostics published" after 40s. Now skips with a reason and reports the child's traceback. |

---

## 2026-08-11 — P16: W1 reliability, doc amendments, evaluation corpora

### W1 defects 2–8 — all fixed, 21 regression tests (`test_w1_reliability.py`)

| # | Defect | Fix |
|---|---|---|
| 2 | **Apply could rewrite the wrong copy** of a repeated phrase — 180-char truncated needle, `Math.min` clamp on the occurrence index, body fallback taking `items[0]` | Server sends the **full** span plus `exact`/`expected`; client verifies `para.text.substring(start,end) === expected` before touching anything, refuses an ambiguous document-wide match, and no longer clamps |
| 3 | **Track Changes switched on at first Apply and never restored** | `beginTracking`/`endTracking` capture and restore the prior mode, in a `finally` so a failed edit cannot strand it |
| 4 | **Polish deleted inline maths** — and, undiscovered until now, **citations too** | Root cause was subtler than recorded: `\s+` in the expletive pattern swallows a masked region (masks are spaces), so the *matched span* covered `$n$` even though the noun phrase did not. Now any span covering a mask is dropped |
| 5 | Footnotes/headers/text boxes/comments never checked, never mentioned | `/check` returns a `coverage` block; the pane states what was not read |
| 6 | **Table cells joined as prose**, skewing metrics and re-sectioning | Client tags `kind:"table"` via `tableNestingLevel`; `Document.table_spans` + `in_table()`; metrics skip them. *A test caught a second path — `from_text` had already run keyword heading detection over the combined string, so a cell reading "Methods" still re-sectioned the document; headings inside table spans are now dropped* |
| 7 | Auto-recheck fired every 4 s regardless of edits (`\r` vs `\n\n` — the strings could never be equal) | `normalizeBody()` on both sides |
| 8 | **Citation fields destroyed** by `insertText` | `overlapsField()` guards both Apply and Polish-insert |

Also: `insertPolished` still called the renamed `maybeEnableTracking` — a
latent `ReferenceError` on every Polish insert, caught before delivery.

Suite 177 → **198 passed**. Noise floor unchanged at **10.4/1000w**.

### CLAUDE.md / AGENTS.md amended

Non-negotiable #1 rewritten to the precise boundary (no cloud, no generative
drafting; local non-generative ML permitted, `tier="gec"`, never
auto-applied). Repo map no longer says `Notes_on_writing/` is fully mined.
Added the three standing rules a future agent would otherwise break: call
`api.analyze`, store settings only in `config.py`, never let a tier fail
silently. Test command corrected to `python3.10` (bare `python3` is a 3.14
with no dependencies).

### Evaluation corpora — `docs/eval-corpora.md`

Sourced acquisition plan with verified licences. Headline: **AESW 2016** —
~1.2M sentences from 9,919 published journal articles, each before *and*
after a professional language editor. Direct download, no registration;
**the site's TLS cert has expired**, so `curl -k` over plain HTTP. CC BY-NC-SA
4.0 plus no-re-identification clauses → `eval/data/` is gitignored, never
redistribute. Also mapped: BEA-2019 family (all non-commercial), ERRANT
(**MIT**, needs the spaCy we already have — prefer to GPL-2.0 m2scorer), and
Tier-2 sets of which **GMEG, CWEB and jfleg declare no licence at all**.

Built `eval/aesw.py` + `eval/stress_test.py` and ran it (3,000 sentences,
63,773 words):

**False positives on editor-approved prose** — 25.1 flags/1000w overall;
16.4 without F601; **9.5 with F601 and S001 excluded**, against a 10.4 thesis
baseline. The craft layer is independently corroborated as well calibrated.
The excess is F601 (34.7%, largely an artifact of feeding isolated sentences
— it cannot see the abbreviation list, which also matters for the desktop
surfaces where input really is a loose selection) and S001 (27.4%, the same
lexicon gaps the thesis corpus showed).

**Detection on text an expert changed** — 38.1% of edited sentences flagged,
**13.0% flagged at the edit site**. First recall figure in the project's
history. Caveats stated in the doc: the grammar tier was dead for this run
(no JRE), AESW edits are largely house-style copy-editing Researchly
deliberately avoids, and edit-site offsets are approximate.

**Consequence for W3**: recall cannot be honestly measured until LanguageTool
runs (`brew install openjdk@17`) — that is now a blocking prerequisite, not
an optional extra. Fix the S001 lexicon first; the craft layer needs nothing.

---

## 2026-08-11 — P17: the grammar tier actually runs (JDK discovery)

User installed `openjdk` + `openjdk@17` and still saw "Grammar checking is
off". Not a false alarm — the banner was right.

**Root cause: Homebrew's openjdk is keg-only.** `brew install openjdk@17`
succeeds, reports success, and links nothing into PATH or into
`/Library/Java/JavaVirtualMachines` (which was empty). `java` therefore still
resolved to Apple's `/usr/bin/java` stub, and `language_tool_python` locates
the JVM with `shutil.which("java")` — so a perfectly good JDK sitting in
`/opt/homebrew/opt/openjdk@17` was invisible to it.

The usual advice is a `sudo ln -s` into `/Library/Java/JavaVirtualMachines`.
Rejected: it needs sudo, it is easy to get wrong, and it would have to be
repeated by every tester. The app should find the JDK it has.

**Fix** — `health.find_java()` / `ensure_java_on_path()`:

- Searches JAVA_HOME → PATH → `/usr/libexec/java_home` → Homebrew opt globs
  → `/Library/Java/JavaVirtualMachines` → sdkman → linux/windows paths.
- **Runs** each candidate and parses the major version rather than trusting
  its presence; requires >= 17, handles `1.8.0_x` numbering.
- Prepends the winner's `bin` to this process's PATH and sets `JAVA_HOME`,
  so `language_tool_python`'s `which("java")` finds it. Scoped to the
  Researchly process; nothing outside it is touched.
- `rules_grammar.reset()` clears the deliberately-sticky `_FAILED`, so
  installing a JDK while the Word server is running no longer requires a
  restart to be noticed.

Verified in a plain shell with no PATH export and `JAVA_HOME` unset: found
`/opt/homebrew/opt/openjdk@25/.../bin/java`, LanguageTool 6.8 started, and
`researchly check` returned LT001 fixes (`has`→`have`, `A`→`An`,
`is`→`are`). Word server `/status` reports the grammar tier ready and
`/check` returns LT001 suggestions.

Suite 198 → **205 passed**, and skips dropped 4 → 1 because the
grammar-dependent tests now actually execute. No `sudo`, no symlink, no PATH
editing required by the user.

**W3's blocking prerequisite is cleared** — the AESW recall measurement can
now be re-run with the correction tier live.

---

## 2026-08-11 — P18: cleanup, packaging fixes, v0.8 tester builds

### Removed (262 MB of stale artifacts)

`desktop-mac/dist/`, `desktop-mac/build/`, `desktop-mac/Researchly.dmg` and
`shipping/Researchly-WordAddin-v0.7.zip` — all built from the pre-W0 engine
(verified: the zip contained no `api.py`/`config.py`/`health.py`). Plus all
`.DS_Store`, all `__pycache__`, and a stray Word lock file at the repo root.

`build_app.sh` was **fixed, not deleted** — deleting the only build entry
point moves the confusion rather than removing it. It had two live defects:
`$MODE` was referenced after the `--alias` block that set it had been
dropped (so `--alias` silently did nothing), and its Java warning still told
the user to create the `sudo` symlink that P17 made unnecessary. It now asks
`health.find_java()` rather than the shell.

### Packaging defects found by actually testing the artifacts

| Defect | Consequence | Fix |
|---|---|---|
| `language_tool_python` **excluded from the .app** by a deliberate `setup.py` comment | the packaged app had **no grammar tier at all**, whatever the user did about Java | bundled |
| `language-tool-python` **commented out in requirements.txt** | root cause of the whole silent-tier saga | now a real dependency |
| `requests` dependency chain not bundled — no `certifi`, `urllib3`, `charset_normalizer` | LanguageTool's 259 MB download would have failed for every tester with a cold cache, while working here because ours is warm | all bundled; verified TLS chain reaches languagetool.org with HTTP 200 from the bundle's own `certifi` |
| `/ping` returned **`"rules": 0`** | taskpane status line read "0 rules" until the first check — a regression from the W0 rewire, which removed server.py's eager rule imports | `api.ensure_rules_loaded()`; `/rules` had it too |

The `RequestsDependencyWarning` still printed by the built app is a py2app
import-timing artifact, not a defect: the same bundled `charset_normalizer`
imports fine (3.4.9) once the path is set up, and LanguageTool is fetched as
a binary stream that never uses charset detection.

### GUI-launch verification (the P17 caveat, closed)

A Finder-launched `.app` gets launchd's minimal environment — no shell rc,
no Homebrew on PATH, no `JAVA_HOME`. Reproduced exactly with
`env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin`: `find_java()` still located the
JDK, `ensure_java_on_path()` made `which("java")` resolve to it, and
`api.analyze` returned LT001 fixes. The built app was then launched for real
in that same stripped environment — "engine ready", no crash. Pinned by
`test_jdk_found_with_a_finder_launch_environment`.

### Shipped

- **`shipping/Researchly-WordAddin-v0.8.zip`** (104 KB) — built by a new
  `word-addin/ship_zip.sh` that copies the engine from source, **asserts
  every required module is present**, and runs an import smoke test before
  zipping. The v0.7 package was assembled by hand, which is exactly how it
  came to ship a three-module-stale engine.
- **`shipping/Researchly-macOS-v0.8.zip`** (~65 MB) — `.dmg` + guides.
- Both carry `1-START-HERE.md` (a numbered, step-by-step tester walkthrough
  with expected output at each step) and `2-ABOUT.md`.

**Fresh-unzip test**, run as a tester would: server started, `/ping` → 37
rules, `/check` returned LT001 + W201 + W202 + S001 with all three tiers on
and the coverage block populated.

Suite **205 → 213 passed**.

---

## 2026-08-11 — P18: the grammar tier's first measurement, and its first tuning

P17 made LT001 able to run. This entry is what happened when it did — the
tier had never once executed in the project's life, so nothing about its
behaviour had ever been measured.

**It immediately failed the project's own standard.** The accepted-thesis
noise floor went 10.4 -> **16.4 flags/1000w**, past the ~11 at which this
project re-tunes rather than ships. LT001 alone contributed 1,713 flags to
*accepted* PhD theses.

Characterising them found one dominant cause: **`UPPERCASE_SENTENCE_START`
was 39.7% of LT001's flags on theses and 26.4% on AESW's editor-approved
published prose** — the noisiest rule on both corpora. Scientific sentences
legitimately begin with a symbol, variable, gene name or unit
("$R_0$ exceeds one", "log-normal priors were used"), and PDF extraction
manufactures more by splitting sentences mid-clause.

Added to `SKIP_TYPO_RULES`, with four siblings that misfire the same way:
`EN_UNPAIRED_QUOTES` / `EN_UNPAIRED_BRACKETS` (numeric citations, interval
notation), `DASH_RULE` (en-dashed year ranges, 2003—2012), `GERMAN_QUOTES`
(reference lists).

| | grammar dead | grammar live | after tuning |
|---|---|---|---|
| thesis noise floor | 10.4 | 16.4 ✗ | **12.5** |
| LT001 flags there | 0 | 1,713 | 592 (−65%) |
| AESW recall at edit site | 13.0% | 15.7% | **15.3%** |

**65% of the noise removed for 0.4pp of recall** — exactly the trade F0.5
weights for. Pinned by tests; suite 208 -> **210 passed**.

A second finding worth keeping: LT001 costs 6.0 flags/1000w on PDF-extracted
theses but only 3.1 on clean published prose. Most of that gap is extraction
damage, not the rule. `dogfooding-report.md:133` already called PDFs hostile
input; this is the number behind it, and it means the thesis corpus
systematically overstates the grammar tier's noise.

**15.3% is now the honest recall figure**, measured with every tier running.
That is the bar a local GEC tagger has to clear to justify itself in W3.

---

## 2026-08-14 — P19: W2 sprint — actionable surfaces, GEC scaffold, ArgumentObject

Executed in a cloud working copy delivered back as `Researchly_Updated_14082026/`
(the user asked for a dedicated directory; the original tree is untouched).
Ten sprint items from the user's Fable-5 execution brief, in order. One
standing user decision recorded up front: **if a capability would ever need a
cloud AI API and no local model can do it, drop the capability — the GEC tier
stays an abstaining scaffold rather than ever calling out.**

### 1–2 · Word add-in: settings truly shared, five-tab pane

The taskpane still kept muted rules in browser localStorage — the /config
backend existed since W0 but nothing called it. Now: mutes/unmutes go through
`/config` (optimistic UI, confirmed by the response), a one-time
`migrateLocalStorageMutes()` moves legacy mutes into the shared config then
deletes the key, and `test_word_addin.py` pins `localStorage.setItem` out of
the source forever. `/check` and `/polish` no longer send a `disabled`
override — the server resolves the shared config, so parity is structural.
The pane is reorganised into **Check | Review | Polish | Settings | Health**:
Review renders the reviewer's brief from a new `/review` endpoint (built from
the same Word paragraphs as /check, so style headings survive); Settings
edits every shared field (document type, volume, locale, preferences,
grammar/gec tiers, muted-rule chips); Health lists all tiers with reasons +
remedies and keeps the probe button.

### 3–4 · Windows: buttons that exist, and a bring-up protocol

The old panel told users "use the buttons below" — buttons that are an
AppKit view existing only in the macOS app. `panel_html.render_polish(...,
actions=True)` now renders Replace/Copy in the HTML, wired through a new
`rlAction()` bridge shim that routes to `window.pywebview.api.action(...)`
(Windows) or `window.webkit.messageHandlers.researchly` (macOS) and no-ops
without a bridge. `researchly_win.py` gained a full `JsApi.action()`
dispatcher (copy fix / dismiss / mute / add-to-dictionary / settings /
replace / copy), re-rendering state after each action, mutes via
`config.mute_rule` (the shared store), hotkeys overridable in desktop.json.
`docs/windows-smoke-checklist.md` is the ordered real-hardware protocol
(env → engine sanity → non-admin launch → capture per target app → panel
actions → settings → packaging), with the known follow-ups (UIA capture,
installer) explicitly out of scope for the first smoke.

### 5 · macOS: the check panel is actionable

WKWebView now has a `researchly` script-message handler; check results
render with per-suggestion **Copy fix / Dismiss / Mute rule / Add to
dictionary** buttons (same HTML as Windows — one renderer, two bridges).
Mute writes the shared config and clears every card of that rule. Added a
**Settings…** menu item (renders `panel_html.render_settings` — same page as
Windows), an **Open Accessibility settings** menu item (deep link to the
Privacy pane), a numbered first-run Accessibility walkthrough, and
configurable hotkeys (`desktop.json` `{"hotkeys": {"check": "r", "polish":
"p"}}`, ⌘⇧ fixed). D2 watch snapshots stay display-only deliberately (no
state to re-render behind the badge). pyobjc side is defensive throughout;
needs an on-device session to verify, like every AX change.

### 6 · Shared settings UI

`panel_html.render_settings(cfg, health, note)` is THE settings page for
both desktop apps; the Word Settings tab renders the same fields natively
against the same `/config`. Every control writes through
`config.with_overrides + save_user`. No surface keeps its own store;
`test_desktop_panel.py` pins the page and `test_word_addin.py` pins the
taskpane side.

### 7–8 · GEC scaffold behind a disabled flag, golden tests

`gec.py` (scaffold: `Edit`, `EditBackend`, `predict_edits`, confidence
threshold 0.8, `MAX_EDIT_CHARS` 40 as an anti-generation gate, no ML deps,
no downloads, never raises) + `rules_gec.py` (GEC001, tier="gec",
fix_safety="review", **opt-in**: only `[tiers] gec = true` runs it — None
means OFF for the learned tier, inverting the deterministic tiers' default
on purpose). Masked-span policy: an edit is dropped if masked≠original over
its span, and insertions at mask boundaries are dropped too. `health.py`
now distinguishes scaffold-missing / present-but-opt-in / ready(+model
version). 14 golden tests in `test_gec.py`: total abstention, opt-in
gating, threshold, crash-abstention, mask straddling, insertion boundaries,
oversized-edit refusal, model-version provenance in the message, GEC001
excluded from POLISH_RULES, and overlap resolution preferring S001/LT001
(explainable) over GEC — that ranking was observed live: LT001 caught the
test's agreement error first and outranked the fake GEC backend, exactly
as designed. **The bar a real model must clear remains 15.3% AESW edit-site
recall (P18).**

### 9–10 · ArgumentObject; review lens consumes it

`argument.py`: sentence-level role labelling (claim, evidence, warrant,
qualifier, limitation, rebuttal, background, method, result, contribution,
implication) by signal lexicons over the MASKED text (offsets = source
offsets; a citation key like `[@because2020]` can never be a warrant —
pinned by test). Roles assemble per section into `ArgumentObject` (the
Toulmin fields from the brief) with deterministic `missing_links`:
claim_without_warrant, claim_without_grounds,
evidence_without_interpretation, limitation_not_reflected_in_claim_strength,
contribution_unclear. Methods/Results are exempt from argumentative
demands (they narrate/report). **No rules registered, no analyze() output
change** — pinned by test. First consumer: `build_review` embeds
`summarize()` output and `render_review` prints an "argument structure"
block listing missing links; the Word /review endpoint and `researchly
review` both carry it. `label_sentence()` is the single swap point for a
future learned classifier. Abstract-lens conversion deferred (gradual, per
the sprint wording) — its move lexicons already overlap; unify when the
argument layer gets its second consumer.

### Fixed en route

- `pygls` 2.x broke the LSP (`LanguageServer` moved); the requirements pin
  `<2` was right and the env here had 2.x — reinstalling the pin fixed it.
  No code change needed.
- `test_jdk_found_with_a_finder_launch_environment` now skips off-macOS:
  on Linux `/usr/bin/java` is a real JDK, not Apple's stub, so the assert
  failed a healthy machine.
- `test_engine_layer` correction-tier test now includes GEC001 as a
  legitimate `tier="gec"` claimant.
- Panel escape test re-aimed at suggestion-derived markup (the page now
  legitimately carries the static bridge `<script>`).

### Measured / verified

- Suite **213 → 252 passed** (+39: 14 gec, 15 argument, 4 word, 6 panel),
  1 skip (the macOS-only JDK test, on Linux).
- Noise floor: unchanged by construction — GEC001 abstains and is opt-in;
  no deterministic rule changed; `test_argument.py` pins analyze() output
  unchanged. (Corpus re-run not repeated for this reason.)
- Live smoke: server `/ping` → 38 rules; `/review` renders the brief with
  the argument block; `/config` persisted mute + gec_tier to the TOML.
- Audits: every surface calls `api.analyze` (grep-verified); no network
  code anywhere in the engine beyond LanguageTool's own local-server
  download; `gec.py`/`argument.py` import no ML and no network; whole tree
  parses under Python 3.10 feature rules.

### Remaining risk

- macOS bridge (WKUserContentController handler) and menu additions are
  untested on hardware — needs the usual on-device session; failures
  degrade to display-only, not crashes.
- Windows remains an unrun scaffold; the smoke checklist is the next step.
- Word taskpane changes need the usual restart-server + Cmd-Q Word cycle
  before judging anything.
- The gec opt-in checkbox is visible in every settings surface while the
  tier can only abstain; health explains this, but testers may still ask.

---

## 2026-08-14 (later) — P20: standalone installers (macOS + Windows)

User request: both desktop apps must ship as standalone installers with
EVERY dependency inside — no Python, no Java, no first-run downloads for
the person installing.

### Engine: vendored-runtime discovery

`health.py` gains `vendor_dir()` / `bundled_java()` /
`bundled_languagetool()`. A standalone build carries a `vendor/` folder
(py2app: `Contents/Resources/vendor`, found via RESOURCEPATH; PyInstaller:
next to the exe or under `_internal/`, found via sys.frozen/_MEIPASS;
tests/overrides: env `RESEARCHLY_VENDOR`). `find_java()` now checks the
bundled JRE FIRST — it is the one runtime the build verified — but a
too-old bundled Java falls through to the system search rather than
killing the tier. `rules_grammar._apply_bundled_lt()` sets
`LTP_JAR_DIR_PATH` to the bundled LanguageTool before the wrapper starts
(never overriding a user-set value), so the 259 MB download never happens
on an installed build. Machines without a bundle behave exactly as before.
8 tests in `test_bundled_runtime.py` (fake vendor tree; no Java, no
network). Suite 252 → **260 passed**.

### Proven end-to-end in the build sandbox

Assembled a real vendor bundle (jlink JRE + cached LanguageTool-6.8),
pointed `RESEARCHLY_VENDOR` at it with JAVA_HOME unset and a bare PATH:
`find_java()` chose the bundled JRE, `LTP_JAR_DIR_PATH` landed on the
bundled LT, and LT001 returned `has → have` with the health line
"ready — local LanguageTool". **Found in the process: `jdk.httpserver` is
NOT in `java.se`, and LanguageTool's server is built on
`com.sun.net.httpserver` — a jlink image without that module dies at
startup with NoClassDefFoundError.** Both build scripts pin
`--add-modules java.se,jdk.httpserver,jdk.unsupported`.

### macOS — `desktop-mac/build_installer.sh`

vendor prep (reuse the build Mac's LT cache or download once via the
wrapper's own SHA256-verified path; jlink from the JDK `health.find_java()`
locates) → py2app → inject `vendor/` into Resources → **ad-hoc re-sign**
(modifying the bundle invalidates the signature; Apple Silicon refuses
unsigned code) → verify the artifact (files present, bundled java runs,
and the engine's own `vendor_dir()`/`find_java()` resolve the bundle under
a simulated RESOURCEPATH — the P18 "test the artifact" lesson) → build
BOTH `Researchly-0.8.dmg` (drag-install) and `Researchly-0.8.pkg`
(double-click installer, pkgbuild, /Applications). Flags: `--skip-jre`,
`--skip-lt`, `--dmg-only`, `--pkg-only`. Must be RUN ON THE MAC (py2app);
`build_app.sh` remains the small dev build.

### Windows — `desktop-win/build_installer.bat` + `installer.iss`

Same vendor prep (jlink; LT reused from cache or downloaded once) →
PyInstaller onedir with `--add-data vendor;vendor` plus
`--collect-all language_tool_python certifi` → artifact verification →
Inno Setup → `Output/Researchly-Setup-0.8.exe`. Installer decisions:
**per-user install** (`{localappdata}\Programs`, PrivilegesRequired=lowest
— no admin prompt, sidestepping the `keyboard`-library admin question for
install at least), optional start-at-login task, uninstall keeps
`~/.researchly` (shared with the other surfaces on purpose). Still
UNTESTED on real Windows like everything in desktop-win;
`windows-smoke-checklist.md` §6 now tests the Setup.exe FIRST, on a
machine with no Python and no Java, watching the network monitor to
confirm nothing downloads.

### Caveats recorded

- Neither installer can be built in this sandbox (py2app needs macOS,
  PyInstaller/Inno need Windows); what was proven here is the engine-side
  discovery end-to-end plus artifact-verification steps baked into the
  scripts.
- Artifacts are ad-hoc/unsigned: right-click-Open on macOS, SmartScreen
  "Run anyway" on Windows — same personal-sharing stance as P14; wider
  distribution needs Developer ID notarization / Authenticode.
- Bundle sizes: LT ~400 MB unpacked + JRE ~90 MB + spaCy stack — expect a
  ~350-450 MB compressed installer. `--skip-lt`/`--skip-jre` trade size
  for the no-download guarantee.

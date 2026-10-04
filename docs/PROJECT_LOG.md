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

---

## 2026-08-14 (later) — P21-EXP: the drafting guide (EXPERIMENT FORK)

**This tree is `Experiment_Researchly/` — a fork of the stable
`Researchly_Updated_14082026/` made at the user's request so the new
ideas cannot destabilise the shipped work.** Scope: Word add-in only.
The two ideas from the "how should a guidance layer work" discussion:
(1) a learned rhetorical-move classifier (encoder-style, non-generative),
(2) exemplar retrieval over accepted manuscripts. No generation anywhere;
the user does the writing.

### Idea 1 — move classifier (`researchly/moves.py`)

v0 = TF-IDF (word 1–2 grams, digits masked) + multinomial logistic
regression, trained by `experiments/train_moves.py` on **PubMed 20k RCT**
(Dernoncourt & Lee 2017; 180k labelled sentences; public benchmark).
Labels map onto the Belcher schema abstract_lens already uses
(BACKGROUND→background, OBJECTIVE→aim, METHODS→methods, RESULTS→findings,
CONCLUSIONS→significance). Artifact: **3.5 MB**, ships in
`researchly/data/models/` with meta.json provenance + metrics.md.

Measured (held-out, 30,135 sentences): **82.6% accuracy**; abstention
curve pinned in the artifact — CONFIDENCE_THRESHOLD 0.6 chosen from it
(84.5% coverage @ 88.3% accuracy). Known weakness, designed around:
OBJECTIVE recall is 0.55 (classic BACKGROUND/OBJECTIVE confusion), and
**"gap" has no labelled corpus at all** → the HYBRID labeller
(`guide.label_hybrid`) gives gap/aim/limitation to high-precision
lexicons and everything else to the model. `MoveClassifier` is the swap
point for a future SciBERT-class encoder; consumers never change.

### Idea 2 — exemplar retrieval (`researchly/exemplars.py`)

"Show me how accepted papers did it": JSONL index of real sentences,
each labelled with its move and citing its source document; queries rank
by TF-IDF cosine similarity to the user's draft section, with a
**max-2-per-source cap per query** (the user's explicit style-bias
concern: no single author's voice should dominate).

Corpus (user-directed, built this session): the 8 accepted theses
already in the repo **plus 12 published papers** — 9 fetched as PMC
open-access full text via PubMed (Prem 2017 contact matrices; Prem 2020
Wuhan; Endo 2020 overdispersion; Mishra 2021 Delta; Levin 2020 IFR;
Hozé 2021; Lefrancq 2021; two Alex Cook papers incl. a Bayesian VAR
dengue study) and 3 from user-provided PDFs (Dehning 2020 Science —
needed OCR, its embedded fonts had no Unicode maps; Monod 2021 Science;
Bouman 2024 PLOS Comp Biol Bayesian workflow). Flaxman 2020 Nature and
Davies 2020 Nat Med are NOT in PMC-OA and were skipped, not scraped.
Raw texts live in `experiments/corpus/` for rebuilds.

`experiments/build_exemplars.py` → **2,189 exemplars from 20 documents**
(all seven moves covered; model-labelled sentences admitted only at
p ≥ 0.75, stricter than the guide's own threshold). Index is plain
inspectable JSONL at `researchly/data/exemplars/exemplars.jsonl`.

### The guide (`researchly/guide.py` + Word surface)

`build_guide(document)`: per detected section, the hybrid move profile
vs `SECTION_EXPECTED` (intro: background+gap+aim; discussion:
significance+limitation; abstract: all six; etc.). Each missing move →
Pallas/Belcher fill-in frame + up to 3 cited exemplars ranked against
the section's own text. Word add-in gains a **Guide tab** (sixth) and
`/guide` endpoint. Payload carries model version/accuracy and corpus
stats so the UI can always say who spoke.

Verified live: intro with background+aim but no gap → guide reports
exactly that, with a topical dengue gap exemplar cited to a thesis.
Suite: 260 → **275 passed** (15 new in test_guide_experiment.py,
including: abstention on missing artifact, lexicon-over-model blind-spot
routing, retrieval-not-generation (every exemplar is a verbatim corpus
row), per-source cap, and api.analyze() output pinned unchanged by the
whole layer).

### Honest limitations (for the next session)

- Move labels come from RCT *abstracts*; full-text prose is out-of-domain
  — abstention absorbs some of this, but a proper eval on annotated
  full-text sections is the gate before merging into the stable tree.
- Exemplar labelling inherits classifier noise (e.g. a "we quantified…"
  sentence can read as aim); the corpus is inspectable JSONL precisely so
  bad exemplars can be audited and pruned.
- New runtime deps (scikit-learn, joblib) are in requirements.txt —
  installer/py2app implications NOT yet handled (this fork ships no
  installers; Word add-in runs from source, where pip deps are fine).
- Desktop surfaces deliberately untouched.

> *Merged into the root log on 2026-10-03 (S0). P19–P20 were written in
> `Researchly_Updated_14082026/` (now `legacy/updated-p20/`), P21-EXP in
> `Experiment_Researchly/` (now `legacy/experiment-p21/`). Paths inside these
> entries refer to those trees as they were at the time.*

## 2026-10-03 — P22: production architecture (prototype → hosted product)

**What.** The user decided to take Researchly from prototype to a hosted,
production app (Vercel), run "like a one-person company" with sub-agents as
specialist staff. Produced `ARCHITECTURE.md` (draft v1) and `PLAN.md` (the
shared checklist the user asked for, to be ticked as work lands).

**How.** Method taken from the user's *The Art of Building Software* (ch. 20–27):
purpose → measurable requirements → architecture proportional to the promise →
trace one action → claim-to-evidence table → thin slices. Three sub-agents
reported first: a codebase audit, a Laya identification, and hosting research.

**Findings worth keeping.**
- **Three diverging code trees.** The "canonical" `prototype/` is the oldest
  (P18). `Researchly_Updated_14082026/` (P20, 260 tests) is the proposed
  baseline. `Experiment_Researchly/` (P21-EXP, 275 tests) holds the only
  trained model. This root log was missing P19–P21.
- **The "local neural network" is partly a scaffold.** The GEC tagger has no
  model. The only trained model is a TF-IDF + logistic-regression move
  classifier: 82.6% on PubMed-RCT abstracts, never measured on thesis prose,
  and stored as a pickle.
- **Third-party exemplars ship today.** 70% of `exemplars.jsonl` (1,539 of
  2,189 sentences) comes from the 8 sample theses. That must not ship in a
  hosted product without the authors' permission.
- **Laya.** Most likely Convai Innovations' Laya: Apache-2.0, a
  ModernBERT-large decision model, the open alternative to TypeSafe's hosted
  Jev. It is non-generative, gives calibrated answers, can abstain, and can
  be fine-tuned on a Mac or Kaggle. But it is near chance zero-shot,
  ≈2 weeks old, has one maintainer, and does not do grammar. Decision: adopt
  only through a bake-off against a plain ModernBERT classifier (ADR-06, S5).
- **Vercel cannot run Java (LanguageTool)** and caps request bodies at
  4.5 MB. The engine therefore runs on Cloud Run with LanguageTool as a
  sidecar; Vercel hosts the web app and the Word taskpane (ADR-03).

**Decisions pending from the user.** D1–D8 in `PLAN.md`. The main one is D1,
the replacement wording for non-negotiable #2 ("Confidential by design").
CLAUDE.md now marks #2 as under revision.

**Files.** `ARCHITECTURE.md` (new), `PLAN.md` (new), `CLAUDE.md` (pointer +
#2 revision note), this entry.

**Addendum (same day): decisions recorded.** The user answered D1–D8:
- **D1:** "Confidential by design" approved as drafted; non-negotiable #2 in
  CLAUDE.md is amended.
- **D2:** free and non-commercial *for now*.
- **D3:** Singapore.
- **D4:** the `Researchly_Updated_14082026` tree is the baseline.
- **D5:** the desktop apps go to maintenance-only.
- **D6:** the theses are for private evaluation only.
- **D7:** `Notes_On_Writing/` is the knowledge source; papers and theses
  come later, through the dataset registry.
- **D8:** Laya is adopted only via the bake-off.

ARCHITECTURE.md is now v1.2. Slice S0 is unblocked.

## 2026-10-03 — P23: S0 Foundation (one repo, CI, licences, clean engine)

**What.** The first build slice of the production plan (PLAN.md S0). It
delivers no user-visible change: one repository, automated checks, and an
engine with no third-party text in it.

**Shipped:**
- **Monorepo (ADR-01, D4).** `Researchly_Updated_14082026` became the
  baseline:
  - engine → `packages/core/`;
  - Word add-in, VS Code extension and desktop apps → `apps/`;
  - `eval/` and `dogfood/` → `ml/`;
  - the other two trees → `legacy/`.

  All moves used `git mv`, so history follows. Test, server, build-script
  and VS Code paths were repointed. Result: 260 passed, 1 skipped, identical
  to before the move.
- **Spelling gaps.** Seven words from the first S001 corpus run were added,
  with a test that fails without them. While writing it I found that
  capitalised words are skipped as possible proper nouns. A test that puts
  the word at the start of a sentence would therefore pass for the wrong
  reason.
- **`ml/datasets.yaml`.** 41 sources, each with a licence, whether that
  licence was seen first-hand, and its permitted use under D2, D6 and D7.
- **`ml/tools/check_third_party.py`.** An 8-word shingle scan of
  `packages/`, `apps/` and `services/` against the theses, the paper corpus
  and Notes_On_Writing. It found **19 hits inside the engine**:
  - Pallas's exemplar abstract and frames;
  - Endo lecture quotes in why-texts;
  - thesis sentences used as test fixtures.

  All were replaced with paraphrases (attribution kept) or synthetic
  fixtures, and the scan now reports 0 hits. Rule logic was proven unchanged
  by comparing each module's syntax tree with strings blanked.
- **CI** (`.github/workflows/`). Four jobs on every PR:
  - ruff (bug-class rules only);
  - engine tests on Python 3.10 with Java 21;
  - the third-party scan;
  - gitleaks (clean over the full history).

  A separate, path-filtered noise-floor workflow runs on engine changes.

**Measured: the real noise floor.**

| Tiers on | flags/1000 words |
|---|---|
| All | **14.84** |
| All except S001 (spelling) | 12.5 |
| All except LT001 (grammar) | 12.8 |

The "12.5" quoted in P18 excluded S001, so the all-tier figure had never
been written down. The target (Q3) is ≤ 11.

`noise_gate.py` fails on a rise of more than 0.3, and also when a rule that
fired at least 20 times drops to zero. A quieter run is how a dead tier
looks. I found this by testing the gate against a run without LanguageTool:
the first version passed it.

**Lessons:**
- Licence audits find things code review doesn't. Course and book wording
  had crept into rule explanations and test fixtures one quote at a time.
- Some old fixtures passed for the wrong reason:
  - C301's hedges were outside the window, so the clause-boundary guard was
    never reached.
  - E703's fixture followed a short sentence, so the noun check never ran.

  Swapping in synthetic fixtures exposed both. Both tests are now stricter.

**Open (PLAN.md Inbox):**
- reach Q3;
- 20 cosmetic lint findings;
- the GPL-3.0 LanguageTool client before any desktop bundle;
- `docs/eval-corpora.md` licence corrections;
- PubMed-RCT's undeclared licence;
- the Pallas year (2022 vs 2023);
- two scanned PDFs the scan can't read;
- `_to_delete/` (owner).

**Addendum (same day): product direction.** The owner answered P1–P5.

| # | Decision |
|---|---|
| P1 | Coach alongside existing tools: a web revision studio plus add-ins, with a Draft / Revise mode |
| P2 | Consistency checks and reporting checklists ship in v1 |
| P3 | Epidemiology is the first discipline pack |
| P4 | Structural checks only for figures, tables and equations |
| P5 | Responsive web plus add-ins; no native apps |

The owner also raised the defining question: "why use Researchly when one
already has LLMs or Grammarly?" ARCHITECTURE.md §1.3 now answers it as
claims an LLM or Grammarly structurally can't make:
- allowed (it never writes);
- confidential;
- sourced;
- consistent;
- section- and discipline-aware;
- teaches;
- whole-document.

Each claim has an evidence row, including an S6 comparison study. The
lesson: an origin story ("built from a professor's notes") is not a moat,
because anyone can paste a style guide into a chatbot. The moat is the set
of promises a generative tool cannot keep. New slice S2b covers the
consistency and structure checks.

## 2026-10-03 — P24: S1 Engine online (code complete; deploy waits on the owner)

**What.** The hosted engine and the web page that calls it, built as a small
team:
- I wrote the contract first.
- A backend agent and a frontend agent built in parallel against it.
- A designer agent did a second pass using the owner's UI/UX skills.
- I integrated, reviewed, tested end to end and wrote the deployment.

**Shipped (PR amriitmohapatra/Researchly#1):**
- **Contract v1.**
  - Pydantic models are exported to OpenAPI, and the TypeScript types are
    generated from that.
  - CI fails on drift. The check caught a real drift before regeneration.
  - Units are documented: offsets are Unicode code points; the passive
    share is 0–1. Every error code is documented, with a test that parses
    the code.
- **Engine service** (`services/engine`).
  - Stateless FastAPI. Each request builds its own in-memory config and
    never reads `~/.researchly`.
  - One engine lock, matched by Cloud Run concurrency 1.
  - Rate limit, body cap (8 MiB, so a valid 1M-character document in
    four-byte characters fits), allow-listed CORS, JSON logs that never
    contain text.
  - LanguageTool runs as a sidecar.
  - No-Java image, non-root, built from an allow-list `.dockerignore`.
- **Q6 canary test** (release-blocking). It found a real leak: a failed log
  write printed a traceback containing the document. Fixed, with a
  regression test.
- **Web page** (`apps/web`, Next.js 16).
  - Highlights, cards, why and source.
  - Per-request nonce CSP.
  - A lint-time boundary check that no server code ever receives text.
  - Code-point to UTF-16 offset conversion, tested with emoji.
  - Redesigned with the owner's design skills; passed the anti-ui-slop
    finish gate.
- **Deployment.**
  - `bootstrap-gcp.sh`: Workload Identity Federation, so no keys.
  - A manual `deploy-engine.yml`: deploy by digest, smoke test.
  - `docs/deploy.md` for the steps only the owner can do.
- **CI** now also runs the service tests, the contract, the web suite
  (lint, typecheck, unit, e2e) and an engine-image privacy-and-boot check.

**Found by doing it for real:**
- **Mocked tests can't find content bugs.** The first run of the web page
  against the real engine and LanguageTool showed two:
  - sources rendered as bare "§4";
  - "the the" flagged twice (LanguageTool plus W207).

  Both are fixed in the engine. `sources.py` expands codes into full
  citations and fails at import on an unknown code. LanguageTool rules that
  W207 already covers are skipped. The noise floor went from 14.84 to 14.75.
- **Briefs must name the owner's skills.** The first web page was built
  without the installed design skills because the brief didn't name them.
  ARCHITECTURE.md §14 now lists the skills per role.
- **A copy-detection scan must ignore numbers.** Page numbers in a thesis
  matched version lists in `package-lock.json`. Shingles now need at least
  5 words with letters, and the scan covers only files git tracks or would
  track.
- **The security review** (security-review skill) found no vulnerabilities
  at its bar. It flagged one logic bug: the public health endpoint probed
  LanguageTool on every hit. Fixed.

**Measured, locally (not Cloud Run):**

| Request | p95 | Target |
|---|---|---|
| 311-word paragraph | 309 ms | 800 ms |
| 10k-word chapter | 4.68 s | 6 s |

The chapter time is about half spaCy and half LanguageTool, run one after
the other; running them in parallel is in the Inbox. A 1M-character request
takes 74 s and 2.8 GiB.

**Waiting on the owner:** `docs/deploy.md` steps 1–6 (GCP project, bootstrap,
repository variables, Vercel, first deploy). After that, the latency
measurements on the real deployment and the S1 exit check.

## 2026-10-03 (later) — P25: S1 live — deployed, measured, and what the live check found

**What:** the owner deployed the engine (Cloud Run, Singapore, with the
LanguageTool sidecar) and the web app (Vercel, `researchly-chi.vercel.app`)
by following `docs/deploy.md`. Claude then checked the live site end to end
and measured it.

**Evidence:**
- Live headless-Chromium run against the production alias: HTTP 200,
  suggestions rendered, no console or CSP errors. The owner confirmed it in
  their own browser.
- Parity: the live engine and the local engine returned the same 63
  suggestions on a synthetic 10,316-word chapter.
- Latency (`bench.py --url`, warm, measured from Claude's cloud sandbox):

| Request | Engine time (p50) | Wall time from sandbox (p95) | Target |
|---|---|---|---|
| 311-word paragraph | 484 ms | 2.02 s | 800 ms |
| 10,228-word chapter | 6.89 s | 9.35 s | 6 s |

  The paragraph meets Q1 on engine time; wall time includes about 1.4 s of
  network from the sandbox and needs re-measuring from Singapore. The
  chapter misses Q2 even on engine time. The same chapter took 4.68 s in the
  local container, so the Cloud Run instance is slower (probably CPU; not
  yet profiled). Running spaCy and LanguageTool in
  parallel is now an S1 task, not an Inbox idea.

**Deployment snags the owner hit (now in `docs/deploy.md`):**
- `apps/web` was missing from Vercel's Root Directory picker until the PR
  was merged; setting it afterwards under Settings worked.
- A `NEXT_PUBLIC_` variable saved as Secret can't be changed to Config;
  delete and re-add it.
- A **Preview** redeploy doesn't move the stable address, and its own
  address is refused by the engine's origin allow-list. Redeploy (or
  promote) to **Production**.
- The first build used the Cloud Run console's older-style engine address;
  the page couldn't reach the engine until it used the deploy Summary's URL.

**Fixed from the live check (4187ded):**
- **The reading key taught false categories.** It showed "seven day window"
  as a Convention (no rule flags it) and "utilize" as a Preference (W201
  calls it an Improvement). The specimens now live in
  `packages/contract/reading-key.json`, exported to the web app as
  `READING_KEY`, and `packages/core/tests/test_reading_key.py` runs each one
  through `api.analyze` and checks the exact span gets the stated category.
  New specimens: "proven" (C302) and "very" (W204). The test also caught
  that "In order to fit the model" on its own reads as a heading and is
  skipped, so the specimen became a full sentence.
- The "Could not reach the checking engine" message now names the engine
  host it tried, which would have diagnosed the stale-URL build at once.
- `bench.py --n-chapter 0` crashed on NaN; a 0 count now skips that size.

**Lessons:**
- **Anything the UI teaches about the engine needs a test against the
  engine.** The key's examples were written from memory of the rules, and
  two of four were wrong. Shared data plus an engine-side test makes the
  drift a red build.
- **Error messages should carry the one fact that separates causes.** A
  wrong build-time address and a dropped connection looked identical.

**Open:** Q2 latency on Cloud Run; the owner's real-chapter exit check
(paste a chapter on the live site, compare with the CLI).

## 2026-10-03 (later) — P26: S2 accounts, files and settings sync (code complete; Supabase waits on the owner)

**What:** the owner chose to defer the Q2 speed-up and start S2. The lead
wrote `docs/s2-design.md`, fixed the API contract first, and ran three
engineers in parallel in isolated worktrees (file adapters, database,
web), building the engine's sign-in and upload route alongside them.
Every branch was reviewed, re-tested and merged by the lead.

**Decisions (s2-design.md):**
- Two tables only (`user_settings`, `dictionary_words`). `profiles`,
  usage and feedback tables wait for a feature that reads them.
- The engine verifies Supabase tokens itself (JWKS; RS256/ES256 pinned to
  the key) and reads settings through PostgREST **with the caller's own
  token**. It holds no secret key, and refuses to start if given one.
- Uploads are raw bytes on `/v1/analyze-file`: multipart would spool files
  over 1 MB to disk. The filename travels in a header (URLs get logged) and
  is never logged.
- With no Supabase configured, engine and site behave exactly as in S1.

**Evidence:**
- Core 475 tests (adapters: LaTeX 106, zip 38, docx 37, with seeded random
  offset round trips and hostile inputs: zip bombs, traversal, symlinks,
  XXE, billion laughs).
- Engine service 145 (tokens and settings 39, uploads 20, three new canary
  scenarios: filename, uploaded text, adapter warnings, token and user id
  never reach a log).
- Database 90 on Postgres 16 with a Supabase shim; all 19 deliberate
  weakenings of the migration caught (re-run by the lead), and a race test
  that sees the lost-update bug it guards against.
- Web 152 unit + 59 e2e in two builds (with and without accounts); axe
  clean in light and dark; screenshots at 375 and 1280 px.
- The web's per-file line numbers match the real `.zip` adapter on 12,910
  offsets of 60 random projects.

**Found and fixed during integration:**
- A filename with an invalid `%`-escape crashed the upload route (500);
  now a 422, with a test.
- The deploy workflow first accepted legacy `eyJ…` keys, which would also
  accept the service-role key (same shape) and bypass RLS. Now only
  `sb_publishable_…` keys pass, in the workflow and in the engine.
- Muting from two tabs at once lost a change (read-modify-write of the
  whole list). `mute_rule` / `unmute_rule` change one rule under the row
  lock.
- LaTeX parse fallback on pasted text was silent; `warnings` is now in
  every response.

**Lessons:**
- **Contract first made parallel work possible.** Three engineers built
  against the same committed shapes; the only integration change was one
  field added after the fact (`warnings`), announced to the web engineer
  before it finished.
- **Ask what a test can see.** The database suite was mutation-tested and
  the race test was run against the old behaviour to prove it fails. A
  green test that cannot fail is decoration.
- **A key's shape is not its permission.** Validation by prefix
  (`sb_publishable_`) is what keeps the RLS-bypassing key out.

**Waiting on the owner:** `docs/deploy.md` step 8 (Supabase project,
migration, URL settings, two variables), then the S2 exit check.

**Addendum (P26, merge):** amriitmohapatra/Researchly#2 merged on
2026-10-03 with all 11 checks green. The first CI run caught one real test
bug: `test_each_user_sees_only_their_own_rows` expected dictionary words in
byte order ("Stan" before "brms"), which the local C-collation cluster used
and CI's en_US Postgres does not. Isolation itself passed. Reproduced
locally with an ICU en-US database, fixed to compare as sets (c975bec).
Lesson: a test that sorts text inherits the server's collation; compare
sets unless order is the point.

## 2026-10-03 (later) — P27: accounts live; large-file pre-flight

**What:** the owner completed `docs/deploy.md` step 8 and confirmed sign-in
and sign-out work. Testing sign-in repeatedly hit Supabase's built-in email
limit (about 2 emails an hour for the whole project): expected, and the
reason real users need a custom email sender (S6). Staying signed in avoids
it, since the session refreshes without email.

**Verified on the live engine:** an anonymous upload and a 1,600-word
anonymous paste are refused with `sign_in_required`; a forged token gets
`unauthorized`; a short anonymous paste still works; every tier is ready
and the file readers are installed (no `files` tier). Probing the Supabase
project itself from Claude's sandbox was blocked by the sandbox's network
policy (`*.supabase.co` not allow-listed); tracked in PLAN.

**Large `.tex` pre-flight** (synthetic LaTeX, grammar on, this machine):

| Words | Time | Peak memory |
|---|---|---|
| 25k | 21 s | 0.6 GB |
| 65k | 44 s | 1.3 GB |
| 120k (whole thesis) | 74 s | 2.1 GB |

Cloud Run ran ~1.5× slower than local in S1, so a whole thesis takes about
110 s there. Memory is comfortable under 4 GB; the response is ~9 MB even
for synthetic word salad (real prose flags far less).

**Found and fixed:** the browser gave up after 120 s while the engine is
allowed 300 s, so a whole thesis would have been abandoned just before it
finished. The browser now waits 290 s; a unit test reads the Cloud Run
spec and keeps the two in step. The file panel says a whole thesis can
take about two minutes.

**Lesson:** a timeout has two ends. When one side's limit is raised for a
new workload (uploads), check the other side's.

## 2026-10-03 (later) — P28: precision fixes from the owner's first real `.tex`

**What:** the owner shared a real 167 KB `.tex` methods report (16,600
prose words, 190 uses of a custom `\code` macro) to test uploads. It was
checked in memory only and is not in the repository; tests use synthetic
sentences. It parsed cleanly in 0.6 s and analysed in ~13 s locally. The
flags exposed bugs no corpus could: the noise-floor corpus is plain text.

**Found and fixed (172 → 117 flags; 9.9 → 6.6 per 1,000 prose words):**
- **Masked maths made words adjacent.** "and $C(0)$ and" was a doubled
  word (all 4 W207 flags); "An $\exp(1)$ prior", "a $90\%$ interval",
  "Student-$t$ rather" drew a/an and spacing errors (about half of the
  LanguageTool flags). `Document.touches_masked()` now tells LT001 and W207
  when their evidence crosses blanked maths, citations or code, across a
  wrapped line but not a paragraph break, and never counting headings.
- **Code read as prose.** `\texttt`, `\path`, `\addcontentsline` and any
  preamble macro defined as a wrapper around code formatting (`\newcommand
  {\code}[1]{\texttt{#1}}`) are now masked.
- **Hyphenated prefixes** ("mis-ordered" → "mis") and **prefixed real words**
  ("unstratified", "uncited", "autoregression") are no longer spelling
  errors; the stem must be a dictionary word as written. Two regressions the
  suite and a corpus review caught on the way: "mispeled" ("mis" + "pele" +
  "d") and "crosssectional" (tripled letter) — both flagged again.
- **Lexicon gaps:** decadal, simplices, programmatically, macOS,
  parameterise/-ize families, hospitalise/-ize, softmax, treedepth,
  walltime, hardcoded, equidispersion and others.
- **F601:** labels with a number attached (BA.1, XBB.1.5, AR(2)) are not
  undefined acronyms.

**Evidence:** 26 new tests (fire and don't-fire); all 17 don't-fire tests
fail on the pre-fix code. Core 502 passed. Noise floor 14.75 → 14.51
(S001 676 → 611), baseline updated with a note; every newly accepted corpus
word was reviewed by hand.

**Not fixed, tracked in PLAN:** section inheritance for nested headings,
a document-type default for methods reports, and LanguageTool's own
misreads on technical prose.

**Lesson:** the corpus measures the plain-text path only. One real LaTeX
document found more LaTeX bugs in ten minutes than the suite had; every
format needs a real-document check, not just synthetic fixtures.

**Addendum (P28, same day):** the real-document bench (P29) caught a
regression in this fix before merge. The first `touches_masked` counted
*every* masked character, so `\emph{`, `\textbf{` and Markdown `**`
silenced real errors beside them ("an \emph{large} increase" was no longer
flagged; on two eLife articles with italic gene names LT001 fell from 135
to 12). `Document.atoms` now records only the masked spans that stood for
a word (maths, citations, references, code, URLs, Word equations), filled
by each reader; the guard checks those. Five new tests fail on the first
version and pass now; the owner's `.tex` result is unchanged (117 flags).
Lesson: "masked" is not one thing. Formatting is masked because it is
noise; maths is masked because it is content we cannot read.

## 2026-10-03 (later) — P29: the real-document test bench

**What:** the owner has no Word or LaTeX files to test with and asked for
automated checking against real articles found with the PubMed and bioRxiv
connectors, web search and GitHub. Two engineers worked in parallel: a
corpus builder (manifest + licences) and a QA engineer (the bench).

**Corpus (`ml/realdocs/manifest.yaml`, 208 documents, metadata only):**
115 PMC Open Access articles in 9 disciplines (34 infectious-disease
epidemiology), 20 PMC articles with native `.docx` supplements, 14
medRxiv/bioRxiv preprints, 18 LaTeX manuscripts on GitHub, 41 Word
robustness files (Apache POI, LibreOffice, python-docx, mammoth.js). Every
licence was seen first-hand per item (PubMed copyright status, bioRxiv
licence field, repository LICENSE at a pinned commit). arXiv was left out:
its per-paper licences could not be verified from this sandbox. 27 hits
showing only "© The Author(s)" were dropped.

**Bench (`ml/realdocs/`, `.github/workflows/realdocs.yml`):** fetches at
run time (never into the repo), renders each JATS article three ways
(plain, a real .docx, a .tex) so format parity exposes reader bugs, and
checks invariants on every document: masked length, segment round-trip,
span bounds and text, no span on masked markup, no file/network/process
access while reading (an audit hook; covers the XXE probe), no crash or
hang. Reports carry no text; snippets go only to the CI artifact and only
for openly licensed items.

**What real documents found (all fixed, each with a regression test):**
- **A regression in my own P28 fix**, before it merged: masked formatting
  (`\emph{`, `**`) counted as material between words and silenced real
  errors. Fixed in PR #3 with `Document.atoms` (b512393).
- A 17 KB Word file with 400 nested tables crashed the reader
  (RecursionError): depth cap + clean refusal.
- Spans on markup: G106 started at `\documentclass`, G104 ended inside
  `\cite{}` or was reversed, AB802 highlighted `\begin{a`. Rules fixed, and
  `engine._trim_to_prose` now trims any span off masked blanks centrally
  (headings exempt: D902 points at them on purpose).
- `\vskip .5em`, `\kern 3pt`: brace-less dimensions read as prose.
- Overleaf projects with a cover letter beside the manuscript were refused;
  the adapter now chooses (side documents never win; most `\input`s, then
  longest) and says which file it checked.
- pandoc/knitr code blocks (`Shaded`/`Highlighting`) broke the parser for
  whole R Markdown papers; glossary/theorem definitions and algorithmic
  pseudo-code leaked as prose ("MTHM MTHM" as a doubled word).
- On a parse failure the reader now tries pylatexenc's lenient mode and
  keeps it only if it recovers ≥ 80% of the words (it kept 99% where it
  worked and 19–57% where it swallowed text); otherwise the regex reader,
  which now masks code too.

**Evidence:** local bench on the 59 GitHub-hosted documents: FAIL (1
crash, 21 span violations in 11 projects, 2 refusals) → **PASS**; LaTeX
19.4 → 16.2 flags/1000w (engineering 38 → 18). Core 525 passed, service
145, bench 26; noise floor unchanged at 14.51 (plain text is unaffected).
The 149 PMC/preprint items can only be fetched in GitHub Actions: their
first run follows the merge.

**Lessons:**
- **Real documents beat imagined ones.** One evening of 59 real files
  found eleven reader bugs that 500 synthetic tests had not.
- **A bench must check itself.** The first local run of the bench caught
  my own regression in an unmerged PR; the invariants (no span on markup)
  are what made it visible, not the flag counts.

**Addendum (P29, first full CI run):** run 37136223549 (1 h 47 min) passed
on all 208 manifest items it could fetch: 115 PMC articles × 3 renderings
(2.25M words), 74 Word supplements, 17 LaTeX projects, 41 robustness files;
6 refusals all expected. Only 3 of 14 preprints were fetched (the preprint
servers refuse automated downloads). Format parity holds on average
(docx −0.44, tex −0.34 flags/1000w against plain). Published PLOS/eLife
articles run at ~16 flags/1000w — no better than the theses — so Q3
(≤ 11) must be tuned against published prose too, not only theses.

**Addendum (P28/P29 merged, 2026-10-04):** amriitmohapatra/Researchly#3
merged to main as 91e1c19, green on every check including the full
real-document run. The fixes reach the live engine when the owner runs
**Deploy engine**; the branch was restarted from main for the next work.

## P30 — 2026-10-04 — Nested headings; preprints through PMC

**Context.** The owner deployed the engine (live check: BA.1 and AR(2) are
no longer flagged; every tier healthy) and said to go ahead with the next
steps: section inheritance, false-flag tuning (Q3), and the preprints.

**Nested headings inherit their parent's section.** P28's methods report
and P29's format-parity gap had one cause: every heading reset the
section, so "Priors" under Methods became "other" and passive-voice advice
meant for Discussion fired in Methods. Plain text hid it because the
plain-text detector only keeps headings with a section word.
- `Heading.level` comes from the markup: LaTeX command depth (`\chapter` 0,
  `\section` 1 … `\subparagraph` 5), Markdown hashes, Word heading styles
  ("Heading 2", the add-in's "Heading2") and, in `.docx`, a custom style's
  outline level. Plain-text headings, the abstract environment and a Word
  Title have none and stand alone, as before.
- `document.resolve_sections()`: a nested heading inherits when it has no
  section word, or when its parent is a plain section name ("Results"), so
  "Model fit" under Results stays Results. A nested heading that is itself
  a section name ("Limitations" under Discussion) keeps its own, and under
  a topical title ("A model of measles transmission") a nested heading's
  own keyword counts. `Heading.keyword` keeps the heading's own class.
- D902 and AB802 now read the whole Introduction / Abstract, subsections
  included, instead of stopping at the first subheading.

**Evidence.** 23 tests in `test_section_nesting.py` (9 fail on the old
code; the 3 that pass are the "unchanged" cases). Core 548, service 145,
bench 26, ruff clean. Noise floor unchanged at 14.51 (plain text). Bench on
the 59 GitHub documents, same cache, main vs this change: PASS both;
G104 51 → 48, and rules limited to some sections fire where those sections
are now recognised (C302 16 → 28, C303 31 → 35); 16.90 → 17.02 flags/1000w.
The +12 C302 are "we prove" in a maths paper's Introduction, which used to
be "other" after its first `\paragraph`: the sections are right, and the
rule's misfire on proofs is now a Q3 item.

**Preprints through PMC.** medRxiv/bioRxiv refused 11 of 14 downloads in
Actions. None of the 14 has a PMC copy, but NIH-funded preprints are
deposited in PMC (NIH Preprint Pilot). PubMed search for preprints on
transmission/epidemiology with free full text; licences read with
`get_copyright_status`; of 40 checked, the 10 CC BY and 1 CC0 were added
(5 infectious-disease epidemiology, 6 biology) as `pmcpreprint-*`, fetched
through Europe PMC like the other 115 articles. Registry entry
`realdocs-pmc-preprints`; method in `ml/realdocs/SOURCES.md`.

**Lessons.**
- A clean before/after needs the same documents on both sides: the
  previous local bench output came from an older engine, so the
  comparison here re-ran main from a worktree on the same cache.
- Recognising more of the document's structure can raise the flag count:
  section-limited rules start to see their sections. Read the new flags
  before calling it a regression.

## P31 — 2026-10-04 — Q3 precision tune: 14.51 → 11.94

**Context.** Next step after P30: bring the thesis noise floor towards Q3
(≤ 11 flags/1000w). Every flag on the 8-thesis corpus was dumped to the
session scratchpad (never committed) and read rule by rule; the owner's own
methods report was re-checked in memory for LanguageTool's misreads.

**Principle.** Remove wrong flags; never hide good advice to reach the
number. A rule or guard changed only where most of its hits were wrong.

**What changed** (each with fire and don't-fire tests, 37 in
`tests/test_q3_precision.py` and `tests/test_rules.py`; the new
don't-fire tests fail on the old code):
- **LT001 566 → 295.** Skipped LanguageTool rules that misread scientific
  prose: the compound-spelling family (`EN_COMPOUNDS_*`, `MAKER_COMPOUNDS`:
  "policy makers", "sub-tropical", "Viet Nam" — 75 hits, house style not
  grammar), `NON_STANDARD_WORD` (67/67 on maths or R code),
  `THE_SUPERLATIVE` (37/39 "least squares"), `NUMBERS_IN_WORDS`,
  `POSSESSIVE_APOSTROPHE`, `I_LOWERCASE`, `THE_PUNCT`, `EN_SPECIFIC_CASE`,
  `ADMIT_ENJOY_VB`. All 11 LT001 flags on the owner's report were misreads;
  4 were compounds. a/an, between…to, comprises of and agreement still fire.
- **G101 779 → 559.** A comma between list items, or brackets holding a
  citation or a short abbreviation, is not an interruption; a restrictive
  clause, participle or bare apposition is part of the subject and needs a
  15-word gap. The 158 flags this dropped were read: ordinary long subjects.
- **S001 611 → 415.** 103 correct words added to the scientific lexicon
  (pediatric, fomites, sylvatic, licensure, a priori, in vitro…); an
  author's name before initials or "et al" is not a typo. Real misspellings
  in the corpus ("subsceptible", "prevalnce") are still caught (tested).
- **C303 138 → 114.** "Cases increased" describes a change; only "X
  increased Y" or a passive claims a cause. The small parser reads
  "Vaccination reduced transmission" as an adjective, which is handled.
- **F601 243 → 220.** Roman numerals, journal names, GDP/UV/ROC/AUC.
- **C302.** "prove" in a sentence with maths or proof vocabulary (bench:
  28 → 6, the Busy Beaver paper from P30).
- **Reference lists are masked** (a "References"/"Bibliography" heading in
  plain text, Markdown or Word): Word reference lists are ordinary
  paragraphs and every rule used to run over them. A table cell reading
  "References" masks nothing (tested). Bench: 8,909 words of reference
  lists no longer checked, 4,055 of them one pandoc `CSLReferences` list.
- G106's one-line description said "over 40 words"; it fires over 50.

**Evidence.** Noise floor 14.51 → **11.94** (gate OK, baseline updated with
a note). Real-document bench (59 GitHub documents): PASS, 17.02 → 14.99
flags/1000w. Core 597 passed, service 145, bench 26, ruff clean,
third-party scan 0 hits (after rewriting test sentences, below).

**What is left (PLAN Q3 item).** ~90% of the remaining S001 flags are PDF
extraction artefacts: `pdftotext` drops every line-break hyphen
("laboratoryconfirmed") and page-break hyphenation leaves fragments. A
trial re-extraction gives 11.3 (old code 13.7), but adds 16k words whose
origin has not been read, so the gate's corpus is unchanged for now. G106
and G101 are now mostly real advice.

**Lessons.**
- The third-party scan caught a test sentence of mine that copied 12 words
  of a thesis sentence I had just read in the flag dump. Reading real flags
  is necessary; writing tests from them invites paraphrase. Every test
  sentence modelled on a corpus example was rewritten as clearly synthetic.
- A measurement can be wrong in the same direction as the product: half of
  the "spelling noise" was the PDF extractor, not the checker. Measure old
  and new code on both corpora before changing the ruler.

**Addendum (P30/P31 merged, 2026-10-04):** amriitmohapatra/Researchly#4
merged to main with all 12 checks green. The full real-document run
(37183107815, 32 min) passed: all 11 PMC preprints fetched and passed every
invariant, though 7 came back abstract-only (PLAN follow-up). The fixes reach
the live engine when the owner runs **Deploy engine**.

## P32 — 2026-10-04 — S2b: structure and consistency checks

**Context.** The owner deployed the P30/P31 engine and asked to go ahead
with S2b (P2 consistency checks, P4 structural checks for figures, tables
and equations). Mid-way the owner also asked to plan a demo manuscript with
deliberate errors and a launch video (PLAN Inbox).

**What was built.**
- `researchly/structure.py`: floats (figure/table, number, label, caption,
  appendix) and mentions. The LaTeX reader now records `\ref`s (also
  preamble macros such as `\fig{x}` -> `fig:x`, and style macros like
  `\figref` it cannot see) and every `\label`; `from_word` records Word
  captions, so the add-in and an uploaded file agree. Ranges
  (`\ref{a}--\ref{c}`), `\captionof`, `\caption*`, panel captions, chapter
  numbering and appendices are handled. Internal `ref`/`label` items are not
  returned by the service (the contract lists five public kinds).
- Rules (Layer 8 in `docs/rule-inventory.md`): X101 uncited float, X102
  out of order, X103 broken reference, X104 placed before first citation
  (Word), X202 short caption, X301 unreferenced numbered equation
  (Preference), X401 number not in the cited table, F612 abbreviation
  defined twice, F613 defined but barely used (Preference), N101 unit
  spacing mixed, N102 sentence opens with a numeral, W211 compound spelled
  two ways. Sources: ICMJE, BIPM SI Brochure, AMA Manual of Style, guide
  §6/§9.1/§9.2/§9.7 (knowledge-base §10).
- `engine.load_rules()` is the one list of rule modules: `api` kept its own
  and missed the new module (health reported 38 of 42 rules).

**Evidence.**
- 76 new tests; core 672+ passed, service 146, ruff clean.
- Real LaTeX projects (17): the first version raised 120 structural
  flags, most wrong; each wrong pattern became a fix and a don't-fire test
  (labels in align/algorithm, `\fig{x}` macros, style `\figref`, ranges,
  panel captions, `\caption*`, appendix floats, captions citing other
  floats); 14 remain and those read are genuine (uncited figures in a
  tutorial paper, tables cited out of order in a replication study).
- X203 (caption abbreviation undefined) was tried and dropped: 79 flags,
  nearly all product names, formulae and initials.
- Noise floor 11.94 → 12.65 on purpose (+204 flags from the consistency
  rules). Judged sample of 45: W211 nearly all correct, N101 5/5, N102 ~9/12,
  F612 ~8/14 before two more guards (reference entries, panel letters).
  Baseline updated with a note; the structural rules do not run on the
  plain-text corpus.
- Local bench (59 GitHub documents): PASS.

**Open.** Tense per section (no named source), concept-level terminology
drift, missing captions, equation symbols: deferred in PLAN. The PMC
articles' docx/tex renderings (CI) are the real precision test for X1xx:
published articles cite every figure in order.

**Lessons.**
- A structural check is only as good as the cross-reference model under
  it: nearly every first-version false flag was the model missing a way
  authors write references, not the rule being wrong.
- Two lists of the same thing drift: the rule-module list existed twice
  and the second copy silently left the new module out.


## P33 — 2026-10-04 — The deliberately bad manuscript: PDF-converted Word

**What.** The owner sent "a deliberately bad version of a manuscript": a
published economics working paper (48k words) run through a PDF-to-Word
converter. Checked in memory only; never committed, not quoted. It held
every artefact a conversion leaves: headings run into their first
paragraph (a 475-word "Heading 1"), table rows styled as headings, tables
as columns aligned with spaces, displayed equations flattened to symbols
and one-letter variables, words hyphenated across lines, captions typed in
body style, appendix floats lettered "Table A.4". Researchly raised 604
flags; most were about the conversion, and the Introduction was masked
whole because it carried a heading style.

**Fixes (engine, all surfaces).**
- Run-in headings (`document.split_run_in`): a heading-styled paragraph of
  more than 25 words is body text. A numbered heading is split off at the
  capitalised word before the first lower-case content word ("2 Methods |
  We fitted …"); the rest is checked as prose. New rule **X501**
  (Correction, Word, source: Word heading styles) says so.
- A document that uses heading styles no longer also gets keyword-guessed
  headings ("Fit statistics" in a table re-sectioned the appendix).
  "C Data Appendix" is an appendix, not Methods; a column-aligned line is
  never a plain-text heading.
- Layout lines (`document.layout_spans`, plain text and Word): a line with
  a four-space column gap, or with a relation sign and mostly maths tokens,
  is masked and kept as an atom. URLs and e-mail addresses are masked.
- **A blank line ends a sentence** (`api.paragraph_breaks`, a spaCy
  component in the shared pipeline) unless the next line carries on in
  lower case. The first version split every blank line and hid real long
  sentences in PDF-extracted theses, where a page break leaves a blank line
  mid-sentence ("about 70% of\n\nall cases"); diffing every G106 flag
  before/after caught it.
- S001 joins a word broken across a line ("effec-\ntive" → one finding,
  "effective") and never joins across a masked line.
- W207 skips aligned columns, single letters (maths) and runs ("Yes Yes
  Yes"); W201 leaves the nouns "leverage" and "endeavour" (it is a
  bulk-safe fix: "financial use" would have been applied unread); G107
  says a repeated noun stack once, with its count; F601 skips titles set
  in capitals; LanguageTool's diacritics suggestions ("numéraire") are
  skipped; 47 statistics/economics words added (winsorized, equilibria,
  premia, transformative …).
- Structure: captions typed in a body style ("Table 2: …"), on a line of
  their own inside a paragraph, or run into a paragraph (X103 checks the
  text before calling a figure missing); lettered appendix numbers
  ("Table A.4", stored as a chapter above any real one, shown as "A.4");
  "(continued)" captions are the same table.
- `ml/dogfood/run_dogfood.py` and the LSP now use `api.get_nlp()`: both
  loaded spaCy themselves, so the gate would not have seen the sentence
  change at all (it first reported 12.40 when the engine gave 11.67).

**Evidence.**
- The manuscript: 604 → 409 flags. What remains is mostly real: words the
  conversion ran together ("firmlevel", "softwareintensive"), apostrophes
  split from a variable ("firm j ’s"), 15 X501, inconsistent spellings
  (non-missing/nonmissing, scatter plot/scatterplot, down-weight/
  downweight, non-zero/nonzero), CRSP defined twice, and Figure 2 placed
  before the text first cites it (X104). 34 floats found (4 main text, 30
  appendix); the first structural pass reported "Figure C.2" and "Table
  C.4" missing, but their captions were run into paragraphs — now read.
- Noise floor 12.65 → **11.67** (baseline updated with a note): G106
  648 → 529, G101 559 → 482, G107 −20, S001 −19, LT001 −16, W207 −14,
  F601 −12; G105 +8 (real "There is" openings once inside a merge). Every
  removed W207/W203/F601/W201 flag was read: all wrong (maths "N n", URLs,
  title pages, "this endeavour").
- Real-document bench: PASS, 14.65 → 13.69/1000w; LaTeX G106 187 → 119,
  each removed flag a "sentence" through an `enumerate`, code listing,
  heading or display equation.
- 35 new tests (`test_converted_documents.py`); core 703+ passed, service
  146, ml 30, ruff clean, third-party scan 0 hits.

**Lessons.**
- A converted PDF is the normal case, not an edge case: students convert
  published papers and old chapters to Word all the time. The engine must
  read layout as layout.
- Every runner must use the one pipeline. A measurement tool that loads
  its own spaCy measures a different product.
- A blank line means different things in a Word file (a paragraph) and a
  PDF extraction (sometimes a page break): decide with the next line, and
  diff before trusting a big drop.

**Addendum (same day): the published-article run.** CI run 37190315670
(cfddd47, before P33) read 547 files, 2.79M words, PASS. The new "S2b by
format" table showed three noisy rules on 140 PMC articles, where a
published article should get almost none. The sandbox cannot fetch PMC or
download the artifact, so each was reproduced on synthetic JATS through
the bench's own converter:
- X401 369 in the Word rendering vs 24 in TeX. A table caption claimed the
  *nearest* cells by distance; with every table at the end of the article,
  Table 2's caption is as close to Table 1's cells as to its own, and the
  tie went to Table 1. An image-only table took the next table's cells.
  Now a caption claims the nearest unclaimed table with no other caption
  between, preferring the one below it.
- X202 74/82: short table titles. ICMJE asks tables for "a short or an
  abbreviated heading"; only a figure caption must stand on its own, so
  X202 now judges figures only.
- X301 373 in TeX: the converter rendered every JATS formula as a numbered
  `equation` and the text cites them by typing "Eq. (3)". X301 now counts
  typed references against the numbers LaTeX prints (rows of an `align`,
  less `\nonumber`); the converter numbers only formulas with a `<label>`.
Each fix has a test that fails on the old code (one passed by luck at
first — the wrong table held no "%", so the percentage was never judged —
and was rewritten with decimals). Core 717 passed, service 146, ml 30,
noise floor unchanged at 11.67, local bench PASS.

**Addendum 2: the rerun.** Run 37194170115 (710436f) PASS, 14.54/1000w
overall (15.41 before P33). X401 Word 369 → 24, equal to TeX; X202 74/82 →
35/40, all figure captions under five words (the converter keeps the
caption's title and paragraphs, so these are short in the article itself);
X301 373 → 249 (a hidden Preference). One regression: X104 fired 33 times
on the native .docx set (supplements of 20 PMC articles), 0 before — typed
captions now count, and a supplement puts every table before the sentence
citing it. X104 now judges captions made with Word's caption style only;
list-of-figures entries (dot leaders, page numbers, TOC styles) are not
captions; a typed caption repeated later is one float. The owner's
manuscript loses its one X104 (a typed caption): 409 → 408. Lesson: a
heuristic input (typed captions) is fine for rules that only stay silent
on it (X103) and risky for rules that fire on it (X104).

**Addendum 3: confirmed.** Run 37197496673 (73c7d5a) PASS: X104 on the
supplement .docx files 33 → 0; X401 24/24, X202 35/40, X301 248
unchanged. Open: X101 16, X102 12, X103 12 per rendering and X104 11 in
the Word rendering of published articles (~1 per 10 articles); judging
them needs the run's samples, which this sandbox cannot download.

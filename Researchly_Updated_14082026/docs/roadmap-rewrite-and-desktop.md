# Researchly Roadmap — Rewriting Without LLMs & the Desktop App

*2026-08-10 · Follows the dogfooding report and v0.2 (telemetry + LSP).
Decisions this phase: rewriting must not depend on LLMs; the desktop goal
is the full Grammarly-style overlay.*

---

## 1. Verification: how Grammarly Desktop actually works

Your findings are accurate. Grammarly for Windows/Mac is a standalone
desktop app (installed via `GrammarlyInstaller.exe` on Windows, a .dmg-style
installer on Mac) that runs at the operating-system level and shows a
floating widget over active applications, with per-app on/off control.

The mechanism matters for our planning: it reads text from other apps via
the OS **accessibility APIs** (AXUIElement on macOS, UI Automation on
Windows) and draws its underlines in separate transparent overlay windows
positioned above the target app. Three consequences (from our Phase-1
research, incl. Grammarly's own engineering retrospectives and support
docs):

1. It requires **per-application special-casing** — Grammarly's own docs
   list apps where it fails or needs workarounds, and a dedicated team
   maintains that compatibility matrix.
2. Browsers and Electron apps mostly do NOT expose their text content
   through accessibility APIs at the granularity needed — which is why
   Grammarly *also* ships a browser extension and Word add-in; the desktop
   app is not actually one universal mechanism.
3. Underline *positioning* needs the target app to answer "where on screen
   is character range X?" (`AXBoundsForRange`) — many apps refuse or lie.

This is why the plan below reaches the overlay in stages that each deliver
value, rather than attempting Grammarly-parity in one jump.

## 2. Rewriting without LLMs — what shipped today (v0.3 "Polish")

**The deterministic rewrite engine** (`researchly/transform.py`) composes
every safe, rule-derived edit into a one-click rewrite of a selected
sentence or paragraph:

- Applies: plain-word substitutions, wordy-phrase compression, filler
  deletion (with re-capitalization), redundant pairs, doubled words,
  buried actions — now grammatically conjugated in place ("performed an
  estimation of the rate" → "estimated the rate"), and expletive-opener
  restructuring ("There are three factors that drive X" → "Three factors
  drive X").
- **Cascades to a fixpoint**: one edit can expose another ("It is important
  to note that there are three factors that drive transmission." →
  "Three factors drive transmission." — two rules composing).
- Output is a **word-level diff plus a per-edit ledger**: every change
  names its rule and the guide's reasoning. This is the structural
  advantage of the no-LLM choice: the rewrite is reproducible, explainable,
  and *cannot invent content* — it is incapable of touching equations,
  citations, numbers, or terminology because edits only ever occur on
  spans a named rule matched (and markup is masked besides).
- Judgment calls (passive voice, hedge selection, causal wording, sentence
  splits) are deliberately NOT auto-applied — they surface as flags,
  because the guide's own position is that they depend on what belongs in
  the topic position, which is the author's call.
- Surfaces: **Word add-in** ("Polish selection" → diff view → insert as
  tracked change) and **CLI** (`researchly polish`). The LSP already
  offers per-edit quick-fixes.

**The honest ceiling, stated plainly:** deterministic rules can compress,
repair, and restructure — they cannot *paraphrase*. Grammarly-Pro-style
"rewrite this sentence fluently in different words" and free-form tone
transformation are generative tasks; no rule system can do them. If that
gap ever matters, the middle path (documented, not built) is a **small
local neural editor** (e.g. CoEdIT, a 770M fine-tuned T5 — runs offline,
free, no API, no chat; NC license already accepted for personal use).
Technically it is a small language model, so whether it honors the
"no LLMs" decision is your call to make later — nothing in today's
architecture blocks adding it as another polish backend.

## 3. Grammarly Pro feature map → Researchly equivalents

| Grammarly Pro | Researchly path | Status |
|---|---|---|
| Rewrite full sentences with a click | Polish (deterministic, explainable) | **shipped today** |
| Adjust writing tone | Register layer: contraction expansion, formality substitutions, hedge/assertiveness dial built on C301/C302/C305 machinery | partial (flags today; dial = next) |
| Write fluently in English | Rule pack + Polish; commodity grammar (agreement/articles) deliberately delegated — optional LanguageTool/Harper integration slot exists in the orchestrator design | partial by design |
| Unlimited personalized suggestions | Local telemetry (`researchly stats`) → keep-rate-driven attenuation; later: personal style profile learned from your accepted theses corpus | foundation shipped (v0.2) |

## 4. Desktop app plan (the overlay, staged)

Target: installable app — **.dmg (macOS first, your machine), then .exe
(Windows)**. Each stage is a working product; each later stage adds overlay
depth. Python core reused throughout (the engine is the asset; the shell
changes).

**Stage D1 — Menu-bar app + universal hotkey (the reliable foundation).**
macOS menu-bar icon (pyobjc/AppKit) hosting the engine in-process; a global
hotkey reads the current selection from ANY app (via the accessibility
selected-text attribute, clipboard fallback), opens a floating panel with
check results + Polish diff, and writes the result back. Works in Word,
browsers, email, Overleaf — because selection reading is the one
accessibility feature nearly everything supports. Packaged with py2app →
`Researchly.app` → `.dmg` (unsigned; first launch via right-click → Open;
signing/notarization only needed if distributing to others).

**Stage D2 — Live watcher + caret-anchored panel.** Track the focused text
element (`AXFocusedUIElement` + value-change notifications), re-check
quietly as you type, show a Grammarly-style floating badge near the field
with the suggestion count; click opens the panel. Per-app allow/deny list
(Grammarly's own control, worth copying). Works in native apps (Word,
Mail, TextEdit); browsers degrade to Stage-D1 behaviour.

**Stage D3 — True underlines.** For apps that answer `AXBoundsForRange`
(Word and native text views largely do), draw a transparent click-through
overlay window with underlines at character positions; hover → suggestion
card. This is the Grammarly-parity stage, and also where per-app breakage
lives — scoped last deliberately, on the foundation of D1/D2 which already
deliver the workflow everywhere.

**Windows (.exe)** follows the same stages via UI Automation + pywin32,
packaged with PyInstaller. Sequenced after the macOS app is proven on your
machine, since you can't test Windows locally.

**Engineering realities to hold onto:** (1) accessibility permission must
be granted once in System Settings → Privacy & Security → Accessibility;
(2) the AX layer cannot be tested in the cloud sandbox — D1 will be built
here, but its first run happens on your Mac with us debugging together;
(3) browsers/Electron will never do D3 — the Word add-in and (future)
browser extension remain the right tools there, exactly as Grammarly's own
architecture concedes.

## 5. Sequencing proposal

1. **Now (shipped):** Polish engine + Word/CLI surfaces + G102 grammar fix.
2. **Next session:** Stage D1 menu-bar app — buildable in one session,
   testable on your Mac the same day, and immediately useful everywhere.
3. Then: tone/register dial (rule-based), Stage D2 watcher.
4. Then: Stage D3 underline overlay for Word/native apps; Windows port;
   optional local neural editor decision.

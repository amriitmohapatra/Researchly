# Checking on this computer (local mode)

Researchly can check a draft without sending it anywhere (ADR-02: "a local
mode that sends nothing anywhere remains available"). This page says, for
each local route, what it checks and what, if anything, it contacts over
the network (Codex review #11, 2026-10-15).

Each route describes itself from the same settings and engine health its
checks run on (`packages/core/researchly/capabilities.py`), so the
description cannot drift from what runs: switch grammar off and every
route's description says so. `packages/core/tests/test_capabilities.py`
checks each description against what the route actually runs, including
that a full local check opens no connection beyond this computer.

## What each route checks

| Route | How it is reached | Writing rules | Spelling | Grammar | Whole-document checks | Reviewer's brief and map |
|---|---|---|---|---|---|---|
| Word, **This computer** | Word pane → Settings → This computer; `apps/word-addin/server.py` on `localhost:3517` (`/v1/analyze-word`) | yes | yes | yes, if Java 17+ | yes (Revise mode) | yes (Revise mode) |
| Word's live underlines, **This computer** | the same server, `/v1/check-paragraphs` | yes (sentence-level) | yes | yes | no: they need the whole document, so they come with Check document | no |
| Desktop overlays, **This computer** (macOS, Windows) | `127.0.0.1:3517/v1/check-paragraphs`, the same server | yes (sentence-level) | yes | yes | no (live check) | no |
| VS Code / Positron extension | `researchly.lsp` over stdio, started by the editor | yes | yes | yes | yes (unless Draft mode) | no |
| Command line | `python3.10 -m researchly check FILE` | yes | yes | yes | yes (unless `--mode draft`) | `review`, `narrative`, `abstract` commands |

"Grammar" is LanguageTool, run by Researchly on this computer (a Java
process listening on localhost only). It needs Java 17 or newer; without it
every route says grammar is off and why, and the other checks still run.
Learned corrections (`gec`) are opt-in and ship without a model, so no route
runs them today.

## What each route contacts

| What | When | Is your text sent? |
|---|---|---|
| Nothing beyond this computer | every check, by default, on every route above | no |
| The local server on `localhost:3517` | Word's and the overlays' "This computer" | the text goes from the Word pane or overlay to that server, on this computer only |
| LanguageTool's download site | once, before the first grammar check, if LanguageTool is not yet on this computer (about 200 MB) | no |
| A LanguageTool server you name in `RESEARCHLY_LT_URL` | every check, only if you set it | yes, to that server (when it is `localhost`, it stays on this computer) |
| The Researchly website | the Word pane's page itself is loaded from it; signed in, your muted rules are read from your account | no |

## Where to see it

- **Word pane**: Settings → Checking engine → This computer shows one line,
  read from the local server: "This computer checks writing rules,
  spelling, grammar and whole-document checks, and builds the reviewer's
  brief and the map. It sends nothing over the network." A tier that is off
  is named, with the reason.
- **`/v1/health`** on the local server (and on the hosted engine) carries
  `capabilities`: the checks with on/off and why, and the network contacts
  (`packages/contract`, `Capabilities`).
- **Editor extension**: the Researchly output channel logs the same line on
  start; the `researchly.capabilities` command returns it as data.
- **`researchly doctor`**: the installation health check.

## Installation health check

```bash
cd packages/core
python3.10 -m researchly doctor          # --json for machine-readable output
```

One line per dependency, with what was found and the fix when something is
wrong: Python version, spaCy and its `en_core_web_sm` model, the SymSpell
dictionary, the LaTeX and `.docx` readers, Java and LanguageTool (or the
LanguageTool server named in `RESEARCHLY_LT_URL`, asked with a fixed
synthetic sentence), the editor extension's language server, the settings
file, and whether `server.py` is running on port 3517 (`--port` for
another). It ends with the line above. It exits 1 when something every
check needs is missing (Python, spaCy or its model, SymSpell), else 0. It
reads no document text and contacts nothing but `127.0.0.1` (and the
LanguageTool server you named, if any).

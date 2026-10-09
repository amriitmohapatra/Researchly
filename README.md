# Researchly

A writing coach for research students: Grammarly-style checks, plus advice
on narrative, logical flow and argument. Every suggestion explains *why* and
cites where the advice comes from. Researchly never writes for you.

## Why Researchly

You spend months on a manuscript, alone or with a team, and send it for
peer review. The decision comes back: one reviewer lists your grammar
mistakes, another says a key section is hard to follow. Neither comment is
about your science.

Researchly does not take the reviewer's place, and it is not a domain
expert. Reviewers still judge the science. Researchly reads the draft before
they do and helps you present the work clearly, so reviewers can spend their
time on your science rather than your sentences.

- **Same draft, same advice.** With the same settings, the same text gets
  the same feedback: the checks are written rules, not a generative model.
- **A source for every suggestion.** Each flag says what was noticed, why it
  matters in plain words, and where the advice comes from.
- **No cloud or generative AI reads your draft.** The text is processed in
  memory for one request by Researchly's own engine and then dropped. A
  local mode that sends nothing anywhere is available for the Word add-in.
- **It never writes for you.** No drafting, rewriting or paraphrasing, so it
  fits where generative AI is restricted.
- **Its noise is measured.** How often it flags accepted theses and
  published articles is tracked (`ml/dogfood`, `ml/realdocs`) as a proxy
  for false alarms; precision from labelled paragraphs is being added.

Researchly is for early-career researchers and for anyone writing in English
as a second language. It teaches the conventions of research writing while
you write, and it encourages you to do the writing yourself.

## What it does

**Checks on the draft**
- **Suggestions, each explained.** Grammar, spelling, word choice, sentence
  clarity, tone and claims. Each is marked as a Correction, Improvement,
  Convention or Preference, says why in plain words, and names its source.
- **Section-aware advice.** Headings such as Methods and Discussion change
  what is flagged: passive voice is expected in Methods.
- **Whole-document consistency.** Figures and tables cited and in order,
  captions, abbreviations defined once, numbers in the text found in the
  table they cite, equations punctuated as part of a sentence, and terms
  used the same way throughout.
- **Grammar and spelling tiers.** An open-source LanguageTool run alongside
  Researchly's own engine, and a spelling tier with a scientific word list
  and your own dictionary. A tier that is off says so; none fails silently.

**Reading the whole paper** (in Revise mode)
- **Reviewer's brief.** The questions a critical reader asks, each answered
  with what was detected and the sentences it rests on, or marked as not
  assessed.
- **Narrative map.** For each section, the moves a reader expects (for
  example the gap and the aim in an Introduction), marked present, missing
  or out of order, with a question and a frame to fill in. The words stay
  yours.
- **Reporting checklists.** STROBE, CONSORT, PRISMA and EPIFORGE items,
  each "reported" with your sentence or "needs your check". They check
  reporting, never the science.

**Learning as you write**
- **Lessons.** 26 short lessons, each with a before-and-after example and a
  habit to keep, linked from every suggestion.
- **Progress, if you opt in.** Per-rule trends across your checks, stored as
  counts only, never text.

**How you work with it**
- **Draft and Revise.** Draft checks what you have written so far; Revise
  checks the finished manuscript as a whole.
- **Check as.** Research article, thesis chapter, abstract, commentary,
  policy brief, grant proposal or response to reviewers, or a guess from the
  headings that shows what it rests on.
- **Files.** Paste text, or upload Word (.docx), LaTeX (.tex or an Overleaf
  .zip), Markdown, Quarto or R Markdown.
- **Print or save as PDF.** The document with its highlights numbered and
  the suggestions beside them, then the brief and the map, made in your
  browser.
- **Optional account.** Muted rules, your dictionary and your settings
  follow you between the website and Word.

**Where it runs**
- The website, the Word add-in (hosted, or with a local engine that sends
  nothing anywhere), the command line, and a language server for VS Code
  and Positron (preview).

**Private repository.** It contains third-party theses and course material
for evaluation, so it is never made public. The public copy,
`amriitmohapatra/researchly-public`, is generated from it by
`tools/public-export/` (see its README).

| Start here | |
|---|---|
| `ARCHITECTURE.md` | What we're building, how it fits together, and why |
| `PLAN.md` | The shared checklist: what's done, what's next |
| `docs/PROJECT_LOG.md` | The full build history |
| `CLAUDE.md` / `AGENTS.md` | Rules for anyone (human or AI) working here |

| Folder | Contents |
|---|---|
| `packages/core/` | The engine (`researchly` Python package) and its tests |
| `packages/contract/` | The API contract (OpenAPI and TypeScript types), and the Learn cards as JSON |
| `apps/web/` | The website and the hosted Word taskpane (Next.js) |
| `apps/` (other) | Word add-in manifests and local server, VS Code extension; macOS/Windows apps (maintenance-only) |
| `services/` | The hosted engine service (FastAPI on Cloud Run, LanguageTool sidecar) |
| `supabase/` | Migrations for optional accounts and their two-user tests |
| `demo/` | The made-up demo paper with 17 planted mistakes |
| `media/` | The launch video and its poster |
| `ml/` | Dataset licence registry, noise-floor corpus run, evaluation harnesses |
| `tools/public-export/` | Generates the public repository and gates what it may contain |
| `legacy/` | Read-only copies of the three prototype trees, for reference |

Run the engine's tests:

```bash
cd packages/core
pip install -r requirements.txt && python -m spacy download en_core_web_sm
python3.10 -m pytest tests/ -q
```

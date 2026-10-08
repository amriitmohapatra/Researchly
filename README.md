# Researchly

A writing coach for research students: Grammarly-style checks, plus advice
on narrative, logical flow and argument. Every suggestion explains *why* and
cites where the advice comes from. Researchly never writes for you.

## Why Researchly

Feedback on scientific writing usually arrives late, after a draft has gone
to a supervisor or a reviewer, and no two readers give the same advice. The
tools that exist either check grammar or write the text for you. Researchly
does neither: it reads the whole draft, shows what a careful reader would
notice, and leaves every change to you.

- **The same answer every time.** The engine is deterministic rules, not a
  language model, so a draft checked twice gets the same feedback twice.
- **A source for every suggestion.** Each flag says what was noticed, why it
  matters and where the advice comes from, so you can judge it rather than
  take it on trust.
- **No AI model reads your draft.** Text is processed in memory for one
  request and then dropped, and a local mode that sends nothing anywhere
  remains available.
- **It never writes for you.** There is no drafting, rewriting or
  paraphrasing, which is what makes it usable where generative AI is
  restricted.
- **A measured false-flag rate.** The checks are run against accepted theses
  and published articles, and how often they flag good writing is tracked in
  this repository (`ml/dogfood`, `ml/realdocs`), so the noise is measured
  rather than guessed.
- **Exact checks across the whole draft.** Every figure and table cited,
  every abbreviation defined once, numbers in the text matching the table,
  and advice that changes with the section, since the passive voice in
  Methods is not a fault.

Researchly is for early-career researchers and for anyone writing in English
as a second language. It teaches the conventions of research writing while
you write, and it encourages you to do the writing yourself.

**Private repository.** It contains third-party theses and course material
for evaluation; see `CLAUDE.md` before ever making it public.

| Start here | |
|---|---|
| `ARCHITECTURE.md` | What we're building, how it fits together, and why |
| `PLAN.md` | The shared checklist: what's done, what's next |
| `docs/PROJECT_LOG.md` | The full build history |
| `CLAUDE.md` / `AGENTS.md` | Rules for anyone (human or AI) working here |

| Folder | Contents |
|---|---|
| `packages/core/` | The engine (`researchly` Python package) and its tests |
| `apps/` | Word add-in, VS Code extension; macOS/Windows apps (maintenance-only) |
| `services/` | The hosted engine service (from slice S1) |
| `ml/` | Dataset licence registry, noise-floor corpus run, evaluation harnesses |
| `legacy/` | Read-only copies of the three prototype trees, for reference |

Run the engine's tests:

```bash
cd packages/core
pip install -r requirements.txt && python -m spacy download en_core_web_sm
python3.10 -m pytest tests/ -q
```

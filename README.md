# Researchly

A writing coach for research students: Grammarly-style checks, plus advice
on narrative, logical flow and argument. Every suggestion explains *why* and
cites where the advice comes from. Researchly never writes for you.

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

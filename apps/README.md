# apps/

Surfaces. Each one calls the engine's `api.analyze()`; none keeps its own
settings or pipeline (CLAUDE.md, "How to work here").

| App | Status |
|---|---|
| `word-addin/` | Active. Talks to a local server today; re-hosted over HTTPS in PLAN.md S3 |
| `vscode-extension/` | Active, untested by the owner. LSP client; `dist/` is the pre-built bundle |
| `desktop-mac/` | **Maintenance-only** (D5). Fix breakage; no new features |
| `desktop-win/` | **Maintenance-only** (D5). Untested scaffold |
| `desktop-overlay-mac/` | New (PLAN S4d R7, ADR-10). Swift/AppKit overlay: underlines in any app through Accessibility; calls the engine's live check. The owner builds it with `build.sh`; core tests run on Linux too |
| `web/` | Arrives in PLAN.md S1 (Next.js on Vercel) |

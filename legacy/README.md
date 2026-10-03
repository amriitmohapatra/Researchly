# legacy/ — read-only

The three prototype trees that existed before the monorepo (PLAN.md S0,
ARCHITECTURE.md ADR-01). Kept for reference and history; **do not edit or
import from here**. Live code is in `packages/`, `apps/`, `ml/`.

| Folder | Was | State |
|---|---|---|
| `prototype-v0.8/` | `prototype/` | v0.8 through P18 (oldest). Its dogfood corpus text moved to `ml/dogfood/` and its VS Code bundle to `apps/vscode-extension/dist/`. |
| `updated-p20/` | `Researchly_Updated_14082026/` | The baseline (D4). Its code moved to `packages/core` and `apps/`; only its docs remain here. |
| `experiment-p21/` | `Experiment_Researchly/` | The P21 drafting-guide fork: move classifier (`move_clf.joblib`), `guide.py`, `exemplars.py`. Re-enters the engine only through PLAN.md S4/S5 and the ADR-06 promotion gate. **70% of its exemplar index is thesis text — never ship it.** |

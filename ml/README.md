# ml/

Offline only — nothing here runs on the request path (ARCHITECTURE.md §5.7).

| Path | Purpose |
|---|---|
| `datasets.yaml` | Licence registry. **Nothing trained on or derived from a source ships unless its `permitted_use` includes `ship_model` / `ship_text`.** |
| `dogfood/` | Noise-floor run over the 8 accepted theses (`text/` is third-party, private). `noise_gate.py` compares a run with `baseline.json`; CI runs it on engine changes. |
| `eval/` | AESW precision/recall harness (`eval/data/` is gitignored; AESW is CC BY-NC-SA). |
| `tools/check_third_party.py` | CI scan: fails if thesis, course or book passages appear in `packages/`, `apps/` or `services/`. |

Noise floor:

```bash
cd ml/dogfood
RESEARCHLY_CORPUS_OUT=/tmp/nf python3.10 run_dogfood.py
python3.10 noise_gate.py /tmp/nf/corpus_stats.json            # compare
python3.10 noise_gate.py /tmp/nf/corpus_stats.json --update --note "why"   # accept a new baseline
```

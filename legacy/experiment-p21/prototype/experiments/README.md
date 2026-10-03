# experiments/ — the drafting-guide layer (Experiment_Researchly fork)

- `train_moves.py`      — reproduce the move classifier (needs the public
                          PubMed RCT corpus; see its docstring)
- `build_exemplars.py`  — rebuild the exemplar index from
                          `../dogfood/text/` + `corpus/` (or your folders)
- `corpus/`             — published papers as plain text (PMC OA fetches
                          + user-provided PDFs; first two lines = title
                          and attribution)

Artifacts land in `../researchly/data/{models,exemplars}/`. The Word
add-in's Guide tab consumes them via `researchly/guide.py`.

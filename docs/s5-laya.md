# S5 — Laya: facts, harness and first measurements

2026-10-15. Owner decision: "For S5, let's stick to Laya for now (as its open
source and free)." ModernBERT and Jev are set aside (ARCHITECTURE.md ADR-06,
amendment of 2026-10-15). This page records what Laya is, as read from its
own sources on that date, what was built around it, and what ran here.

## 1. What Laya is (verified at the source, 2026-10-15)

| | |
|---|---|
| Maker | Convai Innovations (maintainer Nandakishor M). One maintainer; the Hub repo was created 2026-09-18. |
| Model | [huggingface.co/convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya). Three checkpoints in one repo: English (root; ModernBERT-large + decision head, 421M parameters, 512 tokens), `typed-decisions/` (same backbone fine-tuned on a typed-decisions benchmark, 1,024 tokens), `multilingual/` (mmBERT-base, 322M, 1,024 tokens, up to 8,192). |
| Licence | **Apache-2.0**, seen in three places: the repository's [LICENSE](https://raw.githubusercontent.com/NandhaKishorM/laya/main/LICENSE) ("Apache License, Version 2.0"); the Hub model card's own licence field ([API](https://huggingface.co/api/models/convaiinnovations/laya): `cardData.license: apache-2.0`, tag `license:apache-2.0`; README front matter `license: apache-2.0`); and the PyPI package metadata ([laya 0.4.8](https://pypi.org/project/laya/): license `Apache-2.0`, author Convai Innovations). The earlier registry entry could not check the Hub card (huggingface.co was blocked in the 2026-10-03 audit); it is now checked. |
| Pinned here | revision `7b928d828b7b0e022f929d9bd2e44165aa270148` (last modified 2026-10-03); `model.safetensors` 842,609,210 bytes, SHA-256 `891102d3…cbc8d86c` (the Hub's LFS oid). |
| Code | [github.com/NandhaKishorM/laya](https://github.com/NandhaKishorM/laya); docs at [nandhakishorm.github.io/laya](https://nandhakishorm.github.io/laya/). |
| Package | `pip install laya` (0.4.8, uploaded 2026-10-15; Python ≥ 3.10; needs torch ≥ 2.0 and transformers ≥ 4.48; extras `[onnx]`, `[serve]`, …). |
| What it does | Reads a *state* (text) and *typed questions* and returns probabilities in one forward pass: `choice` (one of named options), `score` (an ordinal level), `noul` (yes/no probability). Each option is scored at its own `[MASK]` marker, so the options are defined at request time. **It cannot generate text** (no decoder). |
| Abstention | Opt-in `min_confidence` (a number or a per-bucket map) marks low-confidence answers `abstained`; `laya.calibrate.fit_abstention_thresholds` fits the cut-offs. |
| Training | "RLCD": policy gradient against proper scoring rules plus soft cross-entropy; temperatures fitted per question type on a held-out slice. `laya-train` / `laya.train.finetune` take JSONL rows `{state, questions, expected}`. Their notebook runs on Kaggle's free 2×T4 (4–5 h for 4 epochs over ~30k questions); an MPS script runs on a 16 GB Apple Silicon Mac (`--micro-batch 1 --grad-accum 32`). |
| ONNX | `laya.load(..., backend="onnx")` / `ONNXAgent` run an exported graph on ONNX Runtime and can verify file SHA-256s (`expected_sha256`). The exporter is `scripts/export_onnx.py` in the repository (not in the wheel): opset 18, batch-2 dummies, optional INT8 weight-only dynamic quantization, per tensor. Their own note: INT8 is about 2× faster than eager on CPU and 1.4–2.8× smaller, **but costs real accuracy** (the English checkpoint agreed with eager on 64/96 held-out choices at INT8); per-channel INT8 collapses the model (their #790). |
| Speed (theirs) | T4 GPU: 39.5 ms for one question (English). CPU: 193–464 ms per request with checkpoints preloaded (their table). |
| `laya-evals` | Two different things share the name: the `laya-evals` CLI inside the `laya` package (`laya.evals`: accuracy, ECE, thresholds, a CI gate), and an **independent** community package on PyPI, [laya-evals 0.1.0](https://pypi.org/project/laya-evals/) ([github.com/Gjusev/laya-evals](https://github.com/Gjusev/laya-evals), Apache-2.0), which says of itself "not the `laya-evals` CLI distributed with the upstream `laya` package". The harness here uses neither as a dependency: its metrics are in `harness.py` so they run in CI without torch. |

**Its own "honest limits"** (model card), which match ADR-06's worries:
base checkpoints are near chance zero-shot on decisions they were not
trained for (0.362 vs 0.318 random on typed-decisions; 0.766 after
fine-tuning); shipped temperatures are over-confident (mean ECE 0.466 →
0.081 after refitting); the English checkpoint's `noul` can follow its
`false:`/`true:` labels instead of the state (their #156, so yes/no
questions here are asked as a two-option `choice` with neutral keys A/B, as
they recommend); negated requests can flip `choice` answers (#377); option
position biases sequential checkpoints (#131; `option_order` rotations
average it out, `--rotate` here); `act_probability` carries no signal
(#185). The training mix includes AG News and BoolQ; full data provenance
is not documented (registry note: verify before `ship_model`).

## 2. What was built

| Piece | Where | Status |
|---|---|---|
| Critic interface | `packages/core/researchly/critics/` | `Critic.score(question, span, context) → CriticScore(p, abstain, model_version)`; typed authored questions (`flag-useful`, `sentence-role`); registry; `NullCritic` answers everything until a model is promoted (it always abstains). Per-question calibrated thresholds; malformed output, a missing threshold or an exception all abstain. 23 tests. |
| Health | `health.critic_status()` | "not installed" with reason and remedy; "error" when `critic.json` is malformed or the ONNX SHA-256 differs; "disabled" when verified but no runtime is loaded; "ready" with model version and SHA. It joins `engine_status()` only once something is installed, so today's health output, the service's partial-state logic and every surface are unchanged. |
| Corpus | `ml/corpus/` ([SPEC](../ml/corpus/SPEC.md)) | harvester, licence filter, manifest, weak labels (§3). |
| Laya harness | `ml/critics/laya/` ([README](../ml/critics/laya/README.md)) | `zero_shot.py`, `finetune.py`, `export_onnx.py`, `gate.py`, `MODEL_CARD.md` template; 23 tests with a fake agent (no weights). |

## 3. The S5a corpus (first build, 2026-10-15)

Europe PMC REST API, 1,700 candidates (170 per discipline), each article's
licence read from its own JATS `<permissions>`:

| Discipline | Articles | train (CC BY/CC0) | eval (NC/ND) | test | dev | Structured abstract |
|---|---|---|---|---|---|---|
| clinical-medicine | 140 | 107 | 33 | 18 | 14 | 138 |
| computational-statistics | 170 | 164 | 6 | 14 | 16 | 82 |
| ecology-evolution | 132 | 132 | 0 | 5 | 17 | 1 |
| engineering | 170 | 114 | 56 | 21 | 18 | 16 |
| epidemiology | 135 | 121 | 14 | 13 | 12 | 111 |
| humanities | 157 | 157 | 0 | 16 | 18 | 47 |
| molecular-biology | 157 | 99 | 58 | 11 | 12 | 0 |
| physical-earth-sciences | 169 | 150 | 19 | 21 | 18 | 0 |
| public-health | 166 | 136 | 30 | 19 | 11 | 164 |
| social-sciences | 170 | 170 | 0 | 17 | 17 | 9 |
| **Total** | **1,566** | **1,350** | **216** | 155 | 153 | 568 |

Licences: CC BY 4.0 1,298; CC BY 3.0 13; CC BY (unversioned statement) 17;
CC0 22; CC BY-NC 4.0 152; CC BY-NC-ND (3.0/4.0/unversioned) 64. Dropped:
110 with no Creative Commons licence (mostly publishers' COVID-19
free-access grants, which are not reuse licences), 16 with no full text, 8
abstract-only or too short. 10.5 million words. Humanities: Synthese,
History and Philosophy of the Life Sciences, Humanities & Social Sciences
Communications, Heritage Science, BMC Medical Ethics; social sciences:
Frontiers in Psychology and Humanities & Social Sciences Communications.

Weak labels (cache only): **7,636 abstract sentences** from 561 structured
abstracts (background 1,546, objective 70, methods 2,025, results 2,604,
conclusions 1,391; 6,539 from trainable articles, 790 of them in the test
split), and **61,917 body paragraphs** with IMRaD section roles. Structured
abstracts come from medicine, public health, epidemiology, statistics and
medical ethics; ecology, molecular biology and physical sciences have
almost none, so Task B's labels are biomedical-leaning even though the
corpus is not. "Objective" is rare because most structured abstracts fold
the aim into Background.

## 4. What ran here (CPU-only container)

Laya 0.4.8, English checkpoint at the pinned revision, PyTorch 2.5.1 on
CPU (4 cores, 2 threads for Laya), transformers 4.57.1. The container was
shared with other jobs (load average 8–17 on 4 cores, memory nearly full),
so **latencies are upper bounds**, not a benchmark.

### Task B, zero-shot: sentence roles on held-out articles

300 sentences from whole structured abstracts in the **test split** (articles
no training script reads), 7 disciplines (the ones with structured
abstracts); a separate 150 **dev** sentences fitted one temperature. Input:
`"Sentence k of n in a research abstract: …"`; question: the engine's
`sentence-role` (five options, as Laya's `choice`).

| | Laya zero-shot | TF-IDF move-clf-v0 (same 300) | Majority class |
|---|---|---|---|
| Accuracy | **0.470** | 0.637 | 0.323 |
| Macro-F1 | 0.408 | 0.599 | — |
| ECE (raw) | 0.097 | 0.080 | — |
| ECE after temperature (T = 1.25, fitted on dev) | 0.069 | — | — |
| Precision of the most confident 20% / 40% / 60% | 0.733 / 0.683 / 0.567 | 0.950 / 0.867 / 0.750 | — |
| Coverage at precision ≥ 0.85 | **9.7%** (29 answers) | 41.3% (124) | — |

- Laya predicts "results" for 206 of 300 sentences (97 are results); it
  rarely says "methods" (13 predicted, 66 true). Per discipline, accuracy
  runs 0.41 (public health) to 0.54 (social sciences).
- It is better calibrated than its card warns for this question (raw ECE
  0.097), but calibration cannot fix a weak ranking: almost no confident
  answers reach the 0.85 bar.
- The **TF-IDF baseline drops from 82.6% (PubMed 20k RCT) to 63.7%** on
  these cross-discipline abstracts. The ADR's bar (82.6%) was measured on a
  different, easier distribution; on this test split the like-for-like bar
  is 63.7% (and a model must still clear precision 0.85 at useful coverage).
  The baseline is a pickle trained on PubMed-RCT (licence undeclared); it
  was loaded in a scratch script for this comparison only, never in the
  engine (ADR-06).
- **Latency (CPU, contended):** p50 1.8 s, p95 5.2 s per sentence one at a
  time, 1.6 s per sentence in batches of 8 (fp32 PyTorch, not INT8 ONNX).
  Laya's own CPU figure is 0.19–0.46 s per request on an idle machine;
  re-measure on the owner's Mac before reading anything into these.

Reading: as ADR-06 and Laya's own card predicted, the base checkpoint is a
starting point, not a candidate (above chance, below the TF-IDF model).
Whether fine-tuning on 5,000+ weak-label sentences lifts it past the
like-for-like bar is the S5b question, and needs a GPU (§5).

### Task A, plumbing only (synthetic)

The owner has not labelled yet, so the Task A path ran on synthetic
paragraphs written for the harness (`ml/critics/laya/fixtures/`), in two
stages so the engine and Laya need not share a process: the engine
re-checked the six paragraphs exactly as the Label page does and matched 10
of the 13 labels to their flags (one replaced verdict and one "unsure" set
aside, one label whose rule is not at its position skipped, as designed).
Laya's scoring of those 10 states was **killed by the container's memory
limit** twice (other jobs held ~12 of 16 GB), so no Task A number is
reported; the scoring path is covered by the fake-agent tests, and the
numbers would mean nothing on synthetic labels anyway.

### ONNX export: not run here

The INT8 export needs the fp32 graph (~1.7 GB) plus the INT8 copy (~0.45 GB)
on disk and ~6–8 GB of memory to trace. The container had under 1 GB of
free disk and ~3 GB of free memory by then, so `export_onnx.py` was not run;
its card filling, SHA pinning and the gate that reads them are tested with
synthetic files. The owner runs it after fine-tuning (§5).

## 5. What the owner should run

**Since 2026-10-16 this is one command**: `bash ml/critics/laya/train.sh`
(on the Mac; `--quick` first), or `make_kaggle_kit.sh` +
`kaggle_notebook.ipynb` + `train.sh --import laya-outputs.zip` (Kaggle's free
GPU). It fetches the corpus, assembles Task A (synthetic drafts + published
-article flags) and Task B data, trains, calibrates, exports INT8 ONNX, runs
the noise floor and the gate, and prints a summary. See
[`ml/critics/laya/README.md`](../ml/critics/laya/README.md). The manual steps
below still work:

1. **Corpus on your Mac** (~15 min, ~300 MB outside the repo):
   `python3.10 ml/corpus/harvest.py all --per-discipline 170 && python3.10 ml/corpus/weak_labels.py`
2. **Task B fine-tune** on a free Kaggle T4 (or `--device mps` on your Mac):
   `finetune.py data roles …` then `finetune.py train … --loss soft-ce --shuffle-options`.
3. **Held-out evaluation, INT8 export, gate**: `zero_shot.py roles --model <checkpoint> --n 2000`,
   `export_onnx.py … --question sentence-role=<threshold> --check …`, `gate.py …`.
4. **Task A** needs your labels: 50+ paragraphs on the Label page (300–500
   for a model worth gating), plus the paragraphs' text in a local file.

## 6. Where S5 stands

- The interface, health entry, corpus and harness exist; nothing is
  promoted, so every critic abstains and the engine is unchanged (noise
  floor 11.89, as before).
- The gate would refuse a Laya model today on three counts that are
  decisions, not bugs: `ship_model` is withheld from Laya in the registry
  (D8: only after it wins and its training-data provenance is checked), no
  fire/don't-fire tests name a model yet, and the noise floor (11.89) is
  above the Q3 target of 11.

# Laya: Researchly's S5 critic

Laya is an open-source decision model (Convai Innovations, Apache-2.0). It
reads a passage and answers a question by choosing one of the options it is
given. It cannot write text. Researchly fine-tunes it for two questions:

- **Task A: is this flag useful?** It reads the paragraph, the flagged
  words and the card's message, and answers yes or no. The aim is to hide the
  engine's false flags.
- **Task B: sentence roles.** It reads a sentence of an abstract and says
  whether it is background, objective, methods, results or conclusions.
  The TF-IDF classifier's 82.6% is the score to beat.

Nothing in this folder runs inside the engine. A model reaches the engine
only as a pinned INT8 ONNX file, and only after `gate.py` says PROMOTE
(ARCHITECTURE.md ADR-06). Weights, corpus text and your paragraphs never
enter the repository. Facts about Laya, and the first measurements, are in
[`docs/s5-laya.md`](../../../docs/s5-laya.md).

## Train Laya in one command (your Mac)

```bash
cd ~/Researchly
bash ml/critics/laya/train.sh --quick     # first: a smoke run of a few minutes
bash ml/critics/laya/train.sh             # then: the real run (both tasks)
```

`--dry-run` prints the plan and the time estimates and changes nothing.
`--task a` or `--task b` trains one task. `--device cpu|mps|cuda` picks the
device; the default on Apple Silicon is `mps`. If the run stops, run the same
command again: finished steps are skipped, and training continues from the
last finished epoch.

What you need:

| | |
|---|---|
| Python | Homebrew `python3.10` with the engine installed (`pip install -r packages/core/requirements.txt`, `python -m spacy download en_core_web_sm`, Java for the grammar tier). The script makes its own ML venv in `~/.venvs/laya`. |
| Disk | About 1 GB for the corpus cache and the base model, plus about 2.5 GB per trained task (checkpoint and INT8 ONNX), plus about 3 GB more while exporting. |
| Memory | Training holds about 8–10 GB on a 16 GB Mac, so close other large apps. |
| Time on an M1/M2 (rough) | Task B: about 3.5 hours. Task A: about 2.5 hours. Export and evaluation: about 40 minutes. On CPU only (no `mps`) it is several times slower: about 2.4 s per training sentence (Task B) was measured on a 4-core Linux container. The `--quick` run measures your Mac's real speed and prints a projection. If you would rather not wait, use Kaggle (below). |

## …or on Kaggle's free GPU, in 6 steps

1. On your Mac: `bash ml/critics/laya/make_kaggle_kit.sh`. This writes
   `~/laya-kit.zip` (about 10 MB).
2. Go to kaggle.com → **Datasets** → **New Dataset**. Upload `laya-kit.zip`,
   set it to **Private**, and create it.
3. Go to **Code** → **New Notebook** → **File** → **Import Notebook**, and
   choose `ml/critics/laya/kaggle_notebook.ipynb`. In the right-hand panel,
   choose **Add Input** → *Your Datasets* → the dataset from step 2.
4. In **Settings**, set *Accelerator* to **GPU T4 x2** and turn *Internet*
   **on**.
5. Choose **Save Version** → **Save & Run All (Commit)**. It runs in the
   background; a full run should take about 1–2 hours on one T4 (Kaggle allows 12). Set
   `QUICK = True` in the first cell to try it in a few minutes first.
6. When the run is done, open the version's **Output** tab and download
   `laya-outputs.zip`. Then, on your Mac:

   ```bash
   bash ml/critics/laya/train.sh --import ~/Downloads/laya-outputs.zip
   ```

   This checks the INT8 critics again on your Mac, and on your own labels if
   you have set them (see below). It then runs the noise floor and the gate,
   installs a critic if the gate says PROMOTE, and prints the summary.

The kit holds two kinds of text: synthetic paragraphs written for Researchly,
and sentences and paragraphs of CC BY / CC0 open-access articles. CC BY /
CC0 text may sit in a private dataset; `ATTRIBUTION.md` and the manifest
inside the kit name every article. Your own paragraphs are never in the kit.

## What happens, step by step

| Step | Script | Output (in `~/laya-runs/<date>/`) |
|---|---|---|
| 1. The ML venv (laya, torch, transformers, onnxruntime) | `train.sh` | `~/.venvs/laya` |
| 2. Fetch the open-access corpus: the articles the committed manifest lists, licence-checked, into a cache outside the repo. Then build its weak labels. | `ml/corpus/harvest.py mirror`, `weak_labels.py` | `~/.researchly/corpus` |
| 3. Rebuild the published-article paragraphs that the corpus flag labels point to, checking every paragraph's SHA-256 | `ml/critics/data/corpus/rebuild.py` | `~/laya-corpus` |
| 4. Assemble the training, dev and test files (details below) | `assemble.py` | `data/`, `data/data-report.json` |
| 5. Fine-tune Laya (Task B, then Task A) | `pipeline.py` → `finetune.py` | `b/ckpt`, `a/ckpt` |
| 6. Score dev and test; fit a temperature on dev; choose the threshold on dev | `evaluate.py` | `*/eval-ckpt-*.json` |
| 7. Export to INT8 ONNX, score it again (this is the graph that would ship), and pin it with SHA-256, `critic.json` and a filled model card | `export_onnx.py`, `evaluate.py` | `*/critic/`, `*/eval-int8-*.json` |
| 8. Noise floor on the private thesis corpus, if it is on this machine. No critic runtime is wired into the engine yet, so this measures the engine as it is (11.54 on 2026-10-16) | `ml/dogfood/run_dogfood.py` | `noise/` |
| 9. The promotion gate, and installation into `~/.researchly/models/critic` only on PROMOTE | `gate.py` | `*/gate.txt`, `*/gate.json` |
| 10. A plain-language summary | `pipeline.py summary` | `SUMMARY.txt` |

**The data** (`assemble.py`, counts from 2026-10-16):

| Task A | train | dev | test |
|---|---|---|---|
| Synthetic drafts: parts A, B and C, renumbered 1–450; split 70/15/15 by paragraph | 467 | 109 | 111 |
| Published articles: the corpus's own test split stays the test; dev is 15% of its train split, taken by article | 566 | 108 | 169 |
| All (useful / wrong) | 1,033 (505 / 528) | 217 (116 / 101) | 280 (128 / 152) |

- Every split is stratified by rule and verdict. No paragraph sits in two
  splits, and no corpus article sits in two splits either.
- "Unsure" verdicts are left out.
- Pooled, the training set is about 1 : 1 useful to wrong. When it is more
  lopsided than `--max-ratio` (1.5), the minority verdict is repeated in
  train only.

**Task B:** 5,184 train, 565 dev and 790 test sentences. These come only
from CC BY / CC0 articles, split by article.

**Training settings.** On the Mac, each step takes one example (micro-batch
1), and gradient accumulation makes the effective batch 64 for Task B and
32 for Task A. On a CUDA GPU, each step takes 8 examples. The number of
epochs depends on how much data there is: 3 for Task B and 5 for Task A.
The loss is soft cross-entropy, and the option order is shuffled. Laya's
trainer also fits its own temperatures.

## What the numbers mean

- **Accuracy:** the share of all answers that are right. For Task B it is
  compared with TF-IDF (82.6% on PubMed-RCT, 63.7% on this corpus's test
  split) and with Laya zero-shot (47.0%).
- **Threshold, precision and coverage:** the critic answers only when its
  confidence is at or above a threshold. The threshold is chosen on **dev**
  as the lowest one at which the answers kept are at least 85% right, with
  at least 20 answers kept. It is then applied unchanged to **test**.
  Coverage is the share of test items answered at that threshold, and
  precision is how many of those answers are right. The gate needs
  precision of at least 0.85 on test. If no threshold reaches 0.85 on dev,
  the critic would never answer (threshold 1.0), and the summary says so.
- **INT8 versus the checkpoint:** the numbers the gate reads are from the INT8 graph, because that is what would ship. The summary also shows the PyTorch checkpoint's accuracy and how often INT8 gives the same answer. In the smoke runs here, INT8 matched 78–81% of answers and cost accuracy (roles 0.60 → 0.52). Laya's own notes warn of this.
- **ECE** (calibration error): the gap between how sure the model says it
  is and how often it is right. Lower is better. The gate warns above 0.10.
- **Task A, with the critic:** the share of the engine's flags that are
  useful, first as they are, then after hiding the flags the critic
  confidently calls "not useful". The summary also counts how many useful
  flags would be hidden.
- **Gate verdict:** PROMOTE only if every check passes. It will say **NOT
  PROMOTED** today, on purpose, for these reasons:
  - The registry withholds `ship_model` from Laya until it wins and its
    training mix is checked (D8).
  - No fire / don't-fire tests name the model yet.
  - The noise floor is above 11 per 1,000 words.
  - For Task A, it also needs your labels.

  Each failed check is listed with its reason.

## Your own labels: the independent test

1. Label paragraphs on the website's **Label** page
   ([docs/labelling-guide.md](../../../docs/labelling-guide.md)) and export
   `researchly-labels.json`. The export holds no text.
2. Keep the same paragraphs, as you pasted them, in a local file:
   `{"version": 1, "paragraphs": [{"paragraph": 1, "section": "methods", "text": "…"}]}`.
3. Run any of the commands above with both variables set:

   ```bash
   RESEARCHLY_LABELS=~/Downloads/researchly-labels.json \
   RESEARCHLY_PARAGRAPHS=~/researchly-paragraphs.json \
   bash ml/critics/laya/train.sh            # or: … train.sh --import laya-outputs.zip
   ```

Your labels become `data/flags-test-owner.jsonl`. They are **never trained
on**, never go into the Kaggle kit, and are reported separately as "YOUR
labels". About 50 paragraphs (a few hundred flags) is enough for a first
reading. The gate needs at least 20 confident answers.

## Honesty note: what Task A's test measures

The Task A labels, both in training and in the test split, are **Claude's
judgments**. Claude wrote the synthetic paragraphs for Researchly and judged
their flags. Claude also judged the flags on the published-article
paragraphs. So Task A's test score measures **how well Laya agrees with
Claude**, not whether a flag helps a writer. Only your own labels are an
independent test. That is why the gate reports both, and why it will not
promote a Task A critic until it has been measured on your labels.

Task B's labels come from the authors' own abstract headings (weak labels).
They are noisy, but they are not Claude's.

## Files

| File | What it does |
|---|---|
| `train.sh` | One command on the Mac (`--quick`, `--task`, `--device`, `--dry-run`, `--import`) |
| `make_kaggle_kit.sh`, `kaggle_notebook.ipynb` | The Kaggle route |
| `assemble.py` | Data: merges the synthetic parts, adds the corpus labels, makes splits, balances, writes the report |
| `pipeline.py` | Runs train → evaluate → export → evaluate INT8 → pin; also `plan` and `summary` (no torch needed for these two) |
| `finetune.py` | Builds data for one task (`data`) and runs Laya's trainer, resumable by epoch (`train`) |
| `evaluate.py` | Scores a checkpoint or an INT8 graph; temperature, threshold and per-source / per-rule reports |
| `export_onnx.py` | ONNX export, INT8 quantization, SHA-256, `critic.json`, filled model card |
| `gate.py` | The promotion gate |
| `zero_shot.py` | Laya as shipped (the first spike; `--model <folder>` scores any checkpoint) |
| `harness.py` | Questions (taken from `researchly.critics`), data readers, metrics; no torch |
| `MODEL_CARD.md` | The card template `export_onnx.py` fills |
| `test_laya_harness.py`, `test_laya_pipeline.py` | CI tests with fake agents: no weights |

## Privacy

`~/laya-runs/` holds paragraph text: synthetic, CC BY / CC0, and yours if
you set `RESEARCHLY_LABELS`. Keep it on your machine. Delete
`data/flags-test-owner.jsonl` when you are done. A model trained on your own
text may ship (ADR-06 data table), but these scripts never train on it.

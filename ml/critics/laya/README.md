# Laya critic harness (PLAN S5b)

Owner decision 2026-10-15: S5 uses **Laya** only (open source and free);
ModernBERT and Jev are set aside. Facts about Laya, with links, and the
numbers measured here: [`docs/s5-laya.md`](../../../docs/s5-laya.md).

Nothing in this folder runs in the engine. A model reaches the engine only
as a pinned INT8 ONNX file after `gate.py` says PROMOTE (ARCHITECTURE.md
ADR-06), and weights, corpus text and the owner's paragraphs never enter
the repository.

| File | What it does |
|---|---|
| `harness.py` | Questions (taken from `researchly.critics`, so training asks what the engine will ask), data readers, metrics (accuracy, macro-F1, precision at coverage, ECE, temperature fit, latency). No torch. |
| `zero_shot.py` | Laya as shipped, on Task B (sentence roles, weak labels) and Task A (flag useful? on the owner's labels; `--synthetic` proves the plumbing). |
| `finetune.py` | Builds the training JSONL (`data`) and runs Laya's trainer (`train`). |
| `export_onnx.py` | ONNX export, INT8 quantization, SHA-256, `critic.json`, filled model card. |
| `gate.py` | The promotion gate: card, registry, precision ≥ 0.85, fire/don't-fire tests, noise floor, SHA pin, health entry, no pickles. |
| `MODEL_CARD.md` | The card template `export_onnx.py` fills. |
| `fixtures/` | Synthetic paragraphs and labels (written for the harness; nobody's real writing). |
| `test_laya_harness.py` | CI tests with a fake agent: no weights. |

## Before anything: the corpus and its weak labels

On your Mac (about 15 minutes, ~250 MB in `~/.researchly/corpus`, outside the repo):

```bash
python3.10 ml/corpus/harvest.py all --per-discipline 150
python3.10 ml/corpus/weak_labels.py
```

`ml/corpus/manifest.jsonl` (committed) says which articles to fetch; the
fetch reads each article's licence again from its own XML.

## Task B: sentence roles (baseline to beat: TF-IDF 82.6%)

### 1. Zero-shot spike (CPU is fine; ~1 GB download, ~3 GB RAM)

```bash
python3.10 -m venv ~/.venvs/laya && source ~/.venvs/laya/bin/activate
pip install -r ml/critics/laya/requirements.txt
python ml/critics/laya/zero_shot.py roles \
  --labels ~/.researchly/corpus/labels/sentences.jsonl --n 300 \
  --out ~/laya-zs-roles.json
```

### 2. Fine-tune on a free Kaggle GPU

1. kaggle.com → New Notebook → Settings: **Accelerator GPU T4 x2**,
   **Internet on**. (Laya's trainer uses one GPU; a single T4 has 16 GB.)
2. Upload `roles-train.jsonl` and `roles-dev.jsonl` as a private Kaggle
   dataset. Build them on your Mac first (they hold CC BY / CC0 sentences
   only; the script drops every "eval" article):

   ```bash
   python ml/critics/laya/finetune.py data roles \
     --labels ~/.researchly/corpus/labels/sentences.jsonl \
     --max-per-role 4000 --out ~/laya-data
   ```

3. In the notebook (paths as Kaggle mounts them):

   ```bash
   !pip install -q "laya==0.4.8" "transformers>=4.48,<5"
   !git clone --depth 1 <your clone URL of this repo> researchly
   !python researchly/ml/critics/laya/finetune.py train \
       --data /kaggle/input/<dataset>/roles-train.jsonl \
       --eval-data /kaggle/input/<dataset>/roles-dev.jsonl \
       --out /kaggle/working/laya-roles --device cuda \
       --epochs 4 --micro-batch 8 --grad-accum 8 --loss soft-ce --shuffle-options
   ```

   Laya's README reports 4–5 hours for 4 epochs over ~30k questions on 2×T4;
   20k sentences is about half that on one T4. Kaggle sessions stop at 12
   hours; `checkpoint_latest/` is rewritten each epoch.
4. Download `/kaggle/working/laya-roles` (the checkpoint, ~850 MB) to your Mac.

Or on a **16 GB Apple Silicon Mac** (slower, no upload):

```bash
python ml/critics/laya/finetune.py train --data ~/laya-data/roles-train.jsonl \
  --eval-data ~/laya-data/roles-dev.jsonl --out ~/laya-roles --device mps \
  --micro-batch 1 --grad-accum 64 --loss soft-ce
```

### 3. Evaluate on the held-out test split, export, gate

```bash
python ml/critics/laya/zero_shot.py roles --model ~/laya-roles \
  --labels ~/.researchly/corpus/labels/sentences.jsonl --n 2000 \
  --out ~/laya-roles-heldout.json
python ml/critics/laya/export_onnx.py --checkpoint ~/laya-roles \
  --out ~/laya-roles-onnx --version laya-roles-v1 \
  --question sentence-role=<threshold reaching 0.85 in the report> \
  --report ~/laya-roles-heldout.json \
  --check ~/.researchly/corpus/labels/sentences.jsonl
cd ml/dogfood && RESEARCHLY_CORPUS_OUT=/tmp/nf python3.10 run_dogfood.py && cd -
python ml/critics/laya/gate.py --critic-dir ~/laya-roles-onnx \
  --report ~/laya-roles-heldout.json --noise /tmp/nf/corpus_stats.json
```

(`zero_shot.py --model <folder>` evaluates any checkpoint the same way; the
name is historical.) The gate fails today on purpose: the registry
withholds `ship_model` from Laya until it wins (D8), no fire/don't-fire
tests name a model yet, and the noise floor (11.89) is above 11.

## Task A: "is this flag useful?" (needs your labels)

1. Label 50+ paragraphs on the website's **Label** page
   ([docs/labelling-guide.md](../../../docs/labelling-guide.md)) and export
   `researchly-labels.json` (no text in it).
2. Keep the same paragraphs, as you pasted them, in a local file that never
   leaves your machine:

   ```json
   {"version": 1, "paragraphs": [
     {"paragraph": 1, "section": "methods", "text": "…the paragraph…"}]}
   ```

3. Zero-shot, then training data (add `--telemetry ~/.researchly/telemetry.jsonl`
   for per-rule apply/dismiss counts; those logs hold no text, so they are
   a hint in the input, not labels):

   ```bash
   python ml/critics/laya/zero_shot.py flags --labels ~/Downloads/researchly-labels.json \
     --paragraphs ~/researchly-paragraphs.json --out ~/laya-zs-flags.json
   python ml/critics/laya/finetune.py data flags --labels ~/Downloads/researchly-labels.json \
     --paragraphs ~/researchly-paragraphs.json --out ~/laya-data
   ```

   Train as in Task B with `flags-train.jsonl` / `flags-dev.jsonl`. With 50
   paragraphs (a few hundred flags) expect a weak model: the gate needs
   precision ≥ 0.85 on held-out flags with at least 20 kept, so plan on
   more labels (the guide suggests 300–500 paragraphs for a learned critic).

The flags are re-found by re-checking each paragraph exactly as the Label
page does; if the engine has changed since you labelled, a label whose rule
no longer sits at its position is skipped and counted.

## Privacy

The training files for Task A contain your paragraphs. Keep them on your
machine or in a **private** Kaggle dataset, and delete them after training.
They are your own text, so a model trained on them may ship (ADR-06 data
table); add an `owner-annotations` use note in `ml/datasets.yaml` when you do.

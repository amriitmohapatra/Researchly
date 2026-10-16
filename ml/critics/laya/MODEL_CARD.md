# Model card: {{model_version}}

Template. `export_onnx.py` fills every placeholder field and writes the filled
card next to the exported model; `gate.py` refuses a card with a field left
unfilled. Commit the filled card (never the weights) when a model is
promoted, as `ml/critics/laya/cards/<model_version>.md`.

## What it is

- **Kind:** non-generative critic (ARCHITECTURE.md ADR-06; CLAUDE.md #1). It
  scores authored, typed questions and can abstain. It cannot write text.
- **Base model:** {{base_model}} (Convai Innovations' Laya: ModernBERT-large
  plus a decision head, Apache-2.0; registry id `laya`).
- **Questions it may answer, with their calibrated thresholds:**
  {{questions}}. Below its threshold it abstains, and an abstaining critic
  changes nothing.
- **Runtime:** ONNX Runtime on CPU inside the engine; INT8 weight-only
  dynamic quantization (per tensor).

## Pinned artifact

| | |
|---|---|
| File | `laya.int8.onnx` ({{onnx_bytes}} bytes) |
| SHA-256 | `{{sha256}}` |
| Exported | {{exported}} |
| Pin file | `critic.json` (the engine refuses the model if the SHA differs) |

## Training data

- Registry ids: {{training_data}} (ml/datasets.yaml). Every id must grant
  `ship_model`; `gate.py` checks.
- Licence filter at intake (ml/corpus/SPEC.md): CC BY / CC0 only for
  training; CC BY-NC/ND/SA articles evaluate only.
- No thesis, course or owner text unless the owner consented (D6, D7).

## Held-out evaluation (test split, articles never seen in training)

| | |
|---|---|
| Items | {{heldout_n}} |
| Accuracy (all answered) | {{heldout_accuracy}} |
| ECE (after temperature) | {{heldout_ece}} |
| Coverage at precision ≥ 0.85 | {{coverage_at_gate}} |
| INT8 vs checkpoint | {{int8_check}} |

The baseline to beat for sentence roles is the TF-IDF classifier's 82.6%
(move-clf-v0, PubMed 20k RCT). Per-discipline results are in the evaluation
report.

## Known limits

- 512-token context (about one paragraph).
- Laya's own card: base checkpoints are near chance zero-shot; shipped
  temperatures are over-confident; negated inputs can flip `choice` answers
  (their issue #377); option position biases sequential checkpoints (#131).
- INT8 trades accuracy for speed (their #790); the numbers above are the
  INT8 graph's.

## Promotion gate (ADR-06)

Run `python ml/critics/laya/gate.py` with this card, the exported folder,
the held-out report and a noise-floor run; it checks model card, registry,
held-out precision ≥ 0.85, fire and don't-fire tests, noise floor ≤ the
target, SHA-256 pin, and the `health.py` entry.

"""Export a (fine-tuned) Laya checkpoint to ONNX for the engine's CPU runtime,
quantize it to INT8, pin it by SHA-256 and fill in its model card.

    python ml/critics/laya/export_onnx.py --checkpoint ckpt-roles \\
        --out critic-roles --version laya-roles-v1 \\
        --question sentence-role=0.90 --report zs-or-finetuned-eval.json

Writes into ``--out`` (outside the repo; weights are never committed):

    laya.onnx            fp32 graph (deleted unless --keep-fp32)
    laya.int8.onnx       INT8 weight-only dynamic quantization (CPU)
    tokenizer/, encoder/config.json, rl_agent_config.json
                         copied from the checkpoint; ONNX Runtime needs them
    critic.json          the pin the engine reads (researchly.critics):
                         model_version, onnx_file, sha256, the questions it
                         may answer with their calibrated thresholds, and the
                         SHA-256 of every other file
    MODEL_CARD.md        ml/critics/laya/MODEL_CARD.md with this export's
                         values filled in (commit the filled card when the
                         model is promoted; gate.py checks it)

The export follows Laya's own ``scripts/export_onnx.py`` (Apache-2.0,
https://github.com/NandhaKishorM/laya): the same inputs, dynamic axes and
opset, batch-2 dummies (their #695), and per-tensor INT8 quantization
(their #790: per-channel collapses the model). Laya's own warning applies:
INT8 trades real accuracy for speed and size, so gate.py measures the INT8
graph, not the PyTorch checkpoint, and ``--check`` reports how often INT8
and the checkpoint disagree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent / "MODEL_CARD.md"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export_fp32(checkpoint: str, onnx_path: Path) -> None:
    import torch
    from laya.agent import Agent
    agent = Agent(checkpoint, compile=False, device="cpu")
    batch, seq_len, markers = 2, 17, 3
    inputs = (torch.randint(0, 100, (batch, seq_len), dtype=torch.long),
              torch.ones((batch, seq_len), dtype=torch.long),
              torch.tensor([[1, 5, 9]] * batch, dtype=torch.long),
              torch.ones((batch, markers), dtype=torch.bool),
              torch.zeros(batch, dtype=torch.long))
    names = ["input_ids", "attention_mask", "marker_pos", "marker_mask",
             "qtype"]
    axes = {"input_ids": {0: "batch_size", 1: "seq_len"},
            "attention_mask": {0: "batch_size", 1: "seq_len"},
            "marker_pos": {0: "batch_size", 1: "num_markers"},
            "marker_mask": {0: "batch_size", 1: "num_markers"},
            "qtype": {0: "batch_size"},
            "logits": {0: "batch_size", 1: "num_markers"},
            "act_logits": {0: "batch_size"}}
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(agent.model, inputs, str(onnx_path), export_params=True,
                      opset_version=18, do_constant_folding=True,
                      input_names=names, output_names=["logits", "act_logits"],
                      dynamic_axes=axes)


def quantize_int8(src: Path, dst: Path) -> None:
    import onnx
    from onnxruntime.quantization import QuantType, quantize_dynamic
    model = onnx.load(str(src))
    del model.graph.value_info[:]          # Laya's note: stale shape hints
    quantize_dynamic(model_input=model, model_output=str(dst),
                     op_types_to_quantize=["MatMul"],
                     weight_type=QuantType.QInt8, per_channel=False)


def copy_runtime_files(checkpoint: Path, out: Path) -> list:
    """What ONNXAgent reads besides the graph: config and tokenizer."""
    copied = []
    for rel in ("rl_agent_config.json", "config.json", "encoder/config.json"):
        if (checkpoint / rel).exists():
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(checkpoint / rel, out / rel)
            copied.append(rel)
    if (checkpoint / "tokenizer").is_dir():
        shutil.copytree(checkpoint / "tokenizer", out / "tokenizer",
                        dirs_exist_ok=True)
        copied += [f"tokenizer/{p.name}" for p in
                   sorted((checkpoint / "tokenizer").iterdir())]
    return copied


def check_agreement(checkpoint: str, out: Path, onnx_file: str,
                    states: list, question: dict) -> dict:
    """How often the INT8 graph and the PyTorch checkpoint disagree, and
    CPU latency of each, on the given states."""
    import laya
    from laya.onnx_agent import ONNXAgent
    eager = laya.load(checkpoint, device="cpu")
    fast = ONNXAgent(str(out), onnx_path=str(out / onnx_file))
    qs = {"q": question}
    same, drift, te, tf = 0, 0.0, [], []
    for s in states:
        a, dt = harness.timed(eager.predict, s, qs)
        te.append(dt)
        b, dt = harness.timed(fast.predict, s, qs)
        tf.append(dt)
        pa, pb = a["answers"]["q"], b["answers"]["q"]
        same += pa["choice"] == pb["choice"]
        drift = max(drift, max(abs(pa["probabilities"][k] -
                                   pb["probabilities"][k])
                               for k in pa["probabilities"]))
    return {"states": len(states), "same_answer": same / max(1, len(states)),
            "max_probability_drift": drift,
            "latency_eager_cpu": harness.latency_summary(te),
            "latency_int8_cpu": harness.latency_summary(tf)}


def fill_card(values: dict, dst: Path) -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    dst.write_text(text, encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--checkpoint", type=Path, required=True,
                    help="a local Laya checkpoint folder (fine-tuned)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--version", required=True,
                    help="model version, e.g. laya-roles-v1")
    ap.add_argument("--question", action="append", default=[],
                    help="QUESTION_ID=THRESHOLD, from the held-out "
                         "evaluation (repeatable)")
    ap.add_argument("--report", type=Path,
                    help="held-out evaluation report (zero_shot.py format) "
                         "quoted in the card")
    ap.add_argument("--training-data", default="s5a-oa-corpus-cc-by",
                    help="registry ids of the training data, comma-separated")
    ap.add_argument("--keep-fp32", action="store_true")
    ap.add_argument("--check", type=Path,
                    help="a sentences.jsonl to measure INT8 vs eager on "
                         "(first 50 test-split rows)")
    a = ap.parse_args(argv)
    out = a.out.resolve()
    if harness.REPO in out.parents or out == harness.REPO:
        ap.error("--out must be outside the repository (weights are never "
                 "committed)")
    questions = {}
    for item in a.question:
        qid, _, t = item.partition("=")
        if qid not in harness.critics.QUESTIONS:
            ap.error(f"unknown question {qid!r}")
        questions[qid] = float(t)
    if not questions:
        ap.error("name at least one --question ID=THRESHOLD")

    t0 = time.time()
    fp32 = out / "laya.onnx"
    int8 = out / "laya.int8.onnx"
    export_fp32(str(a.checkpoint), fp32)
    quantize_int8(fp32, int8)
    files = copy_runtime_files(a.checkpoint, out)
    check = None
    if a.check:
        rows = harness.sample_roles(harness.read_jsonl(a.check), 50)
        check = check_agreement(
            str(a.checkpoint), out, int8.name,
            [harness.role_state(r) for r in rows],
            harness.laya_question(harness.critics.SENTENCE_ROLE))
    if not a.keep_fp32:
        fp32.unlink()
    digest = sha256_file(int8)
    descriptor = {
        "model_version": a.version,
        "onnx_file": int8.name,
        "sha256": digest,
        "questions": questions,
        "files": {rel: sha256_file(out / rel) for rel in files},
        "base_model": f"{harness.LAYA_REPO}@{harness.LAYA_REVISION}",
        "exported": time.strftime("%Y-%m-%d"),
    }
    (out / "critic.json").write_text(json.dumps(descriptor, indent=1))
    report = json.loads(a.report.read_text()) if a.report else {}
    zs = report.get("after_temperature") or report.get("zero_shot") or {}
    fill_card({
        "model_version": a.version,
        "sha256": digest,
        "onnx_bytes": int8.stat().st_size,
        "base_model": descriptor["base_model"],
        "questions": ", ".join(f"{k} (threshold {v:.2f})"
                               for k, v in questions.items()),
        "training_data": a.training_data,
        "heldout_accuracy": f"{zs.get('accuracy', float('nan')):.3f}",
        "heldout_ece": f"{zs.get('ece', float('nan')):.3f}",
        "heldout_n": zs.get("n", 0),
        "coverage_at_gate": json.dumps(
            zs.get("risk_coverage", {}).get("coverage_at_gate", {})),
        "int8_check": json.dumps(check) if check else "not run",
        "exported": descriptor["exported"],
    }, out / "MODEL_CARD.md")
    print(json.dumps({"out": str(out), "sha256": digest,
                      "int8_bytes": int8.stat().st_size,
                      "check": check, "seconds": round(time.time() - t0)},
                     indent=1))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("USE_TF", "0")
    sys.exit(main())

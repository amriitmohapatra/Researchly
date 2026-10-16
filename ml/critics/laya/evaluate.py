"""Evaluate a fine-tuned Laya (PyTorch checkpoint or the INT8 ONNX export) on
the assembled files, calibrate it and pick its threshold (PLAN S5b).

    python ml/critics/laya/evaluate.py --task a --model ~/laya-runs/D/a/critic \\
        --backend onnx --data ~/laya-runs/D/data --out ~/laya-runs/D/a/eval-int8

1. Score the dev file; fit one temperature on it (harness.fit_temperature).
2. Pick the question's threshold on dev: the lowest top-1 confidence at
   which the answers kept reach precision >= 0.85 with at least 20 kept
   (the engine abstains below it; researchly.critics.Critic.score).
3. Score each test file (flags-test.jsonl, and flags-test-owner.jsonl when
   present; roles-test.jsonl), apply the dev temperature, and report
   accuracy, macro-F1, ECE, precision and coverage at the dev threshold,
   per source / rule / discipline. No text is written to the reports.

Each test report has the shape gate.py and export_onnx.py read
(``zero_shot`` = raw, ``after_temperature``, ``items``).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
from harness import critics  # noqa: E402

TASKS = {"a": {"prefix": "flags", "question": "flag-useful",
               "group": "source"},
         "b": {"prefix": "roles", "question": "sentence-role",
               "group": "discipline"}}


def engine_question(rows: list) -> "critics.Question":
    qid = next(iter(rows[0]["questions"]))
    return critics.QUESTIONS[qid]


def gold_of(q: "critics.Question", row: dict) -> str:
    """The engine-side gold answer of a Laya row (A/B -> yes/no)."""
    g = row["expected"][q.id]
    if q.type == "yes_no":
        return {"A": "yes", "B": "no"}[g]
    return g


def load_agent(model: str, backend: str = "torch", device: str = "cpu"):
    """A fine-tuned checkpoint folder (torch) or an exported critic folder
    (onnx: laya.int8.onnx beside its tokenizer and config)."""
    if backend == "onnx":
        from laya.onnx_agent import ONNXAgent
        return ONNXAgent(str(model), onnx_path=str(Path(model) /
                                                   "laya.int8.onnx"))
    return harness.load_agent(str(model), device=device)


def score(agent, rows: list, batch_size: int = 16) -> tuple:
    """(engine-keyed probability dicts, seconds per row)."""
    if not rows:
        return [], 0.0
    q = engine_question(rows)
    lq = harness.laya_question(q)
    states = [r["state"] for r in rows]
    t = time.perf_counter()
    if hasattr(agent, "predict_batch"):
        res = []
        for i in range(0, len(states), batch_size):
            res.extend(agent.predict_batch(states[i:i + batch_size],
                                           {q.id: lq}, batch_size=batch_size))
    else:
        res = [agent.predict(s, {q.id: lq}) for s in states]
    secs = (time.perf_counter() - t) / len(states)
    return [harness.from_laya(q, r["answers"][q.id]["probabilities"])
            for r in res], secs


def pick_threshold(dists: list, gold: list) -> dict:
    """The dev threshold: lowest confidence keeping precision >= 0.85 over
    at least 20 answers (harness.risk_coverage), else none."""
    pred = [max(d, key=d.get) for d in dists]
    conf = [d[p] for d, p in zip(dists, pred)]
    correct = [int(p == g) for p, g in zip(pred, gold)]
    best = harness.risk_coverage(conf, correct)["coverage_at_gate"]
    return {"threshold": best["threshold"], "dev_coverage": best["coverage"],
            "dev_kept": best["n"], "reached": best["threshold"] is not None}


def at_threshold(dists: list, gold: list, threshold: Optional[float]) -> dict:
    if threshold is None:
        return {"threshold": None, "precision": None, "kept": 0,
                "coverage": 0.0}
    kept = [(max(d, key=d.get), g) for d, g in zip(dists, gold)
            if max(d.values()) >= threshold]
    n = len(kept)
    return {"threshold": threshold, "kept": n,
            "coverage": n / max(1, len(gold)),
            "precision": (sum(p == g for p, g in kept) / n) if n else None}


def report_for(rows: list, raw: list, t: float, threshold: Optional[float],
               task: str, secs: float) -> dict:
    q = engine_question(rows)
    gold = [gold_of(q, r) for r in rows]
    grp_key = TASKS[task]["group"]
    groups = [str(r.get("meta", {}).get(grp_key, "")) for r in rows]
    cal = [harness.temper(d, t) for d in raw]
    rep = {"task": task, "question": q.id, "n": len(rows),
           "zero_shot": harness.summarise(raw, gold, groups),
           "after_temperature": harness.summarise(cal, gold, groups),
           "temperature": t,
           "at_dev_threshold": at_threshold(cal, gold, threshold),
           "seconds_per_item": secs,
           "items": harness.items(cal, gold, groups)}
    if task == "a":
        rules = [r.get("meta", {}).get("rule", "") for r in rows]
        by_rule = defaultdict(list)
        for d, g, ru in zip(cal, gold, rules):
            by_rule[ru].append((d, g))
        rep["by_rule"] = {
            ru: dict(n=len(v), **{k: at_threshold([d for d, _ in v],
                                                   [g for _, g in v],
                                                   threshold)[k]
                                  for k in ("kept", "precision")})
            for ru, v in sorted(by_rule.items())}
        by_src = defaultdict(list)
        for d, g, s in zip(cal, gold, groups):
            by_src[s].append((d, g))
        rep["by_source"] = {
            s: dict(n=len(v), useful_share=sum(g == "yes" for _, g in v)
                    / len(v), **at_threshold([d for d, _ in v],
                                             [g for _, g in v], threshold))
            for s, v in sorted(by_src.items())}
        # what the critic is for: the engine's flags, without and with it
        rep["engine_precision_without_critic"] = gold.count("yes") / len(gold)
        hidden = [g for d, g in zip(cal, gold)
                  if max(d, key=d.get) == "no" and threshold is not None
                  and d["no"] >= threshold]
        shown = len(gold) - len(hidden)
        rep["with_critic"] = {
            "flags_hidden": len(hidden),
            "useful_flags_hidden": hidden.count("yes"),
            "engine_precision_with_critic":
                (gold.count("yes") - hidden.count("yes")) / max(1, shown)}
    return rep


def evaluate(agent, data: Path, task: str, out: Path,
             batch_size: int = 16, extra_tests: Optional[dict] = None) -> dict:
    """Dev calibration + every test file; writes <out>-dev.json,
    <out>-test.json (and -test-owner.json); returns a short summary."""
    prefix = TASKS[task]["prefix"]
    dev = harness.read_jsonl(data / f"{prefix}-dev.jsonl")
    q = engine_question(dev)
    dev_raw, dev_secs = score(agent, dev, batch_size)
    dev_gold = [gold_of(q, r) for r in dev]
    t = harness.fit_temperature(dev_raw, dev_gold)
    thr = pick_threshold([harness.temper(d, t) for d in dev_raw], dev_gold)
    dev_rep = report_for(dev, dev_raw, t, thr["threshold"], task, dev_secs)
    dev_rep["threshold_choice"] = thr
    out.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{out}-dev.json").write_text(json.dumps(dev_rep, indent=1))
    tests = {"test": data / f"{prefix}-test.jsonl"}
    if task == "a" and (data / "flags-test-owner.jsonl").exists():
        tests["test-owner"] = data / "flags-test-owner.jsonl"
    tests.update(extra_tests or {})
    summary = {"task": task, "question": q.id, "temperature": t,
               "threshold": thr, "dev": _short(dev_rep), "tests": {}}
    for name, path in tests.items():
        rows = harness.read_jsonl(path)
        if not rows:
            continue
        raw, secs = score(agent, rows, batch_size)
        rep = report_for(rows, raw, t, thr["threshold"], task, secs)
        rep["threshold_choice"] = thr
        Path(f"{out}-{name}.json").write_text(json.dumps(rep, indent=1))
        summary["tests"][name] = _short(rep)
    Path(f"{out}-summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def _short(rep: dict) -> dict:
    body = rep["after_temperature"]
    s = {"n": rep["n"], "accuracy": body["accuracy"],
         "macro_f1": body["macro_f1"], "ece": body["ece"],
         "raw_accuracy": rep["zero_shot"]["accuracy"],
         "at_dev_threshold": rep["at_dev_threshold"],
         "seconds_per_item": rep["seconds_per_item"]}
    for k in ("engine_precision_without_critic", "with_critic", "by_source"):
        if k in rep:
            s[k] = rep[k]
    if "by_group" in body and rep["task"] == "b":
        s["by_discipline"] = body["by_group"]
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--task", choices=["a", "b"], required=True)
    ap.add_argument("--model", required=True,
                    help="checkpoint folder (torch) or exported critic "
                         "folder (onnx)")
    ap.add_argument("--backend", choices=["torch", "onnx"], default="torch")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True,
                    help="report prefix: writes <out>-dev.json, -test.json …")
    ap.add_argument("--batch-size", type=int, default=16)
    a = ap.parse_args(argv)
    agent = load_agent(a.model, a.backend, a.device)
    print(json.dumps(evaluate(agent, a.data, a.task, a.out, a.batch_size),
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

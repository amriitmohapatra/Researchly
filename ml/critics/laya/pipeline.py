"""Laya's training pipeline after the data is assembled (PLAN S5b): train,
evaluate, calibrate, export INT8 ONNX, re-evaluate the INT8 graph, pin it.
``train.sh`` (Mac) and ``kaggle_notebook.ipynb`` (Kaggle GPU) both call it.

    python ml/critics/laya/pipeline.py plan   --data DIR --device mps [--task both] [--quick]
    python ml/critics/laya/pipeline.py run    --data DIR --run RUN --device mps [--task both] [--quick]
    python ml/critics/laya/pipeline.py evaluate --data DIR --run RUN [--task both]   # INT8 only
    python ml/critics/laya/pipeline.py summary --run RUN

``run`` per task (Task B first, then Task A), each stage skipped when its
marker says it finished, so re-running the same command resumes:

    <run>/<b|a>/ckpt/          fine-tuned checkpoint (Laya's layout; resumable by epoch)
    <run>/<b|a>/eval-ckpt-*    the checkpoint on dev and test (temperature, threshold)
    <run>/<b|a>/critic/        laya.int8.onnx + tokenizer + critic.json + MODEL_CARD.md
    <run>/<b|a>/eval-int8-*    the INT8 graph on dev and test: what the gate reads

``plan`` and ``summary`` need no torch (they run with plain python3.10).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

TASK_NAMES = {"a": "flags", "b": "roles"}
TITLES = {"a": "Task A: is this flag useful?",
          "b": "Task B: sentence roles in an abstract"}

# Rough seconds per item (train = forward + backward; eval = forward), for
# the plan's time estimates. CUDA: Laya's own T4 figure (4-5 h for 4 epochs
# over ~30k questions). CPU: measured in the container (4 cores, contended).
# MPS: an estimate for an M1/M2 16 GB. A --quick run measures the real rate on
# your machine and prints the projection for the full run.
RATES = {  # device: {task: (train s/item, eval s/item)}
    "cuda": {"b": (0.08, 0.02), "a": (0.20, 0.05)},
    "mps": {"b": (0.8, 0.15), "a": (2.0, 0.4)},
    "cpu": {"b": (2.5, 0.5), "a": (7.0, 1.4)},
}
INT8_EVAL = {"b": 0.25, "a": 0.7}     # seconds per item, ONNX Runtime on CPU
EXPORT_MIN = 12                        # minutes: trace, quantize, check


def count_lines(path: Path) -> int:
    try:
        with path.open(encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


def hyper(n_train: int, device: str, quick: bool) -> dict:
    """Apple-Silicon-safe defaults: micro-batch 1 off CUDA, gradient
    accumulation up to an effective batch of 32 (small data) or 64."""
    if quick:
        epochs = 1
    elif n_train >= 5000:
        epochs = 3
    elif n_train >= 1500:
        epochs = 4
    else:
        epochs = 5
    effective = 64 if n_train >= 3000 else 32
    if quick:
        effective = 8
    micro = 8 if device == "cuda" else 1
    micro = min(micro, effective)
    return {"epochs": epochs, "micro_batch": micro,
            "grad_accum": max(1, effective // micro),
            "effective_batch": effective, "loss": "soft-ce",
            "shuffle_options": True}


def sizes(data: Path, task: str) -> dict:
    p = TASK_NAMES[task]
    out = {k: count_lines(data / f"{p}-{k}.jsonl")
           for k in ("train", "dev", "test")}
    if task == "a":
        out["test-owner"] = count_lines(data / "flags-test-owner.jsonl")
    return out


def default_sizes(task: str, quick: bool) -> dict:
    """What the assembler produced on 2026-10-16 (for a plan made before
    the data exists)."""
    if quick:
        return ({"train": 96, "dev": 48, "test": 48} if task == "a" else
                {"train": 240, "dev": 60, "test": 60})
    return ({"train": 1122, "dev": 162, "test": 246} if task == "a" else
            {"train": 5184, "dev": 565, "test": 790})


def plan(data: Optional[Path], tasks: list, device: str, quick: bool,
         export: bool = True) -> dict:
    out = {"device": device, "quick": quick, "tasks": {}}
    total = 0.0
    for t in tasks:
        n = sizes(data, t) if data and (data / f"{TASK_NAMES[t]}-train.jsonl"
                                        ).exists() else default_sizes(t, quick)
        h = hyper(n["train"], device, quick)
        tr, ev = RATES.get(device, RATES["cpu"])[t]
        ev_n = n["dev"] + n["test"] + n.get("test-owner", 0)
        mins = {"train": n["train"] * h["epochs"] * tr / 60,
                "evaluate checkpoint": ev_n * ev / 60,
                "export INT8 ONNX": EXPORT_MIN if export else 0,
                "evaluate INT8": ev_n * INT8_EVAL[t] / 60 if export else 0}
        out["tasks"][t] = {"sizes": n, "hyper": h,
                           "minutes": {k: round(v, 1) for k, v in mins.items()}}
        total += sum(mins.values())
    out["total_minutes"] = round(total, 1)
    return out


def print_plan(p: dict) -> None:
    print(f"Plan (device {p['device']}{', quick smoke run' if p['quick'] else ''}):")
    for t, d in p["tasks"].items():
        h, n = d["hyper"], d["sizes"]
        print(f"  {TITLES[t]}")
        print(f"    data: {n['train']} train, {n['dev']} dev, {n['test']} test"
              + (f", {n['test-owner']} of your own labels"
                 if n.get("test-owner") else ""))
        print(f"    training: {h['epochs']} epoch(s), micro-batch "
              f"{h['micro_batch']} x {h['grad_accum']} accumulation = "
              f"effective batch {h['effective_batch']}, loss {h['loss']}")
        for k, v in d["minutes"].items():
            print(f"    {k:22} ~{_hm(v)}")
    print(f"  Total: ~{_hm(p['total_minutes'])} (rough; a --quick run "
          "measures your machine and prints a projection)")


def _hm(minutes: float) -> str:
    if minutes < 1:
        return "under a minute"
    if minutes < 90:
        return f"{minutes:.0f} min"
    return f"{minutes / 60:.1f} h"


# --- stages -------------------------------------------------------------------

def _done(d: Path, stage: str) -> bool:
    return (d / f".done-{stage}").exists()


def _mark(d: Path, stage: str, info: Optional[dict] = None) -> None:
    (d / f".done-{stage}").write_text(json.dumps(info or {}, default=str))


def training_ids(data: Path, task: str) -> str:
    if task == "b":
        return "s5a-oa-corpus-cc-by"
    rep = json.loads((data / "data-report.json").read_text())
    srcs = rep.get("task_a", {}).get("sources", {})
    ids = []
    if "synthetic" in srcs:
        ids.append("s5-synthetic-drafts")
    if "corpus" in srcs:
        ids += ["s5-corpus-flag-judgments", "s5a-oa-corpus-cc-by"]
    return ", ".join(ids) or "s5-synthetic-drafts"


def model_version(run: Path, task: str, quick: bool) -> str:
    stamp = "".join(c if c.isalnum() or c == "-" else "-" for c in run.name)
    return f"laya-{TASK_NAMES[task]}-{stamp}" + ("-quick" if quick and
                                                 "quick" not in stamp else "")


def run_task(task: str, data: Path, run: Path, device: str, quick: bool,
             export: bool = True, epochs: Optional[int] = None,
             batch_size: int = 16) -> dict:
    import evaluate
    import export_onnx
    import finetune
    p = TASK_NAMES[task]
    d = run / task
    d.mkdir(parents=True, exist_ok=True)
    n = sizes(data, task)
    h = hyper(n["train"], device, quick)
    if epochs:
        h["epochs"] = epochs
    log = {"task": task, "hyper": h, "sizes": n, "device": device}

    t0 = time.time()
    if not _done(d, "train"):
        print(f"\n== {TITLES[task]}: training ({n['train']} rows, "
              f"{h['epochs']} epochs) ==", flush=True)
        rep = finetune.train(data / f"{p}-train.jsonl", d / "ckpt",
                             eval_data=data / f"{p}-dev.jsonl",
                             device=device, epochs=h["epochs"],
                             micro_batch=h["micro_batch"],
                             grad_accum=h["grad_accum"], loss=h["loss"],
                             shuffle_options=h["shuffle_options"])
        secs = time.time() - t0
        rate = secs / max(1, n["train"] * h["epochs"])
        _mark(d, "train", {"seconds": secs, "seconds_per_item": rate,
                           "report": rep})
    train_info = json.loads((d / ".done-train").read_text())
    log["train"] = train_info

    if not _done(d, "eval-ckpt"):
        print(f"\n== {TITLES[task]}: evaluating the checkpoint ==", flush=True)
        agent = evaluate.load_agent(str(d / "ckpt"), "torch", device)
        s = evaluate.evaluate(agent, data, task, d / "eval-ckpt", batch_size)
        del agent
        _mark(d, "eval-ckpt", s)
    log["eval_ckpt"] = json.loads((d / ".done-eval-ckpt").read_text())

    if export:
        version = model_version(run, task, quick)
        if not _done(d, "export"):
            print(f"\n== {TITLES[task]}: exporting INT8 ONNX ==", flush=True)
            meta = export_onnx.export_graph(d / "ckpt", d / "critic",
                                            check=data / f"{p}-test.jsonl")
            _mark(d, "export", meta)
        if not _done(d, "eval-int8"):
            print(f"\n== {TITLES[task]}: evaluating the INT8 graph ==",
                  flush=True)
            agent = evaluate.load_agent(str(d / "critic"), "onnx")
            s = evaluate.evaluate(agent, data, task, d / "eval-int8",
                                  batch_size)
            _mark(d, "eval-int8", s)
        s = json.loads((d / ".done-eval-int8").read_text())
        test = json.loads((d / "eval-int8-test.json").read_text())
        export_onnx.finalise(d / "critic", version=version,
                             questions={s["question"]:
                                        s["threshold"]["threshold"]},
                             report=test,
                             training_data=training_ids(data, task))
        log["eval_int8"] = s
        log["model_version"] = version
    (d / "run.json").write_text(json.dumps(log, indent=1, default=str))
    return log


def evaluate_int8(task: str, data: Path, run: Path,
                  batch_size: int = 16) -> dict:
    """Re-evaluate an exported critic (e.g. after --import from Kaggle) on
    this machine, including the owner's labels when assembled."""
    import evaluate
    import export_onnx
    d = run / task
    agent = evaluate.load_agent(str(d / "critic"), "onnx")
    s = evaluate.evaluate(agent, data, task, d / "eval-int8", batch_size)
    _mark(d, "eval-int8", s)
    desc = json.loads((d / "critic" / "critic.json").read_text())
    test = json.loads((d / "eval-int8-test.json").read_text())
    export_onnx.finalise(d / "critic", version=desc["model_version"],
                         questions={s["question"]: s["threshold"]["threshold"]},
                         report=test, training_data=training_ids(data, task))
    return s


# --- the plain-language summary --------------------------------------------------------

def _f(x, nd=3) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def _pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def summary_text(run: Path) -> str:
    lines = [f"Laya run: {run}"]
    rep_path = run / "data" / "data-report.json"
    data_rep = json.loads(rep_path.read_text()) if rep_path.exists() else {}
    for task in ("b", "a"):
        d = run / task
        if not (d / "run.json").exists() and not (d / ".done-eval-int8"
                                                  ).exists():
            continue
        info = json.loads((d / "run.json").read_text()) \
            if (d / "run.json").exists() else {}
        lines += ["", TITLES[task]]
        n = info.get("sizes", {})
        h = info.get("hyper", {})
        if n:
            lines.append(f"  Trained on {n.get('train')} examples for "
                         f"{h.get('epochs')} epoch(s) on {info.get('device')}"
                         f" (dev {n.get('dev')}, test {n.get('test')}).")
        if task == "a" and data_rep.get("task_a"):
            c = data_rep["task_a"]["counts"].get("train", {})
            lines.append("  Training flags by source and verdict: " +
                         ", ".join(f"{k} {v}" for k, v in sorted(
                             c.get("by_source_verdict", {}).items())))
        ev_path = d / ".done-eval-int8"
        which = "INT8 graph (what would ship)"
        if not ev_path.exists():
            ev_path, which = d / ".done-eval-ckpt", "checkpoint (not exported)"
        if not ev_path.exists():
            lines.append("  Not evaluated yet.")
            continue
        s = json.loads(ev_path.read_text())
        thr = s["threshold"]
        lines.append(f"  Measured on the {which}:")
        if thr["reached"]:
            lines.append(f"    Threshold chosen on dev: answer only when "
                         f"confidence >= {thr['threshold']:.2f} "
                         f"(precision >= 0.85 on dev, {_pct(thr['dev_coverage'])} "
                         "of dev answered).")
        else:
            lines.append("    No confidence threshold reached precision 0.85 "
                         "on dev, so the exported critic would never answer "
                         "(threshold 1.0).")
        for name, t in s["tests"].items():
            label = {"test": "Held-out test" + (
                " (Claude's judgments: measures agreement with Claude)"
                if task == "a" else " (articles never seen in training)"),
                "test-owner": "YOUR labels (the independent test)"}.get(
                    name, name)
            at = t["at_dev_threshold"]
            lines.append(f"    {label}, {t['n']} items: accuracy "
                         f"{_f(t['accuracy'])} (before temperature "
                         f"{_f(t['raw_accuracy'])}), ECE {_f(t['ece'])}; at the "
                         f"threshold it answers {_pct(at['coverage'])} with "
                         f"precision {_f(at['precision'])}.")
            if task == "b" and name == "test":
                lines.append("      To beat: TF-IDF 0.826 on PubMed-RCT "
                             "(0.637 on this test split); Laya zero-shot "
                             "scored 0.470.")
            if "with_critic" in t:
                w = t["with_critic"]
                lines.append(
                    f"      The engine's flags here are useful "
                    f"{_pct(t['engine_precision_without_critic'])} of the "
                    f"time; hiding the {w['flags_hidden']} the critic "
                    f"confidently calls not useful gives "
                    f"{_pct(w['engine_precision_with_critic'])} "
                    f"({w['useful_flags_hidden']} useful flags hidden).")
        ck = d / ".done-eval-ckpt"
        if which.startswith("INT8") and ck.exists():
            c = json.loads(ck.read_text())["tests"].get("test")
            meta = d / "critic" / "export-meta.json"
            agree = None
            if meta.exists():
                agree = (json.loads(meta.read_text()).get("int8_check") or
                         {}).get("same_answer")
            if c:
                lines.append(f"    Before INT8, the PyTorch checkpoint scored "
                             f"accuracy {_f(c['accuracy'])} on the same test"
                             + (f"; INT8 gives the checkpoint's answer "
                                f"{_pct(agree)} of the time" if agree
                                is not None else "") + ".")
        if task == "a" and "test-owner" not in s["tests"]:
            lines.append("    Your own labels: not provided. Label paragraphs "
                         "on the Label page, then set RESEARCHLY_LABELS and "
                         "RESEARCHLY_PARAGRAPHS (README).")
        g = d / "gate.json"
        if g.exists():
            gate = json.loads(g.read_text())
            failed = [c for c in gate["checks"] if not c["ok"]]
            lines.append(f"  Gate: {gate['verdict']}")
            for c in failed:
                lines.append(f"    - {c['check']}: {c['detail']}")
            inst = d / "installed.txt"
            if inst.exists():
                lines.append("  " + inst.read_text().strip())
        else:
            lines.append("  Gate: not run.")
    rate_lines = []
    for task in ("b", "a"):
        t = run / task / ".done-train"
        if t.exists():
            r = json.loads(t.read_text()).get("seconds_per_item")
            if r:
                rate_lines.append(f"{TASK_NAMES[task]} {r:.2f} s per "
                                  "training example")
    if rate_lines:
        lines += ["", "Measured speed on this machine: " +
                  "; ".join(rate_lines) + "."]
        q = run / "quick-projection.txt"
        if q.exists():
            lines.append(q.read_text().strip())
    return "\n".join(lines)


def projection(run: Path, device: str) -> str:
    """After a --quick run: the full run's training time at the measured
    rate."""
    parts = []
    for task in ("b", "a"):
        t = run / task / ".done-train"
        if not t.exists():
            continue
        rate = json.loads(t.read_text()).get("seconds_per_item")
        full = default_sizes(task, False)
        h = hyper(full["train"], device, False)
        mins = rate * full["train"] * h["epochs"] / 60
        parts.append(f"{TASK_NAMES[task]} ~{_hm(mins)}")
    return ("Full-run training time at that speed (quick runs include "
            "start-up, so this is an upper bound): " + ", ".join(parts)
            + ".") if parts else ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["plan", "run", "evaluate", "summary"])
    ap.add_argument("--data", type=Path)
    ap.add_argument("--run", type=Path)
    ap.add_argument("--task", choices=["a", "b", "both"], default="both")
    ap.add_argument("--device", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--batch-size", type=int, default=16)
    a = ap.parse_args(argv)
    tasks = ["b", "a"] if a.task == "both" else [a.task]
    device = a.device or ("mps" if platform.system() == "Darwin" and
                          platform.machine() == "arm64" else "cpu")
    if a.cmd == "plan":
        print_plan(plan(a.data, tasks, device, a.quick, not a.no_export))
        return 0
    if a.cmd == "summary":
        print(summary_text(a.run))
        return 0
    if not (a.data and a.run):
        ap.error("--data and --run are required")
    os.environ.setdefault("USE_TF", "0")
    if device == "mps":
        # let MPS fall back to CPU for an op it lacks instead of failing
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    a.run.mkdir(parents=True, exist_ok=True)
    for t in tasks:
        if not (a.data / f"{TASK_NAMES[t]}-train.jsonl").exists() and \
                a.cmd == "run":
            print(f"{TITLES[t]}: no training file in {a.data}; skipped")
            continue
        if a.cmd == "run":
            run_task(t, a.data, a.run, device, a.quick, not a.no_export,
                     a.epochs, a.batch_size)
        else:
            evaluate_int8(t, a.data, a.run, a.batch_size)
    if a.quick and a.cmd == "run":
        (a.run / "quick-projection.txt").write_text(projection(a.run, device))
    return 0


if __name__ == "__main__":
    sys.exit(main())

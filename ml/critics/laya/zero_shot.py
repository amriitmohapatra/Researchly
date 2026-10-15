"""Laya, zero-shot, on Researchly's two S5 tasks (PLAN S5b; ADR-06).

Zero-shot is a spike, not a candidate: Laya's own model card says its base
checkpoints are near chance on decisions they were not fine-tuned for, and
D8 says Laya is adopted only through the bake-off. This script measures
where the base checkpoint starts and proves the harness end to end.

Task B, sentence roles, on a held-out slice of the S5a weak labels
(ml/corpus/weak_labels.py writes them into the corpus cache):

    python ml/critics/laya/zero_shot.py roles \\
        --labels ~/.researchly/corpus/labels/sentences.jsonl --n 300 \\
        --out /tmp/laya-zs-roles.json

Task A, "is this flag useful?", on the owner's labelled paragraphs. The
Label page's export (researchly-labels.json) holds no text, so the script
also needs the paragraphs themselves, kept on the owner's machine:

    python ml/critics/laya/zero_shot.py flags \\
        --labels ~/Downloads/researchly-labels.json \\
        --paragraphs ~/researchly-paragraphs.json --out /tmp/laya-zs-flags.json

It re-checks each paragraph the way the Label page does, finds each label's
flag by its position, and skips (and counts) a label whose rule no longer
matches. ``--synthetic`` runs Task A on ml/critics/laya/fixtures/ (synthetic
paragraphs written for this harness) to prove the plumbing.

Reports: accuracy, macro-F1, precision at coverage (the most confident
answers kept), the coverage reaching precision 0.85, ECE before and after a
temperature fitted on a separate dev slice, and CPU latency per item.
No text is written to the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
from harness import critics  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def ask(agent, states: list, question: dict, *, rotate: bool = False,
        batch_size: int = 8, cache: Optional[Path] = None,
        batched_probe: bool = True) -> tuple:
    """(Laya probability dicts, seconds per state, batched) for the states.
    One state per call measures single-item latency honestly; batching is
    reported separately. ``cache`` (a JSONL file, outside the repo) makes a
    long CPU run resumable: each answer is appended as it arrives, keyed by
    a hash of state and question, and is not asked again."""
    qs = harness.rotations(question) if rotate else {"q": question}
    qkey = hashlib.sha256(json.dumps(qs, sort_keys=True).encode()).hexdigest()
    done = {}
    if cache is not None and Path(cache).exists():
        for line in Path(cache).read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[row["key"]] = row
    out = open(cache, "a", encoding="utf-8") if cache is not None else None
    dists, secs = [], []
    try:
        for s in states:
            key = hashlib.sha256((qkey + s).encode()).hexdigest()
            if key in done:
                dists.append(done[key]["probs"])
                secs.append(done[key]["seconds"])
                continue
            res, dt = harness.timed(agent.predict, s, qs)
            secs.append(dt)
            ans = res["answers"]
            probs = (harness.average(ans) if rotate else
                     dict(ans["q"]["probabilities"]))
            dists.append(probs)
            if out is not None:
                out.write(json.dumps({"key": key, "probs": probs,
                                      "seconds": dt}) + "\n")
                out.flush()
    finally:
        if out is not None:
            out.close()
    batched = None
    if batched_probe and hasattr(agent, "predict_batch") and \
            len(states) >= batch_size:
        chunk = states[:batch_size * 4]
        _, dt = harness.timed(agent.predict_batch, chunk, qs,
                              batch_size=batch_size)
        batched = {"states": len(chunk), "batch_size": batch_size,
                   "seconds_per_state": dt / len(chunk)}
    return dists, secs, batched


def run_roles(agent, rows: list, dev_rows: list, *, context: str,
              rotate: bool, cache: Optional[Path] = None) -> dict:
    q = critics.SENTENCE_ROLE
    lq = harness.laya_question(q)
    states = [harness.role_state(r, context) for r in rows]
    raw, secs, batched = ask(agent, states, lq, rotate=rotate, cache=cache)
    dists = [harness.from_laya(q, d) for d in raw]
    gold = [r["role"] for r in rows]
    report = {"task": "B sentence role", "question": q.id,
              "context": context, "rotations": rotate,
              "zero_shot": harness.summarise(dists, gold,
                                             [r["discipline"] for r in rows]),
              "latency_cpu": harness.latency_summary(secs),
              "latency_cpu_batched": batched,
              "baseline_to_beat": harness.BASELINE_TASK_B}
    if dev_rows:
        dev_raw, _, _ = ask(agent, [harness.role_state(r, context)
                                    for r in dev_rows], lq, rotate=rotate,
                            cache=cache, batched_probe=False)
        t = harness.fit_temperature([harness.from_laya(q, d) for d in dev_raw],
                                    [r["role"] for r in dev_rows])
        report["temperature_fitted_on_dev"] = {"t": t, "dev_n": len(dev_rows)}
        dists = [harness.temper(d, t) for d in dists]
        report["after_temperature"] = harness.summarise(dists, gold)
    report["items"] = harness.items(dists, gold,
                                    [r["discipline"] for r in rows])
    # simple references a learned model must clearly beat
    maj = max(set(gold), key=gold.count)
    report["majority_class_accuracy"] = gold.count(maj) / len(gold)
    return report


def flag_items(labels: list, paragraphs: dict, nlp=None) -> tuple:
    """[(state, gold yes/no, rule_id, category)], skipped counts."""
    import label_precision
    kept, dropped = label_precision.dedupe(labels)
    items, skipped = [], {"replaced": dropped, "unsure": 0,
                          "no paragraph text": 0, "flag not found": 0}
    cache = {}
    for x in kept:
        if x["verdict"] == "unsure":
            skipped["unsure"] += 1
            continue
        para = paragraphs.get(x.get("paragraph"))
        if para is None:
            skipped["no paragraph text"] += 1
            continue
        key = x["paragraph"]
        if key not in cache:
            cache[key] = harness.label_page_flags(para["section"],
                                                  para["text"], nlp)
        content, flags = cache[key]
        i = x.get("flag")
        if i is None or i >= len(flags) or flags[i][0] != x["rule_id"]:
            skipped["flag not found"] += 1
            continue
        rule, cat, start, end, message = flags[i]
        state = harness.flag_state(para["section"], para["text"],
                                   content[start:end], message)
        items.append((state, "yes" if x["verdict"] == "useful" else "no",
                      rule, cat))
    return items, skipped


def run_flags(agent, labels: list, paragraphs: dict, *, rotate: bool,
              nlp=None, prepared=None) -> dict:
    """Task A. ``prepared`` = (items, skipped) from ``--export-items``, so
    the engine (spaCy, LanguageTool) and Laya need not share one process."""
    q = critics.FLAG_USEFUL
    items, skipped = prepared or flag_items(labels, paragraphs, nlp)
    if not items:
        return {"task": "A flag useful", "error": "no usable labels",
                "skipped": skipped}
    raw, secs, batched = ask(agent, [s for s, *_ in items],
                             harness.laya_question(q), rotate=rotate)
    dists = [harness.from_laya(q, d) for d in raw]
    gold = [g for _, g, *_ in items]
    out = {"task": "A flag useful", "question": q.id, "rotations": rotate,
           "skipped": skipped,
           "zero_shot": harness.summarise(dists, gold,
                                          [c for *_, c in items]),
           "latency_cpu": harness.latency_summary(secs),
           "latency_cpu_batched": batched,
           "engine_precision_without_critic": gold.count("yes") / len(gold),
           "items": harness.items(dists, gold, [r for _, _, r, _ in items])}
    # What the critic is for: keep a flag only when it says "yes" confidently.
    kept = sorted(zip(dists, gold), key=lambda dg: -dg[0]["yes"])
    out["flags_kept_by_p_yes"] = {
        f"{c:.1f}": sum(g == "yes" for _, g in kept[:max(1, int(c * len(kept)))])
        / max(1, int(c * len(kept))) for c in (1.0, 0.8, 0.6, 0.4)}
    return out


def environment() -> dict:
    env = {"python": platform.python_version(), "machine": platform.machine(),
           "processor": platform.processor() or "", "when": time.strftime(
               "%Y-%m-%d")}
    try:
        import os
        env["cpus"] = os.cpu_count()
        import torch
        env["torch"] = torch.__version__
        env["torch_threads"] = torch.get_num_threads()
        import laya
        env["laya"] = laya.__version__
    except Exception:
        pass
    return env


def _flag_inputs(a, ap) -> tuple:
    if a.synthetic:
        return (FIXTURES / "synthetic-labels.json",
                FIXTURES / "synthetic-paragraphs.json")
    if not (a.labels and a.paragraphs):
        ap.error("flags needs --labels and --paragraphs (or --synthetic)")
    return a.labels, a.paragraphs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("task", choices=["roles", "flags"])
    ap.add_argument("--labels", type=Path,
                    help="roles: sentences.jsonl; flags: researchly-labels.json")
    ap.add_argument("--paragraphs", type=Path,
                    help="flags: the labelled paragraphs' text (local only)")
    ap.add_argument("--synthetic", action="store_true",
                    help="flags: run on the synthetic fixtures")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--dev-n", type=int, default=150)
    ap.add_argument("--use", choices=["train", "eval"], default=None,
                    help="roles: only articles of this use (default both)")
    ap.add_argument("--context", choices=["position", "none"],
                    default="position")
    ap.add_argument("--rotate", action="store_true",
                    help="average every cyclic option order (k x the cost)")
    ap.add_argument("--model", default=harness.LAYA_REPO)
    ap.add_argument("--revision", default=harness.LAYA_REVISION)
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--out", type=Path, help="the report (JSON, no text)")
    ap.add_argument("--cache", type=Path, default=None,
                    help="JSONL of answers so far (outside the repo); a "
                         "re-run resumes instead of asking again")
    ap.add_argument("--export-items", type=Path, default=None,
                    help="flags, stage 1 (engine only, no Laya): write the "
                         "matched flags to this JSONL (it holds paragraph "
                         "text: keep it local) and stop")
    ap.add_argument("--items", type=Path, default=None,
                    help="flags, stage 2 (Laya only): read --export-items")
    a = ap.parse_args(argv)

    if a.task == "flags" and a.export_items:
        import label_precision
        labels_path, paras_path = _flag_inputs(a, ap)
        items, skipped = flag_items(label_precision.load(labels_path),
                                    harness.label_paragraphs(paras_path))
        with a.export_items.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"skipped": skipped}) + "\n")
            for state, gold, rule, cat in items:
                f.write(json.dumps({"state": state, "gold": gold, "rule": rule,
                                    "category": cat}) + "\n")
        print(json.dumps({"items": len(items), "skipped": skipped}))
        return 0
    if not a.out:
        ap.error("--out is required")
    agent = harness.load_agent(a.model, a.revision, threads=a.threads)
    if a.task == "roles":
        if not a.labels:
            ap.error("roles needs --labels sentences.jsonl")
        rows = harness.read_jsonl(a.labels)
        test = harness.sample_roles(rows, a.n, split="test", use=a.use)
        dev = harness.sample_roles(rows, a.dev_n, split="dev", use=a.use)
        report = run_roles(agent, test, dev, context=a.context,
                           rotate=a.rotate, cache=a.cache)
    elif a.items:
        rows = harness.read_jsonl(a.items)
        prepared = ([(r["state"], r["gold"], r["rule"], r["category"])
                     for r in rows[1:]], rows[0]["skipped"])
        report = run_flags(agent, [], {}, rotate=a.rotate, prepared=prepared)
        report["synthetic"] = a.synthetic
    else:
        import label_precision
        labels_path, paras_path = _flag_inputs(a, ap)
        report = run_flags(agent, label_precision.load(labels_path),
                           harness.label_paragraphs(paras_path),
                           rotate=a.rotate)
        report["synthetic"] = a.synthetic
    report["model"] = {"repo": a.model, "revision": a.revision}
    report["environment"] = environment()
    a.out.write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
from harness import critics  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def ask(agent, states: list, question: dict, *, rotate: bool = False,
        batch_size: int = 8) -> tuple:
    """(Laya probability dicts, seconds per state, batched) for the states.
    One state per call measures single-item latency honestly; batching is
    reported separately."""
    qs = harness.rotations(question) if rotate else {"q": question}
    dists, secs = [], []
    for s in states:
        res, dt = harness.timed(agent.predict, s, qs)
        secs.append(dt)
        ans = res["answers"]
        dists.append(harness.average(ans) if rotate else
                     dict(ans["q"]["probabilities"]))
    batched = None
    if hasattr(agent, "predict_batch") and len(states) >= batch_size:
        chunk = states[:batch_size * 4]
        _, dt = harness.timed(agent.predict_batch, chunk, qs,
                              batch_size=batch_size)
        batched = {"states": len(chunk), "batch_size": batch_size,
                   "seconds_per_state": dt / len(chunk)}
    return dists, secs, batched


def run_roles(agent, rows: list, dev_rows: list, *, context: str,
              rotate: bool) -> dict:
    q = critics.SENTENCE_ROLE
    lq = harness.laya_question(q)
    states = [harness.role_state(r, context) for r in rows]
    raw, secs, batched = ask(agent, states, lq, rotate=rotate)
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
                                    for r in dev_rows], lq, rotate=rotate)
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
              nlp=None) -> dict:
    q = critics.FLAG_USEFUL
    items, skipped = flag_items(labels, paragraphs, nlp)
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
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)

    agent = harness.load_agent(a.model, a.revision, threads=a.threads)
    if a.task == "roles":
        if not a.labels:
            ap.error("roles needs --labels sentences.jsonl")
        rows = harness.read_jsonl(a.labels)
        test = harness.sample_roles(rows, a.n, split="test", use=a.use)
        dev = harness.sample_roles(rows, a.dev_n, split="dev", use=a.use)
        report = run_roles(agent, test, dev, context=a.context,
                           rotate=a.rotate)
    else:
        sys.path.insert(0, str(harness.REPO / "ml" / "eval"))
        import label_precision
        if a.synthetic:
            labels_path = FIXTURES / "synthetic-labels.json"
            paras_path = FIXTURES / "synthetic-paragraphs.json"
        else:
            if not (a.labels and a.paragraphs):
                ap.error("flags needs --labels and --paragraphs "
                         "(or --synthetic)")
            labels_path, paras_path = a.labels, a.paragraphs
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

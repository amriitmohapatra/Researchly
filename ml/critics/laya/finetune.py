"""Fine-tune Laya for Researchly's S5 tasks (PLAN S5b; ADR-06).

Two steps. ``data`` builds the training files (JSONL in the format Laya's
own trainer and its ``laya-evals`` read: ``state``, ``questions``,
``expected``); ``train`` runs Laya's trainer (``laya.train.finetune``: RLCD
loss, calibration temperatures fitted on a slice held out before training).
Both run on a free Kaggle GPU (T4, 16 GB) or a 16 GB Apple Silicon Mac; the
README gives the exact commands.

Task B, sentence roles, from the S5a weak labels (training articles only;
the test split is never read here):

    python ml/critics/laya/finetune.py data roles \\
        --labels ~/.researchly/corpus/labels/sentences.jsonl --out data/
    python ml/critics/laya/finetune.py train --data data/roles-train.jsonl \\
        --eval-data data/roles-dev.jsonl --out ckpt-roles --device cuda

Task A, flag re-ranker, from the owner's labels plus the paragraphs' text
(local only), optionally with the text-free accept/dismiss telemetry as a
per-rule prior:

    python ml/critics/laya/finetune.py data flags \\
        --labels researchly-labels.json --paragraphs paragraphs.json \\
        [--telemetry ~/.researchly/telemetry.jsonl] --out data/

Only articles whose manifest ``use`` is "train" (CC BY / CC0) go into
training files; "eval" articles (CC BY-NC/ND/SA) can only evaluate.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
from harness import critics  # noqa: E402


def role_rows(rows: list, split: str, *, context: str = "position",
              max_per_role: int = 0, seed: int = 20261015) -> list:
    """Laya training rows for one split of the weak labels. Only
    trainable (use == "train") articles; optionally capped per role so a
    dominant role does not swamp the rest."""
    q = critics.SENTENCE_ROLE
    lq = harness.laya_question(q)
    pick = [r for r in rows if r["split"] == split and r["use"] == "train"]
    if max_per_role:
        by_role: dict = defaultdict(list)
        for r in pick:
            by_role[r["role"]].append(r)
        rng = random.Random(seed)
        pick = []
        for role in sorted(by_role):
            group = by_role[role]
            rng.shuffle(group)
            pick.extend(group[:max_per_role])
        rng.shuffle(pick)
    return [{"state": harness.role_state(r, context),
             "questions": {q.id: lq},
             "expected": {q.id: r["role"]},
             "meta": {"pmcid": r["pmcid"], "discipline": r["discipline"]}}
            for r in pick]


def flag_rows(labels: list, paragraphs: dict, priors=None, nlp=None) -> tuple:
    """Laya training rows for Task A, and what was skipped."""
    import zero_shot
    items, skipped = zero_shot.flag_items(labels, paragraphs, nlp)
    q = critics.FLAG_USEFUL
    lq = harness.laya_question(q)
    out = []
    for state, gold, rule, cat in items:
        if priors:
            section = state.split("\n", 1)[0].replace("Section: ", "")
            p = harness.prior_text(priors, rule, section)
            if p:
                state += "\n" + p
        out.append({"state": state, "questions": {q.id: lq},
                    "expected": {q.id: "A" if gold == "yes" else "B"},
                    "meta": {"rule_id": rule, "category": cat}})
    return out, skipped


def split_by_paragraph(rows: list, dev_frac: float = 0.2,
                       seed: int = 20261015) -> tuple:
    """Task A train/dev split by paragraph, so one paragraph's flags never
    sit on both sides."""
    rng = random.Random(seed)
    keys = sorted({r["state"].split("\nFlagged words:")[0] for r in rows})
    rng.shuffle(keys)
    dev_keys = set(keys[:max(1, int(len(keys) * dev_frac))])
    train = [r for r in rows if r["state"].split("\nFlagged words:")[0]
             not in dev_keys]
    dev = [r for r in rows if r["state"].split("\nFlagged words:")[0]
           in dev_keys]
    return train, dev


def write_jsonl(rows: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if k != "meta"},
                               ensure_ascii=False) + "\n")


def cmd_data(a) -> int:
    out = Path(a.out)
    if a.task == "roles":
        rows = harness.read_jsonl(a.labels)
        train = role_rows(rows, "train", context=a.context,
                          max_per_role=a.max_per_role)
        dev = role_rows(rows, "dev", context=a.context)
        write_jsonl(train, out / "roles-train.jsonl")
        write_jsonl(dev, out / "roles-dev.jsonl")
        print(json.dumps({"train": len(train), "dev": len(dev),
                          "train_roles": Counter(r["expected"]["sentence-role"]
                                                 for r in train)}, indent=1))
        return 0
    import label_precision
    priors = harness.telemetry_priors(a.telemetry) if a.telemetry else None
    rows, skipped = flag_rows(label_precision.load(a.labels),
                              harness.label_paragraphs(a.paragraphs), priors)
    train, dev = split_by_paragraph(rows)
    write_jsonl(train, out / "flags-train.jsonl")
    write_jsonl(dev, out / "flags-dev.jsonl")
    print(json.dumps({"train": len(train), "dev": len(dev),
                      "skipped": skipped}, indent=1))
    return 0


def cmd_train(a) -> int:
    from laya.train import TrainConfig, finetune
    cfg = TrainConfig(epochs=a.epochs, micro_batch=a.micro_batch,
                      grad_accum=a.grad_accum, loss=a.loss,
                      shuffle_options=("choice",) if a.shuffle_options else (),
                      seed=a.seed,
                      eval_data=str(a.eval_data) if a.eval_data else None)
    base = a.base
    if not Path(base).exists():
        # Pin the base checkpoint: Laya's trainer takes a Hub id without a
        # revision, so fetch the pinned snapshot and train from the folder.
        from huggingface_hub import snapshot_download
        base = snapshot_download(base, revision=a.revision, allow_patterns=[
            "model.safetensors", "rl_agent_config.json", "config.json",
            "encoder/*", "tokenizer/*"])
    report = finetune(str(a.data), base, str(a.out_dir), cfg,
                      device=a.device)
    keep = {k: report.get(k) for k in ("train_items", "calibration_items",
                                        "skipped", "epoch_loss",
                                        "temperature", "calibration")}
    keep["base"] = a.base if Path(a.base).exists() else f"{a.base}@{a.revision}"
    (Path(a.out_dir) / "researchly-train-report.json").write_text(
        json.dumps(keep, indent=1, default=str))
    print(json.dumps(keep, indent=1, default=str))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("data", help="build the training JSONL files")
    d.add_argument("task", choices=["roles", "flags"])
    d.add_argument("--labels", type=Path, required=True)
    d.add_argument("--paragraphs", type=Path)
    d.add_argument("--telemetry", type=Path)
    d.add_argument("--context", choices=["position", "none"],
                   default="position")
    d.add_argument("--max-per-role", type=int, default=0)
    d.add_argument("--out", type=Path, required=True)
    t = sub.add_parser("train", help="fine-tune with Laya's trainer")
    t.add_argument("--data", type=Path, required=True)
    t.add_argument("--eval-data", type=Path)
    t.add_argument("--base", default=harness.LAYA_REPO,
                   help="Hub id (pinned via laya's revision handling) or a "
                        "local checkpoint folder")
    t.add_argument("--revision", default=harness.LAYA_REVISION)
    t.add_argument("--out", dest="out_dir", type=Path, required=True)
    t.add_argument("--device", default="auto")
    t.add_argument("--epochs", type=int, default=4)
    t.add_argument("--micro-batch", type=int, default=8)
    t.add_argument("--grad-accum", type=int, default=8)
    t.add_argument("--loss", choices=["rlcd", "soft-ce"], default="rlcd")
    t.add_argument("--shuffle-options", action="store_true")
    t.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    if a.cmd == "data":
        if a.task == "flags" and not a.paragraphs:
            ap.error("flags needs --paragraphs")
        return cmd_data(a)
    return cmd_train(a)


if __name__ == "__main__":
    sys.exit(main())

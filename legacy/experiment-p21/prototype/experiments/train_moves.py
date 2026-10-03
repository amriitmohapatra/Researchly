#!/usr/bin/env python3
"""Train the v0 rhetorical-move classifier (researchly/moves.py artifact).

Usage:
    python train_moves.py /path/to/PubMed_20k_RCT [--out DIR]

Corpus: PubMed RCT (Dernoncourt & Lee 2017), the 20k split — files
train.txt / dev.txt / test.txt, each line "LABEL\\tsentence", abstracts
separated by ###id lines. Public, citable, standard benchmark for this
task. Get it with:
    git clone --depth 1 https://github.com/Franck-Dernoncourt/pubmed-rct

Model: TF-IDF (word 1-2 grams, digits masked) → multinomial logistic
regression. Deliberately linear: trains in minutes on CPU, artifact is a
few MB, probabilities are usable for abstention, and linear baselines
are within a few points of neural models on this corpus. The
MoveClassifier class is the swap point when an encoder model earns its
footprint — this script's job is to make v0 REPRODUCIBLE and MEASURED.

Outputs into --out (default: researchly/data/models/):
    move_clf.joblib       the sklearn pipeline (compressed)
    move_clf.meta.json    provenance: corpus, seed, versions, metrics
    move_clf.metrics.md   full held-out report incl. the abstention curve

Keep _normalize() here in sync with researchly/moves.py.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

SEED = 20260814
_WS = re.compile(r"\s+")


def _normalize(sentence: str) -> str:
    s = _WS.sub(" ", (sentence or "").strip())
    return re.sub(r"\d", "0", s)


def read_split(path: Path):
    """[(label, sentence)] from one PubMed-RCT file."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("###"):
            continue
        label, _, sent = line.partition("\t")
        if label and sent:
            out.append((label, sent))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", type=Path,
                    help="folder containing train.txt/dev.txt/test.txt")
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parents[1]
                    / "researchly" / "data" / "models")
    ap.add_argument("--max-features", type=int, default=75_000)
    args = ap.parse_args()

    import joblib
    import numpy as np
    import sklearn
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.pipeline import Pipeline

    print("reading corpus …")
    train = read_split(args.corpus / "train.txt")
    test = read_split(args.corpus / "test.txt")
    x_tr = [_normalize(s) for _, s in train]
    y_tr = [lb for lb, _ in train]
    x_te = [_normalize(s) for _, s in test]
    y_te = [lb for lb, _ in test]
    print(f"  train {len(train):,} · test {len(test):,} sentences")

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=3,
                                  max_features=args.max_features,
                                  sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=200, C=4.0,
                                   solver="saga", n_jobs=-1,
                                   random_state=SEED)),
    ])
    print("training …")
    pipeline.fit(x_tr, y_tr)

    print("evaluating …")
    probs = pipeline.predict_proba(x_te)
    classes = list(pipeline.classes_)
    pred = [classes[i] for i in probs.argmax(axis=1)]
    acc = accuracy_score(y_te, pred)
    report = classification_report(y_te, pred, digits=3)

    # Abstention curve: accuracy vs coverage at rising thresholds — this
    # is what justifies moves.CONFIDENCE_THRESHOLD.
    conf = probs.max(axis=1)
    curve = []
    for thr in (0.0, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        keep = conf >= thr
        cov = float(keep.mean())
        acc_k = (accuracy_score(
            [y for y, k in zip(y_te, keep) if k],
            [p for p, k in zip(pred, keep) if k]) if keep.any() else 0.0)
        curve.append({"threshold": thr, "coverage": round(cov, 4),
                      "accuracy": round(acc_k, 4)})

    args.out.mkdir(parents=True, exist_ok=True)
    model_path = args.out / "move_clf.joblib"
    joblib.dump(pipeline, model_path, compress=("xz", 6))

    meta = {
        "version": "moves-v0-tfidf-logreg-20260814",
        "corpus": "PubMed 20k RCT (Dernoncourt & Lee 2017)",
        "labels": classes,
        "seed": SEED,
        "trained": datetime.date.today().isoformat(),
        "sklearn": sklearn.__version__,
        "n_train": len(train),
        "n_test": len(test),
        "max_features": args.max_features,
        "test_accuracy": round(float(acc), 4),
        "abstention_curve": curve,
        "notes": ("Linear v0. 'gap' has no labelled corpus and stays "
                  "lexicon-detected. Swap point: researchly/moves.py."),
    }
    (args.out / "move_clf.meta.json").write_text(
        json.dumps(meta, indent=1), encoding="utf-8")

    md = ["# move_clf held-out report", "",
          f"corpus: {meta['corpus']} · seed {SEED} · "
          f"sklearn {sklearn.__version__}",
          f"test accuracy: **{acc:.4f}** "
          f"({len(test):,} sentences)", "",
          "```", report.rstrip(), "```", "",
          "## Abstention curve (threshold → coverage, accuracy)", ""]
    md += [f"- {c['threshold']:.1f} → coverage {c['coverage']:.1%}, "
           f"accuracy {c['accuracy']:.1%}" for c in curve]
    (args.out / "move_clf.metrics.md").write_text(
        "\n".join(md) + "\n", encoding="utf-8")

    size_mb = model_path.stat().st_size / 1e6
    print(f"test accuracy {acc:.4f} · artifact {size_mb:.1f} MB "
          f"→ {model_path}")
    print("abstention:", curve)
    return 0


if __name__ == "__main__":
    sys.exit(main())

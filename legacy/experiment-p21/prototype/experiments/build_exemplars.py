#!/usr/bin/env python3
"""Build (or rebuild) the exemplar index used by the drafting guide.

Usage:
    python build_exemplars.py [FOLDER ...] [--out FILE]

With no folders given, indexes the repo's two corpora:
    prototype/dogfood/text/        8 accepted PhD theses (PDF-extracted)
    prototype/experiments/corpus/  published papers (PMC OA + user PDFs)

Each .txt file becomes exemplars: sentences are quality-gated
(exemplars.looks_like_prose — length band, prose ratio, no PDF
artifacts), labelled with the SAME hybrid labeller the guide uses
(guide.label_hybrid), and kept only when the label is confident
(lexicon hits, or model probability >= --min-conf, default 0.75 —
stricter than the guide's own threshold because these sentences are
shown as models to imitate). Per-document-per-move cap keeps one long
document from dominating a move.

Source attribution: the first "# " line of the file if present (papers
carry "# Author et al. · Journal Year"), else the filename stem.

Output: JSONL at researchly/data/exemplars/exemplars.jsonl — one
inspectable line per exemplar. Rerun any time the corpus folder grows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTO = HERE.parent
sys.path.insert(0, str(PROTO))

from researchly.exemplars import (INDEX_FILE, looks_like_prose,  # noqa: E402
                                  split_sentences)
from researchly.guide import label_hybrid  # noqa: E402
from researchly.moves import get_classifier  # noqa: E402

PER_DOC_PER_MOVE = 40


def source_name(path: Path, text: str) -> str:
    lines = text.splitlines()
    if len(lines) >= 2 and lines[1].startswith("# "):
        return lines[1][2:].strip()
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip()
    return path.stem


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="*", type=Path)
    ap.add_argument("--out", type=Path, default=INDEX_FILE)
    ap.add_argument("--min-conf", type=float, default=0.75)
    args = ap.parse_args()

    folders = args.folders or [PROTO / "dogfood" / "text",
                               HERE / "corpus"]
    clf = get_classifier()
    if not clf.available():
        print("error: move classifier unavailable "
              f"({clf.why_unavailable()}) — train it first "
              "(experiments/train_moves.py)", file=sys.stderr)
        return 1

    rows: list = []
    per_doc: dict = {}
    files = [p for folder in folders if folder.is_dir()
             for p in sorted(folder.glob("*.txt"))]
    if not files:
        print(f"error: no .txt files under {folders}", file=sys.stderr)
        return 1

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        src = source_name(path, text)
        body = "\n".join(ln for ln in text.splitlines()
                         if not ln.startswith("# "))
        counts: dict = {}
        sentences = [s for s in split_sentences(body)
                     if looks_like_prose(s)]
        labels = ([label_hybrid(s, clf) for s in sentences]
                  if sentences else [])
        for sent, (move, conf, how) in zip(sentences, labels):
            if move == "other":
                continue
            if how == "model" and conf < args.min_conf:
                continue
            if counts.get(move, 0) >= PER_DOC_PER_MOVE:
                continue
            counts[move] = counts.get(move, 0) + 1
            rows.append({"text": sent, "move": move,
                         "confidence": round(float(conf), 3),
                         "how": how, "source": src})
        per_doc[src] = counts
        print(f"  {path.name}: {sum(counts.values())} exemplars "
              f"{dict(sorted(counts.items()))}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_move: dict = {}
    for r in rows:
        by_move[r["move"]] = by_move.get(r["move"], 0) + 1
    print(f"\nwrote {len(rows)} exemplars from {len(files)} documents "
          f"→ {args.out}")
    print("by move:", dict(sorted(by_move.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Build S001's error model, ``researchly/data/spell_errors.json``.

The noisy-channel ranker (researchly/spellrank.py) needs P(typed | meant):
how likely each character edit is. This tool learns it from lists of
(misspelling, intended word) pairs, in the manner of Kernighan, Church &
Gale (1990) with one letter of left context (after Brill & Moore 2000):

    P(edit | context) = (count of the edit + 0.5) / (count of the context
                         in the intended words + 1)

Only lists whose ``ml/datasets.yaml`` entry permits ``ship_model`` may be
used: the table is a model derived from them and ships in the engine. The
tool refuses any other source id. Only the "train" split of each list is
used (ml/eval/spelling_bench.py's hash split), so the "test" split stays
unseen for the benchmark.

    python3.10 ml/tools/build_spell_errors.py \
        --pairs NAME=FILE:FORMAT [--pairs ...] [--out PATH]

With ``--experiment``, sources registered for ``train_experimental`` are
accepted too, and the table must be written outside the repository: it is
for measuring what a learned model would add (ml/eval/spelling_bench.py
``--errors``), never for shipping.

FORMAT is one of spelling_bench's formats (colon, dollar, arrow, csv, tsv).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "ml" / "eval"))

DEFAULT_OUT = (ROOT / "packages" / "core" / "researchly" / "data"
               / "spell_errors.json")
MIN_COUNT = 2


def registry_permits(source_id: str, use: str = "ship_model") -> bool:
    import yaml
    data = yaml.safe_load((ROOT / "ml" / "datasets.yaml").read_text(
        encoding="utf-8"))
    for entry in data.get("datasets") or data.get("entries") or []:
        if entry.get("id") == source_id:
            return use in (entry.get("permitted_use") or [])
    return False


def load_pairs(path: Path, fmt: str) -> list[tuple[str, str]]:
    import spelling_bench as sb
    text = path.read_text(encoding="utf-8", errors="replace")
    if fmt == "tsv":
        rows = [tuple(line.split("\t")[:2]) for line in text.splitlines()
                if "\t" in line]
    else:
        rows = sb.parse(text, fmt)
    return [p for p in sb.clean(rows) if sb.split_of(p[0]) == "train"]


def context_counts(words: list[str]) -> Counter:
    """How often each one- and two-letter context occurs in the intended
    words, with "^" marking the start of a word."""
    c: Counter = Counter()
    for w in words:
        s = "^" + w
        for i in range(len(s)):
            c[s[i]] += 1
            if i + 1 < len(s):
                c[s[i:i + 2]] += 1
    return c


def build(pairs: list[tuple[str, str]]) -> dict:
    from researchly.spellrank import edits

    counts: Counter = Counter()
    for typed, meant in pairs:
        for kind, src, dst in edits(typed, meant):
            counts[(kind, src, dst)] += 1
    ctx = context_counts([m for _, m in pairs])
    table = {}
    for (kind, src, dst), n in counts.items():
        if n < MIN_COUNT:
            continue
        base = ctx.get(src, 0)
        table[f"{kind}|{src}|{dst}"] = round(
            math.log((n + 0.5) / (base + 1)), 3)
    floor = round(min(table.values()) - math.log(2), 3) if table else None
    return {"version": 1, "pairs": len(pairs), "min_count": MIN_COUNT,
            "floor": floor, "edits": dict(sorted(table.items()))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pairs", action="append", required=True,
                    help="REGISTRY_ID=FILE:FORMAT")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--experiment", action="store_true")
    args = ap.parse_args(argv)
    use = "train_experimental" if args.experiment else "ship_model"
    if args.experiment and ROOT in args.out.resolve().parents:
        print("refused: an experimental table must be written outside the "
              "repository", file=sys.stderr)
        return 2

    pairs: list[tuple[str, str]] = []
    sources = []
    for spec in args.pairs:
        source_id, rest = spec.split("=", 1)
        path, fmt = rest.rsplit(":", 1)
        if not registry_permits(source_id, use):
            print(f"refused: ml/datasets.yaml does not permit {use} "
                  f"for '{source_id}'", file=sys.stderr)
            return 2
        got = load_pairs(Path(path), fmt)
        print(f"{source_id}: {len(got)} training pairs", file=sys.stderr)
        pairs += got
        sources.append(source_id)
    model = build(pairs)
    model["sources"] = sources
    args.out.write_text(json.dumps(model, indent=0, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"{len(model['edits'])} edits from {model['pairs']} pairs → "
          f"{args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

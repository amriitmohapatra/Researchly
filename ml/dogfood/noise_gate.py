"""Noise-floor gate: fail if a change makes Researchly noisier on accepted theses.

Accepted PhD theses passed examination, so every flag Researchly raises on
them is a candidate false positive. The flags-per-1000-words rate over that
corpus is the project's proxy for false-positive fatigue (CLAUDE.md #5,
ARCHITECTURE.md Q3).

The gate compares a fresh run of run_dogfood.py against the committed
baseline (baseline.json beside this file):

    python3.10 run_dogfood.py                     # with RESEARCHLY_CORPUS_OUT=<dir>
    python3.10 noise_gate.py <dir>/corpus_stats.json
    python3.10 noise_gate.py <dir>/corpus_stats.json --update   # accept a new baseline

It fails when the total rate rises by more than TOLERANCE. A rule change
that is *meant* to add flags updates the baseline in the same pull request,
so the increase is visible in review rather than silently absorbed.

The baseline is not the target: Q3 asks for <= 11/1000w and the corpus is
above that today. Lowering the baseline is progress; raising it needs a
reason in the PR description.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "baseline.json"

# LanguageTool's rule set can move between releases even when ours does not,
# and the grammar tier is ~2/1000w of the total, so allow a small band.
TOLERANCE = 0.3          # flags per 1000 words
TARGET = 11.0            # ARCHITECTURE.md Q3
SILENT_MIN = 20          # a rule this busy in the baseline must not fall to zero


def summarise(stats: dict) -> dict:
    words = sum(v["words"] for v in stats.values())
    total = sum(v["suggestions"] for v in stats.values())
    by_rule = Counter()
    for v in stats.values():
        by_rule.update(v["by_rule"])
    return {
        "documents": len(stats),
        "words": words,
        "suggestions": total,
        "per_1000_words": round(1000 * total / max(words, 1), 2),
        "by_rule": dict(by_rule.most_common()),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("stats", type=Path, help="corpus_stats.json from run_dogfood.py")
    ap.add_argument("--update", action="store_true",
                    help="write this run as the new baseline")
    ap.add_argument("--note", default="",
                    help="why the baseline moved (stored with --update)")
    args = ap.parse_args(argv)

    current = summarise(json.loads(args.stats.read_text()))

    if args.update:
        current["note"] = args.note
        BASELINE.write_text(json.dumps(current, indent=2) + "\n")
        print(f"baseline written: {current['per_1000_words']}/1000w "
              f"over {current['words']:,} words")
        return 0

    if not BASELINE.exists():
        print(f"no baseline at {BASELINE}; run with --update first", file=sys.stderr)
        return 2
    base = json.loads(BASELINE.read_text())

    if current["documents"] != base["documents"]:
        print(f"corpus changed: {current['documents']} documents vs "
              f"{base['documents']} in the baseline; re-baseline deliberately",
              file=sys.stderr)
        return 2

    delta = round(current["per_1000_words"] - base["per_1000_words"], 2)
    print(f"noise floor: {current['per_1000_words']}/1000w "
          f"(baseline {base['per_1000_words']}, delta {delta:+}, "
          f"target <= {TARGET})")

    rules = sorted(set(current["by_rule"]) | set(base["by_rule"]))
    moved = [(r, base["by_rule"].get(r, 0), current["by_rule"].get(r, 0))
             for r in rules
             if base["by_rule"].get(r, 0) != current["by_rule"].get(r, 0)]
    if moved:
        print("rules whose flag counts changed:")
        for r, b, c in sorted(moved, key=lambda m: m[2] - m[1], reverse=True):
            print(f"  {r:8s} {b:>5} -> {c:<5} ({c - b:+})")

    # A quieter run is not automatically a better one: if LanguageTool or
    # SymSpell failed to load, their rules drop to zero and the rate falls.
    # That is a dead tier (CLAUDE.md: never let a tier fail silently).
    silent = [r for r, b, c in moved if c == 0 and b >= SILENT_MIN]
    if silent:
        print(f"FAIL: {', '.join(silent)} produced no flags at all "
              f"(baseline >= {SILENT_MIN} each). A tier has probably failed to "
              "load; check health before trusting this run. If a rule was "
              "deliberately removed, re-run with --update.", file=sys.stderr)
        return 1

    if delta > TOLERANCE:
        print(f"FAIL: noise floor rose by {delta}/1000w (tolerance {TOLERANCE}). "
              "Re-tune, or if the new flags are intended, re-run with --update "
              "and justify it in the PR.", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Spelling benchmark: how well S001 finds and fixes real misspellings.

Measures, on lists of (misspelling, intended word) pairs:

* **detection**: the share of misspellings S001 does not accept as words
  (spelling.known_with_fallbacks); a misspelling it accepts is a miss;
* **top-1 / top-3**: the share of detected misspellings whose intended word
  is the first, or among the first three, suggestions;
* **false alarms**: the share of the intended words themselves that S001
  would flag (each list's correct side is a free set of real words).

Two rankers are compared on the same pairs: SymSpell alone (edit distance,
then frequency, as S001 ranked until 2026-10-14) and the noisy-channel
ranker (researchly/spellrank.py). Pairs carry no context, so the context
term is off here; context is measured by the sentence cases in the tests.

Lists are fetched at run time into a local cache, never committed. Each one
must have an entry in ml/datasets.yaml that permits evaluation.

    python3.10 ml/eval/spelling_bench.py [--list NAME ...] [--split dev|test]
        [--cache DIR] [--pairs FILE ...] [--json OUT]

The split is deterministic (a hash of the misspelling): "train" (80%) is
what ml/tools/build_spell_errors.py learns the error model from and what
weights are tuned on; "test" (20%) is for reporting. Never tune on "test".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "core"))

# name -> (url, format, datasets.yaml id). Formats:
#   "colon":  "correct: typo typo …" per line (Norvig's spell-testset files)
#   "dollar": "$correct" then one misspelling per line (Mitton's corpora)
#   "arrow":  "typo->correct" or "typo->a, b" per line (typo dictionaries)
#   "csv":    "typo,correct[,…]" per line
_MITTON = "https://titan.dcs.bbk.ac.uk/~ROGER/"
LISTS: dict[str, tuple[str, str, str]] = {
    # Mitton's corpora (Birkbeck): no licence stated; evaluation only.
    "birkbeck": (_MITTON + "missp.dat", "dollar", "mitton-misspelling-corpora"),
    "holbrook": (_MITTON + "holbrook-missp.dat", "dollar",
                 "mitton-misspelling-corpora"),
    "aspell": (_MITTON + "aspell.dat", "dollar", "mitton-misspelling-corpora"),
    "wikipedia-mitton": (_MITTON + "wikipedia.dat", "dollar",
                         "mitton-misspelling-corpora"),
    # Norvig's test sets (drawn from Birkbeck); evaluation only.
    "norvig1": ("https://norvig.com/spell-testset1.txt", "colon",
                "norvig-spell-testsets"),
    "norvig2": ("https://norvig.com/spell-testset2.txt", "colon",
                "norvig-spell-testsets"),
    # Wikipedia's machine-readable list (CC BY-SA 4.0); evaluation only.
    "wikipedia": ("https://en.wikipedia.org/w/index.php?title=Wikipedia:"
                  "Lists_of_common_misspellings/For_machines&action=raw",
                  "arrow", "wikipedia-misspellings-for-machines"),
}


def parse(text: str, fmt: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if fmt == "colon":
        for line in text.splitlines():
            if ":" not in line:
                continue
            right, wrongs = line.split(":", 1)
            pairs += [(w, right.strip()) for w in wrongs.split()]
    elif fmt == "dollar":
        right = None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("$"):
                right = line[1:].strip()
            elif line and right:
                pairs.append((line.split()[0], right))
    elif fmt == "arrow":
        for line in text.splitlines():
            if "->" not in line:
                continue
            typo, fixes = line.split("->", 1)
            fix = fixes.split(",")[0].strip()
            pairs.append((typo.strip(), fix))
    elif fmt == "csv":
        for line in text.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                pairs.append((parts[0], parts[1]))
    else:
        raise ValueError(f"unknown format {fmt}")
    return pairs


def clean(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Single lower-case words only, misspelling ≠ intended, deduplicated."""
    seen = set()
    out = []
    for typo, right in pairs:
        if not (typo.isalpha() and right.isalpha()):
            continue
        if not (typo.islower() and right.islower()) or typo == right:
            continue
        if (typo, right) in seen:
            continue
        seen.add((typo, right))
        out.append((typo, right))
    return out


def split_of(typo: str) -> str:
    h = int(hashlib.sha256(typo.encode("utf-8")).hexdigest()[:8], 16)
    return "test" if h % 5 == 0 else "train"


def fetch(name: str, cache: Path) -> str:
    url, _fmt, _reg = LISTS[name]
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{name}.txt"
    if not path.exists():
        req = urllib.request.Request(
            url, headers={"User-Agent": "researchly-spelling-bench/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            path.write_bytes(r.read())
    return path.read_text(encoding="utf-8", errors="replace")


def evaluate(pairs: list[tuple[str, str]]) -> dict:
    from researchly import spelling, spellrank

    known = spelling.known_with_fallbacks
    n = len(pairs)
    detected = [(t, r) for t, r in pairs if not known(t)]
    res = {"pairs": n, "detected": len(detected)}
    for name, ranker in (
            ("symspell", lambda w: [c for c, _ in
                                    spelling.suggest_with_distance(w, 3)]),
            ("noisy_channel", lambda w: [c for c, _ in
                                         spellrank.rank(w, top_n=3)])):
        top1 = top3 = 0
        for typo, right in detected:
            got = ranker(typo)
            top1 += bool(got) and got[0] == right
            top3 += right in got
        res[name] = {"top1": top1, "top3": top3}
    rights = sorted({r for _, r in pairs})
    res["intended_words"] = len(rights)
    res["false_alarms"] = sum(1 for r in rights if not known(r))
    return res


def report(name: str, r: dict) -> str:
    def pct(a, b):
        return f"{100 * a / b:.1f}%" if b else "n/a"
    d = r["detected"]
    lines = [f"## {name}", "",
             f"- pairs: {r['pairs']}; detected: {d} ({pct(d, r['pairs'])})",
             f"- false alarms on the intended words: {r['false_alarms']} of "
             f"{r['intended_words']} ({pct(r['false_alarms'], r['intended_words'])})",
             "", "| ranker | top-1 | top-3 |", "|---|---|---|"]
    for k in ("symspell", "noisy_channel"):
        lines.append(f"| {k} | {pct(r[k]['top1'], d)} | "
                     f"{pct(r[k]['top3'], d)} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="append", default=[],
                    help="a list from LISTS (repeatable); default: all")
    ap.add_argument("--pairs", action="append", default=[],
                    help="a local file of 'typo<TAB>correct' lines")
    ap.add_argument("--split", choices=("train", "test", "all"),
                    default="test")
    ap.add_argument("--cache", type=Path,
                    default=Path.home() / ".cache" / "researchly-spelling")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--errors", type=Path,
                    help="an error-model table to rank with instead of the "
                         "shipped one (an experiment's output)")
    args = ap.parse_args(argv)
    if args.errors:
        from researchly import spellrank
        spellrank.ERRORS_FILE = args.errors
        spellrank._ERRORS = None

    sets: dict[str, list[tuple[str, str]]] = {}
    for name in args.list or ([] if args.pairs else list(LISTS)):
        sets[name] = parse(fetch(name, args.cache), LISTS[name][1])
    for path in args.pairs:
        rows = [tuple(line.strip().split("\t")[:2]) for line in
                Path(path).read_text(encoding="utf-8").splitlines()
                if "\t" in line]
        sets[Path(path).stem] = rows
    results = {}
    for name, pairs in sets.items():
        pairs = clean(pairs)
        if args.split != "all":
            pairs = [p for p in pairs if split_of(p[0]) == args.split]
        results[name] = evaluate(pairs)
        print(report(f"{name} ({args.split})", results[name]))
    if args.json:
        args.json.write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

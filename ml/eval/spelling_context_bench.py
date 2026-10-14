"""Context benchmark for S001's ranker: typos planted in published prose.

The public misspelling lists (spelling_bench.py) have no context, so they
cannot show what the neighbouring words add. This plants one synthetic slip
(a dropped, swapped, doubled or substituted letter) in about 2% of the
known lower-case words of the CC BY / CC0 PMC articles of the real-document
bench (registry realdocs-europepmc-oa: ci_eval), and compares the first
suggestion of SymSpell alone with the noisy-channel ranker given the word
either side. Fixed seed; output is numbers only.

    python3.10 ml/realdocs/fetch.py --cache CACHE --only <pmc ids>
    python3.10 ml/eval/spelling_context_bench.py CACHE
"""

import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "ml" / "realdocs"))
SEED = 14
RATE = 0.02            # share of eligible words given a planted slip
MAX_CASES = 3000
VOWELS = "aeiou"


def plant(word: str, rng: random.Random) -> str | None:
    """One slip of the commonest kinds (Damerau 1964) inside the word."""
    i = rng.randrange(1, len(word) - 1)
    kind = rng.choice(["delete", "swap", "double", "vowel", "substitute"])
    if kind == "delete":
        return word[:i] + word[i + 1:]
    if kind == "swap":
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    if kind == "double":
        return word[:i] + word[i] + word[i:]
    if kind == "vowel":
        spots = [j for j, c in enumerate(word)
                 if c in VOWELS and 0 < j < len(word) - 1]
        if not spots:
            return None
        j = rng.choice(spots)
        return (word[:j] + rng.choice([v for v in VOWELS if v != word[j]])
                + word[j + 1:])
    return word[:i] + rng.choice("abcdefghijklmnopqrstuvwxyz") + word[i + 1:]


def cases(cache: Path, rng: random.Random) -> list[tuple[str, str, str, str]]:
    """(previous word, typo, next word, intended word)."""
    from convert import parse_jats, render_plain
    from researchly import spelling

    out = []
    for xml in sorted(cache.glob("*/article.xml")):
        text = render_plain(parse_jats(xml.read_bytes())).expect_text
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            toks = re.findall(r"[A-Za-z]+", sentence)
            if len(toks) < 6:
                continue
            for i in range(1, len(toks) - 1):
                word = toks[i]
                if not (word.islower() and len(word) >= 4
                        and spelling.is_known(word) and rng.random() < RATE):
                    continue
                typo = plant(word, rng)
                if typo and typo != word \
                        and not spelling.known_with_fallbacks(typo):
                    out.append((toks[i - 1].lower(), typo,
                                toks[i + 1].lower(), word))
    rng.shuffle(out)
    return out[:MAX_CASES]


def main(argv: list[str] | None = None) -> int:
    from researchly import spelling, spellrank

    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    rng = random.Random(SEED)
    planted = cases(Path(args[0]), rng)
    alone = with_context = 0
    for prev, typo, nxt, meant in planted:
        sym = [c for c, _ in spelling.suggest_with_distance(typo, 3)]
        ranked = [c for c, _ in spellrank.rank(typo, prev, nxt)]
        alone += bool(sym) and sym[0] == meant
        with_context += bool(ranked) and ranked[0] == meant
    n = len(planted) or 1
    print(f"planted slips: {len(planted)}; first suggestion right: "
          f"SymSpell alone {100 * alone / n:.1f}%, noisy channel with the "
          f"neighbouring words {100 * with_context / n:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())

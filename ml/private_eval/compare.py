"""PRIVATE: Researchly's spelling engine against the bundle, side by side.

    python3.10 ml/private_eval/compare.py --bundle-code DIR \
        --bundle-assets DIR [--blocklist FILE] --pmc-cache CACHE \
        [--lists-cache ~/.cache/researchly-spelling] [--theses]

Measures, for both engines, on the same inputs:

1. public misspelling lists, held-out 20% (ml/eval/spelling_bench.py):
   share detected, first suggestion right, right among the first three;
2. slips planted in CC BY sentences (ml/eval/spelling_context_bench.py):
   first suggestion right, with the neighbouring words;
3. false alarms on correct prose: lower-case words of 3+ letters that the
   engine would not accept, per 1,000 words, in the 115 PMC articles (and
   the eight theses with --theses: counts only, never words);
4. which PMC words each engine rejects most often (PMC text is CC BY, so
   the words may be printed; thesis words never are).

Output: Markdown on stdout. Nothing is written to the repository.
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "ml" / "eval"))
sys.path.insert(0, str(ROOT / "ml" / "realdocs"))
sys.path.insert(0, str(Path(__file__).parent))

WORD = re.compile(r"[A-Za-z]+")
SEED = 14
SAMPLE = 600        # pairs per public list (fixed random sample)
PLANTED = 1000      # planted slips


class Ours:
    """Researchly's S001 word check and ranker, without the document-level
    guards (names, 3+ uses), which the bundle has no counterpart for."""

    def __init__(self):
        from researchly import spelling, spellrank
        self.spelling, self.spellrank = spelling, spellrank
        self.domain = spelling.domain_terms()

    def known(self, word: str) -> bool:
        w = word.lower()
        return w in self.domain or self.spelling.known_with_fallbacks(w)

    def suggest(self, word, prev=None, nxt=None, top_n=3):
        return [c for c, _ in self.spellrank.rank(word.lower(), prev, nxt,
                                                  top_n=top_n)]


class OursLeftOnly(Ours):
    """Researchly's ranker given only the word before, as a keyboard is:
    separates the model from the document advantage of seeing both sides."""

    def suggest(self, word, prev=None, nxt=None, top_n=3):
        return super().suggest(word, prev, None, top_n)


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "n/a"


def public_lists(engines, cache: Path) -> list[str]:
    import spelling_bench as sb
    rows = ["| list | engine | detected | top-1 | top-3 |",
            "|---|---|---|---|---|"]
    for name in sb.LISTS:
        if name.startswith("norvig"):          # drawn from Birkbeck
            continue
        pairs = [p for p in sb.clean(sb.parse(sb.fetch(name, cache),
                                              sb.LISTS[name][1]))
                 if sb.split_of(p[0]) == "test"]
        if len(pairs) > SAMPLE:              # the bundle's Python search is slow
            pairs = random.Random(SEED).sample(pairs, SAMPLE)
        for label, eng in engines.items():
            if label.endswith("only)"):
                continue
            det = [(t, r) for t, r in pairs if not eng.known(t)]
            t1 = t3 = 0
            for typo, right in det:
                got = eng.suggest(typo)
                t1 += bool(got) and got[0].lower() == right
                t3 += right in [g.lower() for g in got]
            rows.append(f"| {name} ({len(pairs)}) | {label} | "
                        f"{pct(len(det), len(pairs))} | {pct(t1, len(det))} "
                        f"| {pct(t3, len(det))} |")
    return rows


def planted(engines, pmc: Path) -> list[str]:
    import spelling_context_bench as scb
    # fair to both: the intended word is known to both engines and the
    # typo is accepted by neither
    cases = [c for c in scb.cases(pmc, random.Random(scb.SEED))
             if all(e.known(c[3]) and not e.known(c[1])
                    for e in engines.values())][:PLANTED]
    rows = ["| engine | slips | first suggestion right |", "|---|---|---|"]
    for label, eng in engines.items():
        right = 0
        for prev, typo, nxt, meant in cases:
            got = eng.suggest(typo, prev, nxt)
            right += bool(got) and got[0].lower() == meant
        rows.append(f"| {label} | {len(cases)} | {pct(right, len(cases))} |")
    bundle = engines.get("bundle")
    if bundle is not None:
        fixed = wrong = 0
        for prev, typo, _nxt, meant in cases:
            got = bundle.autocorrect(typo, prev)
            if got is None:
                continue
            fixed += got.lower() == meant
            wrong += got.lower() != meant
        rows += ["", "Keyboard autocorrect (applied only at >= 0.95): "
                 f"right {pct(fixed, len(cases))}, wrong {pct(wrong, len(cases))}, "
                 f"left alone {pct(len(cases) - fixed - wrong, len(cases))}."]
    return rows


def false_alarms(engines, texts: list[str], show_words: bool):
    tokens = Counter()
    words = 0
    for text in texts:
        words += len(text.split())
        for w in WORD.findall(text):
            if w.islower() and len(w) >= 3:
                tokens[w] += 1
    rows = []
    tops = {}
    for label, eng in engines.items():
        if label.endswith("only)"):
            continue
        bad = Counter({w: n for w, n in tokens.items() if not eng.known(w)})
        rows.append((label, sum(bad.values()), words))
        tops[label] = bad.most_common(25) if show_words else []
    return rows, tops


def s001_rate(engine, texts: list[str]) -> tuple[int, int]:
    """S001 flags with this engine's word check inside the rule, so both
    engines get the same guards (URLs, names, hyphenated prefixes, words
    used 3+ times, acronyms)."""
    from researchly import rules_spelling, spelling
    from researchly.document import Document

    saved = (spelling.known_with_fallbacks, spelling.domain_terms)
    if not isinstance(engine, Ours):
        spelling.known_with_fallbacks = engine.known
        spelling.domain_terms = lambda: set()
    try:
        flags = words = 0
        for text in texts:
            words += len(text.split())
            doc = Document.from_text(text, "plain")
            flags += sum(1 for _ in rules_spelling.s001_spelling(None, doc))
    finally:
        spelling.known_with_fallbacks, spelling.domain_terms = saved
    return flags, words


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bundle-code", type=Path, required=True)
    ap.add_argument("--bundle-assets", type=Path, required=True)
    ap.add_argument("--blocklist", type=Path)
    ap.add_argument("--pmc-cache", type=Path, required=True)
    ap.add_argument("--lists-cache", type=Path,
                    default=Path.home() / ".cache" / "researchly-spelling")
    ap.add_argument("--theses", action="store_true")
    args = ap.parse_args(argv)

    from bundle_engine import BundleEngine
    from convert import parse_jats, render_plain

    engines = {"researchly": Ours(),
               "researchly (left word only)": OursLeftOnly(),
               "bundle": BundleEngine(args.bundle_code, args.bundle_assets,
                                      args.blocklist)}
    print("## 1. Public misspelling lists (held-out 20%, no context)\n")
    print("\n".join(public_lists(engines, args.lists_cache)))
    print("\n## 2. Slips planted in CC BY sentences (with context)\n")
    print("\n".join(planted(engines, args.pmc_cache)))

    pmc_texts = [render_plain(parse_jats(x.read_bytes())).expect_text
                 for x in sorted(args.pmc_cache.glob("*/article.xml"))]
    sets = [("PMC articles (115)", pmc_texts, True)]
    if args.theses:
        sets.append(("accepted theses (8)",
                     [p.read_text(encoding="utf-8", errors="ignore")
                      for p in sorted((ROOT / "ml" / "dogfood" / "text")
                                      .glob("*.txt"))], False))
    print("\n## 3. S001 flags on correct prose, each engine's words inside "
          "the same rule\n")
    print("| corpus | engine | flags | per 1,000 words |")
    print("|---|---|---|---|")
    for title, texts, _show in sets:
        for label, eng in engines.items():
            if label.endswith("only)"):
                continue
            flags, words = s001_rate(eng, texts)
            print(f"| {title} | {label} | {flags} | "
                  f"{1000 * flags / words:.2f} |")
    print("\n## 4. False alarms on correct prose (word check only)\n")
    print("| corpus | engine | words rejected | per 1,000 words |")
    print("|---|---|---|---|")
    for title, texts, show in sets:
        rows, tops = false_alarms(engines, texts, show)
        for label, bad, words in rows:
            print(f"| {title} | {label} | {bad} | {1000 * bad / words:.2f} |")
        if show:
            for label, top in tops.items():
                print(f"\n{label}, most rejected PMC words: "
                      + ", ".join(f"{w} ({n})" for w, n in top))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Build ``researchly/data/variants.tsv`` from VarCon.

VarCon (Kevin Atkinson; part of SCOWL, now the English Speller Database)
lists English words spelt differently in American (A), British -ise (B),
British -ize/Oxford (Z), Canadian (C) and Australian (D) usage, one line per
sense: ``A Z: organize / B: organise``. A code followed by ``v`` or ``V``
marks an accepted but less common variant, ``.`` an equal alternative, and
``x`` a misspelling.

Researchly uses it twice:

* S001 accepts a word VarCon lists as a spelling of some dialect ("feces",
  "modeling", "colour"), replacing the old letter-swapping fallback that
  also accepted "rigourous" (our → or) and "controled" (lled → led);
* W210 flags a document that mixes two spellings of one word. A pair is
  kept only when neither spelling is valid in the other's dialect in any
  sense: British English writes "programme" for a plan and "program" for
  software, so program/programme is never a W210 pair.

Licence: VarCon's notices (Atkinson; Titze for Australian data; Kuenning's
BSD-style Ispell notice) are copied into the output's header, as they
require. Registry: ``ml/datasets.yaml`` id ``varcon``. Only entries of size
level 80 or below are used, which keeps the UKACD notice out of scope.

    python3.10 ml/tools/build_variants.py VARCON_TXT VARCON_README [--out PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = (ROOT / "packages" / "core" / "researchly" / "data"
               / "variants.tsv")
MAX_LEVEL = 80
DIALECTS = "ABZCD"
HEADER_LEVEL = re.compile(r"^# .*\(level (\d+)\)")


def parse(text: str):
    """Yield lists of (word, primary dialects, variant dialects) per line,
    one list per sense line."""
    level = 100
    for line in text.splitlines():
        m = HEADER_LEVEL.match(line)
        if m:
            level = int(m.group(1))
            continue
        if not line.strip() or line.startswith("#") or level > MAX_LEVEL:
            continue
        line = line.split("|")[0].strip()
        group = []
        for part in line.split(" / "):
            if ":" not in part:
                continue
            codes, word = part.split(":", 1)
            word = word.strip()
            if not word or "'" in word or " " in word:
                continue
            primary, variant = set(), set()
            for code in codes.split():
                dialect, mark = code[0], code[1:]
                if dialect not in DIALECTS or "x" in mark or "-" in mark:
                    continue
                # "." marks an equal alternative ("A B. Z: among / AV B Zv:
                # amongst"): as standard as the main form, so main here
                (variant if mark and mark != "." else primary).add(dialect)
            if primary or variant:
                group.append((word.lower(), primary, variant))
        if group and not any("Z" in p | v for _w, p, v in group):
            # Oxford (Z) differs from British (B) only on -ize/-ise lines;
            # elsewhere ("colour") it spells as British does.
            group = [(w, p | ({"Z"} if "B" in p else set()),
                      v | ({"Z"} if "B" in v else set())) for w, p, v in group]
        if group:
            # single-spelling lines matter too: "A B: meter | measuring
            # device" is what keeps meter/metre from being a pair
            yield group


def notices(readme: str) -> list[str]:
    """The copyright and permission notices of VarCon's README."""
    start = readme.find("Copyright\n=========")
    if start < 0:
        raise SystemExit("VarCon README: no 'Copyright' section found")
    tail = readme[start:].split("\n", 2)[2].strip("\n")
    return ["# " + line if line else "#" for line in tail.splitlines()]


def build(text: str) -> tuple[dict, list[tuple[str, str]]]:
    valid_in: dict[str, set[str]] = {}
    primary_in: dict[str, set[str]] = {}
    groups = list(parse(text))
    for group in groups:
        for word, primary, variant in group:
            valid_in.setdefault(word, set()).update(primary | variant)
            primary_in.setdefault(word, set()).update(primary)
    words = {w: ("".join(sorted(primary_in[w])),
                 "".join(sorted(valid_in[w] - primary_in[w])))
             for w in sorted(valid_in)}
    pairs = set()
    for group in groups:
        primaries = [(w, p) for w, p, _v in group if p]
        for i, (w1, p1) in enumerate(primaries):
            for w2, p2 in primaries[i + 1:]:
                if w1 == w2 or not (p1 - p2) or not (p2 - p1):
                    continue
                # never a pair if either spelling is the main spelling of
                # the other's dialects in some sense (British "program" for
                # software beside "programme"; "meter" the device beside
                # "metre"). Being an accepted variant there does not count:
                # "color" is a Canadian variant, yet color/colour is a pair.
                if primary_in[w1] & p2 or primary_in[w2] & p1:
                    continue
                pairs.add(tuple(sorted((w1, w2))))
    return words, sorted(pairs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("varcon", type=Path)
    ap.add_argument("readme", type=Path)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    # VarCon is Latin-1 ("naïve" et al.)
    words, pairs = build(args.varcon.read_text(encoding="latin-1"))
    lines = [
        "# Derived from VarCon (Kevin Atkinson, wordlist.aspell.net; now part "
        "of the English Speller",
        "# Database, github.com/en-wl/wordlist) by ml/tools/build_variants.py. "
        "Entries of size level <= 80.",
        "# Rows: '=<TAB>word<TAB>word' = a W210/W213 pair; otherwise "
        "'word<TAB>main dialects<TAB>variant dialects',",
        "# dialects as VarCon codes: A American, B British (-ise), Z British "
        "(-ize, Oxford), C Canadian, D Australian.",
        "# VarCon's notices, reproduced as its licence requires:",
        "#",
        *notices(args.readme.read_text(encoding="latin-1")),
    ]
    lines += [f"=\t{a}\t{b}" for a, b in pairs]
    lines += [f"{w}\t{p}\t{v}" for w, (p, v) in words.items()]
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(words)} spellings, {len(pairs)} consistency pairs → "
          f"{args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

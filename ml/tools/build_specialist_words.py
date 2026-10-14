"""Build ``researchly/data/specialist_words.txt`` from the SPECIALIST Lexicon.

S001 rejected about 1 in 100 lower-case words of published biomedical
prose (spectrin, biofilm, nanoparticles, rifampin, epitopes, norovirus) for
want of a biomedical vocabulary. The NLM's SPECIALIST Lexicon lists the
inflected forms of general and biomedical English (LRAGR) and the spelling
variants of each entry (LRSPL). It may be redistributed with its conditions,
an attribution with release number and date, and a description of any
modification; all three go into the output's header.

Modifications made here (stated as the terms require):
* only single, lower-case, alphabetic word forms are kept (LRAGR's
  inflected-form column), of 5 letters or more: short forms collide with
  common slips ("ad", "ack", "bing"); none with a tripled letter;
* a spelling variant is dropped when it is one or two edits from another
  spelling of the same entry that a general dictionary knows and VarCon
  does not list as a dialect variant: SPECIALIST records the misspellings
  found in the literature ("accessable", "millenium", "amoungst");
* a form Researchly's inflection rules reject is dropped ("controled",
  "controling"): spelling.reinflect finds a correctly inflected form.

Registry: ``specialist-lexicon`` (ml/datasets.yaml).

    python3.10 ml/tools/build_specialist_words.py LRAGR LRSPL \
        --release 2026 --date 2026 [--out PATH]
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "core"))

DEFAULT_OUT = (ROOT / "packages" / "core" / "researchly" / "data"
               / "specialist_words.txt")
MIN_LEN = 5

# Section 4 of the Terms and Conditions for Use of the SPECIALIST NLP Tools
# (https://lhncbc.nlm.nih.gov/LSG/Projects/lexicon/current/web/
# termsAndConditions.html), which 4a requires to accompany a redistribution.
CONDITIONS = """\
4. Use of the SPECIALIST NLP Tools
a. Redistributions of the SPECIALIST NLP Tools in source or binary form must
include this list of conditions in the documentation and/or other materials
provided with the distribution.
b. In any publication or distribution of all or any portion of the SPECIALIST
NLP Tools (1) you must attribute the source of the tools as the SPECIALIST NLP
Tools with the release number and date; (2) you must state any modifications
made to the SPECIALIST NLP Tools along with a complete description of the
modifications, which may be in the form of patch files.
c. You shall not assert any proprietary rights to any portion of the SPECIALIST
NLP Tools, nor represent the SPECIALIST NLP Tools or any part thereof to anyone
as other than a United States Government product.
d. The name of the U.S. Department of Health and Human Services, National
Institutes of Health, National Library of Medicine, Lister Hill National Center
for Biomedical Communications may not be used to endorse or promote products
derived from the SPECIALIST NLP Tools without specific prior written
permission.
e. Neither the United States Government, U.S. Department of Health and Human
Services, National Institutes of Health, National Library of Medicine, Lister
Hill National Center for Biomedical Communications, nor any of its agencies,
contractors, subcontractors or employees of the United States Government make
any warranties, expressed or implied, with respect to the SPECIALIST NLP Tools,
and, furthermore, assume no liability for any party's use, or the results of
such use, of any part of these tools.
These terms and conditions are in effect as long as the user retains any part
of the SPECIALIST NLP Tools."""


TRIPLED = __import__("re").compile(r"(.)\1\1")


def forms(lragr: Path) -> set[str]:
    """Single lower-case alphabetic forms; none with a tripled letter, which
    is a lost hyphen or a slip ("crosssectional"), never a word."""
    out = set()
    with open(lragr, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split("|")
            if len(parts) > 1:
                s = parts[1]
                if len(s) >= MIN_LEN and s.isalpha() and s.islower() \
                        and not TRIPLED.search(s):
                    out.add(s)
    return out


def variant_groups(lrspl: Path) -> list[set[str]]:
    groups: dict[str, set[str]] = collections.defaultdict(set)
    with open(lrspl, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split("|")
            if len(parts) >= 3:
                for s in parts[1:3]:
                    if s.isalpha():
                        groups[parts[0]].add(s.lower())
    return list(groups.values())


def build(words: set[str], groups: list[set[str]]) -> tuple[list[str], dict]:
    from symspellpy.editdistance import DistanceAlgorithm, EditDistance

    from researchly import spelling

    ed = EditDistance(DistanceAlgorithm.DAMERAU_OSA)
    varcon = spelling.variant_words()

    def general(w):
        return spelling.is_known(w) or w in varcon

    misspelt = set()
    for group in groups:
        known = [w for w in group if general(w)]
        for w in group - set(known):
            if w in varcon:
                continue
            if any(0 < ed.compare(w, k, 2) <= 2 for k in known):
                misspelt.add(w)
    misinflected = {w for w in words if spelling.reinflect(w) is not None}
    keep = sorted(words - misspelt - misinflected)
    stats = {"forms": len(words), "dropped_variants": len(words & misspelt),
             "dropped_misinflected": len(misinflected), "kept": len(keep)}
    return keep, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("lragr", type=Path)
    ap.add_argument("lrspl", type=Path)
    ap.add_argument("--release", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    keep, stats = build(forms(args.lragr), variant_groups(args.lrspl))
    header = [
        f"Source: the SPECIALIST NLP Tools, SPECIALIST Lexicon release "
        f"{args.release} ({args.date}), U.S. National Library of Medicine, "
        f"Lister Hill National Center for Biomedical Communications "
        f"(https://lhncbc.nlm.nih.gov/LSG/Projects/lexicon/). A United "
        f"States Government product; no endorsement of Researchly by NLM is "
        f"implied.",
        "",
        "Modifications (a complete description, as condition 4b(2) "
        "requires): built by ml/tools/build_specialist_words.py from LRAGR "
        "and LRSPL. Kept: single, lower-case, alphabetic inflected forms of "
        f"{MIN_LEN} letters or more, none with a tripled letter. Dropped: a spelling variant one or two "
        "edits from another spelling of the same entry that a general "
        "dictionary knows and VarCon does not list as a dialect variant; a "
        "form whose ending Researchly's inflection rules reject.",
        f"Counts: {stats}",
        "",
        "Terms and Conditions for Use of the SPECIALIST NLP Tools, section 4:",
        "",
        *CONDITIONS.splitlines(),
    ]
    lines = ["# " + h if h else "#" for h in header] + keep
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{stats} → {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Repeated unknown words: do repeated typos stay visible and repeated
domain terms stay quiet? (PLAN, Codex review #10.)

Until 2026-10-15 S001 skipped any word used three or more times, taking it
for the author's vocabulary: a typo made three times was never flagged.
Now a repeated unknown word is judged (rules_spelling.repeated_kind): a
known kind of slip next to a common word is flagged at every use (S001); any
other is asked about once, in one grouped card (S003).

Each labelled word is written into the same three invented sentences, so it
appears three times, and the spelling rules are run on that text:

* **typo recall**: the share of a repeated typo's uses that S001 flags
  (higher is better; the old exemption gave 0);
* **typos asked about**: repeated typos that got the grouped question
  instead (still visible, but not marked as errors);
* **term false flags**: the share of a repeated term's uses that S001
  flags (lower is better; the old exemption gave 0);
* **term questions**: repeated terms that got exactly one grouped card
  (allowed: one question per word, never one per use).

Labelled sets:

* the built-in set below: common misspellings and field terms (software,
  coined names) that no shipped dictionary knows, written for this harness;
  the committed test runs on it;
* ``--typos wikipedia``: the held-out 20% of Wikipedia's list of common
  misspellings (fetched by spelling_bench.py into its cache; evaluation
  only, ml/datasets.yaml), keeping those S001 does not accept as words;
* ``--terms specialist``: real biomedical words from the SPECIALIST
  Lexicon that SymSpell's dictionary lacks, hidden from the lexicon for the
  run, so each stands for a field term no dictionary knows.

    python3.10 ml/eval/spelling_repetition.py [--typos wikipedia]
        [--terms specialist] [--sample N] [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "packages" / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "core"))

# Three invented sentences; the word sits mid-sentence in lower case, where
# neither the proper-noun guard nor the sentence-start guard applies.
TEMPLATES = (
    "We measured {w} in every district during the first year.",
    "The {w} changed little after adjustment for age.",
    "Estimates of {w} were stable across the sensitivity analyses.",
)

# Common misspellings, typed three times: each should be flagged each time.
TYPOS = (
    "recieve", "seperate", "occured", "definately", "enviroment",
    "goverment", "accomodate", "untill", "wich", "becuase", "beleive",
    "acheive", "aquire", "arguement", "commited", "concious", "existance",
    "independant", "liason", "neccessary", "noticable", "occurence",
    "persistant", "posession", "prefered", "recomend", "refered",
    "relevent", "succesful", "tommorow", "signficant", "statisical",
    "paramter", "transmision", "regresion", "anaylsis", "resuts",
    "particpants", "hypotheis", "experiement", "infomation", "mesured",
    "analsis", "enrolement", "seasonaility", "vaccinaton", "estimatation",
    "demonstarted", "diffrence", "intervension", "recieved", "begining",
    "similiar", "priviledge", "reponse",
)

# Field terms no shipped dictionary knows (software, coined and drug-like
# names), used three times: each should get one question and no flags.
TERMS = (
    "brms", "pymc", "numpyro", "tidybayes", "snakemake", "fastq",
    "bedtools", "samtools", "kallisto", "deseq", "limma", "scanpy",
    "epinow", "nowcastr", "frobulation", "zanuvimab", "dorlavir",
    "fexamycin", "phylodynamic", "superspreaders", "seroreverters",
    "pangolineage", "nextstrain", "treetime", "iqtree", "mafft",
    "covidestim", "epiestim", "socialmixr", "contactdata", "finalsize",
    "mcstate", "eventdate", "rtestim",
)


def text_for(word: str) -> str:
    return " ".join(t.format(w=word) for t in TEMPLATES)


def _engine():
    """S001 and S003 alone, on a blank tokenizer: neither reads the parse,
    and the full pipeline would only make the run slower."""
    import spacy
    from researchly.engine import REGISTRY, load_rules
    load_rules()
    keep = {"S001", "S003"} & set(REGISTRY)
    disabled = set(REGISTRY) - keep
    return spacy.blank("en"), disabled


def judge(word: str, nlp=None, disabled=None) -> dict:
    """What the spelling rules say about one word used three times."""
    from researchly.document import Document
    from researchly.engine import check
    if nlp is None:
        nlp, disabled = _engine()
    text = text_for(word)
    doc = Document.from_text(text, "plain")
    found = check(doc, nlp, disabled=disabled, show_preferences=True)
    on_word = [s for s in found if s.text.lower() == word]
    grouped = [s for s in on_word if s.rule_id == "S003"]
    return {"word": word,
            "uses": len(TEMPLATES),
            "flags": sum(s.rule_id == "S001" for s in on_word),
            "questions": len(grouped),
            "question_places": (len(grouped[0].occurrences or [])
                                if grouped else 0)}


def evaluate(typos, terms) -> dict:
    nlp, disabled = _engine()
    ty = [judge(w, nlp, disabled) for w in typos]
    te = [judge(w, nlp, disabled) for w in terms]
    uses_ty = sum(r["uses"] for r in ty) or 1
    uses_te = sum(r["uses"] for r in te) or 1
    return {
        "typos": len(ty),
        "typo_uses": uses_ty,
        "typo_recall": round(sum(r["flags"] for r in ty) / uses_ty, 3),
        "typos_fully_flagged": sum(r["flags"] == r["uses"] for r in ty),
        "typos_asked_about": sum(r["questions"] > 0 for r in ty),
        "typos_silent": sum(r["flags"] == 0 and r["questions"] == 0
                            for r in ty),
        "terms": len(te),
        "term_uses": uses_te,
        "term_false_flag_rate": round(sum(r["flags"] for r in te) / uses_te,
                                      3),
        "terms_flagged": sum(r["flags"] > 0 for r in te),
        "terms_one_question": sum(r["questions"] == 1 for r in te),
        "missed_typos": [r["word"] for r in ty if r["flags"] < r["uses"]],
        "flagged_terms": [r["word"] for r in te if r["flags"] > 0],
    }


def unknown(word: str) -> bool:
    """Would S001 consider this word at all (not known to any list)?"""
    from researchly import spelling
    return not (spelling.known_with_fallbacks(word)
                or word in spelling.domain_terms())


def wikipedia_typos(cache: Path, split: str) -> list[str]:
    import spelling_bench as sb
    pairs = sb.clean(sb.parse(sb.fetch("wikipedia", cache), "arrow"))
    seen, out = set(), []
    for typo, _right in pairs:
        if sb.split_of(typo) == split and typo not in seen \
                and len(typo) >= 3 and unknown(typo):
            seen.add(typo)
            out.append(typo)
    return out


def specialist_terms(sample: int, seed: int) -> list[str]:
    """SPECIALIST words SymSpell lacks, then hidden from the lexicon so
    S001 meets them as it would meet any field term it does not know."""
    from researchly import spelling
    rng = random.Random(seed)
    pool = sorted(w for w in spelling.specialist_words()
                  if w.isalpha() and w.islower()
                  and not spelling.is_known(w)
                  and w not in spelling.variant_words()
                  and w not in spelling.domain_terms())
    picked = rng.sample(pool, min(sample, len(pool)))
    spelling._SPECIALIST = frozenset(spelling.specialist_words()
                                     - set(picked))
    return [w for w in picked if unknown(w)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--typos", choices=("builtin", "wikipedia"),
                    default="builtin")
    ap.add_argument("--terms", choices=("builtin", "specialist"),
                    default="builtin")
    ap.add_argument("--split", choices=("train", "test"), default="test")
    ap.add_argument("--sample", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20261015)
    ap.add_argument("--cache", type=Path,
                    default=Path.home() / ".cache" / "researchly-spelling")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    typos = [w for w in TYPOS if unknown(w)]
    if args.typos == "wikipedia":
        typos = wikipedia_typos(args.cache, args.split)
        if args.sample and len(typos) > args.sample:
            typos = random.Random(args.seed).sample(typos, args.sample)
    terms = [w for w in TERMS if unknown(w)]
    if args.terms == "specialist":
        terms = specialist_terms(args.sample, args.seed)
    res = evaluate(typos, terms)
    res["sets"] = {"typos": args.typos, "terms": args.terms,
                   "split": args.split}
    shown = {k: v for k, v in res.items()
             if k not in ("missed_typos", "flagged_terms")}
    print(json.dumps(shown, indent=2))
    if args.json:
        args.json.write_text(json.dumps(res, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

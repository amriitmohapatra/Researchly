"""PRIVATE: spelling-tier flags of one engine on the owner's own documents.

    python3.10 ml/private_eval/docs_compare.py --core PATH --engine researchly \
        --out FLAGS.json DOC [DOC ...]
    python3.10 ml/private_eval/docs_compare.py --core PATH --engine bundle \
        --bundle-code DIR --bundle-assets DIR [--blocklist FILE] \
        --out FLAGS.json DOC [DOC ...]

The owner's drafts are confidential (CLAUDE.md #2): this reads them in
memory and writes the flags to --out, which must be OUTSIDE the
repository. Run once per engine (the --core path picks which Researchly
code is imported, so the version on main and the version on a branch never
share a process).

``researchly``: the spelling-tier rules as that version ships them (S001,
S002, W208, W210, W212, W213; grammar off, so only spelling is compared).
``bundle``: S001 with the bundle's vocabulary as the word check and the
bundle's ranked candidates as the suggestions (Researchly's guards for
names, URLs, acronyms and masked LaTeX still apply), plus, for each flag,
what the keyboard would have replaced the word with on its own (its
autocorrect, applied only at >= 0.95 confidence).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = ("S001", "S002", "W208", "W210", "W212", "W213")


def run_researchly(paths):
    from researchly import api
    out = {}
    for p in paths:
        a = api.analyze(Path(p), disabled={"LT001"})
        out[Path(p).name] = [[s.rule_id, s.text, s.replacement]
                             for s in a.suggestions if s.rule_id in RULES]
    return out


def run_bundle(paths, args):
    sys.path.insert(0, str(Path(__file__).parent))
    from bundle_engine import BundleEngine
    from researchly import rules_spelling, spellrank, spelling
    from researchly.document import Document

    eng = BundleEngine(args.bundle_code, args.bundle_assets, args.blocklist)
    spelling.known_with_fallbacks = eng.known
    spelling.domain_terms = lambda: set()
    spellrank.rank = lambda w, prev=None, nxt=None, top_n=3: [
        (c, 0.0) for c in eng.suggest(w, prev, nxt, top_n)]
    out = {}
    for p in paths:
        doc = Document.from_path(Path(p))
        rows = []
        for s in rules_spelling.s001_spelling(None, doc):
            text = doc.masked[s.start:s.end]
            prev, _nxt = rules_spelling._neighbours(doc.masked, s.start,
                                                    s.end)
            rows.append(["S001", text, s.replacement,
                         eng.autocorrect(text, prev)])
        out[Path(p).name] = rows
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--core", type=Path, required=True)
    ap.add_argument("--engine", choices=("researchly", "bundle"),
                    required=True)
    ap.add_argument("--bundle-code", type=Path)
    ap.add_argument("--bundle-assets", type=Path)
    ap.add_argument("--blocklist", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("docs", nargs="+")
    args = ap.parse_args(argv)
    if ROOT in args.out.resolve().parents:
        print("refused: write the flags outside the repository",
              file=sys.stderr)
        return 2
    sys.path.insert(0, str(args.core))
    out = (run_researchly(args.docs) if args.engine == "researchly"
           else run_bundle(args.docs, args))
    args.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for name, rows in out.items():
        print(f"{name}: {len(rows)} flags")
    return 0


if __name__ == "__main__":
    sys.exit(main())

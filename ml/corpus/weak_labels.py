"""Weak labels from the S5a corpus, written into the cache (never the repo).

    python3.10 ml/corpus/weak_labels.py [--cache DIR]

Reads ml/corpus/manifest.jsonl and the cached JATS files and writes:

- ``<cache>/labels/sentences.jsonl`` — every sentence of a STRUCTURED
  abstract, labelled with the role its heading names: background,
  objective, methods, results or conclusions (the five PubMed-RCT labels,
  so Task B stays comparable with the TF-IDF baseline's 82.6%). Headings
  that mix roles ("Methods and findings") or carry none ("Funding") are
  skipped. One row: pmcid, discipline, split, use, role, position (0-based
  index in the abstract), n (sentences in the abstract), text.
- ``<cache>/labels/paragraphs.jsonl`` — every body paragraph under an IMRaD
  heading, labelled with the section role (introduction, methods, results,
  results-discussion, discussion, conclusion, limitations).

Rows keep the article's ``use``: "train" rows may train a shipped model;
"eval" rows (CC BY-NC/ND/SA) may only evaluate one. Each row also keeps the
article's ``split`` (test/dev/train, per article), so no article contributes
to both sides of an evaluation.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import harvest  # noqa: E402


def labels_for(row: dict, xml: bytes) -> tuple:
    """(sentence rows, paragraph rows) for one manifest row."""
    root = common.parse_xml(xml)
    base = {"pmcid": row["pmcid"], "discipline": row["discipline"],
            "split": row["split"], "use": row["use"]}
    sents = []
    labelled = []
    for heading, paras in common.abstract_sections(root):
        role = common.abstract_role(heading)
        for p in paras:
            for s in common.sentences(p):
                labelled.append((role, s))
    n = len(labelled)
    for i, (role, s) in enumerate(labelled):
        if role is not None:
            sents.append(dict(base, role=role, position=i, n=n, text=s))
    paras_out = []
    for heading, paras in common.body_sections(root):
        role = common.section_role(heading)
        if role is None:
            continue
        for i, p in enumerate(paras):
            if len(p.split()) >= 20:
                paras_out.append(dict(base, section=role, position=i, text=p))
    return sents, paras_out


def build(cache: Path, manifest: Path = common.MANIFEST) -> dict:
    rows = harvest.read_manifest(manifest)
    out_dir = cache / "labels"
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {"sentences": Counter(), "paragraphs": Counter(),
             "articles_with_roles": 0}
    with (out_dir / "sentences.jsonl").open("w", encoding="utf-8") as fs, \
            (out_dir / "paragraphs.jsonl").open("w", encoding="utf-8") as fp:
        for row in rows:
            path = cache / "xml" / f"{row['pmcid']}.xml"
            if not path.exists():
                continue
            xml = path.read_bytes()
            if common.sha256(xml) != row["xml_sha256"]:
                print(f"  {row['pmcid']}: cached XML changed since the "
                      "manifest was built; skipped", file=sys.stderr)
                continue
            sents, paras = labels_for(row, xml)
            stats["articles_with_roles"] += bool(sents)
            for s in sents:
                fs.write(json.dumps(s, ensure_ascii=False) + "\n")
                stats["sentences"][f"{s['use']}:{s['split']}:{s['role']}"] += 1
            for p in paras:
                fp.write(json.dumps(p, ensure_ascii=False) + "\n")
                stats["paragraphs"][f"{p['use']}:{p['split']}:{p['section']}"] += 1
    out = {"sentences": dict(sorted(stats["sentences"].items())),
           "paragraphs": dict(sorted(stats["paragraphs"].items())),
           "articles_with_roles": stats["articles_with_roles"],
           "out": str(out_dir)}
    print(json.dumps(out, indent=1), file=sys.stderr)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--manifest", type=Path, default=common.MANIFEST)
    a = ap.parse_args(argv)
    cache = common.outside_repo(a.cache or common.default_cache())
    build(cache, a.manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Rebuild the paragraphs behind the corpus flag labels (PLAN S5b, Task A).

The labels in this folder (``train-labels.json``, ``test-labels.json``) were
made on body paragraphs of CC BY / CC0 open-access articles from the S5a
corpus. The repository holds no article text, only pointers
(``paragraph-index.json``): each paragraph's PMCID, its index in the list
``ml/corpus/weak_labels.labels_for`` returns for that article, its section
and a SHA-256 of its text. This script fetches the articles' JATS XML into
the corpus cache (outside the repository) if they are not there yet,
re-extracts the paragraphs with the same splitter, checks every hash, and
writes the harness's paragraphs files **outside the repository**:

    python3.10 ml/critics/data/corpus/rebuild.py --out ~/laya-corpus
    # -> ~/laya-corpus/train-paragraphs.json, ~/laya-corpus/test-paragraphs.json

Then, e.g. (README.md in this folder has the full sequence):

    python ml/critics/laya/finetune.py data flags \\
        --labels ml/critics/data/corpus/train-labels.json \\
        --paragraphs ~/laya-corpus/train-paragraphs.json --out ~/laya-data

The cache is ``--cache``, else ``$RESEARCHLY_CORPUS_CACHE``, else
``~/.researchly/corpus`` (the harvester's default, so an existing corpus is
reused). ``--no-fetch`` never touches the network. A paragraph whose hash
differs (Europe PMC re-issued the article's XML) is reported and left out;
the exit code is 1 if any paragraph could not be rebuilt, unless
``--allow-missing``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "ml" / "corpus"))
import common  # noqa: E402
import weak_labels  # noqa: E402

INDEX = HERE / "paragraph-index.json"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_index(path: Path = INDEX) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("paragraphs"), list):
        raise ValueError(f"{path}: not a version-1 paragraph index")
    for p in data["paragraphs"]:
        if "text" in p:
            raise ValueError(f"{path}: the index must not carry text")
    return data


def read_manifest(path: Path) -> dict:
    rows = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["pmcid"]] = r
    return rows


def fetch_missing(cache: Path, pmcids: list) -> Counter:
    """Fetch the JATS XML of articles not yet in the cache (Europe PMC)."""
    import harvest
    xml_dir = cache / "xml"
    xml_dir.mkdir(parents=True, exist_ok=True)
    limiter = harvest.Limiter(harvest.INTERVAL)
    done: Counter = Counter()
    for pmcid in pmcids:
        path = xml_dir / f"{pmcid}.xml"
        if path.exists():
            continue
        try:
            path.write_bytes(harvest.http_get(harvest.FULLTEXT.format(pmcid),
                                              limiter))
            done["fetched"] += 1
        except Exception as err:          # reported per paragraph below
            done["failed"] += 1
            print(f"  {pmcid}: fetch failed ({type(err).__name__})",
                  file=sys.stderr)
    return done


def rebuild(index: dict, manifest: dict, cache: Path) -> tuple:
    """({split: [paragraph rows]}, problems). A row is what
    ``harness.label_paragraphs`` reads: paragraph, section, text."""
    out: dict = {}
    problems: list = []
    extracted: dict = {}
    for p in index["paragraphs"]:
        pmcid = p["pmcid"]
        row = manifest.get(pmcid)
        if row is None:
            problems.append((p["paragraph"], pmcid, "not in the manifest"))
            continue
        if row.get("use") != "train":
            problems.append((p["paragraph"], pmcid,
                             f"manifest use is {row.get('use')!r}, not train"))
            continue
        if pmcid not in extracted:
            path = cache / "xml" / f"{pmcid}.xml"
            if not path.exists():
                extracted[pmcid] = None
            else:
                xml = path.read_bytes()
                if common.sha256(xml) != row.get("xml_sha256"):
                    print(f"  {pmcid}: cached XML differs from the manifest; "
                          "checking paragraph hashes anyway", file=sys.stderr)
                extracted[pmcid] = weak_labels.labels_for(row, xml)[1]
        paras = extracted[pmcid]
        if paras is None:
            problems.append((p["paragraph"], pmcid, "XML not in the cache"))
            continue
        i = p["body_index"]
        if i >= len(paras):
            problems.append((p["paragraph"], pmcid, "paragraph index past "
                             "the article's paragraphs"))
            continue
        got = paras[i]
        if got["section"] != p["section"] or got["position"] != p["position"] \
                or sha256_text(got["text"]) != p["sha256"]:
            problems.append((p["paragraph"], pmcid, "text differs (hash)"))
            continue
        out.setdefault(p["split"], []).append(
            {"paragraph": p["paragraph"], "section": p["section"],
             "text": got["text"]})
    return out, problems


def write(out_dir: Path, rows: dict) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for split, paras in sorted(rows.items()):
        path = out_dir / f"{split}-paragraphs.json"
        path.write_text(json.dumps(
            {"version": 1, "note": "CC BY / CC0 open-access article "
             "paragraphs rebuilt by ml/critics/data/corpus/rebuild.py; "
             "attribution: PMCIDs in paragraph-index.json, DOIs and "
             "licences in ml/corpus/manifest.jsonl. Keep outside the "
             "repository.",
             "paragraphs": sorted(paras, key=lambda r: r["paragraph"])},
            ensure_ascii=False, indent=1), encoding="utf-8")
        written.append(path)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True,
                    help="folder for {train,test}-paragraphs.json "
                         "(outside the repository)")
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--index", type=Path, default=INDEX)
    ap.add_argument("--manifest", type=Path, default=common.MANIFEST)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--allow-missing", action="store_true")
    a = ap.parse_args(argv)
    out_dir = common.outside_repo(a.out)
    cache = common.outside_repo(a.cache or common.default_cache())
    index = read_index(a.index)
    manifest = read_manifest(a.manifest)
    if not a.no_fetch:
        pmcids = sorted({p["pmcid"] for p in index["paragraphs"]})
        got = fetch_missing(cache, pmcids)
        if got:
            print(f"fetch: {dict(got)}", file=sys.stderr)
    rows, problems = rebuild(index, manifest, cache)
    for n, pmcid, why in problems:
        print(f"  paragraph {n} ({pmcid}): {why}", file=sys.stderr)
    paths = write(out_dir, rows)
    print(json.dumps({"rebuilt": {k: len(v) for k, v in sorted(rows.items())},
                      "problems": len(problems),
                      "written": [str(p) for p in paths]}, indent=1))
    return 1 if problems and not a.allow_missing else 0


if __name__ == "__main__":
    sys.exit(main())

"""The corpus flag labels: rebuild.py on a tiny synthetic fake corpus, and
the committed files' shape (labels readable by the harness, pointers only,
no article text).

The XML below is written for these tests; it is not any article's text.
"""

import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "ml" / "corpus"))
sys.path.insert(0, str(REPO / "ml" / "eval"))
import common  # noqa: E402
import rebuild  # noqa: E402
import weak_labels  # noqa: E402

SENT = ("This invented sentence about imaginary river gauges only fills "
        "space so the fake article counts as a full body of text. ")


def fake_xml(pmcid: str, words: str) -> bytes:
    def paras(tag):
        return "".join(f"<p>{tag} paragraph {k} on {words}. {SENT * 4}</p>"
                       for k in range(3))
    return (f"""<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>
<article-id pub-id-type="pmcid">{pmcid}</article-id>
<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/">x</license></permissions>
</article-meta></front><body>
<sec><title>Introduction</title>{paras("Intro")}</sec>
<sec><title>Methods</title><sec><title>Gauges</title>{paras("Methods")}</sec></sec>
<sec><title>Results</title>{paras("Results")}</sec>
<sec><title>Discussion</title>{paras("Discussion")}</sec>
</body></article>""").encode()


@pytest.fixture
def fake(tmp_path):
    cache = tmp_path / "cache"
    (cache / "xml").mkdir(parents=True)
    manifest, index = [], []
    n = 0
    for pmcid, split, words in (("PMC9100001", "train", "rain"),
                                ("PMC9100002", "test", "snow")):
        xml = fake_xml(pmcid, words)
        (cache / "xml" / f"{pmcid}.xml").write_bytes(xml)
        row = {"pmcid": pmcid, "discipline": "engineering", "split": split,
               "use": "train", "licence": "CC-BY-4.0",
               "xml_sha256": common.sha256(xml)}
        manifest.append(row)
        paras = weak_labels.labels_for(row, xml)[1]
        for i in (1, 4, 10):
            n += 1
            p = paras[i]
            index.append({"paragraph": n, "split": split, "pmcid": pmcid,
                          "discipline": "engineering", "licence": "CC-BY-4.0",
                          "body_index": i, "section": p["section"],
                          "position": p["position"],
                          "sha256": rebuild.sha256_text(p["text"])})
    mpath = tmp_path / "manifest.jsonl"
    mpath.write_text("".join(json.dumps(r) + "\n" for r in manifest))
    ipath = tmp_path / "index.json"
    ipath.write_text(json.dumps({"version": 1, "paragraphs": index}))
    return tmp_path, cache, mpath, ipath


def run(tmp, cache, mpath, ipath, *extra):
    return rebuild.main(["--out", str(tmp / "out"), "--cache", str(cache),
                         "--manifest", str(mpath), "--index", str(ipath),
                         "--no-fetch", *extra])


def test_rebuild_writes_both_splits_with_verified_text(fake):
    tmp, cache, mpath, ipath = fake
    assert run(tmp, cache, mpath, ipath) == 0
    train = json.loads((tmp / "out" / "train-paragraphs.json").read_text())
    test = json.loads((tmp / "out" / "test-paragraphs.json").read_text())
    assert [p["paragraph"] for p in train["paragraphs"]] == [1, 2, 3]
    assert [p["paragraph"] for p in test["paragraphs"]] == [4, 5, 6]
    assert [p["section"] for p in train["paragraphs"]] == \
        ["introduction", "methods", "discussion"]
    assert "rain" in train["paragraphs"][0]["text"]
    assert all("snow" in p["text"] for p in test["paragraphs"])
    # the harness reads the files as written
    sys.path.insert(0, str(REPO / "ml" / "critics" / "laya"))
    import harness
    got = harness.label_paragraphs(tmp / "out" / "train-paragraphs.json")
    assert set(got) == {1, 2, 3} and got[2]["section"] == "methods"


def test_changed_text_is_refused_not_silently_used(fake):
    tmp, cache, mpath, ipath = fake
    path = cache / "xml" / "PMC9100001.xml"
    path.write_bytes(path.read_bytes().replace(b"Intro paragraph 1",
                                               b"Intro paragraph one"))
    assert run(tmp, cache, mpath, ipath) == 1
    train = json.loads((tmp / "out" / "train-paragraphs.json").read_text())
    assert [p["paragraph"] for p in train["paragraphs"]] == [2, 3]
    assert run(tmp, cache, mpath, ipath, "--allow-missing") == 0


def test_missing_xml_and_non_trainable_articles_are_reported(fake):
    tmp, cache, mpath, ipath = fake
    (cache / "xml" / "PMC9100002.xml").unlink()
    index = rebuild.read_index(ipath)
    manifest = rebuild.read_manifest(mpath)
    rows, problems = rebuild.rebuild(index, manifest, cache)
    assert len(rows["train"]) == 3 and "test" not in rows
    assert {why for *_, why in problems} == {"XML not in the cache"}
    manifest["PMC9100001"]["use"] = "eval"
    rows, problems = rebuild.rebuild(index, manifest, cache)
    assert "train" not in rows and len(problems) == 6


def test_refuses_an_output_folder_inside_the_repository(fake):
    tmp, cache, mpath, ipath = fake
    with pytest.raises(ValueError):
        rebuild.main(["--out", str(HERE / "rebuilt"), "--cache", str(cache),
                      "--manifest", str(mpath), "--index", str(ipath),
                      "--no-fetch"])


def test_index_with_text_is_refused(tmp_path):
    p = tmp_path / "i.json"
    p.write_text(json.dumps({"version": 1, "paragraphs": [{"text": "x"}]}))
    with pytest.raises(ValueError):
        rebuild.read_index(p)


# --- the committed files --------------------------------------------------------------

def _committed():
    return {name: HERE / name for name in
            ("train-labels.json", "test-labels.json", "paragraph-index.json",
             "notes.jsonl")}


@pytest.mark.skipif(not (HERE / "paragraph-index.json").exists(),
                    reason="labels not committed yet")
def test_committed_labels_point_at_trainable_indexed_paragraphs():
    import label_precision
    files = _committed()
    index = rebuild.read_index(files["paragraph-index.json"])
    by_n = {p["paragraph"]: p for p in index["paragraphs"]}
    assert len(by_n) == len(index["paragraphs"])
    manifest = rebuild.read_manifest(common.MANIFEST)
    for p in index["paragraphs"]:
        assert set(p) <= {"paragraph", "split", "pmcid", "discipline",
                          "licence", "body_index", "section", "position",
                          "sha256", "n_words"}
        row = manifest[p["pmcid"]]
        assert row["use"] == "train" and row["split"] == p["split"]
        assert row["licence"].startswith(("CC-BY-", "CC0-"))
        assert not any(x in row["licence"] for x in ("-NC", "-ND", "-SA"))
    seen = set()
    for split in ("train", "test"):
        labels = label_precision.load(files[f"{split}-labels.json"])
        assert labels
        for x in labels:
            assert by_n[x["paragraph"]]["split"] == split
            assert x["section"] == by_n[x["paragraph"]]["section"]
            key = (x["paragraph"], x["flag"])
            assert key not in seen
            seen.add(key)
    # a paragraph's articles never sit on both sides
    sides = {}
    for p in index["paragraphs"]:
        assert sides.setdefault(p["pmcid"], p["split"]) == p["split"]
    notes = [json.loads(line) for line in
             files["notes.jsonl"].read_text(encoding="utf-8").splitlines()
             if line.strip()]
    assert {(n["paragraph"], n["flag"]) for n in notes} == seen
    for n in notes:
        # at most six flagged words, and no longer quotation in a reason
        words = re.sub(r"[^a-z0-9]+", " ", n.get("words", "").lower())
        assert len(words.split()) <= 6
        assert len(n["reason"]) <= 200
        for quoted in re.findall(r'"([^"]*)"', n["reason"]):
            assert len(quoted.replace("...", " ").split()) <= 6, quoted

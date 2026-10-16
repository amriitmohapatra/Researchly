"""S5a corpus tooling on synthetic JATS (nothing fetched; stdlib only).

The XML below is written for these tests; it is not any article's text.
"""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import harvest  # noqa: E402
import weak_labels  # noqa: E402

BODY_PARA = ("This synthetic paragraph exists so that the parser has enough "
             "body text to count as a full article rather than an abstract "
             "record, and it repeats its point at some length on purpose. ")


def jats(permissions: str, *, structured=True, paras=8, pmcid="9000001",
         doi="10.0000/synthetic.1") -> bytes:
    abstract = ("<abstract><sec><title>Background</title><p>Fevers rise in "
                "the wet season. Nobody knows why.</p></sec>"
                "<sec><title>Methods</title><p>We counted cases in ten towns "
                "[<xref ref-type=\"bibr\">3</xref>].</p></sec>"
                "<sec><title>Results</title><p>Cases doubled after rain. "
                "The effect held in every town.</p></sec>"
                "<sec><title>Funding</title><p>A synthetic grant paid for "
                "this.</p></sec>"
                "<sec><title>Conclusions</title><p>Rain predicts fever.</p>"
                "</sec></abstract>" if structured else
                "<abstract><p>An unstructured synthetic abstract.</p></abstract>")
    body = "".join(f"<p>Record {pmcid}. {BODY_PARA * 3}</p>"
                   for _ in range(paras))
    return (f"""<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:ali="http://www.niso.org/schemas/ali/1.0/"><front><journal-meta><journal-id journal-id-type="nlm-ta">Synth J</journal-id></journal-meta>
<article-meta><article-id pub-id-type="pmcid">PMC{pmcid}</article-id>
<article-id pub-id-type="pmid">123</article-id><article-id pub-id-type="doi">{doi}</article-id>
<pub-date><year>2024</year></pub-date>{permissions}{abstract}</article-meta></front>
<body><sec><title>Introduction</title>{body}</sec><sec><title>2. Materials and methods</title>{body}</sec>
<sec><title>Results</title><sec><title>Nested</title>{body}</sec></sec><sec><title>Discussion</title>{body}</sec></body></article>""").encode()


def perm(inner: str) -> str:
    return f"<permissions>{inner}</permissions>"


# --- licence at intake ----------------------------------------------------------

@pytest.mark.parametrize("inner,spdx,use", [
    ('<license xlink:href="https://creativecommons.org/licenses/by/4.0/">x</license>',
     "CC-BY-4.0", "train"),
    ('<ali:license_ref>http://creativecommons.org/licenses/by/3.0/</ali:license_ref>',
     "CC-BY-3.0", "train"),
    ('<license><p>This is an open access article distributed under the terms of the '
     'Creative Commons Attribution License.</p></license>', "CC-BY-4.0", "train"),
    ('<license xlink:href="https://creativecommons.org/publicdomain/zero/1.0/">x</license>',
     "CC0-1.0", "train"),
    ('<license xlink:href="https://creativecommons.org/licenses/by-nc/4.0/">x</license>',
     "CC-BY-NC-4.0", "eval"),
    ('<license xlink:href="https://creativecommons.org/licenses/by-nc-nd/4.0/">x</license>',
     "CC-BY-NC-ND-4.0", "eval"),
    ('<license xlink:href="http://creativecommons.org/licenses/by-nd/4.0/">x</license>',
     "CC-BY-ND-4.0", "eval"),
    ('<license><p>Creative Commons Attribution-NonCommercial 4.0 International '
     'License</p></license>', "CC-BY-NC-4.0", "eval"),
    ("<license><p>Creative Commons Attribution-NonCommercial License</p></license>",
     "CC-BY-NC-unversioned", "eval"),
    ("<license><license-p>This is an open access article under the CC BY "
     "license.</license-p></license>", "CC-BY-unversioned", "train"),
    ("<copyright-statement>Published by a publisher. This is an Open Access "
     "article under the CC BY-NC-ND 4.0 license</copyright-statement>",
     "CC-BY-NC-ND-4.0", "eval"),
    # Springer Nature / BMC: CC BY for the article, CC0 only for the data
    ('<license><ali:license_ref>https://creativecommons.org/licenses/by/4.0/'
     '</ali:license_ref><license-p>This article is distributed under the terms '
     'of the Creative Commons Attribution 4.0 International License. The '
     'Creative Commons Public Domain Dedication waiver (<ext-link '
     'xlink:href="http://creativecommons.org/publicdomain/zero/1.0/">'
     'http://creativecommons.org/publicdomain/zero/1.0/</ext-link>) applies to '
     'the data made available in this article, unless otherwise stated.'
     '</license-p></license>', "CC-BY-4.0", "train"),
])
def test_licence_classes(inner, spdx, use):
    got, got_use, evidence = common.licence_of(jats(perm(inner)))
    assert (got, got_use) == (spdx, use) and evidence


@pytest.mark.parametrize("inner", [
    "",                                                         # no licence
    "<copyright-statement>© The Authors</copyright-statement>",  # unclear
    ('<license xlink:href="https://creativecommons.org/licenses/by/4.0/"/>'
     '<license xlink:href="https://creativecommons.org/licenses/by-nc/4.0/"/>'),
    # a publisher's own free-access grant is not a reuse licence
    "<license><license-p>The publisher grants permission to make this "
    "research available in PubMed Central for as long as the resource "
    "centre remains active.</license-p></license>",
])
def test_unclear_or_conflicting_licences_are_dropped(inner):
    xml = jats(perm(inner)) if inner else jats("")
    spdx, use, why = common.licence_of(xml)
    assert spdx is None and use is None and why


# --- structure and weak labels ------------------------------------------------------

def test_abstract_and_section_roles():
    root = common.parse_xml(jats(perm(
        '<license xlink:href="https://creativecommons.org/licenses/by/4.0/"/>')))
    heads = [h for h, _ in common.abstract_sections(root)]
    assert heads == ["Background", "Methods", "Results", "Funding",
                     "Conclusions"]
    assert [common.abstract_role(h) for h in heads] == [
        "background", "methods", "results", None, "conclusions"]
    roles = [common.section_role(h) for h, _ in common.body_sections(root)]
    assert roles == ["introduction", "methods", "results", "discussion"]


@pytest.mark.parametrize("heading,role", [
    ("Methods and findings", None), ("Methods and Findings", None),
    ("Objective", "objective"), ("Aims:", "objective"),
    ("Design, setting, and participants", "methods"),
    ("Findings", "results"), ("Interpretation", "conclusions"),
    ("Conclusions and Relevance", "conclusions"), ("Importance", "background"),
    ("Trial registration", None), ("Funding", None),
])
def test_abstract_heading_map(heading, role):
    assert common.abstract_role(heading) == role


def test_citations_are_dropped_from_sentences():
    root = common.parse_xml(jats(perm("")))
    methods = dict(common.abstract_sections(root))["Methods"][0]
    assert "3" not in methods and methods.endswith("towns.")


def test_sentence_splitter_keeps_abbreviations_together():
    s = common.sentences("Cases rose (e.g. in towns). Rates fell, cf. Fig. 2 "
                         "for details. We used R. A model was fitted.")
    # A lone capital before a full stop is read as an initial, so "R. A"
    # stays joined: a weak-label splitter errs towards longer sentences.
    assert s == ["Cases rose (e.g. in towns).",
                 "Rates fell, cf. Fig. 2 for details.",
                 "We used R. A model was fitted."]


def test_split_is_stable_and_roughly_ten_percent():
    splits = [common.split_of(f"PMC{i}") for i in range(4000)]
    assert splits == [common.split_of(f"PMC{i}") for i in range(4000)]
    assert 0.08 < splits.count("test") / 4000 < 0.12
    assert 0.08 < splits.count("dev") / 4000 < 0.12


# --- the manifest holds no text ---------------------------------------------------------

def _cache(tmp_path, docs):
    cache = tmp_path / "cache"
    (cache / "xml").mkdir(parents=True)
    with (cache / "index.jsonl").open("w") as f:
        for pmcid, disc, xml in docs:
            f.write(json.dumps({"pmcid": pmcid, "discipline": disc}) + "\n")
            (cache / "xml" / f"{pmcid}.xml").write_bytes(xml)
    return cache


def test_manifest_end_to_end(tmp_path):
    by = perm('<license xlink:href="https://creativecommons.org/licenses/by/4.0/"/>')
    nc = perm('<license xlink:href="https://creativecommons.org/licenses/by-nc/4.0/"/>')
    docs = [
        ("PMC1", "epidemiology", jats(by, pmcid="1", doi="10.1/a")),
        ("PMC2", "humanities", jats(nc, pmcid="2", doi="10.1/b",
                                    structured=False)),
        ("PMC3", "engineering", jats(perm(""), pmcid="3", doi="10.1/c")),
        ("PMC4", "engineering", jats(by, pmcid="4", doi="10.1/a")),   # DOI dup
        ("PMC5", "engineering", jats(by, pmcid="5", doi="10.1/e", paras=1)),
    ]
    cache = _cache(tmp_path, docs)
    out = tmp_path / "manifest.jsonl"
    summary = harvest.manifest(cache, out, checked="test")
    rows = harvest.read_manifest(out)
    assert [r["pmcid"] for r in rows] == ["PMC1", "PMC2"]
    assert rows[0]["use"] == "train" and "ship_model" in rows[0]["permitted_use"]
    assert rows[1]["use"] == "eval" and "ship_model" not in rows[1]["permitted_use"]
    assert rows[0]["structured_abstract"] and rows[0]["abstract_sections"] == 4
    assert summary["dropped"] == {
        "licence: no Creative Commons licence named": 1,
        "duplicate (DOI)": 1,
        "no full body (abstract only or too short)": 1}
    raw = out.read_text()
    assert "synthetic" not in raw.replace("10.0000/synthetic", "")
    assert "Fevers" not in raw and "paragraph" not in raw.lower().replace(
        '"paragraphs"', "")

    labels = weak_labels.build(cache, out)
    sents = [json.loads(x) for x in
             (cache / "labels" / "sentences.jsonl").read_text().splitlines()]
    assert {s["role"] for s in sents} == {"background", "methods", "results",
                                          "conclusions"}
    assert all(s["pmcid"] == "PMC1" for s in sents)       # PMC2 unstructured
    assert labels["articles_with_roles"] == 1
    paras = (cache / "labels" / "paragraphs.jsonl").read_text().splitlines()
    assert {json.loads(p)["section"] for p in paras} == {
        "introduction", "methods", "results", "discussion"}


def test_manifest_rows_refuse_text_fields():
    row = {"id": "pmc-PMC1", "pmcid": "PMC1", "use": "train",
           "discipline": "epidemiology", "title": "A title is text"}
    with pytest.raises(ValueError):
        common.check_manifest_row(row)
    row.pop("title")
    row["doi"] = "x" * 500
    with pytest.raises(ValueError):
        common.check_manifest_row(row)


def test_cache_inside_the_repo_is_refused():
    with pytest.raises(ValueError):
        common.outside_repo(common.REPO / "ml" / "corpus" / "cache")


def test_committed_manifest_is_valid_and_text_free():
    if not common.MANIFEST.exists():
        pytest.skip("no manifest built yet")
    rows = harvest.read_manifest()
    assert rows and len({r["pmcid"] for r in rows}) == len(rows)
    assert len({r["discipline"] for r in rows}) >= 6
    for r in rows:
        assert r["licence"].startswith(("CC-BY", "CC0"))
        trainable = bool(re.fullmatch(r"CC0-1\.0|CC-BY-(\d\.\d|unversioned)",
                                      r["licence"]))
        assert (r["use"] == "train") == trainable, r["pmcid"]


def test_mirror_seeds_the_index_from_the_manifest_without_rewriting_it(
        tmp_path):
    """harvest.py mirror: the committed manifest's articles, no search."""
    by = perm('<license xlink:href="https://creativecommons.org/licenses/by/4.0/"/>')
    cache = _cache(tmp_path, [("PMC1", "epidemiology",
                               jats(by, pmcid="1", doi="10.1/a"))])
    out = tmp_path / "manifest.jsonl"
    harvest.manifest(cache, out, checked="test")
    before = out.read_text()
    fresh = tmp_path / "fresh-cache"
    fresh.mkdir()
    (fresh / "index.jsonl").write_text(json.dumps(
        {"pmcid": "PMC9", "discipline": "humanities",
         "search_licence": ""}) + "\n")
    assert harvest.seed_from_manifest(fresh, out) == 2
    index = harvest.read_index(fresh)
    assert set(index) == {"PMC1", "PMC9"}
    assert index["PMC1"]["discipline"] == "epidemiology"
    assert out.read_text() == before

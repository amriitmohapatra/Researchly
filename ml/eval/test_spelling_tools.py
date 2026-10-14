"""The spelling benchmark and the two spelling-data builders (2026-10-14).

Synthetic inputs only; nothing is fetched.
"""

import importlib.util
from pathlib import Path

import spelling_bench as sb

ROOT = Path(__file__).resolve().parents[2]


def _tool(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "ml" / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- spelling_bench -----------------------------------------------------------

def test_parses_every_list_format():
    assert sb.parse("$because\nbecuase\nbecasue\n", "dollar") == [
        ("becuase", "because"), ("becasue", "because")]
    assert sb.parse("receive: recieve receve\n", "colon") == [
        ("recieve", "receive"), ("receve", "receive")]
    assert sb.parse(" acheive->achieve\nabotu->about, abbot\n", "arrow") == [
        ("acheive", "achieve"), ("abotu", "about")]
    assert sb.parse("teh,the\n", "csv") == [("teh", "the")]


def test_clean_keeps_single_lowercase_words():
    rows = [("teh", "the"), ("Teh", "The"), ("in the", "inthe"),
            ("same", "same"), ("teh", "the")]
    assert sb.clean(rows) == [("teh", "the")]


def test_split_is_deterministic_and_about_one_fifth_test():
    words = [f"w{i}" for i in range(2000)]
    first = [sb.split_of(w) for w in words]
    assert first == [sb.split_of(w) for w in words]
    share = first.count("test") / len(words)
    assert 0.15 < share < 0.25


def test_evaluate_counts_detection_and_ranking():
    r = sb.evaluate([("recieve", "receive"), ("teh", "the")])
    assert r["pairs"] == 2 and r["detected"] == 2
    assert r["noisy_channel"]["top1"] == 2
    assert r["false_alarms"] == 0


# --- build_spell_errors ------------------------------------------------------

def test_error_model_counts_edits_with_context():
    bse = _tool("build_spell_errors")
    pairs = [("recieve", "receive"), ("beleive", "believe"),
             ("acheive", "achieve")] * 2
    model = bse.build(pairs)
    assert model["pairs"] == 6
    assert any(k.startswith("transpose|") for k in model["edits"])
    assert all(v < 0 for v in model["edits"].values())


def test_error_model_refuses_a_source_without_ship_model(tmp_path, capsys):
    bse = _tool("build_spell_errors")
    pairs = tmp_path / "pairs.tsv"
    pairs.write_text("recieve\treceive\n", encoding="utf-8")
    rc = bse.main(["--pairs", f"wikipedia-misspellings-for-machines="
                              f"{pairs}:tsv",
                   "--out", str(tmp_path / "out.json")])
    assert rc == 2
    assert "does not permit ship_model" in capsys.readouterr().err
    assert not (tmp_path / "out.json").exists()


def test_experimental_table_must_stay_outside_the_repo(tmp_path):
    bse = _tool("build_spell_errors")
    pairs = tmp_path / "pairs.tsv"
    pairs.write_text("recieve\treceive\n", encoding="utf-8")
    rc = bse.main(["--experiment",
                   "--pairs", f"mitton-misspelling-corpora={pairs}:tsv",
                   "--out", str(ROOT / "packages" / "spell_errors.json")])
    assert rc == 2


# --- build_variants ----------------------------------------------------------

VARCON = """\
# color <verified> (level 10)
A Cv: color / B C: colour

# meter <verified> (level 20)
A B: meter | measuring device
A Cv: meter / B C: metre | unit

# organize <verified> (level 20)
A Z: organize / B: organise

# among <verified> (level 10)
A B. Z: among / AV B Zv: amongst

# zymurgize (level 95)
A Z: zymurgize / B: zymurgise
"""


def test_variants_respect_senses_marks_and_levels():
    bv = _tool("build_variants")
    words, pairs = bv.build(VARCON)
    assert ("color", "colour") in pairs
    assert ("organise", "organize") in pairs
    assert ("meter", "metre") not in pairs        # British "meter" (device)
    assert ("among", "amongst") not in pairs      # "." = equal in British
    assert "zymurgize" not in words               # level 95 > 80
    # Oxford (Z) spells "colour" as British does
    assert "Z" in words["colour"][0]
    assert words["organise"][0] == "B"


def test_variants_file_carries_varcons_notice(tmp_path):
    bv = _tool("build_variants")
    src = tmp_path / "varcon.txt"
    src.write_text(VARCON, encoding="latin-1")
    readme = tmp_path / "README"
    readme.write_text("intro\n\nCopyright\n=========\n\nCopyright 2000-2019 "
                      "by Kevin Atkinson\n\nPermission to use ...\n",
                      encoding="latin-1")
    out = tmp_path / "variants.tsv"
    assert bv.main([str(src), str(readme), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "# Copyright 2000-2019 by Kevin Atkinson" in text
    assert "=\tcolor\tcolour" in text


def test_shipped_variants_file_is_current_format():
    path = ROOT / "packages" / "core" / "researchly" / "data" / "variants.tsv"
    rows = [line for line in path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")]
    assert any(r.startswith("=\t") for r in rows)
    assert all(len(r.split("\t")) == 3 for r in rows)
    assert "Kevin Atkinson" in path.read_text(encoding="utf-8")


def test_no_learned_error_table_ships_until_the_owner_decides():
    # PLAN 2026-10-14: the only lists that could train it are CC BY-SA or
    # unlicensed. Remove this test in the change that ships one.
    assert not (ROOT / "packages" / "core" / "researchly" / "data"
                / "spell_errors.json").exists()



# --- build_specialist_words --------------------------------------------------

LRAGR = """\
E1|spectrin|noun|count(thr_sing)|spectrin|spectrin|
E1|spectrins|noun|count(thr_plur)|spectrins|spectrin|
E2|accessible|adj|positive|accessible|accessible|
E2|accessable|adj|positive|accessable|accessible|
E3|crosssectional|adj|positive|crosssectional|crosssectional|
E4|ad|noun|count(thr_sing)|ad|ad|
E5|controled|verb|past|controled|control|
E6|Spectrin Repeat|noun|count(thr_sing)|Spectrin Repeat|x|
"""
LRSPL = "E2|accessible|accessable|\n"


def test_specialist_filtering(tmp_path):
    bsw = _tool("build_specialist_words")
    a, s = tmp_path / "LRAGR", tmp_path / "LRSPL"
    a.write_text(LRAGR, encoding="utf-8")
    s.write_text(LRSPL, encoding="utf-8")
    keep, stats = bsw.build(bsw.forms(a), bsw.variant_groups(s))
    assert "spectrin" in keep and "spectrins" in keep
    assert "accessable" not in keep        # literature misspelling
    assert "crosssectional" not in keep    # tripled letter
    assert "ad" not in keep                # shorter than 5 letters
    assert "controled" not in keep         # misinflected
    assert stats["dropped_variants"] == 1


def test_shipped_specialist_list_carries_its_conditions():
    path = (ROOT / "packages" / "core" / "researchly" / "data"
            / "specialist_words.txt")
    head = "".join(path.open(encoding="utf-8").readlines()[:60])
    assert "SPECIALIST NLP Tools" in head and "release 2026" in head
    assert "Modifications" in head and "4. Use of the SPECIALIST" in head

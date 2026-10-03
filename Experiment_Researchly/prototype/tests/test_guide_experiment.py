"""Experiment (2026-08-14): move classifier + exemplar guide layer.

Pins the contracts of ideas 1+2: the classifier abstains honestly and
carries provenance; the hybrid labeller keeps lexicon precision for the
model's blind spots; exemplar retrieval only returns real, cited corpus
sentences; the guide reports coverage without generating prose; and none
of it changes api.analyze() output.
"""

from pathlib import Path

import pytest

from researchly import api
from researchly import guide as guide_mod
from researchly.document import Document
from researchly.exemplars import ExemplarIndex, get_index
from researchly.moves import MoveClassifier, get_classifier

NLP = api.get_nlp()


# --- classifier ------------------------------------------------------------

def test_model_artifact_ships_and_loads():
    c = get_classifier()
    assert c.available(), c.why_unavailable()
    d = c.describe()
    assert d["version"].startswith("moves-v0")
    assert d["accuracy"] and d["accuracy"] > 0.8       # held-out, pinned
    assert d["trained_on"].startswith("PubMed")


def test_classifier_labels_canonical_sentences():
    c = get_classifier()
    cases = {
        "methods": "We fitted a compartmental transmission model to "
                   "weekly incidence data using Hamiltonian Monte Carlo.",
        "findings": "The reproduction number was 2.3 (95% CI 1.8-2.9).",
        "significance": "These findings suggest that surveillance "
                        "strategies should account for age structure.",
    }
    for want, sent in cases.items():
        move, p = c.predict_one(sent)
        assert move == want, (sent, move, p)
        assert p >= c.threshold


def test_classifier_abstains_rather_than_guessing():
    c = get_classifier()
    move, p = c.predict_one("Der Fluss war im Winter sehr schoen.")
    assert move == "other" or p < 0.8      # non-English: no confident call


def test_missing_model_abstains_with_a_reason():
    c = MoveClassifier(model_path=Path("/nonexistent/model.joblib"))
    assert not c.available()
    assert "train_moves" in c.why_unavailable()
    assert c.predict(["We fitted a model."]) == [("other", 0.0)]


# --- hybrid labeller -------------------------------------------------------

def test_lexicons_cover_the_models_blind_spots():
    gap, _, how = guide_mod.label_hybrid(
        "The role of serotype interactions remains unclear.")
    assert (gap, how) == ("gap", "lexicon")
    aim, _, how = guide_mod.label_hybrid(
        "We aimed to quantify the contribution of household transmission.")
    assert (aim, how) == ("aim", "lexicon")
    lim, _, how = guide_mod.label_hybrid(
        "A key limitation is that mild cases may be undercounted.")
    assert (lim, how) == ("limitation", "lexicon")


def test_model_handles_what_lexicons_do_not():
    move, _, how = guide_mod.label_hybrid(
        "Parameters were estimated with a hierarchical Bayesian model "
        "fitted to age-stratified hospitalisation counts.")
    assert how == "model" and move == "methods"


# --- exemplar index --------------------------------------------------------

def test_shipped_index_loads_with_all_moves():
    idx = get_index()
    assert idx.available(), idx.why_unavailable()
    s = idx.stats()
    assert s["exemplars"] > 1000
    assert len(s["sources"]) >= 15
    for move in ("background", "gap", "aim", "methods", "findings",
                 "significance", "limitation"):
        assert s["by_move"].get(move), f"no exemplars for {move}"


def test_query_returns_only_cited_corpus_sentences():
    idx = get_index()
    out = idx.query("gap", "dengue transmission heterogeneity", k=3)
    assert out
    texts = {r["text"] for r in idx.rows()}
    for ex in out:
        assert ex["move"] == "gap"
        assert ex["source"]                    # every exemplar is cited
        assert ex["text"] in texts             # retrieval, not generation


def test_query_caps_exemplars_per_source():
    idx = get_index()
    for move in ("methods", "findings"):
        out = idx.query(move, "covid transmission model", k=6)
        per = {}
        for ex in out:
            per[ex["source"]] = per.get(ex["source"], 0) + 1
        assert all(n <= 2 for n in per.values()), \
            "one document dominates the exemplars (style-bias guard)"


def test_missing_index_degrades_to_empty():
    idx = ExemplarIndex(path=Path("/nonexistent/exemplars.jsonl"))
    assert not idx.available()
    assert idx.query("gap", "anything") == []
    assert "build_exemplars" in idx.why_unavailable()


# --- the guide -------------------------------------------------------------

INTRO_NO_GAP = (
    "Introduction\n\nDengue is a leading cause of febrile illness "
    "across Southeast Asia and its burden has grown for decades. "
    "We aimed to quantify the contribution of income-related "
    "heterogeneity to transmission.\n\n"
    "Methods\n\nWe fitted a compartmental model to weekly incidence "
    "data. Parameters were estimated in a Bayesian framework.")


def test_guide_flags_missing_gap_with_frames_and_exemplars():
    g = guide_mod.build_guide(Document.from_text(INTRO_NO_GAP, "plain"))
    intro = next(s for s in g["sections"] if s["section"] == "introduction")
    assert intro["checked"]
    assert intro["moves_present"].get("aim")
    missing = {m["move"]: m for m in intro["missing"]}
    assert "gap" in missing
    assert missing["gap"]["frame"]
    assert missing["gap"]["exemplars"], "gap exemplars should surface"
    meth = next(s for s in g["sections"] if s["section"] == "methods")
    assert not meth["missing"], "methods only expects methods sentences"


def test_guide_does_not_nag_unmapped_sections():
    g = guide_mod.build_guide(Document.from_text(
        "Some pasted paragraph with no headings at all.", "plain"))
    for sec in g["sections"]:
        if sec["section"] not in guide_mod.SECTION_EXPECTED:
            assert not sec["checked"] and not sec["missing"]


def test_guide_payload_carries_provenance_not_prose():
    g = guide_mod.build_guide(Document.from_text(INTRO_NO_GAP, "plain"))
    assert g["model"]["version"].startswith("moves-v0")
    assert g["exemplars"]["exemplars"] > 0
    assert "generated" in g["note"] or "generation" in g["note"]


def test_guide_from_word_paragraphs():
    paras = [{"text": "Discussion", "style": "Heading1"},
             {"text": "Transmission was higher in dense districts. "
                      "The rate ratio was 1.8 (95% CI 1.2-2.6).",
              "style": "Normal"}]
    g = guide_mod.build_guide(api.build_document(paras))
    disc = next(s for s in g["sections"] if s["section"] == "discussion")
    missing = {m["move"] for m in disc["missing"]}
    assert "significance" in missing or "limitation" in missing


# --- isolation -------------------------------------------------------------

def test_experiment_layer_does_not_change_analyze_output():
    text = "We utilize a model in order to predict the outcome."
    ids = {s.rule_id for s in api.analyze(text, nlp=NLP).suggestions}
    import researchly.guide, researchly.moves, researchly.exemplars  # noqa
    ids2 = {s.rule_id for s in api.analyze(text, nlp=NLP).suggestions}
    assert ids == ids2
    from researchly.engine import REGISTRY
    assert not any(r.startswith("MV") or r.startswith("EX")
                   for r in REGISTRY)

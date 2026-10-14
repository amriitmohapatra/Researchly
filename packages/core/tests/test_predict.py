"""Word prediction (2026-10-14): a core feature within CLAUDE.md #1's limits.

The limits are what these tests hold: words or a short fixed term, never a
sentence; candidates only (a surface inserts on Tab or click); nothing
inside masked text; the writer can turn it off. The model here is a tiny
synthetic one, so the tests do not depend on the shipped corpus; the last
section checks the shipped model itself. Synthetic sentences only.
"""

from __future__ import annotations

from collections import Counter

import pytest

from researchly import api, config, health, predict

SENTENCES = [
    "we estimated the basic reproduction number from weekly case counts",
    "the basic reproduction number was estimated with a renewal model",
    "we report the median and the confidence interval for each estimate",
    "estimates are shown with a confidence interval in each table",
    "the confidence interval was wide because the sample was small",
    "bayesian inference was used to estimate the transmission rate",
    "we fitted a transmission model to the weekly case counts",
    "the modelling study used a transmission model of influenza",
]
FORMS = {"bayesian": "Bayesian"}


def _tables(sentences, copies=10):
    counts = {k: {} for k in range(predict.ORDER)}
    for _ in range(copies):
        for sent in sentences:
            seq = ["<s>"] + sent.split()
            for i in range(1, len(seq)):
                for k in range(predict.ORDER):
                    if i - k < 0:
                        break
                    ctx = tuple(seq[i - k:i])
                    counts[k].setdefault(ctx, Counter())[seq[i]] += 1
    return {k: {ctx: (sum(c.values()), c.most_common(40))
                for ctx, c in table.items()}
            for k, table in counts.items()}


@pytest.fixture(scope="module")
def model(tmp_path_factory):
    path = tmp_path_factory.mktemp("predict") / "tiny.sqlite"
    predict.write_model(path, _tables(SENTENCES), FORMS, {"version": 1})
    return predict.Model(path)


@pytest.fixture
def shipped(monkeypatch, model):
    """api.complete() with the tiny model in place of the shipped one."""
    monkeypatch.setattr(predict, "_MODEL", model)
    monkeypatch.setattr(predict, "MODEL_FILE", model.path)
    return model


def texts(found):
    return [c.text for c in found]


# --- what it offers ---------------------------------------------------------

def test_completes_the_word_being_typed(model):
    got = predict.complete("We estimated the basic rep", 26, model=model)
    assert got[0].text.split()[0] == "reproduction"
    assert (got[0].start, got[0].end) == (23, 26)


def test_offers_a_fixed_term_when_the_model_is_sure(model):
    got = predict.complete("We estimated the basic rep", 26, model=model)
    assert got[0].text == "reproduction number" and got[0].kind == "term"


def test_next_word_after_a_space(model):
    got = predict.complete("We fitted a transmission ", 25, model=model)
    assert "model" in texts(got)
    assert all(c.start == c.end == 25 for c in got)


def test_never_more_than_three_words(model):
    for text in ("the basic ", "We report the ", "the confidence ", "we "):
        for c in predict.complete(text, len(text), model=model):
            assert len(c.text.split()) <= predict.MAX_TERM_WORDS


def test_a_term_never_ends_on_a_function_word(model):
    for text in ("the confidence ", "the basic ", "a transmission "):
        for c in predict.complete(text, len(text), model=model):
            assert c.text.split()[-1].lower() not in predict._FUNCTION \
                or c.kind == "word"


def test_replacing_the_span_gives_the_candidate(model):
    text = "the confidence inte"
    for c in predict.complete(text, len(text), model=model):
        assert (text[:c.start] + c.text).lower().startswith(text.lower())


def test_saves_at_least_two_letters(model):
    for c in predict.complete("the transmission mode", 21, model=model):
        assert len(c.text) - (c.end - c.start) >= predict.MIN_SAVED


def test_usual_case_and_sentence_start(model):
    assert texts(predict.complete("Inference used bay", 18,
                                  model=model))[:1] == ["Bayesian"]
    got = predict.complete("It rose. The basic rep", 22, model=model)
    assert got[0].text.startswith("reproduction")
    got = predict.complete("It rose. Est", 12, model=model)
    assert all(c.text[0].isupper() for c in got)


def test_follows_the_chosen_spelling(model):
    us = predict.complete("a transmission modelling study and the mod", 42,
                          spelling_choice="us", model=model)
    assert "modeling" in [t.lower() for t in texts(us)]
    assert "modelling" not in [t.lower() for t in texts(us)]


def test_nothing_right_after_punctuation_or_at_a_sentence_start(model):
    assert predict.complete("the basic,", 10, model=model) == []
    assert predict.complete("It rose. ", 9, model=model) == []
    assert predict.complete("", 0, model=model) == []


def test_never_repeats_the_previous_word(model):
    got = predict.complete("we estimated the ", 17, model=model)
    assert "the" not in [t.lower() for t in texts(got)]


# --- api.complete: masking, settings, offsets --------------------------------

def test_api_returns_candidates_with_absolute_offsets(shipped):
    text = "Methods\n\nWe estimated the basic rep and more."
    cursor = text.index(" and")
    got = api.complete(text, cursor, cfg=config.Config())
    assert got.status == "ok"
    c = got.candidates[0]
    assert text[c.start:c.end] == "rep" and c.end == cursor


def test_api_off_when_the_writer_turns_it_off(shipped):
    got = api.complete("the basic rep", cfg=config.Config(prediction=False))
    assert got.status == "off" and got.candidates == []


@pytest.mark.parametrize("text,kind", [
    ("We set $\\alpha + bas", "latex"),            # maths being typed
    ("As shown by \\cite{bas", "latex"),            # a citation key
    ("See \\ref{fig:bas", "latex"),
    ("We call \\bas", "latex"),                     # a command name
    ("Run `predict(bas", "markdown"),              # inline code
    ("```\nx = bas", "markdown"),                   # a code block
    ("Data at https://example.org/bas", "plain"),  # a URL
    ("As [@smith2020; @bas", "markdown"),          # a citation
])
def test_nothing_inside_masked_or_unfinished_markup(shipped, text, kind):
    got = api.complete(text, kind=kind, cfg=config.Config())
    assert got.status == "masked" and got.candidates == []


def test_prose_inside_emphasis_is_still_prose(shipped):
    got = api.complete("We estimated the \\emph{basic rep", kind="latex",
                       cfg=config.Config())
    assert got.status == "ok" and got.candidates


def test_a_citation_breaks_the_context(shipped):
    # the words either side of a masked citation are not one sequence
    text = "We estimated the basic \\cite{x} rep"
    got = api.complete(text, kind="latex", cfg=config.Config())
    assert got.status == "ok"
    plain = api.complete("We estimated the basic rep", cfg=config.Config())
    assert plain.candidates[0].text == "reproduction number"


def test_to_dict_is_the_wire_shape(shipped):
    d = api.complete("the basic rep", cfg=config.Config()).to_dict()
    assert set(d) == {"candidates", "status"}
    assert set(d["candidates"][0]) == {"text", "start", "end", "kind",
                                       "score"}


# --- settings and health -------------------------------------------------------

def test_setting_reads_writes_and_comes_from_the_account(tmp_path):
    path = tmp_path / ".researchly.toml"
    path.write_text("[features]\nprediction = false\n", encoding="utf-8")
    cfg = config._apply(config.Config(), config._read_toml(path))
    assert cfg.prediction is False
    assert "prediction = false" in config.dumps(cfg)
    assert config.apply_remote(config.Config(),
                               {"prediction": False}).prediction is False
    assert config.apply_remote(config.Config(),
                               {"prediction": "no"}).prediction is True


def test_health_reports_prediction():
    rows = {s.tier: s for s in health.engine_status(config.Config())}
    assert "prediction" in rows
    off = {s.tier: s for s in health.engine_status(
        config.Config(prediction=False))}["prediction"]
    assert off.state == "disabled" and off.remedy


# --- the shipped model -------------------------------------------------------

needs_model = pytest.mark.skipif(not predict.available(),
                                 reason="no shipped prediction model")


@needs_model
def test_shipped_model_knows_the_field():
    m = predict.Model(predict.MODEL_FILE)
    assert "number" in [w for w, _ in
                        m.next_words(["the", "basic", "reproduction"])]
    got = predict.complete("We report the 95% confidence int", 32, model=m)
    assert got and got[0].text.lower().startswith("interval")


@needs_model
def test_shipped_model_carries_its_attribution():
    m = predict.Model(predict.MODEL_FILE)
    meta = m.meta()
    assert meta["min_docs"] >= 3
    sources = predict.MODEL_FILE.parent / "predict_sources.tsv"
    head = sources.read_text(encoding="utf-8")[:2000]
    assert "CC BY" in head and "Modifications" in head
    rows = [r for r in sources.read_text(encoding="utf-8").splitlines()
            if r and not r.startswith("#")]
    assert len(rows) == meta["articles"]
    assert all(r.split("\t")[2] in ("CC0-1.0",) or
               r.split("\t")[2].startswith("CC-BY-") for r in rows)


# --- the language server (VS Code, Positron) ----------------------------------

def test_lsp_offsets_count_utf16_columns():
    from researchly.lsp import offset_at
    text = "a\U0001D6FC b\nthe basic rep"
    assert offset_at(text, 0, 3) == 2          # after the 2-unit letter
    assert offset_at(text, 1, 13) == len(text)


def test_lsp_offers_predictions_as_completion_items(shipped):
    from researchly.lsp import completion_items
    items = completion_items("We estimated the basic rep", 26, "plain")
    assert items and items[0].label == "reproduction number"
    edit = items[0].text_edit
    assert (edit.range.start.character, edit.range.end.character) == (23, 26)

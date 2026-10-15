"""The live check (S4d R3): `api.check_paragraphs()`.

Its promise: for each paragraph, exactly the findings the full check gives
for the same paragraph under the same heading, restricted to the
sentence-scope rules. These tests hold it to that on synthetic paragraphs
in every section, with and without the grammar tier, and pin the UTF-16
offsets and the opaque ids the edge adds.

Synthetic sentences only (CLAUDE.md).
"""

from __future__ import annotations

import statistics
import time

import pytest

from researchly import api, rules_grammar, shapes
from researchly.config import Config
from researchly.engine import REGISTRY, Category
from researchly.utf16 import Utf16Index, live_id, to_utf16, utf16_len

# Each paragraph is written to trip a spread of sentence-level rules:
# passive voice, hedges and boosters, wordiness, doubled words, spelling,
# agreement, "data was", long sentences, masked citations, maths and URLs.
PARAGRAPHS = {
    "Methods": (
        "The model was calibrated by the authors using weekly data. In order "
        "to estimate the the reproduction number, we used a renewal equation "
        "(Smith et al., 2020). The data was recieved from each district and "
        "it is important to note that the serial interval was assumed to be "
        "gamma distributed with mean $\\mu = 5.2$ days, as described at "
        "https://example.org/methods."),
    "Results": (
        "The effect was very large in every district and clearly proves that "
        "the intervention worked. The models was fitted to 1,204 cases and "
        "the estimates is shown in Table 2. A total of 45% of the cases were "
        "children, which may possibly suggest that schools played a role."),
    "Discussion": (
        "These results may suggest that transmission declined after the "
        "closures, although it could perhaps be argued that reporting "
        "changed at the same time. The model was calibrated by the authors "
        "using weekly data. Due to the fact that testing was limited, the "
        "true number of infections is unknown."),
    "Introduction": (
        "Measles remains a leading cause of death among young children "
        "despite the availability of a safe and effective vaccine, and "
        "outbreaks continue to occur in settings where coverage has fallen "
        "below the threshold needed to interrupt transmission, which "
        "suggests that a better understanding of the drivers of transmission "
        "is needed in order to design targeted interventions that are both "
        "feasible and acceptable to the communities affected."),
    "Abstract": (
        "We estimated the reproduction number of measles in 40 districts, "
        "and the data was very noisy. The reproduction number were above one "
        "in most of them, which clearly proves the point. Vaccination "
        "campaigns should be targetted at the districts with the lowest "
        "coverage."),
    "Limitations": (
        "Our study has several limitation. The data was aggregated by week, "
        "so day-of-week effects could not be estimated."),
    # A topical heading: no section of its own, so the body section.
    "A model of household transmission": (
        "The colour of each line shows the district, and the color of each "
        "point shows the week. We analyse the data and we analyze the "
        "residuals."),
    # No heading at all.
    "": (
        "The model was calibrated by the authors using weekly data. This are "
        "a deliberate slip so that the grammar tier is exercised."),
}


def _cfg(**kw) -> Config:
    cfg = Config()
    cfg.show_preferences = True
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def _key(s):
    return (s.rule_id, s.start, s.end, s.text, s.message, s.replacement,
            s.section, s.category, s.why, s.plain, s.source, s.tier,
            s.fix_safety, s.learn_ref, round(s.confidence, 6))


def _full(text, heading, cfg, style=""):
    """The full check of the paragraph under its heading, restricted to the
    sentence-scope rules and the paragraph's own text."""
    items = ([{"text": heading, "style": "Heading 1"}] if heading else [])
    items.append({"text": text, "style": style})
    off = len(heading) + 2 if heading else 0
    a = api.analyze(items, cfg=cfg, with_metrics=False)
    live = api.live_rule_ids()
    out = []
    for s in a.suggestions:
        if s.rule_id not in live or s.start < off:
            continue
        s.start -= off
        s.end -= off
        out.append(_key(s))
    return out


def _live(text, heading, cfg, style=""):
    res = api.check_paragraphs(
        [{"id": "p1", "text": text, "heading": heading, "style": style}],
        cfg=cfg)
    assert [p.id for p in res.paragraphs] == ["p1"]
    return [_key(s) for s in res.paragraphs[0].suggestions]


@pytest.mark.parametrize("heading", list(PARAGRAPHS))
def test_live_findings_equal_the_full_checks_for_the_same_paragraph(heading):
    text = PARAGRAPHS[heading]
    cfg = _cfg()
    full = _full(text, heading, cfg)
    assert full, "each synthetic paragraph should trip at least one rule"
    assert _live(text, heading, cfg) == full


@pytest.mark.parametrize("heading", ["Methods", "Discussion", ""])
def test_identical_without_the_grammar_tier_and_with_preferences_hidden(heading):
    cfg = _cfg(grammar_tier=False, show_preferences=False)
    assert _live(PARAGRAPHS[heading], heading, cfg) == \
        _full(PARAGRAPHS[heading], heading, cfg)


def test_identical_under_each_article_type_and_spelling():
    text = PARAGRAPHS["A model of household transmission"]
    for doc_type in ("auto", "commentary", "abstract", "grant"):
        for spelling in ("auto", "uk", "us"):
            cfg = _cfg(document_type=doc_type, spelling=spelling)
            assert _live(text, "", cfg) == _full(text, "", cfg), \
                (doc_type, spelling)


def test_identical_to_a_plain_text_check_under_an_imrad_heading():
    """Pasted text with a typed "Methods" line reads the same as a Word
    heading: same section, same findings."""
    cfg = _cfg()
    for heading in ("Methods", "Results", "Discussion"):
        text = PARAGRAPHS[heading]
        a = api.analyze(f"{heading}\n\n{text}", cfg=cfg, with_metrics=False)
        live = api.live_rule_ids()
        off = len(heading) + 2
        plain = []
        for s in a.suggestions:
            if s.rule_id in live and s.start >= off:
                s.start -= off
                s.end -= off
                plain.append(_key(s))
        assert _live(text, heading, cfg) == plain


def test_many_paragraphs_in_one_call_match_one_at_a_time():
    cfg = _cfg()
    items = [{"id": f"p{i}", "text": t, "heading": h}
             for i, (h, t) in enumerate(PARAGRAPHS.items())]
    together = api.check_paragraphs(items, cfg=cfg)
    assert [p.id for p in together.paragraphs] == [i["id"] for i in items]
    for item, got in zip(items, together.paragraphs):
        alone = _live(item["text"], item["heading"], cfg)
        assert [_key(s) for s in got.suggestions] == alone, item["heading"]


def test_only_sentence_scope_rules_run():
    live = api.live_rule_ids()
    assert live and all(REGISTRY[r].scope == "sentence" for r in live)
    assert not {r.id for r in REGISTRY.values()
                if r.scope == "document"} & live
    res = api.check_paragraphs([{"id": "a", "text": t, "heading": h}
                                for h, t in PARAGRAPHS.items()],
                               cfg=_cfg())
    for p in res.paragraphs:
        assert {s.rule_id for s in p.suggestions} <= live
    assert set(res.assessed_rules) <= live


def test_sections_come_from_the_heading():
    res = api.check_paragraphs(
        [{"id": "m", "text": PARAGRAPHS["Methods"], "heading": "2.3 Statistical analysis"},
         {"id": "d", "text": PARAGRAPHS["Discussion"], "heading": "Discussion"},
         {"id": "n", "text": PARAGRAPHS["Discussion"]}],
        cfg=_cfg())
    sections = {p.id: p.section for p in res.paragraphs}
    assert sections["m"] == "methods"
    assert sections["d"] == "discussion"
    assert sections["n"] == "unknown"
    # Passive voice is never flagged in Methods; it may be elsewhere.
    m = res.paragraphs[0]
    assert all(s.section == "methods" for s in m.suggestions)


def test_unheaded_paragraphs_take_the_article_types_body_section():
    res = api.check_paragraphs([{"id": "c", "text": PARAGRAPHS[""]}],
                               cfg=_cfg(document_type="commentary"))
    assert res.paragraphs[0].section == "discussion"


def test_masked_material_is_never_flagged():
    text = ("We used the the model of (Smith et al., 2020) and $x = the the$ "
            "and `the the` from https://example.org/the-the-page.")
    res = api.check_paragraphs([{"id": "x", "text": text}], cfg=_cfg())
    spans = [(s.start, s.end, s.rule_id) for s in res.paragraphs[0].suggestions]
    for a, b, rid in spans:
        assert "$" not in text[a:b] and "`" not in text[a:b], rid
        assert "example.org" not in text[a:b], rid
        assert "Smith" not in text[a:b], rid


def test_a_heading_paragraph_and_a_blank_one_have_nothing_to_say():
    res = api.check_paragraphs(
        [{"id": "h", "text": "Methods and the the results", "style": "Heading 2"},
         {"id": "b", "text": "   "},
         {"id": "e", "text": ""}], cfg=_cfg())
    assert [p.suggestions for p in res.paragraphs] == [[], [], []]


def test_hidden_preferences_are_counted():
    text = "The effect was very large in every district."
    shown = api.check_paragraphs([{"id": "a", "text": text, "heading": "Results"}],
                                 cfg=_cfg())
    prefs = [s for s in shown.paragraphs[0].suggestions
             if s.category is Category.PREFERENCE]
    assert prefs, "the synthetic sentence should carry a preference"
    hidden = api.check_paragraphs([{"id": "a", "text": text, "heading": "Results"}],
                                  cfg=_cfg(show_preferences=False))
    assert hidden.hidden_preferences == len(prefs)
    assert not [s for s in hidden.paragraphs[0].suggestions
                if s.category is Category.PREFERENCE]


def test_muted_rules_stay_muted():
    text = PARAGRAPHS["Methods"]
    first = api.check_paragraphs([{"id": "a", "text": text, "heading": "Methods"}],
                                 cfg=_cfg())
    rid = first.paragraphs[0].suggestions[0].rule_id
    again = api.check_paragraphs([{"id": "a", "text": text, "heading": "Methods"}],
                                 cfg=_cfg(disabled={rid}))
    assert rid not in {s.rule_id for s in again.paragraphs[0].suggestions}
    assert rid not in again.assessed_rules


def test_the_grammar_request_starts_before_the_parse(monkeypatch):
    started = []
    real = rules_grammar.start_check

    def spy(document):
        started.append(document.masked)
        return real(document)

    monkeypatch.setattr(rules_grammar, "start_check", spy)
    nlp = api.get_nlp()

    class Probe:
        def pipe(self, texts):
            texts = list(texts)
            assert len(started) == len(texts) == 2   # all requests out first
            return nlp.pipe(texts)

        def __call__(self, text):
            return nlp(text)

    api.check_paragraphs([{"id": "a", "text": PARAGRAPHS["Methods"]},
                          {"id": "b", "text": PARAGRAPHS["Results"]}],
                         cfg=_cfg(), nlp=Probe())


# --- UTF-16 offsets ------------------------------------------------------------

def test_utf16_offsets_count_astral_characters_twice():
    text = "a\U0001F600b\U0001D445c"            # a😀b𝑅c
    idx = Utf16Index(text)
    assert [idx(i) for i in range(len(text) + 1)] == [0, 1, 3, 4, 6, 7]
    assert utf16_len(text) == len(text.encode("utf-16-le")) // 2 == 7
    assert to_utf16("plain", 3) == 3


def test_combining_marks_and_flags_follow_utf16():
    for text in ("café ok", "\U0001F1EC\U0001F1E7 flag",
                 "\U0001F469‍\U0001F52C team", "naïve"):
        idx = Utf16Index(text)
        for i in range(len(text) + 1):
            assert idx(i) == len(text[:i].encode("utf-16-le")) // 2


def _shaped(paragraphs, cfg):
    res = api.check_paragraphs(paragraphs, cfg=cfg)
    return res, shapes.live_paragraphs(res)


def test_live_suggestions_carry_utf16_ranges_over_the_flagged_words():
    text = ("\U0001F600 Our results proves the point. "
            "The café data was recieved \U0001D445 late.")
    res, shaped = _shaped([{"id": "p-1", "text": text}], _cfg())
    sugs = shaped[0]["suggestions"]
    assert sugs, "the synthetic paragraph should be flagged"
    units = text.encode("utf-16-le")
    for s in sugs:
        flagged = units[2 * s["begin"]:2 * s["end"]].decode("utf-16-le")
        assert flagged == s["text"]
        assert s["end"] > s["begin"] >= 0


def test_live_ids_are_stable_short_and_opaque():
    text = PARAGRAPHS["Methods"]
    para = [{"id": "para.7:a", "text": text, "heading": "Methods"}]
    _, first = _shaped(para, _cfg())
    _, second = _shaped(para, _cfg())
    ids = [s["id"] for s in first[0]["suggestions"]]
    assert ids == [s["id"] for s in second[0]["suggestions"]]
    assert len(set(ids)) == len(ids)
    for s in first[0]["suggestions"]:
        assert len(s["id"]) == 16 and int(s["id"], 16) >= 0
        assert s["text"] not in s["id"]
        assert s["id"] == live_id(s["rule_id"], "para.7:a", s["begin"],
                                  s["end"], s["text"])
    # Another paragraph id, another id.
    _, other = _shaped([dict(para[0], id="para.8")], _cfg())
    assert not set(ids) & {s["id"] for s in other[0]["suggestions"]}


def test_critical_means_correction():
    _, shaped = _shaped([{"id": "a", "text": t, "heading": h}
                         for h, t in PARAGRAPHS.items()], _cfg())
    seen = set()
    for p in shaped:
        for s in p["suggestions"]:
            assert s["critical"] is (s["category"] == "correction")
            seen.add(s["critical"])
            assert isinstance(s["replacements"], list)
    assert seen == {True, False}


# --- the latency budget ----------------------------------------------------------

# About 200 words of synthetic Methods prose with the usual slips.
BUDGET_PARAGRAPH = " ".join([PARAGRAPHS["Methods"], PARAGRAPHS["Results"],
                             PARAGRAPHS["Discussion"],
                             PARAGRAPHS["Limitations"], PARAGRAPHS["Abstract"]])


def _timings(cfg, runs=25):
    para = [{"id": "p", "text": BUDGET_PARAGRAPH, "heading": "Methods"}]
    api.check_paragraphs(para, cfg=cfg)          # warm
    api.check_paragraphs(para, cfg=cfg)
    out = []
    for _ in range(runs):
        t = time.perf_counter()
        api.check_paragraphs(para, cfg=cfg)
        out.append((time.perf_counter() - t) * 1000)
    out.sort()
    return statistics.median(out), out[int(0.95 * (len(out) - 1))]


def test_budget_paragraph_is_about_200_words():
    assert 180 <= len(BUDGET_PARAGRAPH.split()) <= 220


def test_latency_budget_without_grammar():
    p50, p95 = _timings(_cfg(grammar_tier=False))
    assert p50 < 300 and p95 < 800, (p50, p95)


def test_latency_budget_with_grammar():
    if not rules_grammar.available():
        state, _ = rules_grammar.state()
        pytest.skip("the grammar tier (LanguageTool) is not available here "
                    f"({state}); the budget without grammar is pinned above")
    p50, p95 = _timings(_cfg())
    assert p50 < 300 and p95 < 800, (p50, p95)

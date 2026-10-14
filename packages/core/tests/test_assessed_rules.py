"""Which rules a check could show (Codex review N2, 2026-10-14): the
progress view must tell "not assessed" from "zero findings". Synthetic
text only."""

from researchly import api
from researchly.engine import REGISTRY, Category

TEXT = "Discussion\n\nThese results may suggest that transmission declined.\n"


def assessed(**kw):
    return set(api.analyze(TEXT, with_metrics=False, **kw).assessed_rules)


def test_a_muted_rule_is_not_assessed():
    assert "C303" in assessed()
    assert "C303" not in assessed(disabled={"C303"})


def test_hidden_preferences_are_not_assessed():
    prefs = {r.id for r in REGISTRY.values()
             if r.category is Category.PREFERENCE}
    assert prefs and not prefs & assessed()
    assert prefs <= assessed(show_preferences=True) | {
        r for r in prefs if REGISTRY[r].tier in ("grammar", "gec")}


def test_draft_holds_back_the_document_rules():
    revise, draft = assessed(), assessed(mode="draft")
    held = revise - draft
    assert held and all(api._scope(r) == "document" for r in held)


def test_a_rule_off_for_the_article_type_is_not_assessed():
    a = api.analyze("Introduction\n\nWe argue a point.\n",
                    document_type="commentary", with_metrics=False)
    assert not set(a.profile.rules_off) & set(a.assessed_rules)


def test_a_tier_that_is_down_is_not_assessed():
    assert "LT001" not in assessed(grammar_tier=False)


def test_the_ruleset_names_the_version_and_is_stable():
    a = api.analyze(TEXT, with_metrics=False)
    b = api.analyze("Methods\n\nWe fitted a model.\n", with_metrics=False)
    assert a.ruleset == b.ruleset and "+" in a.ruleset
    assert a.to_dict()["assessed_rules"] == a.assessed_rules

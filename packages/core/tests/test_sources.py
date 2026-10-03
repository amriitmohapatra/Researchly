"""Every suggestion must name a source a student could look up (CLAUDE.md #6).

The S1 end-to-end run against the real engine showed cards whose source read
only "§4" or "§8" — internal shorthand for sections of the founding guide,
meaningless to anyone else. Rules keep their short codes; the registry
expands them into full citations through researchly/sources.py.
"""

import re

import pytest

from researchly import api, sources
from researchly.engine import REGISTRY


@pytest.fixture(scope="module", autouse=True)
def _rules():
    api.ensure_rules_loaded()


def test_every_rule_source_is_a_full_citation():
    for r in REGISTRY.values():
        assert not re.fullmatch(r"[§\w.+\- ]{1,12}", r.source), (r.id, r.source)
        assert len(r.source) >= 15, (r.id, r.source)


def test_guide_sections_are_named_not_just_numbered():
    cited = sources.cite("§4")
    assert "The Craft of Scientific Writing" in cited
    assert "§4" in cited and "Warranting" in cited


def test_composite_codes_cite_every_part():
    cited = sources.cite("§6+Endo")
    assert "The Craft of Scientific Writing" in cited and "Endo" in cited


def test_unknown_code_fails_loudly():
    with pytest.raises(KeyError):
        sources.cite("§99")


def test_suggestions_carry_the_expanded_citation():
    a = api.analyze("Discussion\n\nIt is clearly proven that this works.",
                    kind="plain")
    hits = [s for s in a.suggestions if s.rule_id in ("C302", "C301", "C305")]
    assert hits and all("The Craft of Scientific Writing" in s.source for s in hits)

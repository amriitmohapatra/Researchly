"""British or American: the spelling setting, W213, and a smarter W210.

2026-10-14, after the owner asked that Researchly "detect" UK and US
spelling and let the writer choose one. The variant data is VarCon
(data/variants.tsv, ml/tools/build_variants.py). Synthetic text only.
"""

from researchly import api, config, spelling


TEXT = ("We analysed the colour of the samples in the centre. The "
        "organisation of the behaviour data used a meter and a computer "
        "program. The color scale followed the Centers for Disease "
        "Control guidance.")


def cards(text, rule, **overrides):
    a = api.analyze(text, disabled={"LT001"}, **overrides)
    return [(s.text, s.replacement) for s in a.suggestions
            if s.rule_id == rule]


# --- the data ----------------------------------------------------------------

def test_dialect_spelling_respects_senses():
    assert spelling.dialect_spelling("color", "uk") == "colour"
    assert spelling.dialect_spelling("colour", "us") == "color"
    assert spelling.dialect_spelling("organise", "uk-oxford") == "organize"
    # British English writes these too, in another sense
    assert spelling.dialect_spelling("meter", "uk") is None   # the device
    assert spelling.dialect_spelling("program", "uk") is None  # software
    assert spelling.dialect_spelling("tire", "uk") is None    # to fatigue
    # Oxford spelling keeps -yse
    assert spelling.dialect_spelling("analyse", "uk-oxford") is None


def test_detection_counts_only_telling_words():
    words = "the colour of the centre and the behaviour of the data".split()
    assert spelling.detect_dialect(words)[0] == "uk"
    assert spelling.detect_dialect("the data were collected".split()) == (
        None, 0, 0)


# --- the setting ---------------------------------------------------------------

def test_spelling_setting_reads_from_toml(tmp_path):
    (tmp_path / ".researchly.toml").write_text(
        '[document]\nspelling = "uk"\n', encoding="utf-8")
    cfg = config.load(tmp_path / "paper.md")
    assert cfg.spelling == "uk"
    assert 'spelling = "uk"' in config.dumps(cfg)


def test_unknown_spelling_value_is_ignored(tmp_path):
    (tmp_path / ".researchly.toml").write_text(
        '[document]\nspelling = "klingon"\n', encoding="utf-8")
    assert config.load(tmp_path / "paper.md").spelling == "auto"


# --- W213: a chosen dialect --------------------------------------------------

def test_british_choice_flags_the_american_spelling():
    assert cards(TEXT, "W213", spelling="uk") == [("color", "colour")]


def test_american_choice_flags_every_british_spelling():
    got = dict(cards(TEXT, "W213", spelling="us"))
    assert got == {"analysed": "analyzed", "colour": "color",
                   "centre": "center", "organisation": "organization",
                   "behaviour": "behavior"}


def test_oxford_choice_wants_ize_but_keeps_british_words():
    got = dict(cards(TEXT, "W213", spelling="uk-oxford"))
    assert got == {"organisation": "organization", "color": "colour"}


def test_names_are_not_respelt():
    # "Centers for Disease Control" is a US agency's name
    assert all(t != "Centers" for t, _ in cards(TEXT, "W213",
                                                  spelling="uk"))


def test_auto_runs_no_w213():
    assert cards(TEXT, "W213") == []


# --- W210: mixtures, resolved by the document's own dialect --------------------

def test_mixture_follows_the_documents_dialect():
    a = api.analyze(TEXT, disabled={"LT001"})
    w210 = [s for s in a.suggestions if s.rule_id == "W210"]
    assert [(s.text, s.replacement) for s in w210] == [("color", "colour")]
    assert "mostly uses British spelling" in w210[0].message


def test_a_chosen_dialect_replaces_w210():
    assert cards(TEXT, "W210", spelling="uk") == []


def test_us_plural_analyses_is_not_a_mixture():
    # "analyses" is also the plural of "analysis" in US English; the old
    # hand-made pair analyses/analyzes would have flagged this.
    text = ("The model analyzes weekly counts. Two sensitivity analyses "
            "were run.")
    assert cards(text, "W210") == []

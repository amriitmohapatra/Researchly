"""S2b structural checks: figures, tables and the text that cites them.

Synthetic documents only (CLAUDE.md). Every don't-fire case here is a
pattern a real manuscript on the real-document bench used (P32).
"""

import pytest

from researchly import api
from researchly.document import Document

NLP = api.get_nlp()


def tex(body: str, preamble: str = "") -> Document:
    return Document.from_text(
        "\\documentclass{article}\n" + preamble +
        "\\begin{document}\n\\section{Results}\n" + body +
        "\n\\end{document}\n", "latex")


def fig(label: str, caption: str = "Weekly cases in every district of "
        "the city.") -> str:
    return (f"\\begin{{figure}}\\centering\\includegraphics{{x}}"
            f"\\caption{{{caption}}}\\label{{{label}}}\\end{{figure}}\n")


def table(label: str, caption: str = "Cases by age group and district.",
          rows: str = "a & 1 \\\\") -> str:
    return (f"\\begin{{table}}\\caption{{{caption}}}\\label{{{label}}}"
            f"\\begin{{tabular}}{{ll}}{rows}\\end{{tabular}}\\end{{table}}\n")


def word(*paras) -> Document:
    out = [{"text": "Results", "style": "Heading 1"}]
    for p in paras:
        out.append(p if isinstance(p, dict) else {"text": p})
    return Document.from_word(out)


def cap(text: str) -> dict:
    return {"text": text, "style": "Caption"}


def hits(doc: Document, rule_id: str):
    return [s for s in api.analyze(doc, nlp=NLP,
                                   show_preferences=True).suggestions
            if s.rule_id == rule_id]


# --- X101: never cited -----------------------------------------------------------

def test_x101_fires_on_an_uncited_figure():
    doc = tex("Cases rose (Figure~\\ref{fig:a}).\n" + fig("fig:a") +
              fig("fig:b", "Age distribution of all reported cases."))
    (h,) = hits(doc, "X101")
    assert "Figure 2" in h.message and h.text.startswith("Age distribution")


@pytest.mark.parametrize("doc", [
    # \ref, \cref with two keys, and a written "Figure 2"
    tex("See Figure~\\ref{fig:a} and \\cref{fig:b}.\n" + fig("fig:a") +
        fig("fig:b")),
    tex("See \\cref{fig:a,fig:b}.\n" + fig("fig:a") + fig("fig:b")),
    tex("See Figure~\\ref{fig:a} and Figure 2.\n" + fig("fig:a") +
        fig("fig:b")),
    # a preamble macro that adds the label prefix out of sight
    tex("See \\fig{a} and \\fig{b}.\n" + fig("fig:a") + fig("fig:b"),
        "\\newcommand{\\fig}[1]{Figure~\\ref{fig:#1}}\n"),
    # a style's \figref the project never defines
    tex("See \\figref{fig:a} and \\figref{fig:b}.\n" + fig("fig:a") +
        fig("fig:b")),
    # a range cites everything between
    tex("Figures~\\ref{fig:a}--\\ref{fig:c} show it.\n" + fig("fig:a") +
        fig("fig:b") + fig("fig:c")),
    # cited only from another float's caption
    tex("See Figure~\\ref{fig:a}.\n" + fig("fig:a", "Weekly cases; the "
        "counts are in Table~\\ref{tab:a}.") + table("tab:a")),
])
def test_x101_quiet_when_every_float_is_cited(doc):
    assert hits(doc, "X101") == []


def test_x101_own_caption_does_not_count():
    doc = tex("Cases rose.\n" + fig("fig:a", "Weekly cases (this is "
                                    "Figure~\\ref{fig:a})."))
    assert len(hits(doc, "X101")) == 1


def test_x101_unnumbered_and_panel_captions_are_not_floats():
    doc = tex("See Figure~\\ref{fig:a}.\n"
              "\\begin{figure}\\begin{minipage}{.5\\linewidth}"
              "\\caption*{(a)}\\end{minipage}"
              "\\caption{Weekly cases in every district.}\\label{fig:a}"
              "\\end{figure}\n")
    assert hits(doc, "X101") == []


def test_x101_captionof_is_its_own_float():
    doc = tex("See Figure~\\ref{fig:a}.\n"
              "\\begin{table}\\begin{minipage}{.5\\linewidth}"
              "\\captionof{figure}{Weekly cases in every district.}"
              "\\label{fig:a}\\end{minipage}\\end{table}\n",
              "\\usepackage{caption}\n")
    assert hits(doc, "X101") == []


def test_x101_word():
    doc = word("Cases rose (Figure 1).", cap("Figure 1. Weekly cases."),
               cap("Figure 2. Age distribution of all cases."))
    (h,) = hits(doc, "X101")
    assert "Figure 2" in h.message


# --- X102: cited out of order ------------------------------------------------------

def test_x102_fires_when_figure_2_is_cited_first():
    doc = tex("First Figure~\\ref{fig:b}, then Figure~\\ref{fig:a}.\n" +
              fig("fig:a") + fig("fig:b"))
    (h,) = hits(doc, "X102")
    assert "Figure 1 is first cited after Figure 2" in h.message
    assert h.text == "Figure"            # the word, not the masked \ref


@pytest.mark.parametrize("doc", [
    tex("First Figure~\\ref{fig:a}, then Figure~\\ref{fig:b}, then "
        "Figure~\\ref{fig:a} again.\n" + fig("fig:a") + fig("fig:b")),
    # an appendix figure may be cited from anywhere
    tex("See Figure~\\ref{fig:s} and Figure~\\ref{fig:a}.\n" + fig("fig:a") +
        "\\appendix\n\\section{Extra}\n" + fig("fig:s")),
    tex("Figures~\\ref{fig:a}--\\ref{fig:c} show it.\n" + fig("fig:a") +
        fig("fig:b") + fig("fig:c")),
])
def test_x102_quiet_in_order(doc):
    assert hits(doc, "X102") == []


def test_x102_word_and_supplementary():
    doc = word("See Table 2, Table S1 and Table 1.",
               cap("Table 1. Cases by age."), {"text": "a", "kind": "table"},
               cap("Table 2. Deaths by age."), {"text": "b", "kind": "table"})
    (h,) = hits(doc, "X102")
    assert "Table 1" in h.message


# --- X103: broken cross-references ---------------------------------------------------

def test_x103_fires_on_an_undefined_label():
    doc = tex("See Figure~\\ref{fig:missing}.\n" + fig("fig:a") +
              "Also Figure~\\ref{fig:a}.")
    (h,) = hits(doc, "X103")
    assert "fig:missing" in h.message


@pytest.mark.parametrize("body", [
    # labels in an align, an algorithm, a section: all defined
    "\\begin{align}x &= 1 \\label{eq:x}\\end{align} By \\eqref{eq:x}.",
    "\\begin{algorithm}\\caption{Fit}\\label{alg:fit}\\end{algorithm} "
    "See Algorithm~\\ref{alg:fit}.",
    "\\subsection{Data}\\label{sec:data} See Section~\\ref{sec:data}.",
])
def test_x103_quiet_on_defined_labels(body):
    assert hits(tex(body), "X103") == []


def test_x103_commented_label_does_not_define():
    doc = tex("See Figure~\\ref{fig:gone}.\n% \\label{fig:gone}\n")
    assert len(hits(doc, "X103")) == 1


def test_x103_word_number_with_no_figure():
    doc = word("Cases rose (Figure 1); deaths too (Figure 4).",
               cap("Figure 1. Weekly cases."))
    (h,) = hits(doc, "X103")
    assert "Figure 4" in h.message


@pytest.mark.parametrize("text", [
    "Cases rose (Figure 1), as in Figure 3 of Zqlee et al.",
    "Cases rose (Figure 1); see Figure S3 for deaths.",
])
def test_x103_word_quiet_on_other_papers_and_supplements(text):
    assert hits(word(text, cap("Figure 1. Weekly cases.")), "X103") == []


# --- X104: before its first citation (Word only) --------------------------------------

def test_x104_fires_when_the_figure_comes_first():
    doc = word(cap("Figure 1. Weekly cases."), "Cases rose (Figure 1).")
    (h,) = hits(doc, "X104")
    assert "Figure 1" in h.message


def test_x104_quiet_after_the_citation_and_in_latex():
    assert hits(word("Cases rose (Figure 1).", cap("Figure 1. Weekly "
                                                    "cases.")), "X104") == []
    assert hits(tex(fig("fig:a") + "Cases rose (Figure~\\ref{fig:a})."),
                "X104") == []


# --- surfaces ----------------------------------------------------------------------------

def test_plain_text_gets_no_structural_checks():
    doc = Document.from_text("Results\n\nSee Figure 4 and Table 9.\n\n"
                             "Figure 1. Weekly cases.\n")
    assert not [s for s in api.analyze(doc, nlp=NLP).suggestions
                if s.rule_id.startswith("X")]


def test_every_rule_module_is_loaded():
    # api.ensure_rules_loaded() kept its own list of modules and missed
    # rules_structure: /v1/health reported 38 rules with 42 registered.
    import importlib
    import pathlib
    import sys
    from researchly.engine import REGISTRY, load_rules
    load_rules()
    pkg = pathlib.Path(importlib.import_module("researchly").__file__).parent
    for path in pkg.glob("rules_*.py"):
        assert f"researchly.{path.stem}" in sys.modules, path.stem
    assert api.ensure_rules_loaded() == len(REGISTRY)

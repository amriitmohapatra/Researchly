"""Pasted code, inline maths and other languages in plain text and Word
(2026-10-14; Codex review #5, the English-only notice). All text below is
synthetic: invented code and sentences written for these tests.
"""

import pytest

from researchly import api, reading
from researchly.document import Document


# --- code ------------------------------------------------------------------

@pytest.mark.parametrize("line", [
    "fit <- glm(cases ~ week, family = poisson)",
    "library(rstan)",
    "import numpy as np",
    "from scipy import stats",
    "def simulate(beta, gamma):",
    "for (i in 1:n) {",
    "}",
    "model {",
    "real<lower=0> sigma;",
    "summary(fit)",
    "out = run_model(pars, data = d)",
    "cases %>%",
    "#> [1] 0.42",
    ">>> np.mean(x)",
])
def test_code_lines_are_masked(line):
    assert reading.code_spans(line) == [(0, len(line))]


@pytest.mark.parametrize("line", [
    "We used three models (A, B and C);",
    "Results (Table 2)",
    "The model was fitted in R with the rstan package (version 2.32).",
    "Figure 2 shows the fit (black line);",
    "Methods (continued)",
    "If transmission (as measured by Rt) fell, cases fell too.",
    "for each region (n = 12), we fitted a separate model and compared the "
    "estimates (Table 3).",
])
def test_prose_lines_are_not_code(line):
    assert reading.code_spans(line) == []


def test_fenced_block_is_masked_whole():
    text = "Intro text.\n```\nx = 1\ny equals two in words\n```\nMore text."
    (a, b), = reading.code_spans(text)
    assert text[a:b].startswith("```") and text[a:b].endswith("```")


# --- inline maths ----------------------------------------------------------------

@pytest.mark.parametrize("text,hit", [
    ("The slope $\\beta_1$ was positive.", "$\\beta_1$"),
    ("We set $x^2 + y^2$ to one.", "$x^2 + y^2$"),
    ("with rate \\(\\lambda\\) per day", "\\(\\lambda\\)"),
    ("Call `fit_model()` first.", "`fit_model()`"),
])
def test_inline_maths_and_code_are_masked(text, hit):
    assert [text[a:b] for a, b in reading.inline_spans(text)] == [hit]


def test_prices_are_not_maths():
    assert reading.inline_spans("Doses cost $5 to $10 each.") == []


# --- languages -----------------------------------------------------------------

PT = ("Os resultados mostram que a vacinação reduziu a transmissão entre os "
      "grupos mais vulneráveis e que o efeito foi maior nas crianças.")
ES = ("Los resultados muestran que la vacunación redujo la transmisión entre "
      "los grupos más vulnerables y que el efecto fue mayor en los niños.")
FR = ("Les résultats montrent que la vaccination a réduit la transmission "
      "dans les groupes les plus vulnérables et que cet effet est plus fort.")
DE = ("Die Ergebnisse zeigen, dass die Impfung die Übertragung zwischen den "
      "Gruppen verringert hat und dass der Effekt bei Kindern größer ist.")
EN = ("The results show that vaccination reduced transmission between the "
      "most vulnerable groups and that the effect was larger in children.")


@pytest.mark.parametrize("text,lang", [
    (PT, "Portuguese"), (ES, "Spanish"), (FR, "French"), (DE, "German"),
    ("新型疫苗在儿童中的效果更好，传播率明显下降，研究结果表明接种疫苗"
     "可以降低感染风险并保护脆弱人群的健康。", "another script"),
])
def test_other_languages_are_named(text, lang):
    assert reading.paragraph_language(text) == lang


@pytest.mark.parametrize("text", [
    EN,
    "Smith et al. reported the same; Jones et al. did not (see also van "
    "der Berg et al. and de la Cruz et al. for the cohort data).",
    "Short line.",
])
def test_english_is_english(text):
    assert reading.paragraph_language(text) is None


def test_a_foreign_paragraph_is_masked_and_noted():
    text = EN + "\n\n" + PT + "\n"
    doc = Document.from_text(text, "plain")
    start = text.index(PT)
    assert doc.masked[start:start + len(PT)].strip() == ""
    assert doc.read.get("other_language") == 1
    assert any("not in English (Portuguese)" in w for w in doc.warnings)


def test_a_whole_text_in_another_language_says_so():
    doc = Document.from_text(PT + "\n\n" + PT + "\n", "plain")
    assert any("does not look like English" in w for w in doc.warnings)


def test_pasted_code_raises_no_spelling_flags():
    text = ("We fitted the model in R.\n\n"
            "fitt <- glmmTMB(casez ~ weeek, famly = nbinom2)\n"
            "summary(fitt)\n\n"
            "The estimates are shown below.\n")
    a = api.analyze(text, disabled={"LT001"})
    flagged = {s.text for s in a.suggestions}
    assert not flagged & {"fitt", "casez", "weeek", "famly", "glmmTMB"}
    assert a.document.read.get("code") == 2

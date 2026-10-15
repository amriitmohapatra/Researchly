"""Evidence-linked brief and map (Codex review #3, 2026-10-15): every
point that rests on a sentence carries the sentence's place, a claim
carries the evidence proposed beside it, and what cannot be placed
abstains. Synthetic text only.
"""

from researchly import api, evidence, shapes, wordloc
from researchly.document import Document
from researchly.ingest import load_bytes
from ingest_fixtures import zip_bytes

NLP = api.get_nlp()

# Emoji before and inside the claims: every offset after them differs
# between code points and UTF-16.
PAPER = (
    "Introduction\n\n"
    "Dengue \U0001F99F remains a leading cause of admission in Oldmere. "
    "Little is known about transmission in the dry season.\n\n"
    "Methods\n\n"
    "We fitted a renewal model to weekly counts from three districts.\n\n"
    "Results\n\n"
    "Cases fell by 40% (95% CI 31 to 48) after spraying.\n\n"
    "Discussion\n\n"
    "Admissions fell by 35% in the treated districts (Table 2). "
    "Spraying caused the fall in admissions \U0001F4C9. "
    "Rain reduced the vector population in the north. "
    "This proves that spraying works. "
    "Vector control policy should change.\n")


def analyze(text, **kw):
    return api.analyze(text, nlp=NLP, with_review=True, with_narrative=True,
                       **kw)


def links_of(a, qid):
    q = next(q for q in a.review["questions"] if q["id"] == qid)
    return q["links"]


def utf16(text, a, b):
    raw = text.encode("utf-16-le")
    return raw[2 * a:2 * b].decode("utf-16-le")


def same(quoted, original):
    """A quote is the original sentence on one line, maybe shortened."""
    flat = " ".join(original.split())
    return flat == quoted or (quoted.endswith("\u2026")
                              and flat.startswith(quoted[:-1]))


# --- the brief ------------------------------------------------------------------

def test_every_link_points_at_the_sentence_it_quotes():
    a = analyze(PAPER)
    shaped = shapes.extras(a)["review"]
    n = 0
    for q in shaped["questions"]:
        for link in q["links"]:
            for span in (link["claim"], link["evidence"]):
                if span is None:
                    continue
                n += 1
                text = PAPER[span["start"]:span["end"]]
                assert same(span["text"], text), (span, text)
                # UTF-16 offsets select the same words, emoji included.
                assert utf16(PAPER, span["begin16"], span["end16"]) == text
    assert n >= 5


def test_a_causal_claim_sits_beside_its_nearest_evidence():
    a = analyze(PAPER)
    (claim,) = [x for x in links_of(a, "C") if x["kind"] == "causal_claim"
                and "Spraying caused" in x["claim"]["text"]]
    assert claim["evidence_status"] == "detected"
    assert claim["evidence"]["text"].startswith("Admissions fell by 35%")
    assert claim["evidence_note"]


def test_evidence_in_the_claims_own_sentence():
    text = PAPER.replace("Spraying caused the fall in admissions \U0001F4C9.",
                         "Spraying caused a 35% fall in admissions.")
    a = analyze(text)
    (claim,) = [x for x in links_of(a, "C") if "Spraying caused" in
                x["claim"]["text"]]
    assert claim["evidence_status"] == "detected"
    assert claim["evidence"] == claim["claim"]


def test_no_evidence_nearby_abstains_from_a_link():
    text = ("Introduction\n\nLittle is known about Oldmere.\n\nDiscussion\n\n"
            "We worked hard on this question for many months. "
            "Our team met every week to plan the work. "
            "The weather was poor all summer long. "
            "Spraying caused the fall in admissions. "
            "We thank the district teams for their help.\n")
    a = analyze(text)
    (claim,) = [x for x in links_of(a, "C") if x["kind"] == "causal_claim"]
    assert claim["evidence_status"] == "not_detected"
    assert claim["evidence"] is None            # never a fabricated link
    assert "No number" in claim["evidence_note"]


def test_evidence_never_crosses_a_section():
    # The number is in the Results, the claim opens the Discussion.
    text = ("Results\n\nCases fell by 40% after spraying.\n\nDiscussion\n\n"
            "Spraying caused the fall in cases.\n")
    a = analyze(text)
    (claim,) = [x for x in links_of(a, "C") if x["kind"] == "causal_claim"]
    assert claim["evidence_status"] == "not_detected"


def test_a_muted_check_has_no_links():
    a = analyze(PAPER, disabled=["C303"])
    q = next(q for q in a.review["questions"] if q["id"] == "C")
    assert q["status"] == "not_assessed" and q["links"] == []


def test_points_about_the_whole_document_carry_no_link():
    a = analyze(PAPER)
    kinds = {x["kind"] for q in a.review["questions"] for x in q["links"]}
    # "No limitations section" and the calibration read-out are about the
    # whole text: nothing to place.
    assert "limitations" not in kinds and "calibration" not in kinds
    assert {"gap", "causal_claim", "overclaim"} <= kinds


def test_a_quote_the_text_does_not_hold_is_not_placed():
    doc = Document.from_text(PAPER)
    sents = evidence.Sentences(doc, NLP(doc.masked))
    assert sents.find("A sentence that is not in the text.") is None
    assert sents.find("   ") is None
    found = sents.find("Rain reduced the vector")
    assert found["text"].startswith("Rain reduced the vector population")


def test_the_brief_keeps_its_quoted_evidence_for_older_clients():
    a = analyze(PAPER)
    d = next(q for q in a.review["questions"] if q["id"] == "D")
    assert d["evidence"] and d["links"]


# --- the map --------------------------------------------------------------------

def test_present_moves_and_missing_links_are_placed():
    a = analyze(PAPER)
    n = shapes.extras(a)["narrative"]
    placed = [m for s in n["sections"] for m in s["moves"] if m["span"]]
    assert placed
    for m in placed:
        sp = m["span"]
        assert same(sp["text"], PAPER[sp["start"]:sp["end"]])
        assert m["evidence"] and sp["text"][:20] == m["evidence"][:20]
    assert all(m["span"] is None for s in n["sections"] for m in s["moves"]
               if m["status"] == "not_detected")
    spans = [sp for link in n["missing_links"] for sp in link["spans"]]
    assert spans and all(same(sp["text"], PAPER[sp["start"]:sp["end"]])
                         for sp in spans)


# --- multi-file and Word --------------------------------------------------------

MAIN = ("\\documentclass{article}\n\\begin{document}\n"
        "\\input{sections/results}\n\\input{sections/discussion}\n"
        "\\end{document}\n")
RESULTS = ("\\section{Results}\n"
           "Cases fell by 40\\% after spraying \\cite{k1}.\n")
DISCUSSION = ("\\section{Discussion}\n"
              "Admissions fell by a third in the treated districts "
              "(Table 2).\n"
              "Spraying caused the fall in admissions.\n"
              "This proves that spraying works.\n")


def test_an_overleaf_project_names_the_file_and_line():
    doc = load_bytes("project.zip", zip_bytes({
        "main.tex": MAIN, "sections/results.tex": RESULTS,
        "sections/discussion.tex": DISCUSSION}))
    a = api.analyze(doc, nlp=NLP, with_review=True)
    shaped = shapes.extras(a)["review"]
    links = [x for q in shaped["questions"] for x in q["links"]]
    (claim,) = [x for x in links if x["kind"] == "causal_claim"]
    span = claim["claim"]
    assert span["file"] == "sections/discussion.tex"
    assert span["file_line"] == 3
    assert DISCUSSION.splitlines()[2].startswith(
        doc.original[span["start"]:span["end"]])
    assert claim["evidence"]["file"] == "sections/discussion.tex"
    assert claim["evidence"]["file_line"] == 2


def test_a_single_file_has_no_file_name():
    a = analyze(PAPER)
    spans = [x["claim"] for q in shapes.extras(a)["review"]["questions"]
             for x in q["links"]]
    assert spans and all("file" not in sp for sp in spans)


def test_word_selects_the_sentence_in_its_paragraph():
    paras = [{"text": "Discussion", "style": "Heading 1"},
             {"text": "Admissions \U0001F4C9 fell by 35% in the treated "
                      "districts (Table 2). Spraying caused the fall in "
                      "admissions. This proves that spraying works."}]
    a = api.analyze(paras, nlp=NLP, with_review=True, with_narrative=True)
    doc = a.document
    ex = shapes.extras(a, locate=wordloc.locator(doc, paras))
    links = [x for q in ex["review"]["questions"] for x in q["links"]]
    (claim,) = [x for x in links if x["kind"] == "causal_claim"]
    loc = claim["claim"]["location"]
    text = paras[loc["paragraph"]]["text"]
    assert loc["paragraph"] == 1 and loc["exact"]
    assert text[loc["start"]:loc["end"]] == "Spraying caused the fall in admissions."
    assert loc["snippet"] == text[loc["start"]:loc["end"]]
    assert utf16(text, loc["begin16"], loc["end16"]) == loc["snippet"]
    assert loc["begin16"] == loc["start"] + 1          # the emoji before it
    ev = claim["evidence"]["location"]
    assert ev["paragraph"] == 1 and ev["start"] == 0

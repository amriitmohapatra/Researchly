"""The coverage summary (Codex review #5): what was read, set aside and
left out, and the main .tex file of an ambiguous Overleaf project.

Every document is synthetic, built in memory (ingest_fixtures). The summary
carries counts and fixed labels only: a test checks that no word of the
documents' own text reaches it.
"""

import json

import pytest

from researchly import api, cli, shapes
from researchly.document import Document
from researchly.ingest import IngestError, load_bytes
from ingest_fixtures import W, docx_bytes, para, run, zip_bytes

SECRET = "Zqhidden"     # in the documents' text, never in a summary

WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"


def footnote_ref(n: int) -> str:
    return f'<w:r><w:footnoteReference w:id="{n}"/></w:r>'


def endnote_ref(n: int) -> str:
    return f'<w:r><w:endnoteReference w:id="{n}"/></w:r>'


def comment(n: int) -> str:
    return (f'<w:commentRangeStart w:id="{n}"/>{run("commented words")}'
            f'<w:commentRangeEnd w:id="{n}"/>'
            f'<w:r><w:commentReference w:id="{n}"/></w:r>')


def text_box(words: str) -> str:
    """A text box as Word writes it: once as a drawing, once as the
    fallback picture for older readers."""
    inner = (f'<w:txbxContent><w:p>{run(words)}</w:p></w:txbxContent>')
    return ('<w:r><mc:AlternateContent>'
            f'<mc:Choice Requires="wps"><w:drawing>{inner}</w:drawing>'
            '</mc:Choice>'
            f'<mc:Fallback><w:pict><v:textbox xmlns:v="urn:v">{inner}'
            '</v:textbox></w:pict></mc:Fallback>'
            '</mc:AlternateContent></w:r>')


def part(kind: str, *texts: str) -> str:
    body = "".join(f"<w:p>{run(t)}</w:p>" for t in texts)
    return (f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<w:{kind} xmlns:w="{W}">{body}</w:{kind}>')


NOTES = part("footnotes", f"A note about {SECRET} that nobody checks.")


def rich_docx() -> bytes:
    body = (
        para("Methods", style="berschrift1")
        + para("We fitted a renewal model to weekly counts.",
               footnote_ref(2), " The priors were weak.", footnote_ref(3))
        + para("Discussion", style="berschrift1")
        + para("The estimates were stable.", endnote_ref(1), comment(0))
        + para(text_box(f"Box words about {SECRET} here."),
               "A caption-like line beside the box.")
        + para(text_box("   "))                  # an empty box: not counted
        + para("The same note again.", footnote_ref(2)))  # cited twice
    return docx_bytes(body, extra={
        "word/footnotes.xml": NOTES,
        "word/header1.xml": part("hdr", f"Running head {SECRET}"),
        "word/header2.xml": part("hdr", ""),          # empty: not counted
        "word/footer1.xml": part("ftr", "12"),        # a page number only
        "word/footer2.xml": part("ftr", "Draft for the committee"),
    })


# --- .docx: what was not read ------------------------------------------------

def test_docx_counts_what_it_does_not_read():
    doc = load_bytes("chapter.docx", rich_docx())
    assert doc.not_checked == {"footnotes": 2, "endnotes": 1, "comments": 1,
                               "text_boxes": 1, "headers_footers": 2}
    # none of it was read as text
    assert SECRET not in doc.original
    assert "Running head" not in doc.original


def test_docx_summary_and_sentence():
    a = api.analyze(load_bytes("chapter.docx", rich_docx()))
    summary = shapes.reading_summary(a.document)
    kinds = {i["kind"]: i["count"] for i in summary["not_checked"]}
    assert kinds == {"footnotes": 2, "endnotes": 1, "comments": 1,
                     "text_boxes": 1, "headers_footers": 2}
    line = shapes.reading_sentence(summary)
    assert ("Not checked: 2 footnotes · 1 endnote · 1 comment · 1 text box "
            "· 2 headers or footers.") in line
    assert line.startswith("Checked ")
    # counts and fixed labels only: no document text
    assert SECRET not in json.dumps(summary) and SECRET not in line


def test_a_plain_docx_says_nothing_is_left_out():
    doc = load_bytes("plain.docx", docx_bytes(para("Just one sentence.")))
    assert doc.not_checked == {}
    summary = shapes.reading_summary(doc)
    assert summary["not_checked"] == [] and summary["included"] == []
    assert "Not checked" not in shapes.reading_sentence(summary)


def test_a_damaged_header_is_not_counted_and_sinks_nothing():
    data = docx_bytes(para("A sentence."), extra={
        "word/header1.xml": "<w:hdr not xml"})
    doc = load_bytes("x.docx", data)
    assert doc.not_checked == {}


# --- LaTeX: footnotes are read where they are cited -----------------------------

TEX = ("\\documentclass{article}\n\\begin{document}\n"
       "\\section{Methods}\n"
       "We fitted a renewal model.\\footnote{Weekly counts were used.} "
       "The priors were weak.\\footnote{See the appendix.}\n"
       "% \\footnote{an old note}\n"
       "\\end{document}\n")


def test_latex_footnotes_are_read_and_said_to_be():
    doc = Document.from_text(TEX, "latex")
    assert doc.included == {"footnotes": 2}
    assert "Weekly counts were used" in doc.masked     # read as prose
    line = shapes.reading_sentence(shapes.reading_summary(doc))
    assert ", including 2 footnotes." in line
    assert "Not checked" not in line


def test_the_simpler_latex_reader_counts_footnotes_too(monkeypatch):
    from researchly.ingest import latex
    monkeypatch.setattr(latex, "_Masker", None)        # parser unavailable
    doc = Document.from_text(TEX, "latex")
    assert doc.included == {"footnotes": 2}


def test_no_footnotes_no_mention():
    doc = Document.from_text("\\begin{document}Plain prose.\\end{document}",
                             "latex")
    assert doc.included == {}
    assert "including" not in shapes.reading_sentence(
        shapes.reading_summary(doc))


# --- English only ------------------------------------------------------------------

def test_the_english_only_notice_is_part_of_the_line():
    text = ("We fitted a renewal model to weekly counts of cases.\n\n"
            "Los datos de los casos fueron recogidos por las autoridades de "
            "salud de la provincia durante el año y luego fueron analizados "
            "con un modelo.\n")
    summary = shapes.reading_summary(Document.from_text(text))
    line = shapes.reading_sentence(summary)
    assert "Set aside: 1 paragraph not in English." in line
    assert line.endswith("Researchly checks English only.")


# --- Overleaf: skipped inputs and the main file ----------------------------------------

ROOT = ("\\documentclass{article}\n\\begin{document}\n"
        "Paper words.\\input{missing}\\input{old}\n\\end{document}\n")
LETTER = ("\\documentclass{letter}\n\\begin{document}\n"
          "Dear editor, we resubmit.\n\\end{document}\n")


def test_included_files_that_could_not_be_read_are_counted():
    data = zip_bytes({"main.tex": ROOT, "old.tex": b"caf\xe9 latin-1\n"})
    doc = load_bytes("p.zip", data)
    assert doc.not_checked == {"skipped_files": 2}
    line = shapes.reading_sentence(shapes.reading_summary(doc))
    assert "Not checked: 2 included files that could not be read." in line
    # the warnings still say which, as before
    assert any("missing" in w for w in doc.warnings)


def test_one_main_file_lists_no_candidates():
    doc = load_bytes("p.zip", zip_bytes({"main.tex": ROOT.replace(
        "\\input{missing}\\input{old}", ""), "ch.tex": "Chapter words."}))
    assert doc.main_file == "main.tex" and doc.main_candidates == []


def test_an_ambiguous_project_lists_the_candidates_and_the_one_read():
    data = zip_bytes({"paper.tex": ROOT.replace(
        "\\input{missing}\\input{old}", "\\input{body}"),
        "body.tex": "Body words.", "cover-letter.tex": LETTER})
    doc = load_bytes("p.zip", data)
    assert doc.main_candidates == ["cover-letter.tex", "paper.tex"]
    assert doc.main_file == "paper.tex"            # the letter is set aside
    assert "Body words." in doc.original
    # no silent guess left in the warnings: the choice is data now
    assert not any("several main" in w for w in doc.warnings)


def test_the_writer_can_choose_the_other_root():
    data = zip_bytes({"paper.tex": ROOT.replace(
        "\\input{missing}\\input{old}", ""), "cover-letter.tex": LETTER})
    doc = load_bytes("p.zip", data, main_file="cover-letter.tex")
    assert doc.main_file == "cover-letter.tex"
    assert "Dear editor" in doc.original and "Paper words" not in doc.original
    assert doc.main_candidates == ["cover-letter.tex", "paper.tex"]


def test_a_main_file_that_is_not_there_is_refused_plainly():
    data = zip_bytes({"paper.tex": LETTER})
    with pytest.raises(IngestError) as e:
        load_bytes("p.zip", data, main_file="nope/../thesis.tex")
    assert e.value.code == "unreadable_file"
    assert "no .tex file called" in e.value.message


def test_other_formats_ignore_main_file():
    doc = load_bytes("x.tex", TEX.encode(), main_file="whatever.tex")
    assert doc.main_file is None and doc.main_candidates == []


def test_the_cli_chooses_with_main_and_says_which(tmp_path, capsys):
    path = tmp_path / "project.zip"
    path.write_bytes(zip_bytes({"paper.tex": ROOT.replace(
        "\\input{missing}\\input{old}", ""), "cover-letter.tex": LETTER}))
    cli.main(["check", str(path), "--no-metrics"])
    out = capsys.readouterr().out
    assert "Main file: paper.tex" in out and "--main cover-letter.tex" in out
    assert "Checked " in out
    cli.main(["check", str(path), "--no-metrics", "--json",
              "--main", "cover-letter.tex"])
    payload = json.loads(capsys.readouterr().out)[0]
    assert payload["main_file"] == "cover-letter.tex"
    assert payload["main_candidates"] == ["cover-letter.tex", "paper.tex"]
    assert payload["reading"]["words_checked"] > 0

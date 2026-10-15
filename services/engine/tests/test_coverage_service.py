"""The coverage summary over the wire (Codex review #5) and the engine's
capability description (#11). Synthetic documents only."""

from __future__ import annotations

import io
import json
import urllib.parse
import zipfile

from researchly_service.schemas import AnalyzeFileResponse, HealthResponse

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SECRET = "Zqhidden"


def zip_bytes(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def upload(c, data, name, options=None):
    h = {"content-type": "application/octet-stream",
         "x-researchly-filename": urllib.parse.quote(name)}
    if options is not None:
        h["x-researchly-options"] = json.dumps(options)
    return c.post("/v1/analyze-file", content=data, headers=h)


def run(text):
    return f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'


def docx() -> bytes:
    box = ('<w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing>'
           f'<w:txbxContent><w:p>{run("Box words " + SECRET)}</w:p>'
           '</w:txbxContent></w:drawing></mc:Choice></mc:AlternateContent>'
           '</w:r>')
    body = (f'<w:p>{run("We fitted a renewal model to weekly counts.")}'
            '<w:r><w:footnoteReference w:id="2"/></w:r></w:p>'
            f'<w:p>{box}{run("The priors were weak.")}</w:p>')
    doc = (f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{W}" '
           'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/'
           f'2006"><w:body>{body}<w:sectPr/></w:body></w:document>')
    header = (f'<?xml version="1.0"?><w:hdr xmlns:w="{W}"><w:p>'
              f'{run("Running head " + SECRET)}</w:p></w:hdr>')
    return zip_bytes({"[Content_Types].xml": "<Types/>",
                      "word/document.xml": doc, "word/header1.xml": header})


def test_a_docx_upload_says_what_was_not_checked(client):
    r = upload(client, docx(), "chapter.docx")
    assert r.status_code == 200, r.text
    body = AnalyzeFileResponse.model_validate(r.json())
    got = {i.kind: i.count for i in body.reading.not_checked}
    assert got == {"footnotes": 1, "text_boxes": 1, "headers_footers": 1}
    assert SECRET not in json.dumps(r.json()["reading"])


ROOT = ("\\documentclass{article}\n\\begin{document}\n"
        "Paper words.\\footnote{A note.}\n\\end{document}\n")
LETTER = ("\\documentclass{letter}\n\\begin{document}\n"
          "Dear editor, we resubmit.\n\\end{document}\n")


def test_an_ambiguous_project_lists_its_roots_and_can_be_rechecked(client):
    data = zip_bytes({"paper.tex": ROOT, "cover-letter.tex": LETTER})
    r = upload(client, data, "project.zip")
    assert r.status_code == 200, r.text
    doc = r.json()["document"]
    assert doc["main_file"] == "paper.tex"
    assert doc["main_candidates"] == ["cover-letter.tex", "paper.tex"]
    assert r.json()["reading"]["included"] == [
        {"kind": "footnotes", "count": 1, "label": "footnotes"}]

    r = upload(client, data, "project.zip",
               options={"main_file": "cover-letter.tex"})
    assert r.status_code == 200, r.text
    doc = r.json()["document"]
    assert doc["main_file"] == "cover-letter.tex"
    assert "Dear editor" in doc["text"] and "Paper words" not in doc["text"]


def test_an_unknown_main_file_is_a_plain_error(client):
    data = zip_bytes({"paper.tex": ROOT})
    r = upload(client, data, "project.zip", options={"main_file": "x.tex"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unreadable_file"


def test_a_single_file_has_no_main_file_choice(client):
    r = upload(client, ROOT.encode(), "paper.tex")
    doc = r.json()["document"]
    assert doc["main_file"] is None and doc["main_candidates"] == []


def test_health_says_what_the_hosted_engine_checks(client):
    body = HealthResponse.model_validate(client.get("/v1/health").json())
    caps = body.capabilities
    assert caps is not None and caps.route == "service"
    assert caps.where == "service"
    on = {c.id: c.on for c in caps.checks}
    assert on["rules"] and on["document"] and on["brief"]
    assert caps.summary.startswith("Researchly cloud: checks")
    assert "never stored" in caps.summary


def test_health_capabilities_follow_the_grammar_setting(make_client):
    c = make_client(grammar_enabled=False)
    caps = c.get("/v1/health").json()["capabilities"]
    grammar = next(x for x in caps["checks"] if x["id"] == "grammar")
    assert grammar["on"] is False and grammar["note"] == "turned off in settings"

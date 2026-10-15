"""Evidence-linked brief and scope-aware profiles on the analysis routes
(Codex review #3, #4). Synthetic text only."""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

from researchly_service.schemas import (AnalyzeFileResponse, AnalyzeResponse,
                                        AnalyzeWordResponse)

from test_privacy_canary import (CANARY, assert_logged_request,  # noqa: F401
                                 assert_no_canary_anywhere, capture)

sys.path.insert(0, str(Path(__file__).resolve().parents[3]
                       / "packages/core/tests"))
from ingest_fixtures import zip_bytes  # noqa: E402

PAPER = ("Introduction\n\nDengue \U0001F99F remains a leading cause of "
         "admission. Little is known about the dry season.\n\n"
         "Methods\n\nWe fitted a renewal model to weekly counts.\n\n"
         "Results\n\nCases fell by 40% after spraying.\n\n"
         "Discussion\n\nAdmissions fell by 35% in the treated districts "
         "(Table 2). Spraying caused the fall in admissions. This proves "
         "that spraying works.\n")


def post(client, content=PAPER, **options):
    return client.post("/v1/analyze", json={"format": "plain",
                                            "content": content,
                                            "options": options})


def links(body):
    return [x for q in body.review.questions for x in q.links]


def utf16(text, a, b):
    return text.encode("utf-16-le")[2 * a:2 * b].decode("utf-16-le")


def test_brief_links_index_the_text_in_code_points_and_utf16(client):
    body = AnalyzeResponse.model_validate(
        post(client, review=True, narrative=True).json())
    found = links(body)
    assert found
    for link in found:
        for sp in (link.claim, link.evidence):
            if sp is None:
                continue
            text = PAPER[sp.start:sp.end]
            assert " ".join(text.split()).startswith(sp.text.rstrip("\u2026"))
            assert utf16(PAPER, sp.begin16, sp.end16) == text
            assert sp.location is None and sp.file is None
    (claim,) = [x for x in found if x.kind == "causal_claim"]
    assert claim.evidence_status == "detected"
    assert claim.evidence.text.startswith("Admissions fell by 35%")
    moves = [m for s in body.narrative.sections for m in s.moves if m.span]
    assert moves


def test_older_clients_keep_the_quoted_evidence(client):
    raw = post(client, review=True).json()
    d = next(q for q in raw["review"]["questions"] if q["id"] == "D")
    assert d["evidence"] and d["links"]


def test_word_route_places_the_evidence(client):
    paras = [{"text": "Discussion", "style": "Heading 1"},
             {"text": "Admissions \U0001F4C9 fell by 35% (Table 2). Spraying "
                      "caused the fall in admissions."}]
    r = client.post("/v1/analyze-word", json={
        "paragraphs": paras, "options": {"review": True, "mode": "revise"}})
    body = AnalyzeWordResponse.model_validate(r.json())
    (claim,) = [x for x in links(body) if x.kind == "causal_claim"]
    loc = claim.claim.location
    assert loc.paragraph == 1
    assert loc.snippet == "Spraying caused the fall in admissions."
    assert loc.begin16 == loc.start + 1


def test_a_project_names_the_file_and_line(client):
    files = {"main.tex": "\\documentclass{article}\n\\begin{document}\n"
                         "\\input{sections/discussion}\n\\end{document}\n",
             "sections/discussion.tex":
                 "\\section{Discussion}\nAdmissions fell (Table 2).\n"
                 "Spraying caused the fall in admissions.\n"}
    r = client.post("/v1/analyze-file", content=zip_bytes(files), headers={
        "content-type": "application/octet-stream",
        "x-researchly-filename": urllib.parse.quote("p.zip"),
        "x-researchly-options": json.dumps({"review": True})})
    body = AnalyzeFileResponse.model_validate(r.json())
    (claim,) = [x for x in links(body) if x.kind == "causal_claim"]
    assert claim.claim.file == "sections/discussion.tex"
    assert claim.claim.file_line == 3


def test_scope_is_reported_and_can_be_chosen(client):
    methods = "Methods\n\nWe fitted a renewal model to weekly counts.\n"
    body = AnalyzeResponse.model_validate(post(client, content=methods).json())
    assert body.profile.scope.id == "excerpt" and body.profile.scope.guessed
    body = AnalyzeResponse.model_validate(
        post(client, content=methods, document_scope="whole").json())
    assert body.profile.scope.id == "whole" and not body.profile.scope.guessed
    bad = post(client, content=methods, document_scope="book")
    assert bad.status_code == 422


def test_response_units_reach_the_map(client):
    letter = ("Reviewer 1\n\nComment 1: The intervals are wide.\n\n"
              "Response: We now report them in Table 2.\n\n"
              "Comment 2: Define R0.\n\nResponse: Done.\n")
    body = AnalyzeResponse.model_validate(
        post(client, content=letter, narrative=True).json())
    assert body.profile.id.value == "response-to-reviewers"
    assert [u.label for u in body.narrative.units] == [
        "Reviewer 1, comment 1", "Reviewer 1, comment 2"]
    assert body.narrative.units[0].reply.text == "We now report them in Table 2."


def test_evidence_text_reaches_only_the_response(client, capture):  # noqa: F811
    doc = PAPER.replace("Spraying caused", f"Spraying {CANARY} caused")
    r = post(client, content=doc, review=True, narrative=True)
    assert r.status_code == 200
    assert CANARY in json.dumps(r.json()["review"])
    assert_no_canary_anywhere(capture)

"""Table cell places from the Word add-in (Codex review #7): the optional
`cell` on a Word paragraph lets X401 compare a quoted number with the row
and column the sentence names, and the suggestion carries the compared
cell as `table_evidence`. Without `cell`, the old whole-table check stays.
Both the hosted engine and the local Word server. Synthetic text only."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from researchly.document import MAX_CELL_INDEX
from researchly_service import schemas
from researchly_service.schemas import AnalyzeWordResponse

ROOT = Path(__file__).resolve().parents[3]

ARMS = [["Outcome", "Treatment", "Control"],
        ["Mortality", "8.2%", "12.5%"],
        ["Readmission", "4.1%", "6.3%"]]


def paragraphs(sentence: str, places: bool = True) -> list:
    out = [{"text": "Results", "style": "Heading 1"},
           {"text": sentence},
           {"text": "Table 1. Outcomes by trial arm.", "style": "Caption"}]
    for r, row in enumerate(ARMS):
        for c, text in enumerate(row):
            p = {"text": text, "kind": "table"}
            if places:
                p["cell"] = [0, r, c]
            out.append(p)
    return out


SWAPPED = "The treatment mortality was 12.5% (Table 1)."


def x401(body: dict) -> list:
    return [s for s in body["suggestions"] if s["rule_id"] == "X401"]


def post(client, paras):
    r = client.post("/v1/analyze-word", json={"paragraphs": paras})
    assert r.status_code == 200, r.text
    AnalyzeWordResponse.model_validate(r.json())           # extra=forbid
    return r.json()


def test_cell_places_let_x401_flag_a_swapped_arm(client):
    # 12.5% is the control arm's mortality, quoted for the treatment arm.
    (s,) = x401(post(client, paragraphs(SWAPPED)))
    assert s["text"] == "12.5%"
    assert s["message"] == (
        "Table 1, row 'Mortality', column 'Treatment' holds 8.2%, not "
        "12.5%; 12.5% is in column 'Control' — a value from the wrong "
        "column?")
    ev = s["table_evidence"]
    assert ev["table"] == "Table 1" and ev["cell_text"] == "8.2%"
    assert ev["rounding"] == ""
    assert ev["row_header"] == "Mortality"
    assert ev["column_header"] == "Treatment"
    assert (ev["row"], ev["column"]) == (1, 1)
    assert ev["expected"] == "8.2%" and ev["quoted"] == "12.5%"
    # The location maps back to the sentence's paragraph.
    assert s["location"]["paragraph"] == 1


def test_without_cell_places_the_old_behaviour_stays(client):
    # 12.5% is in the table (the control arm): the whole-table check passes.
    assert x401(post(client, paragraphs(SWAPPED, places=False))) == []
    (s,) = x401(post(client, paragraphs(
        "The treatment mortality was 9.9% (Table 1).", places=False)))
    assert "is not in Table 1" in s["message"]
    assert s["table_evidence"] is None


@pytest.mark.parametrize("cell", [[0, 1], [0, 1, 2, 3, 4], [0, -1, 2],
                                  [0, 1, True], [0, 1, 2.5], [0, 1, 2, 0],
                                  [0, 1, MAX_CELL_INDEX + 1], "0,1,2"])
def test_a_malformed_cell_is_refused(client, cell):
    paras = paragraphs(SWAPPED)
    paras[-1]["cell"] = cell
    r = client.post("/v1/analyze-word", json={"paragraphs": paras})
    assert r.status_code == 422


def test_the_bounds_agree_with_the_engine():
    assert schemas.MAX_CELL_INDEX == MAX_CELL_INDEX


# --- the local Word server (apps/word-addin/server.py) -------------------------

@pytest.fixture(scope="module")
def server():
    path = ROOT / "apps" / "word-addin" / "server.py"
    spec = importlib.util.spec_from_file_location("local_word_server_cells",
                                                  path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["local_word_server_cells"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_local_contract_route_passes_cell_through(server):
    body = server.analyze_word({"paragraphs": paragraphs(SWAPPED)})
    raw = json.loads(json.dumps(body))
    AnalyzeWordResponse.model_validate(raw)
    (s,) = x401(raw)
    assert s["table_evidence"]["expected"] == "8.2%"
    old = json.loads(json.dumps(server.analyze_word(
        {"paragraphs": paragraphs(SWAPPED, places=False)})))
    assert x401(old) == []


def test_the_local_contract_route_refuses_a_malformed_cell(server):
    paras = paragraphs(SWAPPED)
    paras[-1]["cell"] = [0, 1, "2"]
    with pytest.raises(server.ContractError):
        server.parse_word_request({"paragraphs": paras})


def test_the_taskpane_check_route_passes_cell_through(server):
    # The local taskpane posts to /check, which hands the paragraphs to the
    # engine as they are.
    (s,) = x401(server.run_check({"paragraphs": paragraphs(SWAPPED),
                                  "show_preferences": True}))
    assert s["table_evidence"]["expected"] == "8.2%"
    assert x401(server.run_check({"paragraphs": paragraphs(SWAPPED, False),
                                  "show_preferences": True})) == []

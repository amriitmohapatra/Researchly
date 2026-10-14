"""The Word add-in sends table cell places (Codex review #7).

`tablePlaces` in the taskpane is pure: it is cut out of taskpane.js and run
with Node on what Word would report per paragraph. Skipped where Node is
not installed (the owner's Mac need not have it); CI has it.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = (Path(__file__).resolve().parents[3] / "apps" / "word-addin" / "web"
      / "taskpane.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def places(paras):
    code = re.search(r"// <table-places>.*?// </table-places>", JS, re.S)
    assert code, "the <table-places> markers moved"
    script = (code.group(0) + "\nprocess.stdout.write(JSON.stringify("
              f"tablePlaces({json.dumps(paras)})));")
    out = subprocess.run([NODE, "-e", script], capture_output=True,
                         text=True, check=True, timeout=30)
    return json.loads(out.stdout)


def body():
    return {"level": 0}


def cell(row, col, cells=2, level=1):
    return {"level": level, "row": row, "cell": col, "cells": cells}


needs_node = pytest.mark.skipif(NODE is None, reason="Node is not installed")


@needs_node
def test_tables_are_numbered_in_order():
    got = places([body(), cell(0, 0), cell(0, 1), cell(1, 0), cell(1, 1),
                  body(), cell(0, 0, 1), cell(1, 0, 1)])
    assert got == [None, [0, 0, 0], [0, 0, 1], [0, 1, 0], [0, 1, 1],
                   None, [1, 0, 0], [1, 1, 0]]


@needs_node
def test_a_cell_of_two_paragraphs_shares_its_place():
    assert places([cell(0, 0), cell(0, 0), cell(0, 1)]) == [
        [0, 0, 0], [0, 0, 0], [0, 0, 1]]


@needs_node
@pytest.mark.parametrize("table", [
    # Merged cells: the rows report different cell counts.
    [cell(0, 0, 1), cell(1, 0, 2), cell(1, 1, 2)],
    # A table inside a table.
    [cell(0, 0), cell(0, 0, level=2), cell(0, 1)],
    # A paragraph Word could not place.
    [cell(0, 0), {"level": 1}, cell(0, 1)],
    # Rows going backwards: not one table read in order.
    [cell(1, 0), cell(1, 1), cell(0, 0), cell(0, 1)],
    # A cell index past the row's count.
    [cell(0, 0), cell(0, 2)],
])
def test_uncertain_tables_get_no_places(table):
    got = places([body()] + table + [body(), cell(0, 0, 1)])
    assert got[1:1 + len(table)] == [None] * len(table)
    assert got[-1] == [1, 0, 0]            # the next table is still placed


def test_places_are_asked_for_only_on_wordapi_1_3():
    fn = JS[JS.index("async function cellPlaces"):]
    assert fn.index('isSetSupported("WordApi", "1.3")') < fn.index(
        "parentTableCellOrNullObject")
    get = JS[JS.index("async function getParagraphs"):]
    assert "cellPlaces(ctx, paras.items)" in get[:get.index("\n}\n")]

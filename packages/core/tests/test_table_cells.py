"""X401 against the cell a sentence names (Codex review #7).

Word tables arrive with cell places (`Document.table_cells`): from the
.docx reader, and from the Word add-in on WordApi 1.3. A sentence naming
one row and one column is checked against that cell; everything else falls
back to "anywhere in the table". Synthetic tables and sentences only.
"""

import pytest

from researchly import api, tables
from researchly.document import Document, cell_place
from researchly.ingest import load_bytes
from ingest_fixtures import docx_bytes, para

NLP = api.get_nlp()

ARMS = [["Outcome", "Treatment", "Control"],
        ["Mortality", "8.2%", "12.5%"],
        ["Readmission", "4.1%", "6.3%"]]


def cells(rows, table=0, places=True, span=None):
    """Word paragraphs for a table; `span` = {(row, col): colspan}."""
    out = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            p = {"text": text, "kind": "table"}
            if places:
                p["cell"] = [table, r, c] + (
                    [span[(r, c)]] if span and (r, c) in span else [])
            out.append(p)
    return out


def word(sentence, rows=ARMS, caption="Table 1. Outcomes by trial arm.",
         **kw) -> Document:
    return Document.from_word(
        [{"text": "Results", "style": "Heading 1"}, {"text": sentence},
         {"text": caption, "style": "Caption"}] + cells(rows, **kw))


def x401(doc):
    return [s for s in api.analyze(doc, nlp=NLP,
                                   show_preferences=True).suggestions
            if s.rule_id == "X401"]


# --- the cell check --------------------------------------------------------------

def test_a_swapped_group_is_flagged_although_its_number_is_elsewhere():
    # 12.5% is in the table (the control arm): the old check passed it.
    (h,) = x401(word("The treatment mortality was 12.5% (Table 1)."))
    assert h.text == "12.5%"
    assert h.message == ("Table 1 reports 8.2% in the Mortality row, "
                         "Treatment column; this sentence says 12.5%.")
    ev = h.table_evidence
    assert (ev["table"], ev["row"], ev["column"]) == ("Table 1", 1, 1)
    assert (ev["row_header"], ev["column_header"]) == ("Mortality",
                                                      "Treatment")
    assert ev["expected"] == "8.2%" and ev["quoted"] == "12.5%"
    assert ev["rounding"] == ""
    doc = word("The treatment mortality was 12.5% (Table 1).")
    assert doc.original[ev["cell_start"]:ev["cell_end"]] == "8.2%"


def test_a_wrong_row_is_flagged():
    (h,) = x401(word("Readmission in the treatment arm was 8.2% (Table 1)."))
    assert "4.1% in the Readmission row, Treatment column" in h.message


@pytest.mark.parametrize("sentence", [
    "The treatment mortality was 8.2% (Table 1).",
    "In the control arm, readmission reached 6.3% (Table 1).",
    "The-Mortality under CONTROL was 12.5% (Table 1).",   # case, punctuation
])
def test_the_right_cell_is_quiet(sentence):
    assert x401(word(sentence)) == []


def test_repeated_values():
    rows = [["Outcome", "Treatment", "Control"],
            ["Mortality", "8.2%", "8.2%"],
            ["Readmission", "4.1%", "6.3%"]]
    # Held by two cells, one of them the cell named: quiet.
    assert x401(word("Control mortality was 8.2% (Table 1).", rows)) == []
    # Held by two cells, neither of them the cell named: flagged.
    (h,) = x401(word("Control readmission was 8.2% (Table 1).", rows))
    assert h.table_evidence["expected"] == "6.3%"


def test_rounding_is_allowed_and_shown():
    rows = [["Outcome", "Treatment", "Control"],
            ["Mortality", "8.24%", "12.51%"]]
    assert x401(word("Treatment mortality was 8.2% (Table 1).", rows)) == []
    (h,) = x401(word("Treatment mortality was 12.5% (Table 1).", rows))
    assert h.message == ("Table 1 reports 8.24% (8.2% rounded to 1 decimal "
                         "place) in the Mortality row, Treatment column; "
                         "this sentence says 12.5%.")
    assert h.table_evidence["rounding"] == "rounded to 1 decimal place"


def test_a_unit_in_the_header():
    rows = [["Outcome", "Treatment (%)", "Control (%)"],
            ["Mortality", "8.2", "12.5"]]
    assert x401(word("Treatment mortality was 8.2% (Table 1).", rows)) == []
    (h,) = x401(word("Treatment mortality was 12.5% (Table 1).", rows))
    assert h.table_evidence["expected"] == "8.2%"
    assert h.table_evidence["column_header"] == "Treatment"


def test_incompatible_units_are_not_compared_with_the_cell():
    # 12.5 people is not 12.5%: no verdict from the cell; the whole-table
    # fallback finds 12.5 and stays quiet, as before.
    assert x401(word("Treatment mortality was 12.5 per 100 (Table 1).")) == []
    # 0.082 is not 8.2% without a conversion rule: only the old check
    # speaks, and it carries no cell evidence.
    (h,) = x401(word("Treatment mortality was 0.082 (Table 1).",
                     [["Outcome", "Treatment", "Control"],
                      ["Mortality", "8.2%", "1.5"]]))
    assert "is not in Table 1" in h.message and h.table_evidence is None


@pytest.mark.parametrize("rows,sentence", [
    # A header that repeats: two "Total" rows.
    ([["Group", "Treatment", "Control"], ["Total", "8.2%", "12.5%"],
      ["Total", "4.1%", "6.3%"]],
     "Total treatment mortality was 12.5% (Table 1)."),
    # Two columns named.
    (ARMS, "Mortality was 12.5% under treatment versus control (Table 1)."),
    # No row named, and the table has two data rows.
    (ARMS, "Under treatment the share was 12.5% (Table 1)."),
    # A header that is both a row and a column header.
    ([["Group", "Control", "Treatment"], ["Control", "8.2%", "12.5%"],
      ["Mortality", "4.1%", "6.3%"]],
     "Control mortality was 12.5% (Table 1)."),
])
def test_ambiguous_names_abstain(rows, sentence):
    # Each would be a mismatch if a cell were picked; 12.5% is in the
    # table, so the fallback is quiet. Abstaining is not a verdict.
    assert x401(word(sentence, rows)) == []


def test_a_number_worked_out_from_the_table_abstains():
    assert x401(word("Treatment mortality was 12.5% lower (Table 1).")) == []


def test_one_data_column_needs_only_the_row():
    rows = [["Outcome", "Treatment"], ["Mortality", "8.2%"],
            ["Readmission", "4.1%"]]
    (h,) = x401(word("Mortality was 4.1% (Table 1).", rows))
    # The column goes unnamed in the sentence; the message still names it.
    assert h.message.startswith("Table 1 reports 8.2% in the Mortality row, "
                                "Treatment column;")


def test_a_longer_header_wins_over_one_inside_it():
    rows = [["Outcome", "Treatment", "Control"],
            ["Mortality", "8.2%", "12.5%"],
            ["Mortality at one year", "10.4%", "15.0%"]]
    (h,) = x401(word("Treatment mortality at one year was 8.2% (Table 1).",
                     rows))
    assert h.table_evidence["expected"] == "10.4%"


def test_a_merged_cell_leaves_the_table_unsupported():
    rows = [["Outcome", "Arm", ""],
            ["", "Treatment", "Control"],
            ["Mortality", "8.2%", "12.5%"]]
    doc = word("The treatment mortality was 12.5% (Table 1).", rows,
               span={(0, 1): 2})
    assert tables.grids(doc)[0].unsupported == "a merged cell"
    assert x401(doc) == []


def test_without_cell_places_the_old_check_is_kept():
    doc = word("The treatment mortality was 12.5% (Table 1).", places=False)
    assert doc.table_cells == [] and x401(doc) == []
    (h,) = x401(word("The treatment mortality was 9.9% (Table 1).",
                     places=False))
    assert "is not in Table 1" in h.message and h.table_evidence is None


def test_latex_tables_keep_the_old_check():
    doc = Document.from_text(
        "\\documentclass{article}\n\\begin{document}\n\\section{Results}\n"
        "The treatment mortality was 12.5\\% (Table~\\ref{tab:a}).\n"
        "\\begin{table}\\caption{Outcomes by trial arm.}\\label{tab:a}"
        "\\begin{tabular}{lll}Outcome & Treatment & Control \\\\"
        "Mortality & 8.2\\% & 12.5\\% \\\\\\end{tabular}\\end{table}\n"
        "\\end{document}\n", "latex")
    assert x401(doc) == []


# --- cell places -----------------------------------------------------------------

@pytest.mark.parametrize("cell,place", [
    ([0, 1, 2], (0, 1, 2, 1)),
    ([3, 0, 1, 2], (3, 0, 1, 2)),
    (None, None), ([0, 1], None), ([0, 1, 2, 3, 4], None),
    ([0, -1, 2], None), ([0, 1, True], None), ([0, 1, 2, 0], None),
    ([0, 1, 2.0], None), ("0,1,2", None),
])
def test_cell_place(cell, place):
    assert cell_place(cell) == place


def test_from_word_keeps_cell_places():
    doc = word("Text.", [["Outcome", "Treatment"], ["Mortality", "8.2%"]])
    a, b, t, r, c, span = doc.table_cells[-1]
    assert doc.original[a:b] == "8.2%" and (t, r, c, span) == (0, 1, 1, 1)


def test_an_empty_cell_no_longer_splits_a_placed_table():
    # Three empty cells put the last value more than four characters past
    # the others; joined by closeness, the table lost it.
    rows = [["Outcome", "Treatment", "", "", "", "Control"],
            ["Mortality", "8.2%", "", "", "", "12.5%"]]
    sentence = "Mortality in the control arm was 12.5% (Table 1)."
    caption = "Table 1. Mortality (%) by trial arm."
    assert x401(word(sentence, rows, caption)) == []
    (h,) = x401(word(sentence, rows, caption, places=False))
    assert "is not in Table 1" in h.message


def test_header_words():
    assert tables.normalize("The  Treatment-Arm") == "treatment arm"
    assert tables.label("Mortality (%)") == ("mortality", "%")
    assert tables.label("Vaccinated, %") == ("vaccinated", "%")
    assert tables.label("2020")[0] == "" and tables.label("0-14")[0] == ""
    assert tables.header_name("Age  [years]") == "Age"


def test_to_dict_carries_the_evidence():
    (h,) = x401(word("The treatment mortality was 12.5% (Table 1)."))
    assert h.to_dict()["table_evidence"]["expected"] == "8.2%"


# --- the .docx reader ------------------------------------------------------------

def tc(text, props=""):
    return f"<w:tc><w:tcPr>{props}</w:tcPr>{para(text)}</w:tc>"


def tbl(*rows, row_props=""):
    trpr = f"<w:trPr>{row_props}</w:trPr>" if row_props else ""
    return ("<w:tbl><w:tblPr/>"
            + "".join(f"<w:tr>{trpr}{''.join(r)}</w:tr>" for r in rows)
            + "</w:tbl>")


def docx(*blocks):
    return load_bytes("t.docx", docx_bytes("".join(blocks)))


def places(doc):
    return {doc.original[a:b]: (t, r, c, s)
            for a, b, t, r, c, s in doc.table_cells}


def test_docx_cells_are_placed_on_the_grid():
    doc = docx(tbl([tc("Outcome"), tc("Treatment")],
                   [tc("Mortality"), tc("8.2%")]),
               para("Between."),
               tbl([tc("Wide", '<w:gridSpan w:val="2"/>'), tc("Zqc")],
                   [tc("a1"), tc("b1"), tc("c1")]))
    p = places(doc)
    assert p["8.2%"] == (0, 1, 1, 1)
    assert p["Wide"] == (1, 0, 0, 2) and p["Zqc"] == (1, 0, 2, 1)
    assert p["c1"] == (1, 1, 2, 1)


def test_docx_a_cell_of_two_paragraphs_is_one_cell():
    doc = docx(tbl([tc("Outcome"), tc("Treatment")],
                   [tc("Mortality"),
                    f"<w:tc>{para('8.2%')}{para('(n = 12)')}</w:tc>"]))
    (g,) = tables.grids(doc)
    assert g.cells[(1, 1)].text == "8.2% (n = 12)"


@pytest.mark.parametrize("table", [
    tbl([tc("Outcome", '<w:vMerge w:val="restart"/>'), tc("Treatment")],
        [tc("", "<w:vMerge/>"), tc("8.2%")]),
    tbl([tc("Outcome"), tc("Treatment")], [tc("8.2%")],
        row_props='<w:gridBefore w:val="1"/>'),
    tbl([tc("Outcome"), "<w:tc>" + tbl([tc("Inner"), tc("8.2%")]) + "</w:tc>"]),
])
def test_docx_irregular_tables_get_no_places(table):
    assert docx(table).table_cells == []


def test_docx_upload_flags_the_swapped_group():
    doc = docx(para("Results", style="berschrift1"),
               para("The treatment mortality was 12.5% (Table 1)."),
               para("Table 1. Outcomes by trial arm.", style="Beschriftung"),
               tbl([tc("Outcome"), tc("Treatment"), tc("Control")],
                   [tc("Mortality"), tc("8.2%"), tc("12.5%")]))
    (h,) = x401(doc)
    assert h.table_evidence["expected"] == "8.2%"

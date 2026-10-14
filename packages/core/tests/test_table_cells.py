"""X401 reads a table's rows and columns (Codex review #7).

When a sentence names a row and/or a column of the table it cites, the
number it quotes must be in that cell (rounding allowed, a proportion never
taken for a percentage); when it names none, or names them ambiguously, the
number may be anywhere in the table, as before. Synthetic tables only
(CLAUDE.md): LaTeX, Word paragraphs with and without cell places, an
uploaded .docx, and plain text and Markdown (which have no tables here).
"""

import pytest

from researchly import api, tables
from researchly.document import Document
from researchly.ingest import load_bytes
from researchly.rules_structure import table_evidence

from ingest_fixtures import docx_bytes, para
from ingest_fixtures import table as docx_table

NLP = api.get_nlp()


def tex(body: str) -> Document:
    return Document.from_text(
        "\\documentclass{article}\n\\usepackage{booktabs}\n"
        "\\begin{document}\n\\section{Results}\n" + body +
        "\n\\end{document}\n", "latex")


def hits(doc: Document):
    return [s for s in api.analyze(doc, nlp=NLP,
                                   show_preferences=True).suggestions
            if s.rule_id == "X401"]


def evidence(doc: Document):
    return list(table_evidence(NLP(doc.masked), doc))


# Incidence per 1,000 by age group. 4.13 appears twice (repeated value).
AGE = r"""\begin{table}\caption{Cases and incidence by age group.}\label{tab:a}
\begin{tabular}{lrr}\toprule
Age group & Cases & Incidence (per 1,000) \\ \midrule
18--29 & 120 & 4.13 \\
30--44 & 80 & 6.20 \\
45--64 & 60 & 2.31 \\
65+ & 40 & 4.13 \\ \bottomrule
\end{tabular}\end{table}
"""


def age(sentence: str) -> Document:
    return tex(sentence + "\n" + AGE)


# --- rounding --------------------------------------------------------------------

def test_rounded_value_in_the_named_cell_passes_and_says_why():
    doc = age("In Table~\\ref{tab:a}, the incidence in the 18--29 age group "
              "was 4.1 per 1,000.")
    assert hits(doc) == []
    ((_, _, verdict, why),) = evidence(doc)
    assert verdict == "pass"
    assert why == ("Table 1, row '18–29', column 'Incidence (per 1,000)': "
                   "4.13 — the text says 4.1, which matches when rounded to "
                   "1 decimal place")


def test_exact_value_passes_without_a_rounding_note():
    doc = age("In Table~\\ref{tab:a}, the incidence in the 30--44 age group "
              "was 6.20 per 1,000.")
    assert hits(doc) == []
    ((_, _, verdict, why),) = evidence(doc)
    assert verdict == "pass" and "rounded" not in why


def test_wrongly_rounded_value_fires_and_shows_the_rounding():
    doc = age("In Table~\\ref{tab:a}, the incidence in the 18--29 age group "
              "was 4.2 per 1,000.")
    (h,) = hits(doc)
    assert h.text == "4.2"
    assert h.message.startswith(
        "Table 1, row '18–29', column 'Incidence (per 1,000)' holds 4.13 "
        "(4.1 when rounded to 1 decimal place), not 4.2")


def test_more_decimals_than_the_cell_never_matches_by_rounding():
    doc = age("The incidence in the 18--29 age group was 4.134 per 1,000 "
              "(Table~\\ref{tab:a}).")
    (h,) = hits(doc)
    assert h.text == "4.134"


# --- swapped rows ------------------------------------------------------------------

def test_swapped_rows_fire_and_name_the_row_holding_the_number():
    doc = age("In Table~\\ref{tab:a}, the incidence in the 18--29 age group "
              "was 6.2 per 1,000.")
    (h,) = hits(doc)
    assert h.text == "6.2"
    assert "holds 4.13" in h.message and "6.2 is in row '30–44'" in h.message
    assert "wrong row" in h.message


def test_the_same_row_named_in_other_words_order_still_binds():
    doc = age("Incidence was highest at 6.2 per 1,000 among those aged "
              "30--44 (Table~\\ref{tab:a}).")
    assert hits(doc) == []


def test_old_behaviour_would_have_missed_the_swap():
    # 6.2 is in the table, so "anywhere in the table" was satisfied.
    doc = age("The incidence was 6.2 per 1,000 (Table~\\ref{tab:a}).")
    assert hits(doc) == []


# --- repeated values ------------------------------------------------------------

def test_repeated_value_is_fine_when_one_copy_is_in_the_named_row():
    doc = age("Among those aged 65+, the incidence was 4.13 per 1,000 "
              "(Table~\\ref{tab:a}).")
    assert hits(doc) == []


def test_repeated_value_in_other_rows_only_still_fires():
    doc = age("Among those aged 45--64, the incidence was 4.13 per 1,000 "
              "(Table~\\ref{tab:a}).")
    (h,) = hits(doc)
    assert "row '45–64'" in h.message and "4.13 is in row '18–29'" in h.message


# --- wrong groups ---------------------------------------------------------------

SEX = r"""\begin{table}\caption{Incidence by sex and age group.}\label{tab:s}
\begin{tabular}{llr}\toprule
Sex & Age group & Incidence \\ \midrule
\multirow{2}{*}{Men} & 18--29 & 4.13 \\
 & 30--44 & 6.20 \\
\multirow{2}{*}{Women} & 18--29 & 3.52 \\
 & 30--44 & 5.08 \\ \bottomrule
\end{tabular}\end{table}
"""


def test_value_from_the_wrong_group_fires():
    doc = tex("Among women aged 18--29, the incidence was 4.1 per 1,000 "
              "(Table~\\ref{tab:s}).\n" + SEX)
    (h,) = hits(doc)
    assert "row 'Women / 18–29'" in h.message
    assert "row 'Men / 18–29'" in h.message and "wrong group" in h.message


@pytest.mark.parametrize("sentence", [
    "Among women aged 18--29, the incidence was 3.5 per 1,000 "
    "(Table~\\ref{tab:s}).",
    "Among men aged 18--29, the incidence was 4.1 per 1,000 "
    "(Table~\\ref{tab:s}).",
    # the age group alone: either sex's row may hold it
    "In those aged 18--29, the incidence was 3.5 per 1,000 "
    "(Table~\\ref{tab:s}).",
])
def test_value_from_the_named_group_passes(sentence):
    assert hits(tex(sentence + "\n" + SEX)) == []


def test_age_group_alone_still_rules_out_other_ages():
    doc = tex("In those aged 18--29, the incidence was 6.2 per 1,000 "
              "(Table~\\ref{tab:s}).\n" + SEX)
    (h,) = hits(doc)
    assert "6.2 is in row 'Men / 30–44'" in h.message


# Column groups: Men and Women over Cases and Rate (\multicolumn).
COLS = r"""\begin{table}\caption{Cases and rates by region and sex.}\label{tab:c}
\begin{tabular}{lrrrr}\toprule
 & \multicolumn{2}{c}{Men} & \multicolumn{2}{c}{Women} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}
Region & Cases & Rate & Cases & Rate \\ \midrule
North & 120 & 4.13 & 98 & 3.52 \\
South & 80 & 6.20 & 75 & 5.08 \\ \bottomrule
\end{tabular}\end{table}
"""


def test_column_group_and_leaf_header_pick_one_cell():
    ok = tex("In the north, the rate among women was 3.5 per 1,000 "
             "(Table~\\ref{tab:c}).\n" + COLS)
    assert hits(ok) == []
    bad = tex("In the north, the rate among women was 4.1 per 1,000 "
              "(Table~\\ref{tab:c}).\n" + COLS)
    (h,) = hits(bad)
    assert "row 'North', column 'Women / Rate'" in h.message
    assert "column 'Men / Rate'" in h.message


# --- units ------------------------------------------------------------------------

def test_unit_in_the_header_matches_the_same_unit_in_the_text():
    doc = age("In Table~\\ref{tab:a}, the incidence in the 18--29 age group "
              "was 4.1 cases per 1,000.")
    assert hits(doc) == []


def test_a_different_rate_base_fires():
    doc = age("In Table~\\ref{tab:a}, the incidence in the 18--29 age group "
              "was 4.1 per 10,000.")
    (h,) = hits(doc)
    assert "per 1,000" in h.message and "per 10,000" in h.message
    assert "check the units" in h.message


def test_unit_in_the_cell_is_read_with_the_number():
    doc = tex("Mean age at onset was 45.2 years in the north "
              "(Table~\\ref{tab:u}).\n"
              "\\begin{table}\\caption{Age at onset by region.}"
              "\\label{tab:u}\\begin{tabular}{lr}Region & Age at onset \\\\"
              "North & 45.2 years \\\\ South & 51.8 years \\\\"
              "\\end{tabular}\\end{table}\n")
    assert hits(doc) == []


PCT = r"""\begin{table}\caption{Vaccination and testing by age group.}\label{tab:p}
\begin{tabular}{lrrr}\toprule
Age group & Vaccinated (\%) & Proportion tested & Incidence (per 1,000) \\ \midrule
18--29 & 12.5 & 0.43 & 4.13 \\
30--44 & 20.1 & 0.38 & 6.20 \\ \bottomrule
\end{tabular}\end{table}
"""


def test_percent_unit_in_the_header_matches_a_percentage():
    doc = tex("In the 18--29 group, 12.5\\% were vaccinated "
              "(Table~\\ref{tab:p}).\n" + PCT)
    assert hits(doc) == []


def test_a_proportion_is_not_a_percentage():
    doc = tex("In the 18--29 group, the proportion tested was 43.0\\% "
              "(Table~\\ref{tab:p}).\n" + PCT)
    (h,) = hits(doc)
    assert "holds 0.43, a proportion" in h.message
    assert "43.0%, a percentage" in h.message


def test_a_percentage_is_not_a_proportion():
    # The % is in the header, not the cell.
    doc = tex("In the 18--29 group, the share vaccinated was 0.125 "
              "(Table~\\ref{tab:p}).\n" + PCT)
    (h,) = hits(doc)
    assert "holds 12.5, a percentage" in h.message
    assert "0.125, a proportion" in h.message


@pytest.mark.parametrize("sentence", [
    # the column is named in another clause than the number
    "In the 18--29 group incidence peaked early, and 12.5\\% were "
    "vaccinated (Table~\\ref{tab:p}).",
    "Incidence peaked in the young, where 20.1\\% were vaccinated "
    "(Table~\\ref{tab:p}).",
])
def test_a_column_named_for_another_clause_is_not_held_to(sentence):
    assert hits(tex(sentence + "\n" + PCT)) == []


def test_a_rate_quoted_as_a_percentage_fires():
    doc = tex("In the 18--29 group, the incidence was 4.13\\% "
              "(Table~\\ref{tab:p}).\n" + PCT)
    (h,) = hits(doc)
    assert "a rate, not a percentage" in h.message


# --- what abstains ------------------------------------------------------------

@pytest.mark.parametrize("sentence", [
    # two rows named: which number belongs to which is not guessed
    "The incidence was 6.2 per 1,000 in the 18--29 group and 4.1 in the "
    "30--44 group (Table~\\ref{tab:a}).",
    # a comparison: the number beside a row's name may be another row's
    "Unlike those aged 18--29, adults aged 45 and over had an incidence of "
    "6.2 per 1,000 (Table~\\ref{tab:a}).",
    "Incidence in the 18--29 group was lower than the 6.2 per 1,000 seen "
    "elsewhere (Table~\\ref{tab:a}).",
    # a row the table does not have: anywhere in the table
    "Among young adults the incidence was 6.2 per 1,000 "
    "(Table~\\ref{tab:a}).",
    # "cases" names a column of counts, not of rates: not meant
    "In most cases aged 18--29 it reached 4.1 per 1,000 "
    "(Table~\\ref{tab:a}).",
])
def test_ambiguous_sentences_fall_back_to_the_whole_table(sentence):
    assert hits(age(sentence)) == []


def test_fallback_still_catches_a_number_nowhere_in_the_table():
    doc = age("The incidence was 6.2 per 1,000 in the 18--29 group and 4.6 "
              "in the 30--44 group (Table~\\ref{tab:a}).")
    (h,) = hits(doc)
    assert h.text == "4.6" and h.message.startswith("4.6 is not in Table 1")


def test_two_tabulars_in_one_float_fall_back_to_the_whole_table():
    doc = tex("In Table~\\ref{tab:t}, the incidence in the 18--29 group was "
              "6.2.\n\\begin{table}\\caption{Two panels of incidence.}"
              "\\label{tab:t}\\begin{tabular}{lr}Age & Incidence \\\\ "
              "18--29 & 4.13 \\\\ 30--44 & 6.20 \\\\\\end{tabular}"
              "\\begin{tabular}{lr}Age & Incidence \\\\ 18--29 & 3.52 \\\\"
              "\\end{tabular}\\end{table}\n")
    assert hits(doc) == []


@pytest.mark.parametrize("src", [
    # the label on the group's last row: filling it down would mislabel
    "\\begin{tabular}{llr}Sex & Age & Rate \\\\ & 18--29 & 4.13 \\\\"
    "\\multirow{-2}{*}{Men} & 30--44 & 6.20 \\\\\\end{tabular}",
    # tabularray's syntax is not read
    "\\begin{tblr}{lr}Age & Rate \\\\ 18--29 & 4.13 \\\\\\end{tblr}",
    # a header too deep to be one
    "\\begin{tabular}{lr}A & B \\\\ C & D \\\\ E & F \\\\ G & H \\\\"
    "18--29 & 4.13 \\\\\\end{tabular}",
])
def test_unreadable_grids_give_none(src):
    g = tables.latex_grid("\\begin{table}" + src + "\\end{table}")
    assert g is None or tables.read(g) is None


def test_a_row_named_by_a_common_word_is_not_a_row():
    # "after" is prose, not the row "After"
    doc = tex("After adjustment, the rate was 4.1 (Table~\\ref{tab:b}).\n"
              "\\begin{table}\\caption{Rates before and after the campaign.}"
              "\\label{tab:b}\\begin{tabular}{lr}Period & Rate \\\\ "
              "Before & 4.13 \\\\ After & 2.31 \\\\\\end{tabular}"
              "\\end{table}\n")
    assert hits(doc) == []


def test_a_table_with_one_row_label_column_of_results_has_no_rows():
    # The first column holds results, not labels: no row can be named.
    doc = tex("The incidence in the 18--29 group was 6.2 "
              "(Table~\\ref{tab:n}).\n\\begin{table}\\caption{Incidence "
              "estimates by model.}\\label{tab:n}\\begin{tabular}{rr}"
              "4.13 & 6.20 \\\\ 3.52 & 5.08 \\\\\\end{tabular}\\end{table}\n")
    assert hits(doc) == []


# --- Word paragraphs ---------------------------------------------------------

def word(*paras) -> Document:
    out = [{"text": "Results", "style": "Heading 1"}]
    out += [p if isinstance(p, dict) else {"text": p} for p in paras]
    return Document.from_word(out)


def cap(text: str) -> dict:
    return {"text": text, "style": "Caption"}


def grid(rows: list[list[str]], number: int = 0, place: bool = True):
    out = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            p = {"text": text, "kind": "table"}
            if place:
                p["cell"] = [number, r, c]
            out.append(p)
    return out


WORD_ROWS = [["Age group", "Cases", "Incidence per 1,000"],
             ["Men", "", ""],
             ["18–29", "120", "4.13"],
             ["30–44", "80", "6.20"],
             ["Women", "", ""],
             ["18–29", "98", "3.52"],
             ["30–44", "75", "5.08"]]


def word_doc(sentence: str, place: bool = True) -> Document:
    return word(sentence, cap("Table 1. Incidence by sex and age group."),
                *grid(WORD_ROWS, place=place))


def test_word_cells_with_places_pass_a_rounded_value():
    assert hits(word_doc("Among women aged 18–29, the incidence was 3.5 per "
                         "1,000 (Table 1).")) == []


def test_word_cells_with_places_catch_a_swapped_row():
    (h,) = hits(word_doc("Among men aged 18–29, the incidence was 6.2 per "
                         "1,000 (Table 1)."))
    assert "row 'Men / 18–29'" in h.message
    assert "6.2 is in row 'Men / 30–44'" in h.message


def test_word_cells_with_places_catch_a_wrong_group():
    (h,) = hits(word_doc("Among women aged 18–29, the incidence was 4.1 per "
                         "1,000 (Table 1)."))
    assert "wrong group" in h.message


def test_word_cells_without_places_look_anywhere_in_the_table():
    # The add-in sends cells without their row and column: no grid, so a
    # number elsewhere in the table is accepted, as before.
    def doc(sentence, place):
        return word(sentence, cap("Table 1. Incidence by region."),
                    *grid([["Region", "Incidence"], ["North", "4.13"],
                           ["South", "6.20"]], place=place))
    swapped = "In the north, the incidence was 6.2 per 1,000 (Table 1)."
    assert len(hits(doc(swapped, place=True))) == 1
    assert hits(doc(swapped, place=False)) == []
    (h,) = hits(doc("In the north, the incidence was 6.9 per 1,000 "
                    "(Table 1).", place=False))
    assert h.message.startswith("6.9 is not in Table 1")


def test_word_unit_written_in_the_cell():
    doc = word("In the north, the incidence was 4.1 per 1,000 (Table 1).",
               cap("Table 1. Incidence by region."),
               *grid([["Region", "Incidence"],
                      ["North", "4.13 per 1,000"],
                      ["South", "6.20 per 1,000"]]))
    assert hits(doc) == []


def test_word_cells_of_a_nested_table_have_no_grid():
    cells = grid([["Region", "Incidence"], ["North", "4.13"]])
    cells += grid([["South", "6.20"]], number=1)
    doc = word("In the north, the incidence was 6.2 (Table 1).",
               cap("Table 1. Incidence by region."), *cells)
    assert hits(doc) == []


@pytest.mark.parametrize("bad", [[0, 1], [0, -1, 2], ["0", 1, 2], [0, 1, 2, 0],
                                 [True, 1, 2], "0,1,2", None])
def test_malformed_cell_places_are_ignored(bad):
    doc = Document.from_word([{"text": "4.13", "kind": "table", "cell": bad}])
    assert doc.table_cells == [] and doc.table_spans == [(0, 4)]


# --- an uploaded .docx ---------------------------------------------------------

def docx(sentence: str, rows: list[list[str]]) -> Document:
    body = (para("Results", style="berschrift1") + para(sentence) +
            para("Table 1. Incidence by region and age group.",
                 style="Beschriftung") + docx_table(rows))
    return load_bytes("paper.docx", docx_bytes(body))


DOCX_ROWS = [["Region", "Incidence"], ["North", "4.13"], ["South", "6.20"]]


def test_docx_cells_carry_their_row_and_column():
    doc = docx("In the north, the incidence was 4.1 (Table 1).", DOCX_ROWS)
    places = [c[3:] for c in doc.table_cells]
    assert places == [(0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 1),
                      (2, 0, 1), (2, 1, 1)]
    assert hits(doc) == []


def test_docx_swapped_row_fires():
    (h,) = hits(docx("In the north, the incidence was 6.2 (Table 1).",
                     DOCX_ROWS))
    assert "row 'North'" in h.message and "6.2 is in row 'South'" in h.message


def test_docx_merged_header_cell_spans_its_columns():
    span = ('<w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr>'
            + para("Women") + "</w:tc>")
    rows = ("<w:tbl><w:tblPr/>"
            "<w:tr><w:tc>" + para("") + "</w:tc>" + span.replace(
                "Women", "Men") + span + "</w:tr>")
    for cells in (["Region", "Cases", "Rate", "Cases", "Rate"],
                  ["North", "120", "4.13", "98", "3.52"],
                  ["South", "80", "6.20", "75", "5.08"]):
        rows += "<w:tr>" + "".join(f"<w:tc>{para(c)}</w:tc>"
                                   for c in cells) + "</w:tr>"
    rows += "</w:tbl>"
    body = (para("Results", style="berschrift1") +
            para("In the north, the rate among women was 4.1 (Table 1).") +
            para("Table 1. Cases and rates by region and sex.",
                 style="Beschriftung") + rows)
    doc = load_bytes("paper.docx", docx_bytes(body))
    (h,) = hits(doc)
    assert "column 'Women / Rate'" in h.message
    assert "column 'Men / Rate'" in h.message


def test_docx_cell_in_a_content_control_drops_the_tables_places():
    rows = ("<w:tbl><w:tblPr/><w:tr><w:tc>" + para("Region") + "</w:tc>"
            "<w:sdt><w:sdtContent><w:tc>" + para("Incidence") +
            "</w:tc></w:sdtContent></w:sdt></w:tr>"
            "<w:tr><w:tc>" + para("North") + "</w:tc><w:tc>" + para("4.13")
            + "</w:tc></w:tr></w:tbl>")
    body = (para("Results", style="berschrift1") + para("Some text.") + rows)
    doc = load_bytes("paper.docx", docx_bytes(body))
    assert doc.table_cells == [] and len(doc.table_spans) == 4


# --- plain text and Markdown have no tables here ------------------------------

def test_plain_text_tables_are_not_read():
    doc = Document.from_text(
        "Results\n\nIn the north, the incidence was 6.2 (Table 1).\n\n"
        "Table 1. Incidence by region.\n"
        "Region    Incidence\nNorth     4.13\nSouth     6.20\n", "plain")
    assert hits(doc) == []


def test_markdown_tables_are_not_read():
    doc = Document.from_text(
        "# Results\n\nIn the north, the incidence was 6.9 (Table 1).\n\n"
        "| Region | Incidence |\n|---|---|\n| North | 4.13 |\n"
        "| South | 6.20 |\n\nTable: Table 1. Incidence by region.\n",
        "markdown")
    assert hits(doc) == []


# --- the table reader -----------------------------------------------------------

def test_latex_grid_reads_spans_rules_and_markup():
    g = tables.latex_grid(
        "\\begin{table}\\caption{x}\\begin{tabular}{@{}l*{2}{r}@{}}\n"
        "\\toprule % a comment & with an ampersand\n"
        " & \\multicolumn{2}{c}{\\textbf{Incidence}} \\\\\n"
        "\\cmidrule(lr){2-3} Age & Rate\\textsuperscript{a} & 95\\% CI \\\\"
        "[2pt]\\midrule\n"
        "18--29 & $4.13$ & 3.21--5.02 \\\\ \\hline\n"
        "\\rowcolor{gray} 30--44 & \\num{6.20} & 5.10--7.31 \\\\\n"
        "\\bottomrule\\end{tabular}\\end{table}")
    assert [[(c.col, c.span, c.text) for c in r] for r in g.rows] == [
        [(0, 1, ""), (1, 2, "Incidence")],
        [(0, 1, "Age"), (1, 1, "Rate"), (2, 1, "95% CI")],
        [(0, 1, "18–29"), (1, 1, "4.13"), (2, 1, "3.21–5.02")],
        [(0, 1, "30–44"), (1, 1, "6.20"), (2, 1, "5.10–7.31")],
    ]
    t = tables.read(g)
    assert t.header_rows == [0, 1] and t.label_cols == [0]
    assert t.col_name == {1: "Incidence / Rate", 2: "Incidence / 95% CI"}


def test_longtable_keeps_one_header_and_drops_its_caption():
    g = tables.latex_grid(
        "\\begin{longtable}{lr}\\caption{Rates.}\\label{tab:l}\\\\"
        "Region & Rate \\\\ \\midrule\\endfirsthead "
        "Region & Rate \\\\ \\midrule\\endhead "
        "North & 4.13 \\\\ South & 6.20 \\\\\\end{longtable}")
    assert [[c.text for c in r] for r in g.rows] == [
        ["Region", "Rate"], ["North", "4.13"], ["South", "6.20"]]


@pytest.mark.parametrize("cell,text,ok", [
    ("4.13", "4.1", True), ("4.15", "4.2", True), ("4.25", "4.2", True),
    ("4.13", "4.13", True), ("4.1", "4.10", True), ("4.13", "4.2", False),
    ("4.13", "4.134", False), ("41.3%", "41%", True), ("0.43", "43%", False),
])
def test_rounding(cell, text, ok):
    (c,), (t,) = tables.numbers(cell), tables.numbers(text)
    assert tables.rounds_to(c, t) is ok


@pytest.mark.parametrize("label,keys", [
    ("Age group", {"age"}), ("18–29", {"18-29"}), ("Total", set()),
    ("Mean (SD)", set()), ("n (%)", set()), ("Women", {"women"}),
    ("Hospitalised cases*", {"hospitalised", "case"}),
    ("Incidence (per 1,000)", {"incidence"}), ("2", set()),
    ("2019", {"2019"}), ("≥65", {"≥65"}), ("65+", {"65+"}),
])
def test_label_keys(label, keys):
    assert tables.label_keys(label) == keys

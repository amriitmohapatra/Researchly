import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { Suggestion, TableEvidence as Evidence } from "@researchly/contract";
import { TableEvidence } from "@/components/TableEvidence";
import { SuggestionCard } from "@/components/SuggestionCard";
import { WordCard } from "@/components/word/WordCard";
import { DocumentView } from "@/components/DocumentView";
import { resolveSpans, segment } from "@/lib/segments";
import { baseId, cellHighlight, cellId, cellPlace, roundingNote } from "@/lib/table-evidence";
import { sugg } from "./helpers";

// Synthetic: "Mortality was 12.5% (Table 1)." then a two-arm table.
const TEXT = "Mortality was 12.5% (Table 1).\n\nOutcome | Treatment | Control\nMortality | 8.2 | 12.5";
const cellStart = TEXT.indexOf("8.2");

const EV: Evidence = {
  table: "Table 1",
  row: 1,
  column: 1,
  row_header: "Mortality",
  column_header: "Treatment",
  cell_start: cellStart,
  cell_end: cellStart + 3,
  cell_text: "8.2",
  expected: "8.2%",
  quoted: "12.5%",
  rounding: "",
};

function x401(extra: Partial<Suggestion> = {}): Suggestion {
  const at = TEXT.indexOf("12.5%");
  return sugg("x1", at, at + 5, "correction", {
    rule_id: "X401",
    text: "12.5%",
    message: "Table 1, row 'Mortality', column 'Treatment' holds 8.2%, not 12.5%.",
    table_evidence: EV,
    ...extra,
  });
}

describe("the table cell behind an X401 card", () => {
  it("names the place in the table's own words", () => {
    expect(cellPlace(EV)).toBe("Table 1, row “Mortality”, column “Treatment”");
    expect(cellPlace({ ...EV, row_header: "", column_header: "Rate" })).toBe("Table 1, column “Rate”");
  });

  it("says when the comparison allowed rounding, and nothing otherwise", () => {
    expect(roundingNote(EV)).toBeNull();
    expect(roundingNote({ ...EV, rounding: "rounded to 1 decimal place" })).toBe(
      "Compared rounded to 1 decimal place, so a rounded value would still match.",
    );
  });

  it("turns the cell into a highlight that maps back to its card", () => {
    const stand = cellHighlight(x401())!;
    expect(stand.id).toBe(cellId("x1"));
    expect(baseId(stand.id)).toBe("x1");
    expect(baseId("x1")).toBe("x1");
    const [r] = resolveSpans(TEXT, [stand]);
    expect(TEXT.slice(r!.start, r!.end)).toBe("8.2");
    expect(cellHighlight(x401({ table_evidence: null }))).toBeNull();
    expect(cellHighlight(x401({ table_evidence: { ...EV, cell_end: EV.cell_start } }))).toBeNull();
  });

  it("shows where the cell is, what it holds and what the sentence says", () => {
    const html = renderToStaticMarkup(<TableEvidence evidence={EV} />);
    expect(html).toContain("Table 1, row “Mortality”, column “Treatment”");
    expect(html).toContain("The table holds");
    expect(html).toContain("8.2%");
    expect(html).toContain("This sentence says");
    expect(html).toContain("12.5%");
    expect(html).not.toContain("Show the cell");
  });

  it("is on the website card, with Show the cell only when the cell can be placed", () => {
    const props = { active: false, placeable: true, onShowInText: () => {} };
    const withCell = renderToStaticMarkup(<SuggestionCard suggestion={x401()} {...props} onShowCell={() => {}} />);
    expect(withCell).toContain('data-testid="card-table-evidence"');
    expect(withCell).toContain("Show the cell");
    const noPlace = renderToStaticMarkup(<SuggestionCard suggestion={x401()} {...props} />);
    expect(noPlace).toContain('data-testid="card-table-evidence"');
    expect(noPlace).not.toContain("Show the cell");
    const plain = renderToStaticMarkup(<SuggestionCard suggestion={x401({ table_evidence: null })} {...props} />);
    expect(plain).not.toContain("card-table-evidence");
  });

  it("is on the Word card too", () => {
    const s = {
      ...x401(),
      location: { paragraph: 0, start: 14, end: 19, snippet: "12.5%", occurrence: 0, exact: true },
    };
    const html = renderToStaticMarkup(
      <WordCard suggestion={s} active={false} applied={false} busy={false} note={null} actions={null} onSelect={() => {}} onApply={() => {}} />,
    );
    expect(html).toContain('data-testid="card-table-evidence"');
    expect(html).toContain("8.2%");
  });

  it("outlines the cell in the text, apart from the findings", () => {
    const resolved = resolveSpans(TEXT, [x401(), cellHighlight(x401())!]);
    const html = renderToStaticMarkup(
      <DocumentView segments={segment(TEXT, resolved)} activeId="x1" onSelect={() => {}} />,
    );
    expect(html).toMatch(/class="hl hl-correction hl-cell[^"]*"[^>]*data-sids="x1~cell"/);
    expect(html).toMatch(/class="hl hl-correction is-active"[^>]*data-sids="x1"/);
  });
});

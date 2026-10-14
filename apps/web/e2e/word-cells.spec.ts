/**
 * X401 (Codex review #7): the hosted Word taskpane sends each table
 * paragraph's place, `cell: [table, row, col]`, so the engine can compare a
 * quoted number with the row and column a sentence names. The fake Office
 * reports cells as WordApi 1.3 does; anything uncertain (merged cells, a
 * nested table, an older Word, a failed read) sends no places for that
 * table, and the check goes ahead as before. The engine is mocked.
 */
import { expect, test, type Page } from "@playwright/test";
import type { FakeParagraph, FakeWordConfig } from "./fake-office";
import { ENGINE } from "./fixtures";
import { DOC, fakeOffice, mockWordEngine } from "./word-fixtures";

/** A cell paragraph (synthetic text) at `row`, `col` in a row of `of` cells. */
function cell(text: string, row: number, col: number, of: number, level = 1): FakeParagraph {
  return { text, tableNestingLevel: level, cell: { rowIndex: row, cellIndex: col, cellCount: of } };
}

/** The suite's document with its one-cell table replaced by a 2 x 2 table. */
const SIMPLE: FakeParagraph[] = [...DOC.slice(0, 4), cell("Region", 0, 0, 2), cell("Rate", 0, 1, 2), cell("North", 1, 0, 2), cell("8.2", 1, 1, 2)];

async function checkWith(page: Page, config: Partial<FakeWordConfig>) {
  await fakeOffice(page, config);
  const calls = await mockWordEngine(page, ENGINE);
  await page.goto("/word");
  await page.getByTestId("check-document").click();
  await expect(page.getByTestId("tp-results")).toBeVisible();
  expect(calls).toHaveLength(1);
  return calls[0]!.body.paragraphs;
}

test.describe("Word taskpane: table cell places", () => {
  test("WordApi 1.3: every table paragraph reaches the engine with its [table, row, col]; prose carries none", async ({ page }) => {
    const sent = await checkWith(page, { paragraphs: SIMPLE });
    expect(sent.slice(0, 4).every((p) => !("cell" in p))).toBe(true);
    expect(sent.slice(4)).toEqual([
      { text: "Region", style: "Normal", kind: "table", cell: [0, 0, 0] },
      { text: "Rate", style: "Normal", kind: "table", cell: [0, 0, 1] },
      { text: "North", style: "Normal", kind: "table", cell: [0, 1, 0] },
      { text: "8.2", style: "Normal", kind: "table", cell: [0, 1, 1] },
    ]);
  });

  test("merged cells and a nested table get no places; a plain table in the same document still does", async ({ page }) => {
    const sent = await checkWith(page, {
      paragraphs: [
        ...DOC.slice(0, 4),
        // Table 0: merged cells (the rows report 2 and 1 cells).
        cell("Region", 0, 0, 2),
        cell("Rate", 0, 1, 2),
        cell("All regions", 1, 0, 1),
        { text: "Between the tables.", styleBuiltIn: "Normal" },
        // Table 1: a table inside a cell.
        cell("Outer", 0, 0, 1),
        cell("Inner", 0, 0, 1, 2),
        { text: "And again.", styleBuiltIn: "Normal" },
        // Table 2: plain.
        cell("Age", 0, 0, 1),
        cell("12", 1, 0, 1),
      ],
    });
    expect(sent.map((p) => p.cell ?? null)).toEqual([null, null, null, null, null, null, null, null, null, null, null, [2, 0, 0], [2, 1, 0]]);
    expect(sent.filter((p) => p.kind === "table")).toHaveLength(7);
  });

  test("older Word (no WordApi 1.3): the same paragraphs go without places, and the check works", async ({ page }) => {
    const sent = await checkWith(page, { paragraphs: SIMPLE, api13: false });
    expect(sent).toHaveLength(SIMPLE.length);
    expect(sent.some((p) => "cell" in p)).toBe(false);
    expect(sent.slice(4).every((p) => p.kind === "table")).toBe(true);
    await expect(page.getByTestId("word-card").first()).toBeVisible();
  });

  test("Word failing to report cells: the check still goes, with no places", async ({ page }) => {
    const sent = await checkWith(page, { paragraphs: SIMPLE, failures: { cells: true } });
    expect(sent).toHaveLength(SIMPLE.length);
    expect(sent.some((p) => "cell" in p)).toBe(false);
  });
});

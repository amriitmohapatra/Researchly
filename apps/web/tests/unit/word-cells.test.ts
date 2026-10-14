/**
 * Table cell places for X401 (Codex review #7): which row and column each
 * table paragraph sits in, sent as `WordParagraph.cell`. Anything uncertain
 * sends no places for that table; the engine then checks the whole table.
 * The fake Office (e2e/fake-office.ts) reports cells as Word 1.3 does.
 */
import { describe, expect, it } from "vitest";
import { canPlaceCells, MAX_CELL_INDEX, readParagraphs, tablePlaces, type CellReport, type OfficeApi } from "@/lib/word/office";
import { installFakeOffice, type FakeParagraph, type FakeWordConfig } from "../../e2e/fake-office";

/** A cell paragraph: synthetic text, at `row`, `col` in a row of `of` cells. */
function cell(text: string, row: number, col: number, of: number, level = 1): FakeParagraph {
  return { text, tableNestingLevel: level, cell: { rowIndex: row, cellIndex: col, cellCount: of } };
}

/** A 2 x 2 table between two body paragraphs (synthetic). */
const DOC: FakeParagraph[] = [
  { text: "Incidence was 8.2 per 1000 in the north.", styleBuiltIn: "Normal" },
  cell("Region", 0, 0, 2),
  cell("Incidence", 0, 1, 2),
  cell("North", 1, 0, 2),
  cell("8.2", 1, 1, 2),
  { text: "Table 1: Incidence by region.", styleBuiltIn: "Caption" },
];

function fake(config: Partial<FakeWordConfig> = {}) {
  const target: Record<string, unknown> = {};
  const state = installFakeOffice(target, { paragraphs: DOC, ...config });
  target.Word = target.__fakeWordNamespace;
  return { api: target as unknown as OfficeApi, state };
}

const report = (level: number, row?: number, c?: number, cells?: number): CellReport => ({ level, row, cell: c, cells });

describe("tablePlaces (pure)", () => {
  it("numbers tables by runs of table paragraphs and places each cell", () => {
    expect(
      tablePlaces([report(0), report(1, 0, 0, 2), report(1, 0, 1, 2), report(0), report(1, 0, 0, 1), report(1, 1, 0, 1)]),
    ).toEqual([null, [0, 0, 0], [0, 0, 1], null, [1, 0, 0], [1, 1, 0]]);
  });

  it("gives several paragraphs in one cell the same place", () => {
    expect(tablePlaces([report(1, 0, 0, 1), report(1, 0, 0, 1)])).toEqual([
      [0, 0, 0],
      [0, 0, 0],
    ]);
  });

  it("merged cells (rows with different cell counts): no places for that table, the next table still placed", () => {
    expect(tablePlaces([report(1, 0, 0, 3), report(1, 1, 0, 2), report(0), report(1, 0, 0, 1)])).toEqual([
      null,
      null,
      null,
      [1, 0, 0],
    ]);
  });

  it("a nested table: no places for the whole run", () => {
    expect(tablePlaces([report(1, 0, 0, 1), report(2, 0, 0, 1), report(1, 1, 0, 1)])).toEqual([null, null, null]);
  });

  it("an unplaceable paragraph, a cell beyond its row, rows going backwards, non-integers: no places", () => {
    expect(tablePlaces([report(1, 0, 0, 2), report(1)])).toEqual([null, null]);
    expect(tablePlaces([report(1, 0, 2, 2)])).toEqual([null]);
    expect(tablePlaces([report(1, 1, 0, 1), report(1, 0, 0, 1)])).toEqual([null, null]);
    expect(tablePlaces([report(1, 0.5, 0, 1)])).toEqual([null]);
    expect(tablePlaces([report(1, -1, 0, 1)])).toEqual([null]);
  });

  it("stays within the contract's bound (a place beyond it would fail the whole request)", () => {
    expect(tablePlaces([report(1, MAX_CELL_INDEX, 0, 1)])).toEqual([[0, MAX_CELL_INDEX, 0]]);
    expect(tablePlaces([report(1, MAX_CELL_INDEX + 1, 0, 1)])).toEqual([null]);
  });

  it("no tables: all null", () => {
    expect(tablePlaces([report(0), report(0)])).toEqual([null, null]);
    expect(tablePlaces([])).toEqual([]);
  });
});

describe("readParagraphs with table cells", () => {
  it("WordApi 1.3: each table paragraph carries its [table, row, col]; body paragraphs carry none", async () => {
    const { api } = fake();
    const out = await readParagraphs(api);
    expect(out.map((p) => p.cell)).toEqual([undefined, [0, 0, 0], [0, 0, 1], [0, 1, 0], [0, 1, 1], undefined]);
    expect(out[4]).toEqual({ text: "8.2", style: "Normal", kind: "table", cell: [0, 1, 1] });
    expect(out[0]).toEqual({ text: DOC[0]!.text, style: "Normal", kind: "body" });
  });

  it("works without 1.4 (tracked changes) as long as 1.3 is there", async () => {
    const { api } = fake({ api14: false });
    expect(canPlaceCells(api)).toBe(true);
    expect((await readParagraphs(api)).map((p) => p.cell ?? null)).toEqual([null, [0, 0, 0], [0, 0, 1], [0, 1, 0], [0, 1, 1], null]);
  });

  it("older Word (no WordApi 1.3): paragraphs as before, no places, nothing asked of the cell API", async () => {
    const { api } = fake({ api13: false });
    expect(canPlaceCells(api)).toBe(false);
    const out = await readParagraphs(api);
    expect(out.every((p) => !("cell" in p))).toBe(true);
    expect(out.map((p) => p.kind)).toEqual(["body", "table", "table", "table", "table", "body"]);
  });

  it("merged cells: that table gets no places", async () => {
    const { api } = fake({ paragraphs: [cell("Region", 0, 0, 3), cell("Rate", 0, 1, 3), cell("Merged", 1, 0, 2)] });
    expect((await readParagraphs(api)).some((p) => "cell" in p)).toBe(false);
  });

  it("a nested table: no places for its outer table", async () => {
    const { api } = fake({ paragraphs: [cell("Outer", 0, 0, 1), cell("Inner", 0, 0, 1, 2)] });
    expect((await readParagraphs(api)).some((p) => "cell" in p)).toBe(false);
  });

  it("a table paragraph Word cannot place (a null cell): no places for that table, the other table still placed", async () => {
    const { api } = fake({
      paragraphs: [{ text: "Lost", tableNestingLevel: 1 }, cell("Kept", 0, 1, 2), { text: "Between." }, cell("Second", 0, 0, 1)],
    });
    expect((await readParagraphs(api)).map((p) => p.cell ?? null)).toEqual([null, null, null, [1, 0, 0]]);
  });

  it("Word failing to report cells: the paragraphs are still read and sent, with no places", async () => {
    const { api } = fake({ failures: { cells: true } });
    const out = await readParagraphs(api);
    expect(out).toHaveLength(DOC.length);
    expect(out.some((p) => "cell" in p)).toBe(false);
    expect(out[4]).toEqual({ text: "8.2", style: "Normal", kind: "table" });
  });

  it("a document without tables: as before, no places", async () => {
    const { api } = fake({ paragraphs: [DOC[0]!] });
    expect(await readParagraphs(api)).toEqual([{ text: DOC[0]!.text, style: "Normal", kind: "body" }]);
  });
});

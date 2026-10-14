import { expect, test } from "@playwright/test";
import type { Suggestion } from "@researchly/contract";
import { happyResponse } from "./fixtures";
import { check, json, mockEngine, paste } from "./helpers";

// Synthetic: a sentence quoting a value from the wrong arm of a small table.
const TEXT = "Mortality was 12.5% in the treatment arm (Table 1).\n\nOutcome & Treatment & Control\nMortality & 8.2 & 12.5\n";
const at = TEXT.indexOf("12.5%");
const cell = TEXT.indexOf("8.2");

const X401: Suggestion = {
  ...happyResponse.suggestions[0]!,
  id: "x401-1",
  rule_id: "X401",
  rule_name: "number-not-in-table",
  category: "correction",
  tier: "craft",
  span: { start: at, end: at + 5, line: 1, col: at + 1 },
  text: "12.5%",
  section: "unknown",
  message: "Table 1, row 'Mortality', column 'Treatment' holds 8.2%, not 12.5% — a value from the wrong column?",
  replacement: null,
  learn_ref: null,
  table_evidence: {
    table: "Table 1",
    row: 1,
    column: 1,
    row_header: "Mortality",
    column_header: "Treatment",
    cell_start: cell,
    cell_end: cell + 3,
    cell_text: "8.2",
    expected: "8.2%",
    quoted: "12.5%",
    rounding: "",
  },
};

test("an X401 card shows the cell it compared, and Show the cell outlines it in the text", async ({ page }) => {
  await mockEngine(page, (_r, route) =>
    json(route, 200, { ...happyResponse, suggestions: [X401], counts: { correction: 1, improvement: 0, convention: 0, preference: 0 } }),
  );
  await page.goto("/");
  await paste(page, TEXT);
  await check(page);

  const card = page.locator('[data-rule="X401"]');
  const box = card.getByTestId("card-table-evidence");
  await expect(box).toContainText("Table 1, row “Mortality”, column “Treatment”");
  await expect(box.getByTestId("table-expected")).toHaveText("8.2%");
  await expect(box.getByTestId("table-quoted")).toHaveText("12.5%");

  // No cell outline until asked for.
  const doc = page.getByTestId("document");
  await expect(doc.locator(".hl-cell")).toHaveCount(0);
  await box.getByTestId("show-cell").click();
  const outlined = doc.locator(".hl-cell");
  await expect(outlined).toHaveText("8.2");
  await expect(outlined).toBeFocused();

  // The cell stands for its card: choosing it in the text leads back there.
  await outlined.click();
  await expect(card).toBeFocused();

  // Show in text returns to the quoted number and drops the outline.
  await card.getByRole("button", { name: "Show in text" }).click();
  await expect(doc.locator(".hl-cell")).toHaveCount(0);
});

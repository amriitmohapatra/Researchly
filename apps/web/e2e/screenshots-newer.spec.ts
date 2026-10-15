/**
 * Design review screenshots of the newer surfaces (not assertions): the
 * revision queue, a card's table evidence, the reporting checklist with
 * its parts, and in the Word pane at 320px the checklist; light and dark,
 * 375 and 1366px.
 * Each logs every axe violation and any horizontal overflow. Synthetic
 * text only. Runs only with SCREENSHOTS=1; see screenshots-pages.spec.ts.
 */
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { AnalyzeResponse, Suggestion } from "@researchly/contract";
import { ENGINE, happyResponse, SAMPLE_TEXT } from "./fixtures";
import { check, json, mockEngine, paste } from "./helpers";
import { fakeOffice, mockWordEngine } from "./word-fixtures";

const DIR = process.env.SHOTS_DIR ?? "test-results/shots";
const P = process.env.SHOT_PREFIX ?? "page";
test.skip(!process.env.SCREENSHOTS, "set SCREENSHOTS=1 to capture design screenshots");

async function axeAll(page: Page, name: string) {
  const r = await new AxeBuilder({ page }).analyze();
  console.log(
    `AXE ${name}:`,
    r.violations
      .map((v) => `${v.id}/${v.impact}(${v.nodes.length}:${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")})`)
      .join("; ") || "none",
  );
}
async function overflow(page: Page, name: string) {
  const o = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  console.log(`OVERFLOW ${name}: ${o}`);
}

/** ASCII only, so the engine's code-point offsets equal JavaScript's. */
const QUEUE_TEXT = "Methods\nWe recieve weekly counts. The clinics recieve reports. In order to fit the model, we used Stan.\n";
function qsugg(id: string, word: string, from: number, extra: Partial<Suggestion> = {}): Suggestion {
  const start = QUEUE_TEXT.indexOf(word, from);
  return {
    id,
    rule_id: "S001",
    rule_name: "spelling",
    category: "correction",
    tier: "spelling",
    span: { start, end: start + word.length, line: 2, col: start - 7 },
    section: "methods",
    message: "Possible misspelling: “recieve”.",
    why: "A word not in the dictionary.",
    plain: "This word looks misspelled.",
    source: "Spelling dictionary",
    text: word,
    replacement: "receive",
    fix_safety: "review",
    confidence: 1,
    ...extra,
  };
}
const QUEUE_RESPONSE = {
  ...happyResponse,
  sections_detected: ["methods"],
  hidden_preferences: 0,
  suggestions: [
    qsugg("sp-1", "recieve", 0),
    qsugg("sp-2", "recieve", QUEUE_TEXT.indexOf("recieve") + 7),
    qsugg("w-1", "In order to", 0, {
      rule_id: "W202",
      rule_name: "wordy-phrase",
      category: "improvement",
      tier: "craft",
      message: "Wordy phrase: “in order to”.",
      replacement: "To",
    }),
  ],
} satisfies AnalyzeResponse;

const TABLE_TEXT = "Mortality was 12.5% in the treatment arm (Table 1).\n\nOutcome & Treatment & Control\nMortality & 8.2 & 12.5\n";
const tAt = TABLE_TEXT.indexOf("12.5%");
const tCell = TABLE_TEXT.indexOf("8.2");
const X401: Suggestion = {
  ...happyResponse.suggestions[0]!,
  id: "x401-1",
  rule_id: "X401",
  rule_name: "number-not-in-table",
  category: "correction",
  tier: "craft",
  span: { start: tAt, end: tAt + 5, line: 1, col: tAt + 1 },
  text: "12.5%",
  section: "unknown",
  message: "Table 1, row ‘Mortality’, column ‘Treatment’ holds 8.2%, not 12.5%: a value from the wrong column?",
  replacement: null,
  learn_ref: null,
  table_evidence: {
    table: "Table 1",
    row: 1,
    column: 1,
    row_header: "Mortality",
    column_header: "Treatment",
    cell_start: tCell,
    cell_end: tCell + 3,
    cell_text: "8.2",
    expected: "8.2%",
    quoted: "12.5%",
    rounding: "",
  },
};

for (const scheme of ["light", "dark"] as const) {
  for (const w of [375, 1366]) {
    test(`newer surfaces ${w} ${scheme}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
      await page.setViewportSize({ width: w, height: 900 });
      await mockEngine(page);
      // Registered after the default mock, so it answers first; anything else falls back to it.
      await page.route(`${ENGINE}/v1/analyze`, async (route) => {
        if (route.request().method() === "OPTIONS") return route.fallback();
        const body = route.request().postDataJSON() as { content: string };
        if (body.content.startsWith("Methods\nWe recieve")) return json(route, 200, QUEUE_RESPONSE);
        if (body.content.startsWith("Mortality"))
          return json(route, 200, { ...happyResponse, suggestions: [X401], counts: { correction: 1, improvement: 0, convention: 0, preference: 0 } });
        return route.fallback();
      });
      await page.goto("/");

      // The revision queue, one pass.
      await paste(page, QUEUE_TEXT);
      await check(page);
      await page.getByTestId("pass-correctness").click();
      await expect(page.getByTestId("queue")).toBeVisible();
      await page.screenshot({ path: `${DIR}/${P}-queue-${w}-${scheme}.png`, fullPage: true });
      await axeAll(page, `queue ${w} ${scheme}`);
      await overflow(page, `queue ${w}`);

      // A card with its table evidence.
      await paste(page, TABLE_TEXT);
      await check(page);
      const x401 = page.locator('[data-testid="suggestion-card"][data-rule="X401"]');
      await expect(x401).toBeVisible();
      await x401.screenshot({ path: `${DIR}/${P}-table-evidence-${w}-${scheme}.png` });
      await axeAll(page, `table evidence ${w} ${scheme}`);
      await overflow(page, `table evidence ${w}`);

      // The checklist and its parts.
      await paste(page, SAMPLE_TEXT);
      await check(page);
      await page.getByLabel("Reporting checklist").selectOption("epiforge");
      await expect(page.getByTestId("view-checklist")).toBeVisible();
      await page.getByTestId("view-checklist").click();
      await expect(page.getByTestId("checklist")).toBeVisible();
      await page.getByTestId("checklist").screenshot({ path: `${DIR}/${P}-checklist-${w}-${scheme}.png` });
      await axeAll(page, `checklist ${w} ${scheme}`);
      await overflow(page, `checklist ${w}`);
    });
  }

  test(`word checklist 320 ${scheme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await page.setViewportSize({ width: 320, height: 900 });
    const PARAS = [
      { text: "Methods", styleBuiltIn: "Heading1" },
      { text: "We report the confidence int", styleBuiltIn: "Normal" },
    ];
    await fakeOffice(page, { paragraphs: PARAS, cursor: 1 });
    await mockWordEngine(page, ENGINE);
    await page.goto("/word");
    await page.getByTestId("checklist-select").selectOption("strobe");
    await page.getByTestId("check-document").click();
    await expect(page.getByTestId("view-checklist")).toBeVisible();
    await page.getByTestId("view-checklist").click();
    await page.screenshot({ path: `${DIR}/${P}-word-checklist-320-${scheme}.png`, fullPage: true });
    await axeAll(page, `word checklist ${scheme}`);
    await overflow(page, `word checklist 320`);
  });
}

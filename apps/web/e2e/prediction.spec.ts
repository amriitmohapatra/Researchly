/**
 * Word prediction (2026-10-14) and the reading summary, on the build
 * without accounts. The engine is mocked; nothing is inserted unless the
 * writer presses Tab or clicks. Synthetic sentences only.
 */
import { expect, test } from "@playwright/test";
import type { CompleteRequest, CompleteResponse } from "@researchly/contract";
import { ENGINE, responseFor } from "./fixtures";
import { check, json, mockComplete, mockEngine, paste } from "./helpers";
import { fakeOffice, mockWordEngine, wordState } from "./word-fixtures";

/** Offers "interval"/"intervals" when the word before the cursor is "int"; nothing otherwise. */
function intervals(req: CompleteRequest): CompleteResponse {
  const cursor = req.cursor ?? Array.from(req.text).length;
  const before = Array.from(req.text).slice(0, cursor).join("");
  if (!before.endsWith("int")) return { status: "ok", candidates: [] };
  return {
    status: "ok",
    candidates: [
      { text: "interval", start: cursor - 3, end: cursor, kind: "word" },
      { text: "intervals", start: cursor - 3, end: cursor, kind: "word" },
    ],
  };
}

test.describe("word prediction on the website", () => {
  test("after a pause, the candidates show; Tab accepts the first, in code points, and typing goes on", async ({ page }) => {
    await mockEngine(page);
    const seen = await mockComplete(page, intervals);
    await page.goto("/");
    const editor = page.getByLabel("Text to check");
    await editor.click();
    await page.keyboard.type("😀 We report the confidence int");
    await expect(page.getByTestId("prediction-option").first()).toHaveText("interval");
    await expect(page.getByTestId("prediction-live")).toHaveText("Suggested: interval. Tab to accept. Also: intervals.");
    // The cursor is counted in code points: the emoji is one.
    expect(seen.at(-1)).toEqual({ text: "😀 We report the confidence int", cursor: 30, format: "plain", options: { limit: 3 } });

    await page.keyboard.press("Tab");
    await expect(editor).toHaveValue("😀 We report the confidence interval");
    await expect(editor).toBeFocused();
    await expect(page.getByTestId("prediction-option")).toHaveCount(0);
    await page.keyboard.type(" was wide");
    await expect(editor).toHaveValue("😀 We report the confidence interval was wide");
  });

  test("a click accepts any candidate; Esc dismisses; with nothing shown, Tab moves focus as usual", async ({ page }) => {
    await mockEngine(page);
    await mockComplete(page, intervals);
    await page.goto("/");
    const editor = page.getByLabel("Text to check");
    await editor.click();
    await page.keyboard.type("the confidence int");
    await page.getByTestId("prediction-option").nth(1).click();
    await expect(editor).toHaveValue("the confidence intervals");
    await expect(editor).toBeFocused();

    await page.keyboard.type(" and the int");
    await expect(page.getByTestId("prediction-option")).toHaveCount(2);
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("prediction-option")).toHaveCount(0);
    await page.keyboard.press("Tab");
    await expect(editor).toHaveValue("the confidence intervals and the int");
    await expect(editor).not.toBeFocused();
  });

  test("nothing is inserted by itself, and a moved caret drops the offer", async ({ page }) => {
    await mockEngine(page);
    await mockComplete(page, intervals);
    await page.goto("/");
    const editor = page.getByLabel("Text to check");
    await editor.click();
    await page.keyboard.type("the confidence int");
    await expect(page.getByTestId("prediction-option")).toHaveCount(2);
    await page.waitForTimeout(600);
    await expect(editor).toHaveValue("the confidence int");
    await page.keyboard.press("ArrowLeft");
    await expect(page.getByTestId("prediction-option")).toHaveCount(0);
  });

  test("switched off, nothing is asked for, and only the switch is remembered", async ({ page }) => {
    await mockEngine(page);
    const seen = await mockComplete(page, intervals);
    await page.goto("/");
    await page.getByTestId("prediction-switch").uncheck();
    const editor = page.getByLabel("Text to check");
    await editor.click();
    await page.keyboard.type("the confidence int");
    await page.waitForTimeout(600);
    expect(seen).toEqual([]);
    await expect(page.getByTestId("prediction-option")).toHaveCount(0);
    expect(await page.evaluate(() => Object.entries(localStorage))).toEqual([["researchly.prediction", "off"]]);
    await page.reload();
    await expect(page.getByTestId("prediction-switch")).not.toBeChecked();
  });

  test("a status other than ok shows nothing", async ({ page }) => {
    await mockEngine(page);
    await mockComplete(page, () => ({ status: "masked", candidates: [{ text: "interval", start: 0, end: 0, kind: "word" }] }));
    await page.goto("/");
    await page.getByLabel("Text to check").click();
    await page.keyboard.type("$x + int");
    await page.waitForTimeout(600);
    await expect(page.getByTestId("prediction-option")).toHaveCount(0);
  });
});

test.describe("the reading summary", () => {
  test("one quiet line under the heading: words checked and what was set aside", async ({ page }) => {
    await mockEngine(page, (req, route) =>
      json(route, 200, {
        ...responseFor(req),
        reading: {
          words_checked: 4210,
          set_aside: [
            { kind: "code", count: 2, label: "lines of code" },
            { kind: "other_language", count: 1, label: "paragraphs not in English" },
          ],
        },
      }),
    );
    await page.goto("/");
    await paste(page, "Methods\nWe fitted a renewal model.");
    await check(page);
    await expect(page.getByTestId("reading-summary")).toHaveText(
      "Checked 4,210 words. Set aside: 2 lines of code · 1 paragraph not in English.",
    );
  });
});

test.describe("Next words in the Word pane", () => {
  const PARAS = [
    { text: "Methods", styleBuiltIn: "Heading1" },
    { text: "We report the confidence int", styleBuiltIn: "Normal" },
  ];

  test("offers words for the cursor; a click inserts only the rest of the word; Hide turns it off", async ({ page }) => {
    await fakeOffice(page, { paragraphs: PARAS, cursor: 1, cursorAt: PARAS[1]!.text.length });
    await mockWordEngine(page, ENGINE);
    const seen = await mockComplete(page, intervals);
    await page.goto("/word");
    const panel = page.getByTestId("next-words");
    await expect(panel.getByTestId("next-word").first()).toHaveText("interval");
    expect(seen[0]).toEqual({ text: "We report the confidence int", cursor: 28, format: "plain", options: { limit: 3 } });
    // Nothing changed in the document until the click.
    expect((await wordState(page)).edits).toEqual([]);

    await panel.getByTestId("next-word").first().click();
    await expect.poll(async () => (await wordState(page)).paragraphs[1]!.text).toBe("We report the confidence interval");
    const state = await wordState(page);
    expect(state.edits).toEqual([expect.objectContaining({ before: "", text: "erval" })]);
    expect(state.trackingWrites).toEqual([]);

    await panel.getByTestId("next-words-hide").click();
    await expect(page.getByTestId("next-words")).toHaveCount(0);
    await page.getByTestId("tp-settings").locator("summary").click();
    await expect(page.getByTestId("tp-prediction-switch")).not.toBeChecked();
    await page.getByTestId("tp-prediction-switch").check();
    await expect(page.getByTestId("next-words")).toBeVisible();
  });
});

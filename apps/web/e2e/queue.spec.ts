import { expect, test } from "@playwright/test";
import type { AnalyzeResponse, Suggestion } from "@researchly/contract";
import { emptyResponse, ENGINE, happyResponse, SAMPLE_TEXT } from "./fixtures";
import { check, json, mockEngine, paste } from "./helpers";
import { fakeOffice, mockWordEngine, wordState } from "./word-fixtures";

/*
 * Review proposals 1 (the revision queue) and 8 (long documents), in the
 * browser. Invented text only.
 */

/** ASCII only, so the engine's code-point offsets equal JavaScript's. */
const REPEAT_TEXT =
  "Methods\nWe recieve weekly counts. The clinics recieve reports. Districts recieve none. In order to fit the model, we used Stan.\n";

function at(word: string, from = 0): { start: number; end: number } {
  const start = REPEAT_TEXT.indexOf(word, from);
  return { start, end: start + word.length };
}

function suggestion(id: string, span: { start: number; end: number }, extra: Partial<Suggestion>): Suggestion {
  return {
    id,
    rule_id: "S001",
    rule_name: "spelling",
    category: "correction",
    tier: "spelling",
    span: { ...span, line: 2, col: span.start - 7 },
    section: "methods",
    message: "Possible misspelling: “recieve”.",
    why: "A word not in the dictionary.",
    plain: "This word looks misspelled.",
    source: "Spelling dictionary",
    text: REPEAT_TEXT.slice(span.start, span.end),
    replacement: "receive",
    fix_safety: "review",
    confidence: 1,
    ...extra,
  };
}

const first = at("recieve");
const second = at("recieve", first.end);
const third = at("recieve", second.end);
const REPEAT_RESPONSE = {
  ...happyResponse,
  sections_detected: ["methods"],
  hidden_preferences: 0,
  suggestions: [
    suggestion("sp-1", first, {}),
    suggestion("sp-2", second, {}),
    suggestion("sp-3", third, {}),
    suggestion("w-1", at("In order to"), {
      rule_id: "W202",
      rule_name: "wordy-phrase",
      category: "improvement",
      tier: "craft",
      message: "Wordy phrase: “in order to”.",
      replacement: "To",
    }),
  ],
} satisfies AnalyzeResponse;

test.describe("revision queue", () => {
  test("a pass walks one issue at a time; repeats are one issue with their own Next and Previous", async ({ page }) => {
    await mockEngine(page, (_req, route) => json(route, 200, REPEAT_RESPONSE));
    await page.goto("/");
    await paste(page, REPEAT_TEXT);
    await check(page);
    await expect(page.getByRole("heading", { name: "4 suggestions" })).toBeVisible();

    await expect(page.getByTestId("pass-all")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("pass-correctness")).toContainText("3");
    await page.getByTestId("pass-correctness").click();
    const position = page.getByTestId("queue-position");
    await expect(position).toHaveText(/^Issue 1 of 1 in this pass\. Occurrence 1 of 3\./);
    await expect(position).toHaveAttribute("aria-live", "polite");
    await expect(page.getByTestId("queue-occurrences")).toContainText("Found 3 times in your text.");
    const doc = page.getByTestId("document");
    await expect(doc.locator("mark")).toHaveCount(3); // only this pass's findings are highlighted
    await expect(doc.locator('[data-sids~="sp-1"]')).toHaveClass(/is-active/);

    // Keyboard: Next occurrence, twice, then the end holds.
    await page.getByTestId("occ-next").focus();
    await page.keyboard.press("Enter");
    await expect(position).toHaveText(/Occurrence 2 of 3\./);
    await expect(doc.locator('[data-sids~="sp-2"]')).toHaveClass(/is-active/);
    await page.keyboard.press("Enter");
    await expect(position).toHaveText(/Occurrence 3 of 3\./);
    await page.keyboard.press("Enter");
    await expect(position).toHaveText(/Occurrence 3 of 3\./);
    await expect(page.getByTestId("occ-next")).toBeFocused(); // focus never lost at an end
    await expect(page.getByTestId("queue-end")).toContainText("Go on to Clarity next");

    // Dismissing the current card keeps the place: the occurrence before it takes over.
    await page.getByTestId("queue").getByTestId("dismiss").click();
    await expect(position).toHaveText(/Occurrence 2 of 2\./);
    await page.getByTestId("undo-dismiss").click();
    await expect(position).toHaveText(/Occurrence 3 of 3\./);

    await page.getByTestId("queue-next-pass").click();
    await expect(page.getByTestId("pass-clarity")).toHaveAttribute("aria-pressed", "true");
    await expect(position).toHaveText(/^Issue 1 of 1 in this pass\./);

    // Back to the list: everything as before.
    await page.getByTestId("pass-all").click();
    await expect(page.getByTestId("suggestion-card")).toHaveCount(4);
    await expect(page.getByTestId("filter-all")).toBeVisible();
  });
});

test.describe("revision queue in the Word pane", () => {
  test("the same queue, each step selecting the finding's words in Word", async ({ page }) => {
    await fakeOffice(page);
    await mockWordEngine(page, ENGINE);
    await page.goto("/word");
    await page.getByTestId("check-document").click();
    await expect(page.getByTestId("tp-results")).toBeVisible();
    await page.getByTestId("pass-correctness").click();
    const position = page.getByTestId("queue-position");
    // "‘the’ is repeated." twice (one issue), the spelling, and the other repeat with its own message.
    await expect(position).toHaveText(/^Issue 1 of 3 in this pass\. Occurrence 1 of 2\./);
    await page.getByTestId("occ-next").click();
    await expect(position).toHaveText(/Occurrence 2 of 2\./);
    await expect.poll(async () => (await wordState(page)).selection?.paragraph).toBe(3);
    await expect.poll(async () => (await wordState(page)).selection?.text.toLowerCase()).toBe("the the");
    await page.getByTestId("queue-next").click();
    await expect(position).toHaveText(/^Issue 2 of 3 in this pass\. ‘nowcasting’ is not in the dictionary\.$/); // the message is for screen readers
    await expect.poll(async () => (await wordState(page)).selection?.text).toBe("nowcasting");
    await page.getByTestId("pass-all").click();
    await expect(page.getByTestId("queue")).toHaveCount(0);
  });
});

test.describe("long checks", () => {
  test("previous results stay, marked; cancel returns to them; a late reply is dropped; retry shows the new answer", async ({ page }) => {
    let n = 0;
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    await mockEngine(page, async (_req, route) => {
      n++;
      if (n === 2) {
        // The cancelled check's reply comes back anyway, late, and must not be shown.
        await gate;
        await json(route, 200, emptyResponse);
        return;
      }
      await json(route, 200, n === 1 ? happyResponse : REPEAT_RESPONSE);
    });
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    const heading = page.locator("#results-heading");
    await expect(heading).toHaveText(`${happyResponse.suggestions.length} suggestions`);

    await paste(page, REPEAT_TEXT);
    await check(page);
    await expect(page.getByTestId("check-progress")).toBeVisible();
    await expect(page.getByTestId("check-progress")).toContainText("Time so far");
    await expect(page.getByTestId("previous-note")).toHaveAttribute("data-reason", "running");
    await expect(heading).toHaveText(`${happyResponse.suggestions.length} suggestions`);

    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByTestId("check-progress")).toHaveCount(0);
    await expect(page.getByTestId("cancelled-note")).toContainText("Check cancelled.");
    await expect(page.getByTestId("previous-note")).toHaveAttribute("data-reason", "cancelled");
    await expect(heading).toHaveText(`${happyResponse.suggestions.length} suggestions`);

    release();
    await page.waitForTimeout(300);
    await expect(heading).toHaveText(`${happyResponse.suggestions.length} suggestions`); // never "No suggestions"

    await page.getByTestId("retry-cancelled").click();
    await expect(heading).toHaveText("4 suggestions");
    await expect(page.getByTestId("previous-note")).toHaveCount(0);
    await expect(page.getByTestId("cancelled-note")).toHaveCount(0);
  });

  test("a long check says 'still checking' in a polite live region", async ({ page }) => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    await mockEngine(page, async (_req, route) => {
      await gate;
      await json(route, 200, happyResponse);
    });
    await page.clock.install();
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    await expect(page.getByTestId("check-progress")).toBeVisible();
    await page.clock.runFor(10_000);
    await expect(page.getByTestId("check-progress-live")).toHaveText(/^Still checking your text\./);
    await expect(page.getByTestId("check-elapsed")).toHaveText(/^1\d s$/);
    release();
    await expect(page.locator("#results-heading")).toHaveText(`${happyResponse.suggestions.length} suggestions`);
  });
});

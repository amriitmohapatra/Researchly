/**
 * Codex review #10: a word used again and again that no dictionary knows is
 * one grouped question, not a card per use. "Show where" walks every place
 * the word appears, on the website and in the Word taskpane. Build without
 * accounts (project "chromium"); the accounts spec covers Add to
 * dictionary. Synthetic text only.
 */
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { Suggestion, WordSuggestion } from "@researchly/contract";
import { ENGINE, happyResponse } from "./fixtures";
import { check, json, mockEngine, paste } from "./helpers";
import { fakeOffice, fulfillJson, mockWordEngine, wordResponseFor, wordState } from "./word-fixtures";

const TEXT = "Methods\nWe fitted numpyro models. The numpyro sampler ran quickly. Then numpyro stopped.\n";
const MESSAGE =
  "‘numpyro’ appears 3 times and isn’t in the dictionary. If it’s a term, add it to your dictionary; otherwise check its spelling.";

function places(text: string, needle: string): number[] {
  const out: number[] = [];
  for (let i = text.indexOf(needle); i >= 0; i = text.indexOf(needle, i + 1)) out.push(i);
  return out;
}
const AT = places(TEXT, "numpyro");

const QUESTION: Suggestion = {
  ...happyResponse.suggestions[0]!,
  id: "s003-numpyro",
  rule_id: "S003",
  rule_name: "repeated-unknown-word",
  category: "convention",
  tier: "spelling",
  section: "methods",
  span: { start: AT[0]!, end: AT[0]! + 7, line: 2, col: AT[0]! - 7 },
  text: "numpyro",
  message: MESSAGE,
  replacement: null,
  learn_ref: null,
  critical: false,
  occurrences: AT.map((a) => ({ start: a, end: a + 7, line: 2, col: a - 7 })),
};

const ANSWER = {
  ...happyResponse,
  suggestions: [QUESTION],
  counts: { correction: 0, improvement: 0, convention: 1, preference: 0 },
  hidden_preferences: 0,
};

async function axeSerious(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  return r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id);
}

test("the website: one question for every use, and Show where walks each place", async ({ page }) => {
  await mockEngine(page, (_r, route) => json(route, 200, ANSWER));
  await page.goto("/");
  await paste(page, TEXT);
  await check(page);

  await expect(page.getByRole("heading", { name: "1 suggestion" })).toBeVisible();
  const card = page.locator('[data-rule="S003"]');
  await expect(card.getByText(MESSAGE)).toBeVisible();
  await expect(card.getByRole("button", { name: "Show in text" })).toHaveCount(0);
  // Signed out on a build without accounts: no dictionary action and no sign-in note.
  await expect(card.getByTestId("add-word")).toHaveCount(0);
  await expect(card.getByTestId("dictionary-note")).toHaveCount(0);

  // Every use is underlined, each standing for the one card.
  const doc = page.getByTestId("document");
  const marks = doc.locator("mark.hl-convention");
  await expect(marks).toHaveCount(3);
  await expect(marks).toHaveText(["numpyro", "numpyro", "numpyro"]);

  await card.getByTestId("show-where").click();
  await expect(card.getByTestId("place-position")).toHaveText("Place 1 of 3");
  await expect(marks.nth(0)).toBeFocused();
  await expect(card.getByTestId("place-prev")).toHaveAttribute("aria-disabled", "true");

  await card.getByTestId("place-next").click();
  await expect(card.getByTestId("place-position")).toHaveText("Place 2 of 3");
  await expect(marks.nth(1)).toBeFocused();
  await card.getByTestId("place-next").click();
  await expect(card.getByTestId("place-position")).toHaveText("Place 3 of 3");
  await expect(marks.nth(2)).toBeFocused();
  await expect(card.getByTestId("place-next")).toHaveAttribute("aria-disabled", "true");
  await card.getByTestId("place-next").click({ force: true }); // announced unavailable, and held at the last place
  await expect(card.getByTestId("place-position")).toHaveText("Place 3 of 3");
  await card.getByTestId("place-prev").click();
  await expect(card.getByTestId("place-position")).toHaveText("Place 2 of 3");

  // All three light up with the card, and any one of them leads back to it.
  await expect(doc.locator("mark.is-active")).toHaveCount(3);
  await marks.nth(2).click();
  await expect(card).toBeFocused();

  expect(await axeSerious(page)).toEqual([]);
});

test("the website at 320px: the question and its buttons fit without sideways scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await mockEngine(page, (_r, route) => json(route, 200, ANSWER));
  await page.goto("/");
  await paste(page, TEXT);
  await check(page);
  const card = page.locator('[data-rule="S003"]');
  await card.getByTestId("show-where").click();
  await expect(card.getByTestId("place-next")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

/* ---------- Word ---------- */

const WORD_DOC = [
  { text: "Methods", styleBuiltIn: "Heading1" },
  { text: "We fitted numpyro models. The numpyro sampler ran.", styleBuiltIn: "Normal" },
  { text: "Results", styleBuiltIn: "Heading1" },
  { text: "Then numpyro stopped early.", styleBuiltIn: "Normal" },
];

function wordLoc(paragraph: number, occurrence: number) {
  const start = places(WORD_DOC[paragraph]!.text, "numpyro")[occurrence]!;
  return { paragraph, start, end: start + 7, snippet: "numpyro", occurrence, exact: true };
}

const WORD_PLACES = [wordLoc(1, 0), wordLoc(1, 1), wordLoc(3, 0)];
const WORD_QUESTION: WordSuggestion = {
  ...QUESTION,
  span: { start: 9 + WORD_PLACES[0]!.start, end: 9 + WORD_PLACES[0]!.end, line: 3, col: WORD_PLACES[0]!.start + 1 },
  location: WORD_PLACES[0]!,
  occurrence_locations: WORD_PLACES,
};

test("Word: Show where selects each use in the document in turn", async ({ page }) => {
  await fakeOffice(page, { paragraphs: WORD_DOC });
  await mockWordEngine(page, ENGINE, {
    respond: (body, route) =>
      fulfillJson(route, 200, { ...wordResponseFor(body), suggestions: [WORD_QUESTION], counts: { convention: 1 }, hidden_preferences: 0 }),
  });
  await page.goto("/word");
  await page.getByTestId("check-document").click();
  await expect(page.getByTestId("tp-results")).toBeVisible();

  const card = page.locator('[data-testid="word-card"][data-rule="S003"]');
  await expect(card.getByText(MESSAGE)).toBeVisible();
  await expect(card.getByTestId("select-in-document")).toHaveCount(0);

  await card.getByTestId("show-where").click();
  await expect.poll(async () => (await wordState(page)).selection).toMatchObject({ paragraph: 1, start: WORD_PLACES[0]!.start });
  await expect(card.getByTestId("place-position")).toHaveText("Place 1 of 3");
  await card.getByTestId("place-next").click();
  await expect.poll(async () => (await wordState(page)).selection).toMatchObject({ paragraph: 1, start: WORD_PLACES[1]!.start });
  await card.getByTestId("place-next").click();
  await expect.poll(async () => (await wordState(page)).selection).toMatchObject({ paragraph: 3, start: WORD_PLACES[2]!.start });
  await expect(card.getByTestId("place-position")).toHaveText("Place 3 of 3");
  await card.getByTestId("place-prev").click();
  await expect.poll(async () => (await wordState(page)).selection).toMatchObject({ paragraph: 1, start: WORD_PLACES[1]!.start });
});

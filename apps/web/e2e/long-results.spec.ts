/**
 * A long result (2026-10-14 performance pass). Cards off screen are not
 * laid out (globals.css, content-visibility), so the page below them is an
 * estimate: these pin that jumping between the text and the cards still
 * lands on the right one, and that the filter chips (whose list now follows
 * in a deferred render) still show what they say. The document is synthetic
 * (e2e/long-document.ts): ~12,000 words, ~360 cards.
 */
import { expect, test } from "@playwright/test";
import { json, mockEngine, paste, check } from "./helpers";
import { longDocument, longResponse } from "./long-document";

const { text, suggestions } = longDocument(12_000, 33);

test.describe("a long result", () => {
  test.beforeEach(async ({ page }) => {
    await mockEngine(page, async (_req, route) => json(route, 200, longResponse(suggestions)));
    await page.goto("/");
    await paste(page, text);
    await check(page);
    await expect(page.getByTestId("suggestion-card")).toHaveCount(suggestions.length);
  });

  test("a highlight near the end opens its card, focused and on screen", async ({ page }) => {
    const target = suggestions[suggestions.length - 3]!;
    await page.locator(`[data-testid="document"] mark[data-sids~="${target.id}"]`).click();
    const card = page.locator(`#card-${target.id}`);
    await expect(card).toBeFocused();
    await expect(card).toBeInViewport();
  });

  test("Show in text on the last card focuses its highlight, on screen", async ({ page }) => {
    const last = suggestions[suggestions.length - 1]!;
    await page.locator(`#card-${last.id}`).getByRole("button", { name: "Show in text" }).click();
    const mark = page.locator(`[data-testid="document"] mark[data-sids~="${last.id}"]`);
    await expect(mark).toBeFocused();
    await expect(mark).toBeInViewport();
  });

  test("a chip lists exactly its category, and All brings every card back", async ({ page }) => {
    const corrections = suggestions.filter((s) => s.category === "correction").length;
    await page.getByTestId("filter-correction").click();
    await expect(page.getByTestId("filter-correction")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("suggestion-card")).toHaveCount(corrections);
    await expect(page.locator('[data-testid="suggestion-card"]:not([data-category="correction"])')).toHaveCount(0);
    await page.getByTestId("filter-all").click();
    await expect(page.getByTestId("suggestion-card")).toHaveCount(suggestions.length);
  });
});

/**
 * Design review screenshots of every page the main spec does not cover
 * (not assertions): /learn, a lesson, /label, the brief and the map, a
 * card's lesson open, the composer at 1100px and the Word pane at 320px,
 * light and dark, at 375 and 1366px. Each logs every axe violation (all
 * impacts) and any horizontal overflow. Runs only with SCREENSHOTS=1:
 *   SCREENSHOTS=1 SHOTS_DIR=/some/dir SHOT_PREFIX=before npx playwright test screenshots
 */
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { happyResponse, SAMPLE_TEXT, ENGINE } from "./fixtures";
import { json, mockEngine, paste } from "./helpers";
import { fakeOffice, mockWordEngine, DEGRADED } from "./word-fixtures";

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

for (const scheme of ["light", "dark"] as const) {
  for (const w of [375, 1366]) {
    test(`learn ${w} ${scheme}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
      await page.setViewportSize({ width: w, height: 900 });
      await page.goto("/learn");
      await page.screenshot({ path: `${DIR}/${P}-learn-${w}-${scheme}.png`, fullPage: true });
      await axeAll(page, `learn ${w} ${scheme}`);
      await overflow(page, `learn ${w}`);
      await page.goto("/learn/hedging");
      await page.screenshot({ path: `${DIR}/${P}-lesson-${w}-${scheme}.png`, fullPage: true });
      await axeAll(page, `lesson ${w} ${scheme}`);
      await overflow(page, `lesson ${w}`);
    });

    test(`label ${w} ${scheme}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
      await page.setViewportSize({ width: w, height: 900 });
      await page.route(`${ENGINE}/v1/analyze`, async (route) => {
        if (route.request().method() === "OPTIONS")
          return route.fulfill({ status: 204, headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "content-type" } });
        return json(route, 200, happyResponse);
      });
      await page.goto("/label");
      await page.screenshot({ path: `${DIR}/${P}-label-idle-${w}-${scheme}.png`, fullPage: true });
      await page.getByTestId("label-paragraph").fill("We fitted a renewal model to weekly counts. It is clearly proven that the the intervention worked.");
      await page.getByTestId("label-check").click();
      await expect(page.getByTestId("label-card").first()).toBeVisible();
      await page.getByTestId("label-card").first().getByTestId("verdict-useful").click();
      await page.screenshot({ path: `${DIR}/${P}-label-${w}-${scheme}.png`, fullPage: true });
      await axeAll(page, `label ${w} ${scheme}`);
      await overflow(page, `label ${w}`);
    });

    test(`home idle+results ${w} ${scheme}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
      await page.setViewportSize({ width: w, height: 900 });
      await mockEngine(page);
      await page.goto("/");
      await page.screenshot({ path: `${DIR}/${P}-home-idle-${w}-${scheme}.png`, fullPage: true });
      await axeAll(page, `home idle ${w} ${scheme}`);
      await paste(page, SAMPLE_TEXT);
      await page.getByTestId("check").click();
      await expect(page.getByTestId("suggestion-card").first()).toBeVisible();
      await page.screenshot({ path: `${DIR}/${P}-home-results-${w}-${scheme}.png`, fullPage: true });
      await axeAll(page, `home results ${w} ${scheme}`);
      await overflow(page, `home results ${w}`);
      await page.getByTestId("view-brief").click();
      await page.screenshot({ path: `${DIR}/${P}-home-brief-${w}-${scheme}.png`, fullPage: true });
      await axeAll(page, `brief ${w} ${scheme}`);
      await page.getByRole("tab", { name: "Narrative map" }).click();
      await page.screenshot({ path: `${DIR}/${P}-home-map-${w}-${scheme}.png`, fullPage: true });
      await axeAll(page, `map ${w} ${scheme}`);
      await overflow(page, `map ${w}`);
    });
  }

  test(`card lesson open + composer 1100 ${scheme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await page.setViewportSize({ width: 1100, height: 900 });
    await mockEngine(page);
    await page.goto("/");
    await page.locator(".composer").screenshot({ path: `${DIR}/${P}-composer-1100-${scheme}.png` });
    await paste(page, SAMPLE_TEXT);
    await page.getByTestId("check").click();
    const card = page.getByTestId("suggestion-card").filter({ has: page.getByTestId("lesson") }).first();
    await card.getByTestId("lesson").getByText("The lesson").click();
    await card.screenshot({ path: `${DIR}/${P}-card-lesson-${scheme}.png` });
  });

  test(`word segment focus ${scheme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await page.setViewportSize({ width: 320, height: 900 });
    await fakeOffice(page);
    await mockWordEngine(page, ENGINE, { health: DEGRADED });
    await page.goto("/word");
    await expect(page.getByTestId("mode-revise")).toBeVisible();
    await page.getByTestId("mode-revise").focus();
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("ArrowRight");
    await page.locator(".tp-check").screenshot({ path: `${DIR}/${P}-word-segment-focus-${scheme}.png` });
  });

  test(`word 320 ${scheme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await page.setViewportSize({ width: 320, height: 900 });
    await fakeOffice(page);
    await mockWordEngine(page, ENGINE, { health: DEGRADED });
    await page.goto("/word");
    await page.screenshot({ path: `${DIR}/${P}-word-idle-320-${scheme}.png`, fullPage: true });
    await axeAll(page, `word idle ${scheme}`);
    await page.getByTestId("check-document").click();
    await expect(page.getByTestId("word-card").first()).toBeVisible();
    await page.getByTestId("tp-settings").locator("summary").click();
    await page.screenshot({ path: `${DIR}/${P}-word-results-320-${scheme}.png`, fullPage: true });
    await axeAll(page, `word results ${scheme}`);
    await overflow(page, `word 320`);
  });
}

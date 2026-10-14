/**
 * Design review screenshots for the build with accounts (not assertions):
 * Settings, /progress and the account menu, light and dark, at 375 and
 * 1366px, each with every axe violation logged. Runs only with SCREENSHOTS=1
 * (project "accounts"); see screenshots-pages.spec.ts.
 */
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockEngineAuth, mockSupabase, reply, seedSession } from "./supabase-mock";
import { RULES, signedInPaste } from "./accounts-fixtures";

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

const RECORDED = [
  { created_at: "2026-10-01T09:00:00Z", words: 500, document_type: "manuscript", counts: { G106: 4, S001: 1 } },
  { created_at: "2026-10-03T09:00:00Z", words: 1000, document_type: "manuscript", counts: { G106: 3, S001: 1, W202: 1 } },
  { created_at: "2026-10-05T09:00:00Z", words: 2000, document_type: "manuscript", counts: { G106: 2, S001: 2 } },
];

for (const scheme of ["light", "dark"] as const) {
  for (const w of [375, 1366]) {
    test(`settings+progress ${w} ${scheme}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
      await page.setViewportSize({ width: w, height: 900 });
      await seedSession(page);
      await mockSupabase(page, {
        settings: { disabled_rules: ["C120", "G101"], show_preferences: false, locale: "en-GB", keep_progress: true },
        words: ["Rt", "nowcasting"],
        progress: RECORDED,
      } as never);
      await mockEngineAuth(page, (_c, route) => reply(route, 200, signedInPaste), RULES);
      await page.goto("/settings");
      await expect(page.getByTestId("muted-rule").first()).toBeVisible();
      await page.screenshot({ path: `${DIR}/${P}-settings-${w}-${scheme}.png`, fullPage: true });
      await axeAll(page, `settings ${w} ${scheme}`);
      await page.goto("/progress");
      await expect(page.getByTestId("trend").first()).toBeVisible();
      await page.screenshot({ path: `${DIR}/${P}-progress-${w}-${scheme}.png`, fullPage: true });
      await axeAll(page, `progress ${w} ${scheme}`);
      await page.goto("/");
      await page.getByTestId("account-button").click();
      await page.screenshot({ path: `${DIR}/${P}-account-menu-${w}-${scheme}.png` });
      await axeAll(page, `home signed in ${w} ${scheme}`);
    });
  }
}

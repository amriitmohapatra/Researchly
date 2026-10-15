/**
 * S4d R4: underlines in the Word document, on the build without accounts
 * (project "chromium"). Word is the fake Office (e2e/fake-office.ts) with
 * its annotations model (WordApi 1.6 paragraph events, 1.7 underlines, 1.8
 * popups, each switchable); the engine's /v1/analyze-word and
 * /v1/check-paragraphs are mocked. The writer types, clicks, hovers and
 * uses the popup through the fake's hooks.
 */
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { FakeAnnotation, FakeWordConfig } from "./fake-office";
import { ENGINE } from "./fixtures";
import {
  DOC,
  fakeOffice,
  fulfillJson,
  liveResponseFor,
  mockLiveEngine,
  mockWordEngine,
  typeInWord,
  wordPointer,
  wordPopup,
  wordState,
} from "./word-fixtures";

const M365: Partial<FakeWordConfig> = { api16: true, api17: true, api18: true };
const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

/** What the document's underlines read, in document order: words and colour. */
async function underlines(page: Page): Promise<[string, string][]> {
  const s = await wordState(page);
  const order = new Map(s.paragraphs.map((p, i) => [p.uid, i]));
  return [...s.annotations]
    .sort((x, y) => order.get(x.paragraph)! - order.get(y.paragraph)! || x.start - y.start)
    .map((a) => [a.text, a.colorScheme]);
}

async function annotation(page: Page, text: string, nth = 0): Promise<FakeAnnotation> {
  const found = (await wordState(page)).annotations.filter((a) => a.text === text);
  if (!found[nth]) throw new Error(`no underline on "${text}" #${nth}`);
  return found[nth]!;
}

const INITIAL: [string, string][] = [
  ["In order to", "Blue"],
  ["The the", "Red"],
  ["nowcasting", "Red"],
  ["clearly proven", "Green"],
  ["the the", "Red"],
  ["the the", "Red"],
];

function card(page: Page, text: string | RegExp) {
  return page.getByTestId("word-card").filter({ hasText: text });
}

async function open(page: Page, config: Partial<FakeWordConfig> = M365) {
  await fakeOffice(page, config);
  const full = await mockWordEngine(page, ENGINE);
  const live = await mockLiveEngine(page, ENGINE);
  await page.goto("/word");
  return { full, live };
}

test.describe("Word: underlines in the document", () => {
  test("on opening, body paragraphs are checked under their headings and underlined by category; an edit is checked after a pause", async ({ page }) => {
    const { live, full } = await open(page);
    await expect.poll(() => underlines(page)).toEqual(INITIAL);
    // One request: the two body paragraphs, each with the heading above it; not headings, not the table cell.
    expect(live).toHaveLength(1);
    expect(live[0]!.body.paragraphs.map((p) => [p.text, p.style, p.heading])).toEqual([
      [DOC[1]!.text, "Normal", "Methods"],
      [DOC[3]!.text, "Normal", "Discussion"],
    ]);
    expect(live[0]!.body.paragraphs.every((p) => /^[A-Za-z0-9._:-]{1,64}$/.test(p.id))).toBe(true);
    expect(live[0]!.authorization).toBeUndefined();
    expect(full).toHaveLength(0); // the full check runs only on Check document
    // The popup: the category's title, the subtitle and the brand from the manifest; a revision only where it is safe.
    const wordy = await annotation(page, "In order to");
    expect(wordy.popup).toEqual({ branding: "RL.CritiqueBrand", title: "RL.CritiqueImprovement", subtitle: "RL.CritiqueSubtitle", suggestions: ["To"] });
    expect((await annotation(page, "clearly proven")).popup?.suggestions).toEqual([]);
    expect((await annotation(page, "nowcasting")).popup?.title).toBe("RL.CritiqueCorrection");

    // The pane: the state in the header, and the cards, each marked as in the text.
    await expect(page.getByTestId("status-mark")).toHaveAttribute("data-state", "issues");
    await expect(page.getByTestId("status-mark")).toContainText("6 suggestions");
    await expect(page.getByRole("heading", { name: "6 suggestions in the text" })).toBeVisible();
    await expect(page.getByTestId("word-card")).toHaveCount(6);
    await expect(page.getByTestId("in-the-text")).toHaveCount(6);

    // The writer edits the Discussion paragraph: nothing is sent while typing, then only that paragraph.
    await typeInWord(page, 3, "It is clearly proven that the effect was large.");
    await page.waitForTimeout(700);
    expect(live).toHaveLength(1);
    await expect.poll(() => live.length).toBe(2);
    expect(live[1]!.body.paragraphs.map((p) => [p.text, p.heading])).toEqual([["It is clearly proven that the effect was large.", "Discussion"]]);
    expect(live[1]!.body.revision).toBeGreaterThan(live[0]!.body.revision);
    await expect.poll(() => underlines(page)).toEqual(INITIAL.slice(0, 4));
    await expect(page.getByTestId("status-mark")).toContainText("4 suggestions");
    await expect(page.getByTestId("word-card")).toHaveCount(4);
  });

  test("clicking an underline opens its card in the pane; hovering one points to it", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 420 });
    await open(page);
    await expect.poll(() => underlines(page)).toEqual(INITIAL);
    const last = await annotation(page, "the the", 1);
    await wordPointer(page, "click", last.id);
    const target = card(page, "‘the’ is repeated.").last();
    await expect(target).toHaveClass(/is-active/);
    await expect(target).toBeInViewport();
    const wordy = await annotation(page, "In order to");
    await wordPointer(page, "hover", wordy.id);
    await expect(card(page, "In order to")).toHaveClass(/is-active/);
    await expect(card(page, "In order to")).toBeInViewport();
    // The pane never takes the keyboard from the document.
    expect(await page.evaluate(() => document.activeElement?.tagName)).toBe("BODY");
  });

  test("the popup's Accept applies the revision as a tracked change and the pane follows", async ({ page }) => {
    const { live } = await open(page);
    await expect.poll(() => underlines(page)).toEqual(INITIAL);
    const wordy = await annotation(page, "In order to");
    await wordPopup(page, wordy.id, "Accept", "To");
    await expect(card(page, "In order to").getByTestId("card-note")).toContainText("Applied as a tracked change");
    const s = await wordState(page);
    expect(s.edits).toEqual([{ paragraph: 1, start: 0, end: 11, before: "In order to", text: "To", tracked: true }]);
    expect(s.trackingMode).toBe("Off"); // the writer's setting, restored
    // The edited paragraph is checked again: its cards and underlines follow the new text.
    await expect.poll(() => live.length).toBe(2);
    await expect.poll(() => underlines(page)).toEqual(INITIAL.slice(1));
    await expect(page.getByTestId("status-mark")).toContainText("5 suggestions");
  });

  test("a revision Word made itself from the popup is recognised, not made twice", async ({ page }) => {
    await open(page, { ...M365, popupAppliesText: true });
    await expect.poll(() => underlines(page)).toEqual(INITIAL);
    const repeat = await annotation(page, "The the");
    await wordPopup(page, repeat.id, "Accept", "The");
    await expect(card(page, "‘the’ is repeated.").first().getByTestId("card-note")).toContainText("Applied in the document");
    const s = await wordState(page);
    expect(s.edits).toEqual([]);
    expect(s.paragraphs[1]!.text).toBe(DOC[1]!.text.replace("The the", "The"));
  });

  test("Apply in the pane on an underlined finding: the underline is accepted and the words replaced as a tracked change", async ({ page }) => {
    await open(page);
    await expect.poll(() => underlines(page)).toEqual(INITIAL);
    const repeat = card(page, "‘the’ is repeated.").nth(1);
    await expect(repeat.getByTestId("in-the-text")).toBeVisible();
    await repeat.getByTestId("apply-fix").click();
    await expect(repeat.getByTestId("card-note")).toContainText("Applied as a tracked change");
    const s = await wordState(page);
    expect(s.edits).toHaveLength(1);
    expect(s.edits[0]).toMatchObject({ paragraph: 3, before: "the the", text: "the", tracked: true });
    expect(s.annotations.filter((a) => a.text === "the the")).toHaveLength(1);
  });

  test("Reject in the popup and “Not an issue here” in the pane dismiss the finding and its underline; Show brings them back", async ({ page }) => {
    const { live } = await open(page);
    await expect.poll(() => underlines(page)).toEqual(INITIAL);
    await wordPopup(page, (await annotation(page, "clearly proven")).id, "Reject");
    await expect(card(page, "clearly proven")).toHaveCount(0);
    await expect(page.getByTestId("dismissed-note")).toContainText("1 suggestion dismissed while the pane is open.");
    await expect.poll(async () => (await underlines(page)).some(([t]) => t === "clearly proven")).toBe(false);

    await card(page, "nowcasting").getByTestId("dismiss").click();
    await expect(card(page, "nowcasting")).toHaveCount(0);
    await expect.poll(async () => (await underlines(page)).some(([t]) => t === "nowcasting")).toBe(false);
    await expect(page.getByTestId("status-mark")).toContainText("4 suggestions");
    await expect(page.getByTestId("dismissed-note")).toContainText("2 suggestions dismissed");
    // Nothing about a dismissal is stored or sent.
    expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);

    await page.getByTestId("show-dismissed").click();
    await expect(page.getByTestId("word-card")).toHaveCount(6);
    await expect.poll(() => live.length).toBe(2);
    await expect.poll(async () => (await underlines(page)).length).toBe(6);
  });

  test("a reply for text that changed while it was being checked is dropped; the new text is checked", async ({ page }) => {
    await fakeOffice(page, M365);
    await mockWordEngine(page, ENGINE);
    let release: () => void = () => undefined;
    const held = new Promise<void>((r) => (release = r));
    const live = await mockLiveEngine(page, ENGINE, {
      respond: async (req, route, n) => {
        if (n === 2) await held;
        await fulfillJson(route, 200, liveResponseFor(req));
      },
    });
    await page.goto("/word");
    await expect.poll(() => underlines(page)).toEqual(INITIAL);
    await typeInWord(page, 3, "It is the the same here.");
    await expect.poll(() => live.length).toBe(2);
    await expect(page.getByTestId("status-mark")).toHaveAttribute("data-state", "checking");
    await typeInWord(page, 3, "It is clearly proven here.");
    release();
    await expect.poll(() => live.length).toBe(3);
    expect(live[2]!.body.paragraphs.map((p) => p.text)).toEqual(["It is clearly proven here."]);
    await expect.poll(() => underlines(page)).toEqual([...INITIAL.slice(0, 3), ["clearly proven", "Green"]]);
    // The stale reply's "the the" never reached the document or the pane.
    await expect(card(page, "‘the’ is repeated.")).toHaveCount(1);
    await expect(page.getByTestId("status-mark")).toHaveAttribute("data-state", "issues");
  });

  test("Check document: sentence-level findings are underlined, document-wide ones stay in the pane", async ({ page }) => {
    await open(page);
    await expect.poll(() => underlines(page)).toEqual(INITIAL);
    await page.getByTestId("check-document").click();
    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();
    await expect
      .poll(async () => (await wordState(page)).annotations.map((a) => [a.text, a.colorScheme, a.popup?.suggestions]))
      .toEqual([
        ["In order to", "Blue", ["To"]],
        ["The the", "Red", []], // a revision to read first: Apply is in the pane
        ["nowcasting", "Red", []],
        ["clearly proven", "Green", []],
        ["the the", "Red", []],
        ["the the", "Red", []],
      ]);
    // The long sentence overlaps a correction, and the compound spelled two ways reads the whole document: no underline.
    await expect(card(page, "elsewhere in this document").getByTestId("in-the-text")).toHaveCount(0);
    await expect(card(page, "This sentence is long").getByTestId("in-the-text")).toHaveCount(0);
    await expect(card(page, "In order to").getByTestId("in-the-text")).toBeVisible();
    await expect(page.getByTestId("status-mark")).toContainText("8 suggestions");
  });

  test("an older Word (no WordApi 1.7): one quiet line in Settings, nothing drawn or sent live, Check works as before", async ({ page }) => {
    const { live } = await open(page, { api16: true });
    await page.getByTestId("tp-settings").locator("summary").click();
    await expect(page.getByTestId("underlines-unavailable")).toHaveText(
      "Underlines in the document need Word for Microsoft 365, version 16.79 or later. Suggestions still appear here in the pane.",
    );
    await expect(page.getByTestId("tp-live-underlines")).toHaveCount(0);
    await expect(page.getByTestId("status-mark")).toHaveCount(0);
    await page.getByTestId("check-document").click();
    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();
    await expect(page.getByTestId("status-mark")).toHaveAttribute("data-state", "issues");
    expect((await wordState(page)).annotations).toEqual([]);
    expect(live).toHaveLength(0);
  });

  test("a Word without Microsoft 365 (insertion refused): underlines off for the session, the pane as before", async ({ page }) => {
    const { live } = await open(page, { ...M365, failures: { annotations: "insert" } });
    await page.getByTestId("tp-settings").locator("summary").click();
    await expect(page.getByTestId("underlines-unavailable")).toBeVisible();
    expect((await wordState(page)).failedAnnotationInserts).toBeGreaterThan(0);
    await typeInWord(page, 3, "It is the the same.");
    await page.waitForTimeout(2_000);
    expect(live).toHaveLength(1);
    await page.getByTestId("check-document").click();
    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();
    await expect(page.getByTestId("in-the-text")).toHaveCount(0);
    expect((await wordState(page)).annotations).toEqual([]);
  });

  test("WordApi 1.7 without 1.8: underlines without the popup", async ({ page }) => {
    await open(page, { api16: true, api17: true });
    await expect.poll(() => underlines(page)).toEqual(INITIAL);
    expect((await wordState(page)).annotations.every((a) => a.popup === null)).toBe(true);
    expect((await wordState(page)).failedAnnotationInserts).toBe(0);
  });

  test("states: offline when the engine cannot be reached, then back by itself", async ({ page }) => {
    await fakeOffice(page, M365);
    await mockWordEngine(page, ENGINE);
    let down = true;
    const live = await mockLiveEngine(page, ENGINE, {
      respond: (req, route) =>
        down
          ? fulfillJson(route, 503, { error: { code: "unavailable", message: "The engine is starting." } })
          : fulfillJson(route, 200, liveResponseFor(req)),
    });
    await page.goto("/word");
    const mark = page.getByTestId("status-mark");
    await expect(mark).toHaveAttribute("data-state", "offline");
    await expect(mark).toContainText("Can’t check right now");
    expect((await wordState(page)).annotations).toEqual([]);
    down = false;
    await expect(mark).toHaveAttribute("data-state", "issues", { timeout: 10_000 });
    expect(live.length).toBeGreaterThanOrEqual(2);
    await expect.poll(() => underlines(page)).toEqual(INITIAL);
  });

  test("states: checked in part when a tier was down", async ({ page }) => {
    await fakeOffice(page, M365);
    await mockWordEngine(page, ENGINE);
    await mockLiveEngine(page, ENGINE, {
      respond: (req, route) =>
        fulfillJson(route, 200, {
          ...liveResponseFor(req),
          state: "partial",
          health: [{ tier: "grammar", label: "Grammar", ok: false, state: "error", detail: "", remedy: "" }],
        }),
    });
    await page.goto("/word");
    const mark = page.getByTestId("status-mark");
    await expect(mark).toHaveAttribute("data-state", "partial");
    await expect(mark).toContainText("Grammar was not checked");
  });

  test("Live underlines off: ours leave the document, the mark says paused, the choice is remembered", async ({ page }) => {
    const { live } = await open(page);
    await expect.poll(() => underlines(page)).toEqual(INITIAL);
    await page.getByTestId("tp-settings").locator("summary").click();
    const sw = page.getByTestId("tp-live-underlines");
    await expect(sw).toBeChecked();
    await sw.uncheck();
    await expect.poll(() => underlines(page)).toEqual([]);
    await expect(page.getByTestId("status-mark")).toHaveAttribute("data-state", "hidden");
    await expect(page.getByTestId("status-mark")).toContainText("Paused");
    expect(await page.evaluate(() => localStorage.getItem("researchly.word.underlines"))).toBe("off");
    await typeInWord(page, 3, "It is the the same.");
    await page.waitForTimeout(2_000);
    expect(live).toHaveLength(1);
    await page.reload();
    await page.getByTestId("tp-settings").locator("summary").click();
    await expect(page.getByTestId("tp-live-underlines")).not.toBeChecked();
    await page.waitForTimeout(500);
    expect((await wordState(page)).annotations).toEqual([]);
  });

  test("“This computer”: no live check there; Check document still draws the underlines", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("researchly.word.engine", "local"));
    await fakeOffice(page, M365);
    await mockWordEngine(page, "http://localhost:3517");
    const live = await mockLiveEngine(page, "http://localhost:3517");
    await page.goto("/word");
    await page.getByTestId("tp-settings").locator("summary").click();
    await expect(page.getByTestId("underlines-help")).toContainText("underlines appear after Check document");
    await page.waitForTimeout(500);
    expect(live).toHaveLength(0);
    await page.getByTestId("check-document").click();
    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();
    await expect.poll(async () => (await wordState(page)).annotations.length).toBe(6);
  });
});

test.describe("Word underlines: layout and accessibility", () => {
  for (const scheme of ["light", "dark"] as const) {
    test(`320px, ${scheme}: the header's state, underlined cards and Settings fit, no serious axe violations`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.setViewportSize({ width: 320, height: 700 });
      await open(page);
      await expect.poll(() => underlines(page)).toEqual(INITIAL);
      await expect(page.getByTestId("status-mark")).toHaveAttribute("data-state", "issues");
      await page.getByTestId("tp-settings").locator("summary").click();
      await expect(page.getByTestId("tp-live-underlines")).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      const r = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
      expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
      if (process.env.SCREENSHOTS) {
        // Viewport shots: cards off screen are skipped by content-visibility, so a full-page shot shows them blank.
        await page.getByTestId("word-card").first().scrollIntoViewIfNeeded();
        await page.screenshot({ path: `test-results/word-underlines-cards-${scheme}.png` });
        await page.getByTestId("tp-live-underlines").scrollIntoViewIfNeeded();
        await page.screenshot({ path: `test-results/word-underlines-settings-${scheme}.png` });
      }
    });
  }
});

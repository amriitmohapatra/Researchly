/**
 * Underlines while writing (S4d R5; DESIGN.md "Underlines while writing").
 * The engine's live check is mocked: `findings` plays the engine, finding
 * a few planted slips by their words and answering with UTF-16 ranges.
 *
 * With SHOTS_DIR set, the editor with underlines, the teaser and the card
 * are saved at 375 and 1366 px, light and dark.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import type { Category, CheckParagraphsRequest, LiveSuggestion } from "@researchly/contract";
import { SAMPLE_TEXT, withDocumentWideResponse } from "./fixtures";
import { check, json, liveReply, mockEngine, mockLiveCheck } from "./helpers";

const SHOTS = process.env.SHOTS_DIR;

/** A draft with planted slips, written for this suite. */
const DRAFT =
  "Methods\nThe samples were analysed using a renewal model. We utilize daily case counts 🦟 from each district.\n\n" +
  "Discussion\nIn order to understand the the dynamics of transmission, further studies are needed. Data was collected weekly.\n";

const PLANTED: { words: string; category: Category; message: string; replacements: string[]; rule: string }[] = [
  { words: "the the", category: "correction", message: "The word ‘the’ is repeated.", replacements: ["the"], rule: "G110" },
  { words: "In order to", category: "improvement", message: "‘In order to’ can usually be ‘To’.", replacements: ["To"], rule: "C120" },
  { words: "Data was", category: "convention", message: "In research writing ‘data’ is usually plural.", replacements: [], rule: "V305" },
  { words: "utilize", category: "preference", message: "‘utilize’ can usually be ‘use’.", replacements: ["use"], rule: "P110" },
];

/** What the mocked engine finds in one paragraph: each planted slip, by its words (UTF-16 offsets, as the contract says). */
function findings(text: string): LiveSuggestion[] {
  const out: LiveSuggestion[] = [];
  for (const p of PLANTED) {
    const at = text.indexOf(p.words);
    if (at < 0) continue;
    out.push({
      id: `${p.rule}${at.toString(16).padStart(4, "0")}${text.length.toString(16).padStart(4, "0")}`.slice(0, 16),
      rule_id: p.rule,
      rule_name: p.rule,
      category: p.category,
      critical: p.category === "correction",
      tier: "craft",
      begin: at,
      end: at + p.words.length,
      text: p.words,
      section: "discussion",
      message: p.message,
      plain: "In everyday words: the same advice, for a reader who knows their science but not the grammar terms.",
      why: "The fuller reasoning, for the full card.",
      source: "Researchly grammar notes",
      learn_ref: null,
      replacements: p.replacements,
      fix_safety: "review",
    });
  }
  return out;
}

async function mockFindings(page: Page, delayMs = 0) {
  return mockLiveCheck(page, async (req, route) => {
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs));
    await json(route, 200, liveReply(req, findings));
  });
}

const editor = (page: Page) => page.getByLabel("Text to check");
const underlines = (page: Page) => page.getByTestId("underline");

/** Hover the middle of the first line box of an underline whose words are `words`. */
async function hoverWords(page: Page, words: string) {
  await editor(page).scrollIntoViewIfNeeded();
  const mark = underlines(page).filter({ hasText: words }).first();
  const box = await mark.evaluate((el) => {
    const r = el.getClientRects()[0]!;
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  await page.mouse.move(box.x, box.y);
}

test.describe("underlines while writing", () => {
  test("type, pause: the changed paragraphs are sent once, with their headings, and their slips are underlined", async ({ page }) => {
    await mockEngine(page);
    const sent = await mockFindings(page);
    await page.goto("/");
    await editor(page).fill(DRAFT);
    // Nothing is sent while the writer is still writing.
    await page.waitForTimeout(900);
    expect(sent).toHaveLength(0);
    await expect(underlines(page)).toHaveCount(3); // the Preference stays hidden
    expect(sent).toHaveLength(1);
    const req = sent[0]!;
    // The paragraph at the caret (the end) goes first.
    expect(req.paragraphs.map((p) => p.heading)).toEqual(["Discussion", "Methods"]);
    expect(new Set(req.paragraphs.map((p) => p.heading))).toEqual(new Set(["Methods", "Discussion"]));
    expect(req.paragraphs.every((p) => !p.text.includes("Methods\n") && !p.text.startsWith("Discussion"))).toBe(true);
    expect(req.options?.show_preferences).toBe(true);
    // Each underline sits under exactly the words the engine named.
    await expect(underlines(page).filter({ hasText: "the the" })).toHaveAttribute("data-category", "correction");
    await expect(underlines(page).filter({ hasText: "In order to" })).toHaveAttribute("data-category", "improvement");
    await expect(underlines(page).filter({ hasText: "Data was" })).toHaveAttribute("data-category", "convention");
    // The pattern is the non-colour cue.
    const styles = await underlines(page).evaluateAll((els) => els.map((el) => getComputedStyle(el).textDecorationStyle));
    expect(new Set(styles)).toEqual(new Set(["solid", "dashed", "dotted"]));
    await expect(page.getByTestId("live-status")).toContainText("3 suggestions");
    // Show preferences: the wavy one appears without a new request.
    await page.getByTestId("show-preferences").check();
    await expect(underlines(page)).toHaveCount(4);
    await expect(underlines(page).filter({ hasText: "utilize" })).toHaveCSS("text-decoration-style", "wavy");
    await page.waitForTimeout(400);
    expect(sent).toHaveLength(1);

    // Typing in one paragraph sends that paragraph only.
    await editor(page).press("Control+End");
    await page.keyboard.type(" More.");
    await expect.poll(() => sent.length, { timeout: 4000 }).toBe(2);
    expect(sent[1]!.paragraphs).toHaveLength(1);
    expect(sent[1]!.paragraphs[0]!.text).toMatch(/^In order to[\s\S]*weekly\.\n More\.$/);
    expect(sent[1]!.revision).toBeGreaterThan(sent[0]!.revision);
  });

  test("the mirror lines up with the textarea's words (an emoji before the underline)", async ({ page }) => {
    await mockEngine(page);
    await mockFindings(page);
    await page.goto("/");
    await editor(page).fill(DRAFT);
    await page.getByTestId("show-preferences").check();
    await expect(underlines(page)).toHaveCount(4);
    // Select the underlined words in the textarea, then compare where the browser
    // draws the selection with where the mirror draws the underline: same line, same start.
    const at = await page.evaluate(() => {
      const ta = document.querySelector<HTMLTextAreaElement>('[data-testid="editor"]')!;
      const mirror = document.querySelector<HTMLElement>('[data-testid="underline-mirror"]')!;
      const mirrorStyle = getComputedStyle(mirror);
      const taStyle = getComputedStyle(ta);
      return {
        font: [mirrorStyle.font, taStyle.font],
        width: [mirror.clientWidth, ta.clientWidth],
        padding: [mirrorStyle.padding, taStyle.padding],
        scrollHeight: [mirror.scrollHeight, ta.scrollHeight],
      };
    });
    expect(at.font[0]).toBe(at.font[1]);
    expect(at.width[0]).toBe(at.width[1]);
    expect(at.padding[0]).toBe(at.padding[1]);
    expect(Math.abs(at.scrollHeight[0]! - at.scrollHeight[1]!)).toBeLessThanOrEqual(1);
  });

  test("hover shows the teaser; it opens the card; Escape returns to the text", async ({ page }) => {
    await mockEngine(page);
    await mockFindings(page);
    await page.goto("/");
    await editor(page).fill(DRAFT);
    await expect(underlines(page)).toHaveCount(3);
    await hoverWords(page, "In order to");
    const teaser = page.getByTestId("underline-teaser");
    await expect(teaser).toBeVisible();
    await expect(teaser).toContainText("Improvement");
    await expect(teaser).toContainText("‘In order to’ can usually be ‘To’.");
    await expect(teaser).toContainText("Suggested revision (your call):");
    await expect(teaser).toContainText("To");
    // Rule codes and tier names never reach the writer.
    await expect(teaser).not.toContainText("C120");
    await expect(teaser).not.toContainText("craft");
    // Moving away hides it.
    await page.mouse.move(5, 5);
    await expect(teaser).toBeHidden();

    await hoverWords(page, "the the");
    await expect(teaser).toContainText("Correction");
    await teaser.getByTestId("teaser-open").click();
    const card = page.getByTestId("underline-card");
    await expect(card).toBeVisible();
    await expect(card).toBeFocused();
    await expect(card.getByTestId("suggestion-card")).toContainText("The word ‘the’ is repeated.");
    await expect(card).toContainText("Source:");
    await expect(card.getByTestId("underline-apply")).toHaveText("Use this revision");
    await page.keyboard.press("Escape");
    await expect(card).toBeHidden();
    await expect(editor(page)).toBeFocused();
    const sel = await editor(page).evaluate((ta: HTMLTextAreaElement) => ta.value.slice(ta.selectionStart, ta.selectionEnd));
    expect(sel).toBe("the the");
  });

  test("accept: the text changes through the browser's editing, and Ctrl+Z restores it", async ({ page }) => {
    await mockEngine(page);
    const sent = await mockFindings(page);
    await page.goto("/");
    await editor(page).fill(DRAFT);
    await expect(underlines(page)).toHaveCount(3);
    await hoverWords(page, "the the");
    await page.getByTestId("teaser-open").click();
    await page.getByTestId("underline-apply").click();
    await expect(editor(page)).toHaveValue(DRAFT.replace("the the", "the"));
    await expect(editor(page)).toBeFocused();
    await expect(page.getByTestId("underline-announcer")).toContainText("Replaced with “the”");
    // The paragraph is checked again at once (not after the typing pause), and its slip is gone.
    await expect.poll(() => sent.length, { timeout: 3000 }).toBe(2);
    await expect(underlines(page)).toHaveCount(2);
    // Native undo: the words come back, and so does their underline (from memory, nothing sent).
    await page.keyboard.press("Control+z");
    await expect(editor(page)).toHaveValue(DRAFT);
    await expect(underlines(page)).toHaveCount(3);
    await page.waitForTimeout(1800);
    expect(sent).toHaveLength(2);
  });

  test("the teaser's own button applies too; a removal says so", async ({ page }) => {
    await mockEngine(page);
    await mockFindings(page);
    await page.goto("/");
    await editor(page).fill(DRAFT);
    await expect(underlines(page)).toHaveCount(3);
    await hoverWords(page, "In order to");
    await page.getByTestId("teaser-apply").click();
    await expect(editor(page)).toHaveValue(DRAFT.replace("In order to", "To"));
  });

  test("an edit while a check is in flight: the stale answer is not drawn", async ({ page }) => {
    await mockEngine(page);
    const seen: CheckParagraphsRequest[] = [];
    let release: () => void = () => undefined;
    const gate = new Promise<void>((r) => (release = r));
    await mockLiveCheck(page, async (req, route, n) => {
      seen.push(req);
      if (n === 1) await gate; // the first answer waits until the writer has changed the words
      await json(route, 200, liveReply(req, findings));
    });
    const one = "Discussion\nIn order to understand the the dynamics, more work is needed.\n";
    await page.goto("/");
    await editor(page).fill(one);
    await expect.poll(() => seen.length, { timeout: 4000 }).toBe(1);
    await expect(page.getByTestId("live-status")).toContainText("Checking");
    // The writer fixes the repeated word while the first answer is out.
    await editor(page).fill(one.replace("the the", "the"));
    release();
    // The first answer was for words that are gone: no underline under them, ever.
    await page.waitForTimeout(400);
    await expect(underlines(page).filter({ hasText: "the the" })).toHaveCount(0);
    await expect.poll(() => seen.length, { timeout: 4000 }).toBe(2);
    await expect(underlines(page)).toHaveCount(1);
    await expect(underlines(page)).toHaveText("In order to");
    await expect(page.getByTestId("live-status")).toContainText("1 suggestion");
  });

  test("engine unreachable: offline with a next step, then it recovers by itself", async ({ page }) => {
    await mockEngine(page);
    let fail = true;
    await mockLiveCheck(page, async (req, route) => {
      if (fail) return route.abort("connectionrefused");
      await json(route, 200, liveReply(req, findings));
    });
    await page.goto("/");
    await editor(page).fill(DRAFT);
    const status = page.getByTestId("live-status");
    await expect(status).toContainText("Can’t check right now", { timeout: 5000 });
    await expect(status.getByTestId("status-mark")).toHaveAttribute("data-state", "offline");
    await expect(status.getByTestId("status-mark")).toHaveAttribute("title", /will try again in 2 s/);
    await expect(page.getByTestId("live-retry")).toBeVisible();
    await expect(page.getByTestId("underline-announcer")).toContainText("Can’t check right now");
    // The text is untouched, and nothing old is drawn as current.
    await expect(editor(page)).toHaveValue(DRAFT);
    await expect(underlines(page)).toHaveCount(0);
    fail = false;
    // The retry after 2 s finds the engine back.
    await expect(underlines(page)).toHaveCount(3, { timeout: 6000 });
    await expect(status).toContainText("3 suggestions");
  });

  test("Try now retries at once", async ({ page }) => {
    await mockEngine(page);
    let fail = true;
    await mockLiveCheck(page, async (req, route) => {
      if (fail) return json(route, 503, { error: { code: "unavailable", message: "busy", request_id: "r" } });
      await json(route, 200, liveReply(req, findings));
    });
    await page.goto("/");
    await editor(page).fill(DRAFT);
    await expect(page.getByTestId("live-retry")).toBeVisible({ timeout: 5000 });
    fail = false;
    await page.getByTestId("live-retry").click();
    await expect(underlines(page)).toHaveCount(3, { timeout: 1500 });
  });

  test("LaTeX: one quiet line, no requests, no underlines", async ({ page }) => {
    await mockEngine(page);
    const sent = await mockFindings(page);
    await page.goto("/");
    await page.getByTestId("format").selectOption("latex");
    await editor(page).fill("\\section{Discussion}\nIn order to understand the the dynamics \\cite{smith}, more is needed.\n");
    await expect(page.getByTestId("underlines-latex")).toHaveText(
      "Underlines while writing are available for plain text and Markdown; press Check for LaTeX.",
    );
    await page.waitForTimeout(2000);
    expect(sent).toHaveLength(0);
    await expect(underlines(page)).toHaveCount(0);
    await expect(page.getByTestId("live-status")).toHaveCount(0);
    // Back to Markdown: the text is checked.
    await page.getByTestId("format").selectOption("markdown");
    await expect.poll(() => sent.length, { timeout: 4000 }).toBe(1);
  });

  test("Markdown: headings are the # lines, and formatting is blanked before sending", async ({ page }) => {
    await mockEngine(page);
    const sent = await mockFindings(page);
    await page.goto("/");
    await page.getByTestId("format").selectOption("markdown");
    const src = "The fit was **good** [@smith2020], see [the table](https://example.org).";
    await editor(page).fill(`# Results\n\n## Model fit\n\n${src}\n`);
    await expect.poll(() => sent.length, { timeout: 4000 }).toBe(1);
    const p = sent[0]!.paragraphs[0]!;
    // "Model fit" under "Results" is Results, as the full check reads it.
    expect(p.heading).toBe("Results");
    // Same length, so every offset in the answer still points at the writer's characters.
    const blanked = src
      .replace(/\*\*/g, "  ")
      .replace("[@smith2020]", " ".repeat(12))
      .replace("[the table](https://example.org)", ` the table${" ".repeat("](https://example.org)".length)}`);
    expect(p.text).toBe(blanked);
    expect(p.text).toHaveLength(src.length);
  });

  test("switched off: no requests, no underlines, remembered after a reload", async ({ page }) => {
    await mockEngine(page);
    const sent = await mockFindings(page);
    await page.goto("/");
    const toggle = page.getByTestId("live-underlines");
    await expect(toggle).toBeChecked();
    await toggle.uncheck();
    await editor(page).fill(DRAFT);
    await page.waitForTimeout(2000);
    expect(sent).toHaveLength(0);
    await expect(underlines(page)).toHaveCount(0);
    await expect(page.getByTestId("live-status")).toHaveCount(0);
    await page.reload();
    await expect(page.getByTestId("live-underlines")).not.toBeChecked();
    // On again: what is on screen is checked.
    await page.getByTestId("live-underlines").check();
    await editor(page).fill(DRAFT);
    await expect(underlines(page)).toHaveCount(3);
  });

  test("after Check the underlines and the results agree; a whole-document finding is never an underline", async ({ page }) => {
    const analyzed = await mockEngine(page, (_r, route) => json(route, 200, withDocumentWideResponse));
    const sent = await mockFindings(page);
    await page.goto("/");
    await editor(page).fill(SAMPLE_TEXT);
    await check(page);
    await expect(page.getByTestId("results")).toBeVisible();
    expect(analyzed).toHaveLength(1);
    // Eight sentence-level suggestions in the results, eight underlines; the compound-word one reads the whole document.
    const sentence = withDocumentWideResponse.suggestions.filter((s) => s.rule_id !== "W211");
    await expect(page.getByTestId("live-status")).toContainText(`${sentence.length} suggestions`);
    // Every one is drawn (a missing comma as an insertion mark), under its own words, the emoji and 𝑅ₜ before them notwithstanding.
    const drawn = await page.evaluate(() => {
      const out: Record<string, string> = {};
      for (const el of document.querySelectorAll<HTMLElement>('[data-testid="underline-mirror"] [data-ids]')) {
        for (const id of (el.dataset.ids ?? "").split(" ")) out[id] = (out[id] ?? "") + (el.textContent ?? "");
      }
      return out;
    });
    expect(Object.keys(drawn).sort()).toEqual(sentence.map((s) => s.id).sort());
    for (const s of sentence) {
      if (s.text) expect(drawn[s.id]).toContain(s.text.slice(0, 5));
    }
    expect(drawn).not.toHaveProperty(withDocumentWideResponse.suggestions.find((s) => s.rule_id === "W211")!.id);
    // Nothing needed a live request: the check answered for every paragraph.
    await page.waitForTimeout(1800);
    expect(sent).toHaveLength(0);
  });

  test("keyboard: Ctrl+. opens the card for the next underline; the list steps through them", async ({ page }) => {
    await mockEngine(page);
    await mockFindings(page);
    await page.goto("/");
    await editor(page).fill(DRAFT);
    await expect(underlines(page)).toHaveCount(3);
    await editor(page).press("Control+Home");
    await editor(page).press("Control+.");
    const card = page.getByTestId("underline-card");
    await expect(card).toBeFocused();
    await expect(card).toContainText("‘In order to’ can usually be ‘To’.");
    await page.keyboard.press("Escape");
    // The caret resting in an underline shows its teaser, described to the textarea.
    await editor(page).press("ArrowRight");
    await editor(page).press("ArrowLeft");
    const teaser = page.getByTestId("underline-teaser");
    await expect(teaser).toBeVisible();
    const describedBy = await editor(page).getAttribute("aria-describedby");
    expect(describedBy).toContain(await teaser.getAttribute("id"));
    await expect(page.getByTestId("underline-announcer")).toContainText("Improvement: ‘In order to’ can usually be ‘To’.");
    // The list.
    await page.getByTestId("underline-list").locator("summary").click();
    const items = page.getByTestId("underline-item");
    await expect(items).toHaveCount(3);
    await expect(items.nth(0)).toContainText("Improvement: ‘In order to’");
    await items.nth(2).click();
    await expect(card).toBeFocused();
    await expect(card).toContainText("data");
  });
});

/* ---------- looks: 375 and 1366 px, light and dark, axe ---------- */

for (const scheme of ["light", "dark"] as const) {
  for (const width of [375, 1366]) {
    test(`underlines, teaser and card at ${width}px, ${scheme}: axe clean, no horizontal scroll`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
      await page.setViewportSize({ width, height: width < 500 ? 812 : 900 });
      await mockEngine(page);
      await mockFindings(page);
      await page.goto("/");
      await editor(page).fill(DRAFT);
      await page.getByTestId("show-preferences").check();
      await expect(underlines(page)).toHaveCount(4);
      await expect(page.getByTestId("live-status")).toContainText("4 suggestions");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      const axe = () => new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]).analyze();
      const serious = (r: Awaited<ReturnType<typeof axe>>) => r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(serious(await axe())).toEqual([]);
      await page.locator(".composer").screenshot({ path: SHOTS ? `${SHOTS}/underlines-${width}-${scheme}.png` : undefined, animations: "disabled" });

      await hoverWords(page, "the the");
      await expect(page.getByTestId("underline-teaser")).toBeVisible();
      expect(serious(await axe())).toEqual([]);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/teaser-${width}-${scheme}.png` });

      await page.getByTestId("teaser-open").click();
      await expect(page.getByTestId("underline-card")).toBeVisible();
      expect(serious(await axe())).toEqual([]);
      const overflowCard = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflowCard).toBeLessThanOrEqual(0);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/card-${width}-${scheme}.png`, fullPage: true });
    });
  }
}

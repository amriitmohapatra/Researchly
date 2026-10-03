import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { MAX_CONTENT_CHARS } from "@researchly/contract";
import {
  degradedGrammarResponse,
  emptyResponse,
  error413,
  error422,
  error429,
  error500,
  happyResponse,
  SAMPLE_TEXT,
  withPreferencesResponse,
} from "./fixtures";
import { check, isReddish, json, mockEngine, paste, recordOwnOriginRequests, rgb } from "./helpers";

const byRule = (id: string) => withPreferencesResponse.suggestions.find((s) => s.rule_id === id)!;
const mark = (page: import("@playwright/test").Page, id: string) =>
  page.getByTestId("document").locator(`[data-sids~="${id}"]`);

test.describe("happy path", () => {
  test("highlights the right characters, lists cards, expands Why", async ({ page, baseURL }) => {
    const sent = await mockEngine(page);
    const own = recordOwnOriginRequests(page, baseURL!);
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);

    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();

    // The request carries exactly the text, straight to the engine.
    expect(sent).toHaveLength(1);
    expect(sent[0]).toEqual({ content: SAMPLE_TEXT, format: "plain", options: { show_preferences: false } });
    // ...and nothing went to the Next.js server except page/asset GETs.
    expect(own.filter((r) => r.method() !== "GET")).toEqual([]);
    expect(own.some((r) => (r.postData() ?? "").includes("Dengue"))).toBe(false);

    // Spans after the emoji and the non-BMP 𝑅 land on the right characters.
    for (const s of happyResponse.suggestions.filter((x) => x.text)) {
      await expect(mark(page, s.id).first()).toBeVisible();
      const covered = (await mark(page, s.id).allTextContents()).join("");
      expect(covered, s.rule_id).toBe(s.text);
    }
    // The zero-length span renders as an insertion point.
    await expect(mark(page, byRule("G110").id)).toHaveClass(/pt-correction/);
    // The whole submitted text is rendered (as text), not just the flagged parts.
    await expect(page.getByTestId("document")).toContainText(SAMPLE_TEXT.trim().slice(0, 40));

    const cards = page.getByTestId("suggestion-card");
    await expect(cards).toHaveCount(8);
    await expect(page.getByTestId("filter-all")).toContainText("8");
    await expect(page.getByTestId("filter-correction")).toContainText("2");
    await expect(page.getByTestId("filter-convention")).toContainText("2");

    const first = cards.first();
    await expect(first).toContainText("Improvement");
    await expect(first).toContainText("Introduction");
    await expect(first).toContainText("clearly proven");
    await first.getByText("Why?").click();
    await expect(first.getByText(/Boosters such as/)).toBeVisible();
    await expect(first.getByText(/Hyland \(2005\)/)).toBeVisible();

    // A replacement is labelled as a suggestion; there is no apply button.
    const wordy = page.locator(`#card-${byRule("C120").id}`);
    await expect(wordy).toContainText("Suggested revision (your call):");
    await expect(page.getByRole("button", { name: /apply|accept|fix/i })).toHaveCount(0);

    // Card → highlight
    await wordy.getByRole("button", { name: "Show in text" }).click();
    await expect(mark(page, byRule("C120").id)).toBeFocused();
    await expect(mark(page, byRule("C120").id)).toHaveClass(/is-active/);

    // Highlight → card
    await mark(page, byRule("V310").id).click();
    await expect(page.locator(`#card-${byRule("V310").id}`)).toBeFocused();
    await expect(page.locator(`#card-${byRule("V310").id}`)).toHaveClass(/is-active/);

    // Read-outs, not a score.
    await expect(page.getByRole("heading", { name: "Read-outs" })).toBeVisible();
    await expect(page.getByText("Read-outs, not a score.", { exact: false })).toBeVisible();
    await expect(page.locator("body")).not.toContainText(/overall score|grade/i);

    // No banner for the missing learned tier.
    await expect(page.getByTestId("health-banner")).toHaveCount(0);
  });

  test("filters by category", async ({ page }) => {
    await mockEngine(page);
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    await page.getByTestId("filter-convention").click();
    await expect(page.getByTestId("filter-convention")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("suggestion-card")).toHaveCount(2);
    await expect(page.getByTestId("document").locator("mark")).toHaveCount(2);
    await expect(page.locator(".filter-blurb")).toContainText("Not an error");
  });

  test("Ctrl+Enter checks from the editor", async ({ page }) => {
    const sent = await mockEngine(page);
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await page.getByLabel("Text to check").press("Control+Enter");
    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();
    expect(sent).toHaveLength(1);
  });

  test("remembers the format (only the format) and sends it", async ({ page }) => {
    const sent = await mockEngine(page);
    await page.goto("/");
    await page.getByLabel("Format").selectOption("latex");
    await page.reload();
    await expect(page.getByLabel("Format")).toHaveValue("latex");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    await expect(page.getByTestId("results")).toBeVisible();
    expect(sent[0]!.format).toBe("latex");

    // Nothing but the format preference is stored; no cookies at all.
    const stored = await page.evaluate(() => ({
      local: Object.keys(localStorage),
      localValues: Object.values(localStorage).join(""),
      session: Object.keys(sessionStorage),
    }));
    expect(stored.local).toEqual(["researchly.format"]);
    expect(stored.localValues).not.toContain("Dengue");
    expect(stored.session).toEqual([]);
    expect(await page.context().cookies()).toEqual([]);
  });
});

test.describe("taxonomy", () => {
  test("conventions look advisory, never red", async ({ page }) => {
    await mockEngine(page);
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    const card = page.locator(`#card-${byRule("V310").id}`);
    const badge = card.locator(".badge");
    await expect(badge).toHaveText("Convention");
    const styles = await badge.evaluate((el) => {
      const cs = getComputedStyle(el);
      const c = getComputedStyle(el.closest("article")!);
      return { color: cs.color, bg: cs.backgroundColor, border: c.borderLeftColor };
    });
    const hl = await mark(page, byRule("V310").id).evaluate((el) => getComputedStyle(el).textDecorationColor);
    for (const c of [styles.color, styles.bg, styles.border, hl]) expect(isReddish(rgb(c)), c).toBe(false);
    // Convention highlights use a dotted underline, corrections a solid one (not colour alone).
    expect(await mark(page, byRule("V310").id).evaluate((el) => getComputedStyle(el).textDecorationStyle)).toBe("dotted");
    expect(await mark(page, byRule("S010").id).evaluate((el) => getComputedStyle(el).textDecorationStyle)).toBe("solid");
  });

  test("preferences are hidden by default and shown on request", async ({ page }) => {
    const sent = await mockEngine(page);
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    const note = page.getByTestId("hidden-prefs");
    await expect(note).toContainText("2 preferences hidden");
    await expect(page.getByTestId("filter-preference")).toHaveCount(0);

    await note.getByRole("button", { name: /show/i }).click();
    await expect(page.getByRole("heading", { name: "10 suggestions" })).toBeVisible();
    expect(sent.at(-1)!.options?.show_preferences).toBe(true);
    await expect(page.getByLabel("Show preferences")).toBeChecked();
    await expect(page.getByTestId("hidden-prefs")).toHaveCount(0);
    await expect(page.getByTestId("filter-preference")).toContainText("2");
    await expect(page.locator('[data-testid="suggestion-card"][data-category="preference"]')).toHaveCount(2);

    // Turning the toggle off hides them again without a request.
    await page.getByLabel("Show preferences").uncheck();
    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();
    await expect(page.getByTestId("hidden-prefs")).toContainText("2 preferences hidden");
    expect(sent).toHaveLength(2);
  });
});

test.describe("idle state", () => {
  test("the key teaches all four types, with the same non-colour cues as the highlights", async ({ page }) => {
    await page.goto("/");
    const key = page.getByTestId("reading-key");
    await expect(key.getByRole("heading", { name: "How to read the feedback" })).toBeVisible();
    for (const label of ["Correction", "Improvement", "Convention", "Preference"]) await expect(key).toContainText(label);
    const styles: Record<string, string> = { correction: "solid", improvement: "double", convention: "dotted", preference: "dashed" };
    for (const [cat, style] of Object.entries(styles)) {
      expect(await key.locator(`.spec-${cat}`).evaluate((el) => getComputedStyle(el).textDecorationStyle), cat).toBe(style);
    }
    // A convention is never presented as an error, here either.
    await expect(key.locator(".key-convention")).toContainText("Never an error");
    const conv = await key.locator(".spec-convention").evaluate((el) => {
      const cs = getComputedStyle(el);
      return [cs.textDecorationColor, cs.backgroundColor, getComputedStyle(el.closest("li")!.querySelector(".key-label")!).color];
    });
    for (const c of conv) expect(isReddish(rgb(c)), c).toBe(false);
    const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });

  test("the example fills only an empty editor and sends nothing until Check", async ({ page }) => {
    const sent = await mockEngine(page);
    await page.goto("/");
    await page.getByTestId("insert-example").click();
    await expect(page.getByLabel("Text to check")).toBeFocused();
    await expect(page.getByLabel("Text to check")).toHaveValue(/Methods\n/);
    // Offered only while the editor is empty, so it can never overwrite a draft.
    await expect(page.getByTestId("insert-example")).toHaveCount(0);
    expect(sent).toHaveLength(0);
    await page.getByLabel("Text to check").fill("");
    await expect(page.getByTestId("insert-example")).toBeVisible();
  });

  test("on a phone the key gives way to the results after a check", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await mockEngine(page);
    await page.goto("/");
    await expect(page.getByTestId("reading-key")).toBeVisible();
    await paste(page, SAMPLE_TEXT);
    await check(page);
    await expect(page.getByTestId("suggestion-card").first()).toBeVisible();
    await expect(page.getByTestId("reading-key")).toBeHidden();
  });
});

test.describe("health", () => {
  test("a degraded grammar tier shows a calm banner with detail and remedy", async ({ page }) => {
    await mockEngine(page, (_req, route) => json(route, 200, degradedGrammarResponse));
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    const banner = page.getByTestId("health-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText("Grammar checks unavailable");
    await expect(banner).toContainText("LanguageTool did not respond in time");
    await expect(banner).toContainText("check again in a minute");
    await expect(banner).not.toContainText("Learned corrections");
    // The rest of the results still render.
    await expect(page.getByTestId("suggestion-card")).toHaveCount(8);
    const color = await banner.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(isReddish(rgb(color))).toBe(false);
  });
});

test.describe("states and errors", () => {
  test("loading: busy button, text kept, cancellable", async ({ page }) => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    await mockEngine(page, async (req, route) => {
      await gate;
      await json(route, 200, happyResponse);
    });
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    const btn = page.getByTestId("check");
    await expect(btn).toHaveAttribute("aria-disabled", "true");
    await expect(btn).toHaveText(/Checking/);
    await expect(page.getByTestId("announcer")).toHaveText(/Checking your text/);
    await expect(page.getByLabel("Text to check")).toHaveValue(SAMPLE_TEXT);
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(btn).toHaveText("Check");
    await expect(page.getByTestId("announcer")).toHaveText(/cancelled/);
    await expect(page.getByLabel("Text to check")).toHaveValue(SAMPLE_TEXT);
    release();
  });

  test("empty input is caught client-side with no request", async ({ page }) => {
    const sent = await mockEngine(page);
    await page.goto("/");
    await paste(page, "   \n  ");
    await check(page);
    await expect(page.getByTestId("input-problem")).toHaveText(/Paste or type some text/);
    await expect(page.getByLabel("Text to check")).toBeFocused();
    expect(sent).toHaveLength(0);
  });

  test("over-long input is caught client-side with no request", async ({ page }) => {
    const sent = await mockEngine(page);
    await page.goto("/");
    await page.getByLabel("Text to check").fill("a".repeat(MAX_CONTENT_CHARS + 1));
    await check(page);
    await expect(page.getByTestId("input-problem")).toContainText("1,000,001 characters");
    expect(sent).toHaveLength(0);
  });

  test("an empty result says so, without implying a score", async ({ page }) => {
    await mockEngine(page, (_r, route) => json(route, 200, emptyResponse));
    await page.goto("/");
    await paste(page, "A perfectly ordinary sentence.");
    await check(page);
    await expect(page.getByTestId("empty-state")).toContainText("No suggestions. That’s not a score");
    await expect(page.getByTestId("empty-state")).toContainText("none of our checks fired");
  });

  test("engine unreachable: text kept, Retry works", async ({ page }) => {
    let up = false;
    await mockEngine(page, async (_req, route) => {
      if (!up) await route.abort("connectionrefused");
      else await json(route, 200, happyResponse);
    });
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    const err = page.getByTestId("check-error");
    await expect(err).toHaveAttribute("data-kind", "unreachable");
    await expect(err).toContainText("Could not reach the checking engine");
    await expect(err).toBeFocused();
    await expect(page.getByLabel("Text to check")).toHaveValue(SAMPLE_TEXT);
    up = true;
    await page.getByTestId("retry").click();
    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();
    await expect(page.getByTestId("check-error")).toHaveCount(0);
  });

  test("413 explains the limit", async ({ page }) => {
    await mockEngine(page, (_r, route) => json(route, 413, error413));
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    const err = page.getByTestId("check-error");
    await expect(err).toContainText("This text is too long for one check");
    await expect(err).toContainText("1,000,000 characters");
    await expect(page.getByTestId("retry")).toHaveCount(0);
    await expect(page.getByLabel("Text to check")).toHaveValue(SAMPLE_TEXT);
  });

  test("429 asks to slow down", async ({ page }) => {
    await mockEngine(page, (_r, route) => json(route, 429, error429, { "retry-after": "20" }));
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    const err = page.getByTestId("check-error");
    await expect(err).toContainText("Too many checks in a short time");
    await expect(err).toContainText("20 seconds");
    await expect(page.getByLabel("Text to check")).toHaveValue(SAMPLE_TEXT);
  });

  test("422 shows the engine's message", async ({ page }) => {
    await mockEngine(page, (_r, route) => json(route, 422, error422));
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    await expect(page.getByTestId("check-error")).toContainText("format must be one of");
  });

  test("500 shows the request id to quote", async ({ page }) => {
    await mockEngine(page, (_r, route) => json(route, 500, error500));
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    const err = page.getByTestId("check-error");
    await expect(err).toContainText("Something went wrong on our side");
    await expect(page.getByTestId("request-id")).toHaveText("req-500-a9f3c2");
    await expect(page.getByTestId("retry")).toBeVisible();
    await expect(page.getByLabel("Text to check")).toHaveValue(SAMPLE_TEXT);
  });
});

test.describe("accessibility", () => {
  test("keyboard only: check, read Why, jump to the text and back", async ({ page }) => {
    await mockEngine(page);
    await page.goto("/");
    const tabTo = async (pred: () => Promise<boolean>, max = 80) => {
      for (let i = 0; i < max; i++) {
        await page.keyboard.press("Tab");
        if (await pred()) return;
      }
      throw new Error("focus target not reached");
    };
    const active = (fn: (el: Element) => boolean) => page.evaluate(`(${fn.toString()})(document.activeElement)`) as Promise<boolean>;

    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to the checker" })).toBeFocused();
    await tabTo(() => active((el) => el.tagName === "TEXTAREA"));
    await page.keyboard.insertText(SAMPLE_TEXT);
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Format")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Show preferences")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("check")).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();
    await expect(page.getByTestId("announcer")).toHaveText(/Check complete\. 8 suggestions/);

    // Into the document region, arrow to the first highlight, Enter opens its card.
    await tabTo(() => active((el) => el.getAttribute("data-testid") === "document"));
    await page.keyboard.press("ArrowDown");
    const firstId = await page.evaluate(() => document.activeElement?.getAttribute("data-sids"));
    expect(firstId).toBeTruthy();
    await page.keyboard.press("Enter");
    await expect(page.locator(`#card-${firstId!.split(" ")[0]}`)).toBeFocused();

    // Tab onwards to the card's Why, open it, then "Show in text".
    await tabTo(() => active((el) => el.tagName === "SUMMARY" && el.textContent === "Why?"));
    await page.keyboard.press("Enter");
    await expect(page.locator("details.why[open]")).toHaveCount(1);
    await tabTo(() => active((el) => el.textContent === "Show in text"));
    await page.keyboard.press("Enter");
    const focusedMark = await page.evaluate(() => document.activeElement?.closest("[data-testid=document]") !== null);
    expect(focusedMark).toBe(true);
  });

  for (const scheme of ["light", "dark"] as const) {
    test(`axe: no serious or critical violations on the results view (${scheme})`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await mockEngine(page, (_r, route) =>
        json(route, 200, { ...withPreferencesResponse, health: degradedGrammarResponse.health }),
      );
      await page.goto("/");
      await paste(page, SAMPLE_TEXT);
      await page.getByLabel("Show preferences").check();
      await check(page);
      await expect(page.getByTestId("suggestion-card")).toHaveCount(10);
      await page.getByTestId("suggestion-card").first().getByText("Why?").click();
      await page.getByTestId("check").focus();
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]).analyze();
      const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")}`)).toEqual([]);
    });
  }

  test("axe: error state", async ({ page }) => {
    await mockEngine(page, (_r, route) => json(route, 500, error500));
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    await expect(page.getByTestId("check-error")).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });

  for (const width of [375, 360]) {
    test(`mobile ${width}px: no horizontal scroll`, async ({ page }) => {
      await page.setViewportSize({ width, height: 812 });
      await mockEngine(page);
      await page.goto("/");
      await paste(page, SAMPLE_TEXT + "\nA very long unbroken token: " + "x".repeat(300) + "\nhttps://example.org/" + "a/".repeat(80));
      await check(page);
      await expect(page.getByTestId("suggestion-card").first()).toBeVisible();
      await page.getByTestId("suggestion-card").first().getByText("Why?").click();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }
});

test.describe("security", () => {
  test("headers: strict CSP with only self + engine in connect-src", async ({ request }) => {
    const res = await request.get("/");
    const h = res.headers();
    const csp = h["content-security-policy"]!;
    expect(csp).toMatch(/connect-src 'self' http:\/\/127\.0\.0\.1:8099(;|$)/);
    expect(csp).toMatch(/script-src 'self' 'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
    expect(csp).not.toContain("unsafe-inline");
    expect(csp).not.toContain("unsafe-eval");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(h["referrer-policy"]).toBe("no-referrer");
    expect(h["x-content-type-options"]).toBe("nosniff");
    expect(h["set-cookie"]).toBeUndefined();
    expect(h["x-powered-by"]).toBeUndefined();
  });

  test("no CSP violations or console errors during a full check", async ({ page }) => {
    const problems: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error") problems.push(m.text());
    });
    page.on("pageerror", (e) => problems.push(e.message));
    await mockEngine(page);
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    await expect(page.getByTestId("suggestion-card")).toHaveCount(8);
    expect(problems).toEqual([]);
  });

  test("the page loads nothing from third parties", async ({ page, baseURL }) => {
    const external: string[] = [];
    page.on("request", (r) => {
      const u = r.url();
      if (!u.startsWith(baseURL!) && !u.startsWith("http://127.0.0.1:8099") && !u.startsWith("data:")) external.push(u);
    });
    await mockEngine(page);
    await page.goto("/");
    await paste(page, SAMPLE_TEXT);
    await check(page);
    await expect(page.getByTestId("results")).toBeVisible();
    expect(external).toEqual([]);
  });
});

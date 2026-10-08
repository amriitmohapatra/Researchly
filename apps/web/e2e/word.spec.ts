/**
 * S3: the Word add-in's taskpane at /word, on the build without accounts
 * (project "chromium"). Microsoft's office.js is replaced by a fake
 * (e2e/fake-office.ts) served at the same URL, so the page loads it exactly
 * as in Word, under the route's own CSP. The engine is mocked.
 */
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { ENGINE } from "./fixtures";
import {
  at,
  BOOSTER,
  COMPOUND,
  DEGRADED,
  DOC,
  fakeOffice,
  fulfillJson,
  LOCAL_ENGINE,
  LONG,
  mockWordEngine,
  OFFICE_JS,
  REPEAT_2B,
  reviseResponse,
  wordState,
  WORDY,
} from "./word-fixtures";

const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function axeSerious(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
  return r.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")}`);
}

function card(page: Page, ruleOrMessage: string | RegExp) {
  return page.getByTestId("word-card").filter({ hasText: ruleOrMessage });
}

async function openAndCheck(page: Page) {
  await page.goto("/word");
  await page.getByTestId("check-document").click();
  await expect(page.getByTestId("tp-results")).toBeVisible();
}

test.describe("Word taskpane", () => {
  test("loads office.js under its CSP, survives office.js removing history, and checks: cards in document order", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    await fakeOffice(page, { nullHistory: true });
    const calls = await mockWordEngine(page, ENGINE);
    await openAndCheck(page);

    // The request: every paragraph, Word styles, table cells marked, the mode sent explicitly.
    expect(calls).toHaveLength(1);
    const body = calls[0]!.body;
    expect(body.paragraphs).toEqual([
      { text: "Methods", style: "Heading1", kind: "body" },
      { text: DOC[1]!.text, style: "Normal", kind: "body" },
      { text: "Discussion", style: "Heading1", kind: "body" },
      { text: DOC[3]!.text, style: "Normal", kind: "body" },
      { text: "Region", style: "Normal", kind: "table" },
    ]);
    expect(body.options).toEqual({ show_preferences: false, disabled_rules: [], mode: "revise", document_type: "auto", review: true });
    expect(calls[0]!.authorization).toBeUndefined();

    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();
    const rules = await page.getByTestId("word-card").evaluateAll((els) => els.map((e) => e.getAttribute("data-rule")));
    expect(rules).toEqual(["C120", "S010", "S001", "G106", "C201", "S010", "W211", "S010"]);
    // Every card: category, message, the plain explanation, the source; the full reasoning behind a disclosure.
    const first = card(page, "In order to");
    await expect(first).toContainText("Improvement");
    await expect(first).toContainText("Methods");
    await expect(first.getByTestId("card-plain")).toContainText("In everyday words");
    await expect(first).toContainText("Source: The Craft of Scientific Writing, §4");
    await expect(first.getByText("A synthetic explanation")).toBeHidden();
    await expect(first).not.toContainText("Rule");
    await expect(first).not.toContainText("Checked by");
    await expect(first).not.toContainText("C120");
    await first.getByText("The full reasoning").click();
    await expect(first.getByText("A synthetic explanation")).toBeVisible();
    // The stage's help says what each stage checks.
    await expect(page.getByTestId("mode-help")).toHaveText("Draft: check what you've written so far. Revise: check the finished manuscript.");

    await expect(page.getByTestId("coverage")).toContainText("Checked 5 paragraphs of the document body, 1 of them in a table.");
    await expect(page.getByTestId("coverage")).toContainText(
      "Footnotes, endnotes, headers and footers, text boxes and comments were not checked.",
    );
    await expect(page.getByTestId("hidden-prefs")).toContainText("1 preference is hidden");
    await expect(page.getByTestId("held-back")).toHaveCount(0);

    // office.js removed them; the guard put them back, and the router still works.
    expect(await page.evaluate(() => typeof history.replaceState === "function" && typeof history.pushState === "function")).toBe(true);
    expect(errors).toEqual([]);
  });

  test("clicking a card selects that copy of a repeated phrase in the document", async ({ page }) => {
    await fakeOffice(page);
    await mockWordEngine(page, ENGINE);
    await openAndCheck(page);
    await card(page, "second time").locator(".card-msg").click();
    await expect.poll(async () => (await wordState(page)).selection).toEqual({
      paragraph: 3,
      start: at(3, "the the", 1),
      end: at(3, "the the", 1) + 7,
      text: "the the",
    });
    expect(REPEAT_2B.location.occurrence).toBe(1);
    // Keyboard path: the explicit button does the same.
    await card(page, "In order to").getByTestId("select-in-document").click();
    await expect.poll(async () => (await wordState(page)).selection?.start).toBe(0);
  });

  test("an approximate match is selected and said to be approximate", async ({ page }) => {
    await fakeOffice(page);
    await mockWordEngine(page, ENGINE);
    await openAndCheck(page);
    const c = card(page, "This sentence is long");
    await c.getByTestId("select-in-document").click();
    await expect(c.getByTestId("card-note")).toContainText("The match is approximate");
    expect((await wordState(page)).selection?.text).toBe(LONG.location.snippet);
    // No Apply for it (it has no revision).
    await expect(c.getByTestId("apply-fix")).toHaveCount(0);
  });

  test("apply with WordApi 1.4: a tracked change, only that span, and Track Changes is restored", async ({ page }) => {
    await fakeOffice(page, { api14: true, trackingMode: "Off" });
    await mockWordEngine(page, ENGINE);
    await openAndCheck(page);
    const c = card(page, "In order to");
    await c.getByTestId("apply-fix").click();
    await expect(c.getByTestId("card-note")).toContainText("Applied as a tracked change");
    const st = await wordState(page);
    expect(st.edits).toEqual([{ paragraph: 1, start: 0, end: WORDY.text.length, before: "In order to", text: "To", tracked: true }]);
    expect(st.paragraphs[1]!.text.startsWith("To estimate")).toBe(true);
    expect(st.trackingWrites).toEqual(["TrackAll", "Off"]);
    expect(st.trackingMode).toBe("Off");
    await expect(c.getByTestId("apply-fix")).toHaveCount(0);
  });

  test("apply without WordApi 1.4: never touches Track Changes, edits directly, and says so", async ({ page }) => {
    await fakeOffice(page, { api14: false });
    await mockWordEngine(page, ENGINE);
    await openAndCheck(page);
    const c = card(page, "second time");
    await c.getByTestId("apply-fix").click();
    await expect(c.getByTestId("card-note")).toContainText("Applied as a direct edit");
    const st = await wordState(page);
    expect(st.trackingWrites).toEqual([]);
    expect(st.failedBatches).toBe(0);
    expect(st.edits).toEqual([
      { paragraph: 3, start: at(3, "the the", 1), end: at(3, "the the", 1) + 7, before: "the the", text: "the", tracked: false },
    ]);
    // The first "the the" is untouched.
    expect(st.paragraphs[3]!.text).toContain("that the the effect");
  });

  test("apply refuses when the document changed since the check, and changes nothing", async ({ page }) => {
    await fakeOffice(page);
    await mockWordEngine(page, ENGINE);
    await openAndCheck(page);
    await page.evaluate(() => {
      const w = (window as unknown as { __fakeWord: { paragraphs: { text: string }[] } }).__fakeWord;
      w.paragraphs[1]!.text = `Briefly, ${w.paragraphs[1]!.text}`;
    });
    const c = card(page, "In order to");
    await c.getByTestId("apply-fix").click();
    await expect(c.getByTestId("card-note")).toContainText("The document has changed here since the check");
    expect((await wordState(page)).edits).toEqual([]);
    await expect(c.getByTestId("apply-fix")).toBeVisible();
  });

  test("Draft sends mode, shows what it held back, and is remembered on this computer when signed out", async ({ page }) => {
    await fakeOffice(page);
    const calls = await mockWordEngine(page, ENGINE);
    await page.goto("/word");
    await page.getByTestId("mode-draft").check();
    await page.getByTestId("check-document").click();
    await expect(page.getByTestId("held-back")).toContainText("Draft held back 2 document-level suggestions");
    expect(calls[0]!.body.options?.mode).toBe("draft");

    // Switching from the note re-checks in Revise.
    await page.getByTestId("held-back").getByRole("button", { name: "Switch to Revise" }).click();
    await expect(page.getByTestId("held-back")).toHaveCount(0);
    expect(calls.at(-1)!.body.options?.mode).toBe("revise");
    await expect(page.getByTestId("mode-revise")).toBeChecked();

    await page.getByTestId("mode-draft").check();
    await expect.poll(() => calls.at(-1)!.body.options?.mode).toBe("draft");
    await page.reload();
    await expect(page.getByTestId("mode-draft")).toBeChecked();
  });

  test("the reviewer's brief is a tab in the pane: Draft asks for Revise and switches; Check as is sent, re-checks and is said", async ({ page }) => {
    await fakeOffice(page);
    const calls = await mockWordEngine(page, ENGINE);
    await page.goto("/word");
    await page.getByTestId("mode-draft").check();
    await page.getByTestId("check-document").click();
    await expect(page.getByTestId("tp-results")).toBeVisible();
    // Draft never asks for the brief: it is a whole-document read.
    expect(calls[0]!.body.options?.review).toBe(false);
    await page.getByTestId("view-brief").click();
    await expect(page.getByTestId("brief-needs-revise")).toContainText("needs Revise mode");
    await expect(page.getByTestId("word-card")).toHaveCount(0);

    await page.getByTestId("brief-switch-revise").click();
    await expect(page.getByTestId("mode-revise")).toBeChecked();
    await expect.poll(() => calls.length).toBe(2);
    expect(calls[1]!.body.options?.review).toBe(true);
    const questions = page.getByTestId("brief-question");
    await expect(questions).toHaveCount(5);
    await expect(questions.nth(0)).toContainText("Why am I reading this?");
    await expect(questions.nth(0)).toContainText("Yours to answer");
    await expect(questions.nth(2).locator(".brief-evidence q")).toHaveText(
      "It is clearly proven that the the effect of vector control was large, and the the data agree.",
    );
    await expect(page.getByTestId("brief-rules").locator("li")).toHaveText(["Repeated word 4 times", "Wordy phrase once"]);
    await expect(page.getByTestId("brief")).toContainText("Source: M. Wallace & A. Wray (2016)");
    await expect(page.locator("meter, progress")).toHaveCount(0);

    // The suggestions tab brings the cards back without another check.
    await page.getByTestId("view-suggestions").click();
    await expect(page.getByTestId("word-card")).toHaveCount(8);
    expect(calls).toHaveLength(2);

    // Check as: Auto by default, the guess said in the results; a choice is sent, checks again, is said, and is remembered here.
    await expect(page.getByTestId("document-type")).toHaveValue("auto");
    await expect(page.getByTestId("profile-line")).toHaveText("Checked as Research article (from the headings).");
    await page.getByTestId("document-type").selectOption("commentary");
    await expect.poll(() => calls.length).toBe(3);
    expect(calls[2]!.body.options?.document_type).toBe("commentary");
    await expect(page.getByTestId("document-type-help")).toHaveText("An opinion or perspective piece: argued, not reported.");
    await expect(page.getByTestId("profile-line")).toContainText("Checked as a commentary:");
    await page.reload();
    await expect(page.getByTestId("document-type")).toHaveValue("commentary");
    expect(await page.evaluate(() => Object.keys(localStorage).sort())).toEqual(["researchly.document-type", "researchly.word.mode"]);
  });

  test("Check this section: the whole document is sent, only the cursor's section is listed, document-wide checks kept", async ({ page }) => {
    await fakeOffice(page, { cursor: 3 });
    const calls = await mockWordEngine(page, ENGINE);
    await page.goto("/word");
    await page.getByTestId("mode-draft").check();
    await expect(page.getByTestId("mode-help")).toHaveText("Draft: check what you've written so far. Revise: check the finished manuscript.");
    await page.getByTestId("mode-revise").check();
    await page.getByTestId("check-section").click();
    await expect(page.getByTestId("tp-results")).toBeVisible();
    // Never truncated: every paragraph went to the engine.
    expect(calls).toHaveLength(1);
    expect(calls[0]!.body.paragraphs).toHaveLength(DOC.length);

    await expect(page.getByRole("heading", { name: "5 suggestions in “Discussion”" })).toBeVisible();
    const note = page.getByTestId("section-focus");
    await expect(note).toContainText("Showing the section at the cursor, “Discussion”.");
    await expect(note).toContainText("3 more suggestions are elsewhere in it.");
    const inSection = page.locator(".tp-suggestions > .tp-cards [data-testid=word-card]");
    await expect(inSection).toHaveCount(4);
    expect(await inSection.evaluateAll((els) => els.map((e) => e.getAttribute("data-paragraph")))).toEqual(["3", "3", "3", "3"]);
    const whole = page.getByTestId("whole-document");
    await expect(whole.getByRole("heading", { name: "Whole document" })).toBeVisible();
    await expect(whole.getByTestId("word-card")).toHaveAttribute("data-rule", "W211");
    await expect(card(page, "In order to")).toHaveCount(0);
    await expect(page.getByTestId("tp-announcer")).toHaveText("Check complete. 5 suggestions in “Discussion”. 3 more elsewhere in the document.");

    // The section's cards still work in the document.
    await card(page, "second time").getByTestId("select-in-document").click();
    await expect.poll(async () => (await wordState(page)).selection?.paragraph).toBe(3);

    // Everything, without another check.
    await page.getByTestId("show-whole-document").click();
    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();
    await expect(page.getByTestId("section-focus")).toHaveCount(0);
    await expect(page.getByTestId("whole-document")).toHaveCount(0);
    expect(calls).toHaveLength(1);

    // The cursor above the first heading, and a document that lists no rule scopes (the built-in list applies).
    await page.evaluate(() => {
      (window as unknown as { __fakeWord: { selection: unknown } }).__fakeWord.selection = { paragraph: 1, start: 0, end: 0, text: "" };
    });
    await page.getByTestId("check-section").click();
    await expect(page.getByRole("heading", { name: "4 suggestions in “Methods”" })).toBeVisible();
    await expect(inSection).toHaveCount(3);
    await expect(page.getByTestId("whole-document").getByTestId("word-card")).toHaveCount(1);
    expect(calls).toHaveLength(2);
  });

  test("Check this section: a section with nothing to flag, and an engine whose registry lists no scopes", async ({ page }) => {
    await fakeOffice(page, { cursor: 1 });
    await mockWordEngine(page, ENGINE, {
      rules: [],
      respond: (_req, route) =>
        fulfillJson(route, 200, { ...reviseResponse, suggestions: [LONG, BOOSTER, COMPOUND], counts: { improvement: 1, convention: 2 } }),
    });
    await page.goto("/word");
    await page.getByTestId("check-section").click();
    await expect(page.getByTestId("tp-results")).toBeVisible();
    await expect(page.getByRole("heading", { name: "1 suggestion in “Methods”" })).toBeVisible();
    await expect(page.getByTestId("tp-empty")).toContainText("Nothing to flag in this section");
    await expect(page.getByTestId("tp-empty")).toContainText("This is not a score");
    await expect(page.getByTestId("section-focus")).toContainText("2 more suggestions are elsewhere in it.");
    // W211 is not in the registry the engine sent: the built-in list keeps it document-wide.
    await expect(page.getByTestId("whole-document").getByTestId("word-card")).toHaveAttribute("data-rule", "W211");
  });

  test("hidden preferences can be revealed (a re-check that asks for them)", async ({ page }) => {
    await fakeOffice(page);
    const calls = await mockWordEngine(page, ENGINE);
    await openAndCheck(page);
    await page.getByTestId("hidden-prefs").getByRole("button").click();
    await expect.poll(() => calls.length).toBe(2);
    expect(calls[1]!.body.options?.show_preferences).toBe(true);
  });

  test("a degraded tier is shown before and after a check, calmly", async ({ page }) => {
    await fakeOffice(page);
    await mockWordEngine(page, ENGINE, {
      health: DEGRADED,
      respond: (_req, route) => fulfillJson(route, 200, { ...reviseResponse, health: DEGRADED }),
    });
    await page.goto("/word");
    const banner = page.getByTestId("health-banner");
    await expect(banner).toContainText("Grammar checks unavailable");
    await page.getByTestId("check-document").click();
    await expect(page.getByTestId("tp-results")).toBeVisible();
    await expect(banner).toContainText("LanguageTool did not respond in time");
  });

  test("engine errors are explained with a retry", async ({ page }) => {
    await fakeOffice(page);
    let n = 0;
    await mockWordEngine(page, ENGINE, {
      respond: (_req, route) =>
        ++n === 1
          ? fulfillJson(route, 500, { error: { code: "internal", message: "x", request_id: "req-word-500" } })
          : fulfillJson(route, 200, reviseResponse),
    });
    await page.goto("/word");
    await page.getByTestId("check-document").click();
    await expect(page.getByTestId("tp-error")).toContainText("Something went wrong on our side");
    await expect(page.getByTestId("tp-error")).toContainText("req-word-500");
    await page.getByTestId("tp-retry").click();
    await expect(page.getByRole("heading", { name: "8 suggestions" })).toBeVisible();
  });

  test("an empty document is said, and nothing is sent", async ({ page }) => {
    await fakeOffice(page, { paragraphs: [{ text: "" }, { text: "   " }] });
    const calls = await mockWordEngine(page, ENGINE);
    await page.goto("/word");
    await page.getByTestId("check-document").click();
    await expect(page.getByTestId("tp-problem")).toContainText("This document is empty");
    expect(calls).toHaveLength(0);
  });

  test("“This computer”: text goes only to localhost:3517, with no token; a stopped server is explained", async ({ page }) => {
    await fakeOffice(page);
    const cloud = await mockWordEngine(page, ENGINE);
    await page.goto("/word");
    await page.getByTestId("tp-settings").locator("summary").click();
    await page.getByTestId("engine-local").check();
    // Nothing is listening yet: health fails, and the pane says how to start it.
    await expect(page.getByTestId("local-down")).toContainText("Researchly is not running on this computer");
    await page.getByTestId("check-document").click();
    await expect(page.getByTestId("tp-error")).toContainText("python3 server.py");

    const local = await mockWordEngine(page, LOCAL_ENGINE);
    await page.getByTestId("tp-retry").click();
    await expect(page.getByTestId("tp-results")).toBeVisible();
    await expect(page.getByTestId("privacy-line")).toContainText("Nothing is sent over the network");
    expect(local).toHaveLength(1);
    expect(local[0]!.url).toBe(`${LOCAL_ENGINE}/v1/analyze-word`);
    expect(local[0]!.authorization).toBeUndefined();
    expect(cloud).toHaveLength(0);

    await page.reload();
    await page.getByTestId("tp-settings").locator("summary").click();
    await expect(page.getByTestId("engine-local")).toBeChecked();
  });

  test("outside Word the page says how to open it, and reads nothing", async ({ page }) => {
    await fakeOffice(page, { host: null });
    const calls = await mockWordEngine(page, ENGINE);
    await page.goto("/word");
    await expect(page.getByTestId("not-in-word")).toContainText("Open Researchly from Word");
    await expect(page.getByTestId("check-document")).toHaveCount(0);
    expect(calls).toHaveLength(0);
  });

  test("privacy: text goes only to the engine, nothing is stored but the two choices, no cookies", async ({ page, baseURL }) => {
    await fakeOffice(page);
    await mockWordEngine(page, ENGINE);
    const sent: string[] = [];
    page.on("request", (r) => {
      if (r.method() !== "GET" && r.method() !== "OPTIONS") sent.push(new URL(r.url()).origin);
    });
    await page.goto("/word");
    await page.getByTestId("mode-draft").check();
    await page.getByTestId("check-document").click();
    await expect(page.getByTestId("tp-results")).toBeVisible();
    await card(page, "In order to").getByTestId("apply-fix").click();
    await expect(card(page, "In order to").getByTestId("card-note")).toBeVisible();
    expect(new Set(sent)).toEqual(new Set([new URL(ENGINE).origin]));
    expect(sent).not.toContain(baseURL);
    expect(await page.context().cookies()).toEqual([]);
    const stored = await page.evaluate(() => Object.keys(localStorage).sort());
    expect(stored).toEqual(["researchly.word.mode"]);
    expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  });

  test("Report a problem is a mailto with a subject, and asks for no document text", async ({ page }) => {
    await fakeOffice(page);
    await mockWordEngine(page, ENGINE);
    await page.goto("/word");
    const link = page.getByTestId("report-problem");
    await expect(link).toHaveAttribute("href", "mailto:amrit.mohapatra97@gmail.com?subject=Researchly%20Word%20add-in%3A%20a%20problem");
    await expect(page.locator(".tp-footer")).toContainText("don’t paste text from your document");
    // The website's footer has the same contact.
    await page.goto("/");
    await expect(page.getByTestId("report-problem")).toHaveAttribute("href", /^mailto:amrit\.mohapatra97@gmail\.com\?subject=/);
  });
});

test.describe("Word taskpane layout and accessibility", () => {
  for (const scheme of ["light", "dark"] as const) {
    test(`375px wide, ${scheme}: no horizontal scroll, no serious axe violations`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.setViewportSize({ width: 375, height: 800 });
      await fakeOffice(page);
      await mockWordEngine(page, ENGINE, { health: DEGRADED });
      await page.goto("/word");
      await page.getByTestId("tp-settings").locator("summary").click();
      await expect(page.getByTestId("health-banner")).toBeVisible();
      await page.getByTestId("check-document").click();
      await expect(page.getByTestId("tp-results")).toBeVisible();
      await card(page, "This sentence is long").getByTestId("select-in-document").click();
      await card(page, "In order to").getByText("The full reasoning").click();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      expect(await axeSerious(page)).toEqual([]);
    });
  }

  test("320px (the narrowest Word sidebar): still no horizontal scroll", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 700 });
    await fakeOffice(page);
    await mockWordEngine(page, ENGINE);
    await openAndCheck(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test.describe("security headers", () => {
  const directive = (csp: string, name: string) =>
    csp
      .split(";")
      .map((d) => d.trim())
      .find((d) => d.startsWith(`${name} `)) ?? "";

  test("/word: framed only by Office on the web, office.js allowed, local engine reachable", async ({ request }) => {
    const res = await request.get("/word");
    expect(res.status()).toBe(200);
    const h = res.headers();
    expect(h["x-frame-options"]).toBeUndefined();
    const csp = h["content-security-policy"]!;
    expect(directive(csp, "frame-ancestors")).toBe(
      "frame-ancestors 'self' https://*.officeapps.live.com https://*.office.com https://*.office365.com https://*.sharepoint.com https://*.microsoft365.com",
    );
    expect(directive(csp, "script-src")).toContain(new URL(OFFICE_JS).origin);
    expect(directive(csp, "script-src")).not.toContain("unsafe-inline");
    expect(directive(csp, "connect-src")).toBe(`connect-src 'self' ${ENGINE} http://localhost:3517`);
    expect(csp).not.toContain("upgrade-insecure-requests");
    expect(h["referrer-policy"]).toBe("no-referrer");
    expect(h["x-content-type-options"]).toBe("nosniff");
  });

  test("every other route keeps its headers: DENY framing, strict-dynamic, no Office, no localhost", async ({ request }) => {
    for (const path of ["/", "/wordy-page-that-does-not-exist", "/icon.svg"]) {
      const res = await request.get(path);
      const h = res.headers();
      expect(h["x-frame-options"], path).toBe("DENY");
      expect(h["referrer-policy"], path).toBe("no-referrer");
      const csp = h["content-security-policy"];
      if (csp) {
        expect(directive(csp, "frame-ancestors")).toBe("frame-ancestors 'none'");
        expect(directive(csp, "script-src")).toContain("'strict-dynamic'");
        expect(csp).not.toContain("appsforoffice");
        expect(csp).not.toContain("localhost:3517");
      }
    }
  });
});

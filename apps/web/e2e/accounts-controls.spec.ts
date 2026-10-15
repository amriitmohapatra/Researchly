/**
 * Account controls (PLAN #12): "Reset preferences", "Clear my dictionary"
 * (accounts.spec.ts) and "Delete my account", each its own clearly worded
 * action with a confirmation, against the mocked Supabase project. The Word
 * taskpane links to the website's Settings for these rather than repeating
 * them.
 */
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { RULES, signedInPaste } from "./accounts-fixtures";
import { mockEngineAuth, mockSupabase, OTHER_USER_ID, reply, seedSession, STORAGE_KEY, USER } from "./supabase-mock";
import { fakeOffice, reviseResponse } from "./word-fixtures";

const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"];

async function axeSerious(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
  return r.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")}`);
}

/** A writer who has changed every choice, kept words and switched progress on. */
const CUSTOMISED = {
  settings: {
    disabled_rules: ["C120", "G101"],
    show_preferences: true,
    locale: "en-GB",
    mode: "draft",
    document_type: "grant",
    spelling: "uk",
    keep_progress: true,
  },
  words: ["Rt", "nowcasting"],
  progress: [{ created_at: "2026-10-10T09:00:00Z", words: 900, document_type: "grant", counts: { G101: 2 } }],
};

async function openSettings(page: Page, init: Parameters<typeof mockSupabase>[1] = CUSTOMISED) {
  await seedSession(page);
  const sb = await mockSupabase(page, structuredClone(init));
  await mockEngineAuth(page, (_c, route) => reply(route, 200, signedInPaste), RULES);
  await page.goto("/settings");
  await expect(page.getByTestId("muted-rule").first()).toBeVisible();
  return sb;
}

function noOtherUser(sb: Awaited<ReturnType<typeof mockSupabase>>) {
  for (const r of sb.sent) {
    expect(r.body + r.search).not.toContain(OTHER_USER_ID);
    // The functions take no arguments: the account is always the caller's own.
    if (r.path.startsWith("/rest/v1/rpc/") && /reset_my_preferences|delete_my_account/.test(r.path)) {
      expect(r.body === "" ? {} : JSON.parse(r.body)).toEqual({});
      expect(r.body + r.search).not.toContain(USER.id);
    }
  }
}

test.describe("reset preferences", () => {
  test("says what resets and what stays; resets the choices and keeps the words, progress and its switch", async ({ page }) => {
    const sb = await openSettings(page);
    await expect(page.getByTestId("settings-show-preferences")).toBeChecked();
    await expect(page.getByTestId("locale-en-GB")).toBeChecked();
    await expect(page.getByTestId("spelling")).toHaveValue("uk");

    const section = page.getByTestId("reset-preferences");
    await expect(section).toContainText("Your dictionary, your recorded progress and the Keep my progress switch stay as they are.");
    await section.getByTestId("reset-preferences-open").click();
    const dialog = page.getByTestId("reset-preferences-dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: "Reset your preferences?" })).toBeVisible();
    await expect(dialog).toContainText("Every muted rule is unmuted");
    await expect(dialog.getByRole("button", { name: "Keep them" })).toBeFocused();
    expect(await axeSerious(page)).toEqual([]);

    // Keep them: nothing is sent.
    await dialog.getByRole("button", { name: "Keep them" }).click();
    await expect(dialog).toBeHidden();
    await expect(section.getByTestId("reset-preferences-open")).toBeFocused();
    expect(sb.sent.some((r) => r.path === "/rest/v1/rpc/reset_my_preferences")).toBe(false);

    await section.getByTestId("reset-preferences-open").click();
    await dialog.getByTestId("reset-preferences-confirm").click();
    await expect(page.getByTestId("settings-status")).toHaveText(
      "Your preferences were reset. Your dictionary and progress are as they were.",
    );
    await expect(dialog).toBeHidden();
    await expect(page.getByTestId("muted-empty")).toBeVisible();
    await expect(page.getByTestId("settings-show-preferences")).not.toBeChecked();
    await expect(page.getByTestId("locale-en-US")).toBeChecked();
    await expect(page.getByTestId("spelling")).toHaveValue("auto");
    await expect(page.getByTestId("word-count")).toHaveText("2 of 5,000 words");
    await expect(page.getByTestId("keep-progress-switch")).toBeChecked();

    expect(sb.settings).toMatchObject({
      disabled_rules: [],
      show_preferences: false,
      locale: "en-US",
      mode: "revise",
      document_type: "auto",
      spelling: "auto",
      keep_progress: true,
    });
    expect(sb.words).toEqual(["Rt", "nowcasting"]);
    expect(sb.progress).toHaveLength(1);
    expect(sb.sent.filter((r) => r.method === "DELETE")).toEqual([]);
    // This browser follows the account too.
    const local = await page.evaluate(() => [
      window.localStorage.getItem("researchly.spelling"),
      window.localStorage.getItem("researchly.document-type"),
    ]);
    expect(local).toEqual(["auto", "auto"]);
    noOtherUser(sb);
  });

  test("an account database without the migration says so, and nothing changes", async ({ page }) => {
    const sb = await openSettings(page, {
      ...CUSTOMISED,
      rpcErrors: {
        reset_my_preferences: { status: 404, body: { code: "PGRST202", message: "Could not find the function public.reset_my_preferences" } },
      },
    });
    await page.getByTestId("reset-preferences-open").click();
    await page.getByTestId("reset-preferences-confirm").click();
    await expect(page.getByTestId("settings-error")).toHaveText("Resetting isn’t available on this site yet. Nothing was changed.");
    await expect(page.getByTestId("muted-rule")).toHaveCount(2);
    expect(sb.settings?.disabled_rules).toEqual(["C120", "G101"]);
  });
});

test.describe("delete my account", () => {
  test("two steps and a typed word; deletes everything, signs out and says so", async ({ page }) => {
    const sb = await openSettings(page);
    const section = page.getByTestId("delete-account");
    await expect(section).toContainText("To keep the account and start again, reset your preferences instead.");
    const opener = section.getByTestId("delete-account-open");
    await opener.click();
    const dialog = page.getByTestId("delete-account-dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("It can’t be undone, and this browser will be signed out.");
    await expect(dialog.getByRole("button", { name: "Keep my account" })).toBeFocused();
    expect(await axeSerious(page)).toEqual([]);

    // Escape closes and returns focus; nothing is sent.
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(opener).toBeFocused();

    await opener.click();
    const confirm = dialog.getByTestId("delete-account-confirm");
    await confirm.click();
    await expect(dialog.getByTestId("delete-account-problem")).toHaveText("Type the word “delete” to confirm.");
    await expect(dialog.getByTestId("delete-account-word")).toBeFocused();
    await expect(dialog.getByTestId("delete-account-word")).toHaveAttribute("aria-invalid", "true");
    expect(await axeSerious(page)).toEqual([]);
    await dialog.getByTestId("delete-account-word").fill("deleted");
    await confirm.click();
    expect(sb.sent.some((r) => r.path === "/rest/v1/rpc/delete_my_account")).toBe(false);

    await dialog.getByTestId("delete-account-word").fill("Delete");
    await dialog.getByTestId("delete-account-word").press("Enter");

    const done = page.getByTestId("account-deleted");
    await expect(done).toBeVisible();
    await expect(done.getByRole("heading", { name: "Your account was deleted" })).toBeFocused();
    await expect(page.getByTestId("settings")).toHaveCount(0);
    expect(sb.accountDeleted).toBe(true);
    expect(sb.settings).toBeNull();
    expect(sb.words).toEqual([]);
    expect(sb.progress).toEqual([]);
    // Signed out in this browser: the session is gone and the header offers sign-in.
    await expect(page.getByTestId("sign-in")).toBeVisible();
    await expect.poll(() => page.evaluate((k) => window.localStorage.getItem(k), STORAGE_KEY)).toBeNull();
    expect(sb.sent.some((r) => r.path === "/auth/v1/logout")).toBe(true);
    expect(await axeSerious(page)).toEqual([]);
    noOtherUser(sb);

    await done.getByRole("link", { name: "Back to the checker" }).click();
    await expect(page).toHaveURL(/\/$/);
    await page.goto("/settings");
    await expect(page.getByTestId("settings-signed-out")).toBeVisible();
  });

  test("a failed deletion keeps the dialog open, deletes nothing and stays signed in", async ({ page }) => {
    const sb = await openSettings(page, {
      ...CUSTOMISED,
      rpcErrors: { delete_my_account: { status: 500, body: { code: "XX000", message: "internal error" } } },
    });
    await page.getByTestId("delete-account-open").click();
    const dialog = page.getByTestId("delete-account-dialog");
    await dialog.getByTestId("delete-account-word").fill("delete");
    await dialog.getByTestId("delete-account-confirm").click();
    await expect(dialog.getByTestId("delete-account-problem")).toHaveText(
      "Your account could not be deleted just now. Try again; nothing was deleted.",
    );
    await expect(dialog).toBeVisible();
    await expect(dialog).not.toContainText("internal error");
    expect(sb.accountDeleted).toBe(false);
    expect(sb.sent.some((r) => r.path === "/auth/v1/logout")).toBe(false);
    await dialog.getByRole("button", { name: "Keep my account" }).click();
    await expect(page.getByTestId("muted-rule")).toHaveCount(2);
  });

  test("without the migration it says so and points to Report a problem", async ({ page }) => {
    const sb = await openSettings(page, {
      ...CUSTOMISED,
      rpcErrors: { delete_my_account: { status: 404, body: { code: "PGRST202", message: "Could not find the function" } } },
    });
    await page.getByTestId("delete-account-open").click();
    await page.getByTestId("delete-account-word").fill("delete");
    await page.getByTestId("delete-account-confirm").click();
    await expect(page.getByTestId("delete-account-problem")).toContainText("nothing was deleted");
    await expect(page.getByTestId("delete-account-problem")).toContainText("Report a problem");
    expect(sb.accountDeleted).toBe(false);
  });
});

for (const [width, scheme] of [
  [375, "light"],
  [375, "dark"],
  [1280, "dark"],
] as const) {
  test(`account controls at ${width}px, ${scheme}: no horizontal scroll, no serious axe violations`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await openSettings(page);
    const section = page.getByTestId("account-controls");
    await section.scrollIntoViewIfNeeded();
    const overflow = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(await overflow()).toBeLessThanOrEqual(0);
    expect(await axeSerious(page)).toEqual([]);
    await section.getByTestId("reset-preferences-open").click();
    expect(await axeSerious(page)).toEqual([]);
    await page.keyboard.press("Escape");
    await section.getByTestId("delete-account-open").click();
    await page.getByTestId("delete-account-confirm").click();
    expect(await overflow()).toBeLessThanOrEqual(0);
    expect(await axeSerious(page)).toEqual([]);
    const shots = process.env.SHOTS_DIR ?? "test-results/shots";
    await page.screenshot({ path: `${shots}/accounts-delete-account-${width}-${scheme}.png` });
  });
}

test("the Word pane links to the website's Settings for these, rather than repeating them", async ({ page }) => {
  await seedSession(page);
  await mockSupabase(page);
  await fakeOffice(page);
  await mockEngineAuth(page, (_c, route) => reply(route, 200, reviseResponse));
  await page.goto("/word");
  await page.getByTestId("tp-settings").locator("summary").click();
  const note = page.getByTestId("tp-account-controls");
  await expect(note).toContainText("To reset your preferences or delete your account, use Settings on the website");
  const link = note.getByTestId("tp-settings-link");
  await expect(link).toHaveAttribute("href", "/settings");
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(page.getByTestId("delete-account-open")).toHaveCount(0);
});

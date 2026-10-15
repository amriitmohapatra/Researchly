/**
 * The installable app (PLAN S6, "Installable PWA"; P5), against the
 * production build: the manifest and icons, the service worker registering,
 * the offline page, and that nothing the engine returns (or the text sent to
 * it) ever lands in the worker's caches. The /word taskpane never registers.
 */
import { expect, test, type Page } from "@playwright/test";
import { SAMPLE_TEXT } from "./fixtures";
import { check, mockEngine, paste } from "./helpers";

// Playwright's Chromium driver runs in this worker process and reads this
// when a service worker starts: with it, setOffline (and request events)
// reach the worker's own fetches too, so "offline" really is offline.
process.env.PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS = "1";

// Every other spec blocks service workers (playwright.config.ts); these need one.
test.use({ serviceWorkers: "allow" });

/** Waits for the worker to be active and in control of this page (it claims open pages on activate). */
async function controlled(page: Page): Promise<string> {
  return page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    if (!navigator.serviceWorker.controller) {
      await new Promise<void>((resolve) => navigator.serviceWorker.addEventListener("controllerchange", () => resolve(), { once: true }));
    }
    return reg.active?.scriptURL ?? "";
  });
}

/** Every cached entry: its cache, its URL and its body as text. */
async function cached(page: Page): Promise<{ cache: string; url: string; body: string }[]> {
  return page.evaluate(async () => {
    const out: { cache: string; url: string; body: string }[] = [];
    for (const name of await caches.keys()) {
      const cache = await caches.open(name);
      for (const req of await cache.keys()) {
        const res = await cache.match(req);
        out.push({ cache: name, url: req.url, body: res ? await res.text() : "" });
      }
    }
    return out;
  });
}

test("the manifest is linked and installable: name, standalone, colours, icons", async ({ page, request }) => {
  await page.goto("/");
  const href = await page.locator('link[rel="manifest"]').getAttribute("href");
  expect(href).toBeTruthy();
  const res = await request.get(href!);
  expect(res.ok()).toBe(true);
  const m = await res.json();
  expect(m).toMatchObject({ name: "Researchly", short_name: "Researchly", start_url: "/", scope: "/", display: "standalone" });
  expect(m.theme_color).toBe("#f4f5f3");
  expect(m.icons.map((i: { purpose: string; sizes: string }) => `${i.sizes} ${i.purpose}`)).toEqual([
    "192x192 any",
    "512x512 any",
    "192x192 maskable",
    "512x512 maskable",
  ]);
  for (const icon of m.icons as { src: string }[]) {
    const r = await request.get(icon.src);
    expect(r.ok(), icon.src).toBe(true);
    expect(r.headers()["content-type"]).toBe("image/png");
  }
  const apple = await page.locator('link[rel="apple-touch-icon"]').getAttribute("href");
  expect((await request.get(apple!)).ok()).toBe(true);
  await expect(page.locator('meta[name="theme-color"]')).toHaveCount(2);
});

test("the service worker registers, and a check leaves no text or engine reply in its caches", async ({ page }) => {
  const sent = await mockEngine(page);
  const engineReplies: boolean[] = [];
  page.on("response", (r) => {
    if (r.url().includes("/v1/analyze")) engineReplies.push(r.fromServiceWorker());
  });
  await page.goto("/");
  expect(await controlled(page)).toMatch(/\/sw\.js$/);
  // A check with the worker in control: the engine (mocked at its own origin) still answers.
  await paste(page, SAMPLE_TEXT);
  await check(page);
  await expect(page.getByTestId("results")).toBeVisible();
  expect(sent).toHaveLength(1);
  // The worker never answered for the engine: the reply came from the network.
  expect(engineReplies).toEqual([false]);
  // A second page load, served through the worker.
  await page.reload();
  await expect(page.getByLabel("Text to check")).toBeVisible();

  const entries = await cached(page);
  expect(entries.length).toBeGreaterThan(0);
  const origin = new URL(page.url()).origin;
  for (const e of entries) {
    expect(e.cache, e.url).toMatch(/^researchly-(shell|static)-v\d+$/);
    const u = new URL(e.url);
    expect(u.origin, e.url).toBe(origin);
    expect(u.pathname, e.url).toMatch(/^\/(_next\/static\/|icons\/|icon\.svg$|offline\.(html|css)$)/);
    expect(u.search, e.url).toBe("");
    // Not a word of the draft, in any cached file.
    expect(e.body, e.url).not.toContain("reporting delay varied");
  }
  expect(entries.some((e) => e.url.includes("/_next/static/"))).toBe(true);
});

test("offline, a page shows the offline note instead of a browser error", async ({ page, context }) => {
  await mockEngine(page);
  await page.goto("/");
  await controlled(page);
  // The network drops, for the page and for the worker's own fetches (see the flag at the top).
  await context.setOffline(true);
  await page.goto("/learn").catch(() => undefined);
  await expect(page.getByTestId("offline-page")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Researchly needs a connection to check your writing");
  await expect(page.getByText("Nothing you wrote is kept on this device")).toBeVisible();
  // The offline page's own stylesheet came from the worker's cache (the CSP allows no inline style).
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(244, 245, 243)");
  await context.setOffline(false);
  await page.getByRole("link", { name: "Try again" }).click();
  await expect(page.getByLabel("Text to check")).toBeVisible();
});

test("the Word taskpane never registers a service worker", async ({ page }) => {
  // office.js is Microsoft's; here it is simply absent (the pane shows its "outside Word" state).
  await page.route("https://appsforoffice.microsoft.com/**", (route) => route.fulfill({ status: 200, contentType: "text/javascript", body: "" }));
  await page.goto("/word");
  await page.waitForLoadState("networkidle");
  // Give a registration, if there were one, time to happen.
  await page.waitForTimeout(500);
  expect(await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length)).toBe(0);
});

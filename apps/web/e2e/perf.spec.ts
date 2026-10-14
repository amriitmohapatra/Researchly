/**
 * Rendering cost on a thesis-sized result (2026-10-14 performance pass).
 * A measurement, not a test: skipped unless PERF=1, and it asserts only
 * that the page works. Run:
 *
 *   PERF=1 E2E_PORT=3340 npx playwright test --project=chromium e2e/perf.spec.ts
 *
 * The text and its suggestions come from e2e/long-document.ts (a fixed
 * seed): a synthetic ~40,000-word document with ~1,200 placed suggestions,
 * cloned from the sample cards (no real writing). Every number is taken inside the
 * page: from the action to the frame after the DOM shows its result, plus
 * the long tasks (> 50 ms) the main thread ran meanwhile. Results go to the
 * test's attachments and to stdout as one JSON line ("PERF {...}").
 */
import { expect, test, type Page } from "@playwright/test";
import type { AnalyzeWordResponse, WordSuggestion } from "@researchly/contract";
import { ENGINE } from "./fixtures";
import { json, mockEngine } from "./helpers";
import { longDocument as generate, longResponse, SECTIONS } from "./long-document";
import { fakeOffice, fulfillJson, mockWordEngine, reviseResponse } from "./word-fixtures";

test.skip(!process.env.PERF, "performance measurement: run with PERF=1");
test.describe.configure({ mode: "serial" });
// Playwright's trace snapshots the whole DOM around every action: on a page
// with a thousand cards that is most of the main thread's time.
test.use({ trace: "off" });

const WORDS = Number(process.env.PERF_WORDS ?? 40_000);
const EVERY = Number(process.env.PERF_EVERY ?? 33); // a suggestion per this many words
const longDocument = () => generate(WORDS, EVERY);

/** In the page: long tasks since load, and a way to wait for the frame after a condition holds. */
async function instrument(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __long: { start: number; duration: number }[] };
    w.__long = [];
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) w.__long.push({ start: e.startTime, duration: e.duration });
    }).observe({ type: "longtask", buffered: true });
    // Actions and conditions by name: the page's CSP forbids eval, so no strings of code.
    const q = (s: string) => document.querySelector<HTMLElement>(s)!;
    const cards = () => document.querySelectorAll('[data-testid="suggestion-card"]').length;
    const lastWordCard = () => [...document.querySelectorAll<HTMLElement>('[data-testid="word-card"]')].pop()!;
    const select = (v: string) => {
      const s = q('[data-testid="section-filter"]') as HTMLSelectElement;
      s.value = v;
      s.dispatchEvent(new Event("change", { bubbles: true }));
    };
    (window as unknown as { __perf: unknown }).__perf = {
      act: {
        check: () => q('[data-testid="check"]').click(),
        chip: (c: string) => q(`[data-testid="filter-${c}"]`).click(),
        section: select,
        show: (id: string) => document.getElementById(`card-${id}`)!.querySelector("button")!.click(),
        mark: (id: string) => document.querySelector<HTMLElement>(`[data-testid="document"] mark[data-sids~="${id}"]`)!.click(),
        wordCheck: () => q('[data-testid="check-document"]').click(),
        wordSelect: () => lastWordCard().querySelector<HTMLElement>('[data-testid="select-in-document"]')!.click(),
      },
      done: {
        results: () => cards() > 0 && document.querySelectorAll('[data-testid="document"] mark').length > 0,
        chip: ([c, n]: [string, number]) => q(`[data-testid="filter-${c}"]`).getAttribute("aria-pressed") === "true" && cards() === n,
        cards: (n: number) => cards() === n,
        section: (n: number) =>
          document.querySelectorAll("ol.cards > li").length <= n && document.querySelector('[data-testid="section-blurb"]') !== null,
        activeMark: () => Boolean(document.activeElement?.matches("mark.is-active")),
        // The card a highlight opens is focused and on screen (cards above it may never have been laid out).
        cardInView: (id: string) => {
          const el = document.getElementById(`card-${id}`);
          if (!el || document.activeElement !== el) return false;
          const r = el.getBoundingClientRect();
          return r.top >= 0 && r.bottom <= window.innerHeight;
        },
        wordCards: (n: number) => document.querySelectorAll('[data-testid="word-card"]').length === n,
        wordSelected: () =>
          lastWordCard().classList.contains("is-active") &&
          (window as unknown as { __fakeWord: { selection: unknown } }).__fakeWord.selection !== null,
      },
    };
  });
}

type Step = [name: string, arg?: unknown];

/**
 * Run the action `act` (in the page), then wait until the condition `done`
 * holds and a frame has been produced after it. Returns ms from the action
 * to that frame, ms to the first frame after the action (how long the
 * input waited for an answer), and the long-task time inside the interval.
 */
async function timed(
  page: Page,
  act: Step,
  done: Step,
): Promise<{ ms: number; firstFrame: number; longTaskMs: number; longest: number; end: number }> {
  return page.evaluate(
    async ([act, done]) => {
      type Fn = (arg?: unknown) => unknown;
      const perf = (window as unknown as { __perf: { act: Record<string, Fn>; done: Record<string, Fn> } }).__perf;
      const frame = () => new Promise<void>((r) => requestAnimationFrame(() => setTimeout(r, 0)));
      const t0 = performance.now();
      perf.act[act[0]]!(act[1]);
      // The first frame after the action: how long the page took to answer the input at all.
      await frame();
      const firstFrame = performance.now() - t0;
      const deadline = t0 + 60_000;
      while (!perf.done[done[0]]!(done[1])) {
        if (performance.now() > deadline) throw new Error(`timed out waiting for ${done[0]}`);
        await frame();
      }
      await frame();
      const t1 = performance.now();
      const long = (window as unknown as { __long: { start: number; duration: number }[] }).__long.filter(
        (l) => l.start >= t0 - 1 && l.start < t1,
      );
      return {
        ms: Math.round(t1 - t0),
        firstFrame: Math.round(firstFrame),
        longTaskMs: Math.round(long.reduce((a, l) => a + l.duration, 0)),
        longest: Math.round(Math.max(0, ...long.map((l) => l.duration))),
        end: t1,
      };
    },
    [act, done] as const,
  );
}

/** PERF_PROFILE=dir: a V8 CPU profile of one phase, saved as dir/<name>.cpuprofile. */
async function profiled<T>(page: Page, name: string, run: () => Promise<T>): Promise<T> {
  const dir = process.env.PERF_PROFILE;
  if (!dir) return run();
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Profiler.enable");
  await cdp.send("Profiler.setSamplingInterval", { interval: 200 });
  await cdp.send("Profiler.start");
  const out = await run();
  const { profile } = await cdp.send("Profiler.stop");
  const fs = await import("node:fs");
  fs.writeFileSync(`${dir}/${name}.cpuprofile`, JSON.stringify(profile));
  await cdp.detach();
  return out;
}

/** Input-to-next-frame latency of each keystroke typed into the composer. */
async function typingLatency(page: Page, keys: string): Promise<{ p50: number; p95: number; max: number; n: number }> {
  await page.evaluate(() => {
    const w = window as unknown as { __keys: number[]; __keysOn?: boolean };
    w.__keys = [];
    if (w.__keysOn) return;
    w.__keysOn = true;
    document.addEventListener(
      "input",
      (e) => {
        const t = e.timeStamp;
        requestAnimationFrame(() => setTimeout(() => w.__keys.push(performance.now() - t), 0));
      },
      { capture: true },
    );
  });
  const box = page.getByLabel("Text to check");
  await box.focus();
  await page.keyboard.press("Control+End");
  for (const k of keys) {
    await page.keyboard.type(k);
    await page.waitForTimeout(40);
  }
  await page.waitForTimeout(400);
  const xs = (await page.evaluate(() => (window as unknown as { __keys: number[] }).__keys)).sort((a, b) => a - b);
  const q = (p: number) => Math.round(xs[Math.min(xs.length - 1, Math.floor(p * (xs.length - 1)))]!);
  return { p50: q(0.5), p95: q(0.95), max: Math.round(xs[xs.length - 1]!), n: xs.length };
}

test("a thesis-sized result: check, filter, section, show in text, typing", async ({ page }, info) => {
  test.setTimeout(240_000);
  const { text, suggestions } = longDocument();
  const big = longResponse(suggestions);
  await instrument(page);
  await mockEngine(page, async (_req, route) => json(route, 200, big));
  if (process.env.PERF_REDUCED_MOTION) await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  // PERF_CSS: try a stylesheet change without a rebuild.
  if (process.env.PERF_CSS) {
    await page.evaluate((css) => {
      const sheet = new CSSStyleSheet();
      sheet.replaceSync(css);
      document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
    }, process.env.PERF_CSS);
  }
  await page.getByLabel("Text to check").fill(text);
  await page.waitForTimeout(500);

  const result: Record<string, unknown> = { words: text.split(/\s+/).length, chars: text.length, suggestions: suggestions.length };
  result.typing_before_check = await typingLatency(page, " and the model was fitted again");
  await page.getByLabel("Text to check").fill(text);
  await page.waitForTimeout(500);
  const count = (sel: string) => page.evaluate((s) => document.querySelectorAll(s).length, sel);
  result.check_to_cards = await profiled(page, "check", () => timed(page, ["check"], ["results"]));
  // The engine's answer arrived at the fetch's responseEnd: what follows is the page's own work.
  const shownAt = (result.check_to_cards as { end: number }).end;
  result.response_to_cards_ms = await page.evaluate((end) => {
    const f = performance.getEntriesByType("resource").filter((e) => e.name.endsWith("/v1/analyze")).pop() as PerformanceResourceTiming;
    return Math.round(end - f.responseEnd);
  }, shownAt);
  result.cards_rendered = await count('[data-testid="suggestion-card"]');
  result.marks_rendered = await count('[data-testid="document"] mark');
  await page.waitForTimeout(300);

  const improvements = suggestions.filter((s) => s.category === "improvement").length;
  result.filter_chip = await timed(page, ["chip", "improvement"], ["chip", ["improvement", improvements]]);
  await page.waitForTimeout(300);
  result.filter_back_to_all = await profiled(page, "filter-all", () => timed(page, ["chip", "all"], ["cards", suggestions.length]));
  await page.waitForTimeout(300);

  const inMethods = suggestions.filter((s) => s.section === "methods").length;
  result.section_switch = await timed(page, ["section", "methods"], ["section", inMethods + 50]);
  await page.waitForTimeout(300);
  result.section_back_to_all = await timed(page, ["section", "all"], ["cards", suggestions.length]);
  await page.waitForTimeout(300);

  // "Show in text" on the last card: the highlight becomes active and is focused.
  const last = suggestions[suggestions.length - 1]!.id;
  result.show_in_text = await timed(page, ["show", last], ["activeMark"]).catch((e: Error) => e.message.slice(0, 80));
  await page.waitForTimeout(300);
  // And back: a highlight near the end opens its card, focused and in view.
  await page.evaluate(() => window.scrollTo(0, 0));
  const nearEnd = suggestions[suggestions.length - 5]!.id;
  result.mark_to_card = await timed(page, ["mark", nearEnd], ["cardInView", nearEnd]).catch(async (e: Error) => {
    const where = await page.evaluate((id) => {
      const el = document.getElementById(`card-${id}`)!;
      const r = el.getBoundingClientRect();
      return { top: Math.round(r.top), bottom: Math.round(r.bottom), vh: window.innerHeight, focused: document.activeElement === el };
    }, nearEnd);
    return `${e.message.slice(0, 40)} ${JSON.stringify(where)}`;
  });
  result.card_height_avg = await page.evaluate(() => {
    const li = [...document.querySelectorAll("ol.cards > li")].slice(0, 60);
    return Math.round(li.reduce((a, x) => a + x.getBoundingClientRect().height, 0) / Math.max(1, li.length));
  });
  await page.waitForTimeout(300);

  // PERF_TRACE=dir: a Chrome trace of the typing, for where the time goes.
  const traceDir = process.env.PERF_TRACE;
  if (traceDir) await page.context().browser()!.startTracing(page, { path: `${traceDir}/typing.json`, screenshots: false });
  result.typing_with_results = await profiled(page, "typing", () => typingLatency(page, " and the model was fitted again"));
  if (traceDir) await page.context().browser()!.stopTracing();
  info.attachments.push({ name: "perf.json", contentType: "application/json", body: Buffer.from(JSON.stringify(result, null, 2)) });
  console.log(`PERF ${JSON.stringify(result)}`);
  expect(result.cards_rendered).toBe(suggestions.length);
});

/* ---------- the Word taskpane (/word, fake Office) ---------- */

function wordWorkload() {
  const { text, suggestions } = longDocument();
  const parts = text.split("\n\n");
  if (parts[parts.length - 1] === "") parts.pop();
  const offsets: number[] = [];
  let pos = 0;
  for (const p of parts) {
    offsets.push(pos);
    pos += p.length + 2;
  }
  const headings = new Set(SECTIONS.map((s) => `${s[0]!.toUpperCase()}${s.slice(1)}`));
  const paragraphs = parts.map((t) => ({ text: t, styleBuiltIn: headings.has(t) ? "Heading1" : "Normal" }));
  const words: WordSuggestion[] = suggestions.map((s) => {
    let p = 0;
    while (p + 1 < offsets.length && offsets[p + 1]! <= s.span.start) p++;
    const start = s.span.start - offsets[p]!;
    const end = s.span.end - offsets[p]!;
    const occurrence = parts[p]!.slice(0, start).split(s.text).length - 1;
    return { ...s, location: { paragraph: p, start, end, snippet: s.text, occurrence, exact: true } };
  });
  const counts: Record<string, number> = {};
  for (const s of words) counts[s.category] = (counts[s.category] ?? 0) + 1;
  const response: AnalyzeWordResponse = {
    ...reviseResponse,
    suggestions: words,
    counts,
    sections_detected: [...SECTIONS],
    coverage: { paragraphs: paragraphs.length, table_paragraphs: 0, not_checked: [] },
  };
  return { paragraphs, response };
}

test("the Word taskpane on a thesis-sized document: check, select a card", async ({ page }, info) => {
  test.setTimeout(240_000);
  const { paragraphs, response } = wordWorkload();
  await instrument(page);
  await fakeOffice(page, { paragraphs });
  await mockWordEngine(page, ENGINE, { respond: (_req, route) => fulfillJson(route, 200, response) });
  await page.goto("/word");
  await expect(page.getByTestId("check-document")).toBeEnabled();
  const result: Record<string, unknown> = { paragraphs: paragraphs.length, suggestions: response.suggestions.length };
  result.check_to_cards = await profiled(page, "word-check", () =>
    timed(page, ["wordCheck"], ["wordCards", response.suggestions.length]),
  );
  await page.waitForTimeout(300);
  const last = response.suggestions[response.suggestions.length - 1]!.id;
  result.select_last_card = await timed(page, ["wordSelect", last], ["wordSelected"]);
  result.card_height_avg = await page.evaluate(() => {
    const cards = [...document.querySelectorAll('[data-testid="word-card"]')].slice(0, 30);
    return Math.round(cards.reduce((a, x) => a + x.getBoundingClientRect().height, 0) / Math.max(1, cards.length));
  });
  info.attachments.push({ name: "perf-word.json", contentType: "application/json", body: Buffer.from(JSON.stringify(result, null, 2)) });
  console.log(`PERF-WORD ${JSON.stringify(result)}`);
  expect(result.check_to_cards).toBeTruthy();
});

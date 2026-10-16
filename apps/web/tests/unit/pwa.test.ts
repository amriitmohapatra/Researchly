/**
 * The installable app (PLAN S6, "Installable PWA"; P5): the manifest, the
 * icons, when the service worker is registered, and the worker itself.
 *
 * The worker's file (public/sw.js) is loaded as it ships and driven with
 * fake requests, caches and network, to prove it never stores a POST, an
 * engine or Supabase reply, or a page (confidential by design, CLAUDE.md #2).
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { describe, expect, it, vi } from "vitest";
import { TOKENS } from "@researchly/design-tokens";
import manifest from "@/app/manifest";
import { PWA_ICONS, shouldRegisterServiceWorker } from "@/lib/pwa";

const appRoot = path.resolve(__dirname, "../..");
const ORIGIN = "https://researchly.example";
const ENGINE = "https://engine.example";
const SUPABASE = "https://abcdefgh.supabase.co";

/* ---------- the worker, loaded from public/sw.js ---------- */

type Req = { method: string; url: string; mode: string };
interface Sw {
  VERSION: string;
  SHELL_CACHE: string;
  STATIC_CACHE: string;
  OFFLINE_URL: string;
  PRECACHE: string[];
  route(r: Req, origin: string): "static" | "page" | "network";
  isCacheable(r: Req, res: Response | { status: number; type: string; headers: Headers }, origin: string): boolean;
  install(e: unknown, scope: unknown): void;
  activate(e: unknown, scope: unknown): void;
  onFetch(e: unknown, origin: string): void;
}

/** An in-memory Cache Storage that records every put. */
function fakeCaches(seed: Record<string, Record<string, Response>> = {}) {
  const store = new Map<string, Map<string, Response>>();
  for (const [name, entries] of Object.entries(seed)) store.set(name, new Map(Object.entries(entries)));
  const puts: { cache: string; url: string }[] = [];
  const key = (r: Req | string) => (typeof r === "string" ? new URL(r, ORIGIN).href : r.url);
  const open = async (name: string) => {
    if (!store.has(name)) store.set(name, new Map());
    const m = store.get(name)!;
    return {
      put: async (r: Req, res: Response) => {
        puts.push({ cache: name, url: key(r) });
        m.set(key(r), res);
      },
      addAll: async (urls: string[]) => {
        for (const u of urls) m.set(key(u), new Response(`precached ${u}`, { status: 200 }));
      },
      keys: async () => [...m.keys()].map((url) => ({ url })),
      delete: async (r: { url: string }) => m.delete(r.url),
    };
  };
  return {
    store,
    puts,
    api: {
      open,
      keys: async () => [...store.keys()],
      delete: async (name: string) => store.delete(name),
      match: async (r: Req | string) => {
        for (const m of store.values()) {
          const hit = m.get(key(r));
          if (hit) return hit;
        }
        return undefined;
      },
    },
  };
}

function loadWorker(caches: unknown, fetchImpl: (r: Req) => Promise<unknown>): Sw {
  const src = readFileSync(path.join(appRoot, "public/sw.js"), "utf8");
  const cjs = { exports: {} as Sw };
  vm.runInNewContext(src, { module: cjs, caches, fetch: fetchImpl, URL, Response, Headers, Promise });
  return cjs.exports;
}

function basic(body: string, init: { status?: number; headers?: Record<string, string>; type?: string } = {}) {
  const res = new Response(body, { status: init.status ?? 200, headers: init.headers });
  // A browser marks same-origin replies "basic"; Node's Response is "default".
  Object.defineProperty(res, "type", { value: init.type ?? "basic" });
  return res;
}

/** A FetchEvent stand-in: records whether the worker answered, and with what. */
function fetchEvent(request: Req) {
  let answer: Promise<Response> | null = null;
  return {
    request,
    respondWith: vi.fn((p: Promise<Response>) => {
      answer = p;
    }),
    get answer() {
      return answer;
    },
  };
}

const GET = (url: string, mode = "cors"): Req => ({ method: "GET", url, mode });
const POST = (url: string): Req => ({ method: "POST", url, mode: "cors" });

describe("service worker routing (public/sw.js)", () => {
  const sw = loadWorker(fakeCaches().api, async () => basic("x"));

  it("never answers a POST, wherever it goes", () => {
    for (const url of [`${ENGINE}/v1/analyze`, `${ENGINE}/v1/analyze-file`, `${SUPABASE}/rest/v1/rpc/mute_rule`, `${ORIGIN}/`, `${ORIGIN}/_next/static/a.js`]) {
      expect(sw.route(POST(url), ORIGIN), url).toBe("network");
    }
  });

  it("never answers another origin: the engine and Supabase go straight to the network", () => {
    for (const url of [`${ENGINE}/v1/rules`, `${ENGINE}/v1/health`, `${SUPABASE}/auth/v1/user`, `${SUPABASE}/rest/v1/user_settings?select=*`, `http://localhost:3517/v1/health`]) {
      expect(sw.route(GET(url), ORIGIN), url).toBe("network");
    }
  });

  it("leaves the Word taskpane alone, its page and its scripts", () => {
    expect(sw.route(GET(`${ORIGIN}/word`, "navigate"), ORIGIN)).toBe("network");
    expect(sw.route(GET(`${ORIGIN}/word/office-guard.js`), ORIGIN)).toBe("network");
  });

  it("pages are network-only (with the offline fallback); app code, icons and the offline page are static", () => {
    expect(sw.route(GET(`${ORIGIN}/`, "navigate"), ORIGIN)).toBe("page");
    expect(sw.route(GET(`${ORIGIN}/settings`, "navigate"), ORIGIN)).toBe("page");
    expect(sw.route(GET(`${ORIGIN}/_next/static/chunks/app-1a2b.js`), ORIGIN)).toBe("static");
    expect(sw.route(GET(`${ORIGIN}/_next/static/css/9f.css`), ORIGIN)).toBe("static");
    expect(sw.route(GET(`${ORIGIN}/icons/icon-192.png`), ORIGIN)).toBe("static");
    expect(sw.route(GET(`${ORIGIN}/offline.html`), ORIGIN)).toBe("static");
    expect(sw.route(GET(`${ORIGIN}/icon.svg`), ORIGIN)).toBe("static");
  });

  it("everything else is untouched: data requests, the demo manuscript, the manifest, queries", () => {
    for (const p of ["/?_rsc=abc", "/settings?_rsc=1", "/demo/researchly-demo.md", "/manifest.webmanifest", "/_next/image?url=x", "/_next/static/a.js?dpl=7", "/sw.js"]) {
      expect(sw.route(GET(`${ORIGIN}${p}`), ORIGIN), p).toBe("network");
    }
  });

  it("stores only a plain 200 of a static route from this site", () => {
    const js = GET(`${ORIGIN}/_next/static/chunks/a.js`);
    expect(sw.isCacheable(js, basic("x"), ORIGIN)).toBe(true);
    expect(sw.isCacheable(js, basic("x", { status: 206 }), ORIGIN)).toBe(false);
    expect(sw.isCacheable(js, basic("x", { status: 404 }), ORIGIN)).toBe(false);
    expect(sw.isCacheable(js, basic("x", { type: "opaque" }), ORIGIN)).toBe(false);
    expect(sw.isCacheable(js, basic("x", { headers: { "cache-control": "no-store" } }), ORIGIN)).toBe(false);
    expect(sw.isCacheable(js, basic("x", { headers: { "cache-control": "private, max-age=0" } }), ORIGIN)).toBe(false);
    expect(sw.isCacheable(GET(`${ENGINE}/v1/rules`), basic("{}"), ORIGIN)).toBe(false);
    expect(sw.isCacheable(POST(`${ORIGIN}/_next/static/chunks/a.js`), basic("x"), ORIGIN)).toBe(false);
    expect(sw.isCacheable(GET(`${ORIGIN}/`, "navigate"), basic("<html>"), ORIGIN)).toBe(false);
  });

  it("names its caches with the version", () => {
    expect(sw.SHELL_CACHE).toBe(`researchly-shell-${sw.VERSION}`);
    expect(sw.STATIC_CACHE).toBe(`researchly-static-${sw.VERSION}`);
    expect(sw.PRECACHE).toContain(sw.OFFLINE_URL);
  });
});

describe("service worker handlers (public/sw.js)", () => {
  it("a check, an upload, Supabase and a page go by without a single cache write", async () => {
    const c = fakeCaches();
    const network = vi.fn(async (r: Req) => basic(`reply for ${r.method} ${r.url}: the draft text`));
    const sw = loadWorker(c.api, network);
    const requests = [
      POST(`${ENGINE}/v1/analyze`),
      POST(`${ENGINE}/v1/analyze-file`),
      POST(`${ENGINE}/v1/check-paragraphs`),
      GET(`${ENGINE}/v1/rules`),
      GET(`${SUPABASE}/rest/v1/user_settings`),
      POST(`${SUPABASE}/rest/v1/rpc/mute_rule`),
      GET(`${ORIGIN}/?_rsc=1`),
      GET(`${ORIGIN}/word`, "navigate"),
      GET(`${ORIGIN}/demo/researchly-demo.md`),
    ];
    for (const r of requests) {
      const e = fetchEvent(r);
      sw.onFetch(e, ORIGIN);
      expect(e.respondWith, r.url).not.toHaveBeenCalled();
    }
    const nav = fetchEvent(GET(`${ORIGIN}/`, "navigate"));
    sw.onFetch(nav, ORIGIN);
    expect(nav.respondWith).toHaveBeenCalledTimes(1);
    expect(await (await nav.answer!).text()).toContain(`${ORIGIN}/`);
    expect(c.puts).toEqual([]);
    // The worker did not fetch the passed-through requests itself: the browser did (no answer).
    expect(network).toHaveBeenCalledTimes(1);
  });

  it("a page shows the offline page when the network fails, and is never stored", async () => {
    const c = fakeCaches({ "researchly-shell-v1": { [`${ORIGIN}/offline.html`]: new Response("offline page") } });
    const sw = loadWorker(c.api, async () => {
      throw new TypeError("Failed to fetch");
    });
    const e = fetchEvent(GET(`${ORIGIN}/settings`, "navigate"));
    sw.onFetch(e, ORIGIN);
    expect(await (await e.answer!).text()).toBe("offline page");
    expect(c.puts).toEqual([]);
  });

  it("app code is cache-first: fetched once, stored once, then served from the cache", async () => {
    const c = fakeCaches();
    const network = vi.fn(async () => basic("chunk"));
    const sw = loadWorker(c.api, network);
    const url = `${ORIGIN}/_next/static/chunks/app-1.js`;
    for (let i = 0; i < 2; i += 1) {
      const e = fetchEvent(GET(url));
      sw.onFetch(e, ORIGIN);
      expect(await (await e.answer!).text()).toBe("chunk");
    }
    expect(network).toHaveBeenCalledTimes(1);
    expect(c.puts).toEqual([{ cache: sw.STATIC_CACHE, url }]);
  });

  it("a failed or partial reply for app code is passed on but not stored", async () => {
    const c = fakeCaches();
    const sw = loadWorker(c.api, async () => basic("missing", { status: 404 }));
    const e = fetchEvent(GET(`${ORIGIN}/_next/static/chunks/gone.js`));
    sw.onFetch(e, ORIGIN);
    expect((await e.answer!).status).toBe(404);
    expect(c.puts).toEqual([]);
  });

  it("install precaches the offline page; activate deletes other versions' caches only", async () => {
    const c = fakeCaches({ "researchly-static-v0": {}, "researchly-shell-v0": {}, "someone-elses-cache": {} });
    const sw = loadWorker(c.api, async () => basic("x"));
    const waits: Promise<unknown>[] = [];
    const event = { waitUntil: (p: Promise<unknown>) => waits.push(p) };
    const scope = { skipWaiting: vi.fn(async () => undefined), clients: { claim: vi.fn(async () => undefined) } };
    sw.install(event, scope);
    await Promise.all(waits);
    expect(await c.api.match(`${ORIGIN}/offline.html`)).toBeDefined();
    expect(scope.skipWaiting).toHaveBeenCalled();
    sw.activate(event, scope);
    await Promise.all(waits);
    expect((await c.api.keys()).sort()).toEqual([sw.SHELL_CACHE, "someone-elses-cache"].sort());
    expect(scope.clients.claim).toHaveBeenCalled();
  });
});

/* ---------- registration ---------- */

describe("when the service worker is registered (lib/pwa.ts)", () => {
  const base = { production: true, pathname: "/", supported: true, framed: false };
  it("production builds, outside the Word taskpane, in a top-level window", () => {
    expect(shouldRegisterServiceWorker(base)).toBe(true);
    expect(shouldRegisterServiceWorker({ ...base, pathname: "/settings" })).toBe(true);
  });
  it("never in development, without support, in a frame, or on /word", () => {
    expect(shouldRegisterServiceWorker({ ...base, production: false })).toBe(false);
    expect(shouldRegisterServiceWorker({ ...base, supported: false })).toBe(false);
    expect(shouldRegisterServiceWorker({ ...base, framed: true })).toBe(false);
    expect(shouldRegisterServiceWorker({ ...base, pathname: "/word" })).toBe(false);
    expect(shouldRegisterServiceWorker({ ...base, pathname: "/word/" })).toBe(false);
  });
});

/* ---------- manifest and icons ---------- */

/** Width and height from a PNG's IHDR chunk. */
function pngSize(file: string): { width: number; height: number; colourType: number } {
  const b = readFileSync(path.join(appRoot, file));
  expect(b.subarray(1, 4).toString("latin1")).toBe("PNG");
  return { width: b.readUInt32BE(16), height: b.readUInt32BE(20), colourType: b[25]! };
}

describe("web app manifest (app/manifest.ts)", () => {
  const m = manifest();

  it("installs as a standalone app named Researchly, scoped to the whole site", () => {
    expect(m.name).toBe("Researchly");
    expect(m.short_name).toBe("Researchly");
    expect(m.start_url).toBe("/");
    expect(m.scope).toBe("/");
    expect(m.id).toBe("/");
    expect(m.display).toBe("standalone");
    expect(m.lang).toBe("en-GB");
    expect(m.description).toMatch(/never drafts/);
  });

  it("takes its colours from the design tokens", () => {
    expect(m.background_color).toBe(TOKENS["surface.page"].light);
    expect(m.theme_color).toBe(TOKENS["surface.page"].light);
  });

  it("lists 192 and 512 icons, plain and maskable, and each file has its stated size", () => {
    expect(m.icons).toEqual([...PWA_ICONS]);
    const purposes = new Set(PWA_ICONS.map((i) => `${i.sizes} ${i.purpose}`));
    for (const want of ["192x192 any", "512x512 any", "192x192 maskable", "512x512 maskable"]) expect(purposes).toContain(want);
    for (const icon of PWA_ICONS) {
      const [w, h] = icon.sizes.split("x").map(Number);
      const size = pngSize(`public${icon.src}`);
      expect([size.width, size.height], icon.src).toEqual([w, h]);
    }
  });

  it("has a 180px Apple touch icon (app/apple-icon.png, linked by Next.js)", () => {
    const s = pngSize("app/apple-icon.png");
    expect([s.width, s.height]).toEqual([180, 180]);
  });
});

describe("offline page (public/offline.html)", () => {
  const html = readFileSync(path.join(appRoot, "public/offline.html"), "utf8");
  const css = readFileSync(path.join(appRoot, "public/offline.css"), "utf8");

  it("says the checker needs a connection, offers local mode, and keeps nothing", () => {
    expect(html).toContain("needs a connection");
    expect(html).toMatch(/local mode/);
    expect(html).toMatch(/Nothing you wrote is kept on this device/);
    expect(html).toMatch(/href="\/"/);
  });

  it("works under the CSP: no script and no inline style", () => {
    expect(html).not.toMatch(/<script/i);
    expect(html).not.toMatch(/<style|style="/i);
    expect(html).toContain('href="/offline.css"');
  });

  it("follows the house typography: curly apostrophes, no em dash", () => {
    const text = html.replace(/<[^>]+>/g, " ");
    expect(text).not.toMatch(/[A-Za-z]'[a-z]/);
    expect(text).not.toContain("—");
  });

  it("uses the design tokens' colours, light and dark", () => {
    const [light, dark] = css.split("@media (prefers-color-scheme: dark)");
    const pairs: [string, keyof typeof TOKENS][] = [
      ["--bg", "surface.page"],
      ["--ink", "text.primary"],
      ["--ink-2", "text.secondary"],
      ["--line", "line.hairline"],
      ["--accent", "accent.strong"],
      ["--accent-hover", "accent.hover"],
      ["--focus", "focus.strong"],
    ];
    for (const [v, token] of pairs) {
      expect(light, v).toContain(`${v}: ${TOKENS[token].light};`);
      expect(dark, v).toContain(`${v}: ${TOKENS[token].dark};`);
    }
    expect(html).toContain(`content="${TOKENS["surface.page"].light}"`);
    expect(html).toContain(`content="${TOKENS["surface.page"].dark}"`);
  });
});

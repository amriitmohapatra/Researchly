import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SPELLINGS } from "@researchly/contract";
import { SpellingSelect } from "@/components/SpellingSelect";
import { analyze, analyzeWord, buildFileRequest, buildRequest, buildWordRequest } from "@/lib/engine";
import { loadDocumentTypeChoice, loadSpellingChoice, saveSpellingChoice } from "@/lib/prefs";
import { isSpelling, resolveSpelling, SPELLING_CHOICES, SPELLING_HELP, SPELLING_LABELS } from "@/lib/spelling";

/* The account's spelling is read and written through supabase-js; this stands in for it. */
const db = vi.hoisted(() => ({
  row: null as Record<string, unknown> | null,
  error: null as { code?: string; message?: string } | null,
  upserts: [] as unknown[],
  selects: [] as string[],
}));

vi.mock("@/lib/supabase", () => ({
  getSupabase: () =>
    Promise.resolve({
      from: (table: string) => {
        expect(table).toBe("user_settings");
        return {
          select: (cols: string) => {
            db.selects.push(cols);
            return { maybeSingle: async () => ({ data: db.row, error: db.error }) };
          },
          upsert: async (row: unknown, opts: unknown) => {
            db.upserts.push({ row, opts });
            return { error: db.error };
          },
        };
      },
    }),
}));

const { loadSpelling, saveSpelling } = await import("@/lib/account");

describe("the choices", () => {
  it("are the engine's seven, in its order, Auto first, each with a label and a help line", () => {
    expect([...SPELLINGS]).toEqual(["auto", "us", "uk", "uk-oxford", "ca", "au", "in"]);
    expect(SPELLING_CHOICES.map((c) => c.id)).toEqual([...SPELLINGS]);
    expect(Object.keys(SPELLING_LABELS).sort()).toEqual([...SPELLINGS].sort());
    expect(SPELLING_CHOICES.map((c) => c.label)).toEqual([
      "Auto (follow the document)",
      "American",
      "British (-ise)",
      "British (Oxford -ize)",
      "Canadian",
      "Australian",
      "Indian (British spelling)",
    ]);
    for (const s of SPELLINGS) expect(SPELLING_HELP[s].trim().length, s).toBeGreaterThan(20);
    // Indian English is spelled as British English (owner, 2026-10-14).
    expect(SPELLING_HELP.in).toMatch(/British/);
    expect(SPELLING_HELP.uk).toMatch(/organise/);
    expect(SPELLING_HELP["uk-oxford"]).toMatch(/organize/);
  });

  it("isSpelling accepts exactly those values", () => {
    for (const s of SPELLINGS) expect(isSpelling(s), s).toBe(true);
    for (const bad of ["UK", "en-GB", "british", "", null, undefined, 7, ["uk"]]) expect(isSpelling(bad)).toBe(false);
  });
});

describe("which spelling a check sends", () => {
  it("this session's choice, else the account's (signed in), else this browser's, else none", () => {
    expect(resolveSpelling({ chosen: "ca", account: "uk", stored: "us", signedIn: true })).toBe("ca");
    expect(resolveSpelling({ chosen: null, account: "uk", stored: "us", signedIn: true })).toBe("uk");
    expect(resolveSpelling({ chosen: null, account: null, stored: "us", signedIn: true })).toBe("us");
    // Signed out, a stale account value (from before signing out) never applies.
    expect(resolveSpelling({ chosen: null, account: "uk", stored: "au", signedIn: false })).toBe("au");
    // Nothing chosen anywhere: the request leaves it to the engine.
    expect(resolveSpelling({ chosen: null, account: null, stored: null, signedIn: false })).toBeNull();
  });
});

describe("the option on every analysis request", () => {
  const minimal = { suggestions: [], health: [], hidden_preferences: 0, sections_detected: [], schema_version: "1" };
  afterEach(() => vi.unstubAllGlobals());

  it("is sent when chosen and left out otherwise (the engine then applies the account's, or Auto)", () => {
    const base = { content: "x", format: "plain" as const, showPreferences: false };
    expect(buildRequest({ ...base, spelling: "uk" }).options?.spelling).toBe("uk");
    expect(buildRequest(base).options).not.toHaveProperty("spelling");
    expect(buildRequest({ ...base, spelling: null }).options).not.toHaveProperty("spelling");
  });

  it("goes over the wire to /v1/analyze", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(minimal), { status: 200 })));
    await analyze({ content: "We analysed the colour.", format: "plain", showPreferences: false, spelling: "uk-oxford" }, "http://engine.test");
    const [url, init] = vi.mocked(fetch).mock.calls[0]!;
    expect(url).toBe("http://engine.test/v1/analyze");
    expect(JSON.parse(String(init!.body)).options.spelling).toBe("uk-oxford");
  });

  it("rides with a Word check and a file check", async () => {
    const paragraphs = [{ text: "The color scale.", style: "Normal", kind: "body" as const }];
    expect(buildWordRequest({ paragraphs, showPreferences: false, mode: "revise", spelling: "in" }).options?.spelling).toBe("in");
    expect(buildWordRequest({ paragraphs, showPreferences: false, mode: "revise" }).options).not.toHaveProperty("spelling");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ ...minimal, coverage: { paragraphs: 1, table_paragraphs: 0, not_checked: [] } }), { status: 200 })),
    );
    await analyzeWord({ paragraphs, showPreferences: false, mode: "draft", spelling: "au" }, "http://localhost:3517");
    const [, init] = vi.mocked(fetch).mock.calls[0]!;
    expect(JSON.parse(String(init!.body)).options.spelling).toBe("au");

    const file = Object.assign(new Blob(["x"]), { name: "paper.md" });
    const header = buildFileRequest(file, { showPreferences: false, spelling: "us" }, null).headers["x-researchly-options"];
    expect(JSON.parse(header!).spelling).toBe("us");
  });
});

describe("the selector", () => {
  it("lists the seven choices, shows the chosen one and says what it does", () => {
    const html = renderToStaticMarkup(<SpellingSelect id="sp" value="uk" onChange={() => {}} />);
    const values = [...html.matchAll(/<option value="([^"]+)"/g)].map((m) => m[1]);
    expect(values).toEqual([...SPELLINGS]);
    expect(html).toContain('<option value="uk" selected="">British (-ise)</option>');
    expect(html).toContain('<label for="sp" class="control-label">Spelling</label>');
    expect(html).toContain('data-testid="spelling"');
    expect(html).toContain(SPELLING_HELP.uk);
    expect(html).not.toContain('data-testid="spelling-note"');
  });

  it("says when a choice could not be saved to the account", () => {
    const html = renderToStaticMarkup(
      <SpellingSelect id="sp" value="auto" onChange={() => {}} note="This choice could not be saved to your account." />,
    );
    expect(html).toContain('data-testid="spelling-note"');
    expect(html).toContain("could not be saved");
    expect(html).toContain(SPELLING_HELP.auto);
  });
});

/** A window with just enough localStorage for prefs.ts; the unit suite runs without a DOM. */
function fakeWindow(store: Map<string, string>) {
  return {
    localStorage: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, String(v)),
    },
    addEventListener() {},
    removeEventListener() {},
  };
}

describe("remembered in this browser when signed out", () => {
  const store = new Map<string, string>();
  beforeEach(() => {
    store.clear();
    vi.stubGlobal("window", fakeWindow(store));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("round-trips under its own key, touching nothing else", () => {
    expect(loadSpellingChoice()).toBeNull();
    saveSpellingChoice("uk-oxford");
    expect(loadSpellingChoice()).toBe("uk-oxford");
    expect([...store.keys()]).toEqual(["researchly.spelling"]);
    expect(loadDocumentTypeChoice()).toBeNull();
  });

  it("ignores a value that is not a spelling (a tampered store)", () => {
    store.set("researchly.spelling", "klingon");
    expect(loadSpellingChoice()).toBeNull();
  });

  it("survives storage that throws (private mode)", () => {
    vi.stubGlobal("window", {
      localStorage: {
        getItem() {
          throw new Error("blocked");
        },
        setItem() {
          throw new Error("blocked");
        },
      },
    });
    expect(loadSpellingChoice()).toBeNull();
    expect(() => saveSpellingChoice("us")).not.toThrow();
  });
});

describe("kept with the account when signed in", () => {
  beforeEach(() => {
    db.row = null;
    db.error = null;
    db.upserts = [];
    db.selects = [];
  });

  it("reads the column on its own, and a row without one means no choice", async () => {
    db.row = { spelling: "ca" };
    expect(await loadSpelling()).toEqual({ ok: true, data: "ca" });
    expect(db.selects).toEqual(["spelling"]);
    db.row = null;
    expect(await loadSpelling()).toEqual({ ok: true, data: null });
    db.row = { spelling: "klingon" };
    expect(await loadSpelling()).toEqual({ ok: true, data: null });
  });

  it("an account database without the migration fails only this read, with a sentence", async () => {
    db.error = { code: "42703", message: "column user_settings.spelling does not exist" };
    const r = await loadSpelling();
    expect(r.ok).toBe(false);
    expect(!r.ok && r.message).not.toMatch(/column|42703/);
  });

  it("saves to the caller's own row (no user id is sent)", async () => {
    expect(await saveSpelling("uk")).toEqual({ ok: true, data: null });
    expect(db.upserts).toEqual([{ row: { spelling: "uk" }, opts: { onConflict: "user_id" } }]);
    db.error = { code: "23514", message: "violates check constraint user_settings_spelling_known" };
    const r = await saveSpelling("uk");
    expect(r.ok).toBe(false);
  });
});

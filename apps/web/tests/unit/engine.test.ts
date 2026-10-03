import { afterEach, describe, expect, it, vi } from "vitest";
import { analyze, listRules } from "@/lib/engine";

function respond(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })),
  );
}

const minimal = { suggestions: [], health: [], hidden_preferences: 0, sections_detected: [] };
const params = { content: "Some text.", format: "plain" as const, showPreferences: false };

afterEach(() => vi.unstubAllGlobals());

describe("contract version", () => {
  it("an analysis response must say schema_version 1 (regression: the check was loosened for every endpoint)", async () => {
    respond(minimal);
    const missing = await analyze(params, "http://engine.test");
    expect(!missing.ok && missing.error.message).toMatch(/expects version 1/);
    respond({ ...minimal, schema_version: "2" });
    const wrong = await analyze(params, "http://engine.test");
    expect(!wrong.ok && wrong.error.message).toMatch(/version 2/);
    respond({ ...minimal, schema_version: "1" });
    expect((await analyze(params, "http://engine.test")).ok).toBe(true);
  });

  it("/v1/rules has no version field and is still accepted", async () => {
    respond({ rules: [{ id: "G101", name: "n", short: "s" }] });
    const r = await listRules("http://engine.test");
    expect(r.ok && r.data.map((x) => x.id)).toEqual(["G101"]);
  });
});

describe("bearer header on the wire", () => {
  it("is sent when a token exists, and the token is never put anywhere else", async () => {
    respond({ ...minimal, schema_version: "1" });
    const auth = { token: async () => "tok-123", refresh: async () => ({ token: null }), signOutLocally: async () => {} };
    await analyze(params, "http://engine.test", auth);
    const [url, init] = vi.mocked(fetch).mock.calls[0]!;
    expect(String(url)).toBe("http://engine.test/v1/analyze");
    expect((init!.headers as Record<string, string>).authorization).toBe("Bearer tok-123");
    expect(String(init!.body)).not.toContain("tok-123");
    expect(init!.credentials).toBe("omit");
  });
});

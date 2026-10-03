import { describe, expect, it } from "vitest";
import { engineOrigin, normaliseEngineUrl } from "@/lib/config";
import { cspHeader, makeNonce, STATIC_SECURITY_HEADERS } from "@/lib/security";

const directive = (csp: string, name: string) =>
  csp
    .split(";")
    .map((d) => d.trim())
    .find((d) => d.startsWith(`${name} `));

describe("engine URL", () => {
  it("defaults to localhost:8080 and strips trailing slashes", () => {
    expect(normaliseEngineUrl(undefined)).toBe("http://localhost:8080");
    expect(normaliseEngineUrl("https://engine.example.org/")).toBe("https://engine.example.org");
    expect(normaliseEngineUrl("https://x.example/api//")).toBe("https://x.example/api");
  });
  it("rejects non-http URLs", () => {
    expect(() => normaliseEngineUrl("javascript:alert(1)")).toThrow();
    expect(() => normaliseEngineUrl("not a url")).toThrow();
  });
  it("reduces to an origin for the CSP", () => {
    expect(engineOrigin("https://engine.example.org/base/")).toBe("https://engine.example.org");
  });
});

describe("Content-Security-Policy", () => {
  const csp = cspHeader({ nonce: "abc123", engineUrl: "https://engine.example.org", dev: false });

  it("lets the page connect only to itself and the engine origin", () => {
    expect(directive(csp, "connect-src")).toBe("connect-src 'self' https://engine.example.org");
  });
  it("allows scripts only by nonce, with no unsafe-inline or unsafe-eval in production", () => {
    const s = directive(csp, "script-src")!;
    expect(s).toContain("'nonce-abc123'");
    expect(s).toContain("'strict-dynamic'");
    expect(s).not.toContain("unsafe");
    expect(directive(csp, "style-src")).not.toContain("unsafe");
  });
  it("forbids framing, plugins and base-tag hijacking", () => {
    expect(directive(csp, "frame-ancestors")).toBe("frame-ancestors 'none'");
    expect(directive(csp, "object-src")).toBe("object-src 'none'");
    expect(directive(csp, "base-uri")).toBe("base-uri 'none'");
  });
  it("upgrades insecure requests only when the engine is https", () => {
    expect(csp).toContain("upgrade-insecure-requests");
    expect(cspHeader({ nonce: "n", engineUrl: "http://localhost:8080", dev: false })).not.toContain("upgrade-insecure-requests");
  });
  it("allows eval only in development", () => {
    expect(cspHeader({ nonce: "n", engineUrl: undefined, dev: true })).toContain("'unsafe-eval'");
  });
  it("has no external font or script hosts at all", () => {
    expect(csp).not.toMatch(/fonts\.googleapis|gstatic|googletagmanager|cdn\./);
  });
});

describe("static headers and nonces", () => {
  it("sends no referrer and no sniffing", () => {
    const h = Object.fromEntries(STATIC_SECURITY_HEADERS.map((x) => [x.key, x.value]));
    expect(h["Referrer-Policy"]).toBe("no-referrer");
    expect(h["X-Content-Type-Options"]).toBe("nosniff");
    expect(h["X-Frame-Options"]).toBe("DENY");
  });
  it("makes fresh, 128-bit base64 nonces", () => {
    const a = makeNonce();
    expect(a).toMatch(/^[A-Za-z0-9+/]{22}==$/);
    expect(makeNonce()).not.toBe(a);
  });
});

import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { checkBoundary } from "../../scripts/check-boundary.mjs";

const appRoot = path.resolve(__dirname, "../..");

function fixture(files: Record<string, string>): string {
  const root = mkdtempSync(path.join(tmpdir(), "rl-boundary-"));
  const all = { "lib/engine.ts": 'import "client-only";\nexport async function a() { return fetch("x"); }\n', ...files };
  for (const [rel, src] of Object.entries(all)) {
    mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
    writeFileSync(path.join(root, rel), src);
  }
  return root;
}

describe("confidentiality boundary (ADR-02): the Next.js app never receives document text", () => {
  it("holds for this app", () => {
    expect(checkBoundary(appRoot)).toEqual([]);
  });

  it("fails on a route handler", () => {
    const root = fixture({ "app/api/analyze/route.ts": "export async function POST(req) { return req.json(); }" });
    expect(checkBoundary(root).join("\n")).toMatch(/route handlers are not allowed/);
  });

  it("fails on a server action", () => {
    const root = fixture({ "app/actions.ts": '"use server";\nexport async function check(text) { return text; }' });
    expect(checkBoundary(root).join("\n")).toMatch(/server actions/);
  });

  it("fails on an inline server action", () => {
    const root = fixture({ "app/page.tsx": 'export default function P() { async function a() { "use server"; } return null; }' });
    expect(checkBoundary(root).join("\n")).toMatch(/server actions/);
  });

  it("fails on a pages/api route", () => {
    const root = fixture({ "pages/api/check.ts": "export default function h() {}" });
    expect(checkBoundary(root).join("\n")).toMatch(/API routes/);
  });

  it("fails when text could be persisted", () => {
    const root = fixture({ "components/X.tsx": "sessionStorage.setItem('doc', text); localStorage.setItem('d', t);" });
    const out = checkBoundary(root).join("\n");
    expect(out).toMatch(/sessionStorage/);
    expect(out).toMatch(/localStorage is only for the format preference/);
  });

  it("fails on a network call outside lib/engine.ts", () => {
    const root = fixture({ "components/Y.tsx": "fetch('/api/x', { body: text })" });
    expect(checkBoundary(root).join("\n")).toMatch(/lib\/engine\.ts only/);
  });

  it("fails when a proxy reads the request body", () => {
    const root = fixture({ "proxy.ts": "export async function proxy(r) { const b = await r.text(); }" });
    expect(checkBoundary(root).join("\n")).toMatch(/must not read request bodies/);
  });

  it("fails when the engine client is importable from the server", () => {
    const root = fixture({ "lib/engine.ts": "export const x = 1;" });
    expect(checkBoundary(root).join("\n")).toMatch(/client-only/);
  });
});

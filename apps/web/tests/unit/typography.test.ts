import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The house typography for words a writer reads (Web Interface Guidelines;
 * DESIGN.md): a curly apostrophe (’), never a straight one, and the ellipsis
 * character (…), never three dots. Checked in the string literals and JSX
 * text of every source file a page is built from. Comments are skipped, and
 * so is lib/config.ts, whose messages fail a build and are read by a
 * developer, not a writer.
 */

const appRoot = path.resolve(__dirname, "../..");
const SKIP = new Set(["lib/config.ts"]);

function sources(dir: string): string[] {
  return readdirSync(path.join(appRoot, dir)).flatMap((name) => {
    const rel = path.join(dir, name);
    if (statSync(path.join(appRoot, rel)).isDirectory()) return sources(rel);
    return /\.(ts|tsx)$/.test(name) && !SKIP.has(rel) ? [rel] : [];
  });
}

/** Strings a writer could read on one line: "…", `…` and JSX text between > and <. */
const LITERAL = /"[^"\n]*"|`[^`\n]*`|>[^<>{}\n]+</g;

function offences(rel: string, test: RegExp): string[] {
  return readFileSync(path.join(appRoot, rel), "utf8")
    .split("\n")
    .flatMap((line, i) => {
      if (/^\s*(\/\/|\/?\*)/.test(line)) return [];
      const hits = (line.match(LITERAL) ?? []).filter((s) => test.test(s));
      return hits.map((s) => `${rel}:${i + 1} ${s}`);
    });
}

const FILES = ["app", "components", "lib"].flatMap(sources);

describe("typography in user-visible text", () => {
  it("scans the app's sources", () => {
    expect(FILES.length).toBeGreaterThan(40);
    expect(FILES).toContain("components/word/Taskpane.tsx");
  });

  it("uses a curly apostrophe, never a straight one", () => {
    expect(FILES.flatMap((f) => offences(f, /[A-Za-z]'[a-z]/))).toEqual([]);
  });

  it("uses the ellipsis character, never three dots (spread syntax aside)", () => {
    expect(FILES.flatMap((f) => offences(f, /\.\.\.(?![A-Za-z_$[({])/))).toEqual([]);
  });

  it("catches what it is meant to", () => {
    expect("Draft: check what you've written".match(/[A-Za-z]'[a-z]/)).not.toBeNull();
    expect('"Loading..."'.match(LITERAL)?.some((s) => /\.\.\.(?![A-Za-z_$[({])/.test(s))).toBe(true);
    expect('"Loading…"'.match(LITERAL)?.some((s) => /\.\.\.(?![A-Za-z_$[({])/.test(s))).toBe(false);
  });
});

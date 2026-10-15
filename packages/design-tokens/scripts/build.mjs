#!/usr/bin/env node
/**
 * Generate dist/ from tokens.json (S4d R2).
 *
 *   node scripts/build.mjs           validate, then write dist/
 *   node scripts/build.mjs --check   validate, and fail if dist/ is stale
 *   node scripts/build.mjs --report  also print every measured contrast pair
 *
 * Validation fails on a colour token without a light or a dark value, a
 * reference that does not resolve, text below 4.5:1 against its surface,
 * or an underline, rail or mark below 3:1 against the page.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { renderAll, validate } from "./lib.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DIST = path.join(ROOT, "dist");

const args = new Set(process.argv.slice(2));
const src = JSON.parse(readFileSync(path.join(ROOT, "tokens.json"), "utf8"));
const report = [];
const problems = validate(src, report);
if (args.has("--report")) {
  for (const r of report) console.log(`${r.ratio.toFixed(2).padStart(6)}:1  (min ${r.min})  ${r.mode.padEnd(5)}  ${r.what}`);
}
if (problems.length) {
  console.error(`tokens.json is not valid (${problems.length}):`);
  for (const p of problems) console.error(`  - ${p}`);
  process.exit(1);
}

const files = renderAll(src);
if (args.has("--check")) {
  const stale = [];
  for (const [name, text] of Object.entries(files)) {
    let current = "";
    try {
      current = readFileSync(path.join(DIST, name), "utf8");
    } catch {
      current = "";
    }
    if (current !== text) stale.push(name);
  }
  if (stale.length) {
    console.error(`packages/design-tokens/dist is out of date with tokens.json: ${stale.join(", ")}.\n` +
      "Run: node packages/design-tokens/scripts/build.mjs");
    process.exit(1);
  }
  console.log(`design tokens: valid (${report.length} contrast pairs), dist up to date`);
} else {
  mkdirSync(DIST, { recursive: true });
  for (const [name, text] of Object.entries(files)) writeFileSync(path.join(DIST, name), text);
  console.log(`design tokens: valid (${report.length} contrast pairs); wrote ${Object.keys(files).join(", ")}`);
}

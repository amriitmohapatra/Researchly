#!/usr/bin/env node
/**
 * The confidentiality boundary, checked as a lint (ADR-02, ARCHITECTURE §5.3):
 * document text goes from the browser straight to the engine and never
 * through this Next.js app.
 *
 * Fails if the app grows anything that could receive text server-side
 * (route handlers, server actions, API routes, a body-reading proxy), sends
 * text from anywhere but lib/engine.ts, persists anything but the format
 * preference, or loads third-party scripts/fonts.
 *
 * Usage: node scripts/check-boundary.mjs [appRoot]   (exit 1 on violations)
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE_EXT = /\.(c|m)?(t|j)sx?$/;
const SKIP_DIRS = new Set(["node_modules", ".next", "out", "test-results", "playwright-report", "tests", "e2e", "scripts"]);

function walk(dir, root, out = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of entries) {
    if (SKIP_DIRS.has(name)) continue;
    const full = path.join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, root, out);
    else if (SOURCE_EXT.test(name)) out.push(path.relative(root, full).split(path.sep).join("/"));
  }
  return out;
}

/** Strip comments so prose that *mentions* an API does not trip the check. */
function code(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

export function checkBoundary(root) {
  const files = walk(root, root).filter((f) => !/(^|\/)(next\.config|vitest\.config|playwright\.config|eslint\.config)\./.test(f));
  const problems = [];
  const flag = (file, msg) => problems.push(`${file}: ${msg}`);

  for (const f of files) {
    const src = code(readFileSync(path.join(root, f), "utf8"));

    if (/(^|\/)app\/.*\/?route\.(c|m)?(t|j)sx?$/.test(f) || /^(src\/)?app\/route\./.test(f)) {
      flag(f, "route handlers are not allowed: the web app must never receive document text");
    }
    if (/^(src\/)?pages\/api\//.test(f)) flag(f, "API routes are not allowed: the web app must never receive document text");
    if (/(^|[\s;{(])["']use server["']/.test(src)) {
      flag(f, "server actions ('use server') are not allowed: they would send text to the Next.js server");
    }
    if (/\bfetch\s*\(/.test(src) && f !== "lib/engine.ts") {
      flag(f, "network calls belong in lib/engine.ts only (the single, audited path to the engine)");
    }
    if (/\b(XMLHttpRequest|sendBeacon|WebSocket|EventSource)\b/.test(src)) {
      flag(f, "XMLHttpRequest/sendBeacon/WebSocket/EventSource are not allowed; use lib/engine.ts");
    }
    if (/\b(sessionStorage|indexedDB|document\.cookie|cookies\s*\()/.test(src)) {
      flag(f, "no sessionStorage, IndexedDB or cookies in S1: the document is never persisted");
    }
    if (/\blocalStorage\b/.test(src) && f !== "lib/prefs.ts") {
      flag(f, "localStorage is only for the format preference, in lib/prefs.ts");
    }
    if (/dangerouslySetInnerHTML|\binnerHTML\b|insertAdjacentHTML/.test(src)) {
      flag(f, "never render HTML from data; document text is rendered as text");
    }
    if (/from\s+["']next\/script["']|from\s+["']next\/font\/google["']/.test(src)) {
      flag(f, "no third-party scripts or font CDNs");
    }
    if (/^(src\/)?(proxy|middleware)\.(t|j)s$/.test(f) && /\.(body|json|text|formData|arrayBuffer|blob)\s*(\(|\b)/.test(src.replace(/\.headers\b/g, ""))) {
      flag(f, "the proxy must not read request bodies");
    }
  }

  const engine = files.includes("lib/engine.ts") ? readFileSync(path.join(root, "lib/engine.ts"), "utf8") : "";
  if (!/import\s+["']client-only["']/.test(engine)) {
    problems.push("lib/engine.ts: must import 'client-only' so server code can never import the text-sending path");
  }
  return problems;
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const root = path.resolve(process.argv[2] ?? path.join(path.dirname(fileURLToPath(import.meta.url)), ".."));
  const problems = checkBoundary(root);
  if (problems.length) {
    console.error(`Confidentiality boundary check failed (${problems.length}):`);
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }
  console.log("Confidentiality boundary check passed: no route handlers, server actions or text persistence.");
}

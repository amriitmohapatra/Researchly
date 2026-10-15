/**
 * The token file's promises (S4d R2): every colour has a light and a dark
 * value, text clears 4.5:1 against its surface and underlines, rails and
 * marks clear 3:1 against the page, in both modes; dist/ is what the
 * generator makes; the categories keep their names, icons, patterns and
 * Word colours. Run: node --test test/tokens.test.mjs
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { GRAPHIC_MIN, TEXT_MIN, colourTokens, contrast, over, renderAll, resolve, validate } from "../scripts/lib.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const load = () => JSON.parse(readFileSync(path.join(ROOT, "tokens.json"), "utf8"));

test("the token file is valid: light and dark everywhere, contrast above the floors", () => {
  const report = [];
  assert.deepEqual(validate(load(), report), []);
  assert.ok(report.length > 150, `only ${report.length} pairs measured`);
  for (const mode of ["light", "dark"]) {
    assert.ok(report.some((r) => r.mode === mode && r.min === TEXT_MIN));
    assert.ok(report.some((r) => r.mode === mode && r.min === GRAPHIC_MIN));
  }
  for (const r of report) assert.ok(r.ratio >= r.min, `${r.what} ${r.mode} ${r.ratio}`);
});

test("every semantic and component colour token has both modes", () => {
  const tokens = colourTokens(load());
  assert.ok(tokens.length > 50);
  for (const t of tokens) {
    assert.ok(t.value.light && t.value.dark, `${t.path.join(".")} lacks a mode`);
  }
});

test("a token without a dark value fails", () => {
  const src = load();
  delete src.semantic.convention.text.dark;
  const problems = validate(src);
  assert.ok(problems.some((p) => p.includes("convention.text has no dark value")), problems.join("\n"));
  const comp = load();
  comp.component.widget.ring = { light: "{focus.strong}" };
  assert.ok(validate(comp).some((p) => p.includes("widget.ring has no dark value")));
});

test("text below 4.5:1 fails, in either mode", () => {
  const src = load();
  src.semantic.correction.text.light = "#e07a40";
  assert.ok(validate(src).some((p) => p.startsWith("correction.text on surface.page (light)")));
  const dark = load();
  dark.semantic.text.secondary.dark = "#5a5f68";
  assert.ok(validate(dark).some((p) => p.startsWith("text.secondary on surface.page (dark)")));
});

test("an underline below 3:1 against the page fails", () => {
  const src = load();
  src.primitive.orchid["500"] = "#cc79a7"; // the old preference line: 2.80:1 on the paper
  const problems = validate(src);
  assert.ok(problems.some((p) => p.startsWith("component underline.preference.color on surface.page (light)")), problems.join("\n"));
  const dark = load();
  dark.semantic.convention.strong.dark = "#1f3a33";
  assert.ok(validate(dark).some((p) => p.includes("convention.strong on surface.page (dark)")));
});

test("broken references and values are reported, not rendered", () => {
  const src = load();
  src.semantic.focus.strong.light = "{azure.999}";
  src.semantic.focus.subtle.dark = "blue";
  const problems = validate(src);
  assert.ok(problems.some((p) => p.includes("unknown reference {azure.999}")));
  assert.ok(problems.some((p) => p.includes("not a colour or a {reference}: blue")));
});

test("dist/ is exactly what the generator makes", () => {
  for (const [name, text] of Object.entries(renderAll(load()))) {
    assert.equal(readFileSync(path.join(ROOT, "dist", name), "utf8"), text, `${name} is stale: run node scripts/build.mjs`);
  }
});

test("the CSS carries light, prefers-color-scheme dark and the explicit theme attribute", () => {
  const css = renderAll(load())["tokens.css"];
  assert.match(css.split("@media")[0], /\n {2}--rl-correction-strong: #d55e00;\n/);
  assert.match(css, /@media \(prefers-color-scheme: dark\) \{\n {2}:root:not\(\[data-theme="light"\]\) \{/);
  assert.match(css, /:root\[data-theme="dark"\] \{/);
  assert.match(css, /--rl-underline-preference-style: wavy;/);
  assert.match(css, /--rl-underline-improvement-style: dashed;/);
  const lightVars = css.split("@media")[0].match(/--rl-[a-z-]+(?=: #)/g);
  const darkVars = css.split(':root[data-theme="dark"]')[1].match(/--rl-[a-z-]+(?=: #)/g);
  assert.deepEqual(darkVars, lightVars);
});

test("categories: names, icons, patterns and Word annotation colours", () => {
  const src = load();
  assert.deepEqual(Object.keys(src.categories), ["correction", "improvement", "convention", "preference"]);
  const word = Object.fromEntries(Object.entries(src.categories).map(([k, c]) => [k, c.wordAnnotationColor]));
  assert.deepEqual(word, { correction: "Red", improvement: "Blue", convention: "Green", preference: "Lavender" });
  const lines = Object.fromEntries(Object.entries(src.categories).map(([k, c]) => [k, c.underline]));
  assert.deepEqual(lines, { correction: "solid", improvement: "dashed", convention: "dotted", preference: "wavy-dotted" });
  // The website's icon set (apps/web/components/CategoryIcon.tsx).
  const icons = Object.fromEntries(Object.entries(src.categories).map(([k, c]) => [k, c.icon]));
  assert.deepEqual(icons, { correction: "circle-cross", improvement: "arrow-up", convention: "open-book", preference: "sliders" });
  const only = Object.entries(src.categories).filter(([, c]) => c.critical).map(([k]) => k);
  assert.deepEqual(only, ["correction"]);
});

test("a Convention is never painted red", () => {
  const src = load();
  for (const mode of ["light", "dark"]) {
    for (const v of ["strong", "text"]) {
      const hex = resolve(src, src.semantic.convention[v][mode], mode);
      const [r, g] = [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16)];
      assert.ok(g > r, `convention.${v} (${mode}) ${hex} reads as red`);
    }
  }
});

test("the six states, their looks and the retry schedule", () => {
  const { states } = load();
  assert.deepEqual(states.order, ["hidden", "checking", "issues", "clear", "partial", "offline"]);
  assert.deepEqual(states.retrySeconds, [2, 4, 8, 16, 30]);
  const looks = Object.fromEntries(states.order.map((s) => [s, states[s].look]));
  assert.deepEqual(looks, { hidden: "none", checking: "ring", issues: "badge", clear: "tick", partial: "warning", offline: "crossed" });
  for (const s of states.order) {
    assert.ok(!/'|\.\.\./.test(states[s].label + states[s].description), `${s}: straight apostrophe or three dots`);
  }
});

test("contrast arithmetic", () => {
  assert.equal(Math.round(contrast("#000000", "#ffffff") * 100) / 100, 21);
  assert.equal(contrast("#777777", "#777777"), 1);
  assert.equal(over("#00000080", "#ffffff"), "#7f7f7f");
  assert.equal(over("#123456", "#ffffff"), "#123456");
});

/**
 * Researchly design tokens: load, resolve, validate and render (S4d R2).
 *
 * Plain Node (no dependencies), so every surface can run it: the website's
 * lint, CI, and the owner's Mac or Windows machine before a native build.
 */

const HEX = /^#[0-9a-f]{6}([0-9a-f]{2})?$/;
const REF = /^\{([a-z0-9-]+(?:\.[a-z0-9-]+)+)\}$/;
export const MODES = ["light", "dark"];

/** WCAG floors: text 4.5:1 against its surface; underlines, rails and marks 3:1 against the page. */
export const TEXT_MIN = 4.5;
export const GRAPHIC_MIN = 3;

const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const isModal = (v) => isObject(v) && ("light" in v || "dark" in v);

/** Every colour token of the semantic and component tiers: [{ tier, path, value: {light, dark} }]. */
export function colourTokens(src) {
  const out = [];
  const visit = (tier, node, path) => {
    if (isModal(node)) {
      out.push({ tier, path, value: node });
      return;
    }
    if (!isObject(node)) return;
    for (const [k, v] of Object.entries(node)) {
      if (k.startsWith("$")) continue;
      if (k === "pattern" || k === "thickness") continue;
      visit(tier, v, [...path, k]);
    }
  };
  visit("semantic", src.semantic ?? {}, []);
  visit("component", src.component ?? {}, []);
  return out;
}

function lookup(src, path) {
  let node = src;
  for (const p of path) {
    if (!isObject(node) || !(p in node)) return undefined;
    node = node[p];
  }
  return node;
}

/** One token value in one mode, references followed, as lower-case #rrggbb[aa]. */
export function resolve(src, raw, mode, seen = new Set()) {
  if (typeof raw !== "string") throw new Error(`not a colour value: ${JSON.stringify(raw)}`);
  const value = raw.trim().toLowerCase();
  if (HEX.test(value)) return value;
  const m = REF.exec(value);
  if (!m) throw new Error(`not a colour or a {reference}: ${raw}`);
  if (seen.has(m[1])) throw new Error(`reference cycle at {${m[1]}}`);
  seen.add(m[1]);
  const path = m[1].split(".");
  const prim = lookup(src.primitive ?? {}, path);
  if (typeof prim === "string") return resolve(src, prim, mode, seen);
  const sem = lookup(src.semantic ?? {}, path);
  if (isModal(sem)) {
    if (!(mode in sem)) throw new Error(`{${m[1]}} has no ${mode} value`);
    return resolve(src, sem[mode], mode, seen);
  }
  throw new Error(`unknown reference {${m[1]}}`);
}

export function rgba(hex) {
  const h = hex.slice(1);
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
    a: h.length === 8 ? parseInt(h.slice(6, 8), 16) : 255,
  };
}

/** A translucent colour laid over an opaque one. */
export function over(top, base) {
  const t = rgba(top);
  const b = rgba(base);
  const a = t.a / 255;
  const mix = (x, y) => Math.round(x * a + y * (1 - a));
  return "#" + [mix(t.r, b.r), mix(t.g, b.g), mix(t.b, b.b)].map((n) => n.toString(16).padStart(2, "0")).join("");
}

function luminance(hex) {
  const { r, g, b } = rgba(hex);
  const lin = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG 2 contrast ratio; a translucent foreground is laid over the background first. */
export function contrast(fg, bg) {
  const solid = rgba(fg).a < 255 ? over(fg, bg) : fg;
  const a = luminance(solid);
  const b = luminance(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

const key = (path) => path.join(".");

/** The tokens that carry text, and the graphic ones (underlines, rails, rings, marks), by role. */
export function classify(path) {
  const last = path[path.length - 1];
  if (path[0] === "text" || last === "text") return "text";
  if (path[0] === "surface" || last === "subtle" || last === "background" || last === "surface") return "fill";
  if (path[0] === "highlight") return "fill";
  if (path[0] === "accent" && last === "hover") return "fill";
  if (path[0] === "line" && last === "hairline") return "fill";
  return "graphic";
}

/**
 * Every problem with the token file: a colour without a light or a dark
 * value, a value that does not resolve, or a pair below its contrast
 * floor. Empty means valid. `report` collects every measured pair.
 */
export function validate(src, report = []) {
  const problems = [];
  const tokens = colourTokens(src);
  if (!tokens.length) problems.push("no colour tokens");
  const resolved = new Map();
  for (const t of tokens) {
    const name = `${t.tier}:${key(t.path)}`;
    for (const mode of MODES) {
      if (!(mode in t.value) || t.value[mode] === "" || t.value[mode] == null) {
        problems.push(`${name} has no ${mode} value`);
        continue;
      }
      try {
        resolved.set(`${t.tier}:${key(t.path)}:${mode}`, resolve(src, t.value[mode], mode));
      } catch (e) {
        problems.push(`${name} (${mode}): ${e.message}`);
      }
    }
  }
  if (problems.length) return problems;
  const get = (tier, path, mode) => resolved.get(`${tier}:${path}:${mode}`);
  const check = (what, fg, bg, mode, min) => {
    const ratio = contrast(fg, bg);
    report.push({ what, mode, fg, bg, ratio: Math.round(ratio * 100) / 100, min });
    if (ratio + 1e-9 < min) problems.push(`${what} (${mode}): ${ratio.toFixed(2)}:1 is below ${min}:1 (${fg} on ${bg})`);
  };
  for (const mode of MODES) {
    const page = get("semantic", "surface.page", mode);
    const raised = get("semantic", "surface.raised", mode);
    const sunken = get("semantic", "surface.sunken", mode);
    if (!page || !raised || !sunken) {
      problems.push(`surface.page, surface.raised and surface.sunken are required (${mode})`);
      continue;
    }
    for (const t of tokens) {
      const role = classify(t.path);
      const fg = get(t.tier, key(t.path), mode);
      const name = `${t.tier === "semantic" ? "" : "component "}${key(t.path)}`;
      if (role === "text") {
        // Text sits on the page, on cards and on sunken panels.
        const grounds = { page, raised, sunken };
        if (key(t.path) === "text.on-accent") {
          check(`${name} on accent.strong`, fg, get("semantic", "accent.strong", mode), mode, TEXT_MIN);
          continue;
        }
        if (t.path[0] === "widget") {
          check(`${name} on widget.badge.background`, fg, get("component", "widget.badge.background", mode), mode, TEXT_MIN);
          continue;
        }
        for (const [g, bg] of Object.entries(grounds)) check(`${name} on surface.${g}`, fg, bg, mode, TEXT_MIN);
        // A role's text also sits on that role's own tint (badges, pressed chips).
        const sibling = t.tier === "semantic" ? [...t.path.slice(0, -1), "subtle"] : [...t.path.slice(0, -1), "background"];
        const tint = get(t.tier, key(sibling), mode);
        if (tint) {
          for (const [g, bg] of Object.entries({ page, raised })) {
            check(`${name} on ${key(sibling)} over surface.${g}`, fg, over(tint, bg), mode, TEXT_MIN);
          }
        }
      } else if (role === "graphic") {
        check(`${name} on surface.page`, fg, page, mode, GRAPHIC_MIN);
        check(`${name} on surface.raised`, fg, raised, mode, GRAPHIC_MIN);
      }
    }
  }
  for (const [id, c] of Object.entries(src.categories ?? {})) {
    if (!src.patterns?.[c.underline]) problems.push(`category ${id}: unknown underline pattern ${c.underline}`);
    const u = src.component?.underline?.[id];
    if (!u) problems.push(`category ${id}: no component underline.${id}`);
    else if (u.pattern !== c.underline) problems.push(`category ${id}: underline.${id}.pattern ${u.pattern} is not ${c.underline}`);
    for (const f of ["label", "icon", "sfSymbol", "segoeGlyph", "wordAnnotationColor"]) {
      if (!c[f]) problems.push(`category ${id}: no ${f}`);
    }
  }
  for (const id of src.states?.order ?? []) {
    const s = src.states[id];
    if (!s) {
      problems.push(`state ${id} is listed but not defined`);
      continue;
    }
    if (!lookup(src.component ?? {}, s.color.split(".")) || !isModal(lookup(src.component, s.color.split(".")))) {
      problems.push(`state ${id}: colour ${s.color} is not a component colour token`);
    }
  }
  return problems;
}

/* ---------- rendering ---------- */

const HEADER = "Generated by packages/design-tokens/scripts/build.mjs from tokens.json. Do not edit by hand.";

const cssName = (path) => `--rl-${path.join("-")}`;
const camel = (path) =>
  path
    .join("-")
    .split("-")
    .map((w, i) => (i === 0 ? w : w[0].toUpperCase() + w.slice(1)))
    .join("");
const pascal = (path) => {
  const c = camel(path);
  return c[0].toUpperCase() + c.slice(1);
};

/** [{ path, light, dark }] for every colour token, with semantic tokens first. */
export function flat(src) {
  return colourTokens(src).map((t) => ({
    path: t.path,
    tier: t.tier,
    light: resolve(src, t.value.light, "light"),
    dark: resolve(src, t.value.dark, "dark"),
  }));
}

function nonColour(src) {
  const out = [];
  for (const [cat, u] of Object.entries(src.component?.underline ?? {})) {
    out.push({ path: ["underline", cat, "style"], css: src.patterns[u.pattern].css, pattern: u.pattern });
    out.push({ path: ["underline", cat, "thickness"], css: `${u.thickness}px`, thickness: u.thickness });
  }
  return out;
}

export function renderCss(src) {
  const tokens = flat(src);
  const block = (mode, indent) => tokens.map((t) => `${indent}${cssName(t.path)}: ${t[mode]};`).join("\n");
  const fixed = nonColour(src)
    .map((t) => `  ${cssName(t.path)}: ${t.css};`)
    .join("\n");
  return `/* ${HEADER}
 * Light by default; dark under prefers-color-scheme unless the page says
 * data-theme="light", and always under data-theme="dark". */

:root {
${block("light", "  ")}

${fixed}
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
${block("dark", "    ")}
  }
}

:root[data-theme="dark"] {
${block("dark", "  ")}
}
`;
}

const q = (s) => JSON.stringify(s);

export function renderTs(src) {
  const tokens = flat(src);
  const lines = tokens.map(
    (t) => `  ${q(t.path.join("."))}: { light: ${q(t.light)}, dark: ${q(t.dark)}, cssVar: ${q(cssName(t.path))} },`,
  );
  const cats = Object.entries(src.categories).map(([id, c]) => {
    const u = src.component.underline[id];
    return `  ${id}: {
    label: ${q(c.label)},
    critical: ${c.critical},
    icon: ${q(c.icon)},
    sfSymbol: ${q(c.sfSymbol)},
    segoeGlyph: ${q(c.segoeGlyph)},
    wordAnnotationColor: ${q(c.wordAnnotationColor)},
    underline: { pattern: ${q(u.pattern)}, css: ${q(src.patterns[u.pattern].css)}, thickness: ${u.thickness} },
  },`;
  });
  const states = src.states.order.map((id) => {
    const s = src.states[id];
    const one = s.labelOne ? `, labelOne: ${q(s.labelOne)}` : "";
    return `  ${id}: { look: ${q(s.look)}, color: ${q(s.color)}, label: ${q(s.label)}${one}, description: ${q(s.description)} },`;
  });
  return `/* ${HEADER} */

export type Mode = "light" | "dark";

/** Every colour token, resolved per mode, with its CSS custom property. */
export const TOKENS = {
${lines.join("\n")}
} as const;

export type TokenName = keyof typeof TOKENS;

/** The CSS custom property of a token, e.g. var(--rl-correction-strong). */
export function cssVar(name: TokenName): string {
  return \`var(\${TOKENS[name].cssVar})\`;
}

/** Underline patterns (colour is never the only cue). CSS has no wavy-dotted; it draws wavy. */
export type UnderlinePattern = ${Object.keys(src.patterns).map(q).join(" | ")};

/** Per category: its name, icon (ours, an SF Symbol, a Segoe glyph), Word annotation colour and underline. */
export const CATEGORY_TOKENS = {
${cats.join("\n")}
} as const;

export type CategoryId = keyof typeof CATEGORY_TOKENS;

/** The six states every surface shows, in order (docs/inline-review-design.md §3). */
export const STATE_ORDER = ${JSON.stringify(src.states.order)} as const;

export const STATES = {
${states.join("\n")}
} as const;

/** Seconds to wait before each retry after a failure; the last repeats. */
export const RETRY_SECONDS = ${JSON.stringify(src.states.retrySeconds)} as const;
`;
}

const swiftColour = (hex) => {
  const { r, g, b, a } = rgba(hex);
  const h = (n) => "0x" + n.toString(16).padStart(2, "0");
  return `RGBA(${h(r)}, ${h(g)}, ${h(b)}, ${h(a)})`;
};

export function renderSwift(src) {
  const tokens = flat(src);
  const lets = tokens.map(
    (t) => `    public static let ${camel(t.path)} = ColorPair(light: ${swiftColour(t.light)}, dark: ${swiftColour(t.dark)})`,
  );
  const patternCase = (p) => camel(p.split("-"));
  const cats = Object.entries(src.categories).map(([id, c]) => {
    const u = src.component.underline[id];
    return `        "${id}": Category(id: ${q(id)}, label: ${q(c.label)}, critical: ${c.critical}, icon: ${q(c.icon)}, sfSymbol: ${q(c.sfSymbol)}, segoeGlyph: ${q(c.segoeGlyph)}, wordAnnotationColor: ${q(c.wordAnnotationColor)},
                          underline: Underline(color: ${camel(["underline", id, "color"])}, pattern: .${patternCase(u.pattern)}, thickness: ${u.thickness}),
                          highlight: ${camel(["highlight", id])}, rail: ${camel(["card", "rail", id])},
                          badgeText: ${camel(["badge", id, "text"])}, badgeBackground: ${camel(["badge", id, "background"])}),`;
  });
  const states = src.states.order.map((id) => {
    const s = src.states[id];
    return `        "${id}": StateLook(id: ${q(id)}, look: ${q(s.look)}, color: ${camel(s.color.split("."))}, label: ${q(s.label)}, labelOne: ${s.labelOne ? q(s.labelOne) : "nil"}, description: ${q(s.description)}),`;
  });
  return `// ${HEADER}
// Foundation only, so the platform-neutral core can use it; the AppKit
// extension at the end gives each pair as a dynamic NSColor.

import Foundation

public enum ResearchlyTokens {
    public struct RGBA: Equatable, Sendable {
        public let red: Double, green: Double, blue: Double, alpha: Double
        public init(_ r: UInt8, _ g: UInt8, _ b: UInt8, _ a: UInt8) {
            red = Double(r) / 255; green = Double(g) / 255; blue = Double(b) / 255; alpha = Double(a) / 255
        }
    }

    public struct ColorPair: Equatable, Sendable {
        public let light: RGBA
        public let dark: RGBA
        public func resolve(dark isDark: Bool) -> RGBA { isDark ? dark : light }
    }

    public enum UnderlinePattern: String, Sendable {
${Object.keys(src.patterns)
  .map((p) => `        case ${patternCase(p)} = ${q(p)}`)
  .join("\n")}
    }

    public struct Underline: Equatable, Sendable {
        public let color: ColorPair
        public let pattern: UnderlinePattern
        public let thickness: Double
    }

    public struct Category: Equatable, Sendable {
        public let id: String, label: String, critical: Bool
        public let icon: String, sfSymbol: String, segoeGlyph: String, wordAnnotationColor: String
        public let underline: Underline
        public let highlight: ColorPair, rail: ColorPair, badgeText: ColorPair, badgeBackground: ColorPair
    }

    public struct StateLook: Equatable, Sendable {
        public let id: String, look: String
        public let color: ColorPair
        public let label: String, labelOne: String?, description: String
    }

${lets.join("\n")}

    public static let categoryOrder = ${JSON.stringify(Object.keys(src.categories))}

    public static let categories: [String: Category] = [
${cats.join("\n")}
    ]

    public static let stateOrder = ${JSON.stringify(src.states.order)}

    public static let states: [String: StateLook] = [
${states.join("\n")}
    ]

    /// Seconds to wait before each retry after a failure; the last repeats.
    public static let retrySeconds: [Double] = ${JSON.stringify(src.states.retrySeconds)}
}

#if canImport(AppKit)
import AppKit

extension ResearchlyTokens.RGBA {
    public var nsColor: NSColor { NSColor(srgbRed: red, green: green, blue: blue, alpha: alpha) }
}

extension ResearchlyTokens.ColorPair {
    /// Follows the view's appearance (light or dark) at draw time.
    public var nsColor: NSColor {
        NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark.nsColor : light.nsColor
        }
    }
}
#endif
`;
}

export function renderCs(src) {
  const tokens = flat(src);
  const col = (hex) => {
    const { r, g, b, a } = rgba(hex);
    const h = (n) => "0x" + n.toString(16).padStart(2, "0").toUpperCase();
    return `new Rgba(${h(r)}, ${h(g)}, ${h(b)}, ${h(a)})`;
  };
  const fields = tokens.map(
    (t) => `    public static readonly ColorPair ${pascal(t.path)} = new(${col(t.light)}, ${col(t.dark)});`,
  );
  const dict = tokens.map((t) => `        [${q(t.path.join("."))}] = ${pascal(t.path)},`);
  const patternCase = (p) => pascal(p.split("-"));
  const cats = Object.entries(src.categories).map(([id, c]) => {
    const u = src.component.underline[id];
    return `        [${q(id)}] = new Category(${q(id)}, ${q(c.label)}, ${c.critical}, ${q(c.icon)}, ${q(c.sfSymbol)}, ${q(c.segoeGlyph)}, ${q(c.wordAnnotationColor)},
            new Underline(${pascal(["underline", id, "color"])}, UnderlinePattern.${patternCase(u.pattern)}, ${u.thickness}),
            ${pascal(["highlight", id])}, ${pascal(["card", "rail", id])}, ${pascal(["badge", id, "text"])}, ${pascal(["badge", id, "background"])}),`;
  });
  const states = src.states.order.map((id) => {
    const s = src.states[id];
    return `        [${q(id)}] = new StateLook(${q(id)}, ${q(s.look)}, ${pascal(s.color.split("."))}, ${q(s.label)}, ${s.labelOne ? q(s.labelOne) : "null"}, ${q(s.description)}),`;
  });
  return `// ${HEADER}
// Plain C# (no WPF types), so the platform-neutral core can use it. A WPF
// shell builds brushes from Rgba, or a ResourceDictionary from ByName.

#nullable enable
using System.Collections.Generic;

namespace Researchly.Design;

public readonly record struct Rgba(byte R, byte G, byte B, byte A)
{
    public string Hex => A == 0xFF ? $"#{R:X2}{G:X2}{B:X2}" : $"#{A:X2}{R:X2}{G:X2}{B:X2}";
}

public readonly record struct ColorPair(Rgba Light, Rgba Dark)
{
    public Rgba Resolve(bool dark) => dark ? Dark : Light;
}

public enum UnderlinePattern { ${Object.keys(src.patterns).map(patternCase).join(", ")} }

public sealed record Underline(ColorPair Color, UnderlinePattern Pattern, double Thickness);

public sealed record Category(string Id, string Label, bool Critical, string Icon, string SfSymbol, string SegoeGlyph,
    string WordAnnotationColor, Underline Underline, ColorPair Highlight, ColorPair Rail, ColorPair BadgeText, ColorPair BadgeBackground);

public sealed record StateLook(string Id, string Look, ColorPair Color, string Label, string? LabelOne, string Description);

public static class ResearchlyTokens
{
${fields.join("\n")}

    /// <summary>Every colour token by its dotted name, e.g. "correction.strong".</summary>
    public static readonly IReadOnlyDictionary<string, ColorPair> ByName = new Dictionary<string, ColorPair>
    {
${dict.join("\n")}
    };

    public static readonly IReadOnlyList<string> CategoryOrder = new[] { ${Object.keys(src.categories).map(q).join(", ")} };

    public static readonly IReadOnlyDictionary<string, Category> Categories = new Dictionary<string, Category>
    {
${cats.join("\n")}
    };

    public static readonly IReadOnlyList<string> StateOrder = new[] { ${src.states.order.map(q).join(", ")} };

    public static readonly IReadOnlyDictionary<string, StateLook> States = new Dictionary<string, StateLook>
    {
${states.join("\n")}
    };

    /// <summary>Seconds to wait before each retry after a failure; the last repeats.</summary>
    public static readonly IReadOnlyList<double> RetrySeconds = new double[] { ${src.states.retrySeconds.join(", ")} };
}
`;
}

/** Every generated file: name -> contents. */
export function renderAll(src) {
  return {
    "tokens.css": renderCss(src),
    "tokens.ts": renderTs(src),
    "ResearchlyTokens.swift": renderSwift(src),
    "ResearchlyTokens.cs": renderCs(src),
  };
}

/**
 * The six states (S4d R2), drawn by the real component with the real
 * stylesheets, light and dark. Not wired into a page yet (R4 and R5 do
 * that), so the markup is rendered here and laid out with the generated
 * tokens.css and globals.css. With SCREENSHOTS=1 each scheme is saved:
 *   SCREENSHOTS=1 SHOTS_DIR=/some/dir npx playwright test e2e/status-mark.spec.ts
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "@playwright/test";
import { TOKENS } from "@researchly/design-tokens";
import { StatusMark } from "../components/StatusMark";
import { CHECK_STATES, type CheckStatus, INITIAL_STATUS } from "../lib/check-state";

const DIR = process.env.SHOTS_DIR ?? "test-results/shots";
const CSS = [
  readFileSync(path.resolve(__dirname, "../../../packages/design-tokens/dist/tokens.css"), "utf8"),
  readFileSync(path.resolve(__dirname, "../app/globals.css"), "utf8"),
].join("\n");

const EXAMPLES: Record<string, Partial<CheckStatus>> = {
  issues: { count: 3 },
  partial: { count: 1, reason: "Grammar checking was off" },
  offline: { reason: "No connection", retryInMs: 4000, failures: 2 },
};

/**
 * Playwright compiles JSX in test imports to its own component-testing
 * objects ({__pw_type: "jsx"}), which React cannot render. These components
 * are pure (no hooks), so call them and rebuild real React elements.
 */
type PwNode = { __pw_type?: string; type: unknown; props?: Record<string, unknown>; key?: string | null };
function toReact(node: unknown): ReactNode {
  if (Array.isArray(node)) return node.map(toReact);
  if (node === null || typeof node !== "object" || (node as PwNode).__pw_type !== "jsx") return node as ReactNode;
  const { type, props = {}, key } = node as PwNode;
  if (typeof type === "function") return toReact((type as (p: unknown) => unknown)(props));
  const { children, ...rest } = props;
  const kids = Array.isArray(children) ? children.map(toReact) : [toReact(children)];
  return createElement(type as string, { ...rest, key: key ?? undefined }, ...kids);
}
const markup = (status: CheckStatus, showLabel = true) => renderToStaticMarkup(toReact(StatusMark({ status, showLabel })) as never);

function page(): string {
  const rows = CHECK_STATES.map((state) => {
    const status = { ...INITIAL_STATUS, state, ...(EXAMPLES[state] ?? {}) };
    const mark = markup(status);
    const bare = markup(status, false);
    return `<li data-row="${state}"><code>${state}</code><span class="on-page">${mark}</span><span class="on-card">${bare}${mark}</span></li>`;
  }).join("");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><style>${CSS}
    body { padding: 24px; } ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
    li { display: grid; grid-template-columns: 90px 240px 280px; align-items: center; gap: 16px; }
    .on-card { display: inline-flex; gap: 16px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; }
  </style></head><body><main><h1>The six states</h1><ul>${rows}</ul></main></body></html>`;
}

for (const scheme of ["light", "dark"] as const) {
  test(`the six states, one look each (${scheme})`, async ({ page: p }) => {
    await p.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await p.setViewportSize({ width: 720, height: 420 });
    await p.setContent(page());
    for (const state of CHECK_STATES) {
      await expect(p.locator(`[data-row="${state}"] .on-page [data-state="${state}"]`)).toHaveCount(1);
    }
    // Nothing drawn for hidden; one shape for every other state.
    await expect(p.locator('[data-row="hidden"] svg')).toHaveCount(0);
    for (const state of CHECK_STATES.filter((s) => s !== "hidden")) {
      await expect(p.locator(`[data-row="${state}"] .on-page svg`)).toHaveCount(1);
    }
    // Colours are the tokens', in this scheme.
    const rgb = (hex: string) => `rgb(${[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(", ")})`;
    const stroke = (sel: string) => p.locator(sel).first().evaluate((el) => getComputedStyle(el).stroke);
    const fill = (sel: string) => p.locator(sel).first().evaluate((el) => getComputedStyle(el).fill);
    expect(await stroke(".sm-ring")).toBe(rgb(TOKENS["widget.ring"][scheme]));
    expect(await stroke(".status-offline .sm-offline")).toBe(rgb(TOKENS["widget.offline"][scheme]));
    expect(await fill(".sm-warning")).toBe(rgb(TOKENS["widget.warning"][scheme]));
    expect(await fill(".sm-badge")).toBe(rgb(TOKENS["widget.badge.background"][scheme]));
    // Reduced motion: the ring stands still.
    expect(await p.locator(".status-spin").first().evaluate((el) => getComputedStyle(el).animationName)).toBe("none");
    if (process.env.SCREENSHOTS) await p.screenshot({ path: `${DIR}/states-${scheme}.png`, fullPage: true });
  });
}

test("the checking ring turns when motion is allowed", async ({ page: p }) => {
  await p.emulateMedia({ reducedMotion: "no-preference" });
  await p.setContent(page());
  expect(await p.locator(".status-spin").first().evaluate((el) => getComputedStyle(el).animationName)).toBe("status-spin");
});

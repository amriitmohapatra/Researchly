import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { CATEGORY_TOKENS, STATES, TOKENS } from "@researchly/design-tokens";
import { StatusMark } from "@/components/StatusMark";
import { CATEGORIES } from "@/lib/categories";
import {
  CHECK_STATES,
  type CheckEvent,
  type CheckStatus,
  INITIAL_STATUS,
  reduceCheckState,
  retryDelayMs,
  stateDescription,
  stateLabel,
  stateLook,
} from "@/lib/check-state";

const run = (events: CheckEvent[], from: CheckStatus = INITIAL_STATUS) => events.reduce(reduceCheckState, from);

describe("the six states", () => {
  it("are the shared six, in order", () => {
    expect(CHECK_STATES).toEqual(["hidden", "checking", "issues", "clear", "partial", "offline"]);
    expect(INITIAL_STATUS.state).toBe("hidden");
  });

  it("an edit goes to checking; a reply to issues, clear or partial", () => {
    const checking = run([{ type: "edit", revision: 1 }]);
    expect(checking.state).toBe("checking");
    expect(run([{ type: "reply", revision: 1, count: 3 }], checking)).toMatchObject({ state: "issues", count: 3 });
    expect(run([{ type: "reply", revision: 1, count: 0 }], checking)).toMatchObject({ state: "clear", count: 0 });
    expect(run([{ type: "reply", revision: 1, count: 2, partial: true, reason: "Grammar was off" }], checking)).toMatchObject({
      state: "partial",
      count: 2,
      reason: "Grammar was off",
    });
    expect(run([{ type: "reply", revision: 1, count: 0, partial: true }], checking).state).toBe("partial");
  });

  it("drops a reply or a failure for an older revision", () => {
    const s = run([
      { type: "edit", revision: 1 },
      { type: "edit", revision: 2 },
      { type: "reply", revision: 1, count: 5 },
      { type: "failure", revision: 1 },
    ]);
    expect(s).toMatchObject({ state: "checking", revision: 2, count: 0, failures: 0 });
    expect(run([{ type: "reply", revision: 2, count: 1 }], s)).toMatchObject({ state: "issues", count: 1 });
    // An edit never goes backwards.
    expect(run([{ type: "edit", revision: 1 }], s).revision).toBe(2);
  });

  it("a failure goes offline and retries after 2, 4, 8, 16 and 30 s, then every 30 s", () => {
    let s = run([{ type: "edit", revision: 7 }]);
    const waits: (number | null)[] = [];
    for (let i = 0; i < 7; i++) {
      s = run([{ type: "failure", revision: 7, reason: "No connection" }], s);
      expect(s.state).toBe("offline");
      waits.push(s.retryInMs);
      s = run([{ type: "retry", revision: 7 }], s);
      expect(s).toMatchObject({ state: "offline", retryInMs: null }); // stays offline while it tries
    }
    expect(waits).toEqual([2000, 4000, 8000, 16000, 30000, 30000, 30000]);
    expect([1, 2, 3, 4, 5, 6, 60].map(retryDelayMs)).toEqual([2000, 4000, 8000, 16000, 30000, 30000, 30000]);
    expect(retryDelayMs(0)).toBe(2000);
  });

  it("any success leaves offline and resets the wait", () => {
    let s = run([
      { type: "edit", revision: 1 },
      { type: "failure", revision: 1 },
      { type: "failure", revision: 1 },
    ]);
    expect(s.failures).toBe(2);
    s = run([{ type: "reply", revision: 1, count: 0 }], s);
    expect(s).toMatchObject({ state: "clear", failures: 0, retryInMs: null, reason: "" });
    s = run([{ type: "edit", revision: 2 }, { type: "failure", revision: 2 }], s);
    expect(s.retryInMs).toBe(2000);
  });

  it("an edit while offline checks again, and a further failure waits longer", () => {
    const s = run([
      { type: "edit", revision: 1 },
      { type: "failure", revision: 1 },
      { type: "edit", revision: 2 },
    ]);
    expect(s.state).toBe("checking");
    expect(run([{ type: "failure", revision: 2 }], s).retryInMs).toBe(4000);
  });

  it("a retry outside offline changes nothing", () => {
    const s = run([{ type: "edit", revision: 3 }, { type: "reply", revision: 3, count: 1 }]);
    expect(run([{ type: "retry", revision: 3 }], s)).toBe(s);
  });

  it("pausing or leaving the field goes to hidden from any state", () => {
    const states = [
      run([{ type: "edit", revision: 1 }]),
      run([{ type: "edit", revision: 1 }, { type: "reply", revision: 1, count: 4 }]),
      run([{ type: "edit", revision: 1 }, { type: "failure", revision: 1 }]),
    ];
    for (const s of states) {
      for (const type of ["pause", "leave"] as const) {
        expect(run([{ type }], s)).toMatchObject({ state: "hidden", count: 0, retryInMs: null, failures: 0 });
      }
    }
  });

  it("the reducer is pure", () => {
    const s = run([{ type: "edit", revision: 1 }]);
    const copy = JSON.parse(JSON.stringify(s));
    reduceCheckState(s, { type: "reply", revision: 1, count: 2 });
    expect(s).toEqual(copy);
  });
});

describe("labels in plain words, from the design tokens", () => {
  const at = (state: CheckStatus["state"], extra: Partial<CheckStatus> = {}): CheckStatus => ({ ...INITIAL_STATUS, state, ...extra });

  it("says each state the same way on every surface", () => {
    expect(stateLabel(at("hidden"))).toBe("Paused");
    expect(stateLabel(at("checking"))).toBe("Checking…");
    expect(stateLabel(at("issues", { count: 1 }))).toBe("1 suggestion");
    expect(stateLabel(at("issues", { count: 1204 }))).toBe("1,204 suggestions");
    expect(stateLabel(at("clear"))).toBe("Nothing to suggest");
    expect(stateLabel(at("partial"))).toBe("Checked in part");
    expect(stateLabel(at("offline"))).toBe("Can’t check right now");
    for (const s of CHECK_STATES) if (s !== "issues") expect(stateLabel(at(s))).toBe(STATES[s].label);
  });

  it("gives the reason and the next step", () => {
    expect(stateDescription(at("partial", { count: 2, reason: "Grammar checking was off" }))).toBe(
      "Checked in part. 2 suggestions. Grammar checking was off.",
    );
    expect(stateDescription(at("offline", { reason: "No connection", retryInMs: 8000 }))).toBe(
      "Can’t check right now. No connection. Researchly will try again in 8 s. Your text is not lost.",
    );
    expect(stateDescription(at("offline", { retryInMs: null }))).toBe("Can’t check right now. Trying again now.");
    expect(stateDescription(at("clear"))).toBe("Nothing to suggest.");
  });

  it("has one look per state", () => {
    expect(CHECK_STATES.map(stateLook)).toEqual(["none", "ring", "badge", "tick", "warning", "crossed"]);
  });
});

describe("<StatusMark>", () => {
  const html = (s: CheckStatus, showLabel = true) => renderToStaticMarkup(<StatusMark status={s} showLabel={showLabel} />);
  const at = (state: CheckStatus["state"], extra: Partial<CheckStatus> = {}): CheckStatus => ({ ...INITIAL_STATUS, state, ...extra });

  it("is a polite status region carrying the label, with the state as data", () => {
    for (const s of CHECK_STATES) {
      const out = html(at(s, { count: 3 }));
      expect(out).toContain(`data-state="${s}"`);
      expect(out).toContain('role="status"');
      expect(out).toContain('aria-live="polite"');
      expect(out).toContain(stateLabel(at(s, { count: 3 })));
    }
  });

  it("draws nothing for hidden but still tells a screen reader", () => {
    const out = html(at("hidden"));
    expect(out).not.toContain("<svg");
    expect(out).toContain('class="sr-only">Paused<');
  });

  it("draws the shape of each state", () => {
    expect(html(at("checking"))).toContain("status-spin");
    expect(html(at("issues", { count: 7 }))).toMatch(/sm-badge-text[^>]*>7</);
    expect(html(at("issues", { count: 140 }))).toMatch(/sm-badge-text[^>]*>99\+</);
    expect(html(at("clear"))).toContain("sm-mark");
    expect(html(at("partial"))).toContain("sm-warning");
    expect(html(at("offline"))).toContain("sm-offline");
    // The shape is decoration; the words carry the meaning.
    expect(html(at("offline"))).toContain('aria-hidden="true"');
  });

  it("can hide the visible label where only the mark fits", () => {
    expect(html(at("issues", { count: 2 }), false)).toContain('class="sr-only">2 suggestions<');
    expect(html(at("issues", { count: 2 }), true)).toContain('class="status-mark-label">2 suggestions<');
  });
});

describe("the page reads the generated tokens", () => {
  const css = readFileSync(path.resolve(__dirname, "../../app/globals.css"), "utf8");
  const layout = readFileSync(path.resolve(__dirname, "../../app/layout.tsx"), "utf8");
  const tokensCss = readFileSync(path.resolve(__dirname, "../../../../packages/design-tokens/dist/tokens.css"), "utf8");

  it("loads tokens.css before globals.css", () => {
    const a = layout.indexOf("packages/design-tokens/dist/tokens.css");
    const b = layout.indexOf("./globals.css");
    expect(a).toBeGreaterThan(-1);
    expect(b).toBeGreaterThan(a);
  });

  it("writes no category colour of its own", () => {
    for (const cat of ["correction", "improvement", "convention", "preference"]) {
      expect(css).not.toMatch(new RegExp(`--${cat}-(ink|line|tint)\\s*:`));
      expect(css).toContain(`var(--rl-${cat}-strong)`);
      expect(css).toContain(`var(--rl-underline-${cat}-style)`);
    }
    // No hex value of a category colour, in either mode.
    const hexes = Object.entries(TOKENS)
      .filter(([name]) => /^(correction|improvement|convention|preference)\./.test(name))
      .flatMap(([, t]) => [t.light, t.dark])
      .filter((h) => h.length === 7);
    for (const h of hexes) expect(css.toLowerCase()).not.toContain(h);
  });

  it("every --rl- variable the page uses exists in the generated CSS", () => {
    const used = new Set(css.match(/--rl-[a-z0-9-]+/g) ?? []);
    expect(used.size).toBeGreaterThan(20);
    for (const v of used) expect(tokensCss, v).toContain(`${v}:`);
  });

  it("the page's neutrals match the tokens' surface and text roles", () => {
    const value = (block: string, name: string) => new RegExp(`--${name}: (#[0-9a-f]{6});`).exec(block)?.[1];
    const [light, dark] = [css.split("@media (prefers-color-scheme: dark)")[0]!, css.split("@media (prefers-color-scheme: dark)")[1]!];
    const pairs: [string, keyof typeof TOKENS][] = [
      ["bg", "surface.page"],
      ["surface", "surface.raised"],
      ["surface-2", "surface.sunken"],
      ["ink", "text.primary"],
      ["ink-2", "text.secondary"],
      ["line", "line.hairline"],
      ["line-strong", "line.strong"],
      ["accent", "accent.strong"],
      ["accent-ink", "text.on-accent"],
      ["accent-hover", "accent.hover"],
      ["focus", "focus.strong"],
      ["link", "focus.text"],
      ["info-bg", "focus.subtle"],
    ];
    for (const [name, token] of pairs) {
      expect(value(light, name), name).toBe(TOKENS[token].light);
      expect(value(dark, name), name).toBe(TOKENS[token].dark);
    }
  });

  it("each category's pattern on the site is the tokens' pattern", () => {
    for (const [cat, meta] of Object.entries(CATEGORIES)) {
      expect(meta.underline).toBe(CATEGORY_TOKENS[cat as keyof typeof CATEGORY_TOKENS].underline.pattern);
    }
  });

  it("the ring stands still under reduced motion", () => {
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\) \{\s*\.status-spin \{\s*animation: none;/);
  });
});

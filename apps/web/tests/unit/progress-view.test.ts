import { describe, expect, it } from "vitest";
import type { ProgressEvent } from "@/lib/progress";
import { formatRate, MIN_FIRES, ratePer1000, ruleTrends, sparkPath, sparkPoints, trendWord } from "@/lib/progress-view";
import { progressRow } from "@/lib/progress";
import { claimText, recordCheck, resetRecorded, textKey } from "@/lib/record-progress";

const ev = (day: number, words: number, counts: Record<string, number>): ProgressEvent => ({
  created_at: `2026-10-0${day}T10:00:00Z`,
  words,
  document_type: "manuscript",
  counts,
});

describe("progress: each rule's rate per 1,000 words over the recorded checks (S4c)", () => {
  it("orders checks oldest first (loadProgress returns newest first) and keeps rules that fired at least twice", () => {
    const events = [
      ev(3, 2000, { G106: 2 }),
      ev(2, 1000, { G106: 3, W202: 1 }),
      ev(1, 500, { G106: 4, C201: 1 }),
    ];
    const { checks, trends } = ruleTrends(events);
    expect(checks).toBe(3);
    expect(MIN_FIRES).toBe(2);
    // W202 and C201 fired once each: not shown.
    expect(trends.map((t) => t.ruleId)).toEqual(["G106"]);
    expect(trends[0]).toEqual({ ruleId: "G106", rates: [8, 3, 1], first: 8, latest: 1, word: "fewer", notAssessed: 0 });
  });

  it("an older check that did not record what it assessed: a zero proves nothing, so it is a gap; no-word checks are skipped", () => {
    const { checks, trends } = ruleTrends([ev(1, 1000, { S001: 2 }), ev(2, 0, { S001: 9 }), ev(3, 1000, {})]);
    expect(checks).toBe(2);
    expect(trends[0]!.rates).toEqual([2, null]);
    expect(trends[0]!.word).toBeNull();
  });

  it("one check: a value but no direction yet", () => {
    const { trends } = ruleTrends([ev(1, 1000, { G106: 3 })]);
    expect(trends[0]!.word).toBeNull();
  });

  it("says fewer, about the same or more, ignoring small differences", () => {
    expect(trendWord(4, 1)).toBe("fewer");
    expect(trendWord(1, 4)).toBe("more");
    expect(trendWord(2, 2.3)).toBe("about the same");
    expect(trendWord(0, 0.4)).toBe("about the same");
    expect(trendWord(10, 8.5)).toBe("about the same");
    expect(trendWord(10, 7.5)).toBe("fewer");
  });

  it("rates and their wording", () => {
    expect(ratePer1000(3, 1000)).toBe(3);
    expect(ratePer1000(1, 3000)).toBe(0.3);
    expect(ratePer1000(1, 0)).toBe(0);
    expect(formatRate(3)).toBe("3");
    expect(formatRate(0.34)).toBe("0.3");
    expect(formatRate(12.25)).toBe("12.3");
  });

  it("the sparkline runs from zero at the bottom to its own highest value at the top", () => {
    const pts = sparkPoints([0, 5, 10], 100, 40, 4);
    expect(pts.map((p) => p.x)).toEqual([4, 50, 96]);
    expect(pts.map((p) => p.y)).toEqual([36, 20, 4]);
    expect(sparkPoints([2], 100, 40)).toEqual([{ x: 50, y: 4 }]);
    expect(sparkPoints([0, 0], 100, 40, 4).map((p) => p.y)).toEqual([36, 36]);
  });
});


// --- Codex review N2 (2026-10-14): a configuration change is never a trend ---

const ALL = ["C303", "G106", "LT001", "P201", "W202"];
const at = (
  day: number,
  counts: Record<string, number>,
  extra: Partial<ProgressEvent> = {},
): ProgressEvent => ({
  created_at: `2026-10-1${day}T10:00:00Z`,
  words: 1000,
  document_type: "manuscript",
  counts,
  assessed: ALL,
  mode: "revise",
  ruleset: "0.1.0+aaaa",
  ...extra,
});

describe("progress compares like with like (N2)", () => {
  it("muting a rule leaves a gap, never a fall to zero", () => {
    const { trends } = ruleTrends([
      at(1, { C303: 2 }),
      at(2, {}, { assessed: ALL.filter((r) => r !== "C303") }),
    ]);
    const c = trends.find((t) => t.ruleId === "C303")!;
    expect(c.rates).toEqual([2, null]);
    expect(c.word).toBeNull();
    expect(c.notAssessed).toBe(1);
  });

  it("hiding preferences, Draft and a tier that is down are gaps too", () => {
    for (const without of ["P201", "C303", "LT001"]) {
      const { trends } = ruleTrends([
        at(1, { [without]: 3 }),
        at(2, {}, { assessed: ALL.filter((r) => r !== without), mode: without === "C303" ? "draft" : "revise" }),
      ]);
      expect(trends[0]!.word).toBeNull();
    }
  });

  it("an actual reduction between comparable checks is still fewer", () => {
    const { trends } = ruleTrends([at(1, { G106: 4 }), at(2, { G106: 1 })]);
    expect(trends[0]!.rates).toEqual([4, 1]);
    expect(trends[0]!.word).toBe("fewer");
  });

  it("assessed with no findings is a true zero", () => {
    const { trends } = ruleTrends([at(1, { G106: 3 }), at(2, {})]);
    expect(trends[0]!.rates).toEqual([3, 0]);
    expect(trends[0]!.word).toBe("fewer");
  });

  it("compares one article type at a time, the latest by default, and says which", () => {
    const events = [
      at(1, { G106: 5 }, { document_type: "thesis-chapter" }),
      at(2, { G106: 1 }, { document_type: "manuscript" }),
      at(3, { G106: 2 }, { document_type: "manuscript" }),
    ];
    const latest = ruleTrends(events);
    expect(latest.documentType).toBe("manuscript");
    expect(latest.checks).toBe(2);
    expect(latest.trends[0]!.rates).toEqual([1, 2]);
    expect(latest.documentTypes.map((t) => t.id)).toEqual(["manuscript", "thesis-chapter"]);
    const chapters = ruleTrends(events, "thesis-chapter");
    expect(chapters.checks).toBe(1);
  });

  it("checks made by another version of the rules are not compared, and counted", () => {
    const v = ruleTrends([at(1, { G106: 9 }, { ruleset: "0.0.9+old" }), at(2, { G106: 2 }), at(3, { G106: 2 })]);
    expect(v.checks).toBe(2);
    expect(v.otherRuleset).toBe(1);
    expect(v.trends[0]!.first).toBe(2);
  });

  it("dates and Draft are reported for the compared checks", () => {
    const v = ruleTrends([at(1, { G106: 2 }), at(2, { G106: 2 }, { mode: "draft" })]);
    expect(v.from).toBe("2026-10-11T10:00:00Z");
    expect(v.to).toBe("2026-10-12T10:00:00Z");
    expect(v.draft).toBe(1);
  });

  it("the sparkline breaks at a gap instead of drawing through it", () => {
    const pts = sparkPoints([2, null, 4], 100, 40, 4);
    expect(pts[1]!.y).toBeNull();
    expect(sparkPath(pts)).toBe("M4.0 20.0 M96.0 4.0");
    expect(sparkPath(sparkPoints([1, 2], 100, 40, 4))).toMatch(/^M.* L/);
  });
});

describe("what a check records (N2)", () => {
  it("records rule ids, the mode and the rule set: metadata only", () => {
    const row = progressRow({
      suggestions: [],
      metrics: null,
      profile: null,
      assessed_rules: ["G106", "not a rule", "C303", "G106"],
      mode: "draft",
      ruleset: "0.1.0+2795206d",
    } as never);
    expect(row.assessed).toEqual(["C303", "G106"]);
    expect(row.mode).toBe("draft");
    expect(row.ruleset).toBe("0.1.0+2795206d");
    expect(progressRow({ suggestions: [], metrics: null, profile: null, ruleset: "the whole paragraph" } as never).ruleset).toBeNull();
  });

  it("a recheck of the same text is not recorded twice; changed text is", () => {
    resetRecorded();
    const calls: unknown[] = [];
    const record = (d: unknown) => {
      calls.push(d);
      return Promise.resolve();
    };
    const data = { suggestions: [], metrics: null, profile: null } as never;
    const a = textKey("We fitted a model.");
    recordCheck(data, { signedIn: true, keep: true, textKey: a }, record);
    recordCheck(data, { signedIn: true, keep: true, textKey: a }, record);
    recordCheck(data, { signedIn: true, keep: true, textKey: textKey("We fitted two models.") }, record);
    expect(calls).toHaveLength(2);
    expect(claimText(null)).toBe(true);
    expect(textKey("abc")).not.toContain("abc");
  });
});

import { describe, expect, it } from "vitest";
import type { AnalyzeResponse, Suggestion } from "@researchly/contract";
import { applyFilter, hiddenPreferenceCount, revealNeedsRecheck, shownSuggestions, summarySentence } from "@/lib/view";
import { sugg } from "./helpers";

function response(suggestions: Suggestion[], hidden_preferences = 0): AnalyzeResponse {
  return {
    schema_version: "1",
    signed_in: false,
    suggestions,
    counts: {},
    hidden_preferences,
    sections_detected: [],
    health: [],
    engine: { service_version: "0", core_version: "0", rules_loaded: 0 },
    elapsed_ms: 1,
  };
}

describe("view model", () => {
  const list = [
    sugg("p", 0, 3, "preference"),
    sugg("c2", 10, 12, "correction"),
    sugg("i", 4, 8, "improvement"),
    sugg("c1", 4, 6, "correction"),
  ];

  it("hides preferences unless asked, and sorts by position then importance", () => {
    expect(shownSuggestions(response(list), false).map((s) => s.id)).toEqual(["c1", "i", "c2"]);
    expect(shownSuggestions(response(list), true).map((s) => s.id)).toEqual(["p", "c1", "i", "c2"]);
  });

  it("counts hidden preferences from the engine and from the toggle", () => {
    expect(hiddenPreferenceCount(response(list, 0), false)).toBe(1);
    expect(hiddenPreferenceCount(response(list, 0), true)).toBe(0);
    expect(hiddenPreferenceCount(response([], 4), false)).toBe(4);
    expect(hiddenPreferenceCount(response([], 4), true)).toBe(4); // still needs a re-check
  });

  it("knows when revealing preferences needs a fresh request", () => {
    expect(revealNeedsRecheck(response([], 3))).toBe(true);
    expect(revealNeedsRecheck(response(list, 0))).toBe(false);
  });

  it("filters by category", () => {
    expect(applyFilter(list, "correction").map((s) => s.id)).toEqual(["c2", "c1"]);
    expect(applyFilter(list, "all")).toHaveLength(4);
  });

  it("announces a summary without any score", () => {
    expect(summarySentence([])).toBe("Check complete. No suggestions.");
    const s = summarySentence(shownSuggestions(response(list), false));
    expect(s).toBe("Check complete. 3 suggestions: 2 corrections, 1 improvement.");
    expect(s).not.toMatch(/score|grade|%/i);
  });
});

import { describe, expect, it } from "vitest";
import { DOCUMENT_TYPES, type NarrativeMap, type ProfileInfo, type ReviewReport } from "@researchly/contract";
import { briefState, FALLBACK_PROFILES, isDocumentType, narrativeState, profileLine, profileSummary, timesPhrase } from "@/lib/profiles";

const info = (extra: Partial<ProfileInfo>): ProfileInfo => ({
  id: "general",
  label: "General",
  guessed: true,
  note: "",
  rules_off: [],
  ...extra,
});

describe("article types", () => {
  it("knows the contract's types and nothing else", () => {
    for (const t of DOCUMENT_TYPES) expect(isDocumentType(t), t).toBe(true);
    for (const v of ["poem", "", null, undefined, 3, "Manuscript"]) expect(isDocumentType(v)).toBe(false);
  });

  it("falls back to the contract's list with the id as the label, in display order", () => {
    expect(FALLBACK_PROFILES.map((p) => p.id)).toEqual([...DOCUMENT_TYPES]);
    expect(FALLBACK_PROFILES[0]).toEqual({ id: "auto", label: "auto", summary: "" });
    expect(profileSummary(FALLBACK_PROFILES, "grant")).toBe("");
    expect(profileSummary([{ id: "grant", label: "Grant proposal", summary: "Aims for a funder." }], "grant")).toBe("Aims for a funder.");
  });
});

describe("the profile line", () => {
  it("says nothing for a guessed General: that is the engine's ordinary behaviour", () => {
    expect(profileLine(info({ id: "general", guessed: true }))).toBeNull();
    expect(profileLine(undefined)).toBeNull();
    expect(profileLine(null)).toBeNull();
  });
  it("names a guessed type and where the guess came from", () => {
    expect(profileLine(info({ id: "manuscript", label: "Research article", guessed: true }))).toBe(
      "Checked as Research article (from the headings).",
    );
  });
  it("names a chosen type plainly, General included", () => {
    expect(profileLine(info({ id: "grant", label: "Grant proposal", guessed: false }))).toBe("Checked as Grant proposal.");
    expect(profileLine(info({ id: "general", label: "General", guessed: false }))).toBe("Checked as General.");
  });
  it("uses the engine's note alone when there is one, so 'Checked as' is never said twice", () => {
    const note = "Checked as a commentary: there is no abstract to judge.";
    expect(profileLine(info({ id: "commentary", label: "Commentary", guessed: false, note }))).toBe(note);
    expect(profileLine(info({ id: "commentary", label: "Commentary", guessed: true, note: `  ${note}  ` }))).toBe(note);
  });
});

describe("the brief's state", () => {
  const review: ReviewReport = { source: "s", sections: [], words: 1, questions: [], top_rules: [] };
  it("needs Revise in Draft, whatever the engine sent", () => {
    expect(briefState({ mode: "draft", review })).toEqual({ kind: "needs_revise" });
    expect(briefState({ mode: "draft", review: null })).toEqual({ kind: "needs_revise" });
  });
  it("is ready in Revise with a brief, and missing without one (an older engine)", () => {
    expect(briefState({ mode: "revise", review })).toEqual({ kind: "ready", review });
    expect(briefState({ mode: "revise", review: null })).toEqual({ kind: "missing" });
    expect(briefState({ mode: "revise" })).toEqual({ kind: "missing" });
  });
  it("counts a rule's tally in words", () => {
    expect(timesPhrase(1)).toBe("once");
    expect(timesPhrase(2)).toBe("2 times");
    expect(timesPhrase(1200)).toBe("1,200 times");
  });
});

describe("the narrative map's state (S4b)", () => {
  const narrative: NarrativeMap = { note: "n", source: "s", sections: [], unmapped: [], missing_links: [], hedging: [], profile: null };
  it("needs Revise in Draft, whatever the engine sent", () => {
    expect(narrativeState({ mode: "draft", narrative })).toEqual({ kind: "needs_revise" });
    expect(narrativeState({ mode: "draft", narrative: null })).toEqual({ kind: "needs_revise" });
  });
  it("is ready in Revise with a map, and missing without one (an older engine)", () => {
    expect(narrativeState({ mode: "revise", narrative })).toEqual({ kind: "ready", narrative });
    expect(narrativeState({ mode: "revise", narrative: null })).toEqual({ kind: "missing" });
    expect(narrativeState({ mode: "revise" })).toEqual({ kind: "missing" });
  });
  it("is independent of the brief: a map without a brief is still ready", () => {
    expect(narrativeState({ mode: "revise", narrative }).kind).toBe("ready");
    expect(briefState({ mode: "revise", review: null }).kind).toBe("missing");
  });
});

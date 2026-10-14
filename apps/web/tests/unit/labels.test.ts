import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  EMPTY_SESSION,
  EXPORT_FILENAME,
  exportLabels,
  exportText,
  labelContent,
  nextParagraph,
  normaliseSession,
  paragraphsLabelled,
  progressLine,
  labelsToReplace,
  newAttemptId,
  setVerdict,
  startAttempt,
  verdictOf,
  type LabelSession,
} from "@/lib/labels";

/**
 * The file the Python reader's own test loads too (ml/eval/test_label_precision.py):
 * if either side changes the format, one of the two suites fails.
 */
const FIXTURE = path.resolve(import.meta.dirname, "../../../../ml/eval/fixtures/web-labels.json");

/** Synthetic cards: a flag position, a rule, a category (what the page passes to setVerdict). */
const card = (flag: number, rule_id: string, category: string) => ({ flag, rule_id, category });

/** The labelling session the fixture records: two paragraphs, four flags, one changed mind. */
function fixtureSession(): LabelSession {
  let s = startAttempt(EMPTY_SESSION, "attempta01");
  const step = (c: ReturnType<typeof card>, section: string, v: "useful" | "wrong" | "unsure") => {
    s = setVerdict(s, c, section, v);
  };
  step(card(0, "G106", "improvement"), "introduction", "wrong");
  step(card(0, "G106", "improvement"), "introduction", "useful"); // changed mind: replaced, not added
  step(card(1, "S001", "correction"), "introduction", "wrong");
  s = startAttempt(nextParagraph(s), "attemptb02");
  step(card(0, "C201", "convention"), "discussion", "unsure");
  step(card(1, "C201", "convention"), "discussion", "useful"); // two flags of one rule: two labels
  return s;
}

describe("the labels file (S4 exit check)", () => {
  it("is exactly the format ml/eval/label_precision.py reads, and matches the fixture its test loads", () => {
    const s = fixtureSession();
    expect(exportText(s)).toBe(readFileSync(FIXTURE, "utf8"));
    const file = exportLabels(s);
    expect(file.version).toBe(1);
    for (const l of file.labels)
      expect(Object.keys(l).sort()).toEqual(["attempt", "category", "flag", "paragraph", "rule_id", "section", "verdict"]);
    expect(EXPORT_FILENAME).toBe("researchly-labels.json");
  });

  it("never carries text, even if a stored label had some (a tampered store)", () => {
    const s = normaliseSession({
      paragraph: 2,
      labels: [
        { paragraph: 1, rule_id: "G106", category: "improvement", section: "methods", verdict: "useful", text: "a sentence", snippet: "x" },
        { paragraph: 1, rule_id: "G106", verdict: "maybe" },
        { paragraph: 0, rule_id: "G106", verdict: "useful" },
        { paragraph: 1, rule_id: "a rule id with spaces", verdict: "useful" },
        "not a label",
      ],
    });
    expect(s.labels).toEqual([{ paragraph: 1, rule_id: "G106", category: "improvement", section: "methods", verdict: "useful" }]);
    expect(exportText(s)).not.toContain("sentence");
  });

  it("reads a missing or broken store as empty, and never goes back to an earlier paragraph number", () => {
    expect(normaliseSession(null)).toEqual(EMPTY_SESSION);
    expect(normaliseSession("x")).toEqual(EMPTY_SESSION);
    expect(normaliseSession({ paragraph: -3, labels: "x" })).toEqual(EMPTY_SESSION);
    const s = normaliseSession({ paragraph: 1, labels: [{ paragraph: 4, rule_id: "C201", category: "convention", section: "results", verdict: "wrong" }] });
    expect(s.paragraph).toBe(4);
  });

  it("counts paragraphs and flags for the running line", () => {
    const s = fixtureSession();
    expect(paragraphsLabelled(s)).toBe(2);
    expect(progressLine(s)).toBe("2 of 50 paragraphs, 4 flags labelled");
    expect(progressLine(EMPTY_SESSION)).toBe("0 of 50 paragraphs, 0 flags labelled");
  });

  it("Next paragraph moves on only once the current one has a label", () => {
    expect(nextParagraph(EMPTY_SESSION)).toBe(EMPTY_SESSION);
    const r = setVerdict(startAttempt(EMPTY_SESSION, "attemptx01"), card(0, "W202", "improvement"), "results", "useful");
    expect(nextParagraph(r).paragraph).toBe(2);
    expect(nextParagraph(r).attempt).toBeNull();
  });

  it("sends the section's name as a heading line above the paragraph", () => {
    expect(labelContent("methods", "  We fitted a model.  ")).toBe("Methods\n\nWe fitted a model.\n");
    expect(labelContent("conclusion", "Done.")).toBe("Conclusion\n\nDone.\n");
  });
});


// --- Codex review N3 (2026-10-14): one observation per flag, whatever happens ---

describe("label attempts (N3)", () => {
  const roundTrip = (s: LabelSession) => normaliseSession(JSON.parse(JSON.stringify(s)));

  it("a reload mid-paragraph, then a recheck and a new verdict: the earlier label is replaced, not duplicated", () => {
    let s = startAttempt(EMPTY_SESSION, "attempta01");
    s = setVerdict(s, card(0, "G106", "improvement"), "introduction", "wrong");
    s = roundTrip(s); // the reload: the text and the flags on screen are gone
    expect(s.attempt).toBeNull();
    expect(verdictOf(s, 0)).toBeNull();
    expect(labelsToReplace(s)).toBe(1); // the page says the next check replaces it
    s = startAttempt(s, "attemptb02"); // the same paragraph, checked again
    s = setVerdict(s, card(0, "G106", "improvement"), "introduction", "useful");
    const labels = exportLabels(s).labels.filter((l) => l.paragraph === 1);
    expect(labels).toHaveLength(1);
    expect(labels[0]!.verdict).toBe("useful");
  });

  it("a changed verdict replaces the label of the same flag", () => {
    let s = startAttempt(EMPTY_SESSION, "attempta01");
    s = setVerdict(s, card(0, "W202", "improvement"), "results", "wrong");
    s = setVerdict(s, card(0, "W202", "improvement"), "results", "useful");
    expect(s.labels).toHaveLength(1);
    expect(verdictOf(s, 0)).toBe("useful");
  });

  it("an edited paragraph checked again leaves no orphans from the earlier check", () => {
    let s = startAttempt(EMPTY_SESSION, "attempta01");
    s = setVerdict(s, card(0, "S001", "correction"), "methods", "wrong");
    s = setVerdict(s, card(1, "G101", "improvement"), "methods", "useful");
    s = startAttempt(s, "attemptb02"); // the text was edited: different flags now
    s = setVerdict(s, card(0, "G101", "improvement"), "methods", "useful");
    expect(s.labels.map((l) => [l.rule_id, l.attempt])).toEqual([["G101", "attemptb02"]]);
  });

  it("several flags of one rule are several observations", () => {
    let s = startAttempt(EMPTY_SESSION, "attempta01");
    s = setVerdict(s, card(0, "C201", "convention"), "discussion", "useful");
    s = setVerdict(s, card(1, "C201", "convention"), "discussion", "wrong");
    expect(s.labels).toHaveLength(2);
  });

  it("no verdict without a check on screen (an interrupted or failed check starts no attempt)", () => {
    expect(setVerdict(EMPTY_SESSION, card(0, "G106", "improvement"), "results", "useful")).toBe(EMPTY_SESSION);
  });

  it("earlier paragraphs are kept when the current one is checked again", () => {
    let s = setVerdict(startAttempt(EMPTY_SESSION, "attempta01"), card(0, "G106", "improvement"), "results", "useful");
    s = nextParagraph(s);
    s = startAttempt(s, "attemptb02");
    s = startAttempt(s, "attemptc03");
    expect(s.labels.filter((l) => l.paragraph === 1)).toHaveLength(1);
  });

  it("attempt ids are random, short and never text", () => {
    const a = newAttemptId();
    expect(a).toMatch(/^[a-z0-9]{10}$/);
    expect(newAttemptId(() => 0)).toBe("aaaaaaaaaa");
  });

  it("a tampered store cannot smuggle text in an attempt", () => {
    const s = normaliseSession({
      paragraph: 1,
      labels: [{ paragraph: 1, rule_id: "G106", category: "improvement", section: "results", verdict: "useful", attempt: "We fitted a model", flag: 0 }],
    });
    expect(s.labels[0]!.attempt).toBeUndefined();
  });
});

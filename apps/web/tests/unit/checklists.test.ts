import { describe, expect, it } from "vitest";
import type { ChecklistChoiceInfo, ChecklistItem } from "@researchly/contract";
import {
  CHECKLIST_SCOPE_LINE,
  CHECKLIST_STATUS_WORD,
  canConfirm,
  checklistHelp,
  checklistOffer,
  checklistOption,
  checklistTally,
  editionLine,
  FALLBACK_CHECKLISTS,
  isChecklistChoice,
  isChecklistSetting,
  itemRefsLine,
  itemStatus,
  markAnnouncement,
  NO_MARKS,
  notCountedLine,
  partState,
  sectionAbsentLine,
  shownParts,
  statusWords,
  toggleMark,
} from "@/lib/checklists";
import { registryChecklists } from "@/lib/registry";

describe("reporting checklists: the choices", () => {
  it("knows the contract's checklists, Auto and None, and nothing else", () => {
    for (const v of ["auto", "strobe", "consort", "prisma", "epiforge"]) {
      expect(isChecklistChoice(v), v).toBe(true);
      expect(isChecklistSetting(v), v).toBe(true);
    }
    expect(isChecklistSetting("none")).toBe(true);
    expect(isChecklistChoice("none")).toBe(false);
    for (const v of ["STROBE", "", null, undefined, 3, "tripod"]) expect(isChecklistSetting(v)).toBe(false);
  });

  it("sends nothing for None and the id otherwise", () => {
    expect(checklistOption("none")).toBeNull();
    expect(checklistOption("auto")).toBe("auto");
    expect(checklistOption("prisma")).toBe("prisma");
  });

  it("falls back to the engine's own list, in its order, when the registry has none", () => {
    expect(FALLBACK_CHECKLISTS.map((c) => c.id)).toEqual(["strobe", "consort", "prisma", "epiforge"]);
    expect(registryChecklists(null)).toBe(FALLBACK_CHECKLISTS);
    expect(registryChecklists({ rules: [], profiles: [], checklists: [] })).toBe(FALLBACK_CHECKLISTS);
    const own: ChecklistChoiceInfo[] = [{ id: "strobe", label: "STROBE (2007)", design: "cohort studies", pack: "Epi" }];
    expect(registryChecklists({ rules: [], profiles: [], checklists: own })).toBe(own);
  });

  it("says what the chosen checklist is for under the control, from the registry's design", () => {
    expect(checklistHelp(FALLBACK_CHECKLISTS, "none")).toBe("");
    expect(checklistHelp(FALLBACK_CHECKLISTS, "auto")).toMatch(/own words point to/);
    expect(checklistHelp(FALLBACK_CHECKLISTS, "consort")).toBe("For randomised controlled trials.");
    expect(checklistHelp([], "consort")).toBe("");
  });
});

describe("the checklist offer", () => {
  it("offers the checklist the text's words point to, with the registry's label", () => {
    expect(checklistOffer("epiforge", FALLBACK_CHECKLISTS)).toEqual({
      id: "epiforge",
      label: "EPIFORGE",
      sentence: "This reads like an epidemic forecast. Check it against EPIFORGE?",
    });
    expect(checklistOffer("strobe", FALLBACK_CHECKLISTS)?.sentence).toBe("This reads like an observational study. Check it against STROBE?");
    expect(checklistOffer("consort", FALLBACK_CHECKLISTS)?.sentence).toBe("This reads like a randomised controlled trial. Check it against CONSORT?");
    expect(checklistOffer("prisma", FALLBACK_CHECKLISTS)?.sentence).toBe(
      "This reads like a systematic review or meta-analysis. Check it against PRISMA?",
    );
    const relabelled: ChecklistChoiceInfo[] = [{ id: "prisma", label: "PRISMA 2020", design: "systematic reviews", pack: "Epi" }];
    expect(checklistOffer("prisma", relabelled)?.label).toBe("PRISMA 2020");
  });

  it("uses the built-in label when the registry has not arrived", () => {
    expect(checklistOffer("consort", [])?.label).toBe("CONSORT");
  });

  it("offers nothing without a suggestion, for Auto, or for an id this page cannot ask for", () => {
    expect(checklistOffer(null, FALLBACK_CHECKLISTS)).toBeNull();
    expect(checklistOffer(undefined, FALLBACK_CHECKLISTS)).toBeNull();
    expect(checklistOffer("", FALLBACK_CHECKLISTS)).toBeNull();
    expect(checklistOffer("auto", FALLBACK_CHECKLISTS)).toBeNull();
    expect(checklistOffer("tripod", [{ id: "tripod", label: "TRIPOD", design: "prediction models", pack: "Epi" }])).toBeNull();
  });
});

describe("the checklist's words (Codex review N1)", () => {
  const item = (x: Partial<ChecklistItem>): ChecklistItem => ({
    id: "x",
    topic: "Topic",
    question: "Q?",
    plain: "Why.",
    sections: [],
    status: "needs_check",
    section_absent: false,
    ...x,
  });

  it("says every status in cautious words: possible evidence to confirm, partly there, or a prompt; never 'reported'", () => {
    expect(CHECKLIST_STATUS_WORD).toEqual({
      found: "Found: please confirm",
      partial: "Partly there",
      needs_check: "Needs your check",
    });
    expect(Object.values(CHECKLIST_STATUS_WORD).join(" ")).not.toMatch(/report/i);
    expect(CHECKLIST_SCOPE_LINE).toBe("This checks reporting only, never the science.");
    // An older engine's "reported" is read as possible evidence; anything unknown as a prompt.
    expect(itemStatus({ status: "reported" } as unknown as ChecklistItem)).toBe("found");
    expect(itemStatus({ status: "verified" } as unknown as ChecklistItem)).toBe("needs_check");
  });

  it("says the writer's calls in place of the status, as 'you' on screen and 'the writer' on paper", () => {
    const found = item({ status: "found" });
    const partial = item({ status: "partial" });
    const open = item({ status: "needs_check" });
    expect(statusWords(found, undefined)).toBe("Found: please confirm");
    expect(statusWords(found, "confirmed")).toBe("Confirmed by you");
    expect(statusWords(partial, "confirmed", "print")).toBe("Confirmed by the writer");
    expect(statusWords(open, "confirmed")).toBe("Needs your check");
    expect(statusWords(open, "not_applicable")).toBe("Not applicable (your call)");
    expect(statusWords(found, "not_applicable", "print")).toBe("Not applicable (the writer’s call)");
    expect([found, partial, open].map(canConfirm)).toEqual([true, true, false]);
  });

  it("toggles a call, and pressing one releases the other", () => {
    let m = toggleMark(NO_MARKS, "a", "confirmed");
    expect([...m]).toEqual([["a", "confirmed"]]);
    m = toggleMark(m, "a", "not_applicable");
    expect([...m]).toEqual([["a", "not_applicable"]]);
    m = toggleMark(m, "a", "not_applicable");
    expect(m.size).toBe(0);
    expect(NO_MARKS.size).toBe(0); // never mutated
    expect(markAnnouncement("Setting", "confirmed", true)).toBe("Setting: confirmed by you.");
    expect(markAnnouncement("Setting", "confirmed", false)).toBe("Setting: confirmation undone.");
    expect(markAnnouncement("Bias", "not_applicable", true)).toBe("Bias: marked not applicable.");
    expect(markAnnouncement("Bias", "not_applicable", false)).toBe("Bias: not applicable undone.");
  });

  it("names the edition and the guideline's own item numbers, or says the item is good practice", () => {
    const r = { edition: "PRISMA 2020", label: "PRISMA" };
    expect(editionLine(r)).toBe("Selected themes of PRISMA 2020, not a full compliance check.");
    expect(editionLine({ edition: "", label: "PRISMA" })).toBe("Selected themes of PRISMA, not a full compliance check.");
    expect(itemRefsLine(item({ refs: ["6"] }), r)).toBe("PRISMA 2020 item 6");
    expect(itemRefsLine(item({ refs: ["13a", "13b"] }), r)).toBe("PRISMA 2020 items 13a and 13b");
    expect(itemRefsLine(item({ refs: ["1", "2", "3"] }), r)).toBe("PRISMA 2020 items 1, 2 and 3");
    expect(itemRefsLine(item({ refs: [] }), r)).toBe("Good practice, not a numbered item");
    expect(itemRefsLine(item({}), r)).toBe("Good practice, not a numbered item");
  });

  it("tallies in words: possible evidence, partly there, the writer's confirmations and not-applicable calls; never a score", () => {
    const items = [
      ...Array.from({ length: 4 }, (_, i) => item({ id: `f${i}`, status: "found" })),
      item({ id: "p1", status: "partial" }),
      item({ id: "p2", status: "partial" }),
      ...Array.from({ length: 10 }, (_, i) => item({ id: `n${i}` })),
    ];
    expect(checklistTally({ items }, NO_MARKS)).toBe("4 of 16 with possible evidence · 2 partly there · confirmed by you: 0");
    const marks = new Map<string, "confirmed" | "not_applicable">([
      ["f0", "confirmed"],
      ["n0", "confirmed"], // nothing found there: not counted as a confirmation
      ["n1", "not_applicable"],
    ]);
    expect(checklistTally({ items }, marks)).toBe("4 of 16 with possible evidence · 2 partly there · confirmed by you: 1 · not applicable (your call): 1");
    expect(checklistTally({ items }, marks, "print")).toBe(
      "4 of 16 with possible evidence · 2 partly there · confirmed by the writer: 1 · not applicable (the writer’s call): 1",
    );
    expect(checklistTally({ items: items.slice(6) }, NO_MARKS)).toBe("0 of 10 with possible evidence · confirmed by you: 0");
    expect(checklistTally({ items }, marks)).not.toMatch(/%|score|pass|complian/i);
  });

  it("words parts, set-aside sentences and absent sections", () => {
    expect(partState({ found: true })).toBe("Found");
    expect(partState({ found: false })).toBe("Needs your check");
    const parts = [
      { label: "the databases or sources", found: true, evidence: "We searched two databases." },
      { label: "the date of the last search", found: false, evidence: null },
    ];
    expect(shownParts(item({ status: "partial", parts }))).toEqual(parts);
    expect(shownParts(item({ status: "needs_check", parts }))).toEqual([]);
    expect(shownParts(item({ status: "found" }))).toEqual([]);
    expect(notCountedLine({ label: "says this is not reported" })).toBe("A sentence mentions this but says this is not reported:");
    expect(notCountedLine({ label: "is about earlier studies" })).toBe("A sentence mentions this but is about earlier studies:");
    expect(sectionAbsentLine(item({ sections: ["methods"], section_absent: true }))).toBe("No Methods section was found to look in.");
    expect(sectionAbsentLine(item({ sections: ["results", "discussion"], section_absent: true }))).toBe(
      "No Results or Discussion section was found to look in.",
    );
    expect(sectionAbsentLine(item({ sections: ["methods"], section_absent: false }))).toBeNull();
  });
});

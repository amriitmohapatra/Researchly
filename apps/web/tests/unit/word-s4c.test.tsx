import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { ChecklistItem, ChecklistReport, ProfileInfo, WordSuggestion } from "@researchly/contract";
import { WordChecklist } from "@/components/word/WordChecklist";
import {
  clearLabelStore,
  isChecklistPref,
  loadChecklistChoice,
  loadLabelStore,
  saveChecklistChoice,
  saveLabelStore,
} from "@/lib/prefs";
import {
  checklistHelp,
  checklistLabel,
  checklistOptions,
  checklistState,
  FALLBACK_CHECKLISTS,
  itemStatusWord,
  registryChecklists,
} from "@/lib/word/checklist";
import { STALE_NOTE, staleAfterEdit, wordProfileLine } from "@/lib/word/view";

/** Synthetic throughout. */
const REPORT: ChecklistReport = {
  id: "strobe",
  label: "STROBE",
  design: "observational studies",
  source: "A named reporting guideline",
  edition: "STROBE (2007)",
  suggested: true,
  found: 1,
  partial: 1,
  total: 3,
  note: "1 of 3 items has possible evidence in the text; 1 more is partly there.",
  items: [
    {
      id: "a",
      topic: "Setting",
      question: "Are the dates given?",
      plain: "When decides to whom.",
      sections: [],
      refs: ["5"],
      status: "found",
      evidence: "Data were collected <weekly> in 2024.",
      section_absent: false,
    },
    {
      id: "b",
      topic: "Bias",
      question: "Is bias discussed?",
      plain: "Say which way it leans.",
      sections: ["methods"],
      refs: [],
      status: "needs_check",
      evidence: null,
      not_counted: { reason: "absent", label: "says this is not reported", quote: "Bias is not described." },
      section_absent: false,
    },
    {
      id: "c",
      topic: "Participants",
      question: "Are eligibility and selection described?",
      plain: "Who was in decides whom it applies to.",
      sections: ["methods"],
      refs: ["6a"],
      status: "partial",
      evidence: "Adults were eligible.",
      parts: [
        { label: "the eligibility criteria", found: true, evidence: "Adults were eligible." },
        { label: "how participants were selected", found: false, evidence: null },
      ],
      section_absent: false,
    },
  ],
};

describe("the reporting checklist in Word (S4c)", () => {
  it("offers None, Auto, then the registry's checklists by label; falls back to the built-in four", () => {
    expect(checklistOptions(FALLBACK_CHECKLISTS).map((o) => o.label)).toEqual(["None", "Auto", "STROBE", "CONSORT", "PRISMA", "EPIFORGE"]);
    expect(registryChecklists({ rules: [] })).toBeNull();
    expect(registryChecklists({ checklists: [{ id: "strobe", label: "STROBE (2007)", design: "d", pack: "p" }, { nope: 1 }] })).toEqual([
      { id: "strobe", label: "STROBE (2007)", design: "d", pack: "p" },
    ]);
    expect(checklistHelp(FALLBACK_CHECKLISTS, "consort")).toBe("For randomised controlled trials. Reporting only, never the science.");
    expect(checklistHelp(FALLBACK_CHECKLISTS, "none")).toMatch(/Revise only/);
    expect(checklistLabel(FALLBACK_CHECKLISTS, "prisma")).toBe("PRISMA");
    expect(checklistLabel(FALLBACK_CHECKLISTS, null)).toBeNull();
  });

  it("says what the tab shows: the report, a need for Revise, nothing suggested, or an engine without one", () => {
    expect(checklistState({ mode: "revise", checklist: REPORT }, "strobe")).toEqual({ kind: "ready", report: REPORT });
    expect(checklistState({ mode: "draft", checklist: null }, "strobe")).toEqual({ kind: "needs_revise" });
    expect(checklistState({ mode: "revise", checklist: null }, "auto")).toEqual({ kind: "none_suggested" });
    expect(checklistState({ mode: "revise" }, "consort")).toEqual({ kind: "missing" });
  });

  it("renders the website's cautious list in a narrow column: edition, tally, topic and status, item numbers, question, what it rests on, the source", () => {
    const html = renderToStaticMarkup(<WordChecklist state={{ kind: "ready", report: REPORT }} />);
    expect(itemStatusWord(REPORT.items[0]!)).toBe("Found: please confirm");
    expect(itemStatusWord(REPORT.items[1]!)).toBe("Needs your check");
    expect(itemStatusWord(REPORT.items[2]!)).toBe("Partly there");
    expect(itemStatusWord(REPORT.items[0]!, "confirmed")).toBe("Confirmed by you");
    expect(itemStatusWord(REPORT.items[1]!, "confirmed")).toBe("Needs your check"); // nothing found, nothing to confirm
    expect(itemStatusWord(REPORT.items[1]!, "not_applicable")).toBe("Not applicable (your call)");
    // An older engine's "reported" is still only possible evidence.
    expect(itemStatusWord({ status: "reported" } as unknown as Pick<ChecklistItem, "status">)).toBe("Found: please confirm");
    expect(html).not.toMatch(/>Reported</);
    expect(html).toContain('data-testid="checklist-edition">Selected themes of STROBE (2007), not a full compliance check.</p>');
    expect(html).toContain('data-testid="checklist-tally">1 of 3 with possible evidence · 1 partly there · confirmed by you: 0</p>');
    expect(html).toContain("STROBE (2007) item 5");
    expect(html).toContain("Good practice, not a numbered item");
    expect(html).toContain("STROBE (2007) item 6a");
    expect(html).toContain("Setting");
    expect(html).toContain("<q>Data were collected &lt;weekly&gt; in 2024.</q>");
    expect(html).toContain("Say which way it leans.");
    expect(html).not.toContain("When decides to whom."); // a found item shows its sentence, not the reason
    expect(html).toContain("A sentence mentions this but says this is not reported:</span> <q>Bias is not described.</q>");
    expect(html).toContain('<span class="checklist-part-state">Found:</span> the eligibility criteria');
    expect(html).toContain('<span class="checklist-part-state">Needs your check:</span> how participants were selected');
    expect(html).toContain("<cite>A named reporting guideline</cite>");
    expect(html).not.toMatch(/<meter|<progress/);
    // Without a handler there are no controls; with one, both calls, as toggles named by the topic.
    expect(html).not.toContain("<button");
    const live = renderToStaticMarkup(<WordChecklist state={{ kind: "ready", report: REPORT }} marks={new Map([["b", "not_applicable"]])} onMark={() => {}} />);
    expect(live.match(/data-testid="checklist-na"/g)).toHaveLength(3);
    expect(live.match(/data-testid="checklist-confirm"/g)).toHaveLength(2);
    expect(live).toMatch(/aria-pressed="true"[^>]*data-testid="checklist-na"/);
    expect(live).toContain("Not applicable (your call)");
    expect(live).toContain("confirmed by you: 0 · not applicable (your call): 1");
    expect(live).not.toContain("Say which way it leans."); // the writer's call replaces the reason
    expect(live).toContain('role="status" aria-live="polite" aria-atomic="true" data-testid="checklist-live"');
    const topicId = /<span class="wchecklist-topic-name" id="([^"]+)">Setting<\/span>/.exec(live)![1]!;
    expect(live).toContain(`aria-describedby="${topicId}"`);
    const draft = renderToStaticMarkup(<WordChecklist state={{ kind: "needs_revise" }} onSwitchToRevise={() => {}} />);
    expect(draft).toContain("needs Revise mode");
    expect(draft).toContain("Switch to Revise");
  });
});

describe("the profile line with its evidence (S4c)", () => {
  const p = (x: Partial<ProfileInfo>): ProfileInfo => ({ id: "manuscript", label: "Research article", guessed: true, note: "", evidence: "", rules_off: [], ...x });
  it("names the headings a guess rested on", () => {
    expect(wordProfileLine(p({ evidence: "Methods, Results" }))).toBe("Checked as Research article (from the headings: Methods, Results).");
    expect(wordProfileLine(p({}))).toBe("Checked as Research article (from the headings).");
    expect(wordProfileLine(p({ guessed: false, evidence: "x" }))).toBe("Checked as Research article.");
    expect(wordProfileLine(p({ id: "general", label: "General", evidence: "" }))).toBeNull();
    expect(wordProfileLine(p({ note: "Checked as a policy brief: no abstract.", id: "policy-brief", evidence: "Recommendations" }))).toBe(
      "Checked as a policy brief: no abstract. The guess came from the headings: Recommendations.",
    );
    expect(wordProfileLine(null)).toBeNull();
  });
});

describe("after an edit, the paragraph's other suggestions are stale (Codex review R3)", () => {
  const s = (id: string, paragraph: number) => ({ id, location: { paragraph } }) as unknown as WordSuggestion;
  it("lists the others in the same paragraph only", () => {
    expect(staleAfterEdit([s("a", 1), s("b", 1), s("c", 2), s("d", 1)], 1, "a")).toEqual(["b", "d"]);
    expect(STALE_NOTE).toMatch(/Check the document again/);
  });
});

describe("prefs: the checklist choice and the label store, never text", () => {
  const store = new Map<string, string>();
  beforeEach(() => {
    store.clear();
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (k: string) => store.get(k) ?? null,
        setItem: (k: string, v: string) => void store.set(k, String(v)),
        removeItem: (k: string) => void store.delete(k),
      },
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("round-trips the checklist under its own key and ignores anything else", () => {
    expect(loadChecklistChoice()).toBeNull();
    saveChecklistChoice("prisma");
    expect(loadChecklistChoice()).toBe("prisma");
    expect([...store.keys()]).toEqual(["researchly.word.checklist"]);
    store.set("researchly.word.checklist", "iso9001");
    expect(loadChecklistChoice()).toBeNull();
    expect(isChecklistPref("none")).toBe(true);
    expect(isChecklistPref(3)).toBe(false);
  });

  it("keeps the label store as JSON, reads a broken one as nothing, and clears it", () => {
    saveLabelStore({ paragraph: 2, labels: [] });
    expect(loadLabelStore()).toEqual({ paragraph: 2, labels: [] });
    store.set("researchly.labels", "{not json");
    expect(loadLabelStore()).toBeNull();
    clearLabelStore();
    expect(store.size).toBe(0);
  });

  it("survives storage that throws", () => {
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => {
          throw new Error("denied");
        },
        setItem: () => {
          throw new Error("denied");
        },
        removeItem: () => {
          throw new Error("denied");
        },
      },
    });
    expect(loadChecklistChoice()).toBeNull();
    expect(loadLabelStore()).toBeNull();
    expect(() => saveLabelStore({})).not.toThrow();
    expect(() => clearLabelStore()).not.toThrow();
  });
});

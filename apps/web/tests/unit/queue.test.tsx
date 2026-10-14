import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { Suggestion } from "@researchly/contract";
import { CheckProgress } from "@/components/CheckProgress";
import { Results } from "@/components/Results";
import { PREVIOUS_NOTE, previousMark } from "@/lib/check-session";
import { PassChooser, RevisionQueue } from "@/components/RevisionQueue";
import {
  buildQueue,
  issueLine,
  nextPass,
  occurrenceLine,
  PASSES,
  passCounts,
  passOf,
  posAt,
  resolveSpot,
  spotOf,
  stepSpot,
  timesWord,
  type PassId,
  type QueuePos,
} from "@/lib/queue";
import { scopeMap } from "@/lib/scope";
import { shownSuggestions, withoutSetAside } from "@/lib/view";
import { happyResponse, SAMPLE_TEXT, withDocumentWideResponse } from "../../e2e/fixtures";
import { sugg } from "./helpers";

/*
 * Review proposal 1, the revision queue: "Correctness first", "Clarity next",
 * "Whole-document review"; recurring issues grouped with Next and Previous;
 * no score. The usability test (writers finish a chosen pass without
 * losing findings or context) is the owner's; these tests pin the parts a
 * test can: nothing is lost between passes, repeats are grouped, the place
 * survives a dismissal or a mute, and nothing reads as a score.
 */

const noop = () => undefined;

/** Fourteen of the same misspelling, two other corrections, sentence improvements, a convention, document-wide checks, a preference. */
function chapter(): Suggestion[] {
  const out: Suggestion[] = [];
  let at = 0;
  const add = (id: string, category: Suggestion["category"], extra: Partial<Suggestion>) => {
    out.push(sugg(id, at, at + 5, category, extra));
    at += 40;
  };
  add("c-a", "correction", { rule_id: "W207", tier: "craft", message: "Doubled word: “the the”." });
  for (let i = 0; i < 14; i++) {
    add(`sp-${i}`, "correction", { rule_id: "S001", tier: "spelling", message: "Possible misspelling: “recieve”.", text: "recieve" });
    if (i === 6) add("i-1", "improvement", { rule_id: "W202", message: "Wordy phrase: “in order to”." });
  }
  add("sp-other", "correction", { rule_id: "S001", tier: "spelling", message: "Possible misspelling: “seperate”.", text: "seperate" });
  add("i-2", "improvement", { rule_id: "W202", message: "Wordy phrase: “in order to”." });
  add("i-3", "improvement", { rule_id: "G106", message: "A long sentence." });
  add("cv-1", "convention", { rule_id: "N102", message: "A sentence starts with a numeral." });
  add("doc-1", "improvement", { rule_id: "F601", message: "An abbreviation is used before it is defined." });
  add("doc-2", "improvement", { rule_id: "X401", message: "A number in the text is not in its table." });
  add("pref-1", "preference", { rule_id: "W208", message: "A contraction." });
  return out;
}

describe("the three passes", () => {
  const list = chapter();

  it("hold every suggestion exactly once: walking all three loses nothing", () => {
    const passes = PASSES.map((p) => buildQueue(list, p.id, null));
    const ids = passes.flatMap((q) => q.groups.flatMap((g) => g.items.map((s) => s.id)));
    expect(ids.sort()).toEqual(list.map((s) => s.id).sort());
    expect(new Set(ids).size).toBe(ids.length);
    const counts = passCounts(list, null);
    expect(counts.correctness + counts.clarity + counts.whole).toBe(list.length);
  });

  it("map onto the four types and the rule scopes", () => {
    const pass = (id: string) => passOf(list.find((s) => s.id === id)!, null);
    expect(pass("c-a")).toBe("correctness");
    expect(pass("sp-3")).toBe("correctness");
    expect(pass("i-1")).toBe("clarity");
    expect(pass("pref-1")).toBe("clarity"); // only listed when the writer shows preferences
    expect(pass("cv-1")).toBe("whole");
    expect(pass("doc-1")).toBe("whole");
    expect(pass("doc-2")).toBe("whole"); // X-series structure checks read the whole document
    // The engine's registry, when loaded, decides the scope.
    const known = scopeMap([{ id: "G106", name: "n", short: "s", scope: "document" }] as never);
    expect(pass("i-3")).toBe("clarity");
    expect(passOf(list.find((s) => s.id === "i-3")!, known)).toBe("whole");
  });

  it("never put a Convention in the correctness pass (a convention is never an error)", () => {
    for (const s of list.filter((x) => x.category === "convention")) expect(passOf(s, null)).not.toBe("correctness");
  });

  it("offer the next pass that still has findings", () => {
    expect(nextPass("correctness", { correctness: 1, clarity: 0, whole: 3 })).toBe("whole");
    expect(nextPass("whole", { correctness: 1, clarity: 2, whole: 3 })).toBeNull();
  });
});

describe("recurring issues", () => {
  const q = buildQueue(chapter(), "correctness", null);

  it("group the same finding (same check, same message) into one issue, in order of first appearance", () => {
    expect(q.groups.map((g) => g.label)).toEqual([
      "Doubled word: “the the”.",
      "Possible misspelling: “recieve”.",
      "Possible misspelling: “seperate”.",
    ]);
    expect(q.groups[1]!.items).toHaveLength(14);
    expect(q.total).toBe(16);
    expect(q.groups[1]!.items.map((s) => s.id)).toEqual(Array.from({ length: 14 }, (_, i) => `sp-${i}`));
  });

  it("step through occurrences and issues without wrapping, so the end of a pass is visible", () => {
    let spot = resolveSpot(q, null)!;
    expect(spot).toEqual({ group: 0, occurrence: 0 });
    expect(stepSpot(q, spot, "previous-issue")).toEqual(spot);
    spot = stepSpot(q, spot, "next-issue");
    expect(spot).toEqual({ group: 1, occurrence: 0 });
    for (let i = 0; i < 20; i++) spot = stepSpot(q, spot, "next-occurrence");
    expect(spot).toEqual({ group: 1, occurrence: 13 });
    expect(occurrenceLine(spot, q)).toBe("Occurrence 14 of 14");
    spot = stepSpot(q, spot, "previous-occurrence");
    expect(spot.occurrence).toBe(12);
    spot = stepSpot(q, stepSpot(q, spot, "next-issue"), "next-issue");
    expect(spot).toEqual({ group: 2, occurrence: 0 });
    expect(issueLine(spot, q)).toBe("Issue 3 of 3 in this pass");
    expect(occurrenceLine(spot, q)).toBeNull();
    expect(spotOf(q, "sp-5")).toEqual({ group: 1, occurrence: 5 });
  });

  it("are tallied in words, never scored", () => {
    expect([timesWord(1), timesWord(2), timesWord(14), timesWord(1200)]).toEqual(["once", "twice", "14 times", "1,200 times"]);
  });
});

describe("keeping the writer's place", () => {
  const list = chapter();
  const q = buildQueue(list, "correctness", null);
  const at: QueuePos = posAt(q, { group: 1, occurrence: 4 }); // the fifth "recieve"

  it("a dismissed occurrence gives way to the next one of the same issue", () => {
    const after = buildQueue(withoutSetAside(list, new Set([at.id])), "correctness", null);
    const spot = resolveSpot(after, at)!;
    expect(spot).toEqual({ group: 1, occurrence: 4 });
    expect(after.groups[1]!.items[4]!.id).toBe("sp-5");
  });

  it("the last occurrence dismissed: the place moves back to the one before", () => {
    const last = posAt(q, { group: 1, occurrence: 13 });
    const after = buildQueue(withoutSetAside(list, new Set([last.id])), "correctness", null);
    expect(resolveSpot(after, last)).toEqual({ group: 1, occurrence: 12 });
  });

  it("a muted rule removes the whole issue: the place moves to the issue that now stands there", () => {
    const after = buildQueue(withoutSetAside(list, new Set(), new Set(["S001"])), "correctness", null);
    expect(after.groups.map((g) => g.label)).toEqual(["Doubled word: “the the”."]);
    expect(resolveSpot(after, at)).toEqual({ group: 0, occurrence: 0 });
  });

  it("a re-check that kept the suggestion (same id) keeps the exact place, even if others moved", () => {
    const fewer = list.filter((s) => s.id !== "c-a" && s.id !== "sp-0");
    const after = buildQueue(fewer, "correctness", null);
    const spot = resolveSpot(after, at)!;
    expect(after.groups[spot.group]!.items[spot.occurrence]!.id).toBe(at.id);
  });

  it("an empty pass has no place", () => {
    expect(resolveSpot(buildQueue([], "clarity", null), at)).toBeNull();
  });
});

describe("the queue on screen", () => {
  const list = chapter();
  const counts = passCounts(list, null);

  it("the chooser offers all suggestions and the three passes as toggle buttons with tallies", () => {
    const html = renderToStaticMarkup(<PassChooser choice="correctness" counts={counts} onChoose={noop} />);
    expect(html).toContain('aria-pressed="true" data-testid="pass-correctness"');
    expect(html).toContain('aria-pressed="false" data-testid="pass-all"');
    expect(html).toContain("Correctness first");
    expect(html).toContain("Clarity next");
    expect(html).toContain("Whole-document review");
    expect(html).toMatch(/16<span class="sr-only"> findings<\/span>/);
    expect(html).toContain("Likely errors");
  });

  it("a pass says where the writer is, politely, with keyboard-operable Next and Previous", () => {
    const q = buildQueue(list, "correctness", null);
    const html = renderToStaticMarkup(
      <RevisionQueue
        queue={q}
        at={posAt(q, { group: 1, occurrence: 1 })}
        onMove={noop}
        renderCard={(s) => <p data-card={s.id}>{s.message}</p>}
        counts={counts}
        onPass={noop}
      />,
    );
    expect(html).toMatch(/aria-live="polite"[^>]*data-testid="queue-position">Issue 2 of 3 in this pass\. Occurrence 2 of 14\./);
    expect(html).toContain('data-card="sp-1"');
    // Native buttons; an end is aria-disabled (still focusable), never removed from the tab order.
    expect(html).toMatch(/<button type="button"[^>]*data-testid="queue-next">Next issue<\/button>/);
    expect(html).toMatch(/<button type="button"[^>]*aria-label="Previous occurrence"[^>]*data-testid="occ-prev">Previous<\/button>/);
    expect(html).not.toContain("disabled=\"\"");
    expect(html).toContain("Found 14 times in your text.");
    expect(html).toContain("16 findings in this pass");
    expect(html).not.toMatch(/score|grade|%/i);
  });

  it("at the end of a pass it says so and offers the next pass", () => {
    const q = buildQueue(list, "correctness", null);
    const html = renderToStaticMarkup(
      <RevisionQueue queue={q} at={posAt(q, { group: 2, occurrence: 0 })} onMove={noop} renderCard={() => null} counts={counts} onPass={noop} />,
    );
    expect(html).toContain("This is the last issue in this pass.");
    expect(html).toContain("Go on to Clarity next");
    expect(html).toMatch(/data-testid="queue-next"[^>]*>Next issue/);
    expect(html).toMatch(/aria-disabled="true"[^>]*data-testid="queue-next"/);
  });

  it("an empty pass says so, naming the section when one is chosen", () => {
    const html = renderToStaticMarkup(
      <RevisionQueue
        queue={buildQueue([], "whole", null)}
        at={null}
        onMove={noop}
        renderCard={() => null}
        counts={{ correctness: 0, clarity: 0, whole: 0 }}
        onPass={noop}
        scopeNote="in the Methods section"
      />,
    );
    expect(html).toContain("Nothing in this pass in the Methods section.");
  });

  it("every pass's wording is plain: no score, no em dash, no course or lecturer", () => {
    const words = PASSES.flatMap((p) => [p.title, p.help]).join(" ");
    expect(words).not.toMatch(/—|score|grade|lecture|course/i);
    // Conventions are named as not errors in the pass that holds them.
    expect(PASSES.find((p) => p.id === "whole")!.help).toMatch(/Conventions are not errors/);
  });
});

describe("the results view with a pass chosen", () => {
  const base = {
    data: happyResponse,
    submittedText: SAMPLE_TEXT,
    showPreferences: false,
    stale: false,
    busy: false,
    onRevealPreferences: noop,
    view: "suggestions" as const,
    onView: noop,
  };

  it("lists the pass as a queue and highlights only its findings in the text", () => {
    const pass: PassId = "correctness";
    const html = renderToStaticMarkup(<Results {...base} queue={{ pass, at: null }} onQueue={noop} />);
    expect(html).toContain('data-testid="queue"');
    expect(html).toContain('data-pass="correctness"');
    const corrections = happyResponse.suggestions.filter((s) => s.category === "correction");
    const marks = [...html.matchAll(/data-sids="([^"]+)"/g)].flatMap((m) => m[1]!.split(" "));
    expect(marks.length).toBeGreaterThan(0);
    for (const id of marks) expect(corrections.map((s) => s.id)).toContain(id);
    // The category chips step aside; the section chooser stays.
    expect(html).not.toContain('data-testid="filter-all"');
    expect(html).toContain('data-testid="section-filter"');
  });

  it("the whole-document pass holds the document-wide checks and points to the brief and the map at its end", () => {
    const data = withDocumentWideResponse;
    const counts = passCounts(data.suggestions, null);
    const q = buildQueue(shownSuggestions(data, false), "whole", null);
    const last = posAt(q, { group: q.groups.length - 1, occurrence: q.groups[q.groups.length - 1]!.items.length - 1 });
    const html = renderToStaticMarkup(<Results {...base} data={data} queue={{ pass: "whole", at: last }} onQueue={noop} />);
    expect(counts.whole).toBeGreaterThan(0);
    expect(html).toContain('data-pass="whole"');
    expect(html).toContain("Issue 3 of 3 in this pass.");
    expect(html).toContain("Open the reviewer’s brief");
    expect(html).toContain("Open the narrative map");
  });

  it("without a pass the list is exactly as before", () => {
    const html = renderToStaticMarkup(<Results {...base} />);
    expect(html).toContain('data-testid="filter-all"');
    expect(html).not.toContain('data-testid="queue"');
    expect(html).toContain('aria-pressed="true" data-testid="pass-all"');
  });
});

describe("previous results while a newer check runs (review proposal 8)", () => {
  const base = {
    data: happyResponse,
    submittedText: SAMPLE_TEXT,
    showPreferences: false,
    stale: false,
    busy: true,
    onRevealPreferences: noop,
    view: "suggestions" as const,
    onView: noop,
  };

  it("are marked as the previous check's, in words, for each reason", () => {
    for (const reason of ["running", "cancelled", "failed"] as const) {
      const html = renderToStaticMarkup(<Results {...base} previous={reason} />);
      expect(html).toContain(`data-testid="previous-note" data-reason="${reason}"`);
      expect(html).toContain(PREVIOUS_NOTE[reason]);
    }
    expect(renderToStaticMarkup(<Results {...base} busy={false} />)).not.toContain("previous-note");
  });

  it("the mark follows the latest check: running, failed, cancelled; none once a new answer is current or nothing is on screen", () => {
    expect(previousMark(true, { phase: "running", note: null })).toBe("running");
    expect(previousMark(true, { phase: "error", note: null })).toBe("failed");
    expect(previousMark(true, { phase: "done", note: "cancelled" })).toBe("cancelled");
    expect(previousMark(true, { phase: "done", note: null })).toBeNull();
    expect(previousMark(false, { phase: "running", note: null })).toBeNull();
  });

  it("the progress line names the elapsed time outside the live region and says 'still checking' in it only when long", () => {
    const html = renderToStaticMarkup(<CheckProgress startedAt={Date.now()} what="your text" hasPrevious />);
    expect(html).toContain("Checking your text…");
    expect(html).toMatch(/Time so far: <span data-testid="check-elapsed">0 s<\/span>/);
    expect(html).toMatch(/role="status" aria-live="polite" aria-atomic="true" data-testid="check-progress-live"><\/p>/);
    const long = renderToStaticMarkup(<CheckProgress startedAt={Date.now() - 65_000} what="your text" hasPrevious />);
    expect(long).toMatch(/data-testid="check-progress-live">Still checking your text\. A long document can take a minute or two; your previous results stay below until it finishes\.<\/p>/);
    expect(long).toMatch(/data-testid="check-elapsed">1 min 0[5-6] s</);
  });
});

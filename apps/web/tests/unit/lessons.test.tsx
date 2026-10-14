import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { LEARN_CARDS } from "@researchly/contract";
import { ChecklistView } from "@/components/ChecklistView";
import { LessonDisclosure } from "@/components/LessonDisclosure";
import { SuggestionCard } from "@/components/SuggestionCard";
import { ViewTabs } from "@/components/ViewTabs";
import { CHECKLIST } from "../../e2e/fixtures";
import { sugg } from "./helpers";

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
const noop = () => undefined;

describe("the lesson disclosure", () => {
  const card = LEARN_CARDS.find((c) => c.id === "hedging")!;
  const html = renderToStaticMarkup(<LessonDisclosure learnRef="hedging" />);

  it("is a closed native disclosure called 'The lesson'", () => {
    expect(html.startsWith('<details class="lesson"')).toBe(true);
    expect(html).not.toMatch(/<details[^>]* open/);
    expect(html).toContain("<summary>The lesson</summary>");
  });

  it("holds the card's title, lesson, before and after quoted and labelled, the habit and the source", () => {
    expect(html).toContain(esc(card.title));
    expect(html).toContain(esc(card.lesson));
    expect(html).toMatch(/<figcaption class="lesson-example-label">Before<\/figcaption><blockquote class="lesson-quote"><q>/);
    expect(html).toContain(`<q>${esc(card.before)}</q>`);
    expect(html).toContain(`<q>${esc(card.after)}</q>`);
    expect(html.indexOf(esc(card.before))).toBeLessThan(html.indexOf(esc(card.after)));
    expect(html).toContain(esc(card.habit));
    expect(html).toContain(`<cite>${esc(card.source)}</cite>`);
  });

  it("links to all lessons in a new tab, so the results are never left", () => {
    expect(html).toMatch(/<a href="\/learn" target="_blank" rel="noopener"[^>]*>All lessons<span class="sr-only"> \(opens in a new tab\)<\/span><\/a>/);
  });

  it("renders nothing without a known card", () => {
    for (const ref of [null, undefined, "", "no-such-card"]) expect(renderToStaticMarkup(<LessonDisclosure learnRef={ref} />)).toBe("");
  });
});

describe("the card's lesson and dismissal", () => {
  const s = sugg("x1", 0, 4, "improvement", { learn_ref: "concise-words", text: "word" });

  it("carries the lesson after the full reasoning and before the source, and offers 'Not an issue here' only when the results can dismiss", () => {
    const withDismiss = renderToStaticMarkup(<SuggestionCard suggestion={s} active={false} placeable onShowInText={noop} onDismiss={noop} />);
    const order = ['data-testid="card-reasoning"', 'data-testid="lesson"', 'class="card-source"', 'data-testid="dismiss"'].map((m) => withDismiss.indexOf(m));
    expect(order.every((i) => i >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(withDismiss).toContain(">Not an issue here</button>");
    const without = renderToStaticMarkup(<SuggestionCard suggestion={s} active={false} placeable onShowInText={noop} />);
    expect(without).not.toContain("Not an issue here");
    expect(without).not.toContain("card-actions");
  });

  it("has no lesson when the engine names none", () => {
    const html = renderToStaticMarkup(<SuggestionCard suggestion={{ ...s, learn_ref: null }} active={false} placeable onShowInText={noop} />);
    expect(html).not.toContain('data-testid="lesson"');
  });
});

describe("the results tabs", () => {
  it("offer three views by default and the checklist only when asked", () => {
    const three = renderToStaticMarkup(<ViewTabs view="suggestions" onChange={noop} idBase="t" />);
    expect([...three.matchAll(/data-testid="view-([a-z]+)"/g)].map((m) => m[1])).toEqual(["suggestions", "brief", "narrative"]);
    const four = renderToStaticMarkup(<ViewTabs view="checklist" onChange={noop} idBase="t" views={["suggestions", "brief", "narrative", "checklist"]} />);
    expect([...four.matchAll(/data-testid="view-([a-z]+)"/g)].map((m) => m[1])).toEqual(["suggestions", "brief", "narrative", "checklist"]);
    expect(four).toMatch(/aria-selected="true"[^>]*data-testid="view-checklist"/);
  });
});

describe("the checklist view", () => {
  const screen = renderToStaticMarkup(<ChecklistView report={CHECKLIST} marks={new Map()} onMark={noop} />);
  const statuses = (html: string) => [...html.matchAll(/<span class="checklist-status-word">([^<]+)<\/span>/g)].map((m) => m[1]);
  const item = (html: string, id: string) => {
    const at = html.indexOf(`data-item="${id}"`);
    const next = html.indexOf('class="checklist-item"', at);
    return html.slice(at, next === -1 ? html.indexOf("</ol>", at) : next);
  };

  it("reads as a document: edition, tally, the note, every item in order with topic, item numbers, question and a cautious status, then the source and the scope line", () => {
    expect(screen).toContain('data-testid="checklist-edition">Selected themes of EPIFORGE 2020, not a full compliance check.</p>');
    expect(screen).toContain('data-testid="checklist-tally">1 of 6 with possible evidence · 1 partly there · confirmed by you: 0</p>');
    expect(screen).toContain(esc(CHECKLIST.note));
    expect([...screen.matchAll(/data-item="([a-z-]+)"/g)].map((m) => m[1])).toEqual(CHECKLIST.items.map((i) => i.id));
    for (const it of CHECKLIST.items) {
      expect(screen).toContain(`>${esc(it.topic)}</h3>`);
      expect(screen).toContain(esc(it.question));
    }
    expect(statuses(screen)).toEqual([
      "Found: please confirm",
      "Needs your check",
      "Needs your check",
      "Partly there",
      "Needs your check",
      "Needs your check",
    ]);
    expect(screen).not.toMatch(/reported<|>Reported|“reported”/);
    // Item numbers from the guideline; an unnumbered item is said to be good practice.
    expect(item(screen, "model")).toContain('data-testid="checklist-refs">EPIFORGE 2020 item 8</p>');
    expect(item(screen, "data")).toContain('data-testid="checklist-refs">EPIFORGE 2020 items 5 and 6</p>');
    expect(item(screen, "funding")).toContain('data-testid="checklist-refs">Good practice, not a numbered item</p>');
    // Found: the writer's own sentence, quoted, as possible evidence. Needs your check: the reason in everyday words.
    expect(item(screen, "model")).toContain(`<q>${esc(CHECKLIST.items[0]!.evidence!)}</q>`);
    expect(item(screen, "model")).toContain("Possible evidence: ");
    expect(item(screen, "model")).not.toContain(esc(CHECKLIST.items[0]!.plain));
    expect(item(screen, "horizon")).toContain(`<p class="checklist-plain">${esc(CHECKLIST.items[1]!.plain)}</p>`);
    expect(screen.indexOf("checklist-source")).toBeLessThan(screen.indexOf('data-testid="checklist-scope">This checks reporting only, never the science.'));
    expect(screen).toContain(`<cite>${esc(CHECKLIST.source)}</cite>`);
    expect(screen).not.toMatch(/<meter|<progress|\d+ ?%|score/i);
  });

  it("lists a compound question's parts, which are found (with the sentence) and which need a check", () => {
    const data = item(screen, "data");
    const parts = [...data.matchAll(/data-found="(true|false)"><p class="checklist-part-line"><span class="checklist-part-state">([^<]+)<\/span> ([^<]+)<\/p>/g)].map((m) => [
      m[1],
      m[2],
      m[3],
    ]);
    expect(parts).toEqual([
      ["true", "Found:", "the data sources"],
      ["false", "Needs your check:", "whether the data are available"],
    ]);
    expect(data.match(/<q>/g)).toHaveLength(1);
    expect(data).toContain(`<q>${esc(CHECKLIST.items[3]!.parts![0]!.evidence!)}</q>`);
    // Partly there: the reason it matters too, for the part still to find.
    expect(data).toContain(esc(CHECKLIST.items[3]!.plain));
  });

  it("says quietly what the engine set aside and which section the document lacks", () => {
    const horizon = item(screen, "horizon");
    expect(horizon).toContain('data-reason="future"><span>A sentence mentions this but promises it for later:</span> <q>');
    expect(horizon).toContain(esc(CHECKLIST.items[1]!.not_counted!.quote));
    const evaluation = item(screen, "evaluation");
    expect(evaluation).toContain('data-testid="checklist-absent">No Results section was found to look in.</p>');
    // An absent section replaces "readers look in", which would point at nothing.
    expect(evaluation).not.toContain("readers look in");
    expect(item(screen, "uncertainty")).toContain("readers look in Results, Methods");
  });

  it("offers 'Confirmed by me' where there is possible evidence and 'Not applicable' on every item, as toggle buttons named by the topic", () => {
    expect(screen.match(/data-testid="checklist-na"/g)).toHaveLength(CHECKLIST.items.length);
    expect(screen.match(/data-testid="checklist-confirm"/g)).toHaveLength(2);
    expect(item(screen, "model")).toContain(">Confirmed by me</button>");
    expect(item(screen, "data")).toContain(">Confirmed by me</button>");
    expect(item(screen, "horizon")).not.toContain("checklist-confirm");
    expect(screen).not.toMatch(/aria-pressed="true"/);
    const titleId = /<h3 class="checklist-topic" id="([^"]+)">Model description<\/h3>/.exec(screen)![1]!;
    expect(item(screen, "model")).toContain(`aria-pressed="false" aria-describedby="${titleId}"`);
    expect(screen).toContain('role="status" aria-live="polite" aria-atomic="true" data-testid="checklist-live"');
  });

  it("says the writer's calls in place of the status, counts confirmations, and keeps the evidence of a confirmed item", () => {
    const marks = new Map([
      ["model", "confirmed"],
      ["horizon", "not_applicable"],
    ] as const);
    const html = renderToStaticMarkup(<ChecklistView report={CHECKLIST} marks={marks} onMark={noop} />);
    expect(statuses(html).slice(0, 2)).toEqual(["Confirmed by you", "Not applicable (your call)"]);
    expect(html).toContain("1 of 6 with possible evidence · 1 partly there · confirmed by you: 1 · not applicable (your call): 1");
    expect(item(html, "model")).toContain(`<q>${esc(CHECKLIST.items[0]!.evidence!)}</q>`);
    expect(item(html, "model")).toMatch(/aria-pressed="true"[^>]*data-testid="checklist-confirm"/);
    expect(item(html, "horizon")).toMatch(/aria-pressed="true"[^>]*data-testid="checklist-na"/);
    expect(item(html, "horizon")).not.toContain(esc(CHECKLIST.items[1]!.plain));
    expect(item(html, "horizon")).not.toContain("A sentence mentions this");
  });

  it("on paper has no controls and keeps found, confirmed by the writer, not applicable and needs-check apart", () => {
    const marks = new Map([
      ["data", "confirmed"],
      ["uncertainty", "not_applicable"],
    ] as const);
    const paper = renderToStaticMarkup(<ChecklistView report={CHECKLIST} marks={marks} variant="print" />);
    expect(paper).not.toContain("<button");
    expect(paper).not.toContain("aria-live");
    expect(paper).toContain('class="checklist checklist-print"');
    expect(statuses(paper)).toEqual([
      "Found: please confirm",
      "Needs your check",
      "Not applicable (the writer’s call)",
      "Confirmed by the writer",
      "Needs your check",
      "Needs your check",
    ]);
    expect(paper).toContain("1 of 6 with possible evidence · 1 partly there · confirmed by the writer: 1 · not applicable (the writer’s call): 1");
    expect(paper).toContain("Selected themes of EPIFORGE 2020, not a full compliance check.");
  });
});

import { describe, expect, it } from "vitest";
import { MAX_LIVE_CHARS, MAX_LIVE_PARAGRAPHS, type LiveSuggestion, type Suggestion } from "@researchly/contract";
import {
  asSuggestion,
  carryItems,
  classifyHeading,
  fromLive,
  isLiveFormat,
  isSectionName,
  itemAt,
  itemsFromFullCheck,
  itemSummary,
  maskMarkdownInline,
  nextBatch,
  paragraphId,
  paragraphKey,
  paragraphMarks,
  snapUtf16,
  splitParagraphs,
  textToSend,
  visibleItems,
  type LiveItem,
} from "@/lib/live-paragraphs";

function item(over: Partial<LiveItem> & Pick<LiveItem, "begin" | "end">): LiveItem {
  return {
    id: over.id ?? `i${over.begin}-${over.end}`,
    rule_id: "G110",
    rule_name: "Repeated word",
    category: "correction",
    text: "",
    message: "The word is repeated.",
    plain: "",
    why: "",
    source: "Researchly grammar notes",
    learn_ref: null,
    section: "discussion",
    tier: "craft",
    fix_safety: "review",
    replacements: [],
    ...over,
  };
}

describe("splitting the editor's text into paragraphs", () => {
  it("plain text: a blank line ends a paragraph; a section-name line is a heading of its own", () => {
    const text = "Methods\nWe fitted a model.\nIt converged.\n\nDiscussion\nIn order to see.\n\n\nMore here.\n";
    const { paragraphs, headings } = splitParagraphs(text, "plain");
    expect(headings.map((h) => [h.text, h.section])).toEqual([
      ["Methods", "methods"],
      ["Discussion", "discussion"],
    ]);
    expect(paragraphs.map((p) => [p.text, p.heading])).toEqual([
      ["We fitted a model.\nIt converged.", "Methods"],
      ["In order to see.", "Discussion"],
      ["More here.", "Discussion"],
    ]);
    for (const p of paragraphs) expect(text.slice(p.start, p.end)).toBe(p.text);
    expect(paragraphs.map((p) => p.index)).toEqual([0, 1, 2]);
  });

  it("plain text: a short capitalised line that names no section is prose, as the engine reads it", () => {
    const { paragraphs, headings } = splitParagraphs("Acknowledgements\nThanks to all.", "plain");
    expect(headings).toEqual([]);
    expect(paragraphs[0]!.text).toBe("Acknowledgements\nThanks to all.");
    expect(paragraphs[0]!.heading).toBe("");
  });

  it("text before any heading has no heading (the article type's body section)", () => {
    expect(splitParagraphs("Just a sentence.", "plain").paragraphs[0]!.heading).toBe("");
  });

  it("Markdown: # lines are headings; fenced code, front matter and div fences are not prose", () => {
    const text = "---\ntitle: X\n---\n# Methods\n\nWe fit it.\n\n```r\n# not a heading\nx <- 1\n```\n\n::: {.callout}\nA note.\n:::\n";
    const { paragraphs, headings } = splitParagraphs(text, "markdown");
    expect(headings.map((h) => h.text)).toEqual(["Methods"]);
    expect(paragraphs.map((p) => p.text)).toEqual(["We fit it.", "A note."]);
    expect(paragraphs.every((p) => p.heading === "Methods")).toBe(true);
  });

  it("Markdown: a nested heading inherits its section as resolve_sections does", () => {
    const text = "# Results\n\n## Model fit\n\nA.\n\n# Methods\n\n## Priors\n\nB.\n\n# Discussion\n\n## Limitations\n\nC.\n\n# A model of measles\n\n## Data\n\nD.\n";
    const { paragraphs, headings } = splitParagraphs(text, "markdown");
    expect(headings.map((h) => [h.text, h.section])).toEqual([
      ["Results", "results"],
      ["Model fit", "results"],
      ["Methods", "methods"],
      ["Priors", "methods"],
      ["Discussion", "discussion"],
      ["Limitations", "limitations"],
      ["A model of measles", "methods"],
      ["Data", "methods"],
    ]);
    // What is sent names the section the full check would give each paragraph.
    expect(paragraphs.map((p) => [p.text, p.heading])).toEqual([
      ["A.", "Results"],
      ["B.", "Methods"],
      ["C.", "Limitations"],
      ["D.", "Data"],
    ]);
    for (const p of paragraphs) expect(classifyHeading(p.heading)).toBe(headings.find((h) => h.sendAs === p.heading)!.section);
  });

  it("only plain text and Markdown are read live", () => {
    expect(isLiveFormat("plain")).toBe(true);
    expect(isLiveFormat("markdown")).toBe(true);
    expect(isLiveFormat("latex")).toBe(false);
  });

  it("knows a plain section name from a topical title", () => {
    expect(isSectionName("3.2 Statistical analysis")).toBe(true);
    expect(isSectionName("Materials and methods")).toBe(true);
    expect(isSectionName("A model of measles transmission")).toBe(false);
  });
});

describe("keys and ids", () => {
  it("the same heading and text give the same key; either changing gives another", () => {
    expect(paragraphKey("Methods", "We fit.")).toBe(paragraphKey("Methods", "We fit."));
    expect(paragraphKey("Methods", "We fit.")).not.toBe(paragraphKey("Discussion", "We fit."));
    expect(paragraphKey("Methods", "We fit.")).not.toBe(paragraphKey("Methods", "We fit!"));
    expect(paragraphKey("A", "BC")).not.toBe(paragraphKey("AB", "C"));
  });

  it("ids fit the contract's pattern and never carry the text", () => {
    const id = paragraphId(paragraphKey("Methods", "A secret sentence about dengue."));
    expect(id).toMatch(/^[A-Za-z0-9._:-]{1,64}$/);
    expect(id).not.toContain("dengue");
  });
});

describe("what is sent", () => {
  it("Markdown formatting is blanked, same length, words kept", () => {
    const src = "The fit was **good** [@smith2020], see [the table](https://x.org) and ![fig](a.png) <b>here</b> @jones.";
    const out = maskMarkdownInline(src);
    expect(out).toHaveLength(src.length);
    expect(out).toContain("  good  ");
    expect(out).toContain(" the table");
    expect(out).not.toMatch(/[*@[\]()<>]/);
    expect(out).not.toContain("x.org");
    expect(maskMarkdownInline("snake_case stays, _emph_ goes")).toBe("snake_case stays,  emph  goes");
  });

  it("plain text goes as written", () => {
    const [p] = splitParagraphs("A **b** c.", "plain").paragraphs;
    expect(textToSend(p!, "plain")).toBe("A **b** c.");
    expect(textToSend(p!, "markdown")).toBe("A   b   c.");
  });

  it("a batch: nearest the caret first, one per key, within 50 paragraphs and 20,000 characters", () => {
    const text = Array.from({ length: 80 }, (_, i) => `Paragraph number ${i}.`).join("\n\n");
    const { paragraphs } = splitParagraphs(text, "plain");
    const caret = paragraphs[60]!.start + 3;
    const batch = nextBatch(paragraphs, caret);
    expect(batch).toHaveLength(MAX_LIVE_PARAGRAPHS);
    expect(batch[0]!.index).toBe(60);
    expect(new Set(batch.map((p) => p.key)).size).toBe(batch.length);

    const long = "x".repeat(9000);
    const big = splitParagraphs(`${long}a\n\n${long}b\n\n${long}c\n\n${"y".repeat(MAX_LIVE_CHARS + 1)}`, "plain").paragraphs;
    const two = nextBatch(big, 0);
    expect(two.map((p) => p.index)).toEqual([0, 1]);
    expect(two.reduce((n, p) => n + p.text.length, 0)).toBeLessThanOrEqual(MAX_LIVE_CHARS);
    // A paragraph longer than one request is never sent (Check covers it).
    expect(nextBatch([big[3]!], 0)).toEqual([]);

    const dup = splitParagraphs("Same.\n\nSame.\n\n   \n\nOther.", "plain").paragraphs;
    expect(nextBatch(dup, 0).map((p) => p.text)).toEqual(["Same.", "Other."]);
  });
});

describe("drawing: UTF-16 ranges become mirror marks", () => {
  const live = (over: Partial<LiveSuggestion>): LiveSuggestion => ({
    id: "abc",
    rule_id: "G110",
    rule_name: "Repeated word",
    category: "correction",
    critical: true,
    tier: "craft",
    begin: 0,
    end: 0,
    text: "",
    section: "discussion",
    message: "m",
    plain: "",
    why: "",
    source: "s",
    learn_ref: null,
    replacements: ["the"],
    fix_safety: "review",
    ...over,
  });

  it("an emoji and a mathematical letter before the words: the ranges are string indices, the marks cover exactly the words", () => {
    const para = "Dengue 🦟 and 𝑅ₜ rose; the the counts fell.";
    const at = para.indexOf("the the");
    const it1 = fromLive(live({ begin: at, end: at + 7, text: "the the" }), para)!;
    expect(it1.text).toBe("the the");
    const runs = paragraphMarks(para, [it1]);
    expect(runs.map((r) => (r.kind === "text" ? r.text : "")).join("")).toBe(para);
    const marked = runs.filter((r) => r.kind === "text" && r.ids.length);
    expect(marked.map((r) => (r.kind === "text" ? r.text : ""))).toEqual(["the the"]);
  });

  it("combining marks stay inside the underline", () => {
    const para = "The café study was naivë.";
    const at = para.indexOf("café");
    const it1 = fromLive(live({ begin: at, end: at + 5 }), para)!;
    const runs = paragraphMarks(para, [it1]);
    const marked = runs.find((r) => r.kind === "text" && r.ids.length);
    expect(marked && marked.kind === "text" ? marked.text : "").toBe("café");
  });

  it("a range ending inside a surrogate pair never splits it", () => {
    const para = "a🦟b";
    expect(snapUtf16(para, 2)).toBe(1);
    expect(snapUtf16(para, 3)).toBe(3);
    const runs = paragraphMarks(para, [item({ begin: 1, end: 2 })]);
    expect(runs.map((r) => (r.kind === "text" ? r.text : "")).join("")).toBe(para);
  });

  it("overlapping underlines render once, the Correction styling the overlap", () => {
    const para = "could potentially suggest";
    const runs = paragraphMarks(para, [
      item({ id: "a", begin: 0, end: 25, category: "preference" }),
      item({ id: "b", begin: 6, end: 17, category: "correction" }),
    ]);
    const mid = runs.find((r) => r.kind === "text" && r.text === "potentially");
    expect(mid && mid.kind === "text" ? [mid.category, mid.ids] : null).toEqual(["correction", ["b", "a"]]);
  });

  it("a zero-length range is an insertion point", () => {
    const runs = paragraphMarks("ab", [item({ begin: 1, end: 1 })]);
    expect(runs.some((r) => r.kind === "point" && r.at === 1)).toBe(true);
  });

  it("an answer that does not fit its paragraph is not drawn", () => {
    expect(fromLive(live({ begin: 3, end: 40 }), "short")).toBeNull();
    expect(fromLive(live({ category: "tone" as never, begin: 0, end: 1 }), "short")).toBeNull();
  });

  it("Preferences only when asked for; nothing dismissed", () => {
    const xs = [item({ id: "p", begin: 0, end: 1, category: "preference" }), item({ id: "c", begin: 0, end: 1 })];
    expect(visibleItems(xs, false, new Set()).map((i) => i.id)).toEqual(["c"]);
    expect(visibleItems(xs, true, new Set(["c"])).map((i) => i.id)).toEqual(["p"]);
  });
});

describe("carrying underlines across an edit", () => {
  const before = "In order to see the the dynamics clearly.";
  const xs = [
    item({ id: "a", begin: 0, end: 11, text: "In order to" }),
    item({ id: "b", begin: 16, end: 23, text: "the the" }),
    item({ id: "c", begin: 33, end: 40, text: "clearly" }),
  ];

  it("typing after an underline leaves it; typing before one moves it; touching one drops it", () => {
    const after = "In order to see more of the the dynamics clearly.";
    const kept = carryItems(xs, before, after);
    expect(kept.map((i) => [i.id, after.slice(i.begin, i.end)])).toEqual([
      ["a", "In order to"],
      ["b", "the the"],
      ["c", "clearly"],
    ]);
    const fixed = "In order to see the dynamics clearly.";
    expect(carryItems(xs, before, fixed).map((i) => i.id)).toEqual(["a", "c"]);
  });

  it("nothing to carry, nothing carried", () => {
    expect(carryItems([], before, "x")).toEqual([]);
  });
});

describe("a full check's suggestions as underlines", () => {
  // Code-point spans, as /v1/analyze sends them (the emoji counts once there, twice here).
  const text = "Introduction\nDengue 🦟 is clearly proven here.\n\nDiscussion\nIn order to see the the end.\n";
  const cp = (s: string) => Array.from(s).length;
  const span = (words: string) => {
    const at = text.indexOf(words);
    return { start: cp(text.slice(0, at)), end: cp(text.slice(0, at)) + cp(words), line: 0, col: 0 };
  };
  const sugg = (id: string, words: string, rule = "C201", extra: Partial<Suggestion> = {}): Suggestion => ({
    id,
    rule_id: rule,
    rule_name: rule,
    category: "improvement",
    confidence: 1,
    fix_safety: "review",
    message: "m",
    plain: "",
    why: "",
    source: "s",
    section: "introduction",
    tier: "craft",
    text: words,
    span: span(words),
    ...extra,
  });

  it("places each sentence-level suggestion in its paragraph, in UTF-16; whole-document ones are left out", () => {
    const map = itemsFromFullCheck(
      text,
      "plain",
      [sugg("a", "clearly proven"), sugg("b", "the the", "G110", { replacement: "the" }), sugg("w", "Dengue", "W211")],
      (id) => id === "W211",
    );
    const { paragraphs } = splitParagraphs(text, "plain");
    expect(map.size).toBe(2);
    const first = map.get(paragraphs[0]!.key)!;
    expect(first.map((i) => [i.id, paragraphs[0]!.text.slice(i.begin, i.end)])).toEqual([["a", "clearly proven"]]);
    const second = map.get(paragraphs[1]!.key)!;
    expect(second.map((i) => [i.id, i.text, i.replacements])).toEqual([["b", "the the", ["the"]]]);
  });

  it("prefers the engine's own UTF-16 offsets when it sends them", () => {
    const at = text.indexOf("clearly proven");
    const s = sugg("a", "clearly proven", "C201", { span: { start: 0, end: 1, line: 0, col: 0 }, begin16: at, end16: at + 14 });
    const map = itemsFromFullCheck(text, "plain", [s], () => false);
    const p = splitParagraphs(text, "plain").paragraphs[0]!;
    expect(map.get(p.key)!.map((i) => p.text.slice(i.begin, i.end))).toEqual(["clearly proven"]);
  });

  it("every paragraph gets an entry, so none is sent again until it changes", () => {
    const map = itemsFromFullCheck(text, "plain", [], () => false);
    expect([...map.values()]).toEqual([[], []]);
  });
});

describe("reading an underline out", () => {
  it("the item at the caret: the more important one where two meet", () => {
    const xs = [item({ id: "p", begin: 0, end: 20, category: "preference" }), item({ id: "c", begin: 5, end: 9 })];
    expect(itemAt(xs, 6)?.id).toBe("c");
    expect(itemAt(xs, 15)?.id).toBe("p");
    expect(itemAt(xs, 25)).toBeNull();
  });

  it("one line for a list or a screen reader, without rule codes", () => {
    const s = itemSummary(item({ begin: 0, end: 7, text: "the the", message: "The word ‘the’ is repeated." }), "Correction");
    expect(s).toBe("Correction: The word ‘the’ is repeated. (“the the”)");
    expect(s).not.toContain("G110");
  });

  it("the card reads a live item as a suggestion, with a prefixed id so it never clashes with a results card", () => {
    const s = asSuggestion(item({ id: "abc", begin: 2, end: 5, text: "xyz", replacements: ["a", "b"] }), "u-");
    expect(s.id).toBe("u-abc");
    expect(s.replacement).toBe("a");
    expect(s.span).toEqual({ start: 2, end: 5, line: 0, col: 0 });
    expect(asSuggestion(item({ begin: 0, end: 1 })).replacement).toBeNull();
  });
});

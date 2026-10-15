import { readFileSync } from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CheckParagraphsResponse, LiveSuggestion, TierHealth, WordParagraph, WordSuggestion } from "@researchly/contract";
import { CATEGORY_TOKENS } from "@researchly/design-tokens";
import { checkParagraphs, isCurrentReply, liveHeading, partialReason, takeBatch } from "@/lib/live-check";
import { looksLikeCheckParagraphsResponse } from "@/lib/engine";
import {
  annotationColor,
  appliedInPlace,
  changedParagraphs,
  codePointToUtf16,
  critiqueRange,
  dismissalKey,
  goneKeys,
  isLiveCheckable,
  liveLocation,
  liveToWordSuggestion,
  mergeCards,
  nearestHeadings,
  occurrenceAt,
  paragraphKey,
  paragraphUnderlines,
  pickUnderlines,
  popupSuggestions,
  POPUP_RESOURCES,
  shouldUnderline,
  signature,
  snapshotOf,
  utf16ToCodePoint,
  type LiveEntry,
  type Underline,
} from "@/lib/word/live";
import { critiqueOf } from "@/lib/word/annotations";
import { sugg } from "./helpers";

/** Synthetic sentences written for these tests. */
const P = (text: string, style = "Normal", kind: "body" | "table" = "body"): WordParagraph => ({ text, style, kind });

function live(id: string, text: string, needle: string, extra: Partial<LiveSuggestion> = {}): LiveSuggestion {
  const begin = text.indexOf(needle);
  return {
    id,
    rule_id: "S010",
    rule_name: "Repeated word",
    category: "correction",
    critical: true,
    tier: "spelling",
    begin,
    end: begin + needle.length,
    text: needle,
    section: "methods",
    message: "A word is repeated.",
    plain: "The same word twice in a row.",
    why: "w",
    source: "s",
    learn_ref: null,
    replacements: ["the"],
    fix_safety: "safe",
    ...extra,
  };
}

describe("colours and the popup (from the tokens and the manifest)", () => {
  it("maps each category to its Word colour scheme, from the design tokens", () => {
    expect(annotationColor("correction")).toBe("Red");
    expect(annotationColor("improvement")).toBe("Blue");
    expect(annotationColor("convention")).toBe("Green");
    expect(annotationColor("preference")).toBe("Lavender");
    for (const c of ["correction", "improvement", "convention", "preference"] as const) {
      expect(annotationColor(c)).toBe(CATEGORY_TOKENS[c].wordAnnotationColor);
    }
  });

  it("offers revisions in the popup only when they are safe to take unread, never a removal, at most three", () => {
    expect(popupSuggestions({ fix_safety: "safe", replacements: ["To"] })).toEqual(["To"]);
    expect(popupSuggestions({ fix_safety: "review", replacements: ["To"] })).toEqual([]);
    expect(popupSuggestions({ fix_safety: "safe", replacements: [""] })).toEqual([]);
    expect(popupSuggestions({ fix_safety: "safe", replacements: ["a", "b", "a", "c", "d"] })).toEqual(["a", "b", "c"]);
    expect(popupSuggestions({ fix_safety: "safe" })).toEqual([]);
  });

  it("builds Word's critique: colour, range and (with WordApi 1.8) the manifest's resource ids", () => {
    const u: Underline = { id: "x", category: "convention", begin: 4, end: 9, suggestions: [] };
    expect(critiqueOf(u, false)).toEqual({ colorScheme: "Green", start: 4, length: 5 });
    expect(critiqueOf(u, true).popupOptions).toEqual({
      brandingTextResourceId: "RL.CritiqueBrand",
      titleResourceId: "RL.CritiqueConvention",
      subtitleResourceId: "RL.CritiqueSubtitle",
      suggestions: [],
    });
    // Word for Mac drops a manifest with a resource id over 32 characters.
    for (const id of [POPUP_RESOURCES.branding, POPUP_RESOURCES.subtitle, ...Object.values(POPUP_RESOURCES.title)]) {
      expect(id.length).toBeLessThanOrEqual(32);
    }
  });

  it("finds every popup resource in the hosted manifest, in plain words, no vendor names", () => {
    const xml = readFileSync(path.resolve(__dirname, "../../../word-addin/manifest.hosted.xml"), "utf8");
    const value = (id: string) => new RegExp(`<bt:String id="${id.replace(/\./g, "\\.")}" DefaultValue="([^"]*)"`).exec(xml)?.[1];
    expect(value(POPUP_RESOURCES.branding)).toBe("Researchly");
    expect(value(POPUP_RESOURCES.subtitle)).toBe("Why and source: in the Researchly pane");
    expect(value(POPUP_RESOURCES.title.correction)).toBe("Correction");
    expect(value(POPUP_RESOURCES.title.improvement)).toBe("Improvement");
    expect(value(POPUP_RESOURCES.title.convention)).toBe("Convention");
    expect(value(POPUP_RESOURCES.title.preference)).toBe("Preference");
  });

  it("underlines preferences only when they are shown", () => {
    expect(shouldUnderline("preference", false)).toBe(false);
    expect(shouldUnderline("preference", true)).toBe(true);
    expect(shouldUnderline("convention", false)).toBe(true);
  });
});

describe("UTF-16 offsets to Word's start and length", () => {
  const text = "R₀ 🦟 the the end"; // a mosquito is two UTF-16 units, one code point

  it("maps begin/end to start/length when the text there is the flagged words", () => {
    const b = text.indexOf("the the");
    expect(critiqueRange(text, b, b + 7, "the the")).toEqual({ start: b, length: 7 });
    expect(critiqueRange(text, b, b + 7, "different")).toBeNull();
  });

  it("refuses ranges that are empty, reversed, out of range or split a character", () => {
    const mosquito = text.indexOf("🦟");
    expect(critiqueRange(text, 3, 3)).toBeNull();
    expect(critiqueRange(text, 5, 3)).toBeNull();
    expect(critiqueRange(text, 0, text.length + 1)).toBeNull();
    expect(critiqueRange(text, mosquito + 1, mosquito + 2)).toBeNull();
    expect(critiqueRange(text, mosquito, mosquito + 2)).toEqual({ start: mosquito, length: 2 });
  });

  it("converts between UTF-16 and code points both ways", () => {
    const b16 = text.indexOf("the");
    const cp = utf16ToCodePoint(text, b16);
    expect(cp).toBe(b16 - 1);
    expect(codePointToUtf16(text, cp!)).toBe(b16);
    expect(utf16ToCodePoint(text, text.indexOf("🦟") + 1)).toBeNull();
    expect(codePointToUtf16(text, 999)).toBeNull();
  });

  it("knows which copy of repeated words it is (Word's non-overlapping search)", () => {
    const t = "the the the the";
    expect(occurrenceAt(t, "the the", 0)).toBe(0);
    expect(occurrenceAt(t, "the the", 8)).toBe(1);
    expect(occurrenceAt(t, "the the", 4)).toBe(-1); // overlapping: Word's search cannot reach it whole
  });

  it("locates a live suggestion the way the full check does, with UTF-16 kept", () => {
    const loc = liveLocation(text, 2, live("a", text, "the the"));
    expect(loc).toEqual({
      paragraph: 2,
      start: text.indexOf("the the") - 1,
      end: text.indexOf("the the") + 6,
      snippet: "the the",
      occurrence: 0,
      exact: true,
      begin16: text.indexOf("the the"),
      end16: text.indexOf("the the") + 7,
    });
    expect(liveLocation(text, 2, { begin: 0, end: 3, text: "nope" })).toBeNull();
  });

  it("turns a live suggestion into a card, the first revision as the card's", () => {
    const card = liveToWordSuggestion(live("a", text, "the the"), 1, text)!;
    expect(card.replacement).toBe("the");
    expect(card.location.paragraph).toBe(1);
    expect(card.critical).toBe(true);
    expect(liveToWordSuggestion(live("b", text, "the the", { replacements: [] }), 1, text)!.replacement).toBeNull();
    expect(liveToWordSuggestion({ ...live("c", text, "the the"), text: "else" }, 1, text)).toBeNull();
  });
});

describe("paragraphs: keys, the nearest heading, what changed", () => {
  it("keys a paragraph by Word's id where there is one, stripped to the contract's alphabet", () => {
    expect(paragraphKey("{8A0C1F2E-0001}", 4)).toBe("u8A0C1F2E-0001");
    expect(paragraphKey(null, 4)).toBe("i4");
    expect(paragraphKey("{}", 2)).toBe("i2");
    expect(paragraphKey("x".repeat(80), 0)).toHaveLength(64);
  });

  it("walks back to the closest heading-styled paragraph above (not itself, never a table cell)", () => {
    const paras = [P("Body before any heading."), P("Methods", "Heading1"), P("First."), P("Region", "Heading1", "table"), P("Results", "Heading 2"), P("Second.")];
    expect(nearestHeadings(paras)).toEqual(["", "", "Methods", "Methods", "Methods", "Results"]);
  });

  it("checks only body prose live: not headings, tables or blank lines", () => {
    expect(isLiveCheckable(P("A sentence."))).toBe(true);
    expect(isLiveCheckable(P("Methods", "Heading1"))).toBe(false);
    expect(isLiveCheckable(P("A cell.", "Normal", "table"))).toBe(false);
    expect(isLiveCheckable(P("   "))).toBe(false);
  });

  it("finds the paragraphs whose text, style or section changed, and those that went away", () => {
    const before = snapshotOf([P("Methods", "Heading1"), P("One."), P("Two.")], ["a", "b", "c"]);
    const known = new Map(before.map((p) => [p.key, signature(p)]));
    expect(changedParagraphs(before, known)).toEqual([]);
    const typed = snapshotOf([P("Methods", "Heading1"), P("One, edited."), P("Two.")], ["a", "b", "c"]);
    expect(changedParagraphs(typed, known).map((p) => p.key)).toEqual(["b"]);
    // Renaming the heading moves both paragraphs into another section: both are checked again.
    const renamed = snapshotOf([P("Discussion", "Heading1"), P("One."), P("Two.")], ["a", "b", "c"]);
    expect(changedParagraphs(renamed, known).map((p) => p.key)).toEqual(["a", "b", "c"]);
    expect(goneKeys(snapshotOf([P("One.")], ["b"]), ["a", "b", "c"])).toEqual(["a", "c"]);
  });
});

describe("which findings become underlines", () => {
  const text = "In order to fit the the model, we clearly proved it.";
  const card = (id: string, needle: string, extra: Partial<WordSuggestion> = {}): WordSuggestion => {
    const start = text.indexOf(needle);
    return {
      ...sugg(id, start, start + needle.length),
      text: needle,
      location: { paragraph: 0, start, end: start + needle.length, snippet: needle, occurrence: 0, exact: true },
      ...extra,
    };
  };

  it("never overlaps: the more serious category wins, then the shorter range", () => {
    const a: Underline = { id: "a", category: "improvement", begin: 0, end: 10, suggestions: [] };
    const b: Underline = { id: "b", category: "correction", begin: 5, end: 8, suggestions: [] };
    const c: Underline = { id: "c", category: "convention", begin: 12, end: 15, suggestions: [] };
    expect(pickUnderlines([a, b, c]).map((u) => u.id)).toEqual(["b", "c"]);
  });

  it("leaves out document-wide findings, hidden preferences, dismissed ones and ranges that do not fit", () => {
    const list = [
      card("w", "In order to", { category: "improvement", replacement: "To", fix_safety: "safe" }),
      card("r", "the the", { category: "correction", replacement: "the", fix_safety: "review" }),
      card("doc", "model", { rule_id: "W211", category: "convention" }),
      card("pref", "we", { category: "preference" }),
      card("gone", "clearly proved", { category: "convention", location: { paragraph: 0, start: 0, end: 3, snippet: "x", occurrence: 0, exact: true } }),
      card("dis", "clearly", { category: "convention" }),
    ];
    const out = paragraphUnderlines(list, text, { showPreferences: false, scopes: null, dismissed: (s) => s.id === "dis" });
    expect(out.map((u) => [u.id, u.suggestions])).toEqual([
      ["w", ["To"]],
      ["r", []], // a revision to read first: applied from the pane, not the popup
    ]);
    expect(paragraphUnderlines(list, text, { showPreferences: true, scopes: null }).map((u) => u.id)).toContain("pref");
  });
});

describe("the pane's list and stale replies", () => {
  const full = [
    { ...sugg("f1", 0, 3), location: { paragraph: 1, start: 0, end: 3, snippet: "abc", occurrence: 0, exact: true } },
    { ...sugg("f2", 0, 3), location: { paragraph: 2, start: 0, end: 3, snippet: "abc", occurrence: 0, exact: true } },
    { ...sugg("doc", 0, 3), rule_id: "W211", location: { paragraph: 1, start: 5, end: 8, snippet: "abc", occurrence: 0, exact: true } },
  ];
  const keys = ["a", "b", "c"];

  it("swaps a paragraph checked live for its live cards, keeping document-wide findings", () => {
    const liveCard = { ...sugg("l1", 0, 3), location: { paragraph: 1, start: 2, end: 5, snippet: "abc", occurrence: 0, exact: true } };
    const entries = new Map<string, LiveEntry>([["b", { key: "b", index: 1, text: "t", cards: [liveCard] }]]);
    expect(mergeCards(full, keys, entries, null).map((s) => s.id)).toEqual(["l1", "doc", "f2"]);
    expect(mergeCards(full, keys, new Map(), null).map((s) => s.id)).toEqual(["f1", "doc", "f2"]);
    expect(mergeCards(null, [], entries, null).map((s) => s.id)).toEqual(["l1"]);
  });

  it("drops a reply for an older revision, or one that a reset overtook", () => {
    expect(isCurrentReply({ revision: 4 }, { revision: 4, generation: 2 }, { generation: 2 })).toBe(true);
    expect(isCurrentReply({ revision: 3 }, { revision: 4, generation: 2 }, { generation: 2 })).toBe(false);
    expect(isCurrentReply({ revision: 4 }, { revision: 4, generation: 1 }, { generation: 2 })).toBe(false);
  });

  it("keeps a dismissal for the same words in the same paragraph, whatever their offsets", () => {
    expect(dismissalKey("b", { rule_id: "S010", text: "the the" })).toBe(dismissalKey("b", { rule_id: "S010", text: "the the" }));
    expect(dismissalKey("b", { rule_id: "S010", text: "the the" })).not.toBe(dismissalKey("c", { rule_id: "S010", text: "the the" }));
  });

  it("recognises a revision Word already made", () => {
    expect(appliedInPlace("fit the the model", "fit the model", 4, 11, "the")).toBe(true);
    expect(appliedInPlace("fit the the model", "fit the the model", 4, 11, "the")).toBe(false);
  });
});

describe("the live check's batches and request", () => {
  it("takes at most 50 paragraphs and 20,000 characters, in order; a paragraph too long is never sent", () => {
    const many = Array.from({ length: 60 }, (_, i) => ({ id: `p${i}`, text: "x" }));
    const r = takeBatch(many);
    expect(r.batch).toHaveLength(50);
    expect(r.rest).toHaveLength(10);
    const big = [{ text: "a".repeat(15_000) }, { text: "b".repeat(6_000) }, { text: "c".repeat(20_001) }, { text: "d" }];
    const s = takeBatch(big);
    expect(s.batch.map((p) => p.text[0])).toEqual(["a"]);
    expect(s.rest.map((p) => p.text[0])).toEqual(["b", "d"]);
    expect(s.tooLong.map((p) => p.text[0])).toEqual(["c"]);
  });

  it("trims a heading to the contract's 300 characters", () => {
    expect(liveHeading("  Methods ")).toBe("Methods");
    expect(liveHeading("h".repeat(400))).toHaveLength(300);
    expect(liveHeading(null)).toBe("");
  });

  it("says which part of the checking was off, in plain words (the learned tier's absence is not a gap)", () => {
    const t = (tier: string, label: string, ok: boolean): TierHealth => ({ tier, label, ok, state: ok ? "ready" : "error", detail: "", remedy: "" });
    expect(partialReason([t("grammar", "Grammar", false), t("gec", "Learned corrections", false)])).toBe("Grammar was not checked");
    expect(partialReason([t("grammar", "Grammar", false), t("spelling", "Spelling", false)])).toBe("Grammar and Spelling were not checked");
    expect(partialReason([t("grammar", "Grammar", true)])).toBe("");
  });

  afterEach(() => vi.unstubAllGlobals());

  it("posts to /v1/check-paragraphs with no cookies, and validates the reply's shape", async () => {
    const reply: CheckParagraphsResponse = {
      schema_version: "1",
      revision: 7,
      paragraphs: [{ id: "u1", section: "methods", suggestions: [] }],
      state: "ok",
      health: [],
      hidden_preferences: 0,
      signed_in: false,
      elapsed_ms: 5,
    };
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(reply), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const r = await checkParagraphs(
      { revision: 7, paragraphs: [{ id: "u1", text: "A sentence.", style: "Normal", heading: "Methods" }] },
      { engineUrl: "http://engine.test" },
    );
    expect(r).toEqual({ ok: true, data: reply });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://engine.test/v1/check-paragraphs");
    expect(init.credentials).toBe("omit");
    expect(JSON.parse(String(init.body)).paragraphs[0].heading).toBe("Methods");
    expect(looksLikeCheckParagraphsResponse({ ...reply, paragraphs: [{ id: "u1", suggestions: [{ id: "s", begin: -1, end: 2, category: "x", text: "" }] }] })).toBe(false);
  });
});

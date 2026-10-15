import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CheckParagraphsRequest } from "@researchly/contract";
import { UnderlineTeaser } from "@/components/LiveEditor";
import { StatusMark } from "@/components/StatusMark";
import { INITIAL_STATUS } from "@/lib/check-state";
import { checkParagraphs, LIVE_TIMEOUT_MS, looksLikeCheckParagraphsResponse } from "@/lib/live-check";
import type { LiveItem } from "@/lib/live-paragraphs";

const ITEM: LiveItem = {
  id: "a1b2c3d4e5f60718",
  rule_id: "G110",
  rule_name: "Repeated word",
  category: "correction",
  begin: 4,
  end: 11,
  text: "the the",
  message: "The word ‘the’ is repeated.",
  plain: "Read it aloud.",
  why: "w",
  source: "Researchly grammar notes",
  learn_ref: null,
  section: "discussion",
  tier: "grammar",
  fix_safety: "review",
  replacements: ["the"],
};

const teaser = (item: LiveItem, caret = false) =>
  renderToStaticMarkup(
    <UnderlineTeaser id="t1" item={item} caret={caret} place={{ left: 10, top: 20, above: false }} onApply={() => undefined} onOpen={() => undefined} />,
  );

describe("the teaser", () => {
  it("says the category in words with its icon, what was noticed and the revision (your call)", () => {
    const html = teaser(ITEM);
    expect(html).toContain('id="t1"');
    expect(html).toContain("badge-correction");
    expect(html).toContain("<svg");
    expect(html).toContain("Correction");
    expect(html).toContain("The word ‘the’ is repeated.");
    expect(html).toContain("Suggested revision (your call):");
    expect(html).toContain("<q>the</q>");
    expect(html).toContain("Use it");
    expect(html).toContain("Why?");
  });

  it("never shows a rule code or a tier name", () => {
    const html = teaser(ITEM);
    expect(html).not.toContain("G110");
    expect(html).not.toContain(">grammar<");
    expect(html).not.toMatch(/\bgrammar\b(?![^<]*>)/);
  });

  it("no revision: no revision line and no Use it; a removal says so", () => {
    const none = teaser({ ...ITEM, replacements: [] });
    expect(none).not.toContain("Suggested revision");
    expect(none).not.toContain("Use it");
    const removal = teaser({ ...ITEM, replacements: [""] });
    expect(removal).toContain("<em>remove this</em>");
    expect(removal).toContain(">Remove<");
  });

  it("names the shortcut to the card only when shown for the caret", () => {
    expect(teaser(ITEM)).not.toContain("Ctrl + .");
    expect(teaser(ITEM, true)).toContain("Ctrl + . for the card");
  });

  it("a Convention is never worded as an error", () => {
    const html = teaser({ ...ITEM, category: "convention", message: "In research writing ‘data’ is usually plural." });
    expect(html).toContain("Convention");
    expect(html).not.toMatch(/error|wrong|mistake/i);
  });
});

describe("the state beside the editor", () => {
  it("is not a live region there (the editor announces rarely itself); it is elsewhere by default", () => {
    const quiet = renderToStaticMarkup(<StatusMark status={{ ...INITIAL_STATUS, state: "issues", count: 3 }} announce={false} />);
    expect(quiet).not.toContain('role="status"');
    expect(quiet).not.toContain("aria-live");
    expect(quiet).toContain("3 suggestions");
    const loud = renderToStaticMarkup(<StatusMark status={{ ...INITIAL_STATUS, state: "issues", count: 3 }} />);
    expect(loud).toContain('role="status"');
  });
});

describe("the live check's request", () => {
  afterEach(() => vi.unstubAllGlobals());

  const req: CheckParagraphsRequest = {
    revision: 4,
    paragraphs: [{ id: "kabc", text: "In order to see the the end.", heading: "Discussion", style: "" }],
    options: { show_preferences: true, document_type: "auto", review: false, narrative: false },
  };
  const reply = {
    schema_version: "1",
    revision: 4,
    paragraphs: [{ id: "kabc", section: "discussion", suggestions: [{ ...ITEM, critical: true, begin: 16, end: 23 }] }],
    state: "ok",
    health: [],
    hidden_preferences: 0,
    signed_in: false,
    elapsed_ms: 3,
  };

  it("POSTs the paragraphs to /v1/check-paragraphs with no cookies and no referrer", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(reply), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const r = await checkParagraphs(req, { engineUrl: "http://engine.test" });
    expect(r.ok).toBe(true);
    const [url, init] = fetchMock.mock.calls[0]! as unknown as [string, RequestInit];
    expect(url).toBe("http://engine.test/v1/check-paragraphs");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("omit");
    expect(init.referrerPolicy).toBe("no-referrer");
    expect(JSON.parse(init.body as string)).toEqual(req);
  });

  it("an engine failure is a result, not a throw", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    const r = await checkParagraphs(req, { engineUrl: "http://engine.test" });
    expect(r.ok).toBe(false);
  });

  it("refuses an answer it cannot draw safely", () => {
    expect(looksLikeCheckParagraphsResponse(reply)).toBe(true);
    expect(looksLikeCheckParagraphsResponse({ ...reply, revision: -1 })).toBe(false);
    const bad = { ...reply, paragraphs: [{ id: "kabc", suggestions: [{ ...ITEM, begin: 9, end: 2 }] }] };
    expect(looksLikeCheckParagraphsResponse(bad)).toBe(false);
    expect(looksLikeCheckParagraphsResponse(null)).toBe(false);
  });

  it("gives up long before a full check would, far above the engine's budget", () => {
    expect(LIVE_TIMEOUT_MS).toBeGreaterThanOrEqual(5_000);
    expect(LIVE_TIMEOUT_MS).toBeLessThanOrEqual(30_000);
  });
});

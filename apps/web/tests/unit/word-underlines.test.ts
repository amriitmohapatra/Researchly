import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CheckParagraphsRequest, CheckParagraphsResponse, LiveSuggestion, WordSuggestion } from "@researchly/contract";
import type { CheckEvent } from "@/lib/check-state";
import type { CheckResult } from "@/lib/engine";
import { networkError } from "@/lib/errors";
import { UnderlineController, type UnderlineEvents } from "@/lib/word/underlines";
import { snapshotOf } from "@/lib/word/live";
import type { OfficeApi } from "@/lib/word/office";
import { installFakeOffice, type FakeWordConfig, type FakeWordState } from "../../e2e/fake-office";

/** Synthetic paragraphs written for these tests. */
const DOC = [
  { text: "Methods", styleBuiltIn: "Heading1" },
  { text: "In order to fit it, the the model ran.", styleBuiltIn: "Normal" },
  { text: "Discussion", styleBuiltIn: "Heading1" },
  { text: "The effect was clearly proven here.", styleBuiltIn: "Normal" },
];

/** The engine, faked: "the the" is a Correction with a safe revision, "In order to" an Improvement, "clearly proven" a Convention. */
function suggestionsFor(pid: string, text: string): LiveSuggestion[] {
  const out: LiveSuggestion[] = [];
  const add = (needle: string, rule: string, category: LiveSuggestion["category"], replacements: string[]) => {
    const begin = text.indexOf(needle);
    if (begin < 0) return;
    out.push({
      id: `${rule}-${pid}-${begin}`,
      rule_id: rule,
      rule_name: rule,
      category,
      critical: category === "correction",
      tier: "craft",
      begin,
      end: begin + needle.length,
      text: needle,
      section: "methods",
      message: "m",
      plain: "p",
      why: "w",
      source: "s",
      learn_ref: null,
      replacements,
      fix_safety: "safe",
    });
  };
  add("the the", "S010", "correction", ["the"]);
  add("In order to", "C120", "improvement", ["To"]);
  add("clearly proven", "C201", "convention", []);
  return out;
}

function reply(req: CheckParagraphsRequest, extra: Partial<CheckParagraphsResponse> = {}): CheckResult<CheckParagraphsResponse> {
  return {
    ok: true,
    data: {
      schema_version: "1",
      revision: req.revision,
      paragraphs: req.paragraphs.map((p) => ({ id: p.id, section: "methods", suggestions: suggestionsFor(p.id, p.text) })),
      state: "ok",
      health: [],
      hidden_preferences: 0,
      signed_in: false,
      elapsed_ms: 3,
      ...extra,
    },
  };
}

interface Harness {
  c: UnderlineController;
  state: FakeWordState;
  target: Record<string, (...args: unknown[]) => void>;
  sent: CheckParagraphsRequest[];
  events: CheckEvent[];
  reveals: [string, string][];
  unavailable: string[];
  accepts: [string, string][];
  rejects: string[];
  send: ReturnType<typeof vi.fn>;
}

function setup(config: Partial<FakeWordConfig> = {}, send?: (req: CheckParagraphsRequest) => Promise<CheckResult<CheckParagraphsResponse>>, probe = () => Promise.resolve(true)): Harness {
  const target: Record<string, unknown> = {};
  const state = installFakeOffice(target, { paragraphs: DOC, api16: true, api17: true, api18: true, ...config });
  target.Word = target.__fakeWordNamespace;
  const h: Partial<Harness> = { sent: [], events: [], reveals: [], unavailable: [], accepts: [], rejects: [] };
  const sendFn = vi.fn(async (req: CheckParagraphsRequest) => {
    h.sent!.push(req);
    return send ? send(req) : reply(req);
  });
  const events: UnderlineEvents = {
    onEntries: () => undefined,
    onUnderlined: () => undefined,
    onState: (e) => h.events!.push(e),
    onUnavailable: (r) => h.unavailable!.push(r),
    onReveal: (id, how) => h.reveals!.push([id, how]),
    onPopupAccept: (id, r) => h.accepts!.push([id, r]),
    onPopupReject: (id) => h.rejects!.push(id),
  };
  const c = new UnderlineController({
    api: target as unknown as OfficeApi,
    send: (req) => sendFn(req),
    probe,
    events,
    dismissed: () => false,
  });
  return { ...(h as Harness), c, state, target: target as Harness["target"], send: sendFn };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

const settle = () => vi.advanceTimersByTimeAsync(10);

describe("live underlines in Word (fake Office, fake clock)", () => {
  it("on opening, checks every body paragraph once, under its heading, and draws coloured underlines with the popup", async () => {
    const t = setup();
    await t.c.start({ enabled: true, live: true });
    await settle();
    expect(t.sent).toHaveLength(1);
    expect(t.sent[0]!.paragraphs.map((p) => [p.text.slice(0, 8), p.heading])).toEqual([
      ["In order", "Methods"],
      ["The effe", "Discussion"],
    ]);
    expect(t.sent[0]!.options).toMatchObject({ show_preferences: false, document_type: "auto", review: false, narrative: false });
    expect(t.state.annotations.map((a) => [a.text, a.colorScheme, a.popup?.title, a.popup?.suggestions])).toEqual([
      ["In order to", "Blue", "RL.CritiqueImprovement", ["To"]],
      ["the the", "Red", "RL.CritiqueCorrection", ["the"]],
      ["clearly proven", "Green", "RL.CritiqueConvention", []],
    ]);
    expect(t.state.annotations.every((a) => a.popup?.branding === "RL.CritiqueBrand" && a.popup.subtitle === "RL.CritiqueSubtitle")).toBe(true);
    expect(t.events.map((e) => e.type)).toEqual(["edit", "reply"]);
  });

  it("after an edit, waits for a 1.5 s pause, then sends only the changed paragraph and replaces its underlines", async () => {
    const t = setup();
    await t.c.start({ enabled: true, live: true });
    await settle();
    t.target.__fakeWordType!(3, "The effect was large.");
    await vi.advanceTimersByTimeAsync(1_000);
    expect(t.sent).toHaveLength(1); // still typing
    t.target.__fakeWordType!(3, "The effect was large, the the end.");
    await vi.advanceTimersByTimeAsync(1_400);
    expect(t.sent).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(200);
    expect(t.sent).toHaveLength(2);
    expect(t.sent[1]!.paragraphs.map((p) => p.text)).toEqual(["The effect was large, the the end."]);
    expect(t.state.annotations.map((a) => a.text)).toEqual(["In order to", "the the", "the the"]);
    expect(t.state.annotations.some((a) => a.text === "clearly proven")).toBe(false);
  });

  it("drops a reply whose paragraph changed while it was in flight, and checks the new text", async () => {
    let release: (() => void) | null = null;
    let calls = 0;
    const t = setup({}, (req) => {
      calls += 1;
      if (calls === 2) return new Promise((r) => (release = () => r(reply(req))));
      return Promise.resolve(reply(req));
    });
    await t.c.start({ enabled: true, live: true });
    await settle();
    t.target.__fakeWordType!(1, "So the the model ran.");
    await vi.advanceTimersByTimeAsync(1_600); // request 2 is in flight
    t.target.__fakeWordType!(1, "Then the model ran cleanly.");
    release!();
    await settle();
    // Nothing from the stale reply was drawn in paragraph 1.
    expect(t.state.annotations.filter((a) => a.paragraph === t.state.paragraphs[1]!.uid)).toEqual([]);
    await vi.advanceTimersByTimeAsync(1_600);
    expect(t.sent.at(-1)!.paragraphs.map((p) => p.text)).toEqual(["Then the model ran cleanly."]);
    expect(t.state.annotations.map((a) => a.text)).toEqual(["clearly proven"]);
  });

  it("never sends a second request while one is in flight", async () => {
    let pending: ((v: CheckResult<CheckParagraphsResponse>) => void)[] = [];
    const t = setup({}, (req) => new Promise((r) => pending.push(() => r(reply(req)))));
    await t.c.start({ enabled: true, live: true });
    await settle();
    expect(t.sent).toHaveLength(1);
    t.target.__fakeWordType!(1, "Edited while checking.");
    await vi.advanceTimersByTimeAsync(3_000);
    expect(t.sent).toHaveLength(1);
    pending[0]!(undefined as never);
    pending = pending.slice(1);
    await vi.advanceTimersByTimeAsync(1_600);
    expect(t.sent).toHaveLength(2);
  });

  it("goes offline when the engine fails, retries after 2 s, and comes back", async () => {
    let fail = true;
    const t = setup({}, (req) => Promise.resolve(fail ? { ok: false, error: networkError(false) } : reply(req)));
    await t.c.start({ enabled: true, live: true });
    await settle();
    expect(t.events.map((e) => e.type)).toEqual(["edit", "failure"]);
    fail = false;
    await vi.advanceTimersByTimeAsync(2_000);
    await settle();
    expect(t.events.map((e) => e.type)).toEqual(["edit", "failure", "retry", "edit", "reply"]);
    expect(t.state.annotations).toHaveLength(3);
  });

  it("a Word without Microsoft 365 (insertion refused): underlines off for the session, said once", async () => {
    const t = setup({ failures: { annotations: "insert" } });
    await t.c.start({ enabled: true, live: true });
    await settle();
    expect(t.unavailable).toEqual(["refused"]);
    expect(t.state.annotations).toEqual([]);
    t.target.__fakeWordType!(1, "More text.");
    await vi.advanceTimersByTimeAsync(2_000);
    expect(t.sent).toHaveLength(1); // no more live checks
    expect(t.c.isOn).toBe(false);
  });

  it("an older Word (no WordApi 1.7): nothing is drawn or sent", async () => {
    const t = setup({ api17: false, api18: false });
    expect(await t.c.start({ enabled: true, live: true })).toBe("unsupported");
    await vi.advanceTimersByTimeAsync(2_000);
    expect(t.unavailable).toEqual(["unsupported"]);
    expect(t.sent).toEqual([]);
  });

  it("WordApi 1.7 without 1.8: underlines without the popup", async () => {
    const t = setup({ api18: false });
    await t.c.start({ enabled: true, live: true });
    await settle();
    expect(t.state.annotations).toHaveLength(3);
    expect(t.state.annotations.every((a) => a.popup === null)).toBe(true);
    expect(t.state.failedAnnotationInserts).toBe(0);
  });

  it("a popup Word refuses (its strings missing from the manifest): drawn again without it", async () => {
    const t = setup({ failures: { annotations: "popup" } });
    await t.c.start({ enabled: true, live: true });
    await settle();
    expect(t.unavailable).toEqual([]);
    expect(t.state.annotations).toHaveLength(3);
    expect(t.state.annotations.every((a) => a.popup === null)).toBe(true);
  });

  it("without paragraph ids (WordApi 1.7 but not 1.6), edits are found from the selection moving", async () => {
    const t = setup({ api16: false, api17: true, api18: true });
    // 1.7 implies 1.6 in Word's numbering; the fake can still withhold the events to test the fallback path.
    await t.c.start({ enabled: true, live: true });
    await settle();
    t.target.__fakeWordType!(3, "The effect was the the same.");
    await vi.advanceTimersByTimeAsync(1_600);
    expect(t.sent.at(-1)!.paragraphs.map((p) => p.text)).toEqual(["The effect was the the same."]);
  });

  it("an underline clicked or hovered reveals its suggestion; the popup's Accept and Reject are passed on", async () => {
    const t = setup();
    await t.c.start({ enabled: true, live: true });
    await settle();
    const [improve, correct] = t.state.annotations;
    t.target.__fakeWordClick!(correct!.id);
    t.target.__fakeWordHover!(improve!.id);
    await settle();
    expect(t.reveals).toEqual([
      [`S010-u${t.state.paragraphs[1]!.uid!.replace(/[{}]/g, "")}-${DOC[1]!.text.indexOf("the the")}`, "click"],
      [`C120-u${t.state.paragraphs[1]!.uid!.replace(/[{}]/g, "")}-0`, "hover"],
    ]);
    t.target.__fakeWordPopup!(improve!.id, "Accept", "To");
    t.target.__fakeWordPopup!(correct!.id, "Reject");
    await settle();
    expect(t.accepts.map(([, r]) => r)).toEqual(["To"]);
    expect(t.rejects).toHaveLength(1);
    expect(t.state.annotations.find((a) => a.id === correct!.id)).toBeUndefined();
  });

  it("switching off removes our underlines and pauses; on again checks everything", async () => {
    const t = setup();
    await t.c.start({ enabled: true, live: true });
    await settle();
    t.c.setEnabled(false);
    await settle();
    expect(t.state.annotations).toEqual([]);
    expect(t.events.at(-1)).toEqual({ type: "pause" });
    t.c.setEnabled(true);
    await settle();
    expect(t.sent).toHaveLength(2);
    expect(t.state.annotations).toHaveLength(3);
  });

  it("the full check: sentence-level findings only, live results give way", async () => {
    const t = setup();
    await t.c.start({ enabled: true, live: false });
    await settle();
    expect(t.sent).toEqual([]); // this engine has no live check: underlines come from Check document
    const paras = DOC.map((p) => ({ text: p.text, style: p.styleBuiltIn, kind: "body" as const }));
    const snap = snapshotOf(paras, t.state.paragraphs.map((p) => `u${p.uid!.replace(/[{}]/g, "")}`));
    const at = DOC[1]!.text.indexOf("the the");
    const base = { category: "correction", tier: "spelling", section: "methods", message: "m", plain: "p", why: "w", source: "s", fix_safety: "safe", confidence: 1 } as const;
    const sentence: WordSuggestion = {
      ...base,
      id: "full-1",
      rule_id: "S010",
      rule_name: "Repeated word",
      replacement: "the",
      text: "the the",
      span: { start: at, end: at + 7, line: 1, col: at + 1 },
      location: { paragraph: 1, start: at, end: at + 7, snippet: "the the", occurrence: 0, exact: true, begin16: at, end16: at + 7 },
    };
    const docWide: WordSuggestion = { ...sentence, id: "full-2", rule_id: "W211", category: "convention" };
    await t.c.paintFullCheck(snap, [sentence, docWide]);
    expect(t.state.annotations.map((a) => [a.text, a.colorScheme])).toEqual([["the the", "Red"]]);
    expect(t.c.annotationFor("full-1")).toBe(t.state.annotations[0]!.id);
    expect(t.c.annotationFor("full-2")).toBeNull();
  });
});

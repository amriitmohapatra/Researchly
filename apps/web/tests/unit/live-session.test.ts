import { describe, expect, it } from "vitest";
import type { CheckParagraphsRequest, CheckParagraphsResponse, LiveSuggestion, Suggestion } from "@researchly/contract";
import type { CheckResult } from "@/lib/engine";
import { networkError } from "@/lib/errors";
import { splitParagraphs } from "@/lib/live-paragraphs";
import { LIVE_PAUSE_MS, LiveSession, partialReason, type LiveClock } from "@/lib/live-session";

/** A clock the test moves by hand. */
function fakeClock() {
  let now = 0;
  let seq = 0;
  const timers = new Map<number, { at: number; fn: () => void }>();
  const clock: LiveClock = {
    now: () => now,
    setTimeout: (fn, ms) => {
      timers.set(++seq, { at: now + ms, fn });
      return seq;
    },
    clearTimeout: (id) => void timers.delete(id as number),
  };
  const advance = async (ms: number) => {
    const end = now + ms;
    for (;;) {
      const due = [...timers.entries()].filter(([, t]) => t.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
      if (!due) break;
      timers.delete(due[0]);
      now = due[1].at;
      due[1].fn();
      await flush();
    }
    now = end;
    await flush();
  };
  return { clock, advance };
}

const flush = async () => {
  for (let i = 0; i < 5; i++) await Promise.resolve();
};

/** Finds "the the" in any paragraph. */
function find(text: string): LiveSuggestion[] {
  const at = text.indexOf("the the");
  if (at < 0) return [];
  return [
    {
      id: `rep${at}`,
      rule_id: "G110",
      rule_name: "Repeated word",
      category: "correction",
      critical: true,
      tier: "craft",
      begin: at,
      end: at + 7,
      text: "the the",
      section: "discussion",
      message: "The word ‘the’ is repeated.",
      plain: "",
      why: "",
      source: "s",
      learn_ref: null,
      replacements: ["the"],
      fix_safety: "review",
    },
  ];
}

function answer(req: CheckParagraphsRequest, over: Partial<CheckParagraphsResponse> = {}): CheckResult<CheckParagraphsResponse> {
  return {
    ok: true,
    data: {
      schema_version: "1",
      revision: req.revision,
      paragraphs: req.paragraphs.map((p) => ({ id: p.id, section: "discussion", suggestions: find(p.text) })),
      state: "ok",
      health: [],
      hidden_preferences: 0,
      signed_in: false,
      elapsed_ms: 1,
      ...over,
    },
  };
}

/** An engine whose answers the test releases one by one. */
function engine() {
  const calls: { req: CheckParagraphsRequest; signal: AbortSignal; resolve: (r: CheckResult<CheckParagraphsResponse>) => void }[] = [];
  const check = (req: CheckParagraphsRequest, signal: AbortSignal) =>
    new Promise<CheckResult<CheckParagraphsResponse>>((resolve, reject) => {
      calls.push({ req, signal, resolve });
      signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    });
  const reply = async (i: number, over?: Partial<CheckParagraphsResponse>) => {
    calls[i]!.resolve(answer(calls[i]!.req, over));
    await flush();
  };
  return { calls, check, reply };
}

const TEXT = "Discussion\nIn order to see the the dynamics.\n\nMore work is needed.\n";

function setup(text = TEXT) {
  const { clock, advance } = fakeClock();
  const e = engine();
  const s = new LiveSession(e.check, clock);
  s.setEnabled(true);
  s.setDocument(text, "plain");
  const drawn = () =>
    s
      .drawn()
      .map(({ paragraph, item }) => paragraph.text.slice(item.begin, item.end))
      .join("|");
  const type = (next: string) => {
    s.setDocument(next, "plain");
    s.edit();
  };
  return { s, e, advance, drawn, type };
}

describe("the live loop", () => {
  it("waits for the pause, then sends the paragraphs once, with their headings", async () => {
    const { s, e, advance, drawn, type } = setup("");
    type(TEXT);
    await advance(LIVE_PAUSE_MS - 1);
    expect(e.calls).toHaveLength(0);
    expect(s.getSnapshot().status.state).toBe("hidden");
    await advance(1);
    expect(e.calls).toHaveLength(1);
    expect(s.getSnapshot().status.state).toBe("checking");
    // The caret (at the start here) decides the order: the nearest paragraph first.
    expect(e.calls[0]!.req.paragraphs.map((p) => [p.text, p.heading])).toEqual([
      ["In order to see the the dynamics.", "Discussion"],
      ["More work is needed.", "Discussion"],
    ]);
    await e.reply(0);
    expect(drawn()).toBe("the the");
    expect(s.getSnapshot().status).toMatchObject({ state: "issues", count: 1 });
    // Nothing changed: nothing is sent again.
    s.edit();
    await advance(LIVE_PAUSE_MS * 2);
    expect(e.calls).toHaveLength(1);
    expect(s.getSnapshot().status.state).toBe("issues");
  });

  it("typing keeps pushing the pause back; only the changed paragraph is sent", async () => {
    const { e, advance, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    await e.reply(0);
    let t = TEXT;
    for (const typed of [" ", " Y", " Ye", " Yes"]) {
      t = TEXT.replace("needed.", `needed.${typed}`);
      type(t);
      await advance(500);
    }
    expect(e.calls).toHaveLength(1);
    await advance(LIVE_PAUSE_MS);
    expect(e.calls).toHaveLength(2);
    expect(e.calls[1]!.req.paragraphs.map((p) => p.text)).toEqual([splitParagraphs(t, "plain").paragraphs[1]!.text]);
    expect(e.calls[1]!.req.revision).toBeGreaterThan(e.calls[0]!.req.revision);
  });

  it("one request at a time: edits made meanwhile go in the next one", async () => {
    const { e, advance, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    type(TEXT.replace("More work", "Much more work"));
    await advance(LIVE_PAUSE_MS * 3);
    expect(e.calls).toHaveLength(1); // still in flight
    await e.reply(0);
    await advance(0);
    expect(e.calls).toHaveLength(2);
    expect(e.calls[1]!.req.paragraphs.map((p) => p.text)).toEqual(["Much more work is needed."]);
  });

  it("a reply for words that changed while it was out is not drawn", async () => {
    const { s, e, advance, drawn, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    // The writer fixes the repeated word while the answer is out.
    type(TEXT.replace("the the", "the"));
    await e.reply(0);
    expect(drawn()).toBe("");
    // The answer for the unchanged paragraph was kept; the edited one is asked again.
    await advance(LIVE_PAUSE_MS);
    expect(e.calls[1]!.req.paragraphs.map((p) => p.text)).toEqual(["In order to see the dynamics."]);
    await e.reply(1);
    expect(s.getSnapshot().status.state).toBe("clear");
  });

  it("a reply with another revision than the request's is dropped whole", async () => {
    const { e, advance, drawn, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    await e.reply(0, { revision: 9999 });
    expect(drawn()).toBe("");
  });

  it("a changed article type drops the answer in flight and asks again", async () => {
    const { s, e, advance, drawn, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    s.setOptions({ documentType: "grant", spelling: null, showPreferences: false });
    expect(e.calls[0]!.signal.aborted).toBe(true);
    await advance(0);
    expect(e.calls).toHaveLength(2);
    expect(e.calls[1]!.req.options?.document_type).toBe("grant");
    await e.reply(1);
    expect(drawn()).toBe("the the");
  });

  it("offline: retries after 2, 4, 8 s, keeps the text, recovers by itself", async () => {
    const { s, e, advance, drawn, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    e.calls[0]!.resolve({ ok: false, error: networkError(false, "http://engine") });
    await flush();
    expect(s.getSnapshot().status).toMatchObject({ state: "offline", retryInMs: 2000, failures: 1 });
    await advance(1999);
    expect(e.calls).toHaveLength(1);
    await advance(1);
    expect(e.calls).toHaveLength(2);
    expect(s.getSnapshot().status.state).toBe("offline"); // until it answers
    e.calls[1]!.resolve({ ok: false, error: networkError(true, "http://engine") });
    await flush();
    expect(s.getSnapshot().status).toMatchObject({ state: "offline", retryInMs: 4000, failures: 2 });
    await advance(4000);
    await e.reply(2);
    expect(s.getSnapshot().status).toMatchObject({ state: "issues", failures: 0 });
    expect(drawn()).toBe("the the");
  });

  it("Try now retries at once", async () => {
    const { s, e, advance, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    e.calls[0]!.resolve({ ok: false, error: networkError(false, "http://engine") });
    await flush();
    s.retryNow();
    expect(e.calls).toHaveLength(2);
  });

  it("a partial answer says which part was off", async () => {
    const { s, e, advance, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    await e.reply(0, {
      state: "partial",
      health: [{ tier: "grammar", label: "Grammar", ok: false, state: "error", detail: "", remedy: "" }],
    });
    expect(s.getSnapshot().status).toMatchObject({ state: "partial", count: 1, reason: "Grammar was not checked" });
  });

  it("switched off or LaTeX: hidden, and nothing is sent", async () => {
    const { s, e, advance, type } = setup();
    s.setEnabled(false);
    type(TEXT);
    await advance(LIVE_PAUSE_MS * 2);
    expect(e.calls).toHaveLength(0);
    expect(s.getSnapshot()).toMatchObject({ enabled: false, status: { state: "hidden" } });
    s.setEnabled(true);
    s.setDocument("\\section{Discussion}\nthe the", "latex");
    s.edit();
    await advance(LIVE_PAUSE_MS * 2);
    expect(e.calls).toHaveLength(0);
    expect(s.getSnapshot()).toMatchObject({ enabled: false, status: { state: "hidden" } });
  });

  it("switching on never sweeps the text on screen; the next edit is checked", async () => {
    const { s, e, advance, type } = setup();
    s.setEnabled(false);
    s.setDocument(TEXT, "plain");
    s.setEnabled(true);
    await advance(LIVE_PAUSE_MS * 2);
    expect(e.calls).toHaveLength(0);
    type(TEXT.replace("More work", "Much more work"));
    await advance(LIVE_PAUSE_MS);
    expect(e.calls.map((c) => c.req.paragraphs.map((p) => p.text))).toEqual([["Much more work is needed."]]);
  });

  it("a long paste: one request for the paragraphs nearest the caret; the rest is left to Check", async () => {
    const { s, e, advance, type } = setup("");
    const long = Array.from({ length: 120 }, (_, i) => `Paragraph ${i} has the the slip.`).join("\n\n");
    s.setCaretSource(() => long.length);
    type(long);
    await advance(LIVE_PAUSE_MS);
    expect(e.calls).toHaveLength(1);
    expect(e.calls[0]!.req.paragraphs).toHaveLength(50);
    expect(e.calls[0]!.req.paragraphs[0]!.text).toBe("Paragraph 119 has the the slip.");
    expect(s.getSnapshot().leftToCheck).toBe(true);
    await e.reply(0);
    await advance(LIVE_PAUSE_MS * 4);
    expect(e.calls).toHaveLength(1); // never a sweep
    expect(s.drawn()).toHaveLength(50);
    // A full check answers for everything and clears the note.
    s.fullCheckStarted();
    s.fullCheckAnswered(long, "plain", [], { documentType: "auto", spelling: null, showPreferences: false });
    expect(s.getSnapshot().leftToCheck).toBe(false);
  });

  it("text loaded without typing (the demo) is not sent until the writer edits or checks", async () => {
    const { e, advance } = setup(TEXT);
    await advance(LIVE_PAUSE_MS * 3);
    expect(e.calls).toHaveLength(0);
  });

  it("Preferences come back always and are shown only when asked for, without a new request", async () => {
    const { s, e, advance, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    expect(e.calls[0]!.req.options?.show_preferences).toBe(true);
    e.calls[0]!.resolve(answer(e.calls[0]!.req));
    await flush();
    const n = s.drawn().length;
    s.setOptions({ documentType: "auto", spelling: null, showPreferences: true });
    await advance(LIVE_PAUSE_MS);
    expect(e.calls).toHaveLength(1);
    expect(s.drawn()).toHaveLength(n);
  });

  it("dismissing an underline hides it and updates the count", async () => {
    const { s, e, advance, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    await e.reply(0);
    s.dismiss(s.drawn()[0]!.item.id);
    expect(s.drawn()).toHaveLength(0);
    expect(s.getSnapshot().status.state).toBe("clear");
  });

  it("an underline before an edit in the same paragraph stays put until the answer", async () => {
    const { e, advance, drawn, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    await e.reply(0);
    type(TEXT.replace("dynamics.", "dynamics of spread."));
    expect(drawn()).toBe("the the");
    type(TEXT.replace("the the", "the"));
    expect(drawn()).toBe("");
  });

  it("undo brings the answer back from memory", async () => {
    const { e, advance, drawn, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    await e.reply(0);
    type(TEXT.replace("the the", "the"));
    await advance(LIVE_PAUSE_MS);
    await e.reply(1);
    type(TEXT);
    expect(drawn()).toBe("the the");
    await advance(LIVE_PAUSE_MS * 2);
    expect(e.calls).toHaveLength(2);
  });

  it("a full check: checking while it runs, then its sentence-level suggestions are the underlines", async () => {
    const { s, e, advance, drawn } = setup(TEXT);
    s.fullCheckStarted();
    expect(s.getSnapshot().status.state).toBe("checking");
    const at = Array.from(TEXT.slice(0, TEXT.indexOf("the the"))).length;
    const full: Suggestion[] = [
      {
        id: "full1",
        rule_id: "G110",
        rule_name: "Repeated word",
        category: "correction",
        confidence: 1,
        fix_safety: "review",
        message: "m",
        plain: "",
        why: "",
        source: "s",
        section: "discussion",
        tier: "craft",
        text: "the the",
        span: { start: at, end: at + 7, line: 0, col: 0 },
      },
      { ...({} as Suggestion), id: "doc1", rule_id: "W211", category: "convention", span: { start: 11, end: 13, line: 0, col: 0 }, text: "In" },
    ];
    s.setDocumentWide((id) => id === "W211");
    s.fullCheckAnswered(TEXT, "plain", full, { documentType: "manuscript", spelling: null, showPreferences: false });
    await advance(LIVE_PAUSE_MS * 2);
    expect(drawn()).toBe("the the");
    expect(s.getSnapshot().status).toMatchObject({ state: "issues", count: 1 });
    // The check answered for every paragraph: nothing is sent.
    expect(e.calls).toHaveLength(0);
    // Showing Preferences sends nothing: the full check answered these paragraphs (Check again shows its Preferences).
    s.setOptions({ documentType: "manuscript", spelling: null, showPreferences: true });
    await advance(LIVE_PAUSE_MS);
    expect(e.calls).toHaveLength(0);
  });

  it("a failed full check hands back to the live loop", async () => {
    const { s, e, advance, type } = setup();
    type(TEXT);
    s.fullCheckStarted();
    await advance(LIVE_PAUSE_MS * 2);
    expect(e.calls).toHaveLength(0); // the full check answers for the whole text
    s.fullCheckEnded();
    await advance(0);
    expect(e.calls).toHaveLength(1);
  });

  it("empty text: hidden", async () => {
    const { s, e, advance, type } = setup();
    type(TEXT);
    await advance(LIVE_PAUSE_MS);
    await e.reply(0);
    type("");
    expect(s.getSnapshot().status.state).toBe("hidden");
  });

  it("names the part that was off in words", () => {
    expect(partialReason([])).toBe("");
    expect(
      partialReason([
        { tier: "grammar", label: "Grammar", ok: false, state: "error", detail: "", remedy: "" },
        { tier: "gec", label: "Learned", ok: false, state: "missing", detail: "", remedy: "" },
      ]),
    ).toBe("Grammar was not checked");
  });
});

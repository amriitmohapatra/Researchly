import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CompletionCandidate } from "@researchly/contract";
import { buildCompleteRequest, complete, COMPLETE_TIMEOUT_MS, looksLikeCompleteResponse } from "@/lib/engine";
import {
  acceptCandidate,
  codePointToUtf16,
  MAX_SHOWN,
  PREDICTION_DEBOUNCE_MS,
  PredictionScheduler,
  predictionAnnouncement,
  predictionKey,
  predictionWindow,
  RATE_LIMIT_PAUSE_MS,
  remainder,
  resolvePrediction,
  snapshotAt,
  snapUtf16,
  utf16ToCodePoint,
  WINDOW_BEFORE,
  wordInsertion,
  type PredictionReply,
  type PredictionShown,
  type PredictionSnapshot,
} from "@/lib/prediction";
import { loadPredictionChoice, savePredictionChoice } from "@/lib/prefs";
import { predictionFromRow } from "@/lib/account";

/** Synthetic sentences written for these tests. 𝑅 and 😀 are one code point and two UTF-16 units each. */
const EMOJI = "😀";
const MATH_R = "𝑅";

const cand = (text: string, start: number, end: number, kind: "word" | "term" = "word"): CompletionCandidate => ({ text, start, end, kind });

/* ---------- offsets: code points (the engine) vs UTF-16 (the textarea) ---------- */

describe("code-point offsets", () => {
  it("count a character outside the BMP once, as Python does", () => {
    const t = `${MATH_R}0 was ${EMOJI} high`;
    expect(t.length).toBe(15);
    expect(utf16ToCodePoint(t, t.length)).toBe(13);
    expect(utf16ToCodePoint(t, 2)).toBe(1); // after 𝑅
    expect(codePointToUtf16(t, 1)).toBe(2);
    expect(codePointToUtf16(t, 13)).toBe(t.length);
    // Round trip at every code-point boundary.
    for (let cp = 0; cp <= 13; cp++) expect(utf16ToCodePoint(t, codePointToUtf16(t, cp))).toBe(cp);
  });

  it("never splits a surrogate pair: an index in the middle of one moves to its start", () => {
    const t = `a${EMOJI}b`;
    expect(snapUtf16(t, 2)).toBe(1);
    expect(utf16ToCodePoint(t, 2)).toBe(1);
    expect(snapUtf16(t, 3)).toBe(3);
    expect(snapUtf16(t, 99)).toBe(4);
    expect(snapUtf16(t, -5)).toBe(0);
  });

  it("is the identity for plain ASCII", () => {
    const t = "We estimated the basic rep";
    expect(utf16ToCodePoint(t, 10)).toBe(10);
    expect(codePointToUtf16(t, 10)).toBe(10);
  });
});

describe("the window sent around the cursor", () => {
  it("sends a short text whole, with the cursor in code points", () => {
    const t = `${EMOJI} We report the confidence int`;
    const w = predictionWindow(t, t.length);
    expect(w).toEqual({ text: t, cursor: t.length - 1, from: 0 });
  });

  it("sends at most 4,000 characters before the cursor, and adjusts the cursor to the window", () => {
    const long = `${"x ".repeat(3000)}the basic rep`;
    const w = predictionWindow(long, long.length);
    expect(w.text.length).toBe(WINDOW_BEFORE);
    expect(w.from).toBe(long.length - WINDOW_BEFORE);
    expect(w.cursor).toBe(WINDOW_BEFORE);
    expect(w.text.endsWith("the basic rep")).toBe(true);
  });

  it("does not start the window in the middle of an emoji", () => {
    const head = `${EMOJI}`.repeat(10);
    const t = `${head}${"a".repeat(WINDOW_BEFORE - 1)}`;
    // The window would start one unit into the last emoji: it starts after it instead.
    const w = predictionWindow(t, t.length);
    expect(w.text).toBe("a".repeat(WINDOW_BEFORE - 1));
    expect(w.cursor).toBe(WINDOW_BEFORE - 1);
  });

  it("includes the rest of the paragraph after the cursor, but not the next paragraph", () => {
    const t = "Methods\nWe fitted a transmission model to counts.\n\nResults\nIt fitted.";
    const caret = t.indexOf(" model");
    const w = predictionWindow(t, caret);
    expect(w.text).toBe("Methods\nWe fitted a transmission model to counts.");
    expect(w.cursor).toBe(caret);
  });

  it("caps what is sent after the cursor", () => {
    const t = `the ${"word ".repeat(1000)}`;
    const w = predictionWindow(t, 4, 4000, 100);
    expect(w.text.length).toBe(104);
  });
});

describe("accepting a candidate", () => {
  it("replaces [start, end) mapped back to the full text, after an emoji, and puts the caret after it", () => {
    const t = `${MATH_R} We report the confidence int and more`;
    const caret = t.indexOf(" and");
    const w = predictionWindow(t, caret);
    const cpCaret = utf16ToCodePoint(t, caret);
    const done = acceptCandidate(t, w, cand("interval", cpCaret - 3, cpCaret));
    expect(done).toEqual({ text: `${MATH_R} We report the confidence interval and more`, caret: caret + 5 });
  });

  it("maps back through a window that starts late in a long text", () => {
    const t = `${EMOJI.repeat(3000)} the basic rep`;
    const w = predictionWindow(t, t.length);
    expect(w.from).toBeGreaterThan(0);
    const done = acceptCandidate(t, w, cand("reproduction number", w.cursor - 3, w.cursor, "term"));
    expect(done?.text.endsWith(" the basic reproduction number")).toBe(true);
    expect(done?.text.startsWith(EMOJI.repeat(10))).toBe(true);
    expect(done?.caret).toBe(done?.text.length);
  });

  it("inserts a next word at the cursor (start = end)", () => {
    const t = "We fitted a transmission ";
    const w = predictionWindow(t, t.length);
    expect(acceptCandidate(t, w, cand("model", w.cursor, w.cursor))).toEqual({ text: `${t}model`, caret: t.length + 5 });
  });

  it("refuses a candidate that is not for this cursor, or a text that changed", () => {
    const t = "the basic rep";
    const w = predictionWindow(t, t.length);
    expect(acceptCandidate(t, w, cand("reproduction", 10, 12))).toBeNull();
    expect(acceptCandidate(t, w, cand("", 10, 13))).toBeNull();
    expect(acceptCandidate("the basic re", w, cand("reproduction", 10, 13))).toBeNull();
  });
});

describe("the Word panel's insertion: only the rest of the word", () => {
  it("keeps the typed letters as typed and inserts the remainder", () => {
    expect(remainder("int", "interval")).toBe("erval");
    expect(remainder("Conf", "confidence interval")).toBe("idence interval");
    expect(remainder("", "model")).toBe("model");
    expect(remainder("xyz", "interval")).toBe("");
    expect(remainder("intervals", "interval")).toBe("");
  });

  it("works in code points (a window holding an emoji)", () => {
    const before = `${EMOJI} the basic rep`;
    const w = predictionWindow(before, before.length);
    expect(wordInsertion(w, cand("reproduction number", w.cursor - 3, w.cursor, "term"))).toEqual({
      label: "reproduction number",
      insertion: "roduction number",
    });
    expect(wordInsertion(w, cand("model", w.cursor - 3, w.cursor - 1))).toBeNull();
  });
});

/* ---------- keys: Tab accepts, Esc dismisses, typing goes on ---------- */

describe("keys while candidates are shown", () => {
  it("Tab accepts the first candidate; Esc dismisses", () => {
    expect(predictionKey({ key: "Tab" }, true)).toBe("accept");
    expect(predictionKey({ key: "Escape" }, true)).toBe("dismiss");
  });

  it("Tab moves focus as usual when nothing is shown, and Shift+Tab always does", () => {
    expect(predictionKey({ key: "Tab" }, false)).toBeNull();
    expect(predictionKey({ key: "Tab", shiftKey: true }, true)).toBeNull();
    expect(predictionKey({ key: "Tab", ctrlKey: true }, true)).toBeNull();
    expect(predictionKey({ key: "Escape" }, false)).toBeNull();
  });

  it("ordinary typing, and keys during an IME composition, are left alone", () => {
    expect(predictionKey({ key: "a" }, true)).toBeNull();
    expect(predictionKey({ key: "Enter" }, true)).toBeNull();
    expect(predictionKey({ key: "Tab", isComposing: true }, true)).toBeNull();
  });

  it("Tab acceptance end to end: the first candidate, into the text it was asked for", () => {
    const text = "We report the 95% confidence int";
    const snap = snapshotAt(text, text.length, "plain");
    const candidates = [cand("interval", snap.window.cursor - 3, snap.window.cursor), cand("intervals", snap.window.cursor - 3, snap.window.cursor)];
    const key = predictionKey({ key: "Tab" }, candidates.length > 0);
    expect(key).toBe("accept");
    const done = acceptCandidate(snap.full, snap.window, candidates[0]!);
    expect(done).toEqual({ text: "We report the 95% confidence interval", caret: 37 });
  });
});

/* ---------- debounce, abort, sequence: a late reply never shows ---------- */

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

describe("the scheduler", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const ok = (candidates: CompletionCandidate[], status: "ok" | "off" | "masked" | "unavailable" = "ok"): PredictionReply => ({ ok: true, status, candidates });

  it("waits for a pause in typing: one request for a burst of keystrokes", async () => {
    const request = vi.fn(async () => ok([cand("interval", 0, 0)]));
    const shown: (PredictionShown | null)[] = [];
    const s = new PredictionScheduler({ request, onShow: (x) => shown.push(x) });
    s.schedule(snapshotAt("the con", 7, "plain"));
    vi.advanceTimersByTime(100);
    s.schedule(snapshotAt("the conf", 8, "plain"));
    vi.advanceTimersByTime(PREDICTION_DEBOUNCE_MS - 1);
    expect(request).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(request).toHaveBeenCalledTimes(1);
    expect((request.mock.calls[0] as unknown as [PredictionSnapshot])[0].full).toBe("the conf");
    await vi.runAllTimersAsync();
    expect(shown.at(-1)?.snapshot.full).toBe("the conf");
  });

  it("drops a late reply to older text, and aborts its request", async () => {
    const first = deferred<PredictionReply>();
    const second = deferred<PredictionReply>();
    const signals: AbortSignal[] = [];
    const replies = [first, second];
    const request = vi.fn((_snap: PredictionSnapshot, signal: AbortSignal) => {
      signals.push(signal);
      return replies[signals.length - 1]!.promise;
    });
    const shown: (PredictionShown | null)[] = [];
    const s = new PredictionScheduler({ request, onShow: (x) => shown.push(x) });

    s.schedule(snapshotAt("the basic rep", 13, "plain"));
    vi.advanceTimersByTime(PREDICTION_DEBOUNCE_MS);
    s.schedule(snapshotAt("the basic repo", 14, "plain")); // typing went on
    expect(signals[0]!.aborted).toBe(true);
    vi.advanceTimersByTime(PREDICTION_DEBOUNCE_MS);

    // The old reply arrives late, after the new request went out: never shown.
    first.resolve(ok([cand("reproduction", 10, 13)]));
    await vi.runAllTimersAsync();
    expect(shown.filter(Boolean)).toEqual([]);

    second.resolve(ok([cand("reproduction", 10, 14)]));
    await vi.runAllTimersAsync();
    expect(shown.filter(Boolean).map((x) => x!.snapshot.full)).toEqual(["the basic repo"]);
  });

  it("shows nothing unless the status is ok, and at most three", async () => {
    const replies: PredictionReply[] = [
      ok([cand("a", 0, 0)], "masked"),
      ok([cand("a", 0, 0)], "off"),
      ok([], "unavailable"),
      ok(["a", "b", "c", "d", "e"].map((t) => cand(t, 0, 0))),
    ];
    const request = vi.fn(async () => replies.shift()!);
    const shown: (PredictionShown | null)[] = [];
    const s = new PredictionScheduler({ request, onShow: (x) => shown.push(x) });
    for (let i = 0; i < 4; i++) {
      s.schedule(snapshotAt(`t${i} `, 3, "plain"));
      await vi.runAllTimersAsync();
    }
    const visible = shown.filter(Boolean);
    expect(visible).toHaveLength(1);
    expect(visible[0]!.candidates).toHaveLength(MAX_SHOWN);
  });

  it("hides what is shown as soon as the text changes, the caret moves, or Esc", async () => {
    const request = vi.fn(async () => ok([cand("model", 3, 3)]));
    const shown: (PredictionShown | null)[] = [];
    const s = new PredictionScheduler({ request, onShow: (x) => shown.push(x) });
    s.schedule(snapshotAt("We ", 3, "plain"));
    await vi.runAllTimersAsync();
    expect(shown.at(-1)).not.toBeNull();

    s.moved("We ", 3, 3); // the same caret: nothing changes
    expect(shown.at(-1)).not.toBeNull();
    s.moved("We ", 1, 1); // a click elsewhere
    expect(shown.at(-1)).toBeNull();

    s.schedule(snapshotAt("We ", 3, "plain"));
    await vi.runAllTimersAsync();
    s.cancel(); // Esc
    expect(shown.at(-1)).toBeNull();
  });

  it("goes quiet for a while after the engine says too many requests", async () => {
    let now = 0;
    const request = vi.fn(async (): Promise<PredictionReply> => ({ ok: false, rateLimited: true }));
    const s = new PredictionScheduler({ request, onShow: () => undefined, now: () => now });
    s.schedule(snapshotAt("a ", 2, "plain"));
    await vi.runAllTimersAsync();
    expect(request).toHaveBeenCalledTimes(1);
    s.schedule(snapshotAt("ab ", 3, "plain"));
    await vi.runAllTimersAsync();
    expect(request).toHaveBeenCalledTimes(1);
    now = RATE_LIMIT_PAUSE_MS + 1;
    s.schedule(snapshotAt("abc ", 4, "plain"));
    await vi.runAllTimersAsync();
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("a request that throws (aborted, offline) shows nothing", async () => {
    const shown: (PredictionShown | null)[] = [];
    const s = new PredictionScheduler({
      request: async () => {
        throw new DOMException("aborted", "AbortError");
      },
      onShow: (x) => shown.push(x),
    });
    s.schedule(snapshotAt("a ", 2, "plain"));
    await vi.runAllTimersAsync();
    expect(shown).toEqual([]);
  });
});

/* ---------- the switch ---------- */

describe("the word prediction switch", () => {
  it("is on by default", () => {
    expect(resolvePrediction({ chosen: null, account: null, stored: null, signedIn: false })).toBe(true);
  });

  it("signed out, this browser's choice applies", () => {
    expect(resolvePrediction({ chosen: null, account: null, stored: false, signedIn: false })).toBe(false);
    expect(resolvePrediction({ chosen: null, account: false, stored: true, signedIn: false })).toBe(true);
  });

  it("signed in, the account's choice wins over this browser's; the session's own choice wins over both", () => {
    expect(resolvePrediction({ chosen: null, account: false, stored: true, signedIn: true })).toBe(false);
    expect(resolvePrediction({ chosen: null, account: null, stored: false, signedIn: true })).toBe(false);
    expect(resolvePrediction({ chosen: true, account: false, stored: false, signedIn: true })).toBe(true);
  });

  it("is remembered in this browser under its own key, as on/off, never text", () => {
    const store = new Map<string, string>();
    vi.stubGlobal("window", {
      localStorage: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) },
    });
    try {
      expect(loadPredictionChoice()).toBeNull();
      savePredictionChoice(false);
      expect([...store.entries()]).toEqual([["researchly.prediction", "off"]]);
      expect(loadPredictionChoice()).toBe(false);
      savePredictionChoice(true);
      expect(loadPredictionChoice()).toBe(true);
      store.set("researchly.prediction", "maybe");
      expect(loadPredictionChoice()).toBeNull();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("reads the account's column when present and tolerates its absence", () => {
    expect(predictionFromRow({ prediction: false })).toBe(false);
    expect(predictionFromRow({ prediction: true })).toBe(true);
    expect(predictionFromRow({})).toBeNull();
    expect(predictionFromRow(null)).toBeNull();
    expect(predictionFromRow({ prediction: "no" })).toBeNull();
  });
});

/* ---------- the request ---------- */

describe("POST /v1/complete", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends the window, the cursor in code points, the format and a limit, and nothing else", () => {
    expect(buildCompleteRequest({ text: "the basic rep", cursor: 13, format: "latex" })).toEqual({
      text: "the basic rep",
      cursor: 13,
      format: "latex",
      options: { limit: 3 },
    });
    expect(buildCompleteRequest({ text: "x", cursor: 1, format: "plain", limit: 9 }).options?.limit).toBe(5);
  });

  it("goes to the engine with the bearer token when signed in, and no cookies", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ status: "ok", candidates: [cand("interval", 3, 6)] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const auth = { token: async () => "tok", refresh: async () => ({ token: null }), signOutLocally: async () => undefined };
    const r = await complete({ text: "int", cursor: 3, format: "plain" }, "http://engine.test", auth);
    expect(r.ok && r.data.candidates?.[0]?.text).toBe("interval");
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://engine.test/v1/complete");
    expect(init.credentials).toBe("omit");
    expect((init.headers as Record<string, string>).authorization).toBe("Bearer tok");
    expect(JSON.parse(String(init.body))).toEqual({ text: "int", cursor: 3, format: "plain", options: { limit: 3 } });
  });

  it("a refused token is not refreshed or signed out for a prediction: it just offers nothing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ error: { code: "unauthorized", message: "m", request_id: "r" } }), { status: 401 })),
    );
    const signOut = vi.fn(async () => undefined);
    const refresh = vi.fn(async () => ({ token: "new" }));
    const r = await complete({ text: "a", cursor: 1, format: "plain" }, "http://engine.test", { token: async () => "old", refresh, signOutLocally: signOut });
    expect(r.ok).toBe(false);
    expect(refresh).not.toHaveBeenCalled();
    expect(signOut).not.toHaveBeenCalled();
  });

  it("gives up quickly: a prediction that is late is no use", () => {
    expect(COMPLETE_TIMEOUT_MS).toBeLessThanOrEqual(5_000);
  });

  it("accepts only a well-formed reply", () => {
    expect(looksLikeCompleteResponse({ status: "ok", candidates: [] })).toBe(true);
    expect(looksLikeCompleteResponse({ status: "masked" })).toBe(true);
    expect(looksLikeCompleteResponse({ status: "maybe", candidates: [] })).toBe(false);
    expect(looksLikeCompleteResponse({ status: "ok", candidates: [{ text: "x", start: 3, end: 1, kind: "word" }] })).toBe(false);
    expect(looksLikeCompleteResponse({ status: "ok", candidates: [{ text: "", start: 0, end: 0, kind: "word" }] })).toBe(false);
    expect(looksLikeCompleteResponse({ status: "ok", candidates: [{ text: "x", start: 0, end: 0, kind: "sentence" }] })).toBe(false);
  });
});

describe("what a screen reader hears", () => {
  it("names the first candidate and how to take it, then the others", () => {
    expect(predictionAnnouncement([])).toBe("");
    expect(predictionAnnouncement([{ text: "interval" }, { text: "intervals" }])).toBe("Suggested: interval. Tab to accept. Also: intervals.");
  });
});

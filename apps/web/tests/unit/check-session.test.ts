import { afterEach, describe, expect, it, vi } from "vitest";
import type { AnalyzeResponse } from "@researchly/contract";
import { analyze } from "@/lib/engine";
import { createCheckSession, elapsedLabel, progressStatus, STILL_CHECKING_AFTER_MS, type CheckTask } from "@/lib/check-session";

/*
 * Review proposal 8, long documents. "Done when a large synthetic document
 * survives cancel and retry without showing an old response as current."
 * Every test goes through the real engine client (lib/engine.ts) with a
 * mocked fetch whose replies are released by hand, so the order of the
 * answers is controlled exactly.
 */

/** A large synthetic document (invented sentences, about 120,000 words). */
function largeDocument(): string {
  const paragraph =
    "Methods\nWe fitted a renewal model to weekly case counts from three invented districts. " +
    "The generation interval was assumed to follow a gamma distribution with a mean of seven days. " +
    "Priors were weakly informative, and convergence was assessed with the split R-hat statistic.\n\n";
  return paragraph.repeat(2_600);
}

/** A minimal valid answer whose one suggestion names the request it answers. */
function answer(tag: string): AnalyzeResponse {
  return {
    schema_version: "1",
    suggestions: [
      {
        id: `s-${tag}`,
        rule_id: "T001",
        rule_name: "test",
        category: "correction",
        tier: "craft",
        span: { start: 0, end: 7, line: 1, col: 1 },
        section: "methods",
        message: `answer ${tag}`,
        why: "w",
        plain: "p",
        source: "s",
        text: "Methods",
        fix_safety: "review",
        confidence: 1,
      },
    ],
    health: [],
    hidden_preferences: 0,
    sections_detected: ["methods"],
  } as unknown as AnalyzeResponse;
}

interface Pending {
  body: string;
  signal: AbortSignal | null;
  /** Deliver the reply now, whether or not the request was aborted (a network that ignores the abort). */
  deliver: (tag: string) => void;
}

/**
 * fetch, mocked: each call waits until the test delivers its reply. With
 * `honourAbort`, an aborted request rejects like the browser's fetch does;
 * without it the reply still arrives late, which is the case the sequence
 * guard exists for.
 */
function controllableFetch({ honourAbort }: { honourAbort: boolean }) {
  const calls: Pending[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((_url: string, init?: RequestInit) => {
      const signal = init?.signal ?? null;
      return new Promise<Response>((resolve, reject) => {
        const pending: Pending = {
          body: String(init?.body ?? ""),
          signal,
          deliver: (tag) =>
            resolve(new Response(JSON.stringify(answer(tag)), { status: 200, headers: { "content-type": "application/json" } })),
        };
        if (honourAbort && signal) {
          signal.addEventListener("abort", () => reject(new DOMException("The operation was aborted.", "AbortError")), { once: true });
        }
        calls.push(pending);
      });
    }),
  );
  return calls;
}

/** The task a surface runs: the real client, with the session's signal. */
function checkTask(content: string): CheckTask<AnalyzeResponse> {
  return (signal) => analyze({ content, format: "plain", showPreferences: false, mode: "revise", signal }, "http://engine.test");
}

/** Let pending promise callbacks run. */
const flush = () => new Promise((r) => setTimeout(r, 0));

function shownTag(s: { result: AnalyzeResponse | null }): string | null {
  return s.result?.suggestions[0]?.message ?? null;
}

afterEach(() => vi.unstubAllGlobals());

describe("long checks: request sequencing (review proposal 8)", () => {
  const doc = largeDocument();

  it("the synthetic document is large: a whole thesis, under the engine's cap", () => {
    expect(doc.split(/\s+/).length).toBeGreaterThan(100_000);
    expect(doc.length).toBeLessThan(1_000_000);
  });

  it("start A, start B, A answers late: A is ignored and B is shown as current", async () => {
    const calls = controllableFetch({ honourAbort: false });
    const session = createCheckSession<AnalyzeResponse>();
    const results: string[] = [];
    const hooks = { onResult: (d: AnalyzeResponse) => results.push(d.suggestions[0]!.message) };

    const a = session.start(checkTask(doc), hooks);
    await flush();
    const b = session.start(checkTask(`${doc}Discussion\nA changed ending.\n`), hooks);
    await flush();
    expect(calls).toHaveLength(2);
    expect(calls[0]!.signal?.aborted).toBe(true); // A was told to stop
    expect(session.getState().phase).toBe("running");

    calls[1]!.deliver("B");
    expect(await b).toBe("current");
    expect(shownTag(session.getState())).toBe("answer B");

    // A's reply arrives after B's, from a network that ignored the abort.
    calls[0]!.deliver("A");
    expect(await a).toBe("dropped");
    const s = session.getState();
    expect(shownTag(s)).toBe("answer B");
    expect(s.phase).toBe("done");
    expect(s.fromPrevious).toBe(false);
    expect(results).toEqual(["answer B"]); // the surface was never handed A
  });

  it("A answers late while B is still running: A is still ignored, and the old results stay marked as previous", async () => {
    const calls = controllableFetch({ honourAbort: false });
    const session = createCheckSession<AnalyzeResponse>();
    const first = session.start(checkTask("Methods\nA short first draft.\n"));
    await flush();
    calls[0]!.deliver("first");
    await first;

    const a = session.start(checkTask(doc));
    await flush();
    const b = session.start(checkTask(doc));
    await flush();
    calls[1]!.deliver("A"); // A's late reply, before B's
    expect(await a).toBe("dropped");
    let s = session.getState();
    expect(s.phase).toBe("running");
    expect(shownTag(s)).toBe("answer first");
    expect(s.fromPrevious).toBe(true);

    calls[2]!.deliver("B");
    await b;
    s = session.getState();
    expect(shownTag(s)).toBe("answer B");
    expect(s.fromPrevious).toBe(false);
  });

  it("cancel: the previous results are current again, with a cancelled note; a late reply is dropped", async () => {
    const calls = controllableFetch({ honourAbort: false });
    const session = createCheckSession<AnalyzeResponse>();
    const first = session.start(checkTask("Methods\nA short first draft.\n"));
    await flush();
    calls[0]!.deliver("previous");
    await first;

    const long = session.start(checkTask(doc));
    await flush();
    expect(session.getState()).toMatchObject({ phase: "running", fromPrevious: true });
    expect(session.cancel()).toBe(true);
    expect(calls[1]!.signal?.aborted).toBe(true);
    let s = session.getState();
    expect(s).toMatchObject({ phase: "done", note: "cancelled", startedAt: null, error: null });
    expect(shownTag(s)).toBe("answer previous");

    calls[1]!.deliver("cancelled");
    expect(await long).toBe("dropped");
    s = session.getState();
    expect(shownTag(s)).toBe("answer previous");
    expect(s.note).toBe("cancelled");
  });

  it("cancel with a fetch that honours the abort: same outcome, no error shown", async () => {
    const calls = controllableFetch({ honourAbort: true });
    const session = createCheckSession<AnalyzeResponse>();
    const onError = vi.fn();
    const run = session.start(checkTask(doc), { onError });
    await flush();
    session.cancel();
    expect(await run).toBe("dropped");
    expect(calls[0]!.signal?.aborted).toBe(true);
    expect(session.getState()).toMatchObject({ phase: "idle", result: null, note: "cancelled", error: null });
    expect(onError).not.toHaveBeenCalled();
  });

  it("retry after a cancel sends the same large document again and shows its answer as current", async () => {
    const calls = controllableFetch({ honourAbort: true });
    const session = createCheckSession<AnalyzeResponse>();
    const run = session.start(checkTask(doc));
    await flush();
    session.cancel();
    await run;

    const again = session.retry();
    expect(again).not.toBeNull();
    await flush();
    expect(calls).toHaveLength(2);
    expect(calls[1]!.body).toBe(calls[0]!.body); // the same check, not whatever is in the editor now
    expect(JSON.parse(calls[1]!.body).content).toBe(doc);
    expect(session.getState()).toMatchObject({ phase: "running", note: null });
    calls[1]!.deliver("retried");
    expect(await again).toBe("current");
    expect(shownTag(session.getState())).toBe("answer retried");
    expect(session.getState()).toMatchObject({ phase: "done", note: null, fromPrevious: false });
  });

  it("cancel, retry, cancel again, retry again: only the last answer is ever current", async () => {
    const calls = controllableFetch({ honourAbort: false });
    const session = createCheckSession<AnalyzeResponse>();
    const runs = [session.start(checkTask(doc))];
    await flush();
    session.cancel();
    runs.push(session.retry()!);
    await flush();
    session.cancel();
    runs.push(session.retry()!);
    await flush();
    expect(calls).toHaveLength(3);
    // Replies arrive in the worst order: the newest first, then the two cancelled ones.
    calls[2]!.deliver("third");
    calls[0]!.deliver("first");
    calls[1]!.deliver("second");
    expect(await Promise.all(runs)).toEqual(["dropped", "dropped", "current"]);
    expect(shownTag(session.getState())).toBe("answer third");
  });

  it("a failure keeps the previous results on screen, marked as previous; Retry clears it", async () => {
    let n = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        n++;
        if (n === 2) return new Response(JSON.stringify({ error: { code: "internal", message: "boom", request_id: "r1" } }), { status: 500 });
        return new Response(JSON.stringify(answer(`ok${n}`)), { status: 200 });
      }),
    );
    const session = createCheckSession<AnalyzeResponse>();
    await session.start(checkTask("Methods\nShort.\n"));
    await session.start(checkTask(doc));
    let s = session.getState();
    expect(s.phase).toBe("error");
    expect(s.error?.kind).toBe("server");
    expect(s.fromPrevious).toBe(true);
    expect(shownTag(s)).toBe("answer ok1");
    await session.retry();
    s = session.getState();
    expect(s).toMatchObject({ phase: "done", error: null, fromPrevious: false });
    expect(shownTag(s)).toBe("answer ok3");
  });

  it("nothing to cancel or retry before the first check", () => {
    const session = createCheckSession<AnalyzeResponse>();
    expect(session.cancel()).toBe(false);
    expect(session.retry()).toBeNull();
    expect(session.getState()).toMatchObject({ phase: "idle", note: null });
  });

  it("settle (back to the editor) aborts the running check and drops its reply", async () => {
    const calls = controllableFetch({ honourAbort: false });
    const session = createCheckSession<AnalyzeResponse>();
    const run = session.start(checkTask(doc));
    await flush();
    session.settle();
    calls[0]!.deliver("late");
    expect(await run).toBe("dropped");
    expect(session.getState()).toMatchObject({ phase: "idle", result: null, note: null });
  });

  it("subscribers hear every change, and the start time is recorded for the elapsed clock", async () => {
    let t = 1_000;
    const calls = controllableFetch({ honourAbort: false });
    const session = createCheckSession<AnalyzeResponse>({ now: () => t });
    const seen: string[] = [];
    const off = session.subscribe(() => seen.push(session.getState().phase));
    const run = session.start(checkTask(doc));
    expect(session.getState().startedAt).toBe(1_000);
    t = 40_000;
    await flush();
    calls[0]!.deliver("done");
    await run;
    off();
    expect(seen).toEqual(["running", "done"]);
    expect(session.getState().startedAt).toBeNull();
  });
});

describe("what a running check says", () => {
  it("elapsed time reads in seconds, then minutes and seconds", () => {
    expect(elapsedLabel(0)).toBe("0 s");
    expect(elapsedLabel(4_900)).toBe("4 s");
    expect(elapsedLabel(59_999)).toBe("59 s");
    expect(elapsedLabel(65_000)).toBe("1 min 05 s");
    expect(elapsedLabel(-5)).toBe("0 s");
  });

  it("says 'still checking' once a check runs long, and mentions the previous results only when there are some", () => {
    expect(progressStatus(1_000, "your text", true)).toBe("Checking your text…");
    const still = progressStatus(STILL_CHECKING_AFTER_MS, "your text", true);
    expect(still).toMatch(/^Still checking your text\./);
    expect(still).toMatch(/previous results stay below/);
    expect(progressStatus(STILL_CHECKING_AFTER_MS + 1, "the document", false)).not.toMatch(/previous/);
    // Plain words, no score, no em dash (DESIGN.md).
    expect(still).not.toMatch(/—|score/i);
  });
});

/**
 * One check at a time, and never an old answer shown as the current one
 * (Codex review #8, long documents).
 *
 * A check of a whole thesis can take a minute or two. While it runs the
 * previous results stay on screen, marked as previous; Cancel is
 * predictable (the request is aborted and the screen returns to exactly what
 * it showed before, with a "cancelled" note); Retry runs the same check
 * again. Every request carries a sequence number: a reply that arrives after
 * its request was cancelled or superseded by a newer one is dropped, even
 * when the network ignored the abort. Framework-free so the sequencing is
 * unit-tested with a mocked fetch (tests/unit/check-session.test.ts); the
 * React surfaces subscribe to it.
 *
 * Nothing here stores anything: the result lives in memory with the page.
 */
import { clientError, type CheckError } from "./errors";

export type Outcome<T> = { ok: true; data: T } | { ok: false; error: CheckError };

/** Runs one check. `signal` aborts it; `requestId` is this run's sequence number. */
export type CheckTask<T> = (signal: AbortSignal, requestId: number) => Promise<Outcome<T>>;

export type SessionPhase = "idle" | "running" | "done" | "error";

export interface SessionState<T> {
  phase: SessionPhase;
  /** The latest answer that was current when it arrived. Kept while a newer check runs, fails or is cancelled. */
  result: T | null;
  /**
   * True when `result` comes from an earlier check than the latest one
   * started: a newer check is running, failed or was cancelled. The screen
   * must then mark the results as from the previous check.
   */
  fromPrevious: boolean;
  /** When the running check started (ms since the epoch); null when none is running. */
  startedAt: number | null;
  /** The latest check's failure, if it failed. */
  error: CheckError | null;
  /** Set when the latest check was cancelled; cleared by the next start. */
  note: "cancelled" | null;
  /** Sequence number of the latest check started (0 before any). */
  requestId: number;
}

/** How a `start` ended, from the caller's side. */
export type RunEnd = "current" | "dropped";

export interface RunHooks<T> {
  /** Called once with the answer, only if it is still the current request. */
  onResult?: (data: T, requestId: number) => void;
  /** Called once with the failure, only if it is still the current request. */
  onError?: (error: CheckError, requestId: number) => void;
}

export interface CheckSession<T> {
  getState(): SessionState<T>;
  subscribe(listener: () => void): () => void;
  /** Start a check. A running one is aborted and superseded: its reply, if it still comes, is dropped. */
  start(task: CheckTask<T>, hooks?: RunHooks<T>): Promise<RunEnd>;
  /** Abort the running check. The previous results (if any) are current again, with a "cancelled" note. False when nothing ran. */
  cancel(): boolean;
  /** Run the last check again (after a failure or a cancel). Null when there is nothing to retry. */
  retry(): Promise<RunEnd> | null;
  /** Whether there is a check to retry. */
  canRetry(): boolean;
  /** Forget the error and the note, and abort anything running, keeping `result` (e.g. back to the editor). */
  settle(): void;
  /** Abort anything running and drop its reply (the page is closing). */
  dispose(): void;
}

export interface SessionOptions {
  /** Clock, for tests. */
  now?: () => number;
}

export function createCheckSession<T>(options: SessionOptions = {}): CheckSession<T> {
  const now = options.now ?? (() => Date.now());
  let state: SessionState<T> = {
    phase: "idle",
    result: null,
    fromPrevious: false,
    startedAt: null,
    error: null,
    note: null,
    requestId: 0,
  };
  /** The newest sequence number handed out; a reply is current only if it carries this one. */
  let latest = 0;
  let ctrl: AbortController | null = null;
  let last: { task: CheckTask<T>; hooks?: RunHooks<T> } | null = null;
  const listeners = new Set<() => void>();

  const set = (patch: Partial<SessionState<T>>) => {
    state = { ...state, ...patch };
    for (const l of [...listeners]) l();
  };
  const restingPhase = (): SessionPhase => (state.result !== null ? "done" : "idle");

  const start = async (task: CheckTask<T>, hooks?: RunHooks<T>): Promise<RunEnd> => {
    ctrl?.abort(); // supersede: the older request stops, and its id is no longer the latest
    const id = ++latest;
    const mine = new AbortController();
    ctrl = mine;
    last = { task, hooks };
    set({
      phase: "running",
      fromPrevious: state.result !== null,
      startedAt: now(),
      error: null,
      note: null,
      requestId: id,
    });
    let out: Outcome<T>;
    try {
      out = await task(mine.signal, id);
    } catch {
      if (id !== latest || mine.signal.aborted) return "dropped";
      out = { ok: false, error: clientError() };
    }
    // A late reply: cancelled, or overtaken by a newer check. Never shown.
    if (id !== latest || mine.signal.aborted) return "dropped";
    ctrl = null;
    if (out.ok) {
      set({ phase: "done", result: out.data, fromPrevious: false, startedAt: null, error: null });
      hooks?.onResult?.(out.data, id);
    } else {
      set({ phase: "error", fromPrevious: state.result !== null, startedAt: null, error: out.error });
      hooks?.onError?.(out.error, id);
    }
    return "current";
  };

  return {
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    start,
    cancel() {
      if (!ctrl) return false;
      ctrl.abort();
      ctrl = null;
      latest++; // whatever the cancelled request still sends back is stale
      set({ phase: restingPhase(), fromPrevious: state.result !== null, startedAt: null, error: null, note: "cancelled" });
      return true;
    },
    retry() {
      if (!last) return null;
      return start(last.task, last.hooks);
    },
    canRetry: () => last !== null,
    settle() {
      if (ctrl) {
        ctrl.abort();
        ctrl = null;
        latest++;
      }
      set({ phase: restingPhase(), fromPrevious: false, startedAt: null, error: null, note: null });
    },
    dispose() {
      ctrl?.abort();
      ctrl = null;
      latest++;
    },
  };
}

/* ---------- what the screen says while a check runs ---------- */

/** After this long a check is a long one: the status says "Still checking". */
export const STILL_CHECKING_AFTER_MS = 8_000;

/** Elapsed time in words a reader can take in at a glance: "4 s", "1 min 05 s". */
export function elapsedLabel(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  if (total < 60) return `${total} s`;
  const min = Math.floor(total / 60);
  const sec = total % 60;
  return `${min} min ${String(sec).padStart(2, "0")} s`;
}

/** The status line for a running check. `what` is "your text", "your file" or "the document". */
export function progressStatus(elapsedMs: number, what: string, hasPrevious: boolean): string {
  if (elapsedMs < STILL_CHECKING_AFTER_MS) return `Checking ${what}…`;
  return hasPrevious
    ? `Still checking ${what}. A long document can take a minute or two; your previous results stay below until it finishes.`
    : `Still checking ${what}. A long document can take a minute or two.`;
}

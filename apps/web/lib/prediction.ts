/**
 * Word prediction (2026-10-14, CLAUDE.md #1): the pure parts, unit-tested
 * in tests/unit/prediction.test.ts.
 *
 * - The engine counts offsets in Unicode code points (Python indices); a
 *   textarea counts UTF-16 units. Every offset crosses here.
 * - Only a window of text around the cursor is sent: up to 4,000 characters
 *   before it and the rest of its paragraph after it.
 * - Nothing is ever inserted by itself. A candidate is shown; the writer
 *   accepts it with Tab or a click, and only if the text and the cursor are
 *   still exactly as they were when it was asked for.
 * - Stale replies never show: every request has a sequence number and an
 *   AbortController, and a reply is dropped unless it answers the latest one.
 *
 * Nothing here stores or logs text: the window lives in memory for one request.
 */
import type { CompletionCandidate, Format } from "@researchly/contract";
import { buildOffsetMap, codePointLength } from "./segments";

/** The pause in typing before a prediction is asked for. */
export const PREDICTION_DEBOUNCE_MS = 250;
/** How much text before the cursor goes with a request (UTF-16 units). */
export const WINDOW_BEFORE = 4_000;
/** At most this much of the rest of the paragraph after the cursor. */
export const WINDOW_AFTER = 2_000;
/** How many candidates are shown at most. */
export const MAX_SHOWN = 3;
/** After the engine says "too many requests", stay quiet this long. */
export const RATE_LIMIT_PAUSE_MS = 60_000;

const isHigh = (c: number) => c >= 0xd800 && c <= 0xdbff;
const isLow = (c: number) => c >= 0xdc00 && c <= 0xdfff;

/** A UTF-16 index moved off the middle of a surrogate pair (to the pair's start). */
export function snapUtf16(text: string, i: number): number {
  const at = Math.max(0, Math.min(Math.trunc(i), text.length));
  if (at > 0 && at < text.length && isLow(text.charCodeAt(at)) && isHigh(text.charCodeAt(at - 1))) return at - 1;
  return at;
}

/** UTF-16 index → code-point index (what the engine calls an offset). */
export function utf16ToCodePoint(text: string, i: number): number {
  return codePointLength(text.slice(0, snapUtf16(text, i)));
}

/** Code-point index → UTF-16 index (clamped to the string). */
export function codePointToUtf16(text: string, cp: number): number {
  return buildOffsetMap(text).toUtf16(cp);
}

/** What one request sends, and where it sits in the full text. */
export interface PredictionWindow {
  /** The text sent: part of the full text. */
  text: string;
  /** The cursor in `text`, in code points (CompleteRequest.cursor). */
  cursor: number;
  /** Where `text` starts in the full text (UTF-16). */
  from: number;
}

/**
 * The window around the cursor: up to `before` units before it (never
 * splitting a surrogate pair), and after it the rest of its paragraph (up
 * to a blank line), at most `after` units.
 */
export function predictionWindow(full: string, caret: number, before = WINDOW_BEFORE, after = WINDOW_AFTER): PredictionWindow {
  const at = snapUtf16(full, caret);
  let from = Math.max(0, at - before);
  if (from > 0 && isLow(full.charCodeAt(from)) && isHigh(full.charCodeAt(from - 1))) from += 1;
  const blank = full.indexOf("\n\n", at);
  let to = Math.min(blank < 0 ? full.length : blank, at + after);
  to = snapUtf16(full, to);
  const text = full.slice(from, to);
  return { text, cursor: codePointLength(full.slice(from, at)), from };
}

/** The full text with a candidate accepted, and where the caret goes (UTF-16). */
export interface Accepted {
  text: string;
  caret: number;
}

/**
 * Replace the candidate's `[start, end)` (code points in the window) with
 * its text, mapped back to the full text. Null when the candidate does not
 * belong to this window: its `end` must be the cursor it was asked for.
 */
export function acceptCandidate(full: string, win: PredictionWindow, cand: Pick<CompletionCandidate, "text" | "start" | "end">): Accepted | null {
  if (cand.end !== win.cursor || cand.start > cand.end || cand.start < 0 || !cand.text) return null;
  if (full.slice(win.from, win.from + win.text.length) !== win.text) return null;
  const map = buildOffsetMap(win.text);
  const start = win.from + map.toUtf16(cand.start);
  const end = win.from + map.toUtf16(cand.end);
  return { text: full.slice(0, start) + cand.text + full.slice(end), caret: start + cand.text.length };
}

/** The typed part of the word a candidate completes (empty for a next word). */
export function typedPart(win: PredictionWindow, cand: Pick<CompletionCandidate, "start" | "end">): string {
  return Array.from(win.text).slice(cand.start, cand.end).join("");
}

/**
 * What to insert at the cursor to accept a candidate without touching what
 * the writer typed: the candidate's characters after the typed part of the
 * word ("int" + "interval" inserts "erval"). The Word panel uses this:
 * Office JS has no character offsets, so the typed letters stay as typed.
 */
export function remainder(typed: string, candidate: string): string {
  const t = Array.from(typed);
  const c = Array.from(candidate);
  if (t.length > c.length) return "";
  for (let i = 0; i < t.length; i++) if (t[i]!.toLowerCase() !== c[i]!.toLowerCase()) return "";
  return c.slice(t.length).join("");
}

/** What a key does while candidates are shown. Anything else is ordinary typing. */
export type PredictionKey = "accept" | "dismiss" | null;

export function predictionKey(
  e: { key: string; shiftKey?: boolean; altKey?: boolean; ctrlKey?: boolean; metaKey?: boolean; isComposing?: boolean },
  showing: boolean,
): PredictionKey {
  if (!showing || e.isComposing) return null;
  if (e.key === "Escape") return "dismiss";
  // Shift+Tab, Ctrl+Tab and the rest keep their usual meaning (focus moves).
  if (e.key === "Tab" && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) return "accept";
  return null;
}

/** One request's input: the full text and caret as they were (in memory only), and the window sent. */
export interface PredictionSnapshot {
  full: string;
  caret: number;
  window: PredictionWindow;
  format: Format;
}

export function snapshotAt(full: string, caret: number, format: Format): PredictionSnapshot {
  return { full, caret, window: predictionWindow(full, caret), format };
}

/** Candidates on screen, and the snapshot they answer. */
export interface PredictionShown {
  snapshot: PredictionSnapshot;
  candidates: CompletionCandidate[];
}

/** What a request came back with, reduced to what the scheduler needs. */
export type PredictionReply =
  | {
      ok: true;
      status: "ok" | "off" | "masked" | "unavailable";
      candidates: CompletionCandidate[];
      /** What the candidates answer, when the request read it itself (Word reads the cursor's text only once asked). */
      snapshot?: PredictionSnapshot;
    }
  | { ok: false; rateLimited?: boolean };

export interface SchedulerOptions {
  request: (snap: PredictionSnapshot, signal: AbortSignal) => Promise<PredictionReply>;
  onShow: (shown: PredictionShown | null) => void;
  delay?: number;
  now?: () => number;
  setTimer?: (fn: () => void, ms: number) => unknown;
  clearTimer?: (handle: unknown) => void;
}

/**
 * Debounce, abort and sequence for prediction requests.
 *
 * `schedule()` clears what is shown at once (it answered older text), and
 * asks again after a pause. A newer `schedule()` or `cancel()` aborts the
 * request in flight and bumps the sequence, so a late reply is dropped
 * even if the abort came too late to stop it.
 */
export class PredictionScheduler {
  private seq = 0;
  private timer: unknown = null;
  private ctrl: AbortController | null = null;
  private pausedUntil = 0;
  private shown = false;
  /** The snapshot being asked about or shown. */
  private current: PredictionSnapshot | null = null;
  private readonly delay: number;
  private readonly now: () => number;
  private readonly setTimer: (fn: () => void, ms: number) => unknown;
  private readonly clearTimer: (handle: unknown) => void;

  constructor(private readonly opts: SchedulerOptions) {
    this.delay = opts.delay ?? PREDICTION_DEBOUNCE_MS;
    this.now = opts.now ?? (() => Date.now());
    this.setTimer = opts.setTimer ?? ((fn, ms) => setTimeout(fn, ms));
    this.clearTimer = opts.clearTimer ?? ((h) => clearTimeout(h as ReturnType<typeof setTimeout>));
  }

  /** Ask for candidates at this snapshot after the pause. */
  schedule(snap: PredictionSnapshot): void {
    const seq = this.stop();
    if (this.now() < this.pausedUntil) return;
    this.current = snap;
    this.timer = this.setTimer(() => {
      this.timer = null;
      void this.run(snap, seq);
    }, this.delay);
  }

  /** Forget everything pending and hide what is shown. */
  cancel(): void {
    this.stop();
  }

  /**
   * The editor's text or caret is now this: if it is not what the pending
   * or shown candidates were asked for (the caret moved, a click elsewhere),
   * they no longer apply.
   */
  moved(full: string, start: number, end: number): void {
    const snap = this.current;
    if (snap && (start !== end || start !== snap.caret || full !== snap.full)) this.stop();
  }

  private stop(): number {
    this.seq += 1;
    this.current = null;
    if (this.timer !== null) this.clearTimer(this.timer);
    this.timer = null;
    this.ctrl?.abort();
    this.ctrl = null;
    this.show(null);
    return this.seq;
  }

  private show(shown: PredictionShown | null): void {
    if (!shown && !this.shown) return;
    this.shown = shown !== null;
    this.opts.onShow(shown);
  }

  private async run(snap: PredictionSnapshot, seq: number): Promise<void> {
    const ctrl = new AbortController();
    this.ctrl = ctrl;
    let reply: PredictionReply;
    try {
      reply = await this.opts.request(snap, ctrl.signal);
    } catch {
      return; // aborted, or the network failed: nothing to offer
    }
    if (seq !== this.seq || ctrl.signal.aborted) return; // an answer to older text
    this.ctrl = null;
    if (!reply.ok) {
      if (reply.rateLimited) this.pausedUntil = this.now() + RATE_LIMIT_PAUSE_MS;
      this.current = null;
      return;
    }
    const candidates = reply.status === "ok" ? reply.candidates.slice(0, MAX_SHOWN) : [];
    if (candidates.length > 0) this.show({ snapshot: reply.snapshot ?? snap, candidates });
    else this.current = null;
  }
}

/** The switch: this session's choice, else the account's (signed in), else this browser's, else on. */
export function resolvePrediction(p: { chosen: boolean | null; account: boolean | null; stored: boolean | null; signedIn: boolean }): boolean {
  return p.chosen ?? (p.signedIn ? p.account : null) ?? p.stored ?? true;
}

/** The live region's words for the candidates on screen. */
export function predictionAnnouncement(candidates: readonly Pick<CompletionCandidate, "text">[], how = "Tab to accept."): string {
  if (candidates.length === 0) return "";
  const [first, ...rest] = candidates;
  const more = rest.length ? ` Also: ${rest.map((c) => c.text).join(", ")}.` : "";
  return `Suggested: ${first!.text}. ${how}${more}`;
}

/**
 * A candidate as the Word panel offers it: the writer's typed letters stay
 * as typed and only the rest is inserted at the cursor. `label` is what the
 * word will read once inserted. Null when the candidate does not continue
 * what was typed.
 */
export function wordInsertion(win: PredictionWindow, cand: Pick<CompletionCandidate, "text" | "start" | "end">): { label: string; insertion: string } | null {
  if (cand.end !== win.cursor || cand.start > cand.end) return null;
  const typed = typedPart(win, cand);
  const insertion = remainder(typed, cand.text);
  return insertion ? { label: typed + insertion, insertion } : null;
}

/**
 * Underlines while writing (S4d R5): the loop, without React or the DOM.
 *
 * The editor tells the session what the text is (`setDocument`) and when
 * the writer changed it (`edit`). After a pause (1.5 s) the session sends
 * the paragraphs it has no answer for, nearest the caret first, with a
 * revision number, one request at a time; edits made meanwhile are
 * coalesced into the next request. Answers are kept by paragraph key (a
 * hash of heading and text), so an unchanged paragraph is never sent again
 * and an undo brings its underlines straight back.
 *
 * Stale answers never paint: a reply is taken only for paragraphs whose key
 * is still in the text (the words did not change while it was in flight),
 * a reply from before an options change is dropped whole, and the six
 * states (lib/check-state.ts) ignore a reply older than the latest edit.
 * A failure goes offline and retries after 2, 4, 8, 16 and 30 s.
 *
 * Nothing here is stored anywhere: the cache lives in this object, in
 * memory, and goes with the page.
 */
import type { CheckParagraphsRequest, CheckParagraphsResponse, DocumentType, Format, Spelling, Suggestion, TierHealth } from "@researchly/contract";
import { INITIAL_STATUS, reduceCheckState, type CheckEvent, type CheckStatus } from "./check-state";
import type { CheckResult } from "./engine";
import { LIVE_PAUSE_MS, partialReason } from "./live-check";
import {
  canSend,
  carryItems,
  fromLive,
  isLiveFormat,
  itemsFromFullCheck,
  nextBatch,
  paragraphId,
  paragraphKey,
  splitParagraphs,
  textToSend,
  updateParagraphs,
  visibleItems,
  type LiveDocument,
  type LiveFormat,
  type LiveItem,
  type LiveParagraph,
} from "./live-paragraphs";

/** Wait this long after the last keystroke before checking (docs/inline-review-design.md §1.8); shared with Word (R4). */
export { LIVE_PAUSE_MS, partialReason };

export type LiveCheckFn = (request: CheckParagraphsRequest, signal: AbortSignal) => Promise<CheckResult<CheckParagraphsResponse>>;

export interface LiveClock {
  now(): number;
  setTimeout(fn: () => void, ms: number): unknown;
  clearTimeout(id: unknown): void;
}

const realClock: LiveClock = {
  now: () => Date.now(),
  setTimeout: (fn, ms) => setTimeout(fn, ms),
  clearTimeout: (id) => clearTimeout(id as ReturnType<typeof setTimeout>),
};

/** The options a live check is asked with; a change of type or spelling makes every answer out of date. */
export interface LiveOptionsState {
  documentType: DocumentType;
  spelling: Spelling | null;
  showPreferences: boolean;
}

interface Entry {
  items: LiveItem[];
  /** False for a full check's answer given without Preferences: asked again if the writer shows them. */
  withPrefs: boolean;
}

export interface LiveSnapshot {
  /** The six states, for StatusMark. */
  status: CheckStatus;
  /** Whether underlines are drawn at all (switch on, plain text or Markdown, the editor on screen). */
  enabled: boolean;
  doc: LiveDocument;
  /** The underlines a paragraph shows (answer, or carried across an edit), already filtered for the writer. */
  itemsFor: (p: LiveParagraph) => readonly LiveItem[];
  /**
   * More paragraphs changed at once (a long paste) than one live request
   * takes: those nearest the caret were checked, and Check covers the rest.
   * Live checks never sweep the whole text (the engine's live rate limit).
   */
  leftToCheck: boolean;
  /** Changes whenever anything drawn may have changed. */
  version: number;
}

const EMPTY: readonly LiveItem[] = [];
const MAX_CACHE = 4000;


export class LiveSession {
  private readonly check: LiveCheckFn;
  private readonly clock: LiveClock;
  private readonly pauseMs: number;
  private listeners = new Set<() => void>();
  private snapshot: LiveSnapshot | null = null;
  private version = 0;

  private wanted = false;
  private format: LiveFormat | null = null;
  private text = "";
  private doc: LiveDocument = { paragraphs: [], headings: [] };
  private keys = new Set<string>();
  /** Keys new in the latest text (what the writer's last change touched). */
  private changed: string[] = [];
  /** Paragraphs the writer changed and no answer covers yet: the only ones ever sent. */
  private dirty = new Set<string>();
  private leftToCheck = false;
  private cache = new Map<string, Entry>();
  private provisional = new Map<string, LiveItem[]>();
  private dismissed = new Set<string>();
  private filtered = new WeakMap<readonly LiveItem[], readonly LiveItem[]>();
  private status: CheckStatus = INITIAL_STATUS;
  private partial = { on: false, reason: "" };
  private revision = 0;
  private lastEditAt = Number.NEGATIVE_INFINITY;
  private active = false;
  private fullRunning = false;
  private timer: unknown = null;
  private retryTimer: unknown = null;
  private epoch = 0;
  private opts: LiveOptionsState = { documentType: "auto", spelling: null, showPreferences: false };
  private inflight: { revision: number; epoch: number; sent: Map<string, string>; controller: AbortController } | null = null;
  private caret: () => number = () => 0;
  /** Keys already computed, by heading then text: on a keystroke only the edited paragraph is hashed again. */
  private keyMemo = new Map<string, Map<string, string>>();
  private keyMemoSize = 0;
  private documentWide: (ruleId: string) => boolean = () => false;
  private disposed = false;

  constructor(check: LiveCheckFn, clock: LiveClock = realClock, pauseMs = LIVE_PAUSE_MS) {
    this.check = check;
    this.clock = clock;
    this.pauseMs = pauseMs;
  }

  /* ---------- React's external store ---------- */

  subscribe = (fn: () => void): (() => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  getSnapshot = (): LiveSnapshot => {
    if (!this.snapshot) {
      const enabled = this.enabled;
      this.snapshot = {
        status: this.status,
        enabled,
        doc: this.doc,
        itemsFor: this.itemsFor,
        leftToCheck: this.leftToCheck,
        version: this.version,
      };
    }
    return this.snapshot;
  };

  private emit() {
    this.version++;
    this.snapshot = null;
    for (const fn of this.listeners) fn();
  }

  private get enabled(): boolean {
    return this.wanted && this.format !== null;
  }

  private itemsFor = (p: LiveParagraph): readonly LiveItem[] => {
    const raw = this.cache.get(p.key)?.items ?? this.provisional.get(p.key);
    if (!raw || raw.length === 0) return EMPTY;
    let shown = this.filtered.get(raw);
    if (!shown) {
      shown = visibleItems(raw, this.opts.showPreferences, this.dismissed);
      if (shown.length === 0) shown = EMPTY;
      this.filtered.set(raw, shown);
    }
    return shown;
  };

  /** Underlines currently drawn, in document order (for the list, the shortcut and the count). */
  drawn(): { paragraph: LiveParagraph; item: LiveItem }[] {
    const out: { paragraph: LiveParagraph; item: LiveItem }[] = [];
    for (const p of this.doc.paragraphs) {
      for (const item of [...this.itemsFor(p)].sort((a, b) => a.begin - b.begin || a.end - b.end)) out.push({ paragraph: p, item });
    }
    return out;
  }

  /** How many underlines are drawn now. */
  drawnCount(): number {
    return this.count();
  }

  private count(): number {
    let n = 0;
    for (const p of this.doc.paragraphs) n += this.itemsFor(p).length;
    return n;
  }

  private dispatch(event: CheckEvent) {
    const next = reduceCheckState(this.status, event);
    if (next !== this.status) {
      this.status = next;
      this.emit();
    }
  }

  private keyOf = (heading: string, text: string): string => {
    let byText = this.keyMemo.get(heading);
    if (!byText) {
      byText = new Map();
      this.keyMemo.set(heading, byText);
    }
    let key = byText.get(text);
    if (key === undefined) {
      if (this.keyMemoSize > MAX_CACHE) {
        this.keyMemo = new Map([[heading, (byText = new Map())]]);
        this.keyMemoSize = 0;
      }
      key = paragraphKey(heading, text);
      byText.set(text, key);
      this.keyMemoSize++;
    }
    return key;
  };

  /* ---------- inputs ---------- */

  /** Where the caret is, so the paragraph being written is checked first. */
  setCaretSource(fn: () => number) {
    this.caret = fn;
  }

  /** The editor's text and format, after every change (typed, pasted, loaded or applied). */
  setDocument(text: string, format: Format) {
    const live = isLiveFormat(format) ? format : null;
    if (text === this.text && live === this.format) return;
    const before = this.doc;
    const beforeText = this.text;
    const formatChanged = live !== this.format;
    this.text = text;
    this.format = live;
    // Switched off, the text is not even split: typing costs nothing extra. A keystroke inside a
    // paragraph moves the offsets after it instead of splitting the whole text again.
    this.doc =
      live && this.wanted
        ? ((!formatChanged && updateParagraphs(before, beforeText, text, live, this.keyOf)) || splitParagraphs(text, live, this.keyOf))
        : { paragraphs: [], headings: [] };
    const was = this.keys;
    this.keys = new Set(this.doc.paragraphs.map((p) => p.key));
    this.changed = this.doc.paragraphs.filter((p) => !was.has(p.key)).map((p) => p.key);
    if (this.doc.paragraphs.length === 0) this.leftToCheck = false;
    if (formatChanged) {
      this.provisional.clear();
    } else {
      this.carry(before);
    }
    if (!this.enabled) {
      this.stop();
      if (this.status.state !== "hidden") this.dispatch({ type: this.wanted ? "leave" : "pause" });
    } else if (this.doc.paragraphs.length === 0 && this.status.state !== "hidden") {
      this.dispatch({ type: "leave" });
    }
    this.emit();
    if (formatChanged && this.enabled && this.active) this.schedule(0);
  }

  /**
   * Underlines of an edited paragraph that still sit on unchanged words
   * stay in place (moved with the edit) until the next answer. Paired by
   * position: the paragraph that starts where an old one started, or ends
   * where it ended.
   */
  private carry(before: LiveDocument) {
    const next = new Map<string, LiveItem[]>();
    const byStart = new Map(before.paragraphs.map((p) => [p.start, p] as const));
    const shift = this.doc.paragraphs.length === before.paragraphs.length;
    for (const p of this.doc.paragraphs) {
      if (this.cache.has(p.key)) continue;
      const kept = this.provisional.get(p.key);
      if (kept) {
        next.set(p.key, kept);
        continue;
      }
      const old = byStart.get(p.start) ?? (shift ? before.paragraphs[p.index] : undefined);
      if (!old || old.heading !== p.heading) continue;
      const items = this.cache.get(old.key)?.items ?? this.provisional.get(old.key);
      if (!items || items.length === 0) continue;
      const moved = carryItems(items, old.text, p.text);
      if (moved.length) next.set(p.key, moved);
    }
    this.provisional = next;
  }

  /** The writer typed, pasted, deleted or applied a revision: check after the pause. */
  edit(delayMs = this.pauseMs) {
    this.revision++;
    this.lastEditAt = this.clock.now() - (this.pauseMs - delayMs);
    this.active = true;
    if (!this.enabled) return;
    for (const key of this.changed) this.dirty.add(key);
    this.changed = [];
    this.schedule(delayMs);
  }

  /** The "Underlines while writing" switch. */
  setEnabled(on: boolean) {
    if (on === this.wanted) return;
    this.wanted = on;
    if (on && this.format) {
      this.doc = splitParagraphs(this.text, this.format, this.keyOf);
      this.keys = new Set(this.doc.paragraphs.map((p) => p.key));
      this.changed = [];
      this.provisional.clear();
    }
    if (!this.enabled) {
      this.stop();
      this.dispatch({ type: on ? "leave" : "pause" });
      this.emit();
      return;
    }
    // No sweep of what is already on screen: the next edit is checked, and Check covers the rest.
    this.emit();
  }

  setOptions(o: LiveOptionsState) {
    const stale = o.documentType !== this.opts.documentType || o.spelling !== this.opts.spelling;
    const prefsChanged = o.showPreferences !== this.opts.showPreferences;
    this.opts = o;
    if (stale) {
      // Ask again only for what was answered or asked for (never the whole text): one request, nearest the caret.
      for (const key of this.cache.keys()) if (this.keys.has(key)) this.dirty.add(key);
      if (this.inflight) for (const key of this.inflight.sent.values()) this.dirty.add(key);
      this.epoch++;
      this.inflight?.controller.abort();
      this.inflight = null;
      this.cache.clear();
      this.provisional.clear();
    }
    if (prefsChanged) this.filtered = new WeakMap();
    if (!stale && !prefsChanged) return;
    this.emit();
    if (this.enabled && this.active && stale) this.schedule(0);
    else this.settle();
  }

  /** Which rules read the whole document (the engine's registry, when it has arrived): never underlined. */
  setDocumentWide(fn: (ruleId: string) => boolean) {
    this.documentWide = fn;
  }

  /** "Not an issue here" from an underline's card: hidden until the paragraph changes, for this page only. */
  dismiss(id: string) {
    this.dismissed.add(id);
    this.filtered = new WeakMap();
    this.emit();
    this.settle();
  }

  /** A full check is running: say so, and let it answer for the whole text. */
  fullCheckStarted() {
    this.fullRunning = true;
    this.active = true;
    this.clearTimer();
    if (this.enabled) this.dispatch({ type: "edit", revision: this.revision });
  }

  /**
   * A full check answered for `text`: its sentence-level suggestions become
   * the underlines of those paragraphs, so the two agree. `options` are the
   * live options from now on (the check's guessed article type included).
   */
  fullCheckAnswered(
    text: string,
    format: Format,
    suggestions: readonly Suggestion[],
    options: LiveOptionsState,
    health?: readonly TierHealth[],
  ) {
    this.fullRunning = false;
    this.setOptions(options);
    if (isLiveFormat(format)) {
      const seeded = itemsFromFullCheck(text, format, suggestions, this.documentWide);
      for (const [key, items] of seeded) {
        this.cache.delete(key);
        this.cache.set(key, { items, withPrefs: options.showPreferences });
        this.provisional.delete(key);
      }
      this.prune();
    }
    const reason = partialReason(health ?? []);
    this.partial = { on: reason !== "", reason };
    this.leftToCheck = false;
    this.filtered = new WeakMap();
    this.emit();
    if (!this.enabled) return;
    if (this.todo().length) this.schedule(0);
    else this.dispatch({ type: "reply", revision: this.revision, count: this.count(), partial: this.partial.on, reason: this.partial.reason });
  }

  /** A full check failed or was cancelled: the underlines go back to their own loop. */
  fullCheckEnded() {
    if (!this.fullRunning) return;
    this.fullRunning = false;
    if (!this.enabled) return;
    if (this.todo().length) this.schedule(0);
    else this.settle(true);
  }

  /** "Try now" while offline. */
  retryNow() {
    if (!this.enabled) return;
    this.clearRetry();
    this.dispatch({ type: "retry", revision: this.revision });
    this.lastEditAt = Number.NEGATIVE_INFINITY;
    this.send();
  }

  dispose() {
    this.disposed = true;
    this.stop();
    this.listeners.clear();
  }

  /* ---------- the loop ---------- */

  private needs(p: LiveParagraph): boolean {
    const e = this.cache.get(p.key);
    return !e || (this.opts.showPreferences && !e.withPrefs);
  }

  private todo(): LiveParagraph[] {
    if (this.dirty.size === 0) return [];
    return this.doc.paragraphs.filter((p) => this.dirty.has(p.key) && canSend(p) && this.needs(p));
  }

  private clearTimer() {
    if (this.timer !== null) this.clock.clearTimeout(this.timer);
    this.timer = null;
  }

  private clearRetry() {
    if (this.retryTimer !== null) this.clock.clearTimeout(this.retryTimer);
    this.retryTimer = null;
  }

  private stop() {
    this.clearTimer();
    this.clearRetry();
    if (this.inflight) {
      this.inflight.controller.abort();
      this.inflight = null;
    }
  }

  private schedule(delayMs: number) {
    if (this.disposed) return;
    this.clearTimer();
    this.timer = this.clock.setTimeout(() => {
      this.timer = null;
      this.send();
    }, Math.max(0, delayMs));
  }

  /** Nothing in flight and nothing to send: the state follows what is drawn. */
  private settle(force = false) {
    if (!this.enabled || this.inflight || this.fullRunning) return;
    if (this.status.state === "offline" && !force) return;
    if (this.status.state === "hidden" && !force) return;
    if (this.todo().length) return;
    this.dispatch({ type: "reply", revision: this.revision, count: this.count(), partial: this.partial.on, reason: this.partial.reason });
  }

  private send() {
    if (!this.enabled || this.inflight || this.fullRunning || this.disposed) return;
    const wait = this.lastEditAt + this.pauseMs - this.clock.now();
    if (wait > 0) {
      this.schedule(wait);
      return;
    }
    const todo = this.todo();
    if (todo.length === 0) {
      if (this.doc.paragraphs.length === 0) return;
      this.clearRetry();
      this.dispatch({ type: "reply", revision: this.revision, count: this.count(), partial: this.partial.on, reason: this.partial.reason });
      return;
    }
    const format = this.format!;
    const batch = nextBatch(todo, this.caret());
    // One request per pause: what did not fit (a long paste) is left to Check, never swept live.
    if (todo.some((p) => !batch.includes(p) && !batch.some((b) => b.key === p.key))) {
      this.leftToCheck = true;
      this.emit();
    }
    this.dirty.clear();
    const revision = this.revision;
    const request: CheckParagraphsRequest = {
      revision,
      paragraphs: batch.map((p) => ({ id: paragraphId(p.key), text: textToSend(p, format), heading: p.heading, style: "" })),
      options: {
        // Preferences always come back and are filtered here, so the switch never needs a new request.
        show_preferences: true,
        document_type: this.opts.documentType,
        ...(this.opts.spelling ? { spelling: this.opts.spelling } : {}),
        review: false,
        narrative: false,
      },
    };
    const sent = new Map(batch.map((p) => [paragraphId(p.key), p.key] as const));
    const controller = new AbortController();
    const flight = { revision, epoch: this.epoch, sent, controller };
    this.inflight = flight;
    if (this.status.state !== "offline") this.dispatch({ type: "edit", revision });
    this.check(request, controller.signal).then(
      (result) => this.answered(flight, result),
      () => {
        // Aborted (superseded): the next request carries the work.
        if (this.inflight === flight) this.inflight = null;
      },
    );
  }

  private answered(flight: NonNullable<LiveSession["inflight"]>, result: CheckResult<CheckParagraphsResponse>) {
    if (this.inflight !== flight || flight.epoch !== this.epoch || this.disposed) return; // superseded
    this.inflight = null;
    if (!result.ok) {
      // Asked again on the retry, unless their words changed meanwhile.
      for (const key of flight.sent.values()) if (this.keys.has(key)) this.dirty.add(key);
      this.dispatch({ type: "failure", revision: flight.revision, reason: result.error.title });
      const wait = this.status.state === "offline" ? this.status.retryInMs : null;
      if (wait !== null) {
        this.clearRetry();
        this.retryTimer = this.clock.setTimeout(() => {
          this.retryTimer = null;
          this.dispatch({ type: "retry", revision: this.revision });
          this.send();
        }, wait);
      } else {
        this.schedule(0);
      }
      return;
    }
    const data = result.data;
    if (data.revision === flight.revision) {
      for (const para of data.paragraphs) {
        const key = flight.sent.get(para.id);
        // Stale: the paragraph's words changed while the request was out.
        if (!key || !this.keys.has(key)) continue;
        const p = this.doc.paragraphs.find((x) => x.key === key)!;
        const items: LiveItem[] = [];
        for (const s of para.suggestions) {
          const item = fromLive(s, p.text);
          if (item) items.push(item);
        }
        this.cache.delete(key);
        this.cache.set(key, { items, withPrefs: true });
        this.provisional.delete(key);
      }
      this.prune();
      const reason = data.state === "partial" ? partialReason(data.health) || "Part of the checking was off" : "";
      this.partial = { on: data.state === "partial", reason };
    }
    this.clearRetry();
    this.emit();
    const more = this.todo().length > 0;
    if (more && flight.revision === this.revision) {
      // Still checking the rest of this revision: stay "checking", send the next batch now.
      if (this.status.state === "offline") this.dispatch({ type: "edit", revision: this.revision });
      this.schedule(0);
      return;
    }
    this.dispatch({ type: "reply", revision: flight.revision, count: this.count(), partial: this.partial.on, reason: this.partial.reason });
    if (more) this.schedule(this.lastEditAt + this.pauseMs - this.clock.now());
  }

  /** Forget the oldest answers beyond a few thousand (Map order is insertion order). */
  private prune() {
    if (this.cache.size <= MAX_CACHE) return;
    for (const key of this.cache.keys()) {
      if (this.cache.size <= MAX_CACHE) break;
      if (!this.keys.has(key)) this.cache.delete(key);
    }
  }
}

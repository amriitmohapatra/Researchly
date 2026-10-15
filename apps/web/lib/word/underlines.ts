/**
 * The Word pane's underline controller (S4d R4): it watches the document,
 * waits for a pause, sends the paragraphs that changed to the live check,
 * drops replies that no longer fit, and keeps Word's underlines in step.
 *
 * No React here (the pane wires it, tests drive it with the fake Office and
 * fake timers). Nothing is stored: it holds the text it checked in memory,
 * as the pane does, and forgets it when the pane closes.
 *
 * Rules it keeps:
 * - one live request in flight at a time (so never two for one paragraph);
 * - at most 50 paragraphs and 20,000 characters per request;
 * - a reply is painted only if it answers the revision sent, nothing reset
 *   the controller meanwhile, and each paragraph still reads as sent;
 * - the first refused insertion means this Word cannot draw underlines
 *   (no Microsoft 365): it stops, says why, and the pane works as before.
 */
import type { CheckParagraphsRequest, CheckParagraphsResponse, DocumentType, LiveOptions, Spelling, WordSuggestion } from "@researchly/contract";
import type { CheckEvent } from "../check-state";
import { retryDelayMs } from "../check-state";
import type { CheckResult } from "../engine";
import { isCurrentReply, LIVE_PAUSE_MS, liveHeading, partialReason, takeBatch } from "../live-check";
import { isDocumentWide, type ScopeMap } from "../scope";
import {
  actOnAnnotation,
  clearUnderlines,
  listen,
  paintParagraphs,
  readParagraphText,
  readSnapshot,
  underlineSupport,
  type PaintItem,
  type UnderlineSupport,
} from "./annotations";
import {
  changedParagraphs,
  goneKeys,
  isLiveCheckable,
  liveToWordSuggestion,
  paragraphUnderlines,
  signature,
  type LiveEntry,
  type SnapshotParagraph,
} from "./live";
import type { OfficeApi } from "./office";

export type Unavailable =
  /** WordApi 1.7 is not there (an older Word). */
  | "unsupported"
  /** Word reports 1.7 but refused to draw (a one-time-purchase Word, no Microsoft 365). */
  | "refused";

/** What the live check is asked to respect: the same choices as the full check. */
export interface LiveChoices {
  showPreferences: boolean;
  documentType: DocumentType;
  spelling: Spelling | null;
  disabledRules: string[];
}

export interface UnderlineEvents {
  /** The live paragraphs' cards changed. */
  onEntries(entries: ReadonlyMap<string, LiveEntry>): void;
  /** Which suggestions have an underline in the document now. */
  onUnderlined(ids: ReadonlySet<string>): void;
  /** A state change for the pane's status mark (lib/check-state.ts). */
  onState(event: CheckEvent): void;
  /** Underlines cannot be drawn in this Word: off for the session. */
  onUnavailable(reason: Unavailable): void;
  /** The writer clicked or hovered an underline: show its card. */
  onReveal(suggestionId: string, how: "click" | "hover"): void;
  /** The popup's Accept with the revision chosen. */
  onPopupAccept(suggestionId: string, revision: string): void;
  /** The popup's Reject: the writer says it is not an issue. */
  onPopupReject(suggestionId: string): void;
}

export interface UnderlineDeps {
  api: OfficeApi;
  /** POST /v1/check-paragraphs (lib/live-check.ts), bound to the chosen engine and sign-in. */
  send(request: CheckParagraphsRequest, signal: AbortSignal): Promise<CheckResult<CheckParagraphsResponse>>;
  /** GET /v1/health on the chosen engine: is it back? (after a failure with nothing left to send). */
  probe(): Promise<boolean>;
  events: UnderlineEvents;
  /** Is this suggestion dismissed ("Not an issue here")? It is then not underlined. */
  dismissed(key: string, s: WordSuggestion): boolean;
  pauseMs?: number;
}

interface Painted {
  key: string;
  suggestionId: string;
}

export class UnderlineController {
  private readonly d: UnderlineDeps;
  private support: UnderlineSupport = { annotations: false, popups: false, paragraphEvents: false };
  private keyed = false;
  private started = false;
  private ready = false;
  private enabled = false;
  private live = true;
  private stopped = false;
  private unavailable: Unavailable | null = null;
  private popups = false;
  private inserted = false;

  private choices: LiveChoices = { showPreferences: false, documentType: "auto", spelling: null, disabledRules: [] };
  private scopes: ScopeMap | null = null;

  /** Bumped by anything that makes an in-flight reply meaningless: a full check, a setting, switching off. */
  private generation = 0;
  private revision = 0;
  private failures = 0;
  private inFlight: AbortController | null = null;
  private pending = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;

  /** Per paragraph key: the signature last checked (text, style, section). */
  private known = new Map<string, string>();
  private entries = new Map<string, LiveEntry>();
  /** Our annotation ids → which suggestion they draw. */
  private ours = new Map<string, Painted>();

  constructor(deps: UnderlineDeps) {
    this.d = deps;
  }

  /* ---------- lifecycle ---------- */

  /**
   * Find out what this Word can do and start listening. `enabled`: the
   * writer's "Live underlines" choice; `live`: the engine answers live
   * checks (the hosted one; "This computer" underlines after a full check only).
   */
  async start(opts: { enabled: boolean; live: boolean }): Promise<Unavailable | null> {
    if (this.started) return this.unavailable;
    this.started = true;
    this.enabled = opts.enabled;
    this.live = opts.live;
    this.support = underlineSupport(this.d.api);
    this.popups = this.support.popups;
    this.keyed = this.support.paragraphEvents;
    if (!this.support.annotations) {
      this.unavailable = "unsupported";
      this.d.events.onUnavailable("unsupported");
      return this.unavailable;
    }
    await listen(this.d.api, this.support, {
      onClick: (id) => this.reveal(id, "click"),
      onHover: (id) => this.reveal(id, "hover"),
      onPopup: (id, action, suggestion) => this.popup(id, action, suggestion),
      onEdit: () => this.noteEdit(),
    });
    if (this.stopped) return null;
    // Choices made while Word was being asked were recorded; act on them now.
    this.ready = true;
    const want = this.enabled;
    this.enabled = false;
    this.setEnabled(want);
    return null;
  }

  /** The pane is closing: no more timers or requests. Underlines stay until the document closes (Word does not save them). */
  dispose(): void {
    this.stopped = true;
    this.clearTimers();
    this.inFlight?.abort();
  }

  get isOn(): boolean {
    return this.ready && this.enabled && this.unavailable === null && !this.stopped;
  }

  /** Whether paragraphs carry Word's own ids (WordApi 1.6). */
  get usesParagraphIds(): boolean {
    return this.keyed;
  }

  /** Whether underlines follow typing (the engine answers live checks). */
  get isLive(): boolean {
    return this.isOn && this.live;
  }

  /** Switch underlines on or off (the pane's "Live underlines"). Off removes ours from the document. */
  setEnabled(on: boolean): void {
    if (this.unavailable || this.stopped) return;
    if (!this.ready) {
      this.enabled = on;
      return;
    }
    if (!on) {
      const was = this.enabled;
      this.enabled = false;
      this.reset();
      if (was) this.d.events.onState({ type: "pause" });
      return;
    }
    const was = this.enabled;
    this.enabled = true;
    if (!was) {
      this.known.clear();
      if (this.live) this.schedule(0);
    }
  }

  /** The engine changed: whether it answers live checks. Everything is checked again. */
  setLive(live: boolean): void {
    if (this.live === live) return;
    this.live = live;
    if (!this.ready) return;
    this.reset();
    if (this.isOn && live) this.schedule(0);
  }

  /** The check's choices changed (preferences, type, spelling, muted rules): draw everything again. */
  setChoices(next: LiveChoices): void {
    const same =
      next.showPreferences === this.choices.showPreferences &&
      next.documentType === this.choices.documentType &&
      next.spelling === this.choices.spelling &&
      next.disabledRules.join(",") === this.choices.disabledRules.join(",");
    this.choices = { ...next, disabledRules: [...next.disabledRules] };
    if (same || !this.ready) return;
    if (this.isLive) {
      this.reset();
      this.schedule(0);
    }
  }

  setScopes(scopes: ScopeMap | null): void {
    this.scopes = scopes;
  }

  /** Something may have changed in the document: check after the pause. */
  noteEdit(): void {
    if (!this.isLive) return;
    this.schedule(this.d.pauseMs ?? LIVE_PAUSE_MS);
  }

  /** Check these paragraphs again soon (a dismissal undone, an Apply that did not go through). */
  recheck(keys: Iterable<string>): void {
    for (const k of keys) this.known.delete(k);
    if (this.isLive) this.schedule(0);
  }

  /** The next revision, for a full check (an edit as far as the states go). */
  nextRevision(): number {
    this.revision += 1;
    return this.revision;
  }

  /* ---------- the full check ---------- */

  /**
   * Draw the full check's sentence-level findings (Check document). Live
   * results give way to it; document-wide findings stay in the pane.
   * `paragraphs` are exactly what the check read.
   */
  async paintFullCheck(paragraphs: readonly SnapshotParagraph[], suggestions: readonly WordSuggestion[]): Promise<void> {
    if (!this.isOn) return;
    this.generation += 1;
    const gen = this.generation;
    this.clearTimers();
    this.inFlight?.abort();
    this.inFlight = null;
    this.pending = false;
    await this.removeAll();
    if (gen !== this.generation) return;
    this.entries.clear();
    this.d.events.onEntries(this.entries);
    this.known = new Map(paragraphs.map((p) => [p.key, signature(p)]));
    const byParagraph = new Map<number, WordSuggestion[]>();
    for (const s of suggestions) {
      if (isDocumentWide(s.rule_id, this.scopes)) continue;
      const list = byParagraph.get(s.location.paragraph) ?? [];
      list.push(s);
      byParagraph.set(s.location.paragraph, list);
    }
    const items: PaintItem[] = [];
    for (const [index, cards] of byParagraph) {
      const p = paragraphs[index];
      if (!p) continue;
      items.push({ key: p.key, index, text: p.text, underlines: this.underlines(p.key, cards, p.text) });
    }
    await this.paint(items, gen);
  }

  /* ---------- acting on one underline ---------- */

  /** The annotation drawing this suggestion, if any. */
  annotationFor(suggestionId: string): string | null {
    for (const [id, p] of this.ours) if (p.suggestionId === suggestionId) return id;
    return null;
  }

  /** Mark the underline accepted (before the pane applies the revision). False when there is none or Word refused. */
  async accept(suggestionId: string): Promise<boolean> {
    const id = this.annotationFor(suggestionId);
    if (!id) return false;
    const ok = await actOnAnnotation(this.d.api, id, "accept");
    this.forget(id);
    return ok;
  }

  /** "Not an issue here": reject the underline and take it away. */
  async dismiss(suggestionId: string): Promise<void> {
    const id = this.annotationFor(suggestionId);
    if (!id) return;
    await actOnAnnotation(this.d.api, id, "reject");
    await actOnAnnotation(this.d.api, id, "delete");
    this.forget(id);
  }

  /** The paragraph's text now, located by key (or position without paragraph ids). */
  currentText(key: string, index: number): Promise<string | null> {
    return readParagraphText(this.d.api, key, index, this.keyed);
  }

  /* ---------- internals ---------- */

  private forget(annotationId: string) {
    this.ours.delete(annotationId);
    this.d.events.onUnderlined(this.underlinedIds());
  }

  private underlinedIds(): Set<string> {
    return new Set([...this.ours.values()].map((p) => p.suggestionId));
  }

  private reveal(annotationId: string, how: "click" | "hover") {
    const p = this.ours.get(annotationId);
    if (p) this.d.events.onReveal(p.suggestionId, how);
  }

  private popup(annotationId: string, action: string, suggestion: string | null) {
    const p = this.ours.get(annotationId);
    if (!p) return;
    this.ours.delete(annotationId);
    this.d.events.onUnderlined(this.underlinedIds());
    if (action === "Accept" && suggestion !== null) this.d.events.onPopupAccept(p.suggestionId, suggestion);
    else if (action !== "Accept") {
      // Word has marked it rejected; take it out of the document too.
      void actOnAnnotation(this.d.api, annotationId, "delete");
      this.d.events.onPopupReject(p.suggestionId);
    }
  }

  private underlines(key: string, cards: readonly WordSuggestion[], text: string) {
    return paragraphUnderlines(cards, text, {
      showPreferences: this.choices.showPreferences,
      scopes: this.scopes,
      dismissed: (s) => this.d.dismissed(key, s),
    });
  }

  private clearTimers() {
    if (this.timer) clearTimeout(this.timer);
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.timer = null;
    this.retryTimer = null;
  }

  /** Forget everything live and take our underlines out of the document. */
  private reset() {
    this.generation += 1;
    this.clearTimers();
    this.inFlight?.abort();
    this.inFlight = null;
    this.pending = false;
    this.failures = 0;
    this.known.clear();
    if (this.entries.size > 0) {
      this.entries.clear();
      this.d.events.onEntries(this.entries);
    }
    void this.removeAll();
  }

  private async removeAll() {
    const ids = new Set(this.ours.keys());
    this.ours.clear();
    this.d.events.onUnderlined(new Set());
    await clearUnderlines(this.d.api, ids);
  }

  private schedule(ms: number) {
    if (this.stopped) return;
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.round();
    }, ms);
  }

  private options(): LiveOptions {
    return {
      show_preferences: this.choices.showPreferences,
      document_type: this.choices.documentType,
      disabled_rules: this.choices.disabledRules,
      review: false,
      narrative: false,
      ...(this.choices.spelling ? { spelling: this.choices.spelling } : {}),
    };
  }

  /** One round: read, find what changed, send one batch, paint what still fits. */
  private async round(): Promise<void> {
    if (!this.isLive) return;
    if (this.inFlight) {
      this.pending = true;
      return;
    }
    const gen = this.generation;
    let snapshot: SnapshotParagraph[];
    try {
      snapshot = await readSnapshot(this.d.api, this.keyed);
    } catch {
      return; // Word was busy; the next edit tries again
    }
    if (gen !== this.generation || !this.isLive) return;

    // Paragraphs that went away take their cards with them (their underlines went with the text).
    const gone = goneKeys(snapshot, this.entries.keys());
    for (const k of gone) {
      this.entries.delete(k);
      this.known.delete(k);
    }
    for (const [id, p] of this.ours) if (gone.includes(p.key)) this.ours.delete(id);

    const changed = changedParagraphs(snapshot, this.known);
    // Headings, tables and blank lines are not checked: they lose any cards and underlines.
    const quiet = changed.filter((p) => !isLiveCheckable(p));
    const toCheck = changed.filter(isLiveCheckable);
    const { batch, rest, tooLong } = takeBatch(toCheck);
    const emptied: PaintItem[] = [...quiet, ...tooLong].map((p) => ({ key: p.key, index: p.index, text: p.text, underlines: [] }));
    for (const p of [...quiet, ...tooLong]) this.known.set(p.key, signature(p));
    if (emptied.length > 0) {
      await this.paint(emptied, gen);
      for (const e of emptied) this.entries.set(e.key, { key: e.key, index: e.index, text: e.text, cards: [] });
    }
    if (gone.length > 0 || emptied.length > 0) {
      this.d.events.onEntries(this.entries);
      this.d.events.onUnderlined(this.underlinedIds());
    }
    if (batch.length === 0) return;

    const revision = this.nextRevision();
    this.d.events.onState({ type: "edit", revision });
    const ctrl = new AbortController();
    this.inFlight = ctrl;
    const sent = new Map(batch.map((p) => [p.key, p]));
    let reply: CheckResult<CheckParagraphsResponse>;
    try {
      reply = await this.d.send(
        {
          revision,
          paragraphs: batch.map((p) => ({ id: p.key, text: p.text, style: p.style, heading: liveHeading(p.heading) })),
          options: this.options(),
        },
        ctrl.signal,
      );
    } catch {
      // Aborted: a reset or a full check took over.
      if (this.inFlight === ctrl) this.inFlight = null;
      return;
    }
    if (this.inFlight !== ctrl) return; // superseded while waiting
    this.inFlight = null;
    if (gen !== this.generation || this.stopped) return;

    if (!reply.ok) {
      this.failures += 1;
      this.d.events.onState({ type: "failure", revision, reason: reply.error.title });
      this.retryLater(revision);
      return;
    }
    this.failures = 0;
    const data = reply.data;
    if (!isCurrentReply(data, { revision, generation: gen }, { generation: this.generation })) return;

    const items: PaintItem[] = [];
    const cardsByKey = new Map<string, WordSuggestion[]>();
    for (const r of data.paragraphs) {
      const p = sent.get(r.id);
      if (!p) continue;
      const cards = r.suggestions.flatMap((s) => liveToWordSuggestion(s, p.index, p.text) ?? []);
      cardsByKey.set(p.key, cards);
      items.push({ key: p.key, index: p.index, text: p.text, underlines: this.underlines(p.key, cards, p.text) });
    }
    const painted = await this.paint(items, gen);
    if (gen !== this.generation) return;
    for (const item of items) {
      // A paragraph that changed while the check ran is left for the next round: its reply is stale.
      if (!painted.has(item.key)) continue;
      this.entries.set(item.key, { key: item.key, index: item.index, text: item.text, cards: cardsByKey.get(item.key) ?? [] });
      this.known.set(item.key, signature(sent.get(item.key)!));
    }
    this.d.events.onEntries(this.entries);
    this.d.events.onState({
      type: "reply",
      revision,
      count: [...this.entries.values()].reduce((n, e) => n + e.cards.length, 0),
      partial: data.state === "partial",
      reason: partialReason(data.health),
    });
    if (rest.length > 0) this.schedule(0);
    else if (this.pending) {
      this.pending = false;
      this.schedule(this.d.pauseMs ?? LIVE_PAUSE_MS);
    }
  }

  /** Offline: wait 2, 4, 8, 16, then 30 s, and try again; with nothing waiting, ask the engine whether it is back. */
  private retryLater(revision: number) {
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      void this.retry(revision);
    }, retryDelayMs(this.failures));
  }

  /** The pane's full check failed too: the same backoff, probing the engine. */
  noteFailure(revision: number) {
    this.failures += 1;
    this.retryLater(revision);
  }

  private async retry(revision: number) {
    if (this.stopped) return;
    this.d.events.onState({ type: "retry", revision });
    if (this.isLive) {
      const gen = this.generation;
      const snapshot = await readSnapshot(this.d.api, this.keyed).catch(() => null);
      if (gen !== this.generation) return;
      if (snapshot && changedParagraphs(snapshot, this.known).some(isLiveCheckable)) {
        await this.round();
        return;
      }
    }
    const back = await this.d.probe().catch(() => false);
    if (this.stopped) return;
    if (back) {
      this.failures = 0;
      this.d.events.onState({ type: "reply", revision, count: 0 });
    } else {
      this.failures += 1;
      this.d.events.onState({ type: "failure", revision });
      this.retryLater(revision);
    }
  }

  /**
   * Paint, handling a Word that cannot draw: the first refusal is retried
   * without the popup (its strings live in the manifest); a second one
   * means no underlines in this Word, for the session.
   */
  private async paint(items: readonly PaintItem[], gen: number): Promise<Set<string>> {
    const done = new Set<string>();
    if (items.length === 0 || this.unavailable) return done;
    let result = await paintParagraphs(this.d.api, items, { keyed: this.keyed, popups: this.popups, ours: new Set(this.ours.keys()) });
    if (result.failure === "insert" && !this.inserted && this.popups) {
      this.popups = false;
      result = await paintParagraphs(this.d.api, items, { keyed: this.keyed, popups: false, ours: new Set(this.ours.keys()) });
    }
    for (const id of result.removed) this.ours.delete(id);
    if (result.failure === "insert" && !this.inserted) {
      this.unavailable = "refused";
      this.enabled = false;
      this.clearTimers();
      this.d.events.onUnavailable("refused");
      this.d.events.onState({ type: "leave" });
      return done;
    }
    if (gen !== this.generation) {
      // Reset while painting: take back what was just drawn.
      const late = new Set<string>();
      for (const m of result.painted.values()) for (const id of m.values()) late.add(id);
      await clearUnderlines(this.d.api, late);
      return done;
    }
    for (const [key, map] of result.painted) {
      done.add(key);
      for (const [suggestionId, annotationId] of map) {
        this.ours.set(annotationId, { key, suggestionId });
        this.inserted = true;
      }
    }
    // A failed insertion after earlier successes: the cards still update; the underlines come back with the next check.
    if (result.failure === "insert") for (const item of items) done.add(item.key);
    this.d.events.onUnderlined(this.underlinedIds());
    return done;
  }
}

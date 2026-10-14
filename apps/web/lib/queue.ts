/**
 * The revision queue (review proposal 1): three passes over one check's
 * suggestions, so a writer can finish one kind of revision before the next.
 *
 *   Correctness first      every Correction (spelling, grammar, typing
 *                          slips, a broken reference): likely errors.
 *   Clarity next           Improvements that judge one sentence (and
 *                          Preferences, when the writer shows them).
 *   Whole-document review  checks that read the whole text (consistency,
 *                          figure references, abbreviations, the abstract's
 *                          moves) and every Convention, which is never an
 *                          error (CLAUDE.md #3).
 *
 * Every suggestion falls in exactly one pass, so walking all three loses
 * nothing. Within a pass, repeated findings (the same check with the same
 * message, such as one misspelling 14 times) form one issue whose
 * occurrences are stepped through with Next and Previous. Positions are
 * anchored to suggestion ids, so dismissing or muting a card keeps the
 * writer's place. Nothing here counts towards a score: there is none.
 * Pure and shared by the website and the Word taskpane.
 */
import type { Category } from "@researchly/contract";
import { isDocumentWide, type ScopeMap } from "./scope";

export type PassId = "correctness" | "clarity" | "whole";
/** "all" is the ordinary list: every suggestion, the queue not in use. */
export type QueueChoice = "all" | PassId;

export interface PassInfo {
  id: PassId;
  title: string;
  /** One line under the chooser: what this pass holds, in everyday words. */
  help: string;
}

export const PASSES: readonly PassInfo[] = [
  {
    id: "correctness",
    title: "Correctness first",
    help: "Likely errors: spelling, grammar, typing slips and broken references. Fix these before anything else.",
  },
  {
    id: "clarity",
    title: "Clarity next",
    help: "Sentences that are correct but would read more easily if revised.",
  },
  {
    id: "whole",
    title: "Whole-document review",
    help: "Checks that read the whole text, such as consistency, figure references and abbreviations, and the conventions of research writing. Conventions are not errors.",
  },
];

export function passInfo(id: PassId): PassInfo {
  return PASSES.find((p) => p.id === id)!;
}

/** What the queue needs from a suggestion; web and Word suggestions both have it. */
export interface QueueItem {
  id: string;
  rule_id: string;
  category: Category | string;
  message: string;
}

/** Which pass a suggestion belongs to. Exactly one, so the passes partition the list. */
export function passOf(s: QueueItem, known: ScopeMap | null): PassId {
  if (s.category === "correction") return "correctness";
  if (s.category === "convention" || isDocumentWide(s.rule_id, known)) return "whole";
  return "clarity";
}

export function passCounts(list: readonly QueueItem[], known: ScopeMap | null): Record<PassId, number> {
  const out: Record<PassId, number> = { correctness: 0, clarity: 0, whole: 0 };
  for (const s of list) out[passOf(s, known)]++;
  return out;
}

export interface QueueGroup<T extends QueueItem> {
  key: string;
  /** What was noticed: the first occurrence's message. */
  label: string;
  /** Occurrences in document order. */
  items: T[];
}

export interface Queue<T extends QueueItem> {
  pass: PassId;
  /** Issues in the order their first occurrence appears in the text. */
  groups: QueueGroup<T>[];
  /** Findings in the pass (every occurrence counted). */
  total: number;
}

/** Two findings are the same issue when the same check said the same thing. */
export function groupKey(s: QueueItem): string {
  return `${s.rule_id}\u0000${s.message.trim()}`;
}

/** The pass's issues. `list` must already be in document order (and filtered to what the writer is looking at). */
export function buildQueue<T extends QueueItem>(list: readonly T[], pass: PassId, known: ScopeMap | null): Queue<T> {
  const byKey = new Map<string, QueueGroup<T>>();
  const groups: QueueGroup<T>[] = [];
  let total = 0;
  for (const s of list) {
    if (passOf(s, known) !== pass) continue;
    total++;
    const key = groupKey(s);
    let g = byKey.get(key);
    if (!g) {
      g = { key, label: s.message.trim(), items: [] };
      byKey.set(key, g);
      groups.push(g);
    }
    g.items.push(s);
  }
  return { pass, groups, total };
}

/**
 * Where the writer is: anchored to a suggestion id, with the issue's key and
 * the indices as fallbacks for when that suggestion has gone (dismissed,
 * muted, or a re-check moved it).
 */
export interface QueuePos {
  id: string;
  key: string;
  group: number;
  occurrence: number;
}

/** The queue's state, held by the surface (it survives a re-check, never stored). */
export interface QueueState {
  pass: QueueChoice;
  at: QueuePos | null;
}

export const QUEUE_START: QueueState = { pass: "all", at: null };

export interface QueueSpot {
  group: number;
  occurrence: number;
}

const clamp = (n: number, lo: number, hi: number) => Math.min(Math.max(n, lo), hi);

/**
 * The finding to show. The anchored suggestion if it is still there; else
 * the same issue at the nearest occurrence; else the issue now at the same
 * place in the pass (the next one, once an issue is finished). Null only
 * when the pass is empty.
 */
export function resolveSpot<T extends QueueItem>(q: Queue<T>, at: QueuePos | null): QueueSpot | null {
  if (q.groups.length === 0) return null;
  if (!at) return { group: 0, occurrence: 0 };
  for (let g = 0; g < q.groups.length; g++) {
    const o = q.groups[g]!.items.findIndex((s) => s.id === at.id);
    if (o >= 0) return { group: g, occurrence: o };
  }
  const same = q.groups.findIndex((g) => g.key === at.key);
  if (same >= 0) return { group: same, occurrence: clamp(at.occurrence, 0, q.groups[same]!.items.length - 1) };
  return { group: clamp(at.group, 0, q.groups.length - 1), occurrence: 0 };
}

export function posAt<T extends QueueItem>(q: Queue<T>, spot: QueueSpot): QueuePos {
  const g = q.groups[spot.group]!;
  return { id: g.items[spot.occurrence]!.id, key: g.key, group: spot.group, occurrence: spot.occurrence };
}

export type Step = "next-issue" | "previous-issue" | "next-occurrence" | "previous-occurrence";

/** One step through the pass. Never wraps: the ends are ends, so finishing a pass is visible. */
export function stepSpot<T extends QueueItem>(q: Queue<T>, spot: QueueSpot, step: Step): QueueSpot {
  const g = q.groups[spot.group];
  if (!g) return spot;
  switch (step) {
    case "next-issue":
      return spot.group < q.groups.length - 1 ? { group: spot.group + 1, occurrence: 0 } : spot;
    case "previous-issue":
      return spot.group > 0 ? { group: spot.group - 1, occurrence: 0 } : spot;
    case "next-occurrence":
      return { group: spot.group, occurrence: Math.min(spot.occurrence + 1, g.items.length - 1) };
    case "previous-occurrence":
      return { group: spot.group, occurrence: Math.max(spot.occurrence - 1, 0) };
  }
}

/** Find a suggestion in the pass (a highlight clicked in the text). */
export function spotOf<T extends QueueItem>(q: Queue<T>, id: string): QueueSpot | null {
  for (let g = 0; g < q.groups.length; g++) {
    const o = q.groups[g]!.items.findIndex((s) => s.id === id);
    if (o >= 0) return { group: g, occurrence: o };
  }
  return null;
}

/** The pass after this one that still has findings, for "go on to" at the end of a pass. */
export function nextPass(after: PassId, counts: Record<PassId, number>): PassId | null {
  const order = PASSES.map((p) => p.id);
  for (const id of order.slice(order.indexOf(after) + 1)) if (counts[id] > 0) return id;
  return null;
}

const fmt = new Intl.NumberFormat("en-GB");

/** "Issue 3 of 9 in this pass." */
export function issueLine(spot: QueueSpot, q: Queue<QueueItem>): string {
  return `Issue ${fmt.format(spot.group + 1)} of ${fmt.format(q.groups.length)} in this pass`;
}

/** "Occurrence 2 of 14", or null for an issue found once. */
export function occurrenceLine(spot: QueueSpot, q: Queue<QueueItem>): string | null {
  const n = q.groups[spot.group]?.items.length ?? 0;
  return n > 1 ? `Occurrence ${fmt.format(spot.occurrence + 1)} of ${fmt.format(n)}` : null;
}

/** "once", "3 times": a tally, never a score. */
export function timesWord(n: number): string {
  return n === 1 ? "once" : n === 2 ? "twice" : `${fmt.format(n)} times`;
}

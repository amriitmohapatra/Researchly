/**
 * The progress page's view model (S4c): per rule, how often it fired per
 * 1,000 words in each recorded check, oldest first. Pure and unit-tested.
 * A trajectory to notice, never a score: no totals, no grade, no ranking
 * of the writer, only each rule's own line and a word for its direction.
 */
import type { DocumentType } from "@researchly/contract";
import type { ProgressEvent } from "./progress";

export type TrendWord = "fewer" | "about the same" | "more";

export interface RuleTrend {
  ruleId: string;
  /**
   * Flags per 1,000 words in each compared check, oldest first. null where
   * the rule was not assessed in that check (muted, a hidden preference,
   * held back by Draft, off for the article type, its tier down), or where
   * an older check cannot say whether it was (Codex review N2): a gap,
   * never a zero.
   */
  rates: (number | null)[];
  /** The first and the latest assessed values; null when there are none. */
  first: number | null;
  latest: number | null;
  /** null until two checks assessed the rule: there is no direction yet. */
  word: TrendWord | null;
  /** Compared checks in which the rule was not assessed. */
  notAssessed: number;
}

/** Rules shown: those that fired at least this many times across the compared checks. */
export const MIN_FIRES = 2;

/** Flags per 1,000 words, to one decimal place. */
export function ratePer1000(count: number, words: number): number {
  if (!(words > 0) || !(count > 0)) return 0;
  return Math.round((count / words) * 10_000) / 10;
}

/**
 * The direction from the first check to the latest. Small differences are
 * "about the same": half a flag per 1,000 words, or a fifth of the larger
 * value, whichever is bigger, so a short check's noise is not read as change.
 */
export function trendWord(first: number, latest: number): TrendWord {
  const band = Math.max(0.5, 0.2 * Math.max(first, latest));
  if (Math.abs(latest - first) < band) return "about the same";
  return latest < first ? "fewer" : "more";
}

/** "3.2", "0", "12": a rate as written on the page. */
export function formatRate(r: number): string {
  return r.toLocaleString("en-GB", { maximumFractionDigits: 1 });
}

/** The rate of `ruleId` in one check, or null when the check did not assess it. */
export function rateIn(e: ProgressEvent, ruleId: string): number | null {
  const n = e.counts?.[ruleId] ?? 0;
  if (Array.isArray(e.assessed)) return e.assessed.includes(ruleId) ? ratePer1000(n, e.words) : null;
  // An older check: a count proves the rule ran; a zero proves nothing.
  return n > 0 ? ratePer1000(n, e.words) : null;
}

export interface Comparison {
  /** The checks compared, oldest first: one article type, one rule set. */
  checks: number;
  trends: RuleTrend[];
  /** The article type compared, and every type with recorded checks (newest first). */
  documentType: DocumentType | null;
  documentTypes: { id: DocumentType; checks: number }[];
  /** Recorded checks of that type left out because another version of the rules made them. */
  otherRuleset: number;
  /** The dates of the first and the latest compared check (ISO strings). */
  from: string | null;
  to: string | null;
  /** How many compared checks ran in Draft (sentence-level checks only). */
  draft: number;
}

/**
 * Every rule that fired at least MIN_FIRES times across comparable checks,
 * with its rate in each (oldest first). Comparable: the same article type
 * (the latest check's, unless `documentType` picks another) and the same
 * rule set as the latest of those (older checks without one form their own
 * group). `events` may come newest first, as loadProgress returns them;
 * checks of no words are skipped (nothing to divide by).
 */
export function ruleTrends(events: readonly ProgressEvent[], documentType?: DocumentType | null): Comparison {
  const ordered = [...events]
    .filter((e) => e.words > 0)
    .sort((a, b) => (a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0));
  const typeCounts = new Map<DocumentType, number>();
  for (const e of [...ordered].reverse()) typeCounts.set(e.document_type, (typeCounts.get(e.document_type) ?? 0) + 1);
  const documentTypes = [...typeCounts.entries()].map(([id, checks]) => ({ id, checks }));
  const type = documentType && typeCounts.has(documentType) ? documentType : (documentTypes[0]?.id ?? null);
  const ofType = ordered.filter((e) => e.document_type === type);
  const latestRuleset = ofType.length ? (ofType[ofType.length - 1]!.ruleset ?? null) : null;
  const compared = ofType.filter((e) => (e.ruleset ?? null) === latestRuleset);

  const fires = new Map<string, number>();
  for (const e of compared) {
    for (const [id, n] of Object.entries(e.counts ?? {})) {
      if (typeof n === "number" && n > 0) fires.set(id, (fires.get(id) ?? 0) + n);
    }
  }
  const trends = [...fires.entries()]
    .filter(([, n]) => n >= MIN_FIRES)
    .sort(([a, x], [b, y]) => y - x || (a < b ? -1 : 1))
    .map(([ruleId]): RuleTrend => {
      const rates = compared.map((e) => rateIn(e, ruleId));
      const assessed = rates.filter((r): r is number => r !== null);
      const first = assessed[0] ?? null;
      const latest = assessed[assessed.length - 1] ?? null;
      return {
        ruleId,
        rates,
        first,
        latest,
        word: assessed.length > 1 && first !== null && latest !== null ? trendWord(first, latest) : null,
        notAssessed: rates.length - assessed.length,
      };
    });
  return {
    checks: compared.length,
    trends,
    documentType: type,
    documentTypes,
    otherRuleset: ofType.length - compared.length,
    from: compared[0]?.created_at ?? null,
    to: compared[compared.length - 1]?.created_at ?? null,
    draft: compared.filter((e) => e.mode === "draft").length,
  };
}

/**
 * The sparkline's points in a w × h box: x by check order, y from zero
 * (bottom) to the line's own highest value. A check that did not assess the
 * rule has `y: null`: the line breaks there, it is never drawn through.
 */
export function sparkPoints(rates: readonly (number | null)[], w: number, h: number, pad = 4): { x: number; y: number | null }[] {
  const max = Math.max(0, ...rates.filter((r): r is number => r !== null));
  const n = rates.length;
  return rates.map((r, i) => ({
    x: n === 1 ? w / 2 : pad + (i * (w - 2 * pad)) / (n - 1),
    y: r === null ? null : max === 0 ? h - pad : h - pad - (r / max) * (h - 2 * pad),
  }));
}

/** The line's path: one segment per run of assessed checks, broken at every gap. */
export function sparkPath(pts: readonly { x: number; y: number | null }[]): string {
  let d = "";
  let pen = false;
  for (const p of pts) {
    if (p.y === null) {
      pen = false;
      continue;
    }
    d += `${pen ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)} `;
    pen = true;
  }
  return d.trim();
}

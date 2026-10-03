/** Pure view-model helpers for the results screen (unit-tested). */
import type { AnalyzeResponse, Category, Suggestion } from "@researchly/contract";
import { CATEGORIES, CATEGORY_ORDER, countByCategory } from "./categories";

export type Filter = Category | "all";

/** Preferences are hidden unless the writer asked for them (CLAUDE.md #3). */
export function shownSuggestions(data: AnalyzeResponse, showPreferences: boolean): Suggestion[] {
  const list = showPreferences ? data.suggestions : data.suggestions.filter((s) => s.category !== "preference");
  return [...list].sort(
    (a, b) =>
      a.span.start - b.span.start ||
      CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category) ||
      a.span.end - b.span.end ||
      (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );
}

/**
 * Preferences the writer is not seeing: those the engine withheld, plus any
 * it returned that the toggle now hides client-side.
 */
export function hiddenPreferenceCount(data: AnalyzeResponse, showPreferences: boolean): number {
  const returned = data.suggestions.filter((s) => s.category === "preference").length;
  return data.hidden_preferences + (showPreferences ? 0 : returned);
}

/** Whether revealing the hidden preferences needs another request (the engine withheld them). */
export function revealNeedsRecheck(data: AnalyzeResponse): boolean {
  return data.hidden_preferences > 0;
}

export function applyFilter(list: readonly Suggestion[], filter: Filter): Suggestion[] {
  return filter === "all" ? [...list] : list.filter((s) => s.category === filter);
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** The sentence announced to screen readers when a check completes. */
export function summarySentence(list: readonly Suggestion[]): string {
  if (list.length === 0) return "Check complete. No suggestions.";
  const counts = countByCategory(list);
  const parts = CATEGORY_ORDER.filter((c) => counts[c] > 0).map((c) =>
    plural(counts[c], CATEGORIES[c].label.toLowerCase(), CATEGORIES[c].plural.toLowerCase()),
  );
  return `Check complete. ${plural(list.length, "suggestion", "suggestions")}: ${parts.join(", ")}.`;
}

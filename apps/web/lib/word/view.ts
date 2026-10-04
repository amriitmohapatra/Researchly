/** Pure view-model helpers for the Word taskpane (unit-tested). */
import type { AnalyzeWordResponse, Coverage, WordSuggestion } from "@researchly/contract";
import { CATEGORY_ORDER } from "../categories";

/** Preferences hidden unless asked for (CLAUDE.md #3); the rest in document order. */
export function shownWordSuggestions(data: AnalyzeWordResponse, showPreferences: boolean): WordSuggestion[] {
  const list = showPreferences ? data.suggestions : data.suggestions.filter((s) => s.category !== "preference");
  return [...list].sort(
    (a, b) =>
      a.location.paragraph - b.location.paragraph ||
      a.location.start - b.location.start ||
      CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category) ||
      (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );
}

/** "a, b and c" */
export function listSentence(items: readonly string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

const plural = (n: number, one: string, many: string) => `${n.toLocaleString("en-GB")} ${n === 1 ? one : many}`;

/** What was read and what was not, said plainly: silence would read as "nothing to flag". */
export function coverageSentences(c: Coverage): { checked: string; notChecked: string | null } {
  const tables = c.table_paragraphs > 0 ? `, ${plural(c.table_paragraphs, "of them in a table", "of them in tables")}` : "";
  const checked = `Checked ${plural(c.paragraphs, "paragraph", "paragraphs")} of the document body${tables}.`;
  const parts = c.not_checked.filter((p) => p.trim());
  if (parts.length === 0) return { checked, notChecked: null };
  const first = listSentence(parts);
  return { checked, notChecked: `${first.charAt(0).toUpperCase()}${first.slice(1)} ${parts.length === 1 ? "was" : "were"} not checked.` };
}

/** Draft mode's note: what it held back, and that it is a stage, not a verdict. */
export function heldBackSentence(n: number): string | null {
  if (n <= 0) return null;
  return `Draft held back ${plural(n, "document-level suggestion", "document-level suggestions")}, such as figure references and abbreviations defined once.`;
}

/** The sentence announced to screen readers when a check completes. */
export function wordSummary(shown: number): string {
  return shown === 0 ? "Check complete. No suggestions." : `Check complete. ${plural(shown, "suggestion", "suggestions")}.`;
}

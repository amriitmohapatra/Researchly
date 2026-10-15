/**
 * The reading summary (2026-10-14; the coverage summary, Codex review #5):
 * what the check read, what it set aside and what it left out, as one
 * sentence. Counts and the engine's own labels only, never text. Pure and
 * unit-tested (tests/unit/reading.test.tsx). The engine words it the same
 * way for the command line (researchly/shapes.py `reading_sentence`).
 */
import type { ReadingSummary } from "@researchly/contract";

const nf = new Intl.NumberFormat("en-GB");

/** A counted part: what the engine sends (set aside, not checked, included) and what the Word pane counts itself. */
export interface Counted {
  kind: string;
  count: number;
  label: string;
}

/**
 * The engine's labels are plural ("lines of code"). For a count of one the
 * known kinds read in the singular; an unknown kind keeps its label.
 */
const SINGULAR: Record<string, string> = {
  code: "line of code",
  maths_or_code: "bit of maths or code typed into the text",
  layout: "line laid out as a table or an equation",
  marked_up: "bit of maths, a citation or code in the markup",
  other_language: "paragraph not in English",
  footnotes: "footnote",
  endnotes: "endnote",
  comments: "comment",
  text_boxes: "text box",
  headers_footers: "header or footer",
  skipped_files: "included file that could not be read",
};

export function setAsidePhrase(s: Counted): string {
  const label = s.count === 1 ? (SINGULAR[s.kind] ?? s.label) : s.label;
  return `${nf.format(s.count)} ${label}`;
}

function listed(items: readonly Counted[] | undefined): Counted[] {
  return (items ?? []).filter((s) => s.count > 0 && s.label);
}

/**
 * "Checked 4,210 words, including 3 footnotes. Set aside: 2 lines of code ·
 * 1 paragraph not in English. Not checked: 1 text box. Researchly checks
 * English only." Null without a summary.
 *
 * `notChecked` adds parts the surface counted itself (the Word pane reads
 * the body only and counts footnotes and text boxes without reading them).
 */
export function readingSentence(reading: ReadingSummary | null | undefined, notChecked: readonly Counted[] = []): string | null {
  if (!reading || typeof reading.words_checked !== "number") return null;
  const n = reading.words_checked;
  const included = listed(reading.included);
  let line = `Checked ${nf.format(n)} ${n === 1 ? "word" : "words"}`;
  if (included.length > 0) line += `, including ${included.map(setAsidePhrase).join(" · ")}`;
  line += ".";
  const aside = listed(reading.set_aside);
  if (aside.length > 0) line += ` Set aside: ${aside.map(setAsidePhrase).join(" · ")}.`;
  const skipped = [...listed(reading.not_checked), ...listed(notChecked)];
  if (skipped.length > 0) line += ` Not checked: ${skipped.map(setAsidePhrase).join(" · ")}.`;
  if (aside.some((s) => s.kind === "other_language")) line += " Researchly checks English only.";
  return line;
}

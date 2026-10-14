/**
 * The reading summary (2026-10-14): what the check read and what it set
 * aside, as one sentence. Counts and the engine's own labels only, never
 * text. Pure and unit-tested (tests/unit/reading.test.tsx).
 */
import type { ReadingSummary, SetAside } from "@researchly/contract";

const nf = new Intl.NumberFormat("en-GB");

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
};

export function setAsidePhrase(s: Pick<SetAside, "kind" | "count" | "label">): string {
  const label = s.count === 1 ? (SINGULAR[s.kind] ?? s.label) : s.label;
  return `${nf.format(s.count)} ${label}`;
}

/** "Checked 4,210 words. Set aside: 2 lines of code · 1 paragraph not in English." Null without a summary. */
export function readingSentence(reading: ReadingSummary | null | undefined): string | null {
  if (!reading || typeof reading.words_checked !== "number") return null;
  const n = reading.words_checked;
  const words = `Checked ${nf.format(n)} ${n === 1 ? "word" : "words"}.`;
  const aside = (reading.set_aside ?? []).filter((s) => s.count > 0 && s.label);
  if (aside.length === 0) return words;
  return `${words} Set aside: ${aside.map(setAsidePhrase).join(" · ")}.`;
}

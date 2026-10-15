import type { ReadingSummary as Reading } from "@researchly/contract";
import { readingSentence, type Counted } from "@/lib/reading";

/**
 * One quiet line under the results heading: how many words the checks read,
 * what they set aside (code, maths, layout, paragraphs in another language)
 * and what they left out (a file's footnotes, text boxes, headers), in the
 * engine's own words. `notChecked` adds what the surface counted itself
 * (the Word pane). Nothing from an older engine.
 */
export function ReadingSummary({
  reading,
  notChecked,
  className = "reading-line muted",
}: {
  reading: Reading | null | undefined;
  notChecked?: readonly Counted[];
  className?: string;
}) {
  const sentence = readingSentence(reading, notChecked);
  if (!sentence) return null;
  return (
    <p className={className} data-testid="reading-summary">
      {sentence}
    </p>
  );
}

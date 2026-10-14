import type { ReadingSummary as Reading } from "@researchly/contract";
import { readingSentence } from "@/lib/reading";

/**
 * One quiet line under the results heading: how many words the checks read
 * and what they set aside (code, maths, layout, paragraphs in another
 * language), in the engine's own words. Nothing from an older engine.
 */
export function ReadingSummary({ reading, className = "reading-line muted" }: { reading: Reading | null | undefined; className?: string }) {
  const sentence = readingSentence(reading);
  if (!sentence) return null;
  return (
    <p className={className} data-testid="reading-summary">
      {sentence}
    </p>
  );
}

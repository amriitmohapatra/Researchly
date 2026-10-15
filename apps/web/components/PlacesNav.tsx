"use client";

import { placeLine, stepPlace } from "@/lib/occurrences";

interface Props {
  /** How many places the word appears in (two or more). */
  count: number;
  /** The place shown last, or null before "Show where" is used. */
  at: number | null;
  /** Show place `index` (0-based) in the text or the document. */
  onGo: (index: number) => void;
  /** The word the card asks about, for the group's accessible name. */
  word: string;
  /** Word is busy or a check is running: the buttons say so and do nothing. */
  busy?: boolean;
  /** The card's message, which the first button is described by. */
  describedBy?: string;
}

/**
 * "Show where" on a grouped card (Codex review #10): one card stands for
 * every use of a word, and this walks through them, as the revision queue's
 * Previous and Next walk the occurrences of a repeated issue. The place is
 * announced in a polite live region; the buttons at either end say they are
 * unavailable rather than vanish, so focus never falls off the card.
 */
export function PlacesNav({ count, at, onGo, word, busy = false, describedBy }: Props) {
  const go = (index: number) => {
    if (!busy) onGo(index);
  };
  const step = (dir: 1 | -1) => {
    const next = stepPlace(at, count, dir);
    if (next !== at) go(next);
  };
  return (
    <div className="places" role="group" aria-label={`Places ‘${word}’ appears`} data-testid="places">
      <button
        type="button"
        className="btn btn-quiet btn-compact"
        aria-describedby={describedBy}
        aria-disabled={busy || undefined}
        onClick={() => go(at ?? 0)}
        data-testid="show-where"
      >
        Show where
      </button>
      {at !== null ? (
        <span className="places-step">
          <button
            type="button"
            className="btn btn-quiet btn-compact"
            aria-label="Previous place"
            aria-disabled={busy || at === 0 || undefined}
            onClick={() => step(-1)}
            data-testid="place-prev"
          >
            Previous
          </button>
          <button
            type="button"
            className="btn btn-quiet btn-compact"
            aria-label="Next place"
            aria-disabled={busy || at === count - 1 || undefined}
            onClick={() => step(1)}
            data-testid="place-next"
          >
            Next
          </button>
        </span>
      ) : null}
      <span className="places-pos" aria-live="polite" aria-atomic="true" data-testid="place-position">
        {at !== null ? placeLine(at, count) : ""}
      </span>
    </div>
  );
}

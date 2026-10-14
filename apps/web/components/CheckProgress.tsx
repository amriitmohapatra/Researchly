"use client";

import { useEffect, useState } from "react";
import { elapsedLabel, progressStatus, STILL_CHECKING_AFTER_MS } from "@/lib/check-session";

/**
 * A running check (review proposal 8): what is happening ("Checking…",
 * then "Still checking…" once it runs long) and the time so far. Only the
 * "Still checking" sentence goes to a polite live region, once; the start is
 * already announced by the page, and the clock is never read out every
 * second. Shared by the website and the Word taskpane. The Cancel button
 * stays beside Check.
 */
export function CheckProgress({
  startedAt,
  what,
  hasPrevious,
  className,
}: {
  /** When the check started (ms since the epoch). */
  startedAt: number;
  /** "your text", "your file", "the document". */
  what: string;
  /** Results from an earlier check are on screen below. */
  hasPrevious: boolean;
  className?: string;
}) {
  // Rendered only after a check starts (never on the server), so reading the clock here is safe.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = () => setNow(Date.now());
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [startedAt]);
  const elapsed = Math.max(0, now - startedAt);
  const still = elapsed >= STILL_CHECKING_AFTER_MS;
  return (
    <div className={`check-progress${className ? ` ${className}` : ""}`} data-testid="check-progress" data-still={still || undefined}>
      <span className="spinner" aria-hidden="true" />
      <div className="check-progress-body">
        {/* Seen, not spoken: the page's announcer has already said "Checking…". */}
        <p className="check-progress-status" aria-hidden="true" data-testid="check-progress-status">
          {progressStatus(elapsed, what, hasPrevious)}
        </p>
        {/* Spoken once, when a check becomes a long one. Present from the start so the change is announced. */}
        <p className="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="check-progress-live">
          {still ? progressStatus(elapsed, what, hasPrevious) : ""}
        </p>
        <p className="check-progress-time muted">
          Time so far: <span data-testid="check-elapsed">{elapsedLabel(elapsed)}</span>
        </p>
      </div>
    </div>
  );
}

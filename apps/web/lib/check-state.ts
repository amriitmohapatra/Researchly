/**
 * The six states of a live check (S4d R2; docs/inline-review-design.md §3),
 * shared by every surface that checks while the writer writes: the
 * website's status line, the Word pane's header and, through the same
 * tokens, the desktop widget.
 *
 * A pure reducer: no timers, no I/O. The caller owns the clock: after a
 * failure it reads `retryInMs`, waits, sends again with a `retry` event,
 * and feeds the reply back. Replies and failures carry the revision they
 * answer; anything older than the latest edit is dropped, so a slow reply
 * can never paint stale underlines.
 *
 * The words come from the design tokens (packages/design-tokens), so every
 * surface says the same thing.
 */
import { RETRY_SECONDS, STATES, STATE_ORDER } from "@researchly/design-tokens";

export type CheckState = (typeof STATE_ORDER)[number];

export const CHECK_STATES: readonly CheckState[] = STATE_ORDER;

export interface CheckStatus {
  state: CheckState;
  /** The latest revision the writer has made (edits count up). */
  revision: number;
  /** Suggestions on show for that revision (issues, or partial with some). */
  count: number;
  /** Partial: which part of the checking was off. Offline: what went wrong. Plain words. */
  reason: string;
  /** Failures in a row since the last success. */
  failures: number;
  /** Offline: wait this long before the next try; null otherwise. */
  retryInMs: number | null;
}

export type CheckEvent =
  /** The writer changed the text: a check for this revision is (about to be) in flight. */
  | { type: "edit"; revision: number }
  /** A reply for `revision`. `partial` when a tier was down (state "partial" in the reply). */
  | { type: "reply"; revision: number; count: number; partial?: boolean; reason?: string }
  /** The engine could not be reached, or refused (timeout, 5xx, 429, offline). */
  | { type: "failure"; revision: number; reason?: string }
  /** The retry timer fired and the caller sent again: stay offline until it answers. */
  | { type: "retry"; revision: number }
  /** The writer paused checking here. */
  | { type: "pause" }
  /** The writer left the field (or it is not eligible). */
  | { type: "leave" };

export const INITIAL_STATUS: CheckStatus = {
  state: "hidden",
  revision: 0,
  count: 0,
  reason: "",
  failures: 0,
  retryInMs: null,
};

/** How long to wait before retry number `failures` (1-based): 2, 4, 8, 16, 30 s, then 30 s for good. */
export function retryDelayMs(failures: number): number {
  const i = Math.min(Math.max(failures, 1), RETRY_SECONDS.length) - 1;
  return RETRY_SECONDS[i]! * 1000;
}

export function reduceCheckState(status: CheckStatus, event: CheckEvent): CheckStatus {
  switch (event.type) {
    case "edit":
      if (event.revision < status.revision) return status;
      // Failures in a row are kept: if this check fails too, the wait grows.
      return { ...status, state: "checking", revision: event.revision, reason: "", retryInMs: null };
    case "reply": {
      if (event.revision < status.revision) return status; // stale: a newer edit is in flight
      const count = Math.max(0, Math.floor(event.count));
      const state: CheckState = event.partial ? "partial" : count > 0 ? "issues" : "clear";
      return {
        state,
        revision: event.revision,
        count,
        reason: event.partial ? (event.reason ?? "") : "",
        failures: 0,
        retryInMs: null,
      };
    }
    case "failure": {
      if (event.revision < status.revision) return status;
      const failures = status.failures + 1;
      return {
        ...status,
        state: "offline",
        revision: event.revision,
        reason: event.reason ?? "",
        failures,
        retryInMs: retryDelayMs(failures),
      };
    }
    case "retry":
      if (status.state !== "offline" || event.revision < status.revision) return status;
      return { ...status, revision: event.revision, retryInMs: null };
    case "pause":
    case "leave":
      return { ...status, state: "hidden", count: 0, reason: "", failures: 0, retryInMs: null };
  }
}

/** The short label: "Checking…", "3 suggestions", "Can’t check right now". */
export function stateLabel(status: Pick<CheckStatus, "state" | "count">): string {
  const s = STATES[status.state];
  if (status.state === "issues") {
    return status.count === 1 ? STATES.issues.labelOne : STATES.issues.label.replace("{n}", status.count.toLocaleString("en-GB"));
  }
  return s.label;
}

/** The whole state in plain words, for a screen reader or a tooltip: the label, then the detail and the next step. */
export function stateDescription(status: CheckStatus): string {
  const parts: string[] = [stateLabel(status) + "."];
  if (status.state === "partial") {
    if (status.count > 0) parts.push(`${stateLabel({ state: "issues", count: status.count })}.`);
    parts.push(status.reason ? `${status.reason}.` : STATES.partial.description);
  } else if (status.state === "offline") {
    if (status.reason) parts.push(`${status.reason}.`);
    parts.push(
      status.retryInMs === null
        ? "Trying again now."
        : `Researchly will try again in ${Math.round(status.retryInMs / 1000)} s. Your text is not lost.`,
    );
  } else if (status.state === "hidden") {
    parts.push(STATES.hidden.description);
  }
  return parts.join(" ").replace(/\.\./g, ".");
}

/** The look each state has (the tokens' `look`): none, ring, badge, tick, warning or crossed. */
export function stateLook(state: CheckState): (typeof STATES)[CheckState]["look"] {
  return STATES[state].look;
}

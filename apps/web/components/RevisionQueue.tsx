"use client";

import { useId, type ReactNode } from "react";
import {
  issueLine,
  nextPass,
  occurrenceLine,
  PASSES,
  passInfo,
  posAt,
  resolveSpot,
  stepSpot,
  timesWord,
  type PassId,
  type Queue,
  type QueueChoice,
  type QueueItem,
  type QueuePos,
  type Step,
} from "@/lib/queue";

const fmt = new Intl.NumberFormat("en-GB");

/**
 * "Work through": the ordinary list, or one of the three passes of the
 * revision queue (review proposal 1). Toggle buttons, each with the number of
 * findings in its pass: a tally, never a score. Shared by the website and
 * the Word taskpane.
 */
export function PassChooser({
  choice,
  counts,
  onChoose,
  className,
}: {
  choice: QueueChoice;
  counts: Record<PassId, number>;
  onChoose: (c: QueueChoice) => void;
  className?: string;
}) {
  const labelId = useId();
  const helpId = useId();
  return (
    <div className={`passes${className ? ` ${className}` : ""}`} data-testid="pass-chooser">
      <p id={labelId} className="control-label passes-label">
        Work through
      </p>
      <div className="pass-row" role="group" aria-labelledby={labelId} aria-describedby={choice !== "all" ? helpId : undefined}>
        <button
          type="button"
          className="pass-btn"
          aria-pressed={choice === "all"}
          onClick={() => onChoose("all")}
          data-testid="pass-all"
        >
          All suggestions
        </button>
        {PASSES.map((p) => (
          <button
            key={p.id}
            type="button"
            className="pass-btn"
            aria-pressed={choice === p.id}
            onClick={() => onChoose(p.id)}
            data-testid={`pass-${p.id}`}
          >
            <span>{p.title}</span>
            <span className="pass-count">
              {fmt.format(counts[p.id])}
              <span className="sr-only">{counts[p.id] === 1 ? " finding" : " findings"}</span>
            </span>
          </button>
        ))}
      </div>
      {choice !== "all" ? (
        <p id={helpId} className="help pass-help" data-testid="pass-help">
          {passInfo(choice).help}
        </p>
      ) : null}
    </div>
  );
}

interface QueueProps<T extends QueueItem> {
  queue: Queue<T>;
  at: QueuePos | null;
  /** The writer moved: a step, or a pick from the list of issues. */
  onMove: (pos: QueuePos, s: T) => void;
  renderCard: (s: T) => ReactNode;
  counts: Record<PassId, number>;
  /** Go on to another pass (offered at the end of this one). */
  onPass: (p: PassId) => void;
  /** Said when the pass is empty, e.g. "in the Methods section". */
  scopeNote?: string | null;
  /** Shown after the last issue of the pass (the website points to the brief and the map). */
  endExtra?: ReactNode;
  /** Narrow layout (the Word taskpane). */
  compact?: boolean;
}

/**
 * One pass of the revision queue: where the writer is ("Issue 3 of 9 in
 * this pass", announced politely), Previous and Next issue, the
 * occurrences of a repeated finding with their own Previous and Next, the
 * current suggestion's card, and every issue of the pass behind a
 * disclosure. Buttons at an end stay focusable (aria-disabled), so the
 * keyboard never loses its place.
 */
export function RevisionQueue<T extends QueueItem>({
  queue,
  at,
  onMove,
  renderCard,
  counts,
  onPass,
  scopeNote = null,
  endExtra = null,
  compact = false,
}: QueueProps<T>) {
  const titleId = useId();
  const info = passInfo(queue.pass);
  const spot = resolveSpot(queue, at);
  const following = nextPass(queue.pass, counts);
  const followingTitle = following ? passInfo(following).title : null;

  const goOn = following ? (
    <button type="button" className="btn-link" onClick={() => onPass(following)} data-testid="queue-next-pass">
      Go on to {followingTitle}
    </button>
  ) : null;

  if (!spot) {
    return (
      <section className={`queue${compact ? " queue-compact" : ""}`} aria-labelledby={titleId} data-testid="queue">
        <h3 id={titleId} className="col-title">
          {info.title}
        </h3>
        <p className="muted" data-testid="queue-empty">
          Nothing in this pass{scopeNote ? ` ${scopeNote}` : ""}. {goOn}
        </p>
        {endExtra}
      </section>
    );
  }

  const group = queue.groups[spot.group]!;
  const current = group.items[spot.occurrence]!;
  const occ = occurrenceLine(spot, queue);
  const lastIssue = spot.group === queue.groups.length - 1;
  const lastOccurrence = spot.occurrence === group.items.length - 1;
  const move = (step: Step) => {
    const next = stepSpot(queue, spot, step);
    if (next.group === spot.group && next.occurrence === spot.occurrence) return;
    const pos = posAt(queue, next);
    onMove(pos, queue.groups[next.group]!.items[next.occurrence]!);
  };
  const navButton = (step: Step, label: string, atEnd: boolean, testId: string, aria?: string) => (
    <button
      type="button"
      className="btn btn-quiet btn-compact"
      aria-disabled={atEnd || undefined}
      aria-label={aria}
      onClick={() => move(step)}
      data-testid={testId}
    >
      {label}
    </button>
  );

  return (
    <section
      className={`queue${compact ? " queue-compact" : ""}`}
      aria-labelledby={titleId}
      data-testid="queue"
      data-pass={queue.pass}
    >
      <h3 id={titleId} className="col-title">
        {info.title}
      </h3>
      <div className="queue-nav">
        <p className="queue-pos" aria-live="polite" aria-atomic="true" data-testid="queue-position">
          {issueLine(spot, queue)}.{occ ? ` ${occ}.` : ""}
          <span className="sr-only"> {current.message}</span>
        </p>
        <div className="queue-buttons">
          {navButton("previous-issue", "Previous issue", spot.group === 0, "queue-prev")}
          {navButton("next-issue", "Next issue", lastIssue, "queue-next")}
        </div>
      </div>
      {queue.total !== queue.groups.length ? (
        <p className="help queue-total">
          {fmt.format(queue.total)} findings in this pass; a finding repeated in the text counts as one issue.
        </p>
      ) : null}

      {group.items.length > 1 ? (
        <div className="queue-occurrences" role="group" aria-label="Occurrences of this issue" data-testid="queue-occurrences">
          <p className="queue-occ-line">
            Found {timesWord(group.items.length)} in your text.
          </p>
          <div className="queue-buttons">
            {navButton("previous-occurrence", "Previous", spot.occurrence === 0, "occ-prev", "Previous occurrence")}
            <span className="queue-occ-pos" data-testid="occ-position">
              {occ}
            </span>
            {navButton("next-occurrence", "Next", lastOccurrence, "occ-next", "Next occurrence")}
          </div>
        </div>
      ) : null}

      <div className="queue-card" key={current.id}>
        {renderCard(current)}
      </div>

      {lastIssue && lastOccurrence ? (
        <p className="queue-end" data-testid="queue-end">
          This is the last issue in this pass.{" "}
          {goOn ?? <span>Every pass with findings is done; the full list is under All suggestions.</span>}
        </p>
      ) : null}
      {lastIssue && lastOccurrence ? endExtra : null}

      <details className="queue-all" data-testid="queue-all">
        <summary>Every issue in this pass ({fmt.format(queue.groups.length)})</summary>
        <ol className="queue-list">
          {queue.groups.map((g, i) => (
            <li key={g.key}>
              <button
                type="button"
                className="btn-link queue-pick"
                aria-current={i === spot.group ? "step" : undefined}
                onClick={() => {
                  const pos = posAt(queue, { group: i, occurrence: 0 });
                  onMove(pos, g.items[0]!);
                }}
              >
                {g.label}
              </button>{" "}
              <span className="muted queue-times">{timesWord(g.items.length)}</span>
            </li>
          ))}
        </ol>
      </details>
    </section>
  );
}
